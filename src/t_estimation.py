"""
Line-item T-estimation.

For each invoice line item there is a secret threshold `t`: the maximum gross
total (quantity x unit price, incl. VAT) a claims expert would still accept.

This module estimates t as the policy-adjusted fair value of the line item; it
deliberately does NOT judge coverage or relation to the damage (that lives in
`src/violation_check.py`). This lets the charge price `a` track t even for
items we would reject as insurers.

Speed: designed for the 1-minute game window.
- The policy is condensed once per distinct wording (`src/policy_digest.py`)
  and cached on disk, so repeated policies cost zero LLM calls.
- Case photos are downscaled and encoded once per case (`encode_case_images`)
  and shared across all per-item calls, which run in parallel.
- One LLM round-trip per line item, with a hard timeout; `estimate_t_safe`
  never raises, returning a zero-confidence fallback instead so a slow or
  failed call can never block submission.

`estimate_t` returns a `TEstimate` with:

- `t_estimate`: fair gross total (EUR) = unit price x quantity, clamped into
  [t_low, t_high] in code
- `t_low` / `t_high`: a confidence interval believed to contain the true t
- `confidence`: 0..1 self-reported confidence (0.0 marks a fallback)
- `flags`: pricing caveats found in the documents (upgrade, preventive,
  pre_existing, unproven, unrelated, duplicate, fee_padding)
- `reasoning`: short justification (useful for the strategy write-up)

Environment variables (same conventions as `src/api/llm.py`):
- `AZURE_OPENAI_API_KEY`, `OPENAI_API_KEY`, or `OPENAI_KEY`: API key.
- `AZURE_OPENAI_ENDPOINT`: base URL (default: the team's Azure v1 endpoint).
- `AZURE_OPENAI_MODEL` or `OPENAI_MODEL`: deployment name (default:
  `gpt-5.4-mini`).
"""

from __future__ import annotations

import base64
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import OpenAI
from PIL import Image

from src.parse_invoice import LineItem
from src.policy_digest import digest_policy

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_AZURE_ENDPOINT = "https://claim-to-fame-ai.openai.azure.com/openai/v1/"

LLM_TIMEOUT_SECONDS = 25.0
MAX_IMAGE_EDGE = 1024

FLAG_VALUES = [
    "upgrade",
    "preventive",
    "pre_existing",
    "unproven",
    "unrelated",
    "duplicate",
    "fee_padding",
]

