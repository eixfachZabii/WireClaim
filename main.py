from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import Awaitable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.api import list_games, warm_llm_resources
from src.data.case_loader import load_case
from src.data.models import CaseData, FraudDecision, ItemPrice, Proposal
from src.services.fraud_detection import detect_fraud
from src.services.strategy_router import StrategyRouter
from src.services.strategies.fast_path import (
    STANDARD_CHARGE,
    STANDARD_LIMIT,
    llm_values,
    standard_values,
)
from src.services.submission_coordinator import SubmissionCoordinator
from src.timing import log_timing, start_timer

logger = logging.getLogger(__name__)
RUN_SECONDS = 60.0


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
        self._strategy: Proposal | None = None
        self._fraud_indices: set[int] = set()

    def set_fast_path(self, proposal: Proposal) -> bool:
        if proposal.is_empty:
            return False
        self._fast_path = proposal
        return True

    def set_strategy(self, proposal: Proposal) -> bool:
        if proposal.is_empty:
            return False
        self._strategy = proposal
        return True

    def apply_fraud(self, decision: FraudDecision) -> bool:
        current = self._fraud_indices.copy()
        self._fraud_indices.update(decision.fraud_indices)
        return current != self._fraud_indices

    def snapshot(self) -> tuple[ItemPrice, ...]:
        prices = self._standard.by_index()
        valid_indices = set(prices)
        for proposal in (self._fast_path, self._strategy):
            if proposal is not None:
                prices.update(
                    (index, price)
                    for index, price in proposal.by_index().items()
                    if index in valid_indices
                )
        return tuple(
            price.with_limit(0.0) if index in self._fraud_indices else price
            for index, price in sorted(prices.items())
        )


# A Game with no Submission at all is not a zero: it is the (0, 0) default, which
# wrongfully rejects every fair claim at 1.5a and charges nothing. Games 11 and 12 went
# out that way and cost 36,017 and 43,381 -- scores identical to the teams that never
# showed up. So we publish a floor before loading anything, and only then start work.
#
# We cannot know the Line Item count before the Case loads, so we cover a fixed range.
# Settled Games 1-13 all carry 2-4 items (max index 4); 8 is generous headroom while
# keeping the payload small, and indices beyond the real count are accepted and ignored
# (verified against the test Game: PUT of indices 1-8 returned 200). Once the Case
# loads, RunManager.snapshot() drops anything outside its real indices.
BLIND_LINE_ITEMS = 8


def blind_floor() -> tuple[ItemPrice, ...]:
    return tuple(
        ItemPrice(
            index=index,
            charge_price=STANDARD_CHARGE,
            acceptance_limit=STANDARD_LIMIT,
            source="blind_floor",
        )
        for index in range(1, BLIND_LINE_ITEMS + 1)
    )


def format_dry_run_submission(game_id: int, submissions: list[dict[str, float | int]]) -> str:
    rows = [
        (
            int(submission["index"]),
            float(submission["charge_price"]),
            float(submission["acceptance_limit"]),
        )
        for submission in sorted(submissions, key=lambda item: int(item["index"]))
    ]
    lines = [
        "DRY RUN SUBMISSION",
        f"  at_utc: {datetime.now(timezone.utc).isoformat()}",
        f"  request: PUT /api/games/{game_id}/submissions",
        "  mode: simulated; tournament API was not called",
        f"  line_items: {len(rows)}",
        "  line |       charge |        limit",
        "  -----+--------------+--------------",
    ]
    lines.extend(f"  {index:>4} | {charge:>12.2f} | {limit:>12.2f}" for index, charge, limit in rows)
    lines.append(f"  payload: {json.dumps(submissions, ensure_ascii=False)}")
    return "\n".join(lines)


def dry_run_submit(game_id: int, submissions: list[dict[str, float | int]], timeout: float) -> list[dict]:
    logger.info("%s", format_dry_run_submission(game_id, submissions))
    return []


async def run_game(game_id: int, dry_run: bool = False) -> None:
    run_started_at = start_timer()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + RUN_SECONDS
    coordinator = (
        SubmissionCoordinator(game_id, deadline, submitter=dry_run_submit)
        if dry_run
        else SubmissionCoordinator(game_id, deadline)
    )
    await coordinator.start()
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
    coordinator.publish(manager.snapshot())
    tasks = [
        asyncio.create_task(_emit_result(events, "fast_path", llm_values(case), game_id)),
        asyncio.create_task(_emit_result(events, "fraud", detect_fraud(case), game_id)),
        asyncio.create_task(_forward_strategies(events, router, case)),
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
            if _apply_event(manager, event):
                coordinator.publish(manager.snapshot())
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
    except Exception:
        logger.exception("%s failed for Game %s.", kind, game_id)
        log_timing(logger, kind, started_at, "failed", game=game_id)
        return
    log_timing(logger, kind, started_at, game=game_id, produced=result is not None)
    if result is not None:
        await events.put(RunEvent(kind, result))


async def _forward_strategies(
    events: asyncio.Queue[RunEvent],
    router: StrategyRouter,
    case: CaseData,
) -> None:
    started_at = start_timer()
    try:
        async for proposal in router.start_strategies(case):
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


async def retry_expired_games(now: datetime | None = None) -> None:
    games = sorted(
        await asyncio.to_thread(list_games),
        key=lambda game: parse_time(str(game["start_time"])),
    )
    reference_time = now or datetime.now(timezone.utc)
    for game in games:
        start_time = parse_time(str(game["start_time"]))
        if start_time + timedelta(seconds=RUN_SECONDS) > reference_time:
            logger.info("Stopping dry retry before Game %s at %s.", game["id"], start_time.isoformat())
            return
        logger.info("Dry retry for expired Game %s.", game["id"])
        await run_game(int(game["id"]), dry_run=True)


async def watch_games() -> None:
    games = sorted(
        await asyncio.to_thread(list_games),
        key=lambda game: parse_time(str(game["start_time"])),
    )
    logger.info("Loaded %s scheduled Games.", len(games))
    for game in games:
        game_id = int(game["id"])
        start_time = parse_time(str(game["start_time"]))
        now = datetime.now(timezone.utc)
        if start_time + timedelta(seconds=RUN_SECONDS) <= now:
            continue
        wait_seconds = (start_time - now).total_seconds()
        if wait_seconds > 0:
            logger.info("Game %s starts at %s.", game_id, start_time.isoformat())
            await asyncio.sleep(wait_seconds)
        await run_game(game_id)


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
    if args.game_id is not None and args.retry_dry:
        parser.error("--game-id and --retry_dry cannot be used together.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.retry_dry:
        asyncio.run(retry_expired_games())
    elif args.game_id is None:
        asyncio.run(watch_games())
    else:
        asyncio.run(run_game(args.game_id))


if __name__ == "__main__":
    main()
