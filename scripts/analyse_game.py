"""Attribute a settled Game's net, euro by euro, to the mechanism that produced it.

Everything here is reconstructed from public Transactions only -- no model, no LLM. Run it
after every Game so a leaderboard number never stands without its diagnosis:

    PYTHONPATH=. python scripts/analyse_game.py --games 21-23
    PYTHONPATH=. python scripts/analyse_game.py --games 21-23 --sweep --field

What it computes, per Line Item:

* the true Fair Value bracket ``t in [t_lo, t_hi)`` via ``invert_fair_values.brackets``;
* **our own** Charge ``a`` (any row where we are issuer and money moved -- a wrongful
  rejection pays exactly ``a``, an accepted row pays ``min(a, c)`` with ``c >= 4t``) and
  our Limit ``b`` bracketed by ``max(accepted charge) <= b < min(rejected charge)``;
* the realised mechanisms -- income collected, cash paid on accepted claims, cash paid as
  ``1.5a`` wrongful-rejection penalties. These three sum to the published net *by
  identity*, so the residual printed is a self-check and must be 0.00;
* the counterfactual mechanisms -- income forfeited because ``a < t`` (underpricing) and
  because ``a > t`` (fraud-zone rejections). Both are measured against the reference
  Charge ``a = t``, which collects ``t`` from every single opponent: a reviewer either
  accepts and pays ``t``, or wrongfully rejects and still owes ``t``. These are *not* part
  of the net and are reported in their own columns.

The side of ``t`` a Charge fell on is usually **observed, not guessed**: a rejected row
with ``amount > 0`` proves the Charge was fair, ``amount == 0`` proves it was fraud. Only
Charges that all reviewers accepted are unclassified, and those fall back to the bracket.

Two traps this script is built to avoid:

* the ``/matrix`` ``cells`` array is **not indexed by game id** -- it is aligned with the
  ``game_ids`` array in the same payload, which currently starts at 4. Nets are derived
  from Transactions and only cross-checked against ``cells[game_ids.index(game_id)]``.
* **Game 16 does not reconstruct** and is excluded from every aggregate by default.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics as st
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from invert_fair_values import brackets  # noqa: E402
from pull_transactions import _get, teams, transactions  # noqa: E402

INF = math.inf
US = "Bin busy"
LEADERS = ("eyay", "OPUSMOPUS", "error404 ai")
BROKEN_GAMES = frozenset({16})
CASE_DIRS = (Path("[PUBLIC] EHL Cases/cases"), Path("var/cases"))
PENALTY = 1.5


# --------------------------------------------------------------------------------------
# ground truth
# --------------------------------------------------------------------------------------
def published_nets() -> dict[str, dict[int, float]]:
    """Published nets keyed by *game id*.

    ``cells`` is aligned with the payload's ``game_ids``, not with 1..N. Zipping the two
    is the whole point of this function; indexing ``cells`` by game id is the documented
    way to read a wrong number off this endpoint.
    """
    payload = _get("matrix")
    game_ids = payload["game_ids"]
    out: dict[str, dict[int, float]] = {}
    for row in payload["items"]:
        out[row["team_name"]] = dict(zip(game_ids, row["cells"], strict=False))
    return out


def completed_games() -> list[int]:
    return [g["id"] for g in _get("games")["items"] if g["status"] == "completed"]


@dataclass
class Submission:
    """What one team submitted for one Line Item, as far as it is recoverable."""

    charge: float | None = None
    charge_is_lower_bound: bool = False  # only accepted rows seen -> min(a, c)
    fair: bool | None = None  # observed side of t: True a<=t, False a>t
    limit_lo: float = 0.0  # max Charge this team accepted
    limit_hi: float = INF  # min Charge this team rejected


@dataclass
class ItemView:
    """Everything known about one Line Item, from every team's rows."""

    index: int
    t_lo: float
    t_hi: float
    name: str = ""
    subs: dict[str, Submission] = field(default_factory=dict)
    # our realised money on this item
    income: float = 0.0
    paid_accepts: float = 0.0
    penalties: float = 0.0
    reviewers: int = 0
    accepts: int = 0
    # our reviewer-side rows: (issuer, charge, accepted, fair)
    reviews: list[tuple[str, float, bool, bool | None]] = field(default_factory=list)

    @property
    def t_mid(self) -> float:
        return self.t_lo if self.t_hi == INF else (self.t_lo + self.t_hi) / 2

    @property
    def net(self) -> float:
        return self.income - self.paid_accepts - self.penalties


