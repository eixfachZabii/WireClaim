from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence

from src.api import submit_prices
from src.data.models import ItemPrice
from src.services.strategies import STRATEGY_PRIORITIES
from src.timing import log_timing, start_timer

logger = logging.getLogger(__name__)
Submitter = Callable[..., object]
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
WHITE = "\033[97m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BLUE = "\033[94m"


def _paint(value: object, *styles: str) -> str:
    return f"{''.join(styles)}{value}{RESET}"


def _format_field(label: str, value: object, color: str = WHITE) -> str:
    return f"{_paint(label + ':', DIM)} {_paint(value, BOLD, color)}"


def _format_price_comparison(
    before: Sequence[ItemPrice] | None, after: Sequence[ItemPrice]
) -> list[str]:
    before_by_index = {} if before is None else {price.index: price for price in before}
    after_by_index = {price.index: price for price in after}
    before_count = "none" if before is None else str(len(before))
    divider = _paint("||", BOLD, WHITE)
    lines = [
        f"{_paint(f'BEFORE (last successful post; line_items: {before_count})', BOLD, YELLOW)} "
        f"{divider} {_paint(f'AFTER (posting now; line_items: {len(after)})', BOLD, GREEN)}",
        f"{_paint('line |       charge |        limit', YELLOW)} {divider} "
        f"{_paint('line |       charge |        limit', GREEN)}",
        _paint("-----+--------------+-------------- || -----+--------------+--------------", DIM),
    ]
    for index in sorted(before_by_index.keys() | after_by_index.keys()):
        before_price = before_by_index.get(index)
        after_price = after_by_index.get(index)
        before_row = (
            "     |              |             "
            if before_price is None
            else f"{before_price.index:>4} | {before_price.charge_price:>12.2f} | "
            f"{before_price.acceptance_limit:>12.2f}"
        )
        after_row = (
            "     |              |             "
            if after_price is None
            else f"{after_price.index:>4} | {after_price.charge_price:>12.2f} | "
            f"{after_price.acceptance_limit:>12.2f}"
        )
        lines.append(f"{_paint(before_row, YELLOW)} {divider} {_paint(after_row, GREEN)}")
    return lines


def _submission_values(price: ItemPrice | None) -> tuple[float, float] | None:
    return None if price is None else (price.charge_price, price.acceptance_limit)


def _changed_indices(
    before: Sequence[ItemPrice] | None, after: Sequence[ItemPrice]
) -> set[int]:
    before_by_index = {} if before is None else {price.index: price for price in before}
    after_by_index = {price.index: price for price in after}
    return {
        index
        for index in before_by_index.keys() | after_by_index.keys()
        if (
            _submission_values(before_by_index.get(index))
            != _submission_values(after_by_index.get(index))
        )
    }


def _format_write_status(
    before: Sequence[ItemPrice] | None, after: Sequence[ItemPrice], reason: str, force: bool
) -> tuple[str, str, str, str]:
    changed = _changed_indices(before, after)
    if before is None:
        return "INITIAL SAFETY POST", "first submission", BLUE, BLUE
    if not changed:
        status = "UNCHANGED — FORCED REPOST" if force else "UNCHANGED"
        return status, "no Line Item values changed", YELLOW, DIM
    status = f"NEW SNAPSHOT ({len(changed)} Line Items changed)"
    kind, separator, source = reason.partition(":")
    if kind == "strategy" and separator:
        priority = STRATEGY_PRIORITIES.get(source, 0)
        before_by_index = {price.index: price for price in before}
        previous_priority = max(
            (STRATEGY_PRIORITIES.get(before_by_index[index].source, 0) for index in changed if index in before_by_index),
            default=0,
        )
        comparison = "HIGHER" if priority > previous_priority else "EQUAL" if priority == previous_priority else "LOWER"
        return status, f"{comparison} — accepted ({priority} vs {previous_priority})", GREEN, MAGENTA
    if reason == "fraud":
        return status, "FRAUD LOCKS override pricing", GREEN, RED
    if kind == "fast_path" and separator:
        return status, "FAST PATH update", GREEN, CYAN
    if reason == "case_loaded":
        return status, "CASE LOADED baseline", GREEN, BLUE
    return status, "baseline update", GREEN, WHITE


def format_submission_update(
    game_id: int,
    sequence: int,
    reason: str,
    force: bool,
    before: Sequence[ItemPrice] | None,
    after: Sequence[ItemPrice],
    elapsed_s: float = 0.0,
    remaining_s: float = 0.0,
    fraud_indices: frozenset[int] = frozenset(),
) -> str:
    kind, separator, source = reason.partition(":")
    if kind == "strategy" and separator:
        phase = f"STRATEGY {source.removeprefix('strategy')}"
        priority, phase_color = str(STRATEGY_PRIORITIES.get(source, 0)), MAGENTA
    elif kind == "fast_path" and separator:
        phase, source, priority, phase_color = "FAST PATH", "fast lane", "fast", CYAN
    elif reason == "fraud":
        phase, source, priority, phase_color = "FRAUD LOCKS", "fraud locks", "n/a", RED
    elif reason == "case_loaded":
        phase, source, priority, phase_color = "CASE LOADED", "standard", "baseline", BLUE
    elif reason == "standard":
        phase, source, priority, phase_color = "STANDARD", "standard", "baseline", BLUE
    else:
        phase, source, priority, phase_color = "UPDATE", "update", "n/a", WHITE
    write_status, priority_decision, write_color, decision_color = _format_write_status(
        before, after, reason, force
    )
    banner = f"{'#' * 28} {phase} {'#' * 28}"
    lines = [
        f"\n\n\n\n\n{_paint(banner, BOLD, phase_color)}",
        "",
        _paint("POST UPDATE", BOLD, WHITE),
        "",
        _format_field("game", game_id),
        _format_field("sequence", sequence),
        _format_field("time", f"T+{elapsed_s:.2f}s | {remaining_s:.2f}s remaining", CYAN),
        _format_field("source", source, phase_color),
        _format_field("priority", priority, phase_color),
        _format_field("reason", reason, WHITE),
        _format_field("write", write_status, write_color),
        _format_field("priority_decision", priority_decision, decision_color),
        _format_field("force", force, YELLOW if force else DIM),
    ]
    if fraud_indices:
        lines.append(
            _format_field("fraud_locks", f"{sorted(fraud_indices)} -> Limit=0.00 enforced", RED)
        )
    lines.extend(("", ""))
    lines.extend(_format_price_comparison(before, after))
    lines.extend(("", _paint("-" * 72, DIM)))
    return "\n".join(lines)


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
        self._submitted: tuple[ItemPrice, ...] | None = None
        self._submitted_signature: tuple[tuple[int, float, float], ...] | None = None
        self._pending_force = False
        self._pending_reason = "initial"
        self._pending_fraud_indices = frozenset()
        self._submission_sequence = 0
        self._started_at: float | None = None
        self._worker: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        if self._worker is None:
            self._started_at = asyncio.get_running_loop().time()
            self._worker = asyncio.create_task(self._run())

    def publish(
        self,
        prices: Sequence[ItemPrice],
        reason: str = "update",
        force: bool = False,
        fraud_indices: frozenset[int] = frozenset(),
    ) -> bool:
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
        self._pending_fraud_indices = fraud_indices
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
            now = loop.time()
            remaining = self._deadline - now
            if remaining <= 0:
                self._idle.set()
                return
            before = self._submitted
            snapshot = self._pending
            signature = self._pending_signature
            started_at = self._started_at if self._started_at is not None else now
            elapsed_s = now - started_at
            force_submission = self._pending_force
            reason = self._pending_reason
            fraud_indices = self._pending_fraud_indices
            self._pending_force = False
            self._submission_sequence += 1
            sequence = self._submission_sequence
            submission_started_at = start_timer()
            logger.info(
                "%s",
                format_submission_update(
                    self._game_id,
                    sequence,
                    reason,
                    force_submission,
                    before,
                    snapshot,
                    elapsed_s,
                    remaining,
                    fraud_indices,
                ),
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
                self._submitted = snapshot
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
