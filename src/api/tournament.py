"""
QuantCo Claim-to-Fame Functional Tournament API Client & Submission Module.

This module provides purely functional helpers (no class instantiation needed)
to interact with the QuantCo Claim-to-Fame tournament backend:
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
- `BASE_URL`: Base competition URL (default: `https://c2f.public.quantco.cloud/`).
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import requests
from dotenv import find_dotenv, load_dotenv

# Load .env file automatically
env_file = find_dotenv(usecwd=True) or (Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv(dotenv_path=env_file, override=True)

DEFAULT_BASE_URL = "https://c2f.public.quantco.cloud/"


def _get_config(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve API key and base URL from arguments or environment variables."""
    key = (api_key or os.environ.get("TEAM_API_KEY", "")).strip()
    if not key:
        raise ValueError(
            "Missing TEAM_API_KEY. Provide it as an argument or set the 'TEAM_API_KEY' environment variable in your .env file."
        )

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


def _check_response(response: requests.Response, action: str) -> requests.Response:
    """Check API response status and raise descriptive error if not HTTP 200."""
    if response.status_code == 200:
        return response

    status = response.status_code
    error_msg = response.text.strip()

    if status == 401:
        raise RuntimeError(f"[{status}] {action} failed: Unauthorized. Missing or invalid TEAM_API_KEY.")
    elif status == 403:
        raise RuntimeError(
            f"[{status}] {action} failed: Forbidden. Game has not started yet, already ended, or team ineligible."
        )
    elif status == 404:
        raise RuntimeError(f"[{status}] {action} failed: Not found. Verify the game_id.")
    elif status == 422:
        raise RuntimeError(
            f"[{status}] {action} failed: Unprocessable Entity. Check that prices are non-negative and finite."
        )
    else:
        raise RuntimeError(f"[{status}] {action} failed: {error_msg}")


# ============================================================================
# Functional API Operations
# ============================================================================


def list_games(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """Fetch the list of all tournament games and their scheduled start times.

    Calls `GET /api/games/list`.
    """
    key, url = _get_config(api_key, base_url)
    headers = {"X-API-Key": key}
    resp = requests.get(f"{url}/api/games/list", headers=headers, timeout=timeout)
    _check_response(resp, "Listing games")
    return resp.json()


def get_decryption_key(
    game_id: int,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 30.0,
) -> str:
    """Fetch the AES-256 decryption key for a game's case zip archive.

    Calls `GET /api/games/{game_id}/key`.
    """
    key, url = _get_config(api_key, base_url)
    headers = {"X-API-Key": key}
    resp = requests.get(f"{url}/api/games/{game_id}/key", headers=headers, timeout=timeout)
    _check_response(resp, f"Getting decryption key for game {game_id}")
    data = resp.json()
    return str(data["decryption_key"])


def submit_price(
    game_id: int,
    charge_price: float,
    acceptance_limit: float,
    index: int = 1,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 30.0,
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
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """Submit or update line item prices for an active game round.

    Calls `PUT /api/games/{game_id}/submissions`.
    """
    key, url = _get_config(api_key, base_url)
    headers = {"X-API-Key": key, "Content-Type": "application/json"}

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

    resp = requests.put(
        f"{url}/api/games/{game_id}/submissions",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    _check_response(resp, f"Submitting prices for game {game_id}")
    return resp.json()


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
