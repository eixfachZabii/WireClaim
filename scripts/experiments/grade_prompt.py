"""Prompt variant: name the item's quality tier and a market comparable before pricing it.

Game 41 item 3 is the motivating failure: a watch on a Valuables Schedule, the photo shows
a visible tourbillon, moon-phase subdial and power reserve -- a five-figure object by sight
alone -- and the shipped prompt (which asks directly for a price band, with no intermediate
judgement) priced it at 5,524 against a settled `t >= 11,131`.

Two structured fields that let the model MECHANICALLY inflate a number were already tried
and both lost money badly (`model.py`'s docstring: a per-unit rate field -64,590, an
order-of-magnitude class field -127,312, both across 19 Cases) -- because a model that
volunteers a number invites arithmetic our own code cannot check. This is different in kind:
`item_grade` and `comparable` are free-text fields the parser (`model.parse_items`) never
reads at all -- it only ever looks at `line_item`, `coverage_probability` and the three price
fields, exactly as today. The point is not the field, it is making the model SAY, in its own
context window before it commits to a number, whether what it is looking at (including the
photograph, if attached) is ordinary, premium or exceptional, and name one concrete
comparable. If that changes the number, it is because reasoning about it explicitly changed
the model's own judgement, not because a formula read the field back.

Draws through the same `build_input_content` / `build_request_text` plumbing the live path
uses, images attached exactly as `request_evidence` would attach them. Concurrency capped at
2, gated through `live_window.wait_for_safe_window` -- run this only after `retest_draw.py`
and `vision_ablation.py` have both exited (`ps aux | grep -E "retest_draw|vision_ablation"`),
since only one caller may hold the endpoint's 2-concurrency budget at a time.

Cached to `var/experiments/grade_prompt/case_NN_<model>_grade.json`.

    PYTHONPATH=. pixi run python scripts/experiments/grade_prompt.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.api import get_llm_client, get_service_tier  # noqa: E402
from src.data.case_loader import read_case  # noqa: E402
from src.data.models import CaseData  # noqa: E402
from src.services.policy.slice import slice_policy  # noqa: E402
from src.services.strategies.strategy1.strategy import build_input_content  # noqa: E402
from src.services.strategies.strategy2.constants import LLM_TIMEOUT_SECONDS  # noqa: E402
from src.services.strategies.strategy2.model import (  # noqa: E402
    build_request_text,
    extract_json,
    parse_items,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_window import wait_for_safe_window  # noqa: E402
from tail_prompts import ANCHORS, COMMON_HEAD, COVERAGE_RULES  # noqa: E402

CACHE = Path("var/experiments/grade_prompt")
CASES = Path("[PUBLIC] EHL Cases/cases")
MODELS = {"mini": "gpt-5.4-mini", "terra": "gpt-5.6-terra"}

#: Same curated set `vision_ablation.py` uses -- the photo Cases with the highest recovered
#: Fair Value, where a quality-tier misjudgement is most expensive. mini (shipped) gets the
#: full list; terra (markedly more accurate on the plain prompt) the top two, to see whether
#: an already-stronger reader gains anything further from being asked to grade first.
MINI_GAMES = [41, 44, 40, 42, 20, 12, 24, 7, 18, 35, 25, 19]
TERRA_GAMES = [41, 44]

GRADE_PROMPT = f"""{COMMON_HEAD}
For each Line Item return:
- line_item: the POS number printed on the invoice. Use it exactly. Numbering may skip a number and may continue across several invoices in the same document.
- coverage_probability: the probability from 0 to 1 that this Policy indemnifies this position at all. This is the most valuable number you produce. Roughly 40% of positions are worth nothing.
- item_grade: your own judgement, BEFORE you price it, of the quality/rarity tier of the specific item or service this Line Item describes -- one of "ordinary", "premium", or "exceptional". If a photograph is attached, look at it closely: brand marks, materials, visible mechanical complications or craftsmanship (a mechanical watch with a visible tourbillon, a moon-phase subdial, or a perpetual calendar is "exceptional"; a plain quartz watch is "ordinary"), condition, and anything the description or an attached valuation/certificate says about it. An "exceptional" item can legitimately be a five- or six-figure object -- do not let a business-as-usual expectation cap what you write down.
- comparable: one short, concrete, named real-world comparable that anchors your price -- a specific product tier, market segment, or category benchmark (e.g. "entry-level Swiss automatic watch", "haute horlogerie grand complication", "mid-range condensation dryer rental", "budget flat-pack kitchen unit"). Not a brand guess, a market-segment anchor.
- price_low, price_median, price_high: a realistic GROSS TOTAL band in EUR for the WHOLE Line Item at German market prices, consistent with the grade and comparable you just named. Never a net amount, never a per-unit price. Make the band honest: wide when you are unsure, narrow when you are confident.
- clause: the Policy sentence that decides coverage, quoted verbatim.
{ANCHORS}{COVERAGE_RULES}
Return JSON only:
{{"items":[{{"line_item":1,"coverage_probability":0.9,"item_grade":"ordinary","comparable":"","price_low":0.0,"price_median":0.0,"price_high":0.0,"clause":""}}]}}"""


def _draw_path(game_id: int, model_tag: str) -> Path:
    return CACHE / f"case_{game_id:02d}_{model_tag}_grade.json"


def _sync_request(content: list, case, model_name: str, timeout: float):
    content = list(content)
    content[-1] = {"type": "input_text", "text": build_request_text(case, GRADE_PROMPT)}
    client = get_llm_client()
    t0 = time.monotonic()
    error = None
    raw_text = ""
    try:
        response = client.responses.create(
            model=model_name,
            service_tier=get_service_tier(),
            timeout=timeout,
            input=[{"role": "user", "content": content}],
        )
        raw_text = str(response.output_text or "")
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    latency = time.monotonic() - t0
    return raw_text, latency, error


async def draw_one(game_id: int, model_tag: str, semaphore: asyncio.Semaphore, refresh: bool) -> str:
    path = _draw_path(game_id, model_tag)
    if path.exists() and not refresh:
        return f"g{game_id:02d} {model_tag:5s} grade cached"

    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return f"g{game_id:02d} {model_tag:5s} grade SKIPPED (not extracted)"

    case = await read_case(game_id, case_dir)
    sliced = CaseData(
        game_id=case.game_id,
        case_dir=case.case_dir,
        policy_text=slice_policy(case.policy_text),
        description_text=case.description_text,
        line_items=case.line_items,
        image_paths=case.image_paths,
    )
    content = build_input_content(sliced)

    async with semaphore:
        await wait_for_safe_window(f"g{game_id:02d} {model_tag} grade")
        raw_text, latency, error = await asyncio.to_thread(
            _sync_request, content, case, MODELS[model_tag], LLM_TIMEOUT_SECONDS
        )

    items: dict = {}
    grades: dict = {}
    parse_error = None
    if error is None:
        try:
            payload = extract_json(raw_text)
            parsed = parse_items(payload)
            items = {
                str(i): {
                    "coverage_probability": e.coverage_probability,
                    "price_low": e.price_low,
                    "price_median": e.price_median,
                    "price_high": e.price_high,
                }
                for i, e in parsed.items()
            }
            for raw_item in payload.get("items", []):
                if isinstance(raw_item, dict) and "line_item" in raw_item:
                    grades[str(int(raw_item["line_item"]))] = {
                        "item_grade": raw_item.get("item_grade", ""),
                        "comparable": raw_item.get("comparable", ""),
                    }
        except Exception as exc:  # noqa: BLE001
            parse_error = f"{type(exc).__name__}: {exc}"

    blob = {
        "game_id": game_id,
        "model": MODELS[model_tag],
        "model_tag": model_tag,
        "prompt_tag": "grade",
        "has_photo": bool(case.image_paths),
        "timeout_budget_s": LLM_TIMEOUT_SECONDS,
        "latency_s": latency,
        "error": error,
        "parse_error": parse_error,
        "source": "grade-prompt",
        "raw_text": raw_text[:20000],
        "items": items,
        "grades": grades,
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, indent=2))
    status = "OK" if error is None and parse_error is None else f"FAIL({error or parse_error})"
    return f"g{game_id:02d} {model_tag:5s} grade {status} {latency:6.2f}s items={len(items)}"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    jobs = [(g, "mini") for g in MINI_GAMES] + [(g, "terra") for g in TERRA_GAMES]
    print(f"{len(jobs)} grade-prompt draws queued, concurrency={args.concurrency}")

    semaphore = asyncio.Semaphore(args.concurrency)

    async def one(job):
        g, m = job
        try:
            return await draw_one(g, m, semaphore, args.refresh)
        except Exception as exc:  # noqa: BLE001
            return f"g{g:02d} {m:5s} grade EXCEPTION {type(exc).__name__}: {exc}"

    done = 0
    for coro in asyncio.as_completed([one(job) for job in jobs]):
        result = await coro
        done += 1
        print(f"[{done}/{len(jobs)}] {result}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
