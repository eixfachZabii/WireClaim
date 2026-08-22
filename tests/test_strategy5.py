import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.data.models import CaseData, LineItem
from src.services.strategies.strategy5.config import Strategy5Config
from src.services.strategies.strategy5.invoice import (
    InvoiceDocument,
    InvoiceItem,
    extract_invoice_document,
    parse_invoice_items,
)
from src.services.strategies.strategy5.model import (
    CoverageAssessment,
    PriceRange,
    aggregate_price_ranges,
    build_coverage_input_content,
    parse_coverage_assessments,
    parse_price_ranges,
    request_price_ranges,
)
from src.services.strategies.strategy5.strategy import build_proposal, propose


class Strategy5InvoiceTests(unittest.TestCase):
    def test_deterministic_extraction_separates_description_amount_and_unit(self) -> None:
        case = CaseData(game_id=8, case_dir=Path("case_08"))
        parsed = [
            LineItem(1, "Leak detection (14 hrs)", 14.0),
            LineItem(4, "Vehicle costs", quantity_missing=True),
            LineItem(8, "Floor covering removal (82.8 m²)", 82.8),
        ]
        with patch(
            "src.services.strategies.strategy5.invoice.read_invoice_line_items",
            return_value=parsed,
        ), patch(
            "src.services.strategies.strategy5.invoice.read_invoice_text",
            return_value="invoice text",
        ):
            document = extract_invoice_document(case)

        self.assertEqual([item.index for item in document.items], [1, 4, 8])
        self.assertEqual(
            (document.items[0].description, document.items[0].amount, document.items[0].unit),
            ("Leak detection", 14.0, "hrs"),
        )
        self.assertEqual(
            (document.items[1].description, document.items[1].amount, document.items[1].unit),
            ("Vehicle costs", None, None),
        )
        self.assertEqual(
            (document.items[2].description, document.items[2].amount, document.items[2].unit),
            ("Floor covering removal", 82.8, "m²"),
        )
        self.assertEqual(document.text, "invoice text")

    def test_parser_handles_wrapping_concatenated_amounts_and_observed_units(self) -> None:
        items = parse_invoice_items(
            "INVOICE 2026\n"
            "POS. DESCRIPTION AMOUNT UNIT TOTAL\n"
            "5 Freeing the affected pipe run beneath the kitchen sink1 pcs\n"
            "8 Floor covering removal – removal of linoleum incl.\n"
            "skirting and transport to the container\n"
            "82.8 m�\n"
            "20 Electricity costs 2,412.1kWh\n"
            "22 Skilled worker hours 14 �\n"
            "Created on 2026-08-22\n"
        )

        by_index = {item.index: item for item in items}
        self.assertEqual((by_index[5].amount, by_index[5].unit), (1.0, "pcs"))
        self.assertEqual(
            by_index[8].description,
            "Floor covering removal – removal of linoleum incl. skirting and transport to the container",
        )
        self.assertEqual((by_index[8].amount, by_index[8].unit), (82.8, "m²"))
        self.assertEqual((by_index[20].amount, by_index[20].unit), (2412.1, "kWh"))
        self.assertEqual((by_index[22].amount, by_index[22].unit), (14.0, "unknown"))


