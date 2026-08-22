"""Measure what the profitable teams do differently, and price adopting each piece of it.

Two teams are meaningfully profitable (`eyay`, `TakeTheMoneyAndRun`) and we are not. This
script answers *numerically* what they do differently, using only the published
Transactions -- no model, no guessing -- and then puts a euro figure on copying each piece
by replaying **their** submission on **our** Games.

Everything here is built on three existing tools and adds no new inversion logic:

* `pull_transactions.transactions/teams/matrix` -- paged rows, and `{team: {game_id: net}}`.
* `invert_fair_values.brackets`                 -- the exact Fair Value bracket per item.
* `replay_payoffs.snapshot/replay`              -- the counterfactual payoff harness.

What is measured (per team, per Game, then pooled, then split at a regime boundary)
----------------------------------------------------------------------------------
1. `a/t` and `b/t` distributions (p25/median/p75) and the share of Charges in the fair zone
   (`a <= t`, the region where income is owed by *every* opponent whether they accept or not).
2. Accept rate as Reviewer, split into *fair* Charges accepted and *Overcharges* accepted.
   Those are two different skills and the aggregate hides which one a team has.
3. Income decomposition: income from `a <= t` (structural, owed by all sixteen) versus income
   from Overcharges a generous opponent happened to pay (luck, and it evaporates when the
   field tightens).
4. Cost decomposition: paid on accepted fair claims (unavoidable), paid on accepted
   Overcharges (pure loss), and `1.5a` wrongful-rejection penalties (self-inflicted).
5. Consistency: per-Game net variance, and the spread of `a/t`.
6. Whether a team estimates at all: correlation of its Charge against the true `t` across
   items, plus a constant-Charge detector and a `(0,0)`-default detector.
7. The regime question: every metric split at `--split` (default Game 15).

Then the part that decides anything: `--adopt` replays, on each of our usable Games, the
submission `(a, b)` of a donor team, plus the two hybrids (their Charge with our Limit, and
our Charge with their Limit), which isolates whether their edge is on the Issuer or the
Reviewer side.

Two cautions are wired into the output rather than left to the reader:

* the noise floor is **26,622 over 18 Games**; a delta smaller than that is unproven, and
  `--adopt` labels it so;
* a Charge that no reviewer ever paid is **unrecoverable** (`inf`), not zero. Those rows are
  excluded from `a/t` statistics and counted separately, because treating them as `0` would
  invent a fair-zone Charge that never existed.

Usage
-----
    PYTHONPATH=. python scripts/field_study.py --games 1-26
    PYTHONPATH=. python scripts/field_study.py --games 1-26 --split 15
    PYTHONPATH=. python scripts/field_study.py --games 1-26 --verify-nets
    PYTHONPATH=. python scripts/field_study.py --games 1-26 --adopt --per-game
    PYTHONPATH=. python scripts/field_study.py --teams eyay,"Bin busy" --games 7-26
"""

from __future__ import annotations

import argparse
import math
import statistics as st
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path

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
from replay_payoffs import (  # noqa: E402
    _charges_and_limits,
    UnreconstructableGame,
    our_actual_submission,
    replay,
    snapshot,
    usable_games,
)

INF = math.inf
US = "Bin busy"

#: One Game of noise is worthless; this is the measured floor over eighteen Games (CLAUDE.md).
NOISE_FLOOR = 26_622.0

#: Two overall winners, two mid-table, the best team of the *recent* window, and us.
#: `Codacabana` is here because it is second over Games 19-26 while eleventh overall -- the
#: leaderboard total hides whoever is currently good, and that is who is worth copying.
DEFAULT_TEAMS = (
    "eyay",
    "TakeTheMoneyAndRun",
    "OPUSMOPUS",
    "error404 ai",
    "Codacabana",
    US,
)


# ------------------------------------------------------------------ per-Game field state


