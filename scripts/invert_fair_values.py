"""Recover the secret Fair Value of every settled Line Item from public Transactions.

No model, no LLM, no guessing. The payoff table leaks `t` directly:

    rejected with amount > 0  ->  a wrongful rejection, so a <= t, and amount IS the Charge
    rejected with amount = 0  ->  a rightful rejection, so a > t
    accepted with amount = x  ->  x = min(a, c); says nothing about which side of t

Therefore, per Line Item:

    t >= max { a : a was wrongfully rejected }              (t_lo)
    t <  min { a : a was rightfully rejected, a known }     (t_hi)

A Charge that every reviewer accepted is payoff-invariant and carries no information
about `t` at all, which is why some items have no upper bound.

The reconstruction is checkable, and the check is the point: replaying

    net = sum(amount as issuer) - sum(amount if accepted else 1.5 * amount as reviewer)

reproduces the published leaderboard net for every team in every Game to the cent. Run
with --verify to assert it.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics as st

from pull_transactions import matrix, teams, transactions

INF = math.inf


def charges(game_id: int, team_names: list[str]) -> dict[tuple[int, str], float]:
    """The Charge each team submitted per Line Item, where it is recoverable.

    Recoverable from any row where the team is issuer and money moved: an accepted row
    pays min(a, c) and a wrongful rejection pays exactly a. A team rejected by all 16
    reviewers with nothing owed is unrecoverable -- and contributes 0 to every net, so
    it cannot be identified and does not need to be.
    """
    found: dict[tuple[int, str], float] = {}
    for team in team_names:
        for row in transactions(team, game_id):
            if row["issuer"] == team and row["amount"] > 0:
                found[(row["line_item_index"], team)] = row["amount"]
    return found


def brackets(game_id: int, team_names: list[str]) -> dict[int, tuple[float, float]]:
    known = charges(game_id, team_names)
    lo: dict[int, float] = collections.defaultdict(float)
    hi: dict[int, float] = collections.defaultdict(lambda: INF)
    for team in team_names:
        for row in transactions(team, game_id):
            index = row["line_item_index"]
            lo.setdefault(index, 0.0)
            hi.setdefault(index, INF)
            if row["accepted"]:
                continue
            if row["amount"] > 0:  # wrongful rejection: this Charge was at or below t
                lo[index] = max(lo[index], row["amount"])
            else:  # rightful rejection: this Charge was above t
                charge = known.get((index, row["issuer"]))
                if charge is not None:
                    hi[index] = min(hi[index], charge)
    return {index: (lo[index], hi[index]) for index in sorted(lo)}


def verify(game_id: int, team_names: list[str]) -> list[str]:
    """Reproduce every published net from the rows alone. Returns the failures."""
    published = matrix()
    failures = []
    for team in team_names:
        rows = transactions(team, game_id)
        income = sum(r["amount"] for r in rows if r["issuer"] == team)
        paid = sum(
            r["amount"] if r["accepted"] else 1.5 * r["amount"]
            for r in rows
            if r["reviewer"] == team
        )
        want = published[team][game_id - 1]
        if abs(income - paid - want) > 0.01:
            failures.append(f"{team} g{game_id}: got {income - paid:.2f}, published {want:.2f}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--json", help="write the brackets here")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    team_names = teams()

    out: dict[str, dict[int, list[float]]] = {}
    mids: list[float] = []
    for game_id in range(int(start), int(end or start) + 1):
        if args.verify:
            failures = verify(game_id, team_names)
            print(f"G{game_id:3d} verify: {'OK' if not failures else failures}")
        table = brackets(game_id, team_names)
        out[str(game_id)] = {k: [v[0], v[1] if v[1] != INF else None] for k, v in table.items()}
        bounded = [(lo + hi) / 2 for lo, hi in table.values() if hi != INF]
        mids += bounded
        shown = ", ".join(
            f"{k}:[{lo:.0f},{'inf' if hi == INF else f'{hi:.0f}'})" for k, (lo, hi) in table.items()
        )
        print(f"G{game_id:3d} ({len(table):2d} items) {shown}")

    if mids:
        mids.sort()
        def q(p: float) -> float:
            return mids[min(int(p * len(mids)), len(mids) - 1)]
        print(
            f"\nFair Value over {len(mids)} bounded Line Items: "
            f"p10={q(0.1):.0f} p25={q(0.25):.0f} median={st.median(mids):.0f} "
            f"p75={q(0.75):.0f} p90={q(0.9):.0f} max={max(mids):.0f}"
        )
    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=2)


if __name__ == "__main__":
    main()
