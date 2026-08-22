"""Settle the argument about `LIMIT_CEILING` with the six Games we have actually played.

The contradiction
-----------------
`LIMIT_CEILING` was moved 0.85 -> 0.30 on a sweep over Games 1-24 that showed strictness
winning by +35,700. But since Game 21 our penalties -- wrongful-rejection charges, 1.5a on a
Charge we rejected that turned out fair -- total **108,793**, about 75% of income, while we
paid almost nothing on accepted claims. That is the textbook signature of a Limit set too
low, so either the sweep does not transfer, or the penalties are unavoidable.

This script measures which, and it does five things `accept_limit_sweep.py` does not:

1. `sweep`    -- the ceiling over **Games 1-20, 21-26 and all 26**, not 15+/21+, so the old
                 window and the new one are disjoint and cannot borrow each other's Games.
2. `avoidable`-- decomposes the 108,793 against a **per-item oracle Limit `b = t`**. The
                 oracle is the upper bound on what any Limit rule could ever save, and the
                 point of it is that two thirds of a penalty is *not* a saving: rejecting a
                 fair Charge costs `1.5a` where accepting costs `a`, so an oracle that
                 avoids the penalty still pays `a`. Only the `0.5a` surcharge is avoidable.
3. `blame`    -- for every penalised Line Item, our estimate's median against the true
                 bracket, and the multiplier `k = their_charge / our_median` that would have
                 been needed to accept it. `k > 1` means no ceiling at or below 1.0 can
                 reach the item and the *estimate* is at fault, not the Limit.
4. `cliff`    -- how many penalised items had their Limit collapsed to exactly zero by
                 `covered <= COVERAGE_FLOOR`, and what that rule is worth in euros.
5. `holdout`  -- leave-one-out and a strict 1-20 / 21-26 train/test split, because six Games
                 is a tiny sample and the noise floor is ~26,600 for one prompt draw.

Everything reuses the validated harness: `replay_payoffs.snapshot` (all 26 Games reproduce
their published net to the cent), `invert_fair_values.brackets` for ground truth, and
`accept_limit_sweep.decompose` for the three-way split of the reviewer side.

    PYTHONPATH=. pixi run python scripts/limit_audit.py all
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "experiments"))

from accept_limit_sweep import (  # noqa: E402
    Decomposition,
    decompose,
    evidence_for,
    fair_point,
    score,
    snapshots,
)
from replay_payoffs import (  # noqa: E402
    INF,
    US,
    GameSnapshot,
    our_actual_submission,
    usable_games,
)

try:
    from tune_pricing import Params, price  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - depends on the layout of the day
    from experiments.tune_pricing import Params, price  # type: ignore[no-redef]

from dump_evidence import load as load_evidence  # noqa: E402

from src.domain.pricing.engine import Evidence, _lognormal_quantile, implied_sigma  # noqa: E402


# ------------------------------------------------------------------------------- windows


def scoreable(us: str = US) -> tuple[int, ...]:
    """Every Game that reconstructs *and* has cached model evidence to price.

    Nothing is excluded. Game 16 used to be held out of the headline numbers for
    comparability with older measurements; it replays to the cent and is scored here,
    because a window called "1-20" that silently drops a Game is not a window.
    """
    return tuple(g for g in usable_games(us=us) if load_evidence(g) is not None)


def windows(us: str = US) -> dict[str, tuple[int, ...]]:
    """Three samples, two of them **disjoint**.

    `1-20` is the pre-Strategy-2 record; `21-26` is every Game Strategy 2 has played, and
    the only sample where the ceiling under test was the ceiling in force (Games 25-26) or
    at least the pipeline under test (21-24 submitted `STANDARD_LIMIT = 35` from a lower
    layer, so even they are only half on-policy). They share no Game, so agreement between
    them is evidence and disagreement is a regime question rather than an artefact of one
    Game appearing in both totals.
    """
    everything = scoreable(us)
    return {
        "1-20": tuple(g for g in everything if g <= 20),
        "21-26": tuple(g for g in everything if g >= 21),
        "all": everything,
    }


# --------------------------------------------------------------------------------- sweeps

#: 0.00 is in the grid on purpose, and it is not a candidate: `b = 0` wrongfully rejects
#: every fair Charge and is the incident default (README R7/R10). It is here as the *left*
#: end of the plateau, because a sweep that rises monotonically towards it is telling you the
#: multiplier is not the binding constraint rather than telling you to reject everything.
CEILINGS = (
    0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.85, 1.00,
)
#: `1.0 - 1.0 / 3.0` rather than `2.0 / 3.0` on purpose: the two differ in the last bit and
#: the shipped floor is the former, so the sweep has to contain that exact float to be able
#: to report "shipped" as a row rather than as a nearby one.
FLOORS = (0.00, 0.10, 0.20, 0.30, 1.0 / 3.0, 0.40, 0.50, 0.60, 1.0 - 1.0 / 3.0, 0.70, 0.80)


#: Rules for what the Limit does when coverage is doubtful. Sweeping `coverage_floor` alone
#: **cannot** measure the cliff, and finding that out is half the answer: below the floor the
#: conditional quantile `(q - (1 - covered)) / covered` is already negative, `_normal_quantile`
#: saturates at -8, and the Limit comes out as `median * exp(-8 * sigma)` -- 5% of the median
#: at sigma 0.375, 0.8% at 0.60. So lowering the floor does not restore a usable Limit; it
#: only swaps an exact zero for a rounding error, which is why that sweep is flat to a few
#: euros. To put a price on the cliff the rule itself has to change.
COLLAPSE_RULES = {
    #: what ships: exact zero at `covered <= 2/3`
    "hard 2/3 (shipped)": ("hard", 1.0 - 1.0 / 3.0),
    "hard 1/2": ("hard", 0.50),
    "hard 1/3": ("hard", 1.0 / 3.0),
    #: no collapse at all: coverage doubt is ignored and the Limit is the ceiling
    "no collapse": ("none", 0.0),
    #: continuous: `b = covered * ceiling * median`. Still goes to zero as coverage does, so
    #: it keeps the invariant "the Limit collapses when coverage is genuinely doubtful"
    #: without the discontinuity at 2/3.
    "linear in covered": ("linear", 0.0),
    #: linear, but still exactly zero once coverage is worse than a coin flip
    "linear above 1/2": ("linear", 0.50),
}


def price_collapse(evidence: Evidence, params: Params, rule: str) -> tuple[float, float]:
    """`tune_pricing.price` with the coverage collapse replaced by one of `COLLAPSE_RULES`.

    Identical to `price` for `rule = "hard 2/3 (shipped)"`; asserted in
    `tests/test_pricing.py` only in the sense that both go through `price_item`'s arithmetic.
    """
    mode, threshold = COLLAPSE_RULES[rule]
    filled = evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    covered = filled.coverage_probability
    factor = min(
        max(params.charge_intercept - params.charge_slope * sigma, params.charge_low),
        params.charge_high,
    )
    charge = factor * filled.price_median
    ceiling = params.limit_ceiling * filled.price_median

    if mode == "hard":
        if covered <= threshold:
            limit = 0.0
        else:
            conditional = (params.limit_quantile - (1.0 - covered)) / covered
            limit = min(_lognormal_quantile(filled.price_median, sigma, conditional), ceiling)
    elif mode == "none":
        limit = min(_lognormal_quantile(filled.price_median, sigma, params.limit_quantile), ceiling)
    else:  # linear
        if covered <= threshold:
            limit = 0.0
        else:
            unconditional = min(
                _lognormal_quantile(filled.price_median, sigma, params.limit_quantile), ceiling
            )
            limit = covered * unconditional
    if params.cap_limit_at_charge:
        limit = min(limit, charge)
    return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)


def score_collapse(snaps: Sequence[GameSnapshot], params: Params, rule: str) -> Decomposition:
    total = Decomposition()
    for snap in snaps:
        book = {i: price_collapse(e, params, rule) for i, e in evidence_for(snap).items()}
        total = total + decompose(snap, book)
    return total


def _row(label: str, d: Decomposition) -> str:
    return (
        f"  {label:<20} net {d.net:12,.0f}  income {d.income:11,.0f}  "
        f"pay_fair {d.accept_fair:10,.0f}  pay_over {d.accept_over:10,.0f}  "
        f"penalty {d.penalty:11,.0f}  accept {d.accept_rate:5.1%}"
    )


def ceiling_axis(
    snaps: Sequence[GameSnapshot], base: Params = Params()
) -> list[tuple[float, Decomposition]]:
    return [(c, score(snaps, replace(base, limit_ceiling=c))) for c in CEILINGS]


def show_sweep(win: Mapping[str, Sequence[GameSnapshot]]) -> None:
    print("\n" + "=" * 122)
    print("1. THE CEILING, SWEPT OVER THREE SAMPLES (two of them disjoint)")
    print("=" * 122)
    axes = {name: ceiling_axis(snaps) for name, snaps in win.items()}
    print(
        f"\n  {'ceiling':<10}"
        + "".join(f"{name + ' (' + str(len(win[name])) + 'G)':>22}" for name in win)
    )
    for i, ceiling in enumerate(CEILINGS):
        cells = "".join(
            f"{axes[name][i][1].net:>15,.0f}{axes[name][i][1].accept_rate:>7.1%}"
            for name in win
        )
        mark = "  <- shipped" if ceiling == 0.30 else ("  <- was" if ceiling == 0.85 else "")
        print(f"  {ceiling:<10.2f}{cells}{mark}")
    for name, rows in axes.items():
        best = max(rows, key=lambda kv: kv[1].net)
        plateau = [c for c, d in rows if d.net >= best[1].net - 0.03 * abs(best[1].net)]
        per_game = (best[1].net - dict(rows)[0.30].net) / max(len(win[name]), 1)
        print(
            f"\n  [{name}] argmax {best[0]:.2f} at {best[1].net:,.0f}; "
            f"within 3% of it: {plateau}; "
            f"gain over shipped 0.30: {best[1].net - dict(rows)[0.30].net:+,.0f} "
            f"({per_game:+,.0f} a Game)"
        )
        print(f"  [{name}] full decomposition at the interesting points:")
        for ceiling in (0.20, 0.30, 0.45, 0.85):
            print(_row(f"ceiling={ceiling:.2f}", dict(rows)[ceiling]))


# ---------------------------------------------------------------------- avoidable penalty


def oracle_submission(
    snap: GameSnapshot, charges: Mapping[int, float]
) -> dict[int, tuple[float, float]]:
    """`b = t` per Line Item: the best Limit any rule could possibly pick.

    With `b = t` every fair Charge is accepted (cost `a`, which we owed) and every
    Overcharge is rejected (cost 0). So the oracle's reviewer cost is a hard lower bound,
    and the gap between it and ours is the *whole* headroom available to `LIMIT_CEILING`.
    """
    return {i: (charges.get(i, 0.0), fair_point(snap, i)) for i in snap.line_items}


def show_avoidable(win: Mapping[str, Sequence[GameSnapshot]]) -> None:
    print("\n" + "=" * 122)
    print("2. HOW MUCH OF THE PENALTY IS AVOIDABLE? (per-item oracle Limit b = t)")
    print("=" * 122)
    print(
        "\n  Rejecting a fair Charge costs 1.5a; accepting it costs a. So an oracle that\n"
        "  avoids a penalty of P still pays 2P/3 -- only P/3 is a saving. Anything the\n"
        "  oracle also pays is not a Limit problem and is not counted as one.\n"
    )
    print(
        "  game  our_b: penalty   pay_over    cost   ||  oracle: pay_fair    cost  ||"
        "  avoidable"
    )
    print("  " + "-" * 100)
    live_total = Decomposition()
    oracle_total = Decomposition()
    for snap in win["21-26"]:
        charges = {i: a for i, (a, _) in our_actual_submission(snap).items()}
        live = decompose(snap, our_actual_submission(snap))
        oracle = decompose(snap, oracle_submission(snap, charges))
        live_total = live_total + live
        oracle_total = oracle_total + oracle
        print(
            f"  G{snap.game_id:3d}  {live.penalty:13,.0f} {live.accept_over:10,.0f} "
            f"{live.cost:9,.0f}   || {oracle.accept_fair:16,.0f} {oracle.cost:8,.0f}  ||"
            f" {live.cost - oracle.cost:10,.0f}"
        )
    print("  " + "-" * 100)
    print(
        f"  21-26 {live_total.penalty:13,.0f} {live_total.accept_over:10,.0f} "
        f"{live_total.cost:9,.0f}   || {oracle_total.accept_fair:16,.0f} "
        f"{oracle_total.cost:8,.0f}  || {live_total.cost - oracle_total.cost:10,.0f}"
    )
    penalty = live_total.penalty
    owed = penalty * 2.0 / 3.0
    print(
        f"\n  Of {penalty:,.0f} in penalties over Games 21-26:\n"
        f"    {owed:12,.0f}  we owed anyway -- the oracle pays it as `pay_fair` (2/3 of P)\n"
        f"    {penalty - owed:12,.0f}  the 1.5x surcharge -- the only part strictness wasted\n"
        f"  plus {live_total.accept_over:,.0f} paid on accepted Overcharges, which the oracle\n"
        f"  avoids entirely, for a total oracle headroom of "
        f"{live_total.cost - oracle_total.cost:,.0f} over six Games.\n"
    )
    print("  The same question asked of the *shipped* pricer rather than the live submission")
    print("  (Games 21-24 submitted STANDARD_LIMIT = 35, so the live b is not price_item's):")
    print("  " + "-" * 100)
    for name, snaps in win.items():
        shipped = score(snaps, Params())
        oracle = Decomposition()
        for snap in snaps:
            book = {i: price(e, Params()) for i, e in evidence_for(snap).items()}
            charges = {i: a for i, (a, _) in book.items()}
            oracle = oracle + decompose(snap, oracle_submission(snap, charges))
        head = shipped.cost - oracle.cost
        print(
            f"  [{name}:{len(snaps)}G] shipped penalty {shipped.penalty:11,.0f}  "
            f"of which surcharge {shipped.penalty / 3:10,.0f}  "
            f"pay_over {shipped.accept_over:9,.0f}  "
            f"oracle headroom {head:11,.0f} ({head / max(len(snaps), 1):+,.0f}/Game)"
        )


# ------------------------------------------------------------------------ estimate or Limit


@dataclass(frozen=True)
class Penalised:
    game_id: int
    index: int
    their_charge: float
    median: float
    covered: float
    t_lo: float
    t_hi: float
    our_limit: float
    collapsed: bool

    @property
    def needed_k(self) -> float:
        """Ceiling multiplier that would have accepted this Charge: `a / median`."""
        return INF if self.median <= 0 else self.their_charge / self.median


def penalised_items(
    snap: GameSnapshot, submission: Mapping[int, tuple[float, float]]
) -> list[Penalised]:
    """Every (item, opponent Charge) pair we rejected that turned out to be fair."""
    book = evidence_for(snap)
    out: list[Penalised] = []
    for index in snap.line_items:
        _, limit = submission.get(index, (0.0, 0.0))
        t = fair_point(snap, index)
        item = book.get(index)
        median = item.price_median if item else 0.0
        covered = item.coverage_probability if item else 0.0
        lo, hi = snap.fair_brackets[index]
        for team in snap.opponents:
            theirs = snap.charges[index][team]
            if theirs != INF and theirs > limit and theirs <= t:
                out.append(
                    Penalised(
                        game_id=snap.game_id,
                        index=index,
                        their_charge=theirs,
                        median=median,
                        covered=covered,
                        t_lo=lo,
                        t_hi=hi,
                        our_limit=limit,
                        collapsed=limit == 0.0 and covered <= Params().coverage_floor,
                    )
                )
    return out


def show_blame(win: Mapping[str, Sequence[GameSnapshot]]) -> None:
    print("\n" + "=" * 122)
    print("3. IS THE ESTIMATE OR THE LIMIT AT FAULT?")
    print("=" * 122)
    print(
        "\n  For every Charge we penalised: our median against the true bracket, and the\n"
        "  ceiling `k = their_charge / our_median` that would have been needed. k > 1 is\n"
        "  out of reach of any ceiling at or below 1.0, so those penalties are the\n"
        "  estimate's fault and a looser multiplier only treats the symptom.\n"
    )
    print(
        "  game  items  penalised   median/t   k<=0.30  k<=0.45  k<=0.85  k<=1.0   k>1.0"
        "   (euros of penalty)"
    )
    print("  " + "-" * 112)
    everything: list[Penalised] = []
    for snap in win["all"]:
        rows = penalised_items(snap, {i: price(e, Params()) for i, e in evidence_for(snap).items()})
        everything.extend(rows)
        if not rows:
            continue
        ratios = [
            p.median / fair_point(snap, p.index)
            for p in rows
            if fair_point(snap, p.index) > 0 and p.median > 0
        ]
        buckets = [
            sum(1.5 * p.their_charge for p in rows if p.needed_k <= bound)
            for bound in (0.30, 0.45, 0.85, 1.0)
        ]
        over = sum(1.5 * p.their_charge for p in rows if p.needed_k > 1.0)
        print(
            f"  G{snap.game_id:3d} {len(snap.line_items):5d} {len(rows):10d} "
            f"{(statistics.median(ratios) if ratios else float('nan')):10.2f} "
            + "".join(f"{b:9,.0f}" for b in buckets)
            + f"{over:8,.0f}"
        )
    print("  " + "-" * 112)
    for name, snaps in win.items():
        ids = {s.game_id for s in snaps}
        rows = [p for p in everything if p.game_id in ids]
        if not rows:
            continue
        total = sum(1.5 * p.their_charge for p in rows)
        reachable = sum(1.5 * p.their_charge for p in rows if p.needed_k <= 1.0)
        ratios = [
            p.median / ((p.t_lo + p.t_hi) / 2 if p.t_hi != INF else p.t_lo)
            for p in rows
            if p.median > 0 and (p.t_lo > 0 or p.t_hi != INF)
        ]
        low = sum(1 for r in ratios if r < 1.0)
        print(
            f"  [{name}] {len(rows)} penalised Charges, {total:,.0f} of penalty; "
            f"{reachable:,.0f} ({reachable / total:.0%}) reachable by a ceiling <= 1.0, "
            f"{total - reachable:,.0f} ({1 - reachable / total:.0%}) not"
        )
        print(
            f"  [{name}] median(our median / true t) on penalised items = "
            f"{statistics.median(ratios):.2f}; "
            f"{low} of {len(ratios)} ({low / len(ratios):.0%}) had an estimate *below* t"
        )
    ks = sorted(p.needed_k for p in everything if p.needed_k != INF)
    if ks:
        qs = [statistics.quantiles(ks, n=10)[i] for i in (0, 4, 8)]
        print(
            f"\n  needed-k distribution over all penalised Charges: "
            f"p10 {qs[0]:.2f}  median {qs[1]:.2f}  p90 {qs[2]:.2f}"
        )


# ----------------------------------------------------------------------------- the cliff


def show_cliff(win: Mapping[str, Sequence[GameSnapshot]]) -> None:
    print("\n" + "=" * 122)
    print("4. THE COVERAGE CLIFF: `covered <= 2/3` -> Limit exactly zero")
    print("=" * 122)
    floor = Params().coverage_floor
    print(
        f"\n  COVERAGE_FLOOR = 1 - LIMIT_QUANTILE = {floor:.3f}, so an item the model calls\n"
        f"  60% covered gets a Limit of exactly 0 and every fair Charge on it is penalised.\n"
    )
    print("  game  items  collapsed  penalised_charges  of_which_collapsed  euros_collapsed")
    print("  " + "-" * 100)
    tot_items = tot_collapsed = 0
    for snap in win["all"]:
        book = evidence_for(snap)
        collapsed = [i for i, e in book.items() if e.coverage_probability <= floor]
        rows = penalised_items(snap, {i: price(e, Params()) for i, e in book.items()})
        hit = [p for p in rows if p.collapsed]
        tot_items += len(book)
        tot_collapsed += len(collapsed)
        if not rows and not collapsed:
            continue
        print(
            f"  G{snap.game_id:3d} {len(book):5d} {len(collapsed):10d} {len(rows):18d} "
            f"{len(hit):19d} {sum(1.5 * p.their_charge for p in hit):16,.0f}"
        )
    print("  " + "-" * 100)
    print(f"  {tot_collapsed} of {tot_items} Line Items are collapsed by the floor.\n")
    print("  (a) the floor swept as a threshold, at the shipped ceiling 0.30")
    print("  " + "-" * 100)
    for name, snaps in win.items():
        rows = [(f, score(snaps, replace(Params(), coverage_floor=f))) for f in FLOORS]
        best = max(rows, key=lambda kv: kv[1].net)
        shipped = dict(rows)[floor].net
        print(f"\n  [{name}] {len(snaps)} Games   (shipped floor {floor:.3f} -> {shipped:,.0f})")
        for f, d in rows:
            mark = "  <- shipped" if abs(f - floor) < 1e-9 else ""
            if f == best[0]:
                mark += "  <- argmax"
            print(_row(f"floor={f:.3f}", d) + mark)
        print(
            f"    best {best[0]:.3f} at {best[1].net:,.0f}: moving the threshold is worth "
            f"{best[1].net - shipped:+,.0f} over {len(snaps)} Games. Flat, and the reason is\n"
            f"    the -8 sigma clamp -- see COLLAPSE_RULES. The threshold is not the cliff."
        )
    print("\n  (b) the collapse *rule* replaced, which is the only way to price the cliff")
    print("  " + "-" * 100)
    for name, snaps in win.items():
        print(f"\n  [{name}] {len(snaps)} Games")
        base = score_collapse(snaps, Params(), "hard 2/3 (shipped)")
        for rule in COLLAPSE_RULES:
            d = score_collapse(snaps, Params(), rule)
            print(_row(rule, d) + f"  {d.net - base.net:+11,.0f}")


# ------------------------------------------------------------------------------- frontier


def show_frontier(win: Mapping[str, Sequence[GameSnapshot]]) -> None:
    """Steel-man the "too strict" reading: is the *anchor* wrong rather than the multiplier?

    Section 3 finds that on penalised items our median sits at 0.74-0.81 of the true `t`, so
    a Limit anchored on the median is systematically low exactly where it gets punished. If
    the low bias were confined to those items, anchoring the Limit on the band's *upper* end
    would buy the penalties back without loosening on the items where the median is high.
    That is the one version of "the Limit is too strict" that survives section 3, so it has
    to be measured rather than argued away.
    """
    print("\n" + "=" * 122)
    print("6. IS THE ANCHOR WRONG RATHER THAN THE MULTIPLIER? (Limit on price_high, not median)")
    print("=" * 122)
    print()

    def anchored(snaps: Sequence[GameSnapshot], k: float, anchor: str) -> Decomposition:
        total = Decomposition()
        for snap in snaps:
            book = {}
            for index, item in evidence_for(snap).items():
                filled = item.with_defaults()
                charge, _ = price(item, Params())
                base = filled.price_high if anchor == "high" else filled.price_median
                covered = filled.coverage_probability
                limit = 0.0 if covered <= Params().coverage_floor else min(k * base, charge)
                book[index] = (charge, round(max(limit, 0.0), 2))
            total = total + decompose(snap, book)
        return total

    for name, snaps in win.items():
        print(f"  [{name}] {len(snaps)} Games")
        print(_row("median x 0.30 (ship)", score(snaps, Params())))
        for k in (0.10, 0.15, 0.20, 0.30, 0.45):
            print(_row(f"price_high x {k:.2f}", anchored(snaps, k, "high")))
        print()


# -------------------------------------------------------------------------------- holdout


def _plateau_pick(rows: Sequence[tuple[float, Decomposition]]) -> float:
    """Argmax of the net smoothed over immediate neighbours: prefers a flat region."""
    best = (-math.inf, rows[0][0])
    for i, (x, _) in enumerate(rows):
        window = rows[max(0, i - 1) : i + 2]
        value = statistics.fmean(d.net for _, d in window)
        if value > best[0]:
            best = (value, x)
    return best[1]


def show_holdout(win: Mapping[str, Sequence[GameSnapshot]]) -> None:
    print("\n" + "=" * 122)
    print("5. OVERFITTING GUARDS: leave-one-out, and a disjoint train/test split")
    print("=" * 122)
    print(
        "\n  Treat anything under ~30,000 over 18 Games (~1,670 a Game) as noise: two draws\n"
        "  of the same evidence prompt differ by 26,622.\n"
    )
    for name, snaps in win.items():
        held = 0.0
        picks = []
        for snap in snaps:
            train = [s for s in snaps if s.game_id != snap.game_id]
            chosen = _plateau_pick(ceiling_axis(train))
            picks.append(chosen)
            held += score([snap], replace(Params(), limit_ceiling=chosen)).net
        shipped = score(snaps, Params()).net
        print(
            f"  [{name}] LOO held-out {held:12,.0f}  vs fixed-at-0.30 {shipped:12,.0f}  "
            f"picks {sorted(set(picks))}"
        )
    train, test = win["1-20"], win["21-26"]
    for a, b, la, lb in ((train, test, "1-20", "21-26"), (test, train, "21-26", "1-20")):
        chosen = _plateau_pick(ceiling_axis(list(a)))
        got = score(list(b), replace(Params(), limit_ceiling=chosen)).net
        base = score(list(b), Params()).net
        print(
            f"  train {la} -> ceiling {chosen:.2f}; scored on {lb}: {got:,.0f} "
            f"(shipped 0.30 scores {base:,.0f}, difference {got - base:+,.0f})"
        )


# ------------------------------------------------------------------------------------ CLI


def main() -> None:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=("sweep", "avoidable", "blame", "cliff", "frontier", "holdout", "all"),
    )
    args = parser.parse_args()
    win = {name: snapshots(games) for name, games in windows().items()}
    print("windows: " + ", ".join(f"{k}={list(g.game_id for g in v)}" for k, v in win.items()))
    if args.command in ("sweep", "all"):
        show_sweep(win)
    if args.command in ("avoidable", "all"):
        show_avoidable(win)
    if args.command in ("blame", "all"):
        show_blame(win)
    if args.command in ("cliff", "all"):
        show_cliff(win)
    if args.command in ("frontier", "all"):
        show_frontier(win)
    if args.command in ("holdout", "all"):
        show_holdout(win)


if __name__ == "__main__":  # pragma: no cover
    main()
