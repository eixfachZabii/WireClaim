"""Per game: who performed best, what they did, and why it worked.

Simple, fully derivable measures per team and game:
  net            income as Issuer minus costs as Reviewer (incl. 1.5a penalties)
  med a/t        median Charge relative to the derived Fair Value (aggressiveness)
  income split   fair accepts / accepted Overcharges / 1.5a penalties received
  cost split     accepted Overcharges paid / lawyer fees paid
plus a one-line "what worked" verdict from the dominant income source and cost leaks.

Writes data/teams.png (top-3 per game) and data/teams.csv (every team, every game).

Usage:
    python3 case_analysis/teams.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = Path(__file__).resolve().parent / "data"
TEAM = "Bin busy"
TOP_N = 3


def load() -> tuple[dict, dict[int, list[dict]]]:
    analysis = json.loads((DATA_DIR / "analysis.json").read_text())
    transactions: dict[int, list[dict]] = {}
    for path in sorted((DATA_DIR / "raw").glob("transactions_game_*.json")):
        game_id = int(re.search(r"(\d+)", path.stem).group(1))
        transactions[game_id] = json.loads(path.read_text())
    return analysis, transactions


def team_stats(game: dict, rows: list[dict]) -> dict[str, dict]:
    fair = {li["line_item_index"]: li["fair_flags"] for li in game["line_items"]}
    t_pt = {li["line_item_index"]: li["t_point"] for li in game["line_items"]}
    charges = {li["line_item_index"]: li["charges_a"] for li in game["line_items"]}

    stats: dict[str, dict] = {}

    def s(team: str) -> dict:
        return stats.setdefault(team, {
            "inc_fair": 0.0, "inc_over": 0.0, "inc_penalty": 0.0,
            "paid_fair": 0.0, "paid_over": 0.0, "lawyer": 0.0, "net": 0.0,
        })

    for row in rows:
        idx, amount = row["line_item_index"], row["amount"]
        issuer, reviewer = s(row["issuer"]), s(row["reviewer"])
        issuer["net"] += amount
        was_fair = fair.get(idx, {}).get(row["issuer"], True)
        if row["accepted"]:
            issuer["inc_fair" if was_fair else "inc_over"] += amount
            reviewer["paid_fair" if was_fair else "paid_over"] += amount
            reviewer["net"] -= amount
        elif amount > 0:
            issuer["inc_penalty"] += amount
            reviewer["lawyer"] += 1.5 * amount
            reviewer["net"] -= 1.5 * amount

    for team, st in stats.items():
        ratios = [
            charges[i][team] / t_pt[i]
            for i in charges
            if charges[i].get(team) and t_pt.get(i)
        ]
        st["med_at"] = median(ratios) if ratios else None
    return stats


def verdict(st: dict) -> str:
    if st["net"] <= 0:
        leak = "lawyer fees" if st["lawyer"] > st["paid_over"] else "accepted Overcharges"
        return f"lost money (biggest leak: {leak})"
    src = max(("inc_fair", "inc_over", "inc_penalty"), key=lambda k: st[k])
    what = {
        "inc_fair": "honest Charges the Field accepted",
        "inc_over": "Overcharges the Field swallowed",
        "inc_penalty": "1.5a penalties from strict reviewers",
    }[src]
    tight = " + tight Limit (no lawyer fees)" if st["lawyer"] == 0 else ""
    return f"won via {what}{tight}"


def fmt(x: float | None, money: bool = True) -> str:
    if x is None:
        return "-"
    return f"{x:,.0f}" if money else f"{x:.2f}"


def main() -> None:
    analysis, transactions = load()

    header = ["game", "team", "net", "med a/t", "inc fair", "inc over",
              "inc 1.5a", "paid over", "lawyer fees", "what worked"]
    png_rows: list[list[str]] = []
    csv_rows: list[list] = []

    for game in analysis["games"]:
        gid = game["game_id"]
        stats = team_stats(game, transactions.get(gid, []))
        ranked = sorted(stats.items(), key=lambda kv: kv[1]["net"], reverse=True)
        for rank, (team, st) in enumerate(ranked):
            csv_rows.append([gid, rank + 1, team, round(st["net"], 2),
                             None if st["med_at"] is None else round(st["med_at"], 3),
                             round(st["inc_fair"], 2), round(st["inc_over"], 2),
                             round(st["inc_penalty"], 2), round(st["paid_over"], 2),
                             round(st["lawyer"], 2), verdict(st)])
            if rank < TOP_N or team == TEAM:
                label = team if rank < TOP_N else f"{team} (#{rank + 1})"
                png_rows.append([str(gid), label, fmt(st["net"]),
                                 fmt(st["med_at"], money=False), fmt(st["inc_fair"]),
                                 fmt(st["inc_over"]), fmt(st["inc_penalty"]),
                                 fmt(st["paid_over"]), fmt(st["lawyer"]), verdict(st)])

    with (DATA_DIR / "teams.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["game", "rank", "team", "net", "med_a_over_t", "inc_fair",
                         "inc_over", "inc_penalty", "paid_over", "lawyer_fees", "verdict"])
        writer.writerows(csv_rows)

    fig, ax = plt.subplots(figsize=(17, 0.28 * len(png_rows) + 1.4))
    ax.axis("off")
    table = ax.table(cellText=png_rows, colLabels=header, loc="center",
                     cellLoc="center",
                     colWidths=[0.04, 0.14, 0.07, 0.06, 0.07, 0.07, 0.07, 0.07, 0.08, 0.33])
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.25)
    for (r, _c), cell in table.get_celld().items():
        if r == 0:
            cell.set_facecolor("#2c3e50")
            cell.set_text_props(color="white", fontweight="bold")
        elif png_rows[r - 1][1].startswith(TEAM):
            cell.set_facecolor("#fff3cd")
        elif r % 2 == 0:
            cell.set_facecolor("#f2f2f2")
    ax.set_title(f"Best teams per game (top {TOP_N} by net) + {TEAM} — "
                 "what they did and why it worked", fontsize=12, fontweight="bold", pad=12)
    fig.savefig(DATA_DIR / "teams.png", dpi=140, bbox_inches="tight")
    print(f"wrote {DATA_DIR / 'teams.png'} / .csv")


if __name__ == "__main__":
    main()
