"""Strategy 2 — three channels, one posterior per Line Item, deterministic prices.

This module is the orchestration only. The pieces live next to it:

| module         | job                                                              |
| -------------- | ---------------------------------------------------------------- |
| `constants.py` | every tuned number, with the measurement behind it               |
| `prompts.py`   | what we ask the model, and the framings that failed              |
| `channels.py`  | Channel A (dash quantity ⇒ worthless) and B (Price Memory)       |
| `model.py`     | Channel C: the call and the parser                               |
| `blend.py`     | merging ensemble draws, and merging channels                     |
| `strategy.py`  | this file: gather evidence, price it, always answer              |

The division of labour that matters is ADR 0001: **the model reads, the engine prices.**
The model returns a coverage probability and a gross-total price band; `src/pricing.py`
turns that into a Charge and a Limit. No model output is ever submitted directly.

## The two failure modes this is built around

**Charging above the Fair Value.** Income is `a` whenever `a <= t`, and it is collected from
*every* opponent, because a wrongfully rejected fair Charge is still owed. One euro above
`t` and acceptance collapses to 7-17%, so expected income falls from `1.00 t` to about
`0.20 t`. That cliff is why both numbers sit below the estimate.

**Going silent.** Game 23 submitted a Limit of 35 on every Line Item — `STANDARD_LIMIT`, not
anything this engine produces — because Channel C returned nothing, Case 23 had no dash
items and no Price Memory hits, and `build_proposal` therefore had no evidence and returned
`None`. Strategy 1's Proposal stood, we rejected 25 fair Charges (one as low as 36.00 on an
item worth at least 150) and paid 5,548 in penalties.

So the invariant now is: **Strategy 2 prices every Line Item of every Case, always.** When
no channel has anything to say, it falls back to the fitted no-information constants rather
than abstaining, because abstaining hands the Submission to a worse track without saying so.

## The price level is deliberately uncorrected, and that is a measurement

The estimator looks badly miscalibrated: bucketed by the *true* Fair Value, median
`t_hat / t` is 6.01 under 50 EUR and 1.17 over 1,000. Every attempt to correct it has been
scored in euros against the real Field over Games 1-24 and every one lost
(`scripts/experiments/level_fit.py` and its six siblings hold the tables):

| candidate correction, all in the evidence layer          | euros over Games 1-24    |
| -------------------------------------------------------- | ------------------------ |
| `t_hat' = exp(0.889) * t_hat**0.849`, the euro-weighted fit | **-54,713** in-sample |
| the best cell of that whole family, held out three ways   | -14,104 / 0 / -183,048   |
| per-trade multipliers fitted on one half of the Games     | -43,184 held out         |
| price anchors rewritten from the recovered Fair Values    | **-104,515** (48 calls)  |
| a sigma floor at the estimator's measured error of 1.29   | -247,443                 |
| `min` of the ensemble draws instead of the log mean       | -56,435                  |
| `MODEL_SIGMA_PRIOR` at the measured 1.30 instead of 0.6   | -8,106                   |

Two things to take from that before touching the level again.

**The diagnosis inverts with what you condition on.** Bucketed by `t_hat` instead of by `t`,
the same items read median `t_hat / t` of 0.46 under 50 EUR and 1.95 over 1,000 -- we are too
*low* on cheap calls, not too high. Both tables are regression artefacts of their own
conditioning variable, they contradict each other, and only the `t_hat` one can be applied at
submission time. A correction fitted against the first table is fitted backwards.

**The Charge and the Limit want opposite corrections and share one median.** That same fit
applied to the Limit alone is worth +2,776 and applied to the Charge alone -57,489. Nothing
in the evidence layer can separate them, because both numbers come from one median, so what
little there is to win belongs on the Limit side of `src/pricing.py` -- and it is worth
thousands, not the six figures the by-true-`t` table appears to promise.

What would pay is not a level shift at all: moving each median to *its own* true `t`, holding
the band and the coverage fixed, is worth six figures. That is item accuracy, and it comes
from better evidence -- not from any monotone function of the number we already have.
"""

from __future__ import annotations

import asyncio
import logging

