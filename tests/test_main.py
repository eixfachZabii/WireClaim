import argparse
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import main
from main import RunManager
from src.data.models import FraudDecision, ItemPrice, Proposal


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

        self.assertEqual((prices[1].charge_price, prices[1].acceptance_limit), (130.0, 95.0))
        self.assertEqual((prices[2].charge_price, prices[2].acceptance_limit), (300.0, 0.0))

    def test_strategy_keeps_priority_when_fast_path_finishes_later(self) -> None:
        self.manager.set_strategy(proposal("strategy1", [(1, 120.0, 90.0)]))
        self.manager.set_fast_path(proposal("fast_path_llm", [(1, 110.0, 80.0)]))

        prices = {price.index: price for price in self.manager.snapshot()}

        self.assertEqual((prices[1].charge_price, prices[1].acceptance_limit), (120.0, 90.0))

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

    async def test_a_case_that_never_loads_still_submits_a_floor(self) -> None:
        """Games 11 and 12 submitted nothing and scored the (0, 0) default: -36,017 and
        -43,381, identical to the teams that never showed up. A Case that fails to load
        must still leave a non-zero Charge and a non-zero Limit on the board."""
        with patch.object(main, "load_case", side_effect=RuntimeError("no key")):
            with self.assertLogs("main", level="INFO") as logs:
                await main.run_game(99, dry_run=True)

        payloads = [line for line in logs.output if "DRY RUN SUBMISSION" in line]
        self.assertTrue(payloads, "a failed Case load must still publish a Submission")
        self.assertIn("PUT /api/games/99/submissions", payloads[0])
        self.assertNotIn('"charge_price": 0.0', payloads[0])
        self.assertNotIn('"acceptance_limit": 0.0', payloads[0])

    def test_blind_floor_covers_every_index_a_case_might_use(self) -> None:
        floor = main.blind_floor()

        self.assertEqual([price.index for price in floor], list(range(1, 9)))
        for price in floor:
            self.assertGreater(price.charge_price, 0.0)
            self.assertGreater(price.acceptance_limit, 0.0)

    def test_dry_submit_logs_payload_without_api_call(self) -> None:
        submissions = [{"index": 1, "charge_price": 150.0, "acceptance_limit": 75.0}]

        with self.assertLogs("main", level="INFO") as logs:
            result = main.dry_run_submit(7, submissions, timeout=1.0)

        self.assertEqual(result, [])
        self.assertIn("DRY RUN SUBMISSION", logs.output[0])
        self.assertIn("PUT /api/games/7/submissions", logs.output[0])
        self.assertIn("tournament API was not called", logs.output[0])
        self.assertIn("1 |       150.00 |        75.00", logs.output[0])
        self.assertIn('"charge_price": 150.0', logs.output[0])


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


if __name__ == "__main__":
    unittest.main()