@dataclass
class GameView:
    game_id: int
    items: dict[int, ItemView]
    rows: int
    opponents: int

    @property
    def income(self) -> float:
        return sum(i.income for i in self.items.values())

    @property
    def paid_accepts(self) -> float:
        return sum(i.paid_accepts for i in self.items.values())

    @property
    def penalties(self) -> float:
        return sum(i.penalties for i in self.items.values())

    @property
    def net(self) -> float:
        return self.income - self.paid_accepts - self.penalties


def build(game_id: int, team_names: list[str], us: str = US) -> GameView:
    table = brackets(game_id, team_names)
    items = {
        index: ItemView(index=index, t_lo=lo, t_hi=hi) for index, (lo, hi) in table.items()
    }

    # pass 1: every team's Charge and its observed side of t.
    # A wrongful rejection pays exactly `a`; an accepted row pays min(a, c), so the
    # largest amount seen is the Charge and is exact as soon as one rejection paid it.
    for team in team_names:
        for row in transactions(team, game_id):
            item = items.get(row["line_item_index"])
            if item is None:
                continue
            amount, accepted = row["amount"], row["accepted"]
            sub = item.subs.setdefault(row["issuer"], Submission())
            if amount > 0:
                if sub.charge is None or amount > sub.charge:
                    sub.charge = amount
                    sub.charge_is_lower_bound = accepted
                elif amount == sub.charge and not accepted:
                    sub.charge_is_lower_bound = False
            if not accepted:
                sub.fair = amount > 0  # rejected & paid -> fair; rejected & 0 -> fraud

    # pass 2: every team's Limit bracket, now that the Charges are known
    for team in team_names:
        for row in transactions(team, game_id):
            item = items.get(row["line_item_index"])
            if item is None:
                continue
            charge = item.subs.get(row["issuer"], Submission()).charge
            if charge is None:
                continue
            sub = item.subs.setdefault(row["reviewer"], Submission())
            if row["accepted"]:
                sub.limit_lo = max(sub.limit_lo, charge)
            else:
                sub.limit_hi = min(sub.limit_hi, charge)

    # pass 3: our own realised money, using the Charges recovered above
    for row in transactions(us, game_id):
        item = items[row["line_item_index"]]
        amount, accepted = row["amount"], row["accepted"]
        if row["issuer"] == us:
            item.income += amount
        if row["reviewer"] == us:
            item.reviewers += 1
            charge = item.subs.get(row["issuer"], Submission()).charge
            if accepted:
                item.accepts += 1
                item.paid_accepts += amount
            else:
                item.penalties += PENALTY * amount
            item.reviews.append(
                (
                    row["issuer"],
                    charge if charge is not None else amount,
                    accepted,
                    item.subs[row["issuer"]].fair,
                )
            )

    rows = len(transactions(us, game_id))
    opponents = max((i.reviewers for i in items.values()), default=0)
    return GameView(game_id=game_id, items=items, rows=rows, opponents=opponents)


# --------------------------------------------------------------------------------------
# attribution
# --------------------------------------------------------------------------------------
def forfeited(item: ItemView, opponents: int, t: float | None = None) -> tuple[float, float]:
    """(forfeited because a < t, forfeited because a > t) against the a = t reference.

    Charging exactly ``t`` collects ``t`` from every opponent, so the reference income is
    ``opponents * t``. Which bucket the gap lands in is decided by the observed side of
    ``t`` where available, and by the bracket otherwise.
    """
    t = item.t_mid if t is None else t
    reference = opponents * t
    gap = reference - item.income
    sub = item.subs.get(US)
    if sub is None or sub.charge is None:
        # we charged 0 (or were never paid): pure underpricing unless t is 0
        return (gap, 0.0) if t > 0 else (0.0, 0.0)
    fair = sub.fair if sub.fair is not None else sub.charge <= t
    return (gap, 0.0) if fair else (0.0, gap)


