"""Independent reproduction of the upward-charge finding (upward-charge task, item 1).

The claim under test: over our own settled Charges, split by whether the recovered Fair
Value bracket is bounded (t known) or unbounded (t >= t_lo only, selection-biased toward
items nobody rightfully rejected), the ratio `our Charge / t_lo` runs high on bounded items
and low on unbounded ones -- a dispersion error, not a level error.

This does NOT reuse `charge_buckets.py`'s counterfactual Rule -- that recomputes what
*today's* shipped constants would have charged on cached evidence, which is the right tool
for tuning but the wrong one for "what did we actually charge". Games 1-20ish ran earlier
pricing code and Games 21-24 are documented (CLAUDE.md rule 1b) to have submitted
`STANDARD_LIMIT = 35` when Strategy 2 did not land. So this script reads the ACTUAL
submitted Charge straight from the reconstructed Transactions
(`replay_payoffs.snapshot(...).charges[index][US]`), which is authoritative regardless of
which pipeline produced it, and only borrows `charge_buckets.dataset()` for the estimate
`t_hat` (the merged model/memory median at decision time) via an inner join on (game, index).

Vintage: Games 1-38 (`completed_games()` as of this measurement; matches
`var/price_memory.json.built_from_games` and the pinned copy at
`scripts/experiments/pinned/price_memory_vintage_g38.json`). Decision logs cover
Games 26-38; Games 1-25 fall back to `charge_buckets`' reconstruction from cached evidence.

Usage
-----
    PYTHONPATH=. python scripts/experiments/upward_charge_verify.py
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from charge_buckets import ALL_GAMES, dataset  # noqa: E402
from replay_payoffs import US, snapshot  # noqa: E402

INF = float("inf")


def main() -> None:
    est = {(r.game, r.index): r.median for r in dataset()}

    n_charge_rows = 0
    n_unrecoverable = 0
    worth = []  # (game, index, charge, t_lo, t_hi, that_hat_or_None)
    for game_id in ALL_GAMES:
        snap = snapshot(game_id)
        for index in snap.line_items:
            charge = snap.charges[index].get(US)
            if charge is None:
                continue
            n_charge_rows += 1
            if charge == INF:
                n_unrecoverable += 1
                continue
            t_lo, t_hi = snap.fair_brackets[index]
            if t_lo <= 0:
                continue
            worth.append((game_id, index, charge, t_lo, t_hi, est.get((game_id, index))))

    bounded = [w for w in worth if w[4] != INF]
    unbounded = [w for w in worth if w[4] == INF]

    def ratio_stats(pop, num_getter):
        vals = sorted(num_getter(w) / w[3] for w in pop if num_getter(w) is not None)
        if not vals:
            return None
        n = len(vals)
        med = statistics.median(vals)
        p75 = vals[min(int(0.75 * n), n - 1)]
        return n, med, p75

    print(f"vintage: Games {ALL_GAMES[0]}-{ALL_GAMES[-1]} ({len(ALL_GAMES)} Games)")
    print(f"total (game, index) rows with a recoverable actual Charge: {n_charge_rows}")
    print(f"unrecoverable Charges (rejected by all 16, nothing moved): {n_unrecoverable}")
    print(f"of the recoverable ones, t_lo > 0 (worth something): {len(worth)}")
    print(f"  bounded (t known exactly):        {len(bounded)}")
    print(f"  unbounded (t >= t_lo, censored):  {len(unbounded)}")

    print(f"\n{'population':<28}{'n':>5}   {'Charge / t_lo':<22}{'t_hat / t_lo':<22}")
    print(f"{'':28}{'':5}   {'median':>8}{'p75':>8}      {'median':>8}{'p75':>8}")
    for label, pop in (
        ("all items worth something", worth),
        ("bracket bounded (t known)", bounded),
        ("bracket unbounded (t>=t_lo)", unbounded),
    ):
        a = ratio_stats(pop, lambda w: w[2])
        e = ratio_stats(pop, lambda w: w[5])
        a_s = f"{a[1]:>8.2f}{a[2]:>8.2f}" if a else f"{'--':>8}{'--':>8}"
        e_s = f"{e[1]:>8.2f}{e[2]:>8.2f}   (n={e[0]})" if e else f"{'--':>8}{'--':>8}   (n=0)"
        print(f"{label:<28}{len(pop):>5}   {a_s}      {e_s}")

    # "Provably below/above t" -- charge < t_lo is a proof regardless of boundedness;
    # charge > t_hi is only provable where t_hi is finite.
    below = sum(1 for w in worth if w[2] < w[3])
    above = sum(1 for w in worth if w[4] != INF and w[2] > w[4])
    print(
        f"\nprovably below t (Charge < t_lo):  {below}/{len(worth)} = {below / len(worth):.0%}"
    )
    print(
        f"provably above t (Charge > t_hi, bounded only): "
        f"{above}/{len(worth)} = {above / len(worth):.0%}"
    )
    print(
        "(neither: Charge sits inside [t_lo, t_hi) or the bracket is unbounded and "
        "Charge >= t_lo -- consistent with fair, not provably either way)"
    )

    # Sanity: t_hat/t_lo on unbounded items below 1.0 is a PROOF the estimate undershoots,
    # since t_lo is a hard lower bound on the true t.
    unb_est = [w[5] / w[3] for w in unbounded if w[5] is not None]
    if unb_est:
        under = sum(1 for v in unb_est if v < 1.0)
        print(
            f"\nunbounded items where t_hat < t_lo (estimate PROVEN too low): "
            f"{under}/{len(unb_est)} = {under / len(unb_est):.0%}"
        )


if __name__ == "__main__":
    main()
