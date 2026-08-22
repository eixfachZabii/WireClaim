from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from src.data.models import CaseData, Proposal
from src.services.strategies.strategy_1 import propose as strategy_1
from src.services.strategies.strategy_2 import propose as strategy_2

logger = logging.getLogger(__name__)
Strategy = Callable[[CaseData], Awaitable[Proposal | None]]


class StrategyRouter:
    def __init__(self, strategies: tuple[Strategy, ...] | None = None) -> None:
        self._strategies = (strategy_1, strategy_2) if strategies is None else strategies
        self._current: Proposal | None = None

    @property
    def current(self) -> Proposal | None:
        return self._current

    def register(self, proposal: Proposal | None) -> Proposal | None:
        if proposal is None or proposal.is_empty:
            return None
        self._current = proposal
        return proposal

    def start_strategies(self, case: CaseData) -> AsyncIterator[Proposal]:
        return self.results(case)

    async def results(self, case: CaseData) -> AsyncIterator[Proposal]:
        tasks = [asyncio.create_task(strategy(case)) for strategy in self._strategies]
        try:
            for task in asyncio.as_completed(tasks):
                try:
                    proposal = await task
                except Exception:
                    logger.exception("Strategy failed for Game %s.", case.game_id)
                    continue
                active = self.register(proposal)
                if active is not None:
                    yield active
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
