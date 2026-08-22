"""
Fair Value (t) estimation for all Line Items of a Case.

For each Line Item there is a secret threshold t: the maximum gross total
(quantity x unit price, incl. VAT) a claims expert would still accept. This
module estimates t as the policy-adjusted fair value of the item; it
deliberately does NOT judge coverage or relation to the damage (that lives in
`src/services/fraud_detection.py`), so the Charge can track t even for items
we would reject as insurers.

Speed (built for the 1-minute window):
- The policy is condensed once per distinct wording (`src/policy_digest.py`)
  and cached on disk, so repeated policies cost zero LLM calls.
- Case photos are downscaled and base64-encoded once per Case and shared by
  all per-item calls, which run concurrently (one LLM round-trip per item).
- Hard client timeout; a failed item yields no estimate instead of blocking.

Environment variables (same conventions as `src/api/llm.py`):
- `AZURE_OPENAI_API_KEY`, `OPENAI_API_KEY`, or `OPENAI_KEY`: API key.
- `AZURE_OPENAI_ENDPOINT`: base URL (default: the team's Azure v1 endpoint).
- `AZURE_OPENAI_MODEL` or `OPENAI_MODEL`: deployment (default `gpt-5.4-mini`).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Any

from openai import OpenAI
from PIL import Image

from src.data.models import CaseData, FairValueEstimate, FairValueEstimates, LineItem
from src.policy_digest import digest_policy_text

logger = logging.getLogger(__name__)

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


def _model_name() -> str:
    return (
        os.environ.get("AZURE_OPENAI_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or DEFAULT_MODEL
    )


def encode_case_images(image_paths: tuple[Path, ...]) -> list[str]:
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


def _sanitize(index: int, payload: dict[str, Any]) -> FairValueEstimate:
    unit_price = max(0.0, float(payload["unit_price"]))
    quantity = max(0.0, float(payload["quantity"])) or 1.0
    t = unit_price * quantity
    t_low = max(0.0, float(payload["t_low"]))
    t_high = max(0.0, float(payload["t_high"]))
    if t_low > t_high:
        t_low, t_high = t_high, t_low
    return FairValueEstimate(
        line_item_index=index,
        median=_clamp(t, t_low, t_high),
        lower=t_low,
        upper=t_high,
    )


def _estimate_item(
    line_item: LineItem,
    policy_summary: str,
    description_text: str,
    all_items: list[dict[str, Any]],
    encoded_images: list[str],
) -> FairValueEstimate:
    prompt = (
        "Estimate the fair-value threshold t for the TARGET line item.\n\n"
        f"=== POLICY DIGEST ===\n{policy_summary}\n\n"
        f"=== DAMAGE DESCRIPTION ===\n{description_text}\n\n"
        "=== ALL LINE ITEMS OF THIS INVOICE (context: check for duplicates, "
        "repeated fees, cross-references) ===\n"
        f"{json.dumps(all_items, ensure_ascii=False)}\n\n"
        "=== TARGET LINE ITEM ===\n"
        f"{json.dumps(line_item.to_dict(), ensure_ascii=False)}\n"
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image_b64 in encoded_images:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
            }
        )
    response = _get_client().chat.completions.create(
        model=_model_name(),
        temperature=0.0,
        response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    )
    return _sanitize(line_item.index, json.loads(response.choices[0].message.content))


async def estimate_fair_values(
    case: CaseData,
    strategy_name: str,
) -> FairValueEstimates | None:
    """Estimate the Fair Value of every Line Item of the Case concurrently."""
    if not case.line_items:
        return None
    policy_summary = await asyncio.to_thread(_digest_or_raw, case.policy_text)
    encoded_images = await asyncio.to_thread(encode_case_images, case.image_paths)
    all_items = [item.to_dict() for item in case.line_items]
    results = await asyncio.gather(
        *(
            asyncio.to_thread(
                _estimate_item,
                item,
                policy_summary,
                case.description_text,
                all_items,
                encoded_images,
            )
            for item in case.line_items
        ),
        return_exceptions=True,
    )
    values: list[FairValueEstimate] = []
    for item, result in zip(case.line_items, results):
        if isinstance(result, BaseException):
            logger.warning(
                "%s: estimate failed for Line Item %s: %s",
                strategy_name,
                item.index,
                result,
            )
            continue
        values.append(result)
    if not values:
        return None
    return FairValueEstimates(values=tuple(values))


def _digest_or_raw(policy_text: str) -> str:
    try:
        return digest_policy_text(policy_text)
    except Exception:  # noqa: BLE001 - fall back, never block the round
        return policy_text