SYSTEM_PROMPT = """\
You are a senior insurance claims expert. You price ONE invoice line item from
a damage case: estimate the maximum gross total price (unit price x quantity,
including 19% German VAT) that a claims expert would still consider
appropriate. This threshold is called t.

Rules:
- ALWAYS price the work or item itself at fair market value, even when it is
  pre-existing, unproven, unrelated or otherwise objectionable — NEVER return
  0 because of such doubts. Record every doubt in `flags` instead; whether to
  pay is decided elsewhere. (Only a genuinely worthless item prices near 0.)
  Example: a router claimed without the required diagnostic report is flagged
  `unproven` but still priced at the market price of a comparable router.
- Apply the policy digest's pricing rules: where the invoice describes an
  upgrade over the pre-loss standard, price the LIKE-FOR-LIKE equivalent (the
  pre-loss standard), not the upgraded version, and flag `upgrade`.
- Flag `preventive` for precautionary work on parts not confirmed affected,
  `pre_existing` for damage predating the event, `unproven` where required
  proof/reports are missing, `unrelated` where the item does not belong to the
  described damage, `duplicate` where another line item already covers the
  same work, and `fee_padding` for admin fees, repeated call-outs or vehicle
  costs beyond one reasonable charge per trade.
- Use realistic current German market prices and trade rates (e.g. skilled
  plumber/electrician 60-100 EUR/h gross; drying unit rental 40-70 EUR/day;
  call-out/vehicle 30-60 EUR). Use price anchors stated in the documents when
  available.
- `unit_price` is the fair gross price per unit given in the line item
  (per pcs / hr / m2 / m; for "flat rate" or missing quantity use the total
  and quantity 1). The total t = unit_price x quantity is computed in code.
- Use the photos, if provided, to judge damage extent, room size and item
  quality against the claimed quantities.
- Be realistic, not generous: t is the highest price still defensible as fair.
- Give a confidence interval [t_low, t_high] for the TOTAL that you believe
  contains the true threshold, and a confidence score between 0 and 1.
Respond only with the requested JSON.
"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "t_estimate",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "unit_price": {
                "type": "number",
                "description": "Fair gross price per unit (EUR)",
            },
            "quantity": {
                "type": "number",
                "description": "Quantity from the line item (1 if flat rate/missing)",
            },
            "t_low": {"type": "number", "description": "Lower bound for the total"},
            "t_high": {"type": "number", "description": "Upper bound for the total"},
            "confidence": {"type": "number"},
            "flags": {
                "type": "array",
                "items": {"type": "string", "enum": FLAG_VALUES},
            },
            "reasoning": {"type": "string"},
        },
        "required": [
            "unit_price",
            "quantity",
            "t_low",
            "t_high",
            "confidence",
            "flags",
            "reasoning",
        ],
    },
}


@dataclass(frozen=True, slots=True)
class TEstimate:
    """Estimated fair-value threshold for a single invoice line item."""

    t_estimate: float
    t_low: float
    t_high: float
    confidence: float
    reasoning: str
    flags: tuple[str, ...] = field(default=())


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
    return OpenAI(
        api_key=key, base_url=endpoint, timeout=LLM_TIMEOUT_SECONDS, max_retries=1
    )


def encode_case_images(image_paths: list[Path]) -> list[str]:
    """Downscale and base64-encode case photos once, shared by all item calls."""
    encoded: list[str] = []
    for path in image_paths:
        try:
            with Image.open(path) as img:
                img = img.convert("RGB")
                img.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=80)
            encoded.append(base64.b64encode(buffer.getvalue()).decode("ascii"))
        except OSError:
            continue
    return encoded


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sanitize(payload: dict[str, Any]) -> TEstimate:
    unit_price = max(0.0, float(payload["unit_price"]))
    quantity = max(0.0, float(payload["quantity"])) or 1.0
    t = unit_price * quantity
    t_low = max(0.0, float(payload["t_low"]))
    t_high = max(0.0, float(payload["t_high"]))
    if t_low > t_high:
        t_low, t_high = t_high, t_low
    flags = tuple(f for f in payload.get("flags", []) if f in FLAG_VALUES)
    return TEstimate(
        t_estimate=_clamp(t, t_low, t_high),
        t_low=t_low,
        t_high=t_high,
        confidence=_clamp(float(payload["confidence"]), 0.0, 1.0),
        reasoning=str(payload["reasoning"]),
        flags=flags,
    )


def estimate_t(
    line_item: LineItem,
    policy_path: Path,
    description_path: Path,
    all_line_items: list[LineItem] | None = None,
    encoded_images: list[str] | None = None,
    policy_summary: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> TEstimate:
    """Estimate the fair-value threshold t for one invoice line item."""
    if policy_summary is None:
        try:
            policy_summary = digest_policy(policy_path, model=model, api_key=api_key)
        except Exception:  # noqa: BLE001 - fall back, never block the round
            policy_summary = policy_path.read_text(encoding="utf-8", errors="replace")
    description_text = description_path.read_text(encoding="utf-8", errors="replace")

    prompt = (
        "Estimate the fair-value threshold t for the TARGET line item.\n\n"
        f"=== POLICY DIGEST ===\n{policy_summary}\n\n"
        f"=== DAMAGE DESCRIPTION ===\n{description_text}\n\n"
    )
    if all_line_items:
        prompt += (
            "=== ALL LINE ITEMS OF THIS INVOICE (context: check for duplicates, "
            "repeated fees, cross-references) ===\n"
            f"{json.dumps(all_line_items, ensure_ascii=False, default=str)}\n\n"
        )
    prompt += (
        "=== TARGET LINE ITEM ===\n"
        f"{json.dumps(line_item, ensure_ascii=False, default=str)}\n"
    )

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image_b64 in encoded_images or []:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
            }
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
            {"role": "user", "content": content},
        ],
    )
    return _sanitize(json.loads(response.choices[0].message.content))


def estimate_t_safe(
    line_item: LineItem,
    policy_path: Path,
    description_path: Path,
    all_line_items: list[LineItem] | None = None,
    encoded_images: list[str] | None = None,
    policy_summary: str | None = None,
) -> TEstimate:
    """Like `estimate_t`, but never raises: returns a zero-confidence fallback."""
    try:
        return estimate_t(
            line_item,
            policy_path,
            description_path,
            all_line_items=all_line_items,
            encoded_images=encoded_images,
            policy_summary=policy_summary,
        )
    except Exception as error:  # noqa: BLE001 - submission must never be blocked
        return TEstimate(
            t_estimate=0.0,
            t_low=0.0,
            t_high=0.0,
            confidence=0.0,
            reasoning=f"fallback: estimation failed ({error})",
        )
