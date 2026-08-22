"""Is our over-charging *conditional* on something we can see when we decide?

The finding this answers
-----------------------
19 of 46 Charges in the Strategy 2 era (Games 21-27) sat above the Fair Value, so not one
of sixteen reviewers could owe us anything on them. Median `a/t` is 0.99 where the leader
runs 0.68. A **global** Charge multiplier is already ruled out: the replay surface over our
own multiplier is non-monotone (0.55 -> +39,893, 0.65 -> +69,756, 0.75 -> +45,097,
0.85 -> +55,676, 1.00 -> +38,997, 1.15 -> +10,041 over Games 21-27) because the Field's
Limits are clustered, so any peak on it is a fact about sixteen opponents rather than about
pricing (see the note on `CHARGE_INTERCEPT`).

So the remaining question is whether the unrecoverable Charges *concentrate*. If they do, a
conditional rule exists that no multiplier can imitate. If they are scattered uniformly,
that is a negative result and the problem belongs to the evidence layer.

    PYTHONPATH=. python scripts/charge_buckets.py buckets
    PYTHONPATH=. python scripts/charge_buckets.py rules
    PYTHONPATH=. python scripts/charge_buckets.py holdout

What the sample is
------------------
One row per (Game, Line Item) for Games 1-27, each carrying the evidence that was available
*at decision time* and the Fair Value bracket recovered afterwards from the settled
Transactions (`invert_fair_values.brackets`, via `replay_payoffs.snapshot`).

* Games 26-27 are **logged**: `var/decisions/game_0NN.json`, schema 2, exactly what
  Strategy 2 decided.
* Games 1-25 are **reconstructed**: cached model evidence (`scripts/dump_evidence.load`)
  plus the cached Price Memory channel, merged by `blend.combine` and priced by
  `price_item`, i.e. `build_proposal` re-run offline. Two differences from the live path are
  worth stating: the cache holds a single model draw where the live path blends an ensemble
  of two prompts (so the reconstructed `sigma` is the single draw's, slightly narrower), and
  Games 21-24 actually *submitted* `STANDARD_LIMIT = 35` because Strategy 2 did not land.
  Reconstructed rows are therefore "what today's pricing would have done", which is the
  right counterfactual for tuning it, and they are labelled `recon` everywhere below.

Every euro number comes from `replay_payoffs.replay` against the real Field.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import math
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.case_loader import read_case  # noqa: E402
from src.pricing import (  # noqa: E402
    CHARGE_BOUNDS,
    CHARGE_INTERCEPT,
    CHARGE_SLOPE,
    COVERAGE_FLOOR,
    LIMIT_CEILING,
    LIMIT_QUANTILE,
    Evidence,
    _lognormal_quantile,
    implied_sigma,
)
from src.services.strategies.strategy2.blend import combine  # noqa: E402
from scripts.dump_evidence import load as load_evidence  # noqa: E402
from scripts.replay_payoffs import usable_games  # noqa: E402
from scripts.replay_payoffs import replay
from scripts.replay_payoffs import snapshot as _snapshot  # noqa: E402

snapshot = functools.lru_cache(maxsize=None)(_snapshot)

DECISIONS = Path("var/decisions")
CASES = Path("[PUBLIC] EHL Cases/cases")
def _all_games() -> tuple[int, ...]:
    """Every settled Game that reconstructs, discovered rather than hard-coded.

    This was `range(1, 28)` and stayed there while Games 28-32 settled, so every sweep run
    through this module was silently scoring five Games short — including the ones that
    matter most, because a Field measurement does not survive a phase boundary (README R9).
    A literal range is also fragile the other way: widening it past the last settled Game
    raises `KeyError: 'items'` on the unsettled Game's cached payload. Ask the reconstructor.
    """
    return tuple(usable_games(range(1, 101)))


ALL_GAMES = _all_games()
RECENT = tuple(range(21, 28))
INF = float("inf")

#: Which point of the Fair Value bracket the oracle Charge stands on: "lo" is the proven
#: floor (conservative -- it credits an Overcharge on a `t_lo = 0` item with no loss at all),
#: "mid" is the midpoint used everywhere else in the replay harness.
ORACLE = "lo"

_UNIT = re.compile(r"\(([\d.,]+)\s*(pcs|hrs?|m2|m²|m|kg|days?|units?|flat rate)\)", re.I)


# --------------------------------------------------------------------------- the sample


@dataclass(frozen=True)
class Row:
    game: int
    index: int
    origin: str  #: "logged" | "recon"
    evidence: Evidence
    uncovered: bool  #: channel A -- the invoice printed a dash
    channels: tuple[str, ...]
    name: str
    quantity: float
    t_lo: float
    t_hi: float

    @property
    def t(self) -> float:
        return self.t_lo if self.t_hi == INF else (self.t_lo + self.t_hi) / 2.0

    @property
    def median(self) -> float:
        return self.evidence.with_defaults().price_median

    @property
    def sigma(self) -> float:
        filled = self.evidence.with_defaults()
        return implied_sigma(filled.price_low, filled.price_median, filled.price_high)

    @property
    def coverage(self) -> float:
        return self.evidence.coverage_probability

    @property
    def has_memory(self) -> bool:
        return "B:memory" in self.channels

    @property
    def unit(self) -> str:
        found = _UNIT.search(self.name or "")
        if not found:
            return "unknown"
        unit = found.group(2).lower().rstrip("s")
        return {"m2": "m²", "hr": "hr", "unit": "pcs"}.get(unit, unit)

    @property
    def metered(self) -> bool:
        """Hours and areas -- a rate times a quantity -- against pieces and flat rates."""
        return self.unit in {"hr", "m²", "m", "kg", "day"}


def _line_items(game_id: int) -> dict[int, tuple[str, float, bool]]:
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return {}
    case = asyncio.run(read_case(game_id, case_dir))
    return {
        item.index: (item.name, item.quantity, bool(item.quantity_missing))
        for item in case.line_items
    }


def _logged_rows(game_id: int, brackets: dict[int, tuple[float, float]]) -> list[Row]:
    path = DECISIONS / f"game_{game_id:03d}.json"
    if not path.exists():
        return []
    blob = json.loads(path.read_text())
    rows = []
    for item in blob["items"]:
        index = item["index"]
        if index not in brackets:
            continue
        evidence = Evidence(
            index=index,
            coverage_probability=item.get("coverage_probability") or 0.0,
            price_low=item.get("price_low") or 0.0,
            price_median=item.get("price_median") or 0.0,
            price_high=item.get("price_high") or 0.0,
        )
        rows.append(
            Row(
                game=game_id,
                index=index,
                origin="logged",
                evidence=evidence,
                uncovered=bool(item.get("quantity_missing")),
                channels=tuple(item.get("channels") or ()),
                name=item.get("name") or "",
                quantity=float(item.get("quantity") or 1.0),
                t_lo=brackets[index][0],
                t_hi=brackets[index][1],
            )
        )
    return rows


def _recon_rows(game_id: int, brackets: dict[int, tuple[float, float]]) -> list[Row]:
    model = load_evidence(game_id, "model")
    memory = load_evidence(game_id, "memory") or {}
    if model is None:
        return []
    items = _line_items(game_id)
    rows = []
    for index, bracket in brackets.items():
        name, quantity, uncovered = items.get(index, ("", 1.0, False))
        from_model, from_memory = model.get(index), memory.get(index)
        merged = combine(from_model, from_memory)
        if merged is None:
            continue  # uninformed constants: not priced by this module
        channels = []
        if uncovered:
            channels.append("A:no-quantity")
        if from_memory is not None and not uncovered:
            channels.append("B:memory")
        if from_model is not None:
            channels.append("C:model")
        rows.append(
            Row(
                game=game_id,
                index=index,
                origin="recon",
                evidence=merged,
                uncovered=uncovered,
                channels=tuple(channels),
                name=name,
                quantity=quantity,
                t_lo=bracket[0],
                t_hi=bracket[1],
            )
        )
    return rows


def dataset(games=ALL_GAMES) -> list[Row]:
    """Prefer the decision log; fall back to reconstruction from the evidence cache."""
    rows: list[Row] = []
    for game_id in games:
        brackets = snapshot(game_id).fair_brackets
        got = _logged_rows(game_id, brackets) or _recon_rows(game_id, brackets)
        rows.extend(got)
    return rows


# ------------------------------------------------------------------------- the pricing


@dataclass(frozen=True)
class Rule:
    """The shipped pricing, plus one optional conditional multiplier on the Charge."""

    name: str = "shipped"
    #: which one-parameter family this rule belongs to, for the held-out fits
    family: str = "shipped"
    #: multiplies `charge_factor(sigma)`; receives the Row, returns a factor
    scale: object = None
    slope: float = CHARGE_SLOPE
    intercept: float = CHARGE_INTERCEPT

    def price(self, row: Row) -> tuple[float, float]:
        filled = row.evidence.with_defaults()
        sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
        covered = 0.0 if row.uncovered else filled.coverage_probability
        low, high = CHARGE_BOUNDS
        factor = min(max(self.intercept - self.slope * sigma, low), high)
        if self.scale is not None:
            factor *= self.scale(row)
        charge = max(factor, 0.0) * filled.price_median
        if covered <= COVERAGE_FLOOR:
            limit = 0.0
        else:
            conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
            limit = min(
                _lognormal_quantile(filled.price_median, sigma, conditional),
                LIMIT_CEILING * filled.price_median,
            )
        limit = min(limit, charge)
        return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)


def euros(rows: list[Row], rule: Rule, games) -> dict[int, float]:
    """Net per Game from replaying `rule`'s submission against the real Field."""
    by_game: dict[int, list[Row]] = {}
    for row in rows:
        by_game.setdefault(row.game, []).append(row)
    out = {}
    for game_id in games:
        snap = snapshot(game_id)
        submission = {row.index: rule.price(row) for row in by_game.get(game_id, [])}
        # Line Items we have no evidence row for keep their real submitted numbers, so the
        # comparison isolates the rule instead of scoring a partial submission.
        actual = {
            index: (snap.charges[index][snap.us], snap.limit_point(index, snap.us))
            for index in snap.line_items
        }
        actual.update(submission)
        out[game_id] = replay(snap, actual).net
    return out


