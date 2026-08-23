"""Per line item of the last games: derived t, and for Bin busy plus the best
performers of those games their Charge a, Limit b (interval midpoint), a/t, b/t
and the net income/payment on that item.

Bin busy's a and b are our ACTUAL submitted values from var/export/line_items.csv
(columns charge_decided / limit_decided) where available; other teams' values are
reconstructed from the public settled data.

t per item is the rule-inversion bracket from analyze.py ([t_lo, t_hi), t_point).
net per item = amounts received as Issuer − amounts paid as Reviewer (accepted
payouts + 1.5a lawyer penalties on rejected fair Charges).

Writes data/tvalues.png and data/tvalues.csv.

Usage:
    python3 case_analysis/tvalues.py [--games N]   (default: last 5 settled games)
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = Path(__file__).resolve().parent / "data"
EXPORT_CSV = Path(__file__).resolve().parent.parent / "var" / "export" / "line_items.csv"
TEAM = "Bin busy"
TOP_N = 3


def our_submissions() -> dict[tuple[int, int], tuple[float, float]]:
    """(game_id, line_item_index) -> (charge_decided, limit_decided)."""
    result: dict[tuple[int, int], tuple[float, float]] = {}
    if not EXPORT_CSV.exists():
        return result
    with EXPORT_CSV.open() as f:
        for row in csv.DictReader(f):
            try:
                key = (int(row["game_id"]), int(row["line_item_index"]))
                result[key] = (float(row["charge_decided"]), float(row["limit_decided"]))
            except (KeyError, ValueError):
                continue
    return result


def b_mid(interval: dict | None) -> float | None:
    if not interval:
        return None
    lo, hi = interval.get("b_lo"), interval.get("b_hi")
    if hi is not None:
        return ((lo or 0) + hi) / 2
    return lo


def ratio(value: float | None, t: float | None) -> str:
    if value is None or not t:
        return "-"
    return f"{value / t:.2f}"


def fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:,.0f}"


def item_nets(rows: list[dict]) -> dict[tuple[int, str], float]:
    """(line_item_index, team) -> net income/payment on that item."""
    nets: dict[tuple[int, str], float] = {}
    for r in rows:
        i = r["line_item_index"]
        nets[(i, r["issuer"])] = nets.get((i, r["issuer"]), 0.0) + r["amount"]
        cost = r["amount"] if r["accepted"] else (
            1.5 * r["amount"] if r["amount"] > 0 else 0.0)
        nets[(i, r["reviewer"])] = nets.get((i, r["reviewer"]), 0.0) - cost
    return nets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=5, help="how many recent games")
    args = parser.parse_args()

    analysis = json.loads((DATA_DIR / "analysis.json").read_text())
    games = analysis["games"][-args.games:]
    ours = our_submissions()

    nets_by_game: dict[int, dict[tuple[int, str], float]] = {}
    totals: dict[str, float] = {}
    for game in games:
        gid = game["game_id"]
        rows = json.loads(
            (DATA_DIR / "raw" / f"transactions_game_{gid:03d}.json").read_text())
        nets_by_game[gid] = item_nets(rows)
        for (_, team), v in nets_by_game[gid].items():
            totals[team] = totals.get(team, 0.0) + v

    ranked = sorted(totals, key=lambda t: totals[t], reverse=True)
    top = [t for t in ranked if t != TEAM][:TOP_N]
    show = [TEAM, *top]

    header = ["game", "item", "t bracket", "t point"]
    for name in show:
        header += [f"{name} a", f"{name} b", f"{name} a/t", f"{name} b/t",
                   f"{name} net"]

    png_rows: list[list[str]] = []
    for game in games:
        gid = game["game_id"]
        for li in game["line_items"]:
            t = li["t_point"]
            lo, hi = li["t_lo"], li["t_hi"]
            bracket = ("-" if lo is None and hi is None
                       else f"[{lo or 0:,.0f}, {'∞' if hi is None else f'{hi:,.0f}'})")
            row = [str(gid), str(li["line_item_index"]), bracket,
                   "-" if t is None else f"{t:,.0f}"]
            for name in show:
                if name == TEAM and (gid, li["line_item_index"]) in ours:
                    a, b = ours[(gid, li["line_item_index"])]
                else:
                    a = li["charges_a"].get(name)
                    b = b_mid(li["limits_b"].get(name))
                net = nets_by_game[gid].get((li["line_item_index"], name))
                row += [fmt(a), fmt(b), ratio(a, t), ratio(b, t), fmt(net)]
            png_rows.append(row)

    with (DATA_DIR / "tvalues.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(png_rows)

    fig, ax = plt.subplots(figsize=(19, 0.26 * len(png_rows) + 1.6))
    ax.axis("off")
    table = ax.table(cellText=png_rows, colLabels=header, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(7)
    table.scale(1, 1.2)
    table.auto_set_column_width(list(range(len(header))))
    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_facecolor("#2c3e50")
            cell.set_text_props(color="white", fontweight="bold")
            continue
        if 4 <= c <= 8:
            cell.set_facecolor("#fff3cd")
        elif int(png_rows[r - 1][0]) % 2 == 0:
            cell.set_facecolor("#f2f2f2")
    ax.set_title(
        f"Derived t per line item — last {len(games)} settled games: "
        f"a, b, a/t, b/t and net income/payment per item — "
        f"{TEAM} (actual submitted a/b) vs. best of these games ({', '.join(top)})",
        fontsize=11, fontweight="bold", pad=12,
    )
    fig.savefig(DATA_DIR / "tvalues.png", dpi=140, bbox_inches="tight")
    print(f"wrote {DATA_DIR / 'tvalues.png'} / .csv ({len(png_rows)} line items)")


if __name__ == "__main__":
    main()
