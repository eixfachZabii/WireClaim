"""Pull every settled Transaction for a team, following pagination -- and read the
leaderboard `/matrix` without guessing which Game a cell belongs to.

Two defects were found the hard way; both are fixed here, and both fixes are the same
shape: *never trust a length, always carry the identity of the thing you fetched.*

1. Short reads
--------------
The endpoint returns 100 rows per page. Reading only page 1 makes a 17-Line-Item Game look
like a 4-Line-Item Game, which is exactly the mistake that put BLIND_LINE_ITEMS at 8 and
justified a per-Case flag cap on the wrong denominator. We page to the end *and* compare
the row count against the endpoint's own `total`.

That check was already here -- but the on-disk cache under ``var/transactions`` stored a
bare list of rows, so a file written by an older, short-reading version was indistinguishable
from a good one and was reused forever. The cache is now **self-validating**: every file
carries the `total` the endpoint reported, and a file whose row count disagrees with its own
`total` (or which predates the stamp) is refused and re-fetched. `--refresh` forces it.

2. `/matrix` `cells` is not indexed by Game id
----------------------------------------------
We assumed `cells[k]` was Game `k+1`. It is not. `cells` is a **trailing window of the
twenty most recently completed Games**, and the payload tells you which:

    GET /leaderboard/api/matrix -> {"items": [{"team_name", "cells", "total"}, ...],
                                    "game_ids": [4, 5, ..., 23], ...}

With 23 Games completed, `game_ids == [4..23]` and `len(cells) == 20`. Every cell shifts
left by one each time a Game settles, which is why "a net at index 19 under one read
appears at index 16 under another". Positional indexing was therefore wrong for *every*
Game as soon as Game 21 settled, and it silently attributed Game 17's net (-63,789) to
Game 16 (really -4,721). See `scripts/replay_payoffs.py` for the damage.

So `matrix()` no longer returns a positional list. It returns `{team: {game_id: net}}`,
resolved from `game_ids` and cross-checked against `/games`. If the mapping cannot be
established -- no `game_ids`, or a length that does not line up with the completed Games --
it raises `AmbiguousMatrix` rather than guessing, and callers fall back on the authoritative
identity:

    net = sum(amount as issuer) - sum(amount if accepted else 1.5 * amount as reviewer)

Usage
-----
    PYTHONPATH=. python scripts/pull_transactions.py --games 1-23
    PYTHONPATH=. python scripts/pull_transactions.py --games 16 --refresh
    PYTHONPATH=. python scripts/pull_transactions.py --games 1-23 --check-cache
    PYTHONPATH=. python scripts/pull_transactions.py --matrix
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

#: Bump when the on-disk shape changes. A file without the current version is refused,
#: because a file we cannot validate is exactly the thing that poisoned the analysis.
CACHE_VERSION = 2

PAGE_SIZE = 100


class ShortRead(RuntimeError):
    """Fetched fewer rows than the endpoint said existed. Never silently tolerated."""


class AmbiguousMatrix(RuntimeError):
    """`/matrix` cells could not be mapped onto Game ids. Refuse to guess."""


# ------------------------------------------------------------------------------ http


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


# ----------------------------------------------------------------------------- games


def games() -> dict[int, str]:
    """`{game_id: status}` for every scheduled Game, from `/games`."""
    return {int(row["id"]): row["status"] for row in _get("games")["items"]}


def completed_games() -> list[int]:
    """Ascending ids of the Games that have settled. The only list worth iterating."""
    return sorted(gid for gid, status in games().items() if status == "completed")


# ---------------------------------------------------------------------------- matrix


def teams() -> list[str]:
    return [row["team_name"] for row in _get("matrix")["items"]]


def matrix_game_ids(payload: dict | None = None) -> list[int]:
    """Which Game each `cells` position belongs to. Raises rather than guessing.

    The endpoint publishes `game_ids` alongside `items`; that is authoritative and is used
    when its length matches `cells`. The only accepted fallback is the degenerate case
    where `cells` covers *every* completed Game, verified against `/games`. Anything else
    -- including the trailing-window shape we happen to observe today -- is a guess, and a
    guess is what corrupted the per-Game attribution in the first place.
    """
    payload = payload if payload is not None else _get("matrix")
    items = payload.get("items") or []
    if not items:
        raise AmbiguousMatrix("/matrix returned no teams")
    widths = {len(row["cells"]) for row in items}
    if len(widths) != 1:
        raise AmbiguousMatrix(f"/matrix rows disagree on cell count: {sorted(widths)}")
    width = widths.pop()

    published = payload.get("game_ids")
    if isinstance(published, list) and len(published) == width:
        ids = [int(g) for g in published]
    else:
        done = completed_games()
        if len(done) == width:
            ids = done
        else:
            raise AmbiguousMatrix(
                f"/matrix has {width} cells, no usable game_ids "
                f"({published!r}), and {len(done)} Games are completed -- refusing to guess"
            )

    if sorted(ids) != ids or len(set(ids)) != len(ids):
        raise AmbiguousMatrix(f"/matrix game_ids are not a strictly increasing set: {ids}")
    return ids


def matrix() -> dict[str, dict[int, float]]:
    """`{team_name: {game_id: net}}` -- keyed by Game id, never by position.

    The return type changed on purpose. A `list` invited `cells[game_id - 1]`, which is
    wrong whenever the published window does not start at Game 1; a `dict` keyed on the
    real Game id cannot be indexed wrongly, and a missing Game raises `KeyError` instead
    of returning some other Game's money.
    """
    payload = _get("matrix")
    ids = matrix_game_ids(payload)
    return {
        row["team_name"]: {gid: float(net) for gid, net in zip(ids, row["cells"])}
        for row in payload["items"]
    }


def published_net(team: str, game_id: int, table: dict[str, dict[int, float]] | None = None):
    """The leaderboard cell for one (team, Game), or `None` if it is not published.

    `None` is a real answer, not a failure: only the twenty most recent completed Games
    appear in `cells`, so older Games have no cell and must be checked against the identity.
    """
    table = table if table is not None else matrix()
    return table.get(team, {}).get(game_id)


# ---------------------------------------------------------------------- transactions


def _cache_path(team: str, game_id: int) -> Path:
    return CACHE / f"g{game_id:03d}_{team.replace(' ', '_')}.json"


def _read_cache(path: Path) -> tuple[list[dict] | None, str]:
    """`(rows, reason)`. `rows` is None when the file must not be trusted."""
    try:
        blob = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"unreadable ({exc.__class__.__name__})"
    if isinstance(blob, list):
        # Pre-v2: a bare row list with no `total` to check it against. Any of these could
        # have been written by a short read; there is no way to tell from the file alone.
        return None, f"unstamped legacy cache ({len(blob)} rows, no total)"
    if not isinstance(blob, dict) or blob.get("version") != CACHE_VERSION:
        return None, f"cache version {blob.get('version') if isinstance(blob, dict) else '?'}"
    rows = blob.get("rows")
    total = blob.get("total")
    if not isinstance(rows, list) or not isinstance(total, int):
        return None, "malformed cache entry"
    if len(rows) != total:
        return None, f"short read on disk: {len(rows)} rows, total says {total}"
    return rows, "ok"


def _write_cache(path: Path, team: str, game_id: int, rows: list[dict], total: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "team": team,
                "game_id": game_id,
                "total": total,
                "rows": rows,
            }
        )
    )


def remote_total(team: str, game_id: int) -> int:
    """How many rows the endpoint says exist. One cheap request (`page_size=1`)."""
    payload = _get("transactions", team=team, game_id=game_id, page=1, page_size=1)
    return int(payload["total"])


def fetch_transactions(team: str, game_id: int, page_size: int = PAGE_SIZE) -> tuple[list, int]:
    """Page to the end. Returns `(rows, total)` and raises `ShortRead` if they disagree."""
    rows: list[dict] = []
    page = 1
    total: int | None = None
    while True:
        payload = _get("transactions", team=team, game_id=game_id, page=page, page_size=page_size)
        rows.extend(payload["items"])
        total = payload.get("total", total)
        if page >= int(payload.get("total_pages", 1)):
            break
        page += 1
    if total is None:
        raise ShortRead(f"{team} g{game_id}: endpoint reported no total; cannot validate")
    if len(rows) != int(total):
        raise ShortRead(f"{team} g{game_id}: got {len(rows)} rows, endpoint said {total}")
    return rows, int(total)


def transactions(team: str, game_id: int, *, refresh: bool = False) -> list[dict]:
    """Every row for this team in this Game, across all pages, cached and validated.

    A cached file is used only when it carries the endpoint's `total` and its row count
    agrees with it. An unstamped (pre-v2) file is re-validated against the endpoint: if the
    row count matches the live `total` the file is simply re-stamped, otherwise it was a
    short read and is re-fetched in full. Either way a short read can never survive.
    """
    path = _cache_path(team, game_id)
    if not refresh and path.exists():
        rows, reason = _read_cache(path)
        if rows is not None:
            return rows
        if reason.startswith("unstamped legacy cache"):
            legacy = json.loads(path.read_text())
            total = remote_total(team, game_id)
            if len(legacy) == total:  # good read, just unlabelled -- adopt it
                _write_cache(path, team, game_id, legacy, total)
                return legacy
    rows, total = fetch_transactions(team, game_id)
    _write_cache(path, team, game_id, rows, total)
    return rows


def cache_status(team: str, game_id: int) -> str:
    """Why a cached file is or is not trusted, without touching the network."""
    path = _cache_path(team, game_id)
    if not path.exists():
        return "missing"
    return _read_cache(path)[1]


def line_item_count(rows: list[dict]) -> int:
    return max((row["line_item_index"] for row in rows), default=0)


def identity_net(rows: list[dict], team: str) -> float:
    """The authoritative net from the rows alone (docs: the payoff identity).

        net = sum(amount as issuer) - sum(amount if accepted else 1.5 * amount as reviewer)

    This never needs the leaderboard and cannot be misindexed, which is why `verify()` and
    `self_check()` fall back on it when a `/matrix` cell cannot be resolved.
    """
    income = sum(r["amount"] for r in rows if r["issuer"] == team)
    paid = sum(
        r["amount"] if r["accepted"] else 1.5 * r["amount"] for r in rows if r["reviewer"] == team
    )
    return income - paid


# ------------------------------------------------------------------------------- cli


def _parse_games(spec: str) -> list[int]:
    start, _, end = spec.partition("-")
    return list(range(int(start), int(end or start) + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", default="Bin busy")
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--refresh", action="store_true", help="ignore the cache and re-fetch")
    parser.add_argument(
        "--check-cache", action="store_true", help="report cache trust, no network at all"
    )
    parser.add_argument("--matrix", action="store_true", help="print the {game_id: net} mapping")
    parser.add_argument("--all-teams", action="store_true", help="every team, not just --team")
    args = parser.parse_args()

    if args.matrix:
        ids = matrix_game_ids()
        print(f"/matrix cells cover Games {ids[0]}-{ids[-1]} ({len(ids)} cells)")
        print(f"completed Games: {completed_games()}")
        table = matrix()
        for gid, net in sorted(table[args.team].items()):
            print(f"  G{gid:3d} {net:12.2f}")
        return

    game_ids = _parse_games(args.games)
    team_names = teams() if args.all_teams else [args.team]
    for game_id in game_ids:
        for team in team_names:
            if args.check_cache:
                print(f"G{game_id:3d} {team:24s} {cache_status(team, game_id)}")
                continue
            rows = transactions(team, game_id, refresh=args.refresh)
            print(
                f"G{game_id:3d} {team:24s} {len(rows):4d} rows, "
                f"{line_item_count(rows):2d} Line Items, net {identity_net(rows, team):11.2f}"
            )


if __name__ == "__main__":
    main()