def total(rows: list[Row], rule: Rule, games) -> float:
    return sum(euros(rows, rule, games).values())


# ------------------------------------------------------------------------ the reporting


def _income(row: Row, charge: float) -> float:
    """What the Field really pays us for this Charge, from the settled Transactions."""
    snap = snapshot(row.game)
    t = snap.fair_point(row.index)
    return sum(
        charge if charge <= max(snap.limit_point(row.index, team), t) else 0.0
        for team in snap.opponents
    )


@dataclass(frozen=True)
class Stats:
    n: int
    over: int
    share: float
    ratio: float
    #: euros the oracle Charge `a = t_lo` would have earned and we did not, split by side
    over_loss: float
    discount: float
    #: `over_loss` as a share of what the oracle Charge would have earned in this bucket.
    #: Without it the euro columns only say "big items carry big euros".
    over_share: float


def _stats(rows: list[Row]) -> Stats:
    """Per bucket: how often the shipped Charge is unrecoverable, and what it costs.

    Two euro columns, because one number hides the entire trade. `income(a = t_lo)` minus
    `income(a)` is the gap to an oracle, and it has two completely different causes:

        over_loss   the gap on rows where `a > t` -- income we forfeited by over-charging
        discount    the gap on rows where `a <= t` -- the deliberate 0.7 x t_hat discount,
                    which is what R5b *buys* the certainty of being paid with

    Counting items instead of euros over-weights the worthless Line Items, where an
    Overcharge is rejected at zero cost and charging is a free option (R6c).
    """
    shipped = Rule()
    over = 0
    ratios: list[float] = []
    over_loss = discount = oracle_income = 0.0
    for row in rows:
        charge, _ = shipped.price(row)
        oracle = row.t if ORACLE == "mid" else row.t_lo
        oracle_income += _income(row, oracle)
        gap = max(_income(row, oracle) - _income(row, charge), 0.0)
        if row.t <= 0 or charge > row.t:
            over += 1
            over_loss += gap
        else:
            discount += gap
        if row.t > 0:
            ratios.append(charge / row.t)
    n = len(rows)
    return Stats(
        n=n,
        over=over,
        share=over / n if n else 0.0,
        ratio=statistics.median(ratios) if ratios else 0.0,
        over_loss=over_loss,
        discount=discount,
        over_share=over_loss / oracle_income if oracle_income else 0.0,
    )


