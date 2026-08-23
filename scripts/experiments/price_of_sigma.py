"""What one unit of estimation accuracy is worth, in euros, over all 100 Games.

`ceiling.py` establishes that 103 % of everything still on the table above what we submitted is
estimation quality, and that no constant-tuning of the decision rules reaches any of it. That
settles *where* to spend effort but not *how much* -- "improve the estimate" is not a plan until
someone can say what a given improvement pays.

So this measures the curve directly. For a grid of log errors `sigma`, a synthetic estimator is
built by perturbing the **true** Fair Value:

    t_hat = t * exp(N(-sigma^2 / 2, sigma^2))

(the mean correction makes it unbiased in levels, so the curve isolates *dispersion* and does
not smuggle in a level error), priced with the shipped rule `a = 0.69 t_hat`, `b` swept, and
replayed against the real Field. Averaged over `--trials` seeds so the answer is a curve and
not one draw.

Two things this is good for and one it is not:

* it converts "get RMSLE from 0.66 to 0.45" into a number of euros, which is the only way to
  compare an evidence-layer change against anything else;
* it locates the break-even sigma -- the accuracy at which a smart bot stops beating a dumb one.

It is **not** a claim that any particular sigma is achievable. It prices accuracy; it does not
promise it.

Usage
-----
    PYTHONPATH=. python scripts/experiments/price_of_sigma.py
    PYTHONPATH=. python scripts/experiments/price_of_sigma.py --trials 8
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from replay_payoffs import US, reconstruction_status, replay, snapshot  # noqa: E402

WEIGHTED = frozenset(range(81, 101))

#: The shipped Charge multiplier (`CHARGE_INTERCEPT - CHARGE_SLOPE * sigma` lands here for a
#: typical band). Held fixed so the curve reads as the value of accuracy, not of retuning.
CHARGE_FACTOR = 0.69
SIGMAS = [0.0, 0.1, 0.2, 0.3, 0.45, 0.6, 0.75, 0.9, 1.1, 1.4]
BETAS = [0.5, 0.75, 1.0, 1.25]


def weight(game_id: int) -> float:
    return 3.0 if game_id in WEIGHTED else 1.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260823)
    args = parser.parse_args()

    snaps = [
        snapshot(g, US) for g in range(1, 101) if reconstruction_status(g, US).usable
    ]
    print(f"\n{len(snaps)} reconstructable Games, {args.trials} trials per cell\n")

    print(f"  {'sigma':>7}{'best beta':>11}{'net (1x)':>16}{'net (weighted)':>18}{'vs actual':>15}")
    print(f"  {'-' * 7:>7}{'-' * 11:>11}{'-' * 16:>16}{'-' * 18:>18}{'-' * 15:>15}")

    actual_w = sum(
        replay(s, {i: (s.charges[i][US], s.limit_point(i, US)) for i in s.line_items}).net
        * weight(s.game_id)
        for s in snaps
    )

    rows = []
    for sigma in SIGMAS:
        best = None
        for beta in BETAS:
            raw = weighted = 0.0
            for trial in range(args.trials):
                rng = random.Random(args.seed + trial * 7919)
                for snap in snaps:
                    submission = {}
                    for index in snap.line_items:
                        t = snap.fair_point(index)
                        noise = (
                            math.exp(rng.gauss(-sigma * sigma / 2.0, sigma)) if sigma > 0 else 1.0
                        )
                        t_hat = t * noise
                        submission[index] = (CHARGE_FACTOR * t_hat, beta * t_hat)
                    net = replay(snap, submission).net
                    raw += net
                    weighted += net * weight(snap.game_id)
            raw /= args.trials
            weighted /= args.trials
            if best is None or weighted > best[2]:
                best = (beta, raw, weighted)
        rows.append((sigma, *best))
        print(
            f"  {sigma:>7.2f}{best[0]:>11.2f}{best[1]:>16,.0f}{best[2]:>18,.0f}"
            f"{best[2] - actual_w:>15,.0f}"
        )

    print(f"\n  our real submission scored {actual_w:,.0f} weighted")
    crossing = next((s for s, _, _, w in rows if w < actual_w), None)
    print(
        f"  a synthetic estimator matches what we actually did at sigma ~ "
        f"{crossing if crossing is not None else '>1.4'}"
    )
    print(f"\n  {'MARGINAL VALUE OF ACCURACY':<44}{'weighted euros':>18}")
    print(f"  {'-' * 44:<44}{'-' * 18:>18}")
    for (s0, _, _, w0), (s1, _, _, w1) in zip(rows, rows[1:]):
        print(f"  {f'sigma {s1:.2f} -> {s0:.2f}':<44}{w0 - w1:>18,.0f}")


if __name__ == "__main__":
    main()
