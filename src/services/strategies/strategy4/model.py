from __future__ import annotations

import base64
import json
import math
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.api import get_llm_client, get_model_name, get_service_tier
from src.data.case_loader import read_invoice_line_items
from src.data.models import CaseData, LineItem
from src.domain.pricing.engine import Evidence
from src.services.strategies.strategy4.prompts import SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parents[4]
FAIR_VALUE_STUDY_PATH = ROOT / "case_analysis" / "data" / "fair_value_study.json"
GAME_DESCRIPTION_PATH = ROOT / "docs" / "GAME_DESCRIPTION.md"
LLM_TIMEOUT_SECONDS = 55.0
DEFAULT_COVERAGE_PROBABILITY = 0.9
FALLBACK_MEDIAN = 60.0


@dataclass(frozen=True)
class FairValueEvidence:
    index: int
    coverage_probability: float
    t_lower: float
    t_upper: float
    clause: str = ""
    anchors: tuple[str, ...] = ()

    def pricing_evidence(self) -> Evidence:
        if self.t_upper <= 0:
            return Evidence(
                index=self.index,
                coverage_probability=0.0,
                price_low=FALLBACK_MEDIAN * 0.5,
                price_median=FALLBACK_MEDIAN,
                price_high=FALLBACK_MEDIAN * 2,
            )
        low = self.t_lower if self.t_lower > 0 else self.t_upper * 0.5
        high = max(self.t_upper, low)
        return Evidence(
            index=self.index,
            coverage_probability=self.coverage_probability,
            price_low=low,
            price_median=math.sqrt(low * high),
            price_high=high,
        )


def number(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(parsed):
        return 0.0
    return max(parsed, 0.0)


def probability(value: Any, default: float = DEFAULT_COVERAGE_PROBABILITY) -> float:
    if value is None:
        return default
    return min(number(value), 1.0)


def extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise ValueError("Strategy 4 model response did not contain JSON.")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Strategy 4 model response must be a JSON object.")
    return payload


def _normalise_items(items: Iterable[LineItem]) -> tuple[LineItem, ...]:
    indexed: dict[int, LineItem] = {}
    for item in items:
        if item.index > 0:
            indexed.setdefault(item.index, item)
    return tuple(indexed[index] for index in sorted(indexed))


def extract_invoice_items(case: CaseData) -> tuple[LineItem, ...]:
    invoice_path = case.case_dir / "invoices.pdf"
    if invoice_path.is_file():
        try:
            parsed = _normalise_items(read_invoice_line_items(invoice_path))
            if parsed:
                return parsed
        except Exception:
            pass
    return _normalise_items(case.line_items)


def parse_estimates(payload: dict[str, Any], items: Iterable[LineItem]) -> dict[int, FairValueEvidence]:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("Strategy 4 model response did not contain an items list.")
    allowed = {item.index for item in items}
    estimates: dict[int, FairValueEvidence] = {}
    for raw in raw_items:
        if not isinstance(raw, dict) or "t_lower" not in raw or "t_upper" not in raw:
            continue
        index = int(number(raw.get("line_item")))
        if index not in allowed:
            continue
        lower, upper = sorted((number(raw.get("t_lower")), number(raw.get("t_upper"))))
        anchors = raw.get("anchors")
        estimates[index] = FairValueEvidence(
            index=index,
            coverage_probability=probability(raw.get("coverage_probability")),
            t_lower=lower,
            t_upper=upper,
            clause=str(raw.get("clause") or ""),
            anchors=tuple(str(anchor) for anchor in anchors) if isinstance(anchors, list) else (),
        )
    return estimates


def _data_url(path: Path, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _text_documents(case: CaseData) -> str:
    documents = [
        ("GAME_DESCRIPTION.md", _read_text(GAME_DESCRIPTION_PATH)),
        ("policy.txt", case.policy_text),
        ("description.txt", case.description_text),
    ]
    known_names = {name for name, _ in documents}
    try:
        paths = sorted(case.case_dir.glob("*.txt"))
    except OSError:
        paths = []
    for path in paths:
        if path.name not in known_names:
            documents.append((path.name, _read_text(path)))
    return "\n\n".join(f"=== {name} ===\n{text}" for name, text in documents)


def build_input_content(case: CaseData, items: tuple[LineItem, ...]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    invoice_path = case.case_dir / "invoices.pdf"
    if invoice_path.is_file():
        content.append(
            {
                "type": "input_file",
                "filename": invoice_path.name,
                "file_data": _data_url(invoice_path, "application/pdf"),
            }
        )
    if FAIR_VALUE_STUDY_PATH.is_file():
        content.append(
            {
                "type": "input_file",
                "filename": FAIR_VALUE_STUDY_PATH.name,
                "file_data": _data_url(FAIR_VALUE_STUDY_PATH, "application/json"),
            }
        )
    for image_path in case.image_paths:
        if image_path.is_file():
            mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
            content.append({"type": "input_image", "image_url": _data_url(image_path, mime_type)})
    item_payload = json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=1)
    content.append(
        {
            "type": "input_text",
            "text": (
                f"{_text_documents(case)}\n\n=== DETERMINISTIC INVOICE EXTRACTION ===\n"
                f"line_item_count={len(items)}\n{item_payload}\n\n"
                "Return exactly one JSON entry for every listed Line Item index."
            ),
        }
    )
    return content


def request_estimates(
    case: CaseData,
    items: tuple[LineItem, ...],
    timeout: float = LLM_TIMEOUT_SECONDS,
) -> dict[int, FairValueEvidence]:
    response = get_llm_client().responses.create(
        model=get_model_name(),
        service_tier=get_service_tier(),
        timeout=timeout,
        instructions=SYSTEM_PROMPT,
        input=[{"role": "user", "content": build_input_content(case, items)}],
    )
    return parse_estimates(extract_json(str(response.output_text or "")), items)


__all__ = [
    "DEFAULT_COVERAGE_PROBABILITY",
    "FAIR_VALUE_STUDY_PATH",
    "FALLBACK_MEDIAN",
    "GAME_DESCRIPTION_PATH",
    "LLM_TIMEOUT_SECONDS",
    "FairValueEvidence",
    "build_input_content",
    "extract_invoice_items",
    "extract_json",
    "number",
    "parse_estimates",
    "probability",
    "request_estimates",
]
