"""Strategy 2 — three estimation channels, one posterior, deterministic prices.

Replaces Strategy 1. The shape follows `docs/brainstorm/sebi/strats/review/strategy2-plan.md`
and every constant behind it is measured against the reconstructed Fair Values of Games
1-14 (`scripts/invert_fair_values.py`).

Channel A, deterministic and free: an invoice position printed with dashes instead of an
amount and unit is worth nothing -- 20 of 20 such Line Items in the settled Games have
`t = 0`, against a 33% base rate. It also slices the Policy to its operative Parts, which
removes the blocking ~20 s LLM digest from the critical path.

Channel B, Price Memory: settled Fair Values keyed on Line Item wording. Reaches 22% of
items at sigma 0.43, so it is an anchor that narrows the band, never an answer on its own.
It supplies *price* only -- 6 of 15 repeated wordings flip between `t = 0` and `t > 0`, so
coverage is always decided from the Case at hand.

Channel C, the model: carries the remaining ~78%. It returns evidence only -- a coverage
probability and a gross-total price band with a quoted clause -- and never a Charge, a
Limit or a Fair Value (ADR 0001). `src/pricing.py` turns that into numbers.

Channel C is asked **twice, concurrently, in two framings** (`ENSEMBLE_PROMPTS`), and the
two readings are averaged in log space by `_blend`. This is the change that paid: replayed
against the real Field over Games 1-15 and 17-19 it is worth **+28,625** (51,612 -> 80,237,
Price Memory disabled), it wins 12 of the 17 Games where it moves the number at all, and it
holds up under the censoring sensitivity. Two mechanisms, in order of size:

  * The band stops lying. The width the model asserts has a median implied sigma of 0.375
    against a measured log error near 0.8, and it does not even correlate with the error.
    The *disagreement between framings* is a width we observed rather than one the model
    claimed, and `_blend` adds it in quadrature.
  * Averaging halves the estimator's variance, and variance is what the payoff table
    punishes: one euro above `t` earns nothing at all.

It also buys uptime for free -- one framing timing out now costs a draw, not the Channel.

What was tried and did **not** pay, so that nobody spends the quota again (all measured in
euros on the same 18 Games, `scripts/tail_replay.py`, never in log error):

  * Deleting the settled-distribution hint on its own: +14,260 against +54,230. It does fix
    the diagnosed bias -- the median `t_hat / t` on items worth 400-1000 EUR goes 0.93 ->
    1.10 -- but a level shift that also crosses `t` from below forfeits the whole item.
  * Asking for a per-unit rate and multiplying by the invoice quantity: -64,590. It made
    the expensive positions *cheaper* (median `t_hat / t` 0.88 and 0.78 in the top two
    buckets), which is the opposite of the intent.
  * Asking for an explicit magnitude class as a cross-check: -31,550.
  * The reason the first two look like coin flips rather than regressions: two draws of the
    *identical* prompt differ by 26,622 over these 18 Games, so nothing smaller than that
    is measurable from a single sample. Which is also why an ensemble is the right answer.

Two failure modes this is built to avoid, both of which have cost us five figures:
  * Returning nothing. The deterministic channel alone is a complete answer, so a model
    failure downgrades the numbers instead of forfeiting the Game.
  * Charging above `t`. Income is `a` whenever `a <= t`, collected from every opponent
    because a wrongful rejection still owes it, and collapses by ~80% above it. Our median
    `a/t` has been 1.06 where the leaders sit at 0.73-0.85.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from typing import Any

from src.api import get_llm_client, get_model_name, get_service_tier
from src.data.models import CaseData, ItemPrice, Proposal
from src.policy_slice import slice_policy
from src.pricing import Evidence, price_item
from src.timing import log_timing, start_timer

logger = logging.getLogger(__name__)
STRATEGY_NAME = "strategy2"
LLM_TIMEOUT_SECONDS = 55.0
SUBMISSION_RESERVE_SECONDS = 3.0

# Median Fair Value over the 148 settled Line Items with a bounded bracket. Handed to the
# model as a prior because our measured failure is charging *above* `t`.
SETTLED_MEDIAN = 59.0

# Assumed log error of the model's own band, used only to weight it against Price Memory.
# A guess, and the one number here that is not measured -- `scripts/backtest.py` replaces
# it as soon as we score a real run.
MODEL_SIGMA_PRIOR = 0.6

# Price Memory's measured leave-one-out log error.
MEMORY_SIGMA = 0.43

# A band is read as a ~90% interval, so this converts a sigma back into one.
BAND_Z = 1.645

_DISTRIBUTION_HINT = (
    "\nFor reference, the settled distribution of these positions is wide and skewed: a "
    f"quarter are under 20 EUR, the median is around {SETTLED_MEDIAN:.0f} EUR, and the top "
    "decile runs past 400 EUR to several thousand. Use it as a sanity check on the shape, "
    "never as an anchor for an individual position -- an expensive item priced like the "
    "median is the single most expensive mistake you can make here.\n"
)

_PROMPT_TEMPLATE = """Read this insurance Case and return evidence for every invoice Line Item.

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
- Equipment hire, drying, leak detection and disposal are typically 50-400 EUR per position.
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

