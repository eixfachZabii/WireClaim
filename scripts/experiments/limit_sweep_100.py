"""What our Limit was worth, over all 100 Games, holding the whole Field fixed.

`postmortem.py` says we paid a **657,382** lawyer surcharge -- the pure-penalty half of the
`1.5a` we owed on 3,873 fair Charges we rejected -- against **184,806** of Overcharges we let
through. Those two numbers are the two directions the Limit can be wrong in, and they are not
remotely balanced. This measures the trade directly rather than arguing from the ratio.

The counterfactual is exact and needs no model. Our real Charge `a` and Limit `b` are
recovered from the settled Transactions (`replay_payoffs.our_actual_submission`); we resubmit
`(a, lambda * b)` for a grid of `lambda`, hold every opponent's Charge and Limit at what they
really were, and score the real payoff table against the recovered Fair Value brackets. The
income side is provably untouched -- for `a <= t` the Issuer is paid `a` whether the Reviewer
accepts or wrongfully rejects, so scaling *our* Limit moves the cost column only.

Which means the sweep isolates one question with nothing else moving:

    was our Limit too low, and by how much?

Games 81-100 pay 3x, so the weighted total is the one that ranks us; both are reported
because a knob that only works under the tripled weight is a knob that got lucky twice.

Usage
-----
    PYTHONPATH=. python scripts/experiments/limit_sweep_100.py
    PYTHONPATH=. python scripts/experiments/limit_sweep_100.py --games 1-80
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from replay_payoffs import (  # noqa: E402
    US,
    our_actual_submission,
    replay,
    reconstruction_status,
    snapshot,
)

WEIGHTED = frozenset(range(81, 101))
GRID = [0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0, 12.0, 20.0, 1e9]


def weight(game_id: int) -> float:
    return 3.0 if game_id in WEIGHTED else 1.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-100")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    ids = list(range(int(start), int(end or start) + 1))

    snaps = []
    for game_id in ids:
        status = reconstruction_status(game_id, US)
        if not status.usable:
            print(f"  skipping G{game_id}: {status.status} {status.detail}")
            continue
        snaps.append(snapshot(game_id, US))
    print(f"\n{len(snaps)} reconstructable Games\n")

    print(f"  {'lambda':>8}{'net (1x)':>16}{'net (weighted)':>18}{'income':>16}{'cost':>16}")
    print(f"  {'-' * 8:>8}{'-' * 16:>16}{'-' * 18:>18}{'-' * 16:>16}{'-' * 16:>16}")
    best = None
    for lam in GRID:
        raw = weighted = income = cost = 0.0
        for snap in snaps:
            actual = our_actual_submission(snap)
            hypothetical = {i: (a, b * lam) for i, (a, b) in actual.items()}
            result = replay(snap, hypothetical)
            raw += result.net
            weighted += result.net * weight(snap.game_id)
            income += result.income
            cost += result.cost
        label = "inf" if lam > 1e8 else f"{lam:g}"
        star = ""
        if best is None or weighted > best[1]:
            best, star = (lam, weighted), ""
        print(f"  {label:>8}{raw:>16,.0f}{weighted:>18,.0f}{income:>16,.0f}{cost:>16,.0f}{star}")

    print(f"\n  best lambda = {best[0]:g} at {best[1]:,.0f} weighted")


if __name__ == "__main__":
    main()
