"""The coverage dead zone on big Line Items: collapse to zero, or hold at the absolute cap?

    PYTHONPATH=. pixi run python scripts/experiments/big_dead_zone.py

`price_item` collapses the Limit to exactly zero at `covered <= COVERAGE_FLOOR` (2/3), and
the derivation behind that is exact: accepting beats rejecting iff `P(fair) > 2/3`. The
derivation is not what fails. What fails is that the number fed to it is a plain arithmetic
mean over the ensemble draws -- `blend` widens the *band* on disagreement but averages
*coverage* to a point -- so two confident, contradictory readings produce a middling number
that is not a belief at all. Game 53 item 1: draw A read 0.82 quoting the reimbursement
clause, draw B read 0.02 quoting an itemisation exclusion, the mean was 0.42, the Limit
collapsed, and twelve fair Charges were wrongfully rejected for -77,793. Draw A was right;
the item settled at `t >= 8,626`.

Calibrated over 621 Line Items, the dead zone splits by magnitude:

    p in (0, 2/3]      115 items    32% really covered      collapse is right on average
      of which big       7 items    3 of 7 really covered   a coin flip
        covered ones: t = 7,225+, 8,626+, 648
        uncovered ones: t <= 405, 130, 50, 45

So on big items the collapse is a coin flip whose two sides are worth ten thousand euros and
four hundred. And the downside of *not* collapsing is bounded by `LIMIT_CAP` -- the same
absolute wall that made Game 53 unrecoverable is what caps the exposure here.

This sweeps holding the Limit at a floor instead of zero, for big items whose coverage sits
in the dead zone above `p_min`. Everything else is shipped.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.charge_buckets import Row, dataset, snapshot  # noqa: E402
from scripts.replay_payoffs import replay  # noqa: E402

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


def price(row: Row, *, p_min: float, floor_mult: float) -> tuple[float, float]:
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    median = filled.price_median
    big = median >= BIG_ITEM_THRESHOLD
    memory = "B:memory" in row.channels
    covered = 0.0 if row.uncovered else filled.coverage_probability

    charge = charge_factor(sigma) * median
    if big:
        charge *= BIG_ITEM_CHARGE_SCALE

    if covered <= COVERAGE_FLOOR:
        # The change under test. Channel A (`row.uncovered`) is a proven exclusion and is
        # never overridden -- only a doubtful *model* read is held off zero.
        if big and not row.uncovered and covered >= p_min:
            limit = min(floor_mult * LIMIT_CAP, LIMIT_CEILING * median)
        else:
            limit = 0.0
    else:
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        ceiling = LIMIT_CEILING_MEMORY if memory else LIMIT_CEILING
        candidates = [_lognormal_quantile(median, sigma, conditional), ceiling * median]
        if not memory:
            candidates.append(LIMIT_CAP)
        limit = min(candidates)
    return round(max(charge, 0.0), 2), round(max(min(limit, charge), 0.0), 2)


def net(rows, games, **kw) -> float:
    total = 0.0
    for game_id in games:
        sub = {r.index: price(r, **kw) for r in rows if r.game == game_id}
        if sub:
            total += replay(snapshot(game_id), sub).net
    return total


def main() -> None:
    rows = dataset()
    games = sorted({r.game for r in rows})
    folds = {
        "all": games,
        "odd": [g for g in games if g % 2],
        "even": [g for g in games if not g % 2],
        "<=40": [g for g in games if g <= 40],
        ">40": [g for g in games if g > 40],
    }
    base = {n: net(rows, gs, p_min=2.0, floor_mult=0.0) for n, gs in folds.items()}
    print(f"{len(games)} Games, noise floor +/-{NOISE_FLOOR_18*math.sqrt(len(games)/18):,.0f}. "
          f"Delta against the shipped hard collapse to zero.\n")
    print(f"{'p_min':>7}{'floor':>16}" + "".join(f"{k:>11}" for k in folds) + "   folds+")
    print("-" * (23 + 11 * len(folds) + 9))
    for p_min in (0.10, 0.20, 0.30, 0.40):
        for fm in (0.5, 1.0, 2.0):
            cells = [net(rows, gs, p_min=p_min, floor_mult=fm) - base[n] for n, gs in folds.items()]
            pos = sum(1 for c in cells[1:] if c > 0)
            mark = "  <-- all 4" if pos == 4 else ""
            label = f"{fm:.1f}x cap ({fm*LIMIT_CAP:,.0f})"
            print(f"{p_min:>7.2f}{label:>16}" + "".join(f"{c:>+11,.0f}" for c in cells)
                  + f"{pos:>6}/4{mark}")
        print()
    print(f"{'(base)':>23}" + "".join(f"{base[k]:>11,.0f}" for k in folds))


if __name__ == "__main__":
    main()
