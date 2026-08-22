import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backtesting.experiments import run_experiment
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
)
from src.data.models import CaseData, LineItem


class BacktestingExperimentTests(unittest.IsolatedAsyncioTestCase):
    async def test_small_end_to_end_run_writes_reproducible_reports(self) -> None:
        decisions = {
            "Bin busy": TeamDecision("Bin busy", ChargeEstimate(Interval.point(100), "exact"), LimitEstimate(Interval.point(100))),
            "Other": TeamDecision("Other", ChargeEstimate(Interval.point(100), "exact"), LimitEstimate(Interval.point(100))),
        }
        item = HistoricalItem(1, FairValueEstimate(Interval.point(100)), CapEstimate(2000), decisions, name="Repair")
        transactions = (
            Transaction(1, 1, "Bin busy", "Other", True, 100, ("Bin busy", "Other")),
            Transaction(1, 1, "Other", "Bin busy", True, 100, ("Bin busy", "Other")),
        )
        game = HistoricalGame(1, ("Bin busy", "Other"), {1: item}, transactions, {"Bin busy": 0, "Other": 0})
        dataset = HistoricalDataset(1, "dataset", "now", {1: game}, ("Bin busy", "Other"), {"schema_version": 1})
        case = CaseData(1, Path("case"), line_items=(LineItem(1, "Repair"),))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = root / "spec.json"
            spec.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "name": "smoke",
                        "games": "all",
                        "draws": 1,
                        "tracks": [],
                        "validation": {"holdout_fraction": 0.5, "walk_forward_min_train": 1},
                    }
                )
            )
            with (
                patch("backtesting.experiments.load_dataset", return_value=dataset),
                patch("backtesting.experiments._preflight_cases"),
                patch("backtesting.experiments.read_case", new=AsyncMock(return_value=case)),
                patch("backtesting.experiments.RUNS", root / "runs"),
            ):
                run_dir, result = await run_experiment(spec)

            self.assertTrue((run_dir / "report.md").exists())
            self.assertTrue((run_dir / "scores.csv").exists())
            self.assertEqual(result["scores"]["actual"]["1"]["net"]["midpoint"], 0)
            self.assertIn("merged", result["scores"])


if __name__ == "__main__":
    unittest.main()
