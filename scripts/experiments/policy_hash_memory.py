"""Does keying Price Memory on the Policy text separate regimes that the wording cannot?

    PYTHONPATH=. pixi run python scripts/experiments/policy_hash_memory.py

Cases 10, 41, 44 and 53 share one `policy.txt` byte for byte (md5 4fa9117f); Case 27 is a
different document (fa547b5e). That split is exactly the Part 11.1 regime split: the shared
policy says the affected items belong "partly to classes for which sub-limits are agreed ...
and partly to the general class under 4.2.1", and 11.2 pays a no-sub-limit class **in full**;
Case 27's says only "classes of property for which sub-limits are agreed", and it settled at
the cap, t in [3000.00, 3022.15).

The wording key cannot see that. `compensation for robbery damage` pools Game 27's 3,011 with
Game 41's 11,131 -- a 3.70x spread in one entry -- and returns their geometric mean, 5,789,
which is 1.92x too high for a sub-limited Case and 0.52x too low for a general one.

Three arms, leave-one-out over every settled Game:

    baseline      today's store: key on wording alone
    same-hash     train only on Cases sharing this Case's policy md5
    prefer-hash   same-hash when it hits, fall back to the full store when it misses

`same-hash` is the clean measurement of the signal and will cost recall. `prefer-hash` is the
shippable shape: it removes cross-regime contamination without giving up the 69% recall the
wording key already earns. Writes nothing.
"""
from __future__ import annotations

import hashlib
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_price_memory import CASES_DIR, observations  # noqa: E402

from src.evidence.memory import PriceMemory, build_entries  # noqa: E402


def policy_hash(game_id: int) -> str:
    path = CASES_DIR / f"case_{game_id:02d}" / "policy.txt"
    if not path.exists():
        return f"missing-{game_id}"
    return hashlib.md5(path.read_bytes()).hexdigest()[:8]


def _lookup(training, record):
    if not training:
        return None
    memory = PriceMemory.from_dict({"entries": build_entries(training)})
    return memory.lookup(record["display_name"], unit=record["unit"], quantity=record["quantity"])


def run(records, games, hashes, label=""):
    arms = {"baseline": [], "same-hash": [], "prefer-hash": []}
    for game_id in games:
        held_out = [r for r in records if r["game"] == game_id and r["positive"]]
        if not held_out:
            continue
        full = [r for r in records if r["game"] != game_id]
        same = [r for r in full if hashes.get(r["game"]) == hashes.get(game_id)]
        for record in held_out:
            truth = record["t_point"]
            hit_full = _lookup(full, record)
            hit_same = _lookup(same, record)
            if hit_full is not None and hit_full.median > 0:
                arms["baseline"].append(math.log(hit_full.median / truth))
            if hit_same is not None and hit_same.median > 0:
                arms["same-hash"].append(math.log(hit_same.median / truth))
            pref = hit_same if (hit_same is not None and hit_same.median > 0) else hit_full
            if pref is not None and pref.median > 0:
                arms["prefer-hash"].append(math.log(pref.median / truth))
    scorable = sum(1 for r in records if r["positive"] and r["game"] in set(games))
    if label:
        print(f"\n--- {label} ---")
    print(f"{'arm':14s} {'n':>5} {'recall':>8} {'sigma':>8} {'mean|log|':>10} {'bias':>8}")
    print("-" * 58)
    for name, errs in arms.items():
        if not errs:
            print(f"{name:14s} {0:5d}      n/a")
            continue
        print(
            f"{name:14s} {len(errs):5d} {len(errs)/scorable:7.0%} "
            f"{statistics.pstdev(errs):8.3f} {statistics.mean(abs(e) for e in errs):10.3f} "
            f"{statistics.mean(errs):+8.3f}"
        )
    return arms


def main() -> None:
    games = sorted(int(d.name.split("_")[1]) for d in CASES_DIR.iterdir()
                   if d.is_dir() and d.name.startswith("case_") and d.name.split("_")[1].isdigit())
    games = [g for g in games if g >= 1]
    records = observations(games, cases_dir=CASES_DIR)
    hashes = {g: policy_hash(g) for g in games}
    clusters: dict[str, list[int]] = {}
    for g, h in hashes.items():
        clusters.setdefault(h, []).append(g)
    shared = {h: gs for h, gs in clusters.items() if len(gs) > 1}
    covered = sum(len(gs) for gs in shared.values())
    print(f"{len(shared)} policy hashes shared by >1 Case, covering {covered}/{len(games)} Cases\n")
    run(records, games, hashes, "ALL")
    folds = {
        "ODD games": [g for g in games if g % 2],
        "EVEN games": [g for g in games if not g % 2],
        "EARLY (<=28)": [g for g in games if g <= 28],
        "LATE (>28)": [g for g in games if g > 28],
    }
    for name, subset in folds.items():
        run(records, subset, hashes, name)


if __name__ == "__main__":
    main()
