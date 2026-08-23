"""Would the calibration layer have scored more? Leave-one-Game-out, against the real Field.

The measurement, and why it is honest
-------------------------------------
For every Game `g` with a decision log:

1. fit `src/pricing/calibration.Calibration` on the settled residuals of **every other Game**;
2. reprice `g`'s Line Items from the `t_hat` we really produced, through that calibration;
3. replay the resulting `(a, b)` against the Field's real Charges and Limits, scoring on the
   real payoff table and the recovered Fair Value brackets.

Step 1 is the whole point. A calibration fitted on all 100 Games and scored on all 100 Games
would be reporting how well a curve fits the points it was drawn through, which is the shape
of the eight experiments CLAUDE.md records as lost. Excluding `g` makes each Game's score a
genuine out-of-sample prediction, and `--check-loo` asserts the exclusion actually happened
rather than trusting the loop.

What is held fixed, and what that buys
--------------------------------------
`t_hat` is **not** re-derived; it is read from the decision log exactly as the live pipeline
produced it. No model is called, nothing is re-read, no prompt changes. So every euro of
difference is attributable to the calibration layer alone -- if this shows a gain, the gain is
in turning an asserted band into a measured one, and cannot be a better model call in disguise.

The Field is held fixed too, which is the standard caveat on every counterfactual in this
repository: sixteen opponents who saw us bid differently might have bid differently themselves.
For the Limit that objection is provably empty (our `b` cannot move their behaviour and, for
`a <= t`, our income does not depend on their `b` at all); for the Charge it is a real but
second-order effect, since no opponent could observe our Charge before setting their Limit.

Usage
-----
    PYTHONPATH=. python scripts/experiments/calibration_backtest.py
    PYTHONPATH=. python scripts/experiments/calibration_backtest.py --sweep
    PYTHONPATH=. python scripts/experiments/calibration_backtest.py --check-loo
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from replay_payoffs import US, our_actual_submission, reconstruction_status, replay, snapshot  # noqa: E402

from src.pricing.calibration import Calibration  # noqa: E402
from src.pricing.engine import Evidence, price_item  # noqa: E402

EXPORT = ROOT / "var" / "export" / "line_items.csv"
WEIGHTED = frozenset(range(81, 101))

#: Where the Charge and the Limit read the residual distribution. R4 puts the Limit at the
#: quantile the truth exceeds two times in three -- `q = 1/3` -- and R5b puts the Charge below
#: the estimate, near `0.7 t`. Both are *defaults to be measured*, which `--sweep` does.
CHARGE_Q = 0.30
LIMIT_Q = 1.0 / 3.0


def weight(game_id: int) -> float:
    return 3.0 if game_id in WEIGHTED else 1.0


def _f(row: dict, key: str) -> float | None:
    value = (row.get(key) or "").strip()
    if value in ("", "None"):
        return None
    if value == "inf":
        return math.inf
    try:
        return float(value)
    except ValueError:
        return None


def load_items() -> list[dict]:
    """Every logged Line Item, carrying the settled Fair Value **bracket**, not a point.

    `t_lo` and `t_hi` are passed through untouched, `t_hi` infinite where nobody rightfully
    rejected. Collapsing the bracket to a midpoint here is what the first version of this
    experiment did, and it discarded 189 of 531 usable observations -- the 189 on which we
    *underestimate*. `Calibration.fit` consumes the interval directly.
    """
    if not EXPORT.exists():
        raise SystemExit(f"{EXPORT} missing -- run `pixi run export` first")
    out = []
    for row in csv.DictReader(EXPORT.open()):
        t_hat = _f(row, "t_hat")
        if t_hat is None or t_hat <= 0:
            continue
        t_lo, t_hi = _f(row, "t_lo"), _f(row, "t_hi")
        out.append(
            {
                "game_id": int(row["game_id"]),
                "index": int(row["line_item_index"]),
                "t_hat": t_hat,
                "channels": row.get("channels") or "",
                "coverage_probability": _f(row, "coverage_probability"),
                "t_lo": t_lo,
                "t_hi": None if t_hi is None or t_hi == math.inf else t_hi,
            }
        )
    return out


def priced_by_calibration(
    item: dict, cal: Calibration, charge_q: float, limit_q: float
) -> tuple[float, float]:
    """`(a, b)` from the calibration layer, keeping the engine's coverage arithmetic.

    Only the *width* and the *centre* change hands. Coverage still collapses the Limit to zero
    below `COVERAGE_FLOOR` -- that is R6c and it is not what is being tested here -- and the
    Charge is still taken on an assumed-covered item, which is free (a rejected Overcharge on
    a worthless item costs nothing).
    """
    charge_point, limit_point = cal.band(item["t_hat"], item["channels"], (charge_q, limit_q))
    coverage = item["coverage_probability"]
    coverage = 0.9 if coverage is None else coverage
    # Reuse `price_item` purely for its coverage handling by handing it a degenerate band
    # centred on the calibrated Limit point; the Charge is taken directly.
    priced = price_item(
        Evidence(
            index=item["index"],
            coverage_probability=coverage,
            price_low=limit_point,
            price_median=limit_point,
            price_high=limit_point,
        )
    )
    limit = limit_point if priced.limit > 0 else 0.0
    return round(max(charge_point, 0.0), 2), round(max(limit, 0.0), 2)


def fit_loo(
    all_items: list[dict], game_ids: list[int], *, loo: bool = True, check: bool = False
) -> dict[int, Calibration]:
    """One leave-one-out `Calibration` per Game, fitted once and reused across every cell.

    The fit depends on the Game excluded and on nothing else -- not on the quantiles the
    sweep varies -- so refitting inside the sweep loop repeated the same Turnbull EM 42 times
    per Game for identical answers.
    """
    out: dict[int, Calibration] = {}
    for game_id in game_ids:
        training = [i for i in all_items if not (loo and i["game_id"] == game_id)]
        cal = Calibration.fit(training)
        if check and loo and game_id in cal.games:
            raise AssertionError(f"leave-one-out broken: G{game_id} is in its own training set")
        out[game_id] = cal
    return out


def score(
    items_by_game: dict[int, list[dict]],
    fits: dict[int, Calibration],
    game_ids: list[int],
    charge_q: float,
    limit_q: float,
) -> tuple[float, float, dict[int, float]]:
    """`(raw total, weighted total, per-Game net)` for the calibrated submission."""
    raw = weighted = 0.0
    per_game: dict[int, float] = {}
    for game_id in game_ids:
        cal = fits[game_id]
        snap = snapshot(game_id, US)
        submission = dict(our_actual_submission(snap))
        for item in items_by_game.get(game_id, []):
            if item["index"] in submission:
                submission[item["index"]] = priced_by_calibration(item, cal, charge_q, limit_q)
        net = replay(snap, submission).net
        per_game[game_id] = net
        raw += net
        weighted += net * weight(game_id)
    return raw, weighted, per_game


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", action="store_true", help="grid the two quantiles")
    parser.add_argument("--check-loo", action="store_true", help="assert the exclusion happened")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    all_items = load_items()
    fittable = [i for i in all_items if i["t_lo"] is not None and i["t_lo"] > 0]
    bounded = [i for i in fittable if i["t_hi"] is not None]
    items_by_game: dict[int, list[dict]] = defaultdict(list)
    for item in all_items:
        items_by_game[item["game_id"]].append(item)

    game_ids = sorted(
        g for g in items_by_game if reconstruction_status(g, US).usable
    )
    print(
        f"\n{len(all_items)} logged Line Items over {len(items_by_game)} Games; "
        f"{len(fittable)} train the calibration "
        f"({len(bounded)} bounded, {len(fittable) - len(bounded)} right-censored and KEPT).\n"
        f"Scoring {len(game_ids)} reconstructable Games.\n"
    )

    fits = fit_loo(fittable, game_ids, check=args.check_loo)

    baseline_raw = baseline_weighted = 0.0
    baseline_per_game: dict[int, float] = {}
    for game_id in game_ids:
        snap = snapshot(game_id, US)
        net = replay(snap, our_actual_submission(snap)).net
        baseline_per_game[game_id] = net
        baseline_raw += net
        baseline_weighted += net * weight(game_id)
    print(f"  {'BASELINE (what we really submitted)':<44}{baseline_raw:>14,.0f}{baseline_weighted:>16,.0f}")

    if args.sweep:
        print(f"\n  quantile sweep -- gain over baseline, weighted\n")
        charge_grid = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
        limit_grid = [0.20, 1 / 3, 0.45, 0.60, 0.75, 0.90]
        print("    " + "charge\\limit".ljust(14) + "".join(f"{q:>12.2f}" for q in limit_grid))
        best = None
        for cq in charge_grid:
            cells = []
            for lq in limit_grid:
                _, w, _ = score(items_by_game, fits, game_ids, cq, lq)
                cells.append(w - baseline_weighted)
                if best is None or w > best[2]:
                    best = (cq, lq, w)
            print(f"    {cq:<14.2f}" + "".join(f"{c:>12,.0f}" for c in cells))
        print(f"\n  best: charge_q={best[0]:.2f} limit_q={best[1]:.3f} "
              f"weighted {best[2]:,.0f} (gain {best[2] - baseline_weighted:,.0f})")
        return

    raw, weighted, per_game = score(items_by_game, fits, game_ids, CHARGE_Q, LIMIT_Q)
    print(f"  {f'CALIBRATED (LOO, charge_q={CHARGE_Q}, limit_q={LIMIT_Q:.3f})':<44}"
          f"{raw:>14,.0f}{weighted:>16,.0f}")
    print(f"  {'GAIN':<44}{raw - baseline_raw:>14,.0f}{weighted - baseline_weighted:>16,.0f}")

    folds = {
        "odd ids": [g for g in game_ids if g % 2],
        "even ids": [g for g in game_ids if not g % 2],
        "dark 44-81": [g for g in game_ids if 44 <= g <= 81],
        "recal 82-100": [g for g in game_ids if g >= 82],
        "first half": [g for g in game_ids if g <= 62],
        "last half": [g for g in game_ids if g > 62],
    }
    print(f"\n  {'fold':<16}{'n':>5}{'baseline':>14}{'calibrated':>14}{'gain':>13}")
    for name, ids in folds.items():
        base = sum(baseline_per_game[g] * weight(g) for g in ids)
        got = sum(per_game[g] * weight(g) for g in ids)
        print(f"  {name:<16}{len(ids):>5}{base:>14,.0f}{got:>14,.0f}{got - base:>13,.0f}")

    delta = {g: (per_game[g] - baseline_per_game[g]) * weight(g) for g in game_ids}
    up = sum(1 for v in delta.values() if v > 0.01)
    down = sum(1 for v in delta.values() if v < -0.01)
    hero = max(delta, key=lambda g: delta[g])
    print(
        f"\n  Games improved {up}   worsened {down}   unchanged {len(delta) - up - down}\n"
        f"  biggest single contributor G{hero} at {delta[hero]:,.0f}"
        f"   -> without it, gain {weighted - baseline_weighted - delta[hero]:,.0f}"
    )

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "baseline_weighted": round(baseline_weighted, 2),
                    "calibrated_weighted": round(weighted, 2),
                    "per_game": {str(g): round(delta[g], 2) for g in sorted(delta)},
                },
                indent=1,
            )
            + "\n"
        )
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
