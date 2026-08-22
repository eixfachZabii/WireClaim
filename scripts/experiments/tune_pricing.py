"""Measure the pricing constants in `src.domain.pricing.engine` against the real payoff table.

Why this exists
---------------
`src/domain/pricing/engine.py` carries three fitted numbers -- the Charge factor line, the Limit
quantile with its ceiling, and the coverage floor -- and its docstring says they came out
of "a crude simulation". `scripts/replay_payoffs.py` reproduces all fourteen published
nets to the cent, so the honest thing to do is to score the constants in euros against the
real Field instead of against a simulation.

    pixi run python scripts/tune_pricing.py all

The pipeline is: cached model evidence (`scripts/dump_evidence.py`, no quota spent) ->
`price(evidence, Params)` -> `replay_payoffs.replay` -> net in euros, summed over Games
1-14.

Two estimators, deliberately kept apart
---------------------------------------
Multipliers tuned on top of a *biased* estimator absorb that bias, and go wrong the moment
somebody fixes it. So everything is measured twice:

* ``--source model``     the real cached evidence, bias and all;
* ``--source unbiased``  synthetic evidence whose median is the true Fair Value blurred by
  lognormal noise of a stated quality, i.e. an estimator with the same *precision* and no
  *bias*. The band is drawn to be self-consistent with that noise, so `implied_sigma`
  recovers the true error size.

Everything here is read-only with respect to the tournament data; the only state it
touches is `var/evidence` (read) and `var/replay` (read).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dump_evidence import load as load_evidence  # noqa: E402
from replay_payoffs import GameSnapshot, replay, snapshot  # noqa: E402

from src.domain.pricing.engine import (  # noqa: E402
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

GAMES = tuple(range(1, 15))


# ------------------------------------------------------------------ parameterised pricer


@dataclass(frozen=True)
class Params:
    """Every constant `price_item` reads, in one movable object."""

    charge_intercept: float = CHARGE_INTERCEPT
    charge_slope: float = CHARGE_SLOPE
    charge_low: float = CHARGE_BOUNDS[0]
    charge_high: float = CHARGE_BOUNDS[1]
    limit_quantile: float = LIMIT_QUANTILE
    limit_ceiling: float = LIMIT_CEILING
    coverage_floor: float = COVERAGE_FLOOR
    #: `price_item` ends with `b = min(b, a)`. That is an assertion about the posterior,
    #: not a payoff-table fact -- the Charge and the Limit are answers to two different
    #: questions -- so it has to be swept like anything else.
    cap_limit_at_charge: bool = True

    def label(self) -> str:
        return (
            f"charge {self.charge_intercept:.2f}-{self.charge_slope:.2f}s"
            f"[{self.charge_low:.2f},{self.charge_high:.2f}] "
            f"q={self.limit_quantile:.2f} ceil={self.limit_ceiling:.2f} "
            f"floor={self.coverage_floor:.2f}"
        )


BASELINE = Params()


def price(evidence: Evidence, params: Params) -> tuple[float, float]:
    """`price_item` with the constants lifted out. Kept byte-identical in behaviour."""
    filled = evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    covered = filled.coverage_probability

    factor = min(
        max(params.charge_intercept - params.charge_slope * sigma, params.charge_low),
        params.charge_high,
    )
    charge = factor * filled.price_median

    if covered <= params.coverage_floor:
        limit = 0.0
    else:
        conditional = (params.limit_quantile - (1.0 - covered)) / covered
        limit = min(
            _lognormal_quantile(filled.price_median, sigma, conditional),
            params.limit_ceiling * filled.price_median,
        )
    if params.cap_limit_at_charge:
        limit = min(limit, charge)
    return round(max(charge, 0.0), 2), round(max(limit, 0.0), 2)


def submission(evidence: Mapping[int, Evidence], params: Params) -> dict[int, tuple[float, float]]:
    return {index: price(item, params) for index, item in evidence.items()}


# ---------------------------------------------------------------------------- evidence


EvidenceSource = Callable[[GameSnapshot], Mapping[int, Evidence]]


def model_evidence(snap: GameSnapshot) -> dict[int, Evidence]:
    """The real cached model evidence -- biased estimator, exactly what we shipped."""
    cached = load_evidence(snap.game_id)
    if cached is None:
        raise SystemExit(
            f"no cached evidence for Game {snap.game_id}; run scripts/dump_evidence.py"
        )
    return {index: cached[index] for index in snap.line_items if index in cached}


def _fallback_value(snap: GameSnapshot, index: int, cached: Mapping[int, Evidence]) -> float:
    """A plausible list price for an item whose true Fair Value is zero.

    An uncovered item still *has* a price -- the policy just does not pay it -- so the
    unbiased simulation needs a scale for it. The model's own median is the least
    arbitrary one available, and 60.0 (the settled median) covers the rest.
    """
    item = cached.get(index)
    if item is not None and item.price_median > 0:
        return item.price_median
    return 60.0


def unbiased_evidence(
    sigma_error: float = 0.45,
    coverage_confidence: float = 0.85,
    seed: int = 20240822,
) -> EvidenceSource:
    """Synthetic evidence from an estimator with the given precision and no bias.

    `t_hat = t * exp(N(0, sigma_error))`, so the *median* of `t_hat / t` is exactly 1 --
    that is what "unbiased" has to mean for a multiplicative quantity. The band is
    `t_hat * exp(+-1.645 * sigma_error)`, so `implied_sigma` recovers `sigma_error` and the
    Charge factor sees the true quality of the estimate rather than a made-up width.

    Coverage is a calibrated binary signal: `coverage_confidence` on the right side,
    `1 - coverage_confidence` on the wrong one.
    """

    def source(snap: GameSnapshot) -> dict[int, Evidence]:
        rng = random.Random((seed, snap.game_id).__hash__())
        cached = load_evidence(snap.game_id) or {}
        out: dict[int, Evidence] = {}
        for index in snap.line_items:
            covered = not snap.zero_fair_value(index)
            value = snap.fair_point(index) if covered else _fallback_value(snap, index, cached)
            value = max(value, 1.0)
            median = value * math.exp(rng.gauss(0.0, sigma_error))
            p = coverage_confidence if covered else 1.0 - coverage_confidence
            out[index] = Evidence(
                index=index,
                coverage_probability=p,
                price_low=median * math.exp(-1.645 * sigma_error),
                price_median=median,
                price_high=median * math.exp(1.645 * sigma_error),
            )
        return out

    return source


SOURCES: dict[str, EvidenceSource] = {
    "model": model_evidence,
    "unbiased": unbiased_evidence(),
}


# ------------------------------------------------------------------------------ scoring


def snapshots(games: Iterable[int] = GAMES) -> list[GameSnapshot]:
    return [snapshot(g) for g in games]


def net(snaps: Sequence[GameSnapshot], source: EvidenceSource, params: Params) -> float:
    """Total euros over the Games, replayed against the real Field."""
    return sum(replay(snap, submission(source(snap), params)).net for snap in snaps)


def per_game(
    snaps: Sequence[GameSnapshot], source: EvidenceSource, params: Params
) -> dict[int, float]:
    return {snap.game_id: replay(snap, submission(source(snap), params)).net for snap in snaps}


def averaged(
    snaps: Sequence[GameSnapshot], sources: Sequence[EvidenceSource], params: Params
) -> float:
    """Mean net over several draws of a stochastic evidence source."""
    return statistics.fmean(net(snaps, source, params) for source in sources)


def unbiased_replicas(
    sigma_error: float = 0.45, coverage_confidence: float = 0.85, replicas: int = 5
) -> list[EvidenceSource]:
    return [
        unbiased_evidence(sigma_error, coverage_confidence, seed=1000 + k) for k in range(replicas)
    ]


# ------------------------------------------------------------------------------- sweeps


def _table(rows: list[tuple[str, float]], title: str, baseline: float | None = None) -> None:
    print(f"\n{title}")
    print("-" * max(len(title), 46))
    best = max(value for _, value in rows)
    for label, value in rows:
        mark = " <-- best" if value == best else ""
        delta = f"  ({value - baseline:+11,.0f})" if baseline is not None else ""
        print(f"  {label:<26} {value:14,.0f}{delta}{mark}")


def sweep_charge_intercept(snaps, source, base: Params, values) -> list[tuple[str, float]]:
    return [(f"intercept {v:.2f}", net(snaps, source, replace(base, charge_intercept=v)))
            for v in values]


def sweep_charge_slope(snaps, source, base: Params, values) -> list[tuple[str, float]]:
    return [(f"slope {v:.2f}", net(snaps, source, replace(base, charge_slope=v)))
            for v in values]


def sweep_charge_cap(snaps, source, base: Params, values) -> list[tuple[str, float]]:
    return [(f"upper clamp {v:.2f}", net(snaps, source, replace(base, charge_high=v)))
            for v in values]


def sweep_charge_floor(snaps, source, base: Params, values) -> list[tuple[str, float]]:
    return [(f"lower clamp {v:.2f}", net(snaps, source, replace(base, charge_low=v)))
            for v in values]


def sweep_quantile(snaps, source, base: Params, values) -> list[tuple[str, float]]:
    return [(f"quantile {v:.2f}", net(snaps, source, replace(base, limit_quantile=v)))
            for v in values]


def sweep_ceiling(snaps, source, base: Params, values) -> list[tuple[str, float]]:
    return [(f"ceiling {v:.2f}", net(snaps, source, replace(base, limit_ceiling=v)))
            for v in values]


def sweep_coverage_floor(snaps, source, base: Params, values) -> list[tuple[str, float]]:
    return [(f"cov floor {v:.2f}", net(snaps, source, replace(base, coverage_floor=v)))
            for v in values]


AXES: dict[str, tuple[Callable, str, tuple[float, ...]]] = {
    "charge_intercept": (sweep_charge_intercept, "charge_intercept",
                         tuple(round(0.3 + 0.05 * k, 2) for k in range(0, 25))),
    "charge_slope": (sweep_charge_slope, "charge_slope",
                     tuple(round(0.0 + 0.05 * k, 2) for k in range(0, 17))),
    "charge_high": (sweep_charge_cap, "charge_high",
                    tuple(round(0.4 + 0.05 * k, 2) for k in range(0, 21))),
    "charge_low": (sweep_charge_floor, "charge_low",
                   tuple(round(0.05 + 0.05 * k, 2) for k in range(0, 14))),
    "limit_quantile": (sweep_quantile, "limit_quantile",
                       tuple(round(0.05 + 0.05 * k, 2) for k in range(0, 18))),
    "limit_ceiling": (sweep_ceiling, "limit_ceiling",
                      tuple(round(0.2 + 0.1 * k, 2) for k in range(0, 24))),
    "coverage_floor": (sweep_coverage_floor, "coverage_floor",
                       tuple(round(0.0 + 0.05 * k, 2) for k in range(0, 17))),
}


def flat(
    charge: float,
    limit: float,
    coverage_floor: float = COVERAGE_FLOOR,
    cap: bool = True,
) -> Params:
    """`a = charge * median`, `b = min(limit * median, a)` -- the two knobs, bare.

    The quantile is pushed to 0.999 so the ceiling is what binds; that turns the shaped
    rule back into the plain multiplier pair `replay_payoffs.sweep` uses, which is the
    only way to compare "the 1/3 quantile" against "1.0 x t_hat" on equal terms.
    """
    return Params(
        charge_intercept=charge,
        charge_slope=0.0,
        charge_low=0.0,
        charge_high=10.0,
        limit_quantile=0.999,
        limit_ceiling=limit,
        coverage_floor=coverage_floor,
        cap_limit_at_charge=cap,
    )


def flat_charge_curve(
    snaps, sources, limit_multiplier: float, values, cap: bool = True
) -> list[tuple[str, float]]:
    return [
        (f"a = {k:.2f} x median", averaged(snaps, sources, flat(k, limit_multiplier, cap=cap)))
        for k in values
    ]


def flat_limit_curve(
    snaps, sources, charge_multiplier: float, values, cap: bool = True
) -> list[tuple[str, float]]:
    return [
        (f"b = {m:.2f} x median", averaged(snaps, sources, flat(charge_multiplier, m, cap=cap)))
        for m in values
    ]


def joint_grid(snaps, sources, charges, limits, cap: bool = False) -> None:
    """Net over the full (Charge multiplier, Limit multiplier) plane, `b <= a` released."""
    header = "  a\\b  " + "".join(f"{m:>9.2f}" for m in limits)
    print("\njoint flat grid, net in thousands of euros" + ("" if cap else "  (b <= a released)"))
    print(header)
    best = (-math.inf, 0.0, 0.0)
    for k in charges:
        cells = []
        for m in limits:
            value = averaged(snaps, sources, flat(k, m, cap=cap))
            cells.append(value)
            if value > best[0]:
                best = (value, k, m)
        print(f"{k:>6.2f} " + "".join(f"{v / 1000:>9.1f}" for v in cells))
    print(f"best: a = {best[1]:.2f} x median, b = {best[2]:.2f} x median -> {best[0]:,.0f}")


def _peak(rows: list[tuple[float, float]], span: int = 1) -> tuple[float, float]:
    """Argmax of a *smoothed* curve.

    The raw surface is piecewise constant with large steps -- one 7,225 EUR Line Item
    crossing one opponent's Limit moves the total by thousands -- so the bare argmax lands
    on whichever spike a single item happens to make. Averaging each cell with its
    neighbours picks the middle of a plateau instead, which is the honest reading of
    "where is the optimum" and the one that survives a held-out Game.
    """
    best = (-math.inf, 0.0)
    for i, (x, _) in enumerate(rows):
        window = rows[max(0, i - span): i + span + 1]
        score = statistics.fmean(v for _, v in window)
        if score > best[0]:
            best = (score, x)
    return best[1], best[0]


def calibrate(
    snaps,
    sigmas: Sequence[float] = (0.25, 0.35, 0.45, 0.60, 0.75),
    coverage_confidence: float = 0.85,
    replicas: int = 5,
    grid: Sequence[float] | None = None,
    cap: bool = False,
) -> list[tuple[float, float, float, float]]:
    """Best flat Charge and Limit multiplier as a function of estimator error.

    This is the experiment the module's docstring claims to have run, done against the
    real payoff table instead of a simulation. For each `sigma` an unbiased estimator of
    that precision is synthesised, the two multipliers are optimised on a smoothed curve,
    and the pair is returned -- which is exactly the `intercept - slope * sigma` line the
    Charge factor is supposed to be.

    Returns `(sigma, best charge multiplier, best limit multiplier, net at that pair)`.
    """
    grid = grid or tuple(round(0.05 * k, 2) for k in range(2, 31))
    out = []
    for sigma in sigmas:
        sources = unbiased_replicas(sigma, coverage_confidence, replicas)
        charge_rows = [
            (k, averaged(snaps, sources, flat(k, 1.0, cap=cap))) for k in grid
        ]
        best_charge, _ = _peak(charge_rows)
        limit_rows = [
            (m, averaged(snaps, sources, flat(best_charge, m, cap=cap))) for m in grid
        ]
        best_limit, _ = _peak(limit_rows)
        value = averaged(snaps, sources, flat(best_charge, best_limit, cap=cap))
        out.append((sigma, best_charge, best_limit, value))
    return out


def fit_line(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Least-squares `y = intercept - slope * x`, the shape the Charge factor uses."""
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    gradient = sum((x - mx) * (y - my) for x, y in points) / denom if denom else 0.0
    return my - gradient * mx, -gradient


