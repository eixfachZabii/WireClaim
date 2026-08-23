"""A time-safe experiment for expensive cases hidden by a generic memory match.

This module is deliberately outside ``src/strategies``: importing it through a backtest
spec cannot register it with the live router.  It keeps Strategy 2's normal result unless
all of the following are true for a Line Item:

* the past-only Price Memory has a hit;
* the model's median is materially above the memory median;
* the matched wording is generic or contextually weak; and
* a separate, targeted reread confirms the expensive scenario.

On confirmation the two price levels are not inverse-variance averaged into one band.  They
remain an ordinary and a tail component in a mixture distribution.  The Charge maximises
``charge * P(fair value >= charge)`` on that mixture, while the Limit remains its bottom-
third quantile.  This tests the hypothesis that rare cash-generating spikes are being
destroyed by premature averaging without globally raising every large estimate.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping

from backtesting.history import HistoryView
from backtesting.models import Submission
from backtesting.strategies import StrategyContext
from src.api import get_llm_client, get_model_name, get_service_tier
from src.data.models import CaseData
from src.evidence.memory import (
    PriceMemory,
    PriceMemoryHit,
    build_entries,
    is_per_unit,
    normalise,
    normalise_unit,
)
from src.evidence.policy.slice import slice_policy
from src.pricing.engine import COVERAGE_FLOOR, LIMIT_QUANTILE, Evidence, implied_sigma
from src.strategies.strategy2.blend import blend
from src.strategies.strategy2.channels import (
    aggregate_class_discount,
    unit_of,
    worthless_evidence,
)
from src.strategies.strategy2.model import build_request_text, extract_json, parse_items
from src.strategies.strategy2.prompts import ENSEMBLE_PROMPTS
from src.strategies.strategy2.strategy import build_proposal

logger = logging.getLogger(__name__)

_MEMORY_COVERAGE = 0.9
_REQUEST_RESERVE_SECONDS = 5.0
_PRICE_GRID_POINTS = 160

# These words can describe a claim without identifying the thing or service being priced.
# An exact match made only from this vocabulary is not evidence that two Cases share a price
# level.  The list is deliberately conservative: the disagreement and confirmation gates
# still have to fire before it changes a number.
_GENERIC_WORDS = {
    "affected",
    "and",
    "compensation",
    "cost",
    "costs",
    "damage",
    "damaged",
    "damages",
    "due",
    "for",
    "insured",
    "item",
    "items",
    "of",
    "repair",
    "repairs",
    "replacement",
    "robbery",
    "service",
    "services",
    "the",
    "theft",
    "to",
    "water",
    "with",
    "work",
    "works",
}

_BASE_CACHE: dict[tuple[int, int, float, tuple[int, ...]], "_Inputs"] = {}
_ADJUDICATION_CACHE: dict[
    tuple[int, int, float, tuple[int, ...], tuple[int, ...]], dict[int, Evidence]
] = {}


@dataclass(frozen=True)
class _Inputs:
    model: dict[int, Evidence]
    memory: dict[int, Evidence]
    hits: dict[int, PriceMemoryHit]


async def baseline(
    context: StrategyContext, params: Mapping[str, Any]
) -> Mapping[int, Submission]:
    """Strategy 2 using fresh model evidence and strictly past-only Price Memory.

    The baseline shares its model calls with :func:`tail_aware` inside one experiment run,
    making the comparison use identical initial evidence rather than two stochastic draws.
    """
    inputs = await _inputs(context, _timeout(params))
    proposal = build_proposal(context.case, inputs.model, inputs.memory)
    if proposal is None:
        return {}
    return {
        price.index: Submission(price.charge_price, price.acceptance_limit)
        for price in proposal.prices
    }


async def tail_aware(
    context: StrategyContext, params: Mapping[str, Any]
) -> Mapping[int, Submission]:
    """Return Strategy 2 prices, replacing only separately confirmed tail conflicts."""
    timeout = _timeout(params)
    inputs = await _inputs(context, timeout)
    normal = build_proposal(context.case, inputs.model, inputs.memory)
    if normal is None:
        return {}
    submissions = {
        price.index: Submission(price.charge_price, price.acceptance_limit)
        for price in normal.prices
    }

    model = aggregate_class_discount(context.case, inputs.model)
    conflicts = _conflicts(
        context.case,
        model,
        inputs.memory,
        inputs.hits,
        conflict_ratio=_number(params, "conflict_ratio", 3.0),
        tail_threshold=_number(params, "tail_threshold", 1_000.0),
    )
    if not conflicts:
        _write_trace(
            context,
            params,
            inputs,
            model,
            submissions,
            submissions,
            conflicts,
            {},
            set(),
        )
        return submissions

    adjudicated = await _adjudicate(context, tuple(sorted(conflicts)), timeout)
    confirmation_ratio = _number(params, "confirmation_ratio", 2.0)
    agreement_ratio = _number(params, "agreement_ratio", 2.0)
    tail_probability = _probability(params, "tail_probability", 0.70)
    limit_ceiling = max(_number(params, "trusted_tail_limit_ceiling", 0.75), 0.0)
    confirmed: set[int] = set()

    for index in conflicts:
        reread = adjudicated.get(index)
        remembered = inputs.memory[index]
        current = model[index]
        if not _confirms_tail(
            current,
            remembered,
            reread,
            confirmation_ratio=confirmation_ratio,
            agreement_ratio=agreement_ratio,
        ):
            continue
        confirmed.add(index)
        # ``blend`` adds the observed disagreement to the tail component's width.  Coverage
        # remains the already-adjusted Strategy 2 verdict below; this reread adjudicates the
        # price conflict and must not undo deterministic aggregate-policy handling.
        tail = blend([{index: current}, {index: reread}])[index]
        submissions[index] = _mixture_submission(
            remembered,
            tail,
            covered=current.coverage_probability,
            tail_probability=tail_probability,
            limit_ceiling=limit_ceiling,
        )
    _write_trace(
        context,
        params,
        inputs,
        model,
        {
            price.index: Submission(price.charge_price, price.acceptance_limit)
            for price in normal.prices
        },
        submissions,
        conflicts,
        adjudicated,
        confirmed,
    )
    return submissions


def _timeout(params: Mapping[str, Any]) -> float:
    return max(_number(params, "model_timeout_seconds", 55.0), 1.0)


def _number(params: Mapping[str, Any], name: str, default: float) -> float:
    try:
        value = float(params.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def _probability(params: Mapping[str, Any], name: str, default: float) -> float:
    return min(max(_number(params, name, default), 0.0), 1.0)


async def _inputs(context: StrategyContext, timeout: float) -> _Inputs:
    key = (context.game_id, context.seed, timeout, context.history.game_ids)
    cached = _BASE_CACHE.get(key)
    if cached is not None:
        return cached

    async def draw(prompt: str) -> dict[int, Evidence]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_request_evidence, context.case, prompt, timeout),
                timeout=timeout + _REQUEST_RESERVE_SECONDS,
            )
        except Exception as error:
            logger.warning(
                "Tail-aware baseline draw unavailable for Game %s: %s",
                context.game_id,
                error,
            )
            return {}

    draws = list(await asyncio.gather(*(draw(prompt) for prompt in ENSEMBLE_PROMPTS)))
    memory, hits = _memory_evidence(context.case, context.history)
    result = _Inputs(model=blend(draws), memory=memory, hits=hits)
    _BASE_CACHE[key] = result
    return result


def _request_evidence(case: CaseData, prompt: str, timeout: float) -> dict[int, Evidence]:
    """Strategy 2's request shape without writing live-game raw-reply logs."""
    # Kept local for the same reason as Strategy 2's implementation: this is the only
    # dependency borrowed from the legacy strategy and it is otherwise easy to retire.
    from src.legacy.strategy1.strategy import build_input_content

    sliced = CaseData(
        game_id=case.game_id,
        case_dir=case.case_dir,
        policy_text=slice_policy(case.policy_text),
        description_text=case.description_text,
        line_items=case.line_items,
        image_paths=case.image_paths,
    )
    content = build_input_content(sliced)
    content[-1] = {"type": "input_text", "text": build_request_text(case, prompt)}
    response = get_llm_client().responses.create(
        model=get_model_name(),
        service_tier=get_service_tier(),
        timeout=timeout,
        input=[{"role": "user", "content": content}],
    )
    return parse_items(extract_json(str(response.output_text or "")))


