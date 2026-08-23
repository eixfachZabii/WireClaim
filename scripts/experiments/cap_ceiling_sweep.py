"""LIMIT_CAP swept in isolation, and LIMIT_CEILING swept conditioned on estimate confidence.

Two families, held separate because the binding-frequency audit
(`limit_binding_audit.py`) shows they bind on almost disjoint items: LIMIT_CEILING binds on
271 of 425 rows (70.4% of wrongful-rejection penalty) over Games 1-36; LIMIT_CAP binds on 16
(15.4%). Both swept here in euros against the real Field
(`scripts.replay_payoffs.replay`), holding everything else at shipped values, with held-out
folds (odd/even, and a time split) and the noise floor beside every number.

    PYTHONPATH=. pixi run python scripts/experiments/cap_ceiling_sweep.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.charge_buckets import ALL_GAMES, Row, dataset, snapshot  # noqa: E402
from scripts.replay_payoffs import replay  # noqa: E402

from src.pricing.engine import (  # noqa: E402
    CHARGE_BOUNDS,
    CHARGE_INTERCEPT,
    CHARGE_SLOPE,
    COVERAGE_FLOOR,
    LIMIT_CAP,
    LIMIT_CEILING,
    LIMIT_QUANTILE,
    _lognormal_quantile,
    implied_sigma,
)

NOISE_FLOOR_18 = 26_622
WINDOW_19_32 = tuple(g for g in ALL_GAMES if 19 <= g <= 32)


def noise_floor(n_games: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(n_games / 18.0)


PriceFn = Callable[[Row], tuple[float, float]]


def _base(row: Row) -> tuple[float, float]:
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    covered = 0.0 if row.uncovered else filled.coverage_probability
    low, high = CHARGE_BOUNDS
    factor = min(max(CHARGE_INTERCEPT - CHARGE_SLOPE * sigma, low), high)
    charge = max(factor, 0.0) * filled.price_median
    return charge, sigma, covered, filled.price_median


def make_rule(*, cap: float, ceiling_fn: Callable[[Row], float]) -> PriceFn:
    def price(row: Row) -> tuple[float, float]:
        charge, sigma, covered, median = _base(row)
        if covered <= COVERAGE_FLOOR:
            return round(max(charge, 0.0), 2), 0.0
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        q = _lognormal_quantile(median, sigma, conditional)
        ceiling = ceiling_fn(row)
        limit = min(q, ceiling * median, cap, charge)
        return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)

    return price


def flat_ceiling(value: float) -> Callable[[Row], float]:
    return lambda row: value


SHIPPED = make_rule(cap=LIMIT_CAP, ceiling_fn=flat_ceiling(LIMIT_CEILING))


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


def odd_even(games) -> tuple[tuple[int, ...], tuple[int, ...]]:
    return tuple(g for g in games if g % 2 == 1), tuple(g for g in games if g % 2 == 0)


def time_split(games, cut: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    return tuple(g for g in games if g <= cut), tuple(g for g in games if g > cut)


def report(rows: list[Row], name: str, candidates: list[tuple[str, PriceFn]], games, cut: int) -> None:
    base = total(rows, SHIPPED, games)
    odd, even = odd_even(games)
    early, late = time_split(games, cut)
    base_odd, base_even = total(rows, SHIPPED, odd), total(rows, SHIPPED, even)
    base_early, base_late = total(rows, SHIPPED, early), total(rows, SHIPPED, late)
    floor = noise_floor(len(games))
    print(f"\n--- {name}: {len(games)} Games {games[0]}-{games[-1]}  (shipped net {base:+,.0f}, noise floor +/-{floor:,.0f}) ---")
    print(f"{'candidate':<32}{'all':>12}{'delta':>11}{'odd f':>10}{'even f':>10}{'<=%d f'%cut:>10}{'>%d f'%cut:>9}")
    for label, fn in candidates:
        t = total(rows, fn, games)
        t_odd = total(rows, fn, odd) - base_odd
        t_even = total(rows, fn, even) - base_even
        t_early = total(rows, fn, early) - base_early if early else float("nan")
        t_late = total(rows, fn, late) - base_late if late else float("nan")
        print(
            f"{label:<32}{t:>12,.0f}{t - base:>11,.0f}"
            f"{t_odd:>10,.0f}{t_even:>10,.0f}{t_early:>10,.0f}{t_late:>9,.0f}"
        )


def main() -> None:
    rows = dataset(games=ALL_GAMES)
    all_games = ALL_GAMES

    print("=" * 120)
    print("PART 1 -- LIMIT_CAP swept in isolation (LIMIT_CEILING and LIMIT_QUANTILE held at shipped 0.45 / 1/3)")
    print("=" * 120)
    cap_candidates = [
        (f"cap {v:,.0f}", make_rule(cap=v, ceiling_fn=flat_ceiling(LIMIT_CEILING)))
        for v in (708.0, 1000.0, 1500.0, 2500.0, 5000.0, float("inf"))
    ]
    report(rows, "Games 19-32 (brief's window)", cap_candidates, WINDOW_19_32, cut=25)
    report(rows, f"all settled Games", cap_candidates, all_games, cut=(all_games[0] + all_games[-1]) // 2)

    print("\n" + "=" * 120)
    print("PART 2a -- LIMIT_CEILING conditioned on memory channel (Price Memory items looser; model-only stays 0.45; cap held at 708)")
    print("=" * 120)
    memory_candidates = [
        (
            f"memory ceiling {m:.2f}",
            make_rule(
                cap=LIMIT_CAP,
                ceiling_fn=lambda row, m=m: m if row.has_memory else LIMIT_CEILING,
            ),
        )
        for m in (0.45, 0.55, 0.65, 0.75, 0.85, 1.00, 1.25, 1.50)
    ]
    report(rows, "Games 19-32", memory_candidates, WINDOW_19_32, cut=25)
    report(rows, "all settled Games", memory_candidates, all_games, cut=(all_games[0] + all_games[-1]) // 2)

    print("\n" + "=" * 120)
    print("PART 2b -- LIMIT_CEILING conditioned on band width (narrow sigma gets looser ceiling; cap held at 708)")
    print("=" * 120)
    NARROW = 0.30  # sigma below this = "confident" band

    def narrow_ceiling(row: Row, loose: float) -> float:
        return loose if row.sigma < NARROW else LIMIT_CEILING

    narrow_candidates = [
        (f"narrow(sigma<{NARROW}) ceiling {v:.2f}", make_rule(cap=LIMIT_CAP, ceiling_fn=lambda row, v=v: narrow_ceiling(row, v)))
        for v in (0.45, 0.60, 0.75, 0.90, 1.10, 1.40)
    ]
    report(rows, "Games 19-32", narrow_candidates, WINDOW_19_32, cut=25)
    report(rows, "all settled Games", narrow_candidates, all_games, cut=(all_games[0] + all_games[-1]) // 2)

    print("\n" + "=" * 120)
    print("PART 2c -- LIMIT_CEILING conditioned on coverage probability (high-confidence coverage gets looser ceiling; cap held at 708)")
    print("=" * 120)
    HIGH_COV = 0.90

    def cov_ceiling(row: Row, loose: float) -> float:
        cov = 0.0 if row.uncovered else row.evidence.coverage_probability
        return loose if cov >= HIGH_COV else LIMIT_CEILING

    cov_candidates = [
        (f"cov>={HIGH_COV} ceiling {v:.2f}", make_rule(cap=LIMIT_CAP, ceiling_fn=lambda row, v=v: cov_ceiling(row, v)))
        for v in (0.45, 0.60, 0.75, 0.90, 1.10, 1.40)
    ]
    report(rows, "Games 19-32", cov_candidates, WINDOW_19_32, cut=25)
    report(rows, "all settled Games", cov_candidates, all_games, cut=(all_games[0] + all_games[-1]) // 2)

    part3_combined(rows, all_games)


def part3_combined(rows: list[Row], all_games) -> None:
    def memory_ceiling(row: Row, v: float) -> float:
        return v if row.has_memory else LIMIT_CEILING

    combos = [
        ("shipped (0.45 ceiling, cap 708)", make_rule(cap=708.0, ceiling_fn=flat_ceiling(LIMIT_CEILING))),
        ("memory-0.75 ceiling, cap 708", make_rule(cap=708.0, ceiling_fn=lambda r: memory_ceiling(r, 0.75))),
        ("memory-0.75 ceiling, cap 1000", make_rule(cap=1000.0, ceiling_fn=lambda r: memory_ceiling(r, 0.75))),
        ("memory-0.75 ceiling, cap 1500", make_rule(cap=1500.0, ceiling_fn=lambda r: memory_ceiling(r, 0.75))),
        ("flat ceiling 0.75 (all items), cap 708", make_rule(cap=708.0, ceiling_fn=flat_ceiling(0.75))),
    ]
    print("\n" + "=" * 120)
    print("PART 3 -- best member of the family: memory-conditional ceiling x cap, combined")
    print("=" * 120)
    report(rows, "Games 19-32", combos, WINDOW_19_32, cut=25)
    report(rows, "all settled Games", combos, all_games, cut=(all_games[0] + all_games[-1]) // 2)


if __name__ == "__main__":
    main()
