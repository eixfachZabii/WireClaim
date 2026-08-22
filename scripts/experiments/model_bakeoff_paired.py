"""Model bake-off, stage 3: the three follow-ups the coordinator asked for mid-run.

1. Paired RMSLE -- same Line Items only, across all three models, with a sign test.
   The plain per-model RMSLE table compares different item populations (whichever games
   happened to complete for each model); this restricts to the intersection so the number
   is not confounded by composition.
2. Timeout rate and p95 latency by Line Item count bucket, against a 50s budget (the
   coordinator raised `LLM_TIMEOUT_SECONDS` 40 -> 50 mid-run), not this harness's own 75s
   measurement ceiling.
3. The mini+terra hybrid: ensemble draw A = mini's anchored prompt, draw B = terra's
   un-anchored prompt, blended exactly as `blend()` already handles a 1- or 2-draw ensemble.
   Scored against mini-only and terra-only on the paired set, then in euros.

    PYTHONPATH=. pixi run python scripts/experiments/model_bakeoff_paired.py --games 1-32
"""

from __future__ import annotations

import argparse
import asyncio
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.case_loader import read_case  # noqa: E402
from src.pricing import Evidence, price_item  # noqa: E402
from src.services.strategies.strategy2.blend import blend, combine  # noqa: E402

