import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.data.models import CaseData, LineItem
from src.pricing import Evidence
from src.services.strategies.strategy2.strategy import (
    ENSEMBLE_PROMPTS,
    PROMPT,
    PROMPT_UNANCHORED,
    STRATEGY_NAME,
    _band_of,
    _blend,
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


class BlendTests(unittest.TestCase):
    """The ensemble: two framings of the same Case, averaged in log space."""

    def test_the_median_is_the_geometric_mean_of_the_draws(self) -> None:
        blended = _blend([{1: Evidence(1, 0.9, 80.0, 100.0, 125.0)}, {1: Evidence(1, 0.9, 320.0, 400.0, 500.0)}])

        self.assertAlmostEqual(blended[1].price_median, 200.0)

    def test_disagreement_widens_the_band(self) -> None:
        """The spread between framings is the only honest width signal we have.

        The width the model asserts has a median of 0.375 against a measured error near
        0.8, so a band that ignores the disagreement claims precision that is not there.
        """
        agreeing = _blend([{1: Evidence(1, 0.9, 90.0, 100.0, 110.0)}, {1: Evidence(1, 0.9, 90.0, 100.0, 110.0)}])
        disagreeing = _blend([{1: Evidence(1, 0.9, 90.0, 100.0, 110.0)}, {1: Evidence(1, 0.9, 900.0, 1000.0, 1100.0)}])

        self.assertAlmostEqual(agreeing[1].price_high / agreeing[1].price_low, 110.0 / 90.0, places=6)
        self.assertGreater(
            disagreeing[1].price_high / disagreeing[1].price_low,
            agreeing[1].price_high / agreeing[1].price_low,
        )

    def test_a_single_surviving_draw_is_passed_through(self) -> None:
        """One framing timing out must not cost us the model channel."""
        only = {1: Evidence(1, 0.9, 80.0, 100.0, 125.0)}

        self.assertIs(_blend([{}, only]), only)
        self.assertEqual(_blend([{}, {}]), {})

    def test_coverage_averages_over_every_draw(self) -> None:
        blended = _blend([{1: Evidence(1, 1.0, 80.0, 100.0, 125.0)}, {1: Evidence(1, 0.2, 80.0, 100.0, 125.0)}])

        self.assertAlmostEqual(blended[1].coverage_probability, 0.6)

    def test_the_two_framings_differ_only_in_the_distribution_hint(self) -> None:
        self.assertEqual(ENSEMBLE_PROMPTS, (PROMPT, PROMPT_UNANCHORED))
        self.assertIn("the median is around 59 EUR", PROMPT)
        self.assertNotIn("the median is around", PROMPT_UNANCHORED)


class BandTests(unittest.TestCase):
    def test_a_gross_total_band_is_taken_as_given(self) -> None:
        item = {"price_low": 125.0, "price_median": 100.0, "price_high": 80.0}

        self.assertEqual(_band_of(item, quantity=6.75), (80.0, 100.0, 125.0))

    def test_a_per_unit_rate_is_multiplied_by_the_printed_quantity(self) -> None:
        """"Service technician hours (6.75 hrs)" was charged 102 against a true t >= 593."""
        item = {"unit_rate_low": 60.0, "unit_rate_median": 85.0, "unit_rate_high": 110.0}

        low, median, high = _band_of(item, quantity=6.75)

        self.assertAlmostEqual(median, 573.75)
        self.assertAlmostEqual(low, 405.0)
        self.assertAlmostEqual(high, 742.5)

    def test_a_magnitude_class_above_the_number_pulls_the_band_up(self) -> None:
        item = {"price_low": 60.0, "price_median": 140.0, "price_high": 260.0, "magnitude": "low_thousands"}

        low, median, high = _band_of(item, quantity=1.0)

        self.assertGreater(median, 140.0)
        self.assertLess(median, 1000.0)
        self.assertGreaterEqual(high, 2000.0)
        self.assertLessEqual(low, median)

    def test_a_magnitude_class_never_pulls_a_band_down(self) -> None:
        item = {"price_low": 900.0, "price_median": 1500.0, "price_high": 2400.0, "magnitude": "tens"}

        self.assertEqual(_band_of(item, quantity=1.0), (900.0, 1500.0, 2400.0))


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

    def test_one_framing_failing_still_uses_the_other(self) -> None:
        """Two calls means two chances, not two ways to lose the model channel."""
        case = case_with(LineItem(1, "Drying fan"))
        calls: list[str] = []

        def flaky(_case, _timeout, prompt):
            calls.append(prompt)
            if len(calls) == 1:
                raise RuntimeError("model down")
            return {1: Evidence(1, 0.95, 80.0, 100.0, 125.0)}

        with patch(
            "src.services.strategies.strategy2.strategy._request_evidence", side_effect=flaky
        ), patch("src.price_memory.lookup", return_value=None):
            proposal = asyncio.run(propose(case))

        self.assertEqual(len(calls), 2)
        self.assertIsNotNone(proposal)
        self.assertGreater(proposal.prices[0].charge_price, 0.0)

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
