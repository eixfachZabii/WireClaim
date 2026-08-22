"""Euro impact of correcting MODEL_SIGMA_PRIOR and MEMORY_SIGMA/SIGMA_LOG, isolated from
every other constant, through the real `blend.combine()` -> `price_item()` -> replay path.

Why this script exists and how it differs from what's already committed
-------------------------------------------------------------------------
docs/brainstorm/sebi/strats/review/price-memory-coverage.md section 5 already tested
MEMORY_SIGMA/SIGMA_LOG *in isolation* (Channel B answering alone, no model reading) and found
a small, noise-floor-internal, mildly *negative* delta -- and explicitly flagged as untested
follow-up: "test MEMORY_SIGMA's effect inside blend.combine() against real cached model
Evidence". That is what this script does, plus MODEL_SIGMA_PRIOR, which nothing in this repo
has replayed in euros yet (constants.py's own docstring calls it "a prior, not a
measurement").

Sample and its limitation, stated up front
-------------------------------------------
`blend.combine()` needs a real Channel C (model) reading. Regenerating one costs an LLM call,
which this task forbids (the endpoint is shared with the live tournament runner). So the
sample here is every settled Game with a **cached** raw model draw in `var/evidence/
case_NN_model.json` (from `scripts/dump_evidence.py`, run earlier, no new calls) --
Games 1-26 and 28-30 (27 has no cache). That is smaller than "every settled Game": 28 Games,
not the 37+ now on the leaderboard. Every number below is scoped to that sample and says so.

Channel B (memory) is rebuilt fresh here, per scored Game, leave-one-out over every settled
Game 1-37 *except* the one being scored (memory needs no LLM call, only cached transactions
and local invoice PDFs) -- deliberately not read from the possibly-stale cached
`case_NN_memory.json`, which reflects whatever store existed on disk when `dump_evidence.py`
happened to run. This keeps the memory channel's hit set and band width fully controllable
per variant (both MEMORY_SIGMA and, for the per-match-type candidate, a sigma that depends on
`hit.match`) without contaminating it with a stale, uncontrolled snapshot.

Held-out folds, on the 28-Game available sample:
    odd  -> even        (14 vs 14 Games)
    1-20 -> 21+          (20 vs 8 Games: 21,22,23,24,25,26,28,29,30)

CHARGE_INTERCEPT / CHARGE_SLOPE are never touched (imported, used as-is from
src/domain/pricing/engine.py) -- only blend.MODEL_SIGMA_PRIOR / blend.MEMORY_SIGMA are varied,
via monkeypatching the already-imported module attributes in this process only. This process
never touches var/price_memory.json (no writes) and never calls the LLM endpoint.

    PYTHONPATH=. python scripts/experiments/sigma_calibration_replay.py
"""

from __future__ import annotations

import asyncio
import functools
import math
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.data.case_loader import read_case  # noqa: E402
from src.pricing.engine import Evidence, price_item  # noqa: E402
from src.strategies.strategy2 import blend  # noqa: E402
from src.evidence.memory import PriceMemory, build_entries  # noqa: E402
import build_price_memory as bpm  # noqa: E402
from scripts.dump_evidence import load as load_model_evidence  # noqa: E402
from scripts.replay_payoffs import replay, snapshot as _snapshot, usable_games  # noqa: E402

CASES = Path("[PUBLIC] EHL Cases/cases")
snapshot = functools.lru_cache(maxsize=None)(_snapshot)

# ------------------------------------------------------------------------- the population

MEMORY_POOL_GAMES = list(range(1, 38))  # every settled Game with recoverable brackets, for
                                          # building leave-one-out Price Memory (no LLM needed)


def _model_cache_games() -> list[int]:
    games = []
    for g in range(1, 38):
        if (Path("var/evidence") / f"case_{g:02d}_model.json").exists():
            games.append(g)
    return games


