"""Strategy 5 — one coherent Fair-Value estimate over Strategy 2's evidence.

Strategy 2 remains the winning live strategy and remains solely responsible for reading the
Case, coverage analysis, Price Memory, model calls, and evidence blending.  Strategy 5 runs
after it and prices the exact combined evidence written to the decision log.  It therefore
adds no model request and contains no duplicate fraud or coverage detector.

The first version put ``a`` at one posterior quantile and ``b`` at another. That looked
probabilistically tidy and was economically wrong: Strategy 2's stated bands are not
calibrated, and a high ``b`` accepts precisely the opponent overcharges the Limit exists to
reject. The live invariant is now structural and simpler: estimate one ``t`` and submit
``a = b = t_hat``.

The estimate retains Strategy 2's measured ideas: shade below a noisy median, vary that
shade by magnitude, and treat the expensive tail separately. When Strategy 2 has no price
evidence at all, the primary invoice position gets a capital-loss prior and later positions
get a small-parts prior. Proven dash-quantity exclusions alone collapse to zero; Strategy
2's generic zero-Limit label is not an exclusion verdict.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from src.data.models import CaseData, ItemPrice, Proposal
from src.pricing.engine import Evidence
from src.runtime.decisions import load as load_decisions
from src.strategies.strategy2.constants import STRATEGY_NAME as BASELINE_STRATEGY
from src.strategies.strategy5.constants import (
    BIG_ITEM_FACTOR,
    BIG_ITEM_THRESHOLD,
    FAIR_VALUE_FACTOR,
    LOW_VALUE_FACTOR,
    LOW_VALUE_THRESHOLD,
    MID_VALUE_FACTOR,
    MID_VALUE_THRESHOLD,
    PRIMARY_UNINFORMED_FAIR_VALUE,
    STRATEGY_NAME,
    UNINFORMED_FAIR_VALUE,
)


def price_evidence(
    evidence: Evidence,
    *,
    confirmed_uncovered: bool = False,
    uninformed: bool = False,
    primary_uninformed: bool = False,
) -> tuple[float, float]:
    """Return one coherent ``t_hat`` as both ``(a, b)``.

    Coverage uncertainty does not scale the price of a covered loss. It decides whether an
    item is covered, while the median estimates its value conditional on coverage. Only the
    deterministic dash-quantity signal is strong enough to replace that estimate with zero.
    """
    if confirmed_uncovered:
        return 0.0, 0.0
    if uninformed:
        estimate = (
            PRIMARY_UNINFORMED_FAIR_VALUE
            if primary_uninformed
            else UNINFORMED_FAIR_VALUE
        )
        return estimate, estimate
    median = max(evidence.with_defaults().price_median, 0.0)
    if median < LOW_VALUE_THRESHOLD:
        factor = LOW_VALUE_FACTOR
    elif median < MID_VALUE_THRESHOLD:
        factor = MID_VALUE_FACTOR
    elif median < BIG_ITEM_THRESHOLD:
        factor = FAIR_VALUE_FACTOR
    else:
        factor = BIG_ITEM_FACTOR
    estimated_t = round(factor * median, 2)
    return estimated_t, estimated_t


def proposal_from_decisions(
    game_id: int,
    payload: Mapping[str, Any] | None,
    expected_indices: Iterable[int],
    *,
    baseline: Proposal | None = None,
) -> Proposal | None:
    """Reprice Strategy 2's recorded evidence without re-running any evidence channel."""
    expected = set(expected_indices)
    if not payload or payload.get("game_id") != game_id:
        return None
    if payload.get("strategy") != BASELINE_STRATEGY:
        return None

    raw_items = {
        int(raw["index"]): raw
        for raw in payload.get("items") or ()
        if isinstance(raw, Mapping) and raw.get("index") is not None
    }
    # Historical parser glitches occasionally recorded a phantom invoice row that the
    # Tournament API did not settle (Games 54 and 59).  Extra evidence is harmless because
    # it is never submitted; missing evidence is not, because inventing a value would make
    # the comparison cease to be Strategy 2 on identical inputs.
    if not expected.issubset(raw_items):
        return None
    if baseline is not None and not _matches_baseline(raw_items, baseline, expected):
        return None

    prices: list[ItemPrice] = []
    primary_index = min(expected) if expected else None
    for index in sorted(expected):
        raw = raw_items[index]
        evidence = _evidence_from_decision(index, raw)
        charge, limit = price_evidence(
            evidence,
            confirmed_uncovered=bool(raw.get("quantity_missing")),
            uninformed=raw.get("price_median") is None,
            primary_uninformed=index == primary_index,
        )
        prices.append(ItemPrice(index, charge, limit, STRATEGY_NAME))
    return Proposal(STRATEGY_NAME, tuple(prices))


async def propose(
    case: CaseData,
    deadline: float | None = None,
    *,
    baseline: Proposal | None = None,
) -> Proposal | None:
    """Build a live comparison after Strategy 2 has recorded its combined evidence."""
    del deadline  # no I/O or model work is required after the Strategy 2 log exists
    if baseline is None or baseline.source != BASELINE_STRATEGY or baseline.is_empty:
        return None
    return proposal_from_decisions(
        case.game_id,
        load_decisions(case.game_id),
        (item.index for item in case.line_items),
        baseline=baseline,
    )


def _evidence_from_decision(index: int, raw: Mapping[str, Any]) -> Evidence:
    def number(name: str, default: float) -> float:
        try:
            value = float(raw.get(name, default))
        except (TypeError, ValueError):
            return default
        return value if math.isfinite(value) else default

    # ``None`` evidence is Strategy 2's measured no-information path.  Evidence defaults
    # reproduce a prior band while preserving the item's recorded coverage when available.
    # Strategy 2 calls every zero-Limit result ``uncovered-free-option``. That includes a
    # merely uncertain model result whose coverage fell below the pricing floor; the label
    # is not proof that Fair Value is zero. Only the deterministic dash-quantity signal is
    # a confirmed exclusion in the recorded schema.
    return Evidence(
        index=index,
        coverage_probability=number("coverage_probability", 0.9),
        price_low=number("price_low", 0.0),
        price_median=number("price_median", 0.0),
        price_high=number("price_high", 0.0),
    )


def _matches_baseline(
    raw_items: Mapping[int, Mapping[str, Any]],
    baseline: Proposal,
    expected: set[int],
) -> bool:
    current = baseline.by_index()
    if set(current) != expected:
        return False
    try:
        return all(
            math.isclose(float(raw_items[index]["charge"]), current[index].charge_price, abs_tol=0.011)
            and math.isclose(float(raw_items[index]["limit"]), current[index].acceptance_limit, abs_tol=0.011)
            for index in expected
        )
    except (KeyError, TypeError, ValueError):
        return False


__all__ = ["price_evidence", "proposal_from_decisions", "propose"]
