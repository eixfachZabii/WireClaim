"""Run the active strategy, then lower-priority comparisons, and record every Proposal.

Strategy 2 prices the Case first and remains the only live winner. Strategy 5 then reprices
Strategy 2's recorded evidence with its coherent Fair-Value policy, followed by Strategy 4's
tail-aware comparison. Running them after Strategy 2 is intentional: neither can consume
model capacity from the submitted strategy or briefly reach the coordinator first.
`results()` writes every Proposal to the Game's decision log so the settled Field can score
the experiments.

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
from src.strategies import SHADOW_STRATEGIES, STRATEGY_PRIORITIES
from src.legacy.strategy1 import propose as strategy1
from src.strategies.strategy2 import propose as strategy2
from src.legacy.strategy3 import propose as strategy3
from src.strategies.strategy4 import propose as strategy4
from src.strategies.strategy5 import propose as strategy5
from src.runtime.timing import format_error_card, format_skipped_strategy_card, log_timing, start_timer

logger = logging.getLogger(__name__)
Strategy = Callable[..., Awaitable[Proposal | None]]
# `STRATEGY_PRIORITIES` is re-exported for the callers that already import it from here.
# It is defined in `src.strategies` because it describes the tracks rather than
# the router, and because two copies of it had already drifted apart.
__all__ = ["SHADOW_STRATEGIES", "STRATEGY_PRIORITIES", "StrategyRouter"]


class StrategyRouter:
    def __init__(self, strategies: tuple[Strategy, ...] | None = None) -> None:
        #: Strategy 2 remains the live track. Strategies 5 and 4 are deliberately not placed
        #: in this concurrent tuple: they run only after Strategy 2 has completed and are
        #: passed that winning Proposal as their immutable baseline. This prevents both
        #: endpoint contention and a lower-priority transient submission.
        #:
        #: Strategies 1 and 3 were retired for two reasons, and the second is the bigger
        #: one.
        #:
        #: They never won. Over the 18 Games where all three were recorded, Strategy 2 leads
        #: Strategy 3 by 117,135 and Strategy 1 by 327,049, both outside the 26,622 noise
        #: floor at that sample size. Strategy 1 has been best on 2 Games out of 24.
        #:
        #: And each of them fires its own LLM call -- Strategy 1 on terra, Strategy 3 on luna
        #: -- against the same deployment Strategy 2 needs inside the same sixty seconds.
        #: That contention is not theoretical: Game 46 lost *both* of Strategy 2's ensemble
        #: draws to a timeout on a 31-item Case, and Game 49 lost one to an outright HTTP 429
        #: from the endpoint. Two Games of the model channel, spent on two tracks that were
        #: never going to be submitted.
        self._strategies = (strategy2,) if strategies is None else strategies
        self._comparisons = (strategy5, strategy4) if strategies is None else ()
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
        if proposal.source in SHADOW_STRATEGIES:
            # Logged, compared, never submitted -- and deliberately checked before the
            # priority arithmetic rather than expressed as a low number, because `register`
            # rejects a lower priority and not an equal one. See `SHADOW_STRATEGIES`.
            return None
        priority = STRATEGY_PRIORITIES.get(proposal.source, 0)
        if priority < self._current_priority:
            return None
        self._current = proposal
        self._current_priority = priority
        return proposal

    def _register_result(
        self,
        case: CaseData,
        proposal: Proposal | None,
        started_at: float,
    ) -> Proposal | None:
        """Register, diagnose and record one completed strategy result."""
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
        self._capture(case.game_id, proposal)
        return active

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
                    active = self._register_result(case, proposal, started_at)
                    # After `register`, so the recorded winner is the one that would be
                    # submitted right now, and before the yield, so a consumer that stops
                    # iterating early still leaves the Proposal on disk.
                    if active is not None:
                        yield active

            # Default live router only: comparison tracks receive the already-winning
            # Strategy 2 Proposal. They are never scheduled in parallel with Strategy 2, so
            # they cannot steal request capacity or land first.
            for comparison in self._comparisons:
                name = (
                    comparison.__module__.split(".")[-2]
                    if "." in comparison.__module__
                    else comparison.__name__
                )
                started_at = start_timer()
                try:
                    proposal = await comparison(
                        case,
                        deadline=deadline,
                        baseline=self._current,
                    )
                except Exception as error:
                    logger.error(
                        "%s",
                        format_error_card(
                            name,
                            error,
                            case.game_id,
                            "Comparison result skipped; Strategy 2 stays active.",
                            elapsed_s=start_timer() - started_at,
                        ),
                    )
                    logger.debug(
                        "%s traceback for Game %s", name, case.game_id, exc_info=error
                    )
                    log_timing(logger, name, started_at, "failed", game=case.game_id)
                    continue
                log_timing(
                    logger,
                    name,
                    started_at,
                    game=case.game_id,
                    produced=proposal is not None,
                )
                active = self._register_result(case, proposal, started_at)
                if active is not None:
                    # Defensive only: with Strategy 2 above every comparison track, this
                    # cannot happen. Keeping the generic contract makes a priority-table
                    # change visible rather than silently discarded.
                    yield active
        finally:
            for task in jobs:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
