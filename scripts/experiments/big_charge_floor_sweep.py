"""Separate the two things `big_charge_sweep.py`'s winning `floor` family does at once.

    PYTHONPATH=. pixi run python scripts/experiments/big_charge_floor_sweep.py

`big_charge_sweep.py` reports `floor 0.3` as the only rule positive on all four folds
(+109,198 over 63 Games). Reading its `price()` shows the family is doing **two** things, not
one -- and the docstring does not say so:

    charge = charge_factor(sigma) * median
    if big:
        if family == "scale": charge *= param
        elif family == "floor": charge = max(charge, param * price_high)

The `floor` branch never applies the shipped `BIG_ITEM_CHARGE_SCALE` at all. So `floor f` is
"**drop the 1.25** *and* put a floor at `f * price_high`", and `floor 0.0` is exactly
`scale 1.0`. Its +109,198 is therefore not evidence for a floor; it is evidence for dropping
the multiplier, plus an unknown amount for the floor. This script splits them:

    scale k              charge = charge_factor(sigma) * median * k
    floor f              charge = max(charge_factor(sigma) * median,        f * price_high)
    scale+floor f        charge = max(charge_factor(sigma) * median * 1.25, f * price_high)

If the third family is flat against the shipped baseline while the second is strongly
positive, the whole effect is the multiplier and the floor is doing nothing. If the third is
positive too, the floor earns its place independently.

Why this matters more than the euros: Game 62 is a worked example of the mechanism. Line Item
1 settled at `t in [8505, 10350)`. `charge_factor(sigma) * median = 8,280` -- fair, and a fair
Charge is paid by **all sixteen** opponents whatever their Limits, because a wrongful
rejection still owes the issuer the full Charge. The 1.25 lifted it to 10,349.89, one step
over the ceiling, where only the 3 opponents who accepted paid anything. Income 31,050 where
132,480 was available; `error404 ai` Charged 8,504.71 on the same item and took 136,075, which
was 87% of their Game. The `crossings` column below counts exactly that event across the
record: Line Items whose Charge moves from one side of `t` to the other.

Both harnesses are reported. `big_charge_sweep_capped.py` establishes that enforcing
`c = max(4t, 2000)` changes nothing here -- the Cap can only bind on an *accepted* Overcharge,
and the reconstructed Field's Limits essentially never accept a Charge large enough -- so the
capped column is a control, not an expectation.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from charge_buckets import Row, dataset, snapshot  # noqa: E402
from replay_payoffs import replay  # noqa: E402

from src.pricing.engine import (  # noqa: E402
    BIG_ITEM_CHARGE_SCALE,
    BIG_ITEM_THRESHOLD,
    COVERAGE_FLOOR,
    LIMIT_CAP,
    LIMIT_CEILING,
    LIMIT_CEILING_MEMORY,
    LIMIT_QUANTILE,
    _lognormal_quantile,
    charge_factor,
    implied_sigma,
)

NOISE_FLOOR_18 = 26_622


def noise(n: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(max(n, 1) / 18.0)


def price(row: Row, *, family: str, param: float) -> tuple[float, float]:
    """The shipped `price_item`, with only the big-item Charge branch varied.

    The Limit arithmetic is copied verbatim from `engine.price_item` so that a Charge change
    cannot be credited with a Limit change; `min(limit, charge)` at the end preserves `b < a`.
    """
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    median = filled.price_median
    big = median >= BIG_ITEM_THRESHOLD
    memory = "B:memory" in row.channels
    covered = 0.0 if row.uncovered else filled.coverage_probability

    charge = charge_factor(sigma) * median
    if big:
        if family == "scale":
            charge *= param
        elif family == "floor":
            charge = max(charge, param * filled.price_high)
        elif family == "scale+floor":
            charge = max(charge * BIG_ITEM_CHARGE_SCALE, param * filled.price_high)
        else:  # pragma: no cover - programmer error
            raise ValueError(family)

    if covered <= COVERAGE_FLOOR:
        limit = 0.0
    else:
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        ceiling = LIMIT_CEILING_MEMORY if memory else LIMIT_CEILING
        candidates = [_lognormal_quantile(median, sigma, conditional), ceiling * median]
        if not memory:
            candidates.append(LIMIT_CAP)
        limit = min(candidates)
    return round(max(charge, 0.0), 2), round(max(min(limit, charge), 0.0), 2)


def net(rows, games, *, family: str, param: float) -> float:
    total = 0.0
    for game_id in games:
        sub = {r.index: price(r, family=family, param=param) for r in rows if r.game == game_id}
        if sub:
            total += replay(snapshot(game_id), sub).net
    return total


def crossings(rows, *, family: str, param: float) -> tuple[int, int, int]:
    """Line Items whose Charge crosses `t` against the shipped rule, and how many of those
    rest on an unbounded bracket -- `t_hi` empty means "worth at least `t_lo`", so a crossing
    counted there is the weakest kind of evidence and is reported separately rather than
    silently pooled."""
    to_over = to_fair = unbounded = 0
    for row in rows:
        base, _ = price(row, family="scale", param=BIG_ITEM_CHARGE_SCALE)
        trial, _ = price(row, family=family, param=param)
        if base == trial:
            continue
        t = row.t_lo if row.t_hi == float("inf") else (row.t_lo + row.t_hi) / 2.0
        was_fair, is_fair = base <= t, trial <= t
        if was_fair and not is_fair:
            to_over += 1
        elif is_fair and not was_fair:
            to_fair += 1
        else:
            continue
        if row.t_hi == float("inf"):
            unbounded += 1
    return to_over, to_fair, unbounded


def main() -> None:
    rows = dataset()
    games = sorted({r.game for r in rows})
    big = [r for r in rows if r.evidence.with_defaults().price_median >= BIG_ITEM_THRESHOLD]
    folds = {
        "all": games,
        "odd": [g for g in games if g % 2],
        "even": [g for g in games if not g % 2],
        "<=40": [g for g in games if g <= 40],
        ">40": [g for g in games if g > 40],
    }
    base = {n: net(rows, gs, family="scale", param=BIG_ITEM_CHARGE_SCALE) for n, gs in folds.items()}
    print(
        f"{len(games)} Games ({games[0]}-{games[-1]}), {len(rows)} Line Items, of which "
        f"{len(big)} are big (median >= {BIG_ITEM_THRESHOLD:,.0f}) and can move at all.\n"
        f"Noise floor +/-{noise(len(games)):,.0f} over the window, "
        f"+/-{noise(len(folds['odd'])):,.0f} within a half-fold -- so read a fold delta "
        f"smaller than that as flat, not as negative.\n"
        f"Delta against the shipped `scale {BIG_ITEM_CHARGE_SCALE}`.\n"
    )
    print(f"{'rule':<18}" + "".join(f"{k:>11}" for k in folds) + "  folds+   crossings")
    print("-" * (18 + 11 * len(folds) + 24))
    trials = (
        [("scale", k) for k in (0.9, 1.0, 1.1, 1.25)]
        + [("floor", f) for f in (0.0, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45)]
        + [("scale+floor", f) for f in (0.3, 0.4)]
    )
    for family, param in trials:
        cells = [net(rows, gs, family=family, param=param) - base[n] for n, gs in folds.items()]
        pos = sum(1 for c in cells[1:] if c > 0)
        to_over, to_fair, unbdd = crossings(rows, family=family, param=param)
        mark = "  <-- all 4" if pos == 4 else ""
        print(
            f"{family + ' ' + str(param):<18}"
            + "".join(f"{c:>+11,.0f}" for c in cells)
            + f"{pos:>5}/4  {to_fair:>2}->fair {to_over:>2}->over ({unbdd} unbdd){mark}"
        )
    print(f"\n{'(baseline net)':<18}" + "".join(f"{base[k]:>11,.0f}" for k in folds))


if __name__ == "__main__":
    main()
