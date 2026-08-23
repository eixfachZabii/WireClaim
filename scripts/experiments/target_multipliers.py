"""What should `a` and `b` actually be, as multiples of `t_hat`? Swept against the real Field.

The question this answers
-------------------------
R11 fixes the boundary condition: with `t` known, `a = t` and `b = t` are both optimal, the
Charge is a **cliff** (1 % over costs 6,038,602) and the Limit an asymmetric **valley** (1 % low
costs 113,527, 1 % high 5,403). That says the Charge needs a discount and the Limit does not --
but not how much of either, because the size of both depends on how wrong `t_hat` is.

`ceiling.py` rules out the lazy answer: the best flat pair `(alpha, beta)` anywhere in a 72-cell
grid scores **115,593 worse** than what we shipped, because the shipped Charge factor already
varies with the band width and a constant throws that information away. So the object to sweep
is not two numbers, it is the *rule*:

    a = clamp(A - B * sigma_hat, lo, hi) * t_hat        shipped: A = 0.85, B = 0.45, [0.30, 0.80]
    b = C * t_hat                                        shipped: an interacting stack of a
                                                         quantile, a ceiling and a cap

`sigma_hat` is the width the model asserted. It is a **bad** estimate of our real error -- median
0.350 against a realised 0.658 -- but that is not a reason to ignore it here. The question is
whether it *ranks* items usefully, and a sweep of `B` answers exactly that: if `B = 0` wins, the
asserted width carries no signal and the Charge should be a flat multiple.

Method
------
Every Line Item with a logged `t_hat` (Games 26-100) is repriced from the rule above and replayed
against the Field's real Charges and Limits; Games without a logged estimate keep our real
submission, so the sweep is never credited with Games it could not have priced. Weighted at 3x
for Games 81-100. Folds reported for every winning cell, because a total that one regime bought
is not a result.

Usage
-----
    PYTHONPATH=. python scripts/experiments/target_multipliers.py
    PYTHONPATH=. python scripts/experiments/target_multipliers.py --limit-only
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from replay_payoffs import US, our_actual_submission, reconstruction_status, replay, snapshot  # noqa: E402

EXPORT = ROOT / "var" / "export" / "line_items.csv"
WEIGHTED = frozenset(range(81, 101))

SHIPPED_A, SHIPPED_B = 0.85, 0.45
BOUNDS = (0.30, 0.80)


def weight(game_id: int) -> float:
    return 3.0 if game_id in WEIGHTED else 1.0


def load() -> dict[tuple[int, int], tuple[float, float]]:
    """`(game, index) -> (t_hat, sigma_hat)` exactly as the live pipeline produced them."""
    out: dict[tuple[int, int], tuple[float, float]] = {}
    for row in csv.DictReader(EXPORT.open()):
        try:
            t_hat = float(row["t_hat"])
        except (TypeError, ValueError):
            continue
        if t_hat <= 0:
            continue
        try:
            sigma = float(row["sigma"])
        except (TypeError, ValueError):
            sigma = 0.5
        out[(int(row["game_id"]), int(row["line_item_index"]))] = (t_hat, sigma)
    return out


def charge_factor(sigma: float, intercept: float, slope: float) -> float:
    return min(max(intercept - slope * sigma, BOUNDS[0]), BOUNDS[1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-only", action="store_true")
    args = parser.parse_args()

    estimates = load()
    snaps = [s for s in (snapshot(g, US) for g in range(1, 101)
                         if reconstruction_status(g, US).usable)
             if any((s.game_id, i) in estimates for i in s.line_items)]
    print(f"\n{len(snaps)} Games carry a logged estimate ({len(estimates)} Line Items).")

    def total(intercept, slope, beta, subset=None) -> float:
        got = 0.0
        for snap in (subset or snaps):
            mine = our_actual_submission(snap)
            sub = {}
            for index in snap.line_items:
                found = estimates.get((snap.game_id, index))
                if found is None:
                    sub[index] = mine[index]
                    continue
                t_hat, sigma = found
                sub[index] = (charge_factor(sigma, intercept, slope) * t_hat, beta * t_hat)
            got += replay(snap, sub).net * weight(snap.game_id)
        return got

    folds = {
        "odd": [s for s in snaps if s.game_id % 2],
        "even": [s for s in snaps if not s.game_id % 2],
        "26-62": [s for s in snaps if s.game_id <= 62],
        "63-100": [s for s in snaps if s.game_id > 62],
    }

    # ---------------------------------------------------------------- the Limit
    print("\n" + "=" * 74)
    print("THE LIMIT -- b as a multiple of t_hat, Charge held at the shipped rule")
    print("=" * 74)
    print(f"  {'b / t_hat':>10}{'weighted':>16}" + "".join(f"{k:>12}" for k in folds))
    print(f"  {'-'*10:>10}{'-'*16:>16}" + "".join(f"{'-'*12:>12}" for _ in folds))
    best_b = None
    for beta in (0.0, 0.25, 0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0):
        got = total(SHIPPED_A, SHIPPED_B, beta)
        cells = "".join(f"{total(SHIPPED_A, SHIPPED_B, beta, s):>12,.0f}" for s in folds.values())
        print(f"  {beta:>10.2f}{got:>16,.0f}{cells}")
        if best_b is None or got > best_b[1]:
            best_b = (beta, got)
    print(f"\n  best b = {best_b[0]:g} x t_hat")

    if args.limit_only:
        return

    # --------------------------------------------------------------- the Charge
    print("\n" + "=" * 74)
    print(f"THE CHARGE -- a = clamp(A - B*sigma, {BOUNDS[0]}, {BOUNDS[1]}) x t_hat, "
          f"Limit at b = {best_b[0]:g}")
    print("=" * 74)
    print(f"  {'A':>6}{'B':>6}{'weighted':>16}   effective factor at sigma 0.25 / 0.35 / 0.60")
    print(f"  {'-'*6:>6}{'-'*6:>6}{'-'*16:>16}")
    best_c = None
    for intercept in (0.60, 0.70, 0.75, 0.85, 0.95, 1.05):
        for slope in (0.0, 0.25, 0.45, 0.70):
            got = total(intercept, slope, best_b[0])
            eff = " / ".join(
                f"{charge_factor(s, intercept, slope):.2f}" for s in (0.25, 0.35, 0.60)
            )
            mark = "   <- shipped" if (intercept, slope) == (SHIPPED_A, SHIPPED_B) else ""
            print(f"  {intercept:>6.2f}{slope:>6.2f}{got:>16,.0f}   {eff}{mark}")
            if best_c is None or got > best_c[2]:
                best_c = (intercept, slope, got)
    print(f"\n  best: A = {best_c[0]:.2f}, B = {best_c[1]:.2f} at {best_c[2]:,.0f}")

    shipped = total(SHIPPED_A, SHIPPED_B, best_b[0])
    print(f"  shipped rule at the same Limit: {shipped:,.0f}   "
          f"(sweep gains {best_c[2] - shipped:+,.0f})")

    print(f"\n  folds at the best cell:")
    for name, subset in folds.items():
        a = total(best_c[0], best_c[1], best_b[0], subset)
        b = total(SHIPPED_A, SHIPPED_B, best_b[0], subset)
        print(f"    {name:<8}{a - b:>+12,.0f}")


if __name__ == "__main__":
    main()