def coordinate_descent(
    snaps, source: EvidenceSource, base: Params, rounds: int = 3, quiet: bool = False
) -> Params:
    """Walk one axis at a time. The surface is flat enough that this converges in 2-3."""
    current = base
    for round_index in range(rounds):
        moved = False
        for name, (fn, field, values) in AXES.items():
            rows = fn(snaps, source, current, values)
            best_label, best_net = max(rows, key=lambda kv: kv[1])
            best_value = float(best_label.split()[-1])
            if abs(getattr(current, field) - best_value) > 1e-9:
                current = replace(current, **{field: best_value})
                moved = True
            if not quiet:
                print(f"  round {round_index} {field:<16} -> {best_value:.2f}  {best_net:14,.0f}")
        if not moved:
            break
    return current


# ------------------------------------------------------------------------ held-out check


def leave_one_out_axis(
    snaps, source: EvidenceSource, base: Params, field: str, values: Sequence[float]
) -> tuple[float, float, list[tuple[int, float, float]]]:
    """Tune one constant on 13 Games, score the 14th. The only honest check on 14 samples.

    Returns `(held-out total, fixed-constant total, per-Game rows)` where the fixed total
    is the same constant chosen once on all 14 -- the gap between them is the size of the
    overfit.
    """
    rows = []
    held = 0.0
    for snap in snaps:
        train = [s for s in snaps if s.game_id != snap.game_id]
        curve = [(v, net(train, source, replace(base, **{field: v}))) for v in values]
        chosen, _ = _peak(curve)
        score = net([snap], source, replace(base, **{field: chosen}))
        held += score
        rows.append((snap.game_id, chosen, score))
    whole, _ = _peak([(v, net(snaps, source, replace(base, **{field: v}))) for v in values])
    return held, net(snaps, source, replace(base, **{field: whole})), rows


