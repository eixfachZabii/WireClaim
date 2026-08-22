"""Does a trade-level (item -> trade -> global) backoff extend Price Memory past its 22-58%
recall, on the population where it currently has nothing to say at all?

Price Memory today is two tiers: exact wording, then wording-minus-qualifier ("core").
Both are *item*-level -- they require having seen this near-exact wording settle before.
Four items in five, Price Memory is silent and the item is priced by the model alone
(RMSLE ~0.77-1.30 depending on measurement). Fuzzy/Jaccard matching was tried at that same
item level and made things worse (0.43 -> 0.72 at Jaccard 0.7) because it matches on
*surface* text similarity, which conflates unrelated items that happen to share words.

This tries a different axis: not looser text matching, but a coarser semantic level. Every
settled Line Item can be binned into one of nine trades (leak detection, drying, assessment,
labour hours, disposal/hire, small parts, surface work, appliance/electronics, restoration --
`level_anchors.BINS`, already measured sign-consistent across two disjoint Game windows for
the *level* correction, which failed to travel; this asks whether the same partition works
better as a WIDTH/fallback signal than as a multiplicative correction).

Purely offline: cached var/transactions + local invoices.pdf via pdftotext. No LLM calls, no
writes to var/price_memory.json, no network calls (games list comes from what is already
cached locally).

    PYTHONPATH=. pixi run python scripts/experiments/hierarchical_memory.py
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
from level_anchors import bin_of  # noqa: E402
from src.domain.pricing.engine import Evidence  # noqa: E402
from src.domain.pricing.memory import PriceMemory, build_entries  # noqa: E402
from src.services.strategies.strategy2.blend import blend  # noqa: E402

CASES_DIR = ROOT / "[PUBLIC] EHL Cases" / "cases"
TXN_CACHE = ROOT / "var" / "transactions"
EVIDENCE = ROOT / "var" / "evidence"
RETEST_CACHE = ROOT / "var" / "experiments" / "model_bakeoff_retest"


def settled_games() -> list[int]:
    """Games with both an extracted Case and a cached settled Transaction pull. Offline."""
    extracted = {
        int(p.name.split("_")[1])
        for p in CASES_DIR.iterdir()
        if p.name.startswith("case_") and p.name.split("_")[1].isdigit()
    }
    cached = {int(p.name.split("_")[0][1:]) for p in TXN_CACHE.glob("g*_*.json")}
    games = sorted((extracted & cached) - {0})
    return games


def _stats(errors: list[float]) -> tuple[int, float, float, float]:
    if not errors:
        return 0, float("nan"), float("nan"), float("nan")
    n = len(errors)
    bias = statistics.mean(errors)
    sigma = statistics.pstdev(errors) if n > 1 else 0.0
    rmsle = math.sqrt(sum(e * e for e in errors) / n)
    return n, bias, sigma, rmsle


def trade_medians(training: list[dict]) -> dict[tuple[str, str], list[float]]:
    """(trade, basis) -> the raw 'value' observations (per-unit rate or gross total)."""
    out: dict[tuple[str, str], list[float]] = {}
    for r in training:
        if not r["positive"]:
            continue
        trade = bin_of(r["display_name"])
        if trade is None:
            continue
        out.setdefault((trade, r["basis"]), []).append(r["value"])
    return out


def model_evidence_cache() -> dict[tuple[int, int], float]:
    """(game, index) -> cached model price_median, from var/evidence/case_NN_model.json.

    STALE: dumped 19:29-19:49 today, before both prompt fixes (21:53 anchors, 23:38
    distribution hint) shipped. Kept only as a labelled "old prompt" reference point --
    see `retest_model_cache()` for the current-prompt comparison.
    """
    import json

    out: dict[tuple[int, int], float] = {}
    for path in EVIDENCE.glob("case_*_model.json"):
        game_id = int(path.name.split("_")[1])
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for index, item in payload.items():
            median = item.get("price_median", 0.0)
            if median and median > 0:
                out[(game_id, int(index))] = median
    return out


def retest_model_cache(model_tag: str = "mini") -> dict[tuple[int, int], float]:
    """(game, index) -> blended two-draw median under the CURRENT (corrected) prompt.

    Reads `var/experiments/model_bakeoff_retest/case_NN_<model_tag>_{anchor,unanchor}.json`
    -- drawn live tonight through the shipped `ENSEMBLE_PROMPTS`, cached so nothing here
    re-bills. Coverage grows as that draw (running independently) fills in; whatever is
    cached at the time this script runs is what gets scored.
    """
    import json

    def _load(game_id: int, prompt_tag: str) -> dict[int, Evidence]:
        path = RETEST_CACHE / f"case_{game_id:02d}_{model_tag}_{prompt_tag}.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError):
            return {}
        items = payload.get("items") or {}
        return {
            int(i): Evidence(
                index=int(i),
                coverage_probability=v.get("coverage_probability", 0.9),
                price_low=v.get("price_low", 0.0),
                price_median=v.get("price_median", 0.0),
                price_high=v.get("price_high", 0.0),
            )
            for i, v in items.items()
        }

    out: dict[tuple[int, int], float] = {}
    games_seen = {
        int(p.name.split("_")[1]) for p in RETEST_CACHE.glob(f"case_*_{model_tag}_anchor.json")
    } | {
        int(p.name.split("_")[1]) for p in RETEST_CACHE.glob(f"case_*_{model_tag}_unanchor.json")
    }
    for game_id in sorted(games_seen):
        merged = blend([_load(game_id, "anchor"), _load(game_id, "unanchor")])
        for index, ev in merged.items():
            if ev.price_median > 0:
                out[(game_id, index)] = ev.price_median
    return out


def main() -> None:
    games = settled_games()
    print(f"{len(games)} settled+extracted Games available offline: {games[0]}-{games[-1]}")
    records = bpm.observations(games)
    positive = [r for r in records if r["positive"]]
    print(f"{len(records)} Line Items joined, {len(positive)} with proven positive t\n")

    model_caches = {
        "var/evidence (STALE, pre-fix prompt)": model_evidence_cache(),
        "retest mini (current prompt)": retest_model_cache("mini"),
        "retest terra (current prompt)": retest_model_cache("terra"),
    }
    for label, cache in model_caches.items():
        print(f"  model cache [{label}]: {len(cache)} priced items")
    print()

    # -------------------------------------------------------------- leave-one-Game-out
    miss_trade_errs: list[float] = []
    miss_trade_errs_tail: list[float] = []  # t >= 1000
    miss_flat_errs: list[float] = []
    miss_model_errs: dict[str, list[float]] = {label: [] for label in model_caches}
    miss_model_errs_tail: dict[str, list[float]] = {label: [] for label in model_caches}
    n_miss_total = 0
    n_miss_trade_reachable = 0
    worst: list[tuple[float, int, int, str, float, float]] = []

    for game_id in games:
        held_out = [r for r in positive if r["game"] == game_id]
        if not held_out:
            continue
        training = [r for r in records if r["game"] != game_id]
        training_positive = [r for r in training if r["positive"]]

        item_memory = PriceMemory.from_dict({"entries": build_entries(training)})
        trades = trade_medians(training_positive)
        flat_global = (
            statistics.median(r["t_point"] for r in training_positive)
            if training_positive
            else 97.0
        )

        for r in held_out:
            hit = item_memory.lookup(r["display_name"], unit=r["unit"], quantity=r["quantity"])
            if hit is not None and hit.median > 0:
                continue  # item-level memory already answers this one
            n_miss_total += 1
            t = r["t_point"]

            trade = bin_of(r["display_name"])
            bucket = trades.get((trade, r["basis"])) if trade else None
            if bucket:
                n_miss_trade_reachable += 1
                pred = statistics.median(bucket) * (r["quantity"] if r["basis"] == "per_unit" else 1.0)
                if pred > 0:
                    err = math.log(pred / t)
                    miss_trade_errs.append(err)
                    if t >= 1000:
                        miss_trade_errs_tail.append(err)
                    if abs(err) > 1.5:
                        worst.append((err, game_id, r["line_item_index"], r["display_name"], pred, t))

            miss_flat_errs.append(math.log(flat_global / t))

            for label, cache in model_caches.items():
                cached = cache.get((game_id, r["line_item_index"]))
                if cached:
                    merr = math.log(cached / t)
                    miss_model_errs[label].append(merr)
                    if t >= 1000:
                        miss_model_errs_tail[label].append(merr)

    print("=== population: proven-positive Line Items where item-level Price Memory MISSES ===")
    print(f"  n_miss_total={n_miss_total}  reachable by a trade-bin anchor={n_miss_trade_reachable} "
          f"({n_miss_trade_reachable / max(n_miss_total, 1):.0%})\n")

    def report(label: str, errs: list[float]) -> None:
        n, bias, sigma, rmsle = _stats(errs)
        print(f"  {label:32s} n={n:4d}  RMSLE={rmsle:6.3f}  bias={bias:+.3f}  dispersion={sigma:.3f}")

    report("trade-bin anchor (all)", miss_trade_errs)
    report("flat global-median guess", miss_flat_errs)
    for label, errs in miss_model_errs.items():
        report(f"model-only [{label}]", errs)
    print()
    report("trade-bin anchor, t>=1000", miss_trade_errs_tail)
    for label, errs in miss_model_errs_tail.items():
        report(f"model-only [{label}], t>=1000", errs)

    print("\n=== worst trade-bin misses (|log error| > 1.5) ===")
    for err, g, idx, name, pred, t in sorted(worst, key=lambda x: -abs(x[0]))[:15]:
        print(f"  g{g:02d}#{idx:<3d} pred={pred:8.2f}  t={t:8.2f}  log_err={err:+.2f}  {name[:60]}")

    print("\n=== trade bins, size and dispersion (built on ALL Games, for reference) ===")
    all_trades = trade_medians(positive)
    for (trade, basis), values in sorted(all_trades.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if len(values) < 2:
            continue
        med = statistics.median(values)
        logs = [math.log(v / med) for v in values]
        disp = statistics.pstdev(logs) if len(logs) > 1 else 0.0
        print(f"  {trade:22s} {basis:9s} n={len(values):3d}  median={med:9.2f}  internal_dispersion={disp:.3f}")


if __name__ == "__main__":
    main()
