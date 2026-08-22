"""Model bake-off, stage 1: draw the REAL Strategy 2 evidence prompts through three models.

Answers: does `gpt-5.6-terra` or `gpt-5.6-luna` read a Case better than the shipped
`gpt-5.4-mini`? This script only draws and caches raw evidence -- unchanged
`ENSEMBLE_PROMPTS` (`src/services/strategies/strategy2/prompts.py`), same
`build_input_content` / `build_request_text` plumbing as the live path
(`src/services/strategies/strategy2/model.py`), just an explicit `model=` instead of
`get_model_name()`. Nothing in `src/` is touched or imported differently than the live
path already does.

Every response is cached to `var/experiments/model_bakeoff/case_NN_<model>_<prompt>.json`
so a re-run costs nothing. The `mini` + `anchor` cell reuses the already-cached
`var/evidence/case_NN_model.json` (dumped earlier today by `scripts/dump_evidence.py`
under the live `.env`, i.e. genuinely gpt-5.4-mini's anchored draw) instead of re-billing
it -- that halves the mini-model cost of this experiment.

    PYTHONPATH=. pixi run python scripts/experiments/model_bakeoff_draw.py --games 1-32 --concurrency 2

Rate-limit discipline: a global `asyncio.Semaphore` caps concurrent LLM calls (default 2,
matching the live ensemble's own fan-out) across every model and every Game -- this and the
live tournament's own submissions are the only things allowed to call this endpoint.
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
from src.policy_slice import slice_policy  # noqa: E402
from src.services.strategies.strategy1.strategy import build_input_content  # noqa: E402
from src.services.strategies.strategy2.model import (  # noqa: E402
    build_request_text,
    extract_json,
    parse_items,
)
from src.services.strategies.strategy2.prompts import PROMPT, PROMPT_UNANCHORED  # noqa: E402

CACHE = Path("var/experiments/model_bakeoff")
LEGACY_MODEL_CACHE = Path("var/evidence")
CASES = Path("[PUBLIC] EHL Cases/cases")

MODELS = {"mini": "gpt-5.4-mini", "terra": "gpt-5.6-terra", "luna": "gpt-5.6-luna"}
PROMPTS = {"anchor": PROMPT, "unanchor": PROMPT_UNANCHORED}

#: Generous ceiling for *measurement* -- we want to see how long a real call actually takes
#: even past the live LLM_TIMEOUT_SECONDS=40.0, so the latency report can state what fraction
#: would have been cut off. The live path's own timeout is unaffected by this constant.
MEASURE_TIMEOUT = 75.0


def _draw_path(game_id: int, model_tag: str, prompt_tag: str) -> Path:
    return CACHE / f"case_{game_id:02d}_{model_tag}_{prompt_tag}.json"


def _sync_request(content: list, case, model_name: str, prompt_text: str, timeout: float):
    content = list(content)
    content[-1] = {"type": "input_text", "text": build_request_text(case, prompt_text)}
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
    except Exception as exc:  # noqa: BLE001 - we record and move on, never crash the sweep
        error = f"{type(exc).__name__}: {exc}"
    latency = time.monotonic() - t0
    return raw_text, latency, error


async def draw_one(
    game_id: int, model_tag: str, prompt_tag: str, semaphore: asyncio.Semaphore, refresh: bool
) -> str:
    path = _draw_path(game_id, model_tag, prompt_tag)
    if path.exists() and not refresh:
        return f"g{game_id:02d} {model_tag:5s} {prompt_tag:8s} cached"

    if model_tag == "mini" and prompt_tag == "anchor" and not refresh:
        legacy = LEGACY_MODEL_CACHE / f"case_{game_id:02d}_model.json"
        if legacy.exists():
            items = json.loads(legacy.read_text())
            blob = {
                "game_id": game_id,
                "model": MODELS[model_tag],
                "model_tag": model_tag,
                "prompt_tag": prompt_tag,
                "latency_s": None,
                "error": None,
                "parse_error": None,
                "source": "legacy-cache:var/evidence",
                "raw_text": "",
                "items": items,
            }
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(blob, indent=2))
            return f"g{game_id:02d} {model_tag:5s} {prompt_tag:8s} reused legacy cache"

    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return f"g{game_id:02d} {model_tag:5s} {prompt_tag:8s} SKIPPED (not extracted)"

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
        raw_text, latency, error = await asyncio.to_thread(
            _sync_request, content, case, MODELS[model_tag], PROMPTS[prompt_tag], MEASURE_TIMEOUT
        )

    items: dict = {}
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
        except Exception as exc:  # noqa: BLE001
            parse_error = f"{type(exc).__name__}: {exc}"

    blob = {
        "game_id": game_id,
        "model": MODELS[model_tag],
        "model_tag": model_tag,
        "prompt_tag": prompt_tag,
        "latency_s": latency,
        "error": error,
        "parse_error": parse_error,
        "source": "live",
        "raw_text": raw_text[:20000],
        "items": items,
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, indent=2))
    status = "OK" if error is None and parse_error is None else f"FAIL({error or parse_error})"
    return f"g{game_id:02d} {model_tag:5s} {prompt_tag:8s} {status} {latency:6.2f}s items={len(items)}"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-32")
    parser.add_argument("--models", default="mini,terra,luna")
    parser.add_argument("--prompts", default="anchor,unanchor")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))
    model_tags = args.models.split(",")
    prompt_tags = args.prompts.split(",")

    semaphore = asyncio.Semaphore(args.concurrency)
    jobs = [
        (g, m, p)
        for g in game_ids
        for m in model_tags
        for p in prompt_tags
    ]
    print(f"{len(jobs)} draws queued over {len(game_ids)} Games x {len(model_tags)} models x {len(prompt_tags)} prompts, concurrency={args.concurrency}")

    async def one(job):
        g, m, p = job
        try:
            return await draw_one(g, m, p, semaphore, args.refresh)
        except Exception as exc:  # noqa: BLE001
            return f"g{g:02d} {m:5s} {p:8s} EXCEPTION {type(exc).__name__}: {exc}"

    done = 0
    for coro in asyncio.as_completed([one(job) for job in jobs]):
        result = await coro
        done += 1
        print(f"[{done}/{len(jobs)}] {result}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
