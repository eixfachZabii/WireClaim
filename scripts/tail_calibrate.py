"""Sweep post-processing of the model's band, scored in euros on the real Field.

`tail_diagnose.py` says the level of the median is the dominant lever and that the model's
band is far *narrower* than its actual error (implied sigma ~0.45, measured RMSLE ~1.3).
This sweeps the two knobs that follow from that -- a multiplier on the median and a floor
under the implied sigma -- with `replay_payoffs.replay` as the objective.

    pixi run python scripts/tail_calibrate.py --games 1-14
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from replay_payoffs import replay, snapshot  # noqa: E402
from tail_replay import case_of, load_evidence, submission_of  # noqa: E402

from src.pricing import Evidence  # noqa: E402

BAND_Z = 1.645


def reshape(ev: Evidence, multiplier: float, sigma_floor: float) -> Evidence:
    median = ev.price_median * multiplier
    if median <= 0:
        return ev
    sigma = 1.0
    if ev.price_low > 0 and ev.price_high > ev.price_low:
        sigma = math.log(ev.price_high / ev.price_low) / (2 * BAND_Z)
    sigma = max(sigma, sigma_floor)
    return Evidence(
        index=ev.index,
        coverage_probability=ev.coverage_probability,
        price_low=median * math.exp(-BAND_Z * sigma),
        price_median=median,
        price_high=median * math.exp(BAND_Z * sigma),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--tag", default="model")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))

    loaded = []
    for game_id in game_ids:
        model = load_evidence(game_id, args.tag)
        case = case_of(game_id)
        if model is None or case is None:
            continue
        loaded.append((snapshot(game_id), case, model))

    multipliers = [0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0]
    floors = [0.0, 0.3, 0.5, 0.7, 0.9, 1.1, 1.3]
    print("net (EUR) by median multiplier (rows) x implied-sigma floor (cols)")
    print("      " + "".join(f"{f:>12}" for f in floors))
    best = (-1e18, None)
    for multiplier in multipliers:
        line = f"{multiplier:5.1f} "
        for floor in floors:
            total = 0.0
            for snap, case, model in loaded:
                reshaped = {i: reshape(ev, multiplier, floor) for i, ev in model.items()}
                total += replay(snap, submission_of(case, reshaped, memory=False)).net
            line += f"{total:12,.0f}"
            if total > best[0]:
                best = (total, (multiplier, floor))
        print(line)
    print(f"best: multiplier={best[1][0]} sigma_floor={best[1][1]} net {best[0]:,.0f}")


if __name__ == "__main__":
    main()
