"""Is `LIMIT_CEILING = 0.45` still right, or was it fitted to an estimator we no longer have?

    PYTHONPATH=. pixi run python scripts/experiments/limit_ceiling_sweep.py

Game 59 asked the question. Four expensive, correctly-priced Line Items drew 45,418 of lawyer
waste with **zero** rightful rejections between them -- item 2 held a Limit of 701.77
(= 0.45 x 1559.49, the ceiling binding exactly) against a true `t >= 1451`, and wrongly
rejected 12 of 16 fair Charges. The Game's Limit ledger came in at 0.2:1 saved-to-wasted
against a 2.2-2.6:1 record average.

The engine docstring states its own falsification condition: "three or four consecutive
settled Games where 0.60 beats 0.45 on that window alone". This measures it, on the whole
record and on the recent window, against the real payoff table.

The trap it is built to avoid: a ceiling swept on a *biased* estimator absorbs that bias.
Since 0.45 was fitted, Price Memory gained a basis fix (5f6dcc3) and a Policy key (d0ef2c6),
and the invoice parser was reconciled with the memory builder's (c6a079f) -- the last of
which changed nine quantities and removed two invented Line Items. So the estimate feeding
this ceiling is measurably not the one it was fitted against. Writes nothing.
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


def noise(n: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(n / 18.0)


def price(row: Row, *, ceiling: float, ceiling_memory: float) -> tuple[float, float]:
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    median = filled.price_median
    memory = "B:memory" in row.channels
    covered = 0.0 if row.uncovered else filled.coverage_probability

    charge = charge_factor(sigma) * median
    if median >= BIG_ITEM_THRESHOLD:
        charge *= BIG_ITEM_CHARGE_SCALE

    if covered <= COVERAGE_FLOOR:
        limit = 0.0
    else:
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        cap = ceiling_memory if memory else ceiling
        candidates = [_lognormal_quantile(median, sigma, conditional), cap * median]
        if not memory:
            candidates.append(LIMIT_CAP)
        limit = min(candidates)
    return round(max(charge, 0.0), 2), round(max(min(limit, charge), 0.0), 2)


def net(rows, games, *, ceiling, ceiling_memory) -> float:
    total = 0.0
    for game_id in games:
        sub = {
            r.index: price(r, ceiling=ceiling, ceiling_memory=ceiling_memory)
            for r in rows
            if r.game == game_id
        }
        if sub:
            total += replay(snapshot(game_id), sub).net
    return total


def main() -> None:
    rows = dataset()
    games = sorted({r.game for r in rows})
    last = games[-8:]
    folds = {
        "all": games,
        "odd": [g for g in games if g % 2],
        "even": [g for g in games if not g % 2],
        "<=40": [g for g in games if g <= 40],
        ">40": [g for g in games if g > 40],
        "last8": last,
    }
    base = {n: net(rows, gs, ceiling=LIMIT_CEILING, ceiling_memory=LIMIT_CEILING_MEMORY)
            for n, gs in folds.items()}
    print(f"{len(games)} Games, noise floor +/-{noise(len(games)):,.0f}. "
          f"Delta against the shipped ceiling {LIMIT_CEILING} "
          f"(memory {LIMIT_CEILING_MEMORY}). last8 = Games {last[0]}-{last[-1]}.\n")
    header = f"{'ceiling':<18}" + "".join(f"{k:>11}" for k in folds) + "   folds+"
    print(header)
    print("-" * len(header))
    for c in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 0.80, 1.00):
        cells = [net(rows, gs, ceiling=c, ceiling_memory=LIMIT_CEILING_MEMORY) - base[n]
                 for n, gs in folds.items()]
        pos = sum(1 for cell in cells[1:5] if cell > 0)
        mark = "  <-- all 4" if pos == 4 else ""
        print(f"{'model ' + format(c, '.2f'):<18}"
              + "".join(f"{cell:>+11,.0f}" for cell in cells) + f"{pos:>6}/4{mark}")
    print()
    for cm in (0.60, 0.75, 0.90, 1.10):
        cells = [net(rows, gs, ceiling=LIMIT_CEILING, ceiling_memory=cm) - base[n]
                 for n, gs in folds.items()]
        pos = sum(1 for cell in cells[1:5] if cell > 0)
        mark = "  <-- all 4" if pos == 4 else ""
        print(f"{'memory ' + format(cm, '.2f'):<18}"
              + "".join(f"{cell:>+11,.0f}" for cell in cells) + f"{pos:>6}/4{mark}")
    print(f"\n{'(baseline net)':<18}" + "".join(f"{base[k]:>11,.0f}" for k in folds))


if __name__ == "__main__":
    main()
