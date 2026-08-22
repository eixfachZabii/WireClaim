"""`combine()` pins the band width to a constant on 80% of priced Line Items. Unpin it.

## The defect

`blend.combine()` merges the model's reading with a Price Memory anchor by inverse-variance
weighting **on the two fixed priors**, and then rebuilds the band from the posterior width:

    weight_model  = 1 / MODEL_SIGMA_PRIOR**2      # 1 / 0.60**2
    weight_memory = 1 / MEMORY_SIGMA**2           # 1 / 0.43**2
    low, median, high = _band_from(median, sqrt(1 / (weight_model + weight_memory)))

`sqrt(1 / (1/0.6**2 + 1/0.43**2))` is **0.3495 for every item that has ever existed**. It is a
function of two constants; nothing about this Line Item enters it. The model's own asserted
band and the memory's observed spread are both computed and then discarded.

Measured over the 44-Case retest corpus: **277 of 348 scorable priced items (80%) carry
exactly sigma = 0.34951**, and the decision log for the live Game 41 shows the same value to
five decimals. Price Memory now reaches 86% of items, so the share is rising, not falling.

## Why that matters more than it looks

`src/domain/pricing/engine.py` reports that the band width carries no signal -- "split the
items by band width and the narrow third scores RMSLE 0.847 against the wide third's 0.733,
i.e. slightly *backwards*" -- and concludes `CHARGE_SLOPE` "multiplies a number that does not
measure what it claims to". That measurement pooled the 80% of items whose width is a
constant. A constant contributes pure noise to an ordering, and four fifths of the sample
being constant is enough to destroy one.

Restricted to the items whose width is NOT pinned, the width orders the error cleanly and
monotonically:

    narrow  sigma 0.202-0.261   RMSLE 0.183
    middle  sigma 0.261-0.401   RMSLE 0.684
    wide    sigma 0.402-0.920   RMSLE 1.044

That is a 5.7x spread in the correct direction, and it is precisely the falsifier
`engine.py`'s own docstring names: "a band whose width actually orders the error ... then
`CHARGE_SLOPE` is measuring something and its sign can be trusted".

## The candidates

Both keep `combine`'s job (merge two channels) and change only where the WIDTH comes from.
`width_only` additionally holds the median at exactly what ships today, so the euro delta is
attributable to the band alone rather than to a level change smuggled in beside it.

    shipped      median: prior-weighted   width: sqrt(1/(1/0.6^2 + 1/0.43^2)) == 0.3495 always
    width_only   median: UNCHANGED        width: from the model's asserted band + channel
                                                 disagreement, in quadrature
    full         median: weighted by the model's ASSERTED width instead of the prior
                 width:  same as width_only

Disagreement enters the way `blend()` already treats between-draw spread -- in quadrature --
so a Line Item the two channels read differently gets a wider band and a lower Charge and
Limit, which is what a posterior is supposed to do.

Offline: reads the cached retest draws and the local Price Memory. No LLM calls.

    PYTHONPATH=. pixi run python scripts/experiments/band_width_fix.py
"""

from __future__ import annotations

import argparse
import asyncio
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))

from src.domain.pricing.engine import Evidence, implied_sigma, price_item  # noqa: E402
from src.services.strategies.strategy2.blend import sigma_of  # noqa: E402
from src.services.strategies.strategy2.channels import local_evidence  # noqa: E402
from src.services.strategies.strategy2.constants import (  # noqa: E402
    BAND_Z,
    MEMORY_SIGMA,
    MODEL_SIGMA_PRIOR,
)
from src.data.case_loader import read_case  # noqa: E402

from replay_payoffs import replay, snapshot  # noqa: E402
from retest_score import CASES, INF, ensemble  # noqa: E402

NOISE_FLOOR_18 = 26622.0
PINNED_SIGMA = 1.0 / math.sqrt(1.0 / MODEL_SIGMA_PRIOR ** 2 + 1.0 / MEMORY_SIGMA ** 2)


def _band(median: float, sigma: float) -> tuple[float, float, float]:
    return median * math.exp(-BAND_Z * sigma), median, median * math.exp(BAND_Z * sigma)


