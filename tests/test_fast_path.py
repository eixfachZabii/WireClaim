import tempfile
import unittest
from pathlib import Path

from src.data.models import CaseData, LineItem
from src.strategies.fast_path import (
    LLM_TIMEOUT_SECONDS,
    STANDARD_LIMIT,
    _proposal_from_evidence,
    build_input_content,
)


class FastPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.case_dir = Path(self.temp_dir.name)
        (self.case_dir / "invoices.pdf").write_bytes(b"%PDF-1.4")
        (self.case_dir / "damage.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (self.case_dir / "notes.txt").write_text("Additional case notes", encoding="utf-8")
        self.case = CaseData(
            game_id=1,
            case_dir=self.case_dir,
            policy_text="Policy coverage text",
            description_text="Damage description text",
            line_items=(LineItem(1, "Repair"), LineItem(2, "Replacement")),
            image_paths=(self.case_dir / "damage.png",),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_fast_path_allows_a_55_second_request_window(self) -> None:
        self.assertEqual(LLM_TIMEOUT_SECONDS, 55.0)

    def test_input_contains_game_description_and_complete_case_material(self) -> None:
        content = build_input_content(self.case)

        self.assertEqual([part["type"] for part in content], ["input_file", "input_image", "input_text"])
        self.assertEqual(content[0]["filename"], "invoices.pdf")
        self.assertIn("Claim to Fame", content[2]["text"])
        self.assertIn("Policy coverage text", content[2]["text"])
        self.assertIn("Damage description text", content[2]["text"])
        self.assertIn("Additional case notes", content[2]["text"])

    def test_evidence_is_deterministically_converted_to_fast_path_prices(self) -> None:
        proposal = _proposal_from_evidence(
            self.case,
            {
                "items": [
                    {
                        "line_item": 1,
                        "coverage_probability": 0.9,
                        "relatedness_probability": 0.9,
                        "quantity": 1,
                        "price_low": 200.0,
                        "price_high": 300.0,
                        "anchors": ["hourly rate"],
                    }
                ]
            },
        )

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.source, "fast_path_llm")
        self.assertEqual(len(proposal.prices), 2)
        prices = {price.index: price for price in proposal.prices}
        self.assertGreaterEqual(prices[1].charge_price, 150.0)
        self.assertGreater(prices[1].acceptance_limit, 0.0)
        self.assertEqual((prices[2].charge_price, prices[2].acceptance_limit), (150.0, STANDARD_LIMIT))

    def test_scope_exclusions_zero_fast_path_limits_and_other_limits_are_capped(self) -> None:
        case = CaseData(
            game_id=self.case.game_id,
            case_dir=self.case_dir,
            policy_text=(
                "This is not an insurance of the movable belongings of people who live there, "
                "and it is not an insurance of any form of transport used by them."
            ),
            description_text=self.case.description_text,
            line_items=(
                LineItem(1, "Clothing stolen from a car"),
                LineItem(2, "Vehicle costs"),
                LineItem(3, "Repair to a building wall"),
            ),
            image_paths=self.case.image_paths,
        )
        proposal = _proposal_from_evidence(
            case,
            {
                "items": [
                    {
                        "line_item": index,
                        "coverage_probability": 0.9,
                        "relatedness_probability": 0.9,
                        "quantity": 1,
                        "price_low": 1000.0,
                        "price_high": 2000.0,
                        "anchors": ["estimate"],
                    }
                    for index in range(1, 4)
                ]
            },
        )

        self.assertIsNotNone(proposal)
        prices = {price.index: price for price in proposal.prices}
        self.assertEqual(prices[1].acceptance_limit, 0.0)
        self.assertEqual(prices[2].acceptance_limit, 0.0)
        self.assertEqual(prices[3].acceptance_limit, STANDARD_LIMIT)


if __name__ == "__main__":
    unittest.main()
