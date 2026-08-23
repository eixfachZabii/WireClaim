"""Strategy 4 — a tail-aware, lower-priority live comparison.

The strategy starts from Strategy 2's completed Proposal and recorded evidence. It looks
only for the narrow failure mode measured in the tail experiment: a generic Price Memory
match has pulled a much larger current-Case model estimate toward an ordinary historical
price. A targeted reread must independently confirm the expensive interpretation before
anything changes.

Strategy 4 intentionally runs *after* Strategy 2 in :mod:`src.strategies.router`. It does
not launch a second copy of Strategy 2's two-draw ensemble, cannot contend with the winning
track, and has priority 2 versus Strategy 2's priority 4. The router records its Proposal
for later replay but never submits it while Strategy 2 exists.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.data.models import CaseData, ItemPrice, Proposal
from src.evidence.memory import PriceMemoryHit, lookup, normalise
from src.pricing.engine import COVERAGE_FLOOR, LIMIT_QUANTILE, Evidence, implied_sigma
from src.runtime.decisions import load as load_decisions
from src.strategies.strategy2.blend import blend
from src.strategies.strategy2.channels import unit_of
from src.strategies.strategy2.constants import (
    BAND_Z,
    LLM_TIMEOUT_SECONDS,
    MEMORY_SIGMA,
    MODEL_SIGMA_PRIOR,
    STRATEGY_NAME as BASELINE_STRATEGY,
    SUBMISSION_RESERVE_SECONDS,
)
from src.strategies.strategy2.model import request_evidence
from src.strategies.strategy4.constants import (
    AGREEMENT_RATIO,
    CONFIRMATION_RATIO,
    CONFLICT_RATIO,
    LARGE_ITEM_REREAD_THRESHOLD,
    MIN_ADJUDICATION_SECONDS,
    STRATEGY_NAME,
    TAIL_PROBABILITY,
    TAIL_THRESHOLD,
    TRUSTED_TAIL_LIMIT_CEILING,
)

logger = logging.getLogger(__name__)

TRACE_DIR = Path("var/strategy4")
_PRICE_GRID_POINTS = 160

# Words that describe a claim but do not identify the object, scope or service whose price
# should transfer between Cases. The disagreement and reread gates must still both pass.
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


@dataclass(frozen=True)
class Conflict:
    index: int
    name: str
    memory_hit: PriceMemoryHit
    memory: Evidence
    model: Evidence
    coverage_probability: float


async def propose(
    case: CaseData,
    deadline: float | None = None,
    *,
    baseline: Proposal | None = None,
) -> Proposal | None:
    """Return a complete Strategy 4 counterfactual based on Strategy 2's winner."""
    if baseline is None or baseline.source != BASELINE_STRATEGY or baseline.is_empty:
        return None

    prices = {
        price.index: ItemPrice(
            price.index,
            price.charge_price,
            price.acceptance_limit,
            STRATEGY_NAME,
        )
        for price in baseline.prices
    }
    payload = load_decisions(case.game_id)
    # A retry of the same Game can leave an earlier log on disk. Strategy 4 is learning
    # infrastructure, so contaminating its measurement is worse than skipping a conflict.
    # Require the recorded Strategy 2 prices to match the Proposal the router just passed.
    conflicts = (
        _find_conflicts(case, payload)
        if _matches_baseline(payload, baseline)
        else {}
    )
    if not conflicts:
        proposal = Proposal(STRATEGY_NAME, tuple(prices[index] for index in sorted(prices)))
        _write_trace(case.game_id, conflicts, {}, set(), proposal, "no-conflicts")
        return proposal

    timeout = _adjudication_timeout(deadline)
    if timeout < MIN_ADJUDICATION_SECONDS:
        proposal = Proposal(STRATEGY_NAME, tuple(prices[index] for index in sorted(prices)))
        _write_trace(case.game_id, conflicts, {}, set(), proposal, "deadline")
        return proposal

    adjudicated = await _adjudicate(case, conflicts, timeout)
    confirmed: set[int] = set()
    for index, conflict in conflicts.items():
        reread = adjudicated.get(index)
        if not _confirms_tail(conflict.model, conflict.memory, reread):
            continue
        confirmed.add(index)
        tail = blend([{index: conflict.model}, {index: reread}])[index]
        charge, limit = _mixture_prices(
            conflict.memory,
            tail,
            covered=conflict.coverage_probability,
        )
        prices[index] = ItemPrice(index, charge, limit, STRATEGY_NAME)

    proposal = Proposal(STRATEGY_NAME, tuple(prices[index] for index in sorted(prices)))
    _write_trace(case.game_id, conflicts, adjudicated, confirmed, proposal, "completed")
    return proposal


