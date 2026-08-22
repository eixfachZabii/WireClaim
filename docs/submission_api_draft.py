"""
Archived teammate draft - not packaged or used by the initial setup.

QuantCo Claim-to-Fame Functional API Client & Submission Module.

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
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import requests

# Load .env file automatically if python-dotenv is installed
try:
    from pathlib import Path
    from dotenv import find_dotenv, load_dotenv

    env_file = find_dotenv(usecwd=True) or (Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(dotenv_path=env_file, override=True)
except ImportError:
    pass

DEFAULT_BASE_URL = "https://c2f.public.quantco.cloud/"


def _get_config(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve API key and base URL from arguments or environment variables.

    Args:
        api_key: Optional explicit API key.
        base_url: Optional explicit base URL.

    Returns:
        Tuple of (resolved_api_key, resolved_base_url).

    Raises:
        ValueError: If no API key is provided or found in the environment.
    """
    key = (api_key or os.environ.get("TEAM_API_KEY", "")).strip()
    if not key:
        raise ValueError(
            "Missing TEAM_API_KEY. Provide it as an argument or set the 'TEAM_API_KEY' environment variable in your .env file."
        )

    url = (base_url or os.environ.get("BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    return key, url


def _validate_price(name: str, value: float) -> float:
    """Validate that a monetary price is numeric, finite, and non-negative.

    Args:
        name: Parameter name for error messages (e.g. 'charge_price').
        value: The price value to check.

    Returns:
        The validated float value.

    Raises:
        ValueError: If value is negative, NaN, infinite, or not a number.
    """
    if not isinstance(value, (int, float)):
        raise TypeError(f"'{name}' must be a number, got {type(value).__name__}")
    val_float = float(value)
    if math.isnan(val_float) or math.isinf(val_float):
        raise ValueError(f"'{name}' must be finite, got {val_float}")
    if val_float < 0:
        raise ValueError(f"'{name}' must be non-negative (>= 0), got {val_float}")
    return val_float


def _check_response(response: requests.Response, action: str) -> requests.Response:
    """Check API response status and raise descriptive error if not HTTP 200.

    Args:
        response: Response object from requests.
        action: Human-readable action description.

    Returns:
        The successful response object.

    Raises:
        RuntimeError: If response status code is not 200, containing status and error details.
    """
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
    Game 0 is typically a permanent test game always available for testing.

    Args:
        api_key: Team API key (defaults to `TEAM_API_KEY` env var).
        base_url: Base URL (defaults to `BASE_URL` env var or production default).
        timeout: Request timeout in seconds (default: 30.0).

    Returns:
        List[Dict[str, Any]]: List of game dictionaries, e.g.:
            `[{'id': 0, 'start_time': '2026-08-22T12:00:00Z'}, ...]`

    Example:
        >>> games = list_games()
        >>> for g in games:
        ...     print(f"Game {g['id']} starts at {g['start_time']}")
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
    Note: The decryption key only becomes available after the game's `start_time`.

    Args:
        game_id: Integer ID of the game (e.g. 0 for test game).
        api_key: Team API key (defaults to `TEAM_API_KEY` env var).
        base_url: Base URL (defaults to `BASE_URL` env var or production default).
        timeout: Request timeout in seconds (default: 30.0).

    Returns:
        str: Decryption key password to unpack `case_{game_id:02d}.zip`.

    Example:
        >>> key = get_decryption_key(0)
        >>> print(f"Decryption key: {key}")
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
    """Submit a single line item price for an active game round.

    Convenience function for submitting 1 line item directly without wrapping
    in lists or dictionaries.

    Both amounts MUST be the gross total for the line item (not per-unit and not net).

    Args:
        game_id: Integer ID of the target game (e.g., 0).
        charge_price: Charge price 'a' (amount charged to opposing teams as Handyman).
        acceptance_limit: Acceptance limit 'b' (maximum amount willing to pay as Insurance).
        index: 1-based line item index on the invoice (default: 1).
        api_key: Team API key (defaults to `TEAM_API_KEY` env var).
        base_url: Base URL (defaults to `BASE_URL` env var or production default).
        timeout: Request timeout in seconds (default: 30.0).

    Returns:
        Dict[str, Any]: The confirmed submission record from the server, e.g.:
            `{'game_id': 0, 'team_id': 1, 'line_item_index': 1, 'charge_price': 410.0, 'acceptance_limit': 430.0, 'submitted_at': '...'}`

    Example:
        >>> # Submit charge price a=410.0, acceptance limit b=430.0 for line item 1
        >>> result = submit_price(game_id=0, charge_price=410.0, acceptance_limit=430.0)
        >>> print(result)
    """
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
    Implements upsert semantics (last write wins during the 1-minute round).

    Supports multiple input formats:
    - List of dicts: `[{"index": 1, "charge_price": 410.0, "acceptance_limit": 430.0}]`
    - List of tuples (auto-indexed 1..N): `[(410.0, 430.0), (120.0, 150.0)]` -> index 1 & 2

    Args:
        game_id: Integer ID of the target game.
        submissions: Sequence of line item submissions (dicts or (charge_price, acceptance_limit) tuples).
        api_key: Team API key (defaults to `TEAM_API_KEY` env var).
        base_url: Base URL (defaults to `BASE_URL` env var or production default).
        timeout: Request timeout in seconds (default: 30.0).

    Returns:
        List[Dict[str, Any]]: List of confirmed submission dictionaries from the server.

    Example:
        >>> # Using list of dicts:
        >>> res = submit_prices(0, [{"index": 1, "charge_price": 410.0, "acceptance_limit": 430.0}])
        >>> # Or using simple tuples (auto-indexed starting at 1):
        >>> res = submit_prices(0, [(410.0, 430.0), (120.0, 150.0)])
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
    """Print confirmed submissions in a formatted ASCII table.

    Args:
        results: List of submission response dictionaries from `submit_prices` or `submit_price`.
    """
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
