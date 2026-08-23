from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Awaitable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.api import list_games, warm_llm_resources
from src.data.case_loader import load_case
from src.data.models import CaseData, FraudDecision, ItemPrice, Proposal
from src.evidence.fraud_detection import detect_fraud
from src.strategies.router import STRATEGY_PRIORITIES, StrategyRouter
from src.strategies.fast_path import (
    LLM_TIMEOUT_SECONDS,
    STANDARD_CHARGE,
    STANDARD_LIMIT,
    llm_values,
    standard_values,
)
from src.runtime.submission_coordinator import SubmissionCoordinator
from src.runtime.timing import format_error_card, log_timing, start_timer

logger = logging.getLogger(__name__)
RUN_SECONDS = 60.0


def _recovery_action(kind: str) -> str:
    if kind == "fast_path":
        return (
            f"Fast Path exceeded its {LLM_TIMEOUT_SECONDS:.0f}s request timeout; "
            "the current batch stays active while Strategies continue."
        )
    if kind == "fraud":
        return "Fraud locks remain unchanged; the current batch stays active."
    return "This result was skipped; the current batch stays active."


@dataclass(frozen=True)
class RunEvent:
    kind: str
    value: Proposal | FraudDecision


class RunManager:
    def __init__(self, standard: Proposal) -> None:
        if standard.is_empty:
            raise ValueError("Standard values must cover at least one Line Item.")
        self._standard = standard
        self._fast_path: Proposal | None = None
        self._strategy: dict[int, tuple[int, ItemPrice]] = {}
        self._fraud_indices: set[int] = set()

    def set_fast_path(self, proposal: Proposal) -> bool:
        if proposal.is_empty:
            return False
        self._fast_path = proposal
        return True

    def set_strategy(self, proposal: Proposal) -> bool:
        """Merge a Strategy's prices **per Line Item**, keeping the best source per index.

        A Proposal need not cover the whole Case. A 39-item Case cannot be priced by one
        model call inside 60 seconds, so a Strategy is free to publish each Line Item as
        its estimate lands and a slow item then costs one item rather than the whole
        Submission. Swapping the layer wholesale, which this did before, discarded every
        earlier item the moment a partial arrived.

        Ties go to the newer price so a Strategy can revise its own answer, but a
        lower-priority Strategy cannot overwrite an index a higher one has already priced.
        """
        if proposal.is_empty:
            return False
        priority = STRATEGY_PRIORITIES.get(proposal.source, 0)
        changed = False
        for index, price in proposal.by_index().items():
            current = self._strategy.get(index)
            if current is not None and (current[0] > priority or current[1] == price):
                continue
            self._strategy[index] = (priority, price)
            changed = True
        return changed

    def apply_fraud(self, decision: FraudDecision) -> bool:
        current = self._fraud_indices.copy()
        self._fraud_indices.update(decision.fraud_indices)
        return current != self._fraud_indices

    @property
    def fraud_indices(self) -> frozenset[int]:
        return frozenset(self._fraud_indices)

    def snapshot(self) -> tuple[ItemPrice, ...]:
        prices = self._standard.by_index()
        valid_indices = set(prices)
        if self._fast_path is not None:
            prices.update(
                (index, price)
                for index, price in self._fast_path.by_index().items()
                if index in valid_indices
            )
        prices.update(
            (index, price)
            for index, (_, price) in self._strategy.items()
            if index in valid_indices
        )
        return tuple(
            price.with_limit(0.0) if index in self._fraud_indices else price
            for index, price in sorted(prices.items())
        )


#: How many Line Items the blind floor covers. Invoices in the settled record run to 39
#: positions, so this is the observed maximum plus one. An index past the real Line Item
#: count creates no Transaction and costs nothing; a *missing* index is what costs.
BLIND_LINE_ITEMS = 40


