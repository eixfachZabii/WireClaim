"""Is the model's price level correctable by a deterministic map, and is it worth euros?

`tail_diagnose.py` reports the level error conditioned on the *true* Fair Value: median
`t_hat / t` is 4.41 on items worth under 50 EUR and 0.90 on items worth over 1,000. That
table is real but it is not directly actionable, because conditioning on `t` manufactures
regression-to-the-mean in whichever direction you look. A correction has to be conditioned
on what we can observe at submission time, which is `t_hat`.

So this script does three separate things, in that order:

1. **The same diagnosis both ways round.** `--table` prints median `t_hat / t` bucketed by
   true `t` *and* bucketed by `t_hat`. The two disagree in direction, which is the whole
   point: conditioned on `t_hat`, the cheap predictions are the ones that are too *low*.
2. **The fit, conditioned on `t_hat`.** Weighted least squares of `log t` on `log t_hat`,
   euro-weighted, over the recovered Fair Values. This is the minimum-log-error map, not
   the maximum-euro one -- it is printed so the two can be compared.
3. **The euro sweep and a held-out check.** Every candidate `(c0, c1)` is applied to the
   blended ensemble evidence, repriced through the shipped `src/domain/pricing/engine.py`, and scored with
   `replay_payoffs.replay` against the real Field. `--holdout` refits/reselects on a subset
   of Games and reports the score on the Games it never saw.

    pixi run python scripts/experiments/level_fit.py --games 1-24 --table
    pixi run python scripts/experiments/level_fit.py --games 1-24 --sweep
    pixi run python scripts/experiments/level_fit.py --games 1-24 --holdout even
    pixi run python scripts/experiments/level_fit.py --games 1-24 --sweep --tag model,nohint2

Price Memory stays off throughout: it contains the very Games this replays.

## The answer: there is no such map. Do not ship one.

**The diagnosis inverts with what you condition on, and the two directions contradict each
other.** Games 1-24, 235 Line Items with a recovered `t > 0`, blended two-draw ensemble:

    bucket      n (by t / by t_hat)   median t_hat/t by true t   median t_hat/t by t_hat
    ----------  --------------------  -------------------------  -----------------------
    < 50               42 / 21                  6.01                     0.46
    50-150             84 / 60                  1.40                     1.04
    150-400            53 / 80                  0.97                     1.61
    400-1000           42 / 46                  1.03                     1.44
    > 1000             14 / 28                  1.17                     1.95

Conditioned on the truth we look 6x too *high* on cheap items; conditioned on our own
estimate we are 2x too *low* on exactly the same kind of item. Each column is a regression
artefact of its own conditioning variable and they point opposite ways, so **either table
alone justifies a correction that the other calls backwards.** The euro-weighted fit
conditioned on `t_hat` -- the only direction that can be applied at submission time -- is

    log t = 0.889 + 0.849 * log t_hat      residual sigma 1.29

i.e. gamma < 1, the *shrinking* direction, the opposite of "un-shrink the estimator".

**Applied, that fit loses money.** In-sample over all 24 Games: 127,292 -> 72,579, a delta
of **-54,713**, and it loses on 15 of the 24 Games (-18,107 on Game 17, -13,776 on Game 10).

**The whole family is worse than doing nothing.** Sweeping `t_hat' = exp(c0) * t_hat**c1`
over five pivots x nine exponents, the argmax of all 45 cells is `c1 = 1.00` -- the identity,
which is the shipped code. The gradient away from it is steep (-178,105 at the corner).
Held out three ways, and it never once wins:

    fold                                      shipped    recalibrated      delta
    train odd Games,  test even Games          44,668          30,565    -14,104
    train even Games, test odd Games           82,624          82,624          0   (picks c1 = 1)
    train Games 1-12, test Games 13-24        103,934         -79,114   -183,048

The three folds pick exponents 0.95, 1.00 and 1.20 -- they do not even agree on the sign of
the correction. And on a second ensemble draw (`--tag model,nohint2`) the best in-sample
cell gains +16,346 while that same cell *loses* 11,722 on the first draw, which is what the
26,622 noise floor looks like from the inside.

So the level is left exactly as the model returns it, and the reason is not that nobody
tried: a monotone function of `t_hat` cannot repair an error that is item-specific. `--oracle`
sizes what is actually there -- 127,292 shipped, **228,987** with every median moved to its
own true `t` and the band and coverage untouched, 811,569 charging and accepting at `t`. That
+101,695 is item accuracy, and no reparameterisation of `t_hat` recovers any part of it.

`level_units.py`, `level_width.py`, `level_blend.py`, `level_anchors.py`,
`level_prompt_anchors.py` and `level_memory.py` close off the six neighbouring ideas: the
invoice unit, the band width, the aggregator over draws, per-trade multipliers, the prompt's
own price anchors and the model/memory weighting. All measured in euros, all negative or
inside the noise floor.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from replay_payoffs import replay, snapshot  # noqa: E402
from level_compat import (  # noqa: E402
    blend,
    case_of,
    inflate,
    load_evidence,
    parse_games,
    submission_of,
)

from src.domain.pricing.engine import Evidence  # noqa: E402

BAND_Z = 1.645


# ------------------------------------------------------------------------------ loading


def load(games: list[int], tag: str, tail_factor: float = 1.0) -> list[tuple]:
    """`(snapshot, case, blended evidence)` per Game, using the Strategy's own `_blend`."""
    loaded = []
    for game_id in games:
        model = blend([load_evidence(game_id, one) or {} for one in tag.split(",")])
        case = case_of(game_id)
        if not model or case is None:
            continue
        try:
            snap = inflate(snapshot(game_id), tail_factor)
        except Exception as error:  # pragma: no cover - offline / unsettled Game
            print(f"  g{game_id}: no snapshot ({error})", file=sys.stderr)
            continue
        loaded.append((snap, case, model))
    return loaded


