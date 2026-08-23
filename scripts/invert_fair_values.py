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

That identity is **authoritative**: it needs nothing but the rows, so it cannot be thrown
off by how the leaderboard chooses to lay out its `cells` array. The leaderboard cell is
merely a cross-check, and a fallible one -- `/matrix` publishes only a trailing window of
the twenty most recently completed Games (see `pull_transactions.matrix`), so for older
Games there is no cell to compare against at all. `verify()` reports that state explicitly
rather than comparing against whatever number happens to sit at index `game_id - 1`.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics as st

from pull_transactions import (
    AmbiguousMatrix,
    completed_games,
    identity_net,
    cell_agrees,
    matrix,
    teams,
    transactions,
)

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


def verify(
    game_id: int,
    team_names: list[str],
    table: dict[str, dict[int, float]] | None = None,
) -> list[str]:
    """Reproduce every published net from the rows alone. Returns the failures.

    The comparison is against the `/matrix` cell **for this Game id**, resolved by
    `pull_transactions.matrix()`. Two states are not failures and are reported as such by
    `verify_status()` instead: the Game has no published cell (it fell out of the trailing
    twenty-Game window), or the mapping could not be established at all. In both cases the
    identity above is taken as the truth, because it is derived from the rows and has
    nothing to be misindexed by.
    """
    published = table
    if published is None:
        try:
            published = matrix()
        except (AmbiguousMatrix, RuntimeError):
            published = None
    failures = []
    for team in team_names:
        got = identity_net(transactions(team, game_id), team)
        want = None if published is None else published.get(team, {}).get(game_id)
        if want is not None and not cell_agrees(got, want):
            failures.append(f"{team} g{game_id}: got {got:.2f}, published {want:.2f}")
    return failures


def verify_status(
    game_id: int,
    team_names: list[str],
    table: dict[str, dict[int, float]] | None = None,
) -> tuple[str, list[str]]:
    """`(status, failures)` where status is one of `ok`, `mismatch`, `no-cell`, `no-matrix`.

    `ok` means every team's identity net equals its published cell for this Game -- the only
    state in which a per-Game number is safe to score against. `mismatch` is loud on
    purpose: it means the rows and the leaderboard disagree, so something upstream (a short
    read, a voided Game, a settlement we do not model) is wrong and the Game is unusable.
    """
    published = table
    if published is None:
        try:
            published = matrix()
        except (AmbiguousMatrix, RuntimeError):
            return "no-matrix", []
    if not any(game_id in cells for cells in published.values()):
        return "no-cell", []
    failures = verify(game_id, team_names, published)
    return ("ok" if not failures else "mismatch"), failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--games", default="all", help="e.g. 1-14, 16, or 'all' for every completed Game"
    )
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--json", help="write the brackets here")
    args = parser.parse_args()
    team_names = teams()
    if args.games == "all":
        game_ids = completed_games()
    else:
        start, _, end = args.games.partition("-")
        game_ids = list(range(int(start), int(end or start) + 1))

    cells = None
    if args.verify:
        try:
            cells = matrix()
        except (AmbiguousMatrix, RuntimeError) as exc:
            print(f"WARNING: /matrix unusable ({exc}); the identity is the only truth available")

    out: dict[str, dict[int, list[float]]] = {}
    mids: list[float] = []
    statuses: dict[int, str] = {}
    for game_id in game_ids:
        if args.verify:
            status, failures = verify_status(game_id, team_names, cells)
            statuses[game_id] = status
            note = {
                "ok": "OK (all 17 nets reproduced to the cent)",
                "no-cell": "no published cell -- outside the 20-Game /matrix window",
                "no-matrix": "/matrix unusable -- identity taken as truth",
            }.get(status, f"MISMATCH {failures}")
            print(f"G{game_id:3d} verify: {note}")
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
    if statuses:
        by_status: dict[str, list[int]] = collections.defaultdict(list)
        for game_id, status in statuses.items():
            by_status[status].append(game_id)
        print("\nverify summary")
        for status in ("ok", "no-cell", "no-matrix", "mismatch"):
            if by_status[status]:
                print(f"  {status:9s} {by_status[status]}")
        if by_status["mismatch"]:
            print("  ^ these Games are UNUSABLE: do not score against them")
    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=2)


if __name__ == "__main__":
    main()
