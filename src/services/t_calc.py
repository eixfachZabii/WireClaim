from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
from pathlib import Path
from typing import Any

from PIL import Image

from src.api import get_llm_client, get_model_name
from src.data.models import CaseData, FairValueEstimate, FairValueEstimates, LineItem
from src.policy_digest import digest_policy_text
from src.timing import log_timing, start_timer

logger = logging.getLogger(__name__)
LLM_TIMEOUT_SECONDS = 25.0
MAX_IMAGE_EDGE = 1024
FLAG_VALUES = ("upgrade", "preventive", "pre_existing", "unproven", "unrelated", "duplicate", "fee_padding")

SYSTEM_PROMPT = """Read one invoice Line Item and return price evidence for a deterministic Fair Value engine.

Do not decide coverage, relatedness, Charge, Limit, or Fair Value. Estimate only the defensible gross unit price and a gross-total price band for the work or item itself. Use the Policy digest for like-for-like and upgrade rules. Use the Damage Description, all invoice Line Items, and attached images to identify duplicate work, inflated quantities, preventive work, pre-existing damage, or unsupported fees.

Return realistic German market-price evidence. `unit_price` is gross per unit; `quantity` is the plausible quantity; `total_low` and `total_high` are gross totals for the complete Line Item. Record concerns in `flags` and explain the price anchors in `reasoning`.

`quantity_missing: true` means the invoice printed no amount and no unit for this Line Item, only dashes. Every one of the 20 such Line Items in the settled Games turned out to be worth exactly 0, so price it near zero and flag it.

The printed quantity is a weak guide to value across different kinds of work: eight grub screws are not eight technician hours. Anchor on what the whole Line Item is worth."""

RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "price_evidence",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "unit_price": {"type": "number"},
            "quantity": {"type": "number"},
            "total_low": {"type": "number"},
            "total_high": {"type": "number"},
            "confidence": {"type": "number"},
            "flags": {"type": "array", "items": {"type": "string", "enum": list(FLAG_VALUES)}},
            "reasoning": {"type": "string"},
        },
        "required": ["unit_price", "quantity", "total_low", "total_high", "confidence", "flags", "reasoning"],
    },
}



def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number or number in (float("inf"), float("-inf")):
        return 0.0
    return max(number, 0.0)


def encode_case_images(image_paths: tuple[Path, ...]) -> list[str]:
    encoded: list[str] = []
    for path in image_paths:
        try:
            with Image.open(path) as image:
                image = image.convert("RGB")
                image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=80)
        except OSError:
            continue
        encoded.append(base64.b64encode(buffer.getvalue()).decode("ascii"))
    return encoded


def _sanitize(index: int, payload: dict[str, Any]) -> FairValueEstimate:
    quantity = _number(payload.get("quantity")) or 1.0
    total = _number(payload.get("unit_price")) * quantity
    lower, upper = sorted((_number(payload.get("total_low")), _number(payload.get("total_high"))))
    if upper == 0.0:
        lower = upper = total
    median = min(max(total, lower), upper)
    return FairValueEstimate(line_item_index=index, median=median, lower=lower, upper=upper)


def _estimate_item(
    line_item: LineItem,
    policy_digest: str,
    description_text: str,
    all_items: list[dict[str, Any]],
    encoded_images: list[str],
) -> FairValueEstimate:
    prompt = (
        f"=== POLICY DIGEST ===\n{policy_digest}\n\n"
        f"=== DAMAGE DESCRIPTION ===\n{description_text}\n\n"
        f"=== ALL LINE ITEMS ===\n{json.dumps(all_items, ensure_ascii=False)}\n\n"
        f"=== TARGET LINE ITEM ===\n{json.dumps(line_item.to_dict(), ensure_ascii=False)}"
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    content.extend(
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}}
        for image in encoded_images
    )
    response = get_llm_client().chat.completions.create(
        model=get_model_name(),
        timeout=LLM_TIMEOUT_SECONDS,
        response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    )
    return _sanitize(line_item.index, json.loads(response.choices[0].message.content or "{}"))


async def _timed_estimate_item(
    line_item: LineItem,
    case: CaseData,
    policy_digest: str,
    all_items: list[dict[str, Any]],
    encoded_images: list[str],
    strategy_name: str,
) -> FairValueEstimate:
    started_at = start_timer()
    try:
        result = await asyncio.to_thread(
            _estimate_item,
            line_item,
            policy_digest,
            case.description_text,
            all_items,
            encoded_images,
        )
    except Exception:
        log_timing(
            logger,
            "fair_value_item",
            started_at,
            "failed",
            game=case.game_id,
            strategy=strategy_name,
            line_item=line_item.index,
        )
        raise
    log_timing(
        logger,
        "fair_value_item",
        started_at,
        game=case.game_id,
        strategy=strategy_name,
        line_item=line_item.index,
    )
    return result


async def estimate_fair_values(case: CaseData, strategy_name: str) -> FairValueEstimates | None:
    started_at = start_timer()
    if not case.line_items:
        log_timing(logger, "fair_value", started_at, game=case.game_id, strategy=strategy_name, values=0)
        return None
    try:
        policy_digest = await asyncio.to_thread(digest_policy_text, case.policy_text)
    except Exception as error:
        logger.warning("%s: policy digest failed: %s", strategy_name, error)
        policy_digest = case.policy_text
    encoded_images = await asyncio.to_thread(encode_case_images, case.image_paths)
    all_items = [item.to_dict() for item in case.line_items]
    results = await asyncio.gather(
        *(
            _timed_estimate_item(
                line_item,
                case,
                policy_digest,
                all_items,
                encoded_images,
                strategy_name,
            )
            for line_item in case.line_items
        ),
        return_exceptions=True,
    )
    values: list[FairValueEstimate] = []
    for line_item, result in zip(case.line_items, results):
        if isinstance(result, BaseException):
            logger.warning("%s: Fair Value estimate failed for Line Item %s: %s", strategy_name, line_item.index, result)
            continue
        values.append(result)
    log_timing(logger, "fair_value", started_at, game=case.game_id, strategy=strategy_name, values=len(values))
    return FairValueEstimates(values=tuple(values)) if values else None
