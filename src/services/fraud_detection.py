"""
Fraud detection: Line Items whose Limit must be locked to zero.

A Line Item is fraudulent if it is not insured by the policy or if it is
unrelated to the reported damage. One LLM call per item (concurrent) acting
as a claims auditor; price inflation (the third fraud category) is decided
downstream by comparing the opponent's Charge against the Fair Value estimate
from `src/services/t_calc.py`.

A failed check never marks an item fraudulent (rejecting a fair claim costs
1.5a, so uncertainty defaults to "not fraud").
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from src.data.models import CaseData, FraudDecision, LineItem
from src.services.t_calc import LLM_TIMEOUT_SECONDS, _get_client, _model_name

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a senior insurance claims auditor. You review one invoice line item
from a damage case and decide whether it violates the claim:

1. covered: is the item insured by the policy, with no exclusion applying?
2. related: is the item related to the reported damage (a plausible repair or
   replacement for it)?

An item that fails either check is fraudulent and the insurer should not pay
anything for it. Do NOT judge the price here; only coverage and relation.
Respond only with the requested JSON.
"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "violation_check",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "covered": {
                "type": "boolean",
                "description": "Insured by the policy, no exclusion applies",
            },
            "related": {
                "type": "boolean",
                "description": "Related to the reported damage",
            },
            "confidence": {"type": "number"},
            "reasoning": {"type": "string"},
        },
        "required": ["covered", "related", "confidence", "reasoning"],
    },
}


def _check_item(line_item: LineItem, case: CaseData) -> bool:
    """Return True if the Line Item is fraudulent (uncovered or unrelated)."""
    prompt = (
        "Check this invoice line item for violations.\n\n"
        f"=== INSURANCE POLICY ===\n{case.policy_text}\n\n"
        f"=== DAMAGE DESCRIPTION ===\n{case.description_text}\n\n"
        "=== LINE ITEM ===\n"
        f"{json.dumps(line_item.to_dict(), ensure_ascii=False)}\n"
    )
    response = _get_client().chat.completions.create(
        model=_model_name(),
        temperature=0.0,
        timeout=LLM_TIMEOUT_SECONDS,
        response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    payload = json.loads(response.choices[0].message.content)
    return not (bool(payload["covered"]) and bool(payload["related"]))


async def detect_fraud(case: CaseData) -> FraudDecision:
    if not case.line_items:
        return FraudDecision()
    results = await asyncio.gather(
        *(asyncio.to_thread(_check_item, item, case) for item in case.line_items),
        return_exceptions=True,
    )
    fraud_indices: set[int] = set()
    for item, result in zip(case.line_items, results):
        if isinstance(result, BaseException):
            logger.warning("Fraud check failed for Line Item %s: %s", item.index, result)
            continue
        if result:
            fraud_indices.add(item.index)
    return FraudDecision(fraud_indices=frozenset(fraud_indices))
