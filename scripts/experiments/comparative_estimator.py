"""Does asking the model to COMPARE beat asking it to PRICE? Live Gemini, on the items that matter.

The question
------------
H28 gives the specification: on the Line Items Price Memory misses, an estimator must reach
**sigma < 0.60** to be worth anything and about **0.458** to be worth +118,864 weighted. The old
model channel sits near **1.0** there, and unaided lexical retrieval is worse still at **1.348**.

`src/evidence/comparative.py` proposes changing the question rather than the model: retrieve eight
settled Line Items whose Fair Values are known exactly, and ask which one the unpriced item
resembles and by what multiple. The model returns an anchor and a ratio; the engine multiplies.

The control is the point
------------------------
Both arms run on **the same model, the same items, the same run**:

    DIRECT     "what is this line item worth in EUR?"   -- the old architecture
    ANCHORED   "which of these eight, and what ratio?"  -- the new one

Without DIRECT, any improvement could simply be Gemini being better than the retired
`gpt-5.6-terra`, and the architecture would get credit it had not earned. With it, the difference
between the two arms is attributable to the framing and nothing else.

Honest scope
------------
* Only the **105 bounded** memory-miss Line Items can be scored, because only they have a Fair
  Value tight enough to compute a residual against. That sample is censored (a bounded bracket
  means somebody rightfully rejected) so every sigma here is optimistic, as everywhere else.
* The anchor store is rebuilt **leave-one-Game-out** for every item, so no item is ever offered
  a reference drawn from its own Game.
* The model never sees the Fair Value of the item it is pricing, nor the policy, nor the
  settled outcome.

Usage
-----
    PYTHONPATH=. pixi run python scripts/experiments/comparative_estimator.py --limit 20
    PYTHONPATH=. pixi run python scripts/experiments/comparative_estimator.py --flash
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))

from build_price_memory import build_entries, observations, team_names  # noqa: E402
from memory_first import build_predictions  # noqa: E402

from src.api import adk  # noqa: E402
from src.evidence import comparative  # noqa: E402
from src.evidence.memory import PriceMemory, is_per_unit, normalise  # noqa: E402

TOP_K = 8
OUT = ROOT / "var" / "comparative_estimator.json"


def tokens(name: str) -> set[str]:
    return set(normalise(name).split())


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def shortlist(target, records, k: int) -> list[comparative.Anchor]:
    """The k most lexically similar settled Line Items from *other* Games.

    Lexical similarity only shortlists; `retrieval_ceiling.py` shows its top-1 pick is 1.348 and
    therefore useless as a decision. The model does the deciding.
    """
    store = PriceMemory.from_dict(
        {"entries": build_entries([r for r in records if r["game"] != target["game"]])}
    )
    want = tokens(target["display_name"])
    quantity = target["quantity"] or 1.0
    scored = []
    for entry in store._entries.values():  # noqa: SLF001 - measurement path
        if not entry.values:
            continue
        median = statistics.median(entry.values)
        if median <= 0:
            continue
        price = median * quantity if is_per_unit(target["unit"]) else median
        if price <= 0:
            continue
        scored.append((jaccard(want, tokens(entry.display_name)), entry.display_name, price))
    scored.sort(key=lambda s: -s[0])
    return [
        comparative.Anchor(label=name, price=price, unit=target["unit"], quantity=quantity)
        for _, name, price in scored[:k]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="score only the first N items")
    parser.add_argument("--flash", action="store_true", help="use the cheaper/faster model")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument(
        "--all-misses",
        action="store_true",
        help="price every memory miss, not only the bounded ones. Unbounded items cannot be "
             "SCORED (no tight Fair Value) but they can be REPLAYED, which is what decides in euros.",
    )
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    if not adk.available():
        raise SystemExit("no GOOGLE_API_KEY / google-adk -- cannot run the live arms")
    print(f"\nmodel: {adk.model_name(flash=args.flash)}")

    games = list(range(1, 101))
    records = observations(games, names=team_names())
    predictions = build_predictions(games, "loo")
    def is_miss(r):
        return not predictions.get(r["game"], {}).get(int(r["line_item_index"]))

    if args.all_misses:
        targets = [r for r in records if is_miss(r)]
    else:
        targets = [
            r for r in records
            if r["bounded"] and r["positive"] and r["t_point"] > 0 and is_miss(r)
        ]
    if args.limit:
        targets = targets[: args.limit]
    scorable = sum(1 for r in targets if r["bounded"] and r["positive"] and r["t_point"] > 0)
    print(f"{len(targets)} Line Items that Price Memory misses "
          f"({scorable} of them scorable against a bounded Fair Value).\n")

    anchored_agent = adk.build_agent(
        "comparer", comparative.INSTRUCTION, comparative.Comparison, flash=args.flash
    )
    direct_agent = adk.build_agent(
        "pricer", comparative.DIRECT_INSTRUCTION, comparative.DirectPrice, flash=args.flash
    )

    lock = threading.Lock()
    rows: list[dict] = []
    failures = {"anchored": 0, "direct": 0}

    def work(target) -> None:
        anchors = shortlist(target, records, args.top_k)
        name = target["display_name"]
        quantity = target["quantity"] or 1.0
        unit = target["unit"] or ""
        truth = target["t_point"]
        row = {
            "game": target["game"],
            "index": int(target["line_item_index"]),
            "name": name,
            "truth": truth,
            # Only these can be scored. `bounded` alone is not enough -- an item with t_lo = 0
            # has a finite upper bracket but no usable residual, and scoring it produced an
            # RMSLE of 2.4 and a ZeroDivisionError before this flag existed.
            "scorable": bool(target["bounded"] and target["positive"] and truth > 0),
        }

        if anchors:
            try:
                reply = adk.run_structured(
                    anchored_agent,
                    comparative.render_prompt(name, quantity, unit, anchors),
                    comparative.Comparison,
                )
                value = comparative.estimate(reply, anchors)
                if value:
                    row["anchored"] = value
                    row["anchor_used"] = anchors[reply.anchor - 1].label
                    row["ratio"] = reply.ratio
                    row["confidence"] = reply.confidence
            except Exception as exc:  # noqa: BLE001 - a failed call is data, not a crash
                with lock:
                    failures["anchored"] += 1
                row["anchored_error"] = f"{type(exc).__name__}"

        try:
            reply = adk.run_structured(
                direct_agent,
                comparative.render_direct_prompt(name, quantity, unit),
                comparative.DirectPrice,
            )
            if reply.price > 0:
                row["direct"] = float(reply.price)
        except Exception as exc:  # noqa: BLE001
            with lock:
                failures["direct"] += 1
            row["direct_error"] = f"{type(exc).__name__}"

        with lock:
            rows.append(row)
            done = len(rows)
            if done % 10 == 0 or done == len(targets):
                print(f"  {done}/{len(targets)} priced")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, targets))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=1) + "\n")
    print(f"\nwrote {args.out} ({len(rows)} rows) -- saved before analysis, on purpose")

    def score(key: str) -> tuple[int, float, float, float]:
        errs = [
            math.log(r[key] / r["truth"])
            for r in rows
            if r.get(key) and r[key] > 0 and r.get("scorable")
        ]
        if not errs:
            return 0, float("nan"), float("nan"), float("nan")
        rmsle = math.sqrt(statistics.fmean(e * e for e in errs))
        return len(errs), rmsle, statistics.median(errs), statistics.median(abs(e) for e in errs)

    print(f"\n{'=' * 74}\nRESULT -- the bar is sigma 0.60; 0.458 is Price Memory's own accuracy\n{'=' * 74}")
    print(f"  {'arm':<28}{'n':>5}{'RMSLE':>9}{'median log':>13}{'median |log|':>15}")
    print(f"  {'-'*28:<28}{'-'*5:>5}{'-'*9:>9}{'-'*13:>13}{'-'*15:>15}")
    for key, label in (("direct", "DIRECT (old framing)"), ("anchored", "ANCHORED (new framing)")):
        n, rmsle, bias, mae = score(key)
        print(f"  {label:<28}{n:>5}{rmsle:>9.3f}{bias:>13.3f}{mae:>15.3f}")
    print(f"\n  reference: old model channel ~1.0   unaided lexical top-1  1.348")
    print(f"  failed calls: anchored {failures['anchored']}, direct {failures['direct']}")

    both = [r for r in rows if r.get("anchored") and r.get("direct") and r.get("scorable")]
    if both:
        wins = sum(
            1
            for r in both
            if abs(math.log(r["anchored"] / r["truth"])) < abs(math.log(r["direct"] / r["truth"]))
        )
        print(f"  head to head on {len(both)} items: ANCHORED closer on {wins} ({wins/len(both):.0%})")


if __name__ == "__main__":
    main()
