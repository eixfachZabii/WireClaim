"""Run every strategy concurrently, keep the highest-priority complete Proposal — and
record the ones that lose, because otherwise we never learn whether they were right.

Three strategies price every Case at once and `register` throws away everything that does
not outrank the incumbent. Until now that discard was total: only the winner's numbers ever
reached disk, so "would Strategy 3 have scored better on Game 26?" was unanswerable even
though the answer is exactly computable from the settled Transactions. `results()` is the
one place that sees every Proposal, so it writes all of them to the Game's decision log
(`src.runtime.decisions.record_proposals`) alongside the source that is currently winning;
`scripts/learn_from_game.py` then replays each one against the real Field.

The logging is strictly subordinate to the Submission: it happens after `register`, it
swallows every error, and it can only ever cost a small local write. A missing log costs one
Game's learning, a failed Submission costs the Game.

**`fast_path` is not covered here.** It is emitted from `main.py` and never passes through
the router, so it cannot appear in the `proposals` section — its absence there is not
evidence that it stayed silent.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from src.data.models import CaseData, Proposal
from src.runtime.decisions import record_proposals
from src.strategies import STRATEGY_PRIORITIES
from src.legacy.strategy1 import propose as strategy1
from src.strategies.strategy2 import propose as strategy2
from src.legacy.strategy3 import propose as strategy3
from src.runtime.timing import format_error_card, format_skipped_strategy_card, log_timing, start_timer

logger = logging.getLogger(__name__)
Strategy = Callable[..., Awaitable[Proposal | None]]
# `STRATEGY_PRIORITIES` is re-exported for the callers that already import it from here.
# It is defined in `src.strategies` because it describes the tracks rather than
# the router, and because two copies of it had already drifted apart.
__all__ = ["STRATEGY_PRIORITIES", "StrategyRouter"]


class StrategyRouter:
    def __init__(self, strategies: tuple[Strategy, ...] | None = None) -> None:
        self._strategies = (strategy1, strategy2, strategy3) if strategies is None else strategies
        self._current: Proposal | None = None
        self._current_priority = -1
        #: Every Proposal seen this run, winners and losers alike: source -> {index: (a, b)}.
        self._seen: dict[str, dict[int, tuple[float, float]]] = {}

    @property
    def current(self) -> Proposal | None:
        return self._current

    @property
    def seen(self) -> dict[str, dict[int, tuple[float, float]]]:
        """The Proposals of every source, including the ones priority rejected."""
        return dict(self._seen)

    def _capture(self, game_id: int, proposal: Proposal | None) -> None:
        """Add one Proposal to the decision log. Never raises, never blocks meaningfully.

        Called for rejected Proposals too — the whole point is the counterfactual. An empty
        Proposal is recorded as an empty mapping, which says "this strategy answered with
        nothing" rather than "this strategy did not run".
        """
        try:
            if proposal is None:
                return
            self._seen[proposal.source] = {
                price.index: (float(price.charge_price), float(price.acceptance_limit))
                for price in proposal.prices
            }
            record_proposals(
                game_id,
                self._seen,
                winner=None if self._current is None else self._current.source,
            )
        except Exception as error:  # pragma: no cover - must never break a Game
            logger.warning("Could not record the Proposals for Game %s: %s", game_id, error)

    def register(self, proposal: Proposal | None) -> Proposal | None:
        if proposal is None or proposal.is_empty:
            return None
        priority = STRATEGY_PRIORITIES.get(proposal.source, 0)
        if priority < self._current_priority:
            return None
        self._current = proposal
        self._current_priority = priority
        return proposal

    def start_strategies(self, case: CaseData, deadline: float | None = None) -> AsyncIterator[Proposal]:
        return self.results(case, deadline)

    async def results(self, case: CaseData, deadline: float | None = None) -> AsyncIterator[Proposal]:
        jobs: dict[asyncio.Task[Proposal | None], tuple[str, float]] = {}
        for strategy in self._strategies:
            name = strategy.__module__.split(".")[-2] if "." in strategy.__module__ else strategy.__name__
            operation = strategy(case) if deadline is None else strategy(case, deadline)
            jobs[asyncio.create_task(operation, name=name)] = (name, start_timer())
        pending = set(jobs)
        try:
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    name, started_at = jobs[task]
                    try:
                        proposal = task.result()
                    except Exception as error:
                        logger.error(
                            "%s",
                            format_error_card(
                                name,
                                error,
                                case.game_id,
                                "Strategy result skipped; the current batch stays active.",
                                elapsed_s=start_timer() - started_at,
                            ),
                        )
                        logger.debug(
                            "%s traceback for Game %s", name, case.game_id, exc_info=error
                        )
                        log_timing(logger, name, started_at, "failed", game=case.game_id)
                        continue
                    log_timing(logger, name, started_at, game=case.game_id, produced=proposal is not None)
                    candidate_priority = STRATEGY_PRIORITIES.get(proposal.source, 0) if proposal else 0
                    current = self._current
                    if (
                        proposal is not None
                        and not proposal.is_empty
                        and current is not None
                        and candidate_priority < self._current_priority
                    ):
                        logger.info(
                            "%s",
                            format_skipped_strategy_card(
                                case.game_id,
                                proposal.source,
                                candidate_priority,
                                current.source,
                                self._current_priority,
                                start_timer() - started_at,
                                tuple(
                                    (price.index, price.charge_price, price.acceptance_limit)
                                    for price in proposal.prices
                                ),
                            ),
                        )
                    active = self.register(proposal)
                    # After `register`, so the recorded winner is the one that would be
                    # submitted right now, and before the yield, so a consumer that stops
                    # iterating early still leaves the Proposal on disk.
                    self._capture(case.game_id, proposal)
                    if active is not None:
                        yield active
        finally:
            for task in jobs:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
