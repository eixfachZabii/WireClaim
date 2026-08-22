"""Replay a Game with a hypothetical submission of ours, against the real Field.

What this is for
----------------
The published Transactions of a settled Game contain, for every ordered pair of teams and
every Line Item, whether the Charge was accepted and how much money moved. That is enough
to reconstruct *everybody else's behaviour* and to bracket the secret Fair Value `t`. Once
we have those, we can ask the counterfactual that actually matters:

    what would our net have been in Game g if we had submitted (a, b) instead?

holding every opponent's real Charge and Limit fixed. That turns tuning -- of the Fair
Value estimator, of the Charge multiplier, of the Limit multiplier -- into a measurement
instead of an argument.

The payoff table (docs/GAME_DESCRIPTION.md), for issuer H with Charge `a` and reviewer I
with Limit `b`, accept meaning `a <= b`:

    a <= t, accepted   I pays a,          H gets a
    a <= t, rejected   I pays 1.5 * a,    H gets a          (wrongful rejection)
    a >  t, accepted   I pays min(a, c),  H gets min(a, c)
    a >  t, rejected   nothing

The Cap `c >= 4t` is treated as **infinite** here. That is not an assumption we made up:
`cap_conflicts()` checks, for every (Line Item, issuer) in Games 1-14, whether two rows
with money moving ever report two different amounts -- which is what a binding Cap would
look like, since a rejected-but-owed row pays exactly `a` while an accepted row pays
`min(a, c)`. There are zero such conflicts in the observed data, so the Cap never bound
and `min(a, c) = a` throughout.

What is reconstructed, and how
------------------------------
*Charge* of team T on Line Item i: any row where T is the issuer and `amount > 0` pays
exactly `a` (accepted, Cap not binding) or exactly `a` (wrongful rejection). If no row
moved money but some reviewer accepted, the Charge was exactly `0`. If every reviewer
rejected and nothing moved, the Charge is **unrecoverable**; it is recorded as `inf`. That
is the honest encoding: such a Charge sat above `t` *and* above the Limit of all sixteen
reviewers, so treating it as unaffordably high reproduces every real row it appears in.
272 of 3264 (Line Item, team) Charges in Games 1-14 are unrecoverable this way.

*Limit* of team T on Line Item i: a bracket, not a number.

    b >= max { Charge of any issuer T accepted }        (b_lo)
    b <  min { Charge of any issuer T rejected }        (b_hi, possibly inf)

We must pick a representative point inside it. The default is **the midpoint when the
bracket is bounded, and `b_lo` when it is not** (`limit_rule="mid"`). Both endpoints are
defensible; the midpoint is chosen because it is the only choice that is not systematically
biased in either direction, and `b_lo` for the unbounded case is the conservative one -- it
credits an opponent only with the generosity we actually saw, so a sweep never earns income
from an invented Limit. `limit_rule="lo"` and `"hi"` are available to bound the sensitivity;
`sweep()` output moves by a few percent between them.

Crucially, *any* representative inside the bracket reproduces reality when fed our real
submission: a Charge the opponent accepted is `<= b_lo <= rep`, and a Charge it rejected is
`>= b_hi > rep`. The self-check below is therefore not weakened by the choice.

*Fair Value* `t` of Line Item i: the bracket from `invert_fair_values.brackets()` --
`t >= max wrongfully-rejected Charge` (t_lo), `t < min rightfully-rejected Charge` (t_hi,
possibly inf). The point used for the `a <= t` test is the midpoint when bounded and `t_lo`
when not. Same argument: every real row is on the correct side of that point, so the
self-check is exact; only genuinely counterfactual Charges land in the ambiguous interior.

The self-check
--------------
`self_check(game_id)` feeds our *reconstructed actual* submission back in and compares the
replayed net against the published leaderboard cell for `Bin busy`. It reproduces all
fourteen Games to the cent. Without that, none of the numbers this file produces mean
anything -- see `tests/test_replay_payoffs.py`, which asserts it for Games 1-14.

Usage
-----
    python scripts/replay_payoffs.py --games 1-14 --self-check
    python scripts/replay_payoffs.py --games 1-14 --sweep oracle
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))

from invert_fair_values import brackets  # noqa: E402
from pull_transactions import matrix, teams, transactions  # noqa: E402

INF = math.inf
US = "Bin busy"
CACHE = Path("var/replay")

#: Charge and Limit multipliers used when a sweep is not asked for a grid.
DEFAULT_ALPHAS = tuple(round(0.2 + 0.1 * k, 2) for k in range(0, 29))  # 0.2 .. 3.0
DEFAULT_BETAS = tuple(round(0.1 + 0.1 * k, 2) for k in range(0, 20))  # 0.1 .. 2.0


# --------------------------------------------------------------------------- payoffs


def issuer_payoff(charge: float, limit: float, fair_value: float) -> float:
    """What the issuer receives for one Transaction. Cap treated as infinite."""
    if charge <= limit:  # accepted
        return charge
    if charge <= fair_value:  # wrongful rejection: still owed
        return charge
    return 0.0  # rightful rejection


def reviewer_payoff(charge: float, limit: float, fair_value: float) -> float:
    """What the reviewer pays for one Transaction. Cap treated as infinite."""
    if charge <= limit:  # accepted
        return charge
    if charge <= fair_value:  # wrongful rejection: compensation plus the lawyer
        return 1.5 * charge
    return 0.0


# --------------------------------------------------------------------- reconstruction


@dataclass(frozen=True)
class GameSnapshot:
    """Everything about one settled Game that a counterfactual replay needs."""

    game_id: int
    us: str
    line_items: tuple[int, ...]
    #: line item -> (t_lo, t_hi); t_hi may be inf
    fair_brackets: dict[int, tuple[float, float]]
    #: line item -> team -> Charge (inf where unrecoverable)
    charges: dict[int, dict[str, float]]
    #: line item -> team -> (b_lo, b_hi); b_hi may be inf
    limit_brackets: dict[int, dict[str, tuple[float, float]]]
    #: the sixteen opponents we faced, per Line Item, in each role
    opponents: tuple[str, ...]
    published_net: float
    #: (line item, team) pairs whose Charge could not be recovered
    unrecoverable: tuple[tuple[int, str], ...]

    def fair_point(self, index: int) -> float:
        lo, hi = self.fair_brackets[index]
        return lo if hi == INF else (lo + hi) / 2.0

    def limit_point(self, index: int, team: str, rule: str = "mid") -> float:
        lo, hi = self.limit_brackets[index][team]
        if rule == "lo" or hi == INF:
            return lo
        if rule == "hi":
            return math.nextafter(hi, 0.0)
        return (lo + hi) / 2.0

    def zero_fair_value(self, index: int) -> bool:
        """True when no team was ever owed money on this item, i.e. `t = 0` is consistent.

        This is the only observable signature of a worthless Line Item: `t_lo = 0` means
        nobody's Charge was ever wrongfully rejected, so nobody demonstrated entitlement.
        76 of the 192 Line Items in Games 1-14 look like this.
        """
        return self.fair_brackets[index][0] == 0.0


def _charges_and_limits(
    game_id: int, team_names: list[str]
) -> tuple[
    dict[int, dict[str, float]],
    dict[int, dict[str, tuple[float, float]]],
    list[tuple[int, str]],
]:
    rows_by_team = {team: transactions(team, game_id) for team in team_names}
    indices = sorted({row["line_item_index"] for rows in rows_by_team.values() for row in rows})

    charges: dict[int, dict[str, float]] = {i: {} for i in indices}
    unrecoverable: list[tuple[int, str]] = []
    for team, rows in rows_by_team.items():
        paid: dict[int, float] = {}
        accepted_at_zero: set[int] = set()
        for row in rows:
            if row["issuer"] != team:
                continue
            index = row["line_item_index"]
            if row["amount"] > 0:
                paid[index] = max(paid.get(index, 0.0), row["amount"])
            elif row["accepted"]:
                accepted_at_zero.add(index)
        for index in indices:
            if index in paid:
                charges[index][team] = paid[index]
            elif index in accepted_at_zero:
                charges[index][team] = 0.0
            else:
                charges[index][team] = INF
                unrecoverable.append((index, team))

    limits: dict[int, dict[str, tuple[float, float]]] = {
        i: {t: (0.0, INF) for t in team_names} for i in indices
    }
    for team, rows in rows_by_team.items():
        for row in rows:
            if row["reviewer"] != team:
                continue
            index = row["line_item_index"]
            charge = charges[index].get(row["issuer"], INF)
            lo, hi = limits[index][team]
            if row["accepted"]:
                # accepted pays min(a, c) = a, so the row itself carries the Charge
                lo = max(lo, row["amount"])
            elif charge != INF:
                hi = min(hi, charge)
            limits[index][team] = (lo, hi)
    return charges, limits, unrecoverable


def _cache_path(game_id: int, us: str) -> Path:
    return CACHE / f"snapshot_g{game_id:03d}_{us.replace(' ', '_')}.json"


def snapshot(game_id: int, us: str = US, *, use_cache: bool = True) -> GameSnapshot:
    """Reconstruct one Game. Cached on disk under ``var/replay`` keyed on Game id."""
    path = _cache_path(game_id, us)
    if use_cache and path.exists():
        return _decode(json.loads(path.read_text()))

    team_names = teams()
    charges, limits, unrecoverable = _charges_and_limits(game_id, team_names)
    fair = brackets(game_id, team_names)
    our_rows = transactions(us, game_id)
    opponents = tuple(
        sorted({row["issuer"] for row in our_rows} | {row["reviewer"] for row in our_rows} - {us})
    )
    opponents = tuple(t for t in opponents if t != us)
    snap = GameSnapshot(
        game_id=game_id,
        us=us,
        line_items=tuple(sorted(fair)),
        fair_brackets={i: (lo, hi) for i, (lo, hi) in fair.items()},
        charges=charges,
        limit_brackets=limits,
        opponents=opponents,
        published_net=matrix()[us][game_id - 1],
        unrecoverable=tuple(unrecoverable),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_encode(snap), indent=1))
    return snap


def _n(value: float) -> float | None:
    return None if value == INF else value


def _f(value: float | None) -> float:
    return INF if value is None else float(value)


def _encode(snap: GameSnapshot) -> dict:
    return {
        "game_id": snap.game_id,
        "us": snap.us,
        "line_items": list(snap.line_items),
        "fair_brackets": {str(i): [lo, _n(hi)] for i, (lo, hi) in snap.fair_brackets.items()},
        "charges": {str(i): {t: _n(a) for t, a in d.items()} for i, d in snap.charges.items()},
        "limit_brackets": {
            str(i): {t: [lo, _n(hi)] for t, (lo, hi) in d.items()}
            for i, d in snap.limit_brackets.items()
        },
        "opponents": list(snap.opponents),
        "published_net": snap.published_net,
        "unrecoverable": [[i, t] for i, t in snap.unrecoverable],
    }


def _decode(blob: dict) -> GameSnapshot:
    return GameSnapshot(
        game_id=blob["game_id"],
        us=blob["us"],
        line_items=tuple(blob["line_items"]),
        fair_brackets={int(i): (v[0], _f(v[1])) for i, v in blob["fair_brackets"].items()},
        charges={int(i): {t: _f(a) for t, a in d.items()} for i, d in blob["charges"].items()},
        limit_brackets={
            int(i): {t: (v[0], _f(v[1])) for t, v in d.items()}
            for i, d in blob["limit_brackets"].items()
        },
        opponents=tuple(blob["opponents"]),
        published_net=blob["published_net"],
        unrecoverable=tuple((int(i), t) for i, t in blob["unrecoverable"]),
    )


def cap_conflicts(game_id: int, team_names: list[str] | None = None) -> list[str]:
    """Evidence about the Cap: rows for one (Line Item, issuer) that disagree on `a`.

    A binding Cap would make an accepted row pay `c` while a wrongful rejection still pays
    the full `a`, so the two would disagree. Returns the disagreements; empty means the Cap
    never bound in this Game, which is what we observe for all of Games 1-14.
    """
    team_names = team_names or teams()
    seen: dict[tuple[int, str], set[float]] = {}
    for team in team_names:
        for row in transactions(team, game_id):
            if row["issuer"] == team and row["amount"] > 0:
                seen.setdefault((row["line_item_index"], team), set()).add(round(row["amount"], 6))
    return [
        f"g{game_id} item {i} {t}: amounts {sorted(v)}" for (i, t), v in seen.items() if len(v) > 1
    ]


# ------------------------------------------------------------------------------ replay


@dataclass(frozen=True)
class ReplayResult:
    game_id: int
    net: float
    income: float
    cost: float
    #: line item -> (income, cost)
    per_item: dict[int, tuple[float, float]]

    def __str__(self) -> str:  # pragma: no cover - display only
        return (
            f"G{self.game_id:3d} net {self.net:12.2f}  "
            f"(income {self.income:11.2f}, cost {self.cost:11.2f})"
        )


Submission = Mapping[int, tuple[float, float]]


def our_actual_submission(snap: GameSnapshot) -> dict[int, tuple[float, float]]:
    """Our real `(a, b)` per Line Item, reconstructed exactly as an opponent's would be."""
    return {
        index: (snap.charges[index][snap.us], snap.limit_point(index, snap.us))
        for index in snap.line_items
    }