def leave_one_out(snaps, source: EvidenceSource, base: Params) -> tuple[float, float]:
    """Tune on 13 Games, score the 14th. Returns (held-out total, in-sample total)."""
    held = 0.0
    inside = 0.0
    for snap in snaps:
        train = [s for s in snaps if s.game_id != snap.game_id]
        tuned = coordinate_descent(train, source, base, rounds=2, quiet=True)
        held += net([snap], source, tuned)
        inside += net([snap], source, coordinate_descent(snaps, source, base, rounds=2, quiet=True))
    return held, inside


# ---------------------------------------------------------------------------------- cli


def _resolve_source(name: str) -> EvidenceSource:
    if name in SOURCES:
        return SOURCES[name]
    raise SystemExit(f"unknown source {name}")


def main() -> None:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("axes", "flat", "grid", "calibrate", "descend", "loo", "all")
    )
    parser.add_argument("--source", default="model", choices=tuple(SOURCES))
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--sigma-error", type=float, default=0.45)
    parser.add_argument("--coverage-confidence", type=float, default=0.85)
    parser.add_argument("--replicas", type=int, default=5)
    parser.add_argument("--charge", type=float, default=0.70)
    parser.add_argument("--limit", type=float, default=0.50)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    start, _, end = args.games.partition("-")
    snaps = snapshots(range(int(start), int(end or start) + 1))
    if args.source == "unbiased":
        sources = unbiased_replicas(args.sigma_error, args.coverage_confidence, args.replicas)
    else:
        sources = [model_evidence]
    source = _resolve_source(args.source)
    baseline = averaged(snaps, sources, BASELINE)
    print(
        f"source={args.source}  games={args.games}  replicas={len(sources)}  "
        f"baseline net {baseline:,.2f}"
    )

    if args.command == "calibrate":
        for cap in (False, True):
            rows = calibrate(snaps, coverage_confidence=args.coverage_confidence,
                             replicas=args.replicas, cap=cap)
            print(f"\nunbiased estimator, b <= a {'enforced' if cap else 'released'}")
            print("  sigma   best a/median   best b/median          net")
            for sigma, k, m, value in rows:
                print(f"  {sigma:5.2f}   {k:13.2f}   {m:13.2f}   {value:12,.0f}")
            intercept, slope = fit_line([(s, k) for s, k, _, _ in rows])
            l_int, l_slope = fit_line([(s, m) for s, _, m, _ in rows])
            print(f"  Charge line: {intercept:.3f} - {slope:.3f} * sigma")
            print(f"  Limit  line: {l_int:.3f} - {l_slope:.3f} * sigma")
        return

    if args.command == "grid":
        axis = tuple(round(0.1 * k, 2) for k in range(2, 16))
        joint_grid(snaps, sources, axis, axis, cap=False)
        return

    if args.command == "flat":
        grid = tuple(round(0.1 * k, 2) for k in range(1, 21))
        _table(flat_charge_curve(snaps, sources, args.limit, grid),
               f"flat Charge multiplier (Limit fixed at {args.limit:.2f} x median)", baseline)
        _table(flat_limit_curve(snaps, sources, args.charge, grid),
               f"flat Limit multiplier (Charge fixed at {args.charge:.2f} x median)", baseline)
        best_k = max(flat_charge_curve(snaps, sources, args.limit, grid), key=lambda kv: kv[1])
        best_m = max(flat_limit_curve(snaps, sources, args.charge, grid), key=lambda kv: kv[1])
        print(f"\nbest flat pair: {best_k[0]} / {best_m[0]}")
        return

    if args.command in ("axes", "all"):
        for name, (fn, _field, values) in AXES.items():
            _table(fn(snaps, source, BASELINE, values), f"{name} (others at shipped values)",
                   baseline)

    if args.command in ("descend", "all"):
        print("\ncoordinate descent")
        tuned = coordinate_descent(snaps, source, BASELINE)
        print(f"\ntuned: {tuned.label()}")
        print(f"net {net(snaps, source, tuned):,.2f}  (baseline {baseline:,.2f})")
        if args.json:
            print(json.dumps(tuned.__dict__, indent=2))

    if args.command in ("loo", "all"):
        held, inside = leave_one_out(snaps, source, BASELINE)
        print(f"\nleave-one-out held-out total {held:,.2f}  in-sample total {inside:,.2f}")


if __name__ == "__main__":  # pragma: no cover
    main()
