import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backtesting.history import HistoryStore
from backtesting.models import HistoricalDataset, Submission
from backtesting.tracks import merged_submission, run_track_draws
from src.data.models import CaseData, ItemPrice, LineItem, Proposal


class BacktestingTrackTests(unittest.IsolatedAsyncioTestCase):
    async def test_runs_tracks_in_parallel_for_each_sequential_draw_round(self) -> None:
        active = 0
        peak = 0
        calls = []

        async def operation(track, case, timeout):
            nonlocal active, peak
            calls.append(track)
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1
            return Proposal(track, (ItemPrice(1, 100, 20, track),))

        case = CaseData(5, Path("case"), line_items=(LineItem(1, "Repair"),))
        history = HistoryStore(HistoricalDataset(1, "test", "now", {}, ()))
        with tempfile.TemporaryDirectory() as directory, patch(
            "backtesting.tracks._operation", side_effect=operation
        ):
            result = await run_track_draws(
                case,
                history,
                Path(directory),
                draws=2,
                tracks=("strategy1", "strategy2"),
            )

        self.assertEqual(set(result), {0, 1})
        self.assertEqual(calls.count("strategy1"), 2)
        self.assertEqual(calls.count("strategy2"), 2)
        self.assertEqual(peak, 2)

    def test_merged_submission_keeps_the_highest_priority_per_item(self) -> None:
        from backtesting.tracks import TrackDraw

        case = CaseData(5, Path("case"), line_items=(LineItem(1), LineItem(2)))
        draws = {
            "fast_path": TrackDraw(5, "fast_path", 0, {1: Submission(50, 10), 2: Submission(50, 10)}, 1),
            "strategy1": TrackDraw(5, "strategy1", 0, {1: Submission(100, 20)}, 1),
            "strategy2": TrackDraw(5, "strategy2", 0, {1: Submission(200, 30)}, 1),
        }

        merged = merged_submission(case, draws)

        self.assertEqual(merged[1], Submission(200, 30))
        self.assertEqual(merged[2], Submission(50, 10))


if __name__ == "__main__":
    unittest.main()