def combine_variant(model: Evidence | None, memory: Evidence | None, variant: str) -> Evidence | None:
    """`blend.combine`, with only the width (and optionally the weighting) changed.

    Every early-return branch of the shipped function is reproduced verbatim, because those
    branches encode measured decisions (H7's zero-band rescue, Channel A's proven-worthless
    override) that this experiment must not quietly revert.
    """
    if model is None:
        return memory
    if memory is None or memory.price_median <= 0:
        return model
    if model.price_median <= 0:
        return Evidence(
            index=model.index,
            coverage_probability=model.coverage_probability,
            price_low=memory.price_low,
            price_median=memory.price_median,
            price_high=memory.price_high,
        )
    if memory.coverage_probability == 0.0:
        return Evidence(
            index=memory.index,
            coverage_probability=0.0,
            price_low=model.price_low or memory.price_low,
            price_median=model.price_median or memory.price_median,
            price_high=model.price_high or memory.price_high,
        )

    if variant == "shipped":
        w_model = 1.0 / MODEL_SIGMA_PRIOR ** 2
        w_memory = 1.0 / MEMORY_SIGMA ** 2
        total = w_model + w_memory
        median = math.exp(
            (w_model * math.log(model.price_median) + w_memory * math.log(memory.price_median)) / total
        )
        low, median, high = _band(median, math.sqrt(1.0 / total))
        return Evidence(model.index, model.coverage_probability, low, median, high)

    asserted = sigma_of(model)  # the model's own width, or MODEL_SIGMA_PRIOR when unusable
    disagreement = abs(math.log(model.price_median / memory.price_median)) / 2.0

    if variant == "width_only":
        # Median exactly as shipped, so the delta is attributable to the band alone.
        w_model = 1.0 / MODEL_SIGMA_PRIOR ** 2
        w_memory = 1.0 / MEMORY_SIGMA ** 2
    elif variant == "full":
        w_model = 1.0 / max(asserted, 1e-6) ** 2
        w_memory = 1.0 / MEMORY_SIGMA ** 2
    else:
        raise ValueError(variant)

    total = w_model + w_memory
    median = math.exp(
        (w_model * math.log(model.price_median) + w_memory * math.log(memory.price_median)) / total
    )
    posterior = math.sqrt(1.0 / total)
    sigma = math.sqrt(posterior ** 2 + disagreement ** 2)
    low, median, high = _band(median, sigma)
    return Evidence(model.index, model.coverage_probability, low, median, high)


def build(games: list[int], model_tag: str, variants: tuple[str, ...]):
    rows = {v: [] for v in variants}
    subs = {v: {} for v in variants}
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

        for variant in variants:
            submission = {}
            for index in snap.line_items:
                evidence = combine_variant(model.get(index), mem.get(index), variant)
                if evidence is None:
                    continue
                unc = uncovered.get(index, False)
                price = price_item(
                    evidence,
                    confirmed_uncovered=unc,
                    memory_backed=mem.get(index) is not None and not unc,
                )
                submission[index] = (price.charge, price.limit)
                lo, hi = snap.fair_brackets.get(index, (0.0, INF))
                filled = evidence.with_defaults()
                if lo > 0 and filled.price_median > 0:
                    t = lo if hi == INF else (lo + hi) / 2.0
                    rows[variant].append((
                        implied_sigma(filled.price_low, filled.price_median, filled.price_high),
                        abs(math.log(filled.price_median / t)),
                        t,
                    ))
            if submission:
                subs[variant][game_id] = (snap, submission)
    return rows, subs


def terciles(rows: list, label: str) -> None:
    if len(rows) < 9:
        return
    ordered = sorted(rows, key=lambda r: r[0])
    k = len(ordered) // 3
    parts = (("narrow", ordered[:k]), ("middle", ordered[k:2 * k]), ("wide", ordered[2 * k:]))
    out = []
    for name, chunk in parts:
        out.append(f"{name} sigma {chunk[0][0]:.3f}-{chunk[-1][0]:.3f} RMSLE "
                   f"{math.sqrt(st.fmean(e * e for _, e, _ in chunk)):.3f}")
    pinned = sum(1 for s, _, _ in ordered if abs(s - PINNED_SIGMA) < 1e-6)
    print(f"  {label:12s} pinned={pinned:3d}/{len(ordered):3d} ({pinned / len(ordered):3.0%})  " + " | ".join(out))


def fold(subs, variants, label: str, games: list[int]) -> None:
    common = sorted(set.intersection(*(set(subs[v]) for v in variants)) & set(games))
    if not common:
        return
    totals = {v: sum(replay(*subs[v][g]).net for g in common) for v in variants}
    nf = NOISE_FLOOR_18 * math.sqrt(len(common) / 18.0)
    base = totals["shipped"]
    deltas = "  ".join(
        f"{v} {totals[v] - base:>+10,.0f}{'*' if abs(totals[v] - base) > nf else ' '}"
        for v in variants if v != "shipped"
    )
    print(f"  {label:16s} n={len(common):2d}  shipped {base:>11,.0f}   {deltas}   floor +/-{nf:,.0f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="mini", choices=("mini", "terra"))
    args = parser.parse_args()

    games = sorted(
        int(p.name.split("_")[1])
        for p in CASES.iterdir()
        if p.name.startswith("case_") and p.name.split("_")[1].isdigit() and int(p.name.split("_")[1]) > 0
    )
    variants = ("shipped", "width_only", "full")
    rows, subs = build(games, args.model, variants)

    print(f"model={args.model}, {len(games)} Cases, pinned sigma = {PINNED_SIGMA:.5f}\n")
    print("Does the band width order the error? (terciles by asserted width, all priced items)")
    for v in variants:
        terciles(rows[v], v)
    print("\n  same, expensive tail t >= 1000 only:")
    for v in variants:
        terciles([r for r in rows[v] if r[2] >= 1000], v)

    print("\nEuros vs the real Field ('*' = outside that fold's noise floor)")
    fold(subs, variants, "all Games", games)
    fold(subs, variants, "odd", [g for g in games if g % 2 == 1])
    fold(subs, variants, "even", [g for g in games if g % 2 == 0])
    fold(subs, variants, "early (1-20)", [g for g in games if g <= 20])
    fold(subs, variants, "late (21+)", [g for g in games if g > 20])
    fold(subs, variants, "recent (34+)", [g for g in games if g >= 34])


if __name__ == "__main__":
    main()
