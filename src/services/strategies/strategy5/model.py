from __future__ import annotations

import base64
import json
import math
import mimetypes
import re
from dataclasses import dataclass
from statistics import fmean
from typing import Any, Iterable

from src.api import get_llm_client, get_service_tier
from src.data.models import CaseData
from src.domain.pricing.engine import Evidence
from src.services.policy.coverage import repair_quote
from src.services.strategies.strategy5.config import ZERO_LIMIT_VIOLATION_THRESHOLD
from src.services.strategies.strategy5.invoice import InvoiceItem
from src.services.strategies.strategy5.prompts import COVERAGE_SYSTEM_PROMPT, PRICE_SYSTEM_PROMPT

DEFAULT_POLICY_VIOLATION_PROBABILITY = 0.1

PRICE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "minimum": 1},
                    "lower": {"type": "number", "minimum": 0},
                    "upper": {"type": "number", "minimum": 0},
                    "price_basis": {"type": "string", "enum": ["gross_total"]},
                    "anchors": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["index", "lower", "upper", "price_basis", "anchors"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

COVERAGE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "minimum": 1},
                    "policy_violation_probability": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "clause": {"type": "string"},
                    "reasoning": {"type": "string"},
                },
                "required": [
                    "index",
                    "policy_violation_probability",
                    "clause",
                    "reasoning",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class PriceRange:
    index: int
    lower: float
    upper: float
    anchors: tuple[str, ...] = ()


@dataclass(frozen=True)
class AggregatedPriceRange:
    index: int
    average_lower: float
    average_upper: float
    evidence_lower: float
    evidence_median: float
    evidence_upper: float
    model_count: int
    anchors: tuple[str, ...] = ()

    def evidence(self, coverage_probability: float) -> Evidence:
        return Evidence(
            index=self.index,
            coverage_probability=coverage_probability,
            price_low=self.evidence_lower,
            price_median=self.evidence_median,
            price_high=self.evidence_upper,
        )


@dataclass(frozen=True)
class CoverageAssessment:
    index: int
    policy_violation_probability: float
    clause: str = ""
    reasoning: str = ""
    quote_verified: bool = False

    @property
    def coverage_probability(self) -> float:
        return 1.0 - self.policy_violation_probability


def number(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(parsed, 0.0) if math.isfinite(parsed) else 0.0


def probability(value: Any, default: float = DEFAULT_POLICY_VIOLATION_PROBABILITY) -> float:
    if value is None:
        return default
    return min(number(value), 1.0)


def extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise ValueError("Strategy 5 model response did not contain JSON")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Strategy 5 model response must be a JSON object")
    return payload


def parse_price_ranges(
    payload: dict[str, Any],
    items: Iterable[InvoiceItem],
) -> dict[int, PriceRange]:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("Strategy 5 price response did not contain an items list")
    allowed = {item.index for item in items}
    found: dict[int, PriceRange] = {}
    for raw in raw_items:
        if (
            not isinstance(raw, dict)
            or "lower" not in raw
            or "upper" not in raw
            or raw.get("price_basis") != "gross_total"
        ):
            continue
        index = int(number(raw.get("index")))
        if index not in allowed:
            continue
        lower, upper = sorted((number(raw.get("lower")), number(raw.get("upper"))))
        if upper <= 0:
            continue
        raw_anchors = raw.get("anchors")
        anchors = (
            tuple(str(anchor).strip() for anchor in raw_anchors if str(anchor).strip())
            if isinstance(raw_anchors, list)
            else ()
        )
        found[index] = PriceRange(index, lower, upper, anchors)
    return found


def parse_coverage_assessments(
    payload: dict[str, Any],
    items: Iterable[InvoiceItem],
    policy_text: str,
) -> dict[int, CoverageAssessment]:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("Strategy 5 coverage response did not contain an items list")
    allowed = {item.index for item in items}
    found: dict[int, CoverageAssessment] = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        index = int(number(raw.get("index")))
        if index not in allowed:
            continue
        clause = str(raw.get("clause") or "").strip()
        repaired = repair_quote(clause, policy_text)
        verified = bool(repaired)
        violation = probability(raw.get("policy_violation_probability"))
        if violation >= ZERO_LIMIT_VIOLATION_THRESHOLD and not verified:
            violation = DEFAULT_POLICY_VIOLATION_PROBABILITY
        found[index] = CoverageAssessment(
            index=index,
            policy_violation_probability=violation,
            clause=repaired or clause,
            reasoning=str(raw.get("reasoning") or "").strip(),
            quote_verified=verified,
        )
    return found


def _midpoint(price_range: PriceRange) -> float:
    if price_range.lower > 0:
        return math.sqrt(price_range.lower * price_range.upper)
    return price_range.upper * 0.5


def aggregate_price_ranges(
    draws: Iterable[dict[int, PriceRange]],
    items: Iterable[InvoiceItem],
) -> dict[int, AggregatedPriceRange]:
    usable = [draw for draw in draws if draw]
    aggregated: dict[int, AggregatedPriceRange] = {}
    for item in items:
        seen = [draw[item.index] for draw in usable if item.index in draw]
        if not seen:
            continue
        average_lower = fmean(value.lower for value in seen)
        average_upper = fmean(value.upper for value in seen)
        midpoints = [_midpoint(value) for value in seen]
        evidence_lower = min([average_lower, *midpoints])
        evidence_upper = max([average_upper, *midpoints])
        evidence_median = math.exp(fmean(math.log(value) for value in midpoints if value > 0))
        anchors = tuple(
            dict.fromkeys(anchor for value in seen for anchor in value.anchors if anchor)
        )
        aggregated[item.index] = AggregatedPriceRange(
            index=item.index,
            average_lower=average_lower,
            average_upper=average_upper,
            evidence_lower=evidence_lower,
            evidence_median=evidence_median,
            evidence_upper=evidence_upper,
            model_count=len(seen),
            anchors=anchors,
        )
    return aggregated


def _data_url(path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _image_content(case: CaseData) -> list[dict[str, Any]]:
    return [
        {"type": "input_image", "image_url": _data_url(path)}
        for path in case.image_paths
        if path.is_file()
    ]


def _item_json(items: tuple[InvoiceItem, ...]) -> str:
    return json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=1)


def build_price_input_content(
    case: CaseData,
    items: tuple[InvoiceItem, ...],
) -> list[dict[str, Any]]:
    content = _image_content(case)
    content.append(
        {
            "type": "input_text",
            "text": (
                f"=== DAMAGE DESCRIPTION ===\n{case.description_text}\n\n"
                f"=== DETERMINISTIC INVOICE ITEMS ===\n{_item_json(items)}\n\n"
                "Return exactly one result for every supplied index."
            ),
        }
    )
    return content


def build_coverage_input_content(
    case: CaseData,
    items: tuple[InvoiceItem, ...],
    invoice_text: str,
) -> list[dict[str, Any]]:
    content = _image_content(case)
    content.append(
        {
            "type": "input_text",
            "text": (
                f"=== POLICY ===\n{case.policy_text}\n\n"
                f"=== DAMAGE DESCRIPTION ===\n{case.description_text}\n\n"
                f"=== INVOICE TEXT ===\n{invoice_text}\n\n"
                f"=== DETERMINISTIC INVOICE ITEMS ===\n{_item_json(items)}\n\n"
                "Return exactly one result for every supplied index."
            ),
        }
    )
    return content


def _response_format(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "name": name,
            "strict": True,
            "schema": schema,
        }
    }


def request_price_ranges(
    case: CaseData,
    items: tuple[InvoiceItem, ...],
    model: str,
    timeout: float,
) -> dict[int, PriceRange]:
    response = get_llm_client().responses.create(
        model=model,
        service_tier=get_service_tier(),
        timeout=timeout,
        instructions=PRICE_SYSTEM_PROMPT,
        input=[{"role": "user", "content": build_price_input_content(case, items)}],
        text=_response_format("wireclaim_price_ranges", PRICE_RESPONSE_SCHEMA),
    )
    return parse_price_ranges(extract_json(str(response.output_text or "")), items)


def request_coverage_assessments(
    case: CaseData,
    items: tuple[InvoiceItem, ...],
    invoice_text: str,
    model: str,
    timeout: float,
) -> dict[int, CoverageAssessment]:
    response = get_llm_client().responses.create(
        model=model,
        service_tier=get_service_tier(),
        timeout=timeout,
        instructions=COVERAGE_SYSTEM_PROMPT,
        input=[
            {
                "role": "user",
                "content": build_coverage_input_content(case, items, invoice_text),
            }
        ],
        text=_response_format("wireclaim_coverage_assessments", COVERAGE_RESPONSE_SCHEMA),
    )
    return parse_coverage_assessments(
        extract_json(str(response.output_text or "")),
        items,
        case.policy_text,
    )


__all__ = [
    "AggregatedPriceRange",
    "CoverageAssessment",
    "PriceRange",
    "aggregate_price_ranges",
    "build_coverage_input_content",
    "build_price_input_content",
    "parse_coverage_assessments",
    "parse_price_ranges",
    "request_coverage_assessments",
    "request_price_ranges",
]
