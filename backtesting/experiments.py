"""End-to-end historical Field experiment orchestration."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import statistics
import subprocess
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from backtesting.config import CandidateSpec, ExperimentSpec, load_spec
from backtesting.data import load_dataset, parse_games
from backtesting.diagnostics import dataset_diagnostics, score_diagnostics
from backtesting.history import HistoryStore
from backtesting.models import (
    Ambiguity,
    GameScore,
    HistoricalDataset,
    HistoricalGame,
    ItemScore,
    Submission,
    ValueTriple,
    jsonable,
)
from backtesting.paths import CASES, RUN_SCHEMA_VERSION, RUNS
from backtesting.reporting import print_summary, write_report
from backtesting.scoring import reconstructed_submission, score_game
from backtesting.strategies import (
    StrategyContext,
    load_candidate,
    load_json_submissions,
    oracle_submission,
    run_candidate,
    standard_submission,
)
from backtesting.sweeps import chronological_evaluation, expand_grid, parameter_key
from backtesting.tracks import TrackDraw, merged_submission, run_track_draws
from src.data.case_loader import read_case


async def run_experiment(
    spec_path: str | Path,
    *,
    dataset_id: str | None = None,
    games_override: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    spec = load_spec(spec_path)
    if games_override is not None:
        spec = replace(spec, games=games_override)
    dataset = load_dataset(dataset_id)
    game_ids = parse_games(spec.games, sorted(dataset.games), spec.include_game_0)
    if not game_ids:
        raise ValueError(f"no Games matched {spec.games!r} in dataset {dataset.dataset_id[:16]}")
    if spec.seat not in dataset.teams:
        raise ValueError(f"seat {spec.seat!r} is not in dataset teams")
    _preflight_cases(game_ids)
    run_dir, manifest = _create_run(spec_path, spec, dataset, game_ids)
    history = HistoryStore(dataset)
    scores: dict[str, dict[int, GameScore]] = {}
    per_item_rows: list[dict[str, Any]] = []
    track_draw_scores: dict[str, dict[int, list[GameScore]]] = {
        track: {} for track in spec.tracks
    }
    merged_draw_scores: dict[int, list[GameScore]] = {}
    track_records: list[TrackDraw] = []
    candidate_defs = {candidate.name: candidate for candidate in spec.candidates}
    json_inputs = {
        candidate.name: load_json_submissions(candidate.submissions, candidate.name)
        for candidate in spec.candidates
        if candidate.submissions
    }
    callables = {
        candidate.name: load_candidate(candidate.entrypoint)
        for candidate in spec.candidates
        if candidate.entrypoint
    }
    sweep_params = {
        sweep.candidate: expand_grid(candidate_defs[sweep.candidate].params, sweep.grid)
        for sweep in spec.sweeps
    }
    candidate_scores: dict[str, dict[str, dict[int, GameScore]]] = {
        candidate.name: {} for candidate in spec.candidates
    }

    print(
        f"Fresh track execution: {len(game_ids)} Games x {len(spec.tracks)} tracks x "
        f"{spec.draws} draw rounds = {len(game_ids) * len(spec.tracks) * spec.draws} track invocations"
    )
    for game_id in game_ids:
        game = dataset.games[game_id]
        case = await read_case(game_id, CASES / f"case_{game_id:02d}")
        expected = set(game.items)
        _put(scores, "actual", game_id, _actual_score(game, spec.seat))
        _put(
            scores,
            "actual_reconstructed",
            game_id,
            score_game(
                game,
                reconstructed_submission(game, spec.seat),
                seat=spec.seat,
                cap_mode=spec.cap_mode,
            ),
        )
        _put(
            scores,
            "standard",
            game_id,
            score_game(game, standard_submission(case), seat=spec.seat, cap_mode=spec.cap_mode),
        )
        _put(
            scores,
            "oracle_bracket",
            game_id,
            score_game(game, oracle_submission(game), seat=spec.seat, cap_mode=spec.cap_mode),
        )
        _put(
            scores,
            "oracle_point",
            game_id,
            score_game(game, oracle_submission(game, point=True), seat=spec.seat, cap_mode=spec.cap_mode),
        )

        draws = await run_track_draws(
            case,
            history,
            run_dir,
            draws=spec.draws,
            timeout_seconds=spec.timeout_seconds,
            tracks=spec.tracks,
        )
        for draw_index, per_track in draws.items():
            track_records.extend(per_track.values())
            for track, result in per_track.items():
                track_draw_scores[track].setdefault(game_id, []).append(
                    score_game(game, result.submissions, seat=spec.seat, cap_mode=spec.cap_mode)
                )
            merged_draw_scores.setdefault(game_id, []).append(
                score_game(
                    game,
                    merged_submission(case, per_track),
                    seat=spec.seat,
                    cap_mode=spec.cap_mode,
                )
            )
        for track in spec.tracks:
            _put(scores, track, game_id, _average_scores(track_draw_scores[track][game_id]))
        _put(scores, "merged", game_id, _average_scores(merged_draw_scores[game_id]))

        context = StrategyContext(case, history.before(game_id), spec.seed + game_id)
        for candidate in spec.candidates:
            params_list = sweep_params.get(candidate.name, [dict(candidate.params)])
            if dict(candidate.params) not in params_list:
                params_list = [dict(candidate.params), *params_list]
            for params in params_list:
                key = parameter_key(params)
                if candidate.entrypoint:
                    submission = await run_candidate(
                        callables[candidate.name],
                        context,
                        params,
                        expected,
                        allow_missing=candidate.allow_missing,
                    )
                else:
                    submission = json_inputs[candidate.name].get(game_id, {})
                    if not candidate.allow_missing and set(submission) != expected:
                        raise ValueError(
                            f"JSON candidate {candidate.name} Game {game_id} indices "
                            f"{sorted(submission)} != {sorted(expected)}"
                        )
                candidate_scores[candidate.name].setdefault(key, {})[game_id] = score_game(
                    game, submission, seat=spec.seat, cap_mode=spec.cap_mode
                )
            base_key = parameter_key(candidate.params)
            _put(scores, candidate.name, game_id, candidate_scores[candidate.name][base_key][game_id])

    sweeps = {}
    for sweep in spec.sweeps:
        cells = candidate_scores[sweep.candidate]
        validation = chronological_evaluation(
            cells,
            game_ids,
            holdout_fraction=spec.holdout_fraction,
            min_train=spec.walk_forward_min_train,
            step=spec.walk_forward_step,
            objective=sweep.objective,
        )
        sweeps[sweep.candidate] = {
            "objective": sweep.objective,
            "cells": {key: _pooled(per_game) for key, per_game in cells.items()},
            "validation": validation,
        }

    for strategy, per_game in scores.items():
        for game_id, score in per_game.items():
            for index, item in score.per_item.items():
                per_item_rows.append(
                    {
                        "strategy": strategy,
                        "game_id": game_id,
                        "line_item_index": index,
                        "income_lower": item.income.lower,
                        "income_midpoint": item.income.midpoint,
                        "income_upper": item.income.upper,
                        "cost_lower": item.cost.lower,
                        "cost_midpoint": item.cost.midpoint,
                        "cost_upper": item.cost.upper,
                        "net_lower": item.net.lower,
                        "net_midpoint": item.net.midpoint,
                        "net_upper": item.net.upper,
                    }
                )

    result = {
        "schema_version": RUN_SCHEMA_VERSION,
        "manifest": manifest,
        "scores": {
            strategy: {str(game_id): _score_dict(score) for game_id, score in per_game.items()}
            for strategy, per_game in scores.items()
        },
        "per_item": per_item_rows,
        "tracks": _track_statistics(track_records, track_draw_scores),
        "sweeps": sweeps,
        "regimes": _regime_scores(scores, spec.regimes),
        "diagnostics": {
            "dataset": dataset_diagnostics(dataset),
            "scores": score_diagnostics(scores),
        },
    }
    write_report(run_dir, result)
    print_summary(result)
    return run_dir, result


def rerender(run_dir: str | Path) -> dict[str, Any]:
    directory = Path(run_dir)
    result = json.loads((directory / "scores.json").read_text())
    write_report(directory, result)
    print_summary(result)
    return result


def _preflight_cases(game_ids: Sequence[int]) -> None:
    missing = [
        game_id
        for game_id in game_ids
        if not (CASES / f"case_{game_id:02d}" / "policy.txt").exists()
    ]
    if missing:
        raise FileNotFoundError(f"Cases are not extracted for Games {missing}; run `pixi run cases`")


def _create_run(
    spec_path: str | Path,
    spec: ExperimentSpec,
    dataset: HistoricalDataset,
    game_ids: Sequence[int],
) -> tuple[Path, dict[str, Any]]:
    raw = Path(spec_path).read_bytes()
    spec_hash = hashlib.sha256(raw).hexdigest()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}-{spec_hash[:8]}"
    run_dir = RUNS / run_id
    suffix = 1
    while run_dir.exists():
        run_dir = RUNS / f"{run_id}-{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True)
    (run_dir / "spec.json").write_bytes(raw)
    (run_dir / "dataset_manifest.json").write_text(json.dumps(jsonable(dataset.manifest), indent=2))
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        revision = None
    manifest = {
        "run_id": run_dir.name,
        "name": spec.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset.dataset_id,
        "dataset_schema": dataset.schema_version,
        "spec_hash": spec_hash,
        "git_revision": revision,
        "games": list(game_ids),
        "seat": spec.seat,
        "draws": spec.draws,
        "tracks": list(spec.tracks),
        "cap_mode": spec.cap_mode,
        "noise_floor": 26_622.0 * math.sqrt(len(game_ids) / 18.0),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return run_dir, manifest


def _actual_score(game: HistoricalGame, seat: str) -> GameScore:
    per_item = {}
    for index in game.items:
        income = sum(
            row.amount for row in game.transactions if row.line_item_index == index and row.issuer == seat
        )
        cost = sum(
            row.amount if row.accepted else 1.5 * row.amount
            for row in game.transactions
            if row.line_item_index == index and row.reviewer == seat
        )
        per_item[index] = ItemScore(
            index=index,
            income=ValueTriple(income, income, income),
            cost=ValueTriple(cost, cost, cost),
            net=ValueTriple(income - cost, income - cost, income - cost),
        )
    income = sum(item.income.midpoint for item in per_item.values())
    cost = sum(item.cost.midpoint for item in per_item.values())
    return GameScore(
        game.game_id,
        ValueTriple(income, income, income),
        ValueTriple(cost, cost, cost),
        ValueTriple(income - cost, income - cost, income - cost),
        per_item,
    )


def _average_scores(values: Sequence[GameScore]) -> GameScore:
    if not values:
        raise ValueError("cannot average no scores")
    per_item = {}
    for index in values[0].per_item:
        items = [score.per_item[index] for score in values]
        per_item[index] = ItemScore(
            index=index,
            income=_average_triples([item.income for item in items]),
            cost=_average_triples([item.cost for item in items]),
            net=_average_triples([item.net for item in items]),
            ambiguity=items[0].ambiguity,
        )
    return GameScore(
        values[0].game_id,
        _average_triples([score.income for score in values]),
        _average_triples([score.cost for score in values]),
        _average_triples([score.net for score in values]),
        per_item,
        values[0].ambiguity,
    )


def _average_triples(values: Sequence[ValueTriple]) -> ValueTriple:
    return ValueTriple(
        statistics.fmean(value.lower for value in values),
        statistics.fmean(value.midpoint for value in values),
        statistics.fmean(value.upper for value in values),
    )


def _track_statistics(
    records: Sequence[TrackDraw],
    scores: Mapping[str, Mapping[int, Sequence[GameScore]]],
) -> dict[str, Any]:
    output = {}
    for track in sorted({record.track for record in records}):
        selected = [record for record in records if record.track == track]
        pooled_by_draw = []
        max_draws = max((record.draw for record in selected), default=-1) + 1
        for draw in range(max_draws):
            pooled_by_draw.append(
                sum(
                    per_draw[draw].net.midpoint
                    for per_draw in scores[track].values()
                    if draw < len(per_draw)
                )
            )
        runtimes = [record.elapsed_seconds for record in selected]
        output[track] = {
            "calls": len(selected),
            "failures": sum(record.error is not None for record in selected),
            "runtime_mean": statistics.fmean(runtimes) if runtimes else 0.0,
            "runtime_max": max(runtimes, default=0.0),
            "pooled_midpoint_by_draw": pooled_by_draw,
            "pooled_midpoint_spread": max(pooled_by_draw, default=0.0) - min(pooled_by_draw, default=0.0),
        }
    return output


def _regime_scores(
    scores: Mapping[str, Mapping[int, GameScore]], regimes: Sequence[tuple[str, int, int]]
) -> dict[str, Any]:
    return {
        name: {
            strategy: _pooled({game: value for game, value in per_game.items() if start <= game <= end})
            for strategy, per_game in scores.items()
        }
        for name, start, end in regimes
    }


def _pooled(scores: Mapping[int, GameScore]) -> dict[str, Any]:
    return {
        "games": sorted(scores),
        "lower": sum(score.net.lower for score in scores.values()),
        "midpoint": sum(score.net.midpoint for score in scores.values()),
        "upper": sum(score.net.upper for score in scores.values()),
    }


def _score_dict(score: GameScore) -> dict[str, Any]:
    return {
        "game_id": score.game_id,
        "income": asdict(score.income),
        "cost": asdict(score.cost),
        "net": asdict(score.net),
        "ambiguity": asdict(score.ambiguity),
    }


def _put(
    scores: dict[str, dict[int, GameScore]], strategy: str, game_id: int, score: GameScore
) -> None:
    scores.setdefault(strategy, {})[game_id] = score
