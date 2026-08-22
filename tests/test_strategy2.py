import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.data.models import CaseData, LineItem
from src.pricing.engine import Evidence, price_item
from src.strategies.strategy2.blend import blend as _blend, combine as _combine
from src.strategies.strategy2.channels import aggregate_class_discount
from src.strategies.strategy2.constants import (
    LLM_TIMEOUT_SECONDS,
    SETTLED_MEDIAN,
    STRATEGY_NAME,
    SUBMISSION_RESERVE_SECONDS,
)
from src.strategies.strategy2.model import parse_items
from src.strategies.strategy2.prompts import (
    ENSEMBLE_PROMPTS,
    PROMPT,
    PROMPT_UNANCHORED,
)
from src.strategies.strategy2.strategy import build_proposal, propose


def case_with(*line_items: LineItem) -> CaseData:
    return CaseData(
        # 9042, not 42. A real Game id here means `build_proposal` -> `decisions.record()`
        # writes into `var/decisions/game_042.json` on every `pixi run test`, quietly
        # overwriting a settled Game's record with two fixture items. That is how Game 42's
        # log came to say `no-decision-log` for sixteen of the seventeen Line Items it had
        # actually priced, and it sent an hour of diagnosis after a pipeline failure that
        # never happened. `var/decisions/` is tracked now, so it also dirtied the tree on
        # every test run. Ids above 100 cannot collide with a Game.
        game_id=9042,
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

    def test_an_item_no_channel_priced_still_gets_a_number(self) -> None:
        """Strategy 2 owns the whole Case or it hands it to a worse track silently.

        This used to leave the index out, which is how Game 23 ended up submitting
        Strategy 1's flat Limit of 35 and paying 5,548 in wrongful-rejection penalties.
        """
        case = case_with(LineItem(1, "Drying fan"), LineItem(2, "Unknown"))

        proposal = build_proposal(case, {1: Evidence(1, 0.9, 80.0, 100.0, 125.0)}, {})

        self.assertEqual(set(proposal.by_index()), {1, 2})
        unpriced = proposal.by_index()[2]
        self.assertGreater(unpriced.charge_price, 0.0)
        self.assertGreater(unpriced.acceptance_limit, 0.0)

    def test_no_evidence_at_all_still_prices_the_case(self) -> None:
        proposal = build_proposal(case_with(LineItem(1, "Drying fan")), {}, {})

        self.assertIsNotNone(proposal)
        self.assertEqual(set(proposal.by_index()), {1})

    def test_a_case_with_no_line_items_yields_nothing(self) -> None:
        self.assertIsNone(build_proposal(case_with(), {}, {}))

    def test_a_model_hallucinated_index_is_ignored(self) -> None:
        """A model inventing Line Item 99 must not inject one, but item 1 is still priced."""
        case = case_with(LineItem(1, "Drying fan"))

        proposal = build_proposal(case, {99: Evidence(99, 0.9, 80.0, 100.0, 125.0)}, {})

        self.assertEqual(set(proposal.by_index()), {1})


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

    def test_a_zero_model_band_keeps_the_memory_anchor(self) -> None:
        """The model zeroes the band on items it judges uncovered, and that used to throw
        the anchor away: Game 31 item 17 had an exact memory hit at 300 and was Charged
        39.62 (`FALLBACK_MEDIAN`) against a Fair Value of at least 315."""
        combined = _combine(
            Evidence(1, 0.3, 0.0, 0.0, 0.0),
            Evidence(1, 0.9, 195.0, 300.0, 461.0),
        )

        self.assertEqual(combined.price_median, 300.0)
        # The coverage verdict is still the model's, so the Limit collapses as before.
        self.assertAlmostEqual(combined.coverage_probability, 0.3)

    def test_a_zero_model_band_with_no_anchor_is_left_alone(self) -> None:
        only_model = Evidence(1, 0.3, 0.0, 0.0, 0.0)

        self.assertIs(_combine(only_model, Evidence(1, 0.9, 0.0, 0.0, 0.0)), only_model)

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
        # Assert the invariant, not the figure. This test used to pin the literal string
        # "the median is around 59 EUR", which is how a statistic measured over 148 Line
        # Items stayed in the prompt unchallenged until Game 41, by which point the true
        # median over 457 Line Items was 97 and every number in the hint was low.
        self.assertIn(f"median {SETTLED_MEDIAN:.0f} EUR", PROMPT)
        self.assertIn("settled distribution", PROMPT)
        self.assertNotIn("settled distribution", PROMPT_UNANCHORED)


class UncorrectedLevelTests(unittest.TestCase):
    """The blend must not shift the level, in either direction. Both were measured.

    The estimator looks shrunk toward the middle -- bucketed by the true Fair Value, median
    `t_hat / t` is 6.01 under 50 EUR against 1.17 over 1,000 -- and every deterministic
    repair of that has been scored in euros against the real Field over Games 1-24 and lost:
    the euro-weighted fit `exp(0.889) * t_hat**0.849` costs 54,713 in-sample and up to
    183,048 held out, and the whole `exp(c0) * t_hat**c1` family has its argmax at `c1 = 1`,
    which is this behaviour. See `scripts/experiments/level_fit.py` for the tables.

    So the identity is a *decision*, not an omission, and it needs a test -- otherwise the
    next reader of the by-true-`t` table adds a multiplier, and the multiplier looks obviously
    right until it is replayed.
    """

    def test_a_single_draw_is_returned_at_the_level_the_model_stated(self) -> None:
        stated = Evidence(1, 0.9, 80.0, 100.0, 125.0)

        self.assertEqual(_blend([{1: stated}])[1].price_median, 100.0)

    def test_agreeing_draws_keep_the_level_they_agree_on(self) -> None:
        """No shrinking toward `SETTLED_MEDIAN`, and no un-shrinking away from it either."""
        for median in (8.0, 59.0, 400.0, 7000.0):
            blended = _blend(
                [
                    {1: Evidence(1, 0.9, median * 0.8, median, median * 1.25)},
                    {1: Evidence(1, 0.9, median * 0.8, median, median * 1.25)},
                ]
            )

            self.assertAlmostEqual(blended[1].price_median, median, places=6)

    def test_the_charge_scales_linearly_with_the_stated_median(self) -> None:
        """A level correction of any shape would break proportionality somewhere."""
        case = case_with(LineItem(1, "Leak detection call-out"))
        charges = []
        for median in (20.0, 200.0, 2000.0):
            proposal = build_proposal(
                case, {1: Evidence(1, 0.95, median * 0.8, median, median * 1.25)}, {}
            )
            charges.append(proposal.prices[0].charge_price)

        # `delta` rather than `places`: the Charge is rounded to the cent, so a 15.79 EUR
        # Charge cannot be exactly a tenth of a 157.90 one.
        self.assertAlmostEqual(charges[1] / charges[0], 10.0, delta=0.01)
        self.assertAlmostEqual(charges[2] / charges[1], 10.0, delta=0.01)


class ParseItemsTests(unittest.TestCase):
    """The parser reads the price fields and nothing else, on purpose.

    Two richer schemas were measured and both lost money badly: a per-unit rate multiplied
    by the invoice quantity scored -64,590, and an order-of-magnitude class that could pull
    the band upward scored -127,312 across nineteen Cases. Neither is kept even as dead
    code, so a model that volunteers such a field cannot silently re-enable a known loss.
    """

    def test_a_price_band_is_sorted_and_taken_as_given(self) -> None:
        payload = {"items": [{"line_item": 1, "coverage_probability": 0.9,
                              "price_low": 125.0, "price_median": 100.0, "price_high": 80.0}]}

        found = parse_items(payload)

        self.assertEqual(
            (found[1].price_low, found[1].price_median, found[1].price_high),
            (80.0, 100.0, 125.0),
        )

    def test_a_volunteered_rate_or_magnitude_is_ignored(self) -> None:
        payload = {"items": [{"line_item": 1, "coverage_probability": 0.9,
                              "price_low": 60.0, "price_median": 140.0, "price_high": 260.0,
                              "unit_rate_median": 85.0, "magnitude": "low_thousands"}]}

        found = parse_items(payload)

        self.assertEqual(found[1].price_median, 140.0)
        self.assertEqual(found[1].price_high, 260.0)

    def test_the_index_is_the_printed_pos_number(self) -> None:
        """Case 11's invoice has no POS 12 and the settled Game has no index 12."""
        payload = {"items": [{"line_item": 13, "coverage_probability": 0.9,
                              "price_low": 1.0, "price_median": 2.0, "price_high": 3.0}]}

        self.assertEqual(list(parse_items(payload)), [13])

    def test_a_malformed_entry_does_not_cost_the_others(self) -> None:
        payload = {"items": ["nonsense", {"line_item": 0}, {"line_item": 2,
                   "coverage_probability": 0.5, "price_low": 1.0,
                   "price_median": 2.0, "price_high": 3.0}]}

        self.assertEqual(list(parse_items(payload)), [2])

    def test_a_missing_items_list_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            parse_items({"nope": []})


class ProposeTests(unittest.TestCase):
    def test_strategy2_allows_a_55_second_request_window(self) -> None:
        self.assertEqual(LLM_TIMEOUT_SECONDS, 55.0)
        self.assertEqual(SUBMISSION_RESERVE_SECONDS, 3.0)

    def test_a_model_failure_still_produces_a_submission(self) -> None:
        """Submitting nothing is the most expensive thing we do: 139,904 over three Games."""
        case = case_with(LineItem(1, "Vehicle costs", quantity_missing=True))

        with patch(
            "src.strategies.strategy2.strategy.request_evidence",
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
            "src.strategies.strategy2.strategy.request_evidence", side_effect=flaky
        ), patch("src.evidence.memory.lookup", return_value=None):
            proposal = asyncio.run(propose(case))

        self.assertEqual(len(calls), 2)
        self.assertIsNotNone(proposal)
        self.assertGreater(proposal.prices[0].charge_price, 0.0)

    def test_a_model_failure_with_nothing_else_known_still_prices_every_item(self) -> None:
        """Strategy 2 must never go silent.

        Game 23 submitted a Limit of 35 on every Line Item because this path returned None:
        Channel C produced nothing, the Case had no dash items and no Price Memory hits, so
        Strategy 1's Proposal stood and we paid 5,548 in wrongful-rejection penalties.
        Abstaining hands the Submission to a worse track without saying so.
        """
        case = case_with(LineItem(1, "Something never seen before"), LineItem(2, "Nor this"))

        with patch(
            "src.strategies.strategy2.strategy.request_evidence",
            side_effect=RuntimeError("model down"),
        ), patch("src.evidence.memory.lookup", return_value=None):
            proposal = asyncio.run(propose(case))

        self.assertIsNotNone(proposal)
        self.assertEqual(set(proposal.by_index()), {1, 2})
        for price in proposal.prices:
            self.assertGreater(price.charge_price, 0.0)
            self.assertGreater(price.acceptance_limit, 0.0)
            self.assertEqual(price.source, STRATEGY_NAME)


if __name__ == "__main__":
    unittest.main()


class AggregateClassSubLimit(unittest.TestCase):
    """Channel D: two valuables in one Case share one pot, so only the dearest keeps cover.

    Game 44 is the whole case for it -- watch `t >= 9,361` paid, ring `t < 884` and necklace
    `t < 663` both zero, and the model gave all three an identical coverage of 0.925.
    """

    def _case(self, *names: str) -> CaseData:
        return CaseData(
            game_id=99,
            case_dir=None,
            policy_text="",
            description_text="",
            line_items=tuple(LineItem(i, n) for i, n in enumerate(names, start=1)),
            image_paths=(),
        )

    def _evidence(self, *medians: float) -> dict[int, Evidence]:
        return {
            i: Evidence(index=i, coverage_probability=0.925, price_low=m * 0.5,
                        price_median=m, price_high=m * 2.0)
            for i, m in enumerate(medians, start=1)
        }

    def test_only_the_dearest_member_keeps_its_coverage(self) -> None:
        case = self._case("Compensation for stolen watch", "Compensation for stolen ring")
        out = aggregate_class_discount(case, self._evidence(6800.0, 2300.0))

        self.assertEqual(out[1].coverage_probability, 0.925)
        self.assertLess(out[2].coverage_probability, 1 / 3)

    def test_it_moves_the_limit_and_never_the_charge(self) -> None:
        """An uncovered item is worth `t = 0`, so a rejected Charge on it costs nothing
        (R6c). Only the Limit should collapse."""
        case = self._case("Compensation for stolen watch", "Compensation for stolen ring")
        evidence = self._evidence(6800.0, 2300.0)
        out = aggregate_class_discount(case, evidence)

        self.assertEqual(price_item(out[2]).charge, price_item(evidence[2]).charge)
        self.assertEqual(price_item(out[2]).limit, 0.0)

    def test_a_single_valuables_item_is_untouched(self) -> None:
        """The safety case. 43 of 44 settled Cases have at most one valuables item."""
        case = self._case("Compensation for stolen watch", "Replace kitchen worktop")
        evidence = self._evidence(6800.0, 2300.0)

        self.assertEqual(aggregate_class_discount(case, evidence), evidence)

    def test_a_case_with_no_valuables_at_all_is_untouched(self) -> None:
        case = self._case("Skilled worker hours", "Replace kitchen worktop")
        evidence = self._evidence(400.0, 2300.0)

        self.assertEqual(aggregate_class_discount(case, evidence), evidence)
