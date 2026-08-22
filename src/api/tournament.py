"""
QuantCo Claim-to-Fame Functional Tournament API Client & Submission Module.

This module provides purely functional helpers to interact with the QuantCo Claim-to-Fame tournament backend:
- `list_games()`: List all scheduled and test games.
- `get_decryption_key(game_id)`: Retrieve the AES decryption key for a case.
- `submit_price(game_id, charge_price, acceptance_limit, index=1)`: Submit a single line item price.
- `submit_prices(game_id, submissions)`: Submit one or multiple line items.

Why is there an 'index'?
------------------------
An invoice (`invoices.pdf`) in a damage case can have multiple line items
(e.g., Line 1: 'Windshield replacement', Line 2: 'Labor hours', Line 3: 'Sealant').
The backend tournament API maps each line item by its 1-based `index` (1, 2, 3...).
If a case has only 1 line item, `index` is simply 1 (default).

Configuration & Environment Variables:
---------------------------------------
- `TEAM_API_KEY`: Team token sent in the `X-API-Key` HTTP header.
- `BASE_URL`: Base competition URL (default: `https://c2f.public.quantco.cloud`).
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Load .env with optional python-dotenv or stdlib fallback
try:
    from dotenv import find_dotenv, load_dotenv

    env_file = find_dotenv(usecwd=True) or (Path(__file__).resolve().parent.parent.parent / ".env")
    load_dotenv(dotenv_path=env_file, override=True)
except ImportError:
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"\''))

DEFAULT_BASE_URL = "https://c2f.public.quantco.cloud"


class APIError(RuntimeError):
    """Raised when tournament API returns a non-200 HTTP response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.message = message


def _get_urlopen():
    """Retrieve urlopen function, supporting monkeypatching on src.api."""
    try:
        import src.api
        return getattr(src.api, "urlopen", urllib.request.urlopen)
    except Exception:
        return urllib.request.urlopen


def _get_config(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve API key and base URL from arguments or environment variables."""
    key = (api_key or os.environ.get("TEAM_API_KEY", "")).strip()
    if not key:
        raise RuntimeError("TEAM_API_KEY is missing; copy .env.example to .env")

    url = (base_url or os.environ.get("BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    return key, url


def _validate_price(name: str, value: float) -> float:
    """Validate that a monetary price is numeric, finite, and non-negative."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"'{name}' must be a number, got {type(value).__name__}")
    val_float = float(value)
    if math.isnan(val_float) or math.isinf(val_float):
        raise ValueError(f"'{name}' must be finite, got {val_float}")
    if val_float < 0:
        raise ValueError(f"'{name}' must be non-negative (>= 0), got {val_float}")
    return val_float


def _get(path: str, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 10.0) -> Any:
    """Send a GET request to the tournament backend."""
    key, url = _get_config(api_key, base_url)
    request = Request(
        f"{url}{path}",
        headers={"X-API-Key": key, "Accept": "application/json"},
    )
    try:
        with _get_urlopen()(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise APIError(error.code, message) from error


def _put(
    path: str,
    data: Any,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> Any:
    """Send a PUT request to the tournament backend with JSON body."""
    key, url = _get_config(api_key, base_url)
    body = json.dumps(data).encode("utf-8")
    request = Request(
        f"{url}{path}",
        data=body,
        headers={"X-API-Key": key, "Content-Type": "application/json", "Accept": "application/json"},
        method="PUT",
    )
    try:
        with _get_urlopen()(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise APIError(error.code, message) from error


# ============================================================================
# Functional API Operations
# ============================================================================


def list_games(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> List[Dict[str, Any]]:
    """Fetch the list of all tournament games and their scheduled start times.

    Calls `GET /api/games/list`.
    """
    return _get("/api/games/list", api_key=api_key, base_url=base_url, timeout=timeout)


def get_decryption_key(
    game_id: int,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> str:
    """Fetch the AES-256 decryption key for a game's case zip archive.

    Calls `GET /api/games/{game_id}/key`.
    """
    data = _get(f"/api/games/{game_id}/key", api_key=api_key, base_url=base_url, timeout=timeout)
    return str(data["decryption_key"])


def submit_price(
    game_id: int,
    charge_price: float,
    acceptance_limit: float,
    index: int = 1,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """Submit a single line item price for an active game round."""
    results = submit_prices(
        game_id=game_id,
        submissions=[{"index": index, "charge_price": charge_price, "acceptance_limit": acceptance_limit}],
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )
    return results[0] if results else {}


def submit_prices(
    game_id: int,
    submissions: Sequence[Union[Dict[str, Any], Tuple[float, float]]],
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> List[Dict[str, Any]]:
    """Submit or update line item prices for an active game round.

    Calls `PUT /api/games/{game_id}/submissions`.
    """
    payload: List[Dict[str, Union[int, float]]] = []
    for idx, item in enumerate(submissions, start=1):
        if isinstance(item, tuple) and len(item) == 2:
            a, b = item
            charge = _validate_price("charge_price", a)
            limit = _validate_price("acceptance_limit", b)
            payload.append({"index": idx, "charge_price": charge, "acceptance_limit": limit})
        elif isinstance(item, dict):
            item_index = int(item.get("index", idx))
            charge = _validate_price("charge_price", item.get("charge_price", 0.0))
            limit = _validate_price("acceptance_limit", item.get("acceptance_limit", 0.0))
            payload.append({"index": item_index, "charge_price": charge, "acceptance_limit": limit})
        else:
            raise TypeError(
                f"Unsupported submission item format: {item}. Expected dict or (charge_price, acceptance_limit) tuple."
            )

    return _put(
        f"/api/games/{game_id}/submissions",
        data=payload,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )


def print_submissions(results: Sequence[Dict[str, Any]]) -> None:
    """Print confirmed submissions in a formatted ASCII table."""
    if not results:
        print("  No submissions to display.")
        return

    print(f"  {'line':>6}  {'charge price (a)':>18}  {'acceptance limit (b)':>22}  {'submitted at':>24}")
    print(f"  {'-'*6:>6}  {'-'*18:>18}  {'-'*22:>22}  {'-'*24:>24}")
    for item in results:
        line_idx = item.get("line_item_index", item.get("index", 1))
        charge = float(item.get("charge_price", 0.0))
        limit = float(item.get("acceptance_limit", 0.0))
        submitted_at = str(item.get("submitted_at", ""))
        print(f"  {line_idx:>6}  {charge:>18.2f}  {limit:>22.2f}  {submitted_at:>24}")
