import asyncio
import unittest
from pathlib import Path

from src.data.models import CaseData, ItemPrice, Proposal
from src.services.strategy_router import StrategyRouter


def proposal(source: str, charge: float, index: int = 1) -> Proposal:
    return Proposal(source=source, prices=(ItemPrice(index, charge, charge * 0.75, source),))


class StrategyRouterTests(unittest.TestCase):
    def test_strategy2_has_higher_priority_than_strategy1(self) -> None:
        router = StrategyRouter(strategies=())

        self.assertEqual(router.register(proposal("strategy1", 100.0)).source, "strategy1")
        self.assertEqual(router.register(proposal("strategy2", 200.0)).source, "strategy2")
        self.assertEqual(router.register(proposal("strategy3", 300.0)).source, "strategy3")
        self.assertIsNone(router.register(proposal("strategy1", 400.0)))
        self.assertIsNone(router.register(proposal("strategy2", 500.0)))
        self.assertEqual(router.current.source, "strategy3")

    def test_empty_proposal_does_not_replace_active_strategy(self) -> None:
        router = StrategyRouter(strategies=())
        router.register(proposal("strategy1", 100.0))

        self.assertIsNone(router.register(Proposal(source="strategy2", prices=())))
        self.assertEqual(router.current.source, "strategy1")

    def test_lower_priority_strategy_cannot_add_to_the_current_batch(self) -> None:
        router = StrategyRouter(strategies=())
        router.register(proposal("strategy3", 300.0, index=1))

        self.assertIsNone(router.register(proposal("strategy1", 100.0, index=2)))
        self.assertEqual(
            [(price.index, price.charge_price) for price in router.current.prices],
            [(1, 300.0)],
        )

    def test_higher_priority_strategy_replaces_the_entire_batch(self) -> None:
        router = StrategyRouter(strategies=())
        router.register(
            Proposal(
                source="strategy1",
                prices=(
                    ItemPrice(1, 100.0, 75.0, "strategy1"),
                    ItemPrice(2, 200.0, 150.0, "strategy1"),
                ),
            )
        )

        merged = router.register(proposal("strategy3", 300.0, index=1))

        self.assertIsNotNone(merged)
        self.assertEqual(
            [(price.index, price.charge_price) for price in merged.prices],
            [(1, 300.0)],
        )


class StrategyRouterConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_starts_strategies_concurrently_and_keeps_the_highest_complete_batch(self) -> None:
        started: set[str] = set()
        both_started = asyncio.Event()
        release_strategy1 = asyncio.Event()
        release_strategy3 = asyncio.Event()

        async def strategy1(case: CaseData, deadline: float | None = None) -> Proposal:
            started.add("strategy1")
            if len(started) == 2:
                both_started.set()
            await release_strategy1.wait()
            return Proposal(
                source="strategy1",
                prices=(ItemPrice(1, 100.0, 35.0, "strategy1"), ItemPrice(2, 200.0, 35.0, "strategy1")),
            )

        async def strategy3(case: CaseData, deadline: float | None = None) -> Proposal:
            started.add("strategy3")
            if len(started) == 2:
                both_started.set()
            await release_strategy3.wait()
            return Proposal(
                source="strategy3",
                prices=(ItemPrice(1, 300.0, 35.0, "strategy3"), ItemPrice(2, 400.0, 35.0, "strategy3")),
            )

        case = CaseData(game_id=1, case_dir=Path("var/cases/case_01"))
        router = StrategyRouter(strategies=(strategy1, strategy3))
        results = router.results(case, deadline=1.0)
        first_result = asyncio.create_task(anext(results))

        await asyncio.wait_for(both_started.wait(), timeout=0.5)
        self.assertEqual(started, {"strategy1", "strategy3"})
        release_strategy3.set()
        self.assertEqual((await first_result).source, "strategy3")
        release_strategy1.set()
        with self.assertRaises(StopAsyncIteration):
            await anext(results)


if __name__ == "__main__":
    unittest.main()