def _find_conflicts(
    case: CaseData, payload: Mapping[str, Any] | None
) -> dict[int, Conflict]:
    """Recover the pre-memory model level from Strategy 2's combined evidence."""
    if not payload or payload.get("game_id") != case.game_id:
        return {}
    items = {
        int(raw["index"]): raw
        for raw in payload.get("items") or ()
        if isinstance(raw, Mapping) and raw.get("index") is not None
    }
    conflicts: dict[int, Conflict] = {}
    for line_item in case.line_items:
        raw = items.get(line_item.index)
        if raw is None or raw.get("quantity_missing"):
            continue
        combined = _logged_evidence(line_item.index, raw)
        if combined is None:
            continue
        if "B:memory" not in tuple(raw.get("channels") or ()):
            # No memory anchor, so the disagreement gate below cannot be evaluated. Large
            # estimates are still sent for adjudication, **for the record only** -- see
            # `LARGE_ITEM_REREAD_THRESHOLD`. `memory` and `model` are deliberately the same
            # object, which makes `_confirms_tail` structurally unable to fire (it needs the
            # model to sit at twice the incumbent, and here they are equal), so the Proposal
            # is unchanged and the whole value is the reread recorded in the trace.
            if combined.price_median >= LARGE_ITEM_REREAD_THRESHOLD:
                conflicts[line_item.index] = Conflict(
                    line_item.index,
                    line_item.name,
                    PriceMemoryHit(
                        name=line_item.name,
                        key="",
                        match="large-item-review",
                        low=combined.price_low,
                        median=combined.price_median,
                        high=combined.price_high,
                        observations=0,
                        games=(),
                        basis="gross",
                    ),
                    combined,
                    combined,
                    combined.coverage_probability,
                )
            continue
        try:
            hit = lookup(
                line_item.name,
                unit=unit_of(line_item.name),
                quantity=max(line_item.quantity, 1.0),
            )
        except Exception as error:
            logger.warning(
                "Strategy 4 memory lookup failed for Line Item %s: %s",
                line_item.index,
                error,
            )
            continue
        recovered = _recover_model_median(combined, hit)
        if hit is None or recovered is None:
            continue
        if recovered < max(TAIL_THRESHOLD, hit.median * CONFLICT_RATIO):
            continue
        if not _contextually_weak(line_item.name, hit):
            continue
        memory = Evidence(
            line_item.index,
            combined.coverage_probability,
            hit.low,
            hit.median,
            hit.high,
        )
        model = Evidence(
            line_item.index,
            combined.coverage_probability,
            recovered * math.exp(-BAND_Z * MODEL_SIGMA_PRIOR),
            recovered,
            recovered * math.exp(BAND_Z * MODEL_SIGMA_PRIOR),
        )
        conflicts[line_item.index] = Conflict(
            line_item.index,
            line_item.name,
            hit,
            memory,
            model,
            combined.coverage_probability,
        )
    return conflicts


def _matches_baseline(
    payload: Mapping[str, Any] | None, baseline: Proposal
) -> bool:
    if not payload or payload.get("strategy") != BASELINE_STRATEGY:
        return False
    logged = {
        int(raw["index"]): raw
        for raw in payload.get("items") or ()
        if isinstance(raw, Mapping) and raw.get("index") is not None
    }
    current = baseline.by_index()
    if set(logged) != set(current):
        return False
    try:
        return all(
            math.isclose(float(logged[index]["charge"]), price.charge_price, abs_tol=0.01)
            and math.isclose(
                float(logged[index]["limit"]), price.acceptance_limit, abs_tol=0.01
            )
            for index, price in current.items()
        )
    except (KeyError, TypeError, ValueError):
        return False


def _logged_evidence(index: int, raw: Mapping[str, Any]) -> Evidence | None:
    values = (
        raw.get("coverage_probability"),
        raw.get("price_low"),
        raw.get("price_median"),
        raw.get("price_high"),
    )
    if any(value is None for value in values):
        return None
    try:
        return Evidence(index, *(float(value) for value in values))
    except (TypeError, ValueError):
        return None


def _recover_model_median(
    combined: Evidence, hit: PriceMemoryHit | None
) -> float | None:
    if hit is None or combined.price_median <= 0 or hit.median <= 0:
        return None
    model_weight = 1.0 / MODEL_SIGMA_PRIOR**2
    memory_weight = 1.0 / MEMORY_SIGMA**2
    recovered_log = (
        (model_weight + memory_weight) * math.log(combined.price_median)
        - memory_weight * math.log(hit.median)
    ) / model_weight
    try:
        recovered = math.exp(recovered_log)
    except OverflowError:
        return None
    return recovered if math.isfinite(recovered) and recovered > 0 else None


def _contextually_weak(current_name: str, hit: PriceMemoryHit) -> bool:
    current = _meaningful_tokens(current_name)
    historical = _meaningful_tokens(hit.name)
    if hit.match == "core" and current.isdisjoint(historical):
        return True
    if normalise(current_name) == normalise(hit.name) and len(current) < 2:
        return True
    return bool(current and historical and current.isdisjoint(historical))


def _meaningful_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalise(value))
        if len(token) > 2 and token not in _GENERIC_WORDS and not token.isdigit()
    }


def _adjudication_timeout(deadline: float | None) -> float:
    if deadline is None:
        return LLM_TIMEOUT_SECONDS
    remaining = deadline - asyncio.get_running_loop().time() - SUBMISSION_RESERVE_SECONDS
    return max(min(LLM_TIMEOUT_SECONDS, remaining), 0.0)