def _memory_evidence(
    case: CaseData, history: HistoryView
) -> tuple[dict[int, Evidence], dict[int, PriceMemoryHit]]:
    memory = _memory_from_history(history)
    evidence: dict[int, Evidence] = {}
    hits: dict[int, PriceMemoryHit] = {}
    for line_item in case.line_items:
        if line_item.quantity_missing:
            evidence[line_item.index] = worthless_evidence(line_item.index)
            continue
        hit = memory.lookup(
            line_item.name,
            unit=unit_of(line_item.name),
            quantity=max(line_item.quantity, 1.0),
        )
        if hit is None:
            continue
        hits[line_item.index] = hit
        evidence[line_item.index] = Evidence(
            index=line_item.index,
            coverage_probability=_MEMORY_COVERAGE,
            price_low=hit.low,
            price_median=hit.median,
            price_high=hit.high,
        )
    return evidence, hits


def _memory_from_history(history: HistoryView) -> PriceMemory:
    """Build the same memory shape as the harness, using only ``history.games``."""
    observations: list[dict[str, Any]] = []
    for prior_id, game in history.games.items():
        for item in game.items.values():
            interval = item.fair_value.interval
            total = interval.representative()
            unit = normalise_unit(unit_of(item.name))
            quantity = max(item.quantity, 1.0)
            per_unit = is_per_unit(unit)
            observations.append(
                {
                    "key": normalise(item.name),
                    "display_name": item.name,
                    "game": prior_id,
                    "value": total / quantity if per_unit else total,
                    "unit": unit,
                    "positive": interval.low > 0,
                    "line_item_index": item.index,
                    "quantity": quantity,
                    "t_low": interval.low,
                    "t_high": interval.high,
                    "basis": "per_unit" if per_unit else "gross",
                }
            )
    return PriceMemory.from_dict({"entries": build_entries(observations)})


