from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from api.models import Game


class StateStore:
    """Small durable state store; decryption keys are never persisted."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock, self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS game_state (
                    game_id INTEGER PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def register(self, game: Game) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO game_state(game_id, start_time, status, updated_at)
                VALUES (?, ?, 'scheduled', ?)
                ON CONFLICT(game_id) DO UPDATE SET start_time=excluded.start_time
                """,
                (game.id, game.start_time.isoformat(), now),
            )

    def transition(
        self, game: Game, status: str, *, error: str | None = None
    ) -> None:
        self.register(game)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE game_state
                SET status=?,
                    attempts=attempts + CASE WHEN ? = 'key_pending' THEN 1 ELSE 0 END,
                    last_error=?,
                    updated_at=?
                WHERE game_id=?
                """,
                (status, status, error, now, game.id),
            )

    def status(self, game_id: int) -> str | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT status FROM game_state WHERE game_id=?", (game_id,)
            ).fetchone()
        return str(row["status"]) if row else None

    def start_time(self, game_id: int) -> datetime | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT start_time FROM game_state WHERE game_id=?", (game_id,)
            ).fetchone()
        return datetime.fromisoformat(row["start_time"]) if row else None

    def rows(self) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT game_id, start_time, status, attempts, last_error, updated_at
                FROM game_state ORDER BY start_time, game_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

