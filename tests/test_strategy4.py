import asyncio
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.data.models import CaseData, ItemPrice, LineItem, Proposal
from src.evidence.memory import PriceMemoryHit
from src.pricing.engine import Evidence
from src.strategies.strategy4.constants import STRATEGY_NAME
from src.strategies.strategy4.strategy import _find_conflicts, propose


def memory_hit(name: str) -> PriceMemoryHit:
    return PriceMemoryHit(
        name=name,
        key=name.lower(),
        match="exact",
        low=1_958.7316723940103,
        median=3_011.075,
        high=4_628.7976977181415,
        observations=1,
        games=(27,),
        basis="gross",
    )


def case_and_log() -> tuple[CaseData, dict]:
    name = "Compensation for robbery damage (1 pcs)"
    case = CaseData(
        41,
        Path("case"),
        line_items=(LineItem(3, name),),
    )
    payload = {
        "schema": 2,
        "game_id": 41,
        "strategy": "strategy2",
        "items": [
            {
                "index": 3,
                "name": name,
                "quantity": 1.0,
                "quantity_missing": False,
                "channels": ["B:memory", "C:model"],
                "coverage_probability": 0.955,
                "price_low": 3_108.3601606248826,
                "price_median": 5_523.664522371174,
                "price_high": 9_815.744694645771,
                "charge": 4_782.94,
                "limit": 4_142.75,
            }
        ],
    }
    return case, payload


class Strategy4Tests(unittest.IsolatedAsyncioTestCase):
    def test_logged_memory_blend_recovers_the_hidden_tail_estimate(self) -> None:
        case, payload = case_and_log()
        with patch(
            "src.strategies.strategy4.strategy.lookup",
            return_value=memory_hit(case.line_items[0].name),
        ):
            conflicts = _find_conflicts(case, payload)

        self.assertEqual(set(conflicts), {3})
        self.assertTrue(math.isclose(conflicts[3].model.price_median, 18_000, abs_tol=1e-6))

    async def test_confirmed_tail_changes_strategy4_but_not_the_baseline(self) -> None:
        case, payload = case_and_log()
        baseline = Proposal(
            "strategy2",
            (ItemPrice(3, 4_782.94, 4_142.75, "strategy2"),),
        )
        adjudicated = {3: Evidence(3, 0.95, 8_000, 12_000, 18_000)}

        with tempfile.TemporaryDirectory() as directory, patch(
            "src.strategies.strategy4.strategy.TRACE_DIR", Path(directory)
        ), patch(
            "src.strategies.strategy4.strategy.load_decisions", return_value=payload
        ), patch(
            "src.strategies.strategy4.strategy.lookup",
            return_value=memory_hit(case.line_items[0].name),
        ), patch(
            "src.strategies.strategy4.strategy._adjudicate",
            new=AsyncMock(return_value=adjudicated),
        ):
            candidate = await propose(case, baseline=baseline)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.source, STRATEGY_NAME)
        self.assertGreater(candidate.prices[0].charge_price, baseline.prices[0].charge_price)
        self.assertGreater(candidate.prices[0].acceptance_limit, baseline.prices[0].acceptance_limit)
        self.assertEqual(baseline.source, "strategy2")
        self.assertEqual(baseline.prices[0].charge_price, 4_782.94)

    async def test_expired_deadline_relabels_baseline_without_calling_model(self) -> None:
        case, payload = case_and_log()
        baseline = Proposal(
            "strategy2",
            (ItemPrice(3, 4_782.94, 4_142.75, "strategy2"),),
        )
        adjudicate = AsyncMock()

        with tempfile.TemporaryDirectory() as directory, patch(
            "src.strategies.strategy4.strategy.TRACE_DIR", Path(directory)
        ), patch(
            "src.strategies.strategy4.strategy.load_decisions", return_value=payload
        ), patch(
            "src.strategies.strategy4.strategy.lookup",
            return_value=memory_hit(case.line_items[0].name),
        ), patch(
            "src.strategies.strategy4.strategy._adjudicate", new=adjudicate
        ):
            candidate = await propose(
                case,
                deadline=asyncio.get_running_loop().time(),
                baseline=baseline,
            )

        adjudicate.assert_not_awaited()
        self.assertEqual(candidate.source, STRATEGY_NAME)
        self.assertEqual(candidate.prices[0].charge_price, baseline.prices[0].charge_price)


