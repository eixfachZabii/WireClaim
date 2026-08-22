"""Model bake-off RETEST, stage 2: score mini vs terra under the CURRENT (corrected) prompt.

The earlier bake-off (`model_bakeoff_score.py`, `docs/.../model-bakeoff.md`) drew its cache
between 21:48 and 22:20, **before** both prompt fixes landed -- the settled price anchors
(21:53) and `_DISTRIBUTION_HINT`'s real quartiles (23:38, median 59 -> 97, top decile
"several thousand" -> named quartiles running to 11,131). Every number in that report answers
a prompt that is no longer shipping. `retest_draw.py` re-drew all 44 extracted Cases through
today's live `ENSEMBLE_PROMPTS`; this scores them.

What is measured, and how it is kept honest:

* **RMSLE with level and dispersion apart** (CLAUDE.md rule 10 -- a stdev cannot see a level
  error), on three populations kept strictly separate:
    real_money  bounded bracket AND t_lo > 0 -- the only population price accuracy can move
                the payoff on, and the one the standing 0.77 model-only figure measures.
    censored    t_hi == inf -- `t` defaults to the lower bound, so every error here is
                **optimistic by construction**; reported, never pooled into the headline.
    worthless   bounded AND t_lo == 0 -- coverage should already have zeroed the Limit.
* **The expensive tail (`t >= 1000`) reported separately**, since that is where the estimator
  is measurably worst and where the euros are.
* **Paired RMSLE + an exact two-sided sign test** on the Line Items where BOTH models spoke,
  so the comparison is not confounded by which Cases each happened to complete.
* **Euros through the real path** -- `blend` the two framings, `combine` with Price Memory,
  `price_item`, `replay_payoffs.replay` against the real Field -- with odd/even and
  early/late held-out folds and the 26,622-per-18-Games noise floor beside every delta.
* **Band calibration**: does the asserted width order the error? Reported per sigma tercile,
  because `engine.py`'s docstring names exactly that as `CHARGE_SLOPE`'s own falsifier.

Price Memory vintage is pinned: `combine` reads whatever `var/price_memory.json` holds when
this runs, and that store is rebuilt every settled Game by `learn_watch`. The pinned copy
under `scripts/experiments/pinned/` is used when `--pinned-memory` is passed so a re-run
weeks later reproduces. NOTE the look-ahead this carries either way: Price Memory built from
all settled Games contains the Games being replayed. Every *comparison* here is between two
models sharing the identical memory channel, so it cancels; the absolute totals do not, and
are labelled as such.

    PYTHONPATH=. pixi run python scripts/experiments/retest_score.py
    PYTHONPATH=. pixi run python scripts/experiments/retest_score.py --pinned-memory
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics as st
import sys
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.data.case_loader import read_case  # noqa: E402
from src.pricing.engine import Evidence, implied_sigma, price_item  # noqa: E402
from src.evidence.memory import PriceMemory  # noqa: E402
import src.evidence.memory as memory_module  # noqa: E402
from src.strategies.strategy2.blend import blend, combine  # noqa: E402
from src.strategies.strategy2.channels import local_evidence  # noqa: E402

from replay_payoffs import replay, snapshot  # noqa: E402

RETEST = ROOT / "var" / "experiments" / "model_bakeoff_retest"
CASES = ROOT / "[PUBLIC] EHL Cases" / "cases"
PINNED = ROOT / "scripts" / "experiments" / "pinned" / "price_memory_vintage_g38.json"
INF = math.inf
NOISE_FLOOR_18 = 26622.0
MODELS = ("mini", "terra")


def load_draw(game_id: int, model_tag: str, prompt_tag: str) -> dict[int, Evidence]:
    path = RETEST / f"case_{game_id:02d}_{model_tag}_{prompt_tag}.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {
        int(i): Evidence(
            index=int(i),
            coverage_probability=v.get("coverage_probability", 0.9),
            price_low=v.get("price_low", 0.0),
            price_median=v.get("price_median", 0.0),
            price_high=v.get("price_high", 0.0),
        )
        for i, v in (payload.get("items") or {}).items()
    }


def ensemble(game_id: int, model_tag: str) -> dict[int, Evidence]:
    """Both framings blended, exactly as `strategy2.strategy.propose` does it live."""
    return blend([load_draw(game_id, model_tag, "anchor"), load_draw(game_id, model_tag, "unanchor")])


def latencies(model_tag: str) -> list[float]:
    out = []
    for path in RETEST.glob(f"case_*_{model_tag}_*.json"):
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if payload.get("error") is None and payload.get("latency_s") is not None:
            out.append(payload["latency_s"])
    return sorted(out)


def failure_counts(model_tag: str) -> tuple[int, int, int]:
    """(calls, transport errors, parse failures) across every cached draw for this model."""
    calls = errors = parse_fails = 0
    for path in RETEST.glob(f"case_*_{model_tag}_*.json"):
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        calls += 1
        if payload.get("error"):
            errors += 1
        elif payload.get("parse_error") or not payload.get("items"):
            parse_fails += 1
    return calls, errors, parse_fails


class Row:
    __slots__ = ("game", "index", "t_lo", "t_hi", "median", "sigma", "coverage", "name")

    def __init__(self, game, index, t_lo, t_hi, median, sigma, coverage, name):
        self.game, self.index = game, index
        self.t_lo, self.t_hi = t_lo, t_hi
        self.median, self.sigma, self.coverage, self.name = median, sigma, coverage, name

    @property
    def t(self) -> float:
        return self.t_lo if self.t_hi == INF else (self.t_lo + self.t_hi) / 2.0

    @property
    def bounded(self) -> bool:
        return self.t_hi != INF

    @property
    def real_money(self) -> bool:
        return self.bounded and self.t_lo > 0


def build(games: list[int]) -> tuple[dict[str, list[Row]], dict[str, dict[int, dict]]]:
    rows: dict[str, list[Row]] = {m: [] for m in MODELS}
    submissions: dict[str, dict[int, dict]] = {m: {} for m in MODELS}
    for game_id in games:
        try:
            snap = snapshot(game_id)
        except Exception:
            continue
        case_dir = CASES / f"case_{game_id:02d}"
        if not (case_dir / "policy.txt").exists():
            continue
        case = asyncio.run(read_case(game_id, case_dir))
        mem = local_evidence(case)
        meta = {li.index: (li.name, bool(getattr(li, "quantity_missing", False))) for li in case.line_items}

        for model_tag in MODELS:
            model = ensemble(game_id, model_tag)
            if not model:
                continue
            submission: dict[int, tuple[float, float]] = {}
            for index in snap.line_items:
                evidence = combine(model.get(index), mem.get(index))
                if evidence is None:
                    continue
                name, uncovered = meta.get(index, ("", False))
                price = price_item(
                    evidence,
                    confirmed_uncovered=uncovered,
                    memory_backed=mem.get(index) is not None and not uncovered,
                )
                submission[index] = (price.charge, price.limit)
                lo, hi = snap.fair_brackets.get(index, (0.0, INF))
                filled = evidence.with_defaults()
                rows[model_tag].append(
                    Row(game_id, index, lo, hi, filled.price_median, price.sigma,
                        price.covered_probability, name)
                )
            if submission:
                submissions[model_tag][game_id] = {"snap": snap, "submission": submission}
    return rows, submissions


def stat_line(errs: list[float]) -> str:
    if not errs:
        return "n=  0"
    rmsle = math.sqrt(st.fmean(e * e for e in errs))
    return (f"n={len(errs):3d}  RMSLE={rmsle:.3f}  bias={st.fmean(errs):+.3f}  "
            f"dispersion={st.pstdev(errs) if len(errs) > 1 else 0.0:.3f}")


def errors_of(rows: list[Row], population: str, *, tail: bool = False) -> list[float]:
    out = []
    for r in rows:
        if population == "real_money" and not r.real_money:
            continue
        if population == "censored" and r.bounded:
            continue
        if population == "worthless" and not (r.bounded and r.t_lo <= 0):
            continue
        if r.t <= 0 or r.median <= 0:
            continue
        if tail and r.t < 1000:
            continue
        out.append(math.log(r.median / r.t))
    return out


def binom_two_sided(k: int, n: int) -> float:
    if n == 0:
        return 1.0
    k = min(k, n - k)
    return min(sum(comb(n, i) for i in range(k + 1)) * 2 / (2 ** n), 1.0)


def fold_totals(submissions: dict[str, dict[int, dict]], label: str, games: list[int], detail: bool = False) -> None:
    common = sorted(set(submissions["mini"]) & set(submissions["terra"]) & set(games))
    if not common:
        print(f"  {label:22s} no common Games")
        return
    totals = {}
    for m in MODELS:
        totals[m] = sum(replay(submissions[m][g]["snap"], submissions[m][g]["submission"]).net for g in common)
    nf = NOISE_FLOOR_18 * math.sqrt(len(common) / 18.0)
    delta = totals["terra"] - totals["mini"]
    flag = "inside floor" if abs(delta) < nf else "OUTSIDE floor"
    print(f"  {label:22s} n={len(common):2d}  mini {totals['mini']:>12,.0f}  terra {totals['terra']:>12,.0f}  "
          f"terra-mini {delta:>+11,.0f}  floor +/-{nf:>8,.0f}  [{flag}]")
    if detail:
        # A total is only worth quoting if it is not one Case. Report how many Games move
        # each way and what the total looks like with the single biggest contributor removed.
        per_game = sorted(
            ((replay(submissions["terra"][g]["snap"], submissions["terra"][g]["submission"]).net
              - replay(submissions["mini"][g]["snap"], submissions["mini"][g]["submission"]).net, g)
             for g in common),
            key=lambda kv: -abs(kv[0]),
        )
        wins = sum(1 for d, _ in per_game if d > 0)
        print(f"      terra wins {wins}/{len(per_game)} Games; top movers: "
              + ", ".join(f"g{g:02d} {d:+,.0f}" for d, g in per_game[:5]))
        biggest, g_big = per_game[0]
        print(f"      without g{g_big:02d}: {delta - biggest:+,.0f} over {len(common) - 1} Games "
              f"(floor +/-{NOISE_FLOOR_18 * math.sqrt((len(common) - 1) / 18.0):,.0f})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pinned-memory", action="store_true",
                        help="use scripts/experiments/pinned/price_memory_vintage_g38.json")
    args = parser.parse_args()

    if args.pinned_memory and PINNED.exists():
        memory_module._DEFAULT = PriceMemory.load(PINNED)
        print(f"Price Memory PINNED to {PINNED.name} ({len(memory_module._DEFAULT)} entries)\n")
    else:
        store = memory_module.load()
        print(f"Price Memory LIVE from {store.source} ({len(store)} entries, "
              f"Games {store.games[0] if store.games else '?'}-{store.games[-1] if store.games else '?'})\n")

    games = sorted(
        int(p.name.split("_")[1])
        for p in CASES.iterdir()
        if p.name.startswith("case_") and p.name.split("_")[1].isdigit() and int(p.name.split("_")[1]) > 0
    )
    rows, submissions = build(games)

    print("=" * 100)
    print("RMSLE by population -- current (corrected) prompt, two-draw ensemble, memory blended")
    print("=" * 100)
    for population in ("real_money", "censored", "worthless"):
        print(f"\n  {population}:")
        for m in MODELS:
            print(f"    {m:6s} {stat_line(errors_of(rows[m], population))}")
    print("\n  real_money, EXPENSIVE TAIL t >= 1000:")
    for m in MODELS:
        print(f"    {m:6s} {stat_line(errors_of(rows[m], 'real_money', tail=True))}")
    print("\n  censored (t = t_lo, OPTIMISTIC by construction), t >= 1000:")
    for m in MODELS:
        print(f"    {m:6s} {stat_line(errors_of(rows[m], 'censored', tail=True))}")

    print("\n" + "=" * 100)
    print("Paired: only Line Items where BOTH models spoke (real money)")
    print("=" * 100)
    by_key = {m: {(r.game, r.index): r for r in rows[m] if r.real_money and r.median > 0 and r.t > 0} for m in MODELS}
    shared = sorted(set(by_key["mini"]) & set(by_key["terra"]))
    errs = {m: [math.log(by_key[m][k].median / by_key[m][k].t) for k in shared] for m in MODELS}
    for m in MODELS:
        print(f"  {m:6s} {stat_line(errs[m])}")
    mini_win = sum(1 for a, b in zip(errs["mini"], errs["terra"]) if abs(a) < abs(b) - 1e-9)
    terra_win = sum(1 for a, b in zip(errs["mini"], errs["terra"]) if abs(b) < abs(a) - 1e-9)
    n = mini_win + terra_win
    print(f"  sign test: mini better {mini_win}, terra better {terra_win}, "
          f"n={n}, two-sided p={binom_two_sided(mini_win, n):.4f}")

    tail_keys = [k for k in shared if by_key["mini"][k].t >= 1000]
    if tail_keys:
        print(f"\n  paired EXPENSIVE TAIL (t >= 1000), n={len(tail_keys)}:")
        for m in MODELS:
            print(f"    {m:6s} {stat_line([math.log(by_key[m][k].median / by_key[m][k].t) for k in tail_keys])}")

    print("\n" + "=" * 100)
    print("Band calibration -- does the asserted width order the error? (real money)")
    print("=" * 100)
    for m in MODELS:
        scored = sorted(
            ((r.sigma, abs(math.log(r.median / r.t))) for r in rows[m] if r.real_money and r.median > 0 and r.t > 0),
            key=lambda pair: pair[0],
        )
        if len(scored) < 6:
            continue
        third = len(scored) // 3
        for label, chunk in (("narrow", scored[:third]), ("middle", scored[third:2 * third]), ("wide", scored[2 * third:])):
            rmsle = math.sqrt(st.fmean(e * e for _, e in chunk))
            med_sigma = st.median([s for s, _ in chunk])
            print(f"  {m:6s} {label:7s} n={len(chunk):3d}  median asserted sigma={med_sigma:.3f}  RMSLE={rmsle:.3f}")
        print()

    print("=" * 100)
    print("Euros: replayed against the real Field, held-out folds, noise floor beside each")
    print("=" * 100)
    fold_totals(submissions, "all Games", games, detail=True)
    fold_totals(submissions, "odd", [g for g in games if g % 2 == 1])
    fold_totals(submissions, "even", [g for g in games if g % 2 == 0])
    fold_totals(submissions, "early (1-20)", [g for g in games if g <= 20])
    fold_totals(submissions, "late (21+)", [g for g in games if g > 20])
    fold_totals(submissions, "recent (34+)", [g for g in games if g >= 34])

    print("\n" + "=" * 100)
    print("Latency and reliability (real Case prompts, 55s live budget)")
    print("=" * 100)
    for m in MODELS:
        lat = latencies(m)
        calls, errors, parse_fails = failure_counts(m)
        if not lat:
            continue
        def pct(p):
            return lat[min(int(p * len(lat)), len(lat) - 1)]
        over = sum(1 for x in lat if x > 55.0)
        print(f"  {m:6s} calls={calls:3d}  transport_err={errors:2d}  parse/empty={parse_fails:2d}  "
              f"p50={pct(0.5):5.1f}s  p95={pct(0.95):5.1f}s  max={lat[-1]:5.1f}s  over_55s={over}")

    print("\n" + "=" * 100)
    print("Game 41 item 3 -- the tourbillon watch (true t >= 11,131)")
    print("=" * 100)
    for m in MODELS:
        for prompt_tag in ("anchor", "unanchor"):
            item = load_draw(41, m, prompt_tag).get(3)
            if item:
                print(f"  {m:6s} {prompt_tag:9s} median={item.price_median:10.2f}  "
                      f"band=[{item.price_low:.0f}, {item.price_high:.0f}]  cov={item.coverage_probability:.2f}")
        ens = ensemble(41, m).get(3)
        if ens:
            print(f"  {m:6s} {'ENSEMBLE':9s} median={ens.price_median:10.2f}  "
                  f"band=[{ens.price_low:.0f}, {ens.price_high:.0f}]  "
                  f"implied_sigma={implied_sigma(ens.price_low, ens.price_median, ens.price_high):.3f}")

    print("\n" + "=" * 100)
    print("Worst under-prices on the expensive tail (real money, t >= 1000), per model")
    print("=" * 100)
    for m in MODELS:
        bad = sorted(
            (r for r in rows[m] if r.real_money and r.t >= 1000 and r.median > 0),
            key=lambda r: math.log(r.median / r.t),
        )[:10]
        print(f"\n  {m}:")
        for r in bad:
            print(f"    g{r.game:02d}#{r.index:<3d} t={r.t:9.2f}  t_hat={r.median:9.2f}  "
                  f"log_err={math.log(r.median / r.t):+.2f}  {r.name[:52]}")


if __name__ == "__main__":
    main()
