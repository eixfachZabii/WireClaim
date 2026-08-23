from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.api import get_llm_client, get_model_name, get_service_tier
from src.data.models import CaseData, ItemPrice, Proposal
from src.evidence.policy.quotes import has_explicit_line_item_exclusion, is_policy_quote
from src.strategies.fast_path import STANDARD_LIMIT
from src.runtime.timing import log_timing, start_timer

logger = logging.getLogger(__name__)
STRATEGY_NAME = "strategy1"
FALLBACK_ESTIMATE = 150.0
CHARGE_FACTOR = 0.7
LIMIT_QUANTILE = 1 / 3
DEFAULT_COVERAGE_PROBABILITY = 0.9
LLM_TIMEOUT_SECONDS = 55.0
SUBMISSION_RESERVE_SECONDS = 3.0

PROMPT = """Read this insurance Case and return structured evidence for every invoice Line Item.

Do not return a Charge, a Limit, or a Fair Value. Deterministic code prices from your evidence.

Start with the Policy scope: determine whether the reported event is an insured peril, whether the affected property class and location are insured, and quote any clause that excludes them. Then test each Line Item itself. An insured event does not make every invoice charge covered. Compare every Line Item name against exact Policy exclusions, especially movable contents, vehicles or transport, theft outside the insured perils, and ancillary costs such as shipping, delivery, installation, service, maintenance and liability charges. For an exact exclusion, set coverage_probability or relatedness_probability below 0.5 and reproduce the full exclusion as exclusion_quote. Do not lower coverage or relatedness because the Damage Description merely seems suspicious. If no exact exclusion quote exists, keep coverage and relatedness high.

For every Line Item, return:
- line_item: the one-based invoice index
- coverage_probability: probability from 0 to 1 that the Policy economically covers this item
- coverage_clause: exact Policy quote supporting coverage when relevant
- exclusion_quote: exact Policy quote supporting a non-coverage or unrelated verdict; otherwise an empty string
- relatedness_probability: probability from 0 to 1 that the item relates to the Damage Description
- quantity: plausible quantity for the complete Line Item
- unit: unit of the plausible quantity
- trade: relevant trade or product category
- price_low and price_high: a realistic gross-total market-price band for the complete Line Item
- anchors: named evidence supporting the price band, such as labour rate, material, catalogue price, or replacement cost

Check inflated quantities and betterment. Price the plausible quantity and the pre-loss like-for-like standard, never an upgrade. Use all attached documents and images. Price bands must be gross totals for whole Line Items, never net or per-unit values. Return JSON only:
{"items":[{"line_item":1,"coverage_probability":0.9,"coverage_clause":"","exclusion_quote":"","relatedness_probability":0.9,"quantity":1,"unit":"","trade":"","price_low":0.0,"price_high":0.0,"anchors":[""]}]}"""


@dataclass(frozen=True)
class Evidence:
    index: int
    coverage_probability: float
    relatedness_probability: float
    price_low: float
    price_high: float
    coverage_clause: str = ""
    exclusion_quote: str = ""
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
    fallback: float
    confirmed_uncovered: bool
    fallback_used: bool


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


def _apply_explicit_cost_exclusions(
    case: CaseData,
    proposal: Proposal | None,
    source: str,
) -> Proposal | None:
    prices = proposal.by_index() if proposal is not None else {}
    for line_item in case.line_items:
        price = prices.get(line_item.index)
        if price is None:
            price = ItemPrice(
                index=line_item.index,
                charge_price=FALLBACK_ESTIMATE * max(line_item.quantity, 1.0),
                acceptance_limit=STANDARD_LIMIT,
                source=source,
            )
        if has_explicit_line_item_exclusion(line_item.name, case.policy_text):
            price = price.with_limit(0.0)
        prices[line_item.index] = price
    return Proposal(source=source, prices=tuple(sorted(prices.values(), key=lambda price: price.index))) if prices else None


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


