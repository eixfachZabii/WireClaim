"""Channel C: ask the model to price the Line Items, and parse what comes back.

This is the channel that carries the Case. Channel A only speaks about items worth nothing
and Channel B reaches 22% of items, so roughly 78% of every invoice is priced here.

One call per framing for the **whole** Case, not per Line Item, so the model sees
neighbouring positions — that is what lets it notice a duplicate, an inflated quantity, or
a sub-limit that aggregates several lines. The Policy is sliced to its operative Parts
first (`src.services.policy.slice`), which halves the prompt and removes the blocking ~20 s LLM
digest that used to sit on the critical path.

The parser reads **only** `coverage_probability` and the three price fields. Two richer
schemas were tried and both lost money, badly: asking for a per-unit rate and multiplying
by the invoice quantity scored −64,590, and asking for an order-of-magnitude class that
could pull the band upward scored −127,312 across nineteen Cases. Neither is kept even as
dead code, because a model that volunteers such a field would silently re-enable a measured
loss. The negative results are recorded in
`docs/brainstorm/sebi/strats/review/strategy2-plan.md`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.api import get_llm_client, get_model_name, get_service_tier
from src.data.models import CaseData
from src.services.policy.slice import slice_policy
from src.domain.pricing.engine import Evidence
from src.services.strategies.strategy2.constants import LLM_TIMEOUT_SECONDS
from src.services.strategies.strategy2.prompts import PROMPT


def number(value: Any) -> float:
    """A non-negative finite float, or 0.0. Model output is never trusted arithmetically."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return 0.0
    return max(parsed, 0.0)


def extract_json(text: str) -> dict[str, Any]:
    """Pull the JSON object out of a response that may be wrapped in prose or fences."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise ValueError("Strategy 2 model response did not contain JSON.")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Strategy 2 model response must be a JSON object.")
    return payload


def parse_items(payload: dict[str, Any]) -> dict[int, Evidence]:
    """Turn the model's items into Evidence, keyed by the printed invoice POS number.

    A malformed entry is skipped rather than fatal: one bad Line Item must not cost the
    other thirty-eight.
    """
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Strategy 2 model response did not contain an items list.")
    found: dict[int, Evidence] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        index = int(number(item.get("line_item")))
        if index <= 0:
            continue
        low, median, high = sorted(
            number(item.get(key)) for key in ("price_low", "price_median", "price_high")
        )
        found[index] = Evidence(
            index=index,
            coverage_probability=min(number(item.get("coverage_probability")), 1.0),
            price_low=low,
            price_median=median,
            price_high=high,
        )
    return found


def build_request_text(case: CaseData, prompt: str) -> str:
    """The prompt plus the operative Policy, the damage description and the Line Items."""
    line_items = json.dumps([item.to_dict() for item in case.line_items], ensure_ascii=False)
    return (
        f"{prompt}\n\n=== POLICY (operative parts) ===\n{slice_policy(case.policy_text)}"
        f"\n\n=== DAMAGE DESCRIPTION ===\n{case.description_text}"
        f"\n\n=== LINE ITEMS ===\n{line_items}"
    )


def request_evidence(
    case: CaseData,
    timeout: float = LLM_TIMEOUT_SECONDS,
    prompt: str | None = None,
) -> dict[int, Evidence]:
    """One synchronous model call for the whole Case. Raises; the caller decides.

    Blocking on purpose — `propose` runs it in a thread so several framings go out at once.
    """
    # Imported here rather than at module scope: it is the one thing Strategy 2 still
    # borrows from Strategy 1, and a local import keeps the retirement of that module a
    # one-line change instead of a circular-import puzzle.
    from src.services.strategies.strategy1.strategy import build_input_content

    sliced = CaseData(
        game_id=case.game_id,
        case_dir=case.case_dir,
        policy_text=slice_policy(case.policy_text),
        description_text=case.description_text,
        line_items=case.line_items,
        image_paths=case.image_paths,
    )
    content = build_input_content(sliced)
    # `build_input_content` attaches the invoice PDF and any photographs, then puts its own
    # prompt last. Replace that final text block with ours, keeping the attachments.
    content[-1] = {"type": "input_text", "text": build_request_text(case, prompt or PROMPT)}

    response = get_llm_client().responses.create(
        model=get_model_name(),
        service_tier=get_service_tier(),
        timeout=timeout,
        input=[{"role": "user", "content": content}],
    )
    return parse_items(extract_json(str(response.output_text or "")))


__all__ = [
    "build_request_text",
    "extract_json",
    "number",
    "parse_items",
    "request_evidence",
]
