"""Before asking whether a smarter model helps: is the answer even *in* Price Memory?

The question, and why it comes first
------------------------------------
`scripts/experiments/case_anchor_backtest.py` establishes the target. Giving the Line Items that
Price Memory **misses** an estimator of quality sigma is worth, over all 99 Games and against our
real +224,840:

    sigma 0.20  ->  +490,419      sigma 0.60  ->   -15,587
    sigma 0.35  ->  +292,212      sigma 0.80  ->  -205,088
    sigma 0.458 ->  +118,864

positive on 4/4 folds down to 0.458 and negative from 0.60. So a replacement estimator has a hard
specification: **it must reach sigma < 0.60 on the misses, and about 0.458 to be worth having.**
The model channel is at ~1.0 there today, which is why it is the bottleneck.

The obvious next move is a smarter model -- retrieval-augmented: show it the settled Line Items
whose Fair Values we *know*, and ask which one the unpriced item resembles and by what multiple,
so the model supplies a ratio and the engine supplies the level. That is ADR 0001's division of
labour applied where it has never been applied.

**But that is worth building only if the store contains a usable analogue at all.** A model, however
good, can only choose from what it is shown. So this measures the *information*, not the reasoner:

    ORACLE-BEST     the single store entry closest to the truth, chosen with hindsight.
    ORACLE-TOP-K    the best entry within the top K by lexical overlap.
    RANDOM-K        **the control that matters** -- the best entry within K entries drawn at
                    random. Any oracle-over-a-candidate-set is partly measuring how many
                    numbers it got to choose from, not whether they were the right ones.
    LEXICAL-1       what plain nearest-neighbour matching picks on its own, with no oracle.
                    The arm `memory.core_key` already records as making sigma worse.

Reading it, and the trap
------------------------
**ORACLE-BEST is not evidence of anything, and the first version of this script reported it as
if it were.** It comes out at 0.013 -- every missed item has a store entry within 1.3 % of its
true price -- which sounds like "the information is all there". It is not: with ~325 entries
spread over orders of magnitude, *some* number lands near any target by chance. The controls
prove it, because they beat the lexical arm outright:

    ORACLE-BEST (all ~325)   0.013        RANDOM-8    0.508
    TOP-8 by lexical sim     0.358        RANDOM-30   0.206

RANDOM-30 beats TOP-8. So the oracle figures are dominated by candidate-set **size**, and the
only line carrying information is `TOP-K` against `RANDOM-K` at the same K: 0.358 against 0.508
says lexical similarity ranks better than chance, but only modestly.

What this does and does not license:

* it does **not** show a retrieval-augmented model would reach sigma 0.358 -- that arm picks with
  hindsight, and a model cannot;
* it does show the honest target. `LEXICAL-1` at **1.348** is what retrieval achieves unaided,
  worse than the model channel's ~1.0. The distance from 1.348 to the 0.358 available inside the
  same eight candidates is exactly the gap a model asked to **choose among shown anchors** would
  have to close, and 0.60 is where it starts paying.

Every arm is leave-one-Game-out: the store an item is matched against never contains its own Game.

Usage
-----
    PYTHONPATH=. python scripts/experiments/retrieval_ceiling.py
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))

from build_price_memory import build_entries, observations, team_names  # noqa: E402
from memory_first import build_predictions  # noqa: E402

from src.evidence.memory import PriceMemory, is_per_unit, normalise  # noqa: E402

TOP_K = 8

#: Random-candidate controls, at the same sizes as the ranked arms. Without these the oracle
#: numbers read as a discovery when they are mostly a statement about how dense the store is.
CONTROL_SIZES = (8, 30)


def tokens(name: str) -> set[str]:
    return set(normalise(name).split())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=TOP_K)
    args = parser.parse_args()

    games = list(range(1, 101))
    records = observations(games, names=team_names())
    predictions = build_predictions(games, "loo")

    by_game: dict[int, list[dict]] = defaultdict(list)
    for record in records:
        by_game[record["game"]].append(record)

    # The population that matters: bounded Fair Value, and Price Memory does NOT reach it.
    targets = []
    for record in records:
        if not record["bounded"] or not record["positive"] or record["t_point"] <= 0:
            continue
        if predictions.get(record["game"], {}).get(int(record["line_item_index"])):
            continue
        targets.append(record)
    print(f"\n{len(records)} settled Line Items; {len(targets)} are bounded AND missed by memory.")
    print(f"Those are the items a replacement estimator has to price.\n")

    arms: dict[str, list[float]] = defaultdict(list)
    rng = random.Random(20260823)
    contains_good = 0

    for target in targets:
        game = target["game"]
        training = [r for r in records if r["game"] != game]
        store = PriceMemory.from_dict({"entries": build_entries(training)})
        truth = target["t_point"]
        unit = target["unit"]
        quantity = target["quantity"] or 1.0
        target_tokens = tokens(target["display_name"])

        candidates = []
        for key, entry in store._entries.items():  # noqa: SLF001 - measurement, not production
            if not entry.values:
                continue
            median = statistics.median(entry.values)
            if median <= 0:
                continue
            # A per-unit entry holds a rate; scale it to this item's quantity.
            same_unit = getattr(entry, "unit", unit) == unit
            price = median * quantity if is_per_unit(unit) else median
            if price <= 0:
                continue
            candidates.append(
                {
                    "err": abs(math.log(price / truth)),
                    "same_unit": same_unit,
                    "sim": jaccard(target_tokens, tokens(entry.display_name)),
                }
            )
        if not candidates:
            continue

        arms["ORACLE-BEST (all)"].append(min(c["err"] for c in candidates))
        ranked = sorted(candidates, key=lambda c: -c["sim"])
        arms[f"TOP-{args.top_k} by lexical"].append(
            min(c["err"] for c in ranked[: args.top_k])
        )
        for size in CONTROL_SIZES:
            sample = rng.sample(candidates, min(size, len(candidates)))
            arms[f"RANDOM-{size} (control)"].append(min(c["err"] for c in sample))
        arms["LEXICAL-1 (no oracle)"].append(ranked[0]["err"])
        if min(c["err"] for c in candidates) < math.log(1.5):
            contains_good += 1

    print(f"  {'arm':<18}{'n':>6}{'RMSLE':>9}{'median |log|':>15}{'within 1.5x':>13}")
    print(f"  {'-'*18:<18}{'-'*6:>6}{'-'*9:>9}{'-'*15:>15}{'-'*13:>13}")
    order = (
        ["ORACLE-BEST (all)", f"TOP-{args.top_k} by lexical"]
        + [f"RANDOM-{s} (control)" for s in CONTROL_SIZES]
        + ["LEXICAL-1 (no oracle)"]
    )
    for name in order:
        values = arms.get(name, [])
        if not values:
            continue
        rmsle = math.sqrt(statistics.fmean(v * v for v in values))
        near = sum(1 for v in values if v < math.log(1.5)) / len(values)
        print(
            f"  {name:<18}{len(values):>6}{rmsle:>9.3f}{statistics.median(values):>15.3f}"
            f"{near:>13.1%}"
        )

    top = math.sqrt(statistics.fmean(v * v for v in arms[f"TOP-{args.top_k} by lexical"]))
    ctl = math.sqrt(statistics.fmean(v * v for v in arms[f"RANDOM-{args.top_k} (control)"]))
    print(f"\n  The bar to clear is sigma 0.60; 0.458 is memory's own accuracy.")
    print(
        f"  Lexical ranking against its own control at K={args.top_k}: "
        f"{top:.3f} vs {ctl:.3f} -- better than chance, modestly."
    )
    print(
        "  Ignore ORACLE-BEST: with a dense store some entry is near any target by chance,\n"
        "  and RANDOM-30 beating TOP-8 is the proof. See the docstring."
    )


if __name__ == "__main__":
    main()