@dataclass
class Field:
    """One settled Game, reconstructed for every team at once.

    `snapshot()` does this for a single `us`; doing it seventeen times would re-derive the
    same brackets seventeen times. The reconstruction logic is *not* duplicated -- the
    Charge/Limit brackets come from `replay_payoffs._charges_and_limits` and the Fair Value
    bracket from `invert_fair_values.brackets`, the same two functions `snapshot()` calls.
    """

    game_id: int
    items: tuple[int, ...]
    fair: dict[int, tuple[float, float]]
    charges: dict[int, dict[str, float]]
    limits: dict[int, dict[str, tuple[float, float]]]
    rows: dict[str, list[dict]]

    def t(self, index: int) -> float:
        """Representative Fair Value: bracket midpoint, or `t_lo` when unbounded above.

        Every *real* Charge is on the correct side of this point by construction, so any
        classification of a real row as fair/Overcharge is exact. Only counterfactual
        Charges can land in the ambiguous interior.
        """
        lo, hi = self.fair[index]
        return lo if hi == INF else (lo + hi) / 2.0

    def t_bounded(self, index: int) -> bool:
        return self.fair[index][1] != INF

    def b(self, index: int, team: str) -> float:
        lo, hi = self.limits[index][team]
        return lo if hi == INF else (lo + hi) / 2.0


def load_field(game_id: int, team_names: list[str]) -> Field:
    charges, limits, _ = _charges_and_limits(game_id, team_names)
    fair = brackets(game_id, team_names)
    rows = {team: transactions(team, game_id) for team in team_names}
    return Field(
        game_id=game_id,
        items=tuple(sorted(fair)),
        fair=dict(fair),
        charges=charges,
        limits=limits,
        rows=rows,
    )


# ----------------------------------------------------------------------------- measures


@dataclass
class TeamGame:
    """Every measurement for one (team, Game). Sums are euros; ratios are unitless."""

    team: str
    game_id: int
    items: int = 0

    # --- issuer side, from the submitted Charge against the true t
    a_over_t: list[float] = dc_field(default_factory=list)
    b_over_t: list[float] = dc_field(default_factory=list)
    n_fair: int = 0  # a <= t
    n_over: int = 0  # a >  t
    n_unrecoverable: int = 0  # no reviewer ever paid; a is not observable
    n_zero_charge: int = 0
    charges_seen: list[float] = dc_field(default_factory=list)
    pairs_at: list[tuple[float, float]] = dc_field(default_factory=list)  # (a, t) for corr
    #: largest Charge this team ever *accepted and paid for* in this Game. 0 means its Limit
    #: never let a single euro through, which is the observable half of `b = 0`.
    max_b_lo: float = 0.0

    # --- income, from rows where this team is the issuer
    income_fair: float = 0.0  # a <= t: owed by every opponent, accept or not
    income_over: float = 0.0  # a >  t: only a generous reviewer pays

    # --- cost, from rows where this team is the reviewer
    cost_accept_fair: float = 0.0  # unavoidable: they really owed it
    cost_accept_over: float = 0.0  # pure loss: paid above Fair Value
    cost_penalty: float = 0.0  # 1.5a on wrongful rejection

    # --- reviewer decisions
    seen_fair: int = 0
    acc_fair: int = 0
    seen_over: int = 0
    acc_over: int = 0

    net: float = 0.0

    @property
    def income(self) -> float:
        return self.income_fair + self.income_over

    @property
    def cost(self) -> float:
        return self.cost_accept_fair + self.cost_accept_over + self.cost_penalty

    @property
    def zero_charge(self) -> bool:
        """`a = 0` on every Line Item -- the Issuer half of the tournament default.

        This is the signature behind "several teams scored an identical value in a Game": a
        team that Charges nothing earns nothing, so its net is whatever it paid as Reviewer,
        and when the field's Charges all sit above `t` its rejections are *rightful* and cost
        nothing either. Net is then exactly `0`, identically, for every such team. That is
        `a = 0`, not `b = 0` -- worth separating, because `b = 0` alone is sometimes free
        while `a = 0` forfeits the entire structural income.
        """
        return bool(self.charges_seen) and self.n_unrecoverable == 0 and max(self.charges_seen) == 0.0

    @property
    def zero_limit(self) -> bool:
        """`b = 0`: the Limit let no money through at all on any Line Item."""
        return self.items > 0 and self.max_b_lo == 0.0

    @property
    def dark(self) -> bool:
        """The full `(0,0)` default: nothing charged and nothing accepted for money."""
        return self.zero_charge and self.zero_limit


