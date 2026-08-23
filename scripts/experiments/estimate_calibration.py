"""Is our Fair Value estimate biased, badly spread, or badly *calibrated*? Three different faults.

The Limit rule is `b = Q_(1/3)` of our posterior on `t`, and R4 proves that is optimal: accept
`a` exactly when `P(a <= t) > 2/3`. The rule can only be as good as the posterior it quantiles,
and a posterior can fail in three independent ways that a single "sigma" hides:

* **bias** -- `median(t_hat / t)` away from 1. A level error. Fixable with one multiplier.
* **dispersion** -- how far `t_hat` scatters around `t`. Sets how far down `Q_(1/3)` must sit.
* **calibration** -- whether the band we *emit* (`price_low`, `price_high`) matches the error we
  actually make. This is the one that matters and the one nobody measures: if we declare a
  narrow band on an item we in fact get badly wrong, `Q_(1/3)` is a confident number in the
  wrong place, and R4b says the whole rule collapses.

Calibration is measured by PIT (probability integral transform): under our own stated
lognormal posterior, `u = Phi(log(t / t_hat) / sigma_hat)` must be **uniform on [0, 1]** if the
posterior is honest. Two failure signatures:

    u piles up at 0 and 1   ->  the band is too NARROW; reality lands outside it
    u piles up in the middle->  the band is too WIDE; we are needlessly timid
    u skews to one side     ->  bias, already visible in the median

The quantity that decides the Limit is `P(u < 1/3)`. If our `Q_(1/3)` were honest, the Fair
Value would fall below it on exactly a third of Line Items. Whatever that number really is,
*is* the Limit's error, in the only units that matter.

Censoring, stated up front
--------------------------
`t` is a bracket `[t_lo, t_hi)`. Unbounded brackets (nobody rightfully rejected) are excluded
from every ratio, and CLAUDE.md is explicit that this selects on the outcome, so every sigma
here is **optimistic**. The bounded/unbounded split is printed so the reader can judge it, and
the one-sided statistic `P(t_hat > t_lo)` -- which needs no upper bracket and is therefore
uncensored -- is reported alongside as the check.

Usage
-----
    PYTHONPATH=. python scripts/experiments/estimate_calibration.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EXPORT = ROOT / "var" / "export" / "line_items.csv"


def _f(row: dict, key: str) -> float | None:
    value = row.get(key, "")
    if value in ("", "None", "inf"):
        return math.inf if value == "inf" else None
    try:
        return float(value)
    except ValueError:
        return None


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=EXPORT)
    args = parser.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"{args.csv} missing -- run `pixi run export` first")
    rows = list(csv.DictReader(args.csv.open()))

    ratios: list[float] = []          # log(t_hat / t), bounded brackets only
    pits: list[float] = []            # PIT under our own stated band
    by_bucket: dict[str, list[float]] = defaultdict(list)
    by_channel: dict[str, list[float]] = defaultdict(list)
    by_regime: dict[str, list[float]] = defaultdict(list)
    sigmas: list[float] = []
    above_floor = 0
    floor_total = 0
    bounded = unbounded = 0

    for row in rows:
        t_hat = _f(row, "t_hat")
        t_lo = _f(row, "t_lo")
        t_hi = _f(row, "t_hi")
        sigma_hat = _f(row, "sigma")
        game_id = int(row["game_id"])
        if t_hat is None or t_hat <= 0 or t_lo is None:
            continue

        # Uncensored one-sided check: t >= t_lo always, so t_hat > t_lo is a proven overshoot
        # only when t_lo is the *whole* story; here it is simply "did we clear the floor".
        floor_total += 1
        if t_lo > 0 and t_hat > t_lo:
            above_floor += 1

        if t_hi is None or t_hi == math.inf or t_lo <= 0:
            unbounded += 1
            continue
        bounded += 1
        t_point = (t_lo + t_hi) / 2.0
        if t_point <= 0:
            continue
        value = math.log(t_hat / t_point)
        ratios.append(value)

        regime = "awake" if game_id <= 43 else ("dark" if game_id <= 81 else "recalibrated")
        by_regime[regime].append(value)
        by_channel[row.get("channels", "?") or "?"].append(value)
        bucket = (
            "<50" if t_hat < 50 else
            "50-200" if t_hat < 200 else
            "200-400" if t_hat < 400 else
            "400-1k" if t_hat < 1000 else ">1k"
        )
        by_bucket[bucket].append(value)

        if sigma_hat and sigma_hat > 0:
            sigmas.append(sigma_hat)
            # PIT: where does the truth sit inside the posterior we published?
            pits.append(normal_cdf(math.log(t_point / t_hat) / sigma_hat))

    def summarise(values: list[float]) -> tuple[float, float, float]:
        """(median ratio as a multiplier, RMSLE, sd)."""
        if len(values) < 2:
            return (float("nan"),) * 3
        rmsle = math.sqrt(statistics.fmean(v * v for v in values))
        return math.exp(statistics.median(values)), rmsle, statistics.stdev(values)

    med, rmsle, sd = summarise(ratios)
    print(f"\n{'=' * 76}\nFAIR VALUE ESTIMATE -- {len(rows)} logged Line Items\n{'=' * 76}")
    print(f"\n  bracket bounded {bounded}   unbounded {unbounded}"
          f"   ({unbounded / max(bounded + unbounded, 1):.0%} censored -- every sigma below is optimistic)")
    print(f"\n  BIAS         median t_hat / t      {med:>8.3f}")
    print(f"  DISPERSION   RMSLE (total log error) {rmsle:>7.3f}   <- CLAUDE.md rule 10's sigma")
    print(f"               sd of log ratio         {sd:>7.3f}   (cannot see a level error)")
    print(f"  break-even sigma is ~0.85, so we {'CLEAR' if rmsle < 0.85 else 'MISS'} it")
    print(f"\n  uncensored check: t_hat above the proven floor t_lo on "
          f"{above_floor}/{floor_total} = {above_floor / max(floor_total, 1):.1%} of items")

    if pits:
        print(f"\n{'-' * 76}\nCALIBRATION -- PIT of the truth under our own published band\n{'-' * 76}")
        print(f"  n = {len(pits)}   (uniform on [0,1] iff the posterior is honest)")
        edges = [0.0, 0.05, 0.1, 1 / 3, 0.5, 2 / 3, 0.9, 0.95, 1.0]
        print(f"    {'bin':<16}{'observed':>10}{'expected':>10}{'ratio':>9}")
        for lo, hi in zip(edges, edges[1:]):
            got = sum(1 for u in pits if lo <= u < hi) / len(pits)
            want = hi - lo
            print(f"    [{lo:.3f},{hi:.3f})  {got:>9.1%}{want:>10.1%}{got / want:>9.2f}")
        below = sum(1 for u in pits if u < 1 / 3) / len(pits)
        print(f"\n  P(t < our Q_(1/3)) = {below:.1%}   -- an honest posterior gives 33.3%")
        if below > 0.36:
            verdict = (f"our Q_(1/3) is really the {below:.0%} quantile: the band is too WIDE "
                       f"downward, and the Limit sits FAR TOO LOW")
        elif below < 0.30:
            verdict = (f"our Q_(1/3) is really the {below:.0%} quantile: the Limit sits too HIGH")
        else:
            verdict = "the Limit quantile is calibrated; the fault is elsewhere"
        print(f"  VERDICT: {verdict}")
        tails = sum(1 for u in pits if u < 0.05 or u >= 0.95) / len(pits)
        print(f"  tail mass outside the stated 90% band: {tails:.1%} (honest = 10.0%)"
              f"  -> band is {'TOO NARROW' if tails > 0.13 else 'TOO WIDE' if tails < 0.07 else 'about right'}")
        print(f"  median published sigma_hat {statistics.median(sigmas):.3f}"
              f"   vs realised RMSLE {rmsle:.3f}"
              f"   -> we understate our own error by {rmsle / statistics.median(sigmas):.2f}x")

    print(f"\n{'-' * 76}\nWHERE THE ERROR LIVES\n{'-' * 76}")
    for title, table, order in (
        ("by t_hat bucket (the only split knowable at submission time)", by_bucket,
         ["<50", "50-200", "200-400", "400-1k", ">1k"]),
        ("by regime", by_regime, ["awake", "dark", "recalibrated"]),
    ):
        print(f"\n  {title}")
        print(f"    {'group':<16}{'n':>6}{'median t_hat/t':>17}{'RMSLE':>9}")
        for key in order:
            values = table.get(key, [])
            if not values:
                continue
            m, r, _ = summarise(values)
            print(f"    {key:<16}{len(values):>6}{m:>17.3f}{r:>9.3f}")

    print(f"\n  by channel mix")
    print(f"    {'channels':<28}{'n':>6}{'median t_hat/t':>17}{'RMSLE':>9}")
    for key, values in sorted(by_channel.items(), key=lambda kv: -len(kv[1]))[:8]:
        if len(values) < 5:
            continue
        m, r, _ = summarise(values)
        print(f"    {key:<28}{len(values):>6}{m:>17.3f}{r:>9.3f}")


if __name__ == "__main__":
    main()
