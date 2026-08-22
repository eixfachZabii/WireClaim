"""Sweep flat multipliers on the Charge and the Limit that Strategy 2 already produces.

Separates the two sides of the ledger: the Charge decides income (`a <= t`, paid by all
sixteen opponents), the Limit decides cost (a Limit above `t` buys every opponent's
Overcharge). Both are currently driven off the same band, and for the widths the model
returns they come out nearly equal.

    pixi run python scripts/tail_ab_sweep.py --games 1-14
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from replay_payoffs import replay, snapshot  # noqa: E402
from tail_replay import case_of, inflate, load_evidence, submission_of  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--tag", default="model")
    parser.add_argument("--tail-factor", type=float, default=1.0)
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))

    base = []
    for game_id in game_ids:
        model = load_evidence(game_id, args.tag)
        case = case_of(game_id)
        if model is None or case is None:
            continue
        snap = inflate(snapshot(game_id), args.tail_factor)
        base.append((snap, submission_of(case, model, memory=False)))

    charge_multipliers = [0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5]
    limit_multipliers = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25]
    print("net (EUR) by Charge multiplier (rows) x Limit multiplier (cols)")
    print("      " + "".join(f"{m:>12}" for m in limit_multipliers))
    best = (-1e18, None)
    for cm in charge_multipliers:
        line = f"{cm:5.2f} "
        for lm in limit_multipliers:
            total = 0.0
            for snap, submission in base:
                scaled = {i: (a * cm, b * lm) for i, (a, b) in submission.items()}
                total += replay(snap, scaled).net
            line += f"{total:12,.0f}"
            if total > best[0]:
                best = (total, (cm, lm))
        print(line)
    print(f"best: charge x{best[1][0]} limit x{best[1][1]} net {best[0]:,.0f}")


if __name__ == "__main__":
    main()
