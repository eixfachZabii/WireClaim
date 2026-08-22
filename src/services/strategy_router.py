"""Run configured strategies concurrently and record every Proposal for later replay.

Strategy 2 and Strategy 5 have one explicit combination rule: as soon as both complete,
Charge is the maximum of both values per Line Item, while Limit is zero if either Limit is
zero and otherwise their maximum. The merged Proposal is recorded separately and outranks
either individual Proposal. `results()` writes winners and losers to the Game's decision log
so `scripts/learn_from_game.py` can replay each one against the real Field.

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
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping

from src.data.models import CaseData, ItemPrice, Proposal
from src.observability.decisions import record_proposals
from src.services.strategies import STRATEGY_PRIORITIES
from src.services.strategies.strategy1 import propose as strategy1
from src.services.strategies.strategy2 import propose as strategy2
from src.services.strategies.strategy3 import propose as strategy3
from src.services.strategies.strategy4 import propose as strategy4
from src.services.strategies.strategy5 import propose as strategy5
from src.observability.timing import (
    FairValueReference,
    format_error_card,
    format_skipped_strategy_card,
    log_timing,
    start_timer,
)

logger = logging.getLogger(__name__)
Strategy = Callable[..., Awaitable[Proposal | None]]
MERGED_STRATEGY_SOURCE = "strategy2+5"
_MERGED_STRATEGIES = frozenset({"strategy2", "strategy5"})
# `STRATEGY_PRIORITIES` is re-exported for the callers that already import it from here.
# It is defined in `src.services.strategies` because it describes the tracks rather than
# the router, and because two copies of it had already drifted apart.
__all__ = ["MERGED_STRATEGY_SOURCE", "STRATEGY_PRIORITIES", "StrategyRouter"]


def _merge_strategy2_and_5(strategy2_result: Proposal, strategy5_result: Proposal) -> Proposal:
    strategy2_prices = strategy2_result.by_index()
    strategy5_prices = strategy5_result.by_index()
    prices: list[ItemPrice] = []
    for index in sorted(strategy2_prices.keys() | strategy5_prices.keys()):
        from_strategy2 = strategy2_prices.get(index)
        from_strategy5 = strategy5_prices.get(index)
        if from_strategy2 is None or from_strategy5 is None:
            available = from_strategy5 if from_strategy2 is None else from_strategy2
            if available is None:
                continue
            prices.append(
                ItemPrice(
                    index=index,
                    charge_price=available.charge_price,
                    acceptance_limit=available.acceptance_limit,
                    source=MERGED_STRATEGY_SOURCE,
                )
            )
            continue
        limit = (
            0.0
            if from_strategy2.acceptance_limit == 0.0
            or from_strategy5.acceptance_limit == 0.0
            else max(from_strategy2.acceptance_limit, from_strategy5.acceptance_limit)
        )
        prices.append(
            ItemPrice(
                index=index,
                charge_price=max(from_strategy2.charge_price, from_strategy5.charge_price),
                acceptance_limit=limit,
                source=MERGED_STRATEGY_SOURCE,
            )
        )
    return Proposal(source=MERGED_STRATEGY_SOURCE, prices=tuple(prices))


class StrategyRouter:
    def __init__(
        self,
        strategies: tuple[Strategy, ...] | None = None,
        fair_value_references: Mapping[int, FairValueReference] | None = None,
    ) -> None:
        self._strategies = (
            # strategy1,
            strategy2,
            # strategy3,
            # strategy4,
            strategy5,
        ) if strategies is None else strategies
        self._fair_value_references = dict(fair_value_references or {})
        self._completed: dict[str, Proposal] = {}
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

    def _will_merge(self, proposal: Proposal | None) -> bool:
        if proposal is None or proposal.source not in _MERGED_STRATEGIES:
            return False
        partner = next(iter(_MERGED_STRATEGIES - {proposal.source}))
        return partner in self._completed

    def register(self, proposal: Proposal | None) -> Proposal | None:
        if proposal is None or proposal.is_empty:
            return None
        if proposal.source in _MERGED_STRATEGIES:
            self._completed[proposal.source] = proposal
            if _MERGED_STRATEGIES.issubset(self._completed):
                merged = _merge_strategy2_and_5(
                    self._completed["strategy2"],
                    self._completed["strategy5"],
                )
                self._current = merged
                self._current_priority = STRATEGY_PRIORITIES[MERGED_STRATEGY_SOURCE]
                return merged
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
                        and not self._will_merge(proposal)
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
                                self._fair_value_references,
                            ),
                        )
                    active = self.register(proposal)
                    # After `register`, so the recorded winner is the one that would be
                    # submitted right now, and before the yield, so a consumer that stops
                    # iterating early still leaves the Proposal on disk.
                    self._capture(case.game_id, proposal)
                    if active is not None and active is not proposal:
                        self._capture(case.game_id, active)
                    if active is not None:
                        yield active
        finally:
            for task in jobs:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