def _conflicts(
    case: CaseData,
    model: Mapping[int, Evidence],
    memory: Mapping[int, Evidence],
    hits: Mapping[int, PriceMemoryHit],
    *,
    conflict_ratio: float,
    tail_threshold: float,
) -> dict[int, PriceMemoryHit]:
    conflicts: dict[int, PriceMemoryHit] = {}
    for item in case.line_items:
        current = model.get(item.index)
        remembered = memory.get(item.index)
        hit = hits.get(item.index)
        if current is None or remembered is None or hit is None or item.quantity_missing:
            continue
        if remembered.price_median <= 0:
            continue
        if current.price_median < max(tail_threshold, remembered.price_median * conflict_ratio):
            continue
        if _contextually_weak(item.name, hit):
            conflicts[item.index] = hit
    return conflicts


def _contextually_weak(current_name: str, hit: PriceMemoryHit) -> bool:
    current = _meaningful_tokens(current_name)
    historical = _meaningful_tokens(hit.name)
    # Core matches merge qualified wording variants.  With no shared identifying token, that
    # is exactly the cross-context comparison this experiment is intended to challenge.
    if hit.match == "core" and current.isdisjoint(historical):
        return True
    # An exact wording can still be generic (Game 41's "Compensation for robbery damage").
    if normalise(current_name) == normalise(hit.name) and len(current) < 2:
        return True
    return bool(current and historical and current.isdisjoint(historical))


def _meaningful_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalise(value))
        if len(token) > 2 and token not in _GENERIC_WORDS and not token.isdigit()
    }


