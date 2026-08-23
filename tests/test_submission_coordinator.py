import asyncio
import re
import threading
import unittest

from src.data.models import ItemPrice
from src.runtime.submission_coordinator import SubmissionCoordinator, format_submission_update

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def strip_ansi(value: str) -> str:
    return ANSI_ESCAPE.sub("", value)


class SubmissionCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def test_formats_a_complete_strategy_batch_update(self) -> None:
        update = format_submission_update(
            game_id=19,
            sequence=4,
            reason="strategy:strategy3",
            force=False,
            before=(ItemPrice(1, 250.0, 35.0), ItemPrice(2, 350.0, 35.0)),
            after=(ItemPrice(1, 300.0, 35.0), ItemPrice(2, 400.0, 0.0)),
            elapsed_s=23.45,
            remaining_s=36.55,
        )

        plain_update = strip_ansi(update)

        self.assertIn("\033[", update)
        self.assertTrue(
            plain_update.startswith("\n\n\n\n\n############################ STRATEGY 3 ############################")
        )
        self.assertIn("time: T+23.45s | 36.55s remaining", plain_update)
        self.assertIn("source: strategy3", plain_update)
        self.assertIn("priority: 2", plain_update)
        self.assertIn("write: NEW SNAPSHOT (2 Line Items changed)", plain_update)
        self.assertIn("priority_decision: HIGHER — accepted (2 vs 0)", plain_update)
        self.assertIn(
            "BEFORE (last successful post; line_items: 2) || AFTER (posting now; line_items: 2)",
            plain_update,
        )
        self.assertIn(
            "   1 |       250.00 |        35.00 ||    1 |       300.00 |        35.00",
            plain_update,
        )
        self.assertIn(
            "   2 |       350.00 |        35.00 ||    2 |       400.00 |         0.00",
            plain_update,
        )
        self.assertTrue(plain_update.endswith("-" * 72))

    def test_formats_an_unchanged_forced_repost(self) -> None:
        prices = (ItemPrice(1, 300.0, 35.0),)
        update = format_submission_update(
            game_id=19,
            sequence=3,
            reason="fraud",
            force=True,
            before=prices,
            after=prices,
            fraud_indices=frozenset({1}),
        )
        plain_update = strip_ansi(update)

        self.assertIn("write: UNCHANGED — FORCED REPOST", plain_update)
        self.assertIn("priority_decision: no Line Item values changed", plain_update)
        self.assertIn("fraud_locks: [1] -> Limit=0.00 enforced", plain_update)

    def test_formats_phase_banners(self) -> None:
        for reason, banner in (
            ("fast_path:fast_path_llm", "FAST PATH"),
            ("fraud", "FRAUD LOCKS"),
            ("case_loaded", "CASE LOADED"),
        ):
            with self.subTest(reason=reason):
                update = format_submission_update(
                    game_id=19,
                    sequence=1,
                    reason=reason,
                    force=False,
                    before=None,
                    after=(ItemPrice(1, 300.0, 35.0),),
                )

                self.assertIn(f"{'#' * 28} {banner} {'#' * 28}", strip_ansi(update))

    def test_formats_missing_previous_submission(self) -> None:
        update = format_submission_update(
            game_id=19,
            sequence=1,
            reason="standard",
            force=False,
            before=None,
            after=(ItemPrice(1, 300.0, 35.0),),
        )

        plain_update = strip_ansi(update)

        self.assertIn(
            "BEFORE (last successful post; line_items: none) || AFTER (posting now; line_items: 1)",
            plain_update,
        )
        self.assertIn("||    1 |       300.00 |        35.00", plain_update)

    async def test_logs_last_successful_snapshot_before_posting_an_update(self) -> None:
        def submitter(game_id: int, submissions: list[dict[str, float | int]], timeout: float) -> None:
            return None

        coordinator = SubmissionCoordinator(
            game_id=1,
            deadline=asyncio.get_running_loop().time() + 1.0,
            submitter=submitter,
        )
        first = (ItemPrice(1, 100.0, 75.0),)
        second = (ItemPrice(1, 120.0, 0.0),)
        with self.assertLogs("src.runtime.submission_coordinator", level="INFO") as logs:
            await coordinator.start()
            coordinator.publish(first, reason="standard")
            await asyncio.wait_for(coordinator.wait_until_idle(), timeout=0.5)
            coordinator.publish(second, reason="strategy:strategy2")
            await asyncio.wait_for(coordinator.wait_until_idle(), timeout=0.5)
        await coordinator.close()

        updates = [strip_ansi(line) for line in logs.output if "POST UPDATE" in line]
        self.assertEqual(len(updates), 2)
        self.assertIn(
            "BEFORE (last successful post; line_items: none) || AFTER (posting now; line_items: 1)",
            updates[0],
        )
        self.assertIn(
            "BEFORE (last successful post; line_items: 1) || AFTER (posting now; line_items: 1)",
            updates[1],
        )
        self.assertIn(
            "   1 |       100.00 |        75.00 ||    1 |       120.00 |         0.00",
            updates[1],
        )
        self.assertIn("priority: 4", updates[1])

    async def test_new_snapshot_follows_inflight_submission(self) -> None:
        calls: list[list[dict[str, float | int]]] = []
        first_started = threading.Event()
        release_first = threading.Event()

        def submitter(game_id: int, submissions: list[dict[str, float | int]], timeout: float) -> None:
            calls.append(submissions)
            if len(calls) == 1:
                first_started.set()
                release_first.wait(timeout=timeout)

        coordinator = SubmissionCoordinator(
            game_id=1,
            deadline=asyncio.get_running_loop().time() + 1.0,
            submitter=submitter,
        )
        await coordinator.start()
        coordinator.publish((ItemPrice(1, 100.0, 75.0),))
        await asyncio.to_thread(first_started.wait, 0.5)
        coordinator.publish((ItemPrice(1, 120.0, 0.0),))
        release_first.set()
        await asyncio.wait_for(coordinator.wait_until_idle(), timeout=0.5)
        await coordinator.close()

        self.assertEqual(calls[0][0]["acceptance_limit"], 75.0)
        self.assertEqual(calls[1][0]["acceptance_limit"], 0.0)

    async def test_restores_a_previously_sent_snapshot_after_an_inflight_update(self) -> None:
        calls: list[list[dict[str, float | int]]] = []
        first_started = threading.Event()
        second_started = threading.Event()
        release_first = threading.Event()
        release_second = threading.Event()

        def submitter(game_id: int, submissions: list[dict[str, float | int]], timeout: float) -> None:
            calls.append(submissions)
            if len(calls) == 1:
                first_started.set()
                release_first.wait(timeout=timeout)
            elif len(calls) == 2:
                second_started.set()
                release_second.wait(timeout=timeout)

        coordinator = SubmissionCoordinator(
            game_id=1,
            deadline=asyncio.get_running_loop().time() + 1.0,
            submitter=submitter,
        )
        await coordinator.start()
        coordinator.publish((ItemPrice(1, 100.0, 75.0),))
        await asyncio.to_thread(first_started.wait, 0.5)
        coordinator.publish((ItemPrice(1, 120.0, 90.0),))
        release_first.set()
        await asyncio.to_thread(second_started.wait, 0.5)
        coordinator.publish((ItemPrice(1, 100.0, 75.0),))
        release_second.set()
        await asyncio.wait_for(coordinator.wait_until_idle(), timeout=0.5)
        await coordinator.close()

        self.assertEqual([call[0]["charge_price"] for call in calls], [100.0, 120.0, 100.0])


    async def test_posts_a_complete_snapshot_in_one_batch(self) -> None:
        calls: list[list[dict[str, float | int]]] = []

        def submitter(game_id: int, submissions: list[dict[str, float | int]], timeout: float) -> None:
            calls.append(submissions)

        coordinator = SubmissionCoordinator(
            game_id=1,
            deadline=asyncio.get_running_loop().time() + 1.0,
            submitter=submitter,
        )
        prices = (ItemPrice(1, 100.0, 35.0), ItemPrice(2, 200.0, 0.0))
        await coordinator.start()
        coordinator.publish(prices)
        await asyncio.wait_for(coordinator.wait_until_idle(), timeout=0.5)
        await coordinator.close()

        self.assertEqual(calls, [[price.to_submission_dict() for price in prices]])

    async def test_force_reposts_an_unchanged_snapshot(self) -> None:
        calls: list[list[dict[str, float | int]]] = []

        def submitter(game_id: int, submissions: list[dict[str, float | int]], timeout: float) -> None:
            calls.append(submissions)

        coordinator = SubmissionCoordinator(
            game_id=1,
            deadline=asyncio.get_running_loop().time() + 1.0,
            submitter=submitter,
        )
        prices = (ItemPrice(1, 100.0, 75.0),)
        await coordinator.start()
        coordinator.publish(prices, reason="standard")
        await asyncio.wait_for(coordinator.wait_until_idle(), timeout=0.5)
        coordinator.publish(prices, reason="fraud", force=True)
        await asyncio.wait_for(coordinator.wait_until_idle(), timeout=0.5)
        await coordinator.close()

        self.assertEqual(calls, [[prices[0].to_submission_dict()], [prices[0].to_submission_dict()]])


if __name__ == "__main__":
    unittest.main()
