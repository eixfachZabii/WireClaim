"""Channels A and B: everything we know before spending a token.

**Channel A, deterministic and exact.** An invoice position printed with dashes instead of
an amount and a unit is worth nothing: 20 of 20 such Line Items across the settled Games
have `t = 0`, against a 33% base rate for ordinary items. That is the single most reliable
signal in the Case and it costs nothing to read.

**Channel B, Price Memory.** Settled Fair Values keyed on Line Item wording. It reaches 22%
of items at a leave-one-out log error of 0.43, so it is an *anchor that narrows a band*,
never an answer on its own.

Channel B supplies **price only, never coverage**. 6 of 15 repeated wordings flip between
`t = 0` and `t > 0`: "vehicle costs" is worth nothing in Cases 1, 2, 3, 4 and 14 and 34-94
in Cases 5, 8, 9, 11 and 13. Case 22's kitchen air-conditioning unit is worth under 246
while Case 7's identically worded unit was under 81 and its living-room twin 1,233-1,756.
Coverage is a fact about *this* Policy and is always decided from the Case at hand.
"""

from __future__ import annotations

import logging
import re

from src.data.models import CaseData
from src.domain.pricing.engine import Evidence
from src.services.strategies.strategy2.constants import SETTLED_MEDIAN

logger = logging.getLogger(__name__)

#: The parser folds the invoice unit into the Line Item name as a trailing "(12 m)".
_UNIT_IN_NAME = re.compile(
    r"\(\s*[\d.,]+\s+(?P<unit>pcs|hrs?|m2|m²|m|kg|days?|units?|flat rate)\s*\)\s*$",
    re.IGNORECASE,
)

#: Coverage a memory hit reports: deliberately neutral, so the model decides. See the
#: module docstring for why memory must never carry a coverage verdict.
_MEMORY_COVERAGE = 0.9


def unit_of(name: str) -> str | None:
    """Recover the invoice unit from a Line Item name.

    Price Memory stores an hourly or per-metre position **per unit** and multiplies by the
    quantity on lookup; that one rule took its error from 0.66 to 0.43. Without the unit it
    returns a gross total instead, which underprices every labour and area line by the
    quantity — "Remove skirting boards (12 m)" came out at 17.52 against a true Fair Value
    near 122.
    """
    match = _UNIT_IN_NAME.search(name)
    return match.group("unit") if match else None


def worthless_evidence(index: int) -> Evidence:
    """Channel A's verdict: the item is worth nothing, but still price it.

    Coverage 0 collapses the Limit to zero in `price_item`, which is the point. The band is
    kept plausible rather than zero because an uncovered item has `t = 0`, so a rejected
    Charge costs us nothing and charging is a free option (README R6c) — in Game 3, where
    every item was uncovered, two teams charged ~100 and were paid while the field scored 0.
    """
    return Evidence(
        index=index,
        coverage_probability=0.0,
        price_low=SETTLED_MEDIAN * 0.5,
        price_median=SETTLED_MEDIAN,
        price_high=SETTLED_MEDIAN * 2,
    )


def local_evidence(case: CaseData) -> dict[int, Evidence]:
    """Channels A and B together, keyed by Line Item index. Never raises."""
    try:
        from src.domain.pricing.memory import PriceMemory, load, lookup
    except Exception:  # pragma: no cover - the memory channel is optional
        return {}

    # Pick up a store rebuilt since this process started. Every settled Game is ground truth
    # -- `invert_fair_values` recovers `t` exactly -- so `learn_watch` folds each Game into
    # Price Memory as it settles, and Channel B is the only channel measured more accurate
    # than the model. But `load()` caches process-wide, so a runner started before a rebuild
    # would answer all night from the store it read at boot. Once per Case, one small JSON
    # parse, off the model's critical path.
    #
    # The guard is the point. `PriceMemory.load` turns an unreadable or missing store into an
    # *empty* memory rather than raising, and a bare `load(refresh=True)` would then install
    # that emptiness process-wide -- trading a stale channel for no channel, silently, which
    # is precisely the failure the memory module's own docstring warns about. So read first
    # and only adopt a store that actually carries entries.
    try:
        if len(PriceMemory.load()):
            load(refresh=True)
    except Exception as error:  # pragma: no cover - never worth a Game
        logger.warning("Price Memory refresh failed, keeping the loaded store: %s", error)

    found: dict[int, Evidence] = {}
    for line_item in case.line_items:
        if getattr(line_item, "quantity_missing", False):
            found[line_item.index] = worthless_evidence(line_item.index)
            continue
        try:
            hit = lookup(
                line_item.name,
                unit=unit_of(line_item.name),
                quantity=max(line_item.quantity, 1.0),
            )
        except Exception as error:
            logger.warning(
                "Price Memory lookup failed for Line Item %s: %s", line_item.index, error
            )
            continue
        if hit is None:
            continue
        found[line_item.index] = Evidence(
            index=line_item.index,
            coverage_probability=_MEMORY_COVERAGE,
            price_low=hit.low,
            price_median=hit.median,
            price_high=hit.high,
        )
    return found


__all__ = ["local_evidence", "unit_of", "worthless_evidence"]
