"""Split Price Memory's leave-one-out log error by match type (exact/core) and basis
(per_unit/gross), to resolve whether SIGMA_LOG=0.43 is a measurement of a narrower
population than build_price_memory.py --evaluate's pooled 0.581/0.659.

Read-only, offline (uses cached var/transactions + local invoice PDFs; no LLM calls, no
network unless a cache is missing). Never writes var/price_memory.json.

    PYTHONPATH=. python scripts/experiments/sigma_by_match_type.py --games 1-14
    PYTHONPATH=. python scripts/experiments/sigma_by_match_type.py --games 1-37
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_price_memory as bpm  # noqa: E402
from src.evidence.memory import PriceMemory, build_entries  # noqa: E402


def evaluate_by_bucket(records: list[dict], games: list[int], per_unit: bool = True) -> dict:
    """Leave-one-out, same protocol as build_price_memory.evaluate(), but every scored
    hit is filed into (match, basis) buckets instead of pooled into one sigma."""
    buckets: dict[tuple[str, str], list[float]] = {}
    pooled: list[float] = []
    n_scorable = 0
    n_hit = 0
    for game_id in games:
        held_out = [r for r in records if r["game"] == game_id and r["positive"]]
        if not held_out:
            continue
        training = [r for r in records if r["game"] != game_id]
        if not per_unit:
            training = [dict(r, value=r["t_point"], basis="gross") for r in training]
        memory = PriceMemory.from_dict({"entries": build_entries(training)})
        for record in held_out:
            n_scorable += 1
            query_unit = record["unit"] if per_unit else ""
            hit = memory.lookup(record["display_name"], unit=query_unit, quantity=record["quantity"])
            if hit is None or hit.median <= 0:
                continue
            n_hit += 1
            err = math.log(hit.median / record["t_point"])
            pooled.append(err)
            buckets.setdefault((hit.match, hit.basis), []).append(err)
    basis_only: dict[str, list[float]] = {}
    for (_match, basis), errs in buckets.items():
        basis_only.setdefault(basis, []).extend(errs)
    match_only: dict[str, list[float]] = {}
    for (match, _basis), errs in buckets.items():
        match_only.setdefault(match, []).extend(errs)
    return {
        "n_scorable": n_scorable,
        "n_hit": n_hit,
        "pooled": pooled,
        "buckets": buckets,
        "basis_only": basis_only,
        "match_only": match_only,
    }


def _stats(errors: list[float]) -> tuple[int, float, float, float]:
    if not errors:
        return 0, float("nan"), float("nan"), float("nan")
    n = len(errors)
    bias = statistics.mean(errors)
    sigma = statistics.pstdev(errors) if n > 1 else 0.0
    rmsle = math.sqrt(sum(e * e for e in errors) / n)
    return n, bias, sigma, rmsle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-14")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    games = list(range(int(start), int(end or start) + 1))

    print(f"Loading invoice observations for Games {games[0]}-{games[-1]} "
          f"(pdftotext + cached transactions, offline)...")
    records = bpm.observations(games)
    print(f"  {len(records)} Line Items joined, "
          f"{sum(1 for r in records if r['positive'])} with proven positive t")

    for label, per_unit in (("per-unit rule ON (as shipped)", True), ("per-unit rule OFF (all gross)", False)):
        print(f"\n{'=' * 78}\n{label}\n{'=' * 78}")
        result = evaluate_by_bucket(records, games, per_unit=per_unit)
        n, bias, sigma, rmsle = _stats(result["pooled"])
        print(f"POOLED (what --evaluate reports today): n={n}/{result['n_scorable']} "
              f"recall={n / max(result['n_scorable'], 1):.0%} "
              f"bias={bias:+.3f} sigma(pstdev)={sigma:.3f} RMSLE={rmsle:.3f}")
        print(f"\n{'bucket (match, basis)':<28}{'n':>5}{'bias':>9}{'sigma':>9}{'RMSLE':>9}")
        for key in sorted(result["buckets"], key=lambda k: -len(result["buckets"][k])):
            errs = result["buckets"][key]
            n_b, bias_b, sigma_b, rmsle_b = _stats(errs)
            print(f"{str(key):<28}{n_b:>5}{bias_b:>+9.3f}{sigma_b:>9.3f}{rmsle_b:>9.3f}")
        print(f"\n{'bucket (basis only, match pooled)':<34}{'n':>5}{'bias':>9}{'sigma':>9}{'RMSLE':>9}")
        for key in sorted(result["basis_only"], key=lambda k: -len(result["basis_only"][k])):
            errs = result["basis_only"][key]
            n_b, bias_b, sigma_b, rmsle_b = _stats(errs)
            print(f"{key:<34}{n_b:>5}{bias_b:>+9.3f}{sigma_b:>9.3f}{rmsle_b:>9.3f}")
        print(f"\n{'bucket (match only, basis pooled)':<34}{'n':>5}{'bias':>9}{'sigma':>9}{'RMSLE':>9}")
        for key in sorted(result["match_only"], key=lambda k: -len(result["match_only"][k])):
            errs = result["match_only"][key]
            n_b, bias_b, sigma_b, rmsle_b = _stats(errs)
            print(f"{key:<34}{n_b:>5}{bias_b:>+9.3f}{sigma_b:>9.3f}{rmsle_b:>9.3f}")

    print(f"\nCurrent shipped constants: SIGMA_LOG (memory.py) = 0.43, "
          f"measured_leave_one_out_sigma_log (build_price_memory.py payload) = 0.43 (hardcoded)")


if __name__ == "__main__":
    main()
