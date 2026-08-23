"""The ensemble's value is its *width*, not its average -- so measure the width estimator.

    PYTHONPATH=. pixi run python scripts/experiments/ensemble_width.py

Two measurements motivate this, both from `var/ai_log/`, which has both raw model replies per
Case from Game 48 on.

**1. Averaging the draws is nearly worthless.** Decomposing the log error of the 2-draw mean
over 143 Line Items in 18 Games: draw-to-draw noise is `sigma_eps = 0.159`, so it contributes
`sigma_eps^2 / 2 = 0.013` of a total MSE of 1.189 -- **1.1 %**. The draws agree within 1.13x at
the median and differ by more than 2x on 1 % of items. A third draw would cut RMSLE by 0.2 %,
an eighth by 0.4 %. The model is not noisy; it is confidently wrong, and 98.9 % of the error is
shared between the two framings.

**2. The ensemble is nonetheless worth a great deal, and it is the width doing it.** Scoring
each draw alone through the live `price_item` and the real payoff table, model channel only:

    draw 1 alone (anchored prompt)      -85,953
    draw 2 alone (unanchored prompt)    -13,864
    the 2-draw blend                    +41,727      <- +55,591 over the better single draw

+55,591 over 18 Games clears the +/-26,622 floor. Since the medians agree to within 13 %, that
gain cannot be coming from the averaged level. It comes from `blend()` adding the *observed*
disagreement in quadrature with the asserted band, which widens the posterior on exactly the
items the two framings disagree about -- and a wider posterior lowers `charge_factor` and the
Limit quantile. Disagreement we observed is a real quantity; the width the model asserts is
not (median 0.375 against a realised RMSLE near 1.09, ranking the errors slightly backwards).

So the width estimator is worth measuring, and there is a specific reason to think it is
mis-set. `blend()` computes

    observed = sqrt( sum((log_i - mean_log)^2) / n )

which is the **population** standard deviation. The unbiased estimator of the spread divides
by `n - 1`. At `n = 2` -- every Game we have ever played -- the two differ by a factor of
`sqrt(2)`: the population form returns `|delta| / 2` where the sample form returns
`|delta| / sqrt(2)`. **The shipped code therefore understates the observed disagreement by 41 %
on every Line Item.** That is not a tuning question, it is which of two estimators is meant.

`k` below multiplies `observed`. `k = 1.0` is what ships; `k = 1.414` is the Bessel correction
at `n = 2`, i.e. the unbiased sample standard deviation. Higher values are swept because the
correct answer for *prediction* is not obviously the unbiased spread either -- what the band
should represent is the error of the mean, and two framings of one model share most of their
error, so their disagreement is a floor on the true uncertainty rather than an estimate of it.

Scored on the model channel alone, with Price Memory excluded. That is a deliberate limitation
and it cuts both ways: it isolates the change, but it also means the shipped pipeline (where
`combine()` blends a memory anchor over ~50 % of items) will see a smaller effect than the
table below. Read the sign and the fold consistency, not the absolute euros.
"""

from __future__ import annotations

import glob
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from replay_payoffs import replay, snapshot  # noqa: E402

from src.pricing.engine import Evidence, price_item  # noqa: E402
from src.strategies.strategy2.constants import BAND_Z  # noqa: E402

NOISE_FLOOR_18 = 26_622


