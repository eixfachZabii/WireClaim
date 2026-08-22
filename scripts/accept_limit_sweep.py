"""Is our Limit too strict, and by how much in euros?

Strategy 2 went live at Game 21 and its first three Games accepted almost nothing: 12%,
6% and 19% of the Transactions we reviewed, against the 63-65% the three teams in profit
run. Game 23's whole loss was wrongful-rejection penalties (5,548 of them against zero
paid on accepts). This script measures whether that is a mispriced Limit and what moving
it is worth, in euros, on the real Field.

What it does
------------
* Scores every Game `replay_payoffs.usable_games` certifies -- i.e. every Game whose replay
  of our real submission reproduces the identity net computed from its own rows. Game 16
  fails that test and drops out on its own. Nothing here trusts a `/matrix` cell index; that
  bug (the endpoint publishes a trailing twenty-Game window, so positional indexing was off
  by three once Game 21 settled) was found independently while this was being written and is
  fixed in `pull_transactions.matrix`.
* Scores a parameterised `price_item` (`tune_pricing.price`, constants lifted out) through
  `replay_payoffs`, but with the reviewer side **decomposed** into the three things a
  Limit trades off:

      accept_fair   accepted a <= t  -- unavoidable; rejecting it would cost 1.5x this
      accept_over   accepted a >  t  -- pure loss, the price of generosity
      penalty       rejected a <= t  -- 1.5a, the price of strictness

  so `cost = accept_fair + accept_over + penalty` and the trade is visible instead of
  netted away.
* Reports the realised accept rate for every candidate, so a Limit setting can be read
  against the leaders' 63-65%.
* Sweeps `limit_ceiling`, `limit_quantile` and `coverage_floor` one at a time over three
  windows -- all Games, Games 15+, Games 21+ (Strategy 2's own era) -- with leave-one-out
  held-out totals, because the 21+ sample is four Games.

    PYTHONPATH=. pixi run python scripts/accept_limit_sweep.py all
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sys.path.insert(0, str(Path(__file__).resolve().parent / "experiments"))

from dump_evidence import load as load_evidence  # noqa: E402
from replay_payoffs import (  # noqa: E402
    INF,
    US,
    GameSnapshot,
    snapshot,
    usable_games,
)

try:  # `tune_pricing` moved under scripts/experiments/ mid-session
    from tune_pricing import Params, price  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - depends on the layout of the day
    from experiments.tune_pricing import Params, price  # type: ignore[no-redef]

from src.pricing import LIMIT_QUANTILE, Evidence  # noqa: E402


# ------------------------------------------------------------------------ reconstruction


def scoreable(us: str = US, exclude: Sequence[int] = ()) -> tuple[int, ...]:
    """Every Game it is legitimate to score against. Three filters, all loud.

    `replay_payoffs.usable_games` does the hard half: it rejects any Game whose replayed
    net does not reproduce the identity net computed from its own rows. Second, a Game with
    no cached model evidence has nothing to price, so it cannot enter a sweep -- run
    `scripts/dump_evidence.py --games N` to add one. Third, `exclude` is available for a
    Game we distrust for a reason outside the harness.

    Game 16 was the standing example of the third kind ("its Transactions do not
    reconstruct") and it is no longer one: it reproduces its -4,721.32 to the cent. The
    original failure was the `/matrix` window bug, which compared Game 16's rows against
    Game 17's published cell. It is kept out of the headline numbers only so they stay
    comparable with the earlier measurements; `--exclude ''` scores it, and it changes
    nothing that matters -- +634 of income at every ceiling, and a gain over the previous
    constants of +35,726 either way, because its two Line Items are ones we reject at any
    Limit in the sweep.
    """
    return tuple(
        g
        for g in usable_games(us=us)
        if load_evidence(g) is not None and g not in set(exclude)
    )


def windows(us: str = US, exclude: Sequence[int] = ()) -> dict[str, tuple[int, ...]]:
    """The three samples the answer is measured on.

    All Games, Games 15+ (the "recent Field" window that chose the shipped ceiling), and
    Games 21+ -- Strategy 2's own era, the only on-policy sample and much the smallest.
    """
    everything = scoreable(us, exclude)
    return {
        "all": everything,
        "15+": tuple(g for g in everything if g >= 15),
        "21+": tuple(g for g in everything if g >= 21),
    }


def snapshots(games: Iterable[int], us: str = US) -> list[GameSnapshot]:
    return [snapshot(g, us) for g in games]


# ---------------------------------------------------------------------------- decomposed


@dataclass(frozen=True)
class Decomposition:
    """One Game (or several) scored with the reviewer side split three ways."""

    income: float = 0.0
    #: accepted a <= t: money we owe. Rejecting these is what costs 1.5x.
    accept_fair: float = 0.0
    #: accepted a > t: pure loss. This is the whole risk of a loose Limit.
    accept_over: float = 0.0
    #: rejected a <= t: 1.5a of wrongful-rejection penalty. The price of strictness.
    penalty: float = 0.0
    reviews: int = 0
    accepts: int = 0
    #: worst single accepted Overcharge, and where
    worst_over: float = 0.0
    worst_over_where: str = ""

    @property
    def cost(self) -> float:
        return self.accept_fair + self.accept_over + self.penalty

    @property
    def net(self) -> float:
        return self.income - self.cost

    @property
    def accept_rate(self) -> float:
        return self.accepts / self.reviews if self.reviews else 0.0

    def __add__(self, other: "Decomposition") -> "Decomposition":
        worst, where = (
            (self.worst_over, self.worst_over_where)
            if self.worst_over >= other.worst_over
            else (other.worst_over, other.worst_over_where)
        )
        return Decomposition(
            income=self.income + other.income,
            accept_fair=self.accept_fair + other.accept_fair,
            accept_over=self.accept_over + other.accept_over,
            penalty=self.penalty + other.penalty,
            reviews=self.reviews + other.reviews,
            accepts=self.accepts + other.accepts,
            worst_over=worst,
            worst_over_where=where,
        )


def fair_point(snap: GameSnapshot, index: int, rule: str = "mid") -> float:
    """A representative Fair Value inside the inverted bracket.

    `mid` is `replay_payoffs`' own rule and the one the self-check is exact for. The other
    two exist because 44 of 192 Line Items in Games 1-14 have **no upper bracket** -- no
    team ever had a Charge rightfully rejected on them -- so `mid` falls back to `t_lo`, a
    *lower bound*. Every counterfactual Charge above that lower bound is then scored as an
    accepted Overcharge even though it may well have been fair. That biases the whole
    pay-versus-penalty decomposition toward strictness, so it has to be bounded:

        lo   t = t_lo always          -- most pessimistic about generosity
        hi   t = t_hi, or +inf when the bracket is open above -- most optimistic

    The truth is inside. If the recommendation survives `hi`, censoring is not driving it.
    """
    lo, hi = snap.fair_brackets[index]
    if rule == "lo":
        return lo
    if rule == "hi":
        return hi
    return lo if hi == INF else (lo + hi) / 2.0


def decompose(
    snap: GameSnapshot,
    submission: Mapping[int, tuple[float, float]],
    *,
    limit_rule: str = "mid",
    t_rule: str = "mid",
) -> Decomposition:
    """`replay_payoffs.replay`, with the reviewer side split into its three causes.

    Identical arithmetic: `net` here equals `replay(...).net` for the same inputs, which
    `--self-check` asserts against the published cell.
    """
    total = Decomposition()
    for index in snap.line_items:
        charge, limit = submission.get(index, (0.0, 0.0))
        t = fair_point(snap, index, t_rule)
        income = 0.0
        accept_fair = accept_over = penalty = 0.0
        accepts = 0
        worst = 0.0
        for team in snap.opponents:
            their_limit = snap.limit_point(index, team, limit_rule)
            if charge <= their_limit or charge <= t:
                income += charge
            theirs = snap.charges[index][team]
            if theirs <= limit:
                accepts += 1
                if theirs <= t:
                    accept_fair += theirs
                else:
                    accept_over += theirs
                    worst = max(worst, theirs)
            elif theirs <= t and theirs != INF:
                # An unrecoverable Charge (inf) was rejected by all sixteen reviewers, so it
                # sat above every Limit in the Field; it cannot be a wrongful rejection.
                penalty += 1.5 * theirs
        total = total + Decomposition(
            income=income,
            accept_fair=accept_fair,
            accept_over=accept_over,
            penalty=penalty,
            reviews=len(snap.opponents),
            accepts=accepts,
            worst_over=worst,
            worst_over_where=f"G{snap.game_id} item {index}",
        )
    return total


_EVIDENCE: dict[int, dict[int, Evidence]] = {}


def evidence_for(snap: GameSnapshot) -> dict[int, Evidence]:
    if snap.game_id in _EVIDENCE:
        return _EVIDENCE[snap.game_id]
    cached = load_evidence(snap.game_id)
    if cached is None:
        raise SystemExit(f"no cached evidence for Game {snap.game_id}; run dump_evidence.py")
    book = {index: cached[index] for index in snap.line_items if index in cached}
    _EVIDENCE[snap.game_id] = book
    return book


def score(
    snaps: Sequence[GameSnapshot],
    params: Params,
    *,
    limit_rule: str = "mid",
    t_rule: str = "mid",
) -> Decomposition:
    total = Decomposition()
    for snap in snaps:
        book = {index: price(item, params) for index, item in evidence_for(snap).items()}
        total = total + decompose(snap, book, limit_rule=limit_rule, t_rule=t_rule)
    return total


def per_game(snaps: Sequence[GameSnapshot], params: Params) -> dict[int, Decomposition]:
    return {snap.game_id: score([snap], params) for snap in snaps}


# -------------------------------------------------------------------------------- sweeps

CEILINGS = tuple(round(0.20 + 0.05 * k, 2) for k in range(0, 37))  # 0.20 .. 2.00
QUANTILES = tuple(round(0.05 + 0.05 * k, 2) for k in range(0, 18))  # 0.05 .. 0.90
FLOORS = tuple(round(0.0 + 0.05 * k, 2) for k in range(0, 17))  # 0.00 .. 0.80

AXES = {
    "limit_ceiling": CEILINGS,
    "limit_quantile": QUANTILES,
    "coverage_floor": FLOORS,
}


def axis(
    snaps: Sequence[GameSnapshot], base: Params, field: str, values: Sequence[float]
) -> list[tuple[float, Decomposition]]:
    return [(v, score(snaps, replace(base, **{field: v}))) for v in values]


def smoothed_peak(rows: Sequence[tuple[float, Decomposition]], span: int = 1) -> float:
    """Argmax of the net smoothed over neighbours -- picks a plateau, not a spike."""
    best = (-math.inf, 0.0)
    for i, (x, _) in enumerate(rows):
        window = rows[max(0, i - span) : i + span + 1]
        value = statistics.fmean(d.net for _, d in window)
        if value > best[0]:
            best = (value, x)
    return best[1]


def leave_one_out(
    snaps: Sequence[GameSnapshot], base: Params, field: str, values: Sequence[float]
) -> tuple[float, list[tuple[int, float, float]]]:
    """Tune on every Game but one, score the one. Returns (held-out total, rows)."""
    held = 0.0
    rows = []
    for snap in snaps:
        train = [s for s in snaps if s.game_id != snap.game_id]
        chosen = smoothed_peak(axis(train, base, field, values))
        got = score([snap], replace(base, **{field: chosen})).net
        held += got
        rows.append((snap.game_id, chosen, got))
    return held, rows


# --------------------------------------------------------------------------------- print


def _row(label: str, d: Decomposition) -> str:
    return (
        f"  {label:<18} net {d.net:12,.0f}  income {d.income:11,.0f}  "
        f"pay_fair {d.accept_fair:10,.0f}  pay_over {d.accept_over:10,.0f}  "
        f"penalty {d.penalty:11,.0f}  accept {d.accept_rate:5.1%}"
    )


def show_axis(snaps, base: Params, field: str, title: str) -> None:
    rows = axis(snaps, base, field, AXES[field])
    best = max(rows, key=lambda kv: kv[1].net)
    plateau = smoothed_peak(rows)
    print(f"\n{title}: {field} over {len(snaps)} Games")
    print("-" * 118)
    for value, d in rows:
        mark = ""
        if value == best[0]:
            mark += "  <- argmax"
        if value == plateau:
            mark += "  <- plateau"
        print(_row(f"{field}={value:.2f}", d) + mark)


def self_check(snaps) -> None:
    from replay_payoffs import our_actual_submission, replay

    print("\nself-check: our real submission replayed against the published cell")
    print("-" * 118)
    worst = 0.0
    for snap in snaps:
        book = our_actual_submission(snap)
        d = decompose(snap, book)
        r = replay(snap, book)
        worst = max(worst, abs(d.net - snap.published_net), abs(r.net - snap.published_net))
        flag = "OK  " if abs(d.net - snap.published_net) < 0.01 else "FAIL"
        print(
            f"  G{snap.game_id:3d} {flag} replay {d.net:12,.2f}  published {snap.published_net:12,.2f}"
            f"  items {len(snap.line_items):2d}  accept {d.accept_rate:5.1%}"
            f"  pay_fair {d.accept_fair:9,.0f} pay_over {d.accept_over:9,.0f}"
            f" penalty {d.penalty:10,.0f}"
        )
    print(f"  worst absolute deviation: {worst:.6f}")


def show_actual(snaps) -> None:
    """Our live submission next to what `price_item` would produce on the cached evidence.

    These are not the same thing, and the gap is the first thing to establish before
    blaming a constant: the live Strategy 2 accepted 6-19% of Transactions in Games 21-24
    while the shipped constants on the cached evidence accept 57%. If the live Limit is far
    below `price_item`'s, the strictness is coming from somewhere else in the pipeline.
    """
    print("\nlive submission vs price_item on the cached evidence")
    print("-" * 118)
    print(
        "  game item     median cov      a_live      b_live     a_priced     b_priced"
        "        t_lo        t_hi"
    )
    for snap in snaps:
        book = evidence_for(snap)
        for index in snap.line_items:
            item = book.get(index)
            a_live = snap.charges[index][snap.us]
            lo, hi = snap.limit_brackets[index][snap.us]
            t_lo, t_hi = snap.fair_brackets[index]
            a_p, b_p = price(item, Params()) if item else (float("nan"), float("nan"))
            median = item.price_median if item else float("nan")
            cov = item.coverage_probability if item else float("nan")
            print(
                f"  G{snap.game_id:3d} {index:4d} {median:10,.0f} {cov:4.2f} "
                f"{a_live:11,.0f} {lo:7,.0f}-{'inf' if hi == INF else f'{hi:,.0f}':>7} "
                f"{a_p:11,.0f} {b_p:11,.0f} {t_lo:11,.0f} "
                f"{'inf' if t_hi == INF else f'{t_hi:11,.0f}'}"
            )


def censoring(snaps) -> None:
    """How much of the "pure loss" is an artefact of an open Fair Value bracket."""
    open_above = sum(1 for s in snaps for i in s.line_items if s.fair_brackets[i][1] == INF)
    items = sum(len(s.line_items) for s in snaps)
    print(f"\nFair Value brackets open above: {open_above} of {items} Line Items")
    print("-" * 118)
    for label, t_rule in (("t = t_lo (pessimistic)", "lo"), ("t = mid", "mid"), ("t = t_hi", "hi")):
        for ceiling in (0.30, 0.85):
            params = replace(Params(), limit_ceiling=ceiling, coverage_floor=LIMIT_QUANTILE)
            print(_row(f"{label} ceil={ceiling:.2f}", score(snaps, params, t_rule=t_rule)))


def mimic(snaps, teams_to_show: Sequence[str] | None = None) -> None:
    """Score *their* Limit with *our* Charge.

    The leaders run accept rates of 63-65%, so the obvious question is whether adopting
    their reviewing behaviour outright would make us money. This takes each opponent's
    reconstructed Limit (the midpoint of its inverted bracket) as ours, holds our shipped
    Charge fixed, and replays. It is the cleanest available test of "is a 65% accept rate
    profitable in this Field", because it uses a real team's actual thresholds rather than
    a multiplier we invented.
    """
    print("\nour Charge with each opponent's reconstructed Limit")
    print("-" * 118)
    names = teams_to_show or sorted({t for snap in snaps for t in snap.opponents})
    rows = []
    for team in names:
        total = Decomposition()
        for snap in snaps:
            book = {
                index: (price(item, Params())[0], snap.limit_point(index, team))
                for index, item in evidence_for(snap).items()
            }
            total = total + decompose(snap, book)
        rows.append((team, total))
    for team, total in sorted(rows, key=lambda kv: -kv[1].net):
        print(_row(team, total))
    ours = score(snaps, Params())
    print(_row("(our constants)", ours))


#: What this script recommended shipping, and what `src.pricing` now carries: the plateau of
#: every window, with the coverage collapse made exact instead of arriving via the -8 sigma
#: clamp inside the quantile. `Params()` reads the live constants, so once this is shipped
#: the two rows agree -- which is the point: re-running `recommend` re-derives the decision.
RECOMMENDED = replace(Params(), limit_ceiling=0.30, coverage_floor=1.0 - LIMIT_QUANTILE)

#: What was shipped before this measurement: a ceiling from the four Games 15-19, and a
#: coverage floor at the quantile rather than at `1 - quantile`.
PREVIOUS = replace(Params(), limit_ceiling=0.85, coverage_floor=LIMIT_QUANTILE)


def recommend(snaps_by_window) -> None:
    print("\nrecommendation: ceiling 0.30, coverage floor 1 - quantile = 2/3")
    print("-" * 118)
    for name, snaps in snaps_by_window.items():
        print(f"\n[{name}] {len(snaps)} Games")
        for label, params in (
            ("PREVIOUS 0.85", PREVIOUS),
            ("ceil=0.25", replace(Params(), limit_ceiling=0.25)),
            ("ceil=0.30", replace(Params(), limit_ceiling=0.30)),
            ("ceil=0.35", replace(Params(), limit_ceiling=0.35)),
            ("floor=2/3 only", replace(PREVIOUS, coverage_floor=1.0 - LIMIT_QUANTILE)),
            ("RECOMMENDED", RECOMMENDED),
            ("live constants", Params()),
        ):
            print(_row(label, score(snaps, params)))
        gain = score(snaps, RECOMMENDED).net - score(snaps, PREVIOUS).net
        print(f"    gain over the previous constants: {gain:+,.0f} over {len(snaps)} Games "
              f"({gain / len(snaps):+,.0f} a Game)")
        for rule in ("lo", "mid", "hi"):
            d0 = score(snaps, PREVIOUS, t_rule=rule)
            d1 = score(snaps, RECOMMENDED, t_rule=rule)
            print(f"    t={rule:<3} previous {d0.net:12,.0f}  recommended {d1.net:12,.0f}  "
                  f"gain {d1.net - d0.net:+12,.0f}")
    print("\nper-Game, recommended vs previous")
    for snap in snaps_by_window["all"]:
        a = score([snap], PREVIOUS)
        b = score([snap], RECOMMENDED)
        print(
            f"  G{snap.game_id:3d} previous {a.net:11,.0f} ({a.accept_rate:5.1%})  "
            f"recommended {b.net:11,.0f} ({b.accept_rate:5.1%})  diff {b.net - a.net:+11,.0f}"
        )


def main() -> None:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "self-check",
            "axes",
            "candidates",
            "loo",
            "tails",
            "actual",
            "censoring",
            "mimic",
            "recommend",
            "all",
        ),
        nargs="?",
        default="all",
    )
    parser.add_argument("--window", default=None, choices=("all", "15+", "21+"))
    parser.add_argument(
        "--exclude",
        default="16",
        help="comma-separated Games to leave out; '' scores every reconstructable Game",
    )
    args = parser.parse_args()

    win = windows(exclude=[int(g) for g in args.exclude.split(",") if g.strip()])
    snaps = {name: snapshots(games) for name, games in win.items()}
    chosen = [args.window] if args.window else list(win)

    if args.command in ("self-check", "all"):
        self_check(snaps["all"])

    if args.command in ("actual", "all"):
        show_actual(snaps["21+"])

    if args.command in ("censoring", "all"):
        for name in chosen:
            print(f"\n[{name}]")
            censoring(snaps[name])

    if args.command in ("recommend", "all"):
        recommend({name: snaps[name] for name in chosen})

    if args.command in ("mimic", "all"):
        for name in chosen:
            print(f"\n[{name}] {len(snaps[name])} Games")
            mimic(snaps[name])

    if args.command in ("axes", "all"):
        for name in chosen:
            for field in AXES:
                show_axis(snaps[name], Params(), field, f"[{name}]")

    if args.command in ("candidates", "all"):
        print("\nshipped vs candidates, per window")
        print("-" * 118)
        cands = {
            "shipped": Params(),
            "q=0.50": replace(Params(), limit_quantile=0.50),
            "q=0.50 ceil=1.0": replace(Params(), limit_quantile=0.50, limit_ceiling=1.0),
            "q=0.60 ceil=1.0": replace(Params(), limit_quantile=0.60, limit_ceiling=1.0),
            "q=0.70 ceil=1.0": replace(Params(), limit_quantile=0.70, limit_ceiling=1.0),
            "ceil=0.45": replace(Params(), limit_ceiling=0.45),
        }
        for name in chosen:
            print(f"\n[{name}] {len(snaps[name])} Games")
            for label, params in cands.items():
                print(_row(label, score(snaps[name], params)))

    if args.command in ("loo", "all"):
        for name in chosen:
            for field in AXES:
                held, rows = leave_one_out(snaps[name], Params(), field, AXES[field])
                picks = sorted({v for _, v, _ in rows})
                print(
                    f"\n[{name}] LOO {field}: held-out {held:,.0f}  "
                    f"picks {picks}  shipped {score(snaps[name], Params()).net:,.0f}"
                )

    if args.command in ("tails", "all"):
        print("\nis the catastrophic-overprice risk realised? worst accepted Overcharges")
        print("-" * 118)
        for label, params in (
            ("shipped", Params()),
            ("q=0.50 ceil=1.0", replace(Params(), limit_quantile=0.50, limit_ceiling=1.0)),
            ("b = median", replace(Params(), limit_quantile=0.999, limit_ceiling=1.0)),
        ):
            d = score(snaps["all"], params)
            print(
                f"  {label:<18} pay_over {d.accept_over:12,.0f}  "
                f"worst single row {d.worst_over:10,.0f} at {d.worst_over_where}"
            )


if __name__ == "__main__":  # pragma: no cover
    main()
