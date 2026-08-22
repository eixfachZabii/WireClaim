from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api import get_llm_client, warm_llm_resources

MODELS = ("gpt-5.6-terra", "luna")
PROMPT = "Reply with exactly: ok"


def test_chat(model: str, service_tier: str) -> None:
    started_at = perf_counter()
    get_llm_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT}],
        max_completion_tokens=8,
        service_tier=service_tier,
        timeout=20,
    )
    print(
        f"OK route=chat.completions model={model} "
        f"service_tier={service_tier} elapsed_s={perf_counter() - started_at:.3f}"
    )


def test_responses(model: str, service_tier: str) -> None:
    started_at = perf_counter()
    get_llm_client().responses.create(
        model=model,
        input=PROMPT,
        max_output_tokens=16,
        service_tier=service_tier,
        timeout=20,
    )
    print(
        f"OK route=responses model={model} "
        f"service_tier={service_tier} elapsed_s={perf_counter() - started_at:.3f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Test OpenAI service_tier with local .env credentials.")
    parser.add_argument("--tier", choices=("fast", "priority"), default="fast")
    parser.add_argument("--model", action="append", dest="models", choices=MODELS)
    parser.add_argument("--route", choices=("chat", "responses", "both"), default="both")
    args = parser.parse_args()

    warm_llm_resources()
    failed = False
    for model in args.models or MODELS:
        routes = ("chat", "responses") if args.route == "both" else (args.route,)
        for route in routes:
            try:
                (test_chat if route == "chat" else test_responses)(model, args.tier)
            except Exception as error:
                failed = True
                print(
                    f"FAIL route={route} model={model} service_tier={args.tier} "
                    f"error={type(error).__name__}: {error}"
                )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
