"""Who is awake? Per game, classify every team's observable behavior:

- dark        : charged nothing AND rejected everything they reviewed
                (the default a=0, b=0 submission — a money fountain, R10)
- accept-all  : accepted >= 95% of reviewed charges (b effectively infinite)
- reject-all  : accepted <= 5% but still issued real Charges (b ~ 0)
- autopilot   : one identical Charge value repeated on >= 70% of items
                (a scripted fallback, not a per-Case estimate)
- active      : everything else — real per-item numbers and a discriminating Limit

Signals per team & game (from the settled transaction rows):
issued nonzero Charges, acceptance rate as reviewer, lawyer penalties paid.
Also plots the count of not-fully-active opponents per game — the "how dark is
the field" number that decides whether Overcharging pays.

Writes data/activity.png and data/activity.csv.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

DATA_DIR = Path(__file__).resolve().parent / "data"
TEAM = "Bin busy"

STATUSES = ["active", "autopilot", "accept-all", "reject-all", "dark"]
COLORS = {"active": "#2ecc71", "autopilot": "#3498db", "accept-all": "#f1c40f",
          "reject-all": "#e67e22", "dark": "#7f8c8d"}


def classify(rows: list[dict], team: str) -> str:
    # observable charge per line item: max amount seen for this issuer & item
    per_item: dict[int, float] = {}
    for r in rows:
        if r["issuer"] == team:
            i = r["line_item_index"]
            per_item[i] = max(per_item.get(i, 0.0), r["amount"])
    charges = [round(v, 2) for v in per_item.values() if v > 0]
    reviewed = [r for r in rows if r["reviewer"] == team]
    accepted = sum(1 for r in reviewed if r["accepted"])
    acc_rate = accepted / len(reviewed) if reviewed else None
    if not charges and acc_rate is not None and acc_rate <= 0.05:
        return "dark"
    if acc_rate is not None and acc_rate >= 0.95:
        return "accept-all"
    if acc_rate is not None and acc_rate <= 0.05:
        return "reject-all"
    if charges and len(per_item) >= 3:
        most_common = max(charges.count(v) for v in set(charges))
        if most_common / len(per_item) >= 0.7:
            return "autopilot"
    return "active"


def main() -> None:
    files = sorted(DATA_DIR.glob("raw/transactions_game_*.json"))
    games: list[int] = []
    per_game: dict[int, dict[str, str]] = {}
    teams: set[str] = set()
    for f in files:
        gid = int(re.search(r"(\d+)", f.stem).group(1))
        rows = json.loads(f.read_text())
        if not rows:
            continue
        games.append(gid)
        names = {r["issuer"] for r in rows} | {r["reviewer"] for r in rows}
        teams |= names
        per_game[gid] = {t: classify(rows, t) for t in names}

    team_list = sorted(teams, key=lambda t: (t != TEAM, t.lower()))

    with (DATA_DIR / "activity.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["team", *games])
        for t in team_list:
            writer.writerow([t, *(per_game[g].get(t, "-") for g in games)])
        writer.writerow(["# not fully active",
                         *(sum(1 for s in per_game[g].values() if s != "active")
                           for g in games)])

    grid = [[STATUSES.index(per_game[g].get(t, "dark")) for g in games]
            for t in team_list]
    inactive = [sum(1 for s in per_game[g].values() if s != "active") for g in games]

    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(0.42 * len(games) + 3, 0.38 * len(team_list) + 4),
        height_ratios=[len(team_list), 5], sharex=False)
    cmap = ListedColormap([COLORS[s] for s in STATUSES])
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=len(STATUSES) - 1, aspect="auto")
    ax.set_xticks(range(len(games)), games, fontsize=7)
    ax.set_yticks(range(len(team_list)), team_list, fontsize=8)
    for i, t in enumerate(team_list):
        if t == TEAM:
            ax.get_yticklabels()[i].set_fontweight("bold")
    ax.set_title("Team activity per game (from settled transactions)",
                 fontsize=12, fontweight="bold")
    ax.legend(handles=[Patch(color=COLORS[s], label=s) for s in STATUSES],
              loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)

    ax2.bar(range(len(games)), inactive, color="#7f8c8d")
    ax2.set_xticks(range(len(games)), games, fontsize=7)
    ax2.set_ylabel("# not fully active", fontsize=8)
    ax2.set_xlabel("game", fontsize=9)
    ax2.grid(axis="y", alpha=0.3)
    ax2.set_title("How dark is the field? (teams not 'active' per game)", fontsize=10)

    fig.tight_layout()
    fig.savefig(DATA_DIR / "activity.png", dpi=140, bbox_inches="tight")
    print(f"wrote {DATA_DIR / 'activity.png'} / .csv "
          f"({len(team_list)} teams x {len(games)} games)")


if __name__ == "__main__":
    main()