def measure(fld: Field, team: str) -> TeamGame:
    out = TeamGame(team=team, game_id=fld.game_id, items=len(fld.items))

    for index in fld.items:
        a = fld.charges[index].get(team, INF)
        t = fld.t(index)
        b = fld.b(index, team)
        if a == INF:
            out.n_unrecoverable += 1
        else:
            out.charges_seen.append(a)
            if a == 0.0:
                out.n_zero_charge += 1
            if a <= t:
                out.n_fair += 1
            else:
                out.n_over += 1
            if t > 0:
                out.a_over_t.append(a / t)
            if fld.t_bounded(index):
                out.pairs_at.append((a, t))
        if t > 0:
            out.b_over_t.append(b / t)
        out.max_b_lo = max(out.max_b_lo, fld.limits[index][team][0])

    for row in fld.rows[team]:
        index = row["line_item_index"]
        t = fld.t(index)
        if row["issuer"] == team:
            if row["amount"] > 0:
                # amount == a here (the Cap has never bound in any settled row)
                if row["amount"] <= t:
                    out.income_fair += row["amount"]
                else:
                    out.income_over += row["amount"]
        if row["reviewer"] == team:
            a = fld.charges[index].get(row["issuer"], INF)
            fair = a != INF and a <= t
            if fair:
                out.seen_fair += 1
                if row["accepted"]:
                    out.acc_fair += 1
                    out.cost_accept_fair += row["amount"]
                else:
                    out.cost_penalty += 1.5 * row["amount"]
            else:
                out.seen_over += 1
                if row["accepted"]:
                    out.acc_over += 1
                    out.cost_accept_over += row["amount"]
    out.net = identity_net(fld.rows[team], team)
    return out


# ------------------------------------------------------------------------------ helpers


def q(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(int(p * len(ordered)), len(ordered) - 1)]


def pearson(pairs: list[tuple[float, float]]) -> float:
    if len(pairs) < 3:
        return float("nan")
    xs = [x for x, _ in pairs]
    ys = [y for _, y in pairs]
    mx, my = st.fmean(xs), st.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in pairs)
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return float("nan")
    return num / (dx * dy)


def pct(num: int, den: int) -> str:
    return "    n/a" if den == 0 else f"{100.0 * num / den:6.1f}%"


def money(value: float) -> str:
    return f"{value:12,.0f}"


def pool(rounds: list[TeamGame]) -> TeamGame:
    """Sum a team's per-Game measurements into one pooled record."""
    if not rounds:
        return TeamGame(team="?", game_id=0)
    agg = TeamGame(team=rounds[0].team, game_id=0)
    for r in rounds:
        agg.items += r.items
        agg.max_b_lo = max(agg.max_b_lo, r.max_b_lo)
        agg.a_over_t += r.a_over_t
        agg.b_over_t += r.b_over_t
        agg.pairs_at += r.pairs_at
        agg.charges_seen += r.charges_seen
        for name in (
            "n_fair", "n_over", "n_unrecoverable", "n_zero_charge",
            "income_fair", "income_over",
            "cost_accept_fair", "cost_accept_over", "cost_penalty",
            "seen_fair", "acc_fair", "seen_over", "acc_over", "net",
        ):
            setattr(agg, name, getattr(agg, name) + getattr(r, name))
    return agg


# ------------------------------------------------------------------------------- tables


