"""Are the anchors in Strategy 2's prompt true? Measure them against the recovered t.

The prompt hands the model four price anchors. Three of them were written from intuition,
and the recovered Fair Values can check each one:

    "Small parts, fittings, screws and consumables are genuinely cheap: tens of EUR"
    "Equipment hire, drying, leak detection and disposal are typically 50-400 EUR"
    "Tradesman labour runs roughly 60-110 EUR per hour"
    "Appliances, electronics, restoration and structural work reach the low thousands"

`tail_replay.py --worst 25` is full of items where the second one is the proximate cause:
leak detection at t in [715, 824) priced 320, drying at [573, 703) priced 367, assessment
at t >= 620 priced 290. This bins every settled Line Item by keyword and prints the
distribution of the *true* Fair Value per bin, so an anchor can be rewritten from the data
rather than from a guess.

    pixi run python scripts/experiments/level_anchors.py --games 1-14    # the fitting window
    pixi run python scripts/experiments/level_anchors.py --games 15-24   # held out
    pixi run python scripts/experiments/level_anchors.py --fit 1-14 --games 15-24

## What it found: real bins, and a correction that still does not travel

The per-bin errors are sign-consistent across the two disjoint windows, which is more than
any `t_hat` bucket manages -- median `t_hat / t` on leak detection is 0.56 and 0.72, on
disposal and hire 3.35 and 2.46, on small parts 0.54 and 0.25, on surface work 1.77 and
1.73. That is a genuine conditional signal on something observable at submission time.

It still does not pay. Per-bin multipliers `(1 / median ratio) ** shrink`, fitted on one
window and scored on the other:

    fitted on   tested on   shrink   in-sample delta   held-out delta
    ----------  ---------- -------  ----------------  ---------------
    Games 1-14  Games 15-24   0.50           +17,548          -43,184
    Games 1-14  Games 15-24   0.75           +22,241          -80,471
    Games 15-24 Games 1-14    0.50           -24,784          +39,329

One direction gains what the other loses, the in-sample gain does not survive either
transfer, and the two folds disagree about `restoration` and `assessment` entirely. Ten bins
fitted on 100-odd items is a fit to the Games, not to the trades.

The bins themselves are still worth keeping: they are how `level_prompt_anchors.py` was
written, and they are the cheapest way to see which trade a bad Game leaked through.

Deliberately split: any anchor written from a window has to be checked on Games it did not
see, and 1-19 is where every other constant in the Strategy was already fitted.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from level_fit import load  # noqa: E402
from level_compat import parse_games  # noqa: E402

#: Keyword bins, in priority order -- the first that matches wins.
BINS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("leak detection", ("leak detect", "leckage", "moisture survey", "electro-acoustic", "leak local")),
    ("assessment", ("assessment", "inspection", "survey", "report", "documentation")),
    ("drying", ("drying", "dehumidif", "air mover", "trocknung", "borehole")),
    ("labour hours", ("hours", " hrs", "technician", "labour", "worker")),
    ("disposal/hire", ("disposal", "waste", "skip", "hire", "rental", "scaffold")),
    ("small parts", ("screw", "fitting", "consumable", "sealant", "silicone", "small part", "sundries")),
    ("surface work", ("skirting", "plaster", "paint", "wall surface", "ceiling", "floor", "tile", "screed")),
    ("appliance/electronics", ("television", "tv set", "speaker", "electronics", "appliance", "unit", "lighting", "led", "washing", "computer", "laptop")),
    ("restoration", ("restoration", "restore", "painting", "artwork", "furniture", "table", "cabinet")),
)


def bin_of(name: str) -> str:
    lowered = name.lower()
    for label, keywords in BINS:
        if any(keyword in lowered for keyword in keywords):
            return label
    return "other"


def grouped_ratios(loaded: list[tuple]) -> dict[str, list[tuple[float, float]]]:
    """`bin -> [(t, t_hat)]` over every Line Item with a positive recovered Fair Value."""
    grouped: dict[str, list[tuple[float, float]]] = {}
    for snap, case, model in loaded:
        names = {item.index: item.name for item in case.line_items}
        for index in snap.line_items:
            if index not in snap.fair_brackets:
                continue
            t = snap.fair_point(index)
            if t <= 0:
                continue
            evidence = model.get(index)
            grouped.setdefault(bin_of(names.get(index, "")), []).append(
                (t, evidence.price_median if evidence else 0.0)
            )
    return grouped


def factors(grouped: dict[str, list[tuple[float, float]]], *, minimum: int, shrink: float,
            clamp: float) -> dict[str, float]:
    """Per-bin multiplier `(1 / median ratio) ** shrink`, for bins with enough items."""
    out: dict[str, float] = {}
    for label, rows in grouped.items():
        ratios = [m / t for t, m in rows if m > 0]
        if len(ratios) < minimum:
            continue
        factor = (1.0 / statistics.median(ratios)) ** shrink
        out[label] = min(max(factor, 1.0 / clamp), clamp)
    return out


def score(loaded: list[tuple], multipliers: dict[str, float]) -> float:
    """Euros against the real Field with each bin's median scaled by its multiplier."""
    from level_fit import recalibrate
    from replay_payoffs import replay
    from level_compat import submission_of

    total = 0.0
    for snap, case, model in loaded:
        names = {item.index: item.name for item in case.line_items}
        adjusted = {
            index: recalibrate(ev, math.log(multipliers.get(bin_of(names.get(index, "")), 1.0)), 1.0)
            for index, ev in model.items()
        }
        total += replay(snap, submission_of(case, adjusted)).net
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--tag", default="model,nohint")
    parser.add_argument("--fit", default=None, help="fit bins on these Games, e.g. 1-14")
    parser.add_argument("--min-items", type=int, default=4)
    parser.add_argument("--clamp", type=float, default=2.0)
    args = parser.parse_args()

    loaded = load(parse_games(args.games), args.tag)
    grouped = grouped_ratios(loaded)

    if args.fit:
        fit_loaded = load(parse_games(args.fit), args.tag)
        fit_grouped = grouped_ratios(fit_loaded)
        baseline_fit = score(fit_loaded, {})
        baseline_test = score(loaded, {})
        print(
            f"fitted on {args.fit} ({len(fit_loaded)} Games), tested on {args.games} "
            f"({len(loaded)} Games)\n{'shrink':>7} {'in-sample':>13} {'delta':>11} "
            f"{'held-out':>13} {'delta':>11}   factors"
        )
        for shrink in (0.25, 0.5, 0.75, 1.0):
            multipliers = factors(
                fit_grouped, minimum=args.min_items, shrink=shrink, clamp=args.clamp
            )
            in_sample = score(fit_loaded, multipliers)
            held = score(loaded, multipliers)
            shown = " ".join(f"{k.split('/')[0][:9]}={v:.2f}" for k, v in sorted(multipliers.items()))
            print(
                f"{shrink:7.2f} {in_sample:13,.0f} {in_sample - baseline_fit:11,.0f} "
                f"{held:13,.0f} {held - baseline_test:11,.0f}   {shown}"
            )
        return

    print(
        f"\n{'bin':>22} {'n':>4} {'p25 t':>8} {'median t':>9} {'p75 t':>8} {'max t':>8} "
        f"{'median t_hat':>13} {'ratio':>7}"
    )
    for label in [name for name, _ in BINS] + ["other"]:
        rows = grouped.get(label, [])
        if not rows:
            continue
        values = sorted(t for t, _ in rows)
        hats = [m for _, m in rows if m > 0]
        quantile = lambda q: values[min(int(q * len(values)), len(values) - 1)]  # noqa: E731
        ratio = (
            statistics.median([m / t for t, m in rows if m > 0])
            if hats
            else float("nan")
        )
        print(
            f"{label:>22} {len(rows):4d} {quantile(0.25):8.0f} {statistics.median(values):9.0f} "
            f"{quantile(0.75):8.0f} {max(values):8.0f} "
            f"{statistics.median(hats) if hats else math.nan:13.0f} {ratio:7.2f}"
        )


if __name__ == "__main__":
    main()
