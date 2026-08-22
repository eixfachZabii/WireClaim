"""Pull every settled Transaction for a team, following pagination.

The leaderboard endpoint returns 100 rows per page. Reading only page 1 makes a
17-Line-Item Game look like a 4-Line-Item Game, which is exactly the mistake that put
BLIND_LINE_ITEMS at 8 and justified a per-Case flag cap on the wrong denominator.
Always page to the end.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode

BASE = "https://c2f.public.quantco.cloud/leaderboard/api"
CACHE = Path("var/transactions")


def _get(path: str, **params: object) -> dict:
    url = f"{BASE}/{path}?{urlencode({k: str(v) for k, v in params.items()})}"
    for attempt in range(4):
        result = subprocess.run(
            ["curl", "-s", "-m", "30", url], capture_output=True, text=True, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
        time.sleep(1.0 + attempt)
    raise RuntimeError(f"Could not fetch {url}")


def teams() -> list[str]:
    return [row["team_name"] for row in _get("matrix")["items"]]


def matrix() -> dict[str, list[float]]:
    return {row["team_name"]: row["cells"] for row in _get("matrix")["items"]}


def transactions(team: str, game_id: int) -> list[dict]:
    """Every row for this team in this Game, across all pages."""
    cache_path = CACHE / f"g{game_id:03d}_{team.replace(' ', '_')}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    rows: list[dict] = []
    page = 1
    while True:
        payload = _get("transactions", team=team, game_id=game_id, page=page)
        rows.extend(payload["items"])
        if page >= payload.get("total_pages", 1):
            break
        page += 1
    total = payload.get("total")
    if total is not None and len(rows) != total:
        raise RuntimeError(f"{team} g{game_id}: got {len(rows)} rows, endpoint said {total}")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(rows))
    return rows


def line_item_count(rows: list[dict]) -> int:
    return max((row["line_item_index"] for row in rows), default=0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", default="Bin busy")
    parser.add_argument("--games", default="1-14")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    for game_id in range(int(start), int(end or start) + 1):
        rows = transactions(args.team, game_id)
        print(f"G{game_id:3d}: {len(rows):4d} rows, {line_item_count(rows):2d} Line Items")


if __name__ == "__main__":
    main()
