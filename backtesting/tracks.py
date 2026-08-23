"""Fresh, isolated execution of the repository's existing Strategy Tracks."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Mapping, Sequence

from backtesting.history import HistoryStore, use_price_memory
from backtesting.models import Submission
from src.data.models import CaseData, Proposal

TRACKS = ("strategy1", "strategy2", "strategy3", "fast_path")


@dataclass(frozen=True)
class TrackDraw:
    game_id: int
    track: str
    draw: int
    submissions: Mapping[int, Submission]
    elapsed_seconds: float
    error: str | None = None
    timed_out: bool = False

    @property
    def answered(self) -> bool:
        return bool(self.submissions)


async def run_track_draws(
    case: CaseData,
    history: HistoryStore,
    run_dir: Path,
    *,
    draws: int = 3,
    timeout_seconds: float = 60.0,
    tracks: Sequence[str] = TRACKS,
) -> dict[int, dict[str, TrackDraw]]:
    unknown = set(tracks) - set(TRACKS)
    if unknown:
        raise ValueError(f"unknown tracks {sorted(unknown)}")
    decisions_dir = run_dir / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    import src.runtime.decisions as decision_log

    previous_dir = decision_log.DECISIONS_DIR
    decision_log.DECISIONS_DIR = decisions_dir
    results: dict[int, dict[str, TrackDraw]] = {}
    memory = history.memory_before(case.game_id)
    try:
        with use_price_memory(memory):
            for draw in range(draws):
                tasks = [
                    asyncio.create_task(
                        _run_one(case, track, draw, timeout_seconds), name=f"{track}-{draw}"
                    )
                    for track in tracks
                ]
                completed = await asyncio.gather(*tasks)
                results[draw] = {item.track: item for item in completed}
                for item in completed:
                    _save_draw(run_dir, item)
    finally:
        decision_log.DECISIONS_DIR = previous_dir
    return results


async def _run_one(case: CaseData, track: str, draw: int, timeout_seconds: float) -> TrackDraw:
    operation = _operation(track, case, timeout_seconds)
    started = time.monotonic()
    error = None
    timed_out = False
    proposal = None
    try:
        proposal = await asyncio.wait_for(operation, timeout=timeout_seconds)
    except TimeoutError:
        timed_out = True
        error = f"TimeoutError: exceeded {timeout_seconds:.1f}s"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    submissions = _proposal_submissions(proposal)
    return TrackDraw(
        game_id=case.game_id,
        track=track,
        draw=draw,
        submissions=submissions,
        elapsed_seconds=time.monotonic() - started,
        error=error,
        timed_out=timed_out,
    )


def _operation(track: str, case: CaseData, timeout_seconds: float) -> Awaitable[Proposal | None]:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    if track == "strategy1":
        from src.legacy.strategy1 import propose

        return propose(case, deadline)
    if track == "strategy2":
        from src.strategies.strategy2 import propose

        return propose(case, deadline)
    if track == "strategy3":
        from src.legacy.strategy3 import propose

        return propose(case, deadline)
    from src.strategies.fast_path import llm_values

    return llm_values(case)


def merged_submission(
    case: CaseData, draws: Mapping[str, TrackDraw]
) -> dict[int, Submission]:
    from src.strategies import STRATEGY_PRIORITIES
    from src.strategies.fast_path import standard_values

    valid = {item.index for item in case.line_items}
    merged = {
        price.index: Submission(price.charge_price, price.acceptance_limit)
        for price in standard_values(case).prices
    }
    fast = draws.get("fast_path")
    if fast is not None:
        merged.update({index: value for index, value in fast.submissions.items() if index in valid})
    layers = sorted(
        (STRATEGY_PRIORITIES.get(track, 0), result)
        for track, result in draws.items()
        if track in STRATEGY_PRIORITIES
    )
    for _, result in layers:
        merged.update({index: value for index, value in result.submissions.items() if index in valid})
    return merged


def _proposal_submissions(proposal: Proposal | None) -> dict[int, Submission]:
    if proposal is None:
        return {}
    return {
        price.index: Submission(price.charge_price, price.acceptance_limit)
        for price in proposal.prices
    }


def _save_draw(run_dir: Path, draw: TrackDraw) -> None:
    import json

    directory = run_dir / "draws" / f"game_{draw.game_id:03d}" / str(draw.draw)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "game_id": draw.game_id,
        "track": draw.track,
        "draw": draw.draw,
        "elapsed_seconds": draw.elapsed_seconds,
        "error": draw.error,
        "timed_out": draw.timed_out,
        "submissions": {
            str(index): {"charge": value.charge, "limit": value.limit}
            for index, value in draw.submissions.items()
        },
    }
    (directory / f"{draw.track}.json").write_text(json.dumps(payload, indent=2))