def noise(n: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(max(n, 1) / 18.0)


def load_draws() -> dict[int, dict[str, dict[int, Evidence]]]:
    """Every raw model reply, parsed back into the Evidence the pipeline saw."""
    per: dict[int, dict[str, dict[int, Evidence]]] = defaultdict(dict)
    for path in sorted(glob.glob("var/ai_log/game_*.json")):
        payload = json.load(open(path))
        try:
            reply = json.loads(payload["reply"])
        except Exception:
            continue
        evidence: dict[int, Evidence] = {}
        for item in reply.get("items") or []:
            index, median = item.get("line_item"), item.get("price_median")
            if index is None or not median or float(median) <= 0:
                continue
            median = float(median)
            low = float(item.get("price_low") or median * 0.6)
            high = float(item.get("price_high") or median * 1.6)
            coverage = item.get("coverage_probability")
            evidence[int(index)] = Evidence(
                int(index), 0.9 if coverage is None else float(coverage), low, median, high
            )
        if evidence:
            per[payload["game_id"]][payload["draw"]] = evidence
    return per


def sigma_of(evidence: Evidence) -> float:
    if evidence.price_low <= 0 or evidence.price_high <= evidence.price_low:
        return 0.6
    return math.log(evidence.price_high / evidence.price_low) / (2 * BAND_Z)


def blend(draws: list[dict[int, Evidence]], *, k: float) -> dict[int, Evidence]:
    """`strategy2.blend.blend`, with a multiplier on the observed-disagreement term."""
    usable = [draw for draw in draws if draw]
    if not usable:
        return {}
    if len(usable) == 1:
        return usable[0]
    out: dict[int, Evidence] = {}
    for index in set().union(*(set(draw) for draw in usable)):
        seen = [draw[index] for draw in usable if index in draw]
        priced = [item for item in seen if item.price_median > 0]
        if not priced:
            out[index] = seen[0]
            continue
        logs = [math.log(item.price_median) for item in priced]
        mean_log = sum(logs) / len(logs)
        asserted = sum(sigma_of(item) for item in priced) / len(priced)
        observed = math.sqrt(sum((v - mean_log) ** 2 for v in logs) / len(logs)) * k
        sigma = math.sqrt(asserted**2 + observed**2)
        median = math.exp(mean_log)
        out[index] = Evidence(
            index,
            sum(item.coverage_probability for item in seen) / len(seen),
            median * math.exp(-BAND_Z * sigma),
            median,
            median * math.exp(BAND_Z * sigma),
        )
    return out


def score(per, games, *, k: float) -> float:
    total = 0.0
    for game_id in games:
        drawn = list(per[game_id].values())
        evidence = blend(drawn, k=k)
        submission = {}
        for index, item in evidence.items():
            priced = price_item(item)
            submission[index] = (priced.charge, priced.limit)
        if submission:
            total += replay(snapshot(game_id), submission).net
    return total


def main() -> None:
    per = load_draws()
    games = sorted(g for g, by in per.items() if len(by) >= 2)
    folds = {
        "all": games,
        "odd": [g for g in games if g % 2],
        "even": [g for g in games if not g % 2],
        "early": games[: len(games) // 2],
        "late": games[len(games) // 2 :],
    }
    print(
        f"{len(games)} Games with both draws logged (Games {games[0]}-{games[-1]}), model "
        f"channel only, Price Memory excluded.\nNoise floor +/-{noise(len(games)):,.0f}. "
        f"Delta against the shipped population sd (k = 1.0).\n"
    )
    base = {n: score(per, gs, k=1.0) for n, gs in folds.items()}
    print(f"{'k':>7}  {'what it is':<34}" + "".join(f"{n:>11}" for n in folds) + "  folds+")
    print("-" * (43 + 11 * len(folds) + 8))
    labels = {
        1.0: "population sd (shipped)",
        1.414: "unbiased sample sd at n=2",
        2.0: "2x the population sd",
        2.828: "2x the unbiased sd",
        4.0: "4x the population sd",
    }
    for k, label in labels.items():
        cells = [score(per, gs, k=k) - base[n] for n, gs in folds.items()]
        pos = sum(1 for c in cells[1:] if c > 0)
        mark = "  <-- all 4" if pos == 4 else ""
        print(
            f"{k:>7.3f}  {label:<34}"
            + "".join(f"{c:>+11,.0f}" for c in cells)
            + f"{pos:>5}/4{mark}"
        )
    print(f"\n{'(baseline)':>43}" + "".join(f"{base[n]:>11,.0f}" for n in folds))


if __name__ == "__main__":
    main()
