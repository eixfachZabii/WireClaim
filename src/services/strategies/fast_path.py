from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any

from src.api import get_llm_client, get_model_name
from src.data.models import CaseData, ItemPrice, Proposal
from src.timing import log_timing, start_timer

logger = logging.getLogger(__name__)
STANDARD_CHARGE = 100.0
STANDARD_LIMIT = 75.0
FALLBACK_ESTIMATE = 150.0
CHARGE_FACTOR = 0.7
LIMIT_QUANTILE = 1 / 3
DEFAULT_COVERAGE_PROBABILITY = 0.9
LLM_TIMEOUT_SECONDS = 20.0
GAME_DESCRIPTION_PATH = Path(__file__).resolve().parents[3] / "docs" / "GAME_DESCRIPTION.md"

PROMPT = """Read the game rules and this complete insurance Case. Return structured pricing evidence for every invoice Line Item.

Do not return Charge, Limit, or Fair Value values. Deterministic code will derive the submitted numbers. For every Line Item return:
- line_item: one-based invoice index
- coverage_probability: probability from 0 to 1
- relatedness_probability: probability from 0 to 1
- quantity: plausible quantity for the whole Line Item
- price_low and price_high: realistic gross-total price band for the whole Line Item
- anchors: named price anchors

Use the game rule that all values are gross totals for whole Line Items. Read all attached documents and images. Return JSON only:
{"items":[{"line_item":1,"coverage_probability":0.9,"relatedness_probability":0.9,"quantity":1,"price_low":0.0,"price_high":0.0,"anchors":[""]}]}"""


def standard_values(case: CaseData) -> Proposal:
    return Proposal(
        source="standard",
        prices=tuple(
            ItemPrice(
                index=line_item.index,
                charge_price=STANDARD_CHARGE * max(line_item.quantity, 1.0),
                acceptance_limit=STANDARD_LIMIT * max(line_item.quantity, 1.0),
                source="standard",
            )
            for line_item in case.line_items
        ),
    )


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number or number in (float("inf"), float("-inf")):
        return 0.0
    return max(number, 0.0)


def _probability(value: Any) -> float:
    return min(_number(value), 1.0)


def _extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise ValueError("Fast path model response did not contain JSON.")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Fast path model response must be a JSON object.")
    return payload


def _data_url(path: Path, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _text_documents(case: CaseData) -> str:
    documents = [
        ("GAME_DESCRIPTION.md", GAME_DESCRIPTION_PATH.read_text(encoding="utf-8")),
        ("policy.txt", case.policy_text),
        ("description.txt", case.description_text),
    ]
    known_names = {name for name, _ in documents}
    for path in sorted(case.case_dir.glob("*.txt")):
        if path.name not in known_names:
            documents.append((path.name, path.read_text(encoding="utf-8", errors="replace")))
    return "\n\n".join(f"=== {name} ===\n{text}" for name, text in documents)


def build_input_content(case: CaseData) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    invoice_path = case.case_dir / "invoices.pdf"
    if invoice_path.exists():
        content.append(
            {
                "type": "input_file",
                "filename": invoice_path.name,
                "file_data": _data_url(invoice_path, "application/pdf"),
            }
        )
    for image_path in case.image_paths:
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
        content.append({"type": "input_image", "image_url": _data_url(image_path, mime_type)})
    content.append({"type": "input_text", "text": f"{PROMPT}\n\n{_text_documents(case)}"})
    return content


def _proposal_from_evidence(case: CaseData, payload: dict[str, Any]) -> Proposal | None:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("Fast path model response did not contain an items list.")
    known_items = {line_item.index: line_item for line_item in case.line_items}
    prices: list[ItemPrice] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        index = int(_number(raw_item.get("line_item")))
        line_item = known_items.get(index)
        if line_item is None:
            continue
        quantity = max(_number(raw_item.get("quantity")), line_item.quantity, 1.0)
        fallback = FALLBACK_ESTIMATE * quantity
        low, high = sorted((_number(raw_item.get("price_low")), _number(raw_item.get("price_high"))))
        if high <= 0:
            low, high = fallback * 0.75, fallback * 1.25
        median = (low + high) / 2
        charge = max(fallback, round(CHARGE_FACTOR * median, 2))
        covered_probability = max(_probability(raw_item.get("coverage_probability")), DEFAULT_COVERAGE_PROBABILITY)
        relatedness_probability = max(_probability(raw_item.get("relatedness_probability")), DEFAULT_COVERAGE_PROBABILITY)
        probability = covered_probability * relatedness_probability
        zero_mass = 1 - probability
        if LIMIT_QUANTILE <= zero_mass:
            limit = low * LIMIT_QUANTILE
        else:
            conditional_quantile = (LIMIT_QUANTILE - zero_mass) / probability
            limit = low + conditional_quantile * (high - low)
        prices.append(
            ItemPrice(
                index=index,
                charge_price=charge,
                acceptance_limit=round(min(max(limit, 0.0), median), 2),
                source="fast_path_llm",
            )
        )
    return Proposal(source="fast_path_llm", prices=tuple(prices)) if prices else None


def _request_proposal(case: CaseData) -> Proposal | None:
    response = get_llm_client().responses.create(
        model=get_model_name(),
        timeout=LLM_TIMEOUT_SECONDS,
        input=[{"role": "user", "content": build_input_content(case)}],
    )
    return _proposal_from_evidence(case, _extract_json(str(response.output_text or "")))


async def llm_values(case: CaseData) -> Proposal | None:
    started_at = start_timer()
    try:
        return await asyncio.to_thread(_request_proposal, case)
    finally:
        log_timing(logger, "fast_path_llm", started_at, game=case.game_id)
