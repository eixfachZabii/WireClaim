"""A live darkness signal computable from the public leaderboard (item 4 of the task).

The naive signal -- "how many issuers Charged something nonzero this Game" -- is broken:
Games 21, 22 and 28 all read as ~0 active issuers, and none of the three is a dark Field.
Reading the Cases: item counts were 2, 1 and 10 respectively and every recovered `t_lo` in
those Games is 0 -- the Case itself was (almost) worthless, so *rational awake issuers*
correctly Charge nothing. Issuer count conflates "nobody wants this item" with "nobody is
home", because both produce the same zero.

The fix: condition on a Charge being attempted at all, and measure whether the *Reviewer*
side says yes.

    field_accept_rate(game) = (accepted rows where the issuer's recovered Charge is a known
                                positive number) / (all such rows)

A rightful rejection always pays `amount = 0` in the row, so its own `amount` field cannot
tell you what was Charged -- that is why this reuses `invert_fair_values.charges()` (the
already-verified Charge-recovery primitive) to know *which* rows carry a real, positive,
recoverable Charge before asking whether they were accepted. Rows about a Charge of exactly
0 (rational on an uncovered item, trivially "accepted" since 0 <= any Limit) are excluded on
both sides of the ratio, exactly as `rivals.py`'s `per_game_accept` already does for the
same reason.

Why this separates the two explanations the naive count cannot:
  * dark Field:      every positive Charge is Rejected -> accept_rate -> 0, with support
                      (denominator > 0) as long as *any* team anywhere Charged anything --
                      it does not need to be *our* Charge, since this reads the whole public
                      leaderboard, not just our own rows.
  * worthless Case:   nobody Charges anything positive at all -> denominator -> 0 ->
                      reported as "no signal", never silently read as 0% accept.

So low-denominator Games (21, 22, 28) come back `n/a`, not `dark`, while a genuinely dark
Game reports a real, near-zero accept_rate with real support behind it.

Usage
-----
    PYTHONPATH=. python scripts/experiments/dark_signal.py --games 1-33
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from invert_fair_values import charges as recover_charges  # noqa: E402
from pull_transactions import completed_games, teams, transactions  # noqa: E402


def field_signal(game_id: int, team_names: list[str]) -> dict:
    """One Game's darkness signal, plus the naive count for comparison."""
    known = recover_charges(game_id, team_names)  # {(index, issuer): charge}
    naive_active_issuers = len({team for (_, team) in known})

    accepted = 0
    total = 0
    seen_rows: set[tuple[int, str, str]] = set()  # (index, issuer, reviewer) dedupe
    for team in team_names:
        for row in transactions(team, game_id):
            key = (row["line_item_index"], row["issuer"], row["reviewer"])
            if key in seen_rows:
                continue
            seen_rows.add(key)
            charge = known.get((row["line_item_index"], row["issuer"]))
            if charge is None or charge <= 0:
                continue  # unrecoverable or a legitimate 0 -- not an attempted Charge
            total += 1
            if row["accepted"]:
                accepted += 1

    accept_rate = (accepted / total) if total else None
    return {
        "game_id": game_id,
        "naive_active_issuers": naive_active_issuers,
        "priced_rows": total,
        "accepted": accepted,
        "accept_rate": accept_rate,
    }


def _parse_games(spec: str) -> list[int]:
    if spec == "all":
        return completed_games()
    start, _, end = spec.partition("-")
    return list(range(int(start), int(end or start) + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="all")
    args = parser.parse_args()

    team_names = teams()
    game_ids = [g for g in _parse_games(args.games) if g in completed_games()]

    print(f"{'Game':>5} {'naive issuers':>14} {'priced rows':>12} {'accepted':>9} {'accept rate':>12}")
    rates = []
    for game_id in game_ids:
        s = field_signal(game_id, team_names)
        rate_str = f"{s['accept_rate']:.1%}" if s["accept_rate"] is not None else "n/a"
        flag = "  <-- naive reads 0 but this Game is NOT dark (worthless Case)" if (
            s["naive_active_issuers"] == 0 and s["priced_rows"] == 0
        ) else ""
        print(
            f"{game_id:5d} {s['naive_active_issuers']:14d} {s['priced_rows']:12d} "
            f"{s['accepted']:9d} {rate_str:>12}{flag}"
        )
        if s["accept_rate"] is not None:
            rates.append(s["accept_rate"])

    if rates:
        rates.sort()
        n = len(rates)
        median = rates[n // 2] if n % 2 else (rates[n // 2 - 1] + rates[n // 2]) / 2
        print(
            f"\naccept_rate over {n} Games with support: "
            f"min={min(rates):.1%} p25={rates[n // 4]:.1%} median={median:.1%} "
            f"p75={rates[3 * n // 4]:.1%} max={max(rates):.1%}"
        )


if __name__ == "__main__":
    main()
