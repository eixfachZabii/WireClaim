"""Does anything available AT DECISION TIME predict "we are underpricing this item"?

(upward-charge task, item 2)

`t_lo` and bracket-boundedness are NOT available live: boundedness is a post-settlement
property (a bracket is unbounded exactly when nobody rightfully rejected our Charge, which
is itself a consequence of how we priced it -- selection bias, not a free signal). So this
tests only fields present in the decision log / evidence layer at submission time:

    t_hat        the merged model/memory median (`Row.median`)
    sigma        the implied band width (`Row.sigma`)
    channel      B:memory (Price Memory anchor) vs C:model only (`Row.has_memory`)
    coverage     `coverage_probability` (`Row.coverage`)
    quantity     invoice quantity (`Row.quantity`)
    metered      hours/m2/day/kg vs pcs/flat rate (`Row.metered`)

Target: is this item PROVABLY underpriced by what we actually charged --
`actual Charge < t_lo` (a hard proof, true regardless of boundedness; see
`upward_charge_verify.py`). This reuses the same actual-Charge join as that script (not
`charge_buckets`'s counterfactual Rule), because the question is about the real submitted
Charge's failure mode, not today's shipped constants' hypothetical one.

Two views per signal:
  * AUC (Mann-Whitney): P(a random underpriced item's signal > a random non-underpriced
    item's signal). 0.5 = no separation; report which direction is informative.
  * Tercile table: underpriced share in the bottom/middle/top third of the signal.

Usage
-----
    PYTHONPATH=. python scripts/experiments/upward_charge_signals.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from charge_buckets import ALL_GAMES, Row, dataset  # noqa: E402
from replay_payoffs import US, snapshot  # noqa: E402

INF = float("inf")


def joined_rows() -> list[tuple[Row, float, float, bool]]:
    """(Row, actual charge, t_lo, underpriced) for every (game, index) with t_lo > 0
    that both the actual-Charge reconstruction and `charge_buckets.dataset()` can see."""
    by_key: dict[tuple[int, int], Row] = {(r.game, r.index): r for r in dataset()}
    out = []
    for game_id in ALL_GAMES:
        snap = snapshot(game_id)
        for index in snap.line_items:
            charge = snap.charges[index].get(US)
            if charge is None or charge == INF:
                continue
            t_lo, _ = snap.fair_brackets[index]
            if t_lo <= 0:
                continue
            row = by_key.get((game_id, index))
            if row is None:
                continue
            out.append((row, charge, t_lo, charge < t_lo))
    return out


def auc(values: list[float], labels: list[bool]) -> tuple[float, int, int]:
    """Mann-Whitney AUC: P(positive-label value > negative-label value), ties = 0.5."""
    pos = [v for v, l in zip(values, labels) if l]
    neg = [v for v, l in zip(values, labels) if not l]
    if not pos or not neg:
        return float("nan"), len(pos), len(neg)
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(pos) * len(neg)), len(pos), len(neg)


def tercile_table(values: list[float], labels: list[bool], name: str) -> None:
    order = sorted(range(len(values)), key=lambda i: values[i])
    n = len(order)
    thirds = [order[: n // 3], order[n // 3 : 2 * n // 3], order[2 * n // 3 :]]
    tags = ["bottom third", "mid third", "top third"]
    print(f"  tercile table for {name}:")
    for tag, idxs in zip(tags, thirds):
        if not idxs:
            continue
        lo, hi = values[idxs[0]], values[idxs[-1]]
        share = sum(labels[i] for i in idxs) / len(idxs)
        print(f"    {tag:<14} [{lo:>8.3g}, {hi:>8.3g}]  n={len(idxs):>3}  underpriced={share:.0%}")


def main() -> None:
    joined = joined_rows()
    labels = [j[3] for j in joined]
    base_rate = sum(labels) / len(labels)
    print(f"joined rows (t_lo > 0, signal available): {len(joined)}")
    print(f"base rate of 'provably underpriced' (Charge < t_lo): {base_rate:.0%}\n")

    numeric_signals = {
        "t_hat (estimate magnitude)": [j[0].median for j in joined],
        "sigma (band width)": [j[0].sigma for j in joined],
        "coverage_probability": [j[0].coverage for j in joined],
        "quantity": [j[0].quantity for j in joined],
    }
    print(f"{'signal':<32}{'AUC':>7}{'n+':>6}{'n-':>6}   informative direction")
    for name, values in numeric_signals.items():
        a, npos, nneg = auc(values, labels)
        direction = "higher -> more underpriced" if a > 0.5 else "lower -> more underpriced"
        flag = "" if abs(a - 0.5) < 0.05 else "  <-- worth a look" if abs(a - 0.5) < 0.10 else "  <-- SEPARATES"
        print(f"{name:<32}{a:>7.3f}{npos:>6}{nneg:>6}   {direction}{flag}")

    print()
    for name, values in numeric_signals.items():
        tercile_table(values, labels, name)
        print()

    # Categorical: channel (memory vs model-only)
    print("channel (categorical):")
    for tag, sel in (
        ("B:memory (has_memory)", lambda j: j[0].has_memory),
        ("C:model only", lambda j: not j[0].has_memory),
    ):
        sub = [j for j in joined if sel(j)]
        share = sum(j[3] for j in sub) / len(sub) if sub else float("nan")
        print(f"    {tag:<24} n={len(sub):>4}  underpriced={share:.0%}")

    print("\nmetered (categorical):")
    for tag, sel in (
        ("metered (hr/m2/day/kg)", lambda j: j[0].metered),
        ("not metered (pcs/flat/unknown)", lambda j: not j[0].metered),
    ):
        sub = [j for j in joined if sel(j)]
        share = sum(j[3] for j in sub) / len(sub) if sub else float("nan")
        print(f"    {tag:<32} n={len(sub):>4}  underpriced={share:.0%}")

    print("\nquantity > 1 (categorical):")
    for tag, sel in (
        ("qty <= 1", lambda j: j[0].quantity <= 1),
        ("qty > 1", lambda j: j[0].quantity > 1),
    ):
        sub = [j for j in joined if sel(j)]
        share = sum(j[3] for j in sub) / len(sub) if sub else float("nan")
        print(f"    {tag:<24} n={len(sub):>4}  underpriced={share:.0%}")


if __name__ == "__main__":
    main()
