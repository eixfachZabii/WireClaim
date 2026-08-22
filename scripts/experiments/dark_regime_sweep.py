"""Regime-conditioned Charge-multiplier sweep (dark-regime-charge task, item 3).

Why this is a *different* sweep from everything `src/pricing.py` already cites
------------------------------------------------------------------------------
`scripts/experiments/tune_pricing.py` already measures the euro-optimal flat Charge
multiplier as a function of estimator error `sigma`, replayed against the *real* Field
(`calibrate()`). That is exactly the sweep CLAUDE.md says not to re-run.

What it never varied is the Field's *behaviour*. Every one of those replays uses the real,
observed Limits and Charges of Games 1-14 -- an awake Field. The dark-regime hypothesis is
that the optimum shifts once the Field's Limits collapse to zero, because the term that
currently pulls the Charge multiplier *up* (some opponents' loose Limit accepting an
Overcharge) is worth zero against a dark Reviewer. This file is `tune_pricing.calibrate`
with one more axis: which teams are dark, via `dark_regime_replay.regime_snapshot`.

Everything about the estimator (the synthetic `t_hat = t * exp(N(0, sigma))`, the coverage
signal, the 5-replica averaging, the smoothed-peak argmax) is reused unchanged from
`tune_pricing.py` so the two sweeps are comparable on the same footing. The only new code
is `net_regime` / `averaged_regime`, which apply the regime override to the snapshot before
replay and leave evidence generation (which reads only the *original* snapshot's fair-value
brackets, never Limits or Charges) untouched.

Usage
-----
    PYTHONPATH=. python scripts/experiments/dark_regime_sweep.py --games 19-32 --regime fully_dark
    PYTHONPATH=. python scripts/experiments/dark_regime_sweep.py --games 19-32 --all-regimes
    PYTHONPATH=. python scripts/experiments/dark_regime_sweep.py --games 19-32 --folds
    PYTHONPATH=. python scripts/experiments/dark_regime_sweep.py --games 19-32 --cross-cost
"""

from __future__ import annotations

import argparse
import statistics
import sys
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tune_pricing import (  # noqa: E402
    EvidenceSource,
    Params,
    _peak,
    flat,
    submission as price_submission,
    unbiased_replicas,
)
from dark_regime_replay import TOP5, dark_teams_for, regime_snapshot  # noqa: E402
from replay_payoffs import GameSnapshot, US, replay, reconstruction_report, snapshot  # noqa: E402
from pull_transactions import completed_games  # noqa: E402

REGIMES = ("control", "fully_dark", "top5_awake")
SIGMAS = (0.43, 0.60, 0.80)  # measured Price Memory sigma; the two pessimistic RMSLE points
NOISE_FLOOR_18 = 26_622.0


def noise_floor(n_games: int) -> float:
    return NOISE_FLOOR_18 * (n_games / 18.0) ** 0.5


# --------------------------------------------------------------------------- regime net


def net_regime(
    snaps: Sequence[GameSnapshot],
    source: EvidenceSource,
    params: Params,
    regime: str,
    *,
    zero_charges: bool = True,
) -> float:
    total = 0.0
    for snap in snaps:
        evidence = source(snap)  # reads only snap.fair_brackets / zero_fair_value -- unaffected
        rsnap = regime_snapshot(snap, regime, zero_charges=zero_charges)
        total += replay(rsnap, price_submission(evidence, params)).net
    return total


def averaged_regime(
    snaps: Sequence[GameSnapshot],
    sources: Sequence[EvidenceSource],
    params: Params,
    regime: str,
    *,
    zero_charges: bool = True,
) -> float:
    return statistics.fmean(
        net_regime(snaps, source, params, regime, zero_charges=zero_charges) for source in sources
    )


# ------------------------------------------------------------------------------- sweep


def calibrate_regime(
    snaps: Sequence[GameSnapshot],
    regime: str,
    sigmas: Sequence[float] = SIGMAS,
    coverage_confidence: float = 0.85,
    replicas: int = 5,
    grid: Sequence[float] | None = None,
    cap: bool = False,
    zero_charges: bool = True,
) -> list[tuple[float, float, float]]:
    """`(sigma, best flat Charge multiplier, net at that multiplier)` -- Limit fixed at
    `1.0 x median`, uncapped, exactly as `tune_pricing.calibrate`'s Charge pass does, so the
    two are comparable. Returns one row per sigma.
    """
    grid = grid or tuple(round(0.05 * k, 2) for k in range(2, 31))  # 0.10 .. 1.50
    out = []
    for sigma in sigmas:
        sources = unbiased_replicas(sigma, coverage_confidence, replicas)
        rows = [
            (k, averaged_regime(snaps, sources, flat(k, 1.0, cap=cap), regime, zero_charges=zero_charges))
            for k in grid
        ]
        best_k, best_net = _peak(rows)
        out.append((sigma, best_k, best_net))
    return out


def calibrate_regime_joint(
    snaps: Sequence[GameSnapshot],
    regime: str,
    sigmas: Sequence[float] = SIGMAS,
    coverage_confidence: float = 0.85,
    replicas: int = 5,
    grid: Sequence[float] | None = None,
    cap: bool = False,
    zero_charges: bool = True,
) -> list[tuple[float, float, float, float]]:
    """`(sigma, best Charge mult, best Limit mult, net)` -- the joint two-stage optimum,
    mirroring `tune_pricing.calibrate` exactly (Charge first at Limit=1.0 uncapped, then
    Limit at the chosen Charge), so item 5 (does the Limit want to move too) falls out of
    the same sweep as item 3 (does the Charge want to move) on equal footing.
    """
    grid = grid or tuple(round(0.05 * k, 2) for k in range(2, 31))
    out = []
    for sigma in sigmas:
        sources = unbiased_replicas(sigma, coverage_confidence, replicas)
        charge_rows = [
            (k, averaged_regime(snaps, sources, flat(k, 1.0, cap=cap), regime, zero_charges=zero_charges))
            for k in grid
        ]
        best_charge, _ = _peak(charge_rows)
        limit_rows = [
            (m, averaged_regime(snaps, sources, flat(best_charge, m, cap=cap), regime, zero_charges=zero_charges))
            for m in grid
        ]
        best_limit, _ = _peak(limit_rows)
        value = averaged_regime(
            snaps, sources, flat(best_charge, best_limit, cap=cap), regime, zero_charges=zero_charges
        )
        out.append((sigma, best_charge, best_limit, value))
    return out


