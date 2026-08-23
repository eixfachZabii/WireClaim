"""Is the binding error on big Line Items their price, or whether they are covered at all?

    PYTHONPATH=. pixi run python scripts/experiments/big_item_coverage.py

Game 53 asked the question. A robbery item worth `t >= 8,626` read `coverage 0.42`, the
Limit collapsed to zero and every one of twelve fair Charges was wrongfully rejected:
-77,793 in one Line Item. But fixing coverage alone would have lifted the Limit only to
`LIMIT_CAP` (708), which still rejects eleven of the twelve -- so coverage and the absolute
cap have to be priced *together* or each looks worthless on its own.

Four rules, replayed through `scripts.replay_payoffs.replay` against the real Field, all
differences confined to items where our own estimate said `t_hat >= BIG_ITEM_THRESHOLD`:

    shipped        what we run today
    +oracle        coverage replaced by the truth on big items (covered iff t_lo > 0)
    +cap off       LIMIT_CAP lifted on big items, coverage untouched
    +both          the ceiling of the combined fix

`+oracle` is not shippable -- it reads the answer. It measures the prize for getting
coverage right on this bucket, which is what an adjudication call would compete for.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.charge_buckets import ALL_GAMES, Row, dataset, snapshot  # noqa: E402
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


def price(row: Row, *, oracle_coverage: bool, cap_off: bool) -> tuple[float, float]:
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    median = filled.price_median
    big = median >= BIG_ITEM_THRESHOLD
    memory = "B:memory" in row.channels

    covered = 0.0 if row.uncovered else filled.coverage_probability
    if big and oracle_coverage and not row.uncovered:
        covered = 1.0 if row.t_lo > 0 else 0.0

    charge = charge_factor(sigma) * median
    if big:
        charge *= BIG_ITEM_CHARGE_SCALE

    if covered <= COVERAGE_FLOOR:
        limit = 0.0
    else:
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        ceiling = LIMIT_CEILING_MEMORY if memory else LIMIT_CEILING
        candidates = [_lognormal_quantile(median, sigma, conditional), ceiling * median]
        if not memory and not (big and cap_off):
            candidates.append(LIMIT_CAP)
        limit = min(candidates)
    return round(max(charge, 0.0), 2), round(max(min(limit, charge), 0.0), 2)


def net(rows: list[Row], games: list[int], **kw) -> float:
    total = 0.0
    for game_id in games:
        sub = {r.index: price(r, **kw) for r in rows if r.game == game_id}
        if sub:
            total += replay(snapshot(game_id), sub).net
    return total


def main() -> None:
    rows = dataset()
    games = sorted({r.game for r in rows})
    big = [r for r in rows if r.median >= BIG_ITEM_THRESHOLD]
    print(f"{len(rows)} Line Items over {len(games)} Games; {len(big)} with t_hat >= {BIG_ITEM_THRESHOLD:,.0f}")
    print(f"noise floor over {len(games)} Games: +/-{noise(len(games)):,.0f}\n")

    rules = {
        "shipped": dict(oracle_coverage=False, cap_off=False),
        "+oracle coverage": dict(oracle_coverage=True, cap_off=False),
        "+cap off (big)": dict(oracle_coverage=False, cap_off=True),
        "+both": dict(oracle_coverage=True, cap_off=True),
    }
    folds = {
        "all": games,
        "odd": [g for g in games if g % 2],
        "even": [g for g in games if not g % 2],
        "<=40": [g for g in games if g <= 40],
        ">40": [g for g in games if g > 40],
    }
    base = {name: net(rows, gs, **rules["shipped"]) for name, gs in folds.items()}
    print(f"{'rule':<20}" + "".join(f"{k:>12}" for k in folds))
    print("-" * (20 + 12 * len(folds)))
    for label, kw in rules.items():
        cells = [net(rows, gs, **kw) - base[name] for name, gs in folds.items()]
        print(f"{label:<20}" + "".join(f"{c:>+12,.0f}" for c in cells))
    print(f"\n{'(baseline net)':<20}" + "".join(f"{base[k]:>12,.0f}" for k in folds))




# --------------------------------------------------------------- what is even reachable
#
# Every rule above is a rule about `b`. Before tuning one it is worth knowing the ceiling of
# the whole family: an oracle Limit `b = t` accepts every fair Charge and rejects every
# unfair one, which no rule can beat. Run with `oracle` as the first argument.


def oracle_price(row: Row, *, which: str) -> tuple[float, float]:
    charge, limit = price(row, oracle_coverage=False, cap_off=False)
    big = row.median >= BIG_ITEM_THRESHOLD
    target = row.t_lo if row.t_hi == float("inf") else (row.t_lo + row.t_hi) / 2.0
    if which == "limit-big" and big:
        limit = target
    elif which == "limit-all":
        limit = target
    elif which == "charge-big" and big:
        charge = target
    elif which == "charge-all":
        charge = target
    return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)


def oracle_net(rows: list[Row], games: list[int], which: str) -> float:
    total = 0.0
    for game_id in games:
        sub = {r.index: oracle_price(r, which=which) for r in rows if r.game == game_id}
        if sub:
            total += replay(snapshot(game_id), sub).net
    return total


def oracle_main() -> None:
    rows = dataset()
    games = sorted({r.game for r in rows})
    folds = {
        "all": games,
        "odd": [g for g in games if g % 2],
        "even": [g for g in games if not g % 2],
        "<=40": [g for g in games if g <= 40],
        ">40": [g for g in games if g > 40],
    }
    base = {n: net(rows, gs, oracle_coverage=False, cap_off=False) for n, gs in folds.items()}
    print("The ceiling of each family -- an oracle that reads the settled Fair Value.")
    print("Not shippable; it bounds what any rule in that family could ever earn.\n")
    print(f"{'oracle':<20}" + "".join(f"{k:>12}" for k in folds))
    print("-" * (20 + 12 * len(folds)))
    for which in ("limit-big", "limit-all", "charge-big", "charge-all"):
        cells = [oracle_net(rows, gs, which) - base[n] for n, gs in folds.items()]
        print(f"{which:<20}" + "".join(f"{c:>+12,.0f}" for c in cells))
    print(f"\n{'(baseline net)':<20}" + "".join(f"{base[k]:>12,.0f}" for k in folds))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "oracle":
        oracle_main()
    else:
        main()