async def _adjudicate(
    context: StrategyContext, indices: tuple[int, ...], timeout: float
) -> dict[int, Evidence]:
    key = (context.game_id, context.seed, timeout, context.history.game_ids, indices)
    cached = _ADJUDICATION_CACHE.get(key)
    if cached is not None:
        return cached
    selected = [item for item in context.case.line_items if item.index in indices]
    listed = "\n".join(f"- POS {item.index}: {item.name}" for item in selected)
    prompt = f"""Independently re-appraise only the Line Items listed below from the primary Case evidence.

They were selected because a historical price match may refer to a different object or scope.
Do not infer their price from the generic invoice wording alone. Identify the actual object,
service, quantity and declared/scheduled value from the invoice, photographs, damage description
and Policy, then estimate a realistic GROSS TOTAL German market-price band. This is a fresh
adjudication: do not split the difference with an assumed earlier estimate.

Selected positions:
{listed}

Return JSON only and return exactly those positions:
{{"items":[{{"line_item":1,"coverage_probability":0.9,"price_low":0.0,"price_median":0.0,"price_high":0.0,"clause":""}}]}}"""
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_request_evidence, context.case, prompt, timeout),
            timeout=timeout + _REQUEST_RESERVE_SECONDS,
        )
    except Exception as error:
        logger.warning(
            "Tail adjudication unavailable for Game %s Line Items %s: %s",
            context.game_id,
            list(indices),
            error,
        )
        result = {}
    # A verbose response must not accidentally rewrite a Line Item that was never selected.
    result = {index: value for index, value in result.items() if index in indices}
    _ADJUDICATION_CACHE[key] = result
    return result


def _confirms_tail(
    current: Evidence,
    remembered: Evidence,
    reread: Evidence | None,
    *,
    confirmation_ratio: float,
    agreement_ratio: float,
) -> bool:
    if reread is None or remembered.price_median <= 0:
        return False
    if min(current.price_median, reread.price_median) < (
        remembered.price_median * confirmation_ratio
    ):
        return False
    smaller = min(current.price_median, reread.price_median)
    larger = max(current.price_median, reread.price_median)
    return smaller > 0 and larger / smaller <= agreement_ratio


def _mixture_submission(
    ordinary: Evidence,
    tail: Evidence,
    *,
    covered: float,
    tail_probability: float,
    limit_ceiling: float,
) -> Submission:
    ordinary = ordinary.with_defaults()
    tail = tail.with_defaults()
    covered = min(max(covered, 0.0), 1.0)

    points = _charge_grid(ordinary, tail)
    charge = max(
        points,
        key=lambda value: (
            value * _positive_survival(value, ordinary, tail, tail_probability),
            -value,
        ),
    )

    if covered <= COVERAGE_FLOOR:
        limit = 0.0
    else:
        # Remove the posterior's mass at zero, then take the quantile that leaves one third
        # of the whole distribution below it, exactly as ``price_item`` does.
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        lower_quantile = _positive_quantile(
            conditional, ordinary, tail, tail_probability
        )
        positive_median = _positive_quantile(0.5, ordinary, tail, tail_probability)
        # This is the experiment's narrow exception to the ordinary absolute Limit cap: two
        # separate current-Case reads confirmed the tail, so the generic historical match
        # no longer acts as a trusted single level.  The proportional ceiling and Charge
        # clamp remain as guardrails.
        limit = min(lower_quantile, limit_ceiling * positive_median, charge)
    return Submission(round(max(charge, 0.0), 2), round(max(limit, 0.0), 2))


def _charge_grid(ordinary: Evidence, tail: Evidence) -> tuple[float, ...]:
    lower = max(min(ordinary.price_low, tail.price_low) * 0.25, 0.01)
    upper = max(ordinary.price_high, tail.price_high, lower * 2.0) * 1.5
    ratio = upper / lower
    points = {
        lower * ratio ** (step / _PRICE_GRID_POINTS)
        for step in range(_PRICE_GRID_POINTS + 1)
    }
    points.update(
        {
            ordinary.price_low,
            ordinary.price_median,
            ordinary.price_high,
            tail.price_low,
            tail.price_median,
            tail.price_high,
        }
    )
    return tuple(sorted(value for value in points if value > 0 and math.isfinite(value)))


def _positive_survival(
    value: float,
    ordinary: Evidence,
    tail: Evidence,
    tail_probability: float,
) -> float:
    return (1.0 - tail_probability) * (1.0 - _lognormal_cdf(value, ordinary)) + (
        tail_probability * (1.0 - _lognormal_cdf(value, tail))
    )


