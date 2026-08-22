"""Turn the raw leaderboard pull into a strategy-ready analysis JSON.

Reads case_analysis/data/raw/ (produced by fetch_data.py) and writes
case_analysis/data/analysis.json with, per settled Game and Line Item:

- every team's Charge `a` (recovered from published amounts, README R9 semantics:
  the published `amount` is what the Issuer receives in BOTH branches — the 0.5a
  lawyer fee never appears in a Transaction row),
- every team's Limit `b` as an interval [b_lo, b_hi) reconstructed from what the
  team accepted (b >= a) and rejected (b < a),
- averages of the known a values and of the b interval midpoints,
- a bracket for the secret Fair Value t: t_lo = max fair a, t_hi = min amount
  received by a fraudulent issuer (accept of a fraud pays min(a, c) > t),
- per team an estimate of the t they derived (t_hat), inferred from their own
  a and b (see `estimate_team_t`).

The lawyer-penalty rule from GAME_DESCRIPTION.md is what lets us classify rows:
  rejected & amount > 0  => the charge was FAIR (a <= t) and a == amount
                            (the reviewer is charged 1.5a, but the row shows a)
  rejected & amount == 0 => the charge was FRAUDULENT (a > t)
  accepted               => amount == min(a, c); if the issuer is known
                            fraudulent, amount > t, giving an upper bound on t.

Usage:
    python3 case_analysis/analyze.py
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_DIR = DATA_DIR / "raw"
OUT_PATH = DATA_DIR / "analysis.json"

# Deployed heuristic (README R5b): a well-calibrated issuer charges ~0.7 * t_hat.
CHARGE_TO_T_RATIO = 0.7


def load_raw() -> tuple[list[dict], dict, list[dict], dict[int, list[dict]]]:
    games = json.loads((RAW_DIR / "games.json").read_text())
    matrix = json.loads((RAW_DIR / "matrix.json").read_text())
    performance = json.loads((RAW_DIR / "performance.json").read_text())
    transactions: dict[int, list[dict]] = {}
    for path in sorted(RAW_DIR.glob("transactions_game_*.json")):
        game_id = int(re.search(r"(\d+)", path.stem).group(1))
        transactions[game_id] = json.loads(path.read_text())
    return games, matrix, performance, transactions


def analyze_line_item(rows: list[dict]) -> dict:
    """Invert one (game, line_item)'s rows into charges, limits and a t bracket."""
    issuers: dict[str, dict] = {}
    for row in rows:
        entry = issuers.setdefault(
            row["issuer"], {"a": None, "fair": None, "accepted_amounts": set()}
        )
        if row["accepted"]:
            entry["accepted_amounts"].add(round(row["amount"], 6))
        elif row["amount"] > 0:
            entry["fair"] = True
            entry["a"] = round(row["amount"], 6)
        else:
            entry["fair"] = False

    # A fair issuer's rows all show a; an accepted-only issuer shows min(a, c).
    for entry in issuers.values():
        if entry["a"] is None and entry["accepted_amounts"]:
            entry["a"] = max(entry["accepted_amounts"])
        # never rejected: fairness unknown strictly, except a = 0 is trivially fair
        if entry["fair"] is None and entry["accepted_amounts"] and entry["a"] == 0:
            entry["fair"] = True

    # t bracket
    t_lo = 0.0
    t_hi = math.inf
    for entry in issuers.values():
        if entry["fair"] is True and entry["a"] is not None:
            t_lo = max(t_lo, entry["a"])
        if entry["fair"] is False and entry["accepted_amounts"]:
            # amount received by a fraudulent issuer = min(a, c) > t
            t_hi = min(t_hi, min(entry["accepted_amounts"]))

    # Limits: b >= a for every accepted charge, b < a for every rejected one
    limits: dict[str, dict] = {}
    for row in rows:
        a = issuers[row["issuer"]]["a"]
        if a is None:
            continue
        interval = limits.setdefault(row["reviewer"], {"b_lo": 0.0, "b_hi": math.inf})
        if row["accepted"]:
            interval["b_lo"] = max(interval["b_lo"], a)
        else:
            interval["b_hi"] = min(interval["b_hi"], a)

    charges = {
        name: entry["a"] for name, entry in issuers.items() if entry["a"] is not None
    }
    known = [a for a in charges.values() if a > 0]
    b_mids = [
        (iv["b_lo"] + iv["b_hi"]) / 2
        for iv in limits.values()
        if math.isfinite(iv["b_hi"]) and iv["b_hi"] > 0
    ]

    return {
        "charges_a": charges,
        "fair_flags": {n: e["fair"] for n, e in issuers.items()},
        "limits_b": {
            name: {
                "b_lo": iv["b_lo"],
                "b_hi": iv["b_hi"] if math.isfinite(iv["b_hi"]) else None,
            }
            for name, iv in limits.items()
        },
        "avg_a": sum(known) / len(known) if known else 0.0,
        "avg_b_mid": sum(b_mids) / len(b_mids) if b_mids else None,
        "t_lo": t_lo,
        "t_hi": t_hi if math.isfinite(t_hi) else None,
        "t_point": _t_point(t_lo, t_hi),
    }


