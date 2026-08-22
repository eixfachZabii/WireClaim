"""Per-(Game, team) darkness census, and when the Dark Window actually started.

Task: "confirm and date the regime change" -- identify per Game which teams are dark
(`a = 0` as Issuer and `b = 0` as Reviewer), plot the count of dark teams per Game, and
name the Game where it starts rising.

This is a *per-team* classification, distinct from `scripts/experiments/dark_signal.py`
(field-wide accept rate, already built tonight for a different question -- whether to
retune our own Charge/Limit for the dark window). Neither script edits the other.

Direct test (`dark_flag`)
--------------------------
A team is flagged dark in a Game if, over every row where it appears (own cached
Transactions -- one file per team per Game, already fetched):

    issuer_total  = sum(amount for rows where team is issuer)              == 0
    reviewer_paid = sum(amount for rows where team is reviewer & accepted) == 0

`issuer_total == 0` over dozens of rows (every Line Item x every other team) is not a
coincidence: a genuine Charge `a > 0` either gets accepted somewhere (pays `a`) or is
wrongfully rejected somewhere (still pays `a`, per `invert_fair_values`). The only way
every single row pays exactly 0 is `a = 0` on (essentially) every Line Item. Likewise
`reviewer_paid == 0` needs the team to never accept a positive Charge -- consistent with
`b = 0` (a strict-but-alive team with a small positive Limit would occasionally accept a
cheap item; a `b=0` team never does).

Cross-check (`identical_net_groups`)
-------------------------------------
CLAUDE.md's own clue: on Game 35, makalu/TBD/OPUSMOPUS all scored the *same* -55,267; on
Game 34, makalu/AsianSuperNerds both scored -50,380. A dark team's net is purely
`-1.5 * sum(fair Charges the awake field sent it)` -- independent of anything the dark team
itself does -- so if several dark teams face materially the same set of issuers charging
materially the same amounts, their nets coincide. This is corroboration, not the primary
test (it can under-fire if issuers customise Charge per reviewer), but it should agree with
`dark_flag` wherever both have something to say.

Usage
-----
    PYTHONPATH=. python scripts/experiments/dark_team_census.py --games 1-38
    PYTHONPATH=. python scripts/experiments/dark_team_census.py --games 1-38 --json var/experiments/dark_census.json
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pull_transactions import completed_games, teams, transactions  # noqa: E402
from rivals import changepoint  # noqa: E402


def dark_flag(team: str, game_id: int) -> tuple[bool, int]:
    """`(is_dark, n_rows)`. `n_rows == 0` means the team is simply not on record."""
    rows = transactions(team, game_id)
    if not rows:
        return False, 0
    issuer_total = sum(r["amount"] for r in rows if r["issuer"] == team)
    reviewer_paid = sum(r["amount"] for r in rows if r["reviewer"] == team and r["accepted"])
    return (issuer_total == 0.0 and reviewer_paid == 0.0), len(rows)


def identical_net_groups(game_id: int, team_names: list[str]) -> dict[float, list[str]]:
    from pull_transactions import identity_net

    groups: dict[float, list[str]] = collections.defaultdict(list)
    for team in team_names:
        rows = transactions(team, game_id)
        if not rows:
            continue
        net = round(identity_net(rows, team), 2)
        groups[net].append(team)
    return {net: members for net, members in groups.items() if len(members) >= 2}


def census(game_ids: list[int], team_names: list[str]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for gid in game_ids:
        dark_teams = []
        for team in team_names:
            is_dark, n = dark_flag(team, gid)
            if is_dark:
                dark_teams.append(team)
        groups = identical_net_groups(gid, team_names)
        # cross-check: does every team in a >=2 group of identical nets appear in dark_teams?
        corroborated = {net: members for net, members in groups.items() if all(m in dark_teams for m in members)}
        uncorroborated = {net: members for net, members in groups.items() if not all(m in dark_teams for m in members)}
        out[gid] = {
            "dark_teams": sorted(dark_teams),
            "dark_count": len(dark_teams),
            "identical_net_groups": groups,
            "corroborated_groups": corroborated,
            "uncorroborated_groups": uncorroborated,
        }
    return out


def _parse_games(spec: str) -> list[int]:
    done = set(completed_games())
    out: list[int] = []
    for chunk in spec.split(","):
        start, _, end = chunk.partition("-")
        out += list(range(int(start), int(end or start) + 1))
    return [g for g in sorted(set(out)) if g in done]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="all")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    team_names = teams()
    game_ids = _parse_games(args.games) if args.games != "all" else completed_games()

    result = census(game_ids, team_names)

    print(f"{'Game':>5} {'dark':>5} {'/16':>4}  dark teams")
    series: list[tuple[int, float]] = []
    for gid in game_ids:
        row = result[gid]
        series.append((gid, float(row["dark_count"])))
        names = ", ".join(row["dark_teams"])
        print(f"{gid:5d} {row['dark_count']:5d} {row['dark_count']:4d}  {names}")

    print("\nidentical-net corroboration (>=2 teams, same net, all independently flagged dark):")
    for gid in game_ids:
        row = result[gid]
        if row["corroborated_groups"]:
            for net, members in row["corroborated_groups"].items():
                print(f"  G{gid}: {members} all net {net:,.2f} -- all independently dark-flagged")
        if row["uncorroborated_groups"]:
            for net, members in row["uncorroborated_groups"].items():
                flagged = [m for m in members if m in row["dark_teams"]]
                not_flagged = [m for m in members if m not in row["dark_teams"]]
                print(
                    f"  G{gid}: {members} share net {net:,.2f} but NOT all dark-flagged "
                    f"(dark: {flagged}, not: {not_flagged}) -- coincidence or customised Charge"
                )

    gid, before, after, gap = changepoint(series)
    print(
        f"\nchangepoint (max separation, min_side=3): split at G{gid} -- "
        f"mean before {before:.2f}, mean after {after:.2f}, gap/spread {gap:.2f}"
    )
    print("  gap/spread > ~1 is a real break; below that treat the series as noisy but not broken.")

    # Also report simple rolling behaviour: first Game with dark_count >= 3, and the run of
    # Games from there to the end, to see whether it is a step or a ramp.
    threshold_hits = [gid for gid in game_ids if result[gid]["dark_count"] >= 3]
    if threshold_hits:
        print(f"\nfirst Game with >=3 simultaneously-dark teams: G{threshold_hits[0]}")
    counts = [result[gid]["dark_count"] for gid in game_ids]
    print(f"dark_count series: {counts}")

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            str(gid): {
                "dark_teams": row["dark_teams"],
                "dark_count": row["dark_count"],
                "identical_net_groups": {str(k): v for k, v in row["identical_net_groups"].items()},
            }
            for gid, row in result.items()
        }
        Path(args.json).write_text(json.dumps(serializable, indent=2))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
