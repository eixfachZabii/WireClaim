"""Does telling the model about aggregate class sub-limits change its evidence?

Coordinator's lead (from Game 44): a Case can invoice 2+ Line Items that belong to ONE
policy class carrying an AGGREGATE sub-limit (S4.2.2 "Valuables": watches, jewellery,
precious metals/stones -- "applied per item and, where more than one such item is affected,
in the aggregate per insured event across all items"). Game 44 is the first Case that shows
the collision: watch t>=9,361 (positive), ring t<884 (zero), necklace t<663 (zero) -- one
member absorbs the pot, the model priced all three at an identical coverage_probability of
0.925 in the live Submission, i.e. it did not notice.

This adds ONE instruction paragraph to the EXISTING prompt -- no new JSON field, no new
schema. That is deliberate: `model.py`'s docstring records that adding a field the pricing
engine then *used* as a correction lost -64,590 (per-unit rate) and -127,312 (magnitude
class). An instruction that can only act through the coverage_probability / price_median the
model already returns cannot repeat that failure mode structurally, but it can still shift
the LEVEL on every Case that happens to mention two similar nouns, so this scores it on:

  1. The one Case that should change (44): does coverage/price spread across the three
     valuables items instead of landing identically on all three?
  2. The one Case that must NOT change for the wrong reason (41): a single valuables item,
     nothing to aggregate against -- must not get zeroed by a false trigger.
  3. A spread of ordinary Cases with no valuables at all, as a false-positive check.

    PYTHONPATH=. pixi run python scripts/experiments/sublimit_aggregate_prompt.py --games 44,41,3,10,16,1,2,5,8,12
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
from src.evidence.policy.slice import slice_policy  # noqa: E402
from src.legacy.strategy1.strategy import build_input_content  # noqa: E402
from src.strategies.strategy2.constants import LLM_TIMEOUT_SECONDS  # noqa: E402
from src.strategies.strategy2.model import (  # noqa: E402
    build_request_text,
    extract_json,
    parse_items,
)
from src.strategies.strategy2.prompts import PROMPT  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_window import wait_for_safe_window  # noqa: E402

CACHE = Path("var/experiments/aggregate_prompt")
CASES = Path("[PUBLIC] EHL Cases/cases")
MODELS = {"mini": "gpt-5.4-mini"}

# Inserted right before "Return JSON only" so it lands after the coverage rules the model
# has already read, as a late, high-salience instruction rather than buried mid-prompt.
AGGREGATE_ADDENDUM = """
Some Policies group several Line Items into ONE shared class of property with a combined
sub-limit for the whole insured event, rather than a separate limit per item -- valuables
(jewellery, watches, precious metals or stones) are the class most likely to do this, and
some Policies apply the same aggregate structure to means of payment (cash, cards) or other
named classes. Read the Policy for the exact clause before assuming this applies.
If TWO OR MORE Line Items on THIS invoice describe separate items of the SAME such class
(for example two or more of: a watch, a ring, a necklace, a bracelet, other jewellery),
and the Policy's clause for that class aggregates the sub-limit across items rather than
giving each item its own, then the class's limited pot cannot fully cover every member:
price the most valuable member of the class close to its own real value, and price the
other members of the same class low, reflecting that the shared limit is likely already
spent by the time the claim reaches them. Quote the aggregation clause, not just the
class clause, for every member you discount this way. Do NOT apply this to a Case with
only ONE item of a class, and do NOT apply it to unrelated items that merely sound similar
(a phone and a watch are not the same class).
"""

AGGR_PROMPT = PROMPT.replace("Return JSON only:", AGGREGATE_ADDENDUM + "\nReturn JSON only:")
if AGGR_PROMPT == PROMPT:  # pragma: no cover - guards a silent no-op
    raise SystemExit("insertion point 'Return JSON only:' not found in PROMPT")


def _path(game_id: int, model_tag: str) -> Path:
    return CACHE / f"case_{game_id:02d}_{model_tag}_aggr.json"


def _sync_request(content, case, model_name, prompt_text, timeout):
    content = list(content)
    content[-1] = {"type": "input_text", "text": build_request_text(case, prompt_text)}
    client = get_llm_client()
    t0 = time.monotonic()
    error = None
    raw_text = ""
    try:
        response = client.responses.create(
            model=model_name, service_tier=get_service_tier(), timeout=timeout,
            input=[{"role": "user", "content": content}],
        )
        raw_text = str(response.output_text or "")
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    return raw_text, time.monotonic() - t0, error


async def draw_one(game_id: int, model_tag: str, semaphore: asyncio.Semaphore, refresh: bool) -> str:
    path = _path(game_id, model_tag)
    if path.exists() and not refresh:
        return f"g{game_id:02d} {model_tag:5s} cached"
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return f"g{game_id:02d} {model_tag:5s} SKIPPED (not extracted)"
    case = await read_case(game_id, case_dir)
    sliced = CaseData(
        game_id=case.game_id, case_dir=case.case_dir,
        policy_text=slice_policy(case.policy_text), description_text=case.description_text,
        line_items=case.line_items, image_paths=case.image_paths,
    )
    content = build_input_content(sliced)
    async with semaphore:
        await wait_for_safe_window(f"g{game_id:02d} {model_tag} aggr")
        raw_text, latency, error = await asyncio.to_thread(
            _sync_request, content, case, MODELS[model_tag], AGGR_PROMPT, LLM_TIMEOUT_SECONDS
        )
    items, parse_error = {}, None
    if error is None:
        try:
            parsed = parse_items(extract_json(raw_text))
            items = {
                str(i): {
                    "coverage_probability": e.coverage_probability, "price_low": e.price_low,
                    "price_median": e.price_median, "price_high": e.price_high,
                }
                for i, e in parsed.items()
            }
        except Exception as exc:  # noqa: BLE001
            parse_error = f"{type(exc).__name__}: {exc}"
    blob = {
        "game_id": game_id, "model": MODELS[model_tag], "model_tag": model_tag,
        "prompt_tag": "aggr", "latency_s": latency, "error": error, "parse_error": parse_error,
        "raw_text": raw_text[:20000], "items": items,
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, indent=2))
    status = "OK" if error is None and parse_error is None else f"FAIL({error or parse_error})"
    return f"g{game_id:02d} {model_tag:5s} {status} {latency:6.2f}s items={len(items)}"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", required=True, help="comma list")
    parser.add_argument("--models", default="mini")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if args.show:
        print(AGGR_PROMPT)
        return
    game_ids = [int(x) for x in args.games.split(",")]
    model_tags = args.models.split(",")
    semaphore = asyncio.Semaphore(args.concurrency)
    jobs = [(g, m) for g in game_ids for m in model_tags]
    print(f"{len(jobs)} draws queued, concurrency={args.concurrency}")
    tasks = [asyncio.create_task(draw_one(g, m, semaphore, args.refresh)) for g, m in jobs]
    for coro in asyncio.as_completed(tasks):
        print(await coro, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
