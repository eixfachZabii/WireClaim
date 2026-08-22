"""Flatten every Line Item we have ever priced into one table, for backtesting.

    pixi run export

Writes `var/export/line_items.csv` and `.jsonl` — one row per (Game, Line Item), joining
what we *decided* against what the Game *settled at*. Nothing here is estimated,
reconstructed or inferred: every column is either a value the runner recorded at submission
time or a value recovered from published Transactions by arithmetic that reproduces every
leaderboard net to the cent (`scripts/invert_fair_values.py --verify`).

Three sources, joined on `(game_id, line_item_index)`:

* `var/decisions/game_NNN.json` — written by Strategy 2 at submission time, so it is what we
  believed *before* seeing any outcome. Carries the price band, the coverage probability,
  which channels spoke, the pricing rule, and the Charge and Limit it produced. Also carries
  a `proposals` block with what every other Strategy would have submitted for the same item.
* `var/lessons/game_NNN.json` — written after the Game settled. Carries the recovered Fair
  Value bracket, the Charge we are *known* to have submitted, the bracket on our own Limit,
  the penalty that landed on that item, and the stage attribution.
* the recovered Fair Value bracket itself, `[t_lo, t_hi)`.

## Reading the Fair Value columns without fooling yourself

`t_lo` is a **proven floor**: some Reviewer wrongfully rejected a Charge at that level, so
the item was worth at least that much. `t_hi` is a **proven ceiling** where it exists — some
Reviewer rightfully rejected a Charge there, so the item was worth less. Where `t_hi` is
empty the bracket is **unbounded** and the item is worth *at least* `t_lo`, possibly far
more. `t_bounded` says which.

That distinction is not cosmetic and it has already cost this project several hours. The
unbounded items are unbounded precisely *because* nobody rightfully rejected a Charge on
them, which correlates with them being expensive relative to what the field charged. So any
statistic computed **conditional on the true `t`** — "our estimate is low on expensive
items" — is a regression artefact of its own conditioning variable. Bucket by `t_hat`, the
only quantity available at submission time, or the sign of the result flips. See CLAUDE.md's
falsified-intuitions table.

`t_point` is offered as a convenience — the bracket midpoint where bounded, `t_lo` where not
— and it *understates* the unbounded ones by construction. Prefer the bracket.

## What the two Charge columns mean, and why both are here

`charge_decided` is what the pricing engine computed. `charge_settled` is what the settled
Transactions prove we actually submitted. They usually agree. They differ when a later
Strategy overwrote the submission, or when the decision log was written more than once for a
Game — Game 42's log is flagged `partial` for exactly that reason and its rows are marked.
When they disagree, `charge_settled` is authoritative.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DECISIONS = ROOT / "var" / "decisions"
LESSONS = ROOT / "var" / "lessons"
OUT_DIR = ROOT / "var" / "export"

#: A real Game id is three digits. The test suite uses four so its fixtures can never be
#: mistaken for a settled Game -- see `tests/test_strategy2.py`.
REAL_GAME = range(0, 101)

COLUMNS = [
    "game_id",
    "line_item_index",
    "name",
    "quantity",
    "quantity_missing",
    # what we believed at submission time
    "t_hat",
    "price_low",
    "price_high",
    "sigma",
    "coverage_probability",
    "channels",
    "memory_backed",
    "model_backed",
    "rule",
    # what we submitted
    "charge_decided",
    "limit_decided",
    "charge_settled",
    "limit_lower_bracket",
    "limit_upper_bracket",
    # what the Game settled at
    "t_lo",
    "t_hi",
    "t_bounded",
    "t_point",
    # what it cost, and why
    "penalty_on_this_item",
    "stage",
    "why",
    # the counterfactual: what every Strategy would have submitted
    "strategy1_charge",
    "strategy1_limit",
    "strategy2_charge",
    "strategy2_limit",
    "strategy3_charge",
    "strategy3_limit",
    # convenience ratios, all guarded against a zero denominator
    "charge_over_t_lo",
    "limit_over_t_lo",
    "t_hat_over_t_point",
    # provenance
    "decision_log_partial",
]


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _ratio(numerator: Any, denominator: Any) -> float | None:
    try:
        num, den = float(numerator), float(denominator)
    except (TypeError, ValueError):
        return None
    if den <= 0 or num != num or den != den:
        return None
    return round(num / den, 6)


def _proposal(proposals: dict[str, Any], source: str, index: int) -> tuple[Any, Any]:
    """`(charge, limit)` that Strategy `source` offered for this Line Item, or `(None, None)`.

    The block is keyed by source and then by Line Item index as a *string*, because it came
    back through JSON. An empty mapping for a source is meaningful and preserved: it says
    that Strategy answered with nothing, which is not the same as never having run.
    """
    per_source = (proposals or {}).get(source)
    if not isinstance(per_source, dict):
        return None, None
    pair = per_source.get(str(index)) or per_source.get(index)
    if isinstance(pair, (list, tuple)) and len(pair) >= 2:
        return pair[0], pair[1]
    if isinstance(pair, dict):
        return pair.get("charge"), pair.get("limit")
    return None, None


def rows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted(DECISIONS.glob("game_*.json")):
        try:
            game_id = int(path.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        if game_id not in REAL_GAME:
            continue
        decision = _load(path)
        if not decision:
            continue
        lesson = _load(LESSONS / f"game_{game_id:03d}.json") or {}
        settled = {item["index"]: item for item in lesson.get("items", [])}
        proposals = decision.get("proposals") or {}
        partial = bool(decision.get("partial"))

        for item in decision.get("items", []):
            index = item.get("index")
            if index is None:
                continue
            after = settled.get(index, {})
            bracket = after.get("our_limit_bracket") or (None, None)
            t_lo, t_hi = after.get("t_lo"), after.get("t_hi")
            bounded = t_hi is not None and math.isfinite(float(t_hi or math.inf))
            t_point = (float(t_lo) + float(t_hi)) / 2 if bounded and t_lo is not None else t_lo
            channels = item.get("channels") or []
            row = {
                "game_id": game_id,
                "line_item_index": index,
                "name": item.get("name"),
                "quantity": item.get("quantity"),
                "quantity_missing": item.get("quantity_missing"),
                "t_hat": item.get("price_median"),
                "price_low": item.get("price_low"),
                "price_high": item.get("price_high"),
                "sigma": item.get("sigma"),
                "coverage_probability": item.get("coverage_probability"),
                "channels": "|".join(channels),
                "memory_backed": "B:memory" in channels,
                "model_backed": "C:model" in channels,
                "rule": item.get("rule"),
                "charge_decided": item.get("charge"),
                "limit_decided": item.get("limit"),
                "charge_settled": after.get("our_charge"),
                "limit_lower_bracket": bracket[0] if bracket else None,
                "limit_upper_bracket": bracket[1] if bracket else None,
                "t_lo": t_lo,
                "t_hi": t_hi,
                "t_bounded": bounded,
                "t_point": t_point,
                "penalty_on_this_item": after.get("penalties_here"),
                "stage": after.get("stage"),
                "why": after.get("why"),
                "charge_over_t_lo": _ratio(after.get("our_charge"), t_lo),
                "limit_over_t_lo": _ratio(item.get("limit"), t_lo),
                "t_hat_over_t_point": _ratio(item.get("price_median"), t_point),
                "decision_log_partial": partial,
            }
            for source in ("strategy1", "strategy2", "strategy3"):
                charge, limit = _proposal(proposals, source, index)
                row[f"{source}_charge"] = charge
                row[f"{source}_limit"] = limit
            out.append(row)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    table = rows()
    args.out.mkdir(parents=True, exist_ok=True)
    csv_path, jsonl_path = args.out / "line_items.csv", args.out / "line_items.jsonl"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(table)
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in table:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    games = sorted({row["game_id"] for row in table})
    scorable = [r for r in table if r["t_lo"] is not None]
    bounded = [r for r in scorable if r["t_bounded"]]
    print(f"{len(table)} Line Items over {len(games)} Games (Games {games[0]}-{games[-1]})")
    print(f"  with a recovered Fair Value : {len(scorable)}")
    print(f"    of which bounded          : {len(bounded)}  (the rest are worth AT LEAST t_lo)")
    print(f"  memory-backed               : {sum(1 for r in table if r['memory_backed'])}")
    print(f"  from a partial decision log : {sum(1 for r in table if r['decision_log_partial'])}")
    print(f"\nWrote {csv_path}\n      {jsonl_path}")


if __name__ == "__main__":
    main()
