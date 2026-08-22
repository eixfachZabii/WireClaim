"""What we ask the model, and what has already been tried and failed.

The model returns **evidence only** — a coverage probability, a gross-total price band and
a quoted Policy clause. It never returns a Charge, a Limit or a Fair Value; `src/pricing/engine.py`
derives those deterministically (ADR 0001). Two regenerations over one invoice must not
disagree about the number we are scored on.
"""

from __future__ import annotations

from src.strategies.strategy2.constants import SETTLED_MEDIAN

#: Every figure here is measured over the 457 settled Line Items whose Fair Value we have
#: recovered, and every one of them used to be too low. The hint previously said the median
#: was 59 (it is 97), that a quarter fall under 20 (it is 25), and that the top decile "runs
#: past 400 EUR to several thousand" -- when p90 is 616, p99 is 2,345 and the largest settled
#: position we have seen is 11,131. Understating a distribution to a model is not a neutral
#: act: it anchors low, and it anchors hardest exactly where we are already measurably worst,
#: which is the expensive tail. On Game 41 a watch declared on a valuables schedule settled
#: at `t >= 11,131` and we priced it at 5,524.
_DISTRIBUTION_HINT = (
    "\nFor reference, here is the settled distribution of these positions, measured over 457 "
    "positions whose true value is known. It is wide and very skewed:\n"
    "  25% under 25 EUR   median "
    f"{SETTLED_MEDIAN:.0f} EUR"
    "   75% under 330 EUR   90% under 616 EUR   99% under 2,345 EUR\n"
    "The remaining 1% runs into five figures; the largest settled position seen so far is "
    "11,131 EUR. Expensive positions are rarer than they look but they are not bounded by a "
    "few thousand, and they are typically declared valuables, specialist restoration, or a "
    "whole-system replacement rather than a labour line.\n"
    "Use this as a sanity check on the shape, never as an anchor for an individual position. "
    "Pricing an expensive item like the median is the single most expensive mistake you can "
    "make here, and it is the one we actually make: on the positions we have got wrong, we "
    "are far more often too low than too high.\n"
)

_TEMPLATE = """Read this insurance Case and return evidence for every invoice Line Item.

Do not return a Charge, an Acceptance Limit, or a Fair Value. Deterministic code prices your evidence.

For each Line Item return:
- line_item: the POS number printed on the invoice. Use it exactly. Numbering may skip a number and may continue across several invoices in the same document.
- coverage_probability: the probability from 0 to 1 that this Policy indemnifies this position at all. This is the most valuable number you produce. Roughly 40% of positions are worth nothing.
- price_low, price_median, price_high: a realistic GROSS TOTAL band in EUR for the WHOLE Line Item at German market prices. Never a net amount, never a per-unit price. Make the band honest: wide when you are unsure, narrow when you are confident.
- clause: the Policy sentence that decides coverage, quoted verbatim.

Price the actual work at real German market rates, and get the LEVEL right. Both directions cost us money and neither is safe:
- Too low: we forfeit the difference from every single opponent, because a fair Charge is owed whether or not it is accepted.
- Too high: we collect nothing at all.

Anchors, since gross totals for a whole Line Item are easy to get wrong by an order of magnitude:
- Tradesman labour runs roughly 60-110 EUR per hour, so an hourly Line Item is that rate multiplied by the hours: 6.75 technician hours is several hundred EUR, not tens.
- Small parts, fittings, screws and consumables are genuinely cheap: tens of EUR for the whole position.
- Leak detection, leak pinpointing and moisture surveys settle around 430 EUR and reach 850. They are NOT a small call-out fee: seven in ten are above 400.
- Drying (room, cavity, insulation-layer) settles around 425 EUR; large-area or borehole drying reaches 1,400-2,600.
- Damage assessment, inspection and surveys settle around 490 EUR and reach 920.
- Disposal, strip-out and removal are cheaper, around 130 EUR, but a full strip-out reaches 1,000+.
- Equipment and machinery hire runs 50-700 EUR per position.
- Appliances, electronics, restoration and structural work reach the low thousands.

{distribution}
How to judge coverage:
- Judge the SERVICE BEING BILLED, not the object it concerns. Inspection, leak detection, drying and assessment are frequently indemnified even when the item investigated is not insured.
- Read cross-references to the end. An exclusion that finishes with wording like "the head of cost under 5.2.6 remains unaffected" is a pointer to cover, not an exclusion.
- A suspicious detail in the Damage Description is not an exclusion. Only a Policy clause is.
- quantity_missing=true means the invoice printed no amount and no unit, only dashes. Every such position in the settled Cases was worth exactly 0.
- An implausible quantity means the position is priced for the plausible quantity, not that it is excluded.

Return JSON only:
{{"items":[{{"line_item":1,"coverage_probability":0.9,"price_low":0.0,"price_median":0.0,"price_high":0.0,"clause":""}}]}}"""

#: The anchored framing: the model is told the settled distribution as a shape check.
PROMPT = _TEMPLATE.format(distribution=_DISTRIBUTION_HINT)

#: The same question with the distribution paragraph deleted. Deleting it measurably moves
#: the level -- on Games 1-15 and 17-19 the median `t_hat / t` on Line Items worth 400-1000
#: EUR goes from 0.93 to 1.10 and the share we under-price from 62% to 48% -- but on its own
#: it is *not* worth money: replayed against the real Field it lands at +14,260 against the
#: anchored prompt's +54,230, because the same shift also pushes items above `t`, where
#: income is zero. It earns its place only as the second ensemble member: the two framings
#: are wrong in different directions, and their disagreement is the only honest width signal
#: we have.
PROMPT_UNANCHORED = _TEMPLATE.format(distribution="")

#: One call per framing, fired concurrently, so the wall clock is the slower draw rather
#: than the sum. Two is the measured sweet spot: +28,625 over a single call across Games
#: 1-15 and 17-19. More members keep improving the median Game but each is another chance
#: to miss the 60 s window.
ENSEMBLE_PROMPTS = (PROMPT, PROMPT_UNANCHORED)

__all__ = ["ENSEMBLE_PROMPTS", "PROMPT", "PROMPT_UNANCHORED"]
