"""Model bake-off RETEST, stage 2: score the draws in `retest_draw.py`'s cache.

Answers, under the CURRENT `ENSEMBLE_PROMPTS` (the two prompt fixes that shipped tonight
at 21:53 and 23:38 are both live in every draw this script reads): does `gpt-5.6-terra`
beat the shipped `gpt-5.4-mini`; does the answer differ on the expensive tail
(`t >= 1,000`, the population we are measurably worst on); and is terra's latency
survivable inside the live `LLM_TIMEOUT_SECONDS` budget.

Mirrors the live pricing path exactly, not just `request_evidence`: `blend()` the two
ensemble draws, `combine()` with a **pinned** snapshot of Price Memory (see `--pin-memory`;
the live store rebuilds every settled Game, so a moving target would make Games scored
early in this run silently disagree with Games scored late), `price_item()` with the same
`memory_backed` condition `strategy2.strategy.build_proposal` uses, and the same
`_uninformed_price` (`STANDARD_CHARGE`/`STANDARD_LIMIT`) fallback for a Line Item neither
channel could price.

Scoring is **paired**: every reported population (headline, expensive tail, photo /
no-photo) is restricted to Line Items where *both* mini and terra returned usable model
evidence, so a difference in which Cases happened to time out for which model cannot
masquerade as an accuracy difference (this is what nearly invalidated the original
bake-off's headline).

Noise floor: `26,622 x sqrt(n_games / 18)` (CLAUDE.md rule 1b / `sigma-calibration.md`) --
NOT the `34,369-over-30-Games` figure the original bake-off used; that was superseded.

    PYTHONPATH=. pixi run python scripts/experiments/retest_score.py --games 1-42
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import shutil
import statistics as st
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.case_loader import read_case  # noqa: E402
from src.domain.pricing.engine import Evidence, price_item  # noqa: E402
from src.domain.pricing.memory import PriceMemory  # noqa: E402
from src.services.strategies.fast_path import STANDARD_CHARGE, STANDARD_LIMIT  # noqa: E402
from src.services.strategies.strategy2.blend import blend, combine  # noqa: E402
from src.services.strategies.strategy2.channels import (  # noqa: E402
    _MEMORY_COVERAGE,
    unit_of,
    worthless_evidence,
)
from src.services.strategies.strategy2.constants import LLM_TIMEOUT_SECONDS  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay_payoffs import snapshot, replay  # noqa: E402

CACHE = Path("var/experiments/model_bakeoff_retest")
CASES = Path("[PUBLIC] EHL Cases/cases")
INF = math.inf
ZERO_FLOOR = 0.01
NOISE_FLOOR_18 = 26622.0  # over 18 Games; scales as x * sqrt(n / 18)
TAIL_THRESHOLD = 1000.0
LATENCY_BUDGET = LLM_TIMEOUT_SECONDS  # 55.0s, the live budget this was drawn under

MODELS = ("mini", "terra")
MODEL_NAMES = {"mini": "gpt-5.4-mini", "terra": "gpt-5.6-terra"}
BUCKETS = [(1, 5), (6, 10), (11, 20), (21, 999)]


def noise_floor(n: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(n / 18.0)


# --------------------------------------------------------------------------- cache access


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
    draws = [
        _evidence_dict(_blob(game_id, model_tag, "anchor")),
        _evidence_dict(_blob(game_id, model_tag, "unanchor")),
    ]
    return blend(draws)


_CASE_CACHE: dict[int, object] = {}


def get_case(game_id: int):
    if game_id not in _CASE_CACHE:
        case_dir = CASES / f"case_{game_id:02d}"
        if not (case_dir / "policy.txt").exists():
            _CASE_CACHE[game_id] = None
        else:
            _CASE_CACHE[game_id] = asyncio.run(read_case(game_id, case_dir))
    return _CASE_CACHE[game_id]


def memory_evidence(game_id: int, pinned: PriceMemory) -> dict[int, Evidence]:
    """Channels A+B against a PINNED PriceMemory snapshot -- never the live-refreshing one."""
    case = get_case(game_id)
    if case is None:
        return {}
    found: dict[int, Evidence] = {}
    for li in case.line_items:
        if getattr(li, "quantity_missing", False):
            found[li.index] = worthless_evidence(li.index)
            continue
        hit = pinned.lookup(li.name, unit=unit_of(li.name), quantity=max(li.quantity, 1.0))
        if hit is None:
            continue
        found[li.index] = Evidence(
            index=li.index,
            coverage_probability=_MEMORY_COVERAGE,
            price_low=hit.low,
            price_median=hit.median,
            price_high=hit.high,
        )
    return found


# --------------------------------------------------------------------------- rows / submissions


class Row:
    __slots__ = (
        "game", "index", "model", "t_lo", "t_hi", "median", "sigma",
        "model_coverage", "charge", "limit", "has_photo", "model_only_median",
    )

    def __init__(
        self, game, index, model, t_lo, t_hi, median, sigma, model_coverage, charge, limit,
        has_photo, model_only_median,
    ):
        self.game = game
        self.index = index
        self.model = model
        self.t_lo = t_lo
        self.t_hi = t_hi
        self.median = median
        self.sigma = sigma
        self.model_coverage = model_coverage
        self.charge = charge
        self.limit = limit
        self.has_photo = has_photo
        #: `from_model.price_median` -- Channel C ALONE, before the Price Memory `combine()`.
        #: Price Memory folds in the settled Fair Value of every Game once it settles
        #: (README rule 10), so for a Case whose own Game has already settled (as Case 41
        #: has, by the time this retest ran), the post-combine number is not a clean read of
        #: what the model alone saw -- it can be pulled toward (or past) the truth by a
        #: same-wording memory hit that already knows the answer. This field isolates the
        #: model's raw call so that contamination is visible rather than silently blended in.
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


def build_submission(game_id: int, model_tag: str, pinned: PriceMemory):
    """Exactly `strategy2.strategy.build_proposal`'s per-item logic, for one model's evidence."""
    case = get_case(game_id)
    if case is None:
        return None, {}
    mdl = model_evidence(game_id, model_tag)
    mem = memory_evidence(game_id, pinned)
    submission: dict[int, tuple[float, float]] = {}
    from_model_by_index: dict[int, Evidence | None] = {}
    filled_median_by_index: dict[int, float] = {}
    sigma_by_index: dict[int, float] = {}
    for li in case.line_items:
        from_model = mdl.get(li.index)
        from_memory = mem.get(li.index)
        evidence = combine(from_model, from_memory)
        uncovered = bool(getattr(li, "quantity_missing", False))
        from_model_by_index[li.index] = from_model
        if evidence is None:
            submission[li.index] = (STANDARD_CHARGE, STANDARD_LIMIT)
            continue
        price = price_item(
            evidence,
            confirmed_uncovered=uncovered,
            memory_backed=from_memory is not None and not uncovered,
        )
        submission[li.index] = (price.charge, price.limit)
        filled_median_by_index[li.index] = evidence.with_defaults().price_median
        sigma_by_index[li.index] = price.sigma
    return submission, {
        "from_model": from_model_by_index,
        "median": filled_median_by_index,
        "sigma": sigma_by_index,
        "has_photo": bool(case.image_paths),
    }


def _model_only_median(evidence: Evidence | None) -> float:
    return evidence.price_median if evidence is not None else 0.0


def build_rows(game_ids: list[int], pinned: PriceMemory):
    rows: dict[str, list[Row]] = {m: [] for m in MODELS}
    submissions: dict[int, dict[str, dict[int, tuple[float, float]]]] = {}
    for game_id in game_ids:
        try:
            snap = snapshot(game_id)
        except Exception as exc:  # noqa: BLE001
            print(f"  g{game_id:02d}: snapshot unusable ({exc}); skipped", file=sys.stderr)
            continue
        submissions[game_id] = {}
        for model_tag in MODELS:
            sub, meta = build_submission(game_id, model_tag, pinned)
            if sub is None:
                continue
            submissions[game_id][model_tag] = sub
            for index in snap.line_items:
                from_model = meta["from_model"].get(index)
                if from_model is None or index not in meta["median"]:
                    continue
                lo, hi = snap.fair_brackets.get(index, (0.0, INF))
                rows[model_tag].append(
                    Row(
                        game=game_id, index=index, model=model_tag,
                        t_lo=lo, t_hi=hi,
                        median=meta["median"][index], sigma=meta["sigma"][index],
                        model_coverage=from_model.coverage_probability,
                        charge=sub[index][0], limit=sub[index][1],
                        has_photo=meta["has_photo"],
                        model_only_median=_model_only_median(from_model),
                    )
                )
    return rows, submissions


def paired_keys(rows: dict[str, list[Row]]) -> set[tuple[int, int]]:
    """(game, index) keys present for BOTH models -- both had usable model evidence."""
    keys_by_model = {m: {(r.game, r.index) for r in rows[m]} for m in MODELS}
    return keys_by_model["mini"] & keys_by_model["terra"]


# --------------------------------------------------------------------------- RMSLE


def log_errors(
    rows: list[Row], keys: set[tuple[int, int]], *, real_money: bool, tail: bool | None = None,
    photo: bool | None = None, use_model_only: bool = False,
) -> list[float]:
    out = []
    for r in rows:
        if (r.game, r.index) not in keys:
            continue
        if real_money and not (r.t_lo > 0):
            continue
        if tail is True and r.t < TAIL_THRESHOLD:
            continue
        if tail is False and r.t >= TAIL_THRESHOLD:
            continue
        if photo is True and not r.has_photo:
            continue
        if photo is False and r.has_photo:
            continue
        t = r.t
        median = r.model_only_median if use_model_only else r.median
        if t <= 0 or median <= 0:
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


def sign_test(a_errs: list[float], b_errs: list[float]) -> tuple[int, int, int]:
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
    if n == 0:
        return 1.0
    from math import comb
    k = min(k, n - k)
    total = sum(comb(n, i) for i in range(0, k + 1))
    return min(total * 2 / (2 ** n), 1.0)


# --------------------------------------------------------------------------- latency


def item_counts(game_ids: list[int]) -> dict[int, int]:
    out = {}
    for g in game_ids:
        case = get_case(g)
        if case is None:
            continue
        out[g] = len(case.line_items)
    return out


def bucket_of(n: int) -> str:
    for lo, hi in BUCKETS:
        if lo <= n <= hi:
            return f"{lo}-{hi}" if hi != 999 else f"{lo}+"
    return "?"


def latency_stats(model_tag: str, games: list[int]) -> dict:
    completed, timeouts, n_calls = [], 0, 0
    for g in games:
        for prompt_tag in ("anchor", "unanchor"):
            blob = _blob(g, model_tag, prompt_tag)
            if blob is None:
                continue
            n_calls += 1
            if blob.get("error"):
                timeouts += 1
                continue
            lat = blob.get("latency_s")
            if lat is None:
                continue
            completed.append(lat)
    if not completed and n_calls == 0:
        return {"n_calls": 0}
    completed.sort()

    def pct(p):
        if not completed:
            return float("nan")
        return completed[min(int(p * len(completed)), len(completed) - 1)]

    over_budget = timeouts + sum(1 for x in completed if x > LATENCY_BUDGET)
    return {
        "n_calls": n_calls, "n_completed": len(completed), "timeouts": timeouts,
        "p50": pct(0.5), "p95": pct(0.95),
        "max": completed[-1] if completed else float("nan"),
        "over_budget_rate": over_budget / n_calls if n_calls else 0.0,
    }


def latency_report(game_ids: list[int]) -> None:
    counts = item_counts(game_ids)
    print(f"=== latency by Line Item count, budget={LATENCY_BUDGET:.0f}s (the live LLM_TIMEOUT_SECONDS) ===")
    header = f"  {'model':6s} {'bucket':7s} {'calls':>6s} {'timeouts':>9s} {'>budget':>8s} {'p50':>7s} {'p95':>7s} {'max':>7s}"
    print(header)
    for m in MODELS:
        for lo, hi in BUCKETS:
            label = f"{lo}-{hi}" if hi != 999 else f"{lo}+"
            games = [g for g in game_ids if lo <= counts.get(g, -1) <= hi]
            s = latency_stats(m, games)
            if s.get("n_calls", 0) == 0:
                continue
            print(
                f"  {m:6s} {label:7s} {s['n_calls']:6d} {s['timeouts']:9d} "
                f"{s['over_budget_rate']:7.1%} {s['p50']:7.1f} {s['p95']:7.1f} {s['max']:7.1f}"
            )
        s = latency_stats(m, game_ids)
        print(
            f"  {m:6s} {'ALL':7s} {s['n_calls']:6d} {s['timeouts']:9d} "
            f"{s['over_budget_rate']:7.1%} {s['p50']:7.1f} {s['p95']:7.1f} {s['max']:7.1f}"
        )
        print()


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


def _delta(base, other, games):
    common = [g for g in games if g in base and g in other]
    return sum(other[g] for g in common) - sum(base[g] for g in common), len(common)


# --------------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-42")
    parser.add_argument(
        "--pin-memory", default=None,
        help="path to a pinned var/price_memory.json snapshot; default pins the CURRENT live "
             "store to var/experiments/model_bakeoff_retest/price_memory_pinned.json now",
    )
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))

    if args.pin_memory:
        pin_path = Path(args.pin_memory)
    else:
        CACHE.mkdir(parents=True, exist_ok=True)
        pin_path = CACHE / "price_memory_pinned.json"
        if not pin_path.exists():
            live = Path("var/price_memory.json")
            shutil.copy2(live, pin_path)
            print(f"Pinned var/price_memory.json -> {pin_path} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    pinned = PriceMemory.load(pin_path)
    pin_stat = pin_path.stat()
    print(
        f"Price Memory vintage pinned: {pin_path} ({len(pinned)} entries, "
        f"mtime {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(pin_stat.st_mtime))})\n"
    )

    print(f"Scoring Games {game_ids[0]}-{game_ids[-1]} ({len(game_ids)} Games)\n")

    rows, submissions = build_rows(game_ids, pinned)
    for m in MODELS:
        print(f"  {m:6s} ({MODEL_NAMES[m]}): {len(rows[m])} rows with usable model evidence")
    keys = paired_keys(rows)
    print(f"  paired Line Items (both models spoke): {len(keys)}\n")

    latency_report(game_ids)

    print("=== paired RMSLE against recovered Fair Value (post-blend + pinned-memory-combine, post-price_item's with_defaults) ===")
    print(f"  {'population':45s} {'mini':45s} {'terra':45s}")
    for label, kwargs in (
        ("real money, ALL (t_lo>0)", dict(real_money=True)),
        ("real money, expensive tail (t>=1000)", dict(real_money=True, tail=True)),
        ("real money, below tail (t<1000)", dict(real_money=True, tail=False)),
        ("real money, Case HAS a photo", dict(real_money=True, photo=True)),
        ("real money, Case has NO photo", dict(real_money=True, photo=False)),
    ):
        mini_e = log_errors(rows["mini"], keys, **kwargs)
        terra_e = log_errors(rows["terra"], keys, **kwargs)
        print(f"  {label:45s}")
        print(f"    mini : {rmsle_report(mini_e)}")
        print(f"    terra: {rmsle_report(terra_e)}")
        if mini_e and terra_e and len(mini_e) == len(terra_e):
            a_win, tie, b_win = sign_test(mini_e, terra_e)
            n = a_win + b_win
            p = binom_two_sided_p(a_win, n) if n else 1.0
            print(f"    sign test: mini better {a_win} / tie {tie} / terra better {b_win}  (p={p:.3f})")
        print()

    print(
        "=== MODEL-ONLY RMSLE (Channel C alone, pre-combine -- immune to Price Memory "
        "leaking a Case's own already-settled Fair Value back into its own score) ==="
    )
    for label, kwargs in (
        ("real money, ALL (t_lo>0)", dict(real_money=True)),
        ("real money, expensive tail (t>=1000)", dict(real_money=True, tail=True)),
    ):
        mini_e = log_errors(rows["mini"], keys, use_model_only=True, **kwargs)
        terra_e = log_errors(rows["terra"], keys, use_model_only=True, **kwargs)
        print(f"  {label:45s}")
        print(f"    mini : {rmsle_report(mini_e)}")
        print(f"    terra: {rmsle_report(terra_e)}")
        print()

    print("=== euros: replay each model's submission (with STANDARD-constant fallback) against the real Field ===")
    nets = euro_report(submissions, game_ids)
    common = sorted(set(nets["mini"]) & set(nets["terra"]))
    print(f"  common Games scored by both: {len(common)}  ({common})")
    for m in MODELS:
        total = sum(nets[m].get(g, 0.0) for g in common)
        print(f"  {m:6s} total net: {total:,.2f}")
    if common:
        nf = noise_floor(len(common))
        d, n = _delta(nets["mini"], nets["terra"], common)
        flag = "INSIDE noise floor" if abs(d) < nf else "OUTSIDE noise floor"
        print(f"  noise floor for n={n}: +/-{nf:,.0f}  (26,622 x sqrt(n/18))")
        print(f"  delta terra - mini: {d:+,.2f}  [{flag}]")

        print("\n  held-out folds (sign consistency, not a fit):")
        odd = [g for g in common if g % 2 == 1]
        even = [g for g in common if g % 2 == 0]
        first = [g for g in common if g <= 20]
        second = [g for g in common if g > 20]
        for label, subset in (("odd", odd), ("even", even), ("1-20", first), ("21+", second)):
            if not subset:
                continue
            nf_s = noise_floor(len(subset))
            d_s, n_s = _delta(nets["mini"], nets["terra"], subset)
            flag = "inside floor" if abs(d_s) < nf_s else "OUTSIDE floor"
            print(f"    {label:6s} (n={n_s:2d}, floor +/-{nf_s:,.0f}): terra-mini={d_s:+,.0f}  [{flag}]")

        print("\n  per-Game net (mini / terra):")
        for g in common:
            print(f"    G{g:3d}  mini={nets['mini'].get(g, float('nan')):11,.2f}  terra={nets['terra'].get(g, float('nan')):11,.2f}")

    out = {
        "games": game_ids,
        "common_games": common,
        "nets": nets,
        "pinned_memory": str(pin_path),
    }
    out_path = CACHE / "score_summary.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nMachine-readable summary written to {out_path}")


if __name__ == "__main__":
    main()
