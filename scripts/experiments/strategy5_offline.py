"""Score Strategy 5 over the whole settled record, offline, and split its two halves.

    PYTHONPATH=. pixi run python scripts/experiments/strategy5_offline.py

Strategy 5 is a live comparison track at priority 3, below Strategy 2's 4, so it is logged and
never submitted. Waiting for it to accumulate live evidence would take thirty Games. It does not
need to: `proposal_from_decisions` reprices the evidence already recorded in
`var/decisions/game_NNN.json` and makes no model call, so **its own production code path can be
run against every Game we have ever played.** That is what this does.

Two things are reported, and the second matters more than the verdict.

**The verdict**, against what we actually submitted, on Games that reconstruct.

**The decomposition**, because `a = b = t_hat` couples two decisions that the payoff table
treats separately, and they fail by different amounts. Feeding Strategy 5's Charge with the
shipped Limit, and the shipped Charge with Strategy 5's Limit, prices each half on its own.

What the numbers say, at 43 reconstructing Games (noise floor +/-41,147):

    actual (shipped)                    +127,736    baseline
    strategy5, both halves               -50,825    -178,562   (-4,153/Game, better on 11/43)
    strategy5 CHARGE + shipped Limit      +82,538     -45,198
    shipped Charge + strategy5 LIMIT       -5,627    -133,363

So **three quarters of the loss is the Limit.** `a = b = t_hat` places the Limit at 0.50-0.70 x
Strategy 2's median, far above the derived one-third quantile and above the `LIMIT_CEILING` of
0.45, so it accepts the opponent Overcharges the Limit exists to reject. The docstring's own
diagnosis of its first version -- "a high `b` accepts precisely the opponent overcharges the
Limit exists to reject" -- applies to the current one too: tying `b` to `t_hat` raised it rather
than lowering it. `CLAUDE.md` already records `b` above `t_hat` flipping to a monotone loss, and
`H15` re-confirms it from three directions.

The remaining quarter is the Charge, and it is concentrated where the constants file says it is
safest. `BIG_ITEM_FACTOR = 1.35` on `median >= 3000` is justified there as:

    "losing all income by sitting one euro above t is close to free on this bucket"

**That premise was falsified at Game 63 and the engine now carries the correction (H14).** The
issuer is paid on a *wrongful rejection* too, so a Charge at or below `t` is owed by all sixteen
opponents whatever their Limits, while an Overcharge is paid only by the ~3 who accept. Crossing
`t` costs about 5x the income, not nothing. Measured on this tier: **10 of the 13 Line Items with
`median >= 3000` land above `t` under the 1.35 factor.** The same reasoning is what made
`BIG_ITEM_CHARGE_SCALE = 1.25` worth -79,240 before it was reverted to 1.0.

One factual correction to the constants file while it is being read: it states that "the later
slices contain no estimates in this bucket". The record holds 13 Line Items with a median at or
above 3,000, including Game 67 at 13,730 and Game 68 at 8,000.

None of this makes the track a mistake -- a comparison that can never be submitted costs nothing
and this is exactly the evidence it exists to produce. It does mean the two halves should be
measured separately before either is proposed for promotion.
"""

from __future__ import annotations

import glob
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from replay_payoffs import (  # noqa: E402
    our_actual_submission,
    reconstruction_status,
    replay,
    snapshot,
)

from src.strategies.strategy5.constants import BIG_ITEM_THRESHOLD  # noqa: E402
from src.strategies.strategy5.strategy import proposal_from_decisions  # noqa: E402

NOISE_FLOOR_18 = 26_622
DECISIONS = Path(__file__).resolve().parents[2] / "var" / "decisions"


