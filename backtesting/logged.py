"""Deterministically replay Proposals captured by the live decision logs."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from backtesting.data import load_dataset, parse_games
from backtesting.diagnostics import dataset_diagnostics, score_diagnostics
from backtesting.models import GameScore, HistoricalGame, Interval, Submission
from backtesting.paths import RUN_SCHEMA_VERSION, RUNS
from backtesting.reporting import print_summary, write_report
from backtesting.scoring import reconstructed_submission, score_game
from src.observability.decisions import load as load_decisions
from src.observability.decisions import path_for, proposals


def replay_logged(
    games: str,
    *,
    dataset_id: str | None = None,
    source: str = "winner",
    seat: str = "Bin busy",
    cap_mode: str = "fitted",
) -> tuple[Path, dict[str, Any]]:
    dataset = load_dataset(dataset_id)
    game_ids = parse_games(games, sorted(dataset.games))
    if not game_ids:
        raise ValueError(f"no Games matched {games!r}")
    if seat not in dataset.teams:
        raise ValueError(f"seat {seat!r} is not in the dataset")

    run_dir, manifest = _create_run(dataset, game_ids, source, seat, cap_mode)
    scores: dict[str, dict[int, GameScore]] = {"actual": {}, "actual_reconstructed": {}}
    checks: dict[str, Any] = {}
    per_item: list[dict[str, Any]] = []

    for game_id in game_ids:
        game = dataset.games[game_id]
        payload = load_decisions(game_id)
        if payload is None:
            raise FileNotFoundError(f"no readable decision log for Game {game_id}")
        logged = proposals(payload)
        selected = _selected_sources(payload, logged, source)
        scores["actual"][game_id] = actual_score(game, seat)
        scores["actual_reconstructed"][game_id] = score_game(
            game,
            reconstructed_submission(game, seat),
            seat=seat,
            cap_mode=cap_mode,
        )
        game_checks = {
            "schema": payload.get("schema"),
            "strategy": payload.get("strategy"),
            "winner": payload.get("winner"),
            "recorded_at": payload.get("recorded_at"),
            "proposals_recorded_at": payload.get("proposals_recorded_at"),
            "decision_log": str(path_for(game_id)),
            "sources": {},
        }
        for name in selected:
            raw = logged.get(name)
            origin = "proposals"
            if not raw and name == "strategy2":
                raw = _strategy2_items(payload)
                origin = "items"
            if not raw:
                raise ValueError(f"Game {game_id} has no logged Proposal for {name!r}")
            submission = {index: Submission(*pair) for index, pair in raw.items()}
            missing = sorted(set(game.items) - set(submission))
            extra = sorted(set(submission) - set(game.items))
            if missing or extra:
                raise ValueError(
                    f"Game {game_id} {name}: missing Line Items {missing}, extra {extra}"
                )
            compatibility = proposal_compatibility(game, submission, seat)
            scored = score_game(game, submission, seat=seat, cap_mode=cap_mode)
            label = f"logged_{name}"
            scores.setdefault(label, {})[game_id] = scored
            actual = game.authoritative_nets[seat]
            game_checks["sources"][name] = {
                "origin": origin,
                "line_items": len(submission),
                "behaviorally_compatible": not compatibility,
                "compatibility_errors": compatibility,
                "midpoint_net": scored.net.midpoint,
                "actual_net": actual,
                "delta_to_actual": scored.net.midpoint - actual,
                "reproduces_actual_to_cent": abs(scored.net.midpoint - actual) <= 0.01,
            }
            for index, item_score in scored.per_item.items():
                pair = submission[index]
                per_item.append(
                    {
                        "strategy": label,
                        "game_id": game_id,
                        "line_item_index": index,
                        "charge": pair.charge,
                        "limit": pair.limit,
                        "income_lower": item_score.income.lower,
                        "income_midpoint": item_score.income.midpoint,
                        "income_upper": item_score.income.upper,
                        "cost_lower": item_score.cost.lower,
                        "cost_midpoint": item_score.cost.midpoint,
                        "cost_upper": item_score.cost.upper,
                        "net_lower": item_score.net.lower,
                        "net_midpoint": item_score.net.midpoint,
                        "net_upper": item_score.net.upper,
                    }
                )
        checks[str(game_id)] = game_checks

    result = {
        "schema_version": RUN_SCHEMA_VERSION,
        "manifest": manifest,
        "scores": {
            label: {str(game_id): score_dict(score) for game_id, score in per_game.items()}
            for label, per_game in scores.items()
        },
        "per_item": per_item,
        "tracks": {},
        "sweeps": {},
        "regimes": {},
        "logged_replay": checks,
        "diagnostics": {
            "dataset": dataset_diagnostics(dataset),
            "scores": score_diagnostics(scores),
        },
    }
    (run_dir / "logged_replay.json").write_text(json.dumps(checks, indent=2))
    write_report(run_dir, result)
    print_summary(result)
    _print_checks(checks)
    return run_dir, result


def proposal_compatibility(
    game: HistoricalGame, submission: Mapping[int, Submission], seat: str
) -> list[str]:
    errors = []
    for index, item in game.items.items():
        submitted = submission[index]
        decision = item.decisions[seat]
        if not interval_contains(decision.charge.interval, submitted.charge):
            errors.append(
                f"item {index}: logged Charge {submitted.charge:.2f} outside "
                f"{_interval_text(decision.charge.interval)}"
            )
        if not interval_contains(decision.limit.interval, submitted.limit):
            errors.append(
                f"item {index}: logged Limit {submitted.limit:.2f} outside "
                f"{_interval_text(decision.limit.interval)}"
            )
    return errors


def interval_contains(interval: Interval, value: float) -> bool:
    if not math.isfinite(value) or value < interval.low:
        return False
    if interval.low_strict and value <= interval.low:
        return False
    if interval.high is None:
        return True
    return value <= interval.high if interval.high_inclusive else value < interval.high


def actual_score(game: HistoricalGame, seat: str) -> GameScore:
    from backtesting.experiments import _actual_score

    return _actual_score(game, seat)


def score_dict(score: GameScore) -> dict[str, Any]:
    return {
        "game_id": score.game_id,
        "income": asdict(score.income),
        "cost": asdict(score.cost),
        "net": asdict(score.net),
        "ambiguity": asdict(score.ambiguity),
    }


def _selected_sources(
    payload: Mapping[str, Any], logged: Mapping[str, Any], source: str
) -> tuple[str, ...]:
    if source == "all":
        names = tuple(sorted(logged))
        if not names and payload.get("items"):
            return ("strategy2",)
        return names
    if source == "winner":
        winner = payload.get("winner")
        if not winner:
            if payload.get("strategy") == "strategy2" and payload.get("items"):
                return ("strategy2",)
            raise ValueError(f"decision log has no winner: choose --source explicitly")
        return (str(winner),)
    return (source,)


def _strategy2_items(payload: Mapping[str, Any]) -> dict[int, tuple[float, float]]:
    result = {}
    for item in payload.get("items") or ():
        try:
            result[int(item["index"])] = (float(item["charge"]), float(item["limit"]))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _create_run(dataset, game_ids: Sequence[int], source: str, seat: str, cap_mode: str):
    created_at = datetime.now(timezone.utc)
    identity = json.dumps(
        {
            "dataset": dataset.dataset_id,
            "games": list(game_ids),
            "source": source,
            "seat": seat,
            "cap_mode": cap_mode,
        },
        sort_keys=True,
    )
    suffix = hashlib.sha256(identity.encode()).hexdigest()[:8]
    run_id = f"{created_at.strftime('%Y%m%dT%H%M%SZ')}-logged-{suffix}"
    run_dir = RUNS / run_id
    counter = 1
    while run_dir.exists():
        run_dir = RUNS / f"{run_id}-{counter}"
        counter += 1
    run_dir.mkdir(parents=True)
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
        "name": "logged-decision-replay",
        "created_at": created_at.isoformat(),
        "dataset_id": dataset.dataset_id,
        "dataset_schema": dataset.schema_version,
        "git_revision": revision,
        "games": list(game_ids),
        "seat": seat,
        "draws": 0,
        "tracks": [],
        "cap_mode": cap_mode,
        "source": source,
        "mode": "logged-deterministic",
        "noise_floor": 26_622.0 * math.sqrt(len(game_ids) / 18.0),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (run_dir / "dataset_manifest.json").write_text(json.dumps(dataset.manifest, indent=2))
    return run_dir, manifest


def _interval_text(interval: Interval) -> str:
    left = "(" if interval.low_strict else "["
    right = "]" if interval.high_inclusive else ")"
    high = "inf" if interval.high is None else f"{interval.high:.2f}"
    return f"{left}{interval.low:.2f}, {high}{right}"


def _print_checks(checks: Mapping[str, Any]) -> None:
    for game_id, game in checks.items():
        print(f"Game {game_id}: winner={game.get('winner')!r}, schema={game.get('schema')}")
        for source, check in game["sources"].items():
            status = "EXACT" if check["reproduces_actual_to_cent"] else "DIFF"
            compatible = "compatible" if check["behaviorally_compatible"] else "INCOMPATIBLE"
            print(
                f"  {source}: {status}, midpoint {check['midpoint_net']:,.2f}, "
                f"actual {check['actual_net']:,.2f}, delta {check['delta_to_actual']:+,.2f}, "
                f"{compatible}"
            )
