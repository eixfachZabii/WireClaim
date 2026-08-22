import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.data.models import CaseData, LineItem
from src.services.fraud_detection import _check_item, detect_fraud


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

    def test_unquoted_violation_does_not_lock_a_limit(self) -> None:
        client = MagicMock()
        client.chat.completions.create.return_value.choices[0].message.content = (
            '{"covered":false,"related":true,"confidence":0.99,'
            '"exclusion_quote":"","reasoning":"suspicious description"}'
        )
        with patch("src.services.fraud_detection.get_llm_client", return_value=client):
            locked = _check_item(self.case.line_items[0], self.case)

        self.assertFalse(locked)

    def test_quoted_high_confidence_violation_locks_the_limit(self) -> None:
        exclusion = "Losses caused by excluded events are not covered."
        case = CaseData(
            game_id=self.case.game_id,
            case_dir=self.case.case_dir,
            policy_text=exclusion,
            description_text=self.case.description_text,
            line_items=self.case.line_items,
        )
        client = MagicMock()
        client.chat.completions.create.return_value.choices[0].message.content = (
            '{"covered":false,"related":true,"confidence":0.99,'
            '"exclusion_quote":"Losses caused by excluded events are not covered.",'
            '"reasoning":"quoted policy exclusion"}'
        )
        with patch("src.services.fraud_detection.get_llm_client", return_value=client):
            locked = _check_item(case.line_items[0], case)

        self.assertTrue(locked)

    def test_failed_check_does_not_lock_a_limit(self) -> None:
        with patch(
            "src.services.fraud_detection._check_item",
            side_effect=(RuntimeError("model unavailable"), True),
        ):
            decision = asyncio.run(detect_fraud(self.case))

        self.assertEqual(decision.fraud_indices, frozenset({2}))


if __name__ == "__main__":
    unittest.main()
