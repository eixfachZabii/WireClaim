"""Data quality and identifiability diagnostics for historical datasets and scores."""

from __future__ import annotations

import collections
from typing import Mapping

from backtesting.models import GameScore, HistoricalDataset


def dataset_diagnostics(dataset: HistoricalDataset) -> dict:
    charges = collections.Counter()
    bounded_limits = bounded_fair = total_decisions = total_items = 0
    limit_widths = []
    fair_widths = []
    caps = collections.Counter()
    for game in dataset.games.values():
        for item in game.items.values():
            total_items += 1
            caps[item.cap.status] += 1
            if item.fair_value.interval.bounded:
                bounded_fair += 1
                fair_widths.append(item.fair_value.interval.width or 0.0)
            for decision in item.decisions.values():
                total_decisions += 1
                charges[decision.charge.status] += 1
                if decision.limit.interval.bounded:
                    bounded_limits += 1
                    limit_widths.append(decision.limit.interval.width or 0.0)
    return {
        "dataset_id": dataset.dataset_id,
        "games": len(dataset.games),
        "teams": len(dataset.teams),
        "transactions": sum(len(game.transactions) for game in dataset.games.values()),
        "line_items": total_items,
        "team_decisions": total_decisions,
        "charge_statuses": dict(charges),
        "exact_charge_share": (
            sum(charges[key] for key in ("exact", "exact_accepted", "zero")) / total_decisions
            if total_decisions
            else 0.0
        ),
        "bounded_limit_share": bounded_limits / total_decisions if total_decisions else 0.0,
        "bounded_fair_value_share": bounded_fair / total_items if total_items else 0.0,
        "median_limit_width": _median(limit_widths),
        "median_fair_value_width": _median(fair_widths),
        "cap_statuses": dict(caps),
    }


def score_diagnostics(scores: Mapping[str, Mapping[int, GameScore]]) -> dict:
    output = {}
    for strategy, per_game in scores.items():
        games = list(per_game.values())
        lower = sum(game.net.lower for game in games)
        midpoint = sum(game.net.midpoint for game in games)
        upper = sum(game.net.upper for game in games)
        output[strategy] = {
            "games": len(games),
            "lower": lower,
            "midpoint": midpoint,
            "upper": upper,
            "envelope_width": upper - lower,
            "ambiguity": {
                key: sum(getattr(game.ambiguity, key) for game in games)
                for key in (
                    "opponent_limits",
                    "opponent_charges",
                    "fair_values",
                    "caps",
                    "missing_outputs",
                )
            },
        }
    return output


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
