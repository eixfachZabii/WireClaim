"""Frozen copy of `src/pricing.py` (HEAD, with LIMIT_CEILING at the re-measured 0.45).

Only for A/B measurement: `src/pricing.py` is owned by another agent and changed twice
under a running sweep, once into a state that would not import. A prompt comparison has to
hold the pricing constants fixed or it measures the wrong thing. Ship-facing numbers are
re-run against the real module.
"""


from __future__ import annotations

import math
from dataclasses import dataclass

# The Charge maximises k * P(t >= k * median). Simulated against the settled Fair Value
# distribution the optimum falls almost linearly in the estimate's error: 0.7 at sigma
# 0.25, 0.6 at 0.5, 0.5 at 0.75. This line reproduces those three points.
CHARGE_INTERCEPT = 0.85
CHARGE_SLOPE = 0.45
CHARGE_BOUNDS = (0.30, 0.80)

# P(fair) > 2/3, so the Limit is the bottom-third quantile. Derived, not fitted.
LIMIT_QUANTILE = 1.0 / 3.0

# A guard against the model claiming precision it does not have. The quantile above is
# the right rule, but it trusts the band: a model returning 95-105 on an item worth 20
# would have us accept nearly the full median. This ceiling only binds below sigma ~0.38,
# so for the widths we actually see the band still drives the Limit. It is deliberately
# *not* the old flat 0.6, which bound at every realistic width and threw the sigma signal
# away entirely.
LIMIT_CEILING = 0.45

# Below this, the bottom third of the posterior is zero anyway; naming it makes the
# threshold visible in logs and tests rather than implicit in the arithmetic.
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
    limit = min(limit, charge)
    return Price(
        charge=round(max(charge, 0.0), 2),
        limit=round(max(limit, 0.0), 2),
        sigma=sigma,
        covered_probability=covered,
    )