def pairs(loaded: list[tuple]) -> list[tuple[float, float]]:
    """`(t, t_hat)` for every Line Item with a positive recovered Fair Value."""
    out: list[tuple[float, float]] = []
    for snap, _case, model in loaded:
        for index, ev in model.items():
            if index not in snap.fair_brackets or ev.price_median <= 0:
                continue
            t = snap.fair_point(index)
            if t > 0:
                out.append((t, ev.price_median))
    return out


# --------------------------------------------------------------------------- diagnosis


BUCKETS = ((0, 50), (50, 150), (150, 400), (400, 1000), (1000, math.inf))


def table(rows: list[tuple[float, float]], by: str) -> None:
    """Median `t_hat / t` and the under-priced share, bucketed by `t` or by `t_hat`."""
    print(f"\nbucketed by {'true t' if by == 't' else 't_hat'}:")
    print(f"{'bucket':>14} {'n':>4} {'median t_hat/t':>15} {'under-priced':>13}")
    for lo, hi in BUCKETS:
        chosen = [(t, m) for t, m in rows if lo <= (t if by == "t" else m) < hi]
        if not chosen:
            continue
        ratios = [m / t for t, m in chosen]
        under = sum(1 for r in ratios if r < 1.0) / len(ratios)
        label = f"{lo:.0f}-{'inf' if hi == math.inf else f'{hi:.0f}'}"
        print(f"{label:>14} {len(chosen):4d} {statistics.median(ratios):15.2f} {under:12.0%}")


def fit(rows: list[tuple[float, float]], weight: str = "euro") -> tuple[float, float]:
    """WLS of `log t` on `log t_hat`. Returns `(c0, c1)` -- the map, conditioned on t_hat."""
    weights = [t if weight == "euro" else 1.0 for t, _ in rows]
    total = sum(weights)
    mean_x = sum(w * math.log(m) for w, (_, m) in zip(weights, rows)) / total
    mean_y = sum(w * math.log(t) for w, (t, _) in zip(weights, rows)) / total
    cov = sum(
        w * (math.log(m) - mean_x) * (math.log(t) - mean_y) for w, (t, m) in zip(weights, rows)
    ) / total
    var = sum(w * (math.log(m) - mean_x) ** 2 for w, (_, m) in zip(weights, rows)) / total
    c1 = cov / var if var > 0 else 1.0
    return mean_y - c1 * mean_x, c1


def residual_sigma(rows: list[tuple[float, float]], c0: float, c1: float) -> float:
    """RMS of `log t - (c0 + c1 log t_hat)`: what the band *should* be claiming."""
    errors = [math.log(t) - (c0 + c1 * math.log(m)) for t, m in rows]
    return math.sqrt(sum(e * e for e in errors) / len(errors))


