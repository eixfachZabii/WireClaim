"""Euro replay of the measured-sigma candidate (coordinator's mid-task reframe).

Three sigma-lookup configs, all keyed on (channel, basis) -- both readable from the decision
log at submission time, per `measured_sigma_core.channel_of` / `basis_of`:

    "mine"          this script's own independent leave-nothing-out measurement (bounded
                     Line Items only, Games 1-39): memory/per_unit 0.37, memory/gross 0.43,
                     model (either basis) 0.77 -- see the note below on why model is NOT
                     split by basis here.
    "coordinator"   the literal figures in the reframe message: memory/per_unit 0.32,
                     memory/gross 0.55, model (either basis) 0.78.
    "channel_only"  channel alone, no basis split (0.42 memory / 0.77 model) -- isolates
                     whether basis adds anything on top of channel.

Why model is not split by basis: this script's own measurement (see the module-level
comment block) finds model-only + per_unit at sigma 0.959 on n=11 -- WORSE than model-only +
gross (0.729), the opposite sign from the memory channel's pattern and on a sample too small
to trust either way. `sigma-calibration.md` section 2's 0.32/0.55 split is scoped entirely to
Price Memory HITS (`PriceMemoryHit.match`/`.basis`) -- it never measured model-only items by
basis at all. Extending it to model-only items is the coordinator's message's own
extrapolation, not something either measurement supports, so "mine" and "channel_only" do not
make that extrapolation; "coordinator" keeps it, tested literally as asked.

Income depends only on OUR Charge (and each opponent's real Limit); cost depends only on OUR
Limit (and each opponent's real Charge) -- `replay_payoffs.replay`'s own loop. So a single
replay per (Game, config), using both the candidate Charge AND candidate Limit, is enough to
read the Charge-side effect (income delta) and Limit-side effect (cost delta) apart, with no
need for separate charge-only / limit-only submissions.

Baseline is the REAL `price_item()` (not `charge_buckets.Rule`, which never applies
`LIMIT_CEILING_MEMORY` and would silently double-count against it) -- coordinator caution #1.
`blend.MODEL_SIGMA_PRIOR` / `blend.MEMORY_SIGMA` are never touched -- coordinator caution #2.

Usage
-----
    PYTHONPATH=. python scripts/experiments/measured_sigma_replay.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from charge_buckets import ALL_GAMES, Row, _income, dataset  # noqa: E402
from measured_sigma_core import basis_of, channel_of, price_item_measured_sigma  # noqa: E402
from replay_payoffs import US, replay, reviewer_payoff, snapshot  # noqa: E402
from src.pricing.engine import implied_sigma, price_item  # noqa: E402

NOISE_FLOOR_18 = 26_622.0
WINDOW_1939 = tuple(g for g in ALL_GAMES if 19 <= g <= 39)
ODD = tuple(g for g in ALL_GAMES if g % 2)
EVEN = tuple(g for g in ALL_GAMES if not g % 2)
EARLY = tuple(g for g in ALL_GAMES if g <= 20)
LATE = tuple(g for g in ALL_GAMES if g > 20)

CONFIGS = {
    "mine": {
        ("memory", "per_unit"): 0.37,
        ("memory", "gross"): 0.43,
        ("model", "per_unit"): 0.77,
        ("model", "gross"): 0.77,
    },
    "coordinator": {
        ("memory", "per_unit"): 0.32,
        ("memory", "gross"): 0.55,
        ("model", "per_unit"): 0.78,
        ("model", "gross"): 0.78,
    },
    "channel_only": {
        ("memory", "per_unit"): 0.42,
        ("memory", "gross"): 0.42,
        ("model", "per_unit"): 0.77,
        ("model", "gross"): 0.77,
    },
}


def noise_floor(n_games: int) -> float:
    return NOISE_FLOOR_18 * math.sqrt(n_games / 18)


def _cost(row: Row, limit: float) -> float:
    """Real Field reviewer cost for a given Limit on this row -- mirror of `_income`."""
    snap = snapshot(row.game)
    t = snap.fair_point(row.index)
    return sum(
        reviewer_payoff(snap.charges[row.index][team], limit, t) for team in snap.opponents
    )


def candidate_price(row: Row, config: dict[tuple[str, str], float]):
    sigma = config[(channel_of(row), basis_of(row))]
    return price_item_measured_sigma(
        row.evidence, confirmed_uncovered=row.uncovered, memory_backed=row.has_memory,
        sigma_override=sigma,
    )


def baseline_price(row: Row):
    return price_item(row.evidence, confirmed_uncovered=row.uncovered, memory_backed=row.has_memory)


def net_income_cost(rows_by_game: dict, price_fn, games) -> dict[int, tuple[float, float, float]]:
    """`{game: (net, income, cost)}` for a pricing function applied to every row."""
    out = {}
    for game_id in games:
        snap = snapshot(game_id)
        submission = {}
        for row in rows_by_game.get(game_id, []):
            p = price_fn(row)
            submission[row.index] = (p.charge, p.limit)
        actual = {
            index: (snap.charges[index][snap.us], snap.limit_point(index, snap.us))
            for index in snap.line_items
        }
        actual.update(submission)
        r = replay(snap, actual)
        out[game_id] = (r.net, r.income, r.cost)
    return out


def total_net(nic: dict[int, tuple[float, float, float]], games) -> float:
    return sum(nic[g][0] for g in games)


def main() -> None:
    rows = dataset()
    rows_by_game: dict[int, list[Row]] = {}
    for row in rows:
        rows_by_game.setdefault(row.game, []).append(row)

    print(f"vintage: Games {ALL_GAMES[0]}-{ALL_GAMES[-1]} ({len(ALL_GAMES)} Games), {len(rows)} rows\n")

    # ---- sigma the engine currently sees, per bucket (mean asserted band sigma) ----
    from collections import defaultdict
    asserted = defaultdict(list)
    for row in rows:
        filled = row.evidence.with_defaults()
        asserted[(channel_of(row), basis_of(row))].append(
            implied_sigma(filled.price_low, filled.price_median, filled.price_high)
        )
    print("sigma the engine currently sees (mean asserted band width) vs the three configs:")
    print(f"  {'bucket':<24}{'n':>5}{'asserted':>10}{'mine':>8}{'coord.':>8}{'chan-only':>11}")
    for key in sorted(asserted, key=lambda k: -len(asserted[k])):
        n = len(asserted[key])
        mean_a = sum(asserted[key]) / n
        print(
            f"  {str(key):<24}{n:>5}{mean_a:>10.3f}"
            f"{CONFIGS['mine'][key]:>8.2f}{CONFIGS['coordinator'][key]:>8.2f}"
            f"{CONFIGS['channel_only'][key]:>11.2f}"
        )
    print()

    # ---- baseline (real price_item, current engine) ----
    baseline_nic = net_income_cost(rows_by_game, baseline_price, ALL_GAMES)
    base_all = total_net(baseline_nic, ALL_GAMES)
    base_1939 = total_net(baseline_nic, WINDOW_1939)
    base_income_all = sum(baseline_nic[g][1] for g in ALL_GAMES)
    base_cost_all = sum(baseline_nic[g][2] for g in ALL_GAMES)
    print(f"baseline (real price_item, current engine): all 39 Games = {base_all:,.0f}   Games 19-39 = {base_1939:,.0f}")
    print(f"  (income {base_income_all:,.0f}, cost {base_cost_all:,.0f})\n")

    print(f"{'config':<16}{'all 39':>12}{'d(net)':>10}{'d(income':>11}{'/charge)':>1}{'d(-cost':>10}{'/limit)':>1}{'19-39':>10}{'d':>9}")
    for name, config in CONFIGS.items():
        def fn(row, config=config):
            return candidate_price(row, config)
        nic = net_income_cost(rows_by_game, fn, ALL_GAMES)
        net_all = total_net(nic, ALL_GAMES)
        income_all = sum(nic[g][1] for g in ALL_GAMES)
        cost_all = sum(nic[g][2] for g in ALL_GAMES)
        net_1939 = total_net(nic, WINDOW_1939)
        d_charge = income_all - base_income_all
        d_limit = -(cost_all - base_cost_all)
        print(
            f"{name:<16}{net_all:>12,.0f}{net_all - base_all:>10,.0f}"
            f"{d_charge:>12,.0f}{d_limit:>17,.0f}{net_1939:>10,.0f}{net_1939 - base_1939:>9,.0f}"
        )

    floor_all = noise_floor(len(ALL_GAMES))
    floor_1939 = noise_floor(len(WINDOW_1939))
    print(f"\nnoise floor: all 39 +/-{floor_all:,.0f}   Games 19-39 +/-{floor_1939:,.0f}")

    # ---- held-out folds ----
    print("\n=== held-out folds (net delta vs baseline; config fixed, no fitting) ===")
    splits = (
        (ODD, EVEN, "odd->even"),
        (EVEN, ODD, "even->odd"),
        (EARLY, LATE, "1-20->21-39"),
        (LATE, EARLY, "21-39->1-20"),
    )
    for name, config in CONFIGS.items():
        def fn(row, config=config):
            return candidate_price(row, config)
        nic = net_income_cost(rows_by_game, fn, ALL_GAMES)
        cells = []
        for _, test, label in splits:
            delta = total_net(nic, test) - total_net(baseline_nic, test)
            cells.append(f"{label}={delta:>+10,.0f}")
        print(f"  {name:<16}" + "  ".join(cells))
    print(
        f"\n  noise floors: odd/even +/-{noise_floor(len(EVEN)):,.0f}, "
        f"21-39 (n={len(LATE)}) +/-{noise_floor(len(LATE)):,.0f}, "
        f"1-20 (n={len(EARLY)}) +/-{noise_floor(len(EARLY)):,.0f}"
    )

    # ---- monotonicity: interpolate asserted -> measured in log-sigma space ----
    print("\n=== monotonicity: blend weight w (0=shipped asserted band, 1=fully measured) ===")
    for name, config in CONFIGS.items():
        deltas = []
        for w in (0.0, 0.25, 0.5, 0.75, 1.0):
            def fn(row, config=config, w=w):
                filled = row.evidence.with_defaults()
                band_sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
                measured = config[(channel_of(row), basis_of(row))]
                sigma = math.exp((1 - w) * math.log(band_sigma) + w * math.log(measured))
                return price_item_measured_sigma(
                    row.evidence, confirmed_uncovered=row.uncovered,
                    memory_backed=row.has_memory, sigma_override=sigma,
                )
            nic = net_income_cost(rows_by_game, fn, ALL_GAMES)
            deltas.append(total_net(nic, ALL_GAMES) - base_all)
        mono = all(x <= y for x, y in zip(deltas, deltas[1:])) or all(x >= y for x, y in zip(deltas, deltas[1:]))
        print(f"  {name:<16}" + "  ".join(f"w={w:.2f}:{d:>+9,.0f}" for w, d in zip((0, .25, .5, .75, 1.0), deltas)) + f"   monotone={mono}")

    # ---- cliff accounting: Charge side ----
    print("\n=== cliff accounting, Charge side (config 'mine', vs t point estimate) ===")
    worth = [r for r in rows if r.t_lo > 0]
    for name, config in (("mine", CONFIGS["mine"]), ("coordinator", CONFIGS["coordinator"])):
        stayed_n = stayed_gain = 0.0
        crossed_n = crossed_loss = 0.0
        already_n = already_delta = 0.0
        for row in worth:
            base = baseline_price(row)
            cand = candidate_price(row, config)
            if abs(cand.charge - base.charge) < 1e-9:
                continue
            t = row.t
            base_income = _income(row, base.charge)
            cand_income = _income(row, cand.charge)
            delta = cand_income - base_income
            base_side = base.charge <= t
            cand_side = cand.charge <= t
            if base_side and cand_side:
                stayed_n += 1
                stayed_gain += delta
            elif base_side and not cand_side:
                crossed_n += 1
                crossed_loss += delta
            else:
                already_n += 1
                already_delta += delta
        print(
            f"  {name:<12} stayed below t: n={stayed_n:>4.0f} {stayed_gain:>+11,.0f}   "
            f"crossed above t: n={crossed_n:>4.0f} {crossed_loss:>+11,.0f}   "
            f"already above: n={already_n:>4.0f} {already_delta:>+11,.0f}   "
            f"net {stayed_gain + crossed_loss + already_delta:>+11,.0f}"
        )

    # ---- Limit side: loosened / tightened / same ----
    print("\n=== Limit-side breakdown (config 'mine', vs baseline Limit) ===")
    for name, config in (("mine", CONFIGS["mine"]), ("coordinator", CONFIGS["coordinator"])):
        loose_n = loose_delta = 0.0
        tight_n = tight_delta = 0.0
        for row in rows:
            base = baseline_price(row)
            cand = candidate_price(row, config)
            if abs(cand.limit - base.limit) < 1e-9:
                continue
            delta = -( _cost(row, cand.limit) - _cost(row, base.limit) )  # positive = cheaper
            if cand.limit > base.limit:
                loose_n += 1
                loose_delta += delta
            else:
                tight_n += 1
                tight_delta += delta
        print(
            f"  {name:<12} loosened: n={loose_n:>4.0f} net-cost-effect {loose_delta:>+11,.0f}   "
            f"tightened: n={tight_n:>4.0f} net-cost-effect {tight_delta:>+11,.0f}   "
            f"net {loose_delta + tight_delta:>+11,.0f}"
        )

    # ---- does the substituted sigma finally order the forgone-income share correctly? ----
    print("\n=== does substituted sigma order forgone-income share correctly? (config 'mine') ===")
    config = CONFIGS["mine"]
    scored = []
    for row in worth:
        base = baseline_price(row)
        sigma_used = config[(channel_of(row), basis_of(row))]
        oracle_income = _income(row, row.t_lo)
        gap = max(_income(row, row.t_lo) - _income(row, base.charge), 0.0) if (row.t <= 0 or base.charge > row.t) else 0.0
        scored.append((sigma_used, gap, oracle_income))
    scored.sort(key=lambda s: s[0])
    n = len(scored)
    thirds = [scored[: n // 3], scored[n // 3 : 2 * n // 3], scored[2 * n // 3 :]]
    tags = ["narrow (tightest measured sigma)", "mid", "wide (loosest measured sigma)"]
    for tag, third in zip(tags, thirds):
        if not third:
            continue
        lo, hi = third[0][0], third[-1][0]
        forgone = sum(t[1] for t in third)
        oracle = sum(t[2] for t in third)
        share = forgone / oracle if oracle else float("nan")
        print(f"  {tag:<34} sigma [{lo:.2f},{hi:.2f}]  n={len(third):>3}  forgone={forgone:>9,.0f}  of oracle={share:.0%}")


if __name__ == "__main__":
    main()
