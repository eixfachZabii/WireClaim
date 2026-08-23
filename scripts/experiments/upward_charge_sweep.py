"""Sweep upward Charge multipliers on the signals that survive `upward_charge_signals.py`.

(upward-charge task, items 3-4)

Every downward conditional multiplier in `src/domain/pricing/engine.py`'s docstring lost
money. The signal-separation step found continuous decision-time signals (`t_hat`, `sigma`,
`coverage_probability`, `quantity` alone) all sit at AUC 0.44-0.56 -- essentially no
separation -- but two categorical splits show a real gap in the "provably underpriced"
share: channel (memory 72% vs model-only 57%, a signal `engine.py` already tried and
documented failing held-out at Games 1-27) and metered wording (84% vs 64%, a NEW signal --
only downward metered multipliers were ever swept before). Their intersection
(memory & metered, n=25) shows the largest gap of all (88%) but is the smallest bucket.

This file sweeps upward multipliers on exactly these three candidates, replayed by
`replay_payoffs.replay` against the real Field via `charge_buckets.total()`, reusing that
module's `Row`/`Rule`/`dataset()`/`ALL_GAMES` machinery so this measurement sits on the
identical sample and pricing surface as everything else in the engine's docstring.

Windows: all settled Games (1-38) and Games 19-37 (the task's requested window; 37 rather
than 38 so the window does not depend on whichever Game most recently settled).
Folds: odd/even (interleaved, same Field in both halves) and 1-20 -> 21-38 (disjoint,
time-ordered -- the harder test, because GAME-AND-PROOFS R9 says a Field measurement does not
survive a phase boundary).

Usage
-----
    PYTHONPATH=. python scripts/experiments/upward_charge_sweep.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from charge_buckets import ALL_GAMES, Rule, dataset, total  # noqa: E402

NOISE_FLOOR_18 = 26_622.0
WINDOW_1937 = tuple(g for g in ALL_GAMES if 19 <= g <= 37)
ODD = tuple(g for g in ALL_GAMES if g % 2)
EVEN = tuple(g for g in ALL_GAMES if not g % 2)
EARLY = tuple(g for g in ALL_GAMES if g <= 20)
LATE = tuple(g for g in ALL_GAMES if g > 20)


def noise_floor(n_games: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(n_games / 18)


@dataclass(frozen=True)
class Family:
    name: str
    selector: object  # Row -> bool
    multipliers: tuple[float, ...]


FAMILIES = [
    Family("memory (channel)", lambda r: r.has_memory, (1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.4)),
    Family("metered (labour/rate wording)", lambda r: r.metered, (1.0, 1.1, 1.2, 1.3, 1.4)),
    Family("memory & metered (intersection)", lambda r: r.has_memory and r.metered, (1.0, 1.1, 1.2, 1.3, 1.4, 1.5)),
]


def rules_for(family: Family) -> list[Rule]:
    out = []
    for m in family.multipliers:
        out.append(
            Rule(
                name=f"{family.name} x{m}",
                family=family.name,
                scale=lambda r, m=m, sel=family.selector: m if sel(r) else 1.0,
            )
        )
    return out


def main() -> None:
    rows = dataset()
    base_all = total(rows, Rule(), ALL_GAMES)
    base_1937 = total(rows, Rule(), WINDOW_1937)
    print(f"shipped baseline: all 38 Games = {base_all:,.0f}   Games 19-37 = {base_1937:,.0f}\n")

    for family in FAMILIES:
        print(f"=== {family.name} ===")
        print(f"{'rule':<38}{'all 38':>12}{'d':>10}{'19-37':>12}{'d':>10}")
        deltas_all, deltas_1937 = [], []
        for rule in rules_for(family):
            a = total(rows, rule, ALL_GAMES)
            r = total(rows, rule, WINDOW_1937)
            deltas_all.append(a - base_all)
            deltas_1937.append(r - base_1937)
            print(f"{rule.name:<38}{a:>12,.0f}{a - base_all:>10,.0f}{r:>12,.0f}{r - base_1937:>10,.0f}")
        mono_all = all(x <= y for x, y in zip(deltas_all, deltas_all[1:])) or all(
            x >= y for x, y in zip(deltas_all, deltas_all[1:])
        )
        mono_1937 = all(x <= y for x, y in zip(deltas_1937, deltas_1937[1:])) or all(
            x >= y for x, y in zip(deltas_1937, deltas_1937[1:])
        )
        print(f"  monotone in the multiplier: all 38 = {mono_all}   19-37 = {mono_1937}")
        print()

    floor_all = noise_floor(len(ALL_GAMES))
    floor_1937 = noise_floor(len(WINDOW_1937))
    print(f"noise floor: all 38 +/-{floor_all:,.0f}   Games 19-37 +/-{floor_1937:,.0f}\n")

    # -------------------------------------------------------------- held-out folds
    print("=== held-out folds (fit best multiplier on train, score on test) ===")
    splits = (
        (ODD, EVEN, "odd->even"),
        (EVEN, ODD, "even->odd"),
        (EARLY, LATE, "1-20->21-38"),
        (LATE, EARLY, "21-38->1-20"),
    )
    print(f"{'family':<34}" + "".join(f"{label:>16}" for _, _, label in splits))
    totals = {label: 0.0 for _, _, label in splits}
    for family in FAMILIES:
        candidates = rules_for(family)
        cells = []
        for train, test, label in splits:
            best = max(candidates, key=lambda rule: total(rows, rule, train))
            delta = total(rows, best, test) - total(rows, Rule(), test)
            totals[label] += delta
            cells.append(f"{delta:>+16,.0f}({best.name.split('x')[-1]})")
        print(f"{family.name:<34}" + "".join(cells))
    print("\nheld-out net against shipped constants, summed over all three families:")
    for _, _, label in splits:
        n_games = len(EVEN) if "->" in label and label in ("odd->even", "even->odd") else (
            len(LATE) if label == "1-20->21-38" else len(EARLY)
        )
        print(f"  {label:<16}{totals[label]:>+12,.0f}   (noise floor +/-{noise_floor(n_games):,.0f})")


if __name__ == "__main__":
    main()
