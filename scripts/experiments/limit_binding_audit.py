"""Which clamp binds on the Limit -- LIMIT_QUANTILE, LIMIT_CEILING, LIMIT_CAP, or the b<=a
charge clamp -- and how much wrongful-rejection penalty sits behind each, on today's shipped
pricing applied to every settled Game.

    PYTHONPATH=. pixi run python scripts/experiments/limit_binding_audit.py

Method: one row per (Game, Line Item) from `charge_buckets.dataset()` -- the decision log
where one exists (Games 26-35), else the reconstructed evidence cache priced by TODAY's
shipped constants (Games 1-25), which is the same "what today's pricing would have done"
counterfactual every constant in `src/domain/pricing/engine.py` is tuned against. For each
row: recompute `price_item`'s three candidate values (quantile-implied limit, ceiling*median,
cap) under the CURRENT shipped constants, find the argmin, and replay the resulting
(charge, limit) against the real Field to get the wrongful-rejection penalty on that specific
item (the `1.5a` component of `reviewer_payoff`, not the whole item cost).
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.charge_buckets import ALL_GAMES, Row, dataset, snapshot  # noqa: E402
from scripts.replay_payoffs import INF  # noqa: E402

from src.pricing.engine import (  # noqa: E402
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


def charge_of(sigma: float, median: float) -> float:
    low, high = CHARGE_BOUNDS
    factor = min(max(CHARGE_INTERCEPT - CHARGE_SLOPE * sigma, low), high)
    return max(factor, 0.0) * median


def price_and_bind(row: Row) -> tuple[float, float, str]:
    """Returns (charge, limit, binding_label) under TODAY's shipped constants."""
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    covered = 0.0 if row.uncovered else filled.coverage_probability
    charge = charge_of(sigma, filled.price_median)

    if covered <= COVERAGE_FLOOR:
        return round(max(charge, 0.0), 2), 0.0, "coverage-collapse (b=0)"

    conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
    quantile_limit = _lognormal_quantile(filled.price_median, sigma, conditional)
    ceiling_limit = LIMIT_CEILING * filled.price_median
    cap_limit = LIMIT_CAP

    candidates = {
        "quantile (1/3 posterior)": quantile_limit,
        "ceiling (0.45 x median)": ceiling_limit,
        "cap (708 flat)": cap_limit,
    }
    label = min(candidates, key=candidates.get)
    limit = candidates[label]

    if charge < limit:
        label = "charge-clamp (b<=a)"
        limit = charge

    return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2), label


def wrongful_rejection_penalty(snap, index: int, charge: float, limit: float) -> float:
    """Sum of `1.5 * opp_charge` over opponents whose fair Charge we wrongfully rejected."""
    t = snap.fair_point(index)
    total = 0.0
    for team in snap.opponents:
        opp_charge = snap.charges[index].get(team, INF)
        if opp_charge == INF:
            continue
        if opp_charge > limit and opp_charge <= t:
            total += 1.5 * opp_charge
    return total


def main() -> None:
    games = ALL_GAMES
    rows = dataset(games=games)
    print(f"Rows: {len(rows)} across Games {games[0]}-{games[-1]} ({len(games)} Games)\n")

    by_label: dict[str, list[Row]] = {}
    penalty_by_label: dict[str, float] = {}
    tratio_by_label: dict[str, list[float]] = {}
    itemized: list[tuple[str, int, int, float, float, float, float]] = []
    n_items = 0
    n_priced_out_of = 0

    for row in rows:
        n_items += 1
        snap = snapshot(row.game)
        if row.index not in snap.line_items:
            continue
        n_priced_out_of += 1
        charge, limit, label = price_and_bind(row)
        by_label.setdefault(label, []).append(row)
        pen = wrongful_rejection_penalty(snap, row.index, charge, limit)
        penalty_by_label[label] = penalty_by_label.get(label, 0.0) + pen

        # t-hat / t, using the midpoint of the recovered bracket (inf-safe: only when bounded)
        t_mid = None
        if row.t_hi != INF:
            t_mid = (row.t_lo + row.t_hi) / 2.0
            if t_mid > 0:
                tratio_by_label.setdefault(label, []).append(row.median / t_mid)
        if pen > 0:
            itemized.append((label, row.game, row.index, row.median, t_mid or float("nan"), limit, pen))
        if label == "cap (708 flat)":
            print(
                f"CAP-BOUND  G{row.game:<3} item {row.index:<3} t_hat={row.median:<8.0f} "
                f"t_lo={row.t_lo:<8.0f} t_hi={row.t_hi if row.t_hi != INF else float('inf'):<8} "
                f"t_hat/t_lo={(row.median / row.t_lo if row.t_lo > 0 else float('inf')):<6.2f} "
                f"pen={pen:<10,.0f} sigma={row.sigma:.2f} origin={row.origin} channels={row.channels}"
            )

    total_penalty = sum(penalty_by_label.values())

    print(f"Priced rows: {n_priced_out_of} of {n_items}\n")
    print(f"{'binding constraint':<28}{'items':>7}{'share':>8}{'penalty':>14}{'pen share':>11}")
    for label in sorted(by_label, key=lambda l: -penalty_by_label.get(l, 0.0)):
        n = len(by_label[label])
        pen = penalty_by_label.get(label, 0.0)
        print(
            f"{label:<28}{n:>7}{n / n_priced_out_of:>8.1%}"
            f"{pen:>14,.2f}{(pen / total_penalty if total_penalty else 0):>11.1%}"
        )
    print(f"{'TOTAL':<28}{n_priced_out_of:>7}{'':>8}{total_penalty:>14,.2f}\n")

    print("t-hat / t distribution (bounded-bracket items only), by binding constraint:")
    for label in sorted(tratio_by_label, key=lambda l: -penalty_by_label.get(l, 0.0)):
        vals = sorted(tratio_by_label[label])
        if not vals:
            continue
        med = statistics.median(vals)
        p25 = vals[len(vals) // 4]
        p75 = vals[min(len(vals) - 1, 3 * len(vals) // 4)]
        print(
            f"  {label:<28} n={len(vals):<4} median t_hat/t={med:.2f}  "
            f"p25={p25:.2f} p75={p75:.2f}"
        )

    print("\nItemized: every (Game, item) with cap or ceiling as the binding constraint, penalty > 0")
    print(f"{'bind':<10}{'game':>5}{'item':>5}{'t_hat':>9}{'t_mid':>9}{'t_hat/t':>9}{'limit':>9}{'penalty':>12}")
    for label, game, index, t_hat, t_mid, limit, pen in sorted(
        itemized, key=lambda r: -r[-1]
    ):
        if "cap" not in label and "ceiling" not in label:
            continue
        ratio = f"{t_hat / t_mid:.2f}" if t_mid and t_mid == t_mid else "n/a"
        tmid_s = f"{t_mid:.0f}" if t_mid and t_mid == t_mid else "inf"
        tag = "cap" if "cap" in label else "ceil"
        print(f"{tag:<10}{game:>5}{index:>5}{t_hat:>9.0f}{tmid_s:>9}{ratio:>9}{limit:>9.0f}{pen:>12,.0f}")


if __name__ == "__main__":
    main()
