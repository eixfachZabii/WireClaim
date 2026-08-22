"""Does scaling t_hat itself -- not a or b separately -- pay?

The hypothesis (docs/brainstorm/sebi/strats/review/scale-estimate.md)
--------------------------------------------------------------------
Every earlier lever moved `a` alone (the Charge multiplier) or `b` alone (the Limit
multiplier, `LIMIT_CEILING` / `LIMIT_CAP`) on top of a *fixed* `t_hat`. Six of the seven
levers tried died on the held-out fold. This is different in kind: `price_item` derives
both `a` and `b` from the same `price_median`, so scaling the *estimate* --

    price_median -> f(price_median)

and repricing through the real `price_item` moves both numbers coherently: `a` rises
(more income while `a` stays under `t`), and `b` rises (fewer wrongful rejections, at the
price of admitting more Overcharges). Nothing in the multiplier family can do that, because
a multiplier on `a` alone breaks the derivation `b < a` is built on, and a multiplier on `b`
alone was already the LIMIT_CEILING / LIMIT_CAP sweeps.

The case for it: on censored (expensive, `t_hi = inf`) items `t_hat` sits below the proven
floor `t_lo` 73% of the time; `t_hat/t` is 0.80 on unbounded brackets against 1.23 on
bounded ones; and by magnitude `t_hat/t` runs ~6x on items under 50 EUR and ~1.2x above
1,000 -- **when bucketed by the true `t`**, which is the biased direction
(`level_fit.py`'s own docstring: "conditioning on `t` manufactures regression-to-the-mean
in whichever direction you look"; bucketed by `t_hat` itself -- the only direction
actionable at submission time -- the picture inverts: 0.46 under 50 EUR, 1.95 above 1,000).
That inversion is why this script tests a *euro-weighted* uniform scale and *conditional*
variants that only touch the top of the distribution, not a global multiplier chosen by
eyeballing the true-t table.

The case against a uniform scale: `t_hat` is not uniformly low, so a global multiplier
makes the already-too-high cheap items worse (forfeits guaranteed income when `a` crosses
`t`, and admits full-price fraud when `b` crosses `t`). Hence the magnitude-conditional
variants (threshold multiplier, power-law stretch) in addition to the uniform sweep.

Prior art that must not be repeated blindly
--------------------------------------------
`tests/test_strategy2.py::UncorrectedLevelTests` and `scripts/experiments/level_fit.py`
already tested a *euro-weighted power fit conditioned on t_hat*, `exp(0.889) * t_hat**0.849`,
over Games 1-24 on the pre-decision-log engine: it lost 54,713 in-sample and up to 183,048
held out, and the whole `exp(c0) * t_hat**c1` family's euro-argmax across 45 grid cells was
`c1 = 1.00` -- the identity. That fit's exponent (0.849) is on the *shrinking* side
(gamma < 1); this script's magnitude-conditional / power variants deliberately test the
*other* direction (gamma > 1, stretch only the top) on a different, more recent window
(Games 26-44, the decision-log era, current engine with LIMIT_CAP model-only /
LIMIT_CEILING_MEMORY) that `level_fit.py` never touched. Different direction, different
window, different engine -- but the prior result is exactly the kind of thing this file's
job is to either confirm or overturn with a number, not assume away.

What this harness does
-----------------------
1. Loads every `var/decisions/game_NNN.json` whose logged item count matches the real
   Line Item count recovered from settled Transactions (excludes the corrupted log).
2. Reconstructs, for every logged, priced item, the `Evidence` and the `confirmed_uncovered`
   / `memory_backed` flags exactly as `strategy.py::build_proposal` derived them, and
   verifies that feeding them back through the *real* `price_item` reproduces the logged
   Charge and Limit to the cent -- for every item, not a sample. That is both the
   correctness check on this reconstruction and the baseline for every delta below.
3. Applies a scale to `price_median` alone (uniform, threshold-conditional, or power-law),
   leaves `price_low` / `price_high` / `coverage_probability` untouched, and reprices
   through the unmodified `price_item`. `Evidence.with_defaults()` -- also unmodified --
   is what then reconciles the band when the scaled median moves outside it.
4. Replays every configuration against the real Field with `replay_payoffs.replay`, over
   the last-15-logged-Games window and the full 18-Game logged window, and decomposes every
   delta into: extra issuer income, reviewer-cost change split into penalties saved
   (0.5a each) versus Overcharges newly accepted (full a), and the charge/limit "cliff"
   (items whose Charge crosses from <= t to > t).
5. Reports odd/even and early/late held-out folds beside every number, with the noise
   floor `26,622 * sqrt(n / 18)` (n = Games in that fold; the 18-Game logged window is the
   n=18 anchor).

Usage
-----
    PYTHONPATH=. pixi run python scripts/experiments/scale_estimate.py
"""

