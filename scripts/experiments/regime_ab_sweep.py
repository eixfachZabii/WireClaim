"""Fit the Charge and the Limit on the *recent* window, because the estimator's level moved.

    PYTHONPATH=. pixi run python scripts/experiments/regime_ab_sweep.py

Why a recent-window fit is not the usual overfitting mistake
------------------------------------------------------------
This project's standing rule is to validate over every settled Game and to require all four
folds. That rule exists because fitting a constant to a handful of Games has repeatedly
produced numbers that reversed. It is kept here -- the full-record columns are printed
alongside -- but there is a specific, measured reason to look at the recent window separately,
and it is not a hunch:

    window     median log(t_hat/t)   our `a` above `t`   our `a` <= `t`
    G26-40            +0.58                 79             79  (50%)
    G41-55            +0.62                 80             91  (53%)
    G56-64            +1.96                 56             22  (28%)

`a > t` is not an inference from a bracket. A *rightful* rejection of our Charge is direct
evidence that `a > t`, because the reviewer owes nothing only when the Charge exceeds the Fair
Value. So the third row says our Charge now lands above `t` on 72% of Line Items against 50%
before, and it is the reason fair income per Game fell from 39,773 (G41-55) to 13,894
(G56-64) while the honest ceiling per Game fell only from 47,506 to 30,813.

That matters because of the asymmetry in the payoff table: a fair Charge is owed by **all
sixteen** opponents whatever their Limits, an Overcharge is paid only by the few who accept.
So the optimal multiplier is a function of how far out the estimate is, and the estimate got
worse. A constant fitted when 50% of Charges were fair is not the right constant when 28% are.

A pooled sweep cannot see this. Over all 64 Games a global `x0.9` on the Charge scores
-118,049 and every lower value is worse, monotonically -- which reads as "the level is already
optimal". It is optimal *for the average of two different regimes*.

What is swept
-------------
Two multipliers, applied inside the shipped `price_item` arithmetic so nothing else changes:

    charge_k   charge = charge_factor(sigma) * median * charge_k   (then BIG_ITEM_CHARGE_SCALE)
    limit_m    limit  = <the shipped quantile/ceiling/cap result> * limit_m, still clamped <= charge

The `limit <= charge` clamp is kept because it is load-bearing: the Limit is a lower quantile
of the same posterior than the Charge, and letting `b > a` would mean accepting our own
Overcharge.

Windows are nested -- last 10, 15, 20 Games and the full record -- because **a fitted value is
only worth shipping if it is the argmax, or near it, on more than one of them.** An argmax that
appears at 10 Games and vanishes at 20 is noise: the floor at n=10 is +/-19,842.
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


def price(row, *, charge_k: float, limit_m: float) -> tuple[float, float]:
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    median = filled.price_median
    memory = "B:memory" in row.channels
    covered = 0.0 if row.uncovered else filled.coverage_probability

    charge = charge_factor(sigma) * median * charge_k
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
        limit = min(candidates) * limit_m
    return round(max(charge, 0.0), 2), round(max(min(limit, charge), 0.0), 2)


def net_of(rows, games, *, charge_k: float, limit_m: float) -> float:
    total = 0.0
    for game_id in games:
        sub = {
            r.index: price(r, charge_k=charge_k, limit_m=limit_m)
            for r in rows
            if r.game == game_id
        }
        if sub:
            total += replay(snapshot(game_id), sub).net
    return total


def fair_count(rows, games, *, charge_k: float) -> tuple[int, int]:
    fair = over = 0
    wanted = set(games)
    for row in rows:
        if row.game not in wanted:
            continue
        charge, _ = price(row, charge_k=charge_k, limit_m=1.0)
        t = row.t_lo if row.t_hi == INF else (row.t_lo + row.t_hi) / 2.0
        if charge <= t:
            fair += 1
        else:
            over += 1
    return fair, over


def main() -> None:
    rows = dataset()
    games = sorted({r.game for r in rows})
    windows = {
        "last10": games[-10:],
        "last15": games[-15:],
        "last20": games[-20:],
        "all": games,
    }
    print(
        f"{len(games)} Games ({games[0]}-{games[-1]}), {len(rows)} Line Items.\n"
        + "  ".join(f"{k}=G{v[0]}-{v[-1]} (floor +/-{noise(len(v)):,.0f})" for k, v in windows.items())
        + "\n"
    )

    print("=== the Charge alone, global multiplier, Limit untouched ===\n")
    print(f"{'charge x':<11}" + "".join(f"{k:>12}" for k in windows) + "   fair/over on last10")
    print("-" * (11 + 12 * len(windows) + 24))
    base = {k: net_of(rows, v, charge_k=1.0, limit_m=1.0) for k, v in windows.items()}
    for k in (0.40, 0.50, 0.60, 0.70, 0.80, 0.91, 1.00, 1.10):
        cells = [net_of(rows, v, charge_k=k, limit_m=1.0) - base[n] for n, v in windows.items()]
        fair, over = fair_count(rows, windows["last10"], charge_k=k)
        print(f"{f'x {k:.2f}':<11}" + "".join(f"{c:>+12,.0f}" for c in cells) + f"   {fair:>3}/{over:<3}")
    print(f"\n{'(baseline)':<11}" + "".join(f"{base[k]:>12,.0f}" for k in windows))

    print("\n\n=== the Limit alone, global multiplier on the shipped result ===\n")
    print(f"{'limit x':<11}" + "".join(f"{k:>12}" for k in windows))
    print("-" * (11 + 12 * len(windows)))
    for m in (0.50, 0.75, 1.00, 1.18, 1.50, 2.00, 3.00):
        cells = [net_of(rows, v, charge_k=1.0, limit_m=m) - base[n] for n, v in windows.items()]
        print(f"{f'x {m:.2f}':<11}" + "".join(f"{c:>+12,.0f}" for c in cells))

    print("\n\n=== jointly, on the last 10 Games (the window the regime shift covers) ===\n")
    charges = (0.40, 0.50, 0.60, 0.70, 0.80, 0.91, 1.00)
    limits = (0.50, 0.75, 1.00, 1.18, 1.50)
    print(f"{'charge \\ limit':<15}" + "".join(f"{f'x{m:.2f}':>12}" for m in limits))
    print("-" * (15 + 12 * len(limits)))
    best = None
    for k in charges:
        cells = []
        for m in limits:
            value = net_of(rows, windows["last10"], charge_k=k, limit_m=m)
            cells.append(value)
            if best is None or value > best[0]:
                best = (value, k, m)
        print(f"{f'x{k:.2f}':<15}" + "".join(f"{c:>12,.0f}" for c in cells))
    print(f"\n  argmax on last10: charge x{best[1]:.2f}, limit x{best[2]:.2f} -> {best[0]:,.0f} "
          f"against the shipped {base['last10']:,.0f} (+{best[0] - base['last10']:,.0f})")
    print(f"  noise floor at n=10 is +/-{noise(10):,.0f}: a gain smaller than that is not a result.")
    print("\n  Now the same pair on the wider windows -- this is the test that matters:")
    for name, window in windows.items():
        value = net_of(rows, window, charge_k=best[1], limit_m=best[2])
        print(f"    {name:>7} ({len(window):>2} Games): {value:>12,.0f} vs shipped {base[name]:>12,.0f}"
              f"  delta {value - base[name]:>+12,.0f}")


if __name__ == "__main__":
    main()
