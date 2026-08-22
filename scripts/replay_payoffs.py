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
from an invented Limit. `limit_rule="lo"` and `"hi"` are available to bound the sensitivity.

**The choice provably cannot change any conclusion we draw.** It used to say here that
"`sweep()` output moves by a few percent between them", which is vague and, where it matters,
wrong: measured over all 24 completed Games (`--limit-sensitivity`), `lo`, `mid` and `hi`
give the *identical* total to the cent for every Charge multiplier `beta <= 1` -- the actual
submission total (-324,059.01), the best cell (`alpha=1.0, beta=1.0`) and the best total
(811,568.88) are all unchanged. The reason is structural, not luck: for `a <= t` the issuer
is paid `a` whether the reviewer accepts or wrongfully rejects, so our income does not depend
on any opponent's Limit, and our cost depends only on our own `b`. Opponents' reconstructed
Limits only start to matter once we overcharge, and there the spread is real -- up to 94,737
at `beta = 1.1`. Since R5b puts us at `a = 0.7 t̂`, the harness is exactly insensitive in the
region we operate in and only wobbles in the Overcharge region R5c already tells us not to
trust. See `limit_sensitivity()`.

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
replayed net against the authoritative net for `Bin busy`. Without that, none of the numbers
this file produces mean anything -- see `tests/test_replay_payoffs.py`, which asserts it for
every completed Game.

*Authoritative* means the identity, not the leaderboard:

    net = sum(amount as issuer) - sum(amount if accepted else 1.5 * amount as reviewer)

which is computed from the rows and therefore cannot be misattributed. The leaderboard cell
is used only as a cross-check, and `snapshot()` raises `UnreconstructableGame` if the two
disagree.

That distinction is not pedantry; it is the fix for a real failure. `snapshot()` used to
read `matrix()[us][game_id - 1]`, and `/matrix` `cells` is **a trailing window of the twenty
most recently completed Games**, not a list indexed by Game id. Once Game 21 settled the
window slid and every cell moved. The visible symptom was "Game 16 does not reconstruct:
replayed -4,721 against a published -63,789, and only 2 Line Items recovered where the Case
has far more". All three parts of that were wrong about different things:

* -4,721.32 is Game 16's **correct** net, confirmed by the identity over all 17 teams.
* -63,789.25 is **Game 17's** net, which the stale positional index handed to Game 16.
* Case 16's invoice really does have exactly **2 Line Items** ("Clothing and jewellery
  stolen from the car", "Vehicle costs"), and the endpoint reports `total = 64` rows for us,
  which is what we fetched. There was no short read.

So Game 16 reconstructs, and always did. What failed was the attribution -- and the cached
`var/replay` snapshot froze the wrong number in place, which is why snapshots now carry a
`version` and older ones are discarded rather than trusted.

Usage
-----
    PYTHONPATH=. python scripts/replay_payoffs.py --games all --self-check
    PYTHONPATH=. python scripts/replay_payoffs.py --games all --limit-sensitivity
    PYTHONPATH=. python scripts/replay_payoffs.py --games 1-14 --sweep oracle
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
from pull_transactions import (  # noqa: E402
    AmbiguousMatrix,
    completed_games,
    identity_net,
    matrix,
    teams,
    transactions,
)

INF = math.inf
US = "Bin busy"
CACHE = Path("var/replay")

#: Bump to discard every cached snapshot. v1 snapshots stored `published_net` read off a
#: positional `/matrix` index, so Games 15-20 were frozen holding another Game's money.
SNAPSHOT_VERSION = 2


class UnreconstructableGame(RuntimeError):
    """This Game cannot be reconstructed, so no number derived from it may be scored."""


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
    #: The net this Game really produced for `us`. Always the identity over the rows; the
    #: leaderboard cell agrees with it or `snapshot()` refused to build this object.
    published_net: float
    #: (line item, team) pairs whose Charge could not be recovered
    unrecoverable: tuple[tuple[int, str], ...]
    #: The `/matrix` cell for this Game id, or None when the Game is outside the published
    #: twenty-Game window. Kept separately so the cross-check is auditable after the fact.
    leaderboard_net: float | None = None

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


