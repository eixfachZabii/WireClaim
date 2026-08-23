"""The `b <= a` clamp, revisited with the ceilings it was told to be revisited with.

    PYTHONPATH=. pixi run python scripts/experiments/limit_clamp_release.py

`price_item` ends with `limit = min(limit, charge)`, and its own note says why that is not
obviously right and when to re-open it:

    b < a always: the Limit is a lower quantile of the same posterior than the Charge.
    ... nothing in the payoff table requires the second to sit below the first. Releasing this
    clamp is worth +16,421 over Games 1-14 against an unbiased estimator at sigma 0.45 ...
    Kept anyway: with today's fat-tailed estimator the Limit is held at 0.30 x median and this
    clamp almost never binds, so releasing it buys nothing now while removing a guard rail
    that catches genuinely incoherent bands. **Revisit together with `LIMIT_CEILING`, not
    before.**

Both halves of "it almost never binds" have expired. The ceiling is no longer 0.30: it is
`LIMIT_CEILING = 0.45`, and `LIMIT_CEILING_MEMORY = 0.75` on memory-backed items with
`LIMIT_CAP` lifted entirely. And the Charge factor bottoms out well above where it did.

Game 65 is the worked example, and it is the reason this is being measured now. Line Item 3,
"Senior installer hours (3 hrs)", memory-backed, `t_hat = 287` against a settled `t >= 291`
-- a **1.4% estimate error**, the most accurate Line Item on record. The numbers submitted:

    a = 199.01     0.69 x median, the Charge factor
    b = 199.01     <- the clamp. Uncapped it would have been 0.75 x 287 = 215.25,
                      and the one-third quantile alone wanted 247

Thirteen of sixteen opponents Charged between 201.25 and 291.34. Every one was fair, because
`t >= 291`. We rejected all thirteen and paid `1.5x` on each: **-4,953 on one Line Item**, on
a Game whose whole net was -1,014.

That is the structural trap the clamp creates. The Field Charges a median of ~0.73 x `t`, so
its Charges cluster in `[0.7t, t]`. Our Charge sits at ~0.69 x `t_hat` by construction. Tying
`b` to `a` therefore places our Limit *below almost every fair Charge we will ever be shown*,
however good our estimate is -- and the better our estimate, the more reliably it happens,
because a well-estimated item is one where the Field's Charges cluster tightly just under the
true `t`. Accuracy makes this failure *more* likely, not less.

The two are swept jointly because the clamp only binds when the ceiling would have allowed a
higher Limit, so releasing it does nothing without the ceiling and the ceiling does less with
it. `bind%` reports how often the clamp is the binding constraint -- if that number is small
the release cannot matter and the docstring's original reasoning still stands.

H13 in the hypothesis ledger swept `LIMIT_CEILING` alone at Game 59 and found nothing above
0.45 positive on four folds. That sweep had the clamp in place and the old Charge constants, so
it does not answer this question; `LIMIT_CEILING_MEMORY` is swept here too for the same reason.
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
    CHARGE_TRUST_MEMORY,
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


def price(row, *, clamp: bool, ceiling_memory: float, ceiling_model: float):
    """The shipped rule with the clamp and the two ceilings as parameters."""
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    median = filled.price_median
    memory = "B:memory" in row.channels
    covered = 0.0 if row.uncovered else filled.coverage_probability

    charge = charge_factor(sigma) * median
    if memory:
        charge *= CHARGE_TRUST_MEMORY
    if median >= BIG_ITEM_THRESHOLD:
        charge *= BIG_ITEM_CHARGE_SCALE

    bound = False
    if covered <= COVERAGE_FLOOR:
        limit = 0.0
    else:
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        ceiling = ceiling_memory if memory else ceiling_model
        candidates = [_lognormal_quantile(median, sigma, conditional), ceiling * median]
        if not memory:
            candidates.append(LIMIT_CAP)
        limit = min(candidates)
        if limit > charge:
            bound = True
            if clamp:
                limit = charge
    return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2), bound


def net_of(rows, games, **kwargs) -> float:
    total = 0.0
    for game_id in games:
        sub = {}
        for row in rows:
            if row.game != game_id:
                continue
            charge, limit, _ = price(row, **kwargs)
            sub[row.index] = (charge, limit)
        if sub:
            total += replay(snapshot(game_id), sub).net
    return total


def bind_rate(rows, **kwargs) -> float:
    hits = sum(1 for row in rows if price(row, **kwargs)[2])
    return hits / len(rows) if rows else 0.0


def main() -> None:
    rows = dataset()
    games = sorted({r.game for r in rows})
    folds = {
        "all": games,
        "odd": [g for g in games if g % 2],
        "even": [g for g in games if not g % 2],
        "<=45": [g for g in games if g <= 45],
        ">45": [g for g in games if g > 45],
        "last10": games[-10:],
        "last20": games[-20:],
    }
    shipped = dict(clamp=True, ceiling_memory=LIMIT_CEILING_MEMORY, ceiling_model=LIMIT_CEILING)
    base = {n: net_of(rows, gs, **shipped) for n, gs in folds.items()}
    print(
        f"{len(games)} Games, {len(rows)} Line Items. Noise floor "
        f"+/-{noise(len(games)):,.0f} over the record, +/-{noise(10):,.0f} on last10.\n"
        f"Shipped: clamp ON, memory ceiling {LIMIT_CEILING_MEMORY}, model ceiling "
        f"{LIMIT_CEILING}. `bind%` = share of Line Items where `b <= a` is the binding "
        f"constraint.\n"
    )
    print(
        f"{'clamp':>6} {'ceil_mem':>9} {'ceil_mdl':>9}"
        + "".join(f"{k:>11}" for k in folds)
        + "  folds+  bind%"
    )
    print("-" * (26 + 11 * len(folds) + 15))
    trials = []
    for clamp in (True, False):
        for cm in (0.75, 1.00, 1.30):
            for cmodel in (0.45, 0.60):
                trials.append((clamp, cm, cmodel))
    for clamp, cm, cmodel in trials:
        kwargs = dict(clamp=clamp, ceiling_memory=cm, ceiling_model=cmodel)
        cells = [net_of(rows, gs, **kwargs) - base[n] for n, gs in folds.items()]
        pos = sum(1 for c in cells[1:5] if c > 0)
        rate = bind_rate(rows, **kwargs)
        mark = "  <-- all 4" if pos == 4 else ""
        print(
            f"{str(clamp):>6} {cm:>9.2f} {cmodel:>9.2f}"
            + "".join(f"{c:>+11,.0f}" for c in cells)
            + f"{pos:>5}/4  {rate:>5.0%}{mark}"
        )
    print(f"\n{'(baseline)':>26}" + "".join(f"{base[k]:>11,.0f}" for k in folds))


if __name__ == "__main__":
    main()
