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

    pixi run python scripts/level_memory.py --games 1-24
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