class Strategy5ModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.case_dir = Path(self.temp_dir.name)
        (self.case_dir / "damage.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        self.case = CaseData(
            game_id=42,
            case_dir=self.case_dir,
            policy_text="Policy text",
            description_text="Damage text",
            line_items=(LineItem(1, "Drying fans (2 days)", 2.0),),
            image_paths=(self.case_dir / "damage.png",),
        )
        self.items = (InvoiceItem(1, "Drying fans", 2.0, "days"),)

    def test_price_parser_uses_only_deterministic_indices_and_sorts_bounds(self) -> None:
        parsed = parse_price_ranges(
            {
                "items": [
                    {
                        "index": 1,
                        "lower": 250,
                        "upper": 100,
                        "price_basis": "gross_total",
                        "anchors": ["hire quote"],
                    },
                    {
                        "index": 2,
                        "lower": 1,
                        "upper": 2,
                        "price_basis": "gross_total",
                        "anchors": [],
                    },
                ]
            },
            self.items,
        )

        self.assertEqual(set(parsed), {1})
        self.assertEqual((parsed[1].lower, parsed[1].upper), (100.0, 250.0))
        self.assertEqual(parsed[1].anchors, ("hire quote",))

    def test_price_parser_rejects_a_non_gross_range(self) -> None:
        parsed = parse_price_ranges(
            {
                "items": [
                    {
                        "index": 1,
                        "lower": 50,
                        "upper": 80,
                        "price_basis": "per_unit",
                        "anchors": ["hourly rate"],
                    }
                ]
            },
            self.items,
        )

        self.assertEqual(parsed, {})

    def test_aggregation_averages_endpoints_and_preserves_model_disagreement(self) -> None:
        aggregated = aggregate_price_ranges(
            [
                {1: PriceRange(1, 100.0, 200.0, ("anchor A",))},
                {1: PriceRange(1, 300.0, 500.0, ("anchor B",))},
            ],
            self.items,
        )[1]

        self.assertEqual(aggregated.average_lower, 200.0)
        self.assertEqual(aggregated.average_upper, 350.0)
        self.assertEqual(aggregated.model_count, 2)
        self.assertLess(aggregated.evidence_lower, aggregated.average_lower)
        self.assertGreater(aggregated.evidence_upper, aggregated.average_upper)
        self.assertEqual(aggregated.anchors, ("anchor A", "anchor B"))

    def test_coverage_input_contains_policy_description_invoice_text_photo_and_items(self) -> None:
        content = build_coverage_input_content(self.case, self.items, "raw invoice text")

        self.assertEqual([part["type"] for part in content], ["input_image", "input_text"])
        text = content[-1]["text"]
        self.assertIn("Policy text", text)
        self.assertIn("Damage text", text)
        self.assertIn("raw invoice text", text)
        self.assertIn('"amount": 2.0', text)
        self.assertIn('"unit": "days"', text)

    def test_high_violation_probability_requires_a_verbatim_exclusion(self) -> None:
        valid_clause = (
            "The insurer does not cover the cost of routine maintenance, inspection, "
            "servicing or any work unrelated to the insured damage event."
        )
        policy = f"7.2 {valid_clause}"
        parsed = parse_coverage_assessments(
            {
                "items": [
                    {
                        "index": 1,
                        "policy_violation_probability": 0.8,
                        "clause": valid_clause,
                        "reasoning": "Routine service",
                    }
                ]
            },
            self.items,
            policy,
        )
        unverified = parse_coverage_assessments(
            {
                "items": [
                    {
                        "index": 1,
                        "policy_violation_probability": 0.95,
                        "clause": "invented exclusion",
                        "reasoning": "unsupported",
                    }
                ]
            },
            self.items,
            policy,
        )

        self.assertTrue(parsed[1].quote_verified)
        self.assertEqual(parsed[1].policy_violation_probability, 0.8)
        self.assertFalse(unverified[1].quote_verified)
        self.assertEqual(unverified[1].policy_violation_probability, 0.1)

    def test_repairable_exclusion_preserves_probability_and_locks_the_limit(self) -> None:
        policy = (
            "7.1.8 The following costs are not indemnified under this Policy:\n"
            "(a) ordinary administrative expenses;\n"
            "(b) carriage, freight, delivery, dispatch, packaging, postage, courier, "
            "transport, logistics and comparable charges."
        )
        assembled = (
            "7.1.8 (b) carriage, freight, delivery, dispatch, packaging, postage, courier, "
            "transport, logistics and comparable charges."
        )
        parsed = parse_coverage_assessments(
            {
                "items": [
                    {
                        "index": 1,
                        "policy_violation_probability": 0.8,
                        "clause": assembled,
                        "reasoning": "Excluded delivery cost",
                    }
                ]
            },
            self.items,
            policy,
        )

        self.assertTrue(parsed[1].quote_verified)
        self.assertEqual(parsed[1].policy_violation_probability, 0.8)
        self.assertIn(parsed[1].clause, policy)

    def test_request_selects_the_requested_model_and_strict_schema(self) -> None:
        client = MagicMock()
        client.responses.create.return_value.output_text = (
            '{"items":[{"index":1,"lower":100,"upper":200,'
            '"price_basis":"gross_total","anchors":["quote"]}]}'
        )
        with patch(
            "src.services.strategies.strategy5.model.get_llm_client", return_value=client
        ):
            result = request_price_ranges(
                self.case,
                self.items,
                model="gpt-5.6-luna",
                timeout=12.0,
            )

        self.assertEqual(set(result), {1})
        kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-5.6-luna")
        self.assertEqual(kwargs["timeout"], 12.0)
        self.assertTrue(kwargs["text"]["format"]["strict"])
        self.assertIn("Damage text", kwargs["input"][0]["content"][-1]["text"])
        self.assertNotIn("Policy text", kwargs["input"][0]["content"][-1]["text"])


