"""Is the model's price *shrunk toward the middle*, and does un-shrinking it pay?

`tail_diagnose.py` finds the level error is not a constant bias: the model runs ~4x high on
Line Items worth under 50 EUR and ~10% low on those worth over 400. That is the signature
of an estimate pulled toward a central prior, and it has a one-parameter correction:

    log t_hat' = intercept + gamma * log t_hat        gamma > 1 un-shrinks

This fits that line against the recovered Fair Values (euro-weighted, because a EUR 10
error on a EUR 10 item is not the same event as a EUR 3,000 error on a EUR 7,000 one) and
then scores the correction where it counts, in `replay_payoffs.replay`.

    pixi run python scripts/tail_shrink.py --games 1-15,17-19 --frozen-pricing
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from replay_payoffs import replay, snapshot  # noqa: E402
from tail_replay import (  # noqa: E402
    case_of,
    inflate,
    load_evidence,
    parse_games,
    submission_of,
)

from src.pricing.engine import Evidence  # noqa: E402

BAND_Z = 1.645


def fit(rows: list[tuple[float, float, float]]) -> tuple[float, float]:
    """Weighted least squares of `log t` on `log median`. Returns (intercept, gamma)."""
    total = sum(w for _, _, w in rows)
    mean_x = sum(w * math.log(m) for t, m, w in rows) / total
    mean_y = sum(w * math.log(t) for t, m, w in rows) / total
    cov = sum(w * (math.log(m) - mean_x) * (math.log(t) - mean_y) for t, m, w in rows) / total
    var = sum(w * (math.log(m) - mean_x) ** 2 for t, m, w in rows) / total
    gamma = cov / var if var > 0 else 1.0
    return mean_y - gamma * mean_x, gamma


def rescale(ev: Evidence, intercept: float, gamma: float) -> Evidence:
    if ev.price_median <= 0:
        return ev
    median = math.exp(intercept + gamma * math.log(ev.price_median))
    sigma = 1.0
    if ev.price_low > 0 and ev.price_high > ev.price_low:
        sigma = math.log(ev.price_high / ev.price_low) / (2 * BAND_Z)
    return Evidence(
        index=ev.index,
        coverage_probability=ev.coverage_probability,
        price_low=median * math.exp(-BAND_Z * sigma),
        price_median=median,
        price_high=median * math.exp(BAND_Z * sigma),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-15,17-19")
    parser.add_argument("--tag", default="model")
    parser.add_argument("--tail-factor", type=float, default=1.0)
    parser.add_argument("--frozen-pricing", action="store_true")
    parser.add_argument("--weight", default="euro", choices=("euro", "flat"))
    args = parser.parse_args()

    loaded = []
    rows: list[tuple[float, float, float]] = []
    for game_id in parse_games(args.games):
        model = load_evidence(game_id, args.tag)
        case = case_of(game_id)
        if model is None or case is None:
            continue
        snap = inflate(snapshot(game_id), args.tail_factor)
        loaded.append((snap, case, model))
        for index, ev in model.items():
            if index not in snap.fair_brackets or ev.price_median <= 0:
                continue
            t = snap.fair_point(index)
            if t <= 0:
                continue
            rows.append((t, ev.price_median, t if args.weight == "euro" else 1.0))

    intercept, gamma = fit(rows)
    print(f"fit over {len(rows)} items ({args.weight}-weighted): "
          f"log t = {intercept:.3f} + {gamma:.3f} * log t_hat")

    def total(transform) -> float:
        return sum(
            replay(snap, submission_of(case, {i: transform(ev) for i, ev in model.items()})).net
            for snap, case, model in loaded
        )

    baseline = total(lambda ev: ev)
    print(f"{'gamma':>7} {'intercept':>11} {'net':>14} {'delta':>12}")
    print(f"{1.0:7.2f} {0.0:11.3f} {baseline:14,.0f} {0.0:12,.0f}")
    for candidate in (1.05, 1.1, 1.15, 1.2, 1.3, gamma):
        # Hold the fit's own centre of mass fixed so gamma alone is varied.
        centre = math.exp(sum(math.log(m) for _, m, _ in rows) / len(rows))
        offset = math.log(centre) * (1 - candidate)
        net = total(lambda ev, g=candidate, c=offset: rescale(ev, c, g))
        print(f"{candidate:7.2f} {offset:11.3f} {net:14,.0f} {net - baseline:12,.0f}")
    net = total(lambda ev: rescale(ev, intercept, gamma))
    print(f"{gamma:7.2f} {intercept:11.3f} {net:14,.0f} {net - baseline:12,.0f}  (fitted)")


if __name__ == "__main__":
    main()
