"""Incrementally acquire, validate, reconstruct, and persist settled Field data."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import shutil
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from backtesting.legacy import invert_fair_values, pull_transactions
from backtesting.models import (
    CapEstimate,
    ChargeEstimate,
    FairValueEstimate,
    HistoricalDataset,
    HistoricalGame,
    HistoricalItem,
    Interval,
    LimitEstimate,
    TeamDecision,
    Transaction,
    jsonable,
)
from backtesting.paths import CURRENT_DATASET, DATASETS, DATASET_SCHEMA_VERSION
from backtesting.reconstruction import reconstruct_game


def parse_games(spec: str, completed: Sequence[int], include_game_0: bool = False) -> list[int]:
    available = sorted(g for g in completed if include_game_0 or g != 0)
    if spec in {"all", "latest"}:
        return available
    selected: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if part.endswith("-"):
            selected.update(g for g in available if g >= int(part[:-1]))
            continue
        start, separator, end = part.partition("-")
        selected.update(range(int(start), int(end) + 1) if separator else (int(start),))
    missing = sorted(selected - set(available))
    if missing:
        raise ValueError(f"Games are not settled or available: {missing}")
    return sorted(selected)


def normalize_transactions(
    game_id: int, rows_by_team: Mapping[str, Sequence[Mapping[str, Any]]]
) -> tuple[Transaction, ...]:
    grouped: dict[tuple[int, int, str, str], dict[str, Any]] = {}
    for source_team, rows in rows_by_team.items():
        for raw in rows:
            row = Transaction(
                game_id=game_id,
                line_item_index=int(raw["line_item_index"]),
                issuer=str(raw["issuer"]),
                reviewer=str(raw["reviewer"]),
                accepted=bool(raw["accepted"]),
                amount=float(raw["amount"]),
                source_teams=(source_team,),
            )
            existing = grouped.get(row.key)
            if existing is None:
                grouped[row.key] = {
                    "row": row,
                    "sources": {source_team},
                }
                continue
            prior: Transaction = existing["row"]
            if (prior.accepted, prior.amount) != (row.accepted, row.amount):
                raise ValueError(f"Transaction copies disagree for {row.key}")
            existing["sources"].add(source_team)
    normalized = []
    for key, value in grouped.items():
        row: Transaction = value["row"]
        sources = tuple(sorted(value["sources"]))
        expected = {row.issuer, row.reviewer}
        if set(sources) != expected:
            raise ValueError(f"Transaction {key} appears in {sources}, expected {sorted(expected)}")
        normalized.append(
            Transaction(
                game_id=row.game_id,
                line_item_index=row.line_item_index,
                issuer=row.issuer,
                reviewer=row.reviewer,
                accepted=row.accepted,
                amount=row.amount,
                source_teams=sources,
            )
        )
    return tuple(sorted(normalized, key=lambda row: row.key))


def validate_complete_game(game_id: int, teams: Sequence[str], rows: Sequence[Transaction]) -> None:
    expected_pairs = {(issuer, reviewer) for issuer in teams for reviewer in teams if issuer != reviewer}
    indices = {row.line_item_index for row in rows}
    if not indices:
        raise ValueError(f"Game {game_id} has no Transactions")
    for index in indices:
        got = {(row.issuer, row.reviewer) for row in rows if row.line_item_index == index}
        if got != expected_pairs:
            missing = sorted(expected_pairs - got)
            extra = sorted(got - expected_pairs)
            raise ValueError(
                f"Game {game_id} item {index} pair coverage mismatch: "
                f"missing={missing[:5]} extra={extra[:5]}"
            )


def identity_net(rows: Sequence[Transaction], team: str) -> float:
    income = sum(row.amount for row in rows if row.issuer == team)
    cost = sum(
        row.amount if row.accepted else 1.5 * row.amount
        for row in rows
        if row.reviewer == team
    )
    return income - cost


def _case_metadata(game_id: int) -> dict[int, dict[str, object]]:
    from backtesting.paths import CASES
    from src.data.case_loader import read_case

    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return {}
    case = asyncio.run(read_case(game_id, case_dir))
    return {
        item.index: {
            "name": item.name,
            "quantity": item.quantity,
            "quantity_missing": item.quantity_missing,
        }
        for item in case.line_items
    }


def sync_dataset(
    games: str = "all",
    *,
    include_game_0: bool = False,
    refresh_transactions: bool = False,
    request_delay: float = 0.25,
) -> HistoricalDataset:
    completed = pull_transactions.completed_games()
    game_ids = parse_games(games, completed, include_game_0)
    teams = tuple(sorted(pull_transactions.teams()))
    try:
        matrix = pull_transactions.matrix()
    except Exception:
        matrix = {}

    reconstructed: dict[int, HistoricalGame] = {}
    for game_id in game_ids:
        rows_by_team: dict[str, list[dict]] = {}
        for team in teams:
            cached = pull_transactions.cache_status(team, game_id) == "ok"
            rows_by_team[team] = pull_transactions.transactions(
                team, game_id, refresh=refresh_transactions
            )
            if (refresh_transactions or not cached) and request_delay > 0:
                time.sleep(request_delay)
        rows = normalize_transactions(game_id, rows_by_team)
        validate_complete_game(game_id, teams, rows)
        nets = {team: identity_net(rows, team) for team in teams}
        leaderboard = {
            team: float(per_game[game_id])
            for team, per_game in matrix.items()
            if game_id in per_game
        }
        for team, value in leaderboard.items():
            if abs(nets[team] - value) > 0.01:
                raise ValueError(
                    f"Game {game_id} {team}: rows give {nets[team]:.2f}, matrix gives {value:.2f}"
                )
        fair = invert_fair_values.brackets(game_id, list(teams))
        reconstructed[game_id] = reconstruct_game(
            game_id,
            teams,
            rows,
            fair,
            nets,
            leaderboard,
            _case_metadata(game_id),
        )

    payload = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "teams": list(teams),
        "games": {str(game_id): _game_to_dict(game) for game_id, game in reconstructed.items()},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    dataset_id = hashlib.sha256(encoded.encode()).hexdigest()
    generated_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "generated_at": generated_at,
        "games": game_ids,
        "teams": list(teams),
        "game_count": len(game_ids),
        "transaction_count": sum(len(game.transactions) for game in reconstructed.values()),
        "source": "public leaderboard JSON API via scripts/pull_transactions.py",
        "cap_modes": ["fitted", "rules_only"],
    }
    dataset = HistoricalDataset(
        schema_version=DATASET_SCHEMA_VERSION,
        dataset_id=dataset_id,
        generated_at=generated_at,
        games=reconstructed,
        teams=teams,
        manifest=manifest,
    )
    _publish(dataset)
    return dataset


def _publish(dataset: HistoricalDataset) -> Path:
    DATASETS.mkdir(parents=True, exist_ok=True)
    target = DATASETS / dataset.dataset_id[:16]
    if not target.exists():
        staging = Path(tempfile.mkdtemp(prefix="dataset-", dir=DATASETS))
        try:
            _write_dataset(dataset, staging)
            os.replace(staging, target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    pointer = CURRENT_DATASET.with_suffix(".tmp")
    pointer.write_text(json.dumps({"dataset_id": dataset.dataset_id, "path": target.name}, indent=2))
    os.replace(pointer, CURRENT_DATASET)
    return target


def _write_dataset(dataset: HistoricalDataset, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(json.dumps(jsonable(dataset.manifest), indent=2))
    games = {str(game_id): _game_to_dict(game) for game_id, game in dataset.games.items()}
    (directory / "games.json").write_text(json.dumps(games, indent=2, ensure_ascii=False))
    transactions = [
        jsonable(row)
        for game in dataset.games.values()
        for row in game.transactions
    ]
    (directory / "transactions.json").write_text(json.dumps(transactions, indent=1, ensure_ascii=False))
    decisions = _decision_rows(dataset)
    (directory / "decisions.json").write_text(json.dumps(decisions, indent=1, ensure_ascii=False))
    fair_values = _fair_rows(dataset)
    (directory / "fair_values.json").write_text(json.dumps(fair_values, indent=1, ensure_ascii=False))
    line_items = _line_item_rows(dataset)
    (directory / "line_items.json").write_text(json.dumps(line_items, indent=1, ensure_ascii=False))
    _write_csv(directory / "games.csv", _game_rows(dataset))
    _write_csv(directory / "transactions.csv", transactions)
    _write_csv(directory / "decisions.csv", decisions)
    _write_csv(directory / "fair_values.csv", fair_values)
    _write_csv(directory / "line_items.csv", line_items)
    validation = {
        str(game_id): {
            "status": game.validation_status,
            "teams": len(game.teams),
            "items": len(game.items),
            "transactions": len(game.transactions),
        }
        for game_id, game in dataset.games.items()
    }
    (directory / "validation.json").write_text(json.dumps(validation, indent=2))


def load_dataset(dataset_id: str | None = None) -> HistoricalDataset:
    if dataset_id is None:
        pointer = json.loads(CURRENT_DATASET.read_text())
        directory = DATASETS / pointer["path"]
    else:
        matches = [path for path in DATASETS.iterdir() if path.is_dir() and path.name.startswith(dataset_id)]
        if len(matches) != 1:
            raise ValueError(f"dataset prefix {dataset_id!r} matched {len(matches)} directories")
        directory = matches[0]
    manifest = json.loads((directory / "manifest.json").read_text())
    raw_games = json.loads((directory / "games.json").read_text())
    games = {int(game_id): _game_from_dict(value) for game_id, value in raw_games.items()}
    return HistoricalDataset(
        schema_version=int(manifest["schema_version"]),
        dataset_id=str(manifest["dataset_id"]),
        generated_at=str(manifest["generated_at"]),
        games=games,
        teams=tuple(manifest["teams"]),
        manifest=manifest,
    )


def _game_to_dict(game: HistoricalGame) -> dict[str, Any]:
    return {
        "game_id": game.game_id,
        "teams": list(game.teams),
        "items": {
            str(index): {
                "index": item.index,
                "name": item.name,
                "quantity": item.quantity,
                "quantity_missing": item.quantity_missing,
                "fair_value": jsonable(item.fair_value),
                "cap": jsonable(item.cap),
                "decisions": {team: jsonable(decision) for team, decision in item.decisions.items()},
            }
            for index, item in game.items.items()
        },
        "transactions": [jsonable(row) for row in game.transactions],
        "authoritative_nets": dict(game.authoritative_nets),
        "leaderboard_nets": dict(game.leaderboard_nets),
        "validation_status": game.validation_status,
    }


def _game_from_dict(value: Mapping[str, Any]) -> HistoricalGame:
    items: dict[int, HistoricalItem] = {}
    for raw_index, raw in value["items"].items():
        index = int(raw_index)
        fv = raw["fair_value"]
        cap = raw["cap"]
        decisions = {}
        for team, decision in raw["decisions"].items():
            charge = decision["charge"]
            limit = decision["limit"]
            decisions[team] = TeamDecision(
                team=team,
                charge=ChargeEstimate(
                    interval=Interval.from_dict(charge["interval"]),
                    status=charge["status"],
                    accepted=int(charge["accepted"]),
                    rejected_positive=int(charge["rejected_positive"]),
                    rejected_zero=int(charge["rejected_zero"]),
                    observed_amounts=tuple(charge["observed_amounts"]),
                ),
                limit=LimitEstimate(
                    interval=Interval.from_dict(limit["interval"]),
                    lower_witness=limit.get("lower_witness"),
                    upper_witness=limit.get("upper_witness"),
                    accepted_witnesses=int(limit["accepted_witnesses"]),
                    rejected_witnesses=int(limit["rejected_witnesses"]),
                ),
            )
        items[index] = HistoricalItem(
            index=index,
            fair_value=FairValueEstimate(
                interval=Interval.from_dict(fv["interval"]),
                lower_witnesses=tuple(fv.get("lower_witnesses", ())),
                upper_witnesses=tuple(fv.get("upper_witnesses", ())),
            ),
            cap=CapEstimate(
                observed_paid_floor=float(cap["observed_paid_floor"]),
                empirical_floor=float(cap["empirical_floor"]),
                status=cap["status"],
                evidence=tuple(cap.get("evidence", ())),
            ),
            decisions=decisions,
            name=raw.get("name", ""),
            quantity=float(raw.get("quantity", 1.0)),
            quantity_missing=bool(raw.get("quantity_missing", False)),
        )
    transactions = tuple(
        Transaction(**{**row, "source_teams": tuple(row.get("source_teams", ()))})
        for row in value["transactions"]
    )
    return HistoricalGame(
        game_id=int(value["game_id"]),
        teams=tuple(value["teams"]),
        items=items,
        transactions=transactions,
        authoritative_nets={key: float(item) for key, item in value["authoritative_nets"].items()},
        leaderboard_nets={key: float(item) for key, item in value["leaderboard_nets"].items()},
        validation_status=value.get("validation_status", "ok"),
    )


def _decision_rows(dataset: HistoricalDataset) -> list[dict[str, Any]]:
    rows = []
    for game in dataset.games.values():
        for item in game.items.values():
            for team, decision in item.decisions.items():
                rows.append(
                    {
                        "game_id": game.game_id,
                        "line_item_index": item.index,
                        "team": team,
                        "charge_low": decision.charge.interval.low,
                        "charge_high": decision.charge.interval.high,
                        "charge_status": decision.charge.status,
                        "charge_exact": decision.charge.exact,
                        "limit_low": decision.limit.interval.low,
                        "limit_high": decision.limit.interval.high,
                        "limit_bounded": decision.limit.interval.bounded,
                        "limit_lower_witness": decision.limit.lower_witness,
                        "limit_upper_witness": decision.limit.upper_witness,
                    }
                )
    return rows


def _fair_rows(dataset: HistoricalDataset) -> list[dict[str, Any]]:
    return [
        {
            "game_id": game.game_id,
            "line_item_index": item.index,
            "fair_low": item.fair_value.interval.low,
            "fair_high": item.fair_value.interval.high,
            "fair_bounded": item.fair_value.interval.bounded,
            "cap_observed_floor": item.cap.observed_paid_floor,
            "cap_empirical_floor": item.cap.empirical_floor,
            "cap_status": item.cap.status,
        }
        for game in dataset.games.values()
        for item in game.items.values()
    ]


def _line_item_rows(dataset: HistoricalDataset) -> list[dict[str, Any]]:
    return [
        {
            "game_id": game.game_id,
            "line_item_index": item.index,
            "name": item.name,
            "quantity": item.quantity,
            "quantity_missing": item.quantity_missing,
        }
        for game in dataset.games.values()
        for item in game.items.values()
    ]


def _game_rows(dataset: HistoricalDataset) -> list[dict[str, Any]]:
    return [
        {
            "game_id": game.game_id,
            "teams": len(game.teams),
            "line_items": len(game.items),
            "transactions": len(game.transactions),
            "status": game.validation_status,
        }
        for game in dataset.games.values()
    ]


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