PROMPT = _PROMPT_TEMPLATE.format(distribution=_DISTRIBUTION_HINT)

#: The same question with the distribution paragraph deleted. Deleting it measurably moves
#: the level: on Games 1-15 and 17-19 the median `t_hat / t` on Line Items worth 400-1000
#: EUR goes from 0.93 to 1.10 and the share we under-price from 62% to 48%. On its own it
#: is *not* worth money -- replayed against the real Field it lands at +14,260 against the
#: hinted prompt's +54,230, because the same shift also pushes some items above `t`, where
#: income is zero. It earns its place only as the second member of the ensemble below: the
#: two framings are wrong in different directions, and their disagreement is the only
#: honest width signal we have.
PROMPT_UNANCHORED = _PROMPT_TEMPLATE.format(distribution="")

#: One call per framing, fired concurrently. Two is the measured sweet spot on total net
#: (+28,517 over the single call) and more members keep improving the median Game, but each
#: one is another chance to miss the 60 s window.
ENSEMBLE_PROMPTS = (PROMPT, PROMPT_UNANCHORED)


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if number != number or number in (float("inf"), float("-inf")) else max(number, 0.0)


def _extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise ValueError("Strategy 2 model response did not contain JSON.")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Strategy 2 model response must be a JSON object.")
    return payload


_UNIT_IN_NAME = re.compile(r"\(\s*[\d.,]+\s+(?P<unit>pcs|hrs?|m2|m²|m|kg|days?|units?|flat rate)\s*\)\s*$", re.IGNORECASE)


def _unit_of(name: str) -> str | None:
    """Recover the invoice unit, which the parser folds into the name as "(12 m)".

    Price Memory stores an hourly or per-metre position **per unit** and multiplies by
    quantity on lookup -- that single rule took its error from 0.66 to 0.43. Without the
    unit it returns a gross total instead, which underprices every labour and area line
    by the quantity: "Remove skirting boards (12 m)" came out at 17.52 against a true
    Fair Value of ~122.
    """
    match = _UNIT_IN_NAME.search(name)
    return match.group("unit") if match else None


def _memory_evidence(case: CaseData) -> dict[int, Evidence]:
    """Channel A + B: what we know before spending a token."""
    try:
        from src.price_memory import lookup
    except Exception:  # pragma: no cover - memory is optional
        return {}
    found: dict[int, Evidence] = {}
    for line_item in case.line_items:
        if getattr(line_item, "quantity_missing", False):
            # Channel A. 20 of 20 in the settled Games were worth nothing.
            found[line_item.index] = Evidence(
                index=line_item.index,
                coverage_probability=0.0,
                price_low=SETTLED_MEDIAN * 0.5,
                price_median=SETTLED_MEDIAN,
                price_high=SETTLED_MEDIAN * 2,
            )
            continue
        try:
            hit = lookup(line_item.name, unit=_unit_of(line_item.name), quantity=max(line_item.quantity, 1.0))
        except Exception as error:
            logger.warning("Price Memory lookup failed for Line Item %s: %s", line_item.index, error)
            continue
        if hit is None:
            continue
        found[line_item.index] = Evidence(
            index=line_item.index,
            # Memory says nothing about coverage: repeated wordings flip between t = 0
            # and t > 0, so this stays neutral and the model decides.
            coverage_probability=0.9,
            price_low=hit.low,
            price_median=hit.median,
            price_high=hit.high,
        )
    return found


