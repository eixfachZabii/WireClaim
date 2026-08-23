import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.observability import decisions as decision_log
from src.data.models import CaseData, ItemPrice, Proposal
from src.observability.decisions import load, proposals
from src.observability.timing import FairValueReference
from src.services import strategy_router
from src.services.strategy_router import MERGED_STRATEGY_SOURCE, StrategyRouter


def proposal(source: str, charge: float, index: int = 1) -> Proposal:
    return Proposal(source=source, prices=(ItemPrice(index, charge, charge * 0.75, source),))


class StrategyRouterTests(unittest.TestCase):
    def test_default_runner_starts_only_strategy5(self) -> None:
        router = StrategyRouter()

        self.assertEqual(router._strategies, (strategy_router.strategy5,))

    def test_strategy2_outranks_the_others_in_either_arrival_order(self) -> None:
        """Strategy 2 is the only one with constants fitted to the reconstructed Fair
        Values, so it wins regardless of which strategy finishes first."""
        router = StrategyRouter(strategies=())

        self.assertEqual(router.register(proposal("strategy1", 100.0)).source, "strategy1")
        self.assertEqual(router.register(proposal("strategy3", 300.0)).source, "strategy3")
        self.assertEqual(router.register(proposal("strategy2", 200.0)).source, "strategy2")
        self.assertIsNone(router.register(proposal("strategy1", 400.0)))
        self.assertIsNone(router.register(proposal("strategy3", 500.0)))
        self.assertEqual(router.current.source, "strategy2")

    def test_strategy2_wins_even_when_it_lands_first(self) -> None:
        router = StrategyRouter(strategies=())

        self.assertEqual(router.register(proposal("strategy2", 200.0)).source, "strategy2")
        self.assertIsNone(router.register(proposal("strategy3", 300.0)))
        self.assertEqual(router.current.source, "strategy2")

    def test_strategy4_stays_below_the_measured_strategy2_track(self) -> None:
        router = StrategyRouter(strategies=())

        self.assertEqual(router.register(proposal("strategy4", 300.0)).source, "strategy4")
        self.assertEqual(router.register(proposal("strategy2", 200.0)).source, "strategy2")
        self.assertEqual(router.current.source, "strategy2")

    def test_strategy2_then_strategy5_produces_the_special_merge(self) -> None:
        router = StrategyRouter(strategies=())
        strategy2_result = Proposal(
            source="strategy2",
            prices=(
                ItemPrice(1, 100.0, 0.0, "strategy2"),
                ItemPrice(2, 300.0, 40.0, "strategy2"),
                ItemPrice(3, 80.0, 20.0, "strategy2"),
            ),
        )
        strategy5_result = Proposal(
            source="strategy5",
            prices=(
                ItemPrice(1, 120.0, 50.0, "strategy5"),
                ItemPrice(2, 200.0, 60.0, "strategy5"),
                ItemPrice(4, 90.0, 30.0, "strategy5"),
            ),
        )

        self.assertEqual(router.register(strategy2_result).source, "strategy2")
        merged = router.register(strategy5_result)

        self.assertEqual(merged.source, MERGED_STRATEGY_SOURCE)
        self.assertEqual(
            {
                price.index: (price.charge_price, price.acceptance_limit)
                for price in merged.prices
            },
            {
                1: (120.0, 0.0),
                2: (300.0, 60.0),
                3: (80.0, 20.0),
                4: (90.0, 30.0),
            },
        )
        self.assertTrue(all(price.source == MERGED_STRATEGY_SOURCE for price in merged.prices))

    def test_strategy5_then_strategy2_produces_the_same_special_merge(self) -> None:
        strategy2_result = Proposal(
            source="strategy2",
            prices=(ItemPrice(1, 100.0, 0.0, "strategy2"), ItemPrice(2, 300.0, 40.0, "strategy2")),
        )
        strategy5_result = Proposal(
            source="strategy5",
            prices=(ItemPrice(1, 120.0, 50.0, "strategy5"), ItemPrice(2, 200.0, 60.0, "strategy5")),
        )
        router = StrategyRouter(strategies=())

        router.register(strategy5_result)
        merged = router.register(strategy2_result)

        self.assertEqual(merged.source, MERGED_STRATEGY_SOURCE)
        self.assertEqual(
            [(price.index, price.charge_price, price.acceptance_limit) for price in merged.prices],
            [(1, 120.0, 0.0), (2, 300.0, 60.0)],
        )

    def test_an_unknown_source_loses_to_every_known_strategy(self) -> None:
        router = StrategyRouter(strategies=())
        router.register(proposal("strategy1", 100.0))

        self.assertIsNone(router.register(proposal("mystery", 900.0)))

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
    def setUp(self) -> None:
        # `results()` now writes the Proposals it sees, so the log directory is redirected:
        # a test must never leave a decision log behind for a real Game to be analysed.
        self.tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(decision_log, "DECISIONS_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    async def test_logs_a_compact_error_card_for_a_failed_strategy(self) -> None:
        async def failed_strategy(case: CaseData, deadline: float | None = None) -> Proposal:
            raise TimeoutError("model request timed out")

        router = StrategyRouter(strategies=(failed_strategy,))
        case = CaseData(game_id=1, case_dir=Path("var/cases/case_01"))
        with self.assertLogs("src.services.strategy_router", level="ERROR") as logs:
            results = [proposal async for proposal in router.results(case, deadline=1.0)]

        self.assertEqual(results, [])
        self.assertIn("\033[91m", logs.output[0])
        self.assertIn("FAILED", logs.output[0])
        self.assertIn("TimeoutError", logs.output[0])
        self.assertIn("model request timed out", logs.output[0])
        self.assertNotIn("Traceback", logs.output[0])

    async def test_logs_a_gray_comparison_for_a_lower_priority_strategy(self) -> None:
        release_strategy1 = asyncio.Event()

        async def strategy2(case: CaseData, deadline: float | None = None) -> Proposal:
            return Proposal(
                source="strategy2",
                prices=(ItemPrice(1, 200.0, 150.0, "strategy2"),),
            )

        async def strategy1(case: CaseData, deadline: float | None = None) -> Proposal:
            await release_strategy1.wait()
            return Proposal(
                source="strategy1",
                prices=(ItemPrice(1, 100.0, 75.0, "strategy1"),),
            )

        case = CaseData(game_id=1, case_dir=Path("var/cases/case_01"))
        router = StrategyRouter(
            strategies=(strategy2, strategy1),
            fair_value_references={1: FairValueReference(122.94, None, None)},
        )
        results = router.results(case, deadline=1.0)

        self.assertEqual((await anext(results)).source, "strategy2")
        with self.assertLogs("src.services.strategy_router", level="INFO") as logs:
            release_strategy1.set()
            with self.assertRaises(StopAsyncIteration):
                await anext(results)

        comparison = "\n".join(logs.output)
        self.assertIn("\033[90m", comparison)
        self.assertIn("STRATEGY1 COMPARISON ONLY", comparison)
        self.assertIn("candidate: strategy1 (priority 1)", comparison)
        self.assertIn("active: strategy2 (priority 3)", comparison)
        self.assertIn("NOT POSTED", comparison)
        self.assertIn("fair value lower | Fair Value interval", comparison)
        self.assertIn("122.94 | [122.94, ∞)", comparison)

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

    async def test_strategy2_and_strategy5_merge_when_either_finishes_last(self) -> None:
        async def run(first_source: str) -> list[Proposal]:
            release2 = asyncio.Event()
            release5 = asyncio.Event()

            async def strategy2(case: CaseData, deadline: float | None = None) -> Proposal:
                await release2.wait()
                return Proposal(
                    source="strategy2",
                    prices=(ItemPrice(1, 100.0, 0.0, "strategy2"),),
                )

            async def strategy5(case: CaseData, deadline: float | None = None) -> Proposal:
                await release5.wait()
                return Proposal(
                    source="strategy5",
                    prices=(ItemPrice(1, 120.0, 50.0, "strategy5"),),
                )

            strategy2.__module__ = "src.services.strategies.strategy2.strategy"
            strategy5.__module__ = "src.services.strategies.strategy5.strategy"
            router = StrategyRouter(strategies=(strategy2, strategy5))
            results = router.results(CaseData(game_id=1, case_dir=Path("case_01")), deadline=1.0)
            first_result = asyncio.create_task(anext(results))
            await asyncio.sleep(0)
            (release2 if first_source == "strategy2" else release5).set()
            found = [await first_result]
            second_result = asyncio.create_task(anext(results))
            (release5 if first_source == "strategy2" else release2).set()
            found.append(await second_result)
            with self.assertRaises(StopAsyncIteration):
                await anext(results)
            return found

        for first_source in ("strategy2", "strategy5"):
            with self.subTest(first_source=first_source):
                found = await run(first_source)
                self.assertEqual([item.source for item in found], [first_source, MERGED_STRATEGY_SOURCE])
                self.assertEqual(found[-1].prices[0].charge_price, 120.0)
                self.assertEqual(found[-1].prices[0].acceptance_limit, 0.0)


class ProposalRecordingTests(unittest.IsolatedAsyncioTestCase):
    """Every Proposal is logged, not only the one priority keeps.

    Only the winner's numbers were ever recorded, so "would Strategy 3 have done better on
    this Game?" had no answer even though the settled Transactions determine it exactly.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(decision_log, "DECISIONS_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    @staticmethod
    def strategy(source: str, charge: float):
        async def run(case: CaseData, deadline: float | None = None) -> Proposal:
            return Proposal(
                source=source, prices=(ItemPrice(1, charge, charge * 0.3, source),)
            )

        run.__module__ = f"src.services.strategies.{source}.strategy"
        return run

    async def drain(self, router: StrategyRouter, game_id: int = 26) -> list[Proposal]:
        case = CaseData(game_id=game_id, case_dir=Path("var/cases/case_26"))
        return [p async for p in router.results(case, deadline=1.0)]

    async def test_the_losers_are_recorded_next_to_the_winner(self) -> None:
        router = StrategyRouter(
            strategies=(
                self.strategy("strategy1", 100.0),
                self.strategy("strategy2", 200.0),
                self.strategy("strategy3", 300.0),
            )
        )

        await self.drain(router)

        payload = load(26)
        self.assertEqual(
            proposals(payload),
            {
                "strategy1": {1: (100.0, 30.0)},
                "strategy2": {1: (200.0, 60.0)},
                "strategy3": {1: (300.0, 90.0)},
            },
        )
        self.assertEqual(payload["winner"], "strategy2")
        self.assertEqual(payload["game_id"], 26)

    async def test_strategy2_and_strategy5_merge_is_recorded_as_the_winner(self) -> None:
        router = StrategyRouter(
            strategies=(self.strategy("strategy2", 200.0), self.strategy("strategy5", 300.0))
        )

        yielded = await self.drain(router)
        payload = load(26)

        self.assertEqual(yielded[-1].source, MERGED_STRATEGY_SOURCE)
        self.assertEqual(
            proposals(payload),
            {
                "strategy2": {1: (200.0, 60.0)},
                "strategy5": {1: (300.0, 90.0)},
                MERGED_STRATEGY_SOURCE: {1: (300.0, 90.0)},
            },
        )
        self.assertEqual(payload["winner"], MERGED_STRATEGY_SOURCE)

    async def test_an_empty_proposal_is_recorded_as_having_answered_with_nothing(self) -> None:
        async def silent(case: CaseData, deadline: float | None = None) -> Proposal:
            return Proposal(source="strategy1", prices=())

        router = StrategyRouter(strategies=(silent, self.strategy("strategy2", 200.0)))

        await self.drain(router)

        self.assertEqual(proposals(load(26))["strategy1"], {})
        self.assertEqual(load(26)["winner"], "strategy2")

    async def test_a_strategy_that_returns_nothing_is_not_recorded(self) -> None:
        async def nothing(case: CaseData, deadline: float | None = None) -> None:
            return None

        router = StrategyRouter(strategies=(nothing, self.strategy("strategy2", 200.0)))

        await self.drain(router)

        self.assertEqual(sorted(proposals(load(26))), ["strategy2"])

    async def test_a_logging_failure_never_costs_the_submission(self) -> None:
        """A missing log costs one Game's learning; a lost Proposal costs the Game."""
        router = StrategyRouter(strategies=(self.strategy("strategy2", 200.0),))

        with patch.object(
            strategy_router, "record_proposals", side_effect=RuntimeError("disk on fire")
        ):
            yielded = await self.drain(router)

        self.assertEqual([p.source for p in yielded], ["strategy2"])
        self.assertEqual(router.current.source, "strategy2")

    async def test_seen_exposes_the_rejected_proposals(self) -> None:
        router = StrategyRouter(
            strategies=(self.strategy("strategy2", 200.0), self.strategy("strategy3", 300.0))
        )

        await self.drain(router)

        self.assertEqual(sorted(router.seen), ["strategy2", "strategy3"])
        self.assertEqual(router.current.source, "strategy2")


if __name__ == "__main__":
    unittest.main()