# ----------------------------------------------------------------------------- scoring


def recalibrate(ev: Evidence, c0: float, c1: float, sigma_floor: float = 0.0) -> Evidence:
    """`t_hat' = exp(c0 + c1 * log t_hat)`, band width preserved (or floored)."""
    if ev.price_median <= 0:
        return ev
    median = math.exp(c0 + c1 * math.log(ev.price_median))
    sigma = 1.0
    if ev.price_low > 0 and ev.price_high > ev.price_low:
        sigma = math.log(ev.price_high / ev.price_low) / (2 * BAND_Z)
    sigma = max(sigma, sigma_floor)
    return Evidence(
        index=ev.index,
        coverage_probability=ev.coverage_probability,
        price_low=median * math.exp(-BAND_Z * sigma),
        price_median=median,
        price_high=median * math.exp(BAND_Z * sigma),
    )


def nets(loaded: list[tuple], c0: float, c1: float, sigma_floor: float = 0.0) -> dict[int, float]:
    """Net per Game under one candidate map, priced by the shipped `src/domain/pricing/engine.py`."""
    out: dict[int, float] = {}
    for snap, case, model in loaded:
        adjusted = {i: recalibrate(ev, c0, c1, sigma_floor) for i, ev in model.items()}
        out[snap.game_id] = replay(snap, submission_of(case, adjusted)).net
    return out


def total(loaded: list[tuple], c0: float, c1: float, sigma_floor: float = 0.0) -> float:
    return sum(nets(loaded, c0, c1, sigma_floor).values())


def oracle_totals(loaded: list[tuple]) -> dict[str, float]:
    """What perfect item-level accuracy is worth, as the ceiling every candidate is judged by.

    `oracle-median` keeps the model's band width and its coverage probability and moves only
    the median to the recovered `t`, so it isolates exactly the quantity a recalibration map
    is trying to fix. `oracle` charges and accepts at `t` outright.
    """
    shipped = median_moved = both = 0.0
    for snap, case, model in loaded:
        adjusted: dict[int, Evidence] = {}
        for index, ev in model.items():
            t = snap.fair_point(index) if index in snap.fair_brackets else 0.0
            scale = t / ev.price_median if ev.price_median > 0 and t > 0 else 1.0
            adjusted[index] = Evidence(
                index=index,
                coverage_probability=ev.coverage_probability,
                price_low=ev.price_low * scale,
                price_median=ev.price_median * scale,
                price_high=ev.price_high * scale,
            )
        shipped += replay(snap, submission_of(case, model)).net
        median_moved += replay(snap, submission_of(case, adjusted)).net
        both += replay(
            snap, {i: (snap.fair_point(i), snap.fair_point(i)) for i in snap.line_items}
        ).net
    return {"shipped": shipped, "oracle-median": median_moved, "oracle": both}


def pivoted(c1: float, pivot: float) -> tuple[float, float]:
    """The `(c0, c1)` whose map leaves `pivot` EUR unchanged: a one-knob family."""
    return math.log(pivot) * (1.0 - c1), c1


# ------------------------------------------------------------------------------- sweeps

C1_GRID = (0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20)
PIVOT_GRID = (60.0, 120.0, 200.0, 350.0, 600.0)