def noise(n: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(max(n, 1) / 18.0)


def rows() -> list[tuple[int, float, float, float, float]]:
    """`(game, actual, strategy5, s5-charge-only, s5-limit-only)` per usable Game."""
    out = []
    for path in sorted(glob.glob(str(DECISIONS / "game_0*.json"))):
        payload = json.loads(Path(path).read_text())
        game_id = payload.get("game_id")
        if game_id is None or reconstruction_status(game_id).status != "ok":
            continue
        snap = snapshot(game_id)
        indices = [item["index"] for item in payload.get("items") or ()]
        proposal = proposal_from_decisions(game_id, payload, indices, baseline=None)
        if proposal is None:
            continue
        five = {p.index: (p.charge_price, p.acceptance_limit) for p in proposal.prices}
        ours = our_actual_submission(snap)
        charge_only = {i: (five.get(i, (0.0, 0.0))[0], ours.get(i, (0.0, 0.0))[1]) for i in snap.line_items}
        limit_only = {i: (ours.get(i, (0.0, 0.0))[0], five.get(i, (0.0, 0.0))[1]) for i in snap.line_items}
        out.append(
            (
                game_id,
                replay(snap, ours).net,
                replay(snap, five).net,
                replay(snap, charge_only).net,
                replay(snap, limit_only).net,
            )
        )
    return out


def big_tier_crossings() -> tuple[int, int]:
    """Line Items in the `BIG_ITEM_FACTOR` tier, and how many Charge above `t`."""
    above = total = 0
    for path in sorted(glob.glob(str(DECISIONS / "game_0*.json"))):
        payload = json.loads(Path(path).read_text())
        game_id = payload.get("game_id")
        if game_id is None or reconstruction_status(game_id).status != "ok":
            continue
        snap = snapshot(game_id)
        indices = [item["index"] for item in payload.get("items") or ()]
        proposal = proposal_from_decisions(game_id, payload, indices, baseline=None)
        if proposal is None:
            continue
        five = {p.index: p.charge_price for p in proposal.prices}
        for item in payload.get("items") or ():
            if (item.get("price_median") or 0.0) < BIG_ITEM_THRESHOLD:
                continue
            index = item["index"]
            if index not in snap.fair_brackets:
                continue
            total += 1
            low, high = snap.fair_brackets[index]
            point = low if high == math.inf else (low + high) / 2.0
            if five.get(index, 0.0) > point:
                above += 1
    return above, total


def main() -> None:
    data = rows()
    n = len(data)
    if not n:
        print("no usable Game has a Strategy 2 decision log yet.")
        return
    total = [sum(r[i] for r in data) for i in range(1, 5)]
    labels = (
        "actual (shipped)",
        "strategy5, both halves",
        "strategy5 CHARGE + shipped Limit",
        "shipped Charge + strategy5 LIMIT",
    )
    print(
        f"Strategy 5 over {n} reconstructing Games with a Strategy 2 decision log.\n"
        f"Its own code path: reprices `var/decisions`, no model call.\n"
        f"Noise floor at n={n}: +/-{noise(n):,.0f}\n"
    )
    for label, value in zip(labels, total):
        delta = "baseline" if label.startswith("actual") else f"{value - total[0]:+,.0f}"
        print(f"  {label:<34} {value:>12,.0f}   {delta}")
    wins = sum(1 for r in data if r[2] > r[1])
    print(f"\n  strategy5 better on {wins} of {n} Games, {(total[1] - total[0]) / n:+,.0f}/Game")

    folds = {
        "odd": [r for r in data if r[0] % 2],
        "even": [r for r in data if not r[0] % 2],
        "early": data[: n // 2],
        "late": data[n // 2 :],
        "last10": data[-10:],
    }
    print()
    for name, sel in folds.items():
        actual = sum(r[1] for r in sel)
        five = sum(r[2] for r in sel)
        print(
            f"  {name:>7} ({len(sel):>2}g): actual {actual:>10,.0f}  strategy5 {five:>10,.0f}"
            f"  delta {five - actual:>+10,.0f}"
        )

    above, tier = big_tier_crossings()
    print(
        f"\n  Line Items with median >= {BIG_ITEM_THRESHOLD:,.0f} (the BIG_ITEM_FACTOR tier): {tier}"
        f"\n  of those, strategy5's Charge lands ABOVE t: {above}/{tier}"
    )
    print("\n  worst 5 Games for strategy5:")
    for game_id, actual, five, _, _ in sorted(data, key=lambda r: r[2] - r[1])[:5]:
        print(f"    G{game_id:>3} actual {actual:>10,.0f}  strategy5 {five:>10,.0f}  delta {five - actual:>+10,.0f}")


if __name__ == "__main__":
    main()