def authoritative_net(game_id: int, us: str = US) -> tuple[float, float | None]:
    """`(identity net, leaderboard cell or None)` for one team in one Game.

    The identity comes first because it is the one that cannot be wrong: it is arithmetic
    over the fetched rows. The cell is looked up **by Game id** via `matrix()`, which refuses
    to guess the mapping; `None` therefore means "not published" (outside the trailing
    twenty-Game window, or `/matrix` unusable), never "index out of range".
    """
    mine = identity_net(transactions(us, game_id), us)
    try:
        cell = matrix().get(us, {}).get(game_id)
    except (AmbiguousMatrix, RuntimeError):
        cell = None
    return mine, cell


def snapshot(game_id: int, us: str = US, *, use_cache: bool = True) -> GameSnapshot:
    """Reconstruct one Game. Cached on disk under ``var/replay`` keyed on Game id.

    Raises `UnreconstructableGame` when the identity net and the published `/matrix` cell for
    this Game disagree. That is deliberately fatal: a Game whose rows do not add up to its
    published result has either been voided, been settled by rules we do not model, or been
    fetched short, and every one of those makes any counterfactual built on it fiction. The
    old behaviour -- return the number anyway -- is what let a misattributed Game 16 sit in
    the cache being scored against.
    """
    path = _cache_path(game_id, us)
    if use_cache and path.exists():
        blob = json.loads(path.read_text())
        if blob.get("version") == SNAPSHOT_VERSION:
            return _decode(blob)
        # Pre-v2: `published_net` was read off a positional /matrix index and may belong to
        # another Game entirely. Unusable; rebuild from the rows.

    mine, cell = authoritative_net(game_id, us)
    if cell is not None and abs(mine - cell) > 0.01:
        raise UnreconstructableGame(
            f"G{game_id} {us}: rows give {mine:.2f} but /matrix publishes {cell:.2f} "
            f"-- the Game does not reconstruct and must not be scored against"
        )

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
        published_net=mine,
        unrecoverable=tuple(unrecoverable),
        leaderboard_net=cell,
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
        "version": SNAPSHOT_VERSION,
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
        "leaderboard_net": snap.leaderboard_net,
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
        leaderboard_net=blob.get("leaderboard_net"),
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


def self_check(
    game_id: int, us: str = US, *, limit_rule: str = "mid", strict: bool = False
) -> tuple[float, float]:
    """Replay our real submission. Returns `(replayed net, authoritative net)`.

    With `strict=True` a Game that does not reconstruct raises `UnreconstructableGame`
    instead of returning a pair of numbers that a caller might average. Prefer
    `reconstruction_status()` when you want to *report* rather than *fail*.
    """
    snap = snapshot(game_id, us)
    result = replay(snap, our_actual_submission(snap), limit_rule=limit_rule)
    if strict and abs(result.net - snap.published_net) > 0.01:
        raise UnreconstructableGame(
            f"G{game_id} {us}: replay {result.net:.2f} != authoritative "
            f"{snap.published_net:.2f} -- unusable, do not score against it"
        )
    return result.net, snap.published_net


@dataclass(frozen=True)
class Reconstruction:
    """Whether one Game may be scored against, and every number behind that verdict."""

    game_id: int
    status: str  #: "ok" | "mismatch" | "error"
    line_items: int
    replayed: float | None
    authoritative: float | None
    leaderboard: float | None
    detail: str = ""

    @property
    def usable(self) -> bool:
        return self.status == "ok"

    def __str__(self) -> str:  # pragma: no cover - display only
        if self.status == "error":
            return f"G{self.game_id:3d} ERROR  {self.detail}"
        cell = (
            "  (not published)"
            if self.leaderboard is None
            else f"  cell {self.leaderboard:12.2f}"
        )
        flag = "OK  " if self.status == "ok" else "FAIL"
        return (
            f"G{self.game_id:3d} {flag} {self.line_items:3d} items  "
            f"replay {self.replayed:12.2f}  identity {self.authoritative:12.2f}{cell}"
        )