def table_ratios(pools: dict[str, TeamGame], title: str) -> None:
    print(f"\n=== {title}: Charge and Limit against the true Fair Value ===")
    print(
        f"{'team':22s} {'items':>6s} {'a/t p25':>8s} {'a/t med':>8s} {'a/t p75':>8s} "
        f"{'fair%':>7s} {'a=0':>6s} {'unrec':>6s} {'b/t p25':>8s} {'b/t med':>8s} {'b/t p75':>8s}"
    )
    for team, p in pools.items():
        n = p.n_fair + p.n_over
        print(
            f"{team:22s} {p.items:6d} "
            f"{q(p.a_over_t, .25):8.2f} {q(p.a_over_t, .50):8.2f} {q(p.a_over_t, .75):8.2f} "
            f"{pct(p.n_fair, n):>7s} {p.n_zero_charge:6d} {p.n_unrecoverable:6d} "
            f"{q(p.b_over_t, .25):8.2f} {q(p.b_over_t, .50):8.2f} {q(p.b_over_t, .75):8.2f}"
        )
    print("  a/t, b/t over items with t > 0. `unrec` = Charges no reviewer ever paid (a unknown).")


def table_accept(pools: dict[str, TeamGame], title: str) -> None:
    print(f"\n=== {title}: Reviewer behaviour -- two different skills ===")
    print(
        f"{'team':22s} {'rows':>6s} {'accept%':>8s} | {'fair seen':>10s} {'accepted':>9s} "
        f"| {'over seen':>10s} {'accepted':>9s}"
    )
    for team, p in pools.items():
        seen = p.seen_fair + p.seen_over
        acc = p.acc_fair + p.acc_over
        print(
            f"{team:22s} {seen:6d} {pct(acc, seen):>8s} | "
            f"{p.seen_fair:10d} {pct(p.acc_fair, p.seen_fair):>9s} | "
            f"{p.seen_over:10d} {pct(p.acc_over, p.seen_over):>9s}"
        )
    print("  Accepting a fair Charge saves the 1.5x penalty. Accepting an Overcharge is pure loss.")


def table_money(pools: dict[str, TeamGame], title: str) -> None:
    print(f"\n=== {title}: where the money comes from and goes ===")
    print(
        f"{'team':22s} {'net':>12s} | {'inc fair':>12s} {'inc over':>12s} {'over%':>6s} "
        f"| {'pay fair':>12s} {'pay over':>12s} {'penalty':>12s}"
    )
    for team, p in pools.items():
        print(
            f"{team:22s} {money(p.net)} | {money(p.income_fair)} {money(p.income_over)} "
            f"{pct(int(p.income_over), int(p.income) or 1):>6s} | "
            f"{money(p.cost_accept_fair)} {money(p.cost_accept_over)} {money(p.cost_penalty)}"
        )
    print("  `inc fair` is owed by all sixteen opponents regardless of their Limit -- structural.")
    print("  `inc over` needs a generous opponent -- it is the part that dies when the field tightens.")


def table_estimator(pools: dict[str, TeamGame], per_team: dict[str, list[TeamGame]], title: str) -> None:
    print(f"\n=== {title}: is there an estimator behind the Charge? ===")
    print(
        f"{'team':22s} {'corr(a,t)':>10s} {'corr log':>9s} {'distinct/item':>14s} "
        f"{'a=0 Games':>10s} {'b=0 Games':>10s} {'(0,0) Games':>12s}"
    )
    for team, p in pools.items():
        logs = [(math.log1p(a), math.log1p(t)) for a, t in p.pairs_at if a >= 0 and t >= 0]
        rounds = per_team[team]
        # Only multi-item Games can distinguish a constant from an estimator.
        multi = [r for r in rounds if r.items > 1 and r.charges_seen]
        distinct = sum(len(set(round(c, 2) for c in r.charges_seen)) for r in multi)
        n_items = sum(len(r.charges_seen) for r in multi)
        za = [r.game_id for r in rounds if r.zero_charge]
        zb = [r.game_id for r in rounds if r.zero_limit]
        zz = [r.game_id for r in rounds if r.dark]
        print(
            f"{team:22s} {pearson(p.pairs_at):10.2f} {pearson(logs):9.2f} "
            f"{(distinct / n_items if n_items else float('nan')):14.2f} "
            f"{len(za):10d} {len(zb):10d} {len(zz):12d}   {zz[:8]}"
        )
    print("  corr over items with a *bounded* t bracket only. ~1 = a real estimator;")
    print("  ~0 with `distinct/item` near 1/items = a constant that happens to sit somewhere.")
    print("  `a=0 Games`: Charged nothing anywhere -- forfeits all structural income.")
    print("  `b=0 Games`: the Limit let no euro through -- free when the field overcharges,")
    print("  ruinous when it does not (1.5a on every fair Charge).")


