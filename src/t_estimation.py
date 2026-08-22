"""
Line-item T-estimation.

For each invoice line item there is a secret threshold `t`: the maximum gross
total (quantity x unit price, incl. VAT) a claims expert would still accept.
Items not covered by the policy or unrelated to the damage have `t = 0`.

`estimate_t` sends the policy, the damage description, and one line item to an
LLM acting as a claims expert and returns a `TEstimate` with:

- `covered`: covered by the policy AND related to the damage
- `t_estimate`: best point estimate of the fair gross total (EUR)
- `t_low` / `t_high`: a confidence interval believed to contain the true t
- `confidence`: 0..1 self-reported confidence
- `reasoning`: short justification (useful for the strategy write-up)

Environment variables (same conventions as `src/api/llm.py`):
- `AZURE_OPENAI_API_KEY`, `OPENAI_API_KEY`, or `OPENAI_KEY`: API key.
- `AZURE_OPENAI_ENDPOINT`: base URL (default: the team's Azure v1 endpoint).
- `AZURE_OPENAI_MODEL` or `OPENAI_MODEL`: deployment name (default:
  `gpt-5.4-mini`).
The team's Azure endpoint and deployment are used as defaults, so setting the
API key alone is enough.
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
You are a senior insurance claims expert. You review one invoice line item
from a damage case and estimate the maximum gross total price (quantity x
unit price, including VAT) that a claims expert would still consider
appropriate. This threshold is called t.

Rules:
- The item is only covered if the policy covers it AND it is related to the
  reported damage AND no exclusion applies. If not covered, t = 0.
- t is always the gross TOTAL for the whole line item, never a per-unit or
  net price. Multiply by the quantity where one is given.
- Use price anchors from the case documents when available (e.g. a stated
  market value). Otherwise use realistic current market prices in EUR for the
  region implied by the documents (default: Germany).
- Be realistic, not generous: t is the highest price still defensible as fair.
- Give a confidence interval [t_low, t_high] that you believe contains the
  true threshold, and a confidence score between 0 and 1.
Respond only with the requested JSON.
"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "t_estimate",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "covered": {
                "type": "boolean",
                "description": "Covered by policy AND related to the damage",
            },
            "t_estimate": {
                "type": "number",
                "description": "Best estimate of t (gross total, EUR). 0 if not covered.",
            },
            "t_low": {"type": "number"},
            "t_high": {"type": "number"},
            "confidence": {"type": "number"},
            "reasoning": {"type": "string"},
        },
        "required": [
            "covered",
            "t_estimate",
            "t_low",
            "t_high",
            "confidence",
            "reasoning",
        ],
    },
}


@dataclass(frozen=True, slots=True)
class TEstimate:
    """Estimated fair-value threshold for a single invoice line item."""

    covered: bool
    t_estimate: float
    t_low: float
    t_high: float
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


def _sanitize(payload: dict[str, Any]) -> TEstimate:
    covered = bool(payload["covered"])
    t = max(0.0, float(payload["t_estimate"]))
    t_low = max(0.0, float(payload["t_low"]))
    t_high = max(0.0, float(payload["t_high"]))
    if not covered:
        t = t_low = t_high = 0.0
    if t_low > t_high:
        t_low, t_high = t_high, t_low
    return TEstimate(
        covered=covered,
        t_estimate=_clamp(t, t_low, t_high) if covered else 0.0,
        t_low=t_low,
        t_high=t_high,
        confidence=_clamp(float(payload["confidence"]), 0.0, 1.0),
        reasoning=str(payload["reasoning"]),
    )


def estimate_t(
    line_item: LineItem,
    policy_path: Path,
    description_path: Path,
    model: str | None = None,
    api_key: str | None = None,
) -> TEstimate:
    """Estimate the fair-value threshold t for one invoice line item."""
    policy_text = policy_path.read_text(encoding="utf-8", errors="replace")
    description_text = description_path.read_text(encoding="utf-8", errors="replace")
    prompt = (
        "Estimate the fair-value threshold t for this invoice line item.\n\n"
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
