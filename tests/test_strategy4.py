import asyncio
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.data.models import CaseData, LineItem
from src.services.strategies.strategy4 import model
from src.services.strategies.strategy4.model import (
    FairValueEvidence,
    build_input_content,
    extract_invoice_items,
    parse_estimates,
    request_estimates,
)
from src.services.strategies.strategy4.strategy import build_proposal, propose


class Strategy4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.case_dir = Path(self.temp_dir.name)
        (self.case_dir / "invoices.pdf").write_bytes(b"%PDF-1.4")
        (self.case_dir / "damage.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (self.case_dir / "notes.txt").write_text("Additional Case evidence", encoding="utf-8")
        self.study = self.case_dir / "fair_value_study.json"
        self.study.write_text('{"games":[{"game_id":1}]}', encoding="utf-8")
        self.game_description = self.case_dir / "GAME_DESCRIPTION.md"
        self.game_description.write_text("Claim to Fame game rules", encoding="utf-8")
        self.study_patcher = patch.object(model, "FAIR_VALUE_STUDY_PATH", self.study)
        self.game_patcher = patch.object(model, "GAME_DESCRIPTION_PATH", self.game_description)
        self.study_patcher.start()
        self.game_patcher.start()
        self.addCleanup(self.study_patcher.stop)
        self.addCleanup(self.game_patcher.stop)
        self.addCleanup(self.temp_dir.cleanup)
        self.case = CaseData(
            game_id=42,
            case_dir=self.case_dir,
            policy_text="Policy coverage text",
            description_text="Damage description text",
            line_items=(LineItem(1, "Drying fan"), LineItem(3, "Skilled worker hours", 4.0)),
            image_paths=(self.case_dir / "damage.png",),
        )
        self.invoice_patcher = patch.object(
            model, "read_invoice_line_items", return_value=list(self.case.line_items)
        )
        self.invoice_patcher.start()
        self.addCleanup(self.invoice_patcher.stop)

    def test_deterministic_extraction_keeps_indices_and_count(self) -> None:
        items = extract_invoice_items(self.case)

        self.assertEqual([(item.index, item.quantity) for item in items], [(1, 1.0), (3, 4.0)])

    def test_input_attaches_complete_study_and_case_material(self) -> None:
        items = extract_invoice_items(self.case)
        content = build_input_content(self.case, items)

        self.assertEqual(
            [part["type"] for part in content],
            ["input_file", "input_file", "input_image", "input_text"],
        )
        self.assertEqual([content[0]["filename"], content[1]["filename"]], ["invoices.pdf", "fair_value_study.json"])
        study_data = content[1]["file_data"].split(",", 1)[1]
        self.assertEqual(base64.b64decode(study_data), self.study.read_bytes())
        text = content[-1]["text"]
        self.assertIn("Claim to Fame game rules", text)
        self.assertIn("Policy coverage text", text)
        self.assertIn("Damage description text", text)
        self.assertIn("Additional Case evidence", text)
        self.assertIn("line_item_count=2", text)
        self.assertIn('"index": 3', text)

    def test_parser_keeps_only_deterministic_invoice_indices_and_sorts_bounds(self) -> None:
        found = parse_estimates(
            {
                "items": [
                    {"line_item": 1, "coverage_probability": 0.95, "t_lower": 250, "t_upper": 100},
                    {"line_item": 2, "coverage_probability": 0.95, "t_lower": 1, "t_upper": 2},
                    {"line_item": 3, "t_lower": 400, "t_upper": 800, "anchors": ["trade quote"]},
                ]
            },
            self.case.line_items,
        )

        self.assertEqual(set(found), {1, 3})
        self.assertEqual((found[1].t_lower, found[1].t_upper), (100.0, 250.0))
        self.assertEqual(found[3].coverage_probability, 0.9)
        self.assertEqual(found[3].anchors, ("trade quote",))

    def test_bounds_are_priced_by_the_engine_not_submitted_directly(self) -> None:
        proposal = build_proposal(
            self.case,
            {1: FairValueEvidence(1, 0.95, 100.0, 200.0)},
            deterministic={},
        )

        self.assertIsNotNone(proposal)
        prices = proposal.by_index()
        self.assertEqual(set(prices), {1, 3})
        self.assertLess(prices[1].charge_price, 200.0**0.5 * 100.0**0.5)
        self.assertLessEqual(prices[1].acceptance_limit, prices[1].charge_price)
        self.assertNotEqual(prices[1].acceptance_limit, 200.0)
        self.assertGreater(prices[3].charge_price, 0.0)
        self.assertGreater(prices[3].acceptance_limit, 0.0)

    def test_zero_fair_value_evidence_locks_the_limit_but_keeps_a_charge(self) -> None:
        proposal = build_proposal(
            self.case,
            {1: FairValueEvidence(1, 0.0, 0.0, 0.0)},
            deterministic={},
        )

        price = proposal.by_index()[1]
        self.assertGreater(price.charge_price, 0.0)
        self.assertEqual(price.acceptance_limit, 0.0)

    def test_request_uses_a_system_prompt_and_one_response_call(self) -> None:
        client = MagicMock()
        client.responses.create.return_value.output_text = (
            '{"items":[{"line_item":1,"coverage_probability":0.95,"t_lower":100,"t_upper":200}]}'
        )
        with patch.object(model, "get_llm_client", return_value=client):
            found = request_estimates(self.case, extract_invoice_items(self.case), timeout=12.0)

        self.assertEqual(set(found), {1})
        kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["timeout"], 12.0)
        self.assertIn("deterministic pricing engine", kwargs["instructions"])
        self.assertEqual(len(kwargs["input"]), 1)

    def test_model_failure_still_produces_complete_proposal(self) -> None:
        with patch(
            "src.services.strategies.strategy4.strategy.request_estimates",
            side_effect=RuntimeError("model down"),
        ), patch(
            "src.services.strategies.strategy4.strategy.local_evidence",
            return_value={},
        ):
            proposal = asyncio.run(propose(self.case))

        self.assertIsNotNone(proposal)
        self.assertEqual(set(proposal.by_index()), {1, 3})
        for price in proposal.prices:
            self.assertGreater(price.charge_price, 0.0)
            self.assertGreater(price.acceptance_limit, 0.0)


if __name__ == "__main__":
    unittest.main()
