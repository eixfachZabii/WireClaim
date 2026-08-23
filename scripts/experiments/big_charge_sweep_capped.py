"""`big_charge_sweep.py` re-scored with the payment Cap enforced.

    PYTHONPATH=. pixi run python scripts/experiments/big_charge_sweep_capped.py

Why this exists, and why it is a separate file
-----------------------------------------------
`scripts/replay_payoffs.py` treats the Cap as **infinite**, and says so in its docstring:

    The Cap `c >= 4t` is treated as infinite here. ... `cap_conflicts()` checks, for every
    (Line Item, issuer) in Games 1-14, whether two rows with money moving ever report two
    different amounts ... There are zero such conflicts in the observed data, so the Cap
    never bound and `min(a, c) = a` throughout.

**That conclusion expired.** `scripts/rivals.py` establishes `c = max(4t, 2000)` with named
evidence (G22 #1, G28 #7, G29 #2: nine, six and thirteen different issuers each paid exactly
2,000.00; our own Charges of 2,933.51 and 4,649.21 both truncated to 2,000.00; ties to the
cent at non-round values -- 3,848.48 and 12,000.00 -- pinning the `4t` slope). And Game 62
shows it binding again: on Line Item 7, `t in [800, 1506)`, we Charged 8,617.22 and the one
acceptor paid exactly **4,840.00 = 4t**, so `t = 1,210`.

The bias this puts in a Charge sweep is directional, not random. An infinite Cap credits an
Overcharge with `a` per acceptor when the reviewer really pays `min(a, max(4t, 2000))`, so
**every rule that raises the Charge is flattered, and the amount it is flattered by grows
with how far above `t` the Charge sits.** `BIG_ITEM_CHARGE_SCALE` and the `floor` family both
raise the Charge on exactly the bucket where our estimate is furthest out. So the shipped
1.25 -- and `floor 0.3`, which the uncapped sweep reports as the only rule positive on all
four folds -- were both selected on a harness that pays them more than the Field would.

It is a separate file rather than a flag on `big_charge_sweep.py` because the two numbers are
worth reading side by side: the *difference* between them is the size of the bias, and that
difference is itself the result.

What is reused, and what is new
-------------------------------
Everything except the payoff: `dataset()`/`snapshot()` from `scripts.charge_buckets`, the
`price()` families verbatim from `big_charge_sweep` (imported, not copied, so the two sweeps
cannot drift), and `cap_of` from `scripts.rivals`. The only new code is `replay_capped`,
which is the same model already written three times in this repo (`rivals.replay_capped`,
`rivals_study.replay_capped`, `current_winners_study.replay_capped`) -- imported here from
`rivals_study` rather than reproduced a fourth time.

Reading the output
------------------
Two tables. The first is the uncapped sweep's own numbers, so this file stands alone. The
second is the same trials scored with the Cap. A rule whose sign or fold count changes
between them was an artefact of the harness. `folds+` counts the folds with a positive delta
against the shipped `scale 1.25`; the four-fold bar is the project's, and it is not relaxed
here -- but note that a fold's own noise floor is `26,622 * sqrt(n/18)`, so a fold delta of a
few thousand euros over thirty Games is indistinguishable from zero and should be read as
"flat", not as "negative".
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from charge_buckets import dataset, snapshot  # noqa: E402
from replay_payoffs import replay  # noqa: E402
from rivals_study import replay_capped  # noqa: E402

from big_charge_sweep import noise, price  # noqa: E402

TRIALS = (
    [("scale", k) for k in (0.8, 0.9, 1.0, 1.1, 1.25, 1.4)]
    + [("band", w) for w in (0.5, 0.6, 0.7)]
    + [("floor", f) for f in (0.3, 0.4, 0.5)]
)


def net(rows, games, *, family: str, param: float, capped: bool) -> float:
    total = 0.0
    for game_id in games:
        sub = {r.index: price(r, family=family, param=param) for r in rows if r.game == game_id}
        if not sub:
            continue
        snap = snapshot(game_id)
        total += replay_capped(snap, sub) if capped else replay(snap, sub).net
    return total


def crossings(rows, *, family: str, param: float) -> tuple[int, int, int]:
    """How many Line Items move across `t` relative to the shipped 1.25, and how many of
    those rest on an unbounded bracket -- where the `a <= t` test is weakest, because `t_hi`
    empty means the item is worth *at least* `t_lo` and possibly far more."""
    to_over = to_fair = unbounded = 0
    for row in rows:
        base, _ = price(row, family="scale", param=1.25)
        trial, _ = price(row, family=family, param=param)
        if base == trial:
            continue
        t = row.t_lo if row.t_hi == float("inf") else (row.t_lo + row.t_hi) / 2.0
        was_fair, is_fair = base <= t, trial <= t
        if was_fair and not is_fair:
            to_over += 1
        elif is_fair and not was_fair:
            to_fair += 1
        else:
            continue
        if row.t_hi == float("inf"):
            unbounded += 1
    return to_over, to_fair, unbounded


def table(rows, folds, *, capped: bool) -> None:
    base = {n: net(rows, gs, family="scale", param=1.25, capped=capped) for n, gs in folds.items()}
    print(f"{'rule':<16}" + "".join(f"{k:>11}" for k in folds) + "   folds+   crossings")
    print("-" * (16 + 11 * len(folds) + 22))
    for family, param in TRIALS:
        cells = [
            net(rows, gs, family=family, param=param, capped=capped) - base[n]
            for n, gs in folds.items()
        ]
        pos = sum(1 for c in cells[1:] if c > 0)
        to_over, to_fair, unbounded = crossings(rows, family=family, param=param)
        mark = "  <-- all 4" if pos == 4 else ""
        print(
            f"{family + ' ' + str(param):<16}"
            + "".join(f"{c:>+11,.0f}" for c in cells)
            + f"{pos:>6}/4  {to_fair:>3}->fair {to_over:>3}->over ({unbounded} unbdd){mark}"
        )
    print(f"\n{'(baseline net)':<16}" + "".join(f"{base[k]:>11,.0f}" for k in folds))


def main() -> None:
    rows = dataset()
    games = sorted({r.game for r in rows})
    folds = {
        "all": games,
        "odd": [g for g in games if g % 2],
        "even": [g for g in games if not g % 2],
        "<=40": [g for g in games if g <= 40],
        ">40": [g for g in games if g > 40],
    }
    print(
        f"{len(games)} Games ({games[0]}-{games[-1]}), noise floor +/-{noise(len(games)):,.0f} "
        f"over the window and +/-{noise(len(folds['odd'])):,.0f} within a half-fold.\n"
        f"Delta against the shipped scale of 1.25. `crossings` counts Line Items whose "
        f"Charge moves across `t`.\n"
    )
    print("=== Cap treated as INFINITE (what every shipped Charge constant was fitted on) ===\n")
    table(rows, folds, capped=False)
    print("\n\n=== Cap ENFORCED, c = max(4t, 2000) floored by what was observed paid ===\n")
    table(rows, folds, capped=True)


if __name__ == "__main__":
    main()