def _positive_cdf(
    value: float,
    ordinary: Evidence,
    tail: Evidence,
    tail_probability: float,
) -> float:
    return (1.0 - tail_probability) * _lognormal_cdf(value, ordinary) + (
        tail_probability * _lognormal_cdf(value, tail)
    )


def _lognormal_cdf(value: float, evidence: Evidence) -> float:
    if value <= 0:
        return 0.0
    sigma = implied_sigma(
        evidence.price_low, evidence.price_median, evidence.price_high
    )
    if sigma <= 0:
        return 0.0 if value < evidence.price_median else 1.0
    z = math.log(value / evidence.price_median) / sigma
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _positive_quantile(
    quantile: float,
    ordinary: Evidence,
    tail: Evidence,
    tail_probability: float,
) -> float:
    quantile = min(max(quantile, 0.0), 1.0)
    if quantile <= 0:
        return 0.0
    upper = max(ordinary.price_high, tail.price_high, 1.0)
    while _positive_cdf(upper, ordinary, tail, tail_probability) < quantile:
        upper *= 2.0
    lower = 0.0
    for _ in range(64):
        midpoint = (lower + upper) / 2.0
        if _positive_cdf(midpoint, ordinary, tail, tail_probability) < quantile:
            lower = midpoint
        else:
            upper = midpoint
    return upper


def _write_trace(
    context: StrategyContext,
    params: Mapping[str, Any],
    inputs: _Inputs,
    model: Mapping[int, Evidence],
    baseline_submissions: Mapping[int, Submission],
    final_submissions: Mapping[int, Submission],
    conflicts: Mapping[int, PriceMemoryHit],
    adjudicated: Mapping[int, Evidence],
    confirmed: set[int],
) -> None:
    """Persist the decision path beside the run report; never fail a backtest for logging."""
    if context.artifact_dir is None:
        return
    try:
        directory = context.artifact_dir / "tail_aware"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"game_{context.game_id:03d}.json"
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError):
            payload = {
                "game_id": context.game_id,
                "seed": context.seed,
                "history_games": list(context.history.game_ids),
                "runs": {},
            }
        serialised_params = dict(params)
        key = hashlib.sha256(
            json.dumps(serialised_params, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        changed = {
            index
            for index in final_submissions
            if final_submissions[index] != baseline_submissions[index]
        }
        rows = []
        by_index = {item.index: item for item in context.case.line_items}
        for index in sorted(conflicts):
            hit = conflicts[index]
            rows.append(
                {
                    "index": index,
                    "name": by_index[index].name,
                    "memory_match": hit.match,
                    "memory_name": hit.name,
                    "memory_evidence": _evidence_json(inputs.memory.get(index)),
                    "model_evidence": _evidence_json(model.get(index)),
                    "adjudication_evidence": _evidence_json(adjudicated.get(index)),
                    "confirmed": index in confirmed,
                    "changed": index in changed,
                    "baseline": _submission_json(baseline_submissions[index]),
                    "final": _submission_json(final_submissions[index]),
                }
            )
        payload["runs"][key] = {
            "params": serialised_params,
            "model_items": len(inputs.model),
            "memory_items": len(inputs.hits),
            "conflicts": len(conflicts),
            "confirmed": len(confirmed),
            "changed": len(changed),
            "items": rows,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    except Exception as error:  # pragma: no cover - diagnostics must never lose a score
        logger.warning(
            "Could not write tail-aware trace for Game %s: %s", context.game_id, error
        )


def _evidence_json(evidence: Evidence | None) -> dict[str, float] | None:
    if evidence is None:
        return None
    return {
        "coverage_probability": evidence.coverage_probability,
        "price_low": evidence.price_low,
        "price_median": evidence.price_median,
        "price_high": evidence.price_high,
    }


def _submission_json(submission: Submission) -> dict[str, float]:
    return {"charge": submission.charge, "limit": submission.limit}


__all__ = ["baseline", "tail_aware"]
