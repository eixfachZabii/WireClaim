"""Why did the last nine Games turn negative, and is the Charge or the Limit to blame?

    PYTHONPATH=. pixi run python scripts/experiments/recent_regression.py

Commissioned because the per-Game rate reversed without the Cases getting cheaper. Replaying
our own reconstructed submissions against the real Field:

    G26-40   15 Games   mean honest ceiling 24,398   mean net  +4,363
    G41-55   15 Games   mean honest ceiling 47,506   mean net  +4,848
    G56-64    9 Games   mean honest ceiling 30,813   mean net  -2,861

So it is not Case size and it is not a run of worthless Cases. Something in the pipeline got
worse. This splits the net four ways, on the same authoritative rows, to say which side:

    (i)   income from fair Charges      a <= t, paid by ALL 16 opponents
    (ii)  income from Overcharges       a >  t, paid only by those who accept
    (iii) paid on accepts               claims we accepted, min(their a, c)
    (iv)  lawyer                        1.5 * their a on fair claims we rejected

(i) and (ii) are the Issuer side and answer "is our Charge too high" -- an Overcharge shows up
as (i) collapsing while (ii) barely rises, because 16 payers become about 3. (iii) and (iv)
are the Reviewer side and answer "is our Limit wrong", in *which* direction: (iii) growing is
a Limit too high (we pay for other teams' Overcharges), (iv) growing is a Limit too low (we
reject fair claims and pay the lawyer for it).

The second table sweeps a global multiplier on the Charge -- every Line Item, not just the big
ones -- because "our `a` is too high" is a claim about the level and the level is measurable.
Note what the answer is *not*: the big-item sweep in `big_charge_floor_sweep.py` already shows
`scale 0.9` (+25,869) scoring far worse than `scale 1.0` (+79,240), so on that bucket pushing
the Charge *down* past the shipped factor loses. A fair Charge is owed by all sixteen
opponents, so every euro shaved off a Charge that was already fair is a euro lost sixteen
times over; the only thing a lower Charge buys is the few items it rescues from above `t`.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from charge_buckets import dataset, snapshot  # noqa: E402
from replay_payoffs import our_actual_submission, replay  # noqa: E402
from rivals import cap_of  # noqa: E402

from src.pricing.engine import (  # noqa: E402
    BIG_ITEM_CHARGE_SCALE,
    BIG_ITEM_THRESHOLD,
    COVERAGE_FLOOR,
    LIMIT_CAP,
    LIMIT_CEILING,
    LIMIT_CEILING_MEMORY,
    LIMIT_QUANTILE,
    _lognormal_quantile,
    charge_factor,
    implied_sigma,
)

INF = float("inf")
NOISE_FLOOR_18 = 26_622
WINDOWS = ((26, 40), (41, 55), (56, 64))


def noise(n: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(max(n, 1) / 18.0)


def buckets(game_id: int) -> tuple[float, ...] | None:
    """The four-way split of our own net in one Game, from the reconstructed rows."""
    try:
        snap = snapshot(game_id)
    except Exception:
        return None
    submission = our_actual_submission(snap)
    fair = over = accepts = lawyer = 0.0
    for index in snap.line_items:
        charge, limit = submission.get(index, (0.0, 0.0))
        t = snap.fair_point(index)
        for team in snap.opponents:
            b = snap.limit_point(index, team, "mid")
            if charge <= t:
                fair += charge  # owed by every opponent, accepted or not
            elif charge <= b:
                over += min(charge, cap_of(t))
            their = snap.charges[index][team]
            if their == INF:
                continue
            if their <= limit:
                accepts += min(their, cap_of(t))
            elif their <= t:
                lawyer += 1.5 * their
    return fair, over, accepts, lawyer


def side_table() -> None:
    print("=== our own net, split four ways, per window (authoritative rows) ===\n")
    print(
        f"{'window':>10} {'n':>3} {'net':>10} {'(i) fair':>11} {'(ii) over':>10} "
        f"{'(iii) accepts':>14} {'(iv) lawyer':>12} {'fair/Game':>10} {'lawyer/Game':>12}"
    )
    for lo, hi in WINDOWS:
        rows = [b for g in range(lo, hi + 1) if (b := buckets(g))]
        if not rows:
            continue
        fair = sum(r[0] for r in rows)
        over = sum(r[1] for r in rows)
        acc = sum(r[2] for r in rows)
        law = sum(r[3] for r in rows)
        net = fair + over - acc - law
        n = len(rows)
        print(
            f"{f'G{lo}-{hi}':>10} {n:>3} {net:>10,.0f} {fair:>11,.0f} {over:>10,.0f} "
            f"{-acc:>14,.0f} {-law:>12,.0f} {fair / n:>10,.0f} {-law / n:>12,.0f}"
        )
    print(
        "\n  (i) is the prize: a fair Charge is owed by all 16. (iv) growing means the Limit "
        "is\n  too LOW (we reject fair claims); (iii) growing means it is too HIGH."
    )


def price(row, *, charge_k: float, limit_cap: float) -> tuple[float, float]:
    """The shipped `price_item` with a global Charge multiplier and a variable `LIMIT_CAP`."""
    filled = row.evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    median = filled.price_median
    memory = "B:memory" in row.channels
    covered = 0.0 if row.uncovered else filled.coverage_probability

    charge = charge_factor(sigma) * median * charge_k
    if median >= BIG_ITEM_THRESHOLD:
        charge *= BIG_ITEM_CHARGE_SCALE

    if covered <= COVERAGE_FLOOR:
        limit = 0.0
    else:
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        ceiling = LIMIT_CEILING_MEMORY if memory else LIMIT_CEILING
        candidates = [_lognormal_quantile(median, sigma, conditional), ceiling * median]
        if not memory:
            candidates.append(limit_cap)
        limit = min(candidates)
    return round(max(charge, 0.0), 2), round(max(min(limit, charge), 0.0), 2)


def net_of(rows, games, *, charge_k: float = 1.0, limit_cap: float = LIMIT_CAP) -> float:
    total = 0.0
    for game_id in games:
        sub = {
            r.index: price(r, charge_k=charge_k, limit_cap=limit_cap)
            for r in rows
            if r.game == game_id
        }
        if sub:
            total += replay(snapshot(game_id), sub).net
    return total


def fair_share(rows, *, charge_k: float) -> tuple[int, int]:
    """How many Line Items land at or below `t`, and how many above, at this multiplier."""
    at_or_below = above = 0
    for row in rows:
        charge, _ = price(row, charge_k=charge_k, limit_cap=LIMIT_CAP)
        t = row.t_lo if row.t_hi == INF else (row.t_lo + row.t_hi) / 2.0
        if charge <= t:
            at_or_below += 1
        else:
            above += 1
    return at_or_below, above


def sweep(rows, games, folds, *, label: str, key: str, values: tuple[float, ...]) -> None:
    print(f"\n\n=== {label} ===\n")
    base = {n: net_of(rows, gs) for n, gs in folds.items()}
    print(f"{key:<12}" + "".join(f"{k:>11}" for k in folds) + "  folds+   items fair/over")
    print("-" * (12 + 11 * len(folds) + 26))
    for value in values:
        kwargs = {"charge_k": value} if key == "charge x" else {"limit_cap": value}
        cells = [net_of(rows, gs, **kwargs) - base[n] for n, gs in folds.items()]
        pos = sum(1 for c in cells[1:] if c > 0)
        extra = ""
        if key == "charge x":
            good, bad = fair_share(rows, charge_k=value)
            extra = f"  {good:>4}/{bad:<4}"
        mark = "  <-- all 4" if pos == 4 else ""
        print(
            f"{f'{key} {value}':<12}"
            + "".join(f"{c:>+11,.0f}" for c in cells)
            + f"{pos:>5}/4{extra}{mark}"
        )
    print(f"\n{'(baseline)':<12}" + "".join(f"{base[k]:>11,.0f}" for k in folds))


def main() -> None:
    side_table()
    rows = dataset()
    games = sorted({r.game for r in rows})
    folds = {
        "all": games,
        "odd": [g for g in games if g % 2],
        "even": [g for g in games if not g % 2],
        "<=45": [g for g in games if g <= 45],
        ">45": [g for g in games if g > 45],
    }
    print(
        f"\n\n{len(games)} Games, {len(rows)} Line Items. Noise floor "
        f"+/-{noise(len(games)):,.0f} over the window, +/-{noise(len(folds['odd'])):,.0f} "
        f"within a half-fold."
    )
    sweep(
        rows,
        games,
        folds,
        label="a global multiplier on the Charge, every Line Item",
        key="charge x",
        values=(0.6, 0.7, 0.8, 0.9, 1.0, 1.1),
    )
    sweep(
        rows,
        games,
        folds,
        label=f"LIMIT_CAP, currently {LIMIT_CAP:,.0f}, on model-only items",
        key="cap",
        values=(354.0, 708.0, 1_062.0, 1_416.0, 2_124.0, 1e18),
    )


if __name__ == "__main__":
    main()
