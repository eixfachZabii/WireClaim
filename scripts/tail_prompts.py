"""Prompt variants for Strategy 2, and a dumper that caches each one's evidence.

The point of keeping them here rather than in the Strategy is that a variant has to be
*scored* before it is believed, and scoring means a full replay against the real Field
(`tail_replay.py`). Only the winner is promoted into `strategy.py`.

    pixi run python scripts/tail_prompts.py --variant nohint --games 1-14
    pixi run python scripts/tail_replay.py --tag nohint --games 1-14

Evidence lands in `var/evidence/case_NN_<variant>.json`, the same layout `dump_evidence`
uses, so every downstream script reads it with `--tag <variant>`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dump_evidence import _dump, _path, load  # noqa: E402
from tail_replay import CASES  # noqa: E402

from src.data.case_loader import read_case  # noqa: E402
from src.services.strategies.strategy2 import strategy as s2  # noqa: E402

COMMON_HEAD = """Read this insurance Case and return evidence for every invoice Line Item.

Do not return a Charge, an Acceptance Limit, or a Fair Value. Deterministic code prices your evidence.
"""

COVERAGE_RULES = """
How to judge coverage:
- Judge the SERVICE BEING BILLED, not the object it concerns. Inspection, leak detection, drying and assessment are frequently indemnified even when the item investigated is not insured.
- Read cross-references to the end. An exclusion that finishes with wording like "the head of cost under 5.2.6 remains unaffected" is a pointer to cover, not an exclusion.
- A suspicious detail in the Damage Description is not an exclusion. Only a Policy clause is.
- quantity_missing=true means the invoice printed no amount and no unit, only dashes. Every such position in the settled Cases was worth exactly 0.
- An implausible quantity means the position is priced for the plausible quantity, not that it is excluded.
"""

ANCHORS = """
Price the actual work at real German market rates, and get the LEVEL right. Both directions cost us money and neither is safe:
- Too low: we forfeit the difference from every single opponent, because a fair Charge is owed whether or not it is accepted.
- Too high: we collect nothing at all.

Anchors, since gross totals for a whole Line Item are easy to get wrong by an order of magnitude:
- Tradesman labour runs roughly 60-110 EUR per hour, so an hourly Line Item is that rate multiplied by the hours: 6.75 technician hours is several hundred EUR, not tens.
- Small parts, fittings, screws and consumables are genuinely cheap: tens of EUR for the whole position.
- Equipment hire, drying, leak detection and disposal are typically 50-400 EUR per position.
- Appliances, electronics, restoration and structural work reach the low thousands.
"""

# The variant currently shipping: the distribution hint is present.
BASELINE = s2.PROMPT

# Ablation 1 -- the same prompt with the settled-distribution paragraph deleted. An earlier,
# stronger version of that hint produced a systematic undershoot; this asks whether the
# softened one still anchors.
NOHINT = f"""{COMMON_HEAD}
For each Line Item return:
- line_item: the POS number printed on the invoice. Use it exactly. Numbering may skip a number and may continue across several invoices in the same document.
- coverage_probability: the probability from 0 to 1 that this Policy indemnifies this position at all. This is the most valuable number you produce. Roughly 40% of positions are worth nothing.
- price_low, price_median, price_high: a realistic GROSS TOTAL band in EUR for the WHOLE Line Item at German market prices. Never a net amount, never a per-unit price. Make the band honest: wide when you are unsure, narrow when you are confident.
- clause: the Policy sentence that decides coverage, quoted verbatim.
{ANCHORS}{COVERAGE_RULES}
Return JSON only:
{{"items":[{{"line_item":1,"coverage_probability":0.9,"price_low":0.0,"price_median":0.0,"price_high":0.0,"clause":""}}]}}"""

# Ablation 2 -- no hint, plus the two structural changes: a per-unit rate that deterministic
# code multiplies by the printed quantity, and a magnitude class as a cross-check on the
# model's own number.
RATE = f"""{COMMON_HEAD}
For each Line Item return:
- line_item: the POS number printed on the invoice. Use it exactly. Numbering may skip a number and may continue across several invoices in the same document.
- coverage_probability: the probability from 0 to 1 that this Policy indemnifies this position at all. This is the most valuable number you produce. Roughly 40% of positions are worth nothing.
- unit_rate_low, unit_rate_median, unit_rate_high: a realistic GROSS band in EUR **per single unit of the printed quantity** at German market prices. For "Service technician hours (6.75 hrs)" that is the hourly rate; for "Remove skirting boards (12 m)" the price per metre; for "Restore plasterboard ceiling (8 m2)" the price per square metre; for a one-off position with quantity 1 it is simply the price of the whole position. Deterministic code multiplies your rate by the quantity printed on the invoice, so never do that multiplication yourself.
- magnitude: the order of magnitude of the GROSS TOTAL for the whole position, one of "trivial" (under 20 EUR), "tens" (20-120), "hundreds" (120-1000), "low_thousands" (1000-10000). Decide this independently, by thinking about what the whole job costs, and it will be cross-checked against your rate.
- clause: the Policy sentence that decides coverage, quoted verbatim.