def large_model_only_case() -> tuple[CaseData, dict]:
    """Game 67 Line Item 1, verbatim: `C:model` alone, and it settled at `t < 33`."""
    name = "Renew boiler system including flue gas system and (1   flat rate)"
    case = CaseData(67, Path("case"), line_items=(LineItem(1, name), LineItem(2, "Vehicle costs")))
    payload = {
        "schema": 2,
        "game_id": 67,
        "strategy": "strategy2",
        "items": [
            {
                "index": 1,
                "name": name,
                "quantity": 1.0,
                "quantity_missing": False,
                "channels": ["C:model"],
                "coverage_probability": 0.98,
                "price_low": 8_000.0,
                "price_median": 13_730.0,
                "price_high": 23_000.0,
                "charge": 10_343.65,
                "limit": 708.0,
            },
            {
                "index": 2,
                "name": "Vehicle costs",
                "quantity": 1.0,
                "quantity_missing": False,
                "channels": ["C:model"],
                "coverage_probability": 0.94,
                "price_low": 50.0,
                "price_median": 84.0,
                "price_high": 140.0,
                "charge": 66.58,
                "limit": 68.94,
            },
        ],
    }
    return case, payload


class LargeItemRereadTests(unittest.IsolatedAsyncioTestCase):
    """A large model-only estimate is sent for a second reading, and never repriced on it.

    The gates that existed before required a Price Memory hit, so nine Games produced zero
    conflicts and this track tied Strategy 2 to the cent every time. The estimates that actually
    cost money could not reach them: Game 67's boiler at 13,730 against a settled `t < 33` and
    Game 68's ring at 8,000 against `t in [2421, 2850)` were both `C:model` alone.
    """

    def test_a_large_model_only_estimate_is_selected(self) -> None:
        case, payload = large_model_only_case()
        conflicts = _find_conflicts(case, payload)

        self.assertEqual(set(conflicts), {1}, "only the item over the threshold")
        self.assertEqual(conflicts[1].memory_hit.match, "large-item-review")

    def test_a_small_model_only_estimate_is_left_alone(self) -> None:
        """The threshold must not quietly become "adjudicate everything": each item added is
        another line in a prompt the Case has 60 seconds to answer."""
        case, payload = large_model_only_case()
        payload["items"][0]["price_median"] = 1_999.0
        self.assertEqual(_find_conflicts(case, payload), {})

    def test_the_reread_is_recorded_but_never_changes_the_price(self) -> None:
        """The whole first step is buying evidence. `_confirms_tail` cannot fire on this path
        because the incumbent and the model reading are the same Evidence, so whatever the
        adjudication says, the Proposal must equal Strategy 2's."""
        case, payload = large_model_only_case()
        baseline = Proposal(
            "strategy2",
            (
                ItemPrice(1, 10_343.65, 708.0, "strategy2"),
                ItemPrice(2, 66.58, 68.94, "strategy2"),
            ),
        )
        # The reread disagrees violently in both directions; neither may move the Proposal.
        for reread_median in (300.0, 90_000.0):
            with self.subTest(reread=reread_median), tempfile.TemporaryDirectory() as directory, patch(
                "src.strategies.strategy4.strategy.TRACE_DIR", Path(directory)
            ), patch(
                "src.strategies.strategy4.strategy.load_decisions", return_value=payload
            ), patch(
                "src.strategies.strategy4.strategy._adjudicate",
                new=AsyncMock(
                    return_value={1: Evidence(1, 0.98, reread_median * 0.7, reread_median, reread_median * 1.4)}
                ),
            ):
                candidate = asyncio.run(propose(case, None, baseline=baseline))

            self.assertIsNotNone(candidate)
            self.assertEqual(candidate.source, STRATEGY_NAME)
            self.assertEqual(
                {p.index: (p.charge_price, p.acceptance_limit) for p in candidate.prices},
                {1: (10_343.65, 708.0), 2: (66.58, 68.94)},
            )


if __name__ == "__main__":
    unittest.main()