RECON_GAMES = _model_cache_games()
USABLE = set(usable_games(range(1, 38)))
RECON_GAMES = [g for g in RECON_GAMES if g in USABLE]

ODD = tuple(g for g in RECON_GAMES if g % 2 == 1)
EVEN = tuple(g for g in RECON_GAMES if g % 2 == 0)
EARLY = tuple(g for g in RECON_GAMES if g <= 20)
LATE = tuple(g for g in RECON_GAMES if g > 20)


def noise_floor(n_games: int) -> float:
    return 26_622.0 * math.sqrt(n_games / 18.0)


# --------------------------------------------------------------------- observations cache

print(f"Loading invoice observations for Games 1-37 (offline, for the leave-one-out "
      f"memory pool)...", file=sys.stderr)
ALL_RECORDS = bpm.observations(MEMORY_POOL_GAMES)
print(f"  {len(ALL_RECORDS)} Line Items joined", file=sys.stderr)


@functools.lru_cache(maxsize=None)
def _memory_excluding(game_id: int) -> PriceMemory:
    """Leave-one-out Price Memory: every settled Game except `game_id`."""
    training = [r for r in ALL_RECORDS if r["game"] != game_id]
    return PriceMemory.from_dict({"entries": build_entries(training)})


@functools.lru_cache(maxsize=None)
def _line_items(game_id: int) -> dict:
    case_dir = CASES / f"case_{game_id:02d}"
    case = asyncio.run(read_case(game_id, case_dir))
    return {
        item.index: (item.name, item.quantity, bool(item.quantity_missing))
        for item in case.line_items
    }


def _memory_evidence(game_id: int, index: int, name: str, quantity: float, sigma_log: float):
    """Channel B Evidence for one Line Item, band built at the given sigma_log.

    Mirrors src/services/strategies/strategy2/channels.py::local_evidence, minus the unit
    parse (the invoice text isn't re-parsed here; `unit_of` needs the raw name string, which
    `_line_items` already returns from `read_case`, same source the live path uses).
    """
    from src.strategies.strategy2.channels import unit_of

    memory = _memory_excluding(game_id)
    hit = memory.lookup(name, unit=unit_of(name), quantity=max(quantity, 1.0))
    if hit is None:
        return None, None, None
    median = hit.median
    if median <= 0:
        return None, None, None
    low = median * math.exp(-sigma_log)
    high = median * math.exp(sigma_log)
    return (
        Evidence(index=index, coverage_probability=0.9, price_low=low,
                 price_median=median, price_high=high),
        hit.match,
        hit.basis,
    )


# ------------------------------------------------------------------------------ the rows


@dataclass(frozen=True)
class Row:
    game: int
    index: int
    uncovered: bool
    has_memory: bool
    memory_match: str | None  # "exact" | "core" | None
    model_evidence: Evidence | None
    memory_name: str
    memory_quantity: float


def _rows_for_game(game_id: int) -> list[Row]:
    brackets = snapshot(game_id).fair_brackets
    items = _line_items(game_id)
    model = load_model_evidence(game_id, "model") or {}
    rows = []
    for index in brackets:
        name, quantity, uncovered = items.get(index, ("", 1.0, False))
        from_model = model.get(index)
        rows.append(Row(
            game=game_id, index=index, uncovered=uncovered,
            has_memory=False, memory_match=None,  # filled in per-variant (sigma-dependent hit)
            model_evidence=from_model, memory_name=name, memory_quantity=quantity,
        ))
    return rows


ROWS_BY_GAME: dict[int, list[Row]] = {g: _rows_for_game(g) for g in RECON_GAMES}


# --------------------------------------------------------------------------- the variants