def _request_evidence(
    case: CaseData,
    model: str | None = None,
    timeout: float = LLM_TIMEOUT_SECONDS,
) -> tuple[Evidence, ...]:
    client = get_llm_client()
    model = get_model_name(model)
    response = client.responses.create(
        model=model,
        service_tier=get_service_tier(),
        timeout=timeout,
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
        low, high = sorted((_number(item.get("price_low")), _number(item.get("price_high"))))
        anchors = item.get("anchors", ())
        evidence.append(
            Evidence(
                index=index,
                coverage_probability=_probability(item.get("coverage_probability")),
                relatedness_probability=_probability(item.get("relatedness_probability")),
                price_low=low,
                price_high=high,
                coverage_clause=str(item.get("coverage_clause", "")),
                exclusion_quote=str(item.get("exclusion_quote", "")),
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
        fallback = FALLBACK_ESTIMATE * max(item.quantity, 1.0)
        fallback_used = item.price_high <= 0
        low, high = (fallback * 0.75, fallback * 1.25) if fallback_used else (item.price_low, item.price_high)
        exclusion_proven = is_policy_quote(item.exclusion_quote, case.policy_text)
        confirmed_uncovered = exclusion_proven and (
            item.coverage_probability < 0.5 or item.relatedness_probability < 0.5
        )
        if confirmed_uncovered:
            covered_probability = 0.0
        else:
            # Default when the model said nothing; never *floor* what it did say. This
            # was `max(probability, 0.9)`, which silently overrode a verdict of "5%
            # likely covered" with 90% and meant covered_probability could not fall
            # below 0.81 -- so the Limit never collapsed and we paid full price on the
            # 40% of Line Items whose Fair Value is 0. Game 17 paid 70,736 that way.
            coverage = item.coverage_probability or DEFAULT_COVERAGE_PROBABILITY
            relatedness = item.relatedness_probability or DEFAULT_COVERAGE_PROBABILITY
            covered_probability = coverage * relatedness
        estimates.append(
            Estimate(
                index=item.index,
                covered_probability=covered_probability,
                low=low,
                high=high,
                fallback=fallback,
                confirmed_uncovered=confirmed_uncovered,
                fallback_used=fallback_used,
            )
        )
    return tuple(estimates)


def _limit_from_estimate(estimate: Estimate) -> float:
    if estimate.confirmed_uncovered:
        return 0.0
    zero_mass = 1 - estimate.covered_probability
    if LIMIT_QUANTILE <= zero_mass:
        limit = estimate.low * LIMIT_QUANTILE
    else:
        conditional_quantile = (LIMIT_QUANTILE - zero_mass) / estimate.covered_probability
        limit = estimate.low + conditional_quantile * (estimate.high - estimate.low)
    median = (estimate.low + estimate.high) / 2
    return min(max(limit, 0.0), median, STANDARD_LIMIT)


def proposal_from_estimates(estimates: tuple[Estimate, ...], source: str = STRATEGY_NAME) -> Proposal | None:
    prices: list[ItemPrice] = []
    for estimate in estimates:
        median = (estimate.low + estimate.high) / 2
        charge = max(estimate.fallback, round(CHARGE_FACTOR * median, 2))
        limit = round(_limit_from_estimate(estimate), 2)
        if estimate.fallback_used:
            logger.warning("Strategy 1 fallback estimate used for Line Item %s.", estimate.index)
        prices.append(
            ItemPrice(
                index=estimate.index,
                charge_price=charge,
                acceptance_limit=limit,
                source=source,
            )
        )
    if not prices:
        return None
    return Proposal(source=source, prices=tuple(prices))


async def propose_with_model(
    case: CaseData,
    model: str | None = None,
    source: str = STRATEGY_NAME,
    deadline: float | None = None,
) -> Proposal | None:
    started_at = start_timer()
    timeout = LLM_TIMEOUT_SECONDS
    if deadline is not None:
        timeout = max(deadline - asyncio.get_running_loop().time() - SUBMISSION_RESERVE_SECONDS, 0.0)
    if timeout <= 0:
        logger.warning("%s skipped for Game %s because no submission time remains.", source, case.game_id)
        log_timing(logger, source, started_at, "expired", game=case.game_id, model=get_model_name(model))
        return None
    try:
        evidence = await asyncio.to_thread(_request_evidence, case, model, timeout)
        estimates = estimate_fair_values(case, evidence)
        proposal = _apply_explicit_cost_exclusions(
            case,
            proposal_from_estimates(estimates, source),
            source,
        )
    except asyncio.CancelledError:
        log_timing(logger, source, started_at, "cancelled", game=case.game_id, model=get_model_name(model))
        raise
    except Exception:
        log_timing(logger, source, started_at, "failed", game=case.game_id, model=get_model_name(model))
        raise
    log_timing(logger, source, started_at, game=case.game_id, model=get_model_name(model))
    return proposal


async def propose(case: CaseData, deadline: float | None = None) -> Proposal | None:
    return await propose_with_model(case, deadline=deadline)
