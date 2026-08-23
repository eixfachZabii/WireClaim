import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backtesting.logged import interval_contains, proposal_compatibility, replay_logged
from backtesting.models import (
    CapEstimate,
    ChargeEstimate,
    FairValueEstimate,
    HistoricalDataset,
    HistoricalGame,
    HistoricalItem,
    Interval,
    LimitEstimate,
    Submission,
    TeamDecision,
    Transaction,
)
from src.runtime import decisions as decision_log


class LoggedReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        decisions = {
            "Bin busy": TeamDecision(
                "Bin busy",
                ChargeEstimate(Interval.point(100), "exact"),
                LimitEstimate(Interval(90, 110)),
            ),
            "Other": TeamDecision(
                "Other",
                ChargeEstimate(Interval.point(100), "exact"),
                LimitEstimate(Interval(90, 110)),
            ),
        }
        item = HistoricalItem(
            1,
            FairValueEstimate(Interval.point(100)),
            CapEstimate(2000),
            decisions,
            name="Repair",
        )
        transactions = (
            Transaction(1, 1, "Bin busy", "Other", True, 100, ("Bin busy", "Other")),
            Transaction(1, 1, "Other", "Bin busy", True, 100, ("Bin busy", "Other")),
        )
        game = HistoricalGame(
            1,
            ("Bin busy", "Other"),
            {1: item},
            transactions,
            {"Bin busy": 0.0, "Other": 0.0},
        )
        self.dataset = HistoricalDataset(
            1,
            "dataset",
            "now",
            {1: game},
            ("Bin busy", "Other"),
            {"schema_version": 1},
        )

    def test_interval_contains_respects_open_and_strict_boundaries(self) -> None:
        self.assertTrue(interval_contains(Interval(10, 20), 10))
        self.assertFalse(interval_contains(Interval(10, 20), 20))
        self.assertFalse(interval_contains(Interval(10, None, low_strict=True), 10))

    def test_compatibility_detects_a_logged_value_outside_the_identified_bracket(self) -> None:
        game = self.dataset.games[1]
        self.assertEqual(proposal_compatibility(game, {1: Submission(100, 100)}, "Bin busy"), [])
        errors = proposal_compatibility(game, {1: Submission(120, 100)}, "Bin busy")
        self.assertIn("logged Charge 120.00", errors[0])

    def test_replays_the_logged_winner_without_model_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / "decisions"
            logs.mkdir()
            (logs / "game_001.json").write_text(
                json.dumps(
                    {
                        "schema": 2,
                        "game_id": 1,
                        "strategy": "strategy2",
                        "items": [{"index": 1, "charge": 100, "limit": 100}],
                        "proposals": {"strategy2": {"1": [100, 100]}},
                        "winner": "strategy2",
                    }
                )
            )
            with (
                patch.object(decision_log, "DECISIONS_DIR", logs),
                patch("backtesting.logged.load_dataset", return_value=self.dataset),
                patch("backtesting.logged.RUNS", root / "runs"),
            ):
                run_dir, result = replay_logged("1")
                report_exists = (run_dir / "report.md").exists()

        replay = result["logged_replay"]["1"]["sources"]["strategy2"]
        self.assertTrue(replay["behaviorally_compatible"])
        self.assertTrue(replay["reproduces_actual_to_cent"])
        self.assertEqual(result["scores"]["logged_strategy2"]["1"]["net"]["midpoint"], 0.0)
        self.assertTrue(report_exists)


if __name__ == "__main__":
    unittest.main()
