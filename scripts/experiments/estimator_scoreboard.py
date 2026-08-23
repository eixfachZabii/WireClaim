"""Score the vision-ablation and grade-prompt drops against ground truth and against each
other, single anchor-prompt draw vs single anchor-prompt draw so exactly one variable moves
at a time:

    vision effect  = retest_draw's cached <model>_anchor (photo ON)  vs  vision_ablation's
                      <model>_nophoto (same model, same prompt text, photo OFF)
    grade effect   = retest_draw's cached <model>_anchor (baseline prompt, photo ON)  vs
                      grade_prompt's <model>_grade (grade-first prompt, photo ON)

RMSLE is reported on the real-money population (bounded, t_lo > 0) overall and on t >= 1000
separately (CLAUDE.md rule: report level and dispersion apart, and never pool the censored
tail into the headline). Euro deltas run the SAME curated Case list through `combine()` with
the live Price Memory channel (so the reported number matches what would actually have been
submitted) and `price_item()` / `replay_payoffs.replay()` against the real Field, with the
26,622-per-18-Games noise floor scaled to the sample size actually available.

    PYTHONPATH=. pixi run python scripts/experiments/estimator_scoreboard.py
"""

from __future__ import annotations

import json
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.pricing.engine import Evidence, price_item  # noqa: E402
from src.strategies.strategy2.blend import combine  # noqa: E402
from src.strategies.strategy2.channels import local_evidence  # noqa: E402

from replay_payoffs import snapshot, replay  # noqa: E402

RETEST = ROOT / "var" / "experiments" / "model_bakeoff_retest"
VISION = ROOT / "var" / "experiments" / "vision_ablation"
GRADE = ROOT / "var" / "experiments" / "grade_prompt"
CASES = ROOT / "[PUBLIC] EHL Cases" / "cases"
INF = math.inf
NOISE_FLOOR_18 = 26622.0


def cached_games(directory: Path, model_tag: str, suffix: str) -> list[int]:
    """Which Games actually have a cached draw. Discovered from disk, never imported.

    Deliberately not `from vision_ablation import MINI_GAMES`: `scripts/experiments/` is
    shared with other agents working the same night, and that module was rewritten under this
    one mid-session. A scoreboard that imports a peer's constant reports on whatever that peer
    last edited; one that reads the cache reports on the draws that were actually paid for.
    """
    if not directory.exists():
        return []
    return sorted(
        int(p.name.split("_")[1])
        for p in directory.glob(f"case_*_{model_tag}_{suffix}.json")
    )


def _evidence_from(path: Path) -> dict[int, Evidence]:
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


def baseline_anchor(game_id: int, model_tag: str) -> dict[int, Evidence]:
    return _evidence_from(RETEST / f"case_{game_id:02d}_{model_tag}_anchor.json")


def nophoto(game_id: int, model_tag: str) -> dict[int, Evidence]:
    return _evidence_from(VISION / f"case_{game_id:02d}_{model_tag}_nophoto.json")


def grade(game_id: int, model_tag: str) -> dict[int, Evidence]:
    return _evidence_from(GRADE / f"case_{game_id:02d}_{model_tag}_grade.json")


def log_errors(
    games: list[int],
    model_tag: str,
    loader,
    *,
    tail_only: bool = False,
    population: str = "real_money",
) -> list:
    """One row per scorable Line Item: (game, index, log_error, median, t).

    `population` splits the corpus the way CLAUDE.md rule 10 requires and never pools them:
      real_money  bounded bracket AND t_lo > 0 -- the only items price accuracy moves euros on
      censored    t_hi == inf -- `t` falls back to the proven lower bound `t_lo`, so a positive
                  error may be real and a NEGATIVE one is a *proof* of under-pricing. This is
                  also where the expensive items live (nobody rightfully rejected them), which
                  is why a real_money-only headline is blind to exactly the tail we care about.
    """
    out = []
    for g in games:
        try:
            snap = snapshot(g)
        except Exception:
            continue
        ev = loader(g, model_tag)
        for index, item in ev.items():
            if item.price_median <= 0:
                continue
            lo, hi = snap.fair_brackets.get(index, (0.0, INF))
            if population == "real_money":
                if hi == INF or lo <= 0:
                    continue
                t = (lo + hi) / 2.0
            elif population == "censored":
                if hi != INF or lo <= 0:
                    continue
                t = lo
            else:
                raise ValueError(population)
            if tail_only and t < 1000:
                continue
            out.append((g, index, math.log(item.price_median / t), item.price_median, t))
    return out


