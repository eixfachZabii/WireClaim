"""What would a uniformly higher Limit have earned, replayed over every settled Game?

The question: hold our Charge exactly as submitted and multiply only our Limit `b` by
1.10 / 1.15 / 1.25. Replay against the real Field with all sixteen opponents fixed.

Why the answer is decomposable
------------------------------
Our `b` never touches our income. As Issuer we are paid `a` whenever `a <= t` -- whether
the reviewer accepts or wrongfully rejects -- and `min(a, c)` when they accept an
Overcharge; none of that depends on *our* Limit. So every euro a higher `b` moves is a
change in our cost as Reviewer, and it splits exactly two ways per newly-accepted Charge:

    opponent charged a <= t   we now pay `a` instead of `1.5a`   -> we SAVE 0.5a
    opponent charged a >  t   we now pay `a` instead of `0`      -> we LOSE  a

That is R4's `q > 2/3` written as money instead of probability, and it is the whole
mechanism. The report below prints both sides so the total is never a bare number.

Where our `b` comes from
------------------------
`replay_payoffs.our_actual_submission` reconstructs our Limit the way it reconstructs an
opponent's: as a *bracket* `[b_lo, b_hi)` collapsed to a point. Any point in that bracket
reproduces the settled Game exactly -- which is why the self-check passes -- but scaling a
midpoint by 10% is **not** scaling what we really sent. So where a decision log exists
(`var/decisions/game_NNN.json`, Games 26-100) this uses our **exact submitted Limit**, and
falls back to the reconstruction only for Games 1-25, which are reported separately rather
than blended in silently.

Usage:
    PYTHONPATH=. python3 scripts/experiments/limit_scale_backtest.py
"""

from __future__ import annotations

import json
import pathlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.replay_payoffs import (  # noqa: E402
    US,
    completed_games,
    our_actual_submission,
    replay,
    snapshot,
)

MULTIPLIERS = (1.00, 1.05, 1.10, 1.15, 1.25, 1.50)
DECISIONS = Path("var/decisions")


def exact_limits(game_id: int) -> dict[int, float] | None:
    """Our submitted Limit per Line Item, or None if this Game predates the decision log."""
    p = DECISIONS / f"game_{game_id:03d}.json"
    if not p.exists():
        return None
    blob = json.loads(p.read_text())
    out = {}
    for item in blob.get("items", []):
        if item.get("limit") is None:
            continue
        out[int(item["index"])] = float(item["limit"])
    return out or None


def newly_accepted(snap, sub_lo, sub_hi):
    """Money moved by raising the Limit from `sub_lo` to `sub_hi`, split by fair/Overcharge."""
    saved = lost = 0.0
    n_fair = n_over = 0
    for index in snap.line_items:
        b0 = sub_lo[index][1]
        b1 = sub_hi[index][1]
        if b1 <= b0:
            continue
        t = snap.fair_point(index)
        for team in snap.opponents:
            a = snap.charges[index][team]
            if a is None or a == float("inf"):
                continue
            if not (b0 < a <= b1):        # only Charges the raise newly admits
                continue
            if a <= t:
                saved += 0.5 * a          # 1.5a penalty becomes an a payment
                n_fair += 1
            else:
                lost += a                 # a zero becomes a payment
                n_over += 1
    return saved, lost, n_fair, n_over


