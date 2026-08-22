"""For the best candidate (memory-conditional LIMIT_CEILING), split the extra accepts a
looser Limit buys into fair Charges (save 0.5a vs the shipped rule's wrongful rejection) and
Overcharges (cost the full opponent Charge -- the opponent's own secret Cap has never bound
in the settled record, so `min(a, c) ~= a`).

Also checks whether the coverage-probability-conditional candidate is materially the same
population as the memory-conditional one (i.e. whether it is riding the same signal rather
than an independent one).

    PYTHONPATH=. pixi run python scripts/experiments/fair_vs_overcharge_split.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.charge_buckets import ALL_GAMES, dataset, snapshot  # noqa: E402
from scripts.replay_payoffs import INF  # noqa: E402

from src.domain.pricing.engine import (  # noqa: E402
    CHARGE_BOUNDS,
    CHARGE_INTERCEPT,
    CHARGE_SLOPE,
    COVERAGE_FLOOR,
    LIMIT_CAP,
    LIMIT_CEILING,
    LIMIT_QUANTILE,
    _lognormal_quantile,
    implied_sigma,
)


def price(row, ceiling_fn):
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    covered = 0.0 if row.uncovered else filled.coverage_probability
    low, high = CHARGE_BOUNDS
    factor = min(max(CHARGE_INTERCEPT - CHARGE_SLOPE * sigma, low), high)
    charge = max(factor, 0.0) * filled.price_median
    if covered <= COVERAGE_FLOOR:
        return round(max(charge, 0.0), 2), 0.0
    conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
    q = _lognormal_quantile(filled.price_median, sigma, conditional)
    ceiling = ceiling_fn(row)
    limit = min(q, ceiling * filled.price_median, LIMIT_CAP, charge)
    return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)


def shipped_ceiling(row):
    return LIMIT_CEILING


def memory_ceiling_075(row):
    return 0.75 if row.has_memory else LIMIT_CEILING


def main() -> None:
    rows = dataset(games=ALL_GAMES)

    fair_saving = 0.0
    overcharge_cost = 0.0
    n_fair = 0
    n_over = 0
    n_items_widened = 0
    per_game = {}

    for row in rows:
        snap = snapshot(row.game)
        if row.index not in snap.line_items:
            continue
        s_charge, s_limit = price(row, shipped_ceiling)
        c_charge, c_limit = price(row, memory_ceiling_075)
        if c_limit <= s_limit + 1e-9:
            continue  # not widened by this candidate
        n_items_widened += 1
        t = snap.fair_point(row.index)
        item_fair = 0.0
        item_over = 0.0
        for team in snap.opponents:
            opp_charge = snap.charges[row.index].get(team, INF)
            if opp_charge == INF:
                continue
            if s_limit < opp_charge <= c_limit:
                # newly accepted under the candidate
                if opp_charge <= t:
                    fair_saving += 0.5 * opp_charge
                    item_fair += 0.5 * opp_charge
                    n_fair += 1
                else:
                    overcharge_cost += opp_charge
                    item_over += opp_charge
                    n_over += 1
        if item_fair or item_over:
            per_game.setdefault(row.game, [0.0, 0.0])
            per_game[row.game][0] += item_fair
            per_game[row.game][1] += item_over

    print(f"Items where memory-conditional ceiling (0.75) widens the Limit vs shipped: {n_items_widened}")
    print(f"Newly-accepted fair Charges: {n_fair} instances, total saving (0.5a each) = {fair_saving:,.2f}")
    print(f"Newly-accepted Overcharges:  {n_over} instances, total cost (full a)      = {overcharge_cost:,.2f}")
    print(f"Net from this split: {fair_saving - overcharge_cost:,.2f}")
    print(f"Ratio fair-saving : overcharge-cost = {fair_saving / overcharge_cost if overcharge_cost else float('inf'):.2f} : 1")

    print("\nPer-Game breakdown (fair saving, overcharge cost):")
    for g in sorted(per_game):
        f, o = per_game[g]
        print(f"  G{g:<3}  fair {f:>10,.2f}   overcharge {o:>10,.2f}   net {f - o:>10,.2f}")

    # -- overlap check: memory vs high coverage --
    print("\n--- overlap: memory-backed vs coverage>=0.90 ---")
    both = mem_only = cov_only = neither = 0
    for row in rows:
        cov = 0.0 if row.uncovered else row.evidence.coverage_probability
        is_mem = row.has_memory
        is_cov = cov >= 0.90
        if is_mem and is_cov:
            both += 1
        elif is_mem:
            mem_only += 1
        elif is_cov:
            cov_only += 1
        else:
            neither += 1
    total_mem = both + mem_only
    total_cov = both + cov_only
    print(f"memory-backed: {total_mem}   coverage>=0.90: {total_cov}   both: {both}")
    print(f"of memory-backed items, {both}/{total_mem} ({both/total_mem:.0%}) also have coverage>=0.90" if total_mem else "n/a")
    print(f"of coverage>=0.90 items, {both}/{total_cov} ({both/total_cov:.0%}) also have memory" if total_cov else "n/a")


if __name__ == "__main__":
    main()
