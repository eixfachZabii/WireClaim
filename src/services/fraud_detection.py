from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from src.api import get_llm_client
from src.data.models import CaseData, FraudDecision, LineItem

logger = logging.getLogger(__name__)
FRAUD_TIMEOUT_SECONDS = 15.0
FRAUD_CONFIDENCE = 0.85

SYSTEM_PROMPT = """Review one invoice Line Item for a confirmed coverage or relatedness violation.

Return `covered=false` only when a specific Policy exclusion or missing requirement applies. Return `related=false` only when the Line Item does not plausibly address the reported damage. Quote the decisive Policy clause or Case fact in `reasoning`. Do not judge price inflation, Charge, Limit, or Fair Value here.

A false Limit lock wrongfully rejects fair claims, so uncertainty must remain covered and related with a lower confidence score."""

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
            "reasoning": {"type": "string"},
        },
        "required": ["covered", "related", "confidence", "reasoning"],
    },
}


def _model_name() -> str:
    return os.environ.get("AZURE_OPENAI_MODEL") or "gpt-4o"


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
        model=_model_name(),
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
    return violation and _confidence(payload.get("confidence")) >= FRAUD_CONFIDENCE


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
    return FraudDecision(fraud_indices=frozenset(indices))
