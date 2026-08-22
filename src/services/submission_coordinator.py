from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence

from src.api import submit_prices
from src.data.models import ItemPrice
from src.timing import log_timing, start_timer

logger = logging.getLogger(__name__)
Submitter = Callable[..., object]


class SubmissionCoordinator:
    def __init__(self, game_id: int, deadline: float, submitter: Submitter = submit_prices) -> None:
        self._game_id = game_id
        self._deadline = deadline
        self._submitter = submitter
        self._changed = asyncio.Event()
        self._idle = asyncio.Event()
        self._idle.set()
        self._pending: tuple[ItemPrice, ...] | None = None
        self._pending_signature: tuple[tuple[int, float, float], ...] | None = None
        self._submitted_signature: tuple[tuple[int, float, float], ...] | None = None
        self._pending_force = False
        self._pending_reason = "initial"
        self._submission_sequence = 0
        self._worker: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run())

    def publish(self, prices: Sequence[ItemPrice], reason: str = "update", force: bool = False) -> bool:
        snapshot = tuple(sorted(prices, key=lambda price: price.index))
        signature = tuple(
            (price.index, price.charge_price, price.acceptance_limit) for price in snapshot
        )
        if self._closed or not snapshot or (not force and signature == self._pending_signature):
            return False
        self._pending = snapshot
        self._pending_signature = signature
        self._pending_force = self._pending_force or force
        self._pending_reason = reason
        self._idle.clear()
        self._changed.set()
        return True

    async def wait_until_idle(self) -> None:
        await self._idle.wait()

    async def close(self) -> None:
        self._closed = True
        self._idle.set()
        self._changed.set()
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            await self._changed.wait()
            self._changed.clear()
            if self._closed:
                return
            if self._pending is None or (
                self._pending_signature == self._submitted_signature and not self._pending_force
            ):
                self._idle.set()
                continue
            remaining = self._deadline - loop.time()
            if remaining <= 0:
                self._idle.set()
                return
            snapshot = self._pending
            signature = self._pending_signature
            force_submission = self._pending_force
            reason = self._pending_reason
            self._pending_force = False
            self._submission_sequence += 1
            sequence = self._submission_sequence
            submission_started_at = start_timer()
            logger.info(
                "submission_dispatch game=%s sequence=%s reason=%s force=%s line_items=%s",
                self._game_id,
                sequence,
                reason,
                force_submission,
                len(snapshot),
            )
            try:
                await asyncio.to_thread(
                    self._submitter,
                    self._game_id,
                    [price.to_submission_dict() for price in snapshot],
                    timeout=remaining,
                )
            except Exception as error:
                logger.warning("Submission for Game %s failed: %s", self._game_id, error)
                log_timing(
                    logger,
                    "submission",
                    submission_started_at,
                    "failed",
                    game=self._game_id,
                    line_items=len(snapshot),
                    sequence=sequence,
                    reason=reason,
                )
            else:
                self._submitted_signature = signature
                logger.info(
                    "Posted %s Line Items for Game %s (sequence=%s reason=%s).",
                    len(snapshot),
                    self._game_id,
                    sequence,
                    reason,
                )
                log_timing(
                    logger,
                    "submission",
                    submission_started_at,
                    game=self._game_id,
                    line_items=len(snapshot),
                    sequence=sequence,
                    reason=reason,
                )
            if not self._closed and (
                self._pending_signature != signature or self._pending_force
            ):
                self._changed.set()
            else:
                self._idle.set()
