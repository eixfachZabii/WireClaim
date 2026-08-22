from __future__ import annotations

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable

from api.client import EHLClient
from api.models import Game
from wireclaim.domain.models import CaseReady
from wireclaim.orchestration.runner import GameRunner
from wireclaim.state.database import StateStore

LOGGER = logging.getLogger(__name__)


def seconds_until(start_time: datetime, now: datetime | None = None) -> float:
    current = now or datetime.now(timezone.utc)
    return max(0.0, (start_time - current).total_seconds())


class ScheduleWatcher:
    def __init__(
        self,
        *,
        client: EHLClient,
        runner: GameRunner,
        state: StateStore,
        refresh_seconds: float,
        max_workers: int = 4,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._runner = runner
        self._state = state
        self._refresh_seconds = refresh_seconds
        self._max_workers = max_workers
        self._sleep = sleep

    def run_forever(self) -> None:
        active: dict[int, Future[CaseReady]] = {}
        with ThreadPoolExecutor(
            max_workers=self._max_workers, thread_name_prefix="wireclaim-case"
        ) as executor:
            while True:
                self._collect_finished(active)
                games = self._refresh_games()
                now = datetime.now(timezone.utc)
                for game in games:
                    if game.start_time > now:
                        continue
                    if game.id in active or self._state.status(game.id) == "completed":
                        continue
                    active[game.id] = executor.submit(self._runner.run, game)

                upcoming = [game for game in games if game.start_time > now]
                wait = self._refresh_seconds
                if upcoming:
                    wait = min(wait, seconds_until(upcoming[0].start_time, now))
                self._sleep(max(0.05, wait))

    def _refresh_games(self) -> list[Game]:
        try:
            games = self._client.list_games()
        except Exception:
            LOGGER.exception("could not refresh the EHL game schedule")
            return []
        for game in games:
            self._state.register(game)
        return games

    @staticmethod
    def _collect_finished(active: dict[int, Future[CaseReady]]) -> None:
        for game_id, future in list(active.items()):
            if not future.done():
                continue
            del active[game_id]
            try:
                future.result()
            except Exception:
                LOGGER.exception("ingestion failed for game %s", game_id)

