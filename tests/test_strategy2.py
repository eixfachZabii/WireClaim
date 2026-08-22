import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.data.models import CaseData, LineItem
from src.pricing import Evidence
from src.services.strategies.strategy2.strategy import (
    STRATEGY_NAME,
    _combine,
    build_proposal,
    propose,
)


def case_with(*line_items: LineItem) -> CaseData:
    return CaseData(
        game_id=42,
        case_dir=Path(tempfile.gettempdir()),
        policy_text="PART 3 - EXCLUSIONS\n3.1 Wear and tear is not covered under this policy at all.\n",
        description_text="Water damage.",
        line_items=line_items,
    )


class BuildProposalTests(unittest.TestCase):
    def test_prices_every_item_the_model_spoke_about(self) -> None:
        case = case_with(LineItem(1, "Drying fan"), LineItem(2, "Skilled worker hours"))
        model = {
            1: Evidence(1, 0.95, 80.0, 100.0, 125.0),
            2: Evidence(2, 0.95, 400.0, 500.0, 650.0),
        }

        proposal = build_proposal(case, model, {})

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.source, STRATEGY_NAME)
        prices = proposal.by_index()
        self.assertEqual(set(prices), {1, 2})
        for price in prices.values():
            self.assertGreater(price.charge_price, 0.0)
            self.assertLessEqual(price.acceptance_limit, price.charge_price)

    def test_the_charge_lands_below_the_estimate(self) -> None:
        """Income is `a` whenever a <= t and collapses ~80% above it."""
        case = case_with(LineItem(1, "Drying fan"))

        proposal = build_proposal(case, {1: Evidence(1, 1.0, 80.0, 100.0, 125.0)}, {})

        self.assertLess(proposal.prices[0].charge_price, 100.0)

    def test_a_dash_quantity_item_gets_a_zero_limit_but_still_charges(self) -> None:
        """20 of 20 such Line Items in the settled Games were worth nothing."""
        case = case_with(LineItem(1, "Vehicle costs", quantity_missing=True))

        proposal = build_proposal(case, {1: Evidence(1, 0.95, 80.0, 100.0, 125.0)}, {})

        self.assertEqual(proposal.prices[0].acceptance_limit, 0.0)
        self.assertGreater(proposal.prices[0].charge_price, 0.0)

    def test_items_nobody_priced_are_left_to_the_lower_layers(self) -> None:
        case = case_with(LineItem(1, "Drying fan"), LineItem(2, "Unknown"))

        proposal = build_proposal(case, {1: Evidence(1, 0.9, 80.0, 100.0, 125.0)}, {})

        self.assertEqual(set(proposal.by_index()), {1})

    def test_no_evidence_at_all_yields_nothing(self) -> None:
        self.assertIsNone(build_proposal(case_with(LineItem(1, "Drying fan")), {}, {}))

    def test_a_model_hallucinated_index_is_ignored(self) -> None:
        case = case_with(LineItem(1, "Drying fan"))

        proposal = build_proposal(case, {99: Evidence(99, 0.9, 80.0, 100.0, 125.0)}, {})

        self.assertIsNone(proposal)


class CombineTests(unittest.TestCase):
    def test_two_estimates_narrow_the_band(self) -> None:
        model = Evidence(1, 0.9, 50.0, 100.0, 200.0)
        memory = Evidence(1, 0.9, 60.0, 110.0, 190.0)

        combined = _combine(model, memory)

        model_width = model.price_high / model.price_low
        combined_width = combined.price_high / combined.price_low
        self.assertLess(combined_width, model_width)

    def test_the_blended_median_sits_between_the_two(self) -> None:
        combined = _combine(
            Evidence(1, 0.9, 80.0, 100.0, 125.0),
            Evidence(1, 0.9, 160.0, 200.0, 250.0),
        )

        self.assertGreater(combined.price_median, 100.0)
        self.assertLess(combined.price_median, 200.0)

    def test_memory_never_overrides_a_confirmed_worthless_item(self) -> None:
        combined = _combine(
            Evidence(1, 0.95, 80.0, 100.0, 125.0),
            Evidence(1, 0.0, 30.0, 60.0, 120.0),
        )

        self.assertEqual(combined.coverage_probability, 0.0)

    def test_coverage_comes_from_the_model_not_from_memory(self) -> None:
        """6 of 15 repeated wordings flip between t = 0 and t > 0."""
        combined = _combine(
            Evidence(1, 0.2, 80.0, 100.0, 125.0),
            Evidence(1, 0.9, 90.0, 110.0, 130.0),
        )

        self.assertAlmostEqual(combined.coverage_probability, 0.2)

    def test_either_side_alone_is_enough(self) -> None:
        only_model = Evidence(1, 0.9, 80.0, 100.0, 125.0)
        only_memory = Evidence(1, 0.9, 80.0, 100.0, 125.0)

        self.assertIs(_combine(only_model, None), only_model)
        self.assertIs(_combine(None, only_memory), only_memory)
        self.assertIsNone(_combine(None, None))


class ProposeTests(unittest.TestCase):
    def test_a_model_failure_still_produces_a_submission(self) -> None:
        """Submitting nothing is the most expensive thing we do: 139,904 over three Games."""
        case = case_with(LineItem(1, "Vehicle costs", quantity_missing=True))

        with patch(
            "src.services.strategies.strategy2.strategy._request_evidence",
            side_effect=RuntimeError("model down"),
        ):
            proposal = asyncio.run(propose(case))

        self.assertIsNotNone(proposal)
        self.assertGreater(proposal.prices[0].charge_price, 0.0)
        self.assertEqual(proposal.prices[0].acceptance_limit, 0.0)

    def test_a_model_failure_with_nothing_else_known_returns_none(self) -> None:
        case = case_with(LineItem(1, "Something never seen before"))

        with patch(
            "src.services.strategies.strategy2.strategy._request_evidence",
            side_effect=RuntimeError("model down"),
        ), patch("src.price_memory.lookup", return_value=None):
            proposal = asyncio.run(propose(case))

        self.assertIsNone(proposal)


if __name__ == "__main__":
    unittest.main()
