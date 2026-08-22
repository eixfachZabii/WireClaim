"""The tournament heartbeat.

Everything else in WireClaim is driven by this: 100 Games, 757.575758 s apart,
each with a 60-second submission window. Missing a window is the single most
expensive thing we can do (README R7, R10), so the clock is deliberately dumb,
dependency-free and pinned to a local copy of the schedule -- it must keep
working when the network does not.
"""

from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

WINDOW = timedelta(seconds=60)
SCHEDULE = Path(__file__).resolve().parents[2] / "data" / "schedule.json"


@dataclass(frozen=True)
class Game:
    id: int
    start: datetime

    @property
    def close(self) -> datetime:
        return self.start + WINDOW

    def phase(self) -> str:
        """Which of the three tournament regimes this Game falls in (README R10)."""
        hour = self.start.astimezone().hour
        if 8 <= hour < 15:
            return "waking"
        return "awake" if hour >= 15 else "dark"


def load(path: Path = SCHEDULE) -> list[Game]:
    items = json.loads(path.read_text())["items"]
    games = [
        Game(g["id"], datetime.fromisoformat(g["start_time"].replace("Z", "+00:00")))
        for g in items
    ]
    return sorted(games, key=lambda g: g.start)


def now() -> datetime:
    return datetime.now(timezone.utc)


def current(games: list[Game], at: datetime | None = None) -> Game | None:
    """The Game whose submission window is open right now, if any."""
    at = at or now()
    i = bisect_right([g.start for g in games], at) - 1
    if i < 0:
        return None
    game = games[i]
    return game if at < game.close else None


def upcoming(games: list[Game], at: datetime | None = None) -> Game | None:
    """The next Game that has not yet opened."""
    at = at or now()
    i = bisect_right([g.start for g in games], at)
    return games[i] if i < len(games) else None


def sleep_until(target: datetime, slack: timedelta = timedelta(seconds=2)) -> float:
    """Seconds to wait to wake `slack` before `target`. Never negative.

    We wake early on purpose: the key fetch and download have to fit inside the
    window, so arriving late costs far more than spinning for two seconds.
    """
    return max(0.0, (target - slack - now()).total_seconds())


if __name__ == "__main__":  # a glance at where we are in the tournament
    games = load()
    n, up = current(games), upcoming(games)
    print(f"{len(games)} games | now {now().astimezone():%a %H:%M:%S %Z}")
    print(f"open now : {n.id if n else '-'}")
    if up:
        print(
            f"next     : game {up.id} at {up.start.astimezone():%a %H:%M:%S} "
            f"({up.phase()} phase) in {sleep_until(up.start, timedelta(0)):.0f}s"
        )
    from collections import Counter
    print("phases   :", dict(Counter(g.phase() for g in games)))