def table_per_game(per_team: dict[str, list[TeamGame]], game_ids: list[int]) -> None:
    print("\n=== per-Game net, and the a/t median that produced it ===")
    header = f"{'game':>5s}"
    for team in per_team:
        header += f" {team[:14]:>15s}"
    print(header)
    for gid in game_ids:
        line = f"{gid:5d}"
        for team, rounds in per_team.items():
            r = next((x for x in rounds if x.game_id == gid), None)
            if r is None:
                line += f" {'-':>15s}"
            else:
                med = q(r.a_over_t, .5)
                tag = "*" if r.dark else " "
                line += f" {r.net:10,.0f}/{'  nan' if math.isnan(med) else f'{med:5.2f}'}{tag}"
        print(line)
    print("  cell = net / median(a/t);  * = the (0,0) dark signature (no income, accepted nothing)")


def table_field(fields: list[Field], all_teams: list[str]) -> None:
    """The whole field per Game: how many teams are dark, and how many agree exactly.

    Two regime signatures live here and nowhere else.

    * **`a=0` count** -- teams Charging nothing. Games 1-6 are almost entirely this, which is
      why every "total" in the brief starts from a hole nobody was playing in.
    * **modal Charge** -- the largest number of teams submitting the *identical* Charge, to the
      cent, on one Line Item. A cluster of `0.00` is the default. A cluster at a round
      non-zero number (G22: nine teams at exactly 2,000.00 on a single Line Item whose true
      `t < 245.70`) is not a default -- it is the field converging on the same anchor, and
      everyone who paid it lost money to everyone who did not.
    """
    print("\n=== the field, per Game ===")
    print(
        f"{'game':>5s} {'items':>6s} {'t median':>10s} {'a=0 teams':>10s} {'b=0 teams':>10s} "
        f"{'(0,0)':>6s} {'modal Charge':>14s} {'teams':>6s} {'field a/t med':>14s}"
    )
    for fld in fields:
        rounds = [measure(fld, t) for t in all_teams]
        za = sum(1 for r in rounds if r.zero_charge)
        zb = sum(1 for r in rounds if r.zero_limit)
        zz = sum(1 for r in rounds if r.dark)
        ts = [fld.t(i) for i in fld.items]
        # the most-shared exact Charge on any single Line Item
        best = (0, 0.0)
        for index in fld.items:
            counts: dict[float, int] = {}
            for team in all_teams:
                a = fld.charges[index].get(team, INF)
                if a != INF and a > 0:
                    counts[round(a, 2)] = counts.get(round(a, 2), 0) + 1
            for value, n in counts.items():
                if n > best[0]:
                    best = (n, value)
        ratios = [r for rd in rounds for r in rd.a_over_t]
        print(
            f"{fld.game_id:5d} {len(fld.items):6d} {st.median(ts) if ts else 0:10,.0f} "
            f"{za:10d} {zb:10d} {zz:6d} {best[1]:14,.2f} {best[0]:6d} "
            f"{q(ratios, .5):14.2f}"
        )
    print("  `modal Charge` counts only non-zero Charges, so a default cluster shows in `a=0 teams`.")


