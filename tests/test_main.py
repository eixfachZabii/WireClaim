import argparse
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import main
from main import RunManager
from src.data.models import CaseData, FraudDecision, ItemPrice, LineItem, Proposal


def proposal(source: str, prices: list[tuple[int, float, float]]) -> Proposal:
    return Proposal(
        source=source,
        prices=tuple(ItemPrice(index, charge, limit_, source) for index, charge, limit_ in prices),
    )


class RunManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        base = proposal("standard", [(1, 100.0, 75.0), (2, 200.0, 150.0)])
        self.manager = RunManager(base)

    def test_fraud_lock_keeps_strategy_charge(self) -> None:
        self.manager.set_strategy(proposal("strategy1", [(1, 120.0, 90.0), (2, 250.0, 190.0)]))
        self.manager.apply_fraud(FraudDecision(frozenset({2})))

        prices = {price.index: price for price in self.manager.snapshot()}

        self.assertEqual((prices[1].charge_price, prices[1].acceptance_limit), (120.0, 90.0))
        self.assertEqual((prices[2].charge_price, prices[2].acceptance_limit), (250.0, 0.0))

    def test_fraud_lock_survives_a_later_strategy(self) -> None:
        self.manager.set_strategy(proposal("strategy1", [(1, 120.0, 90.0), (2, 250.0, 190.0)]))
        self.manager.apply_fraud(FraudDecision(frozenset({2})))
        self.manager.set_strategy(proposal("strategy2", [(1, 130.0, 95.0), (2, 300.0, 220.0)]))

        prices = {price.index: price for price in self.manager.snapshot()}

        self.assertEqual(self.manager.fraud_indices, frozenset({2}))
        self.assertEqual((prices[1].charge_price, prices[1].acceptance_limit), (130.0, 95.0))
        self.assertEqual((prices[2].charge_price, prices[2].acceptance_limit), (300.0, 0.0))

    def test_strategy5_fraud_lock_preserves_charge_below_limit_invariant(self) -> None:
        self.manager.set_strategy(proposal("strategy5", [(1, 80.0, 140.0)]))
        self.manager.apply_fraud(FraudDecision(frozenset({1})))

        price = {price.index: price for price in self.manager.snapshot()}[1]

        self.assertEqual((price.charge_price, price.acceptance_limit), (0.0, 0.0))

    def test_strategy_keeps_priority_when_fast_path_finishes_later(self) -> None:
        self.manager.set_strategy(proposal("strategy1", [(1, 120.0, 90.0)]))
        self.manager.set_fast_path(proposal("fast_path_llm", [(1, 110.0, 80.0)]))

        prices = {price.index: price for price in self.manager.snapshot()}

        self.assertEqual((prices[1].charge_price, prices[1].acceptance_limit), (120.0, 90.0))

    def test_complete_strategy_result_replaces_the_entire_fast_path_batch(self) -> None:
        self.manager.set_fast_path(proposal("fast_path_llm", [(1, 110.0, 80.0), (2, 210.0, 160.0)]))
        self.manager.set_strategy(proposal("strategy3", [(1, 300.0, 250.0), (2, 400.0, 350.0)]))

        prices = {price.index: price for price in self.manager.snapshot()}

        self.assertEqual((prices[1].charge_price, prices[1].acceptance_limit), (300.0, 250.0))
        self.assertEqual((prices[2].charge_price, prices[2].acceptance_limit), (400.0, 350.0))

    def test_fraud_locks_survive_a_complete_high_priority_strategy_batch(self) -> None:
        self.manager.set_fast_path(proposal("fast_path_llm", [(1, 110.0, 80.0), (2, 210.0, 160.0)]))
        self.manager.apply_fraud(FraudDecision(frozenset({2})))
        self.manager.set_strategy(proposal("strategy3", [(1, 300.0, 250.0), (2, 400.0, 350.0)]))

        prices = {price.index: price for price in self.manager.snapshot()}

        self.assertEqual((prices[1].charge_price, prices[1].acceptance_limit), (300.0, 250.0))
        self.assertEqual((prices[2].charge_price, prices[2].acceptance_limit), (400.0, 0.0))

    def test_republishing_the_same_prices_reports_no_change(self) -> None:
        """The coordinator dedupes by signature, but do not wake it needlessly."""
        first = proposal("strategy2", [(1, 120.0, 90.0)])

        self.assertTrue(self.manager.set_strategy(first))
        self.assertFalse(self.manager.set_strategy(first))

    def test_strategy_has_priority_over_fast_path(self) -> None:
        self.manager.set_fast_path(proposal("fast_path_llm", [(1, 110.0, 80.0)]))
        self.manager.set_strategy(proposal("strategy1", [(1, 120.0, 90.0)]))

        prices = {price.index: price for price in self.manager.snapshot()}

        self.assertEqual((prices[1].charge_price, prices[1].acceptance_limit), (120.0, 90.0))
        self.assertEqual((prices[2].charge_price, prices[2].acceptance_limit), (200.0, 150.0))


class RetryDryTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_expired_games_in_order_and_stops_before_future_game(self) -> None:
        now = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
        games = [
            {"id": 2, "start_time": "2026-08-22T11:58:00Z"},
            {"id": 1, "start_time": "2026-08-22T11:50:00Z"},
            {"id": 3, "start_time": "2026-08-22T12:30:00Z"},
        ]
        run_game = AsyncMock()
        with patch.object(main, "list_games", return_value=games), patch.object(
            main, "run_game", run_game
        ):
            await main.retry_expired_games(now=now)

        self.assertEqual(run_game.await_count, 2)
        self.assertEqual(run_game.await_args_list[0].args, (1,))
        self.assertEqual(run_game.await_args_list[1].args, (2,))
        self.assertTrue(run_game.await_args_list[0].kwargs["dry_run"])
        self.assertTrue(run_game.await_args_list[1].kwargs["dry_run"])

    async def test_stops_before_a_still_active_game(self) -> None:
        now = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
        games = [
            {"id": 1, "start_time": "2026-08-22T11:50:00Z"},
            {"id": 2, "start_time": "2026-08-22T11:59:30Z"},
            {"id": 3, "start_time": "2026-08-22T12:30:00Z"},
        ]
        run_game = AsyncMock()
        with patch.object(main, "list_games", return_value=games), patch.object(
            main, "run_game", run_game
        ):
            await main.retry_expired_games(now=now)

        self.assertEqual(run_game.await_count, 1)
        self.assertEqual(run_game.await_args.args, (1,))

    async def test_a_case_that_never_loads_still_submits_the_blind_floor(self) -> None:
        """Silence is not abstention. Omitted Line Items default to `a = 0, b = 0`, which
        earns nothing and wrongfully rejects every fair claim at 1.5x -- so a Case that never
        loads must still leave a floor behind (CLAUDE.md rule 1). This test previously
        asserted the opposite; it was written in the same commit that deleted the floor."""
        submitter = Mock(return_value=[])
        with (
            patch.object(main, "load_case", side_effect=RuntimeError("no key")),
            patch.object(main, "dry_run_submit", submitter),
        ):
            await main.run_game(99, dry_run=True)

        submitter.assert_called()
        submitted = submitter.call_args.args[1]
        self.assertEqual(len(submitted), main.BLIND_LINE_ITEMS)
        self.assertTrue(all(item["charge_price"] > 0 for item in submitted))

    async def test_first_submission_uses_only_loaded_case_indices(self) -> None:
        case = CaseData(
            game_id=99,
            case_dir=Path("var/cases/case_99"),
            line_items=(LineItem(1, "Repair"), LineItem(2, "Replacement")),
        )
        submitter = Mock(return_value=[])
        with (
            patch.object(main, "load_case", new=AsyncMock(return_value=case)),
            patch.object(main, "warm_llm_resources"),
            patch.object(main, "llm_values", new=AsyncMock(return_value=None)),
            patch.object(main, "detect_fraud", new=AsyncMock(return_value=FraudDecision())),
            patch.object(main, "_forward_strategies", new=AsyncMock(return_value=None)),
            patch.object(main, "dry_run_submit", submitter),
        ):
            await main.run_game(99, dry_run=True)

        self.assertEqual(submitter.call_count, 1)
        first_submissions = submitter.call_args.args[1]
        # The blind floor is published before the key fetch, but the coordinator coalesces
        # pending snapshots before it flushes -- so on a Case that loads normally the floor is
        # superseded in memory and never costs a submission. This is what makes restoring it
        # free: it is visible only on the path where the Case never arrives.
        self.assertEqual([submission["index"] for submission in first_submissions], [1, 2])

    def test_dry_submit_returns_without_logging(self) -> None:
        submissions = [{"index": 1, "charge_price": 150.0, "acceptance_limit": 75.0}]

        with self.assertNoLogs("main", level="INFO"):
            result = main.dry_run_submit(7, submissions, timeout=1.0)

        self.assertEqual(result, [])

    async def test_emit_result_logs_a_compact_error_card_and_continues(self) -> None:
        events: asyncio.Queue[main.RunEvent] = asyncio.Queue()

        async def timeout() -> None:
            raise TimeoutError("gateway read timed out")

        with self.assertLogs("main", level="ERROR") as logs:
            await main._emit_result(events, "fast_path", timeout(), game_id=25)

        self.assertTrue(events.empty())
        self.assertIn("\033[91m", logs.output[0])
        self.assertIn("FAST PATH FAILED", logs.output[0])
        self.assertIn("TimeoutError", logs.output[0])
        self.assertIn("gateway read timed out", logs.output[0])
        self.assertIn("Strategies continue", logs.output[0])
        self.assertNotIn("Traceback", logs.output[0])


