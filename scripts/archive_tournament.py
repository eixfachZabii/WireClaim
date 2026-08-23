"""Freeze the finished tournament into `data/tournament/`, before the API goes away.

Why this exists
---------------
The competition endpoints are the only public record of what happened, and they will not
outlive the hackathon. Everything downstream of this repository -- the write-up, the
hypothesis ledger, any post-mortem measurement -- is derived from three facts that only
those endpoints hold:

1. the **final standings** (`/leaderboard/api/matrix`, field `total`), which is the
   cumulative net over all 100 Games and is the number we are actually ranked on;
2. the **per-Game net of every team**, which the endpoint publishes only for the trailing
   twenty Games (`cells`) but which is *exactly* recoverable for all 100 from the settled
   Transactions we already cache in `var/transactions/`; and
3. the **final-round weighting**, which is not in any handout we were given and was inferred
   -- Games 81-100 pay 3x. It is not an assumption here: it is the unique factor that makes
   (2) reproduce (1) to the cent for all seventeen teams simultaneously.

The archive is written as plain JSON and CSV, small enough to commit, and carries no Case
content -- only team names, Game ids and money, which is exactly what the public leaderboard
page already showed to anyone who loaded it. See CLAUDE.md rule 1a for what may not be
committed; none of it appears here.

The verification gate
---------------------
`reconstruct()` recomputes every team's cumulative net from the raw rows via the payoff
identity

    net(team, game) = sum(amount | issuer = team)
                    - sum(amount if accepted else 1.5 * amount | reviewer = team)

    total(team)     = sum over Games of weight(game) * net(team, game)

and refuses to write anything unless every team's total agrees with the published total to
within a cent. A mismatch means either the cache is short a page (see
`pull_transactions.ShortRead`) or the weighting is wrong, and in both cases the archive
would be a confident-looking lie. Exiting non-zero is the point.

Usage
-----
    PYTHONPATH=. python scripts/archive_tournament.py            # fetch, verify, write
    PYTHONPATH=. python scripts/archive_tournament.py --offline  # verify against the
                                                                 # archived matrix instead
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSACTIONS = ROOT / "var" / "transactions"
OUT = ROOT / "data" / "tournament"
MATRIX_URL = "https://c2f.public.quantco.cloud/leaderboard/api/matrix"

#: Games 81-100 pay triple. Inferred, then verified -- see the module docstring.
WEIGHTED_ROUNDS = frozenset(range(81, 101))
FINAL_ROUND_WEIGHT = 3.0

US = "Bin busy"
CENT = 0.011


def weight(game_id: int) -> float:
    return FINAL_ROUND_WEIGHT if game_id in WEIGHTED_ROUNDS else 1.0


# ------------------------------------------------------------------------------ inputs


def fetch_matrix() -> dict:
    """The live leaderboard. `curl` rather than `urllib` to match `pull_transactions`."""
    proc = subprocess.run(
        ["curl", "-s", "-m", "30", MATRIX_URL], capture_output=True, text=True, check=False
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"could not fetch {MATRIX_URL}: rc={proc.returncode}")
    return json.loads(proc.stdout)


def load_rows() -> dict[tuple[int, str, str, int], tuple[bool, float]]:
    """Every settled Transaction, deduplicated across the seventeen per-team caches.

    Each team's file holds only the rows it appears in, so the same (Game, issuer, reviewer,
    Line Item) arrives twice -- once from the issuer's file and once from the reviewer's.
    Keying on that tuple collapses the duplicate; it is not a heuristic, the four fields are
    the primary key of the fixture list.
    """
    if not TRANSACTIONS.is_dir():
        raise SystemExit(f"no transaction cache at {TRANSACTIONS}; run scripts/pull_transactions.py")
    rows: dict[tuple[int, str, str, int], tuple[bool, float]] = {}
    files = sorted(TRANSACTIONS.glob("g*.json"))
    for path in files:
        blob = json.loads(path.read_text())
        total = blob.get("total")
        if total is None or len(blob.get("rows", [])) != total:
            raise SystemExit(
                f"{path.name} is a short read ({len(blob.get('rows', []))} of {total}); "
                "re-run scripts/pull_transactions.py before archiving"
            )
        game_id = int(blob["game_id"])
        for row in blob["rows"]:
            key = (game_id, row["issuer"], row["reviewer"], int(row["line_item_index"]))
            rows[key] = (bool(row["accepted"]), float(row["amount"]))
    if not rows:
        raise SystemExit("transaction cache is empty")
    return rows


# ---------------------------------------------------------------------- reconstruction


def reconstruct(rows) -> tuple[dict[str, dict[int, float]], dict[int, int]]:
    """`{team: {game: unweighted net}}` plus `{game: line item count}`."""
    per_game: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    items: dict[int, set[int]] = defaultdict(set)
    teams: set[str] = set()
    for (game_id, issuer, reviewer, index), (accepted, amount) in rows.items():
        per_game[issuer][game_id] += amount
        per_game[reviewer][game_id] -= amount if accepted else 1.5 * amount
        items[game_id].add(index)
        teams.update((issuer, reviewer))
    games = sorted(items)
    # A team with no row in a Game still has a net there: zero. Materialise it so every
    # downstream consumer can index the table without a `.get` and a silent default.
    table = {
        team: {game: round(per_game[team].get(game, 0.0), 6) for game in games} for team in teams
    }
    return table, {game: len(indexes) for game, indexes in items.items()}


def verify(table: dict[str, dict[int, float]], published: dict[str, float]) -> list[str]:
    """Names every team whose reconstructed total disagrees with the leaderboard."""
    failures = []
    for team, total in published.items():
        got = sum(net * weight(game) for game, net in table.get(team, {}).items())
        if abs(got - total) > CENT:
            failures.append(f"{team}: reconstructed {got:,.2f} vs published {total:,.2f}")
    missing = sorted(set(table) - set(published))
    failures.extend(f"{team}: in the rows but not on the leaderboard" for team in missing)
    return failures


# ----------------------------------------------------------------------------- outputs


def write(table, line_items, payload, published) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    games = sorted(line_items)
    order = sorted(published, key=lambda t: -published[t])

    (OUT / "matrix_raw.json").write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")

    standings = [
        {
            "rank": rank,
            "team": team,
            "total": round(published[team], 2),
            "unweighted_total": round(sum(table[team].values()), 2),
            "games_1_80": round(sum(v for g, v in table[team].items() if g <= 80), 2),
            "games_81_100_unweighted": round(
                sum(v for g, v in table[team].items() if g >= 81), 2
            ),
        }
        for rank, team in enumerate(order, start=1)
    ]
    (OUT / "final_standings.json").write_text(
        json.dumps(
            {
                "teams": len(order),
                "games": len(games),
                "weighted_rounds": sorted(WEIGHTED_ROUNDS),
                "final_round_weight": FINAL_ROUND_WEIGHT,
                "verified": "every total reproduces the published leaderboard to the cent",
                "standings": standings,
            },
            indent=1,
        )
        + "\n"
    )

    with (OUT / "per_game_net.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["game_id", "line_items", "weight"] + order)
        for game in games:
            writer.writerow(
                [game, line_items[game], weight(game)]
                + [f"{table[team][game]:.4f}" for team in order]
            )

    with (OUT / "standings.md").open("w") as handle:
        handle.write("# Final standings -- Claim to Fame, 100 Games\n\n")
        handle.write(
            "Reconstructed from every settled Transaction and verified against the published\n"
            "leaderboard total to the cent, for all seventeen teams. Games 81-100 pay 3x.\n\n"
        )
        handle.write("| # | team | final net | unweighted | Games 1-80 | Games 81-100 (1x) |\n")
        handle.write("| ---: | --- | ---: | ---: | ---: | ---: |\n")
        for row in standings:
            mark = " **(us)**" if row["team"] == US else ""
            handle.write(
                f"| {row['rank']} | {row['team']}{mark} | {row['total']:,.2f} | "
                f"{row['unweighted_total']:,.2f} | {row['games_1_80']:,.2f} | "
                f"{row['games_81_100_unweighted']:,.2f} |\n"
            )
    print(f"wrote {OUT}/{{matrix_raw.json,final_standings.json,per_game_net.csv,standings.md}}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="verify against the archived matrix instead of fetching a fresh one",
    )
    args = parser.parse_args()

    if args.offline:
        archived = OUT / "matrix_raw.json"
        if not archived.exists():
            raise SystemExit(f"--offline needs {archived}, which does not exist yet")
        payload = json.loads(archived.read_text())
    else:
        payload = fetch_matrix()

    published = {row["team_name"]: float(row["total"]) for row in payload["items"]}
    table, line_items = reconstruct(load_rows())

    failures = verify(table, published)
    if failures:
        print("ARCHIVE REFUSED -- the reconstruction does not reproduce the leaderboard:")
        for line in failures:
            print(f"  {line}")
        sys.exit(1)

    print(f"verified {len(published)} teams over {len(line_items)} Games, exact to the cent")
    write(table, line_items, payload, published)


if __name__ == "__main__":
    main()
