"""The two evidence-layer knobs that are not the level: the band width and the coverage.

`src/pricing.py` says it in its own docstring -- "the band is not calibrated, and that is
the real problem ... it belongs in the evidence layer, not here". The blended ensemble
claims a median implied sigma near 0.4 while the residual of the euro-weighted fit against
the recovered Fair Values is **1.29**, so `charge_factor` is reading a number that does not
measure what it claims. Both of the knobs that follow live in the file this agent owns:

    sigma floor        widen every band to at least this, which lowers Charge and Limit
    coverage transform push the coverage probability toward 0 or 1, which decides the Limit

Everything is scored in euros with `replay_payoffs.replay` against the real Field, over the
blended ensemble evidence, Price Memory off.

    pixi run python scripts/experiments/level_width.py --games 1-24 --sigma
    pixi run python scripts/experiments/level_width.py --games 1-24 --coverage

## Both are negative, and the first one is instructive

**Telling the truth about the width costs money.** Games 1-24, the shipped two-draw blend:

    sigma floor    net        delta
    ---------- ---------- ----------
        none      127,292          0
        0.30      124,699     -2,594
        0.50      100,431    -26,861
        0.60       75,347    -51,945
        0.80       48,711    -78,581
        1.29     -120,151   -247,443   <- the estimator's *measured* log error

The honest width is the worst cell in the sweep. That is not a paradox: `charge_factor`
reads sigma as `0.85 - 0.45 * sigma`, so an honest 1.29 drops the Charge to the 0.30 floor,
and forfeiting 60% of the Charge on every Line Item we *were* pricing correctly costs far
more than the tail it protects. The band and the Charge line are calibrated **as a pair**;
fixing one alone unpicks the pair. Anybody re-deriving `CHARGE_INTERCEPT`/`CHARGE_SLOPE`
from a measured sigma has to move both constants in the same commit, and score it in euros.

**Coverage is already sharp enough to be uninteresting.** Pushing `p -> p**(1+g)` moves the
total by at most 595 euros over the whole grid (g = 0.25 to 2.0), because `LIMIT_CEILING`
binds below the coverage quantile at every band width we actually see.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from level_fit import load, nets, pairs, residual_sigma  # noqa: E402
from replay_payoffs import replay  # noqa: E402
from level_compat import parse_games, submission_of  # noqa: E402

from src.pricing import Evidence, implied_sigma  # noqa: E402

BAND_Z = 1.645

SIGMA_GRID = (0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 1.0, 1.29)
GAMMA_GRID = (0.0, 0.25, 0.5, 1.0, 2.0)


def sharpen(probability: float, gamma: float) -> float:
    """`p ** (1 + gamma)` renormalised against its complement: gamma > 0 pushes toward 0."""
    if gamma == 0.0:
        return probability
    p = min(max(probability, 0.0), 1.0)
    if p in (0.0, 1.0):
        return p
    return p ** (1.0 + gamma)


def coverage_total(loaded: list[tuple], gamma: float) -> float:
    total = 0.0
    for snap, case, model in loaded:
        adjusted = {
            i: Evidence(
                index=i,
                coverage_probability=sharpen(ev.coverage_probability, gamma),
                price_low=ev.price_low,
                price_median=ev.price_median,
                price_high=ev.price_high,
            )
            for i, ev in model.items()
        }
        total += replay(snap, submission_of(case, adjusted)).net
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-15,17-20")
    parser.add_argument("--tag", default="model,nohint")
    parser.add_argument("--sigma", action="store_true")
    parser.add_argument("--coverage", action="store_true")
    args = parser.parse_args()

    loaded = load(parse_games(args.games), args.tag)
    rows = pairs(loaded)
    widths = [
        implied_sigma(ev.price_low, ev.price_median, ev.price_high)
        for _snap, _case, model in loaded
        for ev in model.values()
        if ev.price_median > 0
    ]
    print(
        f"{len(loaded)} Games, {len(rows)} Line Items with t > 0, tag {args.tag}\n"
        f"median implied sigma of the blend {statistics.median(widths):.3f}   "
        f"residual sigma of the euro fit {residual_sigma(rows, 0.789, 0.867):.2f}   "
        f"of the identity {residual_sigma(rows, 0.0, 1.0):.2f}"
    )

    baseline = sum(nets(loaded, 0.0, 1.0).values())
    if args.sigma:
        print(f"\n{'sigma floor':>12} {'net':>14} {'delta':>12}")
        for floor in SIGMA_GRID:
            net = sum(nets(loaded, 0.0, 1.0, floor).values())
            print(f"{floor:12.2f} {net:14,.0f} {net - baseline:12,.0f}")

    if args.coverage:
        print(f"\n{'p -> p^(1+g)':>12} {'net':>14} {'delta':>12}")
        for gamma in GAMMA_GRID:
            net = coverage_total(loaded, gamma)
            print(f"{gamma:12.2f} {net:14,.0f} {net - baseline:12,.0f}")


if __name__ == "__main__":
    main()
