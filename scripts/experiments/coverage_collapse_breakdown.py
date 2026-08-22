"""Of the 102,323 wrongful-rejection penalty sitting on coverage-collapsed (b=0) items, how
much sits on items where the collapse was *wrong* (true t > 0)? Structurally almost all of
it must be: a wrongful-rejection penalty on a collapsed item requires an opponent Charge in
(0, t], which is only possible when t > 0. This checks that arithmetic fact empirically and
reports the COVERAGE_FLOOR-vs-verdict question the coordinator asked for -- NOT a re-run of
the closed coverage-oracle study.

    PYTHONPATH=. pixi run python scripts/experiments/coverage_collapse_breakdown.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.charge_buckets import ALL_GAMES, dataset, snapshot  # noqa: E402
from scripts.replay_payoffs import INF  # noqa: E402

from src.domain.pricing.engine import COVERAGE_FLOOR  # noqa: E402


def main() -> None:
    rows = dataset(games=ALL_GAMES)
    n_collapsed = 0
    n_collapsed_t_pos = 0
    n_collapsed_t_zero = 0
    penalty_t_pos = 0.0
    penalty_t_zero = 0.0
    itemized = []

    for row in rows:
        snap = snapshot(row.game)
        if row.index not in snap.line_items:
            continue
        covered = 0.0 if row.uncovered else row.evidence.coverage_probability
        if covered > COVERAGE_FLOOR:
            continue  # not a collapsed item
        n_collapsed += 1
        t = snap.fair_point(row.index)
        pen = 0.0
        for team in snap.opponents:
            opp_charge = snap.charges[row.index].get(team, INF)
            if opp_charge == INF:
                continue
            if 0.0 < opp_charge <= t:  # limit is 0, so any positive charge <= t is wrongful
                pen += 1.5 * opp_charge
        if t > 0:
            n_collapsed_t_pos += 1
            penalty_t_pos += pen
        else:
            n_collapsed_t_zero += 1
            penalty_t_zero += pen
        if pen > 0:
            itemized.append((row.game, row.index, covered, t, row.t_lo, row.t_hi, pen))

    total_pen = penalty_t_pos + penalty_t_zero
    print(f"Collapsed items (coverage <= {COVERAGE_FLOOR:.3f}): {n_collapsed}")
    print(f"  true t > 0 (collapse was WRONG): {n_collapsed_t_pos} items, penalty {penalty_t_pos:,.2f}")
    print(f"  true t = 0 (collapse was right, t_lo used as point): {n_collapsed_t_zero} items, penalty {penalty_t_zero:,.2f}")
    print(f"  total penalty: {total_pen:,.2f}  (share on t>0 items: {penalty_t_pos/total_pen:.1%})" if total_pen else "no penalty")

    print(f"\n{len(itemized)} collapsed items carry any wrongful-rejection penalty at all:")
    print(f"{'game':>5}{'item':>5}{'coverage_p':>12}{'t_point':>10}{'t_lo':>8}{'t_hi':>10}{'penalty':>12}")
    for g, idx, cov, t, tlo, thi, pen in sorted(itemized, key=lambda r: -r[-1]):
        thi_s = "inf" if thi == INF else f"{thi:.0f}"
        print(f"{g:>5}{idx:>5}{cov:>12.2f}{t:>10.0f}{tlo:>8.0f}{thi_s:>10}{pen:>12,.0f}")


if __name__ == "__main__":
    main()