def net_at_multiplier(
    snaps: Sequence[GameSnapshot],
    regime: str,
    charge_mult: float,
    sigma: float,
    *,
    limit_mult: float = 1.0,
    coverage_confidence: float = 0.85,
    replicas: int = 5,
    cap: bool = False,
    zero_charges: bool = True,
) -> float:
    sources = unbiased_replicas(sigma, coverage_confidence, replicas)
    return averaged_regime(
        snaps, sources, flat(charge_mult, limit_mult, cap=cap), regime, zero_charges=zero_charges
    )


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
    parser.add_argument("--regime", default="fully_dark", choices=REGIMES)
    parser.add_argument("--all-regimes", action="store_true")
    parser.add_argument("--limits-only", action="store_true", help="don't zero opponents' Charges")
    parser.add_argument("--replicas", type=int, default=5)
    parser.add_argument("--sigmas", default=None, help="comma-separated, default 0.43,0.60,0.80")
    parser.add_argument(
        "--cross-cost",
        action="store_true",
        help="two-sided cost of using the wrong regime's optimal multiplier",
    )
    parser.add_argument(
        "--joint", action="store_true", help="also optimise the Limit multiplier (item 5)"
    )
    args = parser.parse_args()

    game_ids = _parse_games(args.games)
    snaps = _load_snaps(game_ids)
    sigmas = tuple(float(s) for s in args.sigmas.split(",")) if args.sigmas else SIGMAS
    zero_charges = not args.limits_only
    print(
        f"Games: {[s.game_id for s in snaps]} ({len(snaps)})  "
        f"noise floor +/-{noise_floor(len(snaps)):,.0f}  zero_charges={zero_charges}"
    )

    regimes = REGIMES if args.all_regimes else (args.regime,)
    results: dict[tuple[str, float], tuple[float, float]] = {}
    for regime in regimes:
        if args.joint:
            rows4 = calibrate_regime_joint(
                snaps, regime, sigmas=sigmas, replicas=args.replicas, zero_charges=zero_charges
            )
            print(f"\n[{regime}] joint (Charge, then Limit)")
            for sigma, best_k, best_m, best_net in rows4:
                results[(regime, sigma)] = (best_k, best_net)
                print(
                    f"  sigma={sigma:.2f}  best a = {best_k:.2f} x median  best b = {best_m:.2f} x median  "
                    f"net {best_net:14,.0f}  ({best_net / len(snaps):9,.0f}/Game)"
                )
            continue
        rows = calibrate_regime(snaps, regime, sigmas=sigmas, replicas=args.replicas, zero_charges=zero_charges)
        print(f"\n[{regime}]")
        for sigma, best_k, best_net in rows:
            results[(regime, sigma)] = (best_k, best_net)
            print(
                f"  sigma={sigma:.2f}  best a = {best_k:.2f} x median  "
                f"net {best_net:14,.0f}  ({best_net / len(snaps):9,.0f}/Game)"
            )

    if args.cross_cost:
        pair = ("control", "fully_dark")
        if not all(r in regimes for r in pair):
            print("\n--cross-cost needs --all-regimes (or --regime with both control and fully_dark)")
            return
        print(f"\n=== two-sided cost of being wrong (control <-> fully_dark) ===")
        for sigma in sigmas:
            k_awake, net_awake_at_awake = results[("control", sigma)]
            k_dark, net_dark_at_dark = results[("fully_dark", sigma)]
            net_dark_at_awake_k = net_at_multiplier(
                snaps, "control", k_dark, sigma, replicas=args.replicas, zero_charges=zero_charges
            )
            net_awake_at_dark_k = net_at_multiplier(
                snaps, "fully_dark", k_awake, sigma, replicas=args.replicas, zero_charges=zero_charges
            )
            cost_shipping_dark_if_awake = net_awake_at_awake - net_dark_at_awake_k
            cost_shipping_awake_if_dark = net_dark_at_dark - net_awake_at_dark_k
            print(f"\n  sigma={sigma:.2f}  (awake-optimal a={k_awake:.2f}, dark-optimal a={k_dark:.2f})")
            print(
                f"    ship dark-tuned a={k_dark:.2f}, field stays awake: "
                f"{net_dark_at_awake_k:,.0f} vs awake-optimal {net_awake_at_awake:,.0f}  "
                f"-> costs {cost_shipping_dark_if_awake:,.0f} over {len(snaps)} Games "
                f"({cost_shipping_dark_if_awake / len(snaps):,.0f}/Game)"
            )
            print(
                f"    ship awake-tuned a={k_awake:.2f}, field goes dark:  "
                f"{net_awake_at_dark_k:,.0f} vs dark-optimal {net_dark_at_dark:,.0f}  "
                f"-> costs {cost_shipping_awake_if_dark:,.0f} over {len(snaps)} Games "
                f"({cost_shipping_awake_if_dark / len(snaps):,.0f}/Game)"
            )


if __name__ == "__main__":
    main()
