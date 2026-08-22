from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Mapping

from src.data.models import CaseData, ItemPrice, Proposal
from src.domain.pricing.engine import Evidence, price_item
from src.observability.timing import log_timing, start_timer
from src.services.strategies.strategy2.blend import combine
from src.services.strategies.strategy2.channels import local_evidence
from src.services.strategies.strategy4.model import (
    FALLBACK_MEDIAN,
    LLM_TIMEOUT_SECONDS,
    FairValueEvidence,
    extract_invoice_items,
    request_estimates,
)

logger = logging.getLogger(__name__)
STRATEGY_NAME = "strategy4"
SUBMISSION_RESERVE_SECONDS = 3.0


def _fallback_evidence(index: int) -> Evidence:
    return Evidence(
        index=index,
        coverage_probability=0.9,
        price_low=FALLBACK_MEDIAN * 0.5,
        price_median=FALLBACK_MEDIAN,
        price_high=FALLBACK_MEDIAN * 2,
    )


def build_proposal(
    case: CaseData,
    estimates: Mapping[int, FairValueEvidence],
    deterministic: Mapping[int, Evidence] | None = None,
) -> Proposal | None:
    local = local_evidence(case) if deterministic is None else deterministic
    prices: list[ItemPrice] = []
    for line_item in case.line_items:
        model_evidence = estimates.get(line_item.index)
        evidence = combine(
            None if model_evidence is None else model_evidence.pricing_evidence(),
            local.get(line_item.index),
        )
        priced = price_item(
            evidence or _fallback_evidence(line_item.index),
            confirmed_uncovered=line_item.quantity_missing,
        )
        prices.append(
            ItemPrice(
                index=line_item.index,
                charge_price=priced.charge,
                acceptance_limit=priced.limit,
                source=STRATEGY_NAME,
            )
        )
    return Proposal(source=STRATEGY_NAME, prices=tuple(prices)) if prices else None


def _request_timeout(deadline: float | None) -> float:
    if deadline is None:
        return LLM_TIMEOUT_SECONDS
    remaining = deadline - asyncio.get_running_loop().time() - SUBMISSION_RESERVE_SECONDS
    return max(min(LLM_TIMEOUT_SECONDS, remaining), 1.0)


async def propose(case: CaseData, deadline: float | None = None) -> Proposal | None:
    started_at = start_timer()
    line_items = await asyncio.to_thread(extract_invoice_items, case)
    if not line_items:
        return None
    priced_case = replace(case, line_items=line_items)
    timeout = _request_timeout(deadline)
    try:
        estimates = await asyncio.wait_for(
            asyncio.to_thread(request_estimates, priced_case, line_items, timeout),
            timeout=timeout + SUBMISSION_RESERVE_SECONDS,
        )
    except Exception as error:
        logger.warning("Strategy 4 model unavailable for Game %s: %s", case.game_id, error)
        estimates = {}
    proposal = build_proposal(priced_case, estimates)
    log_timing(
        logger,
        STRATEGY_NAME,
        started_at,
        game=case.game_id,
        invoice_items=len(line_items),
        model_items=len(estimates),
        priced=0 if proposal is None else len(proposal.prices),
    )
    return proposal


__all__ = ["STRATEGY_NAME", "SUBMISSION_RESERVE_SECONDS", "build_proposal", "propose"]
