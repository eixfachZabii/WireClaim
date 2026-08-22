from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from src.api import get_llm_client, get_model_name
from src.data.models import CaseData, FraudDecision, LineItem
from src.timing import log_timing, start_timer

logger = logging.getLogger(__name__)
FRAUD_TIMEOUT_SECONDS = 15.0
FRAUD_CONFIDENCE = 0.85
MIN_QUOTE_LENGTH = 12

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
    return len(normalized_quote) >= MIN_QUOTE_LENGTH and normalized_quote in _normalize(policy_text)


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
        and _is_policy_quote(str(payload.get("exclusion_quote", "")), case.policy_text)
    )


async def _timed_check(line_item: LineItem, case: CaseData) -> bool:
    started_at = start_timer()
    try:
        result = await asyncio.to_thread(_check_item, line_item, case)
    except Exception:
        log_timing(logger, "fraud_item", started_at, "failed", game=case.game_id, line_item=line_item.index)
        raise
    log_timing(logger, "fraud_item", started_at, game=case.game_id, line_item=line_item.index, fraud=result)
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
    decision = FraudDecision(fraud_indices=frozenset(indices))
    log_timing(logger, "fraud_detection", started_at, game=case.game_id, locks=len(indices))
    return decision
