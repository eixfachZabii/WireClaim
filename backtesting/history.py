"""Past-only historical context and time-safe Price Memory construction."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Iterator, Mapping

from backtesting.models import HistoricalDataset, HistoricalGame
from src.evidence import memory as price_memory
from src.evidence.memory import PriceMemory, build_entries, is_per_unit, normalise, normalise_unit
from src.strategies.strategy2.channels import unit_of


@dataclass(frozen=True)
class HistoryView:
    current_game_id: int
    games: Mapping[int, HistoricalGame]

    def __post_init__(self) -> None:
        leaked = [game_id for game_id in self.games if game_id >= self.current_game_id]
        if leaked:
            raise ValueError(f"history for Game {self.current_game_id} contains future Games {leaked}")

    @property
    def game_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self.games))

    def acceptance_rate(self, minimum_charge: float = 0.01) -> float:
        rows = [
            row
            for game in self.games.values()
            for row in game.transactions
            if row.amount >= minimum_charge
        ]
        return sum(row.accepted for row in rows) / len(rows) if rows else 0.0


class HistoryStore:
    def __init__(self, dataset: HistoricalDataset) -> None:
        self.dataset = dataset
        self._memories: dict[int, PriceMemory] = {}

    def before(self, game_id: int) -> HistoryView:
        return HistoryView(game_id, {key: value for key, value in self.dataset.games.items() if key < game_id})

    def memory_before(self, game_id: int) -> PriceMemory:
        cached = self._memories.get(game_id)
        if cached is not None:
            return cached
        observations = []
        for prior_id, game in self.dataset.games.items():
            if prior_id >= game_id:
                continue
            for item in game.items.values():
                interval = item.fair_value.interval
                total = interval.representative()
                unit = normalise_unit(unit_of(item.name))
                quantity = max(item.quantity, 1.0)
                per_unit = is_per_unit(unit)
                observations.append(
                    {
                        "key": normalise(item.name),
                        "display_name": item.name,
                        "game": prior_id,
                        "value": total / quantity if per_unit else total,
                        "unit": unit,
                        "positive": interval.low > 0,
                        "line_item_index": item.index,
                        "quantity": quantity,
                        "t_low": interval.low,
                        "t_high": interval.high,
                        "basis": "per_unit" if per_unit else "gross",
                    }
                )
        memory = PriceMemory.from_dict({"entries": build_entries(observations)})
        self._memories[game_id] = memory
        return memory


@contextlib.contextmanager
def use_price_memory(memory: PriceMemory) -> Iterator[None]:
    previous = price_memory._DEFAULT
    price_memory._DEFAULT = memory
    try:
        yield
    finally:
        price_memory._DEFAULT = previous
