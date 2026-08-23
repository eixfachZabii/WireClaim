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

## The counterfactual half: what would the *other* strategies have scored?

Three strategies price every Case and only the winner is submitted, so for most of this
tournament we had no evidence that the winner deserved to win. The decision log now carries
**every** Proposal the router saw (`proposals`, schema 2), and `scripts/replay_payoffs.py`
turns each of them into a net with every opponent held fixed — it reproduces every published
net to the cent, so the comparison is a measurement rather than an argument. Per Game the
digest reports:

* the net we actually took (the authoritative identity over the rows, never a `/matrix` cell),
* the net each recorded strategy would have produced,
* an **oracle** (`a = t_lo`, `b = t_hi`) as the ceiling, so the gap to perfect is visible,
* and the **items** that drive the difference between the winner and the best alternative.

Then a pooled view over every Game that has a log, because one Game is inside the noise
floor and a standing answer needs to accumulate: which strategy leads, by how much, whether
that lead clears the noise, and on which kind of Line Item the winner gives money away.
Line Items are bucketed by **our own estimate** `t_hat`, never by the true `t` — see error 2.

`fast_path` is emitted from `main.py` rather than the router, so it is *not* in the log and
cannot be scored here. A missing `fast_path` row means "not recorded", not "stayed silent".

## What it emits

`var/lessons/game_NNN.json` and a short markdown digest on stdout: the per-item join, the
stage attribution, the counterfactual table, and a ranked list of candidate hypotheses with
the euros attached. The digest is deliberately compact — it is meant to be read in full by a
subagent that then proposes one change.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from invert_fair_values import brackets, charges as field_charges  # noqa: E402
from pull_transactions import teams, transactions  # noqa: E402
from replay_payoffs import (  # noqa: E402
    UnreconstructableGame,
    our_actual_submission,
    replay,
    snapshot,
)

from src.runtime.decisions import load as load_decisions  # noqa: E402
from src.runtime.decisions import proposals as logged_proposals  # noqa: E402
from src.strategies import STRATEGY_PRIORITIES  # noqa: E402

US = "Bin busy"
LESSONS_DIR = Path("var/lessons")

#: Two draws of the identical prompt differ by this much over 18 Games. Anything smaller is
#: not a result, and the digest says so rather than letting a reader forget.
NOISE_FLOOR_18_GAMES = 26_622

#: Buckets for "which kind of Line Item does the winner lose on", cut on **our own estimate**
#: `t_hat` and never on the true `t`. Conditioning the other way is error 2 above and it cost
#: 54,713 the one time a correction was fitted that way.
THAT_BUCKETS = ((100.0, "t_hat < 100"), (1_000.0, "t_hat 100-1k"), (math.inf, "t_hat >= 1k"))


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