def reconstruction_status(
    game_id: int, us: str = US, *, limit_rule: str = "mid"
) -> Reconstruction:
    """Report, never raise. `status == "ok"` is the only licence to score against a Game."""
    try:
        snap = snapshot(game_id, us)
    except UnreconstructableGame as exc:
        return Reconstruction(game_id, "mismatch", 0, None, None, None, str(exc))
    except Exception as exc:  # network, missing rows, malformed payload
        return Reconstruction(game_id, "error", 0, None, None, None, f"{type(exc).__name__}: {exc}")
    replayed = replay(snap, our_actual_submission(snap), limit_rule=limit_rule).net
    ok = abs(replayed - snap.published_net) <= 0.01
    return Reconstruction(
        game_id=game_id,
        status="ok" if ok else "mismatch",
        line_items=len(snap.line_items),
        replayed=replayed,
        authoritative=snap.published_net,
        leaderboard=snap.leaderboard_net,
        detail="" if ok else f"replay off by {replayed - snap.published_net:.2f}",
    )


def reconstruction_report(
    game_ids: Iterable[int] | None = None, us: str = US, *, limit_rule: str = "mid"
) -> list[Reconstruction]:
    """Every completed Game (by default), each labelled usable or not."""
    ids = list(game_ids) if game_ids is not None else completed_games()
    return [reconstruction_status(g, us, limit_rule=limit_rule) for g in ids]


def usable_games(game_ids: Iterable[int] | None = None, us: str = US) -> list[int]:
    """The Games it is legitimate to tune against. Anything else is excluded, loudly."""
    return [r.game_id for r in reconstruction_report(game_ids, us) if r.usable]


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
    """`"1-14"`, `"16"`, or `"all"` -- every completed Game, resolved against `/games`."""
    if spec == "all":
        return completed_games()
    start, _, end = spec.partition("-")
    return list(range(int(start), int(end or start) + 1))


def limit_sensitivity(
    snaps: Iterable[GameSnapshot],
    estimator: Callable[[GameSnapshot], Mapping[int, float]] | None = None,
    *,
    alphas: Iterable[float] = DEFAULT_ALPHAS,
    betas: Iterable[float] = DEFAULT_BETAS,
) -> dict:
    """How much the arbitrary `limit_rule` choice moves the numbers. Measured, not argued.

    The docstring at the top of this file picks `limit_rule="mid"` for the reviewer's Limit
    bracket, and claims `sweep()` "moves by a few percent between" the endpoints. Both the
    choice and the claim need checking, so this returns, for `lo`/`mid`/`hi`:

    * `actual`  -- the total over our real submissions (the self-check total),
    * `best`    -- `(alpha, beta, total)` of the best sweep cell,
    * `worst_gap` / `worst_gap_beta` -- the largest `|lo - hi|` anywhere in the grid, and
      which Charge multiplier it happens at.

    The measured answer over all completed Games is sharper than "a few percent", and it has
    a proof rather than a tolerance. **The rule cannot matter at all while `beta <= 1`, and
    the totals under `lo`, `mid` and `hi` are bit-identical there.** The reason is in the
    payoff table: for `a <= t` the issuer is paid `a` whether the reviewer accepts or
    wrongfully rejects, so our *income* does not depend on any opponent's Limit; and our
    *cost* depends only on our own `b`, never on theirs. The opponents' reconstructed Limits
    only become load-bearing once we overcharge (`a > t`), where acceptance decides whether
    money moves.

    So the harness is insensitive exactly where we operate (R5b puts us at `a = 0.7 t̂`) and
    sensitive only in the Overcharge region, which R5c already tells us not to trust.
    """
    snaps = list(snaps)
    estimator = estimator or oracle_estimates
    alphas, betas = tuple(alphas), tuple(betas)
    grids = {
        rule: sweep_total(snaps, estimator, alphas=alphas, betas=betas, limit_rule=rule)
        for rule in ("lo", "mid", "hi")
    }
    gaps = {
        key: abs(grids["lo"][key] - grids["hi"][key]) for key in grids["mid"]
    }
    worst_key = max(gaps, key=lambda k: gaps[k])
    return {
        "rules": {
            rule: {
                "actual": sum(
                    replay(s, our_actual_submission(s), limit_rule=rule).net for s in snaps
                ),
                "best": best_multipliers(grids[rule]),
            }
            for rule in ("lo", "mid", "hi")
        },
        "worst_gap": gaps[worst_key],
        "worst_gap_at": worst_key,
        "insensitive_betas": sorted(
            beta for beta in betas if all(gaps[(a, beta)] == 0.0 for a in alphas)
        ),
        "cells": len(gaps),
    }


