from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import requests

from api.models import APIError, ForbiddenError, Game, NotFoundError, UnauthorizedError


class EHLClient:
    """Authenticated client for schedule and decryption-key retrieval."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: tuple[float, float] = (2.0, 5.0),
        session: requests.Session | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("TEAM_API_KEY is required")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update(
            {"X-API-Key": api_key, "Accept": "application/json"}
        )

    def list_games(self) -> list[Game]:
        response = self._session.get(
            f"{self._base_url}/api/games/list", timeout=self._timeout
        )
        payload = self._json(response, "listing games")
        if not isinstance(payload, list):
            raise ValueError("games response must be a JSON array")
        games = [Game.from_json(item) for item in payload]
        return sorted(games, key=lambda game: (game.start_time, game.id))

    def get_decryption_key(self, game_id: int) -> str:
        response = self._session.get(
            f"{self._base_url}/api/games/{game_id}/key", timeout=self._timeout
        )
        payload = self._json(response, f"retrieving the key for game {game_id}")
        if not isinstance(payload, Mapping):
            raise ValueError("key response must be a JSON object")
        key = payload.get("decryption_key")
        if not isinstance(key, str) or not key:
            raise ValueError("key response has no non-empty decryption_key")
        return key

    # TODO(api-submission): Add PUT /api/games/{game_id}/submissions here once
    # pricing output and the desired live-submission safeguards are defined.

    @staticmethod
    def _json(response: requests.Response, action: str) -> Any:
        if response.status_code != 200:
            detail = response.text.strip()[:500]
            error_type: type[APIError]
            error_type = {
                401: UnauthorizedError,
                403: ForbiddenError,
                404: NotFoundError,
            }.get(response.status_code, APIError)
            raise error_type(response.status_code, action, detail)
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise ValueError(f"{action} returned invalid JSON") from exc

