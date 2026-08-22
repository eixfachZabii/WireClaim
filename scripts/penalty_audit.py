"""The wrongful-rejection fees: is the `LIMIT_CEILING` cliff real, and what actually fixes it?

The question put to this script
-------------------------------
Over Games 19-27 we took **162,965** of wrongful-rejection penalties against **260,245** of
income, and paid 11,110 on everything we accepted. Rejecting a fair Charge costs `1.5a`
where accepting costs `a`, so accepting all of them would have cost 108,643 and the ceiling
on what a perfect Limit saves is **54,322** -- +86,170 would become +140,492.

`scripts/limit_audit.py` concluded the ceiling should stay at 0.30, resting partly on a
sweep with a very sharp cliff: 0.35 -> 0.40 costing 17,492 over six Games while 0.00-0.35 is
flat. `src/pricing.py` itself warns that "the Field's Limits are clustered, so the total
jumps whenever our Charge crosses a cluster; any peak found there is a fact about sixteen
specific opponents, not about pricing." So the cliff had to be decomposed item by item.

What it found
-------------
**1. The cliff is one Line Item.** Resolved at 0.01 the step is not at 0.35 -> 0.40 at all;
it is at **0.37 -> 0.38, and it is -17,591 of which Game 22 item 1 is -19,892**. Drop Game
22 and the same step is **+1,592** -- a gain. Game 22 has exactly one Line Item; its true
Fair Value is under 245.70; our estimate's median was **5,400**; and **ten opponents charged
exactly 2,000.00**. At ceiling 0.37 our Limit is 1,998 and rejects all ten; at 0.38 it is
2,052 and buys all ten. The cliff is our Limit crossing a cluster of identical placeholder
Charges on a single item where the estimator failed by a factor of 22.

**2. And yet the previous audit's *conclusion* about levels is right, for a better reason.**
At our current estimate quality the best single ceiling in 0.05..2.00 is worth **+300 over 27
Games** -- 0% of the 216,179 of oracle headroom (section 4). A level cannot discriminate
because it has nothing to discriminate on: `a / our_median` has median 0.47 on fair Charges
and 0.74 on Overcharges in the recent window, and at *every* threshold the euro trade
`0.5 * fair_captured - over_bought` is negative or within a few hundred euros of zero
(section 2). Raising the Limit is not the lever. That much of `limit_audit.py` stands.

**3. `LIMIT_QUANTILE` is decorative and the real second parameter was never swept.** Of 320
Line Items the derived quantile binds on **zero** of them (section 3); the ceiling binds on
226 and the coverage collapse on 94. So `b = min(quantile, CEILING * median, charge)` is in
practice `b = min(CEILING * median, charge)`, and the honest reading is that the shipped rule
has one knob, not three.

**4. A ceiling cannot bound what we pay, because it is a multiple of the number that broke.**
This is the finding. When the estimate blows up the ceiling blows up with it, so strictness
in *multiples* buys no protection at all against the estimator's upward tail -- it only
happens, in Game 22, to land on the safe side of 2,000 by luck. **Game 29, which settled
after this was written, is the same failure at the shipped 0.30**: median 7,138 against a
Fair Value under 57.30, thirteen opponents at exactly 2,000.00, `b = 0.30 * 7,138 = 2,142`,
and we bought all thirteen for **24,157 of pure loss**. 2,000.00 is the single most common
Charge above 500 euros in the whole record (28 rows, Games 7, 8, 22, 28, 29 -- section 1e).

**5. So the instrument is a cap in euros, not a lower multiple.** Add one term:

    b = min(quantile, CEILING * median, charge, CAP)      CAP = 12 * SETTLED_MEDIAN = 708

With the cap in place the ceiling is free to be loose, because the thing that made loosening
catastrophic is bounded. Over all 27 Games, against the shipped 0.30:

    0.30 + cap 708      +4,203      the minimal change: one new constant, ceiling untouched
    0.70 + cap 708     +17,525
    0.85 + cap 708     +17,665      <- 21-27: +8,566; 1-20: +9,100; Games 28-29: +21,289

and the previous audit's decisive out-of-sample result reverses (section 7c): training the
*ceiling alone* on Games 1-20 picks 0.70 and scores **-39,497** on 21-27, which is what
argued for strictness; training the *pair* picks (0.70, 32x) and scores **-1,980**, while
training the pair on 21-27 picks (0.85, 16x) and scores **+6,658** on 1-20.

Why this is not the same mistake in a new coordinate
----------------------------------------------------
A euro cap is exactly the kind of parameter that can be fitted to one cluster of Charges, so
it is only reported because all four of these hold at once:

* **It is a plateau.** Caps from 8x to 24x `SETTLED_MEDIAN` (472 to 1,416 euros, a factor of
  three) all score 100k-110k over 27 Games against the shipped 90.9k, in both disjoint
  windows (section 7). The edge is at 40x, which is where 2,000 gets through.
* **It survives redrawing the estimator.** Re-scored on all seven cached prompt framings --
  seven independent draws of the estimate over the same Cases, which is what the 26,622
  noise floor is a statement about -- the gain is positive in **7 of 7**, from +13,964 to
  +47,168 (section 8a). A number inside the noise floor that moves the same way under every
  redraw of the noise is not a coincidence.
* **No Game carries it.** Leave-one-Game-out is positive in **27 of 27** folds, range
  +13,259 to +20,279; the worst single Game is -2,614 against flat-0.40's -19,892
  (section 8d, 7b).
* **It is censoring-invariant.** +17,665 at `t_rule=lo` and `mid`, +27,141 at `hi`
  (section 8b), and exactly invariant to opponents' reconstructed Limits (8c).

And it has a mechanism rather than a fit: the settled Fair Value distribution has median 59
and p95 986, so a Limit above ~1,400 is claiming an item is in the top 2.5% of everything we
have ever seen -- a claim our own band cannot support, since `implied_sigma` has median 0.375
against a measured RMSLE of 0.80 and its width carries no signal.

What is *not* claimed
---------------------
The 54,322 is not recovered. Almost all of it is locked behind the estimate, not the Limit:
move the estimate a quarter of the way to the truth in log space and the best ceiling jumps
from 0.25 to 0.80 and from +300 to **+134,459** (section 4). The cap reaches ~8% of the
27-Game headroom and ~19% of the recent window's. It is a bound on a known failure mode, not
a fix for the estimator -- and `src/pricing.py` is right that fixing the band is worth more
than any constant in it.

Provenance
----------
Everything is `replay_payoffs.snapshot` (all Games reproduce their published net to the
cent), `invert_fair_values.brackets` for `t`, and `accept_limit_sweep.decompose` for the
three-way split of the reviewer side. Two things are new here:

* **Games 27+ are scored at all.** They have no `var/evidence/case_NN_model.json`, so every
  earlier sweep stopped at 26. `var/decisions/game_0NN.json` records the *blended* band that
  actually decided the number, and `price(that band, Params())` reproduces the shipped
  `(charge, limit)` **exactly, to the cent, for every item of Games 26, 27, 28 and 29** --
  which is a stronger provenance than the model cache, not a weaker one.
* **`--through` pins the window.** A Game settles every 12.6 minutes; without pinning, "all
  27 Games" silently means something different between two runs. Games past it are reported
  in section 9 as held out.

    PYTHONPATH=. pixi run python scripts/penalty_audit.py all
    PYTHONPATH=. pixi run python scripts/penalty_audit.py cliff --recent 21-26
    PYTHONPATH=. pixi run python scripts/penalty_audit.py recommend --through 27

Sections: `cliff` `reject` `binding` `split` `rules` `robust` `surface` `survive`
`recommend`. Nothing here writes anything, and nothing here changes `src/`.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "experiments"))

from accept_limit_sweep import Decomposition, decompose, fair_point  # noqa: E402
from replay_payoffs import (  # noqa: E402
    INF,
    US,
    GameSnapshot,
    our_actual_submission,
    snapshot,
    usable_games,
)

try:
    from tune_pricing import Params, price  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover
    from experiments.tune_pricing import Params, price  # type: ignore[no-redef]

from dump_evidence import load as load_model_evidence  # noqa: E402

from src.pricing import Evidence, _lognormal_quantile, implied_sigma  # noqa: E402

DECISIONS = Path("var/decisions")

NOISE_18 = 26_622.0


def noise_floor(games: int) -> float:
    return NOISE_18 * math.sqrt(games / 18.0)


# ------------------------------------------------------------------------------ evidence


@dataclass(frozen=True)
class ItemFacts:
    """Everything we knew about one Line Item at submission time, plus its source."""

    game_id: int
    index: int
    evidence: Evidence
    #: channel tags from the decision log, e.g. ("B:memory", "C:model"); () when unknown
    channels: tuple[str, ...] = ()
    #: the rule the live pipeline applied ("priced", "uncovered-free-option", ...)
    rule: str = ""
    #: where the Evidence came from: "model-cache" or "decision-log"
    source: str = "model-cache"
    #: Price Memory (Channel B) had a hit on this Line Item's wording. Measured log error
    #: 0.43 against the model's ~0.80, so this is the one channel flag with a number behind
    #: it, and the only per-item trust signal available at submission time.
    memory: bool = False


def _decision_log(game_id: int) -> dict[int, ItemFacts] | None:
    path = DECISIONS / f"game_{game_id:03d}.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    out: dict[int, ItemFacts] = {}
    for item in raw.get("items", []):
        index = int(item["index"])
        out[index] = ItemFacts(
            game_id=game_id,
            index=index,
            evidence=Evidence(
                index=index,
                coverage_probability=float(item["coverage_probability"]),
                price_low=float(item["price_low"]),
                price_median=float(item["price_median"]),
                price_high=float(item["price_high"]),
            ),
            channels=tuple(item.get("channels", ())),
            rule=str(item.get("rule", "")),
            source="decision-log",
            memory=any("memory" in c for c in item.get("channels", ())),
        )
    return out or None


def _memory_hits(game_id: int) -> set[int]:
    """Which Line Items Price Memory had a wording hit on.

    `var/evidence/case_NN_memory.json` is `channels.local_evidence` dumped for every Case,
    so this is available for Games 1-26 without a model call; Games 27+ carry the same fact
    in the decision log's `channels`. It is *not* a reconstruction after the fact -- the
    memory is keyed on wording, which is in the Case, so the flag was knowable at
    submission time. That matters: a rule may only condition on things we had.
    """
    hits = load_model_evidence(game_id, "memory")
    return set(hits) if hits else set()


_FACTS: dict[int, dict[int, ItemFacts]] = {}


def facts_for(snap: GameSnapshot) -> dict[int, ItemFacts]:
    """Our own estimate per Line Item, from the model cache or the live decision log.

    Games 1-26 have `var/evidence/case_NN_model.json`, which is what every earlier sweep
    scored. Games 27+ have no dumped evidence but do have `var/decisions/game_0NN.json`,
    written by the live pipeline, which records the *blended* band that actually decided
    the number -- strictly better provenance, and the only way to score Game 27 at all.
    `--evidence` chooses which source wins where both exist so the mixing is auditable.
    """
    if snap.game_id in _FACTS:
        return _FACTS[snap.game_id]
    raise RuntimeError("call load_facts() first")


def load_facts(game_ids: Iterable[int], prefer: str = "model") -> dict[int, dict[int, ItemFacts]]:
    for game_id in game_ids:
        cached = load_model_evidence(game_id)
        logged = _decision_log(game_id)
        hits = _memory_hits(game_id)
        model = (
            {
                i: ItemFacts(
                    game_id=game_id,
                    index=i,
                    evidence=e,
                    source="model-cache",
                    memory=i in hits,
                )
                for i, e in cached.items()
            }
            if cached
            else None
        )
        if prefer == "log":
            chosen = logged or model
        else:
            chosen = model or logged
        if chosen is None:
            continue
        # The memory flag comes from the Case either way, so fill it in for the decision-log
        # branch too when the dump exists -- the two agree where both are present.
        if hits:
            chosen = {
                i: (f if f.memory else replace(f, memory=i in hits))
                for i, f in chosen.items()
            }
        _FACTS[game_id] = chosen
    return _FACTS


def evidence_of(snap: GameSnapshot) -> dict[int, Evidence]:
    book = facts_for(snap)
    return {i: book[i].evidence for i in snap.line_items if i in book}


def scoreable(games: Iterable[int]) -> tuple[int, ...]:
    return tuple(g for g in games if g in _FACTS)


def snapshots(games: Iterable[int]) -> list[GameSnapshot]:
    return [snapshot(g) for g in games]


# -------------------------------------------------------------------------------- pricing


def book_for(snap: GameSnapshot, params: Params) -> dict[int, tuple[float, float]]:
    return {i: price(e, params) for i, e in evidence_of(snap).items()}


def score(snaps: Sequence[GameSnapshot], params: Params) -> Decomposition:
    total = Decomposition()
    for snap in snaps:
        total = total + decompose(snap, book_for(snap, params))
    return total


def per_item(
    snap: GameSnapshot, submission: Mapping[int, tuple[float, float]]
) -> dict[int, Decomposition]:
    """`decompose`, but kept per Line Item instead of summed.

    The sum over the returned values is exactly `decompose(snap, submission)`; asserted in
    `check_identities`. Everything in section 1 depends on that, because the claim "one item
    carries the cliff" is only meaningful if item contributions add up to the total.
    """
    out: dict[int, Decomposition] = {}
    for index in snap.line_items:
        out[index] = decompose(
            _one_item(snap, index), {index: submission.get(index, (0.0, 0.0))}
        )
    return out


def _one_item(snap: GameSnapshot, index: int) -> GameSnapshot:
    return replace(snap, line_items=(index,))


# ------------------------------------------------------------------------ 1. is it a cliff


#: 0.01 steps across the reported cliff, then coarser out to 1.00. The reported jump is
#: 0.35 -> 0.40; a step that size cannot tell a cliff from a ramp, so it is resolved at 0.01.
FINE = tuple(round(0.20 + 0.01 * k, 2) for k in range(0, 41))  # 0.20 .. 0.60
COARSE = (0.65, 0.70, 0.75, 0.85, 1.00)
CEILINGS = FINE + COARSE


#: `limit_audit.py`'s published step, which this script exists to explain. Reproduced exactly
#: before anything is said about it, because "the cliff is one item" is only interesting if it
#: is a claim about *that* number rather than about a number nearby.
LIMIT_AUDIT_STEP = -17_492.0


def reconcile_limit_audit(win: Mapping[str, Sequence[GameSnapshot]]) -> str:
    """Reproduce the published 0.35 -> 0.40 step on its own terms, then split it by Game.

    Its terms are Games 21-26 and the *model cache* as the evidence source, so both are forced
    here regardless of what the rest of the run uses -- a reconciliation that quietly changes
    the window or the evidence is not one. `_FACTS` is restored afterwards.
    """
    saved = dict(_FACTS)
    try:
        _FACTS.clear()
        load_facts(sorted(saved), "model")
        snaps = [s for s in win["21-26"] if s.game_id in _FACTS]
        if not snaps:
            return "\n  1z. Cannot reconcile: no model-cache evidence for Games 21-26.\n"
        rows = []
        for ceiling in (0.35, 0.40):
            rows.append(score(snaps, replace(Params(), limit_ceiling=ceiling)).net)
        step = rows[1] - rows[0]
        per = [
            (
                s.game_id,
                decompose(s, book_for(s, replace(Params(), limit_ceiling=0.40))).net
                - decompose(s, book_for(s, replace(Params(), limit_ceiling=0.35))).net,
            )
            for s in snaps
        ]
        worst = min(per, key=lambda kv: kv[1])
        rest = sum(v for g, v in per if g != worst[0])
        agree = "MATCHES" if abs(step - LIMIT_AUDIT_STEP) < 1.0 else "DOES NOT MATCH"
        return (
            "\n  1z. `limit_audit.py`'s published step, on its own terms (Games 21-26,"
            " model cache).\n\n"
            f"      0.35 -> {rows[0]:+,.0f}    0.40 -> {rows[1]:+,.0f}    step {step:+,.0f}"
            f"    {agree} the published {LIMIT_AUDIT_STEP:+,.0f}\n\n"
            "      split by Game: "
            + "  ".join(f"G{g} {v:+,.0f}" for g, v in per)
            + f"\n\n      G{worst[0]} alone supplies {worst[1]:+,.0f} of it; the other"
            f" {len(per) - 1} Games sum to {rest:+,.0f}\n"
            "      -- i.e. they *prefer* the looser ceiling. The step is one Game's sign,\n"
            "      not the sample's.\n"
        )
    finally:
        _FACTS.clear()
        _FACTS.update(saved)


def show_cliff(win: Mapping[str, Sequence[GameSnapshot]], recent: str) -> None:
    print("\n" + "=" * 118)
    print("1. THE 0.35 -> 0.40 CLIFF: RESOLVED AT 0.01, THEN DECOMPOSED BY GAME AND BY ITEM")
    print("=" * 118)
    lo, hi = 0.35, 0.40
    snaps = win[recent]
    base = Params()
    print(reconcile_limit_audit(win))

    print(f"\n  1a. The recent window ({recent}, {len(snaps)}G) at 0.01 resolution.\n")
    print(f"  {'ceiling':<9}{'net':>12}{'d(net)':>10}{'penalty':>12}{'pay_over':>11}{'accept':>8}")
    prev = None
    for c in FINE:
        d = score(snaps, replace(base, limit_ceiling=c))
        step = "" if prev is None else f"{d.net - prev:>10,.0f}"
        print(
            f"  {c:<9.2f}{d.net:>12,.0f}{step:>10}{d.penalty:>12,.0f}"
            f"{d.accept_over:>11,.0f}{d.accept_rate:>8.1%}"
        )
        prev = d.net

    print(f"\n  1b. Where does net(0.40) - net(0.35) come from? Per Game, {recent}.\n")
    print(f"  {'game':<7}{'net@0.35':>12}{'net@0.40':>12}{'delta':>11}{'share':>8}")
    deltas: list[tuple[int, float]] = []
    for snap in snaps:
        a = decompose(snap, book_for(snap, replace(base, limit_ceiling=lo)))
        b = decompose(snap, book_for(snap, replace(base, limit_ceiling=hi)))
        deltas.append((snap.game_id, b.net - a.net))
    total = sum(d for _, d in deltas)
    for game_id, delta in deltas:
        share = delta / total if total else 0.0
        print(f"  G{game_id:<6d}{'':>12}{'':>12}{delta:>11,.0f}{share:>8.0%}")
    print(f"  {'total':<7}{'':>12}{'':>12}{total:>11,.0f}")

    print("\n  1c. Per (Game, Line Item), the items that move at all. Ranked by |delta|.\n")
    print(
        f"  {'where':<14}{'delta':>10}{'d_penalty':>11}{'d_pay_fair':>12}"
        f"{'d_pay_over':>12}{'b@0.35':>10}{'b@0.40':>10}{'median':>11}{'cov':>6}"
    )
    rows: list[tuple[float, str]] = []
    for snap in snaps:
        low = per_item(snap, book_for(snap, replace(base, limit_ceiling=lo)))
        high = per_item(snap, book_for(snap, replace(base, limit_ceiling=hi)))
        blo = book_for(snap, replace(base, limit_ceiling=lo))
        bhi = book_for(snap, replace(base, limit_ceiling=hi))
        book = facts_for(snap)
        for index in snap.line_items:
            delta = high[index].net - low[index].net
            if abs(delta) < 1.0:
                continue
            ev = book[index].evidence if index in book else None
            rows.append(
                (
                    delta,
                    f"  G{snap.game_id:<3d} item {index:<4d}{delta:>10,.0f}"
                    f"{high[index].penalty - low[index].penalty:>11,.0f}"
                    f"{high[index].accept_fair - low[index].accept_fair:>12,.0f}"
                    f"{high[index].accept_over - low[index].accept_over:>12,.0f}"
                    f"{blo.get(index, (0, 0))[1]:>10,.0f}{bhi.get(index, (0, 0))[1]:>10,.0f}"
                    f"{(ev.price_median if ev else 0):>11,.0f}"
                    f"{(ev.coverage_probability if ev else 0):>6.2f}",
                )
            )
    for _, line in sorted(rows, key=lambda kv: kv[0]):
        print(line)
    if rows:
        worst = min(rows, key=lambda kv: kv[0])
        losers = sorted(r for r, _ in rows if r < 0)
        print(
            f"\n  {len(rows)} of {sum(len(s.line_items) for s in snaps)} Line Items move by"
            f" more than 1 euro. Worst single item {worst[0]:,.0f}"
            f" = {worst[0] / total:.0%} of the {total:,.0f} step;"
            f" worst three {sum(losers[:3]):,.0f} = {sum(losers[:3]) / total:.0%}."
        )

    print("\n  1d. The same step with one Game left out at a time (jackknife).\n")
    print(f"  {'dropped':<10}{'step 0.35->0.40':>18}{'':4}{'dropped':<10}{'step':>12}")
    jack = []
    for snap in snaps:
        rest = [s for s in snaps if s.game_id != snap.game_id]
        a = score(rest, replace(base, limit_ceiling=lo)).net
        b = score(rest, replace(base, limit_ceiling=hi)).net
        jack.append((snap.game_id, b - a))
    for i in range(0, len(jack), 2):
        left = f"  -G{jack[i][0]:<7d}{jack[i][1]:>18,.0f}"
        right = (
            f"    -G{jack[i + 1][0]:<8d}{jack[i + 1][1]:>12,.0f}"
            if i + 1 < len(jack)
            else ""
        )
        print(left + right)
    steps = [d for _, d in jack]
    print(
        f"\n  Jackknifed step spans {min(steps):,.0f} .. {max(steps):,.0f}."
        f" Sign flips on leave-one-out: {sum(1 for s in steps if s > 0)}/{len(steps)} folds"
        f" turn the cliff into a gain."
    )
    show_clusters(win["all28"])


def show_clusters(snaps: Sequence[GameSnapshot], floor: float = 500.0) -> None:
    """The Field's large Charges, counted. This is why the cliff is where it is.

    A ceiling is a multiple of *our* median, so it cannot bound what we pay: when the
    estimate blows up the ceiling blows up with it. What we pay is bounded by where the
    Field's Charges actually sit, and above 500 euros they are not spread out -- they pile
    on round numbers, one of which recurs often enough to be a Field constant.
    """
    print("\n  1e. The Field's Charges above 500 euros are not a continuum.\n")
    counts: dict[float, int] = defaultdict(int)
    where: dict[float, set[int]] = defaultdict(set)
    for snap in snaps:
        for index in snap.line_items:
            for team, charge in snap.charges[index].items():
                if team == snap.us or charge == INF or charge < floor:
                    continue
                counts[round(charge, 2)] += 1
                where[round(charge, 2)].add(snap.game_id)
    print(f"  {'charge':>12}{'rows':>7}{'games':>7}   which Games")
    for value, n in sorted(counts.items(), key=lambda kv: -kv[1])[:8]:
        print(
            f"  {value:>12,.2f}{n:>7d}{len(where[value]):>7d}   "
            + ",".join(f"G{g}" for g in sorted(where[value]))
        )
    two_k = counts.get(2000.0, 0)
    print(
        f"\n  2,000.00 exactly is the single most common Charge above 500 in the whole"
        f"\n  record: {two_k} rows across {len(where.get(2000.0, ()))} Games. It looks like a"
        "\n  self-imposed cap several teams apply to their own Charge, and it recurs -- so a"
        "\n  Limit that ever rises above 2,000 buys a dozen of them at once. That is exactly"
        "\n  what happened in Game 22 at ceiling 0.38, and again in Game 29 at the *shipped*"
        "\n  0.30 (see section 9)."
    )


# ------------------------------------------------------------------- 2. what we reject


@dataclass(frozen=True)
class Review:
    """One Charge somebody sent us, with our own estimate for the item beside it."""

    game_id: int
    index: int
    team: str
    charge: float
    t: float
    t_open: bool
    median: float
    covered: float
    sigma: float
    memory: bool

    @property
    def fair(self) -> bool:
        return self.charge <= self.t

    @property
    def ratio(self) -> float:
        """`a / our median`. **Conditioned on our own estimate, never on `t`.**

        This is the only quantity a Limit rule of the shipped shape can act on, because
        `b = ceiling * median` accepts exactly the Charges with `ratio <= ceiling`. So the
        whole question "can a ceiling discriminate?" is the question "do fair and unfair
        Charges separate in this one number?".
        """
        return INF if self.median <= 0 else self.charge / self.median


def reviews(snaps: Sequence[GameSnapshot]) -> list[Review]:
    out: list[Review] = []
    for snap in snaps:
        book = facts_for(snap)
        for index in snap.line_items:
            item = book.get(index)
            ev = item.evidence.with_defaults() if item else None
            lo, hi = snap.fair_brackets[index]
            t = fair_point(snap, index)
            for team in snap.opponents:
                charge = snap.charges[index][team]
                if charge == INF:
                    # Rejected by all sixteen reviewers, so it sat above every Limit in the
                    # Field: it can never be a wrongful rejection and is not a review we can
                    # counterfactually change. Excluding it is what `decompose` does too.
                    continue
                out.append(
                    Review(
                        game_id=snap.game_id,
                        index=index,
                        team=team,
                        charge=charge,
                        t=t,
                        t_open=hi == INF,
                        median=ev.price_median if ev else 0.0,
                        covered=ev.coverage_probability if ev else 0.0,
                        sigma=(
                            implied_sigma(ev.price_low, ev.price_median, ev.price_high)
                            if ev
                            else 0.0
                        ),
                        memory=bool(item and item.memory),
                    )
                )
    return out


def _pct(rows: Sequence[float], q: float) -> float:
    if not rows:
        return float("nan")
    ordered = sorted(rows)
    k = min(int(q * (len(ordered) - 1) + 0.5), len(ordered) - 1)
    return ordered[k]


def show_reject(win: Mapping[str, Sequence[GameSnapshot]], recent: str) -> None:
    print("\n" + "=" * 118)
    print("2. WHAT WE REJECT, AND WHETHER A THRESHOLD CAN TELL IT APART")
    print("=" * 118)
    base = Params()
    for name in ("all", recent):
        snaps = win[name]
        rows = reviews(snaps)
        shipped = {
            (s.game_id, i): b
            for s in snaps
            for i, (_, b) in book_for(s, base).items()
        }
        rejected_fair = [
            r for r in rows if r.fair and r.charge > shipped.get((r.game_id, r.index), 0.0)
        ]
        print(
            f"\n  [{name}: {len(snaps)}G] {len(rows)} recoverable Charges reviewed,"
            f" {sum(1 for r in rows if r.fair)} of them fair."
            f" At the shipped ceiling {len(rejected_fair)} fair Charges are rejected,"
            f" carrying {1.5 * sum(r.charge for r in rejected_fair):,.0f} of penalty"
            f" ({0.5 * sum(r.charge for r in rejected_fair):,.0f} of it avoidable surcharge)."
        )
        gaps = [
            (r.charge - shipped.get((r.game_id, r.index), 0.0)) / r.charge
            for r in rejected_fair
            if r.charge > 0
        ]
        print(
            f"  How far below the Charge our Limit sat, as a fraction of the Charge:"
            f" p25 {_pct(gaps, 0.25):.2f}  median {_pct(gaps, 0.50):.2f}"
            f"  p75 {_pct(gaps, 0.75):.2f}  p95 {_pct(gaps, 0.95):.2f}"
            f"  (1.00 = our Limit was zero: {sum(1 for g in gaps if g > 0.999)} of"
            f" {len(gaps)})"
        )
        print(
            "\n  The separation question. `a/our_median` is the only thing a ceiling sees,\n"
            "  so a ceiling can work only if fair and unfair Charges separate in it.\n"
        )
        for label, subset in (
            ("fair (a <= t)", [r for r in rows if r.fair]),
            ("over (a >  t)", [r for r in rows if not r.fair]),
        ):
            ratios = [r.ratio for r in subset if r.ratio != INF]
            euros = sum(r.charge for r in subset)
            print(
                f"    {label}  n {len(subset):5d}  euros {euros:12,.0f}  a/median:"
                f" p10 {_pct(ratios, 0.10):7.2f}  p25 {_pct(ratios, 0.25):7.2f}"
                f"  median {_pct(ratios, 0.50):7.2f}  p75 {_pct(ratios, 0.75):7.2f}"
                f"  p90 {_pct(ratios, 0.90):7.2f}"
            )
        fair_e = sum(r.charge for r in rows if r.fair and r.ratio != INF)
        over_e = sum(r.charge for r in rows if not r.fair and r.ratio != INF)
        print(
            "\n  Euro-weighted, as a threshold on a/median is raised (this ignores the"
            "\n  quantile and the `b <= a` clamp, so it is the ceiling's best case):\n"
        )
        print(
            f"    {'k':<7}{'fair a captured':>18}{'of fair':>9}"
            f"{'over a bought':>16}{'of over':>9}{'0.5*fair - over':>18}"
        )
        for k in (0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70, 0.85, 1.00, 1.50):
            got = sum(r.charge for r in rows if r.fair and r.ratio <= k)
            bought = sum(r.charge for r in rows if not r.fair and r.ratio <= k)
            print(
                f"    {k:<7.2f}{got:>18,.0f}{got / fair_e if fair_e else 0:>9.0%}"
                f"{bought:>16,.0f}{bought / over_e if over_e else 0:>9.0%}"
                f"{0.5 * got - bought:>18,.0f}"
            )
        print(
            "\n  The last column is the whole trade, exactly: capturing a fair Charge we\n"
            "  were rejecting saves 0.5a (we owed a either way); capturing an Overcharge\n"
            "  costs the full a. Positive means the threshold pays."
        )


# ------------------------------------------------------- 3. which term of the min binds


def terms(ev: Evidence, params: Params) -> dict[str, float]:
    """The three candidate Limits inside `b = min(quantile, ceiling*median, charge)`."""
    filled = ev.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    covered = filled.coverage_probability
    factor = min(
        max(params.charge_intercept - params.charge_slope * sigma, params.charge_low),
        params.charge_high,
    )
    charge = factor * filled.price_median
    if covered <= params.coverage_floor:
        return {"collapse": 0.0}
    conditional = (params.limit_quantile - (1.0 - covered)) / covered
    return {
        "quantile": _lognormal_quantile(filled.price_median, sigma, conditional),
        "ceiling": params.limit_ceiling * filled.price_median,
        "charge": charge,
    }


def show_binding(win: Mapping[str, Sequence[GameSnapshot]], recent: str) -> None:
    print("\n" + "=" * 118)
    print("3. WHICH OF THE THREE TERMS IN `b = min(quantile, CEILING*median, charge)` BINDS?")
    print("=" * 118)
    print(
        "\n  If the ceiling binds everywhere then `LIMIT_QUANTILE` is decorative and the\n"
        "  real parameter is the ceiling. Counted per Line Item, and weighted by the\n"
        "  penalty each item actually carries, because an item we never review is free.\n"
    )
    base = Params()
    for name in ("all", recent):
        snaps = win[name]
        counts: dict[str, int] = defaultdict(int)
        euros: dict[str, float] = defaultdict(float)
        for snap in snaps:
            book = facts_for(snap)
            live = per_item(snap, book_for(snap, base))
            for index in snap.line_items:
                item = book.get(index)
                if item is None:
                    continue
                t = terms(item.evidence, base)
                which = min(t, key=lambda key: t[key])
                counts[which] += 1
                euros[which] += live[index].penalty
        total = sum(counts.values())
        pen = sum(euros.values())
        print(f"  [{name}: {len(snaps)}G] {total} Line Items, {pen:,.0f} of penalty")
        for which in ("collapse", "quantile", "ceiling", "charge"):
            print(
                f"    {which:<10} binds on {counts[which]:4d} items"
                f" ({counts[which] / total if total else 0:5.1%})"
                f"   carrying {euros[which]:11,.0f} of penalty"
                f" ({euros[which] / pen if pen else 0:5.1%})"
            )


# ------------------------------------------------- 4. the Limit's share of the headroom


def oracle_book(snap: GameSnapshot, charges: Mapping[int, float]) -> dict[int, tuple[float, float]]:
    """`b = t` per Line Item: accepts every fair Charge, rejects every Overcharge.

    A hard lower bound on reviewer cost, so the gap to it is the *whole* headroom any Limit
    rule could ever reach. It is not achievable -- it reads `t` -- and is only used as a
    denominator.
    """
    return {i: (charges.get(i, 0.0), fair_point(snap, i)) for i in snap.line_items}


def shrink(ev: Evidence, snap: GameSnapshot, index: int, lam: float) -> Evidence:
    """Move the estimate a fraction `lam` of the way to the truth, in log space.

    `median' = median * (t / median) ** lam`, with the band scaled by the same factor so
    `implied_sigma` is unchanged. `lam = 0` is our estimator; `lam = 1` is perfect. This is
    an **oracle experiment** -- it reads `t` -- and exists only to answer "how much of the
    headroom is locked behind the estimate rather than the Limit". Nothing here is shippable.
    """
    t = fair_point(snap, index)
    filled = ev.with_defaults()
    if lam <= 0 or filled.price_median <= 0 or t <= 0:
        return ev
    factor = (t / filled.price_median) ** lam
    return Evidence(
        index=ev.index,
        coverage_probability=filled.coverage_probability,
        price_low=filled.price_low * factor,
        price_median=filled.price_median * factor,
        price_high=filled.price_high * factor,
    )


CEILING_GRID = tuple(round(0.05 * k, 2) for k in range(1, 41))  # 0.05 .. 2.00


def best_ceiling(
    snaps: Sequence[GameSnapshot], lam: float = 0.0, base: Params = Params()
) -> tuple[float, Decomposition]:
    rows = []
    for c in CEILING_GRID:
        params = replace(base, limit_ceiling=c)
        total = Decomposition()
        for snap in snaps:
            book = {
                i: price(shrink(f.evidence, snap, i, lam), params)
                for i, f in facts_for(snap).items()
                if i in snap.line_items
            }
            total = total + decompose(snap, book)
        rows.append((c, total))
    return max(rows, key=lambda kv: kv[1].net)


def show_split(win: Mapping[str, Sequence[GameSnapshot]], recent: str) -> None:
    print("\n" + "=" * 118)
    print("4. HOW MUCH OF THE HEADROOM IS A LIMIT PROBLEM, AND HOW MUCH AN ESTIMATE PROBLEM?")
    print("=" * 118)
    print(
        "\n  Three reference points, all scored on the same Games with the same Field:\n"
        "    shipped   `LIMIT_CEILING = 0.30`\n"
        "    best k    the best single ceiling in 0.05..2.00 -- everything a level can buy\n"
        "    oracle    `b = t` per item -- everything *any* Limit rule could ever buy\n"
        "  and then the same, with the estimate moved a fraction `lam` toward the truth.\n"
    )
    for name in ("all", recent):
        snaps = win[name]
        n = len(snaps)
        shipped = score(snaps, Params())
        oracle = Decomposition()
        for snap in snaps:
            book = book_for(snap, Params())
            oracle = oracle + decompose(
                snap, oracle_book(snap, {i: a for i, (a, _) in book.items()})
            )
        print(
            f"  [{name}: {n}G]  noise floor {noise_floor(n):,.0f}\n"
            f"    shipped   net {shipped.net:11,.0f}  penalty {shipped.penalty:11,.0f}"
            f"  pay_over {shipped.accept_over:10,.0f}"
        )
        print(
            f"    oracle    net {oracle.net:11,.0f}  penalty {oracle.penalty:11,.0f}"
            f"  pay_over {oracle.accept_over:10,.0f}"
            f"   -> total headroom {oracle.net - shipped.net:+,.0f}"
            f" ({(oracle.net - shipped.net) / n:+,.0f}/Game)"
        )
        print(f"\n    {'lam':<7}{'best k':>9}{'net at best k':>16}{'vs shipped':>13}"
              f"{'oracle net':>13}{'ceiling share':>15}")
        for lam in (0.0, 0.25, 0.5, 0.75, 1.0):
            k, d = best_ceiling(snaps, lam)
            orc = Decomposition()
            for snap in snaps:
                book = {
                    i: price(shrink(f.evidence, snap, i, lam), replace(Params(), limit_ceiling=k))
                    for i, f in facts_for(snap).items()
                    if i in snap.line_items
                }
                orc = orc + decompose(snap, oracle_book(snap, {i: a for i, (a, _) in book.items()}))
            head = orc.net - shipped.net
            share = (d.net - shipped.net) / head if head > 0 else float("nan")
            print(
                f"    {lam:<7.2f}{k:>9.2f}{d.net:>16,.0f}{d.net - shipped.net:>+13,.0f}"
                f"{orc.net:>13,.0f}{share:>15.0%}"
            )
        print(
            "\n    Read the last column as: of everything a perfect Limit would be worth at\n"
            "    that estimate quality, this is the fraction a single ceiling captures.\n"
        )


# ------------------------------------------------------------- 5. rules, not levels


@dataclass(frozen=True)
class Rule:
    """A Limit rule richer than one multiplier. `price` for `Rule()` is the shipped pricer.

    Every field conditions only on things we had at submission time -- the band, the coverage
    probability, and whether Price Memory had a wording hit. None of them reads `t`.
    """

    name: str = "shipped"
    ceiling: float = 0.30
    #: hard euro cap on the Limit, in multiples of `SETTLED_MEDIAN = 59`. The catastrophic
    #: accepted Overcharges all sit on items whose median is two orders above the settled
    #: median, so a cap is the one term that targets them without touching ordinary items.
    cap_multiple: float = INF
    #: ceiling used when `coverage_probability` is below `coverage_split`
    ceiling_doubtful: float | None = None
    coverage_split: float = 0.95
    #: `ceiling = clamp(ceiling - sigma_slope * implied_sigma, 0.05, 2.0)`
    sigma_slope: float = 0.0
    #: ceiling used on Line Items Price Memory priced (measured log error 0.43 vs ~0.80)
    ceiling_memory: float | None = None
    #: anchor the ceiling on `price_low` instead of the median
    anchor_low: bool = False
    #: floor the Limit at this multiple of `SETTLED_MEDIAN` whenever the item is covered,
    #: so an item we distrust still accepts the small Charges instead of paying 1.5a on them
    floor_multiple: float = 0.0


SETTLED_MEDIAN = 59.0


def price_rule(facts: ItemFacts, rule: Rule, base: Params = Params()) -> tuple[float, float]:
    ev = facts.evidence.with_defaults()
    sigma = implied_sigma(ev.price_low, ev.price_median, ev.price_high)
    covered = ev.coverage_probability
    factor = min(
        max(base.charge_intercept - base.charge_slope * sigma, base.charge_low),
        base.charge_high,
    )
    charge = factor * ev.price_median

    ceiling = rule.ceiling
    if rule.ceiling_memory is not None and facts.memory:
        ceiling = rule.ceiling_memory
    if rule.ceiling_doubtful is not None and covered < rule.coverage_split:
        ceiling = rule.ceiling_doubtful
    if rule.sigma_slope:
        ceiling = min(max(ceiling - rule.sigma_slope * sigma, 0.05), 2.0)

    if covered <= base.coverage_floor:
        limit = 0.0
    else:
        anchor = ev.price_low if rule.anchor_low else ev.price_median
        conditional = (base.limit_quantile - (1.0 - covered)) / covered
        limit = min(
            _lognormal_quantile(ev.price_median, sigma, conditional), ceiling * anchor
        )
        if rule.floor_multiple:
            limit = max(limit, rule.floor_multiple * SETTLED_MEDIAN)
    limit = min(limit, rule.cap_multiple * SETTLED_MEDIAN)
    limit = min(limit, charge)
    return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)


def score_rule(snaps: Sequence[GameSnapshot], rule: Rule) -> Decomposition:
    total = Decomposition()
    for snap in snaps:
        book = {
            i: price_rule(f, rule)
            for i, f in facts_for(snap).items()
            if i in snap.line_items
        }
        total = total + decompose(snap, book)
    return total


def candidate_rules() -> list[Rule]:
    out = [Rule("shipped ceiling 0.30")]
    for k in (0.35, 0.40, 0.45, 0.60, 0.85):
        out.append(Rule(f"flat ceiling {k:.2f}", ceiling=k))
    for cap in (4.0, 8.0, 16.0, 32.0):
        out.append(Rule(f"0.30 + cap {cap:.0f}x59", cap_multiple=cap))
    for k, cap in ((0.60, 8.0), (0.60, 16.0), (0.85, 8.0), (0.85, 16.0), (1.00, 8.0)):
        out.append(Rule(f"{k:.2f} + cap {cap:.0f}x59", ceiling=k, cap_multiple=cap))
    for hi, lo in ((0.60, 0.20), (0.85, 0.20), (0.60, 0.30)):
        out.append(
            Rule(f"cov>=.95 {hi:.2f} else {lo:.2f}", ceiling=hi, ceiling_doubtful=lo)
        )
    for slope in (0.3, 0.6, 1.0):
        out.append(Rule(f"0.85 - {slope:.1f}*sigma", ceiling=0.85, sigma_slope=slope))
    for mem in (0.60, 0.85, 1.00):
        out.append(Rule(f"memory {mem:.2f}, model 0.30", ceiling=0.30, ceiling_memory=mem))
    for k in (0.60, 0.85, 1.20):
        out.append(Rule(f"anchor price_low {k:.2f}", ceiling=k, anchor_low=True))
    for f in (0.25, 0.5, 1.0):
        out.append(Rule(f"0.30 + floor {f:.2f}x59", floor_multiple=f))
    return out


def show_rules(win: Mapping[str, Sequence[GameSnapshot]], recent: str) -> None:
    print("\n" + "=" * 118)
    print("5. RULES THAT DISCRIMINATE, SCORED AGAINST THE LEVEL THAT DOES NOT")
    print("=" * 118)
    print(
        "\n  Every rule conditions only on evidence we had at submission time. The two\n"
        "  windows are disjoint, so agreement between them is evidence rather than reuse.\n"
    )
    base_all = score(win["all"], Params()).net
    base_recent = score(win[recent], Params()).net
    print(
        f"  {'rule':<26}{'all 27G':>12}{'vs 0.30':>10}"
        f"{'  ' + recent:>12}{'vs 0.30':>10}{'accept':>8}{'pay_over':>11}{'penalty':>11}"
    )
    print("  " + "-" * 100)
    for rule in candidate_rules():
        a = score_rule(win["all"], rule)
        b = score_rule(win[recent], rule)
        print(
            f"  {rule.name:<26}{a.net:>12,.0f}{a.net - base_all:>+10,.0f}"
            f"{b.net:>12,.0f}{b.net - base_recent:>+10,.0f}"
            f"{b.accept_rate:>8.1%}{b.accept_over:>11,.0f}{b.penalty:>11,.0f}"
        )
    print(
        f"\n  Noise floor is {noise_floor(27):,.0f} over 27 Games and"
        f" {noise_floor(len(win[recent])):,.0f} over {len(win[recent])}."
        " Nothing inside those bands is a finding."
    )


# --------------------------------------------------------- 6. is the level robust at all


def show_robust(win: Mapping[str, Sequence[GameSnapshot]], recent: str) -> None:
    print("\n" + "=" * 118)
    print("6. IS THE PREFERENCE FOR 0.30 A FACT ABOUT PRICING OR ABOUT A FEW GAMES?")
    print("=" * 118)
    print(
        "\n  For each ceiling: the total over all 27 Games, the per-Game gain against the\n"
        "  shipped 0.30, how many Games improve, and a 10%-trimmed mean of the per-Game\n"
        "  gains. A total driven by one Game shows up as a large mean with a small median.\n"
    )
    snaps = win["all"]
    ref = {s.game_id: decompose(s, book_for(s, Params())).net for s in snaps}
    print(
        f"  {'ceiling':<9}{'net 27G':>12}{'vs 0.30':>11}{'per Game':>10}"
        f"{'win/loss':>10}{'median':>10}{'trim mean':>11}{'worst Game':>20}"
    )
    for c in (0.20, 0.25, 0.30, 0.35, 0.37, 0.38, 0.40, 0.45, 0.50, 0.60, 0.85, 1.00):
        params = replace(Params(), limit_ceiling=c)
        gains = []
        for s in snaps:
            gains.append((s.game_id, decompose(s, book_for(s, params)).net - ref[s.game_id]))
        total = sum(g for _, g in gains)
        wins = sum(1 for _, g in gains if g > 1)
        losses = sum(1 for _, g in gains if g < -1)
        ordered = sorted(g for _, g in gains)
        cut = max(1, len(ordered) // 10)
        trimmed = statistics.fmean(ordered[cut:-cut]) if len(ordered) > 2 * cut else 0.0
        worst = min(gains, key=lambda kv: kv[1])
        mark = "  <- shipped" if c == 0.30 else ""
        print(
            f"  {c:<9.2f}{score(snaps, params).net:>12,.0f}{total:>+11,.0f}"
            f"{total / len(snaps):>+10,.0f}{f'{wins}/{losses}':>10}"
            f"{statistics.median(g for _, g in gains):>+10,.0f}{trimmed:>+11,.0f}"
            f"{f'G{worst[0]} {worst[1]:+,.0f}':>20}{mark}"
        )


# -------------------------------------------------- 7. the (ceiling, cap) surface itself


#: The cap is in multiples of `SETTLED_MEDIAN = 59` on purpose rather than in raw euros:
#: it is a statement about how far above the *typical settled Fair Value* we are willing to
#: pay on a single Line Item, which is a fact about the tournament, not about one Game.
CAPS = (2.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0, INF)
GRID_CEILINGS = (0.30, 0.40, 0.50, 0.60, 0.70, 0.85, 1.00, 1.20)


def show_surface(win: Mapping[str, Sequence[GameSnapshot]], recent: str) -> None:
    print("\n" + "=" * 118)
    print("7. THE (CEILING, CAP) SURFACE -- IS THE CAP A PLATEAU OR A FIT TO GAME 22?")
    print("=" * 118)
    print(
        "\n  A euro cap on the Limit is exactly the kind of parameter that can be fitted to"
        "\n  one cluster of Charges, so it only counts if it is flat over a wide range and"
        "\n  agrees between the two disjoint windows. Cap is in multiples of the settled"
        "\n  median Fair Value (59). `inf` is the shipped rule: no cap.\n"
    )
    for name in ("1-20", recent, "all"):
        snaps = win[name]
        print(f"\n  [{name}: {len(snaps)}G]  net, by ceiling (rows) and cap (columns)\n")
        print("  ceil " + "".join(f"{('inf' if c == INF else f'{c:.0f}x'):>9}" for c in CAPS))
        for k in GRID_CEILINGS:
            cells = []
            for cap in CAPS:
                d = score_rule(snaps, Rule("", ceiling=k, cap_multiple=cap))
                cells.append(f"{d.net / 1000:>9.1f}")
            print(f"  {k:<5.2f}" + "".join(cells))
        print("  (thousands of euros)")

    print("\n  7b. The candidates, per Game, over all 27. A rule that wins on one Game is not")
    print("      a rule. `worst` is the single Game that loses most against the shipped 0.30.\n")
    snaps = win["all"]
    ref = {s.game_id: decompose(s, book_for(s, Params())).net for s in snaps}
    print(
        f"  {'rule':<24}{'total':>11}{'win/loss':>10}{'median':>9}{'trim mean':>11}"
        f"{'worst Game':>18}{'best Game':>18}"
    )
    for rule in (
        Rule("cap 8x, ceiling 0.30", ceiling=0.30, cap_multiple=8.0),
        Rule("cap 16x, ceiling 0.30", ceiling=0.30, cap_multiple=16.0),
        Rule("cap 8x, ceiling 0.60", ceiling=0.60, cap_multiple=8.0),
        Rule("cap 16x, ceiling 0.60", ceiling=0.60, cap_multiple=16.0),
        Rule("cap 16x, ceiling 0.85", ceiling=0.85, cap_multiple=16.0),
        Rule("cap 8x, ceiling 0.85", ceiling=0.85, cap_multiple=8.0),
        Rule("memory 0.85 / 0.30", ceiling=0.30, ceiling_memory=0.85),
        Rule("flat 0.40", ceiling=0.40),
    ):
        gains = [
            (s.game_id, score_rule([s], rule).net - ref[s.game_id]) for s in snaps
        ]
        ordered = sorted(g for _, g in gains)
        cut = max(1, len(ordered) // 10)
        worst = min(gains, key=lambda kv: kv[1])
        best = max(gains, key=lambda kv: kv[1])
        print(
            f"  {rule.name:<24}{sum(g for _, g in gains):>+11,.0f}"
            f"{f'{sum(1 for _, g in gains if g > 1)}/{sum(1 for _, g in gains if g < -1)}':>10}"
            f"{statistics.median(g for _, g in gains):>+9,.0f}"
            f"{statistics.fmean(ordered[cut:-cut]):>+11,.0f}"
            f"{f'G{worst[0]} {worst[1]:+,.0f}':>18}"
            f"{f'G{best[0]} {best[1]:+,.0f}':>18}"
        )

    print("\n  7c. Disjoint train/test. Train the pair on one window, score it on the other.\n")
    pairs = [(k, c) for k in GRID_CEILINGS for c in CAPS]
    for train_name, test_name in (("1-20", recent), (recent, "1-20")):
        train, test = win[train_name], win[test_name]
        chosen = max(pairs, key=lambda kc: score_rule(train, Rule("", ceiling=kc[0], cap_multiple=kc[1])).net)
        got = score_rule(test, Rule("", ceiling=chosen[0], cap_multiple=chosen[1])).net
        shipped = score(test, Params()).net
        print(
            f"    train {train_name:<6} -> ceiling {chosen[0]:.2f}, cap"
            f" {('inf' if chosen[1] == INF else f'{chosen[1]:.0f}x')}"
            f"   scored on {test_name}: {got:+,.0f}"
            f"  (shipped 0.30/no cap: {shipped:+,.0f}; {got - shipped:+,.0f})"
        )
    print(
        "\n    Compare with the same split for the ceiling alone, which is the previous\n"
        "    audit's headline result:"
    )
    for train_name, test_name in (("1-20", recent), (recent, "1-20")):
        train, test = win[train_name], win[test_name]
        k = max(CEILING_GRID, key=lambda c: score(train, replace(Params(), limit_ceiling=c)).net)
        got = score(test, replace(Params(), limit_ceiling=k)).net
        shipped = score(test, Params()).net
        print(
            f"    train {train_name:<6} -> ceiling {k:.2f} alone"
            f"   scored on {test_name}: {got:+,.0f}"
            f"  (shipped: {shipped:+,.0f}; {got - shipped:+,.0f})"
        )


# ------------------------------------------------------ 8. does the recommendation survive


#: The recommendation, and the two things it is compared against everywhere below.
SHIPPED = Rule("shipped 0.30, no cap", ceiling=0.30)
PROPOSED = Rule("0.85 + cap 12x59", ceiling=0.85, cap_multiple=12.0)
CONSERVATIVE = Rule("0.30 + cap 12x59", ceiling=0.30, cap_multiple=12.0)

#: Alternative prompt framings dumped by `scripts/dump_evidence.py` variants. Each is a
#: different *draw* of the estimator over the same Cases, which is what the 26,622 noise
#: floor is a statement about -- so re-scoring the recommendation on each of them measures
#: the recommendation against that noise directly instead of comparing to it in the abstract.
EVIDENCE_TAGS = ("model", "nohint", "nohint2", "anchor", "anchornohint", "mag", "rate")


def _facts_from_tag(game_id: int, tag: str) -> dict[int, ItemFacts] | None:
    cached = load_model_evidence(game_id, tag)
    if not cached:
        return None
    hits = _memory_hits(game_id)
    return {
        i: ItemFacts(game_id=game_id, index=i, evidence=e, source=tag, memory=i in hits)
        for i, e in cached.items()
    }


def show_survive(win: Mapping[str, Sequence[GameSnapshot]], recent: str) -> None:
    print("\n" + "=" * 118)
    print("8. DOES THE RECOMMENDATION SURVIVE REDRAWING THE ESTIMATOR AND THE CENSORING?")
    print("=" * 118)
    print(
        "\n  8a. Re-scored on every alternative prompt framing we have cached. Each tag is a\n"
        "  different draw of the estimator over the same Cases, so this is the noise floor\n"
        "  measured rather than quoted. Only the Games a tag covers are scored, so the\n"
        "  levels are not comparable across rows -- the *difference* column is.\n"
    )
    print(
        f"  {'evidence draw':<16}{'games':>7}{'shipped':>11}{'+cap only':>12}"
        f"{'proposed':>11}{'cap only vs':>13}{'proposed vs':>13}"
    )
    saved = dict(_FACTS)
    for tag in EVIDENCE_TAGS:
        _FACTS.clear()
        covered = []
        for game_id in saved:
            book = _facts_from_tag(game_id, tag)
            if book:
                _FACTS[game_id] = book
                covered.append(game_id)
        if not covered:
            continue
        snaps = [s for s in win["all"] if s.game_id in _FACTS]
        a = score_rule(snaps, SHIPPED).net
        b = score_rule(snaps, CONSERVATIVE).net
        c = score_rule(snaps, PROPOSED).net
        print(
            f"  {tag:<16}{len(snaps):>7}{a:>11,.0f}{b:>12,.0f}{c:>11,.0f}"
            f"{b - a:>+13,.0f}{c - a:>+13,.0f}"
        )
    _FACTS.clear()
    _FACTS.update(saved)
    print(
        "\n  A recommendation that is a fact about pricing is positive in every row; one that\n"
        "  is a fact about one prompt is not."
    )

    print(
        "\n  8b. Censoring. 27 Games carry Line Items with no upper bracket, where `t` falls\n"
        "  back to a *lower* bound, so an accepted Charge above it is scored as an\n"
        "  Overcharge that may have been fair. `t_rule=hi` pushes every open bracket to\n"
        "  +inf, which is maximally generous to a loose Limit; `lo` is maximally hostile.\n"
    )
    for t_rule in ("lo", "mid", "hi"):
        row = []
        for name in ("all", recent):
            snaps = win[name]
            a = Decomposition()
            b = Decomposition()
            for snap in snaps:
                book_a = {i: price_rule(f, SHIPPED) for i, f in facts_for(snap).items() if i in snap.line_items}
                book_b = {i: price_rule(f, PROPOSED) for i, f in facts_for(snap).items() if i in snap.line_items}
                a = a + decompose(snap, book_a, t_rule=t_rule)
                b = b + decompose(snap, book_b, t_rule=t_rule)
            row.append((name, a.net, b.net))
        print(
            f"    t_rule={t_rule:<4}"
            + "   ".join(
                f"[{n}] shipped {x:+10,.0f}  proposed {y:+10,.0f}  ({y - x:+,.0f})"
                for n, x, y in row
            )
        )

    print(
        "\n  8c. Opponents' reconstructed Limits. `mid`/`lo`/`hi` inside the inverted bracket.\n"
        "  Only our *income* can depend on this, so it is a check that the Charge side is\n"
        "  not carrying the result.\n"
    )
    for limit_rule in ("lo", "mid", "hi"):
        snaps = win["all"]
        a = Decomposition()
        b = Decomposition()
        for snap in snaps:
            book_a = {i: price_rule(f, SHIPPED) for i, f in facts_for(snap).items() if i in snap.line_items}
            book_b = {i: price_rule(f, PROPOSED) for i, f in facts_for(snap).items() if i in snap.line_items}
            a = a + decompose(snap, book_a, limit_rule=limit_rule)
            b = b + decompose(snap, book_b, limit_rule=limit_rule)
        print(
            f"    limit_rule={limit_rule:<4} shipped {a.net:+11,.0f}  proposed {b.net:+11,.0f}"
            f"  ({b.net - a.net:+,.0f})"
        )

    print("\n  8d. Leave-one-Game-out on the difference, all 27 Games.\n")
    snaps = win["all"]
    diffs = {
        s.game_id: score_rule([s], PROPOSED).net - score_rule([s], SHIPPED).net for s in snaps
    }
    total = sum(diffs.values())
    jack = sorted((total - d, g) for g, d in diffs.items())
    print(
        f"    total {total:+,.0f}.  Leave-one-out range {jack[0][0]:+,.0f} (drop G{jack[0][1]})"
        f" .. {jack[-1][0]:+,.0f} (drop G{jack[-1][1]})."
        f"  Folds still positive: {sum(1 for v, _ in jack if v > 0)}/{len(jack)}."
    )
    ordered = sorted(diffs.items(), key=lambda kv: kv[1])
    print(
        "    Five worst Games: "
        + ", ".join(f"G{g} {v:+,.0f}" for g, v in ordered[:5])
        + "\n    Five best Games:  "
        + ", ".join(f"G{g} {v:+,.0f}" for g, v in ordered[-5:])
    )


# -------------------------------------------------------- 9. the recommendation, in euros


def show_recommend(win: Mapping[str, Sequence[GameSnapshot]], recent: str) -> None:
    print("\n" + "=" * 118)
    print("9. THE RECOMMENDATION, AND THE GAMES THAT SETTLED AFTER IT WAS CHOSEN")
    print("=" * 118)
    print(
        "\n  The rule was chosen on Games 1-27. Games 28+ settled afterwards and were not\n"
        "  used to choose anything, so they are the only genuinely held-out evidence here.\n"
    )
    rules = (
        SHIPPED,
        CONSERVATIVE,
        Rule("0.70 + cap 12x59", ceiling=0.70, cap_multiple=12.0),
        PROPOSED,
    )
    fresh = [s for s in win["all28"] if s.game_id >= 28]
    names = ["1-20", recent, "all"] + ([f"fresh {fresh[0].game_id}+"] if fresh else [])
    samples = [win["1-20"], win[recent], win["all"]] + ([fresh] if fresh else [])
    print("  " + f"{'rule':<22}" + "".join(f"{n + f' ({len(s)}G)':>18}" for n, s in zip(names, samples)))
    base = [score_rule(s, SHIPPED).net for s in samples]
    for rule in rules:
        cells = []
        for sample, ref in zip(samples, base):
            net = score_rule(sample, rule).net
            cells.append(f"{net:>11,.0f}{net - ref:>+7,.0f}" if rule is not SHIPPED else f"{net:>18,.0f}")
        print(f"  {rule.name:<22}" + "".join(cells))
    for snap in fresh:
        a = score_rule([snap], SHIPPED)
        b = score_rule([snap], PROPOSED)
        print(
            f"\n    G{snap.game_id}: shipped {a.net:+,.0f} (pay_over {a.accept_over:,.0f},"
            f" penalty {a.penalty:,.0f})  ->  proposed {b.net:+,.0f}"
            f" (pay_over {b.accept_over:,.0f}, penalty {b.penalty:,.0f})"
            f"  = {b.net - a.net:+,.0f}"
        )
    print(
        "\n  What would falsify this, in the order it would show up:\n"
        "    1. `pay_over` under the proposed rule rising while `penalty` does not fall --\n"
        "       i.e. the Field starts Charging just under the cap. Watch section 5's two\n"
        "       columns each Game.\n"
        "    2. The 2,000.00 cluster disappearing. It is the mechanism; without it the cap\n"
        "       is worth much less and the plateau in section 7 should visibly narrow.\n"
        "    3. The estimator's upward tail being fixed. If `implied_sigma` ever becomes\n"
        "       calibrated (RMSLE 0.80 -> ~0.40) the cap stops being needed and section 4's\n"
        "       `lam` rows say the ceiling alone becomes worth six figures. Re-run then.\n"
        "    4. A Cap `c` that finally binds, which would make an accepted Overcharge\n"
        "       cheaper than `a` and shift every number here toward generosity."
    )


def check_identities(snaps: Sequence[GameSnapshot]) -> None:
    """Two self-checks, both of which must hold or nothing below means anything.

    1. `per_item` sums to `decompose`. Section 1's claim is "one Line Item carries the
       cliff", which is only a claim if item contributions add to the total.
    2. Every decision-log band reprices to the `(charge, limit)` the pipeline actually
       submitted, to the cent. That is what licenses scoring Games 27+ at all: the band in
       the log is not a reconstruction of the input to `price_item`, it *is* the input.
    """
    for snap in snaps:
        book = book_for(snap, Params())
        whole = decompose(snap, book)
        parts = Decomposition()
        for d in per_item(snap, book).values():
            parts = parts + d
        for field in ("income", "accept_fair", "accept_over", "penalty"):
            a, b = getattr(whole, field), getattr(parts, field)
            assert abs(a - b) < 0.01, f"G{snap.game_id} {field}: {a} != {b}"
    print(check_decision_logs())


def check_decision_logs() -> str:
    """Reprice every logged band and compare against the number that was submitted."""
    checked = failed = 0
    games = []
    for path in sorted(DECISIONS.glob("game_*.json")):
        raw = json.loads(path.read_text())
        game_id = int(raw["game_id"])
        book = _decision_log(game_id)
        if book is None:
            continue
        ok = True
        for item in raw.get("items", []):
            index = int(item["index"])
            if index not in book:
                continue
            charge, limit = price(book[index].evidence, Params())
            checked += 1
            if abs(charge - float(item["charge"])) > 0.005 or abs(limit - float(item["limit"])) > 0.005:
                failed += 1
                ok = False
        games.append(f"G{game_id}{'' if ok else ' MISMATCH'}")
    assert failed == 0, f"{failed} of {checked} logged Line Items do not reprice"
    return (
        f"Decision-log self-check: {checked} logged Line Items across {len(games)} Games"
        f" ({', '.join(games)}) all reprice to the submitted (charge, limit) to the cent."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("section", nargs="?", default="all")
    parser.add_argument("--evidence", default="log", choices=("model", "log"))
    parser.add_argument("--recent", default="21-27")
    parser.add_argument("--through", type=int, default=27)
    args = parser.parse_args()
    games = usable_games()
    load_facts(games, args.evidence)
    everything = scoreable(games)
    # `--through` pins the headline window. Games settle every 12.6 minutes, so without it
    # the "all Games" total silently changes between two runs of this script and no number
    # in the write-up can be reproduced. Games past it are still loaded and are reported in
    # section 9 as held-out, which is the only honest thing to do with a Game that arrived
    # after the rule was chosen.
    inside = tuple(g for g in everything if g <= args.through)
    win = {
        "1-20": snapshots(g for g in inside if g <= 20),
        "21-27": snapshots(g for g in inside if 21 <= g <= 27),
        "21-26": snapshots(g for g in inside if 21 <= g <= 26),
        "all": snapshots(inside),
        "all28": snapshots(everything),
    }
    print(
        f"Games scored: {inside} (evidence source preference: {args.evidence})\n"
        f"Settled since, held out of every total but section 9: "
        f"{tuple(g for g in everything if g > args.through) or 'none'}\n"
        f"Noise floor: {noise_floor(len(win['all'])):,.0f} over {len(win['all'])} Games, "
        f"{noise_floor(len(win[args.recent])):,.0f} over the recent {len(win[args.recent])}."
    )
    check_identities(win["all"])
    if args.section in ("all", "cliff"):
        show_cliff(win, args.recent)
    if args.section in ("all", "reject"):
        show_reject(win, args.recent)
    if args.section in ("all", "binding"):
        show_binding(win, args.recent)
    if args.section in ("all", "split"):
        show_split(win, args.recent)
    if args.section in ("all", "rules"):
        show_rules(win, args.recent)
    if args.section in ("all", "robust"):
        show_robust(win, args.recent)
    if args.section in ("all", "surface"):
        show_surface(win, args.recent)
    if args.section in ("all", "survive"):
        show_survive(win, args.recent)
    if args.section in ("all", "recommend"):
        show_recommend(win, args.recent)


if __name__ == "__main__":
    main()