def main() -> None:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="all", help="1-14, 16, or 'all' (default)")
    parser.add_argument("--team", default=US)
    parser.add_argument("--limit-rule", default="mid", choices=("lo", "mid", "hi"))
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--cap-check", action="store_true")
    parser.add_argument(
        "--limit-sensitivity",
        action="store_true",
        help="report the oracle sweep total under limit_rule lo/mid/hi",
    )
    parser.add_argument(
        "--sweep",
        choices=("oracle",),
        help="sweep alpha/beta for the cheating t_mid estimator",
    )
    args = parser.parse_args()

    game_ids = _parse_games(args.games)

    if args.self_check or not (args.sweep or args.cap_check or args.limit_sensitivity):
        report = reconstruction_report(game_ids, args.team, limit_rule=args.limit_rule)
        for row in report:
            print(row)
        good = [r.game_id for r in report if r.usable]
        bad = [r.game_id for r in report if not r.usable]
        print(f"\nreconstructs ({len(good)}): {good}")
        print(f"UNUSABLE     ({len(bad)}): {bad if bad else 'none'}")
        for row in report:
            if not row.usable:
                print(f"  G{row.game_id}: {row.detail}")

    snaps = [snapshot(g, args.team) for g in game_ids]

    if args.cap_check:
        conflicts = [c for snap in snaps for c in cap_conflicts(snap.game_id)]
        print(f"Cap conflicts: {len(conflicts)} {conflicts if conflicts else '(Cap never bound)'}")

    if args.limit_sensitivity:
        report = limit_sensitivity(snaps, oracle_estimates)
        print(f"\nlimit-rule sensitivity over {len(snaps)} Games, {report['cells']} sweep cells")
        for rule, row in report["rules"].items():
            alpha, beta, net = row["best"]
            print(
                f"  {rule:3s} actual total {row['actual']:14,.2f}   "
                f"best alpha={alpha:<4} beta={beta:<4} total {net:14,.2f}"
            )
        knobs = {row["best"][:2] for row in report["rules"].values()}
        actuals = {round(row["actual"], 2) for row in report["rules"].values()}
        bests = {round(row["best"][2], 2) for row in report["rules"].values()}
        print(f"  identical under lo/mid/hi for every beta <= {max(report['insensitive_betas'])}")
        print(
            f"  worst |lo - hi| anywhere in the grid: {report['worst_gap']:,.2f} "
            f"at (alpha, beta) = {report['worst_gap_at']}  -- all of it above beta = 1"
        )
        ok = len(knobs) == 1 and len(actuals) == 1 and len(bests) == 1
        print(
            "  VERDICT: no conclusion changes -- actual total, best (alpha, beta) and best "
            "total are identical under all three rules"
            if ok
            else f"  VERDICT: SENSITIVE -- knobs {sorted(knobs)}, actuals {actuals}, bests {bests}"
        )

    if args.sweep:
        grid = sweep_total(snaps, oracle_estimates, limit_rule=args.limit_rule)
        alpha, beta, net = best_multipliers(grid)
        print(f"\nbest for {args.sweep}: alpha={alpha} beta={beta} total net {net:,.2f}")
        for snap in snaps:
            submission = multiplier_submission(oracle_estimates(snap), alpha, beta)
            print(replay(snap, submission, limit_rule=args.limit_rule))


if __name__ == "__main__":  # pragma: no cover
    main()
