"""Per-hit Price Memory sigma: stop discarding the store's own disagreement with itself.

Coordinator's finding: `combine()` weights every memory hit with the same constant
`MEMORY_SIGMA=0.43`, but a `PriceMemoryHit` already carries `observed_low`/`observed_high`/
`observations`, and the stored band (`hit.low`/`hit.high`) already encodes
`max(SIGMA_LOG, raw_observed_spread_sigma)` -- exactly the per-hit sigma `combine()` should
be using instead of the constant, via the SAME `sigma_of`-shaped calculation
(`log(high/low)/(2*BAND_Z)`) already used for the model side. `combine()` simply never reads
`memory.price_low`/`memory.price_high` for anything but the point weighting; it substitutes
the constant instead.

Three things tested, in the order asked:

1. NAIVE per-hit sigma: `sigma_memory = log(hit.high/hit.low) / (2*BAND_Z)` (identical to
   `blend.sigma_of`, applied to the memory band instead of the model band). For a single-
   observation hit this reproduces `hit.low`/`hit.high` = `median * exp(+/- SIGMA_LOG)`
   EXACTLY -- i.e. sigma_memory == SIGMA_LOG == the current constant, unchanged. Reported
   explicitly, because it predicts (and this script confirms) that the naive fix does
   NOTHING to Game 41 item 3 specifically, which is a single-observation hit.
2. Shrinkage for n>=2: `sigma = SIGMA_LOG + (raw_sigma - SIGMA_LOG) * n/(n+k)`, i.e. only the
   EXCESS width beyond the population SIGMA_LOG is trusted in proportion to how many
   observations back it, swept over k in {0, 2, 5}.
3. A dedicated, MEASURED sigma for observations==1 hits, in place of the SIGMA_LOG fallback
   -- because a single observation from an unrelated Case (Game 41's exact failure) is
   direct evidence that SIGMA_LOG is too tight for n=1 specifically, not just an accident of
   one item. Measured via leave-one-Game-out RMSLE restricted to n==1 hits, i.e. the same
   procedure that produced SIGMA_LOG itself, just split by sample count instead of pooled.

Every number is leave-one-Game-out (a fresh PriceMemory per held-out Game, built from
`build_price_memory.observations()` excluding that Game -- see `memory_tail_bias.py`, reused
here, not re-derived).

    PYTHONPATH=. pixi run python scripts/experiments/memory_perhit_sigma.py --games 1-44
"""

from __future__ import annotations