def paired(rows_a: list, rows_b: list) -> tuple[list, list]:
    """Restrict two row sets to the Line Items BOTH priced.

    Without this the two RMSLEs describe different item populations -- the no-photo arm
    priced two items (g19#8, g19#9) the photo arm left out, and an unpaired comparison
    silently credits or blames the arm for a composition difference rather than for the
    variable under test.
    """
    keys = {(r[0], r[1]) for r in rows_a} & {(r[0], r[1]) for r in rows_b}
    return (
        [r for r in rows_a if (r[0], r[1]) in keys],
        [r for r in rows_b if (r[0], r[1]) in keys],
    )


def _stats(rows) -> str:
    errs = [r[2] for r in rows]
    if not errs:
        return "n=0"
    rmsle = math.sqrt(st.fmean(e * e for e in errs))
    bias = st.fmean(errs)
    disp = st.pstdev(errs) if len(errs) > 1 else 0.0
    return f"n={len(errs):3d}  RMSLE={rmsle:.3f}  bias={bias:+.3f}  dispersion={disp:.3f}"


def euro_delta(games: list[int], model_tag: str, loader_a, loader_b, label_a: str, label_b: str) -> None:
    """Whole-Case submissions (model evidence combined with live Price Memory), replayed."""
    net_a, net_b, common = {}, {}, []
    for g in games:
        try:
            snap = snapshot(g)
        except Exception:
            continue
        case_dir = CASES / f"case_{g:02d}"
        if not (case_dir / "policy.txt").exists():
            continue
        ev_a, ev_b = loader_a(g, model_tag), loader_b(g, model_tag)
        if not ev_a or not ev_b:
            continue
        import asyncio

        from src.data.case_loader import read_case

        case = asyncio.run(read_case(g, case_dir))
        mem = local_evidence(case)
        uncovered = {li.index: bool(getattr(li, "quantity_missing", False)) for li in case.line_items}

        for label, ev, store in ((label_a, ev_a, net_a), (label_b, ev_b, net_b)):
            submission = {}
            for index in snap.line_items:
                combined = combine(ev.get(index), mem.get(index))
                if combined is None:
                    continue
                price = price_item(combined, confirmed_uncovered=uncovered.get(index, False))
                submission[index] = (price.charge, price.limit)
            if submission:
                store[g] = replay(snap, submission).net
        if g in net_a and g in net_b:
            common.append(g)

    if not common:
        print(f"    [{model_tag}] no common Games with both submissions -- nothing to replay yet")
        return
    nf = NOISE_FLOOR_18 * math.sqrt(len(common) / 18.0)
    total_a = sum(net_a[g] for g in common)
    total_b = sum(net_b[g] for g in common)
    flag = "inside noise floor" if abs(total_b - total_a) < nf else "OUTSIDE noise floor"
    print(f"    [{model_tag}] common Games n={len(common)}: {sorted(common)}")
    print(f"      {label_a:10s} total {total_a:>12,.2f}")
    print(f"      {label_b:10s} total {total_b:>12,.2f}")
    print(f"      delta {label_b}-{label_a}: {total_b - total_a:+,.2f}  (noise floor +/-{nf:,.0f})  [{flag}]")

    # Per Game, largest movement first. A total is only worth quoting if it is not one Case:
    # this repo has been burnt by exactly that (an 83,577 penalty figure that was one Line
    # Item; a 17,492 ceiling cliff that was Game 22 alone), so the breakdown ships with the
    # total rather than being available on request.
    per_game = sorted(((net_b[g] - net_a[g], g) for g in common), key=lambda kv: -abs(kv[0]))
    print(f"      per Game ({label_b} - {label_a}), largest first:")
    for delta, g in per_game:
        share = delta / (total_b - total_a) if abs(total_b - total_a) > 1e-9 else float("nan")
        print(f"        g{g:02d}  {delta:>+11,.0f}   ({share:+.0%} of the total delta)")
    if per_game:
        biggest, g_big = per_game[0]
        rest = (total_b - total_a) - biggest
        print(f"      without g{g_big:02d}: {rest:+,.0f} over {len(common) - 1} Games "
              f"(floor +/-{NOISE_FLOOR_18 * math.sqrt((len(common) - 1) / 18.0):,.0f})")


def section(title: str) -> None:
    print(f"\n{'=' * 90}\n{title}\n{'=' * 90}")