def _price_row(row: Row, model_sigma: float, memory_sigma_fn) -> tuple[float, float]:
    """One Line Item's (charge, limit), for a given MODEL_SIGMA_PRIOR and a memory-sigma
    function `memory_sigma_fn(match: str, basis: str) -> float`.

    IMPORTANT, found by testing this harness against a known-analytic case (see the report):
    `blend.combine()`'s inverse-variance weighting reads the *module constants*
    `MODEL_SIGMA_PRIOR` / `MEMORY_SIGMA` directly -- it does **not** derive a weight from the
    passed-in Evidence's own `price_low`/`price_high`. So the sigma baked into the memory
    Evidence's band only matters for combine()'s two fallback branches (model says
    worthless -> pass the memory band through untouched; memory proves uncovered -> pass the
    better band through). The dominant weighted-average branch is driven entirely by the two
    module constants, which is why both are monkeypatched on `blend` itself, every row, right
    before calling `combine()` -- not by varying the Evidence's own band width alone.
    """
    memory_evidence = None
    # Need a provisional lookup to learn the hit's own (match, basis) before picking its
    # sigma; look it up once at the shipped sigma (cheap: PriceMemory.lookup is a dict merge,
    # not I/O), then rebuild the band at the right width for the fallback branches above.
    probe, match, basis = _memory_evidence(
        row.game, row.index, row.memory_name, row.memory_quantity, SHIPPED_MEMORY_SIGMA
    )
    sigma_for_hit = SHIPPED_MEMORY_SIGMA
    if probe is not None:
        sigma_for_hit = memory_sigma_fn(match, basis)
        memory_evidence, match, basis = _memory_evidence(
            row.game, row.index, row.memory_name, row.memory_quantity, sigma_for_hit
        )

    blend.MODEL_SIGMA_PRIOR = model_sigma
    blend.MEMORY_SIGMA = sigma_for_hit
    combined = blend.combine(row.model_evidence, memory_evidence)
    if combined is None:
        return None  # no evidence at all for this Line Item -- not priced by this harness

    memory_backed = memory_evidence is not None and not row.uncovered
    price = price_item(combined, confirmed_uncovered=row.uncovered, memory_backed=memory_backed)
    return price.charge, price.limit


def replay_games(games: tuple[int, ...], model_sigma: float, memory_sigma_fn) -> float:
    total = 0.0
    for game_id in games:
        snap = snapshot(game_id)
        submission = {
            i: (snap.charges[i][snap.us], snap.limit_point(i, snap.us)) for i in snap.line_items
        }
        for row in ROWS_BY_GAME[game_id]:
            priced = _price_row(row, model_sigma, memory_sigma_fn)
            if priced is not None:
                submission[row.index] = priced
        total += replay(snap, submission).net
    return total


# ---------------------------------------------------------------------------------- main

SHIPPED_MODEL_SIGMA = 0.6
SHIPPED_MEMORY_SIGMA = 0.43
MEASURED_MODEL_SIGMA = 0.845          # Channel-C-only RMSLE, terra, n=152 (model-bakeoff.md)
MEASURED_MEMORY_SIGMA_TASK = 0.581    # the figure named in the brief
MEASURED_MEMORY_SIGMA_OWN = 0.51      # this repo's own pooled leave-one-out, Games 1-37, ON

# scripts/experiments/sigma_by_match_type.py (Games 1-37, leave-one-out, per-unit ON) found
# the split that actually separates accurate hits from inaccurate ones is BASIS, not match
# type: per_unit sigma=0.324 (n=33), gross sigma=0.547 (n=127); match-type alone (exact
# sigma=0.518 n=152, core sigma=0.286 n=8) shows core is *not* worse, just rare -- the
# brief's "0.43 is exact-only" hypothesis does not hold. So the "per-match-type" candidate
# below is really per-basis.
PER_BASIS_SIGMA = {"per_unit": 0.33, "gross": 0.55}


def _flat(value: float):
    return lambda match, basis: value