def table_consistency(per_team: dict[str, list[TeamGame]], split: int) -> None:
    print("\n=== consistency: per-Game net distribution, and the regime split ===")
    print(
        f"{'team':22s} {'games':>6s} {'total':>12s} {'mean':>10s} {'stdev':>10s} "
        f"{'worst':>10s} {'pos%':>6s} | {'pre total':>11s} {'post total':>11s}"
    )
    for team, rounds in per_team.items():
        nets = [r.net for r in rounds]
        pre = sum(r.net for r in rounds if r.game_id < split)
        post = sum(r.net for r in rounds if r.game_id >= split)
        positive = sum(1 for n in nets if n > 0)
        print(
            f"{team:22s} {len(nets):6d} {money(sum(nets))} {st.fmean(nets):10,.0f} "
            f"{(st.pstdev(nets) if len(nets) > 1 else 0):10,.0f} {min(nets):10,.0f} "
            f"{pct(positive, len(nets)):>6s} | {pre:11,.0f} {post:11,.0f}"
        )


# -------------------------------------------------------------------------- verification


def verify_nets(team_names: list[str], game_ids: list[int]) -> None:
    """Recompute every per-Game net from the rows and compare against `/matrix`.

    The published table in the brief is not trusted: `identity_net` is arithmetic over the
    fetched rows and cannot be misattributed, whereas a `/matrix` cell can only be located
    by Game id and only for the trailing twenty-Game window.
    """
    try:
        table = matrix()
    except (AmbiguousMatrix, RuntimeError) as exc:
        print(f"WARNING: /matrix unusable ({exc}); identity only")
        table = {}
    print("\n=== net verification: rows vs leaderboard cell ===")
    print(f"{'team':22s} " + " ".join(f"G{g}" for g in game_ids))
    for team in team_names:
        cells = []
        total = 0.0
        for gid in game_ids:
            got = identity_net(transactions(team, gid), team)
            total += got
            want = table.get(team, {}).get(gid)
            flag = "" if want is None or abs(got - want) <= 0.01 else "!"
            cells.append(f"{got:,.0f}{flag}")
        print(f"{team:22s} " + " ".join(cells) + f"  total {total:,.0f}")
    print("  `!` = the rows disagree with the published cell. Blank = agrees, or not published.")


# -------------------------------------------------------------------------- adopt-list


@dataclass
class AdoptResult:
    label: str
    total: float
    per_game: dict[int, float]

    @property
    def games(self) -> int:
        return len(self.per_game)


def donor_submission(
    snap,
    donor: str,
    *,
    take_charge: bool = True,
    take_limit: bool = True,
    charge_scale: float = 1.0,
) -> dict[int, tuple[float, float]]:
    """`(a, b)` per Line Item, mixing the donor's numbers with ours.

    `take_charge=False` keeps our real Charge; `take_limit=False` keeps our real Limit. The
    two hybrids are the whole point: they say whether the donor's edge is on the Issuer side
    or the Reviewer side, which the joint copy cannot separate.

    `charge_scale` multiplies the donor's Charge. Setting it to the ratio of the two median
    `a/t` values re-levels the donor's Charge onto *our* aggressiveness, so what remains of
    the gain is attributable to the *shape* of their estimate rather than to its level. That
    is the only clean way to ask the question: scaling *our* Charge cannot answer it, because
    our unrecoverable Charges (`inf`) stay unrecoverable under any multiplier and so the
    scale test on our own numbers is a lower bound, not an estimate.
    """
    ours = our_actual_submission(snap)
    out: dict[int, tuple[float, float]] = {}
    for index in snap.line_items:
        our_a, our_b = ours[index]
        a = snap.charges[index].get(donor, INF) if take_charge else our_a
        if take_charge and a != INF:
            a *= charge_scale
        b = snap.limit_point(index, donor) if take_limit else our_b
        out[index] = (a, b)
    return out


def unrecoverable_floor(snap, index: int) -> float:
    """The smallest Charge of ours consistent with "every reviewer rejected it and paid 0".

    An unrecoverable Charge is not a missing value; it is a censored one. Every one of the
    sixteen reviewers rejected it *and* owed nothing, so it sat above every reviewer's Limit
    and above `t`. The smallest number satisfying that is just above the largest Limit in the
    field. Using it makes the scale test *optimistic* where `inf` makes it pessimistic, and
    the pair brackets the answer instead of asserting one side of it.
    """
    highest = max(
        (snap.limit_point(index, team) for team in snap.opponents),
        default=0.0,
    )
    t_lo, t_hi = snap.fair_brackets[index]
    floor = max(highest, t_lo if t_hi == INF else t_hi)
    return math.nextafter(floor, INF) if floor > 0 else 0.0


