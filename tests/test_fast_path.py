import tempfile
import unittest
from pathlib import Path

from src.data.models import CaseData, LineItem
from src.services.strategies.fast_path import _proposal_from_evidence, build_input_content


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
        self.assertEqual(len(proposal.prices), 1)
        self.assertEqual(proposal.prices[0].index, 1)
        self.assertGreaterEqual(proposal.prices[0].charge_price, 150.0)
        self.assertGreater(proposal.prices[0].acceptance_limit, 0.0)


if __name__ == "__main__":
    unittest.main()
