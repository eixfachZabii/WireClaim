import tempfile
import unittest
from pathlib import Path

from backtesting.history import HistoryView
from backtesting.models import Submission
from backtesting.strategies import StrategyContext, load_json_submissions, run_candidate
from src.data.models import CaseData


class BacktestingStrategyTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_candidate_is_normalized_and_checked(self) -> None:
        context = StrategyContext(CaseData(4, Path("case")), HistoryView(4, {}), 1)

        def candidate(ctx, params):
            return {1: (params["charge"], 20)}

        result = await run_candidate(candidate, context, {"charge": 100}, {1})
        self.assertEqual(result, {1: Submission(100, 20)})

    async def test_missing_candidate_item_fails_by_default(self) -> None:
        context = StrategyContext(CaseData(4, Path("case")), HistoryView(4, {}), 1)
        with self.assertRaisesRegex(ValueError, "omitted"):
            await run_candidate(lambda ctx, params: {}, context, {}, {1})

    def test_json_submission_interface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "submissions.json"
            path.write_text('{"version":1,"games":{"2":{"1":{"charge":50,"limit":30}}}}')
            loaded = load_json_submissions(path)
        self.assertEqual(loaded[2][1], Submission(50, 30))


if __name__ == "__main__":
    unittest.main()
