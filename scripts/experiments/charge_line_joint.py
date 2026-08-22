"""With a calibrated band in hand, re-fit the Charge line jointly -- the open question.

`src/domain/pricing/engine.py` carries a standing contradiction it cannot resolve on its own:

    CHARGE_INTERCEPT/CHARGE_SLOPE give  k = 0.85 - 0.45 * sigma,  fitted empirically.
    The closed form -- maximise  k * P(t >= k * t_hat) = k * Phi(-ln k / sigma) -- says the
    optimum is nearly FLAT near 0.75 and RISES with sigma, reaching ~0.965 at sigma 0.77.

The fit and the derivation disagree about the *sign*. `level_width.py` already showed why
the fit cannot simply be replaced: "telling the truth about the width costs money", because
`charge_factor` reads sigma as `0.85 - 0.45 sigma`, so an honest sigma of 1.29 drops the
Charge to its 0.30 floor and forfeits income on everything priced correctly. Its own
conclusion was that "the band and the Charge line are calibrated **as a pair**; fixing one
alone unpicks the pair. Anybody re-deriving CHARGE_INTERCEPT/CHARGE_SLOPE from a measured
sigma has to move both constants in the same commit, and score it in euros."

That is exactly what this does. `band_width_fix.py` established that today's band is a
*constant* on 84% of items and that unpinning it produces a width that orders the error
monotonically (expensive tail: 0.154 / 0.410 / 1.752 against a pinned 1.206 / 0.197 / 1.435).
So for the first time the sigma fed to `charge_factor` measures something, and the pair can be
moved together.

Swept here, all against the real Field through `replay_payoffs.replay`:

    band            shipped (pinned 0.3495) | width_only (calibrated, median held fixed)
    charge line     (intercept, slope) over a grid, plus the closed-form optimiser
    folds           odd/even and early/late, with the noise floor beside every cell

The closed form is included as its own "rule" rather than as a grid point, because its whole
claim is that `k` should RISE with sigma; a grid of downward-sloping lines cannot express it.

Offline. No LLM calls.

    PYTHONPATH=. pixi run python scripts/experiments/charge_line_joint.py
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))

from src.pricing.engine import (  # noqa: E402
    CHARGE_BOUNDS,
    COVERAGE_FLOOR,
    LIMIT_CAP,
    LIMIT_CEILING,
    LIMIT_CEILING_MEMORY,
    LIMIT_QUANTILE,
    Evidence,
    _lognormal_quantile,
    implied_sigma,
)
from src.strategies.strategy2.channels import local_evidence  # noqa: E402
from src.data.case_loader import read_case  # noqa: E402

from replay_payoffs import replay, snapshot  # noqa: E402
from retest_score import CASES, INF, ensemble  # noqa: E402
from band_width_fix import combine_variant  # noqa: E402

NOISE_FLOOR_18 = 26622.0


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def closed_form_k(sigma: float, grid: int = 200) -> float:
    """argmax over k of `k * Phi(-ln k / sigma)` -- expected income under a lognormal error.

    Income is `a` whenever `a <= t` and ~0 above it, so with `t = t_hat * exp(N(0, sigma))`
    the expected income from charging `k * t_hat` is `k * P(t >= k t_hat)`, and
    `P(t >= k t_hat) = Phi(-ln k / sigma)`. Solved numerically rather than in closed form
    because the stationarity condition is transcendental.
    """
    if sigma <= 1e-9:
        return 1.0
    best_k, best_value = 0.0, -1.0
    for i in range(1, grid + 1):
        k = 1.5 * i / grid
        value = k * _normal_cdf(-math.log(k) / sigma)
        if value > best_value:
            best_k, best_value = k, value
    return best_k


def price_with_line(
    evidence: Evidence, *, confirmed_uncovered: bool, memory_backed: bool,
    intercept: float, slope: float, closed_form: bool,
) -> tuple[float, float]:
    """`price_item`, verbatim, with only `charge_factor` replaced. Everything else is shipped.

    The Limit path, the coverage collapse, both ceilings, the absolute cap and the `b <= a`
    clamp are reproduced exactly, so a delta here is attributable to the Charge line alone.
    """
    filled = evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    covered = 0.0 if confirmed_uncovered else filled.coverage_probability

    if closed_form:
        factor = closed_form_k(sigma)
    else:
        factor = intercept - slope * sigma
    low, high = CHARGE_BOUNDS
    factor = min(max(factor, low), high)
    charge = factor * filled.price_median

    if covered <= COVERAGE_FLOOR:
        limit = 0.0
    else:
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        ceiling = LIMIT_CEILING_MEMORY if memory_backed else LIMIT_CEILING
        candidates = [
            _lognormal_quantile(filled.price_median, sigma, conditional),
            ceiling * filled.price_median,
        ]
        if not memory_backed:
            candidates.append(LIMIT_CAP)
        limit = min(candidates)
    limit = min(limit, charge)
    return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)


def build(games: list[int], model_tag: str, band: str, rules: list[tuple]):
    subs = {label: {} for label, *_ in rules}
    for game_id in games:
        try:
            snap = snapshot(game_id)
        except Exception:
            continue
        case_dir = CASES / f"case_{game_id:02d}"
        if not (case_dir / "policy.txt").exists():
            continue
        model = ensemble(game_id, model_tag)
        if not model:
            continue
        case = asyncio.run(read_case(game_id, case_dir))
        mem = local_evidence(case)
        uncovered = {li.index: bool(getattr(li, "quantity_missing", False)) for li in case.line_items}

        for label, intercept, slope, closed in rules:
            submission = {}
            for index in snap.line_items:
                combined = combine_variant(model.get(index), mem.get(index), band)
                if combined is None:
                    continue
                unc = uncovered.get(index, False)
                submission[index] = price_with_line(
                    combined,
                    confirmed_uncovered=unc,
                    memory_backed=mem.get(index) is not None and not unc,
                    intercept=intercept, slope=slope, closed_form=closed,
                )
            if submission:
                subs[label][game_id] = (snap, submission)
    return subs


def report(subs, rules, games, baseline_label: str, title: str) -> None:
    print(f"\n{title}")
    folds = [
        ("all", games),
        ("odd", [g for g in games if g % 2 == 1]),
        ("even", [g for g in games if g % 2 == 0]),
        ("early 1-20", [g for g in games if g <= 20]),
        ("late 21+", [g for g in games if g > 20]),
        ("recent 34+", [g for g in games if g >= 34]),
    ]
    header = f"  {'rule':22s}" + "".join(f"{name:>14s}" for name, _ in folds)
    print(header)
    base_totals = {}
    for name, subset in folds:
        common = sorted(set(subs[baseline_label]) & set(subset))
        base_totals[name] = sum(replay(*subs[baseline_label][g]).net for g in common)
    print(f"  {baseline_label + ' (abs)':22s}" + "".join(f"{base_totals[n]:>14,.0f}" for n, _ in folds))
    for label, *_ in rules:
        if label == baseline_label:
            continue
        cells = []
        for name, subset in folds:
            common = sorted(set(subs[label]) & set(subs[baseline_label]) & set(subset))
            if not common:
                cells.append(f"{'-':>14s}")
                continue
            total = sum(replay(*subs[label][g]).net for g in common)
            delta = total - base_totals[name]
            nf = NOISE_FLOOR_18 * math.sqrt(len(common) / 18.0)
            cells.append(f"{delta:>+13,.0f}{'*' if abs(delta) > nf else ' '}")
        print(f"  {label:22s}" + "".join(cells))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="mini", choices=("mini", "terra"))
    args = parser.parse_args()

    print("closed-form argmax of k * Phi(-ln k / sigma), for reference:")
    for s in (0.20, 0.35, 0.50, 0.65, 0.77, 1.00, 1.30):
        print(f"    sigma {s:.2f} -> k {closed_form_k(s):.3f}   (shipped line: {0.85 - 0.45 * s:.3f})")

    games = sorted(
        int(p.name.split("_")[1])
        for p in CASES.iterdir()
        if p.name.startswith("case_") and p.name.split("_")[1].isdigit() and int(p.name.split("_")[1]) > 0
    )

    rules = [
        ("shipped 0.85-0.45s", 0.85, 0.45, False),
        ("flat 0.70", 0.70, 0.0, False),
        ("flat 0.75", 0.75, 0.0, False),
        ("flat 0.80", 0.80, 0.0, False),
        ("0.95-0.45s", 0.95, 0.45, False),
        ("0.75-0.20s", 0.75, 0.20, False),
        ("rising 0.60+0.25s", 0.60, -0.25, False),
        ("closed form", 0.0, 0.0, True),
    ]

    for band in ("shipped", "width_only"):
        subs = build(games, args.model, band, rules)
        report(subs, rules, games, "shipped 0.85-0.45s",
               f"=== band = {band} ===  (model={args.model}; '*' = outside that fold's floor)")


if __name__ == "__main__":
    main()
