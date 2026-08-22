"""`MODEL_SIGMA_PRIOR` is the one constant in Strategy 2 that was never measured. Measure it.

Its docstring says so outright -- "A guess, and the one number here that is not measured".
It decides how a Price Memory hit is weighted against the model in `_combine`: memory gets
`1 / 0.43**2 = 5.4` and the model `1 / prior**2`. At the shipped prior of 0.6 that is a
66/34 split in memory's favour; at the model's *actual* log error it would be 90/10.

And the actual log error is now measured. Over Games 1-24 the blended ensemble's RMSLE
against the recovered Fair Values is 1.30 (`level_width.py`), which is 2.2x the prior.

Scoring this honestly needs one thing the other harnesses skip: Price Memory is built from
the very Games we replay, so it must be rebuilt **leave-one-Game-out** for every Game
scored. That is what this does -- for each Game, a memory from every other Game, then the
Strategy's own `_memory_evidence` / `_combine` / `price_item` path, then
`replay_payoffs.replay`.

    pixi run python scripts/experiments/level_memory.py --games 1-24

## The result: the prior is roughly where it should be, and the theory was backwards

Leave-one-Game-out memory over Games 1-24, 90 Line Items with a hit:

    MODEL_SIGMA_PRIOR    net      delta vs shipped 0.60
    ----------------- ---------- ----------------------
          0.43           128,143                 +7,768
          0.60           120,375                      0   <- shipped
          0.80           116,776                 -3,599
          1.00           112,388                 -7,987
          1.30           112,269                 -8,106   <- the measured log error
          1.60           110,554                 -9,821

Monotone, and it runs the *opposite* way to the argument for changing it. Setting the prior
to the estimator's measured error (1.30) would weight Price Memory 90/10 over the model and
costs 8,106; the euros want the model trusted *more*, not less, and the best cell is at the
edge of the grid where the two channels are weighted equally.

+7,768 is well inside the 26,622 noise floor, so 0.60 stays. What is no longer true is the
claim in `constants.py` that this number is unmeasured: it now has a euro sweep behind it
and a leave-one-out harness that can re-run it after any Game.

One trap worth keeping: `blend.py` does `from ... constants import MODEL_SIGMA_PRIOR`, so
rebinding `constants.MODEL_SIGMA_PRIOR` alone changes nothing. The first run of this sweep
after the module split reported six identical totals for that reason. `level_compat.
set_model_sigma_prior` rebinds every module that names it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_price_memory as bpm  # noqa: E402
from level_fit import load  # noqa: E402
from replay_payoffs import replay  # noqa: E402
from level_compat import (  # noqa: E402
    build_proposal,
    local_evidence,
    model_sigma_prior,
    parse_games,
    set_model_sigma_prior,
)

import src.price_memory as pm  # noqa: E402

PRIORS = (0.43, 0.6, 0.8, 1.0, 1.3, 1.6)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-24")
    parser.add_argument("--tag", default="model,nohint")
    args = parser.parse_args()

    games = parse_games(args.games)
    loaded = load(games, args.tag)
    scored = [snap.game_id for snap, _, _ in loaded]
    records = bpm.observations(games)
    print(f"{len(loaded)} Games, {len(records)} joined settled Line Items, tag {args.tag}")

    memories = {
        game_id: pm.PriceMemory.from_dict(
            {"entries": bpm.build_entries([r for r in records if r["game"] != game_id])}
        )
        for game_id in scored
    }

    shipped_prior = model_sigma_prior()
    results: dict[float, dict[int, float]] = {}
    hits = 0
    for prior in PRIORS:
        set_model_sigma_prior(prior)
        per_game: dict[int, float] = {}
        for snap, case, model in loaded:
            memory = memories[snap.game_id]
            original = pm.lookup
            pm.lookup = lambda name, unit=None, quantity=1.0, _m=memory: _m.lookup(
                name, unit=unit, quantity=quantity
            )
            try:
                memory_evidence = local_evidence(case)
            finally:
                pm.lookup = original
            if prior == PRIORS[0]:
                hits += sum(
                    1
                    for item in case.line_items
                    if item.index in memory_evidence
                    and not getattr(item, "quantity_missing", False)
                )
            proposal = build_proposal(case, model, memory_evidence)
            submission = (
                {p.index: (p.charge_price, p.acceptance_limit) for p in proposal.prices}
                if proposal
                else {}
            )
            per_game[snap.game_id] = replay(snap, submission).net
        results[prior] = per_game
    set_model_sigma_prior(shipped_prior)

    print(f"leave-one-Game-out Price Memory hits on {hits} Line Items\n")
    print(f"{'prior':>7} {'net':>14} {'delta vs 0.6':>14}")
    reference = sum(results[0.6].values())
    for prior in PRIORS:
        net = sum(results[prior].values())
        print(f"{prior:7.2f} {net:14,.0f} {net - reference:14,.0f}")

    print(f"\n{'game':>5}" + "".join(f"{p:>12.2f}" for p in PRIORS))
    for game_id in scored:
        print(f"{game_id:5d}" + "".join(f"{results[p][game_id]:12,.0f}" for p in PRIORS))


if __name__ == "__main__":
    main()