Rates are gross, including 19% VAT. Make the band honest: wide when you are unsure, narrow when you are confident.
{ANCHORS}{COVERAGE_RULES}
Return JSON only:
{{"items":[{{"line_item":1,"coverage_probability":0.9,"unit_rate_low":0.0,"unit_rate_median":0.0,"unit_rate_high":0.0,"magnitude":"hundreds","clause":""}}]}}"""

# Ablation 3 -- no hint, gross totals as before, plus the magnitude class as a cross-check.
# This separates the magnitude idea from the per-unit-rate idea, which `RATE` conflates.
MAG = f"""{COMMON_HEAD}
For each Line Item return:
- line_item: the POS number printed on the invoice. Use it exactly. Numbering may skip a number and may continue across several invoices in the same document.
- coverage_probability: the probability from 0 to 1 that this Policy indemnifies this position at all. This is the most valuable number you produce. Roughly 40% of positions are worth nothing.
- price_low, price_median, price_high: a realistic GROSS TOTAL band in EUR for the WHOLE Line Item at German market prices. Never a net amount, never a per-unit price. An hourly, per-metre or per-square-metre position is the market rate multiplied by the quantity printed on the invoice: do that multiplication and report the product. Make the band honest: wide when you are unsure, narrow when you are confident.
- magnitude: the order of magnitude of that gross total, one of "trivial" (under 20 EUR), "tens" (20-120), "hundreds" (120-1000), "low_thousands" (1000-10000). Decide it independently, by asking what the whole job costs, before you look at your own numbers -- it is cross-checked against them.
- clause: the Policy sentence that decides coverage, quoted verbatim.
{ANCHORS}{COVERAGE_RULES}
Return JSON only:
{{"items":[{{"line_item":1,"coverage_probability":0.9,"price_low":0.0,"price_median":0.0,"price_high":0.0,"magnitude":"hundreds","clause":""}}]}}"""

VARIANTS = {
    "baseline": BASELINE,
    "nohint": NOHINT,
    "nohint2": NOHINT,  # same prompt, second sample: the run-to-run noise floor
    "rate": RATE,
    "mag": MAG,
}


async def one(game_id: int, variant: str, refresh: bool) -> str:
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return f"case {game_id:02d}: not extracted"
    if not refresh and load(game_id, variant) is not None:
        return f"case {game_id:02d}: cached"
    case = await read_case(game_id, case_dir)
    evidence = await asyncio.to_thread(s2._request_evidence, case, 60.0, VARIANTS[variant])
    _path(game_id, variant).parent.mkdir(parents=True, exist_ok=True)
    _path(game_id, variant).write_text(_dump(evidence))
    return f"case {game_id:02d}: {variant} items={len(evidence)}"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="nohint", choices=sorted(VARIANTS))
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))
    limit = asyncio.Semaphore(args.concurrency)

    async def guarded(game_id: int) -> str:
        async with limit:
            try:
                return await one(game_id, args.variant, args.refresh)
            except Exception as error:
                return f"case {game_id:02d}: FAILED {error}"

    for line in await asyncio.gather(*(guarded(g) for g in game_ids)):
        print(line)


if __name__ == "__main__":
    asyncio.run(main())
