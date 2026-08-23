"""Re-run the memory-conditional LIMIT_CEILING sweep against the freshly rebuilt
`price_memory.json` (Games 1-36, 175 entries) instead of the stale one (Games 1-14, 98
entries) the original sweep in `cap_ceiling_sweep.py` measured against.

The store was rebuilt mid-session (`scripts/build_price_memory.py`, ~22:29). This script
pins a copy of it first (it now regrows every ~12.6 min via `learn_watch`) and rebuilds
each row's evidence with a fresh Channel B lookup, WITHOUT calling the model:

* Rows that already had a memory hit under the old store keep their original (already
  correctly blended) evidence untouched -- that IS the "already reachable" measurement.
* Rows that never had a memory hit under the old store have, by construction, evidence
  that is pure model reading (no memory ever blended in) -- so a fresh hit for these can be
  blended straight in with `combine(old_evidence_as_model, fresh_memory_hit)`, exactly as
  the shipped pipeline would.
* This is exact wherever a row's OLD has_memory is False; it changes nothing for rows
  already memory-backed, which is exactly the population that needs no re-measurement.

No LLM call anywhere in this script -- Channel B is a local JSON lookup.

    PYTHONPATH=. pixi run python scripts/experiments/memory_refresh_sweep.py
"""
from __future__ import annotations

import dataclasses
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.charge_buckets import ALL_GAMES, Row, dataset, snapshot  # noqa: E402
from scripts.experiments.cap_ceiling_sweep import (  # noqa: E402
    WINDOW_19_32,
    flat_ceiling,
    make_rule,
    noise_floor,
    odd_even,
    time_split,
    total,
)
from scripts.replay_payoffs import INF, replay  # noqa: E402

from src.pricing.engine import LIMIT_CAP, LIMIT_CEILING, Evidence  # noqa: E402
from src.strategies.strategy2.blend import combine  # noqa: E402
from src.strategies.strategy2.channels import unit_of  # noqa: E402
from src.evidence.memory import PriceMemory  # noqa: E402

SCRATCH = Path(
    "/private/tmp/claude-501/-Users-sebastianrogg-PycharmProjects-Hackathons---Projekte-WireClaim"
    "/faa7ac4c-6f26-488b-b982-6f7ce9364ae6/scratchpad"
)
PINNED_STORE = SCRATCH / "price_memory_pinned_for_audit.json"


def pin_store() -> PriceMemory:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    shutil.copy("var/price_memory.json", PINNED_STORE)
    return PriceMemory.load(PINNED_STORE)


_MEMORY_COVERAGE = 0.9


def refresh_row(row: Row, store: PriceMemory) -> tuple[Row, str]:
    """Returns (possibly-updated row, category): 'none' | 'already' | 'newly'."""
    if row.uncovered:
        return row, "none"  # Channel A items never take a memory lookup

    hit = store.lookup(row.name, unit=unit_of(row.name), quantity=max(row.quantity, 1.0))
    fresh_has_memory = hit is not None

    if row.has_memory:
        # Already reachable under whatever store this row was originally measured against.
        # Its evidence is already the correct blend for that state; do not touch it. (A key
        # essentially never disappears as the store only grows, so this is a no-op either way.)
        return row, "already"

    if not fresh_has_memory:
        return row, "none"

    # Newly reachable: `row.evidence` is, by construction, pure model evidence (no memory
    # was ever blended into it, since has_memory was False).
    fresh_memory_evidence = Evidence(
        index=row.index,
        coverage_probability=_MEMORY_COVERAGE,
        price_low=hit.low,
        price_median=hit.median,
        price_high=hit.high,
    )
    merged = combine(row.evidence, fresh_memory_evidence)
    new_channels = tuple(row.channels) + ("B:memory",)
    new_row = dataclasses.replace(row, evidence=merged, channels=new_channels)
    return new_row, "newly"