def main() -> None:
    section("VISION ABLATION -- photo ON (retest anchor) vs photo OFF (vision_ablation nophoto)")
    for model_tag in ("mini", "terra"):
        games = cached_games(VISION, model_tag, "nophoto")
        if not games:
            print(f"\n  -- model={model_tag}: no no-photo draws cached --")
            continue
        print(f"\n  -- model={model_tag}, Games {games} --")
        for population in ("real_money", "censored"):
            for tail_only in (False, True):
                on, off = paired(
                    log_errors(games, model_tag, baseline_anchor, tail_only=tail_only, population=population),
                    log_errors(games, model_tag, nophoto, tail_only=tail_only, population=population),
                )
                if not on:
                    continue
                label = f"{population}{' t>=1000' if tail_only else ''}"
                print(f"    [{label:20s}] photo ON   {_stats(on)}")
                print(f"    [{label:20s}] photo OFF  {_stats(off)}")
                wins_on = sum(1 for a, b in zip(on, off) if abs(a[2]) < abs(b[2]) - 1e-9)
                wins_off = sum(1 for a, b in zip(on, off) if abs(b[2]) < abs(a[2]) - 1e-9)
                print(f"    [{label:20s}] paired sign test: photo ON better {wins_on}, photo OFF better {wins_off}")
        photo_on = log_errors(games, model_tag, baseline_anchor)
        photo_off = log_errors(games, model_tag, nophoto)
        print("    per-item deltas (game#index: t, photoON_median, photoOFF_median, log_err ON, log_err OFF):")
        on_map = {(g, i): (e, m) for g, i, e, m, t in photo_on}
        off_map = {(g, i): (e, m, t) for g, i, e, m, t in photo_off}
        for (g, i), (err_off, med_off, t) in sorted(off_map.items(), key=lambda kv: -kv[1][2]):
            err_on, med_on = on_map.get((g, i), (float("nan"), float("nan")))
            print(
                f"      g{g:02d}#{i:<3d} t={t:9.2f}  ON={med_on:9.2f} (err {err_on:+.2f})  "
                f"OFF={med_off:9.2f} (err {err_off:+.2f})"
            )
        print("\n    euro replay (whole Case, Price Memory blended in as live):")
        euro_delta(games, model_tag, baseline_anchor, nophoto, "photoON", "photoOFF")

    section("GRADE PROMPT -- baseline anchor vs grade-first (item_grade + comparable fields)")
    for model_tag in ("mini", "terra"):
        games = cached_games(GRADE, model_tag, "grade")
        if not games:
            print(f"\n  -- model={model_tag}: no grade-prompt draws cached --")
            continue
        print(f"\n  -- model={model_tag}, Games {games} --")
        base = log_errors(games, model_tag, baseline_anchor)
        gr = log_errors(games, model_tag, grade)
        print(f"    baseline   {_stats(base)}")
        print(f"    grade      {_stats(gr)}")
        print(f"    baseline, t>=1000  {_stats(log_errors(games, model_tag, baseline_anchor, tail_only=True))}")
        print(f"    grade,    t>=1000  {_stats(log_errors(games, model_tag, grade, tail_only=True))}")
        print("    per-item deltas:")
        base_map = {(g, i): (e, m) for g, i, e, m, t in base}
        grade_map = {(g, i): (e, m, t) for g, i, e, m, t in gr}
        for (g, i), (err_gr, med_gr, t) in sorted(grade_map.items(), key=lambda kv: -kv[1][2]):
            err_base, med_base = base_map.get((g, i), (float("nan"), float("nan")))
            print(
                f"      g{g:02d}#{i:<3d} t={t:9.2f}  base={med_base:9.2f} (err {err_base:+.2f})  "
                f"grade={med_gr:9.2f} (err {err_gr:+.2f})"
            )
        print("\n    euro replay (whole Case, Price Memory blended in as live):")
        euro_delta(games, model_tag, baseline_anchor, grade, "baseline", "grade")

    section("Game 41 item 3 (the tourbillon) under every configuration drawn so far")
    for model_tag in ("mini", "terra"):
        for label, loader in (("baseline (photo ON)", baseline_anchor), ("no photo", nophoto), ("grade prompt", grade)):
            ev = loader(41, model_tag)
            item = ev.get(3)
            if item is None:
                print(f"  {model_tag:5s} {label:22s}  (not drawn)")
            else:
                print(f"  {model_tag:5s} {label:22s}  median={item.price_median:9.2f}  band=[{item.price_low:.0f},{item.price_high:.0f}]  cov={item.coverage_probability:.2f}")
    print("  true t >= 11,131")


if __name__ == "__main__":
    main()