class GameDurationTests(unittest.IsolatedAsyncioTestCase):
    def test_live_games_keep_the_sixty_second_default(self) -> None:
        self.assertEqual(main.game_duration({"id": 1}), main.RUN_SECONDS)
        self.assertEqual(main.game_duration({"id": 1, "duration_seconds": "invalid"}), main.RUN_SECONDS)

    async def test_backtesting_duration_is_passed_to_the_same_runner(self) -> None:
        start = datetime.now(timezone.utc) - timedelta(seconds=120)
        games = [
            {
                "id": 49,
                "start_time": start.isoformat().replace("+00:00", "Z"),
                "duration_seconds": 3600.0,
            }
        ]
        run_game = AsyncMock()
        with patch.object(main, "list_games", return_value=games), patch.object(
            main, "run_game", run_game
        ):
            await main.watch_games()

        run_game.assert_awaited_once_with(49, run_seconds=3600.0)


class MainTests(unittest.TestCase):
    def test_interrupt_stops_runner_cleanly(self) -> None:
        args = argparse.Namespace(game_id=None, retry_dry=False)
        with (
            patch.object(main.argparse.ArgumentParser, "parse_args", return_value=args),
            patch.object(main, "watch_games", new=Mock(return_value=object())),
            patch.object(main.asyncio, "run", side_effect=KeyboardInterrupt),
            self.assertLogs("main", level="INFO") as logs,
        ):
            main.main()

        self.assertIn("INFO:main:Stopping WireClaim runner.", logs.output)

    def test_game_id_and_retry_dry_runs_one_game_without_posting(self) -> None:
        args = argparse.Namespace(game_id=18, retry_dry=True)
        run_game = Mock(return_value=object())
        with (
            patch.object(main.argparse.ArgumentParser, "parse_args", return_value=args),
            patch.object(main, "run_game", new=run_game),
            patch.object(main.asyncio, "run"),
        ):
            main.main()

        run_game.assert_called_once_with(18, dry_run=True)


if __name__ == "__main__":
    unittest.main()