async def _adjudicate(
    case: CaseData, conflicts: Mapping[int, Conflict], timeout: float
) -> dict[int, Evidence]:
    listed = "\n".join(
        f"- POS {conflict.index}: {conflict.name}" for conflict in conflicts.values()
    )
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
            asyncio.to_thread(request_evidence, case, timeout, prompt),
            timeout=timeout,
        )
    except Exception as error:
        logger.warning(
            "Strategy 4 adjudication unavailable for Game %s Line Items %s: %s",
            case.game_id,
            sorted(conflicts),
            error,
        )
        return {}
    return {index: evidence for index, evidence in result.items() if index in conflicts}


def _confirms_tail(
    current: Evidence,
    remembered: Evidence,
    reread: Evidence | None,
) -> bool:
    if reread is None or remembered.price_median <= 0:
        return False
    if min(current.price_median, reread.price_median) < (
        remembered.price_median * CONFIRMATION_RATIO
    ):
        return False
    smaller = min(current.price_median, reread.price_median)
    larger = max(current.price_median, reread.price_median)
    return smaller > 0 and larger / smaller <= AGREEMENT_RATIO


def _mixture_prices(
    ordinary: Evidence,
    tail: Evidence,
    *,
    covered: float,
) -> tuple[float, float]:
    ordinary = ordinary.with_defaults()
    tail = tail.with_defaults()
    covered = min(max(covered, 0.0), 1.0)
    charge = max(
        _charge_grid(ordinary, tail),
        key=lambda value: (
            value * _positive_survival(value, ordinary, tail),
            -value,
        ),
    )
    if covered <= COVERAGE_FLOOR:
        limit = 0.0
    else:
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        lower_quantile = _positive_quantile(conditional, ordinary, tail)
        positive_median = _positive_quantile(0.5, ordinary, tail)
        limit = min(
            lower_quantile,
            TRUSTED_TAIL_LIMIT_CEILING * positive_median,
            charge,
        )
    return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)


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


def _positive_survival(value: float, ordinary: Evidence, tail: Evidence) -> float:
    return (1.0 - TAIL_PROBABILITY) * (1.0 - _lognormal_cdf(value, ordinary)) + (
        TAIL_PROBABILITY * (1.0 - _lognormal_cdf(value, tail))
    )


def _positive_cdf(value: float, ordinary: Evidence, tail: Evidence) -> float:
    return (1.0 - TAIL_PROBABILITY) * _lognormal_cdf(value, ordinary) + (
        TAIL_PROBABILITY * _lognormal_cdf(value, tail)
    )


def _lognormal_cdf(value: float, evidence: Evidence) -> float:
    if value <= 0:
        return 0.0
    sigma = implied_sigma(evidence.price_low, evidence.price_median, evidence.price_high)
    if sigma <= 0:
        return 0.0 if value < evidence.price_median else 1.0
    z = math.log(value / evidence.price_median) / sigma
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _positive_quantile(
    quantile: float,
    ordinary: Evidence,
    tail: Evidence,
) -> float:
    quantile = min(max(quantile, 0.0), 1.0)
    if quantile <= 0:
        return 0.0
    upper = max(ordinary.price_high, tail.price_high, 1.0)
    while _positive_cdf(upper, ordinary, tail) < quantile:
        upper *= 2.0
    lower = 0.0
    for _ in range(64):
        midpoint = (lower + upper) / 2.0
        if _positive_cdf(midpoint, ordinary, tail) < quantile:
            lower = midpoint
        else:
            upper = midpoint
    return upper


def _write_trace(
    game_id: int,
    conflicts: Mapping[int, Conflict],
    adjudicated: Mapping[int, Evidence],
    confirmed: set[int],
    proposal: Proposal,
    status: str,
) -> None:
    """Record why Strategy 4 changed—or did not change—a Proposal. Never raises."""
    try:
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        prices = proposal.by_index()
        rows = []
        for index, conflict in conflicts.items():
            reread = adjudicated.get(index)
            rows.append(
                {
                    "index": index,
                    "name": conflict.name,
                    "memory_match": conflict.memory_hit.match,
                    "memory_name": conflict.memory_hit.name,
                    "memory_median": conflict.memory.price_median,
                    "recovered_model_median": conflict.model.price_median,
                    "adjudication_median": None if reread is None else reread.price_median,
                    "confirmed": index in confirmed,
                    "charge": prices[index].charge_price,
                    "limit": prices[index].acceptance_limit,
                }
            )
        (TRACE_DIR / f"game_{game_id:03d}.json").write_text(
            json.dumps(
                {
                    "game_id": game_id,
                    "strategy": STRATEGY_NAME,
                    "status": status,
                    "conflicts": len(conflicts),
                    "confirmed": len(confirmed),
                    "items": rows,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    except Exception as error:  # pragma: no cover - diagnostics never cost a Game
        logger.warning("Could not write Strategy 4 trace for Game %s: %s", game_id, error)


__all__ = ["Conflict", "propose"]