from model_bakeoff_score import (  # noqa: E402
    CACHE, CASES, MODELS, INF, _blob, _evidence_dict, memory_evidence,
    line_item_meta, MODEL_NAMES,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay_payoffs import snapshot, replay  # noqa: E402

NOISE_FLOOR_30 = 34369.0
BUDGET = 50.0  # the coordinator's raised LLM_TIMEOUT_SECONDS


def item_counts(game_ids: list[int]) -> dict[int, int]:
    out = {}
    for g in game_ids:
        d = CASES / f"case_{g:02d}"
        if not (d / "policy.txt").exists():
            continue
        case = asyncio.run(read_case(g, d))
        out[g] = len(case.line_items)
    return out


# --------------------------------------------------------------------- (2) latency buckets

BUCKETS = [(1, 5), (6, 10), (11, 20), (21, 999)]


def bucket_of(n: int) -> str:
    for lo, hi in BUCKETS:
        if lo <= n <= hi:
            return f"{lo}-{hi}" if hi != 999 else f"{lo}+"
    return "?"


def latency_by_bucket(game_ids: list[int], counts: dict[int, int]) -> None:
    print(f"=== timeout rate and p95 latency by Line Item count, budget={BUDGET:.0f}s ===")
    print(f"  ({sum(1 for g in game_ids if g in counts)} Cases with known item counts)")
    for label, _ in [(bucket_of(lo), None) for lo, _ in BUCKETS]:
        pass
    header = f"  {'model':6s} {'bucket':7s} {'n_calls':>8s} {'timeouts':>9s} {'>50s':>7s} {'p50':>7s} {'p95':>7s} {'max':>7s}"
    print(header)
    for m in MODELS:
        for lo, hi in BUCKETS:
            label = f"{lo}-{hi}" if hi != 999 else f"{lo}+"
            games = [g for g in game_ids if lo <= counts.get(g, -1) <= hi]
            completed = []
            n_calls = 0
            timeouts = 0
            over_budget = 0
            for g in games:
                for prompt_tag in ("anchor", "unanchor"):
                    b = _blob(g, m, prompt_tag)
                    if b is None:
                        continue
                    n_calls += 1
                    if b.get("error"):
                        timeouts += 1
                        over_budget += 1
                        continue
                    lat = b.get("latency_s")
                    if lat is None:
                        continue
                    completed.append(lat)
                    if lat > BUDGET:
                        over_budget += 1
            if n_calls == 0:
                continue
            completed.sort()
            def pct(p, vals=completed):
                if not vals:
                    return float("nan")
                return vals[min(int(p * len(vals)), len(vals) - 1)]
            print(
                f"  {m:6s} {label:7s} {n_calls:8d} {timeouts:9d} "
                f"{over_budget / n_calls:6.1%} {pct(0.5):7.1f} {pct(0.95):7.1f} "
                f"{(completed[-1] if completed else float('nan')):7.1f}"
            )
        print()


# --------------------------------------------------------------------- (1) paired RMSLE


def paired_dataset(game_ids: list[int]) -> dict[tuple[int, int], dict]:
    """(game, index) -> {model: (median, t, uncovered)} only where ALL THREE models spoke."""
    per_model_evidence: dict[str, dict[int, dict[int, Evidence]]] = {m: {} for m in MODELS}
    for g in game_ids:
        for m in MODELS:
            draws = [
                _evidence_dict(_blob(g, m, "anchor")),
                _evidence_dict(_blob(g, m, "unanchor")),
            ]
            per_model_evidence[m][g] = blend(draws)

    combined: dict[tuple[int, int], dict] = {}
    for g in game_ids:
        try:
            snap = snapshot(g)
        except Exception:
            continue
        meta = line_item_meta(g)
        mem = memory_evidence(g)
        for index in snap.line_items:
            lo, hi = snap.fair_brackets.get(index, (0.0, INF))
            if hi == INF or lo <= 0:
                continue  # real-money population only, matching leak_sigma.py
            t = (lo + hi) / 2.0
            row = {}
            ok = True
            for m in MODELS:
                from_model = per_model_evidence[m].get(g, {}).get(index)
                if from_model is None:
                    ok = False
                    break
                from_memory = mem.get(index)
                evidence = combine(from_model, from_memory)
                if evidence is None:
                    ok = False
                    break
                filled = evidence.with_defaults()
                row[m] = filled.price_median
            if ok:
                combined[(g, index)] = {"t": t, **row}
    return combined


def sign_test(a_errs: list[float], b_errs: list[float]) -> tuple[int, int, int]:
    """(a wins, ties, b wins) by |log error|, smaller is better."""
    a_win = b_win = tie = 0
    for a, b in zip(a_errs, b_errs):
        if abs(a) < abs(b) - 1e-9:
            a_win += 1
        elif abs(b) < abs(a) - 1e-9:
            b_win += 1
        else:
            tie += 1
    return a_win, tie, b_win


def binom_two_sided_p(k: int, n: int) -> float:
    """Exact two-sided sign-test p-value at p=0.5, no scipy dependency."""
    if n == 0:
        return 1.0
    from math import comb
    k = min(k, n - k)
    total = sum(comb(n, i) for i in range(0, k + 1))
    p = total * 2 / (2 ** n)
    return min(p, 1.0)


def paired_report(paired: dict[tuple[int, int], dict]) -> dict[str, list[float]]:
    print(f"\n=== paired RMSLE: same {len(paired)} Line Items (real money, all 3 models spoke) ===")
    errs = {m: [] for m in MODELS}
    for key, row in paired.items():
        t = row["t"]
        for m in MODELS:
            errs[m].append(math.log(row[m] / t))
    for m in MODELS:
        e = errs[m]
        if not e:
            print(f"  {m:6s} n=0")
            continue
        rmsle = math.sqrt(st.fmean(x * x for x in e))
        bias = st.fmean(e)
        disp = st.pstdev(e) if len(e) > 1 else 0.0
        print(f"  {m:6s} n={len(e):3d}  RMSLE={rmsle:.3f}  bias={bias:+.3f}  dispersion={disp:.3f}")

    print("\n  sign test on |log error| (smaller wins), paired by Line Item:")
    for other in ("terra", "luna"):
        a_win, tie, b_win = sign_test(errs["mini"], errs[other])
        n = a_win + b_win
        p = binom_two_sided_p(a_win, n) if n else 1.0
        print(
            f"    mini vs {other:5s}: mini better {a_win:3d} / tie {tie:3d} / {other} better {b_win:3d}"
            f"   (n={n}, two-sided sign-test p={p:.3f})"
        )
    return errs


# --------------------------------------------------------------------- (3) hybrid


def hybrid_evidence(game_id: int) -> dict[int, Evidence]:
    """Ensemble draw A = mini/anchor, draw B = terra/unanchor -- exactly what blend() expects."""
    a = _evidence_dict(_blob(game_id, "mini", "anchor"))
    b = _evidence_dict(_blob(game_id, "terra", "unanchor"))
    return blend([a, b])


def hybrid_report(game_ids: list[int]) -> None:
    print("\n=== hybrid: draw A = mini/anchor, draw B = terra/unanchor, blended ===")
    nets: dict[str, dict[int, float]] = {"mini": {}, "terra": {}, "hybrid": {}}
    real_money_errs: dict[str, list[float]] = {"mini": [], "terra": [], "hybrid": []}
    for g in game_ids:
        try:
            snap = snapshot(g)
        except Exception:
            continue
        meta = line_item_meta(g)
        mem = memory_evidence(g)
        variants = {
            "mini": blend([_evidence_dict(_blob(g, "mini", "anchor")), _evidence_dict(_blob(g, "mini", "unanchor"))]),
            "terra": blend([_evidence_dict(_blob(g, "terra", "anchor")), _evidence_dict(_blob(g, "terra", "unanchor"))]),
            "hybrid": hybrid_evidence(g),
        }
        for label, mdl in variants.items():
            if not mdl:
                continue
            submission = {}
            for index in snap.line_items:
                from_model = mdl.get(index)
                from_memory = mem.get(index)
                evidence = combine(from_model, from_memory)
                if evidence is None:
                    continue
                _, uncovered = meta.get(index, ("", False))
                price = price_item(evidence, confirmed_uncovered=uncovered)
                submission[index] = (price.charge, price.limit)
                lo, hi = snap.fair_brackets.get(index, (0.0, INF))
                if hi != INF and lo > 0:
                    t = (lo + hi) / 2.0
                    filled = evidence.with_defaults()
                    if filled.price_median > 0:
                        real_money_errs[label].append(math.log(filled.price_median / t))
            if submission:
                nets[label][g] = replay(snap, submission).net

    print("  RMSLE, real-money items, whatever games each variant produced evidence for:")
    for label in ("mini", "terra", "hybrid"):
        e = real_money_errs[label]
        if not e:
            print(f"    {label:7s} n=0")
            continue
        rmsle = math.sqrt(st.fmean(x * x for x in e))
        print(f"    {label:7s} n={len(e):3d}  RMSLE={rmsle:.3f}  bias={st.fmean(e):+.3f}")

    common = sorted(set(nets["mini"]) & set(nets["terra"]) & set(nets["hybrid"]))
    print(f"\n  euros, common Games (n={len(common)}):")
    if common:
        nf = NOISE_FLOOR_30 * math.sqrt(len(common) / 30.0)
        totals = {label: sum(nets[label][g] for g in common) for label in ("mini", "terra", "hybrid")}
        for label in ("mini", "terra", "hybrid"):
            print(f"    {label:7s} total {totals[label]:>12,.2f}")
        print(f"    noise floor +/-{nf:,.0f}")
        for label in ("terra", "hybrid"):
            d = totals[label] - totals["mini"]
            flag = "inside noise floor" if abs(d) < nf else "OUTSIDE noise floor"
            print(f"    delta {label} - mini: {d:+,.2f}  [{flag}]")
        odd = [g for g in common if g % 2 == 1]
        even = [g for g in common if g % 2 == 0]
        for split_label, subset in (("odd", odd), ("even", even)):
            if not subset:
                continue
            sub_totals = {label: sum(nets[label].get(g, 0.0) for g in subset) for label in ("mini", "terra", "hybrid")}
            nf_s = NOISE_FLOOR_30 * math.sqrt(len(subset) / 30.0)
            print(
                f"    {split_label:5s} (n={len(subset)}, floor +/-{nf_s:,.0f}): "
                f"terra-mini={sub_totals['terra']-sub_totals['mini']:+,.0f}  "
                f"hybrid-mini={sub_totals['hybrid']-sub_totals['mini']:+,.0f}"
            )
    else:
        print("    not enough common Games yet")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-32")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))

    counts = item_counts(game_ids)
    latency_by_bucket(game_ids, counts)

    paired = paired_dataset(game_ids)
    paired_report(paired)

    hybrid_report(game_ids)


if __name__ == "__main__":
    main()
