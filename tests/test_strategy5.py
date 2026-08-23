import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.data.models import CaseData, ItemPrice, LineItem, Proposal
from src.pricing.engine import Evidence
from src.runtime import decisions as decision_log
from src.strategies.strategy5.constants import (
    BIG_ITEM_FACTOR,
    BIG_ITEM_THRESHOLD,
    FAIR_VALUE_FACTOR,
    LOW_VALUE_FACTOR,
    LOW_VALUE_THRESHOLD,
    MID_VALUE_FACTOR,
    MID_VALUE_THRESHOLD,
    PRIMARY_UNINFORMED_FAIR_VALUE,
    STRATEGY_NAME,
    UNINFORMED_FAIR_VALUE,
)
from src.strategies.strategy5.strategy import (
    price_evidence,
    proposal_from_decisions,
    propose,
)


def band(median: float = 100.0, sigma: float = 0.5, coverage: float = 1.0) -> Evidence:
    spread = math.exp(1.645 * sigma)
    return Evidence(1, coverage, median / spread, median, median * spread)


def payload() -> dict:
    evidence = band()
    return {
        "schema": 2,
        "game_id": 7,
        "strategy": "strategy2",
        "items": [
            {
                "index": 1,
                "coverage_probability": evidence.coverage_probability,
                "price_low": evidence.price_low,
                "price_median": evidence.price_median,
                "price_high": evidence.price_high,
                "charge": 62.5,
                "limit": 45.0,
            }
        ],
    }


class CoherentFairValuePolicyTests(unittest.TestCase):
    def test_ordinary_item_uses_one_shaded_fair_value_estimate(self) -> None:
        evidence = band(median=1_000)
        charge, limit = price_evidence(evidence)

        self.assertEqual(charge, round(FAIR_VALUE_FACTOR * evidence.price_median, 2))
        self.assertEqual(limit, charge)

    def test_small_and_mid_value_tiers_are_coherent(self) -> None:
        for median, factor in (
            (LOW_VALUE_THRESHOLD - 1, LOW_VALUE_FACTOR),
            (LOW_VALUE_THRESHOLD, MID_VALUE_FACTOR),
            (MID_VALUE_THRESHOLD - 1, MID_VALUE_FACTOR),
        ):
            charge, limit = price_evidence(band(median=median))
            self.assertEqual(charge, round(factor * median, 2))
            self.assertEqual(limit, charge)

    def test_uninformed_path_uses_a_nonzero_shared_prior(self) -> None:
        self.assertEqual(
            price_evidence(band(), uninformed=True),
            (UNINFORMED_FAIR_VALUE, UNINFORMED_FAIR_VALUE),
        )

    def test_primary_uninformed_path_uses_capital_loss_prior(self) -> None:
        self.assertEqual(
            price_evidence(band(), uninformed=True, primary_uninformed=True),
            (PRIMARY_UNINFORMED_FAIR_VALUE, PRIMARY_UNINFORMED_FAIR_VALUE),
        )

    def test_confirmed_exclusion_wins_over_uninformed_primary_tier(self) -> None:
        self.assertEqual(
            price_evidence(
                band(),
                confirmed_uncovered=True,
                uninformed=True,
                primary_uninformed=True,
            ),
            (0.0, 0.0),
        )

    def test_large_item_uses_strategy2_inspired_tail_factor(self) -> None:
        evidence = band(median=BIG_ITEM_THRESHOLD)
        charge, limit = price_evidence(evidence)

        self.assertEqual(charge, round(BIG_ITEM_FACTOR * BIG_ITEM_THRESHOLD, 2))
        self.assertEqual(limit, charge)

    def test_charge_never_exceeds_limit_across_coverage_and_band_widths(self) -> None:
        for coverage in (0.0, 0.2, 0.5, 2.0 / 3.0, 0.9, 1.0):
            for sigma in (0.05, 0.25, 0.5, 1.0, 2.0):
                charge, limit = price_evidence(band(sigma=sigma, coverage=coverage))
                self.assertGreaterEqual(charge, 0.0)
                self.assertGreaterEqual(limit, charge)

    def test_low_coverage_is_not_mistaken_for_a_proven_exclusion(self) -> None:
        charge, limit = price_evidence(band(coverage=0.5))

        self.assertGreater(charge, 0.0)
        self.assertEqual(limit, charge)

    def test_proven_exclusion_collapses_the_point_estimate(self) -> None:
        self.assertEqual(price_evidence(band(), confirmed_uncovered=True), (0.0, 0.0))


