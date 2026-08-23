"""Candidate strategy protocols, dynamic loading, validation, and fixed baselines."""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

from backtesting.history import HistoryView
from backtesting.models import HistoricalGame, Submission
from src.data.models import CaseData, Proposal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrategyContext:
    case: CaseData
    history: HistoryView
    seed: int
    artifact_dir: Path | None = None

    @property
    def game_id(self) -> int:
        return self.case.game_id

    def random(self) -> random.Random:
        return random.Random(self.seed)


Candidate = Callable[
    [StrategyContext, Mapping[str, Any]],
    Mapping[int, Submission | tuple[float, float]] | Proposal | Awaitable[Mapping[int, Submission | tuple[float, float]] | Proposal],
]


def load_candidate(path: str) -> Candidate:
    module_name, separator, attribute = path.partition(":")
    if not separator:
        raise ValueError("candidate entry point must be 'module:function'")
    candidate = getattr(importlib.import_module(module_name), attribute)
    if not callable(candidate):
        raise TypeError(f"{path!r} is not callable")
    return candidate


async def run_candidate(
    candidate: Candidate,
    context: StrategyContext,
    params: Mapping[str, Any],
    expected_indices: set[int],
    *,
    allow_missing: bool = False,
) -> dict[int, Submission]:
    raw = candidate(context, params)
    if inspect.isawaitable(raw):
        raw = await raw
    if isinstance(raw, Proposal):
        values: Mapping[int, Any] = {
            price.index: (price.charge_price, price.acceptance_limit) for price in raw.prices
        }
    elif isinstance(raw, Mapping):
        values = raw
    else:
        raise TypeError("candidate must return a Proposal or mapping")
    result = {int(index): _submission(value) for index, value in values.items()}
    extra = set(result) - expected_indices
    missing = expected_indices - set(result)
    if extra:
        raise ValueError(f"candidate returned unknown Line Item indices {sorted(extra)}")
    if missing and not allow_missing:
        raise ValueError(f"candidate omitted Line Item indices {sorted(missing)}")
    if missing:
        logger.warning("Candidate omitted Game %s Line Items %s; tournament defaults apply.", context.game_id, sorted(missing))
    return result


def load_json_submissions(path: str | Path, strategy: str | None = None) -> dict[int, dict[int, Submission]]:
    payload = json.loads(Path(path).read_text())
    if int(payload.get("version", 1)) != 1:
        raise ValueError(f"unsupported submission JSON version {payload.get('version')}")
    strategies = payload.get("strategies")
    if strategies is not None:
        if strategy is None:
            if len(strategies) != 1:
                raise ValueError("submission JSON contains multiple strategies; select one")
            strategy = next(iter(strategies))
        games = strategies[strategy]
    else:
        games = payload["games"]
    return {
        int(game_id): {int(index): _submission(value) for index, value in per_item.items()}
        for game_id, per_item in games.items()
    }


def standard_submission(case: CaseData) -> dict[int, Submission]:
    from src.strategies.fast_path import standard_values

    return {
        price.index: Submission(price.charge_price, price.acceptance_limit)
        for price in standard_values(case).prices
    }


def oracle_submission(game: HistoricalGame, point: bool = False) -> dict[int, Submission]:
    result = {}
    for index, item in game.items.items():
        interval = item.fair_value.interval
        value = interval.representative() if point else interval.low
        limit = interval.representative() if point else (interval.high if interval.high is not None else interval.low)
        result[index] = Submission(value, limit)
    return result


def _submission(value: Any) -> Submission:
    if isinstance(value, Submission):
        return value
    if isinstance(value, Mapping):
        return Submission(float(value["charge"]), float(value["limit"]))
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return Submission(float(value[0]), float(value[1]))
    raise TypeError(f"invalid submission value {value!r}")