def blind_floor() -> tuple[ItemPrice, ...]:
    """Something to submit before we know anything at all -- even the Line Item count.

    Published before the key fetch, so the window is never empty. If the Case then loads,
    the real prices overwrite these within a second and this costs exactly nothing
    (submission is an upsert, last write wins). If the Case does *not* load, this is the
    difference between a bad submission and no submission.

    That difference is not small. The API handbook is explicit: "Omitted line items use the
    game defaults of charge_price = 0 and acceptance_limit = 0. They still participate in
    transactions; omitting a line does not opt the team out of it." So silence is not
    abstention -- it is `a = 0, b = 0`, which earns nothing and wrongfully rejects every
    fair claim at 1.5x (CLAUDE.md rule 1, README R7). Games 10-12 paid a combined 139,904
    to establish this, which is why `b5ba5dc` added this function.

    It was then deleted by `9b5ee55`, a 112-line refactor whose message does not mention it
    -- collateral, not a decision. Two tests were written in the same commit to match the new
    behaviour, so nothing recorded that a safety net had been removed, and it stayed gone for
    twenty Games until a documentation audit noticed the docs still described it.
    """
    return tuple(
        ItemPrice(
            index=index,
            charge_price=STANDARD_CHARGE,
            acceptance_limit=STANDARD_LIMIT,
            source="blind_floor",
        )
        for index in range(1, BLIND_LINE_ITEMS + 1)
    )


def dry_run_submit(game_id: int, submissions: list[dict[str, float | int]], timeout: float) -> list[dict]:
    return []


async def run_game(
    game_id: int, dry_run: bool = False, run_seconds: float = RUN_SECONDS
) -> None:
    run_started_at = start_timer()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + run_seconds
    coordinator = (
        SubmissionCoordinator(game_id, deadline, submitter=dry_run_submit)
        if dry_run
        else SubmissionCoordinator(game_id, deadline)
    )
    await coordinator.start()
    # Before the key fetch, so that a Case which never loads still submits something.
    coordinator.publish(blind_floor())

    case_load_started_at = start_timer()
    try:
        remaining = deadline - loop.time()
        if remaining <= 0:
            await coordinator.close()
            return
        case = await asyncio.wait_for(load_case(game_id, deadline), timeout=remaining)
    except Exception as error:
        logger.error("Game %s could not be loaded: %s - blind floor stands.", game_id, error)
        log_timing(logger, "case_load", case_load_started_at, "failed", game=game_id)
        with suppress(TimeoutError):
            await asyncio.wait_for(coordinator.wait_until_idle(), timeout=max(deadline - loop.time(), 0.0))
        await coordinator.close()
        log_timing(logger, "game", run_started_at, "failed", game=game_id, dry_run=dry_run)
        return
    log_timing(logger, "case_load", case_load_started_at, game=game_id)
    if loop.time() >= deadline:
        logger.error("Game %s finished loading after its submission window.", game_id)
        await coordinator.close()
        log_timing(logger, "game", run_started_at, "expired", game=game_id, dry_run=dry_run)
        return

    manager = RunManager(standard_values(case))
    events: asyncio.Queue[RunEvent] = asyncio.Queue()
    router = StrategyRouter()
    try:
        warm_llm_resources()
    except Exception as error:
        logger.warning("Could not warm OpenAI resources: %s", error)
    coordinator.publish(
        manager.snapshot(),
        reason="case_loaded",
        fraud_indices=manager.fraud_indices,
    )
    tasks = [
        asyncio.create_task(_emit_result(events, "fast_path", llm_values(case), game_id)),
        asyncio.create_task(_emit_result(events, "fraud", detect_fraud(case), game_id)),
        asyncio.create_task(_forward_strategies(events, router, case, deadline)),
    ]
    try:
        while loop.time() < deadline:
            if all(task.done() for task in tasks) and events.empty():
                try:
                    await asyncio.wait_for(
                        coordinator.wait_until_idle(),
                        timeout=deadline - loop.time(),
                    )
                except TimeoutError:
                    pass
                break
            try:
                event = await asyncio.wait_for(events.get(), timeout=deadline - loop.time())
            except TimeoutError:
                break
            changed = _apply_event(manager, event)
            reason = f"{event.kind}:{event.value.source}" if isinstance(event.value, Proposal) else event.kind
            logger.info(
                "event_received game=%s kind=%s reason=%s changed=%s",
                game_id,
                event.kind,
                reason,
                changed,
            )
            if changed:
                coordinator.publish(
                    manager.snapshot(),
                    reason=reason,
                    fraud_indices=manager.fraud_indices,
                )
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await coordinator.close()
        log_timing(logger, "game", run_started_at, game=game_id, dry_run=dry_run)


