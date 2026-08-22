"""Three candidate fixes for the one open lever (H3: item accuracy), replayed in euros.

Everything in `scripts/charge_buckets.py` multiplies the **Charge** only -- `Rule.scale`
touches `charge_factor(sigma) * median` and the Limit is only ever a passive `min(..., a)`
of it. Every one of those candidates lost money out of sample (see `rules()`/`holdout()`
there, and the docstring in `src/pricing.py`). This file tests three candidates that were
NOT swept there because they touch the **Limit** side, or the **sigma** that feeds both
numbers, instead of a post-hoc Charge multiplier -- which is exactly where H3's own note
says the residual prize is ("what little there is to win belongs on the Limit side").

Method, identical to `charge_buckets.py` so the numbers are comparable: one row per (Game,
Line Item) for Games 1-32 (`charge_buckets.dataset`), each carrying the evidence available
at decision time and the Fair Value bracket recovered afterwards. Every euro number is
`replay_payoffs.replay` against the real Field, held fixed. Deltas are against the shipped
`Rule()` on the SAME dataset (not the true historical submission -- Games 1-25 are
"recon" rows, i.e. what today's pricing would have done; see `charge_buckets.py`'s own
docstring for why that is the only comparison that isolates the rule).

Candidates
----------
C1  Re-validate `LIMIT_CAP` with the 5 Games (28-32) the original audit did not have.
    `penalty_audit.py` found a 8x-24x SETTLED_MEDIAN plateau over Games 1-27; this re-sweeps
    it over 1-32 holding today's shipped `LIMIT_CEILING = 0.45`.

C2  Channel-conditional `LIMIT_CEILING`: memory-backed items get a looser ceiling (Price
    Memory's measured error is 0.43 against the model's ~0.8, so trusting it further on the
    accept side costs nothing extra on the Charge). Model-only items keep the shipped 0.45.

C3  Channel-conditional sigma: replace the model's self-asserted (uncalibrated -- see
    `src/pricing.py`'s own docstring, "the width carries no signal") `implied_sigma(band)`
    with a fixed, MEASURED prior -- `MEMORY_SIGMA = 0.43` wherever Price Memory spoke,
    `MODEL_SIGMA_HIGH` (swept) where only the model did. This feeds BOTH the Charge factor
    and the Limit quantile coherently, unlike a Charge-only multiplier.

    PYTHONPATH=. pixi run python scripts/leak_candidates.py
"""

from __future__ import annotations

import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from charge_buckets import Row, dataset, snapshot  # noqa: E402
from replay_payoffs import replay  # noqa: E402

from src.domain.pricing.engine import (  # noqa: E402
    CHARGE_BOUNDS,
    CHARGE_INTERCEPT,
    CHARGE_SLOPE,
    COVERAGE_FLOOR,
    LIMIT_CEILING,
    LIMIT_QUANTILE,
    _lognormal_quantile,
    implied_sigma,
)
from src.services.strategies.strategy2.constants import MEMORY_SIGMA  # noqa: E402

ALL_GAMES = tuple(range(1, 33))
LOGGED_GAMES = tuple(range(26, 33))
NOISE_FLOOR_18 = 26_622


def noise_floor(n_games: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(n_games / 18.0)


PriceFn = Callable[[Row], tuple[float, float]]


def shipped(row: Row) -> tuple[float, float]:
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    covered = 0.0 if row.uncovered else filled.coverage_probability
    low, high = CHARGE_BOUNDS
    factor = min(max(CHARGE_INTERCEPT - CHARGE_SLOPE * sigma, low), high)
    charge = max(factor, 0.0) * filled.price_median
    limit = _limit(filled.price_median, sigma, covered, LIMIT_CEILING, cap=708.0)
    limit = min(limit, charge)
    return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)


def _limit(median: float, sigma: float, covered: float, ceiling: float, *, cap: float) -> float:
    if covered <= COVERAGE_FLOOR:
        return 0.0
    conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
    return min(_lognormal_quantile(median, sigma, conditional), ceiling * median, cap)


def make_cap_rule(cap: float) -> PriceFn:
    def price(row: Row) -> tuple[float, float]:
        filled = row.evidence.with_defaults()
        sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
        covered = 0.0 if row.uncovered else filled.coverage_probability
        low, high = CHARGE_BOUNDS
        factor = min(max(CHARGE_INTERCEPT - CHARGE_SLOPE * sigma, low), high)
        charge = max(factor, 0.0) * filled.price_median
        limit = min(_limit(filled.price_median, sigma, covered, LIMIT_CEILING, cap=cap), charge)
        return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)

    return price


