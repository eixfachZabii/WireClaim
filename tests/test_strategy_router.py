import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.runtime import decisions as decision_log
from src.data.models import CaseData, ItemPrice, Proposal
from src.runtime.decisions import load, proposals
from src.strategies import router as strategy_router
from src.strategies.router import StrategyRouter


def proposal(source: str, charge: float, index: int = 1) -> Proposal:
    return Proposal(source=source, prices=(ItemPrice(index, charge, charge * 0.75, source),))


class StrategyRouterTests(unittest.TestCase):
    def test_strategy2_outranks_the_others_in_either_arrival_order(self) -> None:
        """Strategy 2 is the only one with constants fitted to the reconstructed Fair
        Values, so it wins regardless of which strategy finishes first."""
        router = StrategyRouter(strategies=())

        self.assertEqual(router.register(proposal("strategy1", 100.0)).source, "strategy1")
        self.assertEqual(router.register(proposal("strategy3", 300.0)).source, "strategy3")
        self.assertEqual(router.register(proposal("strategy4", 350.0)).source, "strategy4")
        self.assertEqual(router.register(proposal("strategy5", 375.0)).source, "strategy5")
        self.assertEqual(router.register(proposal("strategy2", 200.0)).source, "strategy2")
        self.assertIsNone(router.register(proposal("strategy1", 400.0)))
        self.assertIsNone(router.register(proposal("strategy3", 500.0)))
        self.assertIsNone(router.register(proposal("strategy4", 600.0)))
        self.assertIsNone(router.register(proposal("strategy5", 700.0)))
        self.assertEqual(router.current.source, "strategy2")

    def test_strategy2_wins_even_when_it_lands_first(self) -> None:
        router = StrategyRouter(strategies=())

        self.assertEqual(router.register(proposal("strategy2", 200.0)).source, "strategy2")
        self.assertIsNone(router.register(proposal("strategy3", 300.0)))
        self.assertEqual(router.current.source, "strategy2")

    def test_a_shadow_strategy_is_never_submitted_even_when_it_answers_alone(self) -> None:
        """The case a low priority alone does not cover.

        `register` rejects a *lower* priority, not an equal one, and `_current_priority`
        starts at -1. So a shadow track at priority 0 that answers first -- or answers alone,
        on a Game where Strategy 2 timed out or returned empty, which has happened twice --
        would otherwise become the Submission.
        """
        router = StrategyRouter()

        self.assertIsNone(router.register(proposal("jonas", charge=100.0)))
        self.assertIsNone(router.current)

    def test_a_shadow_strategy_cannot_displace_or_follow_strategy2(self) -> None:
        router = StrategyRouter()

        router.register(proposal("strategy2", charge=50.0))
        self.assertIsNone(router.register(proposal("jonas", charge=100.0)))
        self.assertEqual(router.current.source, "strategy2")

    def test_a_shadow_strategy_is_still_recorded_for_comparison(self) -> None:
        """Logged but not submitted -- otherwise it cannot be scored against Strategy 2."""
        router = StrategyRouter()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(decision_log, "DECISIONS_DIR", Path(directory)):
                router.register(proposal("strategy2", charge=50.0))
                router._capture(7, proposal("jonas", charge=100.0))

                recorded = proposals(load(7))

        self.assertIn("jonas", recorded)
        self.assertEqual(router.current.source, "strategy2")

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
        with self.assertLogs("src.strategies.router", level="ERROR") as logs:
            results = [proposal async for proposal in router.results(case, deadline=1.0)]

        self.assertEqual(results, [])
        self.assertIn("\033[91m", logs.output[0])
        self.assertIn("FAILED", logs.output[0])
        self.assertIn("TimeoutError", logs.output[0])
        self.assertIn("model request timed out", logs.output[0])
        self.assertNotIn("Traceback", logs.output[0])

    async def test_default_router_records_both_comparisons_but_only_yields_strategy2(self) -> None:
        calls: list[str] = []

        async def active(case: CaseData, deadline: float | None = None) -> Proposal:
            calls.append("strategy2")
            return proposal("strategy2", 200.0)

        async def comparison(
            case: CaseData,
            deadline: float | None = None,
            *,
            baseline: Proposal | None = None,
        ) -> Proposal:
            calls.append("strategy4")
            self.assertIsNotNone(baseline)
            self.assertEqual(baseline.source, "strategy2")
            return proposal("strategy4", 400.0)

        async def posterior(
            case: CaseData,
            deadline: float | None = None,
            *,
            baseline: Proposal | None = None,
        ) -> Proposal:
            calls.append("strategy5")
            self.assertIsNotNone(baseline)
            self.assertEqual(baseline.source, "strategy2")
            return proposal("strategy5", 300.0)

        with patch.object(strategy_router, "strategy2", active), patch.object(
            strategy_router, "strategy4", comparison
        ), patch.object(
            strategy_router, "strategy5", posterior
        ):
            router = StrategyRouter()

        case = CaseData(game_id=26, case_dir=Path("var/cases/case_26"))
        yielded = [value async for value in router.results(case, deadline=1.0)]

        self.assertEqual(calls, ["strategy2", "strategy5", "strategy4"])
        self.assertEqual([value.source for value in yielded], ["strategy2"])
        self.assertEqual(router.current.source, "strategy2")
        self.assertEqual(sorted(router.seen), ["strategy2", "strategy4", "strategy5"])
        self.assertEqual(load(26)["winner"], "strategy2")

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
        router = StrategyRouter(strategies=(strategy2, strategy1))
        results = router.results(case, deadline=1.0)

        self.assertEqual((await anext(results)).source, "strategy2")
        with self.assertLogs("src.strategies.router", level="INFO") as logs:
            release_strategy1.set()
            with self.assertRaises(StopAsyncIteration):
                await anext(results)

        comparison = "\n".join(logs.output)
        self.assertIn("\033[90m", comparison)
        self.assertIn("STRATEGY1 COMPARISON ONLY", comparison)
        self.assertIn("candidate: strategy1 (priority 1)", comparison)
        self.assertIn("active: strategy2 (priority 4)", comparison)
        self.assertIn("NOT POSTED", comparison)

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

        run.__module__ = f"src.strategies.{source}.strategy"
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
