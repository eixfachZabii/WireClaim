"""How should two readings of the same Line Item be combined -- and is the spread a signal?

`strategy2._blend` averages the ensemble in log space and adds the between-draw spread to
the model's own claimed width in quadrature. Both halves of that are choices, and the payoff
table is asymmetric enough that the obvious choice need not be the right one: income is `a`
whenever `a <= t` and collapses by ~80% above it, so an aggregator that leans *low* is not
obviously worse than one that centres.

This scores the aggregators against the real Field, and separately asks the prior question:
does the between-draw spread predict the actual log error at all? If it does not, the
quadrature term in `_blend` is decoration.

    pixi run python scripts/experiments/level_blend.py --games 1-24 --tags model,nohint --spread

## The shipped aggregator wins, and the width term inside it is decoration

Games 1-24, blended two-draw ensemble:

    rule                                   net      delta
    ------------------------------- ---------- ----------
    shipped (log mean, quadrature)     127,292          0
    asserted sigma only                118,816     -8,476
    between-draw spread only            91,633    -35,659
    min of the draws                    70,857    -56,435
    max of the draws                    76,348    -50,944
    log mean - 0.25 * spread           108,970    -18,322
    log mean + 0.50 * spread           127,532       +240

The payoff table is asymmetric, so leaning below the centre looks free; it is not. Both
`min` and `shade +1.00` (the same thing on two draws) cost 56,435, because a Charge dragged
below `t` forfeits the difference from all sixteen opponents while gaining nothing.

**The disagreement between framings does not predict the error.** Correlation of the
between-draw spread with the realised `|log(t_hat/t)|` is **+0.036** over 213 items, and the
ordering by thirds runs backwards (median error 0.57 in the narrow third against 0.46 in the
wide third). So the quadrature term in `blend` is not the width signal it was sold as.
Removing it still costs 8,476, though, which is inside the noise floor and in the direction
of a higher Charge -- so it stays, as a guard rather than as a measurement.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from level_compat import (  # noqa: E402
    case_of,
    load_evidence,
    parse_games,
    sigma_of,
    submission_of,
)
from replay_payoffs import replay, snapshot  # noqa: E402

from src.domain.pricing.engine import Evidence  # noqa: E402

BAND_Z = 1.645


def _band(index: int, seen: list[Evidence], median: float, sigma: float) -> Evidence:
    return Evidence(
        index=index,
        coverage_probability=sum(e.coverage_probability for e in seen) / len(seen),
        price_low=median * math.exp(-BAND_Z * sigma),
        price_median=median,
        price_high=median * math.exp(BAND_Z * sigma),
    )


def blend(draws: list[dict[int, Evidence]], rule: str, shade: float = 0.0) -> dict[int, Evidence]:
    """Aggregate the draws under one rule. `shade` multiplies the between-draw spread."""
    usable = [d for d in draws if d]
    if not usable:
        return {}
    out: dict[int, Evidence] = {}
    for index in set().union(*(set(d) for d in usable)):
        seen = [d[index] for d in usable if index in d]
        priced = [e for e in seen if e.price_median > 0]
        if not priced:
            out[index] = seen[0]
            continue
        logs = [math.log(e.price_median) for e in priced]
        mean_log = sum(logs) / len(logs)
        own = sum(sigma_of(e) for e in priced) / len(priced)
        spread = math.sqrt(sum((v - mean_log) ** 2 for v in logs) / len(logs))
        if rule == "shipped":
            median, sigma = math.exp(mean_log), math.sqrt(own**2 + spread**2)
        elif rule == "own-sigma":
            median, sigma = math.exp(mean_log), own
        elif rule == "spread-sigma":
            median, sigma = math.exp(mean_log), max(spread, 0.1)
        elif rule == "min":
            median, sigma = math.exp(min(logs)), math.sqrt(own**2 + spread**2)
        elif rule == "max":
            median, sigma = math.exp(max(logs)), math.sqrt(own**2 + spread**2)
        elif rule == "shade":
            # Lean below the centre by a multiple of the disagreement we observed.
            median = math.exp(mean_log - shade * spread)
            sigma = math.sqrt(own**2 + spread**2)
        else:
            raise SystemExit(f"unknown rule {rule}")
        out[index] = _band(index, seen, median, sigma)
    return out


def spread_report(loaded: list[tuple], draws_by_game: dict[int, list[dict]]) -> None:
    """Is the between-draw spread correlated with the realised log error?"""
    rows: list[tuple[float, float]] = []
    for snap, _case, model in loaded:
        draws = draws_by_game[snap.game_id]
        for index, ev in model.items():
            if index not in snap.fair_brackets or ev.price_median <= 0:
                continue
            t = snap.fair_point(index)
            logs = [
                math.log(d[index].price_median)
                for d in draws
                if index in d and d[index].price_median > 0
            ]
            if t <= 0 or len(logs) < 2:
                continue
            mean_log = sum(logs) / len(logs)
            spread = math.sqrt(sum((v - mean_log) ** 2 for v in logs) / len(logs))
            rows.append((spread, abs(math.log(ev.price_median / t))))
    n = len(rows)
    mean_x = sum(x for x, _ in rows) / n
    mean_y = sum(y for _, y in rows) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in rows) / n
    sx = math.sqrt(sum((x - mean_x) ** 2 for x, _ in rows) / n)
    sy = math.sqrt(sum((y - mean_y) ** 2 for _, y in rows) / n)
    print(f"\nspread vs |log error| over {n} items: corr {cov / (sx * sy):+.3f}")
    ordered = sorted(rows)
    third = n // 3
    for label, chunk in (
        ("narrow third", ordered[:third]),
        ("middle third", ordered[third : 2 * third]),
        ("wide third", ordered[2 * third :]),
    ):
        print(
            f"  {label:>13}: median spread {statistics.median([x for x, _ in chunk]):.2f}"
            f"   median |log error| {statistics.median([y for _, y in chunk]):.2f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-24")
    parser.add_argument("--tags", default="model,nohint")
    parser.add_argument("--spread", action="store_true")
    args = parser.parse_args()

    tags = args.tags.split(",")
    entries = []
    draws_by_game: dict[int, list[dict]] = {}
    for game_id in parse_games(args.games):
        draws = [load_evidence(game_id, tag) or {} for tag in tags]
        case = case_of(game_id)
        if not any(draws) or case is None:
            continue
        try:
            snap = snapshot(game_id)
        except Exception:  # pragma: no cover
            continue
        entries.append((snap, case, draws))
        draws_by_game[game_id] = draws
    print(f"{len(entries)} Games, tags {tags}")

    def total(rule: str, shade: float = 0.0) -> float:
        return sum(
            replay(snap, submission_of(case, blend(draws, rule, shade))).net
            for snap, case, draws in entries
        )

    baseline = total("shipped")
    print(f"\n{'rule':>14} {'net':>14} {'delta':>12}")
    print(f"{'shipped':>14} {baseline:14,.0f} {0.0:12,.0f}")
    for rule in ("own-sigma", "spread-sigma", "min", "max"):
        net = total(rule)
        print(f"{rule:>14} {net:14,.0f} {net - baseline:12,.0f}")
    for shade in (0.25, 0.5, 1.0, -0.5):
        net = total("shade", shade)
        print(f"{'shade ' + format(shade, '+.2f'):>14} {net:14,.0f} {net - baseline:12,.0f}")

    if args.spread:
        loaded = [(snap, case, blend(draws, "shipped")) for snap, case, draws in entries]
        spread_report(loaded, draws_by_game)


if __name__ == "__main__":
    main()
