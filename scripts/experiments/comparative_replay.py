"""The comparative estimator, priced in euros against the real Field. The test that decides.

`comparative_estimator.py` measures the new architecture in log error over the Line Items Price
Memory misses: **DIRECT 0.943, ANCHORED 0.867**, against the retired model channel's ~1.0. H28's
specification is sigma < 0.60, so on that evidence it should not pay -- but log error is not the
scoring function, this repository has been wrong about the sign of that translation before, and
the estimates are already bought and on disk. So it gets replayed.

How the substitution is done, and why
-------------------------------------
For a Line Item where memory misses and the new estimator produced a value, our real submission
is **scaled** by `new / old` rather than repriced from scratch. That keeps the shipped Limit stack
-- the posterior quantile, its ceiling and the released clamp -- intact and changes only the level,
so the measurement isolates the estimate. Flattening the Limit to a constant was measured
separately at **-141,650**, and folding that penalty in here would hide whatever the estimator does.

Games 1-25 have no logged estimate to scale from, so those items are priced fresh at the shipped
multipliers (`a = 0.69 t_hat`, `b = 1.0 t_hat`). That is stated because it is the one place the
arm is not a pure isolation.

Arms
----
    ACTUAL            what we really submitted
    +DIRECT           misses repriced by Gemini asked for a price   (the old framing, new model)
    +ANCHORED         misses repriced by the comparative estimator  (the new framing)
    +ENSEMBLE         misses repriced by the geometric mean of the two, which scored best in
                      log error (0.788) by exploiting their complementary errors
    WARM +ANCHORED    the finished Price Memory on its hits AND the comparative estimator on the
                      misses -- the complete proposed pipeline, both halves at once

Usage
-----
    PYTHONPATH=. pixi run python scripts/experiments/comparative_replay.py
"""

from __future__ import annotations

import argparse
import csv
import json
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

WEIGHTED = frozenset(range(81, 101))
LIMIT_FACTOR = 1.0
EXPORT = ROOT / "var" / "export" / "line_items.csv"


def weight(game_id: int) -> float:
    return 3.0 if game_id in WEIGHTED else 1.0


def load_logged() -> dict[int, dict[int, float]]:
    out: dict[int, dict[int, float]] = defaultdict(dict)
    if not EXPORT.exists():
        return out
    for row in csv.DictReader(EXPORT.open()):
        try:
            value = float(row["t_hat"])
        except (TypeError, ValueError):
            continue
        if value > 0:
            out[int(row["game_id"])][int(row["line_item_index"])] = value
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estimates", type=Path, default=ROOT / "var" / "comparative_all.json")
    args = parser.parse_args()

    rows = json.loads(args.estimates.read_text())
    new: dict[int, dict[int, dict]] = defaultdict(dict)
    for row in rows:
        new[int(row["game"])][int(row["index"])] = row
    logged = load_logged()
    predictions = build_predictions(list(range(1, 101)), "loo")
    snaps = [snapshot(g, US) for g in range(1, 101) if reconstruction_status(g, US).usable]
    priced = sum(len(v) for v in new.values())
    print(f"\n{priced} memory-miss Line Items carry a new estimate, over {len(snaps)} Games.\n")

    def value_of(row: dict, key: str) -> float | None:
        if key == "ensemble":
            a, d = row.get("anchored"), row.get("direct")
            if a and d and a > 0 and d > 0:
                return math.exp((math.log(a) + math.log(d)) / 2)
            return a or d
        value = row.get(key)
        return value if value and value > 0 else None

    def build(key: str | None, warm: bool):
        def make(snap):
            mine = our_actual_submission(snap)
            hits = predictions.get(snap.game_id, {})
            out = {}
            for index in snap.line_items:
                memory = hits.get(index)
                if memory and warm:
                    out[index] = (CHARGE_FACTOR * memory, LIMIT_FACTOR * memory)
                    continue
                if memory or key is None:
                    out[index] = mine[index]
                    continue
                row = new.get(snap.game_id, {}).get(index)
                estimate = value_of(row, key) if row else None
                if not estimate:
                    out[index] = mine[index]
                    continue
                old = logged.get(snap.game_id, {}).get(index)
                if old and old > 0:
                    # Scale our real submission: keeps the shipped Limit stack, moves the level.
                    scale = estimate / old
                    charge, limit = mine[index]
                    out[index] = (charge * scale, limit * scale)
                else:
                    out[index] = (CHARGE_FACTOR * estimate, LIMIT_FACTOR * estimate)
            return out
        return make

    folds = {
        "odd": [s for s in snaps if s.game_id % 2],
        "even": [s for s in snaps if not s.game_id % 2],
        "1-50": [s for s in snaps if s.game_id <= 50],
        "51-100": [s for s in snaps if s.game_id > 50],
    }

    def total(make, subset=None):
        return sum(replay(s, make(s)).net * weight(s.game_id) for s in (subset or snaps))

    actual = total(our_actual_submission)
    base = {k: total(our_actual_submission, v) for k, v in folds.items()}

    arms = [
        ("ACTUAL", build(None, False)),
        ("+DIRECT on misses", build("direct", False)),
        ("+ANCHORED on misses", build("anchored", False)),
        ("+ENSEMBLE on misses", build("ensemble", False)),
        ("WARM + ANCHORED", build("anchored", True)),
        ("WARM only (H25)", build(None, True)),
    ]
    print(f"  {'arm':<22}{'weighted':>13}{'vs actual':>12}{'up/dn':>9}   " +
          "".join(f"{k:>10}" for k in folds))
    print(f"  {'-'*22:<22}{'-'*13:>13}{'-'*12:>12}{'-'*9:>9}   " +
          "".join(f"{'-'*10:>10}" for _ in folds))
    for name, make in arms:
        per = {s.game_id: replay(s, make(s)).net * weight(s.game_id) for s in snaps}
        got = sum(per.values())
        delta = {g: per[g] - replay(snapshot(g, US), our_actual_submission(snapshot(g, US))).net
                 * weight(g) for g in per}
        cells = "".join(
            f"{sum(per[s.game_id] for s in v) - base[k]:>10,.0f}" for k, v in folds.items()
        )
        pos = sum(1 for k, v in folds.items() if sum(per[s.game_id] for s in v) - base[k] > 0)
        up = sum(1 for x in delta.values() if x > 1)
        down = sum(1 for x in delta.values() if x < -1)
        print(f"  {name:<22}{got:>13,.0f}{got - actual:>+12,.0f}{f'{up}/{down}':>9}   {cells}  {pos}/4")


if __name__ == "__main__":
    main()
