"""Case-anchored recalibration: use the Line Items memory *knows* to correct the ones it doesn't.

**NOT WIRED IN. It improves the estimate and does not make money — both are measured, and the
gap between them is the point of this file.** The structure below is real and replicates; the
euro result does not survive a single Game being removed. Read `Why it does not ship` before
reaching for any of it.

The structure this exploits
---------------------------
Split the log residual `r = log(t / t_hat)` over the 30 Cases carrying four or more settled Line
Items, and **29 % of its variance is a Case-level shift** -- a single number per invoice, not per
item. The Case medians themselves have a standard deviation of 0.350, so a whole Case can run a
factor of 1.4 high or low together. Something about the invoice as a whole -- its region, its
trade, the severity of the loss, whichever adjuster wrote it -- moves every price on it at once,
and pricing each Line Item independently throws that away.

It is real, not a censoring artefact. Fitting the shift on half of each Case's items and applying
it to the **other half** cuts held-out RMSLE from 0.709 to 0.583, a 17.8 % reduction. A shift
that were noise, or an artefact of which brackets happen to be bounded, would not transfer to
items it was never fitted on.

Observing it before the Game settles
------------------------------------
The above uses the true `t`, which we obviously do not have at submission time. But we have
something almost as good on a third to two thirds of the invoice: **Price Memory**, whose hits
are measured at sigma 0.458 with a bias of +0.031 against the model channel's ~1.0. So the
Line Items memory can price become a ruler for the ones it cannot:

1. on every Line Item where memory hits, recover what the *model* alone said;
2. take the median of `log(memory / model)` across those -- the model's level error **on this
   invoice**;
3. apply it to the model's estimate on the Line Items memory missed.

Measured on exactly that protocol, with no true `t` used to fit anything, over the Line Items
memory missed:

    >= 2 memory hits in the Case   RMSLE 0.919 -> 0.815
    >= 3 memory hits in the Case   RMSLE 0.887 -> 0.756      (-14.7 %)
    >= 4 memory hits in the Case   RMSLE 0.904 -> 0.773

Why it does not ship
--------------------
Replayed against the real Field over the 73 Games with a logged estimate
(`scripts/experiments/case_anchor_backtest.py`), the arm totals **+92,241 weighted** — and that
number is worthless:

    total                            +92,241
    without Game 62 alone            -19,248
    without the top three Games      -36,139
    Games improved / worsened          17 / 18
    median Game                             0
    folds positive                        2/4     (odd -9,672, Games 63-100 -11,968)

**One Game carries the entire result.** Shrinking the correction toward zero does not rescue it —
at 0.25x and 0.5x the total is outright *negative* (-3,358 and -5,264) with more Games worsened
than improved — and applying it to the Charge alone is no better. Six variants, none robust.

The disconnect is exactly the one CLAUDE.md warns about: RMSLE weights a EUR 10 Line Item like a
EUR 7,000 one and the payoff table does not. The arithmetic of why it is too small to detect:
the correction touches only the Line Items memory misses, about a third of an invoice, in 46 of
73 Games, and it moves them from 0.887 to 0.756 — still far above the sigma ~0.57 where net
crosses zero. Priced off the sigma curve that is worth roughly fifty thousand, which is inside
the noise this repository measures at +/-26,622 per Game.

**So the lesson is about where the bottleneck is, not about this correction.** Fixing the model's
level on the third of items memory cannot reach is not the lever. Getting memory to *reach* them
is: full recall at memory's measured sigma 0.458 is worth around +171,000 against what we
actually scored, against this correction's undetectable ~50,000.

Why this is not the fuzzy-matching idea again
---------------------------------------------
`memory.core_key` records that looser *matching* was measured and made sigma worse -- 0.43 to
0.72 at a Jaccard threshold of 0.7. That result stands and this does not contradict it: nothing
here matches anything. Memory's recall is untouched, every hit is still an exact or core-key hit,
and no wording is ever compared to any other. What changes is what we do with the hits we
already have -- they are used twice, once to price their own Line Item and once as evidence
about the invoice they sit on.

The limits, stated plainly
--------------------------
The log-error result is measured on **41 held-out Line Items** at the shipped threshold: a small
sample, drawn from bounded brackets and therefore censored, with the direction consistent across
thresholds rather than decisively estimated at any one of them. It replicates; it is also not
enough to move money.

Kept rather than deleted because this is the most natural idea available given the data, the
next person will have it, and the whole cycle — measure the structure, confirm it transfers,
build the estimator, find it does not pay — costs a day. `MIN_HITS` and `MAX_SHIFT` are the
values that measured best; neither rescues the euro result.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Iterable, Mapping

#: Fewest memory hits in a Case before its shift is trusted. Two works and three measures best;
#: three is shipped because the estimator is a median and a median of two is an average.
MIN_HITS = 3

#: The correction is clamped to this many log units either way -- a factor of e^0.7 ~ 2.0. A
#: median over three ratios can be wild, and no measured Case shift approaches this bound
#: (their standard deviation is 0.350), so the clamp only ever fires on noise.
MAX_SHIFT = 0.7


@dataclass(frozen=True)
class CaseShift:
    """The model's measured level error on one invoice."""

    shift: float
    #: How many memory hits it was measured from. Below `MIN_HITS` the shift is zero.
    hits: int
    #: True when `MAX_SHIFT` bound the estimate -- worth logging, it means the hits disagreed.
    clamped: bool = False

    @property
    def applies(self) -> bool:
        return self.hits >= MIN_HITS and self.shift != 0.0

    def apply(self, model_estimate: float) -> float:
        """The model's estimate with this invoice's level error taken out."""
        if model_estimate <= 0 or not self.applies:
            return model_estimate
        return model_estimate * math.exp(self.shift)


