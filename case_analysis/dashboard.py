"""Graphical trend dashboard over the settled-game analysis.

Reads case_analysis/data/analysis.json (produced by analyze.py) and renders a
multi-panel matplotlib figure for human analysis:

1. Net score per team (leaderboard bar chart).
2. Fair-Value t brackets per (game, line item) with the field's average Charge.
3. Average Charge a and average Limit-midpoint per game (trend over time).
4. Per-team Charge aggressiveness: median a / t_point (1.0 = charging exactly
   at the fair value; > 1 = habitual overcharger).
5. Per-team fraud rate (share of nonzero Charges that landed in the fraud zone).
6. Team t_hat scatter vs. the true t bracket, for the strongest teams.

Usage:
    python3 case_analysis/dashboard.py            # interactive window
    python3 case_analysis/dashboard.py --save     # write dashboard.png instead
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

DATA_DIR = Path(__file__).resolve().parent / "data"
ANALYSIS_PATH = DATA_DIR / "analysis.json"
PNG_PATH = DATA_DIR / "dashboard.png"


def build_figure(analysis: dict):
    import matplotlib.pyplot as plt

    teams = analysis["teams"]
    games = analysis["games"]
    summary = analysis["team_summary"]

    fig, axes = plt.subplots(3, 2, figsize=(18, 16))
    fig.suptitle(
        f"Claim-to-Fame case analysis — {len(games)} settled games, {len(teams)} teams",
        fontsize=15,
    )

    # 1 · leaderboard
    ax = axes[0][0]
    names = [t["team"] for t in summary]
    nets = [t["net"] or 0 for t in summary]
    colors = ["#2a9d8f" if n >= 0 else "#e76f51" for n in nets]
    ax.barh(names[::-1], nets[::-1], color=colors[::-1])
    ax.set_title("Net score per team (income − costs)")
    ax.set_xlabel("net")

    # 2 · t brackets vs. field average charge
    ax = axes[0][1]
    labels, t_los, t_his, avg_as = [], [], [], []
    for game in games:
        for item in game["line_items"]:
            labels.append(f"g{game['game_id']}·i{item['line_item_index']}")
            t_los.append(item["t_lo"])
            t_his.append(item["t_hi"] if item["t_hi"] is not None else item["t_lo"] * 1.5)
            avg_as.append(item["avg_a"])
    x = range(len(labels))
    ax.bar(x, [hi - lo for lo, hi in zip(t_los, t_his)], bottom=t_los,
           color="#8ecae6", label="t bracket [t_lo, t_hi)")
    ax.plot(x, avg_as, "o-", color="#e76f51", label="field avg Charge a")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.set_title("Fair-Value bracket per Line Item vs. average Charge")
    ax.legend()

    # 3 · per-game trend of avg a and avg b midpoint
    ax = axes[1][0]
    game_ids = [g["game_id"] for g in games]
    avg_a_per_game = [
        sum(i["avg_a"] for i in g["line_items"]) / max(len(g["line_items"]), 1)
        for g in games
    ]
    avg_b_per_game = []
    for g in games:
        mids = [i["avg_b_mid"] for i in g["line_items"] if i["avg_b_mid"]]
        avg_b_per_game.append(sum(mids) / len(mids) if mids else 0)
    ax.plot(game_ids, avg_a_per_game, "o-", label="avg Charge a")
    ax.plot(game_ids, avg_b_per_game, "s--", label="avg Limit midpoint b")
    ax.set_title("Field pricing trend per Game")
    ax.set_xlabel("game id")
    ax.legend()

    # 4 · charge aggressiveness
    ax = axes[1][1]
    agg = [(t["team"], t["median_a_over_t"]) for t in summary if t["median_a_over_t"]]
    agg.sort(key=lambda p: p[1])
    ax.barh([p[0] for p in agg], [p[1] for p in agg], color="#457b9d")
    ax.axvline(1.0, color="k", linestyle=":", label="a = t")
    ax.set_title("Median Charge / t (per team) — >1 = habitual overcharger")
    ax.legend()

    # 5 · fraud rate
    ax = axes[2][0]
    fr = [(t["team"], t["fraud_rate"]) for t in summary if t["fraud_rate"] is not None]
    fr.sort(key=lambda p: p[1])
    ax.barh([p[0] for p in fr], [100 * p[1] for p in fr], color="#e9c46a")
    ax.set_title("Fraud-zone rate (% of nonzero Charges with a > t)")
    ax.set_xlabel("%")

    # 6 · t_hat of top teams vs. true bracket
    ax = axes[2][1]
    top = [t["team"] for t in summary[:5]]
    for team in top:
        xs, ys = [], []
        pos = 0
        for game in games:
            est = next(e for e in game["team_t_estimates"] if e["team"] == team)
            for row in est["items"]:
                if row["t_hat"]:
                    xs.append(pos)
                    ys.append(row["t_hat"])
                pos += 1
            pos += 1
        ax.plot(xs, ys, "o", markersize=4, alpha=0.7, label=team)
    pos = 0
    bx, blo, bhi = [], [], []
    for game in games:
        for item in game["line_items"]:
            bx.append(pos)
            blo.append(item["t_lo"])
            bhi.append(item["t_hi"] if item["t_hi"] is not None else item["t_lo"])
            pos += 1
        pos += 1
    ax.fill_between(bx, blo, bhi, color="grey", alpha=0.3, label="true t bracket")
    ax.set_title("Derived t̂ of the top-5 teams vs. the true t bracket")
    ax.set_xlabel("line item (chronological)")
    ax.legend(fontsize=8)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", action="store_true", help="write PNG instead of opening a window")
    args = parser.parse_args()

    if args.save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    analysis = json.loads(ANALYSIS_PATH.read_text())
    fig = build_figure(analysis)
    if args.save:
        fig.savefig(PNG_PATH, dpi=110)
        print(f"wrote {PNG_PATH}")
    else:
        if matplotlib.get_backend().lower() == "agg":
            raise SystemExit(
                "No GUI matplotlib backend available (Agg cannot open a window). "
                "Install one (e.g. `pip install PyQt5`) or run with --save."
            )
        plt.show()


if __name__ == "__main__":
    main()
