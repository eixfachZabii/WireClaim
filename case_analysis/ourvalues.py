"""Bin busy only — actual submitted a and b, derived t, normalized ratios and
per-item/per-round net for the last 10 settled games.

a and b come from var/export/line_items.csv (charge_decided / limit_decided —
our real submissions); where a game is missing there, they fall back to the
public reconstruction (a from settled rows, b as the interval midpoint).
t is the rule-inversion t_point from analyze.py.

Writes data/ourvalues.csv and rewrites the machine-readable table in
dashboard.md between the OURVALUES markers.

Usage:
    python3 case_analysis/ourvalues.py [--games N]   (default: last 10)
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
EXPORT_CSV = HERE.parent / "var" / "export" / "line_items.csv"
DASHBOARD = HERE / "dashboard.md"
TEAM = "Bin busy"
START = "<!-- OURVALUES:START -->"
END = "<!-- OURVALUES:END -->"


def our_submissions() -> tuple[
    dict[tuple[int, int], tuple[float, float]], dict[tuple[int, int], str]
]:
    """Read the freshest export on every run: (game, item) -> (a, b) and -> name."""
    values: dict[tuple[int, int], tuple[float, float]] = {}
    names: dict[tuple[int, int], str] = {}
    if not EXPORT_CSV.exists():
        return values, names
    with EXPORT_CSV.open() as f:
        for row in csv.DictReader(f):
            try:
                key = (int(row["game_id"]), int(row["line_item_index"]))
            except (KeyError, ValueError):
                continue
            name = (row.get("name") or "").strip()
            if name:
                names[key] = name
            try:
                values[key] = (float(row["charge_decided"]), float(row["limit_decided"]))
            except (KeyError, ValueError):
                continue
    return values, names


def b_mid(interval: dict | None) -> float | None:
    if not interval:
        return None
    lo, hi = interval.get("b_lo"), interval.get("b_hi")
    if hi is not None:
        return ((lo or 0) + hi) / 2
    return lo


def item_net(rows: list[dict], index: int) -> float:
    net = 0.0
    for r in rows:
        if r["line_item_index"] != index:
            continue
        if r["issuer"] == TEAM:
            net += r["amount"]
        if r["reviewer"] == TEAM:
            if r["accepted"]:
                net -= r["amount"]
            elif r["amount"] > 0:
                net -= 1.5 * r["amount"]
    return net


def fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:,.2f}"


def ratio(value: float | None, t: float | None) -> str:
    if value is None or not t:
        return "-"
    return f"{value / t:.2f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=10, help="how many recent games")
    args = parser.parse_args()

    analysis = json.loads((DATA_DIR / "analysis.json").read_text())
    games = analysis["games"][-args.games:]
    ours, names = our_submissions()

    header = ["game", "item", "name", "a (actual)", "b (actual)", "t (derived)",
              "a/t", "b/t", "item net", "source"]
    rows: list[list[str]] = []
    round_nets: dict[int, float] = {}
    for game in games:
        gid = game["game_id"]
        tx = json.loads((DATA_DIR / "raw" / f"transactions_game_{gid:03d}.json").read_text())
        for li in game["line_items"]:
            index = li["line_item_index"]
            if (gid, index) in ours:
                a, b = ours[(gid, index)]
                source = "submitted"
            else:
                a = li["charges_a"].get(TEAM)
                b = b_mid(li["limits_b"].get(TEAM))
                source = "reconstructed"
            t = li["t_point"]
            net = item_net(tx, index)
            round_nets[gid] = round_nets.get(gid, 0.0) + net
            rows.append([str(gid), str(index),
                         names.get((gid, index), "-"), fmt(a), fmt(b), fmt(t),
                         ratio(a, t), ratio(b, t), fmt(net), source])

    with (DATA_DIR / "ourvalues.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    lines = ["", f"Per line item, last {len(games)} settled games (full file: `data/ourvalues.csv`):", ""]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for row in rows:
        lines.append("| " + " | ".join(cell.replace("|", "/") for cell in row) + " |")
    lines += ["", "Net per round:", ""]
    lines.append("| game | net |")
    lines.append("|---|---|")
    for gid in sorted(round_nets):
        lines.append(f"| {gid} | {round_nets[gid]:,.2f} |")
    lines.append("")

    text = DASHBOARD.read_text()
    if START in text and END in text:
        before, rest = text.split(START, 1)
        _, after = rest.split(END, 1)
        DASHBOARD.write_text(before + START + "\n" + "\n".join(lines) + END + after)
        print(f"wrote {DATA_DIR / 'ourvalues.csv'} and updated dashboard.md ({len(rows)} items)")
    else:
        print(f"wrote {DATA_DIR / 'ourvalues.csv'} (dashboard markers not found)")


if __name__ == "__main__":
    main()
