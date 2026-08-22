"""Turn evidence about a Line Item into a Charge and a Limit.

This is the only place in the codebase that decides a number we are scored on. The model
supplies evidence -- a price band and a coverage probability with a quoted clause -- and
this module supplies the arithmetic (ADR 0001: the model reads, the engine prices).

It exists partly to end a duplication: `CHARGE_FACTOR`, `LIMIT_QUANTILE` and the
spike-and-slab formula were copy-pasted into `fast_path.py` and `strategy1/strategy.py`,
and they decide the most expensive number in the pipeline.

## The two decisions, and why they are what they are

Both come out of the payoff table, measured against Games 1-14.

**The Charge.** Income is `a` whenever `a <= t`, and it is collected from *every* opponent,
because a wrongful rejection still owes the issuer `a`. Above `t` the only buyers are the
few teams with a loose Limit. Measured on our own settled Charges:

    a/t <= 1.0   -> paid by all 16 opponents  -> 1.00 x t
    a/t 1.0-1.3  -> 17% accept                -> 0.20 x t
    a/t 1.3-2.0  ->  7% accept                -> 0.15 x t

So an Overcharge forfeits ~80% of income and we never take one deliberately. The Charge
maximises `k * P(t >= k * t_hat)`, which lands at `k ~ 0.7` when the estimate has
lognormal error 0.25 and lower as the error grows.

**The Limit.** Accepting a Charge costs `a`. Rejecting it costs `1.5a` *only if it was
fair*, and nothing otherwise. So accepting is right exactly when

    a < 1.5a * P(fair)      i.e.      P(fair) > 2/3

which makes the Limit the **one-third quantile of the posterior over `t`** -- README R6's
"bottom third", derived rather than asserted.

Coverage uncertainty needs no separate branch: it is probability mass at zero. If an item
is only 50% likely to be covered, the bottom third of its posterior *is* zero, so the
Limit falls out at 0 on its own. That is the correct answer -- 40% of settled Line Items
have `t = 0`, and paying on one is a pure loss.

One empirical shading on top: the 2/3 rule prices an accepted Overcharge at `a`, but the
Cap allows `min(a, c)` with `c >= 4t`, so accepting is worse than the rule assumes. The
best multiplier measured against the real field is 0.5-0.7 of the median, so the Limit is
capped at `LIMIT_CEILING * median` as well.

## What the payoff table said when we finally asked it

Everything above was fitted against a simulation. `scripts/tune_pricing.py` re-measures it
in euros: cached model evidence -> `price_item` -> `scripts/replay_payoffs.replay`, which
reproduces all fourteen published nets to the cent. Games 1-14, 192 Line Items. Three
results, one of which contradicts the derivation above.

**The Charge line survived.** Synthesising an *unbiased* estimator of known precision
(`t_hat = t * exp(N(0, sigma))`, band drawn to match) and optimising the multiplier against
the real Field gives 0.70 at sigma 0.25, 0.65 at 0.35, 0.60 at 0.45, 0.50 at 0.60 and 0.45
at 0.75 -- a least-squares line of `0.829 - 0.519 * sigma` against the shipped
`0.85 - 0.45 * sigma`. That is inside the measurement noise, so the constants stay. The
optimum sits far below 1 at every precision, and the penalty above it is brutal (-103k at
`a = t_hat` against +150k at `0.6 t_hat`), so the "paid by every opponent below `t`"
argument is confirmed rather than merely asserted.

**The ceiling was nearly twice too generous.** See `LIMIT_CEILING`; the fix is worth about
+1,280 a Game, and it settles the standing argument about whether the Limit belongs at the
1/3 quantile or at `1.0 x t_hat`.

**The band is not calibrated, and that is the real problem.** `implied_sigma` on the
current model's evidence has median 0.375, but the estimator's actual RMSLE against the
recovered Fair Values is **0.80** -- overconfident by a factor of 2.1. Worse, the width
carries no signal: split the items by band width and the narrow third scores RMSLE 0.847
against the wide third's 0.733, i.e. slightly *backwards*. So `CHARGE_SLOPE` multiplies a
number that does not measure what it claims to. The line is right; its input is not.
Fixing the band is worth more than any constant in this file, and it belongs in the
evidence layer, not here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# The Charge maximises k * P(t >= k * median). Simulated against the settled Fair Value
# distribution the optimum falls almost linearly in the estimate's error: 0.7 at sigma
# 0.25, 0.6 at 0.5, 0.5 at 0.75. This line reproduces those three points.
#
# Re-measured in euros (`tune_pricing.py calibrate`, Games 1-14, unbiased estimator of the
# stated precision, replayed against the real Field, 5 replicas):
#
#     sigma  best a/median   this line   net at the optimum
#      0.25       0.70         0.7375              +223,134
#      0.35       0.65         0.6925              +182,852
#      0.45       0.60         0.6475              +149,496
#      0.60       0.50         0.5800               +93,772
#      0.75       0.45         0.5125               +60,200
#
# Least squares through the measured column is `0.829 - 0.519 * sigma`; the shipped line
# runs 0.04-0.06 above it, worth under 3% of net at every sigma and smaller than the spread
# between replicas. Left alone deliberately -- refitting it exactly to 0.83/0.52 was tried
# and *lost* money on both the real evidence (13,599 -> 4,397) and the unbiased simulation
# (145,169 -> 130,900), because a lower Charge also drags the Limit down through the
# `b <= a` clamp at the end of `price_item`. Two constants that look separable are not.
#
# Do NOT tune these against the real cached evidence. That surface is not a curve: the
# per-Game argmax scatters over 0.4-1.1 with no plateau (Game 10 rises monotonically to
# +49,980 at 1.1, Game 7 falls monotonically to -16,044) because the Field's Limits are
# clustered, so the total jumps whenever our Charge crosses a cluster. Any peak found there
# is a fact about sixteen specific opponents, not about pricing.
CHARGE_INTERCEPT = 0.85
CHARGE_SLOPE = 0.45
CHARGE_BOUNDS = (0.30, 0.80)

# P(fair) > 2/3, so the Limit is the bottom-third quantile. Derived, not fitted -- and the
# derivation is sound, but on the current evidence it is not what binds. Swept on its own
# against the real Field it is worth almost nothing: every value from 0.20 to 0.90 lands
# within +/-125 euros of the shipped 1/3 over fourteen Games, because `LIMIT_CEILING` sits
# below the quantile at every band width we actually see. Kept at the derived value -- a
# constant that does not bind should be the one the theory chose, not the one a flat sweep
# happened to land on.
LIMIT_QUANTILE = 1.0 / 3.0

# A guard against the model claiming precision it does not have. The quantile above is
# the right rule, but it trusts the band: a model returning 95-105 on an item worth 20
# would have us accept nearly the full median.
#
# This is the one constant the payoff table actually moved, and measuring it settles the
# standing question of whether the Limit belongs at the 1/3 quantile or nearer 1.0 x t_hat.
# Swept in euros over Games 1-14 with everything else at its shipped value:
#
#     ceiling   net (real evidence)   net (unbiased, sigma 0.45)
#       0.20             +31,909                      +103,373
#       0.30             +32,100                      +108,453
#       0.40             +32,393  <- argmax           +117,014
#       0.45             +31,514  <- shipped          +124,229
#       0.50             +26,993                      +129,423
#       0.60             +18,300                      +141,118
#       0.85             +13,599  <- was shipped      +145,169
#
# So the change is worth **+17,915 over fourteen Games, about +1,280 a Game**, and
# 0.20-0.45 is a genuine plateau (spread under 900 on 32,000) rather than a peak. Leave-one-
# out is unanimous on the direction: thirteen of fourteen folds trained on the other
# thirteen Games choose 0.20 and one chooses 0.45, for a held-out total of +26,581 against
# the shipped +13,599 -- an in-sample/held-out gap of 5,300 next to an 18,000 gain.
#
# The two answers are both right, of different estimators, and the difference is not bias,
# it is the *tail*:
#
#   * Given an unbiased lognormal estimator the best Limit really is ~1.0-1.15 x median, and
#     flat in sigma (1.05 at sigma 0.25, 1.05 at 0.45, 1.10 at 0.75). For that estimator
#     "1.0 x t_hat" is correct and this ceiling costs about 21,000 over fourteen Games.
#   * Ours is not that estimator. It is roughly median-unbiased (median t_hat/t = 0.97) but
#     it produces occasional catastrophic overprices at full confidence: Game 7 item 2,
#     median 2,200 against a true Fair Value of 40, coverage 0.98; Game 9 item 1, median
#     3,200 against t = 19. Those are 5-6 sigma in log space -- a lognormal does not
#     generate them. A Limit near the median accepts every opponent's Charge on such an item
#     and pays it, and the Cap has never bound (zero conflicts in 52,224 settled rows), so
#     that loss is unbounded, while a strict Limit only ever forfeits 1.5a on genuinely fair
#     Charges. Ten of fourteen Games prefer a Limit at or below 0.5 x median; the three that
#     prefer a loose one gain little.
#
# 0.45 rather than the 0.40 argmax on purpose: it is the last point of the real-evidence
# plateau and so the cheapest place to stand if somebody fixes the estimator's tail -- it
# recovers 7,200 euros of the unbiased case for 900 of the real one. When the tail is
# measured away, re-run `tune_pricing.py calibrate`; this constant should then rise toward
# 1.0, and that is a one-line change with a measurement behind it.
#
# ...and then the Field moved. Re-running the same sweep over every Case we have, the
# ordering **inverts between the old Games and the recent ones**:
#
#     sample                     ceiling 0.85    ceiling 0.45
#     Games 1-14                     +13,599         +31,514   <- the analysis above
#     Games 15-19                    +38,322         +23,210   <- the opposite
#     all 19                         +51,921         +54,724
#
# Games 17 and 18 alone account for the reversal (-8,285 and -5,681 at 0.45). Over the full
# set the two values differ by 2,802 on ~53,000, which is a coin flip, so this constant is
# not really a pricing fact at all -- it is a fact about how generous the Field currently
# is, and README R9 says a Field measurement does not survive a phase boundary.
#
# **Shipping 0.85, because we are paid on the Games that come next, not the ones already
# settled**, and the last five Games prefer it by about 3,000 each. Re-run
# `tune_pricing.py calibrate` on a recent window after any regime change -- the field is
# expected to go dark overnight and wake up recalibrated, and this number should be
# re-measured at both boundaries rather than inherited.
LIMIT_CEILING = 0.85

# Below this, the bottom third of the posterior is zero anyway; naming it makes the
# threshold visible in logs and tests rather than implicit in the arithmetic.
#
# Swept, and it is the flattest knob in the file: every threshold from 0.10 to 0.70 lands
# within 150 euros of every other over fourteen Games (0.00 costs 133, 0.75 and above cost
# 63). That is not indifference, it is the coverage signal being good enough that the
# threshold hardly matters -- at 1/3 the model calls only 7 of 116 covered items doubtful,
# against 23 of 76 uncovered ones called covered. Kept at the derived value, which sits in
# the middle of the measured plateau; there is no euro case for moving it.
COVERAGE_FLOOR = LIMIT_QUANTILE

# Median Fair Value over the 148 settled Line Items with a bounded bracket. Used only when
# there is no band at all -- it is a prior, not an estimate, and it is deliberately low
# because our historic failure was Charging *above* `t` (median a/t was 1.06).
FALLBACK_MEDIAN = 60.0


@dataclass(frozen=True)
class Evidence:
    """What the model is allowed to say about one Line Item.

    No Charge, no Limit, no Fair Value -- a band, a coverage probability, and a spread.
    """

    index: int
    coverage_probability: float = 0.9
    price_low: float = 0.0
    price_median: float = 0.0
    price_high: float = 0.0

    def with_defaults(self) -> Evidence:
        """Fill a missing or incoherent band from whatever is usable."""
        low, median, high = self.price_low, self.price_median, self.price_high
        known = [value for value in (low, median, high) if value > 0]
        if not known:
            low, median, high = FALLBACK_MEDIAN * 0.5, FALLBACK_MEDIAN, FALLBACK_MEDIAN * 2
        else:
            median = median if median > 0 else sorted(known)[len(known) // 2]
            low = low if low > 0 else median * 0.5
            high = high if high > 0 else median * 2
            low, high = min(low, median), max(high, median)
        return Evidence(
            index=self.index,
            coverage_probability=min(max(self.coverage_probability, 0.0), 1.0),
            price_low=low,
            price_median=median,
            price_high=high,
        )


@dataclass(frozen=True)
class Price:
    charge: float
    limit: float
    sigma: float
    covered_probability: float


def implied_sigma(low: float, median: float, high: float) -> float:
    """Lognormal spread implied by a band, treating it as a ~90% interval.

    A band is the only uncertainty signal the model gives us, and the spread is what sets
    both numbers: the wider the band, the further below the median the Charge and Limit
    have to sit.
    """
    if median <= 0 or high <= 0 or low <= 0 or high <= low:
        return 1.0
    # 90% of a lognormal spans +/- 1.645 sigma in log space.
    return min(math.log(high / low) / (2 * 1.645), 2.0)


def charge_factor(sigma: float) -> float:
    """How far below the estimate to Charge, given how much the estimate can be trusted.

    A Charge at or below `t` is paid by every opponent; one euro above it earns almost
    nothing. So the wider the band, the further under the median we have to aim.
    """
    low, high = CHARGE_BOUNDS
    return min(max(CHARGE_INTERCEPT - CHARGE_SLOPE * sigma, low), high)


def _lognormal_quantile(median: float, sigma: float, quantile: float) -> float:
    """Inverse CDF of a lognormal, via a rational approximation of the normal one."""
    if sigma <= 0:
        return median
    return median * math.exp(sigma * _normal_quantile(quantile))


def _normal_quantile(p: float) -> float:
    """Acklam's rational approximation; accurate to ~1e-9 and dependency-free."""
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    a = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
    b = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00)
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def price_item(evidence: Evidence, *, confirmed_uncovered: bool = False) -> Price:
    """The whole pricing decision for one Line Item.

    `confirmed_uncovered` is for a proven exclusion — a policy clause quoted verbatim.
    It zeroes the Limit but never the Charge: an uncovered item has `t = 0`, so the
    honest branch pays nothing and a rejected Overcharge costs nothing, which makes the
    Charge a free option (README R6c). Game 3 is the proof: every Line Item was
    uncovered, two teams Charged ~100 and were paid by 2 of 16, and the rest of the field
    scored zero.
    """
    filled = evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    covered = 0.0 if confirmed_uncovered else filled.coverage_probability

    # The Charge assumes the item is covered. That is deliberate and it is free: if the
    # item turns out to be worthless the Charge simply gets rejected at no cost, whereas
    # shading it down for doubt forfeits guaranteed income on everything that is covered.
    charge = charge_factor(sigma) * filled.price_median

    # The Limit reads the bottom third of the *whole* posterior, which carries mass
    # (1 - covered) at zero. Below P(covered) = 1/3 that quantile is zero outright.
    if covered <= COVERAGE_FLOOR:
        limit = 0.0
    else:
        # Strip the zero mass, then take the quantile that leaves 1/3 of the total below.
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        limit = min(
            _lognormal_quantile(filled.price_median, sigma, conditional),
            LIMIT_CEILING * filled.price_median,
        )

    # b < a always: the Limit is a lower quantile of the same posterior than the Charge.
    #
    # Measured, and it is not free. The Charge and the Limit answer different questions --
    # "what will the Field pay me" and "what am I willing to pay" -- and nothing in the
    # payoff table requires the second to sit below the first. Releasing this clamp is
    # worth +16,421 over Games 1-14 against an unbiased estimator at sigma 0.45 (149,496
    # against 133,075), and +14,000 to +18,000 at every sigma from 0.25 to 0.75, because
    # such an estimator wants `b ~ 1.0 x median` while `a ~ 0.6 x median`. Kept anyway:
    # with today's fat-tailed estimator the Limit is held at 0.45 x median and this clamp
    # almost never binds, so releasing it buys nothing now while removing a guard rail that
    # catches genuinely incoherent bands. Revisit together with `LIMIT_CEILING`, not before.
    limit = min(limit, charge)
    return Price(
        charge=round(max(charge, 0.0), 2),
        limit=round(max(limit, 0.0), 2),
        sigma=sigma,
        covered_probability=covered,
    )