def reviewer_costs(item: ItemView) -> tuple[float, float, float]:
    """(strictness excess, leniency excess, oracle cost) on the reviewer side.

    Oracle = accept exactly the fair Charges. Rejecting a fair ``a`` costs ``1.5a`` where
    accepting costs ``a``, so strictness excess is ``0.5a``. Accepting a fraudulent ``a``
    costs ``a`` where rejecting costs nothing, so leniency excess is the full ``a``.
    """
    strict = lenient = oracle = 0.0
    for _issuer, charge, accepted, fair in item.reviews:
        if fair is None:
            fair = charge <= item.t_mid
        if fair:
            oracle += charge
            if not accepted:
                strict += 0.5 * charge
        elif accepted:
            lenient += charge
    return strict, lenient, oracle


def limit_estimate(item: ItemView) -> tuple[float, float]:
    sub = item.subs.get(US, Submission())
    return sub.limit_lo, sub.limit_hi


@dataclass
class SweepPoint:
    factor: float
    cost: float
    rate: float
    strict: float  # excess paid because we rejected a fair Charge
    lenient: float  # excess paid because we accepted a fraudulent Charge


def anchor_value(item: ItemView, anchor: str) -> float:
    """The per-item base the sweep factor multiplies.

    ``charge`` uses our own recovered Charge -- ``b = factor * a`` is a policy we could
    actually ship, and our Charge is the only public trace of our own Fair Value estimate.
    ``limit`` uses the midpoint of our recovered Limit bracket, which is degenerate
    whenever every Charge we accepted was 0 (a dark opponent), so the sweep then only
    moves once the factor clears the upper bound.
    """
    if anchor == "limit":
        lo, hi = limit_estimate(item)
        return lo if hi == INF else (lo + hi) / 2
    sub = item.subs.get(US, Submission())
    return sub.charge or 0.0


def sweep(game: GameView, factors: tuple[float, ...], anchor: str = "charge") -> list[SweepPoint]:
    """Reviewer cost and accept rate when our Limit is scaled by ``factor``.

    Decisions are replayed against the *real* opponent Charges and their *observed* side
    of ``t``, so the Limit is the only counterfactual quantity.
    """
    out = []
    for factor in factors:
        cost = strict = lenient = 0.0
        accepted = total = 0
        for item in game.items.values():
            limit = factor * anchor_value(item, anchor)
            for _issuer, charge, _was_accepted, fair in item.reviews:
                if fair is None:
                    fair = charge <= item.t_mid
                total += 1
                if charge <= limit:
                    accepted += 1
                    cost += charge
                    if not fair:
                        lenient += charge
                elif fair:
                    cost += PENALTY * charge
                    strict += 0.5 * charge
        out.append(
            SweepPoint(factor, cost, accepted / total if total else 0.0, strict, lenient)
        )
    return out


def oracle_accept_rate(game: GameView) -> tuple[float, float]:
    """(accept rate of the oracle, its cost). The oracle accepts exactly the fair Charges."""
    fair = total = 0
    cost = 0.0
    for item in game.items.values():
        for _issuer, charge, _accepted, is_fair in item.reviews:
            if is_fair is None:
                is_fair = charge <= item.t_mid
            total += 1
            if is_fair:
                fair += 1
                cost += charge
    return (fair / total if total else 0.0), cost


# --------------------------------------------------------------------------------------
# case files
# --------------------------------------------------------------------------------------
def case_dir(game_id: int) -> Path | None:
    for root in CASE_DIRS:
        candidate = root / f"case_{game_id:02d}"
        if (candidate / "invoices.pdf").exists():
            return candidate
    return None


def item_names(game_id: int) -> dict[int, str]:
    directory = case_dir(game_id)
    if directory is None:
        return {}
    try:
        from src.data.case_loader import read_case

        case = asyncio.run(read_case(game_id, directory))
    except Exception:  # noqa: BLE001 - names are a nicety, never a hard dependency
        return {}
    return {
        li.index: f"{li.name}{' [-- --]' if li.quantity_missing else ''}"
        for li in case.line_items
    }