def _blend(draws: list[dict[int, Evidence]]) -> dict[int, Evidence]:
    """Average several independent readings of the same Case, in log space.

    Two things come out of this, and the second is the important one.

    *The median moves less.* Averaging `k` draws divides the estimator's variance by `k`,
    and variance is what costs us: a Charge one euro above `t` earns nothing at all, so a
    noisy estimate is punished far harder than a biased one.

    *The band finally means something.* `implied_sigma` currently reads the width the model
    asserts, which has a median of 0.375 against a measured error near 0.8 -- overconfident
    by more than a factor of two, and uncorrelated with the actual error. The spread
    *between* framings is a different quantity: it is disagreement we observed rather than
    confidence the model claimed, and adding it in quadrature widens exactly the items the
    two readings disagree about. `src/pricing.py` then does the rest, since a wider band
    lowers both the Charge multiplier and the Limit quantile.

    Measured on the cached evidence for Games 1-15 and 17-19, replayed against the real
    Field: one draw +51,712, two draws +80,229, and the median Game +1,258 -> +3,980. The
    ordering survives the censoring sensitivity (`tail_replay.inflate`, factor 2.0):
    +111,491 -> +129,602.
    """
    usable = [draw for draw in draws if draw]
    if not usable:
        return {}
    if len(usable) == 1:
        return usable[0]
    blended: dict[int, Evidence] = {}
    for index in set().union(*(set(draw) for draw in usable)):
        seen = [draw[index] for draw in usable if index in draw]
        priced = [item for item in seen if item.price_median > 0]
        if not priced:
            blended[index] = seen[0]
            continue
        logs = [math.log(item.price_median) for item in priced]
        mean_log = sum(logs) / len(logs)
        own = sum(_sigma_of(item) for item in priced) / len(priced)
        spread = math.sqrt(sum((value - mean_log) ** 2 for value in logs) / len(logs))
        sigma = math.sqrt(own**2 + spread**2)
        median = math.exp(mean_log)
        blended[index] = Evidence(
            index=index,
            # Coverage is a probability, so it averages on its own scale, over every draw
            # that spoke about the item -- including the ones that priced it at zero.
            coverage_probability=sum(item.coverage_probability for item in seen) / len(seen),
            price_low=median * math.exp(-BAND_Z * sigma),
            price_median=median,
            price_high=median * math.exp(BAND_Z * sigma),
        )
    return blended


def _sigma_of(evidence: Evidence) -> float:
    """The log spread the model asserted, or a wide default when it asserted nothing."""
    if evidence.price_low <= 0 or evidence.price_high <= evidence.price_low:
        return MODEL_SIGMA_PRIOR
    return math.log(evidence.price_high / evidence.price_low) / (2 * BAND_Z)


def _combine(model: Evidence | None, memory: Evidence | None) -> Evidence | None:
    """Inverse-variance blend of two independent estimates, in log space.

    Two estimates of the same quantity are worth more than either, and combining them
    *narrows* the band, which is the whole point: a narrower band raises both the Charge
    and the Limit toward the estimate.
    """
    if model is None:
        return memory
    if memory is None or memory.price_median <= 0 or model.price_median <= 0:
        return model
    # A confirmed-worthless item from Channel A must not be talked out of it by a price.
    if memory.coverage_probability == 0.0:
        return Evidence(
            index=memory.index,
            coverage_probability=0.0,
            price_low=model.price_low or memory.price_low,
            price_median=model.price_median or memory.price_median,
            price_high=model.price_high or memory.price_high,
        )
    weight_model = 1.0 / (MODEL_SIGMA_PRIOR**2)
    weight_memory = 1.0 / (MEMORY_SIGMA**2)
    median = math.exp(
        (weight_model * math.log(model.price_median) + weight_memory * math.log(memory.price_median))
        / (weight_model + weight_memory)
    )
    sigma = math.sqrt(1.0 / (weight_model + weight_memory))
    return Evidence(
        index=model.index,
        coverage_probability=model.coverage_probability,
        price_low=median * math.exp(-BAND_Z * sigma),
        price_median=median,
        price_high=median * math.exp(BAND_Z * sigma),
    )


#: Lower edge, in EUR, of each magnitude class the model may name. The class is a second,
#: coarser reading of the same Line Item, and a coarse reading is much harder to get wrong
#: by an order of magnitude than a number is -- so where the two disagree, the class pulls
#: the band up. It never pulls one down: the measured failure is the underpriced tail.
MAGNITUDE_FLOORS = {
    "trivial": 0.0,
    "tens": 20.0,
    "hundreds": 120.0,
    "low_thousands": 1000.0,
    "thousands": 1000.0,
}


def _apply_magnitude(
    low: float, median: float, high: float, magnitude: Any
) -> tuple[float, float, float]:
    """Widen a band upward when the model's own magnitude class outranks its number."""
    floor = MAGNITUDE_FLOORS.get(str(magnitude or "").strip().lower().replace(" ", "_"))
    if floor is None or median <= 0 or median >= floor:
        return low, median, high
    # Split the difference in log space rather than jumping to the class floor: the number
    # and the class are two readings of one quantity and neither is authoritative.
    median = math.sqrt(median * floor)
    return min(low, median), median, max(high, floor * 2.0)