def main() -> None:
    store = pin_store()
    import json as _json

    meta = _json.loads(Path("var/price_memory.json").read_text())
    print(f"Pinned store: {PINNED_STORE}")
    built = meta.get("built_from_games")
    built_desc = f"{min(built)}-{max(built)} ({len(built)} Games)" if isinstance(built, list) else built
    print(
        f"built_from_games={built_desc}  entries={len(meta.get('entries', {}))}  "
        f"measured_leave_one_out_sigma_log={meta.get('measured_leave_one_out_sigma_log')}"
    )

    rows = dataset(games=ALL_GAMES)
    refreshed: list[Row] = []
    categories: dict[int, str] = {}
    for i, row in enumerate(rows):
        new_row, cat = refresh_row(row, store)
        refreshed.append(new_row)
        categories[i] = cat

    n_none = sum(1 for c in categories.values() if c == "none")
    n_already = sum(1 for c in categories.values() if c == "already")
    n_newly = sum(1 for c in categories.values() if c == "newly")
    print(f"\nRows: {len(rows)}  none={n_none}  already-memory={n_already}  newly-memory={n_newly}")
    print(
        f"Memory-backed share: OLD {n_already}/{len(rows)} ({n_already/len(rows):.0%})  "
        f"-> NEW {n_already+n_newly}/{len(rows)} ({(n_already+n_newly)/len(rows):.0%})"
    )

    # ---------------------------------------------------------------- 1: the sweep itself
    def memory_ceiling(row: Row, v: float) -> float:
        return v if row.has_memory else LIMIT_CEILING

    candidates = [
        (f"memory ceiling {m:.2f}", make_rule(cap=LIMIT_CAP, ceiling_fn=lambda r, m=m: memory_ceiling(r, m)))
        for m in (0.45, 0.55, 0.65, 0.75, 0.85, 1.00)
    ]

    def report_refreshed(name, games, cut):
        shipped = make_rule(cap=LIMIT_CAP, ceiling_fn=flat_ceiling(LIMIT_CEILING))
        base = total(refreshed, shipped, games)
        odd, even = odd_even(games)
        early, late = time_split(games, cut)
        base_odd, base_even = total(refreshed, shipped, odd), total(refreshed, shipped, even)
        base_early, base_late = total(refreshed, shipped, early), total(refreshed, shipped, late)
        floor = noise_floor(len(games))
        print(f"\n--- {name}: {len(games)} Games (shipped net {base:+,.0f}, noise floor +/-{floor:,.0f}) [REFRESHED STORE] ---")
        print(f"{'candidate':<24}{'all':>12}{'delta':>11}{'odd f':>10}{'even f':>10}{'<=%d f'%cut:>10}{'>%d f'%cut:>9}")
        for label, fn in candidates:
            t = total(refreshed, fn, games)
            t_odd = total(refreshed, fn, odd) - base_odd
            t_even = total(refreshed, fn, even) - base_even
            t_early = total(refreshed, fn, early) - base_early if early else float("nan")
            t_late = total(refreshed, fn, late) - base_late if late else float("nan")
            print(
                f"{label:<24}{t:>12,.0f}{t - base:>11,.0f}"
                f"{t_odd:>10,.0f}{t_even:>10,.0f}{t_early:>10,.0f}{t_late:>9,.0f}"
            )

    print("\n" + "=" * 110)
    print("1 -- memory-conditional ceiling sweep, REFRESHED store (1-36, 175 entries)")
    print("=" * 110)
    report_refreshed("Games 19-32", WINDOW_19_32, 25)
    report_refreshed("all settled Games", ALL_GAMES, (ALL_GAMES[0] + ALL_GAMES[-1]) // 2)

    # ------------------------------------------------------- 2: fair vs overcharge, overall
    def fair_vs_over(rows_subset: list[Row], label: str) -> tuple[float, float, int, int]:
        by_game: dict[int, list[Row]] = {}
        for row in rows_subset:
            by_game.setdefault(row.game, []).append(row)
        shipped_fn = make_rule(cap=LIMIT_CAP, ceiling_fn=flat_ceiling(LIMIT_CEILING))
        candidate_fn = make_rule(cap=LIMIT_CAP, ceiling_fn=lambda r: memory_ceiling(r, 0.75))
        fair_saving = over_cost = 0.0
        n_fair = n_over = 0
        for row in rows_subset:
            snap = snapshot(row.game)
            if row.index not in snap.line_items:
                continue
            _, s_limit = shipped_fn(row)
            _, c_limit = candidate_fn(row)
            if c_limit <= s_limit + 1e-9:
                continue
            t = snap.fair_point(row.index)
            for team in snap.opponents:
                opp_charge = snap.charges[row.index].get(team, INF)
                if opp_charge == INF:
                    continue
                if s_limit < opp_charge <= c_limit:
                    if opp_charge <= t:
                        fair_saving += 0.5 * opp_charge
                        n_fair += 1
                    else:
                        over_cost += opp_charge
                        n_over += 1
        ratio = fair_saving / over_cost if over_cost else float("inf")
        print(
            f"  {label:<28} fair {n_fair:>4} insts, {fair_saving:>10,.2f} saved   "
            f"over {n_over:>4} insts, {over_cost:>10,.2f} cost   ratio {ratio:>6.2f}:1   "
            f"net {fair_saving - over_cost:>10,.2f}"
        )
        return fair_saving, over_cost, n_fair, n_over

    print("\n" + "=" * 110)
    print("2 -- fair-vs-Overcharge split for ceiling 0.75, REFRESHED store, whole population")
    print("=" * 110)
    fair_vs_over(refreshed, "ALL memory-backed (refreshed)")

    print("\n" + "=" * 110)
    print("2b -- split by ALREADY-reachable (old store) vs NEWLY-reachable (new store)")
    print("=" * 110)
    already_rows = [r for i, r in enumerate(refreshed) if categories[i] == "already"]
    newly_rows = [r for i, r in enumerate(refreshed) if categories[i] == "newly"]
    print(f"already-reachable: {len(already_rows)} items   newly-reachable: {len(newly_rows)} items")
    fair_vs_over(already_rows, "already-reachable (1-14 store)")
    fair_vs_over(newly_rows, "newly-reachable (1-36 store only)")

    # ------------------------------------------------------- 3: saturation point check
    print("\n" + "=" * 110)
    print("3 -- saturation point check, REFRESHED store, all 36 Games")
    print("=" * 110)
    shipped_fn = make_rule(cap=LIMIT_CAP, ceiling_fn=flat_ceiling(LIMIT_CEILING))
    base_all = total(refreshed, shipped_fn, ALL_GAMES)
    for m in (0.45, 0.55, 0.65, 0.75, 0.85, 1.00, 1.25, 1.50):
        fn = make_rule(cap=LIMIT_CAP, ceiling_fn=lambda r, m=m: memory_ceiling(r, m))
        t = total(refreshed, fn, ALL_GAMES)
        print(f"  ceiling {m:.2f}: net {t:>12,.0f}  delta {t - base_all:>+10,.0f}")


if __name__ == "__main__":
    main()
