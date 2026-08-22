"""Independent verification of the "fair vs Overcharge income" split (dark-regime-charge task, item 1).

Claim being checked (not our code, someone else's finding handed to us):

    Split each team's Issuer income, per settled Game, by whether the money-moving row's
    Charge sat at or below the item's `t_lo` ("fair", provably `a <= t`) or at or above the
    item's `t_hi` ("Overcharge accepted by a loose Reviewer", provably `a > t`). Every row
    that moved money is either a wrongful rejection (proves `a <= t`, so `a <= t_lo` by
    construction of `t_lo = max` over such rows) or an accepted row. An accepted row is only
    classifiable if the item's `t_hi` (from some *other* rightful rejection on the same item)
    is known and `a >= t_hi`; otherwise it is ambiguous and excluded from both buckets.

This script does NOT import `scripts/rivals.py` (whose split logic we were not shown) or
reuse anyone else's aggregation. It imports only the two primitives that are already
verified against the leaderboard to the cent:

    invert_fair_values.brackets(game_id, teams)   -- t_lo/t_hi per Line Item
    pull_transactions.transactions(team, game_id) -- the raw rows

and does its own classification and summation, row by row.

Usage:
    PYTHONPATH=. python scripts/experiments/dark_income_split.py --games 19-32
    PYTHONPATH=. python scripts/experiments/dark_income_split.py --games all
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from invert_fair_values import brackets  # noqa: E402
from pull_transactions import completed_games, teams, transactions  # noqa: E402

INF = float("inf")


def split_income(game_ids: list[int], team_names: list[str]) -> dict[str, dict[str, float]]:
    """`{team: {"fair": eur, "over": eur, "ambiguous": eur, "games": n}}`.

    "fair"      : money-moving row where the item's bracket proves `a <= t` (`a <= t_lo`).
    "over"      : money-moving row where the item's bracket proves `a > t`  (`a >= t_hi`).
    "ambiguous" : money-moving row that lands strictly inside `(t_lo, t_hi)`, or where
                  `t_hi` is unknown (unanimous accept, no rightful rejection anywhere to
                  bound it). Excluded from the two buckets above, reported separately so
                  it is visible rather than silently dropped.
    """
    out: dict[str, dict[str, float]] = collections.defaultdict(
        lambda: {"fair": 0.0, "over": 0.0, "ambiguous": 0.0, "games": 0}
    )
    games_touched: dict[str, set[int]] = collections.defaultdict(set)

    for game_id in game_ids:
        item_bracket = brackets(game_id, team_names)
        for team in team_names:
            rows = transactions(team, game_id)
            for row in rows:
                if row["issuer"] != team or row["amount"] <= 0:
                    continue
                index = row["line_item_index"]
                amount = row["amount"]
                lo, hi = item_bracket.get(index, (0.0, INF))
                if amount <= lo:
                    out[team]["fair"] += amount
                elif hi != INF and amount >= hi:
                    out[team]["over"] += amount
                else:
                    out[team]["ambiguous"] += amount
                games_touched[team].add(game_id)

    for team in out:
        out[team]["games"] = len(games_touched[team])
    return out


def print_report(title: str, split: dict[str, dict[str, float]], top_n: int = 10) -> None:
    print(f"\n=== {title} ===")
    ranked = sorted(split.items(), key=lambda kv: kv[1]["fair"] + kv[1]["over"] + kv[1]["ambiguous"], reverse=True)
    header = f"{'team':22s} {'fair EUR':>12s} {'fair %':>7s} {'over EUR':>12s} {'over %':>7s} {'ambig EUR':>10s} {'total':>12s}"
    print(header)
    for team, d in ranked[:top_n]:
        total = d["fair"] + d["over"] + d["ambiguous"]
        classified = d["fair"] + d["over"]
        fair_pct = 100.0 * d["fair"] / classified if classified else float("nan")
        over_pct = 100.0 * d["over"] / classified if classified else float("nan")
        print(
            f"{team:22s} {d['fair']:12,.0f} {fair_pct:6.1f}% {d['over']:12,.0f} {over_pct:6.1f}% "
            f"{d['ambiguous']:10,.0f} {total:12,.0f}"
        )
    total_ambig = sum(d["ambiguous"] for d in split.values())
    total_all = sum(d["fair"] + d["over"] + d["ambiguous"] for d in split.values())
    print(f"\n  ambiguous income across all teams: {total_ambig:,.0f} of {total_all:,.0f} total "
          f"({100.0 * total_ambig / total_all:.2f}% if total_all else 0)")


def _parse_games(spec: str) -> list[int]:
    if spec == "all":
        return completed_games()
    start, _, end = spec.partition("-")
    return list(range(int(start), int(end or start) + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="19-32")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    team_names = teams()
    game_ids = [g for g in _parse_games(args.games) if g in completed_games()]
    print(f"Games: {game_ids} ({len(game_ids)})")

    split = split_income(game_ids, team_names)
    print_report(f"fair vs Overcharge income, Games {args.games}", split, top_n=args.top)

    # Also report per-Game fair income for the leaders named in the task, since that is the
    # number the dark-field argument hinges on.
    named = ["Bin busy", "eyay", "error404 ai", "TakeTheMoneyAndRun"]
    print("\nper-Game fair income (named teams):")
    for team in named:
        d = split.get(team)
        if not d:
            continue
        per_game = d["fair"] / d["games"] if d["games"] else float("nan")
        print(f"  {team:22s} fair {d['fair']:12,.0f}  games {d['games']:3d}  fair/Game {per_game:9,.0f}")


if __name__ == "__main__":
    main()
