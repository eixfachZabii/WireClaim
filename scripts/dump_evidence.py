"""Cache Strategy 2's model evidence for every extracted Case.

The deterministic layers and the pricing multipliers can be re-tuned thousands of times,
but the model call behind the evidence is slow and costs quota. Dumping it once means
every later sweep is free and reproducible, and two people tuning different constants see
exactly the same inputs.

    pixi run python scripts/dump_evidence.py --games 1-19

Writes `var/evidence/case_NN.json`. Delete a file to re-ask the model for that Case.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from src.data.case_loader import read_case
from src.pricing.engine import Evidence
from src.strategies.strategy2.channels import local_evidence
from src.strategies.strategy2.model import request_evidence

logger = logging.getLogger(__name__)
CACHE = Path("var/evidence")
CASES = Path("[PUBLIC] EHL Cases/cases")


def _path(game_id: int, tag: str = "model") -> Path:
    return CACHE / f"case_{game_id:02d}_{tag}.json"


def _dump(evidence: dict[int, Evidence]) -> str:
    return json.dumps(
        {
            str(index): {
                "coverage_probability": item.coverage_probability,
                "price_low": item.price_low,
                "price_median": item.price_median,
                "price_high": item.price_high,
            }
            for index, item in evidence.items()
        },
        indent=2,
    )


def load(game_id: int, tag: str = "model") -> dict[int, Evidence] | None:
    path = _path(game_id, tag)
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    return {
        int(index): Evidence(index=int(index), **values) for index, values in raw.items()
    }


async def dump_case(game_id: int, refresh: bool = False) -> str:
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return f"case {game_id:02d}: not extracted"
    case = await read_case(game_id, case_dir)
    lines = []
    if refresh or load(game_id) is None:
        evidence = await asyncio.to_thread(request_evidence, case)
        CACHE.mkdir(parents=True, exist_ok=True)
        _path(game_id).write_text(_dump(evidence))
        lines.append(f"model={len(evidence)}")
    else:
        lines.append("model=cached")
    memory = local_evidence(case)
    _path(game_id, "memory").write_text(_dump(memory))
    lines.append(f"memory={len(memory)} items={len(case.line_items)}")
    return f"case {game_id:02d}: " + " ".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-19")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))
    limit = asyncio.Semaphore(args.concurrency)

    async def one(game_id: int) -> str:
        async with limit:
            try:
                return await dump_case(game_id, args.refresh)
            except Exception as error:
                return f"case {game_id:02d}: FAILED {error}"

    for result in await asyncio.gather(*(one(game_id) for game_id in game_ids)):
        print(result)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
