"""`BIG_ITEM_CHARGE_SCALE` re-swept over every Game with a decision log, plus two rivals.

    PYTHONPATH=. pixi run python scripts/experiments/big_charge_sweep.py

The constant was fitted at Game 52 over 26 Games. Game 53 settled a `t >= 8,626` robbery
item afterwards, which is exactly the population it governs, so it gets re-measured rather
than trusted. Three families, all confined to `t_hat >= BIG_ITEM_THRESHOLD`:

    scale k        charge = charge_factor(sigma) * median * k      (the shipped family)
    band w         charge = price_low ** (1-w) * price_high ** w   (log-interpolate the band)
    floor f        charge = max(shipped charge, f * price_high)

`band` and `floor` exist because the shipped family multiplies the *median*, and on this
bucket the median is the quantity that is wrong -- 14 of 25 estimates proven too high, 4
proven too low, and the four low ones carry 242,028 of wrongful-rejection penalty. A rule
anchored on the band's upper end moves with the model's own uncertainty instead.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.charge_buckets import Row, dataset, snapshot  # noqa: E402
from scripts.replay_payoffs import replay  # noqa: E402

from src.pricing.engine import (  # noqa: E402
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
    return NOISE_FLOOR_18 * math.sqrt(n / 18.0)


def price(row: Row, *, family: str, param: float) -> tuple[float, float]:
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
        elif family == "band":
            lo = max(filled.price_low, 1e-9)
            hi = max(filled.price_high, lo)
            charge = math.exp((1.0 - param) * math.log(lo) + param * math.log(hi))
        elif family == "floor":
            charge = max(charge, param * filled.price_high)

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


def net(rows, games, *, family, param) -> float:
    total = 0.0
    for game_id in games:
        sub = {r.index: price(r, family=family, param=param) for r in rows if r.game == game_id}
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
    base = {n: net(rows, gs, family="scale", param=1.25) for n, gs in folds.items()}
    print(f"{len(games)} Games, noise floor +/-{noise(len(games)):,.0f}. "
          f"Delta against the shipped scale of 1.25.\n")
    print(f"{'rule':<16}" + "".join(f"{k:>11}" for k in folds) + "   folds+")
    print("-" * (16 + 11 * len(folds) + 9))
    trials = ([("scale", k) for k in (1.0, 1.25, 1.4, 1.5, 1.6, 1.8)]
              + [("band", w) for w in (0.5, 0.6, 0.7, 0.8)]
              + [("floor", f) for f in (0.3, 0.4, 0.5, 0.6)])
    for family, param in trials:
        cells = [net(rows, gs, family=family, param=param) - base[n] for n, gs in folds.items()]
        pos = sum(1 for c in cells[1:] if c > 0)
        mark = "  <-- all 4" if pos == 4 else ""
        print(f"{family+' '+str(param):<16}" + "".join(f"{c:>+11,.0f}" for c in cells)
              + f"{pos:>6}/4{mark}")
    print(f"\n{'(baseline net)':<16}" + "".join(f"{base[k]:>11,.0f}" for k in folds))


if __name__ == "__main__":
    main()
