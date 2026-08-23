"""How much of the blend should Price Memory carry? Swept walk-forward, with folds.

`memory_first.py` establishes the direction: giving Price Memory more of the blend is worth
money, and it is worth a great deal (+630,751 weighted) when the store has seen the whole
tournament. This sweeps the one number that decides it, so the constant that ships is an
argmax rather than a guess.

`blend.combine` weights the two channels by inverse variance in log space:

    share = (1 / sigma_memory^2) / (1 / sigma_memory^2 + 1 / sigma_model^2)

With the shipped `MEMORY_SIGMA = 0.43` and `MODEL_SIGMA_PRIOR = 0.6` that share is **0.66**.
Both constants are labelled in `constants.py` as what they are -- one measured over Cases 1-14,
one explicitly "a prior, not a measurement" -- and the tournament has since produced ninety-nine
more Games to measure against. Rather than substitute two new sigmas and infer a share, the
share itself is swept: it is the only quantity the blend actually uses, and sweeping it directly
means no arithmetic sits between the measurement and the constant.

**Walk-forward only.** Each Game is priced by a memory built from the strictly earlier Games,
which is what the live pipeline had. The leave-one-out arm in `memory_first.py` scores far
higher and is reported there, but a constant tuned against future Games is a constant tuned
against nothing that will happen again.

Usage
-----
    PYTHONPATH=. python scripts/experiments/blend_weight_sweep.py
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from memory_first import CHARGE_FACTOR, build_predictions, weight  # noqa: E402
from replay_payoffs import US, our_actual_submission, reconstruction_status, replay, snapshot  # noqa: E402

SHARES = [0.66, 0.75, 0.80, 0.83, 0.88, 0.92, 0.96, 1.00]
LIMIT_FACTORS = [0.75, 1.0, 1.25]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-100")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))

    snaps = [snapshot(g, US) for g in game_ids if reconstruction_status(g, US).usable]
    predictions = build_predictions(game_ids, "walk")

    def build(share: float, beta: float):
        def make(snap):
            mine = our_actual_submission(snap)
            hit_map = predictions.get(snap.game_id, {})
            out = {}
            for index in snap.line_items:
                anchor = hit_map.get(index)
                charge, _ = mine[index]
                usable = math.isfinite(charge) and charge > 0
                model_estimate = charge / CHARGE_FACTOR if usable else 0.0
                if anchor is None:
                    out[index] = mine[index]
                elif model_estimate <= 0 or share >= 1.0:
                    out[index] = (CHARGE_FACTOR * anchor, beta * anchor)
                else:
                    blended = math.exp(
                        share * math.log(anchor) + (1 - share) * math.log(model_estimate)
                    )
                    out[index] = (CHARGE_FACTOR * blended, beta * blended)
            return out
        return make

    def total(make, subset=None) -> float:
        return sum(
            replay(s, make(s)).net * weight(s.game_id) for s in (subset if subset else snaps)
        )

    actual = total(our_actual_submission)
    folds = {
        "odd": [s for s in snaps if s.game_id % 2],
        "even": [s for s in snaps if not s.game_id % 2],
        "1-43": [s for s in snaps if s.game_id <= 43],
        "44-81": [s for s in snaps if 44 <= s.game_id <= 81],
        "82-100": [s for s in snaps if s.game_id >= 82],
    }
    baselines = {name: total(our_actual_submission, subset) for name, subset in folds.items()}

    print(f"\n  walk-forward, {len(snaps)} Games. Our real submission: {actual:,.0f} weighted.")
    print(f"  The shipped share is 0.66 (MEMORY_SIGMA 0.43 vs MODEL_SIGMA_PRIOR 0.6).\n")
    print(f"  {'share':>7}{'limit x':>9}{'weighted':>14}{'gain':>12}   " + "".join(f"{n:>11}" for n in folds))
    print(f"  {'-' * 7:>7}{'-' * 9:>9}{'-' * 14:>14}{'-' * 12:>12}   " + "".join(f"{'-' * 11:>11}" for _ in folds))
    best = None
    for share in SHARES:
        for beta in LIMIT_FACTORS:
            make = build(share, beta)
            got = total(make)
            cells = "".join(
                f"{total(make, subset) - baselines[name]:>11,.0f}" for name, subset in folds.items()
            )
            positive = sum(
                1 for name, subset in folds.items() if total(make, subset) - baselines[name] > 0
            )
            print(f"  {share:>7.2f}{beta:>9.2f}{got:>14,.0f}{got - actual:>12,.0f}   {cells}")
            if best is None or got > best[2]:
                best = (share, beta, got, positive)
    print(
        f"\n  best: share={best[0]:.2f} limit={best[1]:.2f} at {best[2]:,.0f} weighted "
        f"(gain {best[2] - actual:,.0f}), positive on {best[3]}/5 folds"
    )


if __name__ == "__main__":
    main()
