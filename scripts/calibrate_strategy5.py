from __future__ import annotations

import argparse
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.observability.decisions import load, proposals
from src.services.strategies.strategy5.config import (
    CONFIG_PATH,
    Strategy5Config,
    load_config,
    save_factors,
)

Submission = Mapping[int, tuple[float, float]]


@dataclass(frozen=True)
class ProposalRun:
    game_id: int
    submission: dict[int, tuple[float, float]]


@dataclass(frozen=True)
class FactorCandidate:
    name: str
    axis: str
    ratio: float
    deltas: tuple[tuple[int, float], ...]

    @property
    def total_delta(self) -> float:
        return sum(delta for _, delta in self.deltas)

    @property
    def odd_delta(self) -> float:
        return sum(delta for game_id, delta in self.deltas if game_id % 2)

    @property
    def even_delta(self) -> float:
        return sum(delta for game_id, delta in self.deltas if not game_id % 2)


@dataclass(frozen=True)
class CalibrationReport:
    game_ids: tuple[int, ...]
    baseline_net: float
    candidates: tuple[FactorCandidate, ...]
    noise_floor: float
    recommendation: FactorCandidate | None


def current_regime_games(
    game_ids: Sequence[int],
    latest_game_id: int,
) -> tuple[int, ...]:
    def regime(game_id: int) -> int:
        if game_id <= 43:
            return 1
        if game_id <= 81:
            return 2
        return 3

    current = regime(latest_game_id)
    return tuple(game_id for game_id in game_ids if game_id > 0 and regime(game_id) == current)


def scale_submission(
    submission: Submission,
    charge_ratio: float = 1.0,
    limit_ratio: float = 1.0,
) -> dict[int, tuple[float, float]]:
    scaled: dict[int, tuple[float, float]] = {}
    for index, (charge, limit) in submission.items():
        adjusted_charge = round(max(float(charge) * charge_ratio, 0.0), 2)
        adjusted_limit = (
            0.0
            if float(limit) == 0.0
            else round(max(float(limit) * limit_ratio, 0.0), 2)
        )
        scaled[int(index)] = (adjusted_charge, min(adjusted_limit, adjusted_charge))
    return scaled


def _factor_specs(config: Strategy5Config) -> tuple[tuple[str, str, float], ...]:
    specs: list[tuple[str, str, float]] = []
    for axis, current in (("alpha", config.alpha_factor), ("beta", config.beta_factor)):
        for direction, multiplier in (
            ("down", 1.0 - config.factor_step),
            ("up", 1.0 + config.factor_step),
        ):
            target = min(max(current * multiplier, config.factor_min), config.factor_max)
            ratio = target / current
            if not math.isclose(ratio, 1.0):
                specs.append((f"{axis}_{direction}", axis, ratio))
    return tuple(specs)


def recommend_candidate(
    candidates: Sequence[FactorCandidate],
    config: Strategy5Config,
    game_count: int,
) -> FactorCandidate | None:
    if game_count < config.minimum_calibration_games:
        return None
    noise_floor = config.noise_floor_18_games * math.sqrt(game_count / 18.0)
    eligible = [
        candidate
        for candidate in candidates
        if candidate.total_delta > noise_floor
        and candidate.odd_delta > 0.0
        and candidate.even_delta > 0.0
    ]
    return max(eligible, key=lambda candidate: candidate.total_delta, default=None)


def evaluate_runs(
    runs: Sequence[ProposalRun],
    config: Strategy5Config,
    snapshot_fn: Callable[[int], Any],
    replay_fn: Callable[[Any, Submission], Any],
) -> CalibrationReport:
    specs = _factor_specs(config)
    deltas: dict[str, list[tuple[int, float]]] = {name: [] for name, _, _ in specs}
    usable_games: list[int] = []
    baseline_net = 0.0
    for run in sorted(runs, key=lambda value: value.game_id):
        try:
            snap = snapshot_fn(run.game_id)
            if set(run.submission) != set(snap.line_items):
                continue
            baseline = float(replay_fn(snap, run.submission).net)
            candidate_nets = {
                name: float(
                    replay_fn(
                        snap,
                        scale_submission(
                            run.submission,
                            charge_ratio=ratio if axis == "alpha" else 1.0,
                            limit_ratio=ratio if axis == "beta" else 1.0,
                        ),
                    ).net
                )
                for name, axis, ratio in specs
            }
        except Exception:
            continue
        usable_games.append(run.game_id)
        baseline_net += baseline
        for name, candidate_net in candidate_nets.items():
            deltas[name].append((run.game_id, candidate_net - baseline))
    candidates = tuple(
        FactorCandidate(name, axis, ratio, tuple(deltas[name]))
        for name, axis, ratio in specs
    )
    count = len(usable_games)
    noise_floor = config.noise_floor_18_games * math.sqrt(count / 18.0)
    return CalibrationReport(
        game_ids=tuple(usable_games),
        baseline_net=baseline_net,
        candidates=candidates,
        noise_floor=noise_floor,
        recommendation=recommend_candidate(candidates, config, count),
    )


def recorded_runs(game_ids: Sequence[int]) -> tuple[ProposalRun, ...]:
    runs: list[ProposalRun] = []
    for game_id in game_ids:
        submission = proposals(load(game_id)).get("strategy5")
        if submission:
            runs.append(ProposalRun(game_id, submission))
    return tuple(runs)


def apply_recommendation(
    recommendation: FactorCandidate,
    path: Path = CONFIG_PATH,
) -> Strategy5Config:
    config = load_config(path)
    if recommendation.axis == "alpha":
        return save_factors(
            config.alpha_factor * recommendation.ratio,
            config.beta_factor,
            path,
        )
    if recommendation.axis == "beta":
        return save_factors(
            config.alpha_factor,
            config.beta_factor * recommendation.ratio,
            path,
        )
    raise ValueError(f"Unknown Strategy 5 factor axis: {recommendation.axis}")


def main() -> None:
    from scripts.pull_transactions import completed_games
    from scripts.replay_payoffs import replay, snapshot

    parser = argparse.ArgumentParser()
    parser.add_argument("--team", default="Bin busy")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    completed = completed_games()
    if not completed:
        print("No completed Games are published.")
        return
    latest_game_id = completed[-1]
    print(f"Latest completed Game: {latest_game_id}")
    config = load_config()
    runs = recorded_runs(current_regime_games(completed, latest_game_id))
    report = evaluate_runs(
        runs,
        config,
        snapshot_fn=lambda game_id: snapshot(game_id, args.team),
        replay_fn=replay,
    )
    print(
        f"Strategy 5 replay: {len(report.game_ids)} Games, "
        f"baseline {report.baseline_net:.2f}, noise floor {report.noise_floor:.2f}"
    )
    for candidate in report.candidates:
        print(
            f"  {candidate.name:10s} x{candidate.ratio:.3f}: "
            f"delta {candidate.total_delta:+.2f} "
            f"(odd {candidate.odd_delta:+.2f}, even {candidate.even_delta:+.2f})"
        )
    if report.recommendation is None:
        print("No factor change clears the sample, noise, and held-out gates.")
        return
    recommendation = report.recommendation
    print(
        f"Recommendation: {recommendation.name} x{recommendation.ratio:.3f} "
        f"({recommendation.total_delta:+.2f})"
    )
    if args.apply:
        updated = apply_recommendation(recommendation)
        print(
            f"Saved ALPHA_FAC={updated.alpha_factor:.3f}, "
            f"BETA_FAC={updated.beta_factor:.3f}"
        )
    else:
        print("Dry run only; pass --apply to change one factor in config.json.")


if __name__ == "__main__":
    main()
