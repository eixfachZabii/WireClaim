"""sigma (RMSLE of log(t_hat/t)) by channel and by subset, bias and dispersion separated.

CLAUDE.md rule 10: use total log error (RMSLE), never a bare standard deviation, because
our failure mode is a *level bias*, not pure noise -- a stdev centres itself on whatever the
data gives it and cannot see a systematic over- or under-estimate. So every row below
reports three numbers, not one:

    bias      mean(log(t_hat/t))       -- the level error; 0 is unbiased, +0.3 is ~35% high
    dispersion  stdev of the log error around that mean -- the part a multiplier cannot fix
    RMSLE     sqrt(bias^2 + dispersion^2) = sqrt(mean(log(t_hat/t)^2)) -- the one number that
              answers "how wrong are we", and the one CLAUDE.md and ARCHITECTURE.md call the
              gate on everything.

Two populations, kept apart rather than pooled, per the rules of evidence in the task this
script was written for:

    logged   Games 26-32 (var/decisions).  What the live pipeline actually decided. Small
             (n=7 Games) but ground truth about *this session's* pipeline.
    recon    Games 1-25.  `build_proposal` re-run offline on cached model + Price Memory
             evidence (`scripts/charge_buckets._recon_rows`), i.e. "what today's pricing
             would have done" -- not what was actually submitted (Games 1-20 mostly predate
             Strategy 2 or ran different constants). Price Memory here is looked up against
             *today's* store, which has absorbed every settled Game including ones that
             postdate the Game being scored -- a look-ahead Channel B never had live. Kept
             separate and labelled, never pooled into the headline number.

sigma is computed only on Line Items whose Fair Value bracket is bounded above
(`t_hi != inf`), same convention as `scripts/backtest.py`. That excludes 44 of 192 items in
the original sample -- the ones nobody ever rightfully rejected, plausibly the expensive
tail -- so every number here is the optimistic case, stated once and not repeated per row.

    PYTHONPATH=. pixi run python scripts/leak_sigma.py
"""

from __future__ import annotations

import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from charge_buckets import Row, dataset  # noqa: E402

INF = math.inf


def log_errors(rows: list[Row]) -> list[float]:
    out = []
    for r in rows:
        if r.t_hi == INF or r.t_lo < 0:
            continue
        t_mid = (r.t_lo + r.t_hi) / 2.0
        if t_mid <= 0 or r.median <= 0:
            continue
        out.append(math.log(r.median / t_mid))
    return out


def report(label: str, rows: list[Row]) -> dict | None:
    errs = log_errors(rows)
    if not errs:
        print(f"  {label:<26} n=0 (nothing bounded)")
        return None
    bias = st.fmean(errs)
    dispersion = st.pstdev(errs) if len(errs) > 1 else 0.0
    rmsle = math.sqrt(sum(e * e for e in errs) / len(errs))
    print(
        f"  {label:<26} n={len(errs):3d}  bias={bias:+.3f}  dispersion={dispersion:.3f}  "
        f"RMSLE={rmsle:.3f}  median t_hat/t={math.exp(st.median(errs)):.2f}x"
    )
    return {"n": len(errs), "bias": bias, "dispersion": dispersion, "rmsle": rmsle}


def channel_label(row: Row) -> str:
    if row.uncovered:
        return "A:no-quantity"
    if row.has_memory and "C:model" in row.channels:
        return "B+C:memory+model"
    if row.has_memory:
        return "B:memory-only"
    if "C:model" in row.channels:
        return "C:model-only"
    return "none"


def main() -> None:
    all_rows = dataset(games=tuple(range(1, 33)))
    logged = [r for r in all_rows if r.origin == "logged"]
    recon = [r for r in all_rows if r.origin == "recon"]

    for pop_label, pop_all in (("LOGGED (Games 26-32, real decisions)", logged),
                                ("RECON (Games 1-25, offline replay of today's pipeline)", recon),
                                ("POOLED (both, for reference only)", all_rows)):
        print(f"\n=== {pop_label} ===")
        print(
            "-- t_lo = 0 items (free option; price accuracy CANNOT move the payoff here, "
            "coverage=0 zeroes the Limit and a rejected Overcharge costs nothing) --"
        )
        report("t_lo = 0 (uneconomic to score)", [r for r in pop_all if r.t_lo <= 0])

        pop = [r for r in pop_all if r.t_lo > 0]
        print(f"-- everything below is the {len(pop)} rows with t_lo > 0 (real money; "
              f"price accuracy here is what the payoff table actually prices) --")
        print("-- by channel --")
        for label in ("A:no-quantity", "B:memory-only", "B+C:memory+model", "C:model-only"):
            report(label, [r for r in pop if channel_label(r) == label])

        print("-- by magnitude of the estimate (t_hat) --")
        report("t_hat < 50", [r for r in pop if r.median < 50])
        report("t_hat 50-500", [r for r in pop if 50 <= r.median < 500])
        report("t_hat >= 500", [r for r in pop if r.median >= 500])

        print("-- by invoice unit --")
        report("metered (hr/m2/day/kg)", [r for r in pop if r.metered])
        report("pcs / flat rate", [r for r in pop if not r.metered and r.unit != "unknown"])

        print("-- by quantity extraction --")
        report("quantity present", [r for r in pop if not r.uncovered])
        report("quantity missing (dash)", [r for r in pop if r.uncovered])

        print("-- by coverage probability --")
        report("coverage <= 2/3", [r for r in pop if r.coverage <= 2 / 3])
        report("coverage 2/3-0.9", [r for r in pop if 2 / 3 < r.coverage < 0.9])
        report("coverage >= 0.9", [r for r in pop if r.coverage >= 0.9])


if __name__ == "__main__":
    main()