def _mechanisms(
    rows: list[dict],
    table: dict[int, tuple[float, float]] | None = None,
    opponent_charges: dict[tuple[int, str], float] | None = None,
) -> dict[str, float]:
    """The Game's money, and -- crucially -- what our strictness *saved* as well as cost.

    The first three numbers were the whole story this digest told for its first forty Games,
    and they made the Limit look like an open wound: every Game printed a large `penalties`
    figure and nothing at all on the other side of the ledger. But a rejection has two very
    different meanings depending on which column of the payoff table it lands in:

        rejected a *fair* Charge    -> we pay 1.5a where accepting costs a. The 0.5a is
                                       waste, and it is the only part that is.
        rejected a *fraudulent* one -> we pay nothing, where a loose Limit would have paid
                                       the whole `a`. That is a saving, and it never appeared.

    Measured over the first forty Games the invisible column is the bigger one: **582,594
    saved against 225,630 of lawyer waste, a ratio of 2.58 to 1**, and +229,600 net once the
    127,364 of fraud we did let through is subtracted. Reading `penalties` alone had us
    arguing the Limit was too tight on four separate occasions.

    Needs the recovered brackets and the Field's Charges, because a rightful rejection is
    recorded as an `amount` of zero -- the Charge we avoided has to be recovered from the
    rows of whoever *did* pay it. Where that is impossible the Charge is simply omitted, so
    `saved_by_rejecting` is a floor rather than an estimate.
    """
    income = sum(r["amount"] for r in rows if r["issuer"] == US)
    paid = sum(r["amount"] for r in rows if r["reviewer"] == US and r["accepted"])
    penalties = sum(1.5 * r["amount"] for r in rows if r["reviewer"] == US and not r["accepted"])
    mechanisms = {
        "income": income,
        "paid_on_accepts": paid,
        "penalties": penalties,
        "net": income - paid - penalties,
    }
    if table is None or opponent_charges is None:
        return mechanisms

    decided: dict[tuple[int, str], bool] = {}
    for row in rows:
        if row["reviewer"] == US and row["issuer"] != US:
            decided[(row["line_item_index"], row["issuer"])] = bool(row["accepted"])

    saved = waste = let_through = 0.0
    for (index, team), charge in opponent_charges.items():
        if team == US or (index, team) not in decided:
            continue
        t_lo, t_hi = table.get(index, (0.0, math.inf))
        accepted = decided[(index, team)]
        if accepted:
            if t_hi != math.inf and charge >= t_hi:
                let_through += charge
        elif charge <= t_lo:
            waste += 0.5 * charge
        elif t_hi != math.inf and charge >= t_hi:
            saved += charge
    mechanisms.update(
        saved_by_rejecting=saved,
        lawyer_waste=waste,
        fraud_let_through=let_through,
        strictness_net=saved - waste - let_through,
    )
    return mechanisms


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
    if covered and median > 0 and median < t_lo:
        # `t_lo` is a *proven* floor -- somebody was wrongfully rejected at that Charge -- so a
        # median below it is definitely wrong, with no interpretation needed.
        #
        # This stage exists because our largest single failure mode had no name and therefore
        # no cost. Game 44's stolen watch carried **85% of that Game's penalty** and was tagged
        # `ok`: `charge-far-below-t` needs the Charge under half the floor, and we Charged
        # 4,738 against a half-floor of 4,680 -- it missed by fifty-eight euros. Game 41's
        # watch was the same shape at a larger scale.
        #
        # Note it is the *median* that is wrong, not the band: Game 44's posterior ran to
        # 12,155 and did contain the truth. So this is a centring failure, which is why
        # widening the band does not fix it and why it survives into the Charge, which is
        # taken as a factor of the median.
        # The shortfall is quoted because the stage alone implies a severity it does not have.
        # Game 76 tagged three items `estimate-too-low`, and one of them was a median of 597
        # against a floor of 599 -- **0.3 % out**, carrying 3,434 of penalty. That is not an
        # estimation failure, it is a Limit sitting a third of the way down a correct posterior,
        # and a reader who sees only the label goes looking for the wrong bug. The per-Game
        # reviews read this line and chase what it says.
        #
        # Deliberately *not* a threshold. The comment above records why: `charge-far-below-t`
        # already gates on `0.5 * t_lo`, and that gate missed Game 44's watch by fifty-eight
        # euros on an item carrying 85 % of the Game's penalty. Suppressing small shortfalls
        # would rebuild exactly that trap. Every one still gets named; the reader now gets the
        # number needed to triage them.
        shortfall = (t_lo - median) / t_lo if t_lo > 0 else 0.0
        return (
            "estimate-too-low",
            f"Estimated {median:.0f} against a proven floor of t >= {t_lo:.0f} "
            f"({shortfall:.1%} low); the Charge and the Limit are both taken from that median, "
            f"so both landed low.",
        )
    return "ok", "Nothing obviously wrong with this item."


