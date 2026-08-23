"""How much of the gap is the estimate, and how much is the decision rule? Four rungs.

Everything in this repository argues about one of two things -- how well we estimate the Fair
Value, and what we do with the estimate -- and almost every argument conflates them. This
separates them by scoring four submissions against the same 100 Games and the same real Field:

    1. DEFAULT      a = 0, b = 0                the tournament's own fallback. Not zero:
                                                `b = 0` wrongfully rejects every fair Charge
                                                and pays `1.5a` for it (R7, R10).
    2. ACTUAL       what we really submitted
    3. BEST-KNOB    a = alpha * t_hat, b = beta * t_hat, best (alpha, beta) over a grid,
                    using *our own* estimate. The ceiling of constant-tuning.
    4. ORACLE       a = b = t                   perfect knowledge, the ceiling of everything.

The three gaps are the whole story:

    ORACLE - BEST-KNOB   what better *estimation* is worth, and nothing else
    BEST-KNOB - ACTUAL   what better *decision rules* are worth on the estimate we already have
    ACTUAL - DEFAULT     what the pipeline earned over going dark

Rung 3 is deliberately the strongest constant-only strategy available, not the one we shipped.
If it sits close to ACTUAL then the decision rules are already at their optimum and no amount
of constant-tuning is worth anything -- which sends every remaining euro to the evidence layer,
and is a far more useful conclusion than another sweep.

Rung 4 uses the bracket midpoint for `t`, or `t_lo` where the bracket is unbounded. That
*understates* the oracle (the truth is at least `t_lo`), so the estimation gap it implies is a
lower bound.

Usage
-----
    PYTHONPATH=. python scripts/experiments/ceiling.py
    PYTHONPATH=. python scripts/experiments/ceiling.py --games 1-80
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from replay_payoffs import (  # noqa: E402
    US,
    our_actual_submission,
    reconstruction_status,
    replay,
    snapshot,
)

EXPORT = ROOT / "var" / "export" / "line_items.csv"
WEIGHTED = frozenset(range(81, 101))

ALPHAS = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1]
BETAS = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]


def weight(game_id: int) -> float:
    return 3.0 if game_id in WEIGHTED else 1.0


def load_estimates() -> dict[tuple[int, int], float]:
    """`(game, index) -> t_hat`, exactly as the live pipeline produced it."""
    out: dict[tuple[int, int], float] = {}
    if not EXPORT.exists():
        return out
    for row in csv.DictReader(EXPORT.open()):
        try:
            value = float(row["t_hat"])
        except (TypeError, ValueError):
            continue
        if value > 0:
            out[(int(row["game_id"]), int(row["line_item_index"]))] = value
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-100")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    ids = range(int(start), int(end or start) + 1)

    estimates = load_estimates()
    snaps = [snapshot(g, US) for g in ids if reconstruction_status(g, US).usable]
    with_estimate = [s for s in snaps if any((s.game_id, i) in estimates for i in s.line_items)]
    print(
        f"\n{len(snaps)} reconstructable Games; {len(with_estimate)} have a logged t_hat "
        f"(Games 26-100 -- the decision log starts there).\n"
    )

    def total(fn) -> tuple[float, float]:
        raw = weighted = 0.0
        for snap in snaps:
            net = replay(snap, fn(snap)).net
            raw += net
            weighted += net * weight(snap.game_id)
        return raw, weighted

    def knobs(alpha: float, beta: float):
        def build(snap):
            out = {}
            for index in snap.line_items:
                t_hat = estimates.get((snap.game_id, index))
                if t_hat is None:
                    # No logged estimate: leave our real submission in place, so this rung
                    # measures the knobs *where the estimate exists* and never credits them
                    # with Games they could not have priced.
                    out[index] = our_actual_submission(snap)[index]
                else:
                    out[index] = (alpha * t_hat, beta * t_hat)
            return out
        return build

    rows = []
    rows.append(("1. DEFAULT (a = 0, b = 0)", *total(lambda s: {i: (0.0, 0.0) for i in s.line_items})))
    rows.append(("2. ACTUAL (what we submitted)", *total(our_actual_submission)))

    best = None
    for alpha in ALPHAS:
        for beta in BETAS:
            raw, weighted = total(knobs(alpha, beta))
            if best is None or weighted > best[2]:
                best = (alpha, beta, weighted, raw)
    rows.append((f"3. BEST-KNOB (a={best[0]}t_hat, b={best[1]}t_hat)", best[3], best[2]))

    rows.append(
        ("4. ORACLE (a = b = t)", *total(lambda s: {i: (s.fair_point(i), s.fair_point(i)) for i in s.line_items}))
    )

    print(f"  {'rung':<40}{'net (1x)':>16}{'net (weighted)':>18}")
    print(f"  {'-' * 40:<40}{'-' * 16:>16}{'-' * 18:>18}")
    for label, raw, weighted in rows:
        print(f"  {label:<40}{raw:>16,.0f}{weighted:>18,.0f}")

    default_w, actual_w, knob_w, oracle_w = (r[2] for r in rows)
    print(f"\n  {'THE THREE GAPS':<40}{'':>16}{'weighted':>18}")
    print(f"  {'-' * 40:<40}{'-' * 16:>16}{'-' * 18:>18}")
    print(f"  {'ACTUAL - DEFAULT  (the pipeline earned)':<40}{'':>16}{actual_w - default_w:>18,.0f}")
    print(f"  {'BEST-KNOB - ACTUAL (better rules worth)':<40}{'':>16}{knob_w - actual_w:>18,.0f}")
    print(f"  {'ORACLE - BEST-KNOB (better ESTIMATE worth)':<40}{'':>16}{oracle_w - knob_w:>18,.0f}")
    share = (oracle_w - knob_w) / max(oracle_w - actual_w, 1e-9)
    print(
        f"\n  Of everything still on the table above ACTUAL, "
        f"{share:.0%} is estimation and {1 - share:.0%} is decision rules."
    )


if __name__ == "__main__":
    main()
