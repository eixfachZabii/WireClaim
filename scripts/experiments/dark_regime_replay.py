"""Dark-field replay: what happens to our Charge multiplier when the Field goes dark.

Extends `scripts/replay_payoffs.py` (NOT modified -- imported) with a *regime* layer: a
GameSnapshot's `limit_brackets` (and, optionally, `charges`) for a chosen set of "dark"
teams are overridden before replay, holding the Case data (Line Items, fair-value brackets,
awake teams' real behaviour) fixed. Everything else -- `replay()`, `sweep_total()`, the
oracle estimator, the multiplier grid -- is reused unchanged from `replay_payoffs.py`, so
this file adds exactly one thing: the ability to ask "what if these teams were asleep".

Two darkness models, because "dark" is ambiguous and the difference matters:

    zero_charges=False  "Limits-only".  Dark teams' Limit -> 0 (they reject everything);
                          their Charge is left at whatever they actually charged in the real
                          Game. This is what the task literally asked for, and it is the
                          CONSERVATIVE model: a truly offline team would not be charging
                          either, so this leaves our reviewer-side cost too high and is a
                          floor on how good the dark regime really is for us.

    zero_charges=True   "Fully dark" (the default here). Dark teams' Limit AND Charge both
                          go to (0, 0) -- the tournament default for a team that submits
                          nothing (CLAUDE.md rule 1). This is the realistic model of a team
                          whose pipeline is not running at all, in either role.

Three regimes are named, matching the task:

    fully_dark   every opponent is dark
    top5_awake   only {eyay, error404 ai, TakeTheMoneyAndRun, OPUSMOPUS, Alpha} stay awake;
                 everyone else (10-15 teams depending on the Game) goes dark
    control      no override -- must reproduce the published net exactly (self-check)

Usage
-----
    PYTHONPATH=. python scripts/experiments/dark_regime_replay.py --games 19-32 --regime fully_dark
    PYTHONPATH=. python scripts/experiments/dark_regime_replay.py --games all --sweep-all
    PYTHONPATH=. python scripts/experiments/dark_regime_replay.py --games all --folds
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from replay_payoffs import (  # noqa: E402
    DEFAULT_ALPHAS,
    DEFAULT_BETAS,
    GameSnapshot,
    US,
    best_multipliers,
    multiplier_submission,
    oracle_estimates,
    our_actual_submission,
    replay,
    reconstruction_report,
    snapshot,
    sweep_total,
)
from pull_transactions import completed_games  # noqa: E402

TOP5 = frozenset({"eyay", "error404 ai", "TakeTheMoneyAndRun", "OPUSMOPUS", "Alpha"})


# --------------------------------------------------------------------------- regime layer


def dark_teams_for(snap: GameSnapshot, regime: str) -> set[str]:
    """Which of `snap.opponents` go dark under a named regime."""
    opponents = set(snap.opponents)
    if regime == "control":
        return set()
    if regime == "fully_dark":
        return set(opponents)
    if regime == "top5_awake":
        return opponents - TOP5
    if regime == "top5_dark":  # mirror check: the leaders go dark, everyone else awake
        return opponents & TOP5
    raise ValueError(f"unknown regime {regime!r}")


def apply_regime(
    snap: GameSnapshot, dark_teams: set[str], *, zero_charges: bool = True
) -> GameSnapshot:
    """Override `dark_teams`' Limit (always) and Charge (if `zero_charges`) to zero.

    Everything else about the snapshot -- the Case, the fair-value brackets, the awake
    teams' real Charges and Limits -- is untouched. `dark_teams` empty is a no-op and must
    replay to the published net (see `control_check`).
    """
    new_charges = {i: dict(d) for i, d in snap.charges.items()}
    new_limits = {i: dict(d) for i, d in snap.limit_brackets.items()}
    for index in snap.line_items:
        for team in dark_teams:
            if team in new_limits[index]:
                new_limits[index][team] = (0.0, 0.0)
            if zero_charges and team in new_charges[index]:
                new_charges[index][team] = 0.0
    return dataclasses.replace(snap, charges=new_charges, limit_brackets=new_limits)


def regime_snapshot(snap: GameSnapshot, regime: str, *, zero_charges: bool = True) -> GameSnapshot:
    return apply_regime(snap, dark_teams_for(snap, regime), zero_charges=zero_charges)


def control_check(snaps: Iterable[GameSnapshot]) -> list[str]:
    """The `control` regime (no override) must replay our real submission to the published
    net exactly, for every Game. Returns the failures; empty means the harness is trusted.
    """
    failures = []
    for snap in snaps:
        ctrl = regime_snapshot(snap, "control")
        got = replay(ctrl, our_actual_submission(snap)).net
        if abs(got - snap.published_net) > 0.01:
            failures.append(f"G{snap.game_id}: control replay {got:.2f} != published {snap.published_net:.2f}")
    return failures


# ------------------------------------------------------------------------------- sweeping


def regime_sweep(
    snaps: list[GameSnapshot],
    regime: str,
    *,
    zero_charges: bool = True,
    alphas: Iterable[float] = DEFAULT_ALPHAS,
    betas: Iterable[float] = DEFAULT_BETAS,
) -> dict[tuple[float, float], float]:
    regime_snaps = [regime_snapshot(s, regime, zero_charges=zero_charges) for s in snaps]
    return sweep_total(regime_snaps, oracle_estimates, alphas=alphas, betas=betas)


def net_at(
    snaps: list[GameSnapshot],
    regime: str,
    alpha: float,
    beta: float,
    *,
    zero_charges: bool = True,
) -> float:
    """Total net over `snaps` under `regime`, submitting the oracle-estimator multiplier
    (alpha, beta) fixed -- used to price "what does X's optimum cost when regime is Y".
    """
    total = 0.0
    for snap in snaps:
        rs = regime_snapshot(snap, regime, zero_charges=zero_charges)
        submission = multiplier_submission(oracle_estimates(rs), alpha, beta)
        total += replay(rs, submission).net
    return total


def best_beta_fixed_alpha(
    grid: dict[tuple[float, float], float], alpha: float
) -> tuple[float, float]:
    """Best (beta, net) at a fixed alpha -- isolates the Charge knob from the Limit knob."""
    row = {beta: net for (a, beta), net in grid.items() if a == alpha}
    beta, net = max(row.items(), key=lambda kv: kv[1])
    return beta, net


# ---------------------------------------------------------------------------------- CLI


def _parse_games(spec: str) -> list[int]:
    if spec == "all":
        return completed_games()
    start, _, end = spec.partition("-")
    return list(range(int(start), int(end or start) + 1))


def _load_snaps(game_ids: list[int], team: str = US) -> list[GameSnapshot]:
    report = reconstruction_report(game_ids, team)
    bad = [r.game_id for r in report if not r.usable]
    if bad:
        print(f"WARNING: dropping unreconstructable Games {bad}")
    return [snapshot(g, team) for g in game_ids if g not in bad]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="19-32")
    parser.add_argument("--team", default=US)
    parser.add_argument(
        "--regime", default="fully_dark", choices=("control", "fully_dark", "top5_awake", "top5_dark")
    )
    parser.add_argument("--zero-charges", dest="zero_charges", action="store_true", default=True)
    parser.add_argument("--limits-only", dest="zero_charges", action="store_false")
    parser.add_argument("--sweep-all", action="store_true", help="sweep all four regimes")
    parser.add_argument("--control-check", action="store_true")
    args = parser.parse_args()

    game_ids = _parse_games(args.games)
    snaps = _load_snaps(game_ids, args.team)
    print(f"Games: {[s.game_id for s in snaps]} ({len(snaps)}) team={args.team}")

    if args.control_check or args.sweep_all:
        failures = control_check(snaps)
        print(f"\ncontrol check: {'OK, all reproduce published nets' if not failures else failures}")

    regimes = ("control", "fully_dark", "top5_awake") if args.sweep_all else (args.regime,)
    for regime in regimes:
        grid = regime_sweep(snaps, regime, zero_charges=args.zero_charges)
        alpha, beta, net = best_multipliers(grid)
        print(
            f"\n[{regime}] (zero_charges={args.zero_charges}) best alpha={alpha} beta={beta} "
            f"net={net:,.2f} over {len(snaps)} Games ({net / len(snaps):,.2f}/Game)"
        )
        # also report best beta holding alpha fixed near the current shipped Limit posture
        for fixed_alpha in (0.3, 0.45):
            if fixed_alpha in {round(0.2 + 0.1 * k, 2) for k in range(29)}:
                beta_f, net_f = best_beta_fixed_alpha(grid, fixed_alpha)
                print(
                    f"    at alpha={fixed_alpha}: best beta={beta_f} net={net_f:,.2f} "
                    f"({net_f / len(snaps):,.2f}/Game)"
                )


if __name__ == "__main__":
    main()