def replay(
    snap: GameSnapshot,
    submission: Submission,
    *,
    limit_rule: str = "mid",
) -> ReplayResult:
    """Our net in this Game had we submitted `submission`, with the Field held fixed.

    `submission` maps Line Item index to `(charge, limit)`. Missing Line Items are treated
    as `(0, 0)` -- the tournament default, which is not free: `b = 0` wrongfully rejects
    every fair Charge and pays `1.5a` for it.
    """
    income = 0.0
    cost = 0.0
    per_item: dict[int, tuple[float, float]] = {}
    for index in snap.line_items:
        charge, limit = submission.get(index, (0.0, 0.0))
        t = snap.fair_point(index)
        item_income = 0.0
        item_cost = 0.0
        for team in snap.opponents:
            item_income += issuer_payoff(charge, snap.limit_point(index, team, limit_rule), t)
            item_cost += reviewer_payoff(snap.charges[index][team], limit, t)
        per_item[index] = (item_income, item_cost)
        income += item_income
        cost += item_cost
    return ReplayResult(snap.game_id, income - cost, income, cost, per_item)


def self_check(game_id: int, us: str = US, *, limit_rule: str = "mid") -> tuple[float, float]:
    """Replay our real submission. Returns `(replayed net, published net)`."""
    snap = snapshot(game_id, us)
    result = replay(snap, our_actual_submission(snap), limit_rule=limit_rule)
    return result.net, snap.published_net


