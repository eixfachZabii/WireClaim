"""Model bake-off, stage 2: score the drawn evidence.

Reads the raw draws `model_bakeoff_draw.py` cached under `var/experiments/model_bakeoff/`,
reconstructs the same pipeline the live path runs -- `blend` the two ensemble prompts,
`combine` with the (free, deterministic) Price Memory channel, `price_item` -- for each of
the three models, and reports:

  * RMSLE of `price_median` against the recovered Fair Value, level (bias) and dispersion
    reported separately (CLAUDE.md rule 10), bounded items vs the censored (unbounded)
    remainder scored separately.
  * Band calibration: RMSLE by the model's own asserted sigma tercile -- does a wider band
    actually mean a worse estimate?
  * Coverage confusion at the COVERAGE_FLOOR = 2/3 threshold that actually zeroes the Limit
    in `src/pricing.py`: recall, false-positive rate, Brier, matching
    `scripts/coverage_bakeoff.py`'s methodology exactly.
  * Latency p50/p95 on real Case prompts (not a trivial ping), and the share that would
    have missed LLM_TIMEOUT_SECONDS=40.0 and the 60s window.
  * Euro delta via `scripts.replay_payoffs.replay` against the real Field, mini vs terra vs
    luna, with odd/even and 1-20/21-32 held-out splits and the stated noise floor.

    PYTHONPATH=. pixi run python scripts/experiments/model_bakeoff_score.py --games 1-32
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.case_loader import read_case  # noqa: E402
from src.domain.pricing.engine import Evidence, price_item, COVERAGE_FLOOR, implied_sigma  # noqa: E402
from src.services.strategies.strategy2.blend import blend, combine  # noqa: E402
from src.services.strategies.strategy2.channels import local_evidence  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dump_evidence import load as load_legacy_evidence  # noqa: E402
from replay_payoffs import snapshot, replay  # noqa: E402

CACHE = Path("var/experiments/model_bakeoff")
CASES = Path("[PUBLIC] EHL Cases/cases")
INF = math.inf
ZERO_FLOOR = 0.01
NOISE_FLOOR_30 = 34369.0  # stated noise floor over 30 Games; scales as sqrt(n/30)

MODELS = ("mini", "terra", "luna")
MODEL_NAMES = {"mini": "gpt-5.4-mini", "terra": "gpt-5.6-terra", "luna": "gpt-5.6-luna"}


def _blob(game_id: int, model_tag: str, prompt_tag: str) -> dict | None:
    path = CACHE / f"case_{game_id:02d}_{model_tag}_{prompt_tag}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _evidence_dict(blob: dict | None) -> dict[int, Evidence]:
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
    """Blend the two ensemble draws for this model, exactly as `strategy2.strategy.propose`."""
    draws = [
        _evidence_dict(_blob(game_id, model_tag, "anchor")),
        _evidence_dict(_blob(game_id, model_tag, "unanchor")),
    ]
    return blend(draws)


def memory_evidence(game_id: int) -> dict[int, Evidence]:
    cached = load_legacy_evidence(game_id, "memory")
    if cached is not None:
        return cached
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return {}
    case = asyncio.run(read_case(game_id, case_dir))
    return local_evidence(case)


def line_item_meta(game_id: int) -> dict[int, tuple[str, bool]]:
    """index -> (name, quantity_missing), for `confirmed_uncovered`."""
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return {}
    case = asyncio.run(read_case(game_id, case_dir))
    return {
        item.index: (item.name, bool(getattr(item, "quantity_missing", False)))
        for item in case.line_items
    }


class Row:
    __slots__ = (
        "game", "index", "model", "t_lo", "t_hi", "median", "sigma",
        "coverage", "model_coverage", "charge", "limit", "model_only_median",
    )

    def __init__(
        self, game, index, model, t_lo, t_hi, median, sigma, coverage, model_coverage,
        charge, limit, model_only_median,
    ):
        self.game = game
        self.index = index
        self.model = model
        self.t_lo = t_lo
        self.t_hi = t_hi
        self.median = median
        self.sigma = sigma
        self.coverage = coverage
        #: the model's OWN coverage_probability (blended ensemble, pre-combine, pre-Channel-A
        #: override) -- this is what "grade Channel C" has to mean, since `coverage` above
        #: gets zeroed by the deterministic dash-quantity rule identically for every model.
        self.model_coverage = model_coverage
        self.charge = charge
        self.limit = limit
        self.model_only_median = model_only_median

    @property
    def t(self) -> float:
        return self.t_lo if self.t_hi == INF else (self.t_lo + self.t_hi) / 2.0

    @property
    def bounded(self) -> bool:
        return self.t_hi != INF

    @property
    def worthless(self) -> bool:
        return self.t_lo <= 0.0


def build_rows(game_ids: list[int]) -> tuple[dict[str, list[Row]], dict[int, dict[str, dict[int, tuple[float, float]]]]]:
    """rows per model, and submissions[model][game] = {index: (charge, limit)}."""
    rows: dict[str, list[Row]] = {m: [] for m in MODELS}
    submissions: dict[int, dict[str, dict[int, tuple[float, float]]]] = {}

    for game_id in game_ids:
        try:
            snap = snapshot(game_id)
        except Exception as exc:  # noqa: BLE001
            print(f"  g{game_id:02d}: snapshot unusable ({exc}); skipped", file=sys.stderr)
            continue
        meta = line_item_meta(game_id)
        mem = memory_evidence(game_id)
        submissions[game_id] = {}
        for model_tag in MODELS:
            mdl = model_evidence(game_id, model_tag)
            if not mdl:
                continue
            submission: dict[int, tuple[float, float]] = {}
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
                filled = evidence.with_defaults()
                model_only_median = from_model.price_median if from_model is not None else 0.0
                model_coverage = from_model.coverage_probability if from_model is not None else 0.9
                rows[model_tag].append(
                    Row(
                        game=game_id, index=index, model=model_tag,
                        t_lo=lo, t_hi=hi,
                        median=filled.price_median, sigma=price.sigma,
                        coverage=price.covered_probability,
                        model_coverage=model_coverage,
                        charge=price.charge, limit=price.limit,
                        model_only_median=model_only_median,
                    )
                )
            submissions[game_id][model_tag] = submission
    return rows, submissions


# --------------------------------------------------------------------------- RMSLE


#: The population definitions match `scripts/leak_sigma.py` exactly -- that script is where
#: the "estimator's actual RMSLE is 0.80" figure in `src/pricing.py`'s docstring comes from,
#: so a comparable number here has to use the same three-way split rather than a bounded/
#: unbounded split alone:
#:
#:   real_money  t_hi != inf AND t_lo > 0   -- the ONLY population price accuracy can move
#:               the payoff on; this is what "0.80" measures and what we compare against.
#:   worthless   t_hi != inf AND t_lo <= 0  -- "uneconomic to score": coverage should have
#:               zeroed the Limit already, so an accurate price here buys nothing. Reported
#:               so a bad number here isn't silently pooled into the headline.
#:   censored    t_hi == inf                -- nobody was ever rightfully rejected, so `t`
#:               defaults to the lower bound `t_lo`; optimistic by construction (CLAUDE.md).
def log_errors(rows: list[Row], *, population: str, use_model_only: bool = False) -> list[float]:
    out = []
    for r in rows:
        if population == "real_money" and not (r.bounded and r.t_lo > 0):
            continue
        if population == "worthless" and not (r.bounded and r.t_lo <= 0):
            continue
        if population == "censored" and r.bounded:
            continue
        t = r.t
        if t <= 0:
            continue
        median = r.model_only_median if use_model_only else r.median
        if median <= 0:
            continue
        out.append(math.log(median / t))
    return out


def rmsle_report(errs: list[float]) -> str:
    if not errs:
        return "n=0"
    rmsle = math.sqrt(st.fmean(e * e for e in errs))
    bias = st.fmean(errs)
    disp = st.pstdev(errs) if len(errs) > 1 else 0.0
    return f"n={len(errs):3d}  RMSLE={rmsle:.3f}  bias={bias:+.3f}  dispersion={disp:.3f}"


# --------------------------------------------------------------------------- coverage


def coverage_confusion(rows: list[Row]) -> tuple[float, float, float, int]:
    hits = misses = false_pos = true_neg = 0
    squared = []
    for r in rows:
        p = r.model_coverage
        truth = 0.0 if r.worthless else 1.0
        squared.append((p - truth) ** 2)
        flagged = p <= COVERAGE_FLOOR
        if r.worthless:
            hits += flagged
            misses += not flagged
        else:
            false_pos += flagged
            true_neg += not flagged
    worthless_n = hits + misses
    valuable_n = false_pos + true_neg
    recall = hits / worthless_n if worthless_n else 0.0
    fpr = false_pos / valuable_n if valuable_n else 0.0
    brier = st.fmean(squared) if squared else 0.0
    return recall, fpr, brier, len(rows)


# --------------------------------------------------------------------------- latency


def latency_stats(model_tag: str, game_ids: list[int]) -> dict:
    """p50/p90/p95/max over COMPLETED calls only; the >40s/>58s share over ALL attempts.

    A timed-out call has no real completion latency (we gave up at `MEASURE_TIMEOUT`), so
    mixing it into the percentile column would report an artefact of our own probe's
    ceiling, not the model's speed. It unambiguously exceeded both thresholds, though, so
    it belongs in the "share that would have missed the window" denominator.
    """
    completed = []
    attempts = 0
    untimed = 0  # legacy-cache reuse: no timing recorded, excluded from the window share too
    over_40 = over_58 = 0
    for game_id in game_ids:
        for prompt_tag in ("anchor", "unanchor"):
            blob = _blob(game_id, model_tag, prompt_tag)
            if blob is None:
                continue
            attempts += 1
            lat = blob.get("latency_s")
            if blob.get("error"):
                over_40 += 1
                over_58 += 1
                continue
            if lat is None:
                untimed += 1
                continue  # legacy-cache reuse: no timing recorded
            completed.append(lat)
            if lat > 40.0:
                over_40 += 1
            if lat > 58.0:
                over_58 += 1
    if not completed:
        return {"n": 0, "attempts": attempts}
    completed.sort()

    def pct(p):
        idx = min(int(p * len(completed)), len(completed) - 1)
        return completed[idx]

    denom = attempts - untimed
    return {
        "n": len(completed), "attempts": attempts,
        "p50": pct(0.5), "p90": pct(0.9), "p95": pct(0.95), "max": completed[-1],
        "over_40s": over_40 / denom if denom else 0.0,
        "over_58s": over_58 / denom if denom else 0.0,
    }


def error_counts(model_tag: str, game_ids: list[int]) -> dict:
    n = errs = timeouts = parse_errs = 0
    for game_id in game_ids:
        for prompt_tag in ("anchor", "unanchor"):
            blob = _blob(game_id, model_tag, prompt_tag)
            if blob is None:
                continue
            n += 1
            if blob.get("error"):
                errs += 1
                if "Timeout" in blob["error"] or "timed out" in blob["error"].lower():
                    timeouts += 1
            if blob.get("parse_error"):
                parse_errs += 1
    return {"n": n, "errors": errs, "timeouts": timeouts, "parse_errors": parse_errs}


# --------------------------------------------------------------------------- euros


def euro_report(submissions: dict, game_ids: list[int]) -> dict[str, dict[int, float]]:
    nets: dict[str, dict[int, float]] = {m: {} for m in MODELS}
    for game_id in game_ids:
        if game_id not in submissions:
            continue
        try:
            snap = snapshot(game_id)
        except Exception:
            continue
        for model_tag in MODELS:
            sub = submissions[game_id].get(model_tag)
            if not sub:
                continue
            nets[model_tag][game_id] = replay(snap, sub).net
    return nets


def _fmt_delta(base: dict[int, float], other: dict[int, float], games: list[int]) -> tuple[float, float, int]:
    common = [g for g in games if g in base and g in other]
    total_base = sum(base[g] for g in common)
    total_other = sum(other[g] for g in common)
    return total_other - total_base, total_other, len(common)


def noise_floor(n: int) -> float:
    return NOISE_FLOOR_30 * math.sqrt(n / 30.0)


# --------------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-32")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))

    print(f"Scoring Games {game_ids[0]}-{game_ids[-1]} ({len(game_ids)} Games)\n")

    rows, submissions = build_rows(game_ids)

    print("=== coverage of the sample ===")
    for m in MODELS:
        print(f"  {m:6s} ({MODEL_NAMES[m]:14s}): {len(rows[m])} priced Line Item rows")
    print()

    print("=== latency (real Case prompts, per model call) ===")
    for m in MODELS:
        stats = latency_stats(m, game_ids)
        errs = error_counts(m, game_ids)
        if stats["n"] == 0:
            print(f"  {m:6s}: no successful calls yet")
            continue
        print(
            f"  {m:6s}  n={stats['n']:3d}  p50={stats['p50']:6.2f}s  p90={stats['p90']:6.2f}s  "
            f"p95={stats['p95']:6.2f}s  max={stats['max']:6.2f}s  "
            f">40s={stats['over_40s']:5.1%}  >58s={stats['over_58s']:5.1%}   "
            f"(calls={errs['n']} errors={errs['errors']} timeouts={errs['timeouts']} parse_err={errs['parse_errors']})"
        )
    print()

    print("=== RMSLE against recovered Fair Value (post-combine evidence: model blend + memory) ===")
    print("(population definitions match scripts/leak_sigma.py -- the source of the '0.80' figure in src/pricing.py)")
    print(f"  {'model':6s} {'real money (t_lo>0, bounded) -- THE headline number':52s}")
    for m in MODELS:
        b = rmsle_report(log_errors(rows[m], population="real_money"))
        print(f"  {m:6s} {b}")
    print(f"\n  {'model':6s} {'worthless-but-bounded (t_lo<=0) -- uneconomic, payoff-irrelevant':60s}")
    for m in MODELS:
        w = rmsle_report(log_errors(rows[m], population="worthless"))
        print(f"  {m:6s} {w}")
    print(f"\n  {'model':6s} {'censored (t_hi=inf) -- optimistic use of t_lo, per CLAUDE.md':55s}")
    for m in MODELS:
        c = rmsle_report(log_errors(rows[m], population="censored"))
        print(f"  {m:6s} {c}")
    print()

    print("=== RMSLE, model-only (Channel C alone, before the Price Memory blend), real-money population ===")
    for m in MODELS:
        b = rmsle_report(log_errors(rows[m], population="real_money", use_model_only=True))
        print(f"  {m:6s} {b}")
    print()

    print("=== band calibration: RMSLE by the model's own sigma tercile (t_lo > 0 rows only) ===")
    for m in MODELS:
        real_money = [r for r in rows[m] if r.bounded and r.t_lo > 0]
        if len(real_money) < 6:
            print(f"  {m:6s}: too few bounded real-money rows ({len(real_money)})")
            continue
        sigmas = sorted(r.sigma for r in real_money)
        q1, q2 = sigmas[len(sigmas) // 3], sigmas[2 * len(sigmas) // 3]
        narrow = [r for r in real_money if r.sigma < q1]
        mid = [r for r in real_money if q1 <= r.sigma < q2]
        wide = [r for r in real_money if r.sigma >= q2]
        rn = rmsle_report([math.log(max(r.median, ZERO_FLOOR) / r.t) for r in narrow])
        rm = rmsle_report([math.log(max(r.median, ZERO_FLOOR) / r.t) for r in mid])
        rw = rmsle_report([math.log(max(r.median, ZERO_FLOOR) / r.t) for r in wide])
        print(f"  {m:6s} narrow(<{q1:.2f}): {rn}")
        print(f"  {'':6s} mid   :            {rm}")
        print(f"  {'':6s} wide(>={q2:.2f}):  {rw}")
        ordered = "ordered correctly (narrow < wide)" if narrow and wide else "n/a"
        print()
    print()

    print("=== coverage confusion at COVERAGE_FLOOR=2/3 (truth: t_lo<=0 is worthless) ===")
    print(f"  {'model':6s} {'recall':>8s} {'false_pos':>10s} {'brier':>8s} {'n':>6s}")
    for m in MODELS:
        recall, fpr, brier, n = coverage_confusion(rows[m])
        print(f"  {m:6s} {recall:8.1%} {fpr:10.1%} {brier:8.3f} {n:6d}")
    print()

    print("=== euros: replay each model's submission against the real Field ===")
    nets = euro_report(submissions, game_ids)
    common_games = sorted(set(nets["mini"]) & set(nets["terra"]) & set(nets["luna"]))
    print(f"  common Games scored (all 3 models produced a submission): {len(common_games)}")
    for m in MODELS:
        total = sum(nets[m].get(g, 0.0) for g in common_games)
        print(f"  {m:6s} total net over {len(common_games)} Games: {total:,.2f}")
    if common_games:
        nf = noise_floor(len(common_games))
        print(f"  noise floor for n={len(common_games)}: +/-{nf:,.0f} (scaled from +/-34,369 over 30 Games)")
        for m in ("terra", "luna"):
            delta, total, n = _fmt_delta(nets["mini"], nets[m], common_games)
            flag = "INSIDE noise floor" if abs(delta) < nf else "OUTSIDE noise floor"
            print(f"  delta {m} - mini: {delta:+,.2f} over {n} Games  [{flag}]")

        print("\n  held-out splits (sign consistency, not a fit):")
        odd = [g for g in common_games if g % 2 == 1]
        even = [g for g in common_games if g % 2 == 0]
        first = [g for g in common_games if g <= 20]
        second = [g for g in common_games if g > 20]
        for label, subset in (("odd", odd), ("even", even), ("1-20", first), ("21+", second)):
            if not subset:
                continue
            nf_s = noise_floor(len(subset))
            line = f"    {label:6s} (n={len(subset):2d}, floor +/-{nf_s:,.0f}):"
            for m in ("terra", "luna"):
                delta, _, _ = _fmt_delta(nets["mini"], nets[m], subset)
                line += f"  {m}={delta:+,.0f}"
            print(line)

        print("\n  per-Game net (mini / terra / luna):")
        for g in common_games:
            print(
                f"    G{g:3d}  mini={nets['mini'].get(g, float('nan')):11,.2f}  "
                f"terra={nets['terra'].get(g, float('nan')):11,.2f}  "
                f"luna={nets['luna'].get(g, float('nan')):11,.2f}"
            )

    # dump machine-readable summary
    out = {
        "games": game_ids,
        "common_games": common_games,
        "nets": nets,
        "latency": {m: latency_stats(m, game_ids) for m in MODELS},
        "errors": {m: error_counts(m, game_ids) for m in MODELS},
        "rmsle_real_money": {
            m: {
                "n": len(log_errors(rows[m], population="real_money")),
                "rmsle": math.sqrt(st.fmean(e * e for e in log_errors(rows[m], population="real_money"))) if log_errors(rows[m], population="real_money") else None,
                "bias": st.fmean(log_errors(rows[m], population="real_money")) if log_errors(rows[m], population="real_money") else None,
            }
            for m in MODELS
        },
        "coverage": {
            m: dict(zip(("recall", "false_positive", "brier", "n"), coverage_confusion(rows[m])))
            for m in MODELS
        },
    }
    out_path = CACHE / "score_summary.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nMachine-readable summary written to {out_path}")


if __name__ == "__main__":
    main()
