import json
import tempfile
import unittest
from pathlib import Path

from backtesting.reporting import render_markdown, write_report


class BacktestingReportingTests(unittest.TestCase):
    def setUp(self) -> None:
        triple = {"lower": 1.0, "midpoint": 2.0, "upper": 3.0}
        self.result = {
            "manifest": {
                "name": "test",
                "run_id": "run-1",
                "dataset_id": "data-1",
                "dataset_schema": 1,
                "git_revision": "abc",
                "cap_mode": "fitted",
                "games": [1],
                "draws": 3,
            },
            "scores": {
                "candidate": {
                    "1": {"income": triple, "cost": triple, "net": triple}
                }
            },
            "per_item": [{"strategy": "candidate", "game_id": 1, "line_item_index": 1}],
            "tracks": {},
            "sweeps": {},
            "diagnostics": {
                "dataset": {
                    "transactions": 1,
                    "team_decisions": 1,
                    "exact_charge_share": 1.0,
                    "bounded_limit_share": 1.0,
                    "bounded_fair_value_share": 1.0,
                    "charge_statuses": {"exact": 1},
                    "cap_statuses": {"fitted": 1},
                }
            },
        }

    def test_markdown_contains_provenance_scores_and_caveats(self) -> None:
        report = render_markdown(self.result)
        self.assertIn("Dataset: `data-1`", report)
        self.assertIn("candidate", report)
        self.assertIn("identified-set envelopes", report)

    def test_writes_all_primary_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_report(root, self.result)
            names = {path.name for path in root.iterdir()}
            loaded = json.loads((root / "scores.json").read_text())
        self.assertTrue({"scores.json", "scores.csv", "per_item.csv", "report.md"} <= names)
        self.assertEqual(loaded["manifest"]["run_id"], "run-1")


if __name__ == "__main__":
    unittest.main()