# ------------------------------------------------------------------------------- sweep


def multiplier_submission(
    estimates: Mapping[int, float], alpha: float, beta: float
) -> dict[int, tuple[float, float]]:
    """`a = beta * t_hat`, `b = alpha * t_hat` -- the two knobs on top of an estimator."""
    return {index: (beta * t_hat, alpha * t_hat) for index, t_hat in estimates.items()}


def sweep(
    snap: GameSnapshot,
    estimates: Mapping[int, float],
    *,
    alphas: Iterable[float] = DEFAULT_ALPHAS,
    betas: Iterable[float] = DEFAULT_BETAS,
    limit_rule: str = "mid",
) -> dict[tuple[float, float], float]:
    """Net as a function of the Limit multiplier `alpha` and the Charge multiplier `beta`."""
    grid: dict[tuple[float, float], float] = {}
    for alpha in alphas:
        for beta in betas:
            submission = multiplier_submission(estimates, alpha, beta)
            grid[(alpha, beta)] = replay(snap, submission, limit_rule=limit_rule).net
    return grid


def sweep_total(
    snapshots: Iterable[GameSnapshot],
    estimator: Callable[[GameSnapshot], Mapping[int, float]],
    *,
    alphas: Iterable[float] = DEFAULT_ALPHAS,
    betas: Iterable[float] = DEFAULT_BETAS,
    limit_rule: str = "mid",
) -> dict[tuple[float, float], float]:
    """The same sweep summed over several Games -- what we actually tune against."""
    alphas = tuple(alphas)
    betas = tuple(betas)
    total: dict[tuple[float, float], float] = {(a, b): 0.0 for a in alphas for b in betas}
    for snap in snapshots:
        grid = sweep(snap, estimator(snap), alphas=alphas, betas=betas, limit_rule=limit_rule)
        for key, value in grid.items():
            total[key] += value
    return total


