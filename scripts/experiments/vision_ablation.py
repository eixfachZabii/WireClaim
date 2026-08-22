"""Is the model actually using the attached photographs, and how much are they worth?

`request_evidence` (`src/services/strategies/strategy2/model.py`) attaches every image in
`case.image_paths` via `build_input_content` before the prompt. Game 41 is the flagship
case for asking whether that photo earns its place: item 3 is a watch on a Valuables
Schedule, the photo shows a visible tourbillon complication plus a moon-phase subdial and
power reserve -- a five-figure object by sight alone -- and it settled at `t >= 11,131`
while the shipped pipeline priced it at 5,524.

This draws the SAME cached anchor prompt through the SAME models already running in
`retest_draw.py` (mini, terra), but with `case.image_paths` emptied before
`build_input_content`, so the only difference from the retest cache's `*_anchor.json`
files is whether the model ever saw the picture. Two regenerations of a *text-identical*
prompt already disagree by the ensemble's own measured between-draw spread, so the
comparison is framed as "photo vs no-photo", never "one draw vs one draw" -- the retest
cache's `unanchor` draw supplies a second-opinion sanity check on the same photo-on side.

Every response is cached to `var/experiments/vision_ablation/case_NN_<model>_nophoto.json`.
Concurrency capped at 2 and gated through `live_window.wait_for_safe_window`, exactly like
`retest_draw.py` -- this and that script are the only two things allowed to call the shared
endpoint tonight, so this one must never run while the other is still in flight (check with
`ps aux | grep retest_draw` first).

    PYTHONPATH=. pixi run python scripts/experiments/vision_ablation.py
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
from src.services.strategies.strategy2.prompts import PROMPT  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_window import wait_for_safe_window  # noqa: E402

CACHE = Path("var/experiments/vision_ablation")
CASES = Path("[PUBLIC] EHL Cases/cases")
MODELS = {"mini": "gpt-5.4-mini", "terra": "gpt-5.6-terra"}

#: Highest recovered Fair Value among the 37 photo Cases (`replay_payoffs.snapshot`, offline,
#: run once to rank them -- see the report for the full list). mini gets the whole priority
#: list; terra (markedly more accurate, per model-bakeoff.md) only the top two, where a
#: vision effect would matter most in euros.
MINI_GAMES = [41, 44, 40, 42, 20, 12, 24, 7, 18, 35, 25, 19]
TERRA_GAMES = [41, 44]


def _draw_path(game_id: int, model_tag: str) -> Path:
    return CACHE / f"case_{game_id:02d}_{model_tag}_nophoto.json"


def _sync_request(content: list, case, model_name: str, timeout: float):
    content = list(content)
    content[-1] = {"type": "input_text", "text": build_request_text(case, PROMPT)}
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
        return f"g{game_id:02d} {model_tag:5s} nophoto cached"

    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return f"g{game_id:02d} {model_tag:5s} nophoto SKIPPED (not extracted)"

    case = await read_case(game_id, case_dir)
    sliced = CaseData(
        game_id=case.game_id,
        case_dir=case.case_dir,
        policy_text=slice_policy(case.policy_text),
        description_text=case.description_text,
        line_items=case.line_items,
        image_paths=[],  # the ablation: everything else identical, no photo attached
    )
    content = build_input_content(sliced)

    async with semaphore:
        await wait_for_safe_window(f"g{game_id:02d} {model_tag} nophoto")
        raw_text, latency, error = await asyncio.to_thread(
            _sync_request, content, case, MODELS[model_tag], LLM_TIMEOUT_SECONDS
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
        "prompt_tag": "anchor",
        "has_photo": False,
        "timeout_budget_s": LLM_TIMEOUT_SECONDS,
        "latency_s": latency,
        "error": error,
        "parse_error": parse_error,
        "source": "vision-ablation",
        "raw_text": raw_text[:20000],
        "items": items,
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, indent=2))
    status = "OK" if error is None and parse_error is None else f"FAIL({error or parse_error})"
    return f"g{game_id:02d} {model_tag:5s} nophoto {status} {latency:6.2f}s items={len(items)}"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    jobs = [(g, "mini") for g in MINI_GAMES] + [(g, "terra") for g in TERRA_GAMES]
    print(f"{len(jobs)} no-photo draws queued, concurrency={args.concurrency}")

    semaphore = asyncio.Semaphore(args.concurrency)

    async def one(job):
        g, m = job
        try:
            return await draw_one(g, m, semaphore, args.refresh)
        except Exception as exc:  # noqa: BLE001
            return f"g{g:02d} {m:5s} nophoto EXCEPTION {type(exc).__name__}: {exc}"

    done = 0
    for coro in asyncio.as_completed([one(job) for job in jobs]):
        result = await coro
        done += 1
        print(f"[{done}/{len(jobs)}] {result}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
