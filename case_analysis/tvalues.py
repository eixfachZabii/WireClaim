"""Per line item of the last games: derived t, our implied t-hat, and a/t & b/t
for Bin busy vs. the current top performers.

t per item is the rule-inversion bracket from analyze.py ([t_lo, t_hi), t_point).
"Our t-hat" is inferred from our own Charge: the submission itself is not public,
but our Charge a is, and per R5b a is placed relative to the t we derived — so
a / 0.7 is the closest observable proxy (shown next to the raw Charge).

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
TEAM = "Bin busy"
COMPARE = ["eyay", "error404 ai"]


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=5, help="how many recent games")
    args = parser.parse_args()

    analysis = json.loads((DATA_DIR / "analysis.json").read_text())
    top = COMPARE
    games = analysis["games"][-args.games:]

    header = ["game", "item", "t bracket", "t point",
              f"{TEAM} a", f"{TEAM} t-hat (a/0.7)", f"{TEAM} a/t"]
    header += [f"{name} a/t" for name in top]
    header += [f"{TEAM} b/t"]
    header += [f"{name} b/t" for name in top]

    png_rows: list[list[str]] = []
    t_errors: list[float] = []
    for game in games:
        for li in game["line_items"]:
            t = li["t_point"]
            lo, hi = li["t_lo"], li["t_hi"]
            bracket = ("-" if lo is None and hi is None
                       else f"[{lo or 0:,.0f}, {'∞' if hi is None else f'{hi:,.0f}'})")
            our_a = li["charges_a"].get(TEAM)
            if our_a and t:
                t_errors.append(abs(our_a / 0.7 - t) / t)
            row = [
                str(game["game_id"]), str(li["line_item_index"]), bracket,
                "-" if t is None else f"{t:,.0f}",
                "-" if not our_a else f"{our_a:,.0f}",
                "-" if not our_a else f"{our_a / 0.7:,.0f}",
                ratio(our_a, t),
            ]
            row += [ratio(li["charges_a"].get(name), t) for name in top]
            row += [ratio(b_mid(li["limits_b"].get(TEAM)), t)]
            row += [ratio(b_mid(li["limits_b"].get(name)), t) for name in top]
            png_rows.append(row)

    avg_off = (f"{100 * sum(t_errors) / len(t_errors):,.0f}%" if t_errors else "-")
    summary = (["avg", "", "", "", "", f"t-hat off by {avg_off}", ""]
               + [""] * (len(header) - 7))
    png_rows.append(summary)

    with (DATA_DIR / "tvalues.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(png_rows)

    fig, ax = plt.subplots(figsize=(16, 0.26 * len(png_rows) + 1.6))
    ax.axis("off")
    table = ax.table(cellText=png_rows, colLabels=header, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    table.scale(1, 1.2)
    table.auto_set_column_width(list(range(len(header))))
    prev_game = None
    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_facecolor("#2c3e50")
            cell.set_text_props(color="white", fontweight="bold")
            continue
        game_id = png_rows[r - 1][0]
        if c == 0 and game_id != prev_game:
            prev_game = game_id
        if r == len(png_rows):
            cell.set_facecolor("#d6eaf8")
            cell.set_text_props(fontweight="bold")
        elif c in (4, 5, 6, 7 + len(top)):
            cell.set_facecolor("#fff3cd")
        elif game_id.isdigit() and int(game_id) % 2 == 0:
            cell.set_facecolor("#f2f2f2")
    ax.set_title(
        f"Derived t per line item — last {len(games)} settled games: "
        f"{TEAM} vs. {', '.join(top)} — a/t side by side, then b/t; "
        f"last row: avg % our implied t-hat is off the derived t",
        fontsize=11, fontweight="bold", pad=12,
    )
    fig.savefig(DATA_DIR / "tvalues.png", dpi=140, bbox_inches="tight")
    print(f"wrote {DATA_DIR / 'tvalues.png'} / .csv ({len(png_rows)} line items)")


if __name__ == "__main__":
    main()