def _band_of(item: dict[str, Any], quantity: float) -> tuple[float, float, float]:
    """The gross-total band for one Line Item, from a per-unit rate or given outright.

    Neither of the alternative schemas is in `ENSEMBLE_PROMPTS`, because both were measured
    and both lost money -- see the module docstring. The parser keeps them so the experiment
    is one flag away (`scripts/tail_prompts.py --variant rate|mag`) and so a model that
    volunteers a rate is not silently read as a gross total of a few tens of euros.
    """
    rates = [
        _number(item.get(key)) for key in ("unit_rate_low", "unit_rate_median", "unit_rate_high")
    ]
    if any(rate > 0 for rate in rates):
        low, median, high = sorted(rate * max(quantity, 1.0) for rate in rates)
    else:
        low, median, high = sorted(
            _number(item.get(key)) for key in ("price_low", "price_median", "price_high")
        )
    return _apply_magnitude(low, median, high, item.get("magnitude"))


def _request_evidence(
    case: CaseData, timeout: float = LLM_TIMEOUT_SECONDS, prompt: str | None = None
) -> dict[int, Evidence]:
    """Channel C. One call for the whole Case, so the model sees neighbouring items."""
    from src.services.strategies.strategy1.strategy import build_input_content

    sliced = CaseData(
        game_id=case.game_id,
        case_dir=case.case_dir,
        policy_text=slice_policy(case.policy_text),
        description_text=case.description_text,
        line_items=case.line_items,
        image_paths=case.image_paths,
    )
    content = build_input_content(sliced)
    content[-1] = {
        "type": "input_text",
        "text": f"{prompt or PROMPT}\n\n=== POLICY (operative parts) ===\n{sliced.policy_text}"
        f"\n\n=== DAMAGE DESCRIPTION ===\n{case.description_text}"
        f"\n\n=== LINE ITEMS ===\n{json.dumps([item.to_dict() for item in case.line_items], ensure_ascii=False)}",
    }
    response = get_llm_client().responses.create(
        model=get_model_name(),
        service_tier=get_service_tier(),
        timeout=timeout,
        input=[{"role": "user", "content": content}],
    )
    payload = _extract_json(str(response.output_text or ""))
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Strategy 2 model response did not contain an items list.")
    quantities = {line_item.index: line_item.quantity for line_item in case.line_items}
    found: dict[int, Evidence] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        index = int(_number(item.get("line_item")))
        if index <= 0:
            continue
        low, median, high = _band_of(item, quantities.get(index, 1.0))
        found[index] = Evidence(
            index=index,
            coverage_probability=min(_number(item.get("coverage_probability")), 1.0),
            price_low=low,
            price_median=median,
            price_high=high,
        )
    return found


def build_proposal(
    case: CaseData,
    model_evidence: dict[int, Evidence],
    memory_evidence: dict[int, Evidence],
) -> Proposal | None:
    """Price every Line Item we can say anything about. Pure function, no I/O."""
    prices: list[ItemPrice] = []
    for line_item in case.line_items:
        combined = _combine(model_evidence.get(line_item.index), memory_evidence.get(line_item.index))
        if combined is None:
            continue
        uncovered = getattr(line_item, "quantity_missing", False)
        price = price_item(combined, confirmed_uncovered=uncovered)
        prices.append(
            ItemPrice(
                index=line_item.index,
                charge_price=price.charge,
                acceptance_limit=price.limit,
                source=STRATEGY_NAME,
            )
        )
    return Proposal(source=STRATEGY_NAME, prices=tuple(prices)) if prices else None


async def propose(case: CaseData, deadline: float | None = None) -> Proposal | None:
    started_at = start_timer()
    memory_evidence = _memory_evidence(case)
    timeout = LLM_TIMEOUT_SECONDS
    if deadline is not None:
        timeout = max(
            min(
                LLM_TIMEOUT_SECONDS,
                deadline - asyncio.get_running_loop().time() - SUBMISSION_RESERVE_SECONDS,
            ),
            1.0,
        )

    async def draw(prompt: str) -> dict[int, Evidence]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_request_evidence, case, timeout, prompt), timeout=timeout + 2.0
            )
        except Exception as error:
            # Deliberately not fatal, on either member. The deterministic and memory
            # channels are a complete answer on their own, submitting nothing is the most
            # expensive thing we do, and one framing surviving is most of the ensemble.
            logger.warning(
                "Strategy 2 model evidence unavailable for Game %s: %s", case.game_id, error
            )
            return {}

    # Concurrent, so the wall clock is the slowest single call rather than their sum.
    draws = list(await asyncio.gather(*(draw(prompt) for prompt in ENSEMBLE_PROMPTS)))
    model_evidence = _blend(draws)
    proposal = build_proposal(case, model_evidence, memory_evidence)
    log_timing(
        logger,
        STRATEGY_NAME,
        started_at,
        game=case.game_id,
        model_draws=sum(1 for draw_result in draws if draw_result),
        model_items=len(model_evidence),
        memory_items=len(memory_evidence),
        priced=0 if proposal is None else len(proposal.prices),
    )
    return proposal