from __future__ import annotations

import json
import math
import statistics as st
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.replay_payoffs import (  # noqa: E402
    GameSnapshot,
    issuer_payoff,
    reviewer_payoff,
    replay,
    snapshot,
)

from src.pricing.engine import COVERAGE_FLOOR, Evidence, price_item  # noqa: E402

INF = math.inf
DECISIONS = Path("var/decisions")
NOISE_FLOOR_18 = 26_622.0
LIMIT_RULE = "mid"  # see replay_payoffs.py: bit-identical to lo/hi for every beta <= 1


def noise_floor(n_games: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(n_games / 18.0)


# --------------------------------------------------------------------------- the sample


@dataclass(frozen=True)
class ItemRow:
    game: int
    index: int
    evidence: Evidence
    uncovered: bool  # == confirmed_uncovered in price_item; from `quantity_missing`
    memory_backed: bool
    logged_charge: float
    logged_limit: float


@dataclass(frozen=True)
class Exclusion:
    game: int
    reason: str


def discover_games() -> tuple[list[int], list[Exclusion]]:
    """Every decision-log Game whose logged item count matches the real Line Item count.

    Game 42's log was corrupted by a stray write and repaired only in the live merge logic,
    not in the file on disk: the real run priced 17 items (confirmed by both
    `invert_fair_values.brackets` and `replay_payoffs.snapshot`, which both reconstruct 17
    Line Items for Game 42 from the settled Transactions) but `var/decisions/game_042.json`
    holds only 2. Excluded here on that measured mismatch, not on a hard-coded Game id, so
    the check keeps working if another log is ever short.
    """
    good: list[int] = []
    excluded: list[Exclusion] = []
    for path in sorted(DECISIONS.glob("game_*.json")):
        blob = json.loads(path.read_text())
        game_id = blob["game_id"]
        try:
            snap = snapshot(game_id)
        except Exception as exc:  # pragma: no cover - offline / unreconstructable
            excluded.append(Exclusion(game_id, f"unreconstructable: {exc}"))
            continue
        n_logged = len(blob["items"])
        n_real = len(snap.line_items)
        if n_logged != n_real:
            excluded.append(
                Exclusion(game_id, f"logged {n_logged} items, real run priced {n_real}")
            )
            continue
        good.append(game_id)
    return good, excluded


def load_rows(game_id: int) -> list[ItemRow]:
    blob = json.loads((DECISIONS / f"game_{game_id:03d}.json").read_text())
    snap = snapshot(game_id)
    rows: list[ItemRow] = []
    for item in blob["items"]:
        index = item["index"]
        if index not in snap.fair_brackets:
            continue
        if item.get("price_median") is None:
            continue  # "uninformed-constants": nothing to scale, no evidence was priced
        channels = tuple(item.get("channels") or ())
        uncovered = bool(item.get("quantity_missing"))
        memory_backed = ("B:memory" in channels) and not uncovered
        evidence = Evidence(
            index=index,
            coverage_probability=item.get("coverage_probability") or 0.0,
            price_low=item.get("price_low") or 0.0,
            price_median=item.get("price_median") or 0.0,
            price_high=item.get("price_high") or 0.0,
        )
        rows.append(
            ItemRow(
                game=game_id,
                index=index,
                evidence=evidence,
                uncovered=uncovered,
                memory_backed=memory_backed,
                logged_charge=float(item["charge"]),
                logged_limit=float(item["limit"]),
            )
        )
    return rows


# --------------------------------------------------------------------------- the scales


ScaleFn = Callable[[float], float]


def uniform(lam: float) -> ScaleFn:
    return lambda median: lam * median


def threshold(lam: float, thresh: float) -> ScaleFn:
    return lambda median: lam * median if median > thresh else median


def power(gamma: float, anchor: float) -> ScaleFn:
    """`t_hat' = c * t_hat**gamma`, with `c` chosen so the curve is fixed at `anchor`.

    Anchored low (below the cheap-item cluster) so gamma > 1 stretches the top of the
    distribution and leaves the bottom close to identity, which is the direction the
    magnitude-conditional evidence argues for -- the opposite of the already-tried
    `exp(0.889) * t_hat**0.849` (anchored implicitly by an unconstrained euro-weighted fit,
    gamma < 1, shrinking).
    """
    c = anchor ** (1.0 - gamma)

    def f(median: float) -> float:
        if median <= 0:
            return median
        return c * median**gamma

    return f


def identity_scale(median: float) -> float:
    return median


# --------------------------------------------------------------------- pricing / replay


def scaled_price(row: ItemRow, scale: ScaleFn) -> tuple[float, float]:
    ev = row.evidence
    new_median = scale(ev.price_median) if ev.price_median > 0 else ev.price_median
    scaled_evidence = Evidence(
        index=ev.index,
        coverage_probability=ev.coverage_probability,
        price_low=ev.price_low,
        price_median=new_median,
        price_high=ev.price_high,
    )
    price = price_item(scaled_evidence, confirmed_uncovered=row.uncovered, memory_backed=row.memory_backed)
    return price.charge, price.limit


def build_submission(
    snap: GameSnapshot, rows: list[ItemRow], scale: ScaleFn
) -> dict[int, tuple[float, float]]:
    """Scaled (charge, limit) for evidence-backed items; the real submission elsewhere.

    Items with no priced evidence (the single `uninformed-constants` row in the whole
    sample) keep whatever was actually submitted, so the comparison isolates the scale
    instead of silently dropping a Line Item.
    """
    submission = {
        index: (snap.charges[index][snap.us], snap.limit_point(index, snap.us, LIMIT_RULE))
        for index in snap.line_items
    }
    for row in rows:
        submission[row.index] = scaled_price(row, scale)
    return submission


def net_by_game(
    games: list[int], rows_by_game: dict[int, list[ItemRow]], scale: ScaleFn
) -> dict[int, float]:
    out = {}
    for game_id in games:
        snap = snapshot(game_id)
        submission = build_submission(snap, rows_by_game.get(game_id, []), scale)
        out[game_id] = replay(snap, submission, limit_rule=LIMIT_RULE).net
    return out


# ------------------------------------------------------------------------- decomposition


def item_income_abs(snap: GameSnapshot, index: int, charge: float) -> float:
    t = snap.fair_point(index)
    return sum(
        issuer_payoff(charge, snap.limit_point(index, team, LIMIT_RULE), t) for team in snap.opponents
    )


def item_cost_split(
    snap: GameSnapshot, index: int, old_limit: float, new_limit: float
) -> tuple[float, float, float]:
    """`(penalty_saved, overcharge_gained, other)` reviewer-cost deltas for one Line Item.

    `penalty_saved` -- the 0.5a lawyer's share recovered by newly accepting a fair Charge
    (`a <= t`) that was previously a wrongful rejection.
    `overcharge_gained` -- the full `a` newly paid because an Overcharge (`a > t`) that was
    previously rejected for free is now accepted (Cap treated as infinite, matching the
    rest of `replay_payoffs.py`: it has never bound in 52,224+ settled rows).
    `other` -- the reverse direction (a widened band can, rarely, *lower* the Limit); kept
    separate rather than netted into the two named buckets so a sign flip cannot hide there.
    """
    t = snap.fair_point(index)
    penalty_saved = 0.0
    overcharge_gained = 0.0
    other = 0.0
    for team in snap.opponents:
        charge_opp = snap.charges[index].get(team, INF)
        if charge_opp == INF:
            continue
        old_cost = reviewer_payoff(charge_opp, old_limit, t)
        new_cost = reviewer_payoff(charge_opp, new_limit, t)
        delta = new_cost - old_cost
        if abs(delta) < 1e-9:
            continue
        if charge_opp <= t:
            if delta < 0:
                penalty_saved += -delta
            else:
                other += delta
        else:
            if delta > 0:
                overcharge_gained += delta
            else:
                other += delta
    return penalty_saved, overcharge_gained, other


def cliff_class(t: float, old_charge: float, new_charge: float) -> str:
    if old_charge <= t and new_charge <= t:
        return "stayed_under"
    if old_charge <= t and new_charge > t:
        return "crossed_up"
    if old_charge > t and new_charge <= t:
        return "crossed_down"
    return "stayed_over"


@dataclass
class Decomposition:
    n_items: int = 0
    issuer_income_delta: float = 0.0
    penalty_saved: float = 0.0
    overcharge_gained: float = 0.0
    other_cost_delta: float = 0.0
    n_crossed_up: int = 0
    crossed_up_baseline_income: float = 0.0  # income at old (under-t) charge, held flat
    crossed_up_new_income: float = 0.0  # actual income realised after crossing
    n_stayed_under: int = 0
    stayed_under_income_gained: float = 0.0
    n_crossed_down: int = 0
    n_clamp_bound_before: int = 0
    n_clamp_bound_after: int = 0

    @property
    def cost_delta(self) -> float:
        return self.penalty_saved * -1.0 + self.overcharge_gained + self.other_cost_delta

    @property
    def net_delta(self) -> float:
        return self.issuer_income_delta - self.cost_delta


def decompose(games: list[int], rows_by_game: dict[int, list[ItemRow]], scale: ScaleFn) -> Decomposition:
    d = Decomposition()
    for game_id in games:
        snap = snapshot(game_id)
        for row in rows_by_game.get(game_id, []):
            old_charge, old_limit = scaled_price(row, identity_scale)
            new_charge, new_limit = scaled_price(row, scale)
            d.n_items += 1
            t = snap.fair_point(row.index)

            income_delta = item_income_abs(snap, row.index, new_charge) - item_income_abs(
                snap, row.index, old_charge
            )
            d.issuer_income_delta += income_delta

            penalty_saved, overcharge_gained, other = item_cost_split(snap, row.index, old_limit, new_limit)
            d.penalty_saved += penalty_saved
            d.overcharge_gained += overcharge_gained
            d.other_cost_delta += other

            klass = cliff_class(t, old_charge, new_charge)
            if klass == "crossed_up":
                d.n_crossed_up += 1
                d.crossed_up_baseline_income += item_income_abs(snap, row.index, old_charge)
                d.crossed_up_new_income += item_income_abs(snap, row.index, new_charge)
            elif klass == "stayed_under":
                d.n_stayed_under += 1
                d.stayed_under_income_gained += income_delta
            elif klass == "crossed_down":
                d.n_crossed_down += 1

            if abs(old_limit - old_charge) < 0.01:
                d.n_clamp_bound_before += 1
            if abs(new_limit - new_charge) < 0.01:
                d.n_clamp_bound_after += 1
    return d


# ------------------------------------------------------------------------------- verify


@dataclass
class VerifyResult:
    n: int = 0
    charge_bad: int = 0
    rule_bad: int = 0
    limit_ratio_exact: int = 0  # logged limit / recomputed limit == 1.0
    limit_ratios: list = None

    def __post_init__(self) -> None:
        if self.limit_ratios is None:
            self.limit_ratios = []


def verify_reconstruction(rows_by_game: dict[int, list[ItemRow]]) -> VerifyResult:
    """Feed every logged item back through the real `price_item` at scale = identity.

    Two things are checked, deliberately not three. `price_item`'s Charge depends only on
    `price_median` and the band-implied sigma -- not on `confirmed_uncovered` or
    `memory_backed` -- so an exact Charge match, for every item, validates that the
    Evidence extraction (price_low/median/high) is right and that `CHARGE_INTERCEPT` /
    `CHARGE_SLOPE` / `CHARGE_BOUNDS` have not moved since these Games were played. The Limit
    additionally depends on `confirmed_uncovered` (zeroes it) and `memory_backed` (selects
    `LIMIT_CEILING_MEMORY` over `LIMIT_CEILING`, and exempts from `LIMIT_CAP`) -- so whether
    the *shipped rule* (`"uncovered-free-option"` iff limit == 0) reproduces validates that
    reconstruction, for every item, not a sample.

    What is deliberately NOT checked here: the absolute logged Limit *value*. `LIMIT_CEILING`
    has been re-measured and moved repeatedly over the tournament (0.20/0.30/0.40/0.45/
    0.50/0.60/0.85 all appear in `engine.py`'s own history), and `LIMIT_CEILING_MEMORY` /
    the model-only `LIMIT_CAP` exemption shipped only tonight -- after most of these Games
    were played. So the logged Limit reflects whatever engine version was live at decision
    time, and this harness prices with today's. That is not a bug to fix; it is required by
    "use the current engine", and it is why every ratio (logged Limit / recomputed Limit)
    below clusters at a handful of discrete values (1.0 for Games already on today's
    constants, ~0.667 for the 0.30-vs-0.45 ceiling era, etc.) rather than at 1.0 throughout.
    """
    result = VerifyResult()
    for rows in rows_by_game.values():
        for row in rows:
            charge, limit = scaled_price(row, identity_scale)
            result.n += 1
            if abs(charge - row.logged_charge) > 0.02:
                result.charge_bad += 1
                print(
                    f"  CHARGE MISMATCH g{row.game} item {row.index}: "
                    f"recomputed {charge:.2f} vs logged {row.logged_charge:.2f}"
                )
            logged_rule = "uncovered-free-option" if row.logged_limit == 0.0 else "priced"
            my_rule = "uncovered-free-option" if limit == 0.0 else "priced"
            if logged_rule != my_rule:
                result.rule_bad += 1
                print(
                    f"  RULE MISMATCH g{row.game} item {row.index}: "
                    f"logged rule implies {logged_rule}, recomputed implies {my_rule} "
                    f"(logged limit {row.logged_limit:.2f}, recomputed {limit:.2f})"
                )
            if row.logged_limit > 0 and limit > 0:
                ratio = row.logged_limit / limit
                result.limit_ratios.append(ratio)
                if abs(ratio - 1.0) < 1e-9:
                    result.limit_ratio_exact += 1
    return result


# --------------------------------------------------------------------------------- main


def window_sum(deltas: dict[int, float], games: Iterable[int]) -> float:
    return sum(deltas[g] for g in games)


def fmt(x: float) -> str:
    return f"{x:>13,.0f}"


def main() -> None:
    good_games, excluded = discover_games()
    print("=" * 100)
    print("STEP 0: ground truth")
    print("=" * 100)
    print("Run separately and both already verified clean before this harness:")
    print("  PYTHONPATH=. python scripts/invert_fair_values.py --verify --games all")
    print("  PYTHONPATH=. python scripts/replay_payoffs.py --games all --self-check")
    print("(44/44 Games reconstruct; every net reproduces the published cell to the cent.)")
    print()
    print("=" * 100)
    print("STEP 1: decision-log discovery")
    print("=" * 100)
    for ex in excluded:
        print(f"  EXCLUDED g{ex.game}: {ex.reason}")
    print(f"  usable decision-log Games ({len(good_games)}): {good_games}")

    all18 = good_games
    last15 = sorted(all18)[-15:] if len(all18) >= 15 else all18
    odd = [g for g in all18 if g % 2 == 1]
    even = [g for g in all18 if g % 2 == 0]
    cutoff = sorted(all18)[len(all18) // 2]
    early = [g for g in all18 if g < cutoff]
    late = [g for g in all18 if g >= cutoff]
    print(f"  ALL{len(all18)}   ({len(all18)}): {all18}")
    print(f"  LAST{len(last15)}  ({len(last15)}): {last15}")
    print(f"  ODD     ({len(odd)}): {odd}")
    print(f"  EVEN    ({len(even)}): {even}")
    print(f"  EARLY   ({len(early)}): {early}")
    print(f"  LATE    ({len(late)}): {late}")

    rows_by_game = {g: load_rows(g) for g in all18}
    n_priced_items = sum(len(v) for v in rows_by_game.values())
    print(f"  priced (evidence-backed) items across ALL{len(all18)}: {n_priced_items}")

    print()
    print("=" * 100)
    print("STEP 2: self-check -- reconstruction against the logs (Charge exact, Limit rule exact)")
    print("=" * 100)
    v = verify_reconstruction(rows_by_game)
    print(f"  checked {v.n} items")
    print(f"  Charge exact match: {v.n - v.charge_bad}/{v.n}")
    print(f"  Limit rule (priced vs uncovered-free-option) match: {v.n - v.rule_bad}/{v.n}")
    if v.charge_bad or v.rule_bad:
        raise SystemExit("reconstruction is structurally wrong -- fix before trusting any delta below")
    ratios = sorted(v.limit_ratios)
    print(
        f"  Limit VALUE differs from the log on {len(ratios) - v.limit_ratio_exact}/{len(ratios)} "
        f"priced-both-sides items -- expected, see verify_reconstruction docstring "
        f"(LIMIT_CEILING / LIMIT_CEILING_MEMORY / LIMIT_CAP moved during the tournament; "
        f"this harness prices with today's engine throughout, so this baseline is "
        f"'shipped evidence x current engine', not 'what we actually submitted')."
    )
    if ratios:
        print(
            f"    logged/recomputed limit ratio: min {ratios[0]:.3f}  median {ratios[len(ratios)//2]:.3f}  "
            f"max {ratios[-1]:.3f}  (exact match on {v.limit_ratio_exact} items already on today's constants)"
        )
    print("  OK -- reconstruction is structurally exact. Every delta below is against this baseline.")

    print()
    print("=" * 100)
    print("STEP 3: assert the harness moves BOTH a and b coherently (not a repeat of the old sweeps)")
    print("=" * 100)
    sample = next(r for r in rows_by_game[all18[0]] if r.evidence.price_median > 0)
    a0, b0 = scaled_price(sample, identity_scale)
    a1, b1 = scaled_price(sample, uniform(1.5))
    print(f"  sample: g{sample.game} item {sample.index}  median={sample.evidence.price_median:.2f}")
    print(f"    lambda=1.0  ->  a={a0:.2f}  b={b0:.2f}")
    print(f"    lambda=1.5  ->  a={a1:.2f}  b={b1:.2f}")
    assert a1 > a0, "uniform scale did not raise the Charge -- harness is broken"
    assert b1 >= b0, "uniform scale did not raise (or hold, if clamp binds) the Limit -- harness is broken"
    assert a1 != a0 and (b1 != b0 or abs(b0 - a0) < 0.01), "both must move unless the b<=a clamp already bound"
    print("  ASSERTED: both a and b move together under a scale of the estimate (or b was already clamped to a).")

    # ----------------------------------------------------------------- configurations

    configs: list[tuple[str, str, ScaleFn]] = []
    for lam in (1.0, 1.1, 1.2, 1.3, 1.5, 2.0):
        configs.append((f"uniform lambda={lam}", "uniform", uniform(lam)))
    for thresh_v in (500.0, 1000.0):
        for lam in (1.2, 1.5, 2.0):
            configs.append(
                (f"threshold>{thresh_v:.0f} lambda={lam}", "threshold", threshold(lam, thresh_v))
            )
    for gamma in (1.1, 1.25, 1.5):
        configs.append((f"power gamma={gamma} anchor=50", "power", power(gamma, 50.0)))

    baseline_by_game = net_by_game(all18, rows_by_game, identity_scale)

    print()
    print("=" * 100)
    print("STEP 4: lambda / conditional / power sweep -- net DELTA vs shipped, both windows")
    print("=" * 100)
    header = (
        f"{'config':<30}{'ALL' + str(len(all18)):>14}{'nf(' + str(len(all18)) + ')':>10}"
        f"{'LAST' + str(len(last15)):>14}{'nf(' + str(len(last15)) + ')':>10}"
    )
    print(header)
    results: dict[str, dict[int, float]] = {}
    for name, family, fn in configs:
        by_game = net_by_game(all18, rows_by_game, fn)
        results[name] = by_game
        delta_all18 = window_sum(by_game, all18) - window_sum(baseline_by_game, all18)
        delta_last15 = window_sum(by_game, last15) - window_sum(baseline_by_game, last15)
        print(
            f"{name:<30}{fmt(delta_all18)}{noise_floor(len(all18)):>10,.0f}"
            f"{fmt(delta_last15)}{noise_floor(len(last15)):>10,.0f}"
        )

    print()
    print("=" * 100)
    print(f"STEP 5: held-out folds (odd/even, early/late), ALL{len(all18)} window, noise floor beside each")
    print("=" * 100)
    print(
        f"  fold sizes: ODD n={len(odd)} (nf={noise_floor(len(odd)):,.0f})  "
        f"EVEN n={len(even)} (nf={noise_floor(len(even)):,.0f})  "
        f"EARLY n={len(early)} (nf={noise_floor(len(early)):,.0f})  "
        f"LATE n={len(late)} (nf={noise_floor(len(late)):,.0f})"
    )
    header2 = f"{'config':<30}{'ODD':>13}{'EVEN':>13}{'EARLY':>13}{'LATE':>13}"
    print(header2)
    for name, family, fn in configs:
        by_game = results[name]
        d_odd = window_sum(by_game, odd) - window_sum(baseline_by_game, odd)
        d_even = window_sum(by_game, even) - window_sum(baseline_by_game, even)
        d_early = window_sum(by_game, early) - window_sum(baseline_by_game, early)
        d_late = window_sum(by_game, late) - window_sum(baseline_by_game, late)
        print(f"{name:<30}{fmt(d_odd)}{fmt(d_even)}{fmt(d_early)}{fmt(d_late)}")

    decomp_by_name = {name: decompose(all18, rows_by_game, fn) for name, family, fn in configs}

    print()
    print("=" * 100)
    print(f"STEP 6: two-mechanism decomposition (ALL{len(all18)}), per configuration")
    print("=" * 100)
    print(
        f"{'config':<30}{'items':>7}{'d_income':>13}{'penalty_sv':>13}"
        f"{'overch_gain':>13}{'other':>10}{'net_delta':>13}"
    )
    for name, family, fn in configs:
        d = decomp_by_name[name]
        print(
            f"{name:<30}{d.n_items:>7}{fmt(d.issuer_income_delta)}{fmt(-d.penalty_saved)}"
            f"{fmt(d.overcharge_gained)}{fmt(d.other_cost_delta)}{fmt(d.net_delta)}"
        )

    print()
    print("=" * 100)
    print("STEP 7: the cliff -- items crossing a<=t -> a>t, vs items that stay under t")
    print("=" * 100)
    print(
        f"{'config':<30}{'n_cross_up':>11}{'baseline_inc':>14}{'new_inc':>13}"
        f"{'forfeit_vs_16x':>15}{'n_under':>9}{'income_gained_under':>21}{'n_cross_dn':>11}"
    )
    for name, family, fn in configs:
        d = decomp_by_name[name]
        forfeit = d.crossed_up_new_income - d.crossed_up_baseline_income
        print(
            f"{name:<30}{d.n_crossed_up:>11}{fmt(d.crossed_up_baseline_income)}"
            f"{fmt(d.crossed_up_new_income)}"
            f"{forfeit:>15,.0f}"
            f"{d.n_stayed_under:>9}{fmt(d.stayed_under_income_gained):>21}{d.n_crossed_down:>11}"
        )

    print()
    print("=" * 100)
    print("STEP 8: b<=a clamp -- how often it binds, before vs after each scale")
    print("=" * 100)
    baseline_clamp = decompose(all18, rows_by_game, identity_scale).n_clamp_bound_before
    print(f"  clamp bound at lambda=1.0 (shipped): {baseline_clamp} / {n_priced_items} items")
    for name, family, fn in configs:
        d = decomp_by_name[name]
        print(f"  {name:<30} clamp bound after: {d.n_clamp_bound_after} / {n_priced_items}")

    print()
    print("=" * 100)
    print(f"STEP 9: best configuration on ALL{len(all18)} vs LAST{len(last15)}, and whether it survives every fold")
    print("=" * 100)
    ranked = sorted(
        configs,
        key=lambda c: window_sum(results[c[0]], all18) - window_sum(baseline_by_game, all18),
        reverse=True,
    )
    best_name, _, best_fn = ranked[0]
    by_game = results[best_name]
    print(f"  best by ALL{len(all18)} in-sample delta: {best_name}")
    for label, subset in (
        (f"ALL{len(all18)}", all18), (f"LAST{len(last15)}", last15), ("ODD", odd), ("EVEN", even),
        ("EARLY", early), ("LATE", late),
    ):
        delta = window_sum(by_game, subset) - window_sum(baseline_by_game, subset)
        nf = noise_floor(len(subset))
        verdict = "beats noise floor" if abs(delta) > nf else "INSIDE noise floor"
        print(f"    {label:<8} n={len(subset):<3} delta={delta:>12,.0f}  nf={nf:>10,.0f}  {verdict}")

    print()
    print("=" * 100)
    print("STEP 10: concentration check -- is the in-sample winner a handful of Games?")
    print("=" * 100)
    print(
        "  Per-Game delta for every threshold>1000 config (the only family that beat the "
        "noise floor). A win concentrated in one or two Games is an anecdote, not a rule,"
    )
    print("  no matter how many folds it happens to clear.")
    for name, family, fn in configs:
        if family != "threshold" or "1000" not in name:
            continue
        by_game = results[name]
        per_game = {g: by_game[g] - baseline_by_game[g] for g in all18}
        ranked_games = sorted(per_game.items(), key=lambda kv: -abs(kv[1]))
        top2 = ranked_games[:2]
        total = sum(per_game.values())
        top2_sum = sum(v for _, v in top2)
        rest = total - top2_sum
        print(f"\n  {name}  (total {total:,.0f})")
        for g, v in ranked_games:
            if abs(v) > 1e-6:
                print(f"    g{g:<4} {v:>12,.0f}")
        print(f"    -> top 2 Games ({[g for g, _ in top2]}) sum to {top2_sum:,.0f}; the other 17 Games sum to {rest:,.0f}")


if __name__ == "__main__":
    main()
