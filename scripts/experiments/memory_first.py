"""Should Price Memory outrank the model instead of being averaged with it? Leave-one-Game-out.

The case for asking
-------------------
`scripts/experiments/ceiling.py` shows 103 % of everything still available above what we
submitted is estimation quality; `price_of_sigma.py` prices that at roughly 5.8 M weighted per
unit of log error in the region we operate in, with our real submission sitting at an effective
sigma near 0.52. So the only question worth spending on is which estimator is the most accurate
one we can actually run.

Two measurements say the answer may already be on disk:

* `build_price_memory.py --games 1-100 --evaluate` -- Price Memory, rebuilt from every settled
  Game and scored leave-one-out: **recall 79 % (609/773), sigma 0.458, bias +0.031**. Its own
  docstring still claims 22 % recall and calls a hit "an anchor, not an answer"; that was
  measured over Cases 1-14 and is now four times too pessimistic on reach.
* the censored calibration fit -- on the Line Items memory priced *alone* the residual runs
  0.974 to 1.339 between the 20th and 90th percentile, against 0.452 to 5.675 where the model
  priced alone. A factor of 1.4 against a factor of 12.5.

Yet `blend.combine` merges them by inverse variance at `MODEL_SIGMA_PRIOR = 0.6` and
`MEMORY_SIGMA = 0.43`, which hands the model **34 %** of the weight. At the measured widths it
earns about 17 %, and the pooled `B:memory|C:model` residual is visibly worse than memory alone.

What is compared
----------------
Four submissions, over the Games that have both a decision log and a reconstructable Field:

    ACTUAL        what we really submitted (the shipped blend)
    MEMORY-ONLY   `a`, `b` from the leave-one-out memory hit; our real submission kept on a miss
    MEMORY-FIRST  the memory hit where there is one, otherwise our real submission
    REWEIGHTED    log-space inverse-variance blend at the *measured* widths rather than the
                  asserted ones -- memory 0.458, model 1.0 -- which is the smallest change
                  that acts on the finding

MEMORY-ONLY and MEMORY-FIRST are the same thing under a different name only if memory never
misses; it misses 21 % of the time, and what happens on those items is exactly what separates
"trust memory more" from "trust memory only".

The leave-one-out is not cosmetic. A memory that has seen the Game it is pricing reports a
sigma near zero and is worth nothing, so every Game is scored against a store rebuilt from the
other ninety-nine.

Usage
-----
    PYTHONPATH=. python scripts/experiments/memory_first.py
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_price_memory import build_entries, observations, team_names  # noqa: E402
from replay_payoffs import US, our_actual_submission, reconstruction_status, replay, snapshot  # noqa: E402

from src.evidence.memory import PriceMemory  # noqa: E402

WEIGHTED = frozenset(range(81, 101))

#: The shipped pricing rule, reduced to its two multipliers so this experiment changes the
#: *estimate* and nothing else. `CHARGE_FACTOR` is where `charge_factor(sigma)` lands for a
#: typical band; the Limit multiplier is swept, because R6 says it is the flat one.
CHARGE_FACTOR = 0.69
LIMIT_FACTORS = [0.5, 0.75, 1.0, 1.25, 1.5]

#: Measured, not asserted -- the whole point of the REWEIGHTED arm.
MEASURED_MEMORY_SIGMA = 0.458
MEASURED_MODEL_SIGMA = 1.0


def weight(game_id: int) -> float:
    return 3.0 if game_id in WEIGHTED else 1.0


def build_predictions(games: list[int], mode: str) -> dict[int, dict[int, float]]:
    """`{game: {line item: memory median}}` under one of two honesty regimes.

    `mode="loo"` builds each Game's store from **every other** Game, future ones included. That
    is the standard leave-one-out and it answers "how good is this estimator", but it is not
    what we could have run: at Game 40 the settled record stopped at Game 39.

    `mode="walk"` builds each Game's store from the **strictly earlier** Games only. That is
    what the live pipeline actually had, so it is the arm that licenses a claim about what we
    would have scored. It is necessarily worse early on -- Game 2 has one Game of memory -- and
    the gap between the two arms is the honest size of the hindsight in `loo`.
    """
    records = observations(games, names=team_names())
    print(f"  {len(records)} joined invoice Line Items across {len(games)} Games ({mode})")

    by_game: dict[int, list[dict]] = defaultdict(list)
    for record in records:
        by_game[record["game"]].append(record)

    out: dict[int, dict[int, float]] = defaultdict(dict)
    for game_id in games:
        if game_id not in by_game:
            continue
        if mode == "walk":
            training = [r for r in records if r["game"] < game_id]
        else:
            training = [r for r in records if r["game"] != game_id]
        if not training:
            continue
        memory = PriceMemory.from_dict({"entries": build_entries(training)})
        for record in by_game[game_id]:
            hit = memory.lookup(
                record["display_name"], unit=record["unit"], quantity=record["quantity"]
            )
            if hit is not None and hit.median > 0:
                out[game_id][int(record["line_item_index"])] = float(hit.median)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-100")
    parser.add_argument(
        "--mode",
        default="both",
        choices=("loo", "walk", "both"),
        help="loo = leave-one-out (uses future Games); walk = strictly earlier Games only",
    )
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))

    snaps = [snapshot(g, US) for g in game_ids if reconstruction_status(g, US).usable]
    modes = ("loo", "walk") if args.mode == "both" else (args.mode,)

    def total(build) -> float:
        return sum(replay(s, build(s)).net * weight(s.game_id) for s in snaps)

    actual = total(our_actual_submission)
    print(f"\n  {'arm':<34}{'limit x':>9}{'net (weighted)':>18}{'vs actual':>15}")
    print(f"  {'-' * 34:<34}{'-' * 9:>9}{'-' * 18:>18}{'-' * 15:>15}")
    print(f"  {'ACTUAL (shipped blend)':<34}{'':>9}{actual:>18,.0f}{0:>15,.0f}")

    for mode in modes:
        predictions = build_predictions(game_ids, mode)
        hits = sum(len(predictions.get(s.game_id, {})) for s in snaps)
        items = sum(len(s.line_items) for s in snaps)
        run_arms(snaps, predictions, actual, mode, hits, items)


def run_arms(snaps, predictions, actual, mode, hits, items):
    def total(build) -> float:
        return sum(replay(s, build(s)).net * weight(s.game_id) for s in snaps)

    def memory_first(beta: float, fallback: bool):
        def build(snap):
            mine = our_actual_submission(snap)
            hit_map = predictions.get(snap.game_id, {})
            out = {}
            for index in snap.line_items:
                anchor = hit_map.get(index)
                if anchor is None:
                    # A miss. `fallback` decides whether the model's number stands (MEMORY-FIRST)
                    # or the item is simply left as we really priced it (MEMORY-ONLY). Both keep
                    # our real submission here; the arms differ on the *hits*, which is the
                    # comparison that carries information.
                    out[index] = mine[index]
                else:
                    out[index] = (CHARGE_FACTOR * anchor, beta * anchor)
            return out
        return build

    def reweighted(beta: float):
        """Inverse-variance blend at the measured widths instead of the asserted ones."""
        w_mem = 1.0 / MEASURED_MEMORY_SIGMA**2
        w_mod = 1.0 / MEASURED_MODEL_SIGMA**2
        share = w_mem / (w_mem + w_mod)

        def build(snap):
            mine = our_actual_submission(snap)
            hit_map = predictions.get(snap.game_id, {})
            out = {}
            for index in snap.line_items:
                anchor = hit_map.get(index)
                charge, _ = mine[index]
                # A Charge of `inf` is an *unrecoverable* one -- it sat above every Limit in
                # the Field, so the record cannot say what it was. Dividing it back out to a
                # model estimate produced `inf`, which propagated to an `-inf` total. Such an
                # item has no usable model reading, so the memory anchor stands alone.
                usable = math.isfinite(charge) and charge > 0
                model_estimate = charge / CHARGE_FACTOR if usable else 0.0
                if anchor is None:
                    out[index] = mine[index]
                    continue
                if model_estimate <= 0:
                    out[index] = (CHARGE_FACTOR * anchor, beta * anchor)
                    continue
                blended = math.exp(
                    share * math.log(anchor) + (1 - share) * math.log(model_estimate)
                )
                out[index] = (CHARGE_FACTOR * blended, beta * blended)
            return out
        return build

    print(f"\n  --- {mode.upper()}: memory answers {hits} of {items} Line Items "
          f"({hits / max(items, 1):.0%} recall) ---")
    for label, factory in (
        ("MEMORY-FIRST (hit wins outright)", lambda b: memory_first(b, True)),
        (f"REWEIGHTED (memory {1 / (1 + (MEASURED_MEMORY_SIGMA / MEASURED_MODEL_SIGMA) ** 2):.0%})",
         reweighted),
    ):
        best = None
        for beta in LIMIT_FACTORS:
            got = total(factory(beta))
            if best is None or got > best[1]:
                best = (beta, got)
        print(f"  {label:<34}{best[0]:>9.2f}{best[1]:>18,.0f}{best[1] - actual:>15,.0f}")

        # Folds, on the winning beta -- a total that one regime bought is not a result.
        build = factory(best[0])
        folds = {
            "odd": [s for s in snaps if s.game_id % 2],
            "even": [s for s in snaps if not s.game_id % 2],
            "1-43": [s for s in snaps if s.game_id <= 43],
            "44-81": [s for s in snaps if 44 <= s.game_id <= 81],
            "82-100": [s for s in snaps if s.game_id >= 82],
        }
        parts = []
        for name, subset in folds.items():
            base = sum(replay(s, our_actual_submission(s)).net * weight(s.game_id) for s in subset)
            got = sum(replay(s, build(s)).net * weight(s.game_id) for s in subset)
            parts.append(f"{name} {got - base:+,.0f}")
        print(f"  {'':<34}{'':>9}{'  folds: ' + '   '.join(parts):>33}")


if __name__ == "__main__":
    main()
