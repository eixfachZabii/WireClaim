import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.data.models import CaseData, LineItem
from src.services.fraud_detection import detect_fraud


class FraudDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.case = CaseData(
            game_id=1,
            case_dir=Path(self.temp_dir.name),
            policy_text="Policy text",
            description_text="Damage text",
            line_items=(LineItem(1, "Covered repair"), LineItem(2, "Unrelated item")),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_locks_only_items_with_confirmed_violations(self) -> None:
        with patch(
            "src.services.fraud_detection._check_item",
            side_effect=(False, True),
        ):
            decision = asyncio.run(detect_fraud(self.case))

        self.assertEqual(decision.fraud_indices, frozenset({2}))

    def test_failed_check_does_not_lock_a_limit(self) -> None:
        with patch(
            "src.services.fraud_detection._check_item",
            side_effect=(RuntimeError("model unavailable"), True),
        ):
            decision = asyncio.run(detect_fraud(self.case))

        self.assertEqual(decision.fraud_indices, frozenset({2}))


if __name__ == "__main__":
    unittest.main()