import argparse
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.pricing.engine import Evidence, price_item  # noqa: E402
from src.strategies.strategy2.constants import BAND_Z, MODEL_SIGMA_PRIOR  # noqa: E402
from src.evidence.memory import SIGMA_LOG  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory_tail_bias import (  # noqa: E402
    build_loo_memories, model_evidence, rmsle, noise_floor,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay_payoffs import snapshot, replay  # noqa: E402

RETEST_CACHE = Path("var/experiments/model_bakeoff_retest")
INF = math.inf


def hit_sigma_naive(hit) -> float:
    """Recover the sigma `memory.py` itself means by a hit's band.

    BUG FOUND WHILE BUILDING THIS: `memory.py`'s `PriceMemoryHit.widened()` builds a band as
    `median * exp(+/- sigma)` directly -- i.e. `log(high/low) == 2 * sigma` -- but
    `blend.sigma_of` / `engine.implied_sigma` (the MODEL-side convention) treat a band as a
    ~90% interval and divide by `2 * BAND_Z` (1.645) instead of `2`. These are two different
    conventions for "how wide is this band" living in the same codebase. Applying the
    model-side formula to a memory band (the first version of this function did exactly
    that) divides by 1.645 where it should divide by 1, giving sigma_memory = SIGMA_LOG /
    BAND_Z = 0.26 for a single-observation hit -- TIGHTER than the shipped 0.43, not
    identical to it as the docstring above originally claimed. That silently made "variant 1"
    trust memory MORE at n=1, not leave it unchanged, and the Game 41 numbers below were
    wrong until this was caught. Fixed to match `memory.py`'s own convention exactly, which
    is the only reading under which a naive per-hit sigma reproduces the shipped constant
    exactly at n=1 (the desired baseline-preserving property)."""
    if hit.low <= 0 or hit.high <= hit.low:
        return SIGMA_LOG
    return math.log(hit.high / hit.low) / 2.0


def hit_sigma_shrunk(hit, k: float, single_obs_sigma: float) -> float:
    """Shrinkage for n>=2, a dedicated (measured) constant for n==1."""
    if hit.observations <= 1:
        return single_obs_sigma
    raw = hit_sigma_naive(hit)
    n = hit.observations
    weight = n / (n + k) if k > 0 else 1.0
    return SIGMA_LOG + (raw - SIGMA_LOG) * weight


def combine_perhit(model: Evidence | None, memory_hit, *, sigma_fn, memory_coverage: float = 0.9) -> Evidence | None:
    """Reimplements `blend.combine`'s numeric core with a per-hit memory sigma.

    `memory_hit` is the raw `PriceMemoryHit` (or None), not an `Evidence` -- this needs
    `.observations`, which the `Evidence` object the live code builds does not carry (a real
    gap the src/ patch below closes by adding a `sample_count` field).
    """
    if model is None:
        if memory_hit is None:
            return None
        return Evidence(index=0, coverage_probability=memory_coverage,
                         price_low=memory_hit.low, price_median=memory_hit.median, price_high=memory_hit.high)
    if memory_hit is None or memory_hit.median <= 0:
        return model
    if model.price_median <= 0:
        return Evidence(index=model.index, coverage_probability=model.coverage_probability,
                         price_low=memory_hit.low, price_median=memory_hit.median, price_high=memory_hit.high)

    sigma_memory = sigma_fn(memory_hit)
    weight_model = 1.0 / (MODEL_SIGMA_PRIOR ** 2)
    weight_memory = 1.0 / (sigma_memory ** 2)
    total = weight_model + weight_memory
    median = math.exp(
        (weight_model * math.log(model.price_median) + weight_memory * math.log(memory_hit.median)) / total
    )
    sigma = math.sqrt(1.0 / total)
    low = median * math.exp(-BAND_Z * sigma)
    high = median * math.exp(BAND_Z * sigma)
    return Evidence(index=model.index, coverage_probability=model.coverage_probability,
                     price_low=low, price_median=median, price_high=high)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-44")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    all_games = list(range(int(start), int(end or start) + 1))
    game_ids = sorted({int(f.stem.split("_")[1]) for f in RETEST_CACHE.glob("case_*.json")} & set(all_games))
    print(f"scoring {len(game_ids)} games\n")

    loo, by_game = build_loo_memories(game_ids)

    # --- 0. how many hits at each observation count, and their raw leave-one-out sigma ---
    from src.data.case_loader import read_case
    from src.strategies.strategy2.channels import unit_of
    import asyncio
    CASES = Path("[PUBLIC] EHL Cases/cases")
    meta: dict[int, dict] = {}
    for g in game_ids:
        d = CASES / f"case_{g:02d}"
        if not (d / "policy.txt").exists():
            continue
        case = asyncio.run(read_case(g, d))
        meta[g] = {
            li.index: (li.name, unit_of(li.name), max(li.quantity, 1.0), bool(getattr(li, "quantity_missing", False)))
            for li in case.line_items
        }

    hits_by_n: dict[str, list[tuple[float, float]]] = {"n=1": [], "n>=2": []}
    for g in game_ids:
        try:
            snap = snapshot(g)
        except Exception:
            continue
        mem_store = loo[g]
        for idx, (name, unit, qty, uncovered) in meta.get(g, {}).items():
            if uncovered:
                continue
            hit = mem_store.lookup(name, unit=unit, quantity=qty)
            if hit is None:
                continue
            lo, hi = snap.fair_brackets.get(idx, (0.0, INF))
            if lo <= 0:
                continue
            t = lo if hi == INF else (lo + hi) / 2.0
            bucket = "n=1" if hit.observations <= 1 else "n>=2"
            hits_by_n[bucket].append((t, hit.median))

    print("=== 0. hit population by observation count, leave-one-Game-out ===")
    for label, rows in hits_by_n.items():
        if not rows:
            print(f"  {label}: n=0")
            continue
        errs = [math.log(m / t) for t, m in rows]
        r = math.sqrt(st.fmean(e * e for e in errs))
        b = st.fmean(errs)
        print(f"  {label:6s} hits: n={len(rows):3d}  empirical RMSLE={r:.3f}  bias={b:+.3f}  (SIGMA_LOG constant = {SIGMA_LOG})")
    single_obs_measured = None
    if hits_by_n["n=1"]:
        errs1 = [math.log(m / t) for t, m in hits_by_n["n=1"]]
        single_obs_measured = math.sqrt(st.fmean(e * e for e in errs1))
    print()

    def score(model_tag: str, sigma_fn, label: str):
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
            submission: dict[int, tuple[float, float]] = {}
            for idx in snap.line_items:
                name, unit, qty, uncovered = meta.get(g, {}).get(idx, ("", "", 1.0, False))
                from_model = mdl.get(idx)
                hit = None if uncovered else mem_store.lookup(name, unit=unit, quantity=qty)
                evidence = combine_perhit(from_model, hit, sigma_fn=sigma_fn)
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
        print(f"  [{label:22s}] tail(t>=1000): {rmsle(tail_errs)}   body(t<1000): {rmsle(body_errs)}")
        return {"tail": tail_errs, "body": body_errs, "nets": nets}

    def game41_item3(model_tag: str, sigma_fn):
        g = 41
        mdl = model_evidence(g, model_tag)
        from_model = mdl.get(3)
        mem_store = loo[g]
        name, unit, qty, uncovered = meta.get(g, {}).get(3, ("", "", 1.0, False))
        hit = mem_store.lookup(name, unit=unit, quantity=qty)
        evidence = combine_perhit(from_model, hit, sigma_fn=sigma_fn)
        return from_model, hit, evidence

    for model_tag in ("mini", "terra"):
        print(f"\n########## model = {model_tag} ##########")
        variants = {
            "shipped (const 0.43)": lambda h: 0.43,
            "1: naive per-hit": hit_sigma_naive,
            "2: shrink k=2": lambda h: hit_sigma_shrunk(h, 2.0, SIGMA_LOG),
            "2: shrink k=5": lambda h: hit_sigma_shrunk(h, 5.0, SIGMA_LOG),
        }
        if single_obs_measured is not None:
            variants[f"3: shrink k=2 + n=1@{single_obs_measured:.2f}"] = lambda h, s=single_obs_measured: hit_sigma_shrunk(h, 2.0, s)
            variants[f"3: shrink k=5 + n=1@{single_obs_measured:.2f}"] = lambda h, s=single_obs_measured: hit_sigma_shrunk(h, 5.0, s)
        # also sweep a few explicit n=1 sigmas for sensitivity, independent of the measured value
        for s in (0.6, 0.8, 1.0):
            variants[f"3: shrink k=2 + n=1@{s:.2f}(swept)"] = lambda h, s=s: hit_sigma_shrunk(h, 2.0, s)

        results = {}
        for label, fn in variants.items():
            results[label] = score(model_tag, fn, label)

        print("\n  Game 41 item 3 (the tourbillon watch, t >= 11,131) under each variant:")
        for label, fn in variants.items():
            from_model, hit, evidence = game41_item3(model_tag, fn)
            print(
                f"    [{label:38s}] model_only={from_model.price_median:9,.0f}  "
                f"memory_hit_median={hit.median if hit else 0:9,.0f} (n_obs={hit.observations if hit else 0})  "
                f"combined_median={evidence.price_median if evidence else 0:9,.0f}"
            )

        print("\n  euros:")
        base_nets = results["shipped (const 0.43)"]["nets"]
        common_all = sorted(set.intersection(*(set(results[l]["nets"]) for l in variants)))
        for label in variants:
            nets = results[label]["nets"]
            total = sum(nets[g] for g in common_all)
            delta = total - sum(base_nets[g] for g in common_all)
            print(f"    [{label:38s}] n={len(common_all)} net={total:+12,.0f}  delta_vs_shipped={delta:+10,.0f}")
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
            line = f"    fold {split_label:5s} n={len(subset):3d} floor=+/-{nf:7,.0f}  shipped={base:+10,.0f}"
            for label in variants:
                if label == "shipped (const 0.43)":
                    continue
                v = sum(results[label]["nets"].get(g, 0.0) for g in subset)
                line += f"  {label.split(':')[0]}={v-base:+8,.0f}"
            print(line)


if __name__ == "__main__":
    main()