def scaled_submission(
    snap, k: float, *, which: str, floor_unrecoverable: bool = False
) -> dict[int, tuple[float, float]]:
    """Our own submission with the Charge (or the Limit) multiplied by `k`.

    This is the control that separates the two explanations for eyay's edge. If "charge
    `0.75 t̂` instead of `1.0 t̂`" is the whole story, then scaling *our* Charge down by the
    ratio of the medians captures most of the gain without importing their estimator; if it
    does not, the gain really is estimator quality and cannot be had with a multiplier.
    """
    ours = our_actual_submission(snap)
    out = {}
    for index, (a, b) in ours.items():
        if which == "charge":
            if a == INF and floor_unrecoverable:
                a = unrecoverable_floor(snap, index)
            out[index] = (a if a == INF else a * k, b)
        else:
            out[index] = (a, b * k)
    return out


def adopt_study(game_ids: list[int], donors: list[str], *, us: str = US) -> list[AdoptResult]:
    snaps = []
    for gid in game_ids:
        try:
            snaps.append(snapshot(gid, us))
        except UnreconstructableGame as exc:
            print(f"  skipping G{gid}: {exc}")
    results: list[AdoptResult] = []

    def run(label: str, builder) -> None:
        per = {s.game_id: replay(s, builder(s)).net for s in snaps}
        results.append(AdoptResult(label, sum(per.values()), per))

    run("us (actual)", lambda s: our_actual_submission(s))
    for donor in donors:
        if donor == us:
            continue
        run(f"{donor}: a+b", lambda s, d=donor: donor_submission(s, d))
        run(f"{donor}: a only (our b)", lambda s, d=donor: donor_submission(s, d, take_limit=False))
        run(f"{donor}: b only (our a)", lambda s, d=donor: donor_submission(s, d, take_charge=False))
    # Re-level the strongest donor onto our own aggressiveness: if the gain survives, the
    # edge is estimate *shape*; if it evaporates, the edge was only the Charge multiplier.
    for donor in donors[:2]:
        for k in (0.75, 1.0, 1.33, 1.5):
            run(
                f"{donor}: a x {k:.2f} (our b)",
                lambda s, d=donor, k=k: donor_submission(s, d, take_limit=False, charge_scale=k),
            )
    for k in (0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.1, 1.25):
        run(f"our a x {k:.2f} (our b)", lambda s, k=k: scaled_submission(s, k, which="charge"))
    for k in (0.5, 0.7, 0.8, 1.0):
        run(
            f"our a x {k:.2f} unrec@floor",
            lambda s, k=k: scaled_submission(s, k, which="charge", floor_unrecoverable=True),
        )
    for k in (0.5, 0.75, 1.25, 1.5, 2.0, 3.0):
        run(f"our b x {k:.2f} (our a)", lambda s, k=k: scaled_submission(s, k, which="limit"))
    return results


def print_adopt(results: list[AdoptResult], *, per_game: bool = False) -> None:
    base = next(r for r in results if r.label == "us (actual)")
    print(f"\n=== adopt-list: our net on {base.games} usable Games, replayed ===")
    print(f"{'submission':34s} {'total':>13s} {'delta vs us':>13s} {'per Game':>11s}  verdict")
    ranked = sorted(results, key=lambda r: -r.total)
    for r in ranked:
        delta = r.total - base.total
        floor = NOISE_FLOOR * r.games / 18.0
        if r.label == "us (actual)":
            verdict = "baseline"
        elif abs(delta) < floor:
            verdict = f"inside noise (+-{floor:,.0f})"
        else:
            verdict = "ADOPT" if delta > 0 else "reject"
        print(
            f"{r.label:34s} {r.total:13,.0f} {delta:13,.0f} "
            f"{delta / max(r.games, 1):11,.0f}  {verdict}"
        )
    print(f"  noise floor scaled from 26,622 / 18 Games = {NOISE_FLOOR / 18:,.0f} per Game.")
    if per_game:
        print("\n  per-Game detail (net):")
        gids = sorted(base.per_game)
        print("    " + f"{'submission':34s}" + "".join(f"{g:>10d}" for g in gids))
        for r in ranked:
            print("    " + f"{r.label:34s}" + "".join(f"{r.per_game[g]:10,.0f}" for g in gids))


