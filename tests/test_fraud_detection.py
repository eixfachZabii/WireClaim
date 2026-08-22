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
        exclusion = (
            "Damage caused by storm surge is not covered under this section of the policy."
        )
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
            f'"exclusion_quote":"{exclusion}",'
            '"reasoning":"quoted policy exclusion"}'
        )
        with patch("src.services.fraud_detection.get_llm_client", return_value=client):
            locked = _check_item(case.line_items[0], case)

        self.assertTrue(locked)

    def test_generic_policy_phrase_does_not_lock_a_limit(self) -> None:
        """A verbatim quote that proves nothing must not zero a Limit.

        This is the Game 10 regression: the gate only checked that the quote was a
        12-character substring of a ~63,000 character Policy, so boilerplate like
        "the schedule" passed. Every Line Item got flagged and the wrongful-rejection
        penalties came to 65,806.
        """
        boilerplate = (
            "The policyholder shall be indemnified in accordance with the schedule of cover "
            "set out in this document."
        )
        case = CaseData(
            game_id=self.case.game_id,
            case_dir=self.case.case_dir,
            policy_text=boilerplate,
            description_text=self.case.description_text,
            line_items=self.case.line_items,
        )
        client = MagicMock()
        client.chat.completions.create.return_value.choices[0].message.content = (
            '{"covered":false,"related":true,"confidence":0.99,'
            f'"exclusion_quote":"{boilerplate}",'
            '"reasoning":"cherry-picked boilerplate"}'
        )
        with patch("src.services.fraud_detection.get_llm_client", return_value=client):
            locked = _check_item(case.line_items[0], case)

        self.assertFalse(locked)

    def _case_with(self, item_count: int) -> CaseData:
        return CaseData(
            game_id=self.case.game_id,
            case_dir=self.case.case_dir,
            policy_text=self.case.policy_text,
            description_text=self.case.description_text,
            line_items=tuple(
                LineItem(index, f"Item {index}") for index in range(1, item_count + 1)
            ),
        )

    def test_flagging_every_item_of_a_larger_case_discards_the_verdict(self) -> None:
        case = self._case_with(4)
        with patch("src.services.fraud_detection._check_item", return_value=True):
            decision = asyncio.run(detect_fraud(case))

        self.assertEqual(decision.fraud_indices, frozenset())

    def test_flagging_every_item_of_a_two_item_case_is_kept(self) -> None:
        """Game 3 was genuinely uncovered end to end, so 2-of-2 must survive."""
        case = self._case_with(2)
        with patch("src.services.fraud_detection._check_item", return_value=True):
            decision = asyncio.run(detect_fraud(case))

        self.assertEqual(decision.fraud_indices, frozenset({1, 2}))

    def test_partial_flagging_of_a_four_item_case_survives(self) -> None:
        """Two genuine exclusions out of four must not be discarded as implausible."""
        case = self._case_with(4)
        with patch(
            "src.services.fraud_detection._check_item",
            side_effect=(False, True, True, False),
        ):
            decision = asyncio.run(detect_fraud(case))

        self.assertEqual(decision.fraud_indices, frozenset({2, 3}))

    def test_failed_check_does_not_lock_a_limit(self) -> None:
        with patch(
            "src.services.fraud_detection._check_item",
            side_effect=(RuntimeError("model unavailable"), True),
        ):
            decision = asyncio.run(detect_fraud(self.case))

        self.assertEqual(decision.fraud_indices, frozenset({2}))


if __name__ == "__main__":
    unittest.main()
