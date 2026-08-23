"""Is case-anchored recalibration worth money? Replayed against the real Field, all 100 Games.

`src/evidence/case_anchor.py` reduces RMSLE on the Line Items Price Memory misses from 0.887 to
0.756. That is a statement about log error, and CLAUDE.md is explicit that log error is not the
scoring function: it weights a EUR 10 Line Item the same as a EUR 7,000 one, and the payoff table
does not. So the change is scored here in euros, against the Field's real Charges and Limits,
with the recovered Fair Value brackets -- the only measurement that decides anything.

What is held fixed
------------------
Everything except the estimate on the Line Items memory missed. The pricing rules are the shipped
ones, the Limit is whatever we really submitted, memory hits keep the blend they really got, and
no model is called. Every euro of difference is the Case shift and nothing else.

The arms
--------
    ACTUAL        what we really submitted
    ANCHORED      memory-miss Line Items corrected by the Case shift, hits untouched
    ANCHORED+WARM memory-miss corrected AND memory hits repriced from the finished store,
                  i.e. the Case shift stacked on top of the H25 warm-store result

Both anchored arms use only information available before the Game settled: the memory store is
built leave-one-Game-out, and the shift is measured from memory hits rather than from `t`.

Usage
-----
    PYTHONPATH=. python scripts/experiments/case_anchor_backtest.py
    PYTHONPATH=. python scripts/experiments/case_anchor_backtest.py --sweep-min-hits
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))

from memory_first import CHARGE_FACTOR, build_predictions  # noqa: E402
from replay_payoffs import US, our_actual_submission, reconstruction_status, replay, snapshot  # noqa: E402

from src.evidence import case_anchor  # noqa: E402

EXPORT = ROOT / "var" / "export" / "line_items.csv"
WEIGHTED = frozenset(range(81, 101))

#: `blend.combine`'s memory share at the shipped constants (MEMORY_SIGMA 0.43,
#: MODEL_SIGMA_PRIOR 0.6). Needed to undo the blend and recover the model's own reading.
MEMORY_SHARE = (1 / 0.43**2) / ((1 / 0.43**2) + (1 / 0.6**2))

LIMIT_FACTOR = 1.0


def weight(game_id: int) -> float:
    return 3.0 if game_id in WEIGHTED else 1.0


def _f(row, key):
    value = (row.get(key) or "").strip()
    if value in ("", "None"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_estimates() -> dict[int, dict[int, float]]:
    """`{game: {index: blended t_hat}}` exactly as the live pipeline produced it."""
    out: dict[int, dict[int, float]] = defaultdict(dict)
    for row in csv.DictReader(EXPORT.open()):
        t_hat = _f(row, "t_hat")
        if t_hat and t_hat > 0:
            out[int(row["game_id"])][int(row["line_item_index"])] = t_hat
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep-min-hits", action="store_true")
    args = parser.parse_args()

    estimates = load_estimates()
    predictions = build_predictions(list(range(1, 101)), "loo")
    snaps = [s for s in (snapshot(g, US) for g in range(1, 101)
                         if reconstruction_status(g, US).usable)
             if s.game_id in estimates]
    print(f"\n{len(snaps)} Games carry a logged estimate.\n")

    def shift_for(game_id: int, line_items, min_hits: int) -> case_anchor.CaseShift:
        rows = []
        for index in line_items:
            memory = predictions.get(game_id, {}).get(index)
            blended = estimates.get(game_id, {}).get(index)
            if memory and blended:
                rows.append({"memory": memory, "blended": blended})
        saved = case_anchor.MIN_HITS
        case_anchor.MIN_HITS = min_hits
        try:
            return case_anchor.measure(rows, memory_share=MEMORY_SHARE)
        finally:
            case_anchor.MIN_HITS = saved

    def build(snap, *, anchored: bool, warm: bool, min_hits: int):
        mine = our_actual_submission(snap)
        hits = predictions.get(snap.game_id, {})
        logged = estimates.get(snap.game_id, {})
        shift = shift_for(snap.game_id, snap.line_items, min_hits) if anchored else None
        out = {}
        for index in snap.line_items:
            memory = hits.get(index)
            if memory and warm:
                out[index] = (CHARGE_FACTOR * memory, LIMIT_FACTOR * memory)
                continue
            if memory or not anchored:
                out[index] = mine[index]
                continue
            blended = logged.get(index)
            if not blended:
                out[index] = mine[index]
                continue
            # A memory miss: `blended` IS the model's own reading, nothing to undo.
            corrected = shift.apply(blended)
            charge, limit = mine[index]
            scale = corrected / blended if blended > 0 else 1.0
            out[index] = (charge * scale, limit * scale)
        return out

    def total(fn, subset=None):
        return sum(replay(s, fn(s)).net * weight(s.game_id) for s in (subset or snaps))

    folds = {
        "odd": [s for s in snaps if s.game_id % 2],
        "even": [s for s in snaps if not s.game_id % 2],
        "26-62": [s for s in snaps if s.game_id <= 62],
        "63-100": [s for s in snaps if s.game_id > 62],
    }
    actual = total(our_actual_submission)
    base_folds = {k: total(our_actual_submission, v) for k, v in folds.items()}

    if args.sweep_min_hits:
        print(f"  {'MIN_HITS':>9}{'weighted':>14}{'vs actual':>13}   " +
              "".join(f"{k:>11}" for k in folds))
        print(f"  {'-'*9:>9}{'-'*14:>14}{'-'*13:>13}   " + "".join(f"{'-'*11:>11}" for _ in folds))
        for mh in (2, 3, 4, 5, 6):
            fn = lambda s, mh=mh: build(s, anchored=True, warm=False, min_hits=mh)
            got = total(fn)
            cells = "".join(f"{total(fn, v) - base_folds[k]:>11,.0f}" for k, v in folds.items())
            print(f"  {mh:>9}{got:>14,.0f}{got - actual:>+13,.0f}   {cells}")
        return

    mh = case_anchor.MIN_HITS
    arms = {
        "ACTUAL": lambda s: our_actual_submission(s),
        "ANCHORED": lambda s: build(s, anchored=True, warm=False, min_hits=mh),
        "ANCHORED+WARM": lambda s: build(s, anchored=True, warm=True, min_hits=mh),
        "WARM only (H25)": lambda s: build(s, anchored=False, warm=True, min_hits=mh),
    }
    print(f"  {'arm':<18}{'weighted':>14}{'vs actual':>13}   " + "".join(f"{k:>11}" for k in folds))
    print(f"  {'-'*18:<18}{'-'*14:>14}{'-'*13:>13}   " + "".join(f"{'-'*11:>11}" for _ in folds))
    for name, fn in arms.items():
        got = total(fn)
        cells = "".join(f"{total(fn, v) - base_folds[k]:>11,.0f}" for k, v in folds.items())
        print(f"  {name:<18}{got:>14,.0f}{got - actual:>+13,.0f}   {cells}")

    applied = sum(
        1 for s in snaps if shift_for(s.game_id, s.line_items, mh).applies
    )
    print(f"\n  the shift applies in {applied} of {len(snaps)} Games (MIN_HITS = {mh})")


if __name__ == "__main__":
    main()
