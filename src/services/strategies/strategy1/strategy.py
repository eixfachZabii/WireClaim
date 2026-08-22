from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.api import get_llm_client
from src.data.models import CaseData, ItemPrice, Proposal

STRATEGY_NAME = "strategy1"
UNCOVERED_CHARGE = 150.0
CHARGE_FACTOR = 0.7
LIMIT_QUANTILE = 1 / 3

PROMPT = """Read this insurance Case and return structured evidence for every invoice Line Item.

Do not return a Charge, a Limit, or a Fair Value. The deterministic strategy engine prices from your evidence.

For every Line Item, return:
- line_item: the one-based invoice index
- coverage_probability: probability from 0 to 1 that the Policy economically covers this item
- coverage_clause: exact Policy clause supporting the coverage or exclusion assessment
- relatedness_probability: probability from 0 to 1 that the item relates to the Damage Description
- quantity: plausible quantity for the complete Line Item
- unit: unit of the plausible quantity
- trade: relevant trade or product category
- price_low and price_high: a realistic gross-total market-price band for the complete Line Item
- anchors: named evidence supporting the price band, such as labour rate, material, catalogue price, or replacement cost

Use all attached documents and images. Price bands must be gross totals for whole Line Items, never net or per-unit values. Return JSON only:
{"items":[{"line_item":1,"coverage_probability":0.0,"coverage_clause":"","relatedness_probability":0.0,"quantity":1,"unit":"","trade":"","price_low":0.0,"price_high":0.0,"anchors":[""]}]}"""


@dataclass(frozen=True)
class Evidence:
    index: int
    coverage_probability: float
    relatedness_probability: float
    price_low: float
    price_high: float
    coverage_clause: str = ""
    quantity: float = 1.0
    unit: str = ""
    trade: str = ""
    anchors: tuple[str, ...] = ()


@dataclass(frozen=True)
class Estimate:
    index: int
    covered_probability: float
    low: float
    high: float


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
        raise ValueError("Strategy 1 model response did not contain JSON.")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Strategy 1 model response must be a JSON object.")
    return payload


def _text_documents(case: CaseData) -> str:
    documents = [("policy.txt", case.policy_text), ("description.txt", case.description_text)]
    known_names = {name for name, _ in documents}
    for path in sorted(case.case_dir.glob("*.txt")):
        if path.name in known_names:
            continue
        documents.append((path.name, path.read_text(encoding="utf-8", errors="replace")))
    return "\n\n".join(f"=== {name} ===\n{text}" for name, text in documents)


def _data_url(path: Path, mime_type: str) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


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
        content.append(
            {
                "type": "input_image",
                "image_url": _data_url(image_path, mime_type),
            }
        )
    content.append(
        {
            "type": "input_text",
            "text": f"{PROMPT}\n\n{_text_documents(case)}",
        }
    )
    return content


def _request_evidence(case: CaseData) -> tuple[Evidence, ...]:
    client = get_llm_client()
    model = os.environ.get("AZURE_OPENAI_MODEL") or "gpt-4o"
    response = client.responses.create(
        model=model,
        input=[{"role": "user", "content": build_input_content(case)}],
    )
    payload = _extract_json(str(response.output_text or ""))
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("Strategy 1 model response did not contain an items list.")
    evidence: list[Evidence] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        index = int(_number(item.get("line_item")))
        if index <= 0:
            continue
        low = _number(item.get("price_low"))
        high = _number(item.get("price_high"))
        low, high = sorted((low, high))
        anchors = item.get("anchors", ())
        evidence.append(
            Evidence(
                index=index,
                coverage_probability=_probability(item.get("coverage_probability")),
                relatedness_probability=_probability(item.get("relatedness_probability")),
                price_low=low,
                price_high=high,
                coverage_clause=str(item.get("coverage_clause", "")),
                quantity=_number(item.get("quantity")) or 1.0,
                unit=str(item.get("unit", "")),
                trade=str(item.get("trade", "")),
                anchors=tuple(str(anchor) for anchor in anchors) if isinstance(anchors, list) else (),
            )
        )
    return tuple(evidence)


def estimate_fair_values(case: CaseData, evidence: tuple[Evidence, ...]) -> tuple[Estimate, ...]:
    valid_indices = {line_item.index for line_item in case.line_items}
    estimates: list[Estimate] = []
    for item in evidence:
        if item.index not in valid_indices:
            continue
        estimates.append(
            Estimate(
                index=item.index,
                covered_probability=item.coverage_probability * item.relatedness_probability,
                low=item.price_low,
                high=item.price_high,
            )
        )
    return tuple(estimates)


def proposal_from_estimates(estimates: tuple[Estimate, ...]) -> Proposal | None:
    prices: list[ItemPrice] = []
    for estimate in estimates:
        median = (estimate.low + estimate.high) / 2
        if estimate.covered_probability <= 0 or median <= 0:
            charge = UNCOVERED_CHARGE
            limit = 0.0
        else:
            charge = max(UNCOVERED_CHARGE, round(CHARGE_FACTOR * median, 2))
            zero_mass = 1 - estimate.covered_probability
            if LIMIT_QUANTILE <= zero_mass:
                limit = 0.0
            else:
                conditional_quantile = (LIMIT_QUANTILE - zero_mass) / estimate.covered_probability
                limit = round(estimate.low + conditional_quantile * (estimate.high - estimate.low), 2)
        prices.append(
            ItemPrice(
                index=estimate.index,
                charge_price=charge,
                acceptance_limit=max(limit, 0.0),
                source=STRATEGY_NAME,
            )
        )
    if not prices:
        return None
    return Proposal(source=STRATEGY_NAME, prices=tuple(prices))


async def propose(case: CaseData) -> Proposal | None:
    evidence = await asyncio.to_thread(_request_evidence, case)
    estimates = estimate_fair_values(case, evidence)
    return proposal_from_estimates(estimates)
