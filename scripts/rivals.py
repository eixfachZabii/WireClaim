"""Reverse-engineer each rival's *mechanism* from the settled record -- and price stealing it.

`scripts/field_study.py` answered "what do the profitable teams do differently, in ratios".
This answers the next question: **how does each team actually make its money**, and which
single rule of theirs is worth euros to us. It adds five measurements that study does not
make, and one correction to it.

The correction first, because it changes a headline
---------------------------------------------------
`2,000.00` is *not* the field's favourite round number. It is the **payment Cap**.

A Charge is recovered from `amount`, and `amount` on an accepted row is `min(a, c)`, not `a`.
On three Line Items (G22 #1, G28 #7, G29 #2) nine, six and thirteen *different* issuers were
each paid exactly `2000.00` -- and on two of them we know our own Charge from `var/decisions`:
**2,933.51 (G28 #7) and 4,649.21 (G29 #2), both paid 2,000.00**. So those "2,000.00 Charges"
are truncations of unknown larger Charges, and every team that looks like it anchored on 2,000
merely charged *something above it*. Once cap-censored rows are removed, exact-round Charges
above 500 number **0 for eyay, error404 ai, TakeTheMoneyAndRun, OPUSMOPUS and Codacabana**.
See `cap_report()` and `anchor_report()`.

The Cap model that survives all settled Games (`--cap`):

    c = max(4t, 2000)

* **Floor.** Items with `t < 60` and `t < 246` paid out exactly `2,000.00`, which cannot be
  `4t`. Our own 4,649.21 was truncated to 2,000.00, so `c = 2000` *exactly* there -- not
  merely `>= 2000`.
* **Slope.** Ties at *non-round* values pin `4t`: G19 #4 four issuers at `3,848.48`
  (`/4 = 962.12`, inside the bracket `[854.5, 1242.0)`) and G27 #3 three issuers at
  `12,000.00` (`/4 = 3000.00`, inside `[3000.0, 3022.2)`). A tie to the cent at a non-round
  number is not independent estimation.
* **No counterexample.** No accepted row with a bounded `t` exceeds `max(4*t_hi, 2000)`.

Two consequences that matter more than the Cap itself:

1. **Any Charge above `max(4t̂, 2000)` is strictly wasteful** (R5/R6c): it cannot increase what
   a reviewer pays and can only reduce who accepts.
2. **Reconstruction is contaminated on cap-censored items.** A Charge recovered only from
   accepted rows at `>= 2000` is a *lower bound*, and a rejection of such an issuer yields a
   *wrong* `b_hi` for the reviewer. `charge_status()` labels every recovered Charge so the
   contaminated ones can be excluded rather than quietly believed.

What is measured here that `field_study` does not measure
--------------------------------------------------------
* `--anchor`   round-number anchoring with cap-censoring removed, and what anchoring earned.
* `--review`   reviewer skill in **euros**: excess cost against an oracle Limit `b = t`, split
               into wrongful-rejection penalty and over-payment. Two different errors.
* `--fountain` the pairwise Overcharge flow matrix: who hands money to the field, who
               collects it, and from whom.
* `--breaks`   a changepoint search per team over net / median `a/t` / accept rate / Charge
               dispersion, so "they changed at Game X" is a measurement, not a story.
* `--cap`      the Cap evidence above, plus who charges past it and what it costs them.
* `--steal`    a cap-aware replay of donor submissions *and of inferred rules* on our Games.
               `replay_payoffs.replay` treats `c` as infinite, which is now known to be wrong;
               `replay_capped()` re-derives `c` and self-checks against the published net for
               every Game (`--verify`).

Everything printed under "measured" is arithmetic over published Transactions. Verdicts are
in euros and are labelled against the noise floor (26,622 over 18 Games, scaled `sqrt(n/18)`).

Usage
-----
    PYTHONPATH=. python scripts/rivals.py --all
    PYTHONPATH=. python scripts/rivals.py --cap --verify
    PYTHONPATH=. python scripts/rivals.py --anchor --review --fountain --games 19-30
    PYTHONPATH=. python scripts/rivals.py --steal --games 19-30
    PYTHONPATH=. python scripts/rivals.py --breaks --teams eyay,Codacabana
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics as st
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from invert_fair_values import brackets  # noqa: E402
from pull_transactions import (  # noqa: E402
    completed_games,
    identity_net,
    teams,
    transactions,
)
from replay_payoffs import (  # noqa: E402
    GameSnapshot,
    UnreconstructableGame,
    our_actual_submission,
    snapshot,
)
from field_study import unrecoverable_floor  # noqa: E402

INF = math.inf
US = "Bin busy"

#: The measured floor over eighteen Games (CLAUDE.md). Scaled as sqrt(n/18): a sum of n
#: independent per-Game nets has standard deviation growing like sqrt(n), not like n.
NOISE_FLOOR_18 = 26_622.0

#: The Cap's absolute floor, established twice from our own known Charges (see module docs).
CAP_FLOOR = 2000.0

#: The eight teams the brief names, plus the control.
DEFAULT_TEAMS = (
    "eyay",
    "TakeTheMoneyAndRun",
    "Codacabana",
    "OPUSMOPUS",
    "error404 ai",
    "Nullpointer Naan",
    "makalu",
    US,
)


def noise_floor(n_games: int) -> float:
    """The euro band inside which a replay delta is not evidence of anything."""
    return NOISE_FLOOR_18 * math.sqrt(max(n_games, 0) / 18.0)


def cap_of(fair_value: float) -> float:
    """`c = max(4t, 2000)` -- the Cap model that fits every settled row (see `cap_report`)."""
    return max(4.0 * fair_value, CAP_FLOOR)


# --------------------------------------------------------------------------- the record


@dataclass
class Book:
    """One settled Game, reconstructed for every team, with the Cap taken seriously.

    `charge[item][team]` is the recovered Charge (`inf` when no reviewer ever paid a cent) and
    `status[item][team]` says how much that number can be trusted:

    ``exact``     witnessed by a wrongful rejection -- pays the full `a`, so `a` is exact and
                  provably `<= t`;
    ``exact-acc`` recovered from an accepted row below `CAP_FLOOR`, where the Cap cannot bind;
    ``capped``    recovered from accepted rows at `>= CAP_FLOOR` with a corroborating tie --
                  a **lower bound**, the true Charge is unknown and larger;
    ``uncapped?`` accepted at `>= CAP_FLOOR` with no tie: exact unless the Cap bound silently;
    ``zero``      accepted at 0 -- the issuer charged nothing;
    ``censored``  every reviewer rejected and owed nothing: `a > t` and `a > max b`.
    """

    game_id: int
    team_names: tuple[str, ...]
    items: tuple[int, ...]
    fair: dict[int, tuple[float, float]]
    charge: dict[int, dict[str, float]]
    status: dict[int, dict[str, str]]
    limit: dict[int, dict[str, tuple[float, float]]]
    rows: dict[str, list[dict]]

    # ---- fair value

    def t(self, index: int) -> float:
        lo, hi = self.fair[index]
        return lo if hi == INF else (lo + hi) / 2.0

    def t_bounded(self, index: int) -> bool:
        return self.fair[index][1] != INF

    def cap(self, index: int) -> float:
        """`c` for this item under the fitted model, floored by what was actually paid."""
        observed = max(
            (
                row["amount"]
                for rows in self.rows.values()
                for row in rows
                if row["accepted"] and row["amount"] > 0 and row["line_item_index"] == index
            ),
            default=0.0,
        )
        return max(cap_of(self.t(index)), observed)

    # ---- limits

    def b(self, index: int, team: str) -> float:
        lo, hi = self.limit[index][team]
        return lo if hi == INF else (lo + hi) / 2.0

    def trustworthy(self, index: int, team: str) -> bool:
        return self.status[index][team] in ("exact", "exact-acc", "zero")


def plausible_cap(amount: float, bracket: tuple[float, float]) -> bool:
    """Could `c = amount` on an item whose Fair Value lies in `bracket`?

    `c = max(4t, 2000)`, so `c = amount` needs either `amount = 2000` with `t <= 500`, or
    `amount = 4t` with `amount/4` inside the bracket. This is what separates a Cap from a
    coincidence: G10 #3 has two issuers tied at `4,500.00` on an item worth **at least**
    7,225, and `4500/4 = 1125` is far below `t_lo`, so `c` cannot be 4,500 -- two teams simply
    both charged a round 4,500 and were paid it in full.
    """
    lo, hi = bracket
    if abs(amount - CAP_FLOOR) < 0.005:
        return lo <= CAP_FLOOR / 4.0
    return lo <= amount / 4.0 < hi


def load_book(game_id: int, team_names: list[str]) -> Book:
    rows = {team: transactions(team, game_id) for team in team_names}
    fair = brackets(game_id, team_names)
    items = tuple(sorted(fair))

    # Which (item, amount) pairs several issuers share at a value the Cap could actually take?
    # A tie to the cent at such a value is the observable signature of truncation.
    ties: dict[tuple[int, float], set[str]] = collections.defaultdict(set)
    for team in team_names:
        for row in rows[team]:
            if (
                row["issuer"] == team
                and row["accepted"]
                and row["amount"] >= CAP_FLOOR - 0.005
                and plausible_cap(round(row["amount"], 2), fair[row["line_item_index"]])
            ):
                ties[(row["line_item_index"], round(row["amount"], 2))].add(team)

    charge: dict[int, dict[str, float]] = {i: {} for i in items}
    status: dict[int, dict[str, str]] = {i: {} for i in items}
    for team in team_names:
        paid: dict[int, float] = {}
        witnessed: set[int] = set()  # a wrongful rejection proves the Charge exactly
        accepted_zero: set[int] = set()
        for row in rows[team]:
            if row["issuer"] != team:
                continue
            index = row["line_item_index"]
            if row["amount"] > 0:
                paid[index] = max(paid.get(index, 0.0), row["amount"])
                if not row["accepted"]:
                    witnessed.add(index)
            elif row["accepted"]:
                accepted_zero.add(index)
        for index in items:
            if index in paid:
                value = paid[index]
                charge[index][team] = value
                if index in witnessed:
                    status[index][team] = "exact"
                elif value < CAP_FLOOR - 0.005:
                    status[index][team] = "exact-acc"
                elif len(ties[(index, round(value, 2))]) >= 2:
                    status[index][team] = "capped"
                else:
                    status[index][team] = "uncapped?"
            elif index in accepted_zero:
                charge[index][team] = 0.0
                status[index][team] = "zero"
            else:
                charge[index][team] = INF
                status[index][team] = "censored"

    limit: dict[int, dict[str, tuple[float, float]]] = {
        i: {t: (0.0, INF) for t in team_names} for i in items
    }
    for team in team_names:
        for row in rows[team]:
            if row["reviewer"] != team:
                continue
            index = row["line_item_index"]
            issuer = row["issuer"]
            lo, hi = limit[index][team]
            if row["accepted"]:
                lo = max(lo, row["amount"])
            elif charge[index].get(issuer, INF) != INF:
                # A rejection bounds `b` above only if the issuer's Charge is known exactly.
                # On a cap-censored issuer the recovered value is a lower bound, so using it
                # here would invent a *tighter* Limit bracket than the record supports.
                if status[index][issuer] != "capped":
                    hi = min(hi, charge[index][issuer])
            limit[index][team] = (lo, hi)

    return Book(
        game_id=game_id,
        team_names=tuple(team_names),
        items=items,
        fair=dict(fair),
        charge=charge,
        status=status,
        limit=limit,
        rows=rows,
    )


def load_books(game_ids: list[int], team_names: list[str]) -> list[Book]:
    return [load_book(g, team_names) for g in game_ids]


# ------------------------------------------------------------------------- measurements


@dataclass
class Stat:
    """Per-team, per-window accumulators. Every field is either euros or a count."""

    team: str
    games: set[int] = dc_field(default_factory=set)

    # issuer side
    n_items: int = 0
    n_exact: int = 0
    n_capped: int = 0
    n_censored: int = 0
    n_zero: int = 0
    a_over_t: list[float] = dc_field(default_factory=list)
    pairs_at: list[tuple[float, float]] = dc_field(default_factory=list)
    n_fair: int = 0
    n_over: int = 0
    n_above_cap: int = 0  # charged above `c` -- strictly wasteful
    round_charges: int = 0
    round_income: float = 0.0
    other_income: float = 0.0
    round_items: int = 0
    other_items: int = 0
    #: `sum over opponents of t` for the items in each bucket -- the honest ceiling on that
    #: bucket, so `income / ceiling` compares anchored and priced Charges on the same scale.
    #: Without it the comparison is meaningless: round numbers land on *big* items, so income
    #: per item is high for a reason that has nothing to do with anchoring.
    round_ceiling: float = 0.0
    other_ceiling: float = 0.0
    income_fair: float = 0.0
    income_over: float = 0.0
    t_available: float = 0.0  # sum of `t` over items, times opponents: the honest ceiling

    # reviewer side
    seen_fair: int = 0
    acc_fair: int = 0
    seen_over: int = 0
    acc_over: int = 0
    pay_fair: float = 0.0
    pay_over: float = 0.0
    penalty: float = 0.0

    net: float = 0.0
    per_game: dict[int, float] = dc_field(default_factory=dict)
    per_game_a_over_t: dict[int, list[float]] = dc_field(default_factory=dict)
    #: `(accepted fair, seen fair, accepted Overcharge, seen Overcharge)` per Game, counting
    #: only rows where the issuer Charged something. A Charge of `0` is accepted by everyone
    #: including a team at `b = 0`, so leaving those rows in makes the early Games -- when a
    #: third of the field Charged nothing -- look like an era of reckless generosity. That
    #: artefact put a spurious "break at Game 4" on every single team.
    per_game_accept: dict[int, tuple[int, int, int, int]] = dc_field(default_factory=dict)
    per_game_charges: dict[int, list[float]] = dc_field(default_factory=dict)

    # ---- derived, all in euros

    @property
    def income(self) -> float:
        return self.income_fair + self.income_over

    @property
    def cost(self) -> float:
        return self.pay_fair + self.pay_over + self.penalty

    @property
    def excess_cost(self) -> float:
        """What a *perfect* Limit `b = t` would have saved: the reviewer's whole error bill.

        With `b = t` every fair Charge is accepted (cost `a`, which was owed anyway) and every
        Overcharge is rejected (cost 0). So the unavoidable cost is `pay_fair + penalty/1.5`
        and everything else is error:

            excess = penalty/3 * 1  (the 0.5a lawyer fee on each wrongful rejection)
                   + pay_over       (euros handed over above Fair Value)
        """
        return self.penalty / 3.0 + self.pay_over

    @property
    def forgone_income(self) -> float:
        """Structural income left on the table: `sum over opponents of t` minus what was earned.

        `a = t` collects `t` from every opponent whether they accept or not (R1), so this is the
        honest ceiling. Negative values are possible and mean Overcharges more than covered the
        gap -- which is borrowed money, not skill.
        """
        return self.t_available - self.income


def is_round(value: float) -> bool:
    """An exact multiple of 100 above 500 -- the anchoring signature the brief asks about."""
    return value > 500 and abs(value - round(value / 100.0) * 100.0) < 0.005


def measure(book: Book, team: str, stat: Stat) -> None:
    stat.games.add(book.game_id)
    stat.per_game_a_over_t.setdefault(book.game_id, [])
    stat.per_game_charges.setdefault(book.game_id, [])
    opponents = len(book.team_names) - 1

    item_income: dict[int, float] = collections.defaultdict(float)
    for row in book.rows[team]:
        if row["issuer"] == team and row["amount"] > 0:
            item_income[row["line_item_index"]] += row["amount"]

    for index in book.items:
        a = book.charge[index][team]
        state = book.status[index][team]
        t = book.t(index)
        stat.n_items += 1
        stat.t_available += t * (len(book.team_names) - 1)
        if state == "censored":
            stat.n_censored += 1
            continue
        if state == "capped":
            stat.n_capped += 1
            stat.n_above_cap += 1
            stat.n_over += 1  # a >= 2000 > c/... : a capped Charge is always above `t`
            continue
        stat.n_exact += 1
        if a == 0.0:
            stat.n_zero += 1
        if a <= t:
            stat.n_fair += 1
        else:
            stat.n_over += 1
            if a > book.cap(index) + 0.005:
                stat.n_above_cap += 1
        if t > 0:
            stat.a_over_t.append(a / t)
            stat.per_game_a_over_t[book.game_id].append(a / t)
        if book.t_bounded(index):
            stat.pairs_at.append((a, t))
        stat.per_game_charges[book.game_id].append(a)
        if is_round(a):
            stat.round_charges += 1
            stat.round_items += 1
            stat.round_income += item_income[index]
            stat.round_ceiling += t * opponents
        else:
            stat.other_items += 1
            stat.other_income += item_income[index]
            stat.other_ceiling += t * opponents

    game_acc = [0, 0, 0, 0]  # accepted fair, seen fair, accepted over, seen over
    for row in book.rows[team]:
        index = row["line_item_index"]
        t = book.t(index)
        if row["issuer"] == team:
            if row["amount"] > 0:
                if row["amount"] <= t:
                    stat.income_fair += row["amount"]
                else:
                    stat.income_over += row["amount"]
        if row["reviewer"] == team:
            a = book.charge[index].get(row["issuer"], INF)
            fair = a != INF and book.status[index][row["issuer"]] != "capped" and a <= t
            seen += 1
            acc += 1 if row["accepted"] else 0
            if fair:
                stat.seen_fair += 1
                if row["accepted"]:
                    stat.acc_fair += 1
                    stat.pay_fair += row["amount"]
                else:
                    stat.penalty += 1.5 * row["amount"]
            else:
                stat.seen_over += 1
                if row["accepted"]:
                    stat.acc_over += 1
                    stat.pay_over += row["amount"]
    stat.per_game_accept[book.game_id] = (acc, seen)
    net = identity_net(book.rows[team], team)
    stat.net += net
    stat.per_game[book.game_id] = net


def measure_all(books: list[Book], team_names: list[str]) -> dict[str, Stat]:
    stats = {team: Stat(team=team) for team in team_names}
    for book in books:
        for team in team_names:
            measure(book, team, stats[team])
    return stats


# ------------------------------------------------------------------------------ helpers


def q(values, p: float) -> float:
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
    return float("nan") if dx == 0 or dy == 0 else num / (dx * dy)


def spearman(pairs: list[tuple[float, float]]) -> float:
    """Rank correlation -- immune to the one huge item that can carry a Pearson number."""
    if len(pairs) < 3:
        return float("nan")

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda k: values[k])
        out = [0.0] * len(values)
        k = 0
        while k < len(order):
            j = k
            while j + 1 < len(order) and values[order[j + 1]] == values[order[k]]:
                j += 1
            mean_rank = (k + j) / 2.0
            for m in range(k, j + 1):
                out[order[m]] = mean_rank
            k = j + 1
        return out

    xs = ranks([x for x, _ in pairs])
    ys = ranks([y for _, y in pairs])
    return pearson(list(zip(xs, ys)))


def pct(num: float, den: float) -> str:
    return "    n/a" if not den else f"{100.0 * num / den:6.1f}%"


def money(value: float) -> str:
    return f"{value:12,.0f}"


def parse_games(spec: str) -> list[int]:
    done = set(completed_games())
    if spec == "all":
        return sorted(done)
    out: list[int] = []
    for chunk in spec.split(","):
        start, _, end = chunk.partition("-")
        out += list(range(int(start), int(end or start) + 1))
    return [g for g in sorted(set(out)) if g in done]


# ------------------------------------------------------------------- Q1 estimate/anchor


def anchor_report(stats: dict[str, Stat], order: list[str], title: str) -> None:
    print(f"\n=== {title}: estimator or anchor? ===")
    print(
        f"{'team':22s} {'items':>6s} {'corr(a,t)':>10s} {'rank corr':>10s} {'a/t med':>8s} "
        f"{'fair%':>7s} {'round>500':>10s} {'collect% round':>15s} {'collect% other':>15s}"
    )
    for team in order:
        s = stats[team]
        n = s.n_fair + s.n_over
        print(
            f"{team:22s} {s.n_items:6d} {pearson(s.pairs_at):10.2f} {spearman(s.pairs_at):10.2f} "
            f"{q(s.a_over_t, 0.5):8.2f} {pct(s.n_fair, n):>7s} {s.round_charges:10d} "
            f"{pct(s.round_income, s.round_ceiling):>15s} "
            f"{pct(s.other_income, s.other_ceiling):>15s}"
        )
    print("  corr over items with a bounded `t` and an *uncensored* Charge only.")
    print("  `round>500` = exact multiples of 100 above 500, cap-truncated rows removed.")
    print("  `collect%` = income earned / the honest ceiling (`sum over opponents of t`) on the")
    print("  same items. 100 % is what `a = t` collects; anchoring pays iff round beats other.")


# ---------------------------------------------------------------- Q2 income composition


def income_report(stats: dict[str, Stat], order: list[str], title: str) -> None:
    print(f"\n=== {title}: where the income comes from ===")
    print(
        f"{'team':22s} {'net':>12s} | {'inc fair':>12s} {'inc over':>12s} {'over%':>7s} "
        f"{'ceiling':>12s} {'forgone':>12s} | {'excess cost':>12s}"
    )
    for team in order:
        s = stats[team]
        print(
            f"{team:22s} {money(s.net)} | {money(s.income_fair)} {money(s.income_over)} "
            f"{pct(s.income_over, s.income):>7s} {money(s.t_available)} "
            f"{money(s.forgone_income)} | {money(s.excess_cost)}"
        )
    print("  `inc fair` is owed by every opponent whatever their Limit -- structural income.")
    print("  `inc over` is borrowed: it needs a generous opponent and dies when the field tightens.")
    print("  `ceiling` = sum over items and opponents of the true `t`, i.e. what `a = t` collects.")
    print("  `excess cost` = 0.5a on every wrongful rejection + every euro paid above Fair Value:")
    print("  the reviewer's entire error bill against a perfect Limit `b = t`.")


# ------------------------------------------------------------------ Q3 reviewer skill


def review_report(stats: dict[str, Stat], order: list[str], title: str) -> None:
    print(f"\n=== {title}: do they discriminate as reviewers? ===")
    print(
        f"{'team':22s} {'accept%':>8s} {'fair acc%':>10s} {'over acc%':>10s} {'J':>6s} | "
        f"{'penalty':>12s} {'pay over':>12s} {'excess':>12s} {'EUR/row':>8s}"
    )
    for team in order:
        s = stats[team]
        seen = s.seen_fair + s.seen_over
        acc = s.acc_fair + s.acc_over
        j = (
            (s.acc_fair / s.seen_fair - s.acc_over / s.seen_over)
            if s.seen_fair and s.seen_over
            else float("nan")
        )
        print(
            f"{team:22s} {pct(acc, seen):>8s} {pct(s.acc_fair, s.seen_fair):>10s} "
            f"{pct(s.acc_over, s.seen_over):>10s} {j:6.2f} | {money(s.penalty)} "
            f"{money(s.pay_over)} {money(s.excess_cost)} "
            f"{(s.excess_cost / seen if seen else float('nan')):8,.0f}"
        )
    print("  `J` = fair-accept rate minus Overcharge-accept rate (Youden): the discrimination the")
    print("  headline accept rate hides. J = 0 is a coin that ignores the Charge; J = 1 is an oracle.")
    print("  `EUR/row` is the euro cost of imperfect discrimination per reviewed Transaction --")
    print("  the only version of this table that can be compared across Games of different size.")


# ------------------------------------------------------------ Q4 fountains and farmers


@dataclass
class Flow:
    """Euros that moved because a reviewer accepted an Overcharge, or wrongfully rejected."""

    over: dict[tuple[str, str], float] = dc_field(default_factory=lambda: collections.defaultdict(float))
    fair: dict[tuple[str, str], float] = dc_field(default_factory=lambda: collections.defaultdict(float))
    penalty: dict[tuple[str, str], float] = dc_field(default_factory=lambda: collections.defaultdict(float))


def flows(books: list[Book]) -> Flow:
    flow = Flow()
    for book in books:
        for team in book.team_names:
            for row in book.rows[team]:
                if row["issuer"] != team:
                    continue
                key = (row["issuer"], row["reviewer"])
                t = book.t(row["line_item_index"])
                if row["accepted"] and row["amount"] > 0:
                    if row["amount"] > t:
                        flow.over[key] += row["amount"]
                    else:
                        flow.fair[key] += row["amount"]
                elif not row["accepted"] and row["amount"] > 0:
                    flow.penalty[key] += 0.5 * row["amount"]
    return flow


def fountain_report(books: list[Book], stats: dict[str, Stat], title: str) -> None:
    flow = flows(books)
    paid_out: dict[str, float] = collections.defaultdict(float)
    burned: dict[str, float] = collections.defaultdict(float)
    harvested: dict[str, float] = collections.defaultdict(float)
    for (issuer, reviewer), value in flow.over.items():
        paid_out[reviewer] += value
        harvested[issuer] += value
    for (_, reviewer), value in flow.penalty.items():
        burned[reviewer] += value

    print(f"\n=== {title}: money fountains and the teams farming them ===")
    print(
        f"{'team':22s} {'over paid out':>14s} {'lawyer burned':>14s} {'total gift':>12s} | "
        f"{'over harvested':>15s} {'harvest/gift':>13s}"
    )
    ranked = sorted(
        stats, key=lambda t: -(paid_out[t] + burned[t])
    )
    for team in ranked:
        gift = paid_out[team] + burned[team]
        take = harvested[team]
        print(
            f"{team:22s} {money(paid_out[team])[2:]:>14s} {money(burned[team])[2:]:>14s} "
            f"{money(gift)} | {money(take)[2:]:>15s} "
            f"{(take / gift if gift else float('inf')):13.2f}"
        )
    print("  `over paid out` = euros this team handed over above Fair Value (pure loss).")
    print("  `lawyer burned` = the 0.5a it destroyed by wrongfully rejecting (nobody receives it).")
    print("  `total gift` is the euros the field extracted from it; `over harvested` what it took.")

    print("\n  top Overcharge flows (issuer -> reviewer), euros:")
    for (issuer, reviewer), value in sorted(flow.over.items(), key=lambda kv: -kv[1])[:15]:
        print(f"    {issuer:22s} -> {reviewer:22s} {value:12,.0f}")
    print("\n  who each top farmer took it from:")
    for farmer in sorted(harvested, key=lambda t: -harvested[t])[:4]:
        parts = sorted(
            ((rev, v) for (iss, rev), v in flow.over.items() if iss == farmer),
            key=lambda kv: -kv[1],
        )[:5]
        detail = ", ".join(f"{rev} {v:,.0f}" for rev, v in parts)
        print(f"    {farmer:22s} {harvested[farmer]:12,.0f}  from: {detail}")


# --------------------------------------------------------------------- Q5 strategy break


def changepoint(series: list[tuple[int, float]], min_side: int = 3) -> tuple[int, float, float, float]:
    """The split that most separates the series into two levels.

    Returns `(game_id, mean_before, mean_after, |gap| / spread)`. The last number is the gap in
    units of the series' own standard deviation, so it is comparable across metrics; anything
    below ~1 is not a break, it is noise wearing a break's clothes.
    """
    values = [v for _, v in series if not math.isnan(v)]
    ids = [g for g, v in series if not math.isnan(v)]
    if len(values) < 2 * min_side:
        return (0, float("nan"), float("nan"), 0.0)
    spread = st.pstdev(values) or 1.0
    best = (0, float("nan"), float("nan"), -1.0)
    for k in range(min_side, len(values) - min_side + 1):
        before, after = values[:k], values[k:]
        gap = abs(st.fmean(after) - st.fmean(before)) / spread
        if gap > best[3]:
            best = (ids[k], st.fmean(before), st.fmean(after), gap)
    return best


def breaks_report(stats: dict[str, Stat], order: list[str], title: str) -> None:
    print(f"\n=== {title}: did anyone change strategy, and when? ===")
    print(
        f"{'team':22s} {'metric':>12s} {'break at':>9s} {'before':>10s} {'after':>10s} {'gap/sd':>7s}"
    )
    for team in order:
        s = stats[team]
        gids = sorted(s.games)
        series = {
            "median a/t": [(g, q(s.per_game_a_over_t.get(g, []), 0.5)) for g in gids],
            "accept%": [
                (g, (s.per_game_accept[g][0] / s.per_game_accept[g][1] if s.per_game_accept[g][1] else float("nan")))
                for g in gids
            ],
            "charge CV": [(g, _cv(s.per_game_charges.get(g, []))) for g in gids],
            "net": [(g, s.per_game[g]) for g in gids],
        }
        for name, data in series.items():
            gid, before, after, gap = changepoint(data)
            flag = "  <-- break" if gap >= 1.0 else ""
            print(
                f"{team:22s} {name:>12s} {gid:9d} {before:10.2f} {after:10.2f} {gap:7.2f}{flag}"
            )
    print("  `gap/sd` >= 1.0 is where the two halves differ by more than the series' own noise.")
    print("  `charge CV` = stdev/mean of the Charges submitted in a Game: a collapse toward 0 is")
    print("  a team that stopped pricing items individually (a constant or a template).")


def _cv(values: list[float]) -> float:
    finite = [v for v in values if v not in (INF,) and not math.isnan(v)]
    if len(finite) < 2:
        return float("nan")
    mean = st.fmean(finite)
    return float("nan") if mean == 0 else st.pstdev(finite) / mean


# -------------------------------------------------------------------------- Q6 the Cap


def cap_report(books: list[Book]) -> None:
    print("\n=== the Cap: does it bind, at what value, and who wastes money on it? ===")
    print("  ties at or above the Cap floor -- several issuers paid the identical amount:")
    print(
        f"    {'game':>5s} {'item':>5s} {'amount':>11s} {'issuers':>8s} {'t bracket':>22s} "
        f"{'amount/4':>10s} {'verdict':>15s}"
    )
    proven: list[str] = []
    for book in books:
        ties: dict[tuple[int, float], set[str]] = collections.defaultdict(set)
        for team in book.team_names:
            for row in book.rows[team]:
                if row["issuer"] == team and row["accepted"] and row["amount"] >= CAP_FLOOR - 0.005:
                    ties[(row["line_item_index"], round(row["amount"], 2))].add(team)
        for (index, amount), issuers in sorted(ties.items()):
            if len(issuers) < 2:
                continue
            lo, hi = book.fair[index]
            bracket = f"[{lo:,.1f},{'inf' if hi == INF else f'{hi:,.1f}'})"
            inside = lo <= amount / 4.0 < hi
            if inside:
                verdict = "c = 4t"
            elif plausible_cap(amount, (lo, hi)):
                verdict = "c = 2000 floor"
            else:
                verdict = "coincidence"
            print(
                f"    {book.game_id:5d} {index:5d} {amount:11,.2f} {len(issuers):8d} "
                f"{bracket:>22s} {amount / 4:10,.2f} {verdict:>15s}"
            )
            if inside:
                proven.append(f"G{book.game_id} #{index}: c = 4t exactly, t = {amount / 4:,.2f}")

    # Our own submitted Charges are the only place where `a` is known independently of the
    # record, which is the only way to prove the Cap *truncated* rather than merely tied.
    #
    # The log is only admissible where it *is* the submission. In Game 26 it is not: eight of
    # ten logged Charges are strictly above what every payer paid, by ratios (0.33-0.97) that
    # no single Cap can produce, and `c < 4t` would be illegal on several of them. That Game
    # submitted numbers other than the ones it logged -- the same failure CLAUDE.md records
    # for Games 21-24 (a `STANDARD_LIMIT` from a lower layer). So a Game is admissible only
    # when the log reproduces the recovered Charge on most items, and a truncation is a proof
    # only when the paid amount is a legal Cap for that item.
    print("\n  truncation proven against our own submission log (var/decisions):")
    any_proof = False
    for book in books:
        log = Path(f"var/decisions/game_{book.game_id:03d}.json")
        if not log.exists():
            continue
        try:
            logged = {int(i["index"]): float(i["charge"]) for i in json.loads(log.read_text())["items"]}
        except (KeyError, ValueError, json.JSONDecodeError):
            continue
        comparable = {
            index: (logged[index], book.charge[index][US])
            for index in logged
            if index in book.charge and book.charge[index][US] != INF
        }
        agree = sum(1 for a, rec in comparable.values() if abs(a - rec) < 0.02)
        if not comparable or agree < 0.5 * len(comparable):
            print(
                f"    G{book.game_id}: log matches only {agree}/{len(comparable)} recovered "
                f"Charges -- the log is not the submission, excluded"
            )
            continue
        for index, (submitted, recovered) in comparable.items():
            if submitted <= recovered + 0.005:
                continue
            lo, hi = book.fair[index]
            if not plausible_cap(round(recovered, 2), (lo, hi)):
                print(
                    f"    G{book.game_id} #{index}: logged {submitted:,.2f} vs paid "
                    f"{recovered:,.2f}, but {recovered:,.2f} is not a legal Cap here -- "
                    f"not Cap evidence"
                )
                continue
            any_proof = True
            print(
                f"    G{book.game_id} #{index}: we charged {submitted:,.2f}, every payer paid "
                f"{recovered:,.2f}  =>  c = {recovered:,.2f} exactly  "
                f"(t < {'inf' if hi == INF else f'{hi:,.1f}'}, so 4t < "
                f"{(4 * hi) if hi != INF else float('inf'):,.0f} and the floor is what binds)"
            )
    if not any_proof:
        print("    none in this window")

    violations = []
    for book in books:
        for team in book.team_names:
            for row in book.rows[team]:
                if row["issuer"] != team or not row["accepted"] or row["amount"] <= 0:
                    continue
                lo, hi = book.fair[row["line_item_index"]]
                if hi != INF and row["amount"] > max(4 * hi, CAP_FLOOR) + 0.01:
                    violations.append(
                        f"G{book.game_id} #{row['line_item_index']} {team}: paid {row['amount']:,.2f}"
                        f" > max(4*t_hi, 2000) = {max(4 * hi, CAP_FLOOR):,.2f}"
                    )
    print(f"\n  counterexamples to c = max(4t, 2000): {len(violations)}")
    for line in violations[:10]:
        print(f"    {line}")
    for line in proven:
        print(f"  pinned: {line}")

    print("\n  who charged above their own Cap (strictly wasteful -- fewer acceptances, same pay):")
    waste: dict[str, list[str]] = collections.defaultdict(list)
    for book in books:
        for index in book.items:
            c = book.cap(index)
            for team in book.team_names:
                a = book.charge[index][team]
                state = book.status[index][team]
                if state == "capped":
                    waste[team].append(f"G{book.game_id}#{index} truncated at {a:,.0f}")
                elif state in ("exact", "exact-acc", "uncapped?") and a > c + 0.005:
                    waste[team].append(f"G{book.game_id}#{index} a={a:,.0f} > c={c:,.0f}")
    for team in sorted(waste, key=lambda t: -len(waste[t])):
        print(f"    {team:22s} {len(waste[team]):3d}  {'; '.join(waste[team][:4])}")
    if not waste:
        print("    nobody")


# ------------------------------------------------------------------- Q7 the steal list


def replay_capped(
    snap: GameSnapshot,
    submission: dict[int, tuple[float, float]],
    *,
    limit_rule: str = "mid",
) -> float:
    """Our net had we submitted `submission`, with the **Cap enforced**.

    `replay_payoffs.replay` treats `c` as infinite; that was defensible while no accepted row
    had ever disagreed with a wrongful-rejection row, and it is now known to be wrong (three
    Line Items truncate at 2,000.00). Enforcing `c = max(4t, 2000)` matters in exactly one
    place -- it stops a counterfactual Charge above the Cap from being credited with income it
    could never have earned, which is the difference between "charge more" looking free and
    looking wasteful.

    `--verify` feeds our reconstructed real submission back in and checks the result against
    the published net for every Game, so the Cap model is falsifiable here and not just argued.
    """
    income = 0.0
    cost = 0.0
    for index in snap.line_items:
        charge, limit = submission.get(index, (0.0, 0.0))
        t = snap.fair_point(index)
        c = max(cap_of(t), _observed_cap(snap, index))
        for team in snap.opponents:
            b = snap.limit_point(index, team, limit_rule)
            if charge <= b:
                income += min(charge, c)
            elif charge <= t:
                income += charge
            their_a = snap.charges[index][team]
            if their_a <= limit:
                cost += min(their_a, c)
            elif their_a <= t:
                cost += 1.5 * their_a
    return income - cost


def _observed_cap(snap: GameSnapshot, index: int) -> float:
    """Never model a Cap below what somebody was actually paid on this item."""
    return max((a for a in snap.charges[index].values() if a != INF), default=0.0)


def donor_submission(
    snap: GameSnapshot,
    donor: str,
    *,
    take_charge: bool = True,
    take_limit: bool = True,
) -> dict[int, tuple[float, float]]:
    ours = our_actual_submission(snap)
    out: dict[int, tuple[float, float]] = {}
    for index in snap.line_items:
        our_a, our_b = ours[index]
        a = snap.charges[index].get(donor, INF) if take_charge else our_a
        b = snap.limit_point(index, donor) if take_limit else our_b
        out[index] = (a, b)
    return out


def rule_submissions(snap: GameSnapshot) -> dict[str, dict[int, tuple[float, float]]]:
    """The inferred *rules*, as submissions. Each one is a sentence you could implement."""
    ours = our_actual_submission(snap)
    out: dict[str, dict[int, tuple[float, float]]] = {}

    def rule(label: str, fn) -> None:
        out[label] = {index: fn(index, *ours[index]) for index in snap.line_items}

    rule("R-cap2000: a <- min(a, 2000)", lambda i, a, b: (min(a, CAP_FLOOR), b))
    rule(
        "R-capexact: a <- min(a, max(4t,2000))",
        lambda i, a, b: (min(a, max(cap_of(snap.fair_point(i)), _observed_cap(snap, i))), b),
    )
    for k in (0.7, 0.8):
        rule(f"R-level: a x {k}", lambda i, a, b, k=k: (a if a == INF else a * k, b))
        rule(
            f"R-level+floor: a x {k}, censored -> floor",
            lambda i, a, b, k=k: (
                (unrecoverable_floor(snap, i) if a == INF else a * k),
                b,
            ),
        )
    rule(
        "R-anchor2000: unpriceable a <- 2000",
        lambda i, a, b: ((CAP_FLOOR if a == INF else a), b),
    )
    rule(
        "R-worthless@cap: t_lo == 0 -> a = 2000",
        lambda i, a, b: ((CAP_FLOOR if snap.fair_brackets[i][0] == 0.0 else a), b),
    )
    for x in (500.0, 1000.0, 2000.0):
        rule(f"R-neveraccept>{x:.0f}", lambda i, a, b, x=x: (a, min(b, x)))
    for k in (0.5, 1.5, 2.0):
        rule(f"R-limit x {k}", lambda i, a, b, k=k: (a, b * k))
    rule("R-b=0 (panic)", lambda i, a, b: (a, 0.0))
    return out


@dataclass
class Steal:
    label: str
    total: float
    per_game: dict[int, float]

    @property
    def games(self) -> int:
        return len(self.per_game)


def steal_list(game_ids: list[int], donors: list[str], *, us: str = US) -> list[Steal]:
    snaps: list[GameSnapshot] = []
    for gid in game_ids:
        try:
            snaps.append(snapshot(gid, us))
        except UnreconstructableGame as exc:
            print(f"  skipping G{gid}: {exc}")
    results: list[Steal] = []

    def run(label: str, builder) -> None:
        per = {s.game_id: replay_capped(s, builder(s)) for s in snaps}
        results.append(Steal(label, sum(per.values()), per))

    run("us (actual)", our_actual_submission)
    for donor in donors:
        if donor == us:
            continue
        run(f"{donor}: a+b", lambda s, d=donor: donor_submission(s, d))
        run(f"{donor}: a only (our b)", lambda s, d=donor: donor_submission(s, d, take_limit=False))
        run(f"{donor}: b only (our a)", lambda s, d=donor: donor_submission(s, d, take_charge=False))
    labels = list(rule_submissions(snaps[0]))
    for label in labels:
        run(label, lambda s, label=label: rule_submissions(s)[label])
    return results


def print_steal(results: list[Steal], *, per_game: bool = False) -> None:
    base = next(r for r in results if r.label == "us (actual)")
    floor = noise_floor(base.games)
    print(f"\n=== the steal list: our net over {base.games} Games, Cap enforced ===")
    print(f"{'submission':40s} {'total':>13s} {'delta vs us':>13s} {'per Game':>10s}  verdict")
    for r in sorted(results, key=lambda r: -r.total):
        delta = r.total - base.total
        if r.label == "us (actual)":
            verdict = "baseline"
        elif abs(delta) < floor:
            verdict = f"inside noise (+-{floor:,.0f})"
        else:
            verdict = "STEAL" if delta > 0 else "reject"
        print(
            f"{r.label:40s} {r.total:13,.0f} {delta:13,.0f} "
            f"{delta / max(r.games, 1):10,.0f}  {verdict}"
        )
    print(f"  noise floor = 26,622 * sqrt({base.games}/18) = {floor:,.0f} euros over the window.")
    if per_game:
        gids = sorted(base.per_game)
        print("\n  per-Game net:")
        print("    " + f"{'submission':40s}" + "".join(f"{g:>10d}" for g in gids))
        for r in sorted(results, key=lambda r: -r.total):
            print("    " + f"{r.label:40s}" + "".join(f"{r.per_game[g]:10,.0f}" for g in gids))


def verify_capped(game_ids: list[int], us: str = US) -> None:
    """Does the Cap-aware replay still reproduce the published net? It must, exactly."""
    print("\n=== verify: Cap-aware replay against the authoritative net ===")
    bad = 0
    for gid in game_ids:
        try:
            snap = snapshot(gid, us)
        except UnreconstructableGame as exc:
            print(f"G{gid:3d} UNRECONSTRUCTABLE {exc}")
            bad += 1
            continue
        got = replay_capped(snap, our_actual_submission(snap))
        ok = abs(got - snap.published_net) <= 0.01
        bad += 0 if ok else 1
        print(
            f"G{gid:3d} {'OK  ' if ok else 'FAIL'} replay {got:13,.2f}  "
            f"identity {snap.published_net:13,.2f}"
        )
    print(f"  {len(game_ids) - bad}/{len(game_ids)} Games reproduce to the cent under c = max(4t, 2000).")


# --------------------------------------------------------------------------------- cli


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teams", default=",".join(DEFAULT_TEAMS))
    parser.add_argument("--games", default="all")
    parser.add_argument(
        "--windows",
        default="",
        help="extra windows to re-run every table over, e.g. '1-14,15-30,19-30,27-30'",
    )
    parser.add_argument("--anchor", action="store_true")
    parser.add_argument("--income", action="store_true")
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--fountain", action="store_true")
    parser.add_argument("--breaks", action="store_true")
    parser.add_argument("--cap", action="store_true")
    parser.add_argument("--steal", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--per-game", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all:
        args.anchor = args.income = args.review = True
        args.fountain = args.breaks = args.cap = args.steal = True

    all_teams = teams()
    wanted = [t.strip() for t in args.teams.split(",") if t.strip()]
    if wanted == ["all"]:
        wanted = all_teams
    unknown = [t for t in wanted if t not in all_teams]
    if unknown:
        raise SystemExit(f"unknown teams {unknown}; known: {all_teams}")

    game_ids = parse_games(args.games)
    windows = [(args.games, game_ids)]
    for spec in [w for w in args.windows.split(",") if w.strip()]:
        windows.append((spec, parse_games(spec)))

    need_books = args.anchor or args.income or args.review or args.fountain or args.breaks or args.cap
    if need_books:
        print(f"loading {len(game_ids)} Games x {len(all_teams)} teams ...", file=sys.stderr)
        books = {b.game_id: b for b in load_books(game_ids, all_teams)}

        for spec, ids in windows:
            window_books = [books[g] for g in ids if g in books]
            if not window_books:
                continue
            stats = measure_all(window_books, all_teams)
            order = sorted(wanted, key=lambda t: -stats[t].net)
            title = f"G{spec}"
            if args.anchor:
                anchor_report(stats, order, title)
            if args.income:
                income_report(stats, order, title)
            if args.review:
                review_report(stats, order, title)
            if args.fountain:
                fountain_report(window_books, {t: stats[t] for t in all_teams}, title)
            if args.breaks:
                breaks_report(stats, order, title)
        if args.cap:
            cap_report([books[g] for g in game_ids])

    if args.verify:
        verify_capped(game_ids)
    if args.steal:
        for spec, ids in windows:
            if not ids:
                continue
            print(f"\n################ steal list over G{spec} ################")
            print_steal(steal_list(ids, wanted), per_game=args.per_game)


if __name__ == "__main__":
    main()
