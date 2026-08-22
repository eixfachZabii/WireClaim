# 1. The model reads, the engine prices

Date: 2026-08-22
Status: Accepted

## Context

Every Line Item requires us to submit two numbers, a Charge and a Limit. Those
numbers _are_ the score — there is no downstream human, no review step, and no
narrative layer between what we compute and what the tournament pays us on.

The obvious build is one prompt: hand a model the policy, the damage description
and the invoice line, and ask for a fair price. It is a two-hour build and it
would work, in the sense of producing numbers.

We have been here before. SampleRepo's ADR 0021 retired exactly this shape:
the portfolio-health verdict came straight out of a model's free JSON, so
"nothing computes it, nothing tests it, and two regenerates over identical data
may disagree." That was a _word_ on a card. Here it is the number we are paid on,
a hundred times, unattended, through the night.

Three further pressures point the same way:

**The pricing rules are not intuitions, they are arithmetic.** R5b puts the
optimal Charge at ≈ 0.7 × the median Estimate — _below_ the median, because
charging at the median forfeits the claim half the time. R6 puts the Limit in the
bottom third. R6b shrinks the Estimate toward the category median by
`τ²/(τ² + σ²)`. No language model produces these by reasoning about them, and
asking it to apply them is strictly worse than computing them.

**What we need is a distribution, not a number.** R4b shows the quantity that
actually determines our score is the _width_ of the posterior, not its centre —
`Q₁ᐟ₃` is only safe if the interval is calibrated. A model asked for "a fair
price" returns a point. A model asked for "a price and a confidence interval"
returns a point and a fabricated interval.

**Coverage is worth more than pricing.** `t = 0` for uncovered items, so the
coverage gate dominates every pricing refinement — and coverage is genuine
reading comprehension against a policy document, which is precisely what a model
is good at.

## Decision

Agents read. The engine prices.

The ADK agent team emits **structured evidence only** — a coverage verdict with
the policy clause quoted verbatim, a relatedness verdict, extracted quantity and
unit and trade category, and a price _band with named anchors_ (trade, hourly
rate range, time per unit, material range). No agent emits a Charge, a Limit, or
a Fair Value.

A deterministic pricing engine consumes that evidence, builds a log-normal
posterior over Fair Value (median _and_ width, from the band), applies shrinkage
(R6b), and derives the Charge and Limit by the quantile rules (R5b, R6) with the
acceptance rate gated per R5c.

## Consequences

**Reproducible.** Identical evidence yields an identical Submission, and that is
assertable in a test. Given the Price Memory this also means a Case we have seen
prices the same way twice.

**Debuggable at 04:00.** When a Submission looks wrong, the evidence and the
arithmetic are separately inspectable. A single mega-prompt is not.

**Improvable without touching prompts.** R9 calibration adjusts the engine's
shrinkage and interval width from settled Games. Under the mega-prompt shape,
calibration would mean prompt-fiddling with no way to verify the effect.

**The band is now the model's job, and it is a hard one.** We have moved the
difficulty rather than removed it: a model that fabricates a confident narrow
band poisons the posterior just as surely as one that fabricates a price. R4b's
coverage check against realised Fair Value brackets is the defence, and it is
load-bearing.

**More moving parts under a 60-second budget.** Four agents plus a join plus an
engine is more to go wrong than one call. The Fast Path (a heuristic Submission
fired early, overwritten later) exists partly to pay for this.

**Retrieved prices must not launder into verdicts.** The Price Memory feeds the
agents as context, which creates a path for a remembered price to come back as
if it were freshly reasoned evidence. The evidence contract must keep retrieved
anchors labelled as retrieved.
