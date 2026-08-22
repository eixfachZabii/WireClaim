"""Cumulative balance per team over the settled games, as one line chart.

Per game each team's net is derived from the settled transaction rows:
income as Issuer (published amounts) minus costs as Reviewer (accepted
payouts plus the 1.5a lawyer penalty on every wrongly rejected fair Charge).
Cumulative sums give the running "total balance" per team.

Writes data/balance.png and data/balance.csv.

Usage:
    python3 case_analysis/balance.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = Path(__file__).resolve().parent / "data"
HIGHLIGHT = "Bin busy"


def game_nets() -> tuple[list[int], dict[str, list[float]]]:
    per_game: list[tuple[int, dict[str, float]]] = []
    teams: set[str] = set()
    for path in sorted((DATA_DIR / "raw").glob("transactions_game_*.json")):
        game_id = int(re.search(r"(\d+)", path.stem).group(1))
        net: dict[str, float] = {}
        for row in json.loads(path.read_text()):
            amount = row["amount"]
            net[row["issuer"]] = net.get(row["issuer"], 0.0) + amount
            cost = amount if row["accepted"] else (1.5 * amount if amount > 0 else 0.0)
            net[row["reviewer"]] = net.get(row["reviewer"], 0.0) - cost
        per_game.append((game_id, net))
        teams.update(net)

    ids = [g for g, _ in per_game]
    balances: dict[str, list[float]] = {t: [] for t in teams}
    for team in teams:
        total = 0.0
        for _, net in per_game:
            total += net.get(team, 0.0)
            balances[team].append(total)
    return ids, balances


def main() -> None:
    ids, balances = game_nets()
    order = sorted(balances, key=lambda t: balances[t][-1], reverse=True)

    with (DATA_DIR / "balance.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["game", *order])
        for i, game_id in enumerate(ids):
            writer.writerow([game_id] + [f"{balances[t][i]:.2f}" for t in order])

    fig, ax = plt.subplots(figsize=(16, 9), constrained_layout=True)
    cmap = plt.get_cmap("tab20")
    for i, team in enumerate(order):
        highlight = team == HIGHLIGHT
        ax.plot(
            ids, balances[team],
            color="black" if highlight else cmap(i % 20),
            lw=3.0 if highlight else 1.6,
            zorder=3 if highlight else 2,
            marker="o", markersize=4 if highlight else 2.5,
            label=f"{team} ({balances[team][-1]:+,.0f})",
        )
        ax.annotate(
            team, (ids[-1], balances[team][-1]),
            xytext=(6, 0), textcoords="offset points",
            fontsize=8, fontweight="bold" if highlight else "normal",
            va="center",
        )
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_title(f"Total balance per team over {len(ids)} settled games "
                 "(cumulative net from settled transactions)",
                 fontsize=14, fontweight="bold")
    ax.set_xlabel("game")
    ax.set_ylabel("total balance")
    ax.set_xticks(ids)
    ax.margins(x=0.08)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, ncols=2, loc="upper left", framealpha=0.9)
    fig.savefig(DATA_DIR / "balance.png", dpi=130, bbox_inches="tight")
    print(f"wrote {DATA_DIR / 'balance.png'} / .csv")


if __name__ == "__main__":
    main()
