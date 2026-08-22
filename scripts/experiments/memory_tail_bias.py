"""Is Price Memory itself biased low on the tail, and does a magnitude-conditional
weight in `blend.combine()` fix the damage it does to a good model read?

Coordinator's finding: `combine()`'s fixed inverse-variance weights (MEMORY_SIGMA=0.43 vs
MODEL_SIGMA_PRIOR=0.6) give memory ~1.95x the model's weight regardless of magnitude, and
on the expensive tail (t>=1000) that drags mini's raw read (RMSLE 0.500) down to 1.145
post-combine, while terra's hotter raw read (0.795) barely moves (stays 0.775) because it
already overshoots in the direction memory pulls it *away* from.

This script:
  (A) Measures `stored_median / t` bucketed by `t`, LEAVE-ONE-GAME-OUT (a fresh PriceMemory
      rebuilt excluding the game under test, for every game -- not the single pinned
      snapshot other reports use, which has look-ahead for every game simultaneously since
      it was built from all 44). Answers "is the store itself low up there."
  (B) Tests two magnitude-conditional variants of `combine()` against the shipped one:
        - "drop":  above a threshold t_hat, ignore Channel B entirely (pure model).
        - "widen": above the threshold, multiply MEMORY_SIGMA by a factor before the
          inverse-variance weighting (a continuous de-weighting, not a hard cutoff).
      Scored in RMSLE (tail t>=1000 AND body t<1000, so a body regression cannot hide
      behind a tail win) and in EUROS via `price_item` + `replay_payoffs.replay`, with the
      standard odd/even and 1-20/21+ folds and the 26,622*sqrt(n/18) noise floor.
  Both for mini and terra (`var/experiments/model_bakeoff_retest/`), since the coordinator
  wants to know whether fixing the blend flips the model ranking back.

No LLM calls -- everything here reads already-cached model evidence.

    PYTHONPATH=. pixi run python scripts/experiments/memory_tail_bias.py --games 1-44
"""

from __future__ import annotations

import argparse
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.domain.pricing.engine import Evidence, price_item  # noqa: E402
from src.domain.pricing.memory import (  # noqa: E402
    PriceMemory,
    build_entries,
)
from src.services.strategies.strategy2.constants import BAND_Z  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_price_memory import observations  # noqa: E402
from replay_payoffs import snapshot, replay  # noqa: E402

import json  # noqa: E402

RETEST_CACHE = Path("var/experiments/model_bakeoff_retest")
INF = math.inf
NOISE_FLOOR_18 = 26622.0
MODEL_SIGMA_PRIOR = 0.6
MEMORY_SIGMA = 0.43