def sweep(loaded: list[tuple], baseline: float) -> list[tuple[float, float, float]]:
    """The pivoted family, in euros. Returns `(net, c0, c1)` sorted best first."""
    print(f"\n{'pivot':>7} {'c1':>6} {'c0':>8} {'net':>14} {'delta':>12}")
    results: list[tuple[float, float, float]] = []
    for pivot in PIVOT_GRID:
        for c1 in C1_GRID:
            c0, _ = pivoted(c1, pivot)
            net = total(loaded, c0, c1)
            results.append((net, c0, c1))
            if c1 != 1.00:
                print(f"{pivot:7.0f} {c1:6.2f} {c0:8.3f} {net:14,.0f} {net - baseline:12,.0f}")
    print(f"{'--':>7} {1.00:6.2f} {0.0:8.3f} {baseline:14,.0f} {0.0:12,.0f}   (shipped)")
    return sorted(results, reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-15,17-20")
    parser.add_argument("--tag", default="model,nohint")
    parser.add_argument("--tail-factor", type=float, default=1.0)
    parser.add_argument("--table", action="store_true")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--holdout", default=None, choices=("even", "odd", "late", "loo"))
    parser.add_argument("--sigma-floor", type=float, default=0.0)
    parser.add_argument("--apply", nargs=2, type=float, metavar=("C0", "C1"), default=None)
    parser.add_argument("--oracle", action="store_true", help="the item-accuracy ceiling")
    args = parser.parse_args()

    games = parse_games(args.games)
    loaded = load(games, args.tag, args.tail_factor)
    rows = pairs(loaded)
    print(f"{len(loaded)} Games, {len(rows)} Line Items with t > 0, tag {args.tag}")

    if args.table:
        table(rows, "t")
        table(rows, "hat")
        for weight in ("euro", "flat"):
            c0, c1 = fit(rows, weight)
            print(
                f"{weight:>5}-weighted fit: log t = {c0:.3f} + {c1:.3f} * log t_hat"
                f"   residual sigma {residual_sigma(rows, c0, c1):.2f}"
            )

    baseline_by_game = nets(loaded, 0.0, 1.0)
    baseline = sum(baseline_by_game.values())

    if args.apply:
        c0, c1 = args.apply
        after = nets(loaded, c0, c1, args.sigma_floor)
        print(f"\n{'game':>5} {'shipped':>12} {'recalibrated':>14} {'delta':>12}")
        for game_id in sorted(after):
            before = baseline_by_game[game_id]
            print(
                f"{game_id:5d} {before:12,.0f} {after[game_id]:14,.0f} "
                f"{after[game_id] - before:12,.0f}"
            )
        change = sum(after.values()) - baseline
        print(f"{'TOTAL':>5} {baseline:12,.0f} {sum(after.values()):14,.0f} {change:12,.0f}")
        deltas = sorted(after[g] - baseline_by_game[g] for g in after)
        print(f"{'MEDIAN':>5} {'':>12} {'':>14} {deltas[len(deltas) // 2]:12,.0f}")

    if args.oracle:
        print()
        for label, value in oracle_totals(loaded).items():
            print(f"{label:>16} {value:14,.0f}")

    if args.sweep:
        results = sweep(loaded, baseline)
        net, c0, c1 = results[0]
        print(f"\nbest in-sample: c0={c0:.3f} c1={c1:.2f} net {net:,.0f} (+{net - baseline:,.0f})")

    if args.holdout:
        folds = holdout_folds(args.holdout, [snap.game_id for snap, _, _ in loaded])
        chosen_total = shipped_total = 0.0
        for train, test in folds:
            train_set = [entry for entry in loaded if entry[0].game_id in train]
            test_set = [entry for entry in loaded if entry[0].game_id in test]
            train_base = total(train_set, 0.0, 1.0)
            best = max(
                (
                    (total(train_set, *pivoted(c1, pivot)), pivot, c1)
                    for pivot in PIVOT_GRID
                    for c1 in C1_GRID
                ),
                key=lambda row: row[0],
            )
            _, pivot, c1 = best
            c0, _ = pivoted(c1, pivot)
            held = total(test_set, c0, c1)
            base = total(test_set, 0.0, 1.0)
            chosen_total += held
            shipped_total += base
            print(
                f"train {sorted(train)[0]}..{sorted(train)[-1]} ({len(train)} Games) "
                f"picks pivot={pivot:.0f} c1={c1:.2f} (train +{best[0] - train_base:,.0f})"
                f"  ->  held-out {sorted(test)}: {base:,.0f} -> {held:,.0f} "
                f"({held - base:+,.0f})"
            )
        print(f"held-out total: {shipped_total:,.0f} -> {chosen_total:,.0f} "
              f"({chosen_total - shipped_total:+,.0f})")


def holdout_folds(kind: str, game_ids: list[int]) -> list[tuple[set[int], set[int]]]:
    if kind == "even":
        test = {g for g in game_ids if g % 2 == 0}
    elif kind == "odd":
        test = {g for g in game_ids if g % 2 == 1}
    elif kind == "late":
        test = set(sorted(game_ids)[len(game_ids) // 2:])
    else:
        return [({g for g in game_ids if g != held}, {held}) for held in sorted(game_ids)]
    return [({g for g in game_ids if g not in test}, test)]


if __name__ == "__main__":
    main()
