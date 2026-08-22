"""Model bake-off RETEST, stage 1: draw the CURRENT Strategy 2 prompt through mini and terra.

Why a retest, and why a fresh cache directory instead of reusing
`var/experiments/model_bakeoff/`: that earlier sweep's cache was drawn between 21:48 and
22:20, entirely **before** two prompt fixes that shipped later the same night --
"Replace the guessed price anchors with the settled ones" (21:53:26) and "Tell the model the
truth about the price distribution" (23:38:39, `_DISTRIBUTION_HINT`'s quartiles: median
59->97, top decile "several thousand" -> named quartiles running to 11,131). Every cached
response in the old directory answered a *different* prompt than the one shipping now, so it
cannot answer whether today's prompt changes the mini-vs-terra verdict. This script re-draws
from scratch under the current `ENSEMBLE_PROMPTS` (imported live from
`src.strategies.strategy2.prompts`, not copied), through the same
`build_input_content` / `build_request_text` plumbing the live path uses -- images attached,
nothing in `src/` touched or imported differently.

Every response is cached to `var/experiments/model_bakeoff_retest/case_NN_<model>_<prompt>.json`
so a re-run costs nothing. `--games` accepts a comma list or a range; the default draws every
currently-extracted Case (1-42; Case 0 is the permanent test Case and is excluded) in a
priority order: Case 41 (the named vision/tourbillon probe) first, then every other Case
carrying an item with recovered Fair Value >= 1,000 (the "expensive tail" population this
report is scored on), then every remaining Case with a photograph, then everything else --
so an interim read (expensive tail + latency) is available long before the full sweep
finishes.

Concurrency is capped at 2 (`--concurrency`), matching the live ensemble's own fan-out and
this task's rate-limit instruction -- this and the live tournament's own submissions are the
only things allowed to hit this endpoint tonight. `scripts/experiments/live_window.py` gates
every call so none is *started* within 68s of a Game boundary or before 70s past one, which
guarantees no call (max 55s, matching the live `LLM_TIMEOUT_SECONDS`) is ever in flight during
the instructed T-10s..T+70s live window.

    PYTHONPATH=. pixi run python scripts/experiments/retest_draw.py --concurrency 2
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
from src.strategies.strategy2.prompts import PROMPT, PROMPT_UNANCHORED  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_window import wait_for_safe_window  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay_payoffs import snapshot  # noqa: E402

CACHE = Path("var/experiments/model_bakeoff_retest")
CASES = Path("[PUBLIC] EHL Cases/cases")
INF = float("inf")

MODELS = {"mini": "gpt-5.4-mini", "terra": "gpt-5.6-terra", "luna": "gpt-5.6-luna"}
PROMPTS = {"anchor": PROMPT, "unanchor": PROMPT_UNANCHORED}

#: Matches the live budget exactly, so latency measured here is directly comparable to the
#: 55s window the live path actually enforces (no "measure past the real budget" ceiling).
CALL_TIMEOUT = LLM_TIMEOUT_SECONDS


def _draw_path(game_id: int, model_tag: str, prompt_tag: str) -> Path:
    return CACHE / f"case_{game_id:02d}_{model_tag}_{prompt_tag}.json"


def priority_games(all_games: list[int]) -> list[int]:
    """Case 41 first, then the rest of the expensive tail, then photo Cases, then the rest."""
    expensive: list[int] = []
    for g in all_games:
        try:
            snap = snapshot(g)
        except Exception:
            continue
        for lo, hi in snap.fair_brackets.values():
            t = lo if hi == INF else (lo + hi) / 2.0
            if t >= 1000:
                expensive.append(g)
                break
    photo = [g for g in all_games if (CASES / f"case_{g:02d}" / "photo.jpg").exists()]

    ordered: list[int] = []
    for bucket in ([41], expensive, photo, all_games):
        for g in bucket:
            if g in all_games and g not in ordered:
                ordered.append(g)
    return ordered


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
    except Exception as exc:  # noqa: BLE001 - record and move on, never crash the sweep
        error = f"{type(exc).__name__}: {exc}"
    latency = time.monotonic() - t0
    return raw_text, latency, error


async def draw_one(
    game_id: int, model_tag: str, prompt_tag: str, semaphore: asyncio.Semaphore, refresh: bool
) -> str:
    path = _draw_path(game_id, model_tag, prompt_tag)
    if path.exists() and not refresh:
        return f"g{game_id:02d} {model_tag:5s} {prompt_tag:8s} cached"

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
        await wait_for_safe_window(f"g{game_id:02d} {model_tag} {prompt_tag}")
        raw_text, latency, error = await asyncio.to_thread(
            _sync_request, content, case, MODELS[model_tag], PROMPTS[prompt_tag], CALL_TIMEOUT
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
        "timeout_budget_s": CALL_TIMEOUT,
        "latency_s": latency,
        "error": error,
        "parse_error": parse_error,
        "source": "live-retest",
        "raw_text": raw_text[:20000],
        "items": items,
        "has_photo": bool(case.image_paths),
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, indent=2))
    status = "OK" if error is None and parse_error is None else f"FAIL({error or parse_error})"
    return f"g{game_id:02d} {model_tag:5s} {prompt_tag:8s} {status} {latency:6.2f}s items={len(items)}"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default=None, help="comma list or a-b range; default = every extracted Case 1-42, priority-ordered")
    parser.add_argument("--models", default="mini,terra")
    parser.add_argument("--prompts", default="anchor,unanchor")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    if args.games is None:
        all_games = sorted(
            int(d.name.split("_")[1])
            for d in CASES.glob("case_*")
            if (d / "policy.txt").exists() and int(d.name.split("_")[1]) >= 1
        )
        game_ids = priority_games(all_games)
    elif "-" in args.games and "," not in args.games:
        start, _, end = args.games.partition("-")
        game_ids = list(range(int(start), int(end or start) + 1))
    else:
        game_ids = [int(x) for x in args.games.split(",")]

    model_tags = args.models.split(",")
    prompt_tags = args.prompts.split(",")

    semaphore = asyncio.Semaphore(args.concurrency)
    # Preserve priority order: (game, model, prompt) triples in game-priority order first,
    # so the expensive-tail / photo Cases are drawn before the long tail of cheap Cases.
    jobs = [(g, m, p) for g in game_ids for m in model_tags for p in prompt_tags]
    print(
        f"{len(jobs)} draws queued over {len(game_ids)} Games x {len(model_tags)} models x "
        f"{len(prompt_tags)} prompts, concurrency={args.concurrency}, call timeout={CALL_TIMEOUT}s"
    )
    print(f"Game order (priority-first): {game_ids}")

    async def one(job):
        g, m, p = job
        try:
            return await draw_one(g, m, p, semaphore, args.refresh)
        except Exception as exc:  # noqa: BLE001
            return f"g{g:02d} {m:5s} {p:8s} EXCEPTION {type(exc).__name__}: {exc}"

    # Launch strictly in priority order (not asyncio.as_completed's arbitrary creation order)
    # so the semaphore is contended for by the expensive/photo Cases first even though many
    # results resolve out of order.
    tasks = [asyncio.create_task(one(job)) for job in jobs]
    done = 0
    for coro in asyncio.as_completed(tasks):
        result = await coro
        done += 1
        print(f"[{done}/{len(jobs)}] {result}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