def make_channel_ceiling_rule(memory_ceiling: float, model_ceiling: float = LIMIT_CEILING) -> PriceFn:
    def price(row: Row) -> tuple[float, float]:
        filled = row.evidence.with_defaults()
        sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
        covered = 0.0 if row.uncovered else filled.coverage_probability
        low, high = CHARGE_BOUNDS
        factor = min(max(CHARGE_INTERCEPT - CHARGE_SLOPE * sigma, low), high)
        charge = max(factor, 0.0) * filled.price_median
        ceiling = memory_ceiling if row.has_memory else model_ceiling
        limit = min(_limit(filled.price_median, sigma, covered, ceiling, cap=708.0), charge)
        return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)

    return price


def make_channel_sigma_rule(model_sigma: float, memory_sigma: float = MEMORY_SIGMA) -> PriceFn:
    def price(row: Row) -> tuple[float, float]:
        filled = row.evidence.with_defaults()
        sigma = memory_sigma if row.has_memory else model_sigma
        covered = 0.0 if row.uncovered else filled.coverage_probability
        low, high = CHARGE_BOUNDS
        factor = min(max(CHARGE_INTERCEPT - CHARGE_SLOPE * sigma, low), high)
        charge = max(factor, 0.0) * filled.price_median
        limit = min(_limit(filled.price_median, sigma, covered, LIMIT_CEILING, cap=708.0), charge)
        return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)

    return price


def euros(rows: list[Row], price_fn: PriceFn, games) -> dict[int, float]:
    by_game: dict[int, list[Row]] = {}
    for row in rows:
        by_game.setdefault(row.game, []).append(row)
    out = {}
    for game_id in games:
        snap = snapshot(game_id)
        submission = {row.index: price_fn(row) for row in by_game.get(game_id, [])}
        actual = {
            index: (snap.charges[index][snap.us], snap.limit_point(index, snap.us))
            for index in snap.line_items
        }
        actual.update(submission)
        out[game_id] = replay(snap, actual).net
    return out


def total(rows: list[Row], price_fn: PriceFn, games) -> float:
    return sum(euros(rows, price_fn, games).values())


def holdout_split(games) -> tuple[tuple[int, ...], tuple[int, ...]]:
    odd = tuple(g for g in games if g % 2 == 1)
    even = tuple(g for g in games if g % 2 == 0)
    return odd, even


def sweep(rows: list[Row], name: str, candidates: list[tuple[str, PriceFn]], games) -> None:
    base = total(rows, shipped, games)
    odd, even = holdout_split(games)
    base_odd, base_even = total(rows, shipped, odd), total(rows, shipped, even)
    print(f"\n--- {name} (baseline shipped = {base:+,.0f} over {len(games)} Games) ---")
    print(f"{'candidate':<28}{'all':>12}{'delta':>11}{'odd->even':>13}{'even->odd':>13}")
    for label, fn in candidates:
        t = total(rows, fn, games)
        t_odd = total(rows, fn, odd)
        t_even = total(rows, fn, even)
        print(
            f"{label:<28}{t:>12,.0f}{t - base:>11,.0f}"
            f"{t_even - base_even:>13,.0f}{t_odd - base_odd:>13,.0f}"
        )
    floor = noise_floor(len(games))
    print(f"noise floor over {len(games)} Games: +/-{floor:,.0f}")


def main() -> None:
    rows_all = dataset(games=ALL_GAMES)
    rows_logged = [r for r in rows_all if r.origin == "logged"]

    print("=" * 100)
    print("C1 -- LIMIT_CAP re-swept over Games 1-32 (ceiling held at shipped 0.45)")
    print("=" * 100)
    cap_candidates = [
        (f"cap {m:.0f}x med ({m*59:.0f})", make_cap_rule(m * 59.0))
        for m in (8, 12, 16, 20, 24, 30, 40)
    ]
    sweep(rows_all, "all 32 Games", cap_candidates, ALL_GAMES)
    sweep(rows_logged, "logged-only (26-32)", cap_candidates, LOGGED_GAMES)

    print("\n" + "=" * 100)
    print("C2 -- channel-conditional LIMIT_CEILING (memory-backed items looser, model-only unchanged)")
    print("=" * 100)
    ceiling_candidates = [
        (f"memory ceiling {m:.2f}", make_channel_ceiling_rule(m))
        for m in (0.45, 0.55, 0.65, 0.75, 0.85, 1.0)
    ]
    sweep(rows_all, "all 32 Games", ceiling_candidates, ALL_GAMES)
    sweep(rows_logged, "logged-only (26-32)", ceiling_candidates, LOGGED_GAMES)

    print("\n" + "=" * 100)
    print("C3 -- channel-conditional sigma feeding BOTH Charge and Limit")
    print("=" * 100)
    sigma_candidates = [
        (f"model-sigma {m:.2f} (memory=0.43)", make_channel_sigma_rule(m))
        for m in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2)
    ]
    sweep(rows_all, "all 32 Games", sigma_candidates, ALL_GAMES)
    sweep(rows_logged, "logged-only (26-32)", sigma_candidates, LOGGED_GAMES)


if __name__ == "__main__":
    main()
