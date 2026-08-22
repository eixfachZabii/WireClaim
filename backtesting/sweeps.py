"""Parameter grid expansion and chronological out-of-sample evaluation."""

from __future__ import annotations

import itertools
import json
from typing import Any, Mapping, Sequence

from backtesting.models import GameScore


def expand_grid(base: Mapping[str, Any], grid: Mapping[str, Sequence[Any]]) -> list[dict[str, Any]]:
    keys = tuple(sorted(grid))
    return [
        {**base, **dict(zip(keys, values))}
        for values in itertools.product(*(grid[key] for key in keys))
    ]


def parameter_key(params: Mapping[str, Any]) -> str:
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def chronological_evaluation(
    scores: Mapping[str, Mapping[int, GameScore]],
    game_ids: Sequence[int],
    *,
    holdout_fraction: float,
    min_train: int,
    step: int,
    objective: str = "midpoint_net",
) -> dict[str, Any]:
    ordered = tuple(sorted(game_ids))
    cutoff = max(1, min(len(ordered) - 1, round(len(ordered) * (1.0 - holdout_fraction))))
    train, test = ordered[:cutoff], ordered[cutoff:]
    chosen = _best(scores, train, objective)
    holdout = _summary(scores[chosen], test)
    walk_rows = []
    for offset in range(min_train, len(ordered), max(step, 1)):
        prior = ordered[:offset]
        upcoming = ordered[offset : offset + max(step, 1)]
        if not upcoming:
            break
        selected = _best(scores, prior, objective)
        walk_rows.append(
            {
                "train_games": list(prior),
                "test_games": list(upcoming),
                "selected": selected,
                "score": _summary(scores[selected], upcoming),
            }
        )
    walk_games = sum((row["test_games"] for row in walk_rows), [])
    walk_lower = sum(row["score"]["lower"] for row in walk_rows)
    walk_midpoint = sum(row["score"]["midpoint"] for row in walk_rows)
    walk_upper = sum(row["score"]["upper"] for row in walk_rows)
    return {
        "train_games": list(train),
        "test_games": list(test),
        "selected": chosen,
        "train_score": _summary(scores[chosen], train),
        "holdout_score": holdout,
        "walk_forward": walk_rows,
        "walk_forward_score": {
            "games": walk_games,
            "lower": walk_lower,
            "midpoint": walk_midpoint,
            "upper": walk_upper,
        },
    }


def _best(
    scores: Mapping[str, Mapping[int, GameScore]], games: Sequence[int], objective: str
) -> str:
    if objective not in {"midpoint_net", "lower_net"}:
        raise ValueError(f"unsupported sweep objective {objective!r}")
    def rank(key: str) -> tuple[float, float, str]:
        summary = _summary(scores[key], games)
        primary = summary["midpoint"] if objective == "midpoint_net" else summary["lower"]
        return (primary, summary["lower"], _reverse_lexical(key))
    return max(scores, key=rank)


def _reverse_lexical(value: str) -> str:
    return "".join(chr(0x10FFFF - ord(character)) for character in value)


def _summary(scores: Mapping[int, GameScore], games: Sequence[int]) -> dict[str, Any]:
    selected = [scores[game_id].net for game_id in games]
    return {
        "games": list(games),
        "lower": sum(value.lower for value in selected),
        "midpoint": sum(value.midpoint for value in selected),
        "upper": sum(value.upper for value in selected),
    }
