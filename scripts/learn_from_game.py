"""Turn a settled Game into a lesson, in the form an agent can act on.

    PYTHONPATH=. pixi run python scripts/learn_from_game.py            # every new Game
    PYTHONPATH=. pixi run python scripts/learn_from_game.py --games 26-30

`scripts/analyse_game.py` already attributes euros to mechanisms. This does the other half:
it joins the **decision log** written at submission time (`var/decisions/game_NNN.json`)
against the **reconstructed Fair Value**, so the output names the stage that was wrong rather
than the amount that was lost. "We lost 5,548" is not actionable. "Coverage on item 3 came
back 0.25 and the item was worth at least 150, and the Limit collapsed because of it" is.

## The four methodology errors this is built to prevent

Each of these produced a wrong conclusion in this project, and each is now impossible to
make by using this script instead of ad-hoc queries.

1. **Judging in log error rather than euros.** Log error weights a EUR 10 Line Item the same
   as a EUR 7,000 one, and the settled distribution runs to 7,225. Every verdict here is
   denominated in euros, with the log error reported only as a diagnostic.
2. **Conditioning on the true Fair Value.** Bucketing `t_hat / t` by *true* `t` says we are
   4x too high on cheap items; bucketing the same 235 items by *`t_hat`* says we are 46% too
   low. Both are regression artefacts and only the second is applicable, because at decision
   time we know `t_hat` and not `t`. A level correction fitted the first way lost 54,713.
   **This script conditions on `t_hat` and refuses to print the other view.**
3. **Ignoring the noise floor.** Two draws of the identical prompt differ by 26,622 over 18
   Games. A single Game is far inside that, so per-Game deltas are reported as evidence
   *towards* a hypothesis, never as a result, and the script says so in its own output.
4. **Reading the leaderboard positionally.** `/matrix` `cells` is a trailing 20-Game window
   aligned to `game_ids`, not indexed by Game id. Everything here derives nets from the
   Transaction identity instead.

## What it emits

`var/lessons/game_NNN.json` and a short markdown digest on stdout: the per-item join, the
stage attribution, and a ranked list of candidate hypotheses with the euros attached. The
digest is deliberately compact — it is meant to be read in full by a subagent that then
proposes one change.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from invert_fair_values import brackets  # noqa: E402
from pull_transactions import teams, transactions  # noqa: E402

from src.decision_log import load as load_decisions  # noqa: E402

US = "Bin busy"
LESSONS_DIR = Path("var/lessons")

#: Two draws of the identical prompt differ by this much over 18 Games. Anything smaller is
#: not a result, and the digest says so rather than letting a reader forget.
NOISE_FLOOR_18_GAMES = 26_622


def _our_numbers(rows: list[dict]) -> tuple[dict[int, float], dict[int, tuple[float, float]]]:
    """Our Charge per item, and the bracket on our Limit, from the settled rows."""
    charges: dict[int, float] = {}
    accepted: dict[int, list[float]] = {}
    rejected: dict[int, list[float]] = {}
    for row in rows:
        index = row["line_item_index"]
        if row["issuer"] == US and row["amount"] > 0:
            charges[index] = row["amount"]
        if row["reviewer"] == US:
            (accepted if row["accepted"] else rejected).setdefault(index, []).append(row["amount"])
    limits: dict[int, tuple[float, float]] = {}
    for index in set(accepted) | set(rejected):
        low = max((a for a in accepted.get(index, []) if a > 0), default=0.0)
        high = min((a for a in rejected.get(index, []) if a > 0), default=math.inf)
        limits[index] = (low, high)
    return charges, limits


def _mechanisms(rows: list[dict]) -> dict[str, float]:
    income = sum(r["amount"] for r in rows if r["issuer"] == US)
    paid = sum(r["amount"] for r in rows if r["reviewer"] == US and r["accepted"])
    penalties = sum(1.5 * r["amount"] for r in rows if r["reviewer"] == US and not r["accepted"])
    return {
        "income": income,
        "paid_on_accepts": paid,
        "penalties": penalties,
        "net": income - paid - penalties,
    }


def _stage(item: dict, t_lo: float, t_hi: float, charge: float | None) -> tuple[str, str]:
    """Name the stage that went wrong, and say why. This is the whole point of the script."""
    if item is None:
        return "no-decision-log", "Strategy 2 did not record this item; it may not have landed."
    if item["rule"] == "uninformed-constants":
        return "no-evidence", "No channel priced this item; the fitted constants were used."
    if not item["channels"]:
        return "no-channel", "No channel spoke at all."

    covered = t_lo > 0
    p = item.get("coverage_probability")
    median = item.get("price_median") or 0.0

    if covered and p is not None and p <= 2 / 3:
        return (
            "coverage-too-low",
            f"Coverage came back {p:.2f} so the Limit collapsed, but the item is worth at "
            f"least {t_lo:.0f}.",
        )
    if not covered and p is not None and p > 2 / 3:
        return (
            "coverage-too-high",
            f"Coverage came back {p:.2f} but the item is worth about nothing "
            f"(t < {t_hi:.0f}).",
        )
    if covered and charge is not None and charge > t_hi:
        return (
            "charge-above-t",
            f"Charged {charge:.0f} against t < {t_hi:.0f}, so every opponent owed us nothing.",
        )
    if covered and charge is not None and t_lo > 0 and charge < 0.5 * t_lo:
        return (
            "charge-far-below-t",
            f"Charged {charge:.0f} against t >= {t_lo:.0f}; the difference was forfeited from "
            f"every opponent.",
        )
    if covered and median > 0 and t_lo > 0 and median > 3 * t_hi:
        return "estimate-too-high", f"Estimated {median:.0f} against t < {t_hi:.0f}."
    return "ok", "Nothing obviously wrong with this item."


def analyse(game_id: int, team_names: list[str]) -> dict | None:
    rows = transactions(US, game_id)
    if not rows:
        return None
    table = brackets(game_id, team_names)
    log = load_decisions(game_id)
    by_index = {item["index"]: item for item in (log or {}).get("items", [])}
    charges, limits = _our_numbers(rows)

    items = []
    for index in sorted(table):
        t_lo, t_hi = table[index]
        decision = by_index.get(index)
        charge = charges.get(index)
        stage, why = _stage(decision, t_lo, t_hi, charge)
        # Penalties attributable to this item: 1.5x every fair Charge we rejected.
        penalty = sum(
            1.5 * r["amount"]
            for r in rows
            if r["reviewer"] == US and not r["accepted"] and r["line_item_index"] == index
        )
        items.append(
            {
                "index": index,
                "name": (decision or {}).get("name", ""),
                "t_lo": t_lo,
                "t_hi": None if t_hi == math.inf else t_hi,
                "our_charge": charge,
                "our_limit_bracket": limits.get(index),
                "estimate_median": (decision or {}).get("price_median"),
                "coverage_probability": (decision or {}).get("coverage_probability"),
                "channels": (decision or {}).get("channels"),
                "rule": (decision or {}).get("rule"),
                "penalties_here": penalty,
                "stage": stage,
                "why": why,
            }
        )

    # Estimate quality, conditioned on what we knew at decision time. See error 2 above.
    ratios = [
        (i["estimate_median"], (i["t_lo"] + i["t_hi"]) / 2)
        for i in items
        if i["estimate_median"] and i["t_hi"] and i["t_lo"] > 0
    ]
    log_errors = [math.log(est / true) for est, true in ratios if est > 0 and true > 0]

    return {
        "game_id": game_id,
        "had_decision_log": log is not None,
        "mechanisms": _mechanisms(rows),
        "items": items,
        "estimate": {
            "n_scorable": len(log_errors),
            "median_log_error": st.median(log_errors) if log_errors else None,
            "rmsle": math.sqrt(sum(e * e for e in log_errors) / len(log_errors))
            if log_errors
            else None,
        },
        "cost_by_stage": _cost_by_stage(items),
    }


def _cost_by_stage(items: list[dict]) -> dict[str, float]:
    """Penalties grouped by the stage that caused them. Ranks what to fix next."""
    totals: dict[str, float] = {}
    for item in items:
        totals[item["stage"]] = totals.get(item["stage"], 0.0) + item["penalties_here"]
    return dict(sorted(totals.items(), key=lambda kv: -kv[1]))


def digest(report: dict) -> str:
    m = report["mechanisms"]
    lines = [
        f"## Game {report['game_id']}  net {m['net']:+,.0f}",
        "",
        f"income {m['income']:+,.0f} | paid on accepts −{m['paid_on_accepts']:,.0f} "
        f"| penalties −{m['penalties']:,.0f}",
    ]
    if not report["had_decision_log"]:
        lines += [
            "",
            "**No decision log for this Game.** Either it predates the log or Strategy 2 did "
            "not run. Without it the stage attribution below is guesswork — check first.",
        ]
    est = report["estimate"]
    if est["rmsle"] is not None:
        lines += [
            "",
            f"estimate on {est['n_scorable']} scorable items: median log error "
            f"{est['median_log_error']:+.2f}, RMSLE {est['rmsle']:.2f} "
            f"(conditioned on our own estimate, never on the true value)",
        ]
    lines += ["", "### Penalties by stage", ""]
    for stage, cost in report["cost_by_stage"].items():
        if cost > 0:
            lines.append(f"- **{stage}** −{cost:,.0f}")
    worst = sorted(report["items"], key=lambda i: -i["penalties_here"])[:4]
    lines += ["", "### The items that cost the most", ""]
    for item in worst:
        if item["penalties_here"] <= 0 and item["stage"] == "ok":
            continue
        t_hi = "inf" if item["t_hi"] is None else f"{item['t_hi']:.0f}"
        lines.append(
            f"- item {item['index']} *{item['name'][:44]}* — t in [{item['t_lo']:.0f}, {t_hi}), "
            f"we charged {item['our_charge'] or 0:.0f}, penalties −{item['penalties_here']:,.0f}"
            f"\n  **{item['stage']}**: {item['why']}"
        )
    lines += [
        "",
        f"> One Game is far inside the {NOISE_FLOOR_18_GAMES:,} noise floor measured over 18 "
        "Games, so treat everything above as evidence towards a hypothesis, not a result. "
        "Confirm with `scripts/replay_payoffs.py` over every Game before changing a constant.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default=None, help="e.g. 26-30; default is every new Game")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of the digest")
    args = parser.parse_args()

    if args.games:
        start, _, end = args.games.partition("-")
        wanted = range(int(start), int(end or start) + 1)
    else:
        existing = {int(p.stem.split("_")[1]) for p in LESSONS_DIR.glob("game_*.json")}
        wanted = [
            int(p.stem.split("_")[1])
            for p in sorted(Path("var/decisions").glob("game_*.json"))
            if int(p.stem.split("_")[1]) not in existing
        ]

    team_names = teams()
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    for game_id in wanted:
        try:
            report = analyse(game_id, team_names)
        except Exception as error:
            print(f"Game {game_id}: could not analyse ({type(error).__name__}: {error})")
            continue
        if report is None:
            print(f"Game {game_id}: not settled yet.")
            continue
        (LESSONS_DIR / f"game_{game_id:03d}.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2) if args.json else digest(report))
        print()


if __name__ == "__main__":
    main()