class Strategy5ProposalTests(unittest.IsolatedAsyncioTestCase):
    def test_reprices_recorded_evidence_and_preserves_all_indices(self) -> None:
        result = proposal_from_decisions(7, payload(), {1})

        self.assertIsNotNone(result)
        self.assertEqual(result.source, STRATEGY_NAME)
        self.assertEqual([price.index for price in result.prices], [1])
        self.assertLessEqual(result.prices[0].charge_price, result.prices[0].acceptance_limit)

    def test_refuses_partial_or_non_strategy2_evidence(self) -> None:
        self.assertIsNone(proposal_from_decisions(7, payload(), {1, 2}))
        wrong = dict(payload(), strategy="strategy1")
        self.assertIsNone(proposal_from_decisions(7, wrong, {1}))

    def test_recorded_proven_exclusion_collapses_both_values(self) -> None:
        excluded = payload()
        excluded["items"][0]["quantity_missing"] = True
        excluded["items"][0]["rule"] = "uncovered-free-option"

        result = proposal_from_decisions(7, excluded, {1})

        self.assertEqual(result.prices[0].charge_price, 0.0)
        self.assertEqual(result.prices[0].acceptance_limit, 0.0)

    def test_first_uninformed_invoice_position_gets_primary_prior(self) -> None:
        missing = payload()
        missing["items"] = [
            {"index": 4, "price_median": None, "charge": 300, "limit": 35},
            {"index": 9, "price_median": None, "charge": 300, "limit": 35},
        ]

        result = proposal_from_decisions(7, missing, {4, 9})

        by_index = result.by_index()
        self.assertEqual(by_index[4].charge_price, PRIMARY_UNINFORMED_FAIR_VALUE)
        self.assertEqual(by_index[4].acceptance_limit, PRIMARY_UNINFORMED_FAIR_VALUE)
        self.assertEqual(by_index[9].charge_price, UNINFORMED_FAIR_VALUE)
        self.assertEqual(by_index[9].acceptance_limit, UNINFORMED_FAIR_VALUE)

    def test_zero_limit_rule_without_dash_quantity_is_not_an_exclusion(self) -> None:
        uncertain = payload()
        uncertain["items"][0]["coverage_probability"] = 0.2
        uncertain["items"][0]["rule"] = "uncovered-free-option"

        result = proposal_from_decisions(7, uncertain, {1})

        self.assertGreater(result.prices[0].charge_price, 0.0)
        self.assertEqual(result.prices[0].charge_price, result.prices[0].acceptance_limit)

    async def test_live_strategy_reuses_log_and_rejects_a_stale_baseline(self) -> None:
        case = CaseData(7, Path("case"), line_items=(LineItem(1, "Repair"),))
        baseline = Proposal("strategy2", (ItemPrice(1, 62.5, 45.0, "strategy2"),))
        stale = Proposal("strategy2", (ItemPrice(1, 63.0, 45.0, "strategy2"),))

        with tempfile.TemporaryDirectory() as directory, patch.object(
            decision_log, "DECISIONS_DIR", Path(directory)
        ):
            Path(directory, "game_007.json").write_text(json.dumps(payload()))
            result = await propose(case, baseline=baseline)
            rejected = await propose(case, baseline=stale)

        self.assertIsNotNone(result)
        self.assertEqual(result.source, STRATEGY_NAME)
        self.assertIsNone(rejected)


if __name__ == "__main__":
    unittest.main()