def buckets(rows: list[Row]) -> None:
    def show(title, groups):
        print(f"\n{title}")
        print(
            f"  {'bucket':<24}{'n':>5}{'a>t':>6}{'share':>8}{'med a/t':>10}"
            f"{'over_loss':>12}{'of oracle':>11}{'discount':>12}"
        )
        for label, group in groups:
            s = _stats(group)
            if not s.n:
                continue
            print(
                f"  {label:<24}{s.n:>5}{s.over:>6}{s.share:>8.0%}{s.ratio:>10.2f}"
                f"{s.over_loss:>12,.0f}{s.over_share:>11.0%}{s.discount:>12,.0f}"
            )

    def split(key, labels):
        return [(label, [r for r in rows if key(r) == label]) for label in labels]

    s = _stats(rows)
    print(
        f"all rows: n={s.n} unrecoverable={s.over} ({s.share:.0%}) "
        f"median a/t={s.ratio:.2f} over_loss={s.over_loss:,.0f} discount={s.discount:,.0f}"
    )
    show(
        "is the Line Item worth anything? (t_lo > 0 means somebody was owed on it)",
        [
            ("t_lo = 0 (free option)", [r for r in rows if r.t_lo <= 0]),
            ("t_lo > 0 (real money)", [r for r in rows if r.t_lo > 0]),
        ],
    )
    rows = [r for r in rows if r.t_lo > 0]
    print(f"\n=== everything below is the {len(rows)} rows with t_lo > 0 ===")

    sigmas = sorted(r.sigma for r in rows)
    q1, q2 = sigmas[len(sigmas) // 3], sigmas[2 * len(sigmas) // 3]
    show(
        "sigma (implied band width) -- terciles",
        [
            (f"narrow <{q1:.2f}", [r for r in rows if r.sigma < q1]),
            (f"mid {q1:.2f}-{q2:.2f}", [r for r in rows if q1 <= r.sigma < q2]),
            (f"wide >={q2:.2f}", [r for r in rows if r.sigma >= q2]),
        ],
    )
    show(
        "which channel spoke",
        [
            ("A:no-quantity", [r for r in rows if r.uncovered]),
            ("model only", [r for r in rows if not r.uncovered and not r.has_memory]),
            ("model + memory", [r for r in rows if not r.uncovered and r.has_memory]),
        ],
    )
    show(
        "coverage probability",
        [
            ("<= 2/3 (collapsed)", [r for r in rows if r.coverage <= COVERAGE_FLOOR]),
            ("2/3 - 0.9", [r for r in rows if COVERAGE_FLOOR < r.coverage < 0.9]),
            (">= 0.9", [r for r in rows if r.coverage >= 0.9]),
        ],
    )
    show(
        "magnitude of the estimate (t_hat = median)",
        [
            ("< 50", [r for r in rows if r.median < 50]),
            ("50 - 500", [r for r in rows if 50 <= r.median < 500]),
            (">= 500", [r for r in rows if r.median >= 500]),
        ],
    )
    show(
        "invoice unit",
        [
            ("metered (hr/m²/day/kg)", [r for r in rows if r.metered]),
            ("pcs / flat rate", [r for r in rows if not r.metered and r.unit != "unknown"]),
            ("unit not parsed", [r for r in rows if r.unit == "unknown"]),
        ],
    )
    show(
        "quantity",
        [
            ("qty <= 1", [r for r in rows if r.quantity <= 1]),
            ("qty > 1", [r for r in rows if r.quantity > 1]),
        ],
    )
    show("origin of the row", split(lambda r: r.origin, ["logged", "recon"]))
    show(
        "era",
        [
            ("Games 1-20", [r for r in rows if r.game <= 20]),
            ("Games 21-27", [r for r in rows if r.game >= 21]),
        ],
    )


def _candidates() -> list[Rule]:
    rules = [Rule()]
    for slope in (-0.45, -0.225, 0.0, 0.225, 0.45, 0.675, 0.9):
        rules.append(Rule(name=f"slope={slope}", family="sigma slope", slope=slope))
    # Does sigma carry the sign `CHARGE_SLOPE` assumes? These three hold the *mean* factor
    # at the shipped line's value on the observed sigmas (~0.69) and only reorder the items:
    # flat ignores sigma, inverted discounts the *narrow* bands, which is the direction the
    # bucket table points. A plain negative slope cannot be read, because `CHARGE_BOUNDS`
    # clamps it at 0.80 and every negative value collapses onto `slope = 0`.
    # And the level sweep for both, matched pair by pair, so "flat beats the line" can be
    # told apart from "this level beats that level" -- the surface the multiplier already
    # failed on.
    for level in (0.60, 0.64, 0.66, 0.69, 0.72, 0.75, 0.80):
        rules.append(
            Rule(name=f"flat {level}", family="flat level", intercept=level, slope=0.0)
        )
        rules.append(
            Rule(
                name=f"line {level + 0.17:.2f}-0.45s",
                family="line level",
                intercept=level + 0.17,
                slope=0.45,
            )
        )
    rules.append(
        Rule(name="inverted 0.55+0.45s", family="inverted", intercept=0.55, slope=-0.45)
    )
    rules.append(
        Rule(name="inverted 0.62+0.22s", family="inverted", intercept=0.62, slope=-0.225)
    )
    for m in (0.7, 0.85, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.4):
        rules.append(
            Rule(
                name=f"memory x{m}",
                family="memory up/down",
                scale=lambda r, m=m: m if r.has_memory else 1.0,
            )
        )
    for m in (0.6, 0.7, 0.8, 0.9, 1.0):
        rules.append(
            Rule(
                name=f"model-only x{m}",
                family="model-only",
                scale=lambda r, m=m: 1.0 if r.has_memory else m,
            )
        )
    for m in (0.6, 0.7, 0.8, 0.9, 1.0):
        rules.append(
            Rule(
                name=f"big (>=500) x{m}",
                family="big t_hat",
                scale=lambda r, m=m: m if r.median >= 500 else 1.0,
            )
        )
    for m in (0.6, 0.7, 0.8, 0.9, 1.0):
        rules.append(
            Rule(
                name=f"small (<50) x{m}",
                family="small t_hat",
                scale=lambda r, m=m: m if r.median < 50 else 1.0,
            )
        )
    for m in (0.6, 0.7, 0.8, 0.9, 1.0):
        rules.append(
            Rule(
                name=f"doubtful coverage x{m}",
                family="coverage",
                scale=lambda r, m=m: m if r.coverage < 0.9 else 1.0,
            )
        )
    for m in (0.6, 0.7, 0.8, 0.9, 1.0):
        rules.append(
            Rule(
                name=f"metered x{m}",
                family="metered unit",
                scale=lambda r, m=m: m if r.metered else 1.0,
            )
        )
    for m in (0.6, 0.7, 0.8, 0.9, 1.0):
        rules.append(
            Rule(
                name=f"qty>1 x{m}",
                family="quantity",
                scale=lambda r, m=m: m if r.quantity > 1 else 1.0,
            )
        )
    # The intersection the bucket table points at: 57,955 of the 76,642 euros of forgone
    # income sits on `median >= 500`, and 53,768 of it on model-only items.
    for m in (0.7, 0.8, 0.9):
        rules.append(
            Rule(
                name=f"model-only & big x{m}",
                family="model-only & big",
                scale=lambda r, m=m: m if (r.median >= 500 and not r.has_memory) else 1.0,
            )
        )
    # The one direction the measurement actually argues for: Price Memory has a 0.43 log
    # error against the model's 0.80, so a memory-backed item deserves a *higher* multiplier
    # and a model-only item a lower one. Swept in both coordinates, because bar 2 asks
    # whether the rule is monotone in its own parameter.
    for up in (1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35):
        rules.append(
            Rule(
                name=f"memory x{up}, model x0.9",
                family="memory up (model x0.9)",
                scale=lambda r, up=up: up if r.has_memory else 0.9,
            )
        )
    for down in (0.75, 0.8, 0.85, 0.9, 0.95, 1.0):
        rules.append(
            Rule(
                name=f"memory x1.15, model x{down}",
                family="model down (memory x1.15)",
                scale=lambda r, down=down: 1.15 if r.has_memory else down,
            )
        )
    # Both one-dimensional sweeps above hold the *other* coordinate at a value fitted on the
    # whole record, which leaks the in-sample argmax into every held-out fold. This family
    # fits the pair jointly, and it is the only honest version of the test.
    for up in (1.0, 1.1, 1.15, 1.2, 1.3):
        for down in (0.8, 0.9, 1.0):
            rules.append(
                Rule(
                    name=f"joint memory x{up} model x{down}",
                    family="memory/model, fitted jointly",
                    scale=lambda r, up=up, down=down: up if r.has_memory else down,
                )
            )
    return rules


def rules(rows: list[Row]) -> None:
    base_all = total(rows, Rule(), ALL_GAMES)
    base_recent = total(rows, Rule(), RECENT)
    print(f"{'rule':<24}{'all 27':>12}{'d':>10}{'G21-27':>12}{'d':>10}")
    for rule in _candidates():
        a = total(rows, rule, ALL_GAMES)
        r = total(rows, rule, RECENT)
        print(
            f"{rule.name:<24}{a:>12,.0f}{a - base_all:>10,.0f}"
            f"{r:>12,.0f}{r - base_recent:>10,.0f}"
        )
    floor_all = 26_622 * math.sqrt(len(ALL_GAMES) / 18)
    floor_recent = 26_622 * math.sqrt(len(RECENT) / 18)
    print(f"\nnoise floor: all 27 +/-{floor_all:,.0f}   G21-27 +/-{floor_recent:,.0f}")


def _families() -> dict[str, list[Rule]]:
    families: dict[str, list[Rule]] = {}
    for rule in _candidates()[1:]:
        families.setdefault(rule.family, []).append(rule)
    return {name: group for name, group in families.items() if len(group) > 1}


def holdout(rows: list[Row]) -> None:
    """Fit each family's parameter on one half of the Games, score it on the other.

    Two splits. Odd/even interleaves the two regimes so both halves see the same Field;
    1-20 against 21-27 is the disjoint regime split, which is the harder test and the one
    that matters, because we are paid on the Games that come next.
    """
    odd = tuple(g for g in ALL_GAMES if g % 2)
    even = tuple(g for g in ALL_GAMES if not g % 2)
    early, late = tuple(range(1, 21)), RECENT
    splits = (
        (odd, even, "odd->even"),
        (even, odd, "even->odd"),
        (early, late, "1-20->21-27"),
        (late, early, "21-27->1-20"),
    )
    families = _families()
    print(f"{'family':<32}" + "".join(f"{label:>16}" for _, _, label in splits))
    totals = {label: 0.0 for _, _, label in splits}
    for name, group in families.items():
        cells = []
        for train, test, label in splits:
            best = max(group, key=lambda rule: total(rows, rule, train))
            delta = total(rows, best, test) - total(rows, Rule(), test)
            totals[label] += delta
            cells.append(f"{delta:>+16,.0f}")
        print(f"{name:<32}" + "".join(cells))
    print("\nheld-out net against the shipped constants, by split:")
    for _, _, label in splits:
        print(f"  {label:<16}{totals[label]:>+12,.0f} summed over every family above")
    print(
        "\nA family that were a real conditional rule would be positive in all four "
        "columns. Compare each cell against the noise floor: "
        f"+/-{26_622 * math.sqrt(len(even) / 18):,.0f} on a half of the record, "
        f"+/-{26_622 * math.sqrt(len(RECENT) / 18):,.0f} on Games 21-27."
    )


def field(games=ALL_GAMES) -> None:
    """The same split for every team, because the headline comparison depends on it.

    "Median `a/t` 0.99 against eyay's 0.68, 19 of 46 unrecoverable against their 7 of 316"
    pools two populations. A Charge on a Line Item nobody was ever owed money for (`t_lo = 0`)
    is above `t` by construction and costs nothing when rejected (R6c) -- it is a free option
    we take deliberately. A team that declines to Charge on those items scores a beautiful
    `a/t` and forfeits the option. So the ratio has to be read on `t_lo > 0` items alone.
    """
    print(
        f"{'team':<18}{'items':>7}{'charged':>9}"
        f"{'  |  t_lo = 0: charged  a>t':<30}"
        f"{'  |  t_lo > 0: n  a>t  share  med a/t':<40}"
    )
    tally: dict[str, list[float]] = {}
    for game_id in games:
        snap = snapshot(game_id)
        for index in snap.line_items:
            worthless = snap.fair_brackets[index][0] <= 0.0
            t = snap.fair_point(index)
            for team, charge in snap.charges[index].items():
                row = tally.setdefault(team, [0, 0, 0, 0, 0, 0])
                row[0] += 1
                if charge > 0:
                    row[1] += 1
                if worthless:
                    row[2] += 1 if charge > 0 else 0
                    row[3] += 1 if charge > t else 0
                else:
                    row[4] += 1
                    row[5] += 1 if charge > t else 0
    ratios: dict[str, list[float]] = {}
    for game_id in games:
        snap = snapshot(game_id)
        for index in snap.line_items:
            if snap.fair_brackets[index][0] <= 0.0:
                continue
            t = snap.fair_point(index)
            for team, charge in snap.charges[index].items():
                if charge != INF and t > 0:
                    ratios.setdefault(team, []).append(charge / t)
    for team, row in sorted(tally.items(), key=lambda pair: -pair[1][4]):
        real = row[4]
        median = statistics.median(ratios.get(team, [0.0]))
        print(
            f"{team:<18}{row[0]:>7}{row[1]:>9}"
            f"{row[2]:>14}{row[3]:>10}"
            f"{real:>16}{row[5]:>5}{row[5] / real if real else 0:>8.0%}{median:>9.2f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["buckets", "rules", "holdout", "field", "all"])
    parser.add_argument(
        "--oracle",
        choices=["lo", "mid"],
        default="lo",
        help="which point of the Fair Value bracket the oracle Charge stands on",
    )
    args = parser.parse_args()
    global ORACLE
    ORACLE = args.oracle
    rows = dataset()
    if args.command in ("field", "all"):
        field()
    if args.command in ("buckets", "all"):
        buckets(rows)
    if args.command in ("rules", "all"):
        print()
        rules(rows)
    if args.command in ("holdout", "all"):
        print()
        holdout(rows)


if __name__ == "__main__":
    main()
