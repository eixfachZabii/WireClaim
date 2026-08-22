import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.data.models import CaseData, LineItem
from src.services.strategies.strategy1.strategy import (
    Evidence,
    _request_evidence,
    build_input_content,
    estimate_fair_values,
    proposal_from_estimates,
    propose,
)


class Strategy1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.case_dir = Path(self.temp_dir.name)
        (self.case_dir / "invoices.pdf").write_bytes(b"%PDF-1.4")
        (self.case_dir / "damage-photo.jpeg").write_bytes(b"\xff\xd8\xff\xd9")
        (self.case_dir / "notes.txt").write_text("Additional assessor notes", encoding="utf-8")
        self.case = CaseData(
            game_id=1,
            case_dir=self.case_dir,
            policy_text="Policy coverage text",
            description_text="Damage description text",
            line_items=(LineItem(1, "Repair"), LineItem(2, "Replacement")),
            image_paths=(self.case_dir / "damage-photo.jpeg",),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_input_contains_invoice_images_and_all_text_documents(self) -> None:
        content = build_input_content(self.case)

        self.assertEqual([part["type"] for part in content], ["input_file", "input_image", "input_text"])
        self.assertEqual(content[0]["filename"], "invoices.pdf")
        self.assertTrue(content[1]["image_url"].startswith("data:image/jpeg;base64,"))
        self.assertIn("Policy coverage text", content[2]["text"])
        self.assertIn("Damage description text", content[2]["text"])
        self.assertIn("Additional assessor notes", content[2]["text"])

    def test_estimates_produce_deterministic_prices_and_skip_unknown_indices(self) -> None:
        estimates = estimate_fair_values(
            self.case,
            (
                Evidence(1, 0.9, 0.9, 100.0, 200.0),
                Evidence(2, 0.1, 1.0, 100.0, 200.0),
                Evidence(3, 1.0, 1.0, 100.0, 200.0),
            ),
        )
        proposal = proposal_from_estimates(estimates)

        self.assertIsNotNone(proposal)
        prices = {price.index: price for price in proposal.prices}
        self.assertEqual(set(prices), {1, 2})
        self.assertGreater(prices[1].acceptance_limit, 0.0)
        self.assertGreater(prices[2].acceptance_limit, 0.0)
        self.assertGreaterEqual(prices[1].charge_price, 150.0)
        self.assertGreaterEqual(prices[2].charge_price, 150.0)

    def test_unquoted_doubt_defaults_to_covered_with_positive_limit(self) -> None:
        estimates = estimate_fair_values(
            self.case,
            (Evidence(1, 0.1, 0.1, 100.0, 200.0),),
        )
        proposal = proposal_from_estimates(estimates)

        self.assertIsNotNone(proposal)
        self.assertGreater(proposal.prices[0].acceptance_limit, 0.0)

    def test_quoted_exclusion_sets_limit_to_zero_but_keeps_plausible_charge(self) -> None:
        exclusion = "Losses caused by excluded events are not covered."
        case = CaseData(
            game_id=self.case.game_id,
            case_dir=self.case.case_dir,
            policy_text=exclusion,
            description_text=self.case.description_text,
            line_items=self.case.line_items,
            image_paths=self.case.image_paths,
        )
        estimates = estimate_fair_values(
            case,
            (
                Evidence(
                    index=1,
                    coverage_probability=0.1,
                    relatedness_probability=1.0,
                    price_low=400.0,
                    price_high=500.0,
                    exclusion_quote=exclusion,
                ),
            ),
        )
        proposal = proposal_from_estimates(estimates)

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.prices[0].acceptance_limit, 0.0)
        self.assertEqual(proposal.prices[0].charge_price, 315.0)

    def test_missing_price_band_uses_quantity_scaled_fallback(self) -> None:
        estimates = estimate_fair_values(
            self.case,
            (
                Evidence(
                    index=1,
                    coverage_probability=0.9,
                    relatedness_probability=0.9,
                    price_low=0.0,
                    price_high=0.0,
                    quantity=3.0,
                ),
            ),
        )
        proposal = proposal_from_estimates(estimates)

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.prices[0].charge_price, 450.0)
        self.assertGreater(proposal.prices[0].acceptance_limit, 0.0)

    def test_model_evidence_preserves_clauses_and_named_anchors(self) -> None:
        client = MagicMock()
        client.responses.create.return_value.output_text = (
            '{"items":[{"line_item":1,"coverage_probability":0.8,'
            '"coverage_clause":"Policy section 4",'
            '"relatedness_probability":0.9,"quantity":2,"unit":"hours",'
            '"trade":"plumbing","price_low":120,"price_high":180,'
            '"anchors":["60 EUR per hour","two hour repair"]}]}'
        )
        with patch(
            "src.services.strategies.strategy1.strategy.get_llm_client",
            return_value=client,
        ):
            evidence = _request_evidence(self.case)

        self.assertEqual(evidence[0].coverage_clause, "Policy section 4")
        self.assertEqual(evidence[0].quantity, 2.0)
        self.assertEqual(evidence[0].trade, "plumbing")
        self.assertEqual(evidence[0].anchors, ("60 EUR per hour", "two hour repair"))
        content = client.responses.create.call_args.kwargs["input"][0]["content"]
        self.assertEqual([part["type"] for part in content], ["input_file", "input_image", "input_text"])

    def test_propose_runs_the_strategy_local_estimator(self) -> None:
        evidence = (Evidence(1, 1.0, 1.0, 300.0, 400.0),)
        with patch(
            "src.services.strategies.strategy1.strategy._request_evidence",
            return_value=evidence,
        ):
            proposal = asyncio.run(propose(self.case))

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.source, "strategy1")
        self.assertEqual(proposal.prices[0].index, 1)


if __name__ == "__main__":
    unittest.main()
