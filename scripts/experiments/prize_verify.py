"""Independent check of the coordinator's Reviewer-side "prize" table.

Replays four Limit rules against the real Field, holding our Charge at whatever we actually
submitted (Reviewer cost does not depend on our own Charge, only on our Limit and the
opponents' Charges/Fair Value):

    actual   -- our real submitted Limit
    accept   -- b = inf on every item (accept everything)
    reject   -- b = 0 on every item (reject everything)
    oracle   -- b = t (the fair value point) on every item, the best any Limit rule can do

    PYTHONPATH=. pixi run python scripts/experiments/prize_verify.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.replay_payoffs import (  # noqa: E402
    INF,
    our_actual_submission,
    replay,
    snapshot,
    usable_games,
)


def cost_under(snap, limit_fn) -> float:
    actual = our_actual_submission(snap)
    submission = {
        index: (actual[index][0], limit_fn(snap, index)) for index in snap.line_items
    }
    return replay(snap, submission).cost


def main() -> None:
    games = sorted(usable_games(range(1, 101)))
    windows = {
        "13-35 (coordinator's claim)": [g for g in games if 13 <= g <= 35],
        "all usable (1-35)": games,
        "19-32 (brief's window)": [g for g in games if 19 <= g <= 32],
    }

    rules = {
        "actual": lambda snap, i: snap.limit_point(i, snap.us),
        "accept everything (b=inf)": lambda snap, i: INF,
        "reject everything (b=0)": lambda snap, i: 0.0,
        "oracle (b=t)": lambda snap, i: snap.fair_point(i),
    }

    for label, game_ids in windows.items():
        print(f"\n=== {label}: n={len(game_ids)} games {game_ids} ===")
        snaps = [snapshot(g) for g in game_ids]
        totals = {}
        for rule_name, fn in rules.items():
            total = sum(cost_under(s, fn) for s in snaps)
            totals[rule_name] = total
        base = totals["actual"]
        for rule_name, total in totals.items():
            delta = total - base
            print(f"  {rule_name:<30}{total:>14,.2f}   vs actual {delta:>+14,.2f}")


if __name__ == "__main__":
    main()
