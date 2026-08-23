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


if __name__ == "__main__":
    unittest.main()
