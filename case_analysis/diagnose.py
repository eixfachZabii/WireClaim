"""Per-game money decomposition and Charge/Limit diagnosis for one team.

Reads data/raw/transactions_game_*.json and data/analysis.json and prints,
per settled game:

- income as Issuer, split into fair Charges, Overcharges accepted, and
  fair-rejected payouts (the Reviewer paid 1.5a; we still received a);
- costs as Reviewer, split into fair accepts, Overcharge accepts (pure loss),
  and 1.5a lawyer penalties;
- Charge-side stats: our a vs. the derived t bracket, vs. the top-3 teams;
- Limit-side stats: wrongful rejections and Overcharge accepts per item.

Usage:
    python3 case_analysis/diagnose.py [--team "Bin busy"] [--top 3]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


def load() -> tuple[dict, dict[int, list[dict]]]:
    analysis = json.loads((DATA_DIR / "analysis.json").read_text())
    transactions: dict[int, list[dict]] = {}
    for path in sorted((DATA_DIR / "raw").glob("transactions_game_*.json")):
        game_id = int(re.search(r"(\d+)", path.stem).group(1))
        transactions[game_id] = json.loads(path.read_text())
    return analysis, transactions


def decompose(game: dict, rows: list[dict], team: str) -> dict:
    """Split the team's money in one game into rule-derived buckets."""
    fair = {i["line_item_index"]: i["fair_flags"] for i in game["line_items"]}
    out = {
        "inc_fair": 0.0, "inc_over": 0.0, "inc_rej_fair": 0.0,
        "cost_fair_acc": 0.0, "cost_over_acc": 0.0, "cost_lawyer": 0.0,
        "n_over_acc": 0, "n_lawyer": 0, "n_issued_rej0": 0,
    }
    for row in rows:
        idx = row["line_item_index"]
        if row["issuer"] == team:
            if row["accepted"]:
                if fair[idx].get(team) is False:
                    out["inc_over"] += row["amount"]
                else:
                    out["inc_fair"] += row["amount"]
            elif row["amount"] > 0:
                out["inc_rej_fair"] += row["amount"]
            else:
                out["n_issued_rej0"] += 1
        if row["reviewer"] == team:
            if row["accepted"]:
                if fair[idx].get(row["issuer"]) is False:
                    out["cost_over_acc"] += row["amount"]
                    out["n_over_acc"] += 1
                else:
                    out["cost_fair_acc"] += row["amount"]
            elif row["amount"] > 0:
                out["cost_lawyer"] += 1.5 * row["amount"]
                out["n_lawyer"] += 1
    out["income"] = out["inc_fair"] + out["inc_over"] + out["inc_rej_fair"]
    out["costs"] = out["cost_fair_acc"] + out["cost_over_acc"] + out["cost_lawyer"]
    out["net"] = out["income"] - out["costs"]
    return out


def charge_stats(game: dict, team: str) -> list[tuple]:
    """Per line item: (idx, a, t_point, a/t, fair_flag)."""
    stats = []
    for item in game["line_items"]:
        a = item["charges_a"].get(team)
        t = item["t_point"]
        stats.append((
            item["line_item_index"], a, t,
            (a / t) if a and t else None,
            item["fair_flags"].get(team),
        ))
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", default="Bin busy")
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args()

    analysis, transactions = load()
    top = [t["team"] for t in analysis["team_summary"][:args.top]]
    print(f"team={args.team!r}  top-{args.top}={top}")

    header = (
        "game  income(fair/over/rejfair)          costs(fairacc/overacc/lawyer)"
        "            net       #overacc #lawyer #rej0"
    )
    print(header)
    totals: dict[str, float] = {}
    for game in analysis["games"]:
        d = decompose(game, transactions[game["game_id"]], args.team)
        for k, v in d.items():
            totals[k] = totals.get(k, 0) + v
        print(
            f"{game['game_id']:>4}  "
            f"{d['income']:>9,.0f} ({d['inc_fair']:,.0f}/{d['inc_over']:,.0f}/{d['inc_rej_fair']:,.0f})"
            f"   {d['costs']:>9,.0f} ({d['cost_fair_acc']:,.0f}/{d['cost_over_acc']:,.0f}/{d['cost_lawyer']:,.0f})"
            f"   {d['net']:>9,.0f}   {d['n_over_acc']:>4} {d['n_lawyer']:>5} {d['n_issued_rej0']:>5}"
        )
    print(
        f" ALL  {totals['income']:>9,.0f} ({totals['inc_fair']:,.0f}/{totals['inc_over']:,.0f}/"
        f"{totals['inc_rej_fair']:,.0f})   {totals['costs']:>9,.0f} ({totals['cost_fair_acc']:,.0f}/"
        f"{totals['cost_over_acc']:,.0f}/{totals['cost_lawyer']:,.0f})   {totals['net']:>9,.0f}"
        f"   {totals['n_over_acc']:>4.0f} {totals['n_lawyer']:>5.0f} {totals['n_issued_rej0']:>5.0f}"
    )

    print("\nCharge aggressiveness (median a/t per game, ours vs. top teams):")
    for game in analysis["games"]:
        def med(team: str, game=game) -> float | None:
            vals = sorted(r for _, _, _, r, _ in charge_stats(game, team) if r)
            return vals[len(vals) // 2] if vals else None

        ours = med(args.team)
        tops = [med(t) for t in top]
        fmt = lambda v: f"{v:.2f}" if v else "  - "
        print(f"  game {game['game_id']:>3}: ours={fmt(ours)}  " +
              "  ".join(f"{t}={fmt(v)}" for t, v in zip(top, tops)))


if __name__ == "__main__":
    main()
