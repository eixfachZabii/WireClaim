from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
from collections.abc import Awaitable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.api import list_games, warm_llm_resources
from src.data.case_loader import load_case
from src.data.models import CaseData, FraudDecision, ItemPrice, Proposal
from src.services.fraud_detection import detect_fraud
from src.services.strategy_router import STRATEGY_PRIORITIES, StrategyRouter
from src.services.strategies.fast_path import LLM_TIMEOUT_SECONDS, llm_values, standard_values
from src.services.submission_coordinator import SubmissionCoordinator
from src.observability.timing import FairValueReference, format_error_card, log_timing, start_timer

logger = logging.getLogger(__name__)
RUN_SECONDS = 60.0
FAIR_VALUE_STUDY_PATH = Path(__file__).resolve().parent / "case_analysis" / "data" / "fair_value_study.json"


def load_fair_value_references(game_id: int) -> dict[int, FairValueReference]:
    try:
        payload = json.loads(FAIR_VALUE_STUDY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        logger.warning("Could not load Fair Value Study for dry run: %s", error)
        return {}
    games = payload.get("games") if isinstance(payload, dict) else None
    if not isinstance(games, list):
        logger.warning("Fair Value Study has no Games list; dry run will omit reference columns.")
        return {}
    game = next((entry for entry in games if isinstance(entry, dict) and entry.get("game_id") == game_id), None)
    if not isinstance(game, dict):
        return {}
    line_items = game.get("line_items")
    if not isinstance(line_items, list):
        logger.warning("Fair Value Study Game %s has no Line Items list.", game_id)
        return {}
    references: dict[int, FairValueReference] = {}
    for item in line_items:
        try:
            index = int(item["index"])
            fair_value = item["fair_value"]
            lower = float(fair_value["lower"])
            upper_data = fair_value["upper"]
            upper = upper_data["value"]
            relation = upper_data["relation"]
            if index <= 0 or lower < 0 or not math.isfinite(lower):
                continue
            if upper is None:
                if relation is not None:
                    continue
                references[index] = FairValueReference(lower, None, None)
                continue
            upper_value = float(upper)
            if not math.isfinite(upper_value) or relation not in {"lt", "le"}:
                continue
            references[index] = FairValueReference(lower, upper_value, relation)
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return references


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


def dry_run_submit(game_id: int, submissions: list[dict[str, float | int]], timeout: float) -> list[dict]:
    return []


async def run_game(game_id: int, dry_run: bool = False) -> None:
    run_started_at = start_timer()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + RUN_SECONDS
    fair_value_references = load_fair_value_references(game_id) if dry_run else {}
    coordinator = (
        SubmissionCoordinator(
            game_id,
            deadline,
            submitter=dry_run_submit,
            fair_value_references=fair_value_references,
        )
        if dry_run
        else SubmissionCoordinator(game_id, deadline)
    )
    await coordinator.start()

    case_load_started_at = start_timer()
    try:
        remaining = deadline - loop.time()
        if remaining <= 0:
            await coordinator.close()
            return
        case = await asyncio.wait_for(load_case(game_id, deadline), timeout=remaining)
    except Exception as error:
        logger.error("Game %s could not be loaded: %s - no submission was sent.", game_id, error)
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
    router = StrategyRouter(fair_value_references=fair_value_references)
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
        logger.info("\n\n\n################ CASE %s ##################\n\n\n", game["id"])
        logger.info("Dry retry for expired Game %s.", game["id"])
        await run_game(int(game["id"]), dry_run=True)


async def _run_with_executor_cleanup(operation: Awaitable[None]) -> None:
    try:
        await operation
    finally:
        await asyncio.get_running_loop().shutdown_default_executor()


def _run_operation(operation: Awaitable[None]) -> None:
    asyncio.run(_run_with_executor_cleanup(operation))


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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for http_logger in ("httpx", "httpx2", "httpcore", "httpcore2"):
        logging.getLogger(http_logger).setLevel(logging.WARNING)
    try:
        if args.game_id is not None:
            operation = run_game(args.game_id, dry_run=args.retry_dry)
        elif args.retry_dry:
            operation = retry_expired_games()
        else:
            operation = watch_games()
        _run_operation(operation)
    except KeyboardInterrupt:
        logger.info("Stopping WireClaim runner.")


if __name__ == "__main__":
    main()