def _t_point(t_lo: float, t_hi: float) -> float:
    """Single working number for t: bracket midpoint, else the lower bound."""
    if math.isfinite(t_hi):
        return (t_lo + t_hi) / 2
    return t_lo


def estimate_team_t(team: str, items: list[dict]) -> dict:
    """Estimate the t a team derived per line item, from its own a and b.

    Two independent signals:
    - from the Charge: an issuer following the fair-zone logic charges at or
      below its t_hat; the deployed heuristic is a ~= 0.7 * t_hat, so
      t_from_a = a / 0.7 (upper-biased for teams charging at t_hat exactly).
    - from the Limit interval: a reviewer places b at/below its t_hat, so the
      interval midpoint is a floor-ish proxy.
    """
    per_item = []
    for item in items:
        a = item["charges_a"].get(team)
        iv = item["limits_b"].get(team)
        t_from_a = a / CHARGE_TO_T_RATIO if a else None
        t_from_b = None
        if iv is not None and iv["b_hi"] is not None:
            t_from_b = (iv["b_lo"] + iv["b_hi"]) / 2
        elif iv is not None and iv["b_lo"] > 0:
            t_from_b = iv["b_lo"]
        candidates = [x for x in (t_from_a, t_from_b) if x]
        per_item.append(
            {
                "line_item_index": item["line_item_index"],
                "a": a,
                "b_lo": iv["b_lo"] if iv else None,
                "b_hi": iv["b_hi"] if iv else None,
                "t_from_a": t_from_a,
                "t_from_b": t_from_b,
                "t_hat": sum(candidates) / len(candidates) if candidates else None,
                "true_t_lo": item["t_lo"],
                "true_t_hi": item["t_hi"],
            }
        )
    return {"team": team, "items": per_item}


def main() -> None:
    games, matrix, performance, transactions = load_raw()
    teams = [cell["team_name"] for cell in matrix["items"]]

    games_out = []
    for game_id, rows in sorted(transactions.items()):
        by_item: dict[int, list[dict]] = {}
        for row in rows:
            by_item.setdefault(row["line_item_index"], []).append(row)

        items = []
        for index in sorted(by_item):
            item = analyze_line_item(by_item[index])
            item["line_item_index"] = index
            items.append(item)

        games_out.append(
            {
                "game_id": game_id,
                "n_line_items": len(items),
                "line_items": items,
                "team_t_estimates": [estimate_team_t(t, items) for t in teams],
            }
        )

    # Cross-game per-team aggregates (accuracy of each team's derived t)
    team_summary = []
    for team in teams:
        ratios, n_charges, n_fair, n_fraud = [], 0, 0, 0
        for game in games_out:
            for item in game["line_items"]:
                a = item["charges_a"].get(team)
                flag = item["fair_flags"].get(team)
                if a:
                    n_charges += 1
                    if item["t_point"]:
                        ratios.append(a / item["t_point"])
                if flag is True:
                    n_fair += 1
                elif flag is False:
                    n_fraud += 1
        perf = next((p for p in performance if p["team_name"] == team), {})
        team_summary.append(
            {
                "team": team,
                "net": perf.get("net"),
                "income": perf.get("income"),
                "costs": perf.get("costs"),
                "n_nonzero_charges": n_charges,
                "n_fair_charges": n_fair,
                "n_fraud_charges": n_fraud,
                "fraud_rate": n_fraud / (n_fair + n_fraud) if (n_fair + n_fraud) else None,
                "median_a_over_t": sorted(ratios)[len(ratios) // 2] if ratios else None,
            }
        )

    payload = {
        "generated_from": {
            "settled_games": sorted(transactions),
            "n_teams": len(teams),
            "total_games_scheduled": len(games),
        },
        "teams": teams,
        "games": games_out,
        "team_summary": sorted(
            team_summary, key=lambda t: -(t["net"] if t["net"] is not None else -math.inf)
        ),
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH} ({len(games_out)} settled games, {len(teams)} teams)")


if __name__ == "__main__":
    main()
