"""What the Field actually charges, as a distribution over `log(a / t)`. Measured, all 100 Games.

Why this number is the one that was missing
-------------------------------------------
Our Limit is `Q_(1/3)` of our own posterior on the Fair Value, and R4 proves that is the right
*rule*: accept a Charge `a` exactly when `P(a <= t) > 2/3`, because accepting costs `a` while
rejecting costs `1.5a` when the claim was fair and `0` when it was not.

But the engine computes `P(a <= t)` from our prior on `t` alone, and that is not the
probability the rule asks for. At settlement we do not evaluate a threshold against a random
`t`; we evaluate it against a Charge that **an opponent chose after reading the same invoice**.
`a` is evidence about `t`. A Charge of 900 on an item we estimated at 700 is not simply "above
our median" -- it is also sixteen-teams-worth of testimony that the item is expensive.

So the quantity that decides the Limit is `P(a <= t | a)`, and Bayes needs one input we have
never measured: the law of the Field's Charge relative to the truth,

    log(a / t) = log f,     f the Field's Charge factor

This script measures it, because `t` is exactly recoverable. `invert_fair_values.brackets()`
returns `[t_lo, t_hi)` per Line Item; a Charge below `t_lo` is *provably* fair and one at or
above `t_hi` is *provably* an Overcharge, so every (team, Line Item) Charge can be scored
without a model and without a guess.

The censoring, stated up front
------------------------------
`log f` is only computed where the bracket is bounded, and a bounded bracket requires somebody
to have rightfully rejected -- which is a selection on the outcome, precisely the trap
CLAUDE.md names ("Never condition on the answer"). Two mitigations, both reported:

* the fair/Overcharge **rates** are computed on the provable classification alone, which needs
  no bracket width and is therefore uncensored;
* `m` and `s` are reported both on bounded brackets and on the wider `t_lo`-only sample, so a
  reader can see how much the censoring moves them.

Usage
-----
    PYTHONPATH=. python scripts/experiments/field_charge_law.py
    PYTHONPATH=. python scripts/experiments/field_charge_law.py --json var/field_law.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from replay_payoffs import US, reconstruction_status, snapshot  # noqa: E402

INF = math.inf
REGIMES = (("awake", 1, 43), ("dark", 44, 81), ("recalibrated", 82, 100))


def describe(values: list[float]) -> dict[str, float]:
    if len(values) < 2:
        return {"n": len(values), "median": 0.0, "mean": 0.0, "sd": 0.0, "p10": 0.0, "p90": 0.0}
    ordered = sorted(values)
    quantile = lambda q: ordered[min(int(q * len(ordered)), len(ordered) - 1)]  # noqa: E731
    return {
        "n": len(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "sd": statistics.stdev(values),
        "p10": quantile(0.10),
        "p90": quantile(0.90),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    # log(a / t) where the bracket pins t well enough to divide by it
    logf_bounded: list[float] = []
    logf_lo: list[float] = []
    per_regime: dict[str, list[float]] = defaultdict(list)
    per_team_fair: dict[str, list[int]] = defaultdict(list)
    per_team_logf: dict[str, list[float]] = defaultdict(list)
    provable = {"fair": 0, "over": 0, "unknown": 0, "zero": 0}
    per_regime_rate: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    games = [g for g in range(1, 101) if reconstruction_status(g, US).usable]
    for game_id in games:
        snap = snapshot(game_id, US)
        regime = next(n for n, lo, hi in REGIMES if lo <= game_id <= hi)
        for index in snap.line_items:
            low, high = snap.fair_brackets[index]
            for team, charge in snap.charges[index].items():
                if team == US or charge == INF:
                    continue
                if charge <= 0.0:
                    provable["zero"] += 1
                    continue
                # Provable classification -- needs no bracket width, so it is uncensored.
                if charge <= low:
                    kind = "fair"
                elif high != INF and charge >= high:
                    kind = "over"
                else:
                    kind = "unknown"
                provable[kind] += 1
                per_regime_rate[regime][kind] += 1
                if kind in ("fair", "over"):
                    per_team_fair[team].append(1 if kind == "fair" else 0)

                # log f needs a point for t. Bounded brackets get the midpoint; unbounded
                # ones get t_lo, which *overstates* f (t is at least t_lo), and are reported
                # separately for exactly that reason.
                if low > 0:
                    logf_lo.append(math.log(charge / low))
                    if high != INF:
                        point = (low + high) / 2.0
                        value = math.log(charge / point)
                        logf_bounded.append(value)
                        per_regime[regime].append(value)
                        per_team_logf[team].append(value)

    bounded = describe(logf_bounded)
    unbounded = describe(logf_lo)
    resolved = provable["fair"] + provable["over"]

    print(f"\n{'=' * 76}\nTHE FIELD'S CHARGE LAW -- {len(games)} Games\n{'=' * 76}")
    print(f"\n  Provable classification of every opponent Charge (uncensored)")
    print(f"    {'fair (a <= t_lo)':<34}{provable['fair']:>8}  {provable['fair'] / resolved:>7.1%} of resolved")
    print(f"    {'Overcharge (a >= t_hi)':<34}{provable['over']:>8}  {provable['over'] / resolved:>7.1%} of resolved")
    print(f"    {'inside the bracket, unresolved':<34}{provable['unknown']:>8}")
    print(f"    {'charged zero':<34}{provable['zero']:>8}")

    print(f"\n  log(a / t), bounded brackets only  (t = bracket midpoint)")
    for key in ("n", "median", "mean", "sd", "p10", "p90"):
        print(f"    {key:<10}{bounded[key]:>12.4f}")
    print(f"    {'-> f median':<10}{math.exp(bounded['median']):>12.4f}   (the Field Charges this x t)")
    print(f"    {'-> s':<10}{bounded['sd']:>12.4f}   (spread of log f -- the Bayes input)")

    print(f"\n  log(a / t_lo), every item with a floor  (t >= t_lo, so this OVERstates f)")
    for key in ("n", "median", "mean", "sd"):
        print(f"    {key:<10}{unbounded[key]:>12.4f}")

    print(f"\n  By regime -- CLAUDE.md rule 9 says these must be checked separately")
    print(f"    {'regime':<14}{'n':>7}{'median log f':>15}{'sd':>9}{'fair rate':>12}")
    for name, _, _ in REGIMES:
        values = per_regime[name]
        rate = per_regime_rate[name]
        got = rate["fair"] + rate["over"]
        stats = describe(values)
        print(
            f"    {name:<14}{stats['n']:>7}{stats['median']:>15.4f}{stats['sd']:>9.4f}"
            f"{(rate['fair'] / got if got else 0):>12.1%}"
        )

    print(f"\n  By team -- who is worth trusting (>= 40 resolved Charges)")
    print(f"    {'team':<24}{'n':>6}{'fair rate':>12}{'median log f':>15}")
    ranked = sorted(
        ((t, v) for t, v in per_team_fair.items() if len(v) >= 40),
        key=lambda kv: -statistics.fmean(kv[1]),
    )
    for team, flags in ranked:
        logs = per_team_logf.get(team, [])
        med = statistics.median(logs) if logs else float("nan")
        print(f"    {team:<24}{len(flags):>6}{statistics.fmean(flags):>12.1%}{med:>15.4f}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "games": games,
                    "provable": provable,
                    "log_f_bounded": bounded,
                    "log_f_lo": unbounded,
                    "per_regime": {
                        n: describe(per_regime[n]) | {"fair_rate": (
                            per_regime_rate[n]["fair"]
                            / max(per_regime_rate[n]["fair"] + per_regime_rate[n]["over"], 1)
                        )}
                        for n, _, _ in REGIMES
                    },
                    "per_team_fair_rate": {
                        t: statistics.fmean(v) for t, v in per_team_fair.items() if len(v) >= 40
                    },
                },
                indent=1,
                sort_keys=True,
            )
            + "\n"
        )
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
