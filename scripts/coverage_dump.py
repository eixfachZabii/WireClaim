"""Cache `src.services.coverage.assess_coverage` for every extracted Case.

Same reason as `scripts/dump_evidence.py`: the grading and the euro replay below get run
dozens of times while a threshold is argued about, and the model call behind the verdict is
slow and costs quota. Dumping it once makes every later sweep free, reproducible, and
identical for two people looking at the same table.

    set -a && . .env && set +a
    PYTHONPATH=. python scripts/coverage_dump.py --games 1-30
    PYTHONPATH=. python scripts/coverage_dump.py --games 8 --refresh --time

Writes `var/coverage/case_NN.json`, one file per Game:

    {"game_id": 8, "items": 39, "seconds": 12.3, "chunk_failures": 0,
     "verdicts": {"1": {"p_covered": .., "clause": .., "quote_verified": .., "reasoning": ..}}}

`seconds` is wall clock for the whole pass -- the number that decides whether this can run
inside the 60-second window at all -- and it is recorded per Game rather than reported once,
because Case 8 (39 Line Items, five chunks x two samples) is the only Case that matters for
that question and it must be auditable after the fact.

`chunk_failures` is the reason this file is not just `dump_evidence.py` with a different
call. `assess_coverage` is built so a failed chunk **degrades silently** to
`DEFAULT_P_COVERED` -- that is the invariant that keeps a broken model from costing a
Submission, and it is exactly wrong for a measurement, because a rate-limited run produces a
file full of 0.9 that grades like a flat prior and is indistinguishable from a real verdict.
Worse, a half-failed Case is *invisible*: one sample defaults to 0.9, the other says 0.05,
and `merge_samples` reports 0.475 with the surviving sample's reasoning attached. So the
dump counts the module's own `Coverage chunk failed` warnings, retries the Case while any
chunk failed, and **refuses to write a degraded file** rather than caching a fiction.
Sixteen concurrent chunks against one deployment reliably trips a 429, so `--concurrency`
defaults low.

Delete a file to re-ask the model for that Case; `--refresh` does it for the whole range.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.case_loader import read_case  # noqa: E402
from src.services.policy.coverage import CoverageVerdict, assess_coverage  # noqa: E402

CACHE = Path("var/coverage")
CASES = Path("[PUBLIC] EHL Cases/cases")

logger = logging.getLogger(__name__)


def _path(game_id: int) -> Path:
    return CACHE / f"case_{game_id:02d}.json"


def load(game_id: int) -> dict[int, CoverageVerdict] | None:
    """`{index: CoverageVerdict}` for one Game, or None when it has not been dumped."""
    path = _path(game_id)
    if not path.exists():
        return None
    blob = json.loads(path.read_text())
    return {
        int(index): CoverageVerdict(
            index=int(index),
            p_covered=float(values["p_covered"]),
            clause=values.get("clause") or "",
            quote_verified=bool(values.get("quote_verified")),
            reasoning=values.get("reasoning") or "",
        )
        for index, values in blob["verdicts"].items()
    }


def probabilities(game_id: int) -> dict[int, float] | None:
    verdicts = load(game_id)
    return None if verdicts is None else {i: v.p_covered for i, v in verdicts.items()}


def seconds(game_id: int) -> float | None:
    path = _path(game_id)
    if not path.exists():
        return None
    return json.loads(path.read_text()).get("seconds")


class _ChunkFailureCounter(logging.Handler):
    """Counts `assess_coverage`'s own degradation warnings for one pass."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.failures = 0

    def emit(self, record: logging.LogRecord) -> None:
        if "Coverage chunk" in str(record.msg):
            self.failures += 1


async def _one_pass(case) -> tuple[tuple, float, int]:
    counter = _ChunkFailureCounter()
    module_logger = logging.getLogger("src.services.coverage")
    module_logger.addHandler(counter)
    try:
        started = time.monotonic()
        verdicts = await assess_coverage(case)
        elapsed = time.monotonic() - started
    finally:
        module_logger.removeHandler(counter)
    return verdicts, elapsed, counter.failures


#: How many times a Case is re-asked while any chunk is still failing. A 429 clears in
#: seconds; anything that survives four attempts is not a rate limit and the Case is left
#: undumped rather than written degraded.
ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 15.0


async def dump_case(game_id: int, refresh: bool = False) -> str:
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return f"case {game_id:02d}: not extracted"
    if not refresh and load(game_id) is not None:
        return f"case {game_id:02d}: cached ({seconds(game_id):.1f}s)"
    case = await read_case(game_id, case_dir)

    for attempt in range(1, ATTEMPTS + 1):
        verdicts, elapsed, failures = await _one_pass(case)
        if not failures:
            break
        if attempt == ATTEMPTS:
            return (
                f"case {game_id:02d}: DEGRADED after {ATTEMPTS} attempts "
                f"({failures} chunk failures) -- not written"
            )
        await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)

    CACHE.mkdir(parents=True, exist_ok=True)
    _path(game_id).write_text(
        json.dumps(
            {
                "game_id": game_id,
                "items": len(case.line_items),
                "seconds": round(elapsed, 2),
                "chunk_failures": 0,
                "verdicts": {
                    str(verdict.index): verdict.to_dict() for verdict in verdicts
                },
            },
            indent=1,
        )
    )
    collapsed = sum(1 for verdict in verdicts if verdict.collapses_limit)
    return (
        f"case {game_id:02d}: items={len(verdicts)} collapsed={collapsed} "
        f"{elapsed:.1f}s"
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-30")
    parser.add_argument("--refresh", action="store_true")
    # Cases are dumped concurrently for throughput, which makes the per-Case `seconds`
    # an *upper* bound on the live wall clock rather than a measurement of it. `--time`
    # forces one Case at a time so the number can be quoted.
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--time", action="store_true", help="one Case at a time")
    args = parser.parse_args()

    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))
    limit = asyncio.Semaphore(1 if args.time else args.concurrency)

    async def one(game_id: int) -> str:
        async with limit:
            try:
                return await dump_case(game_id, args.refresh)
            except Exception as error:  # never fatal: a missing Case is not a broken run
                return f"case {game_id:02d}: FAILED {error}"

    for result in await asyncio.gather(*(one(game_id) for game_id in game_ids)):
        print(result, flush=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
