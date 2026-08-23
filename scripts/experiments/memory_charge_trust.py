"""The Limit trusts Price Memory more than the model. The Charge does not. Should it?

    PYTHONPATH=. pixi run python scripts/experiments/memory_charge_trust.py

`src/pricing/engine.py` already treats the two channels asymmetrically on the Limit:
`LIMIT_CEILING_MEMORY = 0.75` against `LIMIT_CEILING = 0.45`, and lifting `LIMIT_CAP` on
memory-backed items too. That was measured at **+40,791, positive on all four folds**, on one
argument: a memory-backed wording has been *seen settle*, so its value was recovered exactly by
`invert_fair_values`, while a model-only estimate is unchecked. The measured log errors are
`MEMORY_SIGMA = 0.43` against `MODEL_SIGMA_PRIOR = 0.6` -- and the model's real error is worse
than its prior (RMSLE 1.66 / 1.82 / 2.20 over G26-40 / G41-55 / G56-64).

**The Charge ignores the channel entirely.** `charge = charge_factor(sigma) * median`, where
`sigma` is read off the band the model asserted -- a quantity whose median is 0.375 and which
`blend.py`'s own docstring says "does not even correlate with the actual error". So the Charge
applies the same discount to an anchor we have watched settle and to a number the model
invented.

Why this is the shape of change that should work, when a global multiplier is not
------------------------------------------------------------------------------------
A fair Charge is owed by **all sixteen** opponents whatever their Limits; an Overcharge is paid
only by the ~1 in 5 who accept. So the discount below `t_hat` is insurance, and its correct
size is proportional to how wrong `t_hat` might be. One rate for two channels with a 4x
difference in log error must be too timid on one and too bold on the other.

Every *global* Charge change has now been measured and lost: a flat multiplier below 1.0 loses
monotonically on all four folds and on the last 10, 15 and 20 Games separately
(`regime_ab_sweep.py`); the band-interpolation and `price_high`-floor families lose or are
flat (`big_charge_floor_sweep.py`); and the exact expected-income argmax, which is what
`charge_factor` approximates, loses in every cell of a two-parameter sweep
(`expected_income_charge.py`). What none of those vary is *who the estimate came from*.

Note the one adjacent negative, so this is not confused with it. `ORCHESTRATOR.md` records
"Charge conditioned on channel, sigma, unit, quantity -- every **downward** multiplier loses;
held-out delta -15,354". That measured making the Charge *more* timid on the weaker channel.
This measures making it *bolder on the stronger one*, which is the direction
`LIMIT_CEILING_MEMORY` took and which has never been swept for the Charge.

`k_memory` multiplies `charge_factor(sigma)` on items where Channel B spoke. `k_model` does the
same for model-only items and is swept alongside so the two are not confounded: if the win is
really "charge more everywhere" it will show up as `k_model > 1` helping too, and the
`regime_ab_sweep` result (x1.10 globally is -27,185) says it should not.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from charge_buckets import dataset, snapshot  # noqa: E402
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

INF = float("inf")
NOISE_FLOOR_18 = 26_622


def noise(n: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(max(n, 1) / 18.0)


def price(row, *, k_memory: float, k_model: float) -> tuple[float, float]:
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    median = filled.price_median
    memory = "B:memory" in row.channels
    covered = 0.0 if row.uncovered else filled.coverage_probability

    charge = charge_factor(sigma) * median * (k_memory if memory else k_model)
    if median >= BIG_ITEM_THRESHOLD:
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


def net_of(rows, games, *, k_memory: float, k_model: float) -> float:
    total = 0.0
    for game_id in games:
        sub = {
            r.index: price(r, k_memory=k_memory, k_model=k_model)
            for r in rows
            if r.game == game_id
        }
        if sub:
            total += replay(snapshot(game_id), sub).net
    return total


def fair_split(rows, games, *, k_memory: float, k_model: float) -> tuple[int, int]:
    """Fair/over counts on memory-backed items only -- the population being moved."""
    fair = over = 0
    wanted = set(games)
    for row in rows:
        if row.game not in wanted or "B:memory" not in row.channels:
            continue
        charge, _ = price(row, k_memory=k_memory, k_model=k_model)
        t = row.t_lo if row.t_hi == INF else (row.t_lo + row.t_hi) / 2.0
        if charge <= t:
            fair += 1
        else:
            over += 1
    return fair, over


def main() -> None:
    rows = dataset()
    games = sorted({r.game for r in rows})
    mem = sum(1 for r in rows if "B:memory" in r.channels)
    folds = {
        "all": games,
        "odd": [g for g in games if g % 2],
        "even": [g for g in games if not g % 2],
        "<=45": [g for g in games if g <= 45],
        ">45": [g for g in games if g > 45],
        "last10": games[-10:],
        "last20": games[-20:],
    }
    base = {n: net_of(rows, gs, k_memory=1.0, k_model=1.0) for n, gs in folds.items()}
    print(
        f"{len(games)} Games, {len(rows)} Line Items, {mem} memory-backed "
        f"({mem / len(rows):.0%}). Noise floor +/-{noise(len(games)):,.0f} over the record, "
        f"+/-{noise(10):,.0f} on last10.\nDelta against the shipped Charge. "
        f"`folds+` counts odd/even/<=45/>45.\n"
    )
    print(
        f"{'k_mem':>6} {'k_mdl':>6}"
        + "".join(f"{k:>11}" for k in folds)
        + "  folds+   memory items fair/over"
    )
    print("-" * (13 + 11 * len(folds) + 30))
    trials = [(k, 1.0) for k in (1.0, 1.1, 1.2, 1.3, 1.4, 1.5)] + [
        (1.0, 1.1),
        (1.3, 1.1),
        (1.3, 0.9),
    ]
    for k_memory, k_model in trials:
        cells = [
            net_of(rows, gs, k_memory=k_memory, k_model=k_model) - base[n] for n, gs in folds.items()
        ]
        pos = sum(1 for c in cells[1:5] if c > 0)
        fair, over = fair_split(rows, games, k_memory=k_memory, k_model=k_model)
        mark = "  <-- all 4" if pos == 4 else ""
        print(
            f"{k_memory:>6.2f} {k_model:>6.2f}"
            + "".join(f"{c:>+11,.0f}" for c in cells)
            + f"{pos:>5}/4    {fair:>4}/{over:<4}{mark}"
        )
    print(f"\n{'(baseline)':>13}" + "".join(f"{base[k]:>11,.0f}" for k in folds))


if __name__ == "__main__":
    main()
