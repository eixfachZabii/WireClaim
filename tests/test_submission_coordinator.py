import asyncio
import threading
import unittest

from src.data.models import ItemPrice
from src.services.submission_coordinator import SubmissionCoordinator


class SubmissionCoordinatorTests(unittest.IsolatedAsyncioTestCase):
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