def analyse(game_id: int, team_names: list[str], *, with_replay: bool = True) -> dict | None:
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

    counterfactual = (
        counterfactuals(game_id, log, items)
        if with_replay
        else {"available": False, "note": "Counterfactual replay skipped (--no-replay)."}
    )

    return {
        "game_id": game_id,
        "had_decision_log": log is not None,
        "log_schema": (log or {}).get("schema"),
        "mechanisms": _mechanisms(rows, table, field_charges(game_id, team_names)),
        "items": items,
        "counterfactual": counterfactual,
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


# ------------------------------------------------------------------- counterfactual nets


def _noise_floor(n_games: int) -> float:
    """The measured noise floor rescaled to `n_games`, as a total in euros.

    26,622 is a *measured* total over 18 Games, so the per-Game scale is
    `26,622 / sqrt(18) ≈ 6,275` if the draws are independent, and the total over n Games
    grows as `sqrt(n)`. The independence is an assumption; the 26,622 is not. Either way the
    honest reading is that a lead smaller than this number is not a result yet.
    """
    return NOISE_FLOOR_18_GAMES * math.sqrt(max(n_games, 1) / 18.0)


def _bucket(t_hat: float | None) -> str:
    if not t_hat or t_hat <= 0:
        return "no estimate"
    for edge, label in THAT_BUCKETS:
        if t_hat < edge:
            return label
    return THAT_BUCKETS[-1][1]


def _oracle_submissions(snap) -> tuple[dict[int, tuple[float, float]], dict[int, tuple[float, float]]]:
    """Two ceilings: `a = t` (the honest fair-play bound) and the true best play.

    **`a = t_lo` is not a ceiling and printing it as one was a bug.** On a Line Item worth
    nothing `t_lo` is 0, so that "oracle" charges nothing, earns nothing, and loses to
    whatever we actually did. Game 28 made it obvious: all ten items had `t = 0`, we scored
    +5,298 by charging anyway, and the "oracle" came out at −760 with a "gap to perfect" of
    −5,298. A ceiling you can beat is a broken measurement, not a triumph.

    So the first reference is `a = t, b = t`: charge the Fair Value exactly, which every
    opponent owes whether they accept or wrongfully reject, and accept exactly the fair
    Charges. That is the bound on honest play.

    The second is the **true optimum against this specific Field**, which is higher, because
    an Overcharge is a free option (R6c): a rejected Overcharge costs the issuer nothing, so
    on an item worth little the best Charge is the largest one a generous opponent will still
    pay. Income is separable per Line Item, so it can be maximised exactly:

        a <= t   ->  income = a x (every opponent, all of whom owe it)
        a >  t   ->  income = a x (opponents whose Limit still accepts it)

    The candidates are therefore `t` and each opponent's Limit. This is what "perfect" really
    means here, and it is a fact about *these sixteen opponents* — it is a yardstick, never a
    strategy, because R9 says their Limits will not survive their next recalibration.
    """
    fair_play: dict[int, tuple[float, float]] = {}
    best_play: dict[int, tuple[float, float]] = {}
    n_opponents = max(len(snap.opponents), 1)
    for index in snap.line_items:
        point = snap.fair_point(index)
        fair_play[index] = (point, point)

        # Guaranteed-acceptance thresholds: a Charge at or below `b_lo` is certainly accepted.
        thresholds = sorted(
            {
                low
                for low, _high in snap.limit_brackets.get(index, {}).values()
                if low > 0
            }
        )
        best_charge, best_income = point, point * n_opponents
        for candidate in thresholds:
            if candidate <= point:
                continue  # already covered by charging `point`, which everybody owes
            takers = sum(
                1
                for low, _high in snap.limit_brackets.get(index, {}).values()
                if candidate <= low
            )
            if candidate * takers > best_income:
                best_charge, best_income = candidate, candidate * takers
        best_play[index] = (best_charge, point)
    return fair_play, best_play


def _item_nets(result) -> dict[int, float]:
    return {index: income - cost for index, (income, cost) in result.per_item.items()}


def counterfactuals(game_id: int, log: dict | None, item_rows: list[dict]) -> dict:
    """What each recorded strategy would have scored on this Game, and where they differ.

    Never raises: a Game that cannot be reconstructed, or has no log, returns a report that
    says so. The alternative — a silent gap — is what let a misattributed Game 16 sit in a
    cache being scored against for a week.
    """
    recorded = logged_proposals(log)
    report: dict = {
        "available": False,
        "note": "",
        "winner": (log or {}).get("winner"),
        "strategies": {},
        "drivers": [],
    }
    if log is None:
        report["note"] = "No decision log for this Game, so no Proposal was recorded."
        return report
    if not recorded:
        report["note"] = (
            "The log predates the `proposals` section (schema 1), so only the winner's "
            "numbers exist. Nothing to compare — this is not evidence that the other "
            "strategies stayed silent."
        )

    try:
        snap = snapshot(game_id)
    except UnreconstructableGame as error:
        report["note"] = f"Game does not reconstruct: {error}"
        return report
    except Exception as error:  # network, missing rows, malformed payload
        report["note"] = f"Could not reconstruct the Game ({type(error).__name__}: {error})."
        return report

    replayed_actual = replay(snap, our_actual_submission(snap))
    reconstructs = abs(replayed_actual.net - snap.published_net) <= 0.01
    requested_oracle, exact_oracle = _oracle_submissions(snap)
    report.update(
        {
            "available": True,
            "reconstructs": reconstructs,
            "actual_net": snap.published_net,
            "replayed_actual_net": replayed_actual.net,
            "oracle_net": replay(snap, requested_oracle).net,
            "oracle_exact_net": replay(snap, exact_oracle).net,
            "line_items": len(snap.line_items),
        }
    )
    if not reconstructs:
        report["note"] = (
            f"Replaying our own submission gives {replayed_actual.net:,.2f} against an "
            f"authoritative {snap.published_net:,.2f}. Treat every counterfactual below as "
            "unusable until that is explained."
        )

    per_item: dict[str, dict[int, float]] = {}
    for source, submission in sorted(recorded.items()):
        if not submission:
            report["strategies"][source] = {
                "net": None,
                "items_priced": 0,
                "note": "answered with an empty Proposal",
            }
            continue
        result = replay(snap, submission)
        per_item[source] = _item_nets(result)
        report["strategies"][source] = {
            "net": result.net,
            "income": result.income,
            "cost": result.cost,
            "items_priced": len(submission),
            "items_missing": sorted(set(snap.line_items) - set(submission)),
        }

    scored = {s: d["net"] for s, d in report["strategies"].items() if d["net"] is not None}
    winner = report["winner"] if report["winner"] in scored else None
    alternatives = {s: n for s, n in scored.items() if s != winner}
    if winner is not None and alternatives:
        best = max(alternatives, key=lambda s: alternatives[s])
        report["best_alternative"] = best
        report["best_alternative_delta"] = alternatives[best] - scored[winner]
        report["drivers"] = _drivers(
            snap, per_item[winner], per_item[best], log, item_rows
        )
    elif scored:
        report["best_alternative"] = None
        report["best_alternative_delta"] = 0.0
    return report


def _drivers(
    snap, winner_items: dict[int, float], alt_items: dict[int, float], log: dict, item_rows: list[dict]
) -> list[dict]:
    """Per-item `alternative - winner`, largest absolute difference first.

    This is the actionable part: a total says which strategy to prefer, an item says what to
    change in the one we keep. The bucket is cut on our own estimate, never on the true `t`.
    """
    by_index = {row["index"]: row for row in item_rows}
    logged = {item["index"]: item for item in (log or {}).get("items", [])}
    drivers = []
    for index in sorted(set(winner_items) | set(alt_items)):
        delta = alt_items.get(index, 0.0) - winner_items.get(index, 0.0)
        if abs(delta) < 0.01:
            continue
        t_hat = (logged.get(index) or {}).get("price_median")
        t_lo, t_hi = snap.fair_brackets[index]
        drivers.append(
            {
                "index": index,
                "name": (by_index.get(index) or {}).get("name") or (logged.get(index) or {}).get("name", ""),
                "delta": delta,
                "winner_net": winner_items.get(index, 0.0),
                "alternative_net": alt_items.get(index, 0.0),
                "t_hat": t_hat,
                "bucket": _bucket(t_hat),
                "t_lo": t_lo,
                "t_hi": None if t_hi == math.inf else t_hi,
                "rule": (logged.get(index) or {}).get("rule"),
            }
        )
    return sorted(drivers, key=lambda d: -abs(d["delta"]))


def digest(report: dict) -> str:
    m = report["mechanisms"]
    lines = [
        f"## Game {report['game_id']}  net {m['net']:+,.0f}",
        "",
        f"income {m['income']:+,.0f} | paid on accepts −{m['paid_on_accepts']:,.0f} "
        f"| penalties −{m['penalties']:,.0f}",
    ]
    if "strictness_net" in m:
        # The other side of the Limit's ledger. Without this the digest prints a large
        # `penalties` figure every Game and nothing at all to weigh it against, which reads
        # as "the Limit is bleeding us" when over forty Games strictness is +229,600 ahead.
        ratio = m["saved_by_rejecting"] / m["lawyer_waste"] if m["lawyer_waste"] else float("inf")
        lines += [
            "",
            f"the Limit: +{m['saved_by_rejecting']:,.0f} saved by rightly rejecting "
            f"| −{m['lawyer_waste']:,.0f} lawyer waste on fair claims "
            f"| −{m['fraud_let_through']:,.0f} fraud let through "
            f"→ **{m['strictness_net']:+,.0f}**"
            + (f"  ({ratio:.1f}:1 saved to wasted)" if ratio != float("inf") else ""),
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
    lines += _counterfactual_lines(report.get("counterfactual") or {})
    lines += [
        "",
        f"> One Game is far inside the {NOISE_FLOOR_18_GAMES:,} noise floor measured over 18 "
        f"Games (≈ {_noise_floor(1):,.0f} for a single Game), so treat everything above as "
        "evidence towards a hypothesis, not a result. Confirm with `scripts/replay_payoffs.py` "
        "over every Game before changing a constant.",
    ]
    return "\n".join(lines)


def _counterfactual_lines(cf: dict) -> list[str]:
    """The per-Game counterfactual table. Says why it is empty rather than printing nothing."""
    lines = ["", "### What each strategy would have scored", ""]
    if not cf.get("available"):
        return lines + [f"_{cf.get('note') or 'Not computed.'}_"]

    actual = cf["actual_net"]
    lines.append(f"- **actually submitted** {actual:+,.0f}  (authoritative identity over the rows)")
    for source, data in sorted(
        cf["strategies"].items(), key=lambda kv: -(kv[1]["net"] if kv[1]["net"] is not None else -math.inf)
    ):
        if data["net"] is None:
            lines.append(f"- `{source}` — {data.get('note', 'no net')}")
            continue
        flag = "  ← winner, submitted" if source == cf.get("winner") else ""
        missing = data.get("items_missing") or []
        gap = f", {len(missing)} item(s) unpriced" if missing else ""
        lines.append(
            f"- `{source}` {data['net']:+,.0f}  ({data['items_priced']} items priced{gap})"
            f"  vs actual {data['net'] - actual:+,.0f}{flag}"
        )
    lines.append(
        f"- **honest ceiling** (a = b = t) {cf['oracle_net']:+,.0f}; **best play against this "
        f"Field** {cf['oracle_exact_net']:+,.0f} — gap to perfect "
        f"{cf['oracle_exact_net'] - actual:+,.0f}"
    )
    if cf.get("note"):
        lines += ["", f"_{cf['note']}_"]
    if not cf.get("reconstructs", True):
        lines += ["", "**This Game does not reconstruct — do not act on the table above.**"]

    best = cf.get("best_alternative")
    if best and cf.get("drivers"):
        delta = cf["best_alternative_delta"]
        floor = _noise_floor(1)
        verdict = "would have beaten" if delta > 0 else "lost to"
        placing = "inside" if abs(delta) <= floor else "outside"
        lines += [
            "",
            f"Best alternative `{best}` {verdict} the winner by {abs(delta):,.0f}, which is "
            f"{placing} the {floor:,.0f} single-Game noise floor — one Game never justifies a "
            "change either way. The items driving it:",
            "",
        ]
        for driver in cf["drivers"][:5]:
            t_hi = "inf" if driver["t_hi"] is None else f"{driver['t_hi']:.0f}"
            t_hat = "—" if driver["t_hat"] is None else f"{driver['t_hat']:.0f}"
            lines.append(
                f"- item {driver['index']} *{driver['name'][:40]}* {driver['delta']:+,.0f} "
                f"(winner {driver['winner_net']:+,.0f}, `{best}` {driver['alternative_net']:+,.0f}) "
                f"— t_hat {t_hat} [{driver['bucket']}], t in [{driver['t_lo']:.0f}, {t_hi})"
            )
    elif cf.get("strategies"):
        # Three states reach here and they are not the same thing. This branch used to assert
        # the first one unconditionally, so a Game that recorded strategy2, strategy4 and
        # strategy5 -- and printed all three, with their nets, four lines above -- was followed
        # by "Only one strategy was recorded". `best_alternative` was set; what was empty was
        # `drivers`, because the best alternative priced every Line Item identically to the
        # winner and so no item *drove* a difference.
        scored = {
            source: data["net"]
            for source, data in cf["strategies"].items()
            if data.get("net") is not None
        }
        winner = cf.get("winner")
        others = {s: n for s, n in scored.items() if s != winner}
        if len(scored) < 2 or winner not in scored:
            lines += [
                "",
                "_Only one strategy was recorded, so there is nothing to compare against._",
            ]
        elif all(abs(net - scored[winner]) < 0.01 for net in others.values()):
            lines += [
                "",
                f"_Every other track priced this Case identically to `{winner}` "
                f"({', '.join(sorted(others))}), so there is no difference to attribute._",
            ]
        else:
            ranked = sorted(others.items(), key=lambda kv: -kv[1])
            lines += [
                "",
                f"_No alternative beat `{winner}` on this Case:_ "
                + ", ".join(f"`{s}` {net - scored[winner]:+,.0f}" for s, net in ranked)
                + ". _One Game never justifies a change either way._",
            ]
    return lines


# ------------------------------------------------------------------------- pooled answer


def pooled(reports: list[dict]) -> dict:
    """Accumulate the counterfactual across Games, which is the only scale that can decide.

    Two strategies are only compared on the Games where **both** were recorded — an unpaired
    total would credit whichever strategy happened to be logged on the expensive Cases. The
    per-item losses are bucketed on our own estimate `t_hat`, never on the true `t`.

    The pairing is **against a reference track**, not an intersection across every track, and
    that distinction is the whole reason this function was rewritten. It used to keep only the
    Games where *all* sources had a net. Strategy 4 landed at Game 62, so on its first Game
    that intersection became empty and the digest reported `+0 over the 0 shared Game(s)` for
    every track at once — 37 Games of accumulated evidence blanked by adding one experiment.
    Pairing each track against the reference costs nothing when the tracks are coeval and
    degrades gracefully when they are not: a new track is simply compared over the handful of
    Games it has, with its own `n` printed next to it.

    The reference is the track with the most Games recorded, ties broken by priority — in
    practice Strategy 2, which is also the only track the router may submit, so "how does this
    compare to what we actually sent" is the question a reader wants answered anyway.
    """
    usable = [
        r
        for r in reports
        if (r.get("counterfactual") or {}).get("available")
        and (r["counterfactual"].get("reconstructs", True))
    ]
    nets: dict[str, dict[int, float]] = {}
    for report in usable:
        for source, data in report["counterfactual"]["strategies"].items():
            if data["net"] is not None:
                nets.setdefault(source, {})[report["game_id"]] = data["net"]

    games = sorted({g for by_game in nets.values() for g in by_game})
    reference = (
        max(nets, key=lambda s: (len(nets[s]), STRATEGY_PRIORITIES.get(s, 0))) if nets else None
    )
    overlap = (
        {source: sorted(set(by_game) & set(nets[reference])) for source, by_game in nets.items()}
        if reference
        else {}
    )
    #: The Games where every track answered. Reported for honesty about the sample, but no
    #: longer the denominator of anything -- see the docstring.
    shared = [g for g in games if all(g in by_game for by_game in nets.values())] if nets else []

    per_source = {
        source: {
            "games": len(by_game),
            "total": sum(by_game.values()),
            "shared_games": len(overlap[source]),
            "total_on_shared": sum(by_game[g] for g in overlap[source]),
            "reference_on_shared": sum(nets[reference][g] for g in overlap[source]),
        }
        for source, by_game in sorted(nets.items())
    }
    # "Best on N" is counted only over the Games where a track actually had a rival, and the
    # denominator is carried alongside it. A track logged alone in a Game has not won it.
    wins: dict[str, int] = {}
    contested: dict[str, int] = {}
    for game_id in games:
        contenders = {s: by_game[game_id] for s, by_game in nets.items() if game_id in by_game}
        if len(contenders) < 2:
            continue
        for source in contenders:
            contested[source] = contested.get(source, 0) + 1
        best = max(contenders, key=lambda s: contenders[s])
        wins[best] = wins.get(best, 0) + 1

    buckets: dict[str, dict[str, float]] = {}
    for report in usable:
        cf = report["counterfactual"]
        best = cf.get("best_alternative")
        if not best:
            continue
        for driver in cf["drivers"]:
            row = buckets.setdefault(
                driver["bucket"], {"winner_gave_away": 0.0, "winner_won": 0.0, "items": 0}
            )
            row["items"] += 1
            key = "winner_gave_away" if driver["delta"] > 0 else "winner_won"
            row[key] += abs(driver["delta"])

    # The headline is the reference against its strongest challenger, measured on that
    # challenger's own overlap -- so the sample size behind the verdict is the challenger's,
    # and it is printed. `_noise_floor` is evaluated at that same n rather than at the
    # all-tracks intersection, which was how a 1-Game track used to make every lead read as
    # decided over zero Games.
    leader = reference
    challengers = {
        source: data
        for source, data in per_source.items()
        if source != reference and data["shared_games"] > 0
    }
    # Ranked by the *delta* to the reference on each challenger's own overlap, not by raw
    # total: two challengers scored over different windows have incomparable totals, which is
    # the same error this function was rewritten to remove.
    runner_up = (
        max(
            challengers,
            key=lambda s: challengers[s]["total_on_shared"] - challengers[s]["reference_on_shared"],
        )
        if challengers
        else None
    )
    lead = 0.0
    lead_games = 0
    if runner_up:
        lead_games = per_source[runner_up]["shared_games"]
        lead = per_source[runner_up]["reference_on_shared"] - per_source[runner_up]["total_on_shared"]

    return {
        "games_with_counterfactual": [r["game_id"] for r in usable],
        "games_missing_log": [
            r["game_id"] for r in reports if not (r.get("counterfactual") or {}).get("available")
        ],
        "shared_games": shared,
        "reference": reference,
        "per_source": per_source,
        "wins_on_shared": dict(sorted(wins.items(), key=lambda kv: -kv[1])),
        "contested_games": contested,
        "leader": leader,
        "runner_up": runner_up,
        "lead_over_runner_up": lead,
        "lead_games": lead_games,
        "noise_floor": _noise_floor(lead_games),
        "decisive": bool(lead_games) and abs(lead) > _noise_floor(lead_games),
        "loss_by_bucket": dict(sorted(buckets.items(), key=lambda kv: -kv[1]["winner_gave_away"])),
        "actual_total": sum(r["counterfactual"]["actual_net"] for r in usable),
        "oracle_total": sum(r["counterfactual"]["oracle_exact_net"] for r in usable),
    }


def _lessons_on_disk() -> list[dict]:
    """Every lesson written so far, so the pooled answer accumulates instead of resetting."""
    reports = []
    for path in sorted(LESSONS_DIR.glob("game_*.json")):
        try:
            reports.append(json.loads(path.read_text()))
        except (OSError, ValueError):
            continue
    return reports


def pooled_digest(pool: dict) -> str:
    lines = ["## Pooled across every Game with a decision log", ""]
    if pool["games_missing_log"]:
        missing = ", ".join(str(g) for g in pool["games_missing_log"])
        lines += [
            f"No usable counterfactual for Game(s) {missing} — either the Game predates the "
            "log, the log predates the `proposals` section, or the Game does not reconstruct. "
            "Those Games are excluded rather than guessed at.",
            "",
        ]
    if not pool["per_source"]:
        scored = ", ".join(str(g) for g in pool["games_with_counterfactual"]) or "none"
        return "\n".join(
            lines
            + [
                "_No strategy Proposal has been recorded yet, so there is nothing to compare._ "
                f"Game(s) {scored} reconstruct and have an actual and an oracle net, but their "
                "logs predate the `proposals` section: the counterfactual answer starts "
                "accumulating with the next Game the router logs.",
            ]
        )

    reference = pool["reference"]
    lines += [
        f"Scored on {len(pool['games_with_counterfactual'])} Game(s); "
        f"{len(pool['shared_games'])} of them recorded every track. Each track below is "
        f"compared against `{reference}` over the Games **both** were recorded in, so a newly "
        f"added track shrinks its own sample and nobody else's.",
        "",
    ]
    for source, data in sorted(pool["per_source"].items(), key=lambda kv: -kv[1]["total_on_shared"]):
        contested = pool["contested_games"].get(source, 0)
        if source == reference:
            lines.append(
                f"- `{source}` {data['total']:+,.0f} over all {data['games']} Game(s) it was "
                f"recorded in — the reference; best on {pool['wins_on_shared'].get(source, 0)} "
                f"of the {contested} Game(s) where it had a rival"
            )
            continue
        delta = data["total_on_shared"] - data["reference_on_shared"]
        lines.append(
            f"- `{source}` {data['total_on_shared']:+,.0f} against `{reference}`'s "
            f"{data['reference_on_shared']:+,.0f} over the {data['shared_games']} Game(s) both "
            f"were recorded in ({delta:+,.0f}) — {data['total']:+,.0f} over all "
            f"{data['games']}; best on {pool['wins_on_shared'].get(source, 0)} of {contested}"
        )
    lines += [
        "",
        f"- **actually submitted** {pool['actual_total']:+,.0f}; **oracle ceiling** "
        f"{pool['oracle_total']:+,.0f}",
    ]
    if pool["leader"] and pool["runner_up"]:
        verdict = "clears" if pool["decisive"] else "does **not** clear"
        lines += [
            "",
            f"`{pool['leader']}` leads `{pool['runner_up']}` by {pool['lead_over_runner_up']:,.0f} "
            f"over the {pool['lead_games']} Game(s) both were recorded in, which {verdict} the "
            f"{pool['noise_floor']:,.0f} noise floor at that sample size. "
            + (
                "Treat it as measured."
                if pool["decisive"]
                else "So the priority order is not yet justified by evidence — keep it and keep measuring."
            )
            + (
                f" On {pool['lead_games']} Game(s) only; re-read this line as more settle."
                if pool["lead_games"] < 5
                else ""
            ),
        ]
    if pool["loss_by_bucket"]:
        lines += ["", "### Where the winner gives money away (bucketed on our own t_hat)", ""]
        for bucket, row in pool["loss_by_bucket"].items():
            lines.append(
                f"- **{bucket}** — the winner gave away {row['winner_gave_away']:,.0f} to the "
                f"best alternative and beat it by {row['winner_won']:,.0f} elsewhere, "
                f"over {row['items']:.0f} item(s) where the two differed"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default=None, help="e.g. 26-30; default is every new Game")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of the digest")
    parser.add_argument(
        "--no-replay",
        action="store_true",
        help="skip the counterfactual replay (faster, and works without the replay cache)",
    )
    parser.add_argument(
        "--pooled-only",
        action="store_true",
        help="re-pool the lessons already on disk without re-analysing any Game",
    )
    args = parser.parse_args()

    if args.pooled_only:
        print(pooled_digest(pooled(_lessons_on_disk())))
        return

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
            report = analyse(game_id, team_names, with_replay=not args.no_replay)
        except Exception as error:
            print(f"Game {game_id}: could not analyse ({type(error).__name__}: {error})")
            continue
        if report is None:
            print(f"Game {game_id}: not settled yet.")
            continue
        (LESSONS_DIR / f"game_{game_id:03d}.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2) if args.json else digest(report))
        print()

    # Pooled over every lesson on disk, not only the Games analysed just now: one Game can
    # never settle "is Strategy 2 the best of the three", and the standing answer is the
    # only one worth acting on.
    if not args.json and not args.no_replay:
        print(pooled_digest(pooled(_lessons_on_disk())))


if __name__ == "__main__":
    main()
