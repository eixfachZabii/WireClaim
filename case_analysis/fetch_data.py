"""Pull all public tournament data into local JSON files.

Fetches, for every settled (completed) Game:
- the game schedule            (GET /leaderboard/api/games)
- the head-to-head matrix      (GET /leaderboard/api/matrix)   -> team list + pairwise nets
- per-team performance         (GET /leaderboard/api/performance?team=..)
- every settled Transaction    (GET /leaderboard/api/transactions?game_id=..&team=..)

Everything is written under case_analysis/data/raw/ as plain JSON so the
analysis step (analyze.py) never needs the network. Re-running is incremental:
transactions for a game already on disk are not re-fetched.

Usage:
    python3 case_analysis/fetch_data.py            # fetch everything new
    python3 case_analysis/fetch_data.py --force    # re-fetch all games

Only reads the same endpoints the public leaderboard page calls (allowed per
GAME-AND-PROOFS R9), at a polite rate.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

LEADERBOARD_API = "https://c2f.public.quantco.cloud/leaderboard/api"
DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_DIR = DATA_DIR / "raw"
RATE_LIMIT_SECONDS = 0.4


def _get(path: str) -> dict:
    """GET a leaderboard endpoint; fall back to curl if urllib lacks a CA bundle."""
    url = LEADERBOARD_API + path
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)
    except OSError:
        import subprocess

        out = subprocess.run(["curl", "-sSf", url], capture_output=True, check=True)
        return json.loads(out.stdout)


def _save(name: str, payload: object) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def fetch_games() -> list[dict]:
    games = _get("/games?page_size=1000")["items"]
    _save("games.json", games)
    return games


def fetch_matrix() -> dict:
    matrix = _get("/matrix")
    _save("matrix.json", matrix)
    return matrix


def fetch_performance(team_names: list[str]) -> list[dict]:
    rows = []
    for name in team_names:
        rows.append(_get(f"/performance?team={urllib.parse.quote(name)}"))
        time.sleep(RATE_LIMIT_SECONDS)
    _save("performance.json", rows)
    return rows


def fetch_game_transactions(game_id: int, team_names: list[str]) -> list[dict]:
    """All unique Transaction rows of one settled game.

    The endpoint requires a team filter; querying every team and deduplicating
    yields the full set of rows (each row names both issuer and reviewer).
    """
    rows: dict[tuple, dict] = {}
    for name in team_names:
        team_q = urllib.parse.quote(name)
        page = 1
        while True:
            data = _get(
                f"/transactions?game_id={game_id}&team={team_q}"
                f"&page={page}&page_size=500"
            )
            for row in data["items"]:
                key = (
                    row["issuer"],
                    row["reviewer"],
                    row["line_item_index"],
                    bool(row["accepted"]),
                    float(row["amount"]),
                )
                rows[key] = {
                    "issuer": row["issuer"],
                    "reviewer": row["reviewer"],
                    "line_item_index": row["line_item_index"],
                    "accepted": bool(row["accepted"]),
                    "amount": float(row["amount"]),
                }
            if page >= data["total_pages"]:
                break
            page += 1
            time.sleep(RATE_LIMIT_SECONDS)
        time.sleep(RATE_LIMIT_SECONDS)
    return sorted(rows.values(), key=lambda r: (r["line_item_index"], r["issuer"], r["reviewer"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-fetch games already on disk")
    args = parser.parse_args()

    games = fetch_games()
    matrix = fetch_matrix()
    team_names = [cell["team_name"] for cell in matrix["items"]]
    print(f"{len(games)} games scheduled, {len(team_names)} teams on the leaderboard")

    fetch_performance(team_names)

    completed = [g for g in games if g.get("status") == "completed"]
    print(f"{len(completed)} settled games to pull transactions for")
    for game in completed:
        game_id = game["id"]
        out = RAW_DIR / f"transactions_game_{game_id:03d}.json"
        if out.exists() and not args.force:
            print(f"  game {game_id}: cached ({out.name})")
            continue
        rows = fetch_game_transactions(game_id, team_names)
        _save(out.name, rows)
        print(f"  game {game_id}: {len(rows)} transaction rows")

    print(f"done -> {RAW_DIR}")


if __name__ == "__main__":
    main()
