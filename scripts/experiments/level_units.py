"""Does the invoice unit predict the level error, and does conditioning on it pay?

`level_fit.py` shows a log-linear recalibration of `t_hat` is not worth money -- the euro
argmax over the whole `(pivot, c1)` family is the identity on one ensemble draw and moves by
more than its own best gain on another. So the level error is not a function of `t_hat`
alone. This asks whether it is a function of something else we can observe at submission
time: the **invoice unit** and the **quantity**, both of which the parser keeps ("Remove
skirting boards (12 m)").

    pixi run python scripts/experiments/level_units.py --games 1-24 --table
    pixi run python scripts/experiments/level_units.py --games 1-24 --sweep
    pixi run python scripts/experiments/level_units.py --games 1-24 --decompose 0.64 0.90

## What it found

The unit is a weak predictor of the level error. Games 1-24, median `t_hat / t`: 1.40 on
`pcs` (n=136), 1.26 on `hrs` (23), 1.20 on `m2` (14), 1.12 on flat rates (38), 1.59 on the
unlabelled rest (17) -- and 0.72 on `m`, the one bin pointing the other way, with seven items
in it. Every unit is over-priced except that one, which is a level statement, not a unit
statement, and `level_fit.py` has already shown the level is at its euro optimum.

`--decompose` is the durable finding here. For the euro-weighted fit
`exp(0.889) * t_hat**0.849`, over Games 1-24:

    applied to nothing (shipped)    127,292
    applied to the Charge only       69,803
    applied to the Limit only      *130,068*
    applied to both                  72,579

The two sides of one correction pull in opposite directions: the Charge wants the level left
exactly where it is (-57,489 if it moves), the Limit mildly wants it shrunk (+2,776, inside
the noise). An evidence-layer correction cannot separate them, because both numbers are
derived from the same median. So any future level work belongs on the Limit side of
`src/pricing/engine.py` -- and it is worth about 2,800 euros, not the six figures the by-true-`t`
table seems to promise.

`--decompose` answers a separate question that any evidence-layer correction has to face:
moving the median moves the Charge *and* the Limit. It prices the Charge from one Evidence
and the Limit from another, so the income and cost sides of a correction can be read apart.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from level_fit import load, recalibrate  # noqa: E402
from replay_payoffs import replay  # noqa: E402
from level_compat import build_proposal, parse_games, unit_of as raw_unit_of  # noqa: E402

from src.pricing.engine import Evidence, price_item  # noqa: E402

UNITS = ("pcs", "hrs", "m2", "m", "flat rate", "other")


def unit_of(name: str) -> str:
    unit = (raw_unit_of(name) or "other").lower()
    if unit in ("hr", "hrs"):
        return "hrs"
    if unit in ("m²", "m2"):
        return "m2"
    return unit if unit in UNITS else "other"


def rows_with_unit(loaded: list[tuple]) -> list[tuple[float, float, str, float]]:
    """`(t, t_hat, unit, quantity)` for every Line Item with a positive Fair Value."""
    out = []
    for snap, case, model in loaded:
        names = {item.index: item.name for item in case.line_items}
        quantities = {item.index: item.quantity for item in case.line_items}
        for index, ev in model.items():
            if index not in snap.fair_brackets or ev.price_median <= 0:
                continue
            t = snap.fair_point(index)
            if t > 0:
                out.append((t, ev.price_median, unit_of(names.get(index, "")), quantities.get(index, 1.0)))
    return out


def table(rows: list) -> None:
    print(f"\n{'unit':>10} {'n':>4} {'median t_hat/t':>15} {'euro-wtd ratio':>15} {'under':>7}")
    for unit in UNITS:
        chosen = [(t, m) for t, m, u, _ in rows if u == unit]
        if not chosen:
            continue
        ratios = [m / t for t, m in chosen]
        weighted = sum(m for _, m in chosen) / sum(t for t, _ in chosen)
        under = sum(1 for r in ratios if r < 1.0) / len(ratios)
        print(
            f"{unit:>10} {len(chosen):4d} {statistics.median(ratios):15.2f} "
            f"{weighted:15.2f} {under:6.0%}"
        )


def scale_by_unit(loaded: list[tuple], factors: dict[str, float]) -> float:
    total = 0.0
    for snap, case, model in loaded:
        names = {item.index: item.name for item in case.line_items}
        adjusted = {}
        for index, ev in model.items():
            factor = factors.get(unit_of(names.get(index, "")), 1.0)
            adjusted[index] = recalibrate(ev, math.log(factor), 1.0)
        proposal = build_proposal(case, adjusted, {})
        submission = (
            {p.index: (p.charge_price, p.acceptance_limit) for p in proposal.prices}
            if proposal
            else {}
        )
        total += replay(snap, submission).net
    return total


def decompose(loaded: list[tuple], c0: float, c1: float) -> None:
    """Net when the map moves only the Charge, only the Limit, or both."""
    print(f"\nmap exp({c0:.3f}) * t_hat^{c1:.2f} applied to ...")
    for label, on_charge, on_limit in (
        ("nothing (shipped)", False, False),
        ("the Charge only", True, False),
        ("the Limit only", False, True),
        ("both", True, True),
    ):
        total = 0.0
        for snap, case, model in loaded:
            plain = {i: price_item(ev.with_defaults()) for i, ev in model.items()}
            moved = {
                i: price_item(recalibrate(ev, c0, c1).with_defaults()) for i, ev in model.items()
            }
            submission = {
                i: (
                    (moved if on_charge else plain)[i].charge,
                    (moved if on_limit else plain)[i].limit,
                )
                for i in model
            }
            total += replay(snap, submission).net
        print(f"  {label:>20} {total:14,.0f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-15,17-20")
    parser.add_argument("--tag", default="model,nohint")
    parser.add_argument("--table", action="store_true")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--decompose", nargs=2, type=float, metavar=("C0", "C1"), default=None)
    args = parser.parse_args()

    loaded = load(parse_games(args.games), args.tag)
    rows = rows_with_unit(loaded)
    print(f"{len(loaded)} Games, {len(rows)} Line Items with t > 0, tag {args.tag}")

    if args.table:
        table(rows)

    if args.decompose:
        decompose(loaded, *args.decompose)

    if args.sweep:
        baseline = scale_by_unit(loaded, {})
        print(f"\nbaseline {baseline:,.0f}")
        print(f"{'unit':>10} {'factor':>7} {'net':>14} {'delta':>12}")
        for unit in UNITS:
            for factor in (0.5, 0.7, 0.85, 1.25, 1.5, 2.0):
                net = scale_by_unit(loaded, {unit: factor})
                print(f"{unit:>10} {factor:7.2f} {net:14,.0f} {net - baseline:12,.0f}")


if __name__ == "__main__":
    main()
