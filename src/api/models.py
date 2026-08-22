from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class APIError(RuntimeError):
    """Base exception for an EHL API failure."""

    def __init__(self, status_code: int, action: str, detail: str = "") -> None:
        message = f"{action} failed with HTTP {status_code}"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)
        self.status_code = status_code
        self.action = action
        self.detail = detail


class UnauthorizedError(APIError):
    pass


class ForbiddenError(APIError):
    pass


class NotFoundError(APIError):
    pass


@dataclass(frozen=True, slots=True)
class Game:
    id: int
    start_time: datetime

    @classmethod
    def from_json(cls, payload: Any) -> Game:
        if not isinstance(payload, dict):
            raise ValueError("game must be a JSON object")
        game_id = payload.get("id")
        raw_start = payload.get("start_time")
        if isinstance(game_id, bool) or not isinstance(game_id, int) or game_id < 0:
            raise ValueError("game id must be a nonnegative integer")
        if not isinstance(raw_start, str):
            raise ValueError("game start_time must be a string")

        normalized = raw_start[:-1] + "+00:00" if raw_start.endswith("Z") else raw_start
        try:
            start_time = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"invalid game start_time: {raw_start!r}") from exc
        if start_time.tzinfo is None:
            raise ValueError("game start_time must include a timezone")
        return cls(id=game_id, start_time=start_time.astimezone(timezone.utc))

