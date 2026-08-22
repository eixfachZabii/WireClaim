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
from src.services.strategies.strategy2.constants import SETTLED_MEDIAN
from src.services.strategies.strategy5.config import Strategy5Config, load_config
from src.services.strategies.strategy5.invoice import InvoiceDocument, extract_invoice_document
from src.services.strategies.strategy5.model import (
    AggregatedPriceRange,
    CoverageAssessment,
    aggregate_price_ranges,
    request_coverage_assessments,
    request_price_ranges,
)

logger = logging.getLogger(__name__)
STRATEGY_NAME = "strategy5"
LLM_TIMEOUT_SECONDS = 55.0
SUBMISSION_RESERVE_SECONDS = 3.0


def _fallback_evidence(index: int, coverage_probability: float) -> Evidence:
    return Evidence(
        index=index,
        coverage_probability=coverage_probability,
        price_low=SETTLED_MEDIAN * 0.5,
        price_median=SETTLED_MEDIAN,
        price_high=SETTLED_MEDIAN * 2.0,
    )


def _scaled_price(
    index: int,
    evidence: Evidence,
    confirmed_uncovered: bool,
    config: Strategy5Config,
) -> ItemPrice:
    priced = price_item(evidence, confirmed_uncovered=confirmed_uncovered)
    charge = round(priced.charge * config.alpha_factor, 2)
    limit = 0.0 if priced.limit == 0.0 else round(priced.limit * config.beta_factor, 2)
    limit = min(limit, charge)
    return ItemPrice(
        index=index,
        charge_price=max(charge, 0.0),
        acceptance_limit=max(limit, 0.0),
        source=STRATEGY_NAME,
    )


def build_proposal(
    case: CaseData,
    document: InvoiceDocument,
    ranges: Mapping[int, AggregatedPriceRange],
    coverage: Mapping[int, CoverageAssessment],
    config: Strategy5Config,
    deterministic: Mapping[int, Evidence] | None = None,
) -> Proposal | None:
    priced_case = replace(case, line_items=document.line_items)
    local = local_evidence(priced_case) if deterministic is None else deterministic
    prices: list[ItemPrice] = []
    for item in document.items:
        assessment = coverage.get(item.index)
        covered_probability = (
            1.0 - config.default_policy_violation_probability
            if assessment is None
            else assessment.coverage_probability
        )
        aggregated = ranges.get(item.index)
        model_evidence = (
            None if aggregated is None else aggregated.evidence(covered_probability)
        )
        evidence = combine(model_evidence, local.get(item.index))
        if evidence is None:
            evidence = _fallback_evidence(item.index, covered_probability)
        confirmed_uncovered = item.quantity_missing or bool(
            assessment is not None
            and assessment.quote_verified
            and assessment.policy_violation_probability
            >= config.zero_limit_violation_threshold
        )
        prices.append(_scaled_price(item.index, evidence, confirmed_uncovered, config))
    return Proposal(source=STRATEGY_NAME, prices=tuple(prices)) if prices else None


def _request_timeout(deadline: float | None) -> float:
    if deadline is None:
        return LLM_TIMEOUT_SECONDS
    remaining = deadline - asyncio.get_running_loop().time() - SUBMISSION_RESERVE_SECONDS
    return max(min(LLM_TIMEOUT_SECONDS, remaining), 0.0)


async def propose(case: CaseData, deadline: float | None = None) -> Proposal | None:
    started_at = start_timer()
    try:
        config = load_config()
    except Exception as error:
        logger.warning("Strategy 5 config unavailable for Game %s: %s", case.game_id, error)
        config = Strategy5Config()
    document = await asyncio.to_thread(extract_invoice_document, case)
    if not document.items:
        return None
    priced_case = replace(case, line_items=document.line_items)
    timeout = _request_timeout(deadline)
    if timeout <= 0.0:
        proposal = build_proposal(priced_case, document, {}, {}, config)
        log_timing(
            logger,
            STRATEGY_NAME,
            started_at,
            "deadline-fallback",
            game=case.game_id,
            priced=0 if proposal is None else len(proposal.prices),
        )
        return proposal

    async def price_draw(model: str):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    request_price_ranges,
                    priced_case,
                    document.items,
                    model,
                    timeout,
                ),
                timeout=timeout,
            )
        except Exception as error:
            logger.warning(
                "Strategy 5 price model %s unavailable for Game %s: %s",
                model,
                case.game_id,
                error,
            )
            return {}

    async def coverage_draw():
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    request_coverage_assessments,
                    priced_case,
                    document.items,
                    document.text,
                    config.coverage_model,
                    timeout,
                ),
                timeout=timeout,
            )
        except Exception as error:
            logger.warning(
                "Strategy 5 coverage model unavailable for Game %s: %s",
                case.game_id,
                error,
            )
            return {}

    results = await asyncio.gather(
        *(price_draw(model) for model in config.models),
        coverage_draw(),
    )
    price_draws = results[:-1]
    coverage = results[-1]
    ranges = aggregate_price_ranges(price_draws, document.items)
    proposal = build_proposal(priced_case, document, ranges, coverage, config)
    policy_locks = sum(
        1
        for assessment in coverage.values()
        if assessment.quote_verified
        and assessment.policy_violation_probability >= config.zero_limit_violation_threshold
    )
    logger.info(
        "Strategy 5 policy gate locked %s/%s Line Items for Game %s.",
        policy_locks,
        len(document.items),
        case.game_id,
    )
    log_timing(
        logger,
        STRATEGY_NAME,
        started_at,
        game=case.game_id,
        price_models=sum(1 for draw in price_draws if draw),
        range_items=len(ranges),
        coverage_items=len(coverage),
        policy_locks=policy_locks,
        priced=0 if proposal is None else len(proposal.prices),
    )
    return proposal


__all__ = [
    "LLM_TIMEOUT_SECONDS",
    "STRATEGY_NAME",
    "SUBMISSION_RESERVE_SECONDS",
    "build_proposal",
    "propose",
]