async def _emit_result(
    events: asyncio.Queue[RunEvent],
    kind: str,
    operation: Awaitable[Proposal | FraudDecision | None],
    game_id: int,
) -> None:
    started_at = start_timer()
    try:
        result = await operation
    except asyncio.CancelledError:
        log_timing(logger, kind, started_at, "cancelled", game=game_id)
        raise
    except Exception as error:
        logger.error(
            "%s",
            format_error_card(
                kind,
                error,
                game_id,
                _recovery_action(kind),
                elapsed_s=start_timer() - started_at,
            ),
        )
        log_timing(logger, kind, started_at, "failed", game=game_id)
        return
    log_timing(logger, kind, started_at, game=game_id, produced=result is not None)
    if result is not None:
        await events.put(RunEvent(kind, result))


async def _forward_strategies(
    events: asyncio.Queue[RunEvent],
    router: StrategyRouter,
    case: CaseData,
    deadline: float,
) -> None:
    started_at = start_timer()
    try:
        async for proposal in router.start_strategies(case, deadline):
            log_timing(logger, "strategy_result", started_at, game=case.game_id, source=proposal.source)
            await events.put(RunEvent("strategy", proposal))
    finally:
        log_timing(logger, "strategy_manager", started_at, game=case.game_id)


def _apply_event(manager: RunManager, event: RunEvent) -> bool:
    if event.kind == "fast_path" and isinstance(event.value, Proposal):
        return manager.set_fast_path(event.value)
    if event.kind == "strategy" and isinstance(event.value, Proposal):
        return manager.set_strategy(event.value)
    if event.kind == "fraud" and isinstance(event.value, FraudDecision):
        return manager.apply_fraud(event.value)
    raise ValueError(f"Unsupported RunEvent: {event.kind}")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def game_duration(game: dict) -> float:
    try:
        duration = float(game.get("duration_seconds", RUN_SECONDS))
    except (TypeError, ValueError):
        return RUN_SECONDS
    return duration if duration > 0 else RUN_SECONDS


async def retry_expired_games(now: datetime | None = None) -> None:
    games = sorted(
        await asyncio.to_thread(list_games),
        key=lambda game: parse_time(str(game["start_time"])),
    )
    reference_time = now or datetime.now(timezone.utc)
    for game in games:
        start_time = parse_time(str(game["start_time"]))
        duration = game_duration(game)
        if start_time + timedelta(seconds=duration) > reference_time:
            logger.info("Stopping dry retry before Game %s at %s.", game["id"], start_time.isoformat())
            return
        logger.info("\n\n\n################ CASE %s ##################\n\n\n", game["id"])
        logger.info("Dry retry for expired Game %s.", game["id"])
        if duration == RUN_SECONDS:
            await run_game(int(game["id"]), dry_run=True)
        else:
            await run_game(int(game["id"]), dry_run=True, run_seconds=duration)


async def watch_games() -> None:
    games = sorted(
        await asyncio.to_thread(list_games),
        key=lambda game: parse_time(str(game["start_time"])),
    )
    logger.info("Loaded %s scheduled Games.", len(games))
    for game in games:
        game_id = int(game["id"])
        start_time = parse_time(str(game["start_time"]))
        duration = game_duration(game)
        now = datetime.now(timezone.utc)
        if start_time + timedelta(seconds=duration) <= now:
            continue
        wait_seconds = (start_time - now).total_seconds()
        if wait_seconds > 0:
            logger.info("Game %s starts at %s.", game_id, start_time.isoformat())
            await asyncio.sleep(wait_seconds)
        if duration == RUN_SECONDS:
            await run_game(game_id)
        else:
            await run_game(game_id, run_seconds=duration)


def main() -> None:
    parser = argparse.ArgumentParser(description="WireClaim Game runner")
    parser.add_argument("--game-id", type=int, help="Process one Game immediately.")
    parser.add_argument(
        "--retry-dry",
        "--retry_dry",
        dest="retry_dry",
        action="store_true",
        help="Run expired Games in order and print submissions without posting them.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for http_logger in ("httpx", "httpx2", "httpcore", "httpcore2"):
        logging.getLogger(http_logger).setLevel(logging.WARNING)
    try:
        if args.game_id is not None:
            asyncio.run(run_game(args.game_id, dry_run=args.retry_dry))
        elif args.retry_dry:
            asyncio.run(retry_expired_games())
        else:
            asyncio.run(watch_games())
    except KeyboardInterrupt:
        logger.info("Stopping WireClaim runner.")


if __name__ == "__main__":
    main()
