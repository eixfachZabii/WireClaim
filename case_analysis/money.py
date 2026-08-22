"""Bin busy money flows per game, from the settled transaction rows.

Writes data/binbusy_money.png (+ .csv) with two panels:

1. Income vs. expenses per game — income = amounts received as Issuer;
   expenses as Reviewer = accepted amounts paid out + 1.5a lawyer penalties
   (a rejected row with amount > 0 means the charge was fair: the issuer got
   a and we paid 1.5a).
2. Lawyer fees per game — how many times we paid the 1.5a penalty and what
   it cost, i.e. when our Limit wrongly rejected a fair Charge.

Usage:
    python3 case_analysis/money.py
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
TEAM = "Bin busy"


def main() -> None:
    games: list[dict] = []
    for path in sorted((DATA_DIR / "raw").glob("transactions_game_*.json")):
        game_id = int(re.search(r"(\d+)", path.stem).group(1))
        income = expenses_accepted = lawyer_total = 0.0
        lawyer_count = 0
        for row in json.loads(path.read_text()):
            if row["issuer"] == TEAM:
                income += row["amount"]
            if row["reviewer"] == TEAM:
                if row["accepted"]:
                    expenses_accepted += row["amount"]
                elif row["amount"] > 0:  # fair charge rejected -> 1.5a penalty
                    lawyer_total += 1.5 * row["amount"]
                    lawyer_count += 1
        games.append({
            "game": game_id,
            "income": income,
            "expenses_accepted": expenses_accepted,
            "lawyer_count": lawyer_count,
            "lawyer_total": lawyer_total,
            "expenses": expenses_accepted + lawyer_total,
            "net": income - expenses_accepted - lawyer_total,
        })

    with (DATA_DIR / "binbusy_money.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(games[0].keys()))
        writer.writeheader()
        writer.writerows(games)

    ids = [g["game"] for g in games]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), constrained_layout=True)
    fig.suptitle(f"{TEAM} — money flows per game ({len(games)} settled games)",
                 fontsize=14, fontweight="bold")

    width = 0.35
    ax1.bar([i - width / 2 for i in ids], [g["income"] for g in games],
            width, label="income (as Issuer)", color="#2a9d8f")
    ax1.bar([i + width / 2 for i in ids], [g["expenses_accepted"] for g in games],
            width, label="paid out (accepted as Reviewer)", color="#e76f51")
    ax1.bar([i + width / 2 for i in ids], [g["lawyer_total"] for g in games], width,
            bottom=[g["expenses_accepted"] for g in games],
            label="lawyer fees (1.5a penalties)", color="#9b2226")
    ax1.plot(ids, [g["net"] for g in games], "k.-", label="net")
    ax1.axhline(0, color="grey", lw=0.8)
    ax1.set_title("Income vs. expenses")
    ax1.set_xlabel("game")
    ax1.set_xticks(ids)
    ax1.legend()
    ax1.grid(axis="y", alpha=0.3)

    ax2.bar(ids, [g["lawyer_count"] for g in games], color="#9b2226")
    for g in games:
        if g["lawyer_count"]:
            ax2.annotate(f"{g['lawyer_total']:,.0f}", (g["game"], g["lawyer_count"]),
                         ha="center", va="bottom", fontsize=9)
    ax2.set_title("Lawyer fees paid (count per game, label = total cost) — "
                  "our Limit wrongly rejected a fair Charge")
    ax2.set_xlabel("game")
    ax2.set_ylabel("times paid 1.5a")
    ax2.set_xticks(ids)
    ax2.grid(axis="y", alpha=0.3)

    fig.savefig(DATA_DIR / "binbusy_money.png", dpi=130, bbox_inches="tight")
    print(f"wrote {DATA_DIR / 'binbusy_money.png'} / .csv")


if __name__ == "__main__":
    main()