def noise_floor(n: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(n / 18.0)


# ------------------------------------------------------------------- leave-one-out memory


def build_loo_memories(game_ids: list[int], unbounded_k: float = 1.0) -> tuple[dict[int, PriceMemory], dict]:
    """One PriceMemory per held-out game, built from every OTHER game in `game_ids`.

    `unbounded_k`: multiplier applied to `record["value"]` for records whose bracket was
    unbounded (`t_high is None`, i.e. `fair_value()` fell back to `t_lo`, the proven floor).
    k=1.0 reproduces the shipped store exactly. This is the store-side fix the coordinator
    asked to re-test: `build_price_memory.fair_value()` stores the floor, never a corrected
    estimate, for every unbounded bracket -- and unbounded brackets are disproportionately
    the expensive third of the corpus.
    """
    print(f"  building leave-one-Game-out Price Memories (k={unbounded_k})...", file=sys.stderr)
    all_records = observations(game_ids)
    by_game: dict[int, list] = {}
    for r in all_records:
        by_game.setdefault(r["game"], []).append(r)
    out: dict[int, PriceMemory] = {}
    for g in game_ids:
        train_records = [
            (dict(r, value=r["value"] * unbounded_k) if (unbounded_k != 1.0 and r["t_high"] is None) else r)
            for r in all_records if r["game"] != g
        ]
        entries = build_entries(train_records)
        out[g] = PriceMemory.from_dict({"entries": entries})
    return out, by_game


# ------------------------------------------------------------------- (A) store bias by t


def store_bias_report(game_ids: list[int], loo: dict[int, PriceMemory], by_game: dict) -> None:
    print("=== (A) Price Memory's OWN median vs true t, leave-one-Game-out, bucketed by t ===")
    buckets = [(0, 50), (50, 150), (150, 400), (400, 1000), (1000, 1e9)]
    rows = []
    for g in game_ids:
        mem = loo[g]
        try:
            snap = snapshot(g)
        except Exception:
            continue
        for r in by_game.get(g, []):
            if not r["positive"]:
                continue
            idx = r["line_item_index"]
            lo, hi = snap.fair_brackets.get(idx, (0.0, INF))
            if lo <= 0:
                continue
            t = lo if hi == INF else (lo + hi) / 2.0
            hit = mem.lookup(r["display_name"], unit=r["unit"], quantity=r["quantity"])
            if hit is None:
                continue
            rows.append((t, hit.median, hi == INF))
    for blo, bhi in buckets:
        sel = [row for row in rows if blo <= row[0] < bhi]
        if not sel:
            continue
        ratios = sorted(m / t for t, m, _ in sel)
        log_errs = [math.log(m / t) for t, m, _ in sel]
        bias = st.fmean(log_errs)
        censored_n = sum(1 for _, _, c in sel if c)
        print(
            f"  t in [{blo:>5},{bhi:>8}) n={len(sel):3d} (censored={censored_n:3d}) "
            f"median(stored/t)={ratios[len(ratios)//2]:5.2f}  mean_log_bias={bias:+.3f}  "
            f"share stored<t={sum(1 for r in ratios if r < 1)/len(ratios):4.0%}"
        )
    print()


# ------------------------------------------------------------------- (B) combine variants


def combine_variant(
    model: Evidence | None, memory: Evidence | None, *, mode: str, threshold: float, factor: float
) -> Evidence | None:
    """Reimplements `blend.combine`'s numeric core with a magnitude-conditional weight.

    Structurally identical to the shipped function for the branches that are unaffected
    (model is None -> memory; memory missing/zero -> model unchanged; model zero-band ->
    unchanged; memory-proven-zero -> unchanged) -- only the final inverse-variance blend
    branch (both channels have a real, positive band) is touched, since that is the only
    branch the coordinator's arithmetic concerns.
    """
    if model is None:
        return memory
    if memory is None or memory.price_median <= 0:
        return model
    if model.price_median <= 0:
        return Evidence(
            index=model.index, coverage_probability=model.coverage_probability,
            price_low=memory.price_low, price_median=memory.price_median, price_high=memory.price_high,
        )
    if memory.coverage_probability == 0.0:
        return Evidence(
            index=memory.index, coverage_probability=0.0,
            price_low=model.price_low or memory.price_low,
            price_median=model.price_median or memory.price_median,
            price_high=model.price_high or memory.price_high,
        )

    memory_sigma = MEMORY_SIGMA
    if mode == "drop" and model.price_median >= threshold:
        return model
    if mode == "widen" and model.price_median >= threshold:
        memory_sigma = MEMORY_SIGMA * factor

    weight_model = 1.0 / (MODEL_SIGMA_PRIOR ** 2)
    weight_memory = 1.0 / (memory_sigma ** 2)
    total = weight_model + weight_memory
    median = math.exp(
        (weight_model * math.log(model.price_median) + weight_memory * math.log(memory.price_median)) / total
    )
    sigma = math.sqrt(1.0 / total)
    low = median * math.exp(-BAND_Z * sigma)
    high = median * math.exp(BAND_Z * sigma)
    return Evidence(
        index=model.index, coverage_probability=model.coverage_probability,
        price_low=low, price_median=median, price_high=high,
    )


# ------------------------------------------------------------------- cache access (model)


def _blob(game_id: int, model_tag: str, prompt_tag: str) -> dict | None:
    p = RETEST_CACHE / f"case_{game_id:02d}_{model_tag}_{prompt_tag}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _ev(blob: dict | None) -> dict[int, Evidence]:
    if blob is None or not blob.get("items"):
        return {}
    return {
        int(i): Evidence(
            index=int(i),
            coverage_probability=v.get("coverage_probability", 0.9),
            price_low=v.get("price_low", 0.0),
            price_median=v.get("price_median", 0.0),
            price_high=v.get("price_high", 0.0),
        )
        for i, v in blob["items"].items()
    }


def model_evidence(game_id: int, model_tag: str) -> dict[int, Evidence]:
    from src.services.strategies.strategy2.blend import blend
    return blend([_ev(_blob(game_id, model_tag, "anchor")), _ev(_blob(game_id, model_tag, "unanchor"))])


def memory_as_evidence(hit) -> Evidence | None:
    if hit is None:
        return None
    return Evidence(index=0, coverage_probability=0.9, price_low=hit.low, price_median=hit.median, price_high=hit.high)


# ------------------------------------------------------------------- scoring


def rmsle(errs: list[float]) -> str:
    if not errs:
        return "n=0"
    r = math.sqrt(st.fmean(e * e for e in errs))
    b = st.fmean(errs)
    return f"n={len(errs):3d} RMSLE={r:.3f} bias={b:+.3f}"


def score_variant(
    game_ids: list[int], model_tag: str, loo: dict[int, PriceMemory], meta: dict,
    *, mode: str, threshold: float, factor: float,
) -> dict:
    tail_errs, body_errs = [], []
    nets: dict[int, float] = {}
    for g in game_ids:
        try:
            snap = snapshot(g)
        except Exception:
            continue
        mdl = model_evidence(g, model_tag)
        if not mdl:
            continue
        mem_store = loo[g]
        li_meta = meta.get(g, {})
        submission: dict[int, tuple[float, float]] = {}
        for idx in snap.line_items:
            name, unit, qty, uncovered = li_meta.get(idx, ("", "", 1.0, False))
            from_model = mdl.get(idx)
            hit = None if uncovered else mem_store.lookup(name, unit=unit, quantity=qty)
            from_memory = memory_as_evidence(hit)
            if mode == "shipped":
                from src.services.strategies.strategy2.blend import combine
                evidence = combine(from_model, from_memory)
            else:
                evidence = combine_variant(from_model, from_memory, mode=mode, threshold=threshold, factor=factor)
            if evidence is None:
                continue
            price = price_item(evidence, confirmed_uncovered=uncovered, memory_backed=hit is not None and not uncovered)
            submission[idx] = (price.charge, price.limit)

            lo, hi = snap.fair_brackets.get(idx, (0.0, INF))
            if lo <= 0:
                continue
            t = lo if hi == INF else (lo + hi) / 2.0
            filled = evidence.with_defaults()
            if filled.price_median <= 0:
                continue
            e = math.log(filled.price_median / t)
            (tail_errs if t >= 1000 else body_errs).append(e)
        if submission:
            nets[g] = replay(snap, submission).net
    return {"tail": tail_errs, "body": body_errs, "nets": nets}


def fold_line(nets: dict[int, float], games: list[int]) -> str:
    common = [g for g in games if g in nets]
    if not common:
        return "n=0"
    total = sum(nets[g] for g in common)
    nf = noise_floor(len(common))
    return f"n={len(common):3d} net={total:+12,.0f} floor=+/-{nf:8,.0f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-44")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    all_games = list(range(int(start), int(end or start) + 1))
    # restrict to games actually present in the retest cache (else "no model evidence" noise)
    game_ids = sorted({int(f.stem.split("_")[1]) for f in RETEST_CACHE.glob("case_*.json")} & set(all_games))
    print(f"scoring {len(game_ids)} games present in the retest cache: {game_ids}\n")

    loo_k1, by_game = build_loo_memories(game_ids)
    store_bias_report(game_ids, loo_k1, by_game)

    # per-game metadata: index -> (name, unit, quantity, uncovered)
    from src.data.case_loader import read_case
    import asyncio
    CASES = Path("[PUBLIC] EHL Cases/cases")
    meta: dict[int, dict] = {}
    for g in game_ids:
        d = CASES / f"case_{g:02d}"
        if not (d / "policy.txt").exists():
            continue
        case = asyncio.run(read_case(g, d))
        from src.services.strategies.strategy2.channels import unit_of
        meta[g] = {
            li.index: (li.name, unit_of(li.name), max(li.quantity, 1.0), bool(getattr(li, "quantity_missing", False)))
            for li in case.line_items
        }

    def euro_table(results: dict, labels: list[str], base_label: str = "shipped") -> None:
        base_nets = results[base_label]["nets"]
        common_all = sorted(set.intersection(*(set(results[l]["nets"]) for l in labels)))
        for label in labels:
            nets = results[label]["nets"]
            total = sum(nets[g] for g in common_all)
            delta = total - sum(base_nets[g] for g in common_all)
            print(f"    [{label:16s}] all(n={len(common_all)}) net={total:+12,.0f}  delta_vs_{base_label}={delta:+10,.0f}")
        for split_label, subset in (
            ("odd", [g for g in common_all if g % 2 == 1]),
            ("even", [g for g in common_all if g % 2 == 0]),
            ("1-20", [g for g in common_all if g <= 20]),
            ("21+", [g for g in common_all if g > 20]),
        ):
            if not subset:
                continue
            nf = noise_floor(len(subset))
            base = sum(base_nets.get(g, 0.0) for g in subset)
            line = f"    fold {split_label:5s} n={len(subset):3d} floor=+/-{nf:7,.0f}  {base_label}={base:+10,.0f}"
            for label in labels:
                if label == base_label:
                    continue
                v = sum(results[label]["nets"].get(g, 0.0) for g in subset)
                line += f"  {label}={v-base:+9,.0f}"
            print(line)

    # -- (B) blend-side fix: magnitude-conditional combine() weight ------------------------
    blend_variants = [
        ("shipped", None, None, 1.0),
        ("drop@500", "drop", 500.0, 1.0),
        ("drop@1000", "drop", 1000.0, 1.0),
        ("widen@500x3", "widen", 500.0, 3.0),
        ("widen@1000x3", "widen", 1000.0, 3.0),
        ("widen@1000x5", "widen", 1000.0, 5.0),
    ]
    # -- (A2) store-side fix: fair_value(unbounded) = t_lo * k, swept, leave-one-out -------
    store_ks = [1.0, 1.17, 1.5, 2.0, 3.0]
    print("=== (A2) store-side fix: unbounded fair_value = t_lo * k, leave-one-Game-out, shipped combine() ===")
    print("    (re-opens build_price_memory.py's own docstring claim that k>1 'measured worse'")
    print("     -- that was Games 1-14, mini, old prompt; store is now 41 Games, corrected prompt.)")

    for model_tag in ("mini", "terra"):
        print(f"\n########## model = {model_tag} ##########")

        print("\n-- (B) blend-side fix (store held at shipped k=1) --")
        blend_results = {}
        for label, mode, threshold, factor in blend_variants:
            res = score_variant(game_ids, model_tag, loo_k1, meta,
                                 mode=(mode or "shipped"), threshold=(threshold or 0.0), factor=factor)
            blend_results[label] = res
            print(f"  [{label:16s}] tail(t>=1000): {rmsle(res['tail'])}   body(t<1000): {rmsle(res['body'])}")
        print("\n  euros:")
        euro_table(blend_results, [l for l, *_ in blend_variants])

        print("\n-- (A2) store-side fix (blend held at shipped weights) --")
        store_results = {}
        store_loo_cache: dict[float, dict] = {1.0: loo_k1}
        for k in store_ks:
            loo_k = store_loo_cache.get(k) or build_loo_memories(game_ids, unbounded_k=k)[0]
            store_loo_cache[k] = loo_k
            label = f"store_k={k}"
            res = score_variant(game_ids, model_tag, loo_k, meta, mode="shipped", threshold=0.0, factor=1.0)
            store_results[label] = res
            print(f"  [{label:16s}] tail(t>=1000): {rmsle(res['tail'])}   body(t<1000): {rmsle(res['body'])}")
        print("\n  euros:")
        euro_table(store_results, [f"store_k={k}" for k in store_ks], base_label="store_k=1.0")

        # -- combined: best single blend variant (by tail RMSLE, excl. shipped) + best k ---
        best_blend = min(
            (l for l, *_ in blend_variants if l != "shipped"),
            key=lambda l: math.sqrt(st.fmean(e * e for e in blend_results[l]["tail"])) if blend_results[l]["tail"] else 1e9,
        )
        best_k = min(
            (k for k in store_ks if k != 1.0),
            key=lambda k: math.sqrt(st.fmean(e * e for e in store_results[f"store_k={k}"]["tail"])) if store_results[f"store_k={k}"]["tail"] else 1e9,
        )
        bv_label, bv_mode, bv_threshold, bv_factor = next(v for v in blend_variants if v[0] == best_blend)
        print(f"\n-- combined: best blend ({best_blend}) + best store k ({best_k}) --")
        loo_best_k = store_loo_cache[best_k]
        combined = score_variant(game_ids, model_tag, loo_best_k, meta,
                                  mode=(bv_mode or "shipped"), threshold=(bv_threshold or 0.0), factor=bv_factor)
        shipped_both = score_variant(game_ids, model_tag, loo_k1, meta, mode="shipped", threshold=0.0, factor=1.0)
        print(f"  [combined       ] tail(t>=1000): {rmsle(combined['tail'])}   body(t<1000): {rmsle(combined['body'])}")
        print(f"  [shipped/shipped] tail(t>=1000): {rmsle(shipped_both['tail'])}   body(t<1000): {rmsle(shipped_both['body'])}")
        print("\n  euros:")
        euro_table({"shipped": shipped_both, "combined": combined}, ["shipped", "combined"])


if __name__ == "__main__":
    main()
