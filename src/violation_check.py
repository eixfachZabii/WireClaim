"""
Line-item fraud / violation detection.

A line item is fraudulent (t = 0) if it is not insured by the policy, or if
it is unrelated to the reported damage. `check_violation` sends the policy,
the damage description, and one line item to an LLM acting as a claims
auditor and returns a `ViolationCheck` with:

- `covered`: insured by the policy (no exclusion applies)
- `related`: related to the reported damage
- `fraudulent`: True if either check fails
- `confidence`: 0..1 self-reported confidence
- `reasoning`: short justification

Price inflation (the third fraud category) cannot be judged from the item
alone; it is decided downstream by comparing the opponent's charge `a`
against the estimated threshold from `src/t_estimation.py`.

Environment variables (same conventions as `src/t_estimation.py`):
- `AZURE_OPENAI_API_KEY`, `OPENAI_API_KEY`, or `OPENAI_KEY`: API key.
- `AZURE_OPENAI_ENDPOINT`: base URL (default: the team's Azure v1 endpoint).
- `AZURE_OPENAI_MODEL` or `OPENAI_MODEL`: deployment name (default:
  `gpt-5.4-mini`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from src.parse_invoice import LineItem

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_AZURE_ENDPOINT = "https://claim-to-fame-ai.openai.azure.com/openai/v1/"

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


@dataclass(frozen=True, slots=True)
class ViolationCheck:
    """Fraud verdict for a single invoice line item (price not considered)."""

    covered: bool
    related: bool
    fraudulent: bool
    confidence: float
    reasoning: str


def _get_client(api_key: str | None = None) -> OpenAI:
    key = (
        api_key
        or os.environ.get("AZURE_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_KEY")
    )
    if not key:
        raise ValueError(
            "Missing API key. Set 'AZURE_OPENAI_API_KEY' (or 'OPENAI_API_KEY' / "
            "'OPENAI_KEY') in the environment or .env file."
        )
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or DEFAULT_AZURE_ENDPOINT
    if not endpoint.startswith(("http://", "https://")):
        endpoint = DEFAULT_AZURE_ENDPOINT
    return OpenAI(api_key=key, base_url=endpoint)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sanitize(payload: dict[str, Any]) -> ViolationCheck:
    covered = bool(payload["covered"])
    related = bool(payload["related"])
    return ViolationCheck(
        covered=covered,
        related=related,
        fraudulent=not (covered and related),
        confidence=_clamp(float(payload["confidence"]), 0.0, 1.0),
        reasoning=str(payload["reasoning"]),
    )


def check_violation(
    line_item: LineItem,
    policy_path: Path,
    description_path: Path,
    model: str | None = None,
    api_key: str | None = None,
) -> ViolationCheck:
    """Check one invoice line item for coverage/relation violations."""
    policy_text = policy_path.read_text(encoding="utf-8", errors="replace")
    description_text = description_path.read_text(encoding="utf-8", errors="replace")
    prompt = (
        "Check this invoice line item for violations.\n\n"
        f"=== INSURANCE POLICY ===\n{policy_text}\n\n"
        f"=== DAMAGE DESCRIPTION ===\n{description_text}\n\n"
        f"=== LINE ITEM ===\n{json.dumps(line_item, ensure_ascii=False, default=str)}\n"
    )

    client = _get_client(api_key)
    model_name = (
        model
        or os.environ.get("AZURE_OPENAI_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or DEFAULT_MODEL
    )
    response = client.chat.completions.create(
        model=model_name,
        temperature=0.0,
        response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return _sanitize(json.loads(response.choices[0].message.content))
