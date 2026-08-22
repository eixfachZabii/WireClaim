"""The exact four-bucket decomposition of our net, per Game, verified to the cent.

    (i)   Issuer income from fair Charges          (a <= t, whatever the reviewer did)
    (ii)  Issuer income from accepted Overcharges   (a >  t, accepted by a generous Limit)
    (iii) Reviewer cost from accepted claims        (their a <= our b, whatever the truth)
    (iv)  Reviewer cost from 1.5x wrongful rejection (their a <= t, we rejected it anyway)

This is a *classification* of the identity net, not a new measurement: every euro that
moves in a settled Game is already in `pull_transactions.transactions()`, and
`pull_transactions.identity_net()` is

    net = sum(amount as issuer) - sum(amount if accepted else 1.5 * amount as reviewer)

which is exactly (i)+(ii) - (iii)-(iv) once (i)/(ii) split "amount as issuer" by whether
that issuer's own Charge sat at or below the Fair Value, and (iii)/(iv) split "amount as
reviewer" by the `accepted` flag alone (no Fair Value needed there -- 1.5x is exactly the
wrongful-rejection definition). So this script cannot help but reconcile to the cent; it is
checked anyway, every Game, because a silent reconciliation failure is worse than a loud one.

The only judgement call is which point of the Fair Value bracket to test `a` against for
the (i)/(ii) split, on items whose bracket is unbounded above (`t_hi = inf`). We use
`GameSnapshot.fair_point` -- the same convention `replay_payoffs.py` uses everywhere else,
so this bucketing is consistent with every other number in this repo rather than a new
convention invented for this report.

    PYTHONPATH=. pixi run python scripts/leak_buckets.py --games 1-32
    PYTHONPATH=. pixi run python scripts/leak_buckets.py --games 1-32 --json var/leak/buckets.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pull_transactions import transactions  # noqa: E402
from replay_payoffs import US, UnreconstructableGame, snapshot  # noqa: E402


def decompose(game_id: int, us: str = US) -> dict:
    snap = snapshot(game_id, us)
    rows = transactions(us, game_id)

    fair_income = 0.0
    overcharge_income = 0.0
    accepted_cost = 0.0
    penalty_cost = 0.0

    for row in rows:
        index = row["line_item_index"]
        t = snap.fair_point(index)
        if row["issuer"] == us:
            amount = row["amount"]
            if amount <= 0:
                continue
            if amount <= t:
                fair_income += amount
            else:
                overcharge_income += amount
        if row["reviewer"] == us:
            amount = row["amount"]
            if row["accepted"]:
                accepted_cost += amount
            elif amount > 0:  # wrongful rejection: 1.5x the Charge we should have paid
                penalty_cost += 1.5 * amount
            # rightful rejection (amount == 0, rejected): costs nothing, contributes to none

    net = fair_income + overcharge_income - accepted_cost - penalty_cost
    identity = _identity_net(rows, us)
    return {
        "game_id": game_id,
        "fair_income": round(fair_income, 2),
        "overcharge_income": round(overcharge_income, 2),
        "accepted_cost": round(accepted_cost, 2),
        "penalty_cost": round(penalty_cost, 2),
        "net": round(net, 2),
        "identity_net": round(identity, 2),
        "reconciled": abs(net - identity) <= 0.01,
        "authoritative_net": round(snap.published_net, 2),
        "line_items": len(snap.line_items),
    }


def _identity_net(rows: list[dict], team: str) -> float:
    income = sum(r["amount"] for r in rows if r["issuer"] == team)
    paid = sum(
        r["amount"] if r["accepted"] else 1.5 * r["amount"] for r in rows if r["reviewer"] == team
    )
    return income - paid


def _parse_games(spec: str) -> list[int]:
    start, _, end = spec.partition("-")
    return list(range(int(start), int(end or start) + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-32")
    parser.add_argument("--team", default=US)
    parser.add_argument("--json", help="write the per-Game rows here")
    args = parser.parse_args()

    rows = []
    totals = {"fair_income": 0.0, "overcharge_income": 0.0, "accepted_cost": 0.0, "penalty_cost": 0.0, "net": 0.0}
    bad = []
    print(
        f"{'Game':>4} {'items':>5} {'fair_inc':>11} {'over_inc':>10} {'accept_cost':>12} "
        f"{'penalty':>11} {'net':>12} {'authoritative':>13} {'ok':>4}"
    )
    for game_id in _parse_games(args.games):
        try:
            row = decompose(game_id, args.team)
        except UnreconstructableGame as exc:
            print(f"G{game_id:3d}  UNRECONSTRUCTABLE: {exc}")
            bad.append(game_id)
            continue
        rows.append(row)
        for key in totals:
            totals[key] += row[key] if key != "net" else row["net"]
        ok = "OK" if row["reconciled"] and abs(row["net"] - row["authoritative_net"]) <= 0.01 else "FAIL"
        if ok == "FAIL":
            bad.append(game_id)
        print(
            f"G{game_id:3d} {row['line_items']:5d} {row['fair_income']:11,.2f} "
            f"{row['overcharge_income']:10,.2f} {row['accepted_cost']:12,.2f} "
            f"{row['penalty_cost']:11,.2f} {row['net']:12,.2f} {row['authoritative_net']:13,.2f} {ok:>4}"
        )

    print(
        f"\n{'TOTAL':>4} {'':>5} {totals['fair_income']:11,.2f} {totals['overcharge_income']:10,.2f} "
        f"{totals['accepted_cost']:12,.2f} {totals['penalty_cost']:11,.2f} {totals['net']:12,.2f}"
    )
    print(f"\nGames reconciled to the cent: {len(rows) - len([g for g in bad if g in [r['game_id'] for r in rows]])}/{len(rows)}")
    if bad:
        print(f"Games needing attention: {bad}")

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