# --------------------------------------------------------------------------------- cli


def parse_games(spec: str) -> list[int]:
    if spec == "all":
        return completed_games()
    out: list[int] = []
    for chunk in spec.split(","):
        start, _, end = chunk.partition("-")
        out += list(range(int(start), int(end or start) + 1))
    return sorted(set(out))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teams", default=",".join(DEFAULT_TEAMS), help="comma separated")
    parser.add_argument("--games", default="all")
    parser.add_argument("--split", type=int, default=15, help="first Game of the second regime")
    parser.add_argument("--control", action="store_true", help="add the worst team as a control")
    parser.add_argument("--per-game", action="store_true")
    parser.add_argument("--adopt", action="store_true", help="replay donors on our Games")
    parser.add_argument("--verify-nets", action="store_true")
    parser.add_argument("--no-tables", action="store_true")
    args = parser.parse_args()

    all_teams = teams()
    game_ids = [g for g in parse_games(args.games) if g in set(completed_games())]
    wanted = [t.strip() for t in args.teams.split(",") if t.strip()]
    unknown = [t for t in wanted if t not in all_teams]
    if unknown:
        raise SystemExit(f"unknown team(s) {unknown}; known: {all_teams}")

    if args.control:
        totals = {t: sum(identity_net(transactions(t, g), t) for g in game_ids) for t in all_teams}
        worst = min(totals, key=lambda t: totals[t])
        if worst not in wanted:
            wanted.append(worst)
        print(f"control (worst total over these Games): {worst} at {totals[worst]:,.0f}")

    if args.verify_nets:
        verify_nets(wanted, game_ids)

    per_team: dict[str, list[TeamGame]] = {t: [] for t in wanted}
    fields: list[Field] = []
    for gid in game_ids:
        fld = load_field(gid, all_teams)
        fields.append(fld)
        for team in wanted:
            per_team[team].append(measure(fld, team))

    if not args.no_tables:
        for label, keep in (
            ("ALL Games", lambda g: True),
            (f"PRE regime (G < {args.split})", lambda g: g < args.split),
            (f"POST regime (G >= {args.split})", lambda g: g >= args.split),
        ):
            subset = {t: [r for r in rs if keep(r.game_id)] for t, rs in per_team.items()}
            if not any(subset.values()):
                continue
            pools = {t: pool(rs) for t, rs in subset.items()}
            table_ratios(pools, label)
            table_accept(pools, label)
            table_money(pools, label)
            table_estimator(pools, subset, label)
        table_consistency(per_team, args.split)
        if args.per_game:
            table_per_game(per_team, game_ids)
            table_field(fields, all_teams)

    if args.adopt:
        usable = usable_games(game_ids)
        skipped = sorted(set(game_ids) - set(usable))
        if skipped:
            print(f"\nexcluded from the replay (do not reconstruct): {skipped}")
        donors = [t for t in wanted if t != US]
        # The whole window, then each regime on its own. A verdict that holds over Games
        # 1-26 but not over the current regime is a verdict about a pipeline we already
        # replaced, and adopting on the strength of it would be adopting into the past.
        windows = [("all Games", usable)]
        pre = [g for g in usable if g < args.split]
        post = [g for g in usable if g >= args.split]
        if pre and post:
            windows += [(f"PRE (G < {args.split})", pre), (f"POST (G >= {args.split})", post)]
        for label, window in windows:
            print(f"\n----- window: {label}")
            print_adopt(adopt_study(window, donors), per_game=args.per_game)


if __name__ == "__main__":
    main()
