import argparse
import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
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


class FairValueReferenceTests(unittest.TestCase):
    def test_loads_the_matching_game_and_preserves_its_identified_sets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            study = Path(directory) / "fair_value_study.json"
            study.write_text(
                """{
                  "games": [
                    {"game_id": 18, "line_items": [{"index": 1, "fair_value": {"lower": 10, "upper": {"value": null, "relation": null}}}]},
                    {"game_id": 19, "line_items": [
                      {"index": 1, "fair_value": {"lower": 122.94, "upper": {"value": null, "relation": null}}},
                      {"index": 2, "fair_value": {"lower": 200, "upper": {"value": 300, "relation": "lt"}}}
                    ]}
                  ]
                }""",
                encoding="utf-8",
            )
            with patch.object(main, "FAIR_VALUE_STUDY_PATH", study):
                references = main.load_fair_value_references(19)

        self.assertEqual(references[1].lower, 122.94)
        self.assertEqual(references[1].interval(), "[122.94, ∞)")
        self.assertEqual(references[2].interval(), "[200.00, 300.00)")

    def test_returns_no_references_when_the_study_has_no_matching_game(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            study = Path(directory) / "fair_value_study.json"
            study.write_text('{"games": [{"game_id": 18, "line_items": []}]}', encoding="utf-8")
            with patch.object(main, "FAIR_VALUE_STUDY_PATH", study):
                references = main.load_fair_value_references(19)

        self.assertEqual(references, {})


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

    async def test_a_case_that_never_loads_does_not_submit_unknown_indices(self) -> None:
        submitter = Mock(return_value=[])
        with (
            patch.object(main, "load_case", side_effect=RuntimeError("no key")),
            patch.object(main, "dry_run_submit", submitter),
        ):
            await main.run_game(99, dry_run=True)

        submitter.assert_not_called()

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
            patch.object(main, "llm_values", new=AsyncMock(return_value=None)) as fast_path,
            patch.object(main, "detect_fraud", new=AsyncMock(return_value=FraudDecision())),
            patch.object(main, "_forward_strategies", new=AsyncMock(return_value=None)),
            patch.object(main, "dry_run_submit", submitter),
        ):
            await main.run_game(99, dry_run=True)

        fast_path.assert_not_awaited()
        self.assertEqual(submitter.call_count, 1)
        first_submissions = submitter.call_args.args[1]
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


class ExecutorCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_executor_is_shutdown_when_the_operation_is_cancelled(self) -> None:
        loop = Mock()
        loop.shutdown_default_executor = AsyncMock()

        async def cancelled() -> None:
            raise asyncio.CancelledError

        with patch.object(main.asyncio, "get_running_loop", return_value=loop):
            with self.assertRaises(asyncio.CancelledError):
                await main._run_with_executor_cleanup(cancelled())

        loop.shutdown_default_executor.assert_awaited_once_with()


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