def invoice_text(game_id: int) -> str:
    directory = case_dir(game_id)
    if directory is None:
        return ""
    result = subprocess.run(
        ["pdftotext", "-layout", str(directory / "invoices.pdf"), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


# --------------------------------------------------------------------------------------
# printing
# --------------------------------------------------------------------------------------
def fmt_t(item: ItemView) -> str:
    hi = "inf" if item.t_hi == INF else f"{item.t_hi:.0f}"
    return f"[{item.t_lo:.0f},{hi})"


def fmt_limit(item: ItemView) -> str:
    lo, hi = limit_estimate(item)
    return f"[{lo:.0f},{'inf' if hi == INF else f'{hi:.0f}'})"


def ratio(value: float | None, base: float) -> str:
    if value is None or base <= 0:
        return "  -  "
    return f"{value / base:5.2f}"


def report(game: GameView, names: dict[int, str], published: float | None) -> dict:
    print(f"\n{'=' * 118}")
    head = f"GAME {game.game_id}  --  {len(game.items)} Line Items, {game.rows} rows, {game.opponents} opponents"
    print(head)
    print("=" * 118)
    print(
        f"{'idx':>3} {'t bracket':>16} {'our a':>9} {'a/t':>6} {'our b':>16} {'b/t':>6} "
        f"{'income':>9} {'paid':>9} {'penalty':>9} {'net':>10} {'acc':>7} {'side':>5}"
    )
    lo_forfeit = hi_forfeit = 0.0
    strict_total = lenient_total = oracle_total = 0.0
    for index in sorted(game.items):
        item = game.items[index]
        sub = item.subs.get(US, Submission())
        b_lo, b_hi = limit_estimate(item)
        b_mid = b_lo if b_hi == INF else (b_lo + b_hi) / 2
        low, high = forfeited(item, game.opponents)
        lo_forfeit += low
        hi_forfeit += high
        strict, lenient, oracle = reviewer_costs(item)
        strict_total += strict
        lenient_total += lenient
        oracle_total += oracle
        side = "-" if sub.fair is None else ("a<=t" if sub.fair else "a>t")
        charge = f"{sub.charge:9.0f}" if sub.charge is not None else "        ?"
        print(
            f"{index:3d} {fmt_t(item):>16} {charge} {ratio(sub.charge, item.t_mid):>6} "
            f"{fmt_limit(item):>16} {ratio(b_mid, item.t_mid):>6} "
            f"{item.income:9.0f} {item.paid_accepts:9.0f} {item.penalties:9.0f} "
            f"{item.net:10.0f} {item.accepts:3d}/{item.reviewers:<3d} {side:>5}"
        )
        if names.get(index):
            print(f"      {names[index][:110]}")

    realised = game.income - game.paid_accepts - game.penalties
    print("-" * 118)
    print(
        "legend: 'our b' is a bracket, not a value -- read it as b < upper bound. Where we "
        "accepted nothing but a 0 Charge the\n        lower bound is 0 and b/t is an "
        "artefact of the two midpoints; 'side' is the observed side of t, '-' = only "
        "accepted rows."
    )
    print("REALISED MECHANISMS (these sum to the net by identity)")
    print(f"  income collected                     {game.income:12,.2f}")
    print(f"  cash paid on accepted claims        -{game.paid_accepts:12,.2f}")
    print(f"  cash paid as 1.5a penalties         -{game.penalties:12,.2f}")
    print(f"  = net                                {realised:12,.2f}")
    if published is not None:
        print(f"  published net (matrix, by game_id)   {published:12,.2f}")
        print(f"  RESIDUAL                             {realised - published:12,.2f}")
    else:
        print("  published net                             not on /matrix for this Game")

    reference = game.opponents * sum(i.t_mid for i in game.items.values())
    print("COUNTERFACTUAL: income forfeited against a = t (t at bracket midpoint)")
    print(f"  forfeited because a was below t      {lo_forfeit:12,.2f}")
    print(f"  forfeited because a was above t      {hi_forfeit:12,.2f}")
    print(f"  income at a = t   ({game.opponents} x sum t)     {reference:12,.2f}")
    print(f"  income at a = 0.7t (R5b target)      {0.7 * reference:12,.2f}")
    print(f"  income actually collected            {game.income:12,.2f}")
    ratios = [
        (item.subs[US].charge / item.t_mid)
        for item in game.items.values()
        if US in item.subs and item.subs[US].charge and item.t_mid > 0
    ]
    if ratios:
        # sigma is the log error of the implied Fair Value estimate t_hat = a / 0.7 (R5b),
        # measured against the bracket midpoint. CLAUDE.md rule 10: RMSLE, not stdev,
        # because the failure mode is a level bias and a stdev cannot see one.
        logs = [math.log(r / 0.7) for r in ratios]
        rmsle = math.sqrt(sum(x * x for x in logs) / len(logs))
        print(
            f"CHARGE CALIBRATION over {len(ratios)} items: median a/t {st.median(ratios):.2f} "
            f"(target 0.70), implied t_hat/t median {st.median(ratios) / 0.7:.2f}, RMSLE {rmsle:.2f}"
        )
    print("REVIEWER SIDE vs the accept-exactly-the-fair-Charges oracle")
    print(f"  oracle cost (unavoidable)            {oracle_total:12,.2f}")
    print(f"  excess from strictness (0.5a)        {strict_total:12,.2f}")
    print(f"  excess from leniency (a on a>t)      {lenient_total:12,.2f}")
    rate = sum(i.accepts for i in game.items.values()) / max(
        sum(i.reviewers for i in game.items.values()), 1
    )
    ideal_rate, ideal_cost = oracle_accept_rate(game)
    print(
        f"  accept rate ours {rate:6.1%}   oracle {ideal_rate:6.1%}   "
        f"our reviewer cost {game.paid_accepts + game.penalties:,.0f} vs oracle {ideal_cost:,.0f}"
    )
    return {
        "game": game.game_id,
        "items": len(game.items),
        "income": game.income,
        "paid_accepts": game.paid_accepts,
        "penalties": game.penalties,
        "net": realised,
        "published": published,
        "residual": None if published is None else realised - published,
        "forfeit_below_t": lo_forfeit,
        "forfeit_above_t": hi_forfeit,
        "income_at_t": reference,
        "income_at_0.7t": 0.7 * reference,
        "median_a_over_t": st.median(ratios) if ratios else None,
        "oracle_cost": oracle_total,
        "excess_strict": strict_total,
        "excess_lenient": lenient_total,
        "accept_rate": rate,
        "oracle_accept_rate": ideal_rate,
    }


def detail_report(game: GameView) -> None:
    """Every Charge we reviewed, with what our decision cost against the oracle."""
    for index in sorted(game.items):
        item = game.items[index]
        print(f"\n  item {index}: t in {fmt_t(item)}, our Limit {fmt_limit(item)}")
        print(f"  {'issuer':>20} {'charge':>9} {'side':>5} {'ours':>7} {'we paid':>9} {'excess':>9}")
        for issuer, charge, accepted, fair in sorted(item.reviews, key=lambda r: -r[1]):
            observed = fair
            if fair is None:
                fair = charge <= item.t_mid
            paid = charge if accepted else (PENALTY * charge if fair else 0.0)
            excess = 0.0 if accepted and fair else (0.5 * charge if fair and not accepted else (charge if accepted else 0.0))
            side = ("a<=t" if fair else "a>t") + ("" if observed is not None else "?")
            print(
                f"  {issuer:>20} {charge:9.0f} {side:>5} {'accept' if accepted else 'reject':>7} "
                f"{paid:9.0f} {excess:9.0f}"
            )


def field_report(game: GameView, leaders: tuple[str, ...]) -> None:
    print("\nFIELD -- Charge and Limit against t (bracket midpoint). b is itself a bracket.")
    for index in sorted(game.items):
        item = game.items[index]
        print(f"  item {index}: t in {fmt_t(item)}  (midpoint {item.t_mid:,.0f})")
        print(f"    {'team':>20} {'a':>9} {'a/t':>6} {'b bracket':>18} {'b/t':>6}")
        for team in (US, *leaders):
            sub = item.subs.get(team, Submission())
            b_mid = sub.limit_lo if sub.limit_hi == INF else (sub.limit_lo + sub.limit_hi) / 2
            bracket = f"[{sub.limit_lo:.0f},{'inf' if sub.limit_hi == INF else f'{sub.limit_hi:.0f}'})"
            charge = f"{sub.charge:9.0f}" if sub.charge is not None else f"{'?':>9}"
            print(
                f"    {team:>20} {charge} {ratio(sub.charge, item.t_mid):>6} "
                f"{bracket:>18} {ratio(b_mid, item.t_mid):>6}"
            )

    print("\nFIELD -- reviewer side, every team scored against the same oracle")
    print(
        f"{'team':>20} {'accepts':>10} {'rate':>7} {'paid':>10} {'penalty':>10} "
        f"{'rev cost':>10} {'oracle':>10} {'strict':>9} {'lenient':>9} {'net':>10}"
    )
    for team in (US, *leaders):
        accepts = reviews = 0
        paid = penalty = income = oracle = strict = lenient = 0.0
        for row in transactions(team, game.game_id):
            item = game.items.get(row["line_item_index"])
            if item is None:
                continue
            if row["issuer"] == team:
                income += row["amount"]
            if row["reviewer"] != team:
                continue
            reviews += 1
            sub = item.subs.get(row["issuer"], Submission())
            charge = sub.charge if sub.charge is not None else row["amount"]
            fair = sub.fair if sub.fair is not None else charge <= item.t_mid
            if row["accepted"]:
                accepts += 1
                paid += row["amount"]
                if fair:
                    oracle += charge
                else:
                    lenient += charge
            else:
                penalty += PENALTY * row["amount"]
                if fair:
                    oracle += charge
                    strict += 0.5 * charge
        print(
            f"{team:>20} {accepts:4d}/{reviews:<5d} {accepts / max(reviews, 1):7.1%} "
            f"{paid:10,.0f} {penalty:10,.0f} {paid + penalty:10,.0f} {oracle:10,.0f} "
            f"{strict:9,.0f} {lenient:9,.0f} {income - paid - penalty:10,.0f}"
        )


def sweep_report(games: list[GameView], factors: tuple[float, ...], anchor: str) -> None:
    print(f"\n{'=' * 118}")
    print(
        f"LIMIT SWEEP -- b = factor x {'our own Charge a' if anchor == 'charge' else 'our recovered Limit'}, "
        "replayed against the real field"
    )
    print("cost = what we would have paid as Reviewer; rate = resulting accept rate")
    print("=" * 118)
    print(f"{'factor':>7} " + " ".join(f"{f'G{g.game_id}':>18}" for g in games) + f" {'TOTAL':>13} {'strict':>10} {'lenient':>10}")
    curves = {g.game_id: {p.factor: p for p in sweep(g, factors, anchor)} for g in games}
    best: tuple[float, float] | None = None
    for factor in factors:
        cells = []
        total = strict = lenient = 0.0
        for game in games:
            point = curves[game.game_id][factor]
            total += point.cost
            strict += point.strict
            lenient += point.lenient
            cells.append(f"{point.cost:11,.0f} {point.rate:5.0%}")
        if best is None or total < best[1]:
            best = (factor, total)
        print(
            f"{factor:7.2f} " + " ".join(f"{c:>18}" for c in cells)
            + f" {total:13,.0f} {strict:10,.0f} {lenient:10,.0f}"
        )
    actual = sum(g.paid_accepts + g.penalties for g in games)
    reviews = sum(sum(i.reviewers for i in g.items.values()) for g in games)
    accepts = sum(sum(i.accepts for i in g.items.values()) for g in games)
    print(f"{'ACTUAL':>7} " + " " * (19 * len(games) - 1) + f" {actual:13,.0f}")
    print("\nper-Game optimum (each Game scored on its own best factor):")
    per_game_best = 0.0
    for game in games:
        point = min(curves[game.game_id].values(), key=lambda p: p.cost)
        per_game_best += point.cost
        print(
            f"  G{game.game_id}: factor {point.factor:6.2f} cost {point.cost:11,.0f} "
            f"rate {point.rate:5.0%}  (actual cost {game.paid_accepts + game.penalties:,.0f}, "
            f"rate {sum(i.accepts for i in game.items.values()) / max(sum(i.reviewers for i in game.items.values()), 1):.0%})"
        )
    if best:
        rates = [curves[g.game_id][best[0]].rate for g in games]
        pooled = sum(
            curves[g.game_id][best[0]].rate * sum(i.reviewers for i in g.items.values())
            for g in games
        ) / max(reviews, 1)
        print(
            f"\nsingle best factor {best[0]:.2f}: reviewer cost {best[1]:,.0f} "
            f"vs {actual:,.0f} actual -> saves {actual - best[1]:,.0f}; "
            f"accept rate {pooled:.1%} against our actual {accepts / max(reviews, 1):.1%} "
            f"(per Game {', '.join(f'{r:.0%}' for r in rates)})"
        )
        print(
            f"one factor per Game would cost {per_game_best:,.0f} "
            f"-- {best[1] - per_game_best:,.0f} below the best single factor, "
            "which is the price of not knowing the Game in advance"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="21-", help="e.g. 21-30, 21-, or 8")
    parser.add_argument("--team", default=US)
    parser.add_argument("--names", action="store_true", help="print Line Item names from the Case")
    parser.add_argument("--field", action="store_true", help="compare against the leaders")
    parser.add_argument("--sweep", action="store_true", help="Limit multiplier sweep")
    parser.add_argument("--anchor", choices=("charge", "limit"), default="charge")
    parser.add_argument("--detail", action="store_true", help="every Charge we reviewed, per item")
    parser.add_argument("--include-broken", action="store_true", help="do not drop Game 16")
    parser.add_argument("--json", help="write the per-Game summary here")
    args = parser.parse_args()

    done = completed_games()
    start, _, end = args.games.partition("-")
    first = int(start)
    last = int(end) if end else max(done)
    wanted = [g for g in range(first, last + 1) if g in done]
    dropped = [g for g in wanted if g in BROKEN_GAMES and not args.include_broken]
    wanted = [g for g in wanted if g not in dropped]
    if dropped:
        print(f"NOTE: excluding Game(s) {dropped} -- the reconstruction does not close there.")

    team_names = teams()
    published = published_nets().get(args.team, {})
    views: list[GameView] = []
    summaries: list[dict] = []
    for game_id in wanted:
        game = build(game_id, team_names, us=args.team)
        views.append(game)
        names = item_names(game_id) if args.names else {}
        summaries.append(report(game, names, published.get(game_id)))
        if args.detail:
            detail_report(game)
        if args.field:
            field_report(game, LEADERS)

    if len(views) > 1:
        print(f"\n{'=' * 118}")
        print(f"TOTALS over Games {wanted}")
        print("=" * 118)
        keys = [
            ("income", "income collected"),
            ("paid_accepts", "cash paid on accepted claims"),
            ("penalties", "cash paid as 1.5a penalties"),
            ("net", "net"),
            ("forfeit_below_t", "forfeited because a < t"),
            ("forfeit_above_t", "forfeited because a > t"),
            ("income_at_t", "income if a = t"),
            ("income_at_0.7t", "income if a = 0.7t"),
            ("oracle_cost", "oracle reviewer cost"),
            ("excess_strict", "excess from strictness"),
            ("excess_lenient", "excess from leniency"),
        ]
        for key, label in keys:
            print(f"  {label:<32} {sum(s[key] for s in summaries):14,.2f}")
        residuals = [s["residual"] for s in summaries if s["residual"] is not None]
        print(f"  {'max |residual| vs published':<32} {max(map(abs, residuals), default=0):14,.2f}")
        rate = sum(sum(i.accepts for i in g.items.values()) for g in views) / max(
            sum(sum(i.reviewers for i in g.items.values()) for g in views), 1
        )
        print(f"  {'accept rate (pooled)':<32} {rate:14.1%}")
        # Accepting a Charge costs `a` whichever side of t it sits; rejecting costs
        # `1.5a` if it was fair and 0 if it was not. So accepting is right exactly when
        # P(a <= t) > 2/3. Against a field whose fair share is below 2/3, a Reviewer with
        # no per-Charge discrimination should reject everything -- that is the bar our
        # accept rate has to be judged against, not the leaders' accept rate.
        fair = total = 0
        for game in views:
            for item in game.items.values():
                for _issuer, charge, _accepted, is_fair in item.reviews:
                    total += 1
                    fair += bool(is_fair if is_fair is not None else charge <= item.t_mid)
        base = fair / max(total, 1)
        print(f"  {'fair share of Charges we saw':<32} {base:14.1%}  ({fair}/{total})")
        print(
            f"  {'break-even confidence to accept':<32} {2 / 3:14.1%}  -> "
            f"{'reject-everything is optimal without per-Charge discrimination' if base < 2 / 3 else 'accepting pays even blind'}"
        )
        print(
            f"  {'oracle accept rate (perfect t)':<32} {base:14.1%}  worth "
            f"{sum(s['excess_strict'] + s['excess_lenient'] for s in summaries):,.0f} against what we did"
        )

    if args.sweep:
        sweep_report(
            views,
            (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0, 1e9),
            args.anchor,
        )

    if args.json:
        Path(args.json).write_text(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
