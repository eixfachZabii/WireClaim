"""Small read-only client for the EHL game API."""

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class APIError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _get(path: str):
    api_key = os.environ.get("TEAM_API_KEY")
    if not api_key:
        raise RuntimeError("TEAM_API_KEY is missing; copy .env.example to .env")
    base_url = os.environ.get(
        "BASE_URL", "https://c2f.public.quantco.cloud"
    ).rstrip("/")

    request = Request(
        f"{base_url}{path}",
        headers={"X-API-Key": api_key, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            return json.load(response)
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise APIError(error.code, message) from error


def list_games() -> list[dict]:
    return _get("/api/games/list")


def get_decryption_key(game_id: int) -> str:
    return _get(f"/api/games/{game_id}/key")["decryption_key"]


# TODO: Add the submission function here once the analysis output is ready.
