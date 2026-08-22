from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from src.data.models import CaseData, Proposal
from src.services.strategies.strategy1 import propose as strategy1
from src.services.strategies.strategy2 import propose as strategy2
from src.services.strategies.strategy3 import propose as strategy3
from src.timing import log_timing, start_timer

logger = logging.getLogger(__name__)
Strategy = Callable[[CaseData], Awaitable[Proposal | None]]
STRATEGY_PRIORITIES = {"strategy1": 1, "strategy2": 2, "strategy3": 3}


class StrategyRouter:
    def __init__(self, strategies: tuple[Strategy, ...] | None = None) -> None:
        self._strategies = (strategy1, strategy2, strategy3) if strategies is None else strategies
        self._current: Proposal | None = None
        self._current_priority = -1

    @property
    def current(self) -> Proposal | None:
        return self._current

    def register(self, proposal: Proposal | None) -> Proposal | None:
        if proposal is None or proposal.is_empty:
            return None
        priority = STRATEGY_PRIORITIES.get(proposal.source, 0)
        if priority < self._current_priority:
            return None
        self._current = proposal
        self._current_priority = priority
        return proposal

    def start_strategies(self, case: CaseData) -> AsyncIterator[Proposal]:
        return self.results(case)

    async def results(self, case: CaseData) -> AsyncIterator[Proposal]:
        jobs: dict[asyncio.Task[Proposal | None], tuple[str, float]] = {}
        for strategy in self._strategies:
            name = strategy.__module__.split(".")[-2] if "." in strategy.__module__ else strategy.__name__
            jobs[asyncio.create_task(strategy(case), name=name)] = (name, start_timer())
        pending = set(jobs)
        try:
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    name, started_at = jobs[task]
                    try:
                        proposal = task.result()
                    except Exception:
                        logger.exception("Strategy failed for Game %s.", case.game_id)
                        log_timing(logger, name, started_at, "failed", game=case.game_id)
                        continue
                    log_timing(logger, name, started_at, game=case.game_id, produced=proposal is not None)
                    active = self.register(proposal)
                    if active is not None:
                        yield active
        finally:
            for task in jobs:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
