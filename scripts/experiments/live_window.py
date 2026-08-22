"""Gate LLM calls out of the live tournament's Game boundary window.

The task instruction for this harness is explicit: **sleep through every live Game window,
from T-10s to T+70s around each Game boundary** -- the live runner (`main.py` /
`scripts/supervise.sh`, confirmed running throughout this measurement) shares the same Azure
OpenAI deployment, and a rate-limit hit there costs a whole Game.

A single evidence call can take up to `LLM_TIMEOUT_SECONDS` (55s) to return, so "don't call
during [T-10, T+70]" is not the same as "don't start a call during [T-10, T+70]": a call
started at T-30 would still be in flight at T-10 and run traffic straight through the danger
window. `wait_for_safe_window` gates on **starting** a call, with enough margin before T-10
that a full-length call is guaranteed to complete before the window opens (55s call + 13s
margin => don't start inside 68s of the next boundary), and it holds calls back until T+70
has actually passed after a boundary.

Every Game boundary sits at `GAME_0_START + k * GAME_PERIOD_SECONDS` for integer `k`; this
module only needs the phase within one period, not which Game index we are in.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

#: Game 33's published start time. Any exact boundary works as the phase reference --
#: every other boundary is this time plus an integer multiple of the period.
GAME_33_START_UTC = "2026-08-22T19:44:02.424+00:00"
GAME_PERIOD_SECONDS = 757.575758

#: Longest a single evidence call is allowed to run (matches the live
#: `LLM_TIMEOUT_SECONDS`) plus a safety margin, and the published post-boundary buffer.
PRE_BOUNDARY_BUFFER = 68.0
POST_BOUNDARY_BUFFER = 70.0

_T0 = datetime.fromisoformat(GAME_33_START_UTC).timestamp()


def phase() -> float:
    """Seconds elapsed since the most recent Game boundary, in [0, GAME_PERIOD_SECONDS)."""
    return (time.time() - _T0) % GAME_PERIOD_SECONDS


def seconds_until_safe() -> float:
    """0.0 if it is safe to start a call now, else how long to sleep before rechecking."""
    p = phase()
    since_boundary = p
    until_next = GAME_PERIOD_SECONDS - p
    if since_boundary < POST_BOUNDARY_BUFFER:
        return POST_BOUNDARY_BUFFER - since_boundary + 0.5
    if until_next < PRE_BOUNDARY_BUFFER:
        return until_next + POST_BOUNDARY_BUFFER + 0.5
    return 0.0


async def wait_for_safe_window(label: str = "") -> None:
    """Block until it is safe to start a new LLM call. Loops in case a long sleep overshoots."""
    first = True
    while True:
        wait = seconds_until_safe()
        if wait <= 0.0:
            return
        if first:
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            print(
                f"  [live-window] {now} {label} pausing {wait:.1f}s to clear the live Game boundary",
                flush=True,
            )
            first = False
        await asyncio.sleep(wait)


if __name__ == "__main__":
    print(f"phase={phase():.1f}s  seconds_until_safe={seconds_until_safe():.1f}s")
