from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from src.api import get_llm_client, get_model_name
from src.data.models import CaseData, FraudDecision, LineItem
from src.evidence.policy.quotes import is_policy_quote
from src.runtime.timing import format_fraud_lock_card, log_timing, start_timer

logger = logging.getLogger(__name__)
FRAUD_TIMEOUT_SECONDS = 15.0
FRAUD_CONFIDENCE = 0.85

# A circuit breaker for the failure mode that cost us Game 10: the gate flagging every
# Line Item, which zeroes every Limit and turns each fair claim into a 1.5a penalty.
#
# Cases are large -- settled Games carry 2 to 39 Line Items, median 15 -- so a share is
# the right denominator, and the measured rate of genuinely uncovered items is low: in
# Game 8, 3 of 39 items drew a Charge of 0 from every team in the field.
#
# The allowance floor matters as much as the share. Small Cases exist (Games 3 and 6
# have 2 Line Items each) and Game 3 was genuinely uncovered end to end, so a share
# alone would overrule a correct verdict on a 2-item Case. Below the floor we never
# second-guess the gate.
#
# Tripping the breaker is cheap: it discards the mask and falls back to the Strategy's
# own posterior Limit, never to an unbounded one.
MAX_FLAGGED_SHARE = 0.35
MIN_FLAGGED_ALLOWANCE = 2

SYSTEM_PROMPT = """Review one invoice Line Item for a confirmed coverage or relatedness violation.

Coverage and relatedness are the default. A suspicious detail in the Damage Description is not an exclusion. Return `covered=false` or `related=false` only when `exclusion_quote` contains an exact Policy clause proving an exclusion, missing requirement, scope restriction, or that this Line Item cannot be covered. Otherwise keep both verdicts true with an appropriate confidence score.

`quantity_missing: true` means the invoice printed no amount and no unit for this Line Item, only dashes. Every one of the 20 such Line Items in the settled Games had a Fair Value of exactly 0, so treat it as strong evidence the item is not indemnifiable — but still cite the Policy clause that says so.

Do not judge price inflation, Charge, Limit, or Fair Value here."""

RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "coverage_relatedness_check",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "covered": {"type": "boolean"},
            "related": {"type": "boolean"},
            "confidence": {"type": "number"},
            "exclusion_quote": {"type": "string"},
            "reasoning": {"type": "string"},
        },
        "required": ["covered", "related", "confidence", "exclusion_quote", "reasoning"],
    },
}



def _confidence(value: Any) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def _check_item(line_item: LineItem, case: CaseData) -> bool:
    prompt = (
        f"=== POLICY ===\n{case.policy_text}\n\n"
        f"=== DAMAGE DESCRIPTION ===\n{case.description_text}\n\n"
        f"=== LINE ITEM ===\n{json.dumps(line_item.to_dict(), ensure_ascii=False)}"
    )
    response = get_llm_client().chat.completions.create(
        model=get_model_name(),
        timeout=FRAUD_TIMEOUT_SECONDS,
        response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    violation = not (bool(payload.get("covered")) and bool(payload.get("related")))
    return (
        violation
        and _confidence(payload.get("confidence")) >= FRAUD_CONFIDENCE
        and is_policy_quote(str(payload.get("exclusion_quote", "")), case.policy_text)
    )


async def _timed_check(line_item: LineItem, case: CaseData) -> bool:
    started_at = start_timer()
    try:
        result = await asyncio.to_thread(_check_item, line_item, case)
    except Exception:
        log_timing(logger, "fraud_item", started_at, "failed", game=case.game_id, line_item=line_item.index)
        raise
    if result:
        log_timing(logger, "fraud_item", started_at, game=case.game_id, line_item=line_item.index, fraud=True)
    return result


async def detect_fraud(case: CaseData) -> FraudDecision:
    started_at = start_timer()
    results = await asyncio.gather(
        *(_timed_check(line_item, case) for line_item in case.line_items),
        return_exceptions=True,
    )
    indices: set[int] = set()
    for line_item, result in zip(case.line_items, results):
        if isinstance(result, BaseException):
            logger.warning("Fraud check failed for Line Item %s: %s", line_item.index, result)
            continue
        if result:
            indices.add(line_item.index)
    total = len(case.line_items)
    logger.info("Fraud gate flagged %s/%s Line Items for Game %s.", len(indices), total, case.game_id)
    allowance = max(MIN_FLAGGED_ALLOWANCE, MAX_FLAGGED_SHARE * total)
    if len(indices) > allowance:
        logger.error(
            "Fraud gate flagged %s of %s Line Items for Game %s, over the allowance of %.1f - "
            "discarding the whole verdict rather than zeroing that many Limits.",
            len(indices), total, case.game_id, allowance,
        )
        indices.clear()
    locked_items = tuple(
        (line_item.index, line_item.name)
        for line_item in case.line_items
        if line_item.index in indices
    )
    if locked_items:
        logger.warning("%s", format_fraud_lock_card(case.game_id, locked_items))
    decision = FraudDecision(fraud_indices=frozenset(indices))
    log_timing(logger, "fraud_detection", started_at, game=case.game_id, locks=len(indices))
    return decision