def recover_model_estimate(blended: float, memory: float, memory_share: float) -> float | None:
    """Undo `blend.combine` to get back what the model alone said.

    `combine` is an inverse-variance blend in log space,

        log(blend) = w * log(memory) + (1 - w) * log(model)

    so the model's own reading is recoverable exactly whenever `w < 1`. Returns `None` on
    anything that cannot be inverted rather than a number that would quietly be wrong.
    """
    if blended <= 0 or memory <= 0 or not 0.0 <= memory_share < 1.0:
        return None
    log_model = (math.log(blended) - memory_share * math.log(memory)) / (1.0 - memory_share)
    if not math.isfinite(log_model) or abs(log_model) > 30:
        return None
    return math.exp(log_model)


def measure(
    observations: Iterable[Mapping[str, float]], *, memory_share: float
) -> CaseShift:
    """The Case shift from the Line Items memory priced.

    Each observation needs `memory` (the anchor) and `blended` (what `combine` produced). The
    model's own estimate is recovered from the pair, and the shift is the median of
    `log(memory / model)` -- how far the model ran from the ruler, on this invoice.

    A median, not a mean: one Line Item where the model is out by an order of magnitude is
    exactly the case this has to survive, and it is common enough that a mean is unusable.
    """
    ratios: list[float] = []
    for row in observations:
        memory = float(row.get("memory") or 0.0)
        blended = float(row.get("blended") or 0.0)
        model = recover_model_estimate(blended, memory, memory_share)
        if model is None or model <= 0:
            continue
        ratios.append(math.log(memory / model))
    if len(ratios) < MIN_HITS:
        return CaseShift(0.0, len(ratios))
    raw = statistics.median(ratios)
    shift = max(-MAX_SHIFT, min(MAX_SHIFT, raw))
    return CaseShift(shift, len(ratios), clamped=shift != raw)


__all__ = ["CaseShift", "MAX_SHIFT", "MIN_HITS", "measure", "recover_model_estimate"]
