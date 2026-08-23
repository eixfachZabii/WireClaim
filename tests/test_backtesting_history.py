import unittest

from backtesting.history import HistoryStore, HistoryView, use_price_memory
from backtesting.models import (
    CapEstimate,
    FairValueEstimate,
    HistoricalDataset,
    HistoricalGame,
    HistoricalItem,
    Interval,
)
from src.evidence import memory as price_memory


class BacktestingHistoryTests(unittest.TestCase):
    def test_history_rejects_current_or_future_games(self) -> None:
        game = HistoricalGame(2, (), {}, (), {})
        with self.assertRaisesRegex(ValueError, "future"):
            HistoryView(2, {2: game})

    def test_price_memory_contains_only_earlier_games_and_restores_global(self) -> None:
        item = HistoricalItem(
            1,
            FairValueEstimate(Interval.point(120)),
            CapEstimate(2000),
            {},
            name="Skilled worker hours (2 hrs)",
            quantity=2,
        )
        games = {
            1: HistoricalGame(1, (), {1: item}, (), {}),
            3: HistoricalGame(3, (), {1: item}, (), {}),
        }
        dataset = HistoricalDataset(1, "test", "now", games, ())
        store = HistoryStore(dataset)
        memory = store.memory_before(3)

        self.assertEqual(memory.games, (1,))
        previous = price_memory._DEFAULT
        with use_price_memory(memory):
            self.assertIs(price_memory._DEFAULT, memory)
        self.assertIs(price_memory._DEFAULT, previous)

    def test_price_memory_is_restored_after_an_exception(self) -> None:
        memory = HistoryStore(HistoricalDataset(1, "test", "now", {}, ())).memory_before(2)
        previous = price_memory._DEFAULT
        with self.assertRaises(RuntimeError):
            with use_price_memory(memory):
                raise RuntimeError("boom")
        self.assertIs(price_memory._DEFAULT, previous)


if __name__ == "__main__":
    unittest.main()