VARIANTS = [
    ("shipped (0.60 model, 0.43 memory)", SHIPPED_MODEL_SIGMA, _flat(SHIPPED_MEMORY_SIGMA)),
    ("model only -> 0.845", MEASURED_MODEL_SIGMA, _flat(SHIPPED_MEMORY_SIGMA)),
    ("memory only -> 0.581 (task figure)", SHIPPED_MODEL_SIGMA, _flat(MEASURED_MEMORY_SIGMA_TASK)),
    ("memory only -> 0.51 (own pooled measurement)", SHIPPED_MODEL_SIGMA, _flat(MEASURED_MEMORY_SIGMA_OWN)),
    ("both -> 0.845 / 0.581", MEASURED_MODEL_SIGMA, _flat(MEASURED_MEMORY_SIGMA_TASK)),
    ("both -> 0.845 / 0.51", MEASURED_MODEL_SIGMA, _flat(MEASURED_MEMORY_SIGMA_OWN)),
]


def main() -> None:
    print(f"Games with cached model evidence AND usable snapshot: {RECON_GAMES} "
          f"({len(RECON_GAMES)} Games)")
    print(f"  odd  ({len(ODD)}): {ODD}")
    print(f"  even ({len(EVEN)}): {EVEN}")
    print(f"  1-20 ({len(EARLY)}): {EARLY}")
    print(f"  21+  ({len(LATE)}): {LATE}")

    folds = [
        ("all", RECON_GAMES),
        ("odd", ODD),
        ("even", EVEN),
        ("1-20", EARLY),
        ("21+", LATE),
    ]

    baseline = {name: replay_games(games, SHIPPED_MODEL_SIGMA, _flat(SHIPPED_MEMORY_SIGMA))
                for name, games in folds}

    print(f"\n{'variant':<48}" + "".join(f"{n:>14}" for n, _ in folds))
    print(f"{'shipped baseline (net, EUR)':<48}"
          + "".join(f"{baseline[n]:>14,.0f}" for n, _ in folds))
    print("-" * (48 + 14 * len(folds)))
    for label, model_sigma, memory_sigma_fn in VARIANTS[1:]:
        row = []
        for name, games in folds:
            net = replay_games(games, model_sigma, memory_sigma_fn)
            row.append(net - baseline[name])
        print(f"{label:<48}" + "".join(f"{d:>+14,.0f}" for d in row))

    print(f"\nnoise floors: all n={len(RECON_GAMES)} +/-{noise_floor(len(RECON_GAMES)):,.0f}   "
          f"odd n={len(ODD)} +/-{noise_floor(len(ODD)):,.0f}   "
          f"even n={len(EVEN)} +/-{noise_floor(len(EVEN)):,.0f}   "
          f"1-20 n={len(EARLY)} +/-{noise_floor(len(EARLY)):,.0f}   "
          f"21+ n={len(LATE)} +/-{noise_floor(len(LATE)):,.0f}")

    # ---- per-basis memory sigma (the split section 2 actually supports), model unchanged
    def per_basis_sigma(match: str, basis: str) -> float:
        return PER_BASIS_SIGMA.get(basis, SHIPPED_MEMORY_SIGMA)

    print(f"\nper-basis memory sigma candidate (per_unit->0.33, gross->0.55, model unchanged "
          f"at 0.60):")
    row = []
    for name, games in folds:
        net = replay_games(games, SHIPPED_MODEL_SIGMA, per_basis_sigma)
        row.append(net - baseline[name])
    print(f"{'per-basis-conditional memory sigma':<48}"
          + "".join(f"{d:>+14,.0f}" for d in row))

    print(f"\nper-basis memory sigma + calibrated model sigma (0.845):")
    row = []
    for name, games in folds:
        net = replay_games(games, MEASURED_MODEL_SIGMA, per_basis_sigma)
        row.append(net - baseline[name])
    print(f"{'per-basis memory + model->0.845':<48}"
          + "".join(f"{d:>+14,.0f}" for d in row))


if __name__ == "__main__":
    main()
