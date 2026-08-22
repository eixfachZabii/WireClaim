"""Simple, easy-to-read tables from the settled-game data.

Reads data/raw/transactions_game_*.json and data/analysis.json and writes:

- data/table_binbusy.png / .csv — one row per game: how many line items had
  a derived t = 0, on how many items Bin busy said "fraud" (rejected every
  nonzero charge, i.e. acted as if b = 0), how many of those really had t = 0,
  and the same fraud-call rate averaged over the top-3 and top-5 teams.
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


def said_fraud_items(game: dict, game_rows: list[dict], team: str) -> set[int]:
    """Items where the team, as reviewer, rejected every nonzero charge (acted as if t = 0, i.e. b ~ 0)."""
    charges = {i["line_item_index"]: i["charges_a"] for i in game["line_items"]}
    seen: dict[int, bool] = {}
    for row in game_rows:
        idx = row["line_item_index"]
        if row["reviewer"] != team or not charges.get(idx, {}).get(row["issuer"]):
            continue
        seen[idx] = seen.get(idx, True) and not row["accepted"]
    return {idx for idx, all_rejected in seen.items() if all_rejected}


def binbusy_table(analysis: dict, transactions: dict[int, list[dict]]) -> list[list[str]]:
    """Per game: items Bin busy called all-fraud (b = 0) vs. top teams vs. the derived t."""
    top3 = [t["team"] for t in analysis["team_summary"][:3]]
    top5 = [t["team"] for t in analysis["team_summary"][:5]]
    rows = [[
        "game", "items", "t = 0 items (derived)",
        f"{TEAM} said fraud (b = 0)", "of which really t = 0",
        "top 3 said fraud (avg)", "top 5 said fraud (avg)",
    ]]
    for game in analysis["games"]:
        game_id = game["game_id"]
        game_rows = transactions.get(game_id, [])
        items = game["line_items"]
        n = len(items)
        t_zero = {i["line_item_index"] for i in items if i["t_lo"] == 0 and i["t_hi"] is not None}
        bb = said_fraud_items(game, game_rows, TEAM)
        bb_right = bb & t_zero

        def avg_calls(teams: list[str], game=game, game_rows=game_rows, n=n) -> str:
            # average, over the game's items, of how many of these teams said fraud
            if not n or not teams:
                return "-"
            total = sum(len(said_fraud_items(game, game_rows, t)) for t in teams)
            return f"{total / n:.1f}/{len(teams)}"

        rows.append([
            str(game_id), str(n), f"{len(t_zero)}/{n}",
            f"{len(bb)}/{n}", f"{len(bb_right)}/{len(bb)}" if bb else "-",
            avg_calls(top3), avg_calls(top5),
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
