"""Simple trend dashboard over the settled-game analysis.

Reads case_analysis/data/analysis.json (produced by analyze.py) and renders
four easy-to-read panels:

1. Net score per team (leaderboard).
2. Average Charge a vs. average Limit b vs. derived t per game (trend).
3. Per-team fraud-zone rate (% of nonzero Charges above the derived t).
4. Per-team median Charge / t (charge aggressiveness; 1.0 = charging at t).

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

    games = analysis["games"]
    summary = analysis["team_summary"]

    fig, axes = plt.subplots(2, 2, figsize=(16, 10), constrained_layout=True)
    fig.suptitle(
        f"Claim-to-Fame — {len(games)} settled games, {len(analysis['teams'])} teams",
        fontsize=15,
        fontweight="bold",
    )

    # 1 · leaderboard
    ax = axes[0][0]
    names = [t["team"] for t in summary][::-1]
    nets = [t["net"] or 0 for t in summary][::-1]
    ax.barh(names, nets, color=["#2a9d8f" if n >= 0 else "#e76f51" for n in nets])
    ax.set_title("Net score per team")
    ax.tick_params(labelsize=9)

    # 2 · per-game averages: a, b, derived t
    ax = axes[0][1]
    game_ids = [g["game_id"] for g in games]
    avg_a, avg_b, avg_t = [], [], []
    for g in games:
        items = g["line_items"]
        avg_a.append(sum(i["avg_a"] for i in items) / max(len(items), 1))
        mids = [i["avg_b_mid"] for i in items if i["avg_b_mid"]]
        avg_b.append(sum(mids) / len(mids) if mids else 0)
        ts = [i["t_point"] for i in items if i["t_point"]]
        avg_t.append(sum(ts) / len(ts) if ts else 0)
    ax.plot(game_ids, avg_a, "o-", label="avg Charge a")
    ax.plot(game_ids, avg_b, "s--", label="avg Limit b")
    ax.plot(game_ids, avg_t, "^:", color="grey", label="avg derived t")
    ax.set_title("Field averages per game")
    ax.set_xlabel("game")
    ax.legend()

    # 3 · fraud rate
    ax = axes[1][0]
    fr = sorted(
        ((t["team"], t["fraud_rate"]) for t in summary if t["fraud_rate"] is not None),
        key=lambda p: p[1],
    )
    ax.barh([p[0] for p in fr], [100 * p[1] for p in fr], color="#e9c46a")
    ax.set_title("Fraud-zone rate (% of nonzero Charges with a > t)")
    ax.set_xlabel("%")
    ax.tick_params(labelsize=9)

    # 4 · charge aggressiveness
    ax = axes[1][1]
    agg = sorted(
        ((t["team"], t["median_a_over_t"]) for t in summary if t["median_a_over_t"]),
        key=lambda p: p[1],
    )
    ax.barh([p[0] for p in agg], [p[1] for p in agg], color="#457b9d")
    ax.axvline(1.0, color="k", linestyle=":", label="a = t")
    ax.set_title("Median Charge / t per team (>1 = overcharger)")
    ax.legend()
    ax.tick_params(labelsize=9)

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
        fig.savefig(PNG_PATH, dpi=120)
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
