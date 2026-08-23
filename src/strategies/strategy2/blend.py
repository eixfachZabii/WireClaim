"""Combining several readings of the same Line Item into one piece of evidence.

Two different merges happen here and they answer different questions.

`blend` merges the **ensemble**: the same Case read twice in two framings. Averaging halves
the estimator's variance, and variance is what the payoff table punishes — a Charge one euro
above `t` earns nothing at all, so a noisy estimate is hurt far worse than a biased one.

More importantly it produces a width we can believe. `implied_sigma` in `src/pricing/engine.py`
reads the width the *model asserts*, which has a median of 0.375 against a measured log
error near 0.8, and which does not even correlate with the actual error — sorting Line Items
by asserted width puts the narrow third at a slightly *worse* error than the wide third. The
spread *between framings* is a different quantity: disagreement we observed rather than
confidence the model claimed. `blend` adds it in quadrature, so the band widens on exactly
the items the two readings disagree about, and `src/pricing/engine.py` then lowers both the Charge
multiplier and the Limit quantile for them.

Measured on the cached evidence for Games 1-15 and 17-19, replayed against the real Field:
one draw +51,712, two draws +80,229, median Game +1,258 → +3,980. The ordering survives the
censoring sensitivity (factor 2.0: +111,491 → +129,602).

`combine` merges the **channels**: the model's reading against a Price Memory anchor. These
are genuinely independent estimates of one quantity, so an inverse-variance weighting in log
space *narrows* the band, which raises both numbers toward the estimate.
"""

from __future__ import annotations

import math

from src.pricing.engine import Evidence
from src.strategies.strategy2.constants import (
    BAND_Z,
    MEMORY_SIGMA,
    MODEL_SIGMA_PRIOR,
)


def _band_from(median: float, sigma: float) -> tuple[float, float, float]:
    """A band whose implied sigma reads back as `sigma`."""
    return median * math.exp(-BAND_Z * sigma), median, median * math.exp(BAND_Z * sigma)


def sigma_of(evidence: Evidence) -> float:
    """The log spread the model asserted, or the prior when it asserted nothing usable."""
    if evidence.price_low <= 0 or evidence.price_high <= evidence.price_low:
        return MODEL_SIGMA_PRIOR
    return math.log(evidence.price_high / evidence.price_low) / (2 * BAND_Z)


def blend(draws: list[dict[int, Evidence]]) -> dict[int, Evidence]:
    """Average independent readings of a Case in log space, widening on disagreement."""
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
            # Every draw called it worthless. Keep that verdict rather than inventing a band.
            blended[index] = seen[0]
            continue
        logs = [math.log(item.price_median) for item in priced]
        mean_log = sum(logs) / len(logs)
        asserted = sum(sigma_of(item) for item in priced) / len(priced)
        observed = math.sqrt(sum((value - mean_log) ** 2 for value in logs) / len(logs))
        low, median, high = _band_from(
            math.exp(mean_log), math.sqrt(asserted**2 + observed**2)
        )
        blended[index] = Evidence(
            index=index,
            # Coverage is a probability, so it averages on its own scale — over every draw
            # that spoke about the item, including ones that priced it at zero.
            coverage_probability=sum(item.coverage_probability for item in seen) / len(seen),
            price_low=low,
            price_median=median,
            price_high=high,
        )
    return blended


def combine(model: Evidence | None, memory: Evidence | None) -> Evidence | None:
    """Inverse-variance blend of the model's reading and a Price Memory anchor."""
    if model is None:
        return memory
    if memory is None or memory.price_median <= 0:
        return model
    if model.price_median <= 0:
        # The model zeroes the band on items it judges uncovered — every one of the nine
        # zero-band Line Items in the logged Games came back with coverage <= 0.30. That
        # conflates "not covered" with "worth nothing", and discarding the anchor here
        # dropped the item through `Evidence.with_defaults` onto `FALLBACK_MEDIAN`, so
        # every such item was Charged the same 39.62 whatever it was worth. Game 31 item
        # 17 had an exact memory hit at 300 from Game 5 and a Fair Value of at least 315.
        #
        # `price_item` prices the Charge as if the item were covered on purpose: an
        # uncovered item has `t = 0`, so a rejected Charge costs nothing and charging is a
        # free option (README R6c). Keep the model's coverage verdict — the Limit still
        # collapses — and take the anchor's band. Replayed over the logged Games this is
        # +3,190, positive in all four Games it touches and neutral in the rest.
        return Evidence(
            index=model.index,
            coverage_probability=model.coverage_probability,
            price_low=memory.price_low,
            price_median=memory.price_median,
            price_high=memory.price_high,
        )
    if memory.coverage_probability == 0.0:
        # Channel A proved the item is worthless. A price must not talk it out of that:
        # keep coverage at zero so the Limit collapses, but take the better band.
        return Evidence(
            index=memory.index,
            coverage_probability=0.0,
            price_low=model.price_low or memory.price_low,
            price_median=model.price_median or memory.price_median,
            price_high=model.price_high or memory.price_high,
        )

    weight_model = 1.0 / (MODEL_SIGMA_PRIOR**2)
    weight_memory = 1.0 / (MEMORY_SIGMA**2)
    total = weight_model + weight_memory
    median = math.exp(
        (weight_model * math.log(model.price_median) + weight_memory * math.log(memory.price_median))
        / total
    )
    low, median, high = _band_from(median, math.sqrt(1.0 / total))
    return Evidence(
        index=model.index,
        # Coverage comes from the model alone; memory has no opinion worth having on it.
        coverage_probability=model.coverage_probability,
        price_low=low,
        price_median=median,
        price_high=high,
    )


__all__ = ["blend", "combine", "sigma_of"]