class Strategy5PricingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = CaseData(
            game_id=42,
            case_dir=Path("case_42"),
            policy_text="Policy",
            description_text="Damage",
            line_items=(LineItem(1, "Drying fans (2 days)", 2.0),),
        )
        self.document = InvoiceDocument(
            items=(InvoiceItem(1, "Drying fans", 2.0, "days"),),
            line_items=self.case.line_items,
            text="invoice text",
        )
        self.ranges = aggregate_price_ranges(
            [{1: PriceRange(1, 100.0, 200.0, ("market anchor",))}],
            self.document.items,
        )

    def test_policy_violation_zeroes_limit_but_keeps_charge(self) -> None:
        coverage = {
            1: CoverageAssessment(
                index=1,
                policy_violation_probability=0.8,
                clause="quoted exclusion",
                reasoning="excluded",
                quote_verified=True,
            )
        }
        proposal = build_proposal(
            self.case,
            self.document,
            self.ranges,
            coverage,
            Strategy5Config(),
            deterministic={},
        )

        price = proposal.by_index()[1]
        self.assertGreater(price.charge_price, 0.0)
        self.assertEqual(price.acceptance_limit, 0.0)
        self.assertNotEqual(price.charge_price, self.ranges[1].average_lower)

    def test_alpha_and_beta_factors_are_applied_after_engine_pricing(self) -> None:
        base = build_proposal(
            self.case,
            self.document,
            self.ranges,
            {},
            Strategy5Config(),
            deterministic={},
        ).by_index()[1]
        adjusted = build_proposal(
            self.case,
            self.document,
            self.ranges,
            {},
            Strategy5Config(alpha_factor=0.9, beta_factor=1.1),
            deterministic={},
        ).by_index()[1]

        self.assertAlmostEqual(adjusted.charge_price, round(base.charge_price * 0.9, 2))
        self.assertAlmostEqual(adjusted.acceptance_limit, round(base.acceptance_limit * 1.1, 2))
        self.assertLessEqual(adjusted.acceptance_limit, adjusted.charge_price)

    def test_propose_runs_three_price_models_and_coverage_concurrently(self) -> None:
        requested_models: list[str] = []

        def price_request(case, items, model, timeout):
            requested_models.append(model)
            return {1: PriceRange(1, 100.0, 200.0, (model,))}

        with patch(
            "src.services.strategies.strategy5.strategy.extract_invoice_document",
            return_value=self.document,
        ), patch(
            "src.services.strategies.strategy5.strategy.request_price_ranges",
            side_effect=price_request,
        ), patch(
            "src.services.strategies.strategy5.strategy.request_coverage_assessments",
            return_value={},
        ), patch(
            "src.services.strategies.strategy5.strategy.local_evidence",
            return_value={},
        ):
            proposal = asyncio.run(propose(self.case))

        self.assertEqual(
            set(requested_models),
            {"gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.4-mini"},
        )
        self.assertEqual(set(proposal.by_index()), {1})

    def test_near_deadline_skips_models_and_returns_complete_fallback(self) -> None:
        async def run():
            return await propose(
                self.case,
                deadline=asyncio.get_running_loop().time() + 1.0,
            )

        with patch(
            "src.services.strategies.strategy5.strategy.extract_invoice_document",
            return_value=self.document,
        ), patch(
            "src.services.strategies.strategy5.strategy.request_price_ranges"
        ) as price_request, patch(
            "src.services.strategies.strategy5.strategy.request_coverage_assessments"
        ) as coverage_request, patch(
            "src.services.strategies.strategy5.strategy.local_evidence",
            return_value={},
        ):
            proposal = asyncio.run(run())

        price_request.assert_not_called()
        coverage_request.assert_not_called()
        self.assertEqual(set(proposal.by_index()), {1})
        self.assertGreater(proposal.by_index()[1].charge_price, 0.0)

    def test_model_failures_still_return_a_complete_nonzero_proposal(self) -> None:
        with patch(
            "src.services.strategies.strategy5.strategy.extract_invoice_document",
            return_value=self.document,
        ), patch(
            "src.services.strategies.strategy5.strategy.request_price_ranges",
            side_effect=RuntimeError("model down"),
        ), patch(
            "src.services.strategies.strategy5.strategy.request_coverage_assessments",
            side_effect=RuntimeError("coverage down"),
        ), patch(
            "src.services.strategies.strategy5.strategy.local_evidence",
            return_value={},
        ):
            proposal = asyncio.run(propose(self.case))

        price = proposal.by_index()[1]
        self.assertGreater(price.charge_price, 0.0)
        self.assertGreater(price.acceptance_limit, 0.0)


if __name__ == "__main__":
    unittest.main()
