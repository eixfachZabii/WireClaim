from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from src.api import get_llm_client, get_model_name
from src.data.models import CaseData, FraudDecision, LineItem

logger = logging.getLogger(__name__)
FRAUD_TIMEOUT_SECONDS = 15.0
FRAUD_CONFIDENCE = 0.85

# A quote only proves an exclusion if it is long enough to be specific and actually
# contains exclusion language. At 12 characters against a ~63,000 character Policy,
# "the schedule" and "the policyholder" both passed -- which is how Games 10 and 11
# came to flag 100% of Line Items and pay 65,806 and 36,017 in wrongful-rejection
# penalties.
MIN_QUOTE_LENGTH = 60
EXCLUSION_MARKERS = (
    "not covered", "no cover", "excluded", "exclusion", "does not cover",
    "is not insured", "no indemnity", "not indemnified", "does not extend",
    "not apply", "shall not",
)

# A circuit breaker for the failure mode that cost us Game 10: the gate flagging every
# Line Item, which zeroes every Limit and turns each fair claim into a 1.5a penalty.
#
# It is deliberately a count and not a share. Settled Games 1-13 carry only 2-4 Line
# Items each (max index 4), so any percentage threshold is hostage to rounding: at 35%
# of 4 items a single legitimate second flag would be thrown away. Only the extreme
# case -- *every* item excluded -- is implausible enough to overrule.
#
# It stays off for Cases of 2, because a genuinely whole-uncovered Case exists (Game 3,
# 2 items, t = 0 on both). Tripping it is also cheap: discarding the verdict falls back
# to the Strategy's own posterior Limit, not to an unbounded one.
MIN_ITEMS_FOR_ALL_FLAGGED_BREAKER = 3

SYSTEM_PROMPT = """Review one invoice Line Item for a confirmed coverage or relatedness violation.

Coverage and relatedness are the default. A suspicious detail in the Damage Description is not an exclusion. Return `covered=false` or `related=false` only when `exclusion_quote` contains an exact Policy clause proving an exclusion, missing requirement, scope restriction, or that this Line Item cannot be covered. Otherwise keep both verdicts true with an appropriate confidence score.

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


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _is_policy_quote(quote: str, policy_text: str) -> bool:
    normalized_quote = _normalize(quote)
    if len(normalized_quote) < MIN_QUOTE_LENGTH:
        return False
    if not any(marker in normalized_quote for marker in EXCLUSION_MARKERS):
        return False
    return normalized_quote in _normalize(policy_text)


def _check_item(line_item: LineItem, case: CaseData) -> bool:
    prompt = (
        f"=== POLICY ===\n{case.policy_text}\n\n"
        f"=== DAMAGE DESCRIPTION ===\n{case.description_text}\n\n"
        f"=== LINE ITEM ===\n{json.dumps(line_item.to_dict(), ensure_ascii=False)}"
    )
    response = get_llm_client().chat.completions.create(
        model=get_model_name(),
        temperature=0.0,
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
        and _is_policy_quote(str(payload.get("exclusion_quote", "")), case.policy_text)
    )


async def detect_fraud(case: CaseData) -> FraudDecision:
    results = await asyncio.gather(
        *(asyncio.to_thread(_check_item, line_item, case) for line_item in case.line_items),
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
    if total >= MIN_ITEMS_FOR_ALL_FLAGGED_BREAKER and len(indices) == total:
        logger.error(
            "Fraud gate flagged every one of %s Line Items for Game %s - discarding the whole "
            "verdict rather than zeroing every Limit.",
            total, case.game_id,
        )
        return FraudDecision(fraud_indices=frozenset())
    return FraudDecision(fraud_indices=frozenset(indices))
