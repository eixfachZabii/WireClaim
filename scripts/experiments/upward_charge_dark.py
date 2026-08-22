"""Does the upward-multiplier recommendation change in the Dark Window? (task item 6)

Games ~44-81 have not settled yet (the cached record stops at Game 38, `completed_games()`
verified live at measurement time), so there is no *observed* dark Game to replay. What
exists is `scripts/experiments/dark_regime_replay.py`'s regime layer, already built and
tested for exactly this question: it overrides a chosen set of opponents' Limit (and,
optionally, Charge) to zero before replay, holding the Case data and the awake teams' real
behaviour fixed. `fully_dark` (every opponent's Limit -> 0, Charge -> 0) is the regime that
matches CLAUDE.md rule 9's description of the overnight window: "a dark Reviewer rejects
everything... an accepted Overcharge earns nothing."

This applies the strongest candidate from `upward_charge_sweep.py` (memory-channel x1.15 --
the one candidate with a real in-sample peak, even though it failed the monotonicity bar)
under `control` (= the real, awake Games 1-38) and `fully_dark`, using the same
`charge_buckets.Rule`-priced submission in both, and reports the delta against the shipped
rule in each regime.

The theoretical prediction (payoff table, `replay_payoffs.py` docstring): our income when
`a <= t` is `a` whether the reviewer accepts or wrongfully rejects -- darkness does not
touch it. Only `a > t` depends on acceptance, and a dark reviewer never accepts. So the
"stayed below t" gains from `upward_charge_cliff.py` should be UNCHANGED by darkness and
the "crossed above t" losses should get WORSE (100% forfeiture instead of the ~80% forfeited
against an awake, ~17%-generous Field).

Usage
-----
    PYTHONPATH=. python scripts/experiments/upward_charge_dark.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from charge_buckets import ALL_GAMES, Rule, dataset  # noqa: E402
from dark_regime_replay import regime_snapshot  # noqa: E402
from replay_payoffs import replay, snapshot  # noqa: E402

CANDIDATE = Rule(name="memory x1.15", scale=lambda r: 1.15 if r.has_memory else 1.0)


def net_under_regime(rows_by_game: dict, rule: Rule, regime: str) -> dict[int, float]:
    out = {}
    for game_id in ALL_GAMES:
        snap = regime_snapshot(snapshot(game_id), regime)
        submission = {row.index: rule.price(row) for row in rows_by_game.get(game_id, [])}
        actual = {
            index: (snap.charges[index][snap.us], snap.limit_point(index, snap.us))
            for index in snap.line_items
        }
        actual.update(submission)
        out[game_id] = replay(snap, actual).net
    return out


def main() -> None:
    rows = dataset()
    rows_by_game: dict[int, list] = {}
    for row in rows:
        rows_by_game.setdefault(row.game, []).append(row)

    for regime in ("control", "fully_dark"):
        base = net_under_regime(rows_by_game, Rule(), regime)
        cand = net_under_regime(rows_by_game, CANDIDATE, regime)
        base_total = sum(base.values())
        cand_total = sum(cand.values())
        delta = cand_total - base_total
        label = "awake (control, = the real Games 1-38)" if regime == "control" else "fully dark (every opponent Limit+Charge -> 0)"
        print(f"regime: {label}")
        print(f"  shipped net:  {base_total:>14,.0f}")
        print(f"  {CANDIDATE.name:<12}net:  {cand_total:>14,.0f}")
        print(f"  delta:        {delta:>+14,.0f}\n")


if __name__ == "__main__":
    main()
