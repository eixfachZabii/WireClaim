"""How does an upward multiplier's euros split between "stayed below t" and "crossed above
t"? (upward-charge task, item 5)

For each candidate, every priced Line Item with `t_lo > 0` falls into one of three buckets,
comparing the shipped Charge against the candidate Charge to the point estimate of `t`
(`Row.t`: the bracket midpoint when bounded, `t_lo` when not):

    stayed below t     both Charges <= t         -- extra income captured, no new risk
    crossed above t     shipped <= t, candidate > t  -- the multiplier CAUSED an Overcharge
    already above t     shipped already > t        -- multiplier makes an existing
                                                        Overcharge worse (or, for t_lo = 0
                                                        items, costs nothing per R6c)

`_income(row, charge)` replays what the real Field actually pays for a given Charge on that
Line Item (all 16 opponents' reconstructed Limits), so the euros are the real payoff, not a
theoretical `a * P(accept)`.

Usage
-----
    PYTHONPATH=. python scripts/experiments/upward_charge_cliff.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from charge_buckets import ALL_GAMES, Rule, _income, dataset  # noqa: E402

CANDIDATES = [
    Rule(name="memory x1.15", scale=lambda r: 1.15 if r.has_memory else 1.0),
    Rule(name="metered x1.1", scale=lambda r: 1.1 if r.metered else 1.0),
    Rule(name="memory & metered x1.1", scale=lambda r: 1.1 if (r.has_memory and r.metered) else 1.0),
]


def main() -> None:
    rows = [r for r in dataset() if r.game in ALL_GAMES and r.t_lo > 0]
    shipped = Rule()
    print(f"{len(rows)} rows with t_lo > 0 over Games {ALL_GAMES[0]}-{ALL_GAMES[-1]}\n")

    for candidate in CANDIDATES:
        stayed_n = stayed_gain = 0.0
        crossed_n = crossed_loss = 0.0  # candidate income - shipped income, on crossers (<=0 expected)
        already_n = already_delta = 0.0
        touched = 0
        for row in rows:
            base_charge, _ = shipped.price(row)
            cand_charge, _ = candidate.price(row)
            if abs(cand_charge - base_charge) < 1e-9:
                continue  # multiplier did not touch this row (selector false)
            touched += 1
            t = row.t
            base_income = _income(row, base_charge)
            cand_income = _income(row, cand_charge)
            delta = cand_income - base_income
            base_side = base_charge <= t
            cand_side = cand_charge <= t
            if base_side and cand_side:
                stayed_n += 1
                stayed_gain += delta
            elif base_side and not cand_side:
                crossed_n += 1
                crossed_loss += delta
            else:
                already_n += 1
                already_delta += delta

        print(f"=== {candidate.name} ===  ({touched} rows touched by the selector)")
        print(
            f"  stayed below t:   n={stayed_n:>4.0f}   income delta {stayed_gain:>+12,.0f}  "
            f"(extra euros captured, no new risk)"
        )
        print(
            f"  crossed above t:  n={crossed_n:>4.0f}   income delta {crossed_loss:>+12,.0f}  "
            f"(income forgone -- the multiplier caused this)"
        )
        print(
            f"  already above t:  n={already_n:>4.0f}   income delta {already_delta:>+12,.0f}  "
            f"(was already an Overcharge; multiplier made it worse, or item is t_lo>0 but "
            f"shipped already priced above the point estimate)"
        )
        net = stayed_gain + crossed_loss + already_delta
        print(f"  net over these {touched} touched rows: {net:>+12,.0f}\n")


if __name__ == "__main__":
    main()