def best_multipliers(grid: Mapping[tuple[float, float], float]) -> tuple[float, float, float]:
    """`(alpha, beta, net)` of the best cell."""
    (alpha, beta), net = max(grid.items(), key=lambda kv: kv[1])
    return alpha, beta, net


def oracle_estimates(snap: GameSnapshot) -> dict[int, float]:
    """The cheating estimator: the midpoint of the true Fair Value bracket."""
    return {index: snap.fair_point(index) for index in snap.line_items}


# --------------------------------------------------------------------------------- cli


def _parse_games(spec: str) -> list[int]:
    start, _, end = spec.partition("-")
    return list(range(int(start), int(end or start) + 1))


def main() -> None:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--team", default=US)
    parser.add_argument("--limit-rule", default="mid", choices=("lo", "mid", "hi"))
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--cap-check", action="store_true")
    parser.add_argument(
        "--sweep",
        choices=("oracle",),
        help="sweep alpha/beta for the cheating t_mid estimator",
    )
    args = parser.parse_args()

    snaps = [snapshot(g, args.team) for g in _parse_games(args.games)]

    if args.cap_check:
        conflicts = [c for snap in snaps for c in cap_conflicts(snap.game_id)]
        print(f"Cap conflicts: {len(conflicts)} {conflicts if conflicts else '(Cap never bound)'}")

    if args.self_check or not (args.sweep or args.cap_check):
        worst = 0.0
        for snap in snaps:
            got, want = self_check(snap.game_id, args.team, limit_rule=args.limit_rule)
            worst = max(worst, abs(got - want))
            flag = "OK " if abs(got - want) < 0.01 else "FAIL"
            print(f"G{snap.game_id:3d} {flag} replayed {got:12.2f}  published {want:12.2f}")
        print(f"worst absolute deviation: {worst:.6f}")

    if args.sweep:
        grid = sweep_total(snaps, oracle_estimates, limit_rule=args.limit_rule)
        alpha, beta, net = best_multipliers(grid)
        print(f"\nbest for {args.sweep}: alpha={alpha} beta={beta} total net {net:,.2f}")
        for snap in snaps:
            submission = multiplier_submission(oracle_estimates(snap), alpha, beta)
            print(replay(snap, submission, limit_rule=args.limit_rule))


if __name__ == "__main__":  # pragma: no cover
    main()
