"""Where the 100 Games went: a money decomposition, not a narrative.

The leaderboard says we finished fifth on +238,255.07. That single number hides the only
thing worth knowing, which is *which of the four payoff branches* the money came out of.
Every euro that moved in this tournament sits in exactly one of them (docs/GAME-AND-PROOFS.md):

    as Issuer, a <= t        income      we were paid `a` by all sixteen, whoever accepted
    as Issuer, a >  t        income      we were paid `a` only by whoever accepted anyway
    as Reviewer, a <= t, b >= a   cost    we paid `a`      -- correct, unavoidable
    as Reviewer, a <= t, b <  a   cost    we paid `1.5a`   -- the lawyer; the 0.5a is waste
    as Reviewer, a >  t, b >= a   cost    we paid `a`      -- fraud let through; all waste
    as Reviewer, a >  t, b <  a   cost    we paid nothing  -- correct

`t` is not observed, but it is *bracketed* exactly by `invert_fair_values.brackets()`, and
the bracket is enough to classify almost every row: a Charge below `t_lo` is provably fair,
one at or above `t_hi` is provably an Overcharge. Rows landing inside the open interval are
counted separately and never silently folded into either side -- they are the honest measure
of how much of this decomposition the public record cannot resolve.

Three numbers come out that no per-Game net can show:

* **lawyer waste** -- the `0.5a` surcharge we paid for rejecting claims that were fair.
  Pure loss, caused entirely by our Limit sitting too low.
* **fraud let through** -- what we paid on Charges above the Fair Value. Pure loss, caused
  entirely by our Limit sitting too high.
* **forfeited income** -- what we would have been paid had we Charged just under `t` instead
  of what we did Charge, on the items where we overshot. Caused entirely by the estimate.

Those three are the whole structural surface of the strategy. Everything else is arithmetic.

Usage
-----
    PYTHONPATH=. python scripts/postmortem.py                 # all 100 Games
    PYTHONPATH=. python scripts/postmortem.py --games 1-80
    PYTHONPATH=. python scripts/postmortem.py --json var/postmortem.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from invert_fair_values import brackets  # noqa: E402
from pull_transactions import teams, transactions  # noqa: E402

INF = math.inf
US = "Bin busy"
WEIGHTED_ROUNDS = frozenset(range(81, 101))


def weight(game_id: int) -> float:
    return 3.0 if game_id in WEIGHTED_ROUNDS else 1.0


@dataclass
class Bucket:
    """One payoff branch, counted and totalled."""

    rows: int = 0
    money: float = 0.0

    def add(self, amount: float) -> None:
        self.rows += 1
        self.money += amount


@dataclass
class Decomposition:
    """The whole tournament, split by branch. Money is *unweighted* unless noted."""

    income_fair: Bucket = field(default_factory=Bucket)
    income_over: Bucket = field(default_factory=Bucket)
    income_unknown: Bucket = field(default_factory=Bucket)
    paid_fair: Bucket = field(default_factory=Bucket)
    paid_lawyer: Bucket = field(default_factory=Bucket)  # the whole 1.5a
    paid_fraud: Bucket = field(default_factory=Bucket)
    paid_unknown: Bucket = field(default_factory=Bucket)
    rejected_right: Bucket = field(default_factory=Bucket)
    #: `0.5a` of every `paid_lawyer` row -- the part that is pure penalty.
    lawyer_surcharge: float = 0.0
    #: What we forfeited by Charging above `t` -- `t_lo` per opponent, the safe lower bound.
    forfeited: float = 0.0
    forfeited_items: int = 0

    def net(self) -> float:
        income = self.income_fair.money + self.income_over.money + self.income_unknown.money
        cost = (
            self.paid_fair.money
            + self.paid_lawyer.money
            + self.paid_fraud.money
            + self.paid_unknown.money
        )
        return income - cost


def classify(charge: float, low: float, high: float) -> str:
    """`"fair"`, `"over"` or `"unknown"` for one Charge against a Fair Value bracket."""
    if charge <= low:
        return "fair"
    if high != INF and charge >= high:
        return "over"
    return "unknown"


def our_charges(rows: list[dict], us: str) -> dict[int, float]:
    """Our Charge per Line Item, recovered from the rows that moved money.

    An accepted row pays `min(a, c)` and a wrongfully rejected row pays exactly `a`; with the
    Cap unobserved in 52k rows both are `a`. A Line Item where nothing moved and somebody
    accepted means we Charged zero. Where every reviewer rejected and nothing moved the
    Charge is above every Limit in the Field and is not recoverable -- omitted, not guessed.
    """
    seen: dict[int, float] = {}
    zero: set[int] = set()
    for row in rows:
        if row["issuer"] != us:
            continue
        index = int(row["line_item_index"])
        if row["amount"] > 0:
            seen[index] = float(row["amount"])
        elif row["accepted"]:
            zero.add(index)
    for index in zero:
        seen.setdefault(index, 0.0)
    return seen


def decompose(game_ids: list[int], us: str = US) -> tuple[Decomposition, dict[int, dict]]:
    total = Decomposition()
    names = teams()
    per_game: dict[int, dict] = {}

    for game_id in game_ids:
        rows = transactions(us, game_id)
        try:
            bounds = brackets(game_id, names)
        except Exception as exc:  # pragma: no cover - a Game we cannot bracket is skipped loudly
            print(f"  G{game_id}: no Fair Value brackets ({type(exc).__name__}: {exc})")
            continue

        game = Decomposition()
        ours = our_charges(rows, us)

        for row in rows:
            index = int(row["line_item_index"])
            amount = float(row["amount"])
            low, high = bounds.get(index, (0.0, INF))

            if row["issuer"] == us and row["reviewer"] != us:
                kind = classify(amount, low, high)
                {"fair": game.income_fair, "over": game.income_over}.get(
                    kind, game.income_unknown
                ).add(amount)

            elif row["reviewer"] == us and row["issuer"] != us:
                if amount == 0.0:
                    # Nothing moved: either an Overcharge we rightly rejected, or a Charge of
                    # zero. Both are free; counted for the accept-rate denominator only.
                    game.rejected_right.add(0.0)
                    continue
                kind = classify(amount, low, high)
                if not row["accepted"]:
                    # Money moving on a rejected row *is* the wrongful-rejection branch: it
                    # only happens when `a <= t`. The bracket cannot contradict that, so this
                    # is the one classification the record makes for us.
                    game.paid_lawyer.add(1.5 * amount)
                    game.lawyer_surcharge += 0.5 * amount
                elif kind == "over":
                    game.paid_fraud.add(amount)
                elif kind == "fair":
                    game.paid_fair.add(amount)
                else:
                    game.paid_unknown.add(amount)

        # Forfeited income: on a Line Item we Charged above the *proven* floor `t_lo`, every
        # one of the sixteen would have paid `t_lo` had we Charged it. `t_lo` is a lower
        # bound on `t`, so this is a lower bound on what the overshoot cost.
        opponents = len(names) - 1
        for index, charge in ours.items():
            low, high = bounds.get(index, (0.0, INF))
            if high != INF and charge >= high and low > 0:
                earned = sum(
                    float(r["amount"])
                    for r in rows
                    if r["issuer"] == us and int(r["line_item_index"]) == index
                )
                game.forfeited += max(low * opponents - earned, 0.0)
                game.forfeited_items += 1

        for name in (
            "income_fair", "income_over", "income_unknown", "paid_fair", "paid_lawyer",
            "paid_fraud", "paid_unknown", "rejected_right",
        ):
            bucket = getattr(total, name)
            other = getattr(game, name)
            bucket.rows += other.rows
            bucket.money += other.money
        total.lawyer_surcharge += game.lawyer_surcharge
        total.forfeited += game.forfeited
        total.forfeited_items += game.forfeited_items
        per_game[game_id] = {
            "net": round(game.net(), 2),
            "weighted_net": round(game.net() * weight(game_id), 2),
            "income": round(
                game.income_fair.money + game.income_over.money + game.income_unknown.money, 2
            ),
            "lawyer_surcharge": round(game.lawyer_surcharge, 2),
            "fraud_let_through": round(game.paid_fraud.money, 2),
            "forfeited": round(game.forfeited, 2),
            "line_items": len(ours),
        }

    return total, per_game


def report(total: Decomposition, per_game: dict[int, dict], game_ids: list[int]) -> None:
    money = lambda x: f"{x:>14,.2f}"  # noqa: E731
    income = total.income_fair.money + total.income_over.money + total.income_unknown.money
    cost = (
        total.paid_fair.money + total.paid_lawyer.money
        + total.paid_fraud.money + total.paid_unknown.money
    )
    weighted = sum(row["weighted_net"] for row in per_game.values())

    print(f"\n{'=' * 78}\nMONEY DECOMPOSITION -- {len(per_game)} Games\n{'=' * 78}")
    print(f"\n  AS ISSUER (income){'':>28}{'rows':>8}{'money':>16}")
    for label, bucket in (
        ("charged at or below t (paid by all 16)", total.income_fair),
        ("charged above t (paid only by the loose)", total.income_over),
        ("bracket cannot resolve", total.income_unknown),
    ):
        print(f"    {label:<46}{bucket.rows:>8}{money(bucket.money)}")
    print(f"    {'TOTAL INCOME':<46}{'':>8}{money(income)}")

    print(f"\n  AS REVIEWER (cost){'':>28}{'rows':>8}{'money':>16}")
    for label, bucket in (
        ("paid a fair claim (correct, unavoidable)", total.paid_fair),
        ("wrongful rejection -- paid 1.5a", total.paid_lawyer),
        ("Overcharge accepted -- fraud let through", total.paid_fraud),
        ("bracket cannot resolve", total.paid_unknown),
        ("rightly rejected -- paid nothing", total.rejected_right),
    ):
        print(f"    {label:<46}{bucket.rows:>8}{money(bucket.money)}")
    print(f"    {'TOTAL COST':<46}{'':>8}{money(cost)}")

    print(f"\n  {'NET (unweighted)':<48}{'':>8}{money(total.net())}")
    print(f"  {'NET (Games 81-100 at 3x)':<48}{'':>8}{money(weighted)}")

    print(f"\n{'-' * 78}\nTHE THREE STRUCTURAL LOSSES -- every euro here was avoidable\n{'-' * 78}")
    print(f"  {'lawyer waste (the 0.5a surcharge; Limit too low)':<58}{money(total.lawyer_surcharge)}")
    print(f"  {'fraud let through (Limit too high)':<58}{money(total.paid_fraud.money)}")
    print(
        f"  {f'forfeited income ({total.forfeited_items} items charged above t)':<58}"
        f"{money(total.forfeited)}"
    )
    print(f"  {'TOTAL RECOVERABLE (lower bound)':<58}{money(total.lawyer_surcharge + total.paid_fraud.money + total.forfeited)}")

    worst = sorted(per_game.items(), key=lambda kv: kv[1]["weighted_net"])[:12]
    print(f"\n{'-' * 78}\nTHE TWELVE WORST GAMES (weighted)\n{'-' * 78}")
    print(f"  {'game':>5}{'items':>7}{'weighted':>13}{'income':>12}{'lawyer':>12}{'fraud':>12}{'forfeit':>12}")
    for game_id, row in worst:
        print(
            f"  {game_id:>5}{row['line_items']:>7}{row['weighted_net']:>13,.0f}"
            f"{row['income']:>12,.0f}{row['lawyer_surcharge']:>12,.0f}"
            f"{row['fraud_let_through']:>12,.0f}{row['forfeited']:>12,.0f}"
        )


def _parse_games(spec: str) -> list[int]:
    if spec == "all":
        return list(range(1, 101))
    out: list[int] = []
    for part in spec.split(","):
        start, _, end = part.partition("-")
        out.extend(range(int(start), int(end or start) + 1))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="all")
    parser.add_argument("--team", default=US)
    parser.add_argument("--json", type=Path, help="also write the per-Game table here")
    args = parser.parse_args()

    game_ids = _parse_games(args.games)
    total, per_game = decompose(game_ids, args.team)
    report(total, per_game, game_ids)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(per_game, indent=1, sort_keys=True) + "\n")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
