"""Charge at the argmax of expected income instead of a fitted line in sigma.

    PYTHONPATH=. pixi run python scripts/experiments/expected_income_charge.py

The shipped Charge is `charge_factor(sigma) * price_median` with
`charge_factor(sigma) = 0.85 - 0.45 * sigma`, a line fitted to the record. The payoff table
gives the quantity that line is approximating, exactly, so it can be maximised directly.

Per opponent, for a Charge `a` against a secret Fair Value `t` and Cap `c = max(4t, 2000)`:

    t >= a    the Charge is fair and is owed whether the opponent accepts or rejects   ->  a
    t <  a    a rightful rejection pays nothing; an acceptance pays min(a, c)          ->  rho * min(a, c)

so with `rho` the rate at which the Field accepts an Overcharge,

    E[income] / 16  =  a * P(t >= a)  +  rho * E[ min(a, max(4t, 2000)) * 1{t < a} ]

Three things fall out of that expression which no multiplier on the median can express:

1. **The 16-versus-rho asymmetry.** A fair Charge is paid by every opponent; an Overcharge by
   about one in five. That is the cliff `BIG_ITEM_CHARGE_SCALE` fell off (see H14).
2. **The Cap truncates the Overcharge branch.** On an item we believe is worth ~nothing the
   whole upside is `rho * 2000`, so **every euro of Charge above 2,000 is strictly wasted** --
   it cannot raise what an acceptor pays and can only reduce who accepts. Game 62 Charged
   10,349.89 and 8,617.22 on items the model had called uncovered; the one acceptor on the
   second paid exactly 4,840.00. `rivals.py` establishes `c = max(4t, 2000)`.
3. **Coverage enters as mass at zero** rather than as a separate rule, because `P(t >= a)` is
   `covered * P(t >= a | covered)`. The Charge stops being coverage-blind without needing a
   branch, and R6c is preserved automatically: when `covered -> 0` the objective becomes
   `rho * min(a, 2000)`, which is maximised at 2,000, not at infinity.

The two parameters, both swept rather than assumed
--------------------------------------------------
`rho` -- the Field's acceptance rate on an Overcharge. Directly measurable from the settled
rows, but it moves with the regime, so it is swept.

`sigma_k` -- a calibration multiplier on `implied_sigma`, and the reason this experiment
matters more than it looks. `implied_sigma` has a median of ~0.375 across the record while the
measured log error of the estimate is far larger (RMSLE 1.66 / 1.82 / 2.20 over G26-40 /
G41-55 / G56-64). So `P(t >= a)` computed from the band is **overconfident**, and an argmax
that trusts it will Charge too close to the median. If `sigma_k > 1` wins, the shipped fitted
line has been absorbing that miscalibration all along, which would explain why a linear
function of a badly-scaled sigma beats the exact objective computed from the same sigma.

Read the folds, not the total: the standing bar is positive on all four (odd, even, early,
late) plus the recent windows, and the noise floor is `26,622 * sqrt(n/18)`.
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
    COVERAGE_FLOOR,
    LIMIT_CAP,
    LIMIT_CEILING,
    LIMIT_CEILING_MEMORY,
    LIMIT_QUANTILE,
    _lognormal_quantile,
    implied_sigma,
)

INF = float("inf")
NOISE_FLOOR_18 = 26_622
CAP_FLOOR = 2_000.0
#: Quadrature nodes for the Fair Value. 96 log-spaced points from Q0.001 to Q0.999 reproduce
#: the closed-form mean of a lognormal to under 0.5% across the sigma range we see, which is
#: far inside the noise floor of anything measured here.
NODES = 96


def noise(n: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(max(n, 1) / 18.0)


def _quantile(median: float, sigma: float, p: float) -> float:
    return _lognormal_quantile(median, sigma, p)


def _grid(median: float, sigma: float) -> tuple[tuple[float, float], ...]:
    """`(t, weight)` nodes for the covered branch of the Fair Value distribution."""
    edges = [(i + 0.5) / NODES for i in range(NODES)]
    return tuple((_quantile(median, sigma, p), 1.0 / NODES) for p in edges)


def best_charge(median: float, sigma: float, covered: float, rho: float) -> float:
    """The Charge maximising expected income per opponent. See the module docstring."""
    if median <= 0:
        return 0.0
    nodes = _grid(median, sigma)
    covered = min(max(covered, 0.0), 1.0)
    # Candidate Charges: the quadrature nodes themselves (the objective is piecewise smooth
    # with kinks exactly at the nodes and at the Cap floor), plus the Cap floor.
    candidates = sorted({t for t, _ in nodes if t > 0} | {CAP_FLOOR})
    best_value = -1.0
    best = 0.0
    for a in candidates:
        fair = 0.0
        over = 0.0
        for t, w in nodes:
            if t >= a:
                fair += w
            else:
                over += w * min(a, max(4.0 * t, CAP_FLOOR))
        # `1 - covered` is mass at t = 0: never fair, and its Cap is the floor.
        expected = covered * (a * fair + rho * over) + (1.0 - covered) * rho * min(a, CAP_FLOOR)
        if expected > best_value:
            best_value, best = expected, a
    return best


def price(row, *, rho: float, sigma_k: float) -> tuple[float, float]:
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    median = filled.price_median
    memory = "B:memory" in row.channels
    covered = 0.0 if row.uncovered else filled.coverage_probability

    charge = best_charge(median, max(sigma * sigma_k, 1e-6), covered, rho)

    # The Limit is left exactly as shipped, so this measures the Charge and nothing else.
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


def shipped(row) -> tuple[float, float]:
    from src.pricing.engine import price_item

    result = price_item(
        row.evidence,
        confirmed_uncovered=row.uncovered,
        memory_backed="B:memory" in row.channels,
    )
    return result.charge, result.limit


def net_of(rows, games, pricer) -> float:
    total = 0.0
    for game_id in games:
        sub = {r.index: pricer(r) for r in rows if r.game == game_id}
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
        "<=45": [g for g in games if g <= 45],
        ">45": [g for g in games if g > 45],
        "last10": games[-10:],
    }
    base = {n: net_of(rows, gs, shipped) for n, gs in folds.items()}
    print(
        f"{len(games)} Games ({games[0]}-{games[-1]}), {len(rows)} Line Items. "
        f"Noise floor +/-{noise(len(games)):,.0f} over the record, "
        f"+/-{noise(10):,.0f} on last10.\n"
        f"Delta against the shipped `charge_factor(sigma) * median`.\n"
    )
    print(f"{'rho':>5} {'sigma_k':>8}" + "".join(f"{k:>11}" for k in folds) + "  folds+")
    print("-" * (14 + 11 * len(folds) + 8))
    for rho in (0.0, 0.10, 0.20):
        for sigma_k in (1.0, 1.5, 2.0, 2.5, 3.0):
            def pricer(row, rho=rho, sigma_k=sigma_k):
                return price(row, rho=rho, sigma_k=sigma_k)

            cells = [net_of(rows, gs, pricer) - base[n] for n, gs in folds.items()]
            pos = sum(1 for c in cells[1:5] if c > 0)
            mark = "  <-- all 4" if pos == 4 else ""
            print(
                f"{rho:>5.2f} {sigma_k:>8.1f}"
                + "".join(f"{c:>+11,.0f}" for c in cells)
                + f"{pos:>5}/4{mark}"
            )
    print(f"\n{'(baseline)':>14}" + "".join(f"{base[k]:>11,.0f}" for k in folds))


if __name__ == "__main__":
    main()
