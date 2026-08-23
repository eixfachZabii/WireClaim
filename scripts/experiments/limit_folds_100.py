"""Is the Limit gap real, or did one Game buy it? Same sweep, cut eight ways.

`limit_sweep_100.py` says scaling our Limit by 1.25-1.5 is worth +113k to +134k weighted over
all 100 Games. A single total is exactly the kind of number this repository has been burned by
(CLAUDE.md: "One Game is far inside the 26,622 noise floor"), so the same counterfactual is run
on disjoint subsets that no tuning could have coordinated:

* **odd / even Game ids** -- interleaved, so any drift in the Field cancels;
* **the three regimes** (awake 1-43, dark 44-81, recalibrated 82-100) -- a knob that only
  works in one regime is a knob that read the Field, and CLAUDE.md rule 9 says that does not
  survive a phase boundary;
* **first half / last half** -- the honest walk-forward: would tuning on 1-50 have helped on
  51-100?
* **leave-one-Game-out worst case** -- drop the single Game that contributes most to the gain
  and check the gain survives.

A knob that wins every one of those is a knob about the payoff table. A knob that wins the
total and loses two folds is a knob about 2026-08-22.

Usage
-----
    PYTHONPATH=. python scripts/experiments/limit_folds_100.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from replay_payoffs import US, our_actual_submission, reconstruction_status, replay, snapshot  # noqa: E402

WEIGHTED = frozenset(range(81, 101))
GRID = [1.0, 1.1, 1.25, 1.4, 1.5, 1.75, 2.0]


def weight(game_id: int) -> float:
    return 3.0 if game_id in WEIGHTED else 1.0


def net_for(snap, lam: float) -> float:
    actual = our_actual_submission(snap)
    return replay(snap, {i: (a, b * lam) for i, (a, b) in actual.items()}).net


def main() -> None:
    snaps = []
    for game_id in range(1, 101):
        if reconstruction_status(game_id, US).usable:
            snaps.append(snapshot(game_id, US))
    print(f"{len(snaps)} reconstructable Games\n")

    # net[lambda][game_id] -- computed once, sliced many times.
    table = {lam: {snap.game_id: net_for(snap, lam) for snap in snaps} for lam in GRID}

    def total(lam: float, ids) -> float:
        return sum(table[lam][g] * weight(g) for g in ids if g in table[lam])

    folds = {
        "ALL 1-100": [s.game_id for s in snaps],
        "odd ids": [s.game_id for s in snaps if s.game_id % 2],
        "even ids": [s.game_id for s in snaps if not s.game_id % 2],
        "awake 1-43": [s.game_id for s in snaps if s.game_id <= 43],
        "dark 44-81": [s.game_id for s in snaps if 44 <= s.game_id <= 81],
        "recal 82-100": [s.game_id for s in snaps if s.game_id >= 82],
        "first half": [s.game_id for s in snaps if s.game_id <= 50],
        "last half": [s.game_id for s in snaps if s.game_id > 50],
    }

    head = "".join(f"{lam:>11g}" for lam in GRID)
    print(f"  {'fold':<14}{'n':>4}{head}   best")
    print(f"  {'-' * 14:<14}{'-' * 4:>4}{'-' * (11 * len(GRID))}")
    for name, ids in folds.items():
        base = total(1.0, ids)
        cells = "".join(f"{total(lam, ids) - base:>11,.0f}" for lam in GRID)
        best = max(GRID, key=lambda lam: total(lam, ids))
        print(f"  {name:<14}{len(ids):>4}{cells}   {best:g}")
    print("\n  (cells are the gain over lambda = 1, i.e. over what we really submitted)")

    # Leave-one-out: does one Game carry the headline?
    ids = folds["ALL 1-100"]
    gain = {g: (table[1.25][g] - table[1.0][g]) * weight(g) for g in ids}
    hero = max(gain, key=lambda g: gain[g])
    villain = min(gain, key=lambda g: gain[g])
    headline = total(1.25, ids) - total(1.0, ids)
    print(
        f"\n  lambda = 1.25 gain {headline:,.0f} weighted over {len(ids)} Games\n"
        f"    biggest single contributor  G{hero:<3d} {gain[hero]:>12,.0f}"
        f"   -> without it {headline - gain[hero]:,.0f}\n"
        f"    worst single contributor    G{villain:<3d} {gain[villain]:>12,.0f}\n"
        f"    Games improved {sum(1 for v in gain.values() if v > 0.01):>3d}"
        f"   unchanged {sum(1 for v in gain.values() if abs(v) <= 0.01):>3d}"
        f"   worsened {sum(1 for v in gain.values() if v < -0.01):>3d}"
    )


if __name__ == "__main__":
    main()
