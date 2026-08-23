"""A second tier above `BIG_ITEM_THRESHOLD`: does the far tail want a larger scale still?

    PYTHONPATH=. pixi run python scripts/experiments/big_fish_tier.py

`big_charge_sweep.py` shows the shipped 1.25 is the argmax over all 53 Games and that a
larger scale is worth +40,671 on Games >40 while costing -214,641 on Games <=40. Broken
down per Game the late gain is not one Game crossing a Limit cluster -- it is three (41
+15,305, 44 +20,679, 53 +14,668), every one of them a theft or robbery compensation line
whose Fair Value settled far above our estimate. The Game that punishes a larger scale
(27, "Compensation for robbery damage") is the same *kind* of item, so the wording is not
the discriminator. The magnitude is: the three winners estimate 5,524-6,840, the loser
3,795.

So this sweeps a second threshold `T2` with its own scale `k2`, holding everything at or
below `BIG_ITEM_THRESHOLD` exactly as shipped. Folds are reported because the total over 53
Games is inside the +/-45,682 noise floor and fold consistency is the bar every other
constant in `engine.py` had to clear.
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


def price(row: Row, *, t2: float, k2: float) -> tuple[float, float]:
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    median = filled.price_median
    memory = "B:memory" in row.channels
    covered = 0.0 if row.uncovered else filled.coverage_probability

    charge = charge_factor(sigma) * median
    if median >= t2:
        charge *= k2
    elif median >= BIG_ITEM_THRESHOLD:
        charge *= BIG_ITEM_CHARGE_SCALE

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


def net(rows, games, *, t2, k2) -> float:
    total = 0.0
    for game_id in games:
        sub = {r.index: price(r, t2=t2, k2=k2) for r in rows if r.game == game_id}
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
    INF = float("inf")
    base = {n: net(rows, gs, t2=INF, k2=1.0) for n, gs in folds.items()}
    print(f"{len(games)} Games, noise floor +/-{NOISE_FLOOR_18 * math.sqrt(len(games)/18):,.0f}. "
          f"Delta against the shipped single tier (1.25 above 1,000).\n")
    print(f"{'T2':>7}{'k2':>6}" + "".join(f"{k:>11}" for k in folds) + "   folds+")
    print("-" * (13 + 11 * len(folds) + 9))
    for t2 in (2000.0, 3000.0, 4000.0, 5000.0, 6000.0):
        for k2 in (1.5, 1.75, 2.0, 2.5):
            cells = [net(rows, gs, t2=t2, k2=k2) - base[n] for n, gs in folds.items()]
            pos = sum(1 for c in cells[1:] if c > 0)
            mark = "  <-- all 4" if pos == 4 else ""
            print(f"{t2:>7,.0f}{k2:>6.2f}" + "".join(f"{c:>+11,.0f}" for c in cells)
                  + f"{pos:>6}/4{mark}")
        print()
    print(f"{'(base)':>13}" + "".join(f"{base[k]:>11,.0f}" for k in folds))


if __name__ == "__main__":
    main()
