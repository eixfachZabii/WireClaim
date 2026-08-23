"""Price Memory's held-out log error on genuinely disjoint folds (no look-ahead), split by
match type (exact/core) and basis (per_unit/gross).

Unlike build_price_memory.py --evaluate (non-disjoint leave-one-out: for held-out Case g, the
training memory is built from *every other* Case, including ones that settled after g -- a
mild look-ahead a live system never has), this builds the memory from a train set of Games
once and scores it on a disjoint score set, matching docs/brainstorm/sebi/strats/review/
price-memory-coverage.md section 3's methodology so its numbers can be cross-checked.

Offline: cached var/transactions + local invoice PDFs. No LLM calls, no writes to
var/price_memory.json.

    PYTHONPATH=. python scripts/experiments/sigma_disjoint_folds.py
"""

from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_price_memory as bpm  # noqa: E402
from src.evidence.memory import PriceMemory, build_entries  # noqa: E402

ALL_GAMES = list(range(1, 37))
FOLDS = [
    ("odd -> even", [g for g in ALL_GAMES if g % 2 == 1], [g for g in ALL_GAMES if g % 2 == 0]),
    ("even -> odd", [g for g in ALL_GAMES if g % 2 == 0], [g for g in ALL_GAMES if g % 2 == 1]),
    ("1-20 -> 21-36", list(range(1, 21)), list(range(21, 37))),
]


def _stats(errors: list[float]) -> tuple[int, float, float, float]:
    if not errors:
        return 0, float("nan"), float("nan"), float("nan")
    n = len(errors)
    bias = statistics.mean(errors)
    sigma = statistics.pstdev(errors) if n > 1 else 0.0
    rmsle = math.sqrt(sum(e * e for e in errors) / n)
    return n, bias, sigma, rmsle


def main() -> None:
    print("Loading invoice observations for Games 1-36 (offline)...")
    records = bpm.observations(ALL_GAMES)
    print(f"  {len(records)} Line Items joined, "
          f"{sum(1 for r in records if r['positive'])} with proven positive t")

    for label, per_unit in (("per-unit rule ON (as shipped)", True), ("per-unit rule OFF", False)):
        print(f"\n{'=' * 90}\n{label}\n{'=' * 90}")
        for fold_name, train, score in FOLDS:
            training = [r for r in records if r["game"] in train]
            if not per_unit:
                training = [dict(r, value=r["t_point"], basis="gross") for r in training]
            memory = PriceMemory.from_dict({"entries": build_entries(training)})
            pooled: list[float] = []
            buckets: dict[tuple[str, str], list[float]] = {}
            n_scorable = 0
            for r in records:
                if r["game"] not in score or not r["positive"]:
                    continue
                n_scorable += 1
                query_unit = r["unit"] if per_unit else ""
                hit = memory.lookup(r["display_name"], unit=query_unit, quantity=r["quantity"])
                if hit is None or hit.median <= 0:
                    continue
                err = math.log(hit.median / r["t_point"])
                pooled.append(err)
                buckets.setdefault((hit.match, hit.basis), []).append(err)
            n, bias, sigma, rmsle = _stats(pooled)
            print(f"\n-- fold: {fold_name}  (train={len(train)}g, score={len(score)}g) --")
            print(f"   pooled: n={n}/{n_scorable} recall={n / max(n_scorable, 1):.0%} "
                  f"bias={bias:+.3f} sigma={sigma:.3f} RMSLE={rmsle:.3f}")
            for key in sorted(buckets, key=lambda k: -len(buckets[k])):
                errs = buckets[key]
                n_b, bias_b, sigma_b, rmsle_b = _stats(errs)
                print(f"     {str(key):<28} n={n_b:<4} bias={bias_b:+.3f} "
                      f"sigma={sigma_b:.3f} RMSLE={rmsle_b:.3f}")

    print("\nCross-check reference (price-memory-coverage.md section 3, per-unit ON, pooled):")
    print("  odd->even n=113 scorable, 34 hits, bias +0.163 sigma 0.533 RMSLE 0.558")
    print("  even->odd n=165 scorable, 61 hits, bias -0.148 sigma 0.680 RMSLE 0.696")
    print("  1-20->21-32 n=61 scorable, 32 hits, bias -0.136 sigma 0.593 RMSLE 0.609")
    print("  (that doc used score fold 21-32, not 21-36; scorable counts will differ here)")


if __name__ == "__main__":
    main()
