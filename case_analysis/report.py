"""Simple, easy-to-read tables from the settled-game data.

Reads data/raw/transactions_game_*.json and data/analysis.json and writes:

- data/table_binbusy.png / .csv — one row per (game, line item):
  the derived Fair Value t, Bin busy's Limit b interval, how often Bin busy
  said "fraud" (rejected), and how often that was wrong. "Wrongly rejected"
  is exact per the rules: a rejected row with amount > 0 means the charge was
  fair (the reviewer paid the 1.5a lawyer penalty).
- data/table_averages.png / .csv — one row per game: average Charge a and
  Limit b of all active teams (teams that always submitted 0 are excluded),
  the same averages for the top-3 teams by net, Bin busy's own averages,
  and the derived t estimate.

Usage:
    python3 case_analysis/report.py
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
TOP_N = 3


def load() -> tuple[dict, dict[int, list[dict]]]:
    analysis = json.loads((DATA_DIR / "analysis.json").read_text())
    transactions: dict[int, list[dict]] = {}
    for path in sorted((DATA_DIR / "raw").glob("transactions_game_*.json")):
        game_id = int(re.search(r"(\d+)", path.stem).group(1))
        transactions[game_id] = json.loads(path.read_text())
    return analysis, transactions


def fmt(value, digits=0) -> str:
    if value is None:
        return "-"
    return f"{value:,.{digits}f}"


def binbusy_table(analysis: dict, transactions: dict[int, list[dict]]) -> list[list[str]]:
    """Per (game, line item): derived t, Bin busy's b, and its fraud calls vs. reality."""
    rows = [[
        "game", "item", "t_lo", "t_hi", "t = 0?",
        f"{TEAM} b (lo..hi)", "said fraud (rejected)", "wrongly rejected (was fair)",
        "accepted", "wrongly accepted (was fraud)",
    ]]
    for game in analysis["games"]:
        game_id = game["game_id"]
        # Bin busy's review decisions, straight from the settled rows
        decisions: dict[int, dict] = {}
        for row in transactions.get(game_id, []):
            if row["reviewer"] != TEAM:
                continue
            d = decisions.setdefault(
                row["line_item_index"],
                {"rejected": 0, "wrong_reject": 0, "accepted": 0, "wrong_accept": 0},
            )
            if row["accepted"]:
                d["accepted"] += 1
            else:
                d["rejected"] += 1
                if row["amount"] > 0:  # fair charge rejected => 1.5a penalty paid
                    d["wrong_reject"] += 1

        for item in game["line_items"]:
            index = item["line_item_index"]
            d = decisions.get(index, {"rejected": 0, "wrong_reject": 0, "accepted": 0, "wrong_accept": 0})
            # accepted fraud: issuer flagged fraudulent whose charge Bin busy accepted
            for row in transactions.get(game_id, []):
                if (row["reviewer"] == TEAM and row["line_item_index"] == index
                        and row["accepted"] and item["fair_flags"].get(row["issuer"]) is False):
                    d["wrong_accept"] += 1
            iv = item["limits_b"].get(TEAM)
            b_str = f"{fmt(iv['b_lo'])}..{fmt(iv['b_hi'])}" if iv else "-"
            t_zero = item["t_lo"] == 0 and item["t_hi"] is not None
            rows.append([
                str(game_id), str(index), fmt(item["t_lo"]), fmt(item["t_hi"]),
                "yes" if t_zero else "", b_str,
                str(d["rejected"]), str(d["wrong_reject"]),
                str(d["accepted"]), str(d["wrong_accept"]),
            ])
    return rows


def averages_table(analysis: dict) -> list[list[str]]:
    """Per game: field / top-3 / Bin busy average a and b, plus the derived t."""
    # active teams = charged nonzero at least once across all games
    active = set()
    for game in analysis["games"]:
        for item in game["line_items"]:
            for team, a in item["charges_a"].items():
                if a:
                    active.add(team)
    top = [t["team"] for t in analysis["team_summary"][:TOP_N]]

    def team_avgs(game: dict, teams) -> tuple:
        a_vals, b_vals = [], []
        for item in game["line_items"]:
            for team in teams:
                a = item["charges_a"].get(team)
                if a:
                    a_vals.append(a)
                iv = item["limits_b"].get(team)
                if iv and iv["b_hi"] is not None:
                    b_vals.append((iv["b_lo"] + iv["b_hi"]) / 2)
        avg = lambda v: sum(v) / len(v) if v else None
        return avg(a_vals), avg(b_vals)

    rows = [[
        "game", "avg a (active teams)", "avg b (active teams)",
        f"avg a (top {TOP_N})", f"avg b (top {TOP_N})",
        f"{TEAM} avg a", f"{TEAM} avg b", "avg derived t",
    ]]
    for game in analysis["games"]:
        a_all, b_all = team_avgs(game, active)
        a_top, b_top = team_avgs(game, top)
        a_bb, b_bb = team_avgs(game, [TEAM])
        t_points = [i["t_point"] for i in game["line_items"] if i["t_point"]]
        t_avg = sum(t_points) / len(t_points) if t_points else None
        rows.append([
            str(game["game_id"]), fmt(a_all), fmt(b_all), fmt(a_top), fmt(b_top),
            fmt(a_bb), fmt(b_bb), fmt(t_avg),
        ])
    return rows


def save_table(rows: list[list[str]], name: str, title: str) -> None:
    with (DATA_DIR / f"{name}.csv").open("w", newline="") as f:
        csv.writer(f).writerows(rows)

    header, body = rows[0], rows[1:]
    fig_height = 0.6 + 0.28 * len(body)
    fig, ax = plt.subplots(figsize=(max(10, 1.4 * len(header)), fig_height))
    ax.axis("off")
    table = ax.table(cellText=body, colLabels=header, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.3)
    table.auto_set_column_width(list(range(len(header))))
    for col in range(len(header)):
        table[0, col].set_facecolor("#264653")
        table[0, col].set_text_props(color="white", fontweight="bold")
    for row in range(1, len(body) + 1):
        if row % 2 == 0:
            for col in range(len(header)):
                table[row, col].set_facecolor("#f1f3f4")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(DATA_DIR / f"{name}.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {DATA_DIR / name}.png / .csv")


def main() -> None:
    analysis, transactions = load()
    n = len(analysis["games"])
    save_table(
        binbusy_table(analysis, transactions),
        "table_binbusy",
        f"{TEAM} as reviewer — fraud calls vs. derived Fair Value ({n} settled games)",
    )
    save_table(
        averages_table(analysis),
        "table_averages",
        f"Average Charge a / Limit b per game — field vs. top {TOP_N} vs. {TEAM}",
    )


if __name__ == "__main__":
    main()