def main() -> None:
    games = completed_games()
    print(f"Replaying {len(games)} completed Games against the real Field\n")

    rows, skipped, exact_games, recon_games = [], [], [], []
    for g in games:
        try:
            snap = snapshot(g, US)
        except Exception as exc:                       # noqa: BLE001
            skipped.append((g, f"snapshot failed: {exc}"))
            continue
        base = our_actual_submission(snap)
        ex = exact_limits(g)
        if ex:
            base = {i: (a, ex.get(i, b)) for i, (a, b) in base.items()}
            exact_games.append(g)
        else:
            recon_games.append(g)
        try:
            baseline = replay(snap, base)
        except Exception as exc:                       # noqa: BLE001
            skipped.append((g, f"replay failed: {exc}"))
            continue
        drift = baseline.net - snap.published_net
        row = {"game": g, "published": snap.published_net, "base": baseline.net,
               "drift": drift, "exact": bool(ex), "nets": {}, "split": {}}
        for m in MULTIPLIERS:
            sub = {i: (a, b * m) for i, (a, b) in base.items()}
            row["nets"][m] = replay(snap, sub).net
            row["split"][m] = newly_accepted(snap, base, sub)
        rows.append(row)

    ok = [r for r in rows if abs(r["drift"]) <= 0.01]
    bad = [r for r in rows if abs(r["drift"]) > 0.01]

    print(f"exact Limit from decision log : {len(exact_games)} Games "
          f"(G{min(exact_games)}-G{max(exact_games)})" if exact_games else "no decision logs")
    print(f"reconstructed Limit (bracket) : {len(recon_games)} Games {recon_games}")
    print(f"baseline reproduces published : {len(ok)} of {len(rows)} Games to the cent")
    if bad:
        print(f"  !! {len(bad)} Games drift; EXCLUDED from every total below:")
        for r in bad[:12]:
            print(f"     G{r['game']:3d} replay {r['base']:12,.2f} vs published "
                  f"{r['published']:12,.2f}  ({r['drift']:+,.2f})")
    if skipped:
        print(f"  !! {len(skipped)} Games not replayable, EXCLUDED: "
              f"{[g for g, _ in skipped]}")

    def totals(sel, label):
        if not sel:
            return
        b = sum(r["base"] for r in sel)
        print(f"\n{label}  ({len(sel)} Games, baseline {b:+,.0f})")
        print(f"  {'x b':>6} {'total net':>14} {'delta':>12}   "
              f"{'saved (fair)':>13} {'lost (over)':>13}  {'items f/o':>12}")
        for m in MULTIPLIERS:
            tot = sum(r["nets"][m] for r in sel)
            sv = sum(r["split"][m][0] for r in sel)
            ls = sum(r["split"][m][1] for r in sel)
            nf = sum(r["split"][m][2] for r in sel)
            no = sum(r["split"][m][3] for r in sel)
            print(f"  {m:>6.2f} {tot:>14,.0f} {tot - b:>+12,.0f}   "
                  f"{sv:>+13,.0f} {-ls:>+13,.0f}  {nf:>5d}/{no:<6d}")

    # ---- robustness: a total is not a result until you know how it is spread ----
    print("\n\nPER-GAME SPREAD (exact-Limit Games only) -- a total carried by two Games is noise")
    ex_ok = [r for r in ok if r["exact"]]
    print(f"  {'x b':>6} {'better':>7} {'worse':>6} {'flat':>5} {'median d':>10} "
          f"{'best Game':>18} {'worst Game':>18}")
    for m in MULTIPLIERS[1:]:
        ds = sorted(((r["nets"][m] - r["base"]), r["game"]) for r in ex_ok)
        better = sum(1 for d, _ in ds if d > 0.01)
        worse = sum(1 for d, _ in ds if d < -0.01)
        flat = len(ds) - better - worse
        med = ds[len(ds) // 2][0]
        print(f"  {m:>6.2f} {better:>7d} {worse:>6d} {flat:>5d} {med:>+10,.0f} "
              f"{f'G{ds[-1][1]} {ds[-1][0]:+,.0f}':>18} {f'G{ds[0][1]} {ds[0][0]:+,.0f}':>18}")

    # ---- where our Limit actually sits, which is what makes the sign of all this ----
    from statistics import median
    ratios_t, ratios_lo = [], []
    for r in ex_ok:
        snap = snapshot(r["game"], US)
        ex = exact_limits(r["game"]) or {}
        for i in snap.line_items:
            b = ex.get(i)
            t = snap.fair_point(i)
            if b is None or not t or t <= 0:
                continue
            ratios_t.append(b / t)
    if ratios_t:
        rs = sorted(ratios_t)
        print(f"\n  our submitted Limit vs the recovered Fair Value, {len(rs)} Line Items:")
        print(f"    median b/t {median(rs):.2f}   "
              f"p25 {rs[len(rs)//4]:.2f}   p75 {rs[3*len(rs)//4]:.2f}   "
              f"share with b < t: {sum(1 for x in rs if x < 1) / len(rs):.0%}")

    # ---- machine-readable, so this is re-checkable rather than quotable ----
    out = pathlib.Path("var/backtest"); out.mkdir(parents=True, exist_ok=True)
    with (out / "limit_scale.csv").open("w") as fh:
        fh.write("game,exact_limit,baseline_net," +
                 ",".join(f"net_x{m}" for m in MULTIPLIERS) + "\n")
        for r in sorted(ok, key=lambda r: r["game"]):
            fh.write(f"{r['game']},{int(r['exact'])},{r['base']:.2f}," +
                     ",".join(f"{r['nets'][m]:.2f}" for m in MULTIPLIERS) + "\n")
    print(f"\n  wrote {out / 'limit_scale.csv'}")

    totals(ok, "ALL usable Games")
    totals([r for r in ok if r["exact"]], "Games with an EXACT submitted Limit")
    late = [r for r in ok if r["exact"] and r["game"] >= 81]
    totals(late, "Triple-weighted era only (G81+, raw net -- multiply by 3 for the board)")


if __name__ == "__main__":
    main()
