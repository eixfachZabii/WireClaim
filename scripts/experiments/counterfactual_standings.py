"""If we had run the finished strategy from Game 1, where would everyone have finished?

Why our net is not enough
-------------------------
Every counterfactual in this repository so far reports **our** net. That is the wrong number for
a question about placement, because the tournament is not seventeen independent scores: every
euro we are paid is a euro some opponent pays, and every claim we accept is income for the team
that issued it. Bidding differently moves the whole table.

    we Charge closer to `t`   -> our income rises AND sixteen opponents' costs rise
    we accept more claims     -> our costs rise AND sixteen opponents' income rises

The first effect is doubly good for our rank; the second is a straight transfer that *helps*
everyone we pay. A counterfactual that only re-scores our row silently assumes the second effect
away and will overstate how far we climb.

So this recomputes all seventeen rows. Only the pairs that involve us can change -- an
opponent's fixtures against the other fifteen are untouched by anything we do -- which gives an
exact decomposition:

    net(T, counterfactual) = net(T, actual)
                           - [T's pairs against us, as they really settled]
                           + [T's pairs against us, under our new submission]

`net(T, actual)` comes from `data/tournament/per_game_net.csv`, which reproduces the published
leaderboard to the cent for all seventeen teams. The two bracketed terms are computed from the
same payoff table and the same reconstructed Fair Value brackets as everything else.

The self-check that makes it worth reading
------------------------------------------
`--validate` computes the "as they really settled" term two independent ways -- through the
replay model, and directly from the settled Transaction rows -- and reports the disagreement.
They must match, because the subtraction is only legitimate if the model is faithful on exactly
those cross terms. Anything else is a counterfactual built on a bookkeeping error.

The arms
--------
`ACTUAL`
    What we really submitted. Must reproduce the real standings exactly; the first row of the
    output is a test, not a result.

`WARM-STORE`
    The finished Price Memory, leave-one-Game-out, pricing every Line Item it can answer;
    our real submission everywhere else. **No assumptions at all** -- this is the pure value of
    having shipped the store on day one, and it is a *lower* bound on the finished pipeline
    because on a miss it keeps whatever we really did, including the Games where we Charged
    nothing at all.

`FULL-PIPELINE`
    The finished pipeline run from Game 1. Games 26-100 already have the mature model channel,
    so a miss there keeps our real submission and nothing is invented. Games 1-25 have no model
    reading at all, so a miss is priced by a *simulated* channel drawn from the residual the
    model really produced later (`src/pricing/calibration.py`, `C:model` stratum). This is the
    only arm with a synthetic component and it is marked as such wherever it is reported.
    Averaged over `--trials` seeds.

`NO-BLANKS`
    Neither of the above, isolated: our real submission with only its two *failures* repaired --
    a Charge of zero, and a Charge so far above the Field that no reviewer's Limit reached it.
    Both are Games where the pipeline produced nothing usable rather than something inaccurate.

Usage
-----
    PYTHONPATH=. python scripts/experiments/counterfactual_standings.py --validate
    PYTHONPATH=. python scripts/experiments/counterfactual_standings.py --trials 5
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))

from memory_first import CHARGE_FACTOR, build_predictions  # noqa: E402
from pull_transactions import transactions  # noqa: E402
from replay_payoffs import (  # noqa: E402
    US,
    issuer_payoff,
    our_actual_submission,
    reconstruction_status,
    reviewer_payoff,
    snapshot,
)

from src.pricing.calibration import Calibration  # noqa: E402

INF = math.inf
WEIGHTED = frozenset(range(81, 101))
STANDINGS = ROOT / "data" / "tournament" / "per_game_net.csv"
EXPORT = ROOT / "var" / "export" / "line_items.csv"

#: The Limit multiplier the walk-forward sweep picked (`blend_weight_sweep.py`): b = 1.0 x the
#: estimate. Paired with `CHARGE_FACTOR = 0.69` from R5b, these are the shipped rules, not new
#: knobs -- this experiment changes the *estimate*, never the arithmetic over it.
LIMIT_FACTOR = 1.0


def weight(game_id: int) -> float:
    return 3.0 if game_id in WEIGHTED else 1.0


# ------------------------------------------------------------------ real standings


def real_per_game() -> dict[str, dict[int, float]]:
    """`{team: {game: unweighted net}}` from the verified archive."""
    if not STANDINGS.exists():
        raise SystemExit(f"{STANDINGS} missing -- run `pixi run archive` first")
    rows = list(csv.reader(STANDINGS.open()))
    header, body = rows[0], rows[1:]
    teams = header[3:]
    table: dict[str, dict[int, float]] = {t: {} for t in teams}
    for row in body:
        game_id = int(row[0])
        for team, value in zip(teams, row[3:]):
            table[team][game_id] = float(value)
    return table


# ------------------------------------------------------------- the cross terms


def cross_terms(snap, submission) -> dict[str, float]:
    """`{team: net that team takes from its fixtures against us}` under our `submission`.

    Both directions, for every Line Item:

        T issues to us   -> T receives `issuer_payoff(a_T, b_us, t)`
        T reviews us     -> T pays     `reviewer_payoff(a_us, b_T, t)`
    """
    out: dict[str, float] = defaultdict(float)
    for index in snap.line_items:
        charge, limit = submission.get(index, (0.0, 0.0))
        t = snap.fair_point(index)
        for team in snap.opponents:
            their_charge = snap.charges[index][team]
            their_limit = snap.limit_point(index, team)
            out[team] += issuer_payoff(their_charge, limit, t)
            out[team] -= reviewer_payoff(charge, their_limit, t)
    return out


def our_net(snap, submission) -> float:
    total = 0.0
    for index in snap.line_items:
        charge, limit = submission.get(index, (0.0, 0.0))
        t = snap.fair_point(index)
        for team in snap.opponents:
            total += issuer_payoff(charge, snap.limit_point(index, team), t)
            total -= reviewer_payoff(snap.charges[index][team], limit, t)
    return total


def cross_terms_from_rows(game_id: int) -> dict[str, float]:
    """The same quantity, straight from the settled Transactions. The independent check."""
    out: dict[str, float] = defaultdict(float)
    for row in transactions(US, game_id):
        amount = float(row["amount"])
        if row["issuer"] != US and row["reviewer"] == US:
            out[row["issuer"]] += amount
        elif row["issuer"] == US and row["reviewer"] != US:
            out[row["reviewer"]] -= amount if row["accepted"] else 1.5 * amount
    return out


# ----------------------------------------------------------------------- the arms


def arm_actual(snap, _predictions, _rng, _cal):
    return our_actual_submission(snap)


def _from_anchor(anchor: float) -> tuple[float, float]:
    return (CHARGE_FACTOR * anchor, LIMIT_FACTOR * anchor)


def arm_warm_store(snap, predictions, _rng, _cal):
    mine = our_actual_submission(snap)
    hits = predictions.get(snap.game_id, {})
    return {
        index: (_from_anchor(hits[index]) if index in hits else mine[index])
        for index in snap.line_items
    }


#: The decision log -- and therefore the mature pipeline -- starts here. Before it, no model
#: reading exists for any Line Item and none can be recovered without re-running the model over
#: Cases 1-25.
MATURE_FROM = 26


def arm_full_pipeline(snap, predictions, rng, cal):
    """The finished pipeline run from Game 1: warm store everywhere, model on the misses.

    The two halves are treated differently on purpose, because only one of them needs a
    simulation:

    * **Games 26-100** already *have* the mature model channel -- it is what we really ran. A
      miss keeps our real submission, so nothing here is invented.
    * **Games 1-25** have no model reading at all. A miss is priced by drawing `r = log(t /
      t_hat)` from the `C:model` stratum of the censoring-aware fit, so the simulated channel
      makes the error the model really made later on, skew and fat left tail included -- neither
      of which a lognormal would carry.

    An earlier version applied the draw across all 100 Games and scored *worse* than keeping our
    real submission (346,235 against 617,298 over Games 26-100). That was not a finding about
    the model, it was the arm overwriting a real estimator with a random draw from its own error
    distribution; a single draw is worse than the thing it is drawn from.
    """
    mine = our_actual_submission(snap)
    hits = predictions.get(snap.game_id, {})
    out = {}
    for index in snap.line_items:
        if index in hits:
            out[index] = _from_anchor(hits[index])
            continue
        t = snap.fair_point(index)
        if snap.game_id >= MATURE_FROM or t <= 0:
            out[index] = mine[index]
            continue
        stratum = cal.resolve(t, "C:model")
        residual = stratum.quantile(rng.random()) if stratum.n else 0.0
        out[index] = _from_anchor(t * math.exp(-residual))
    return out


def arm_no_blanks(snap, _predictions, _rng, _cal):
    """Our real submission with only its blanks repaired -- no better estimate anywhere.

    Two failures, both of which produce *zero* income rather than inaccurate income:

    * a Charge of exactly 0 (Games 2, 3, 11, 12 -- 22 of 22 Line Items in Game 11)
    * a Charge no reviewer's Limit reached, so no row reveals it (27 of 39 in Game 8)

    Both are replaced by the Field's own median Charge on that Line Item, which is the most
    conservative plausible number available and needs no model: it is what the other sixteen
    teams, reading the same invoice, thought the item was worth.
    """
    mine = our_actual_submission(snap)
    out = {}
    for index in snap.line_items:
        charge, limit = mine[index]
        broken = (not math.isfinite(charge)) or charge <= 0.0
        if not broken:
            out[index] = (charge, limit)
            continue
        field = sorted(
            c for team, c in snap.charges[index].items()
            if team != US and math.isfinite(c) and c > 0
        )
        if not field:
            out[index] = (charge if math.isfinite(charge) else 0.0, limit)
            continue
        anchor = field[len(field) // 2]
        out[index] = (anchor, max(limit, anchor))
    return out


ARMS = {
    "ACTUAL": arm_actual,
    "NO-BLANKS": arm_no_blanks,
    "WARM-STORE": arm_warm_store,
    "FULL-PIPELINE": arm_full_pipeline,
}
SYNTHETIC = {"FULL-PIPELINE"}


# -------------------------------------------------------------------- evaluation


def standings_for(snaps, predictions, real, arm, cal, *, trials: int, seed: int):
    """`{team: weighted total}` under one arm, plus our per-Game net."""
    teams = list(real)
    totals = {t: 0.0 for t in teams}
    per_game: dict[int, float] = {}
    runs = trials if arm in SYNTHETIC else 1

    for snap in snaps:
        w = weight(snap.game_id)
        real_cross = cross_terms(snap, our_actual_submission(snap))
        ours = 0.0
        agg: dict[str, float] = defaultdict(float)
        for trial in range(runs):
            rng = random.Random(seed + trial * 7919 + snap.game_id)
            submission = ARMS[arm](snap, predictions, rng, cal)
            ours += our_net(snap, submission)
            for team, value in cross_terms(snap, submission).items():
                agg[team] += value
        ours /= runs
        per_game[snap.game_id] = ours
        totals[US] += ours * w
        for team in teams:
            if team == US:
                continue
            new = agg[team] / runs
            totals[team] += (real[team][snap.game_id] - real_cross[team] + new) * w

    # Games we cannot reconstruct keep their real result for everyone, us included.
    played = {s.game_id for s in snaps}
    for team in teams:
        for game_id, value in real[team].items():
            if game_id not in played:
                totals[team] += value * weight(game_id)
    return totals, per_game


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    real = real_per_game()
    snaps = [snapshot(g, US) for g in range(1, 101) if reconstruction_status(g, US).usable]
    print(f"\n{len(snaps)} reconstructable Games, {len(real)} teams")

    if args.validate:
        print("\nVALIDATION -- the cross terms, two independent ways")
        worst = 0.0
        for snap in snaps:
            model = cross_terms(snap, our_actual_submission(snap))
            rows = cross_terms_from_rows(snap.game_id)
            for team in set(model) | set(rows):
                worst = max(worst, abs(model.get(team, 0.0) - rows.get(team, 0.0)))
        print(f"  worst disagreement across every (Game, team): {worst:,.4f}")
        print("  " + ("OK -- the subtraction is legitimate" if worst < 0.02
                      else "FAIL -- do not trust anything below"))
        if worst >= 0.02:
            sys.exit(1)

    print("\nBuilding leave-one-Game-out Price Memory...")
    predictions = build_predictions(list(range(1, 101)), "loo")

    # The model channel's own measured residual, for the synthetic arm only.
    fit_rows = []
    if EXPORT.exists():
        for row in csv.DictReader(EXPORT.open()):
            try:
                t_hat = float(row["t_hat"])
                t_lo = float(row["t_lo"])
            except (TypeError, ValueError):
                continue
            t_hi = row.get("t_hi", "")
            fit_rows.append({
                "game_id": int(row["game_id"]),
                "t_hat": t_hat,
                "t_lo": t_lo,
                "t_hi": None if t_hi in ("", "inf", "None") else float(t_hi),
                "channels": row.get("channels") or "",
            })
    cal = Calibration.fit(fit_rows)

    results = {}
    for arm in ARMS:
        totals, per_game = standings_for(
            snaps, predictions, real, arm, cal, trials=args.trials, seed=args.seed
        )
        results[arm] = (totals, per_game)

    # ---- our own line, and the early/late split the whole question is about
    print(f"\n{'=' * 82}\nOUR NET, AND WHERE IT COMES FROM\n{'=' * 82}")
    print(f"  {'arm':<20}{'weighted':>14}{'Games 1-25':>14}{'Games 26-100':>15}{'rank':>7}")
    print(f"  {'-' * 20:<20}{'-' * 14:>14}{'-' * 14:>14}{'-' * 15:>15}{'-' * 7:>7}")
    for arm, (totals, per_game) in results.items():
        early = sum(v * weight(g) for g, v in per_game.items() if g <= 25)
        late = sum(v * weight(g) for g, v in per_game.items() if g > 25)
        order = sorted(totals, key=lambda t: -totals[t])
        rank = order.index(US) + 1
        tag = " *" if arm in SYNTHETIC else ""
        print(
            f"  {arm + tag:<20}{totals[US]:>14,.0f}{early:>14,.0f}{late:>15,.0f}{rank:>7}"
        )
    print("\n  * contains a simulated model channel for the Line Items Price Memory misses.")

    # ---- the full table
    for arm, (totals, _) in results.items():
        order = sorted(totals, key=lambda t: -totals[t])
        print(f"\n{'-' * 82}\n{arm} -- full standings, every team's net recomputed\n{'-' * 82}")
        print(f"  {'#':>3}  {'team':<24}{'net':>16}{'vs actual':>16}{'moved':>8}")
        actual_totals = results["ACTUAL"][0]
        actual_order = sorted(actual_totals, key=lambda t: -actual_totals[t])
        for rank, team in enumerate(order, start=1):
            was = actual_order.index(team) + 1
            delta = totals[team] - actual_totals[team]
            moved = "-" if was == rank else f"{was}->{rank}"
            mark = "  <- us" if team == US else ""
            print(
                f"  {rank:>3}  {team:<24}{totals[team]:>16,.0f}{delta:>16,.0f}{moved:>8}{mark}"
            )

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    arm: {
                        "totals": {t: round(v, 2) for t, v in totals.items()},
                        "our_per_game": {str(g): round(v, 2) for g, v in sorted(pg.items())},
                    }
                    for arm, (totals, pg) in results.items()
                },
                indent=1,
            )
            + "\n"
        )
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