from src.data.models import CaseData, ItemPrice, Proposal
from src.pricing import Evidence, price_item
from src.services.strategies.fast_path import STANDARD_CHARGE, STANDARD_LIMIT
from src.services.strategies.strategy2.blend import blend, combine
from src.services.strategies.strategy2.channels import local_evidence
from src.services.strategies.strategy2.constants import (
    LLM_TIMEOUT_SECONDS,
    STRATEGY_NAME,
)
from src.services.strategies.strategy2.model import request_evidence
from src.services.strategies.strategy2.prompts import ENSEMBLE_PROMPTS
from src.timing import log_timing, start_timer

logger = logging.getLogger(__name__)

#: Leave this much of the window for the final PUT after the last draw returns.
_SUBMISSION_RESERVE_SECONDS = 2.0


def _uninformed_price(index: int) -> ItemPrice:
    """What to submit for a Line Item nothing could price.

    `STANDARD_CHARGE` and `STANDARD_LIMIT` are the fitted answers to "we know nothing":
    the Charge maximises `a * P(t >= a)` over the settled Fair Value distribution, and the
    Limit minimises avoidable cost over every Charge whose side of `t` is known. They are
    poor — no constant can beat a real estimate — but they are measured, and they are
    enormously better than the `(0, 0)` default this track exists to prevent.
    """
    return ItemPrice(
        index=index,
        charge_price=STANDARD_CHARGE,
        acceptance_limit=STANDARD_LIMIT,
        source=STRATEGY_NAME,
    )


def build_proposal(
    case: CaseData,
    model_evidence: dict[int, Evidence],
    memory_evidence: dict[int, Evidence],
) -> Proposal | None:
    """Price every Line Item in the Case. Pure function, no I/O.

    Returns `None` only for a Case with no Line Items at all, which is not a thing that
    happens — every other path yields a number for every index.
    """
    prices: list[ItemPrice] = []
    for line_item in case.line_items:
        evidence = combine(
            model_evidence.get(line_item.index), memory_evidence.get(line_item.index)
        )
        if evidence is None:
            prices.append(_uninformed_price(line_item.index))
            continue
        price = price_item(
            evidence,
            confirmed_uncovered=getattr(line_item, "quantity_missing", False),
        )
        prices.append(
            ItemPrice(
                index=line_item.index,
                charge_price=price.charge,
                acceptance_limit=price.limit,
                source=STRATEGY_NAME,
            )
        )
    return Proposal(source=STRATEGY_NAME, prices=tuple(prices)) if prices else None


def _draw_timeout(deadline: float | None) -> float:
    if deadline is None:
        return LLM_TIMEOUT_SECONDS
    remaining = deadline - asyncio.get_running_loop().time() - _SUBMISSION_RESERVE_SECONDS
    return max(min(LLM_TIMEOUT_SECONDS, remaining), 1.0)


async def propose(case: CaseData, deadline: float | None = None) -> Proposal | None:
    started_at = start_timer()
    memory_evidence = local_evidence(case)
    timeout = _draw_timeout(deadline)

    async def draw(prompt: str) -> dict[int, Evidence]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(request_evidence, case, timeout, prompt),
                timeout=timeout + _SUBMISSION_RESERVE_SECONDS,
            )
        except Exception as error:
            # Never fatal, on either member. One framing surviving is most of the ensemble,
            # and the local channels plus the fitted constants still price the whole Case.
            logger.warning(
                "Strategy 2 draw unavailable for Game %s: %s", case.game_id, error
            )
            return {}

    # Concurrent, so the wall clock is the slower draw rather than the sum of both.
    draws = list(await asyncio.gather(*(draw(prompt) for prompt in ENSEMBLE_PROMPTS)))
    model_evidence = blend(draws)
    proposal = build_proposal(case, model_evidence, memory_evidence)
    log_timing(
        logger,
        STRATEGY_NAME,
        started_at,
        game=case.game_id,
        model_draws=sum(1 for result in draws if result),
        model_items=len(model_evidence),
        memory_items=len(memory_evidence),
        priced=0 if proposal is None else len(proposal.prices),
    )
    return proposal


__all__ = ["build_proposal", "propose"]
