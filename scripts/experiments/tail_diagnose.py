"""Decompose Strategy 2's tail loss: is the median wrong, or is the band too wide?

The two causes need different fixes, so measure them apart. Every variant below reprices
the *same* cached model evidence and is scored with `replay_payoffs.replay`, in euros.

    variant            what it changes
    ------------------ ---------------------------------------------------------------
    baseline           the evidence exactly as the model returned it
    oracle-median      keeps the model's band width and coverage, moves the median to t
    tight-band         keeps the model's median, collapses the band to sigma 0.15
    oracle-coverage    keeps the model's band, sets coverage from the true bracket
    oracle             charge and limit both at t (the ceiling of this harness)

    pixi run python scripts/tail_diagnose.py --games 1-14
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

from src.pricing import Evidence, price_item  # noqa: E402

INF = math.inf
BAND_Z = 1.645


def _sub(case, evidence, snap) -> dict[int, tuple[float, float]]:
    return submission_of(case, evidence, memory=False)


def variants(case, model, snap) -> dict[str, dict[int, tuple[float, float]]]:
    out: dict[str, dict[int, tuple[float, float]]] = {}
    out["baseline"] = _sub(case, model, snap)

    oracle_median: dict[int, Evidence] = {}
    tight: dict[int, Evidence] = {}
    oracle_cov: dict[int, Evidence] = {}
    for index, ev in model.items():
        t = snap.fair_point(index) if index in snap.fair_brackets else ev.price_median
        scale = t / ev.price_median if ev.price_median > 0 and t > 0 else 1.0
        oracle_median[index] = Evidence(
            index, ev.coverage_probability, ev.price_low * scale, t, ev.price_high * scale
        )
        median = ev.price_median
        tight[index] = Evidence(
            index,
            ev.coverage_probability,
            median * math.exp(-BAND_Z * 0.15),
            median,
            median * math.exp(BAND_Z * 0.15),
        )
        covered = 1.0 if (index in snap.fair_brackets and snap.fair_brackets[index][0] > 0) else 0.0
        oracle_cov[index] = Evidence(
            index, covered, ev.price_low, ev.price_median, ev.price_high
        )
    out["oracle-median"] = _sub(case, oracle_median, snap)
    out["tight-band"] = _sub(case, tight, snap)
    out["oracle-coverage"] = _sub(case, oracle_cov, snap)
    out["oracle"] = {i: (snap.fair_point(i), snap.fair_point(i)) for i in snap.line_items}
    return out


def level_stats(model, snap) -> list[tuple[float, float, float]]:
    """(t, model median, ratio) for every item with a positive true Fair Value."""
    rows = []
    for index, ev in model.items():
        if index not in snap.fair_brackets:
            continue
        lo, hi = snap.fair_brackets[index]
        t = snap.fair_point(index)
        if t <= 0 or ev.price_median <= 0:
            continue
        rows.append((t, ev.price_median, ev.price_median / t))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--tag", default="model")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))

    names = ["baseline", "oracle-median", "tight-band", "oracle-coverage", "oracle"]
    totals = {name: 0.0 for name in names}
    rows: list[tuple[float, float, float]] = []
    header = f"{'game':>5}" + "".join(f"{name:>17}" for name in names)
    print(header)
    for game_id in game_ids:
        model = load_evidence(game_id, args.tag)
        case = case_of(game_id)
        if model is None or case is None:
            continue
        snap = snapshot(game_id)
        line = f"{game_id:5d}"
        for name, submission in variants(case, model, snap).items():
            net = replay(snap, submission).net
            totals[name] += net
            line += f"{net:17,.0f}"
        print(line)
        rows += level_stats(model, snap)
    print(f"{'TOTAL':>5}" + "".join(f"{totals[name]:17,.0f}" for name in names))

    if rows:
        rows.sort(key=lambda r: r[0])
        print(f"\nlevel error over {len(rows)} items with t > 0, by true Fair Value decile:")
        buckets = [(0, 50), (50, 150), (150, 400), (400, 1000), (1000, 1e9)]
        for lo, hi in buckets:
            sel = [r for r in rows if lo <= r[0] < hi]
            if not sel:
                continue
            ratios = sorted(r[2] for r in sel)
            euro_short = sum(max(r[0] - r[1], 0.0) for r in sel)
            print(
                f"  t in [{lo:>5},{hi:>8}) n={len(sel):3d} "
                f"median a_hat/t={ratios[len(ratios) // 2]:5.2f} "
                f"share under-priced={sum(1 for r in ratios if r < 1) / len(ratios):4.0%} "
                f"euro shortfall={euro_short:9,.0f}"
            )
        rmsle = math.sqrt(sum(math.log(r[2]) ** 2 for r in rows) / len(rows))
        print(f"  overall RMSLE = {rmsle:.3f}")


if __name__ == "__main__":
    main()
