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
from src.pricing.engine import Evidence
from src.strategies.strategy2.constants import SETTLED_MEDIAN

logger = logging.getLogger(__name__)

#: Line Items naming a member of the "Valuables" class (Policy 4.2.2): jewellery, watches,
#: precious metals or stones. The only aggregate sub-limit class measured so far. Extend this
#: table if a second is confirmed -- 4.2.3 "means of payment" is named in the Policy text but
#: has never been observed to collide the way valuables has.
_AGGREGATE_CLASSES = {
    "valuables": re.compile(
        r"\b(watch(?:es)?|ring|necklace|bracelet|earring|jewell?ery|brooch|cufflink|"
        r"pendant|tiara|gem(?:stone)?|diamond|locket|anklet)\b",
        re.IGNORECASE,
    ),
}

#: Below this, `price_item`'s existing zero-collapse already zeroes the Limit
#: (`COVERAGE_FLOOR = 1 - LIMIT_QUANTILE = 2/3`). 0.30 sits under it with margin for the
#: model's own coverage read to vary without escaping the collapse.
_AGGREGATE_DISCOUNT_COVERAGE = 0.30

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


def aggregate_class_discount(
    case: CaseData, model_evidence: dict[int, Evidence]
) -> dict[int, Evidence]:
    """When two or more Line Items share an aggregate sub-limit, only the dearest is covered.

    Some Policies put a whole class of property under **one** sub-limit shared across every
    item of that class in the event, not a limit each. Policy 4.2.2, in every Case seen:
    valuables "form a single class of property... applied per item and, where more than one
    such item is affected, **in the aggregate per insured event across all items**".

    Game 44 is the only Case in the corpus that has shown the collision, and it shows it
    cleanly: watch `t >= 9,361` (paid), ring `t < 884` and necklace `t < 663` (both zero).
    The watch alone exhausted the shared pot. The model priced all three at an *identical*
    coverage probability of 0.925 -- it never noticed there was a pot to exhaust. A prompt
    fix was tried first and failed on both the Case it needed to fix and a single-item safety
    check; this is the deterministic replacement (ADR 0001: the model reads, the engine
    prices), and detection needs no model call.

    Only the **Limit** moves, and only downward: `price_item` derives the Charge without ever
    reading `coverage_probability`, so Issuer income on the discounted members is untouched --
    which is right, because an uncovered item is worth `t = 0` and a rejected Charge on it
    costs nothing (README R6c). Worth +2,026.89 replayed over Game 44.

    Deliberately narrow. It fires only where a class has two or more matched members that
    *both* carry model evidence to compare; one matched member, or a member the model never
    priced, leaves the evidence untouched. No other Case in 44 has ever had two valuables
    items, so its measured downside across the corpus is exactly zero.
    """
    out = dict(model_evidence)
    for pattern in _AGGREGATE_CLASSES.values():
        members = [item for item in case.line_items if pattern.search(item.name or "")]
        if len(members) < 2:
            continue
        priced = [
            (item, model_evidence[item.index])
            for item in members
            if item.index in model_evidence
        ]
        if len(priced) < 2:
            continue
        winner = max(priced, key=lambda pair: pair[1].price_median)[0].index
        for item, evidence in priced:
            if item.index == winner:
                continue
            out[item.index] = Evidence(
                index=evidence.index,
                coverage_probability=min(
                    evidence.coverage_probability, _AGGREGATE_DISCOUNT_COVERAGE
                ),
                price_low=evidence.price_low,
                price_median=evidence.price_median,
                price_high=evidence.price_high,
            )
    return out


def local_evidence(case: CaseData) -> dict[int, Evidence]:
    """Channels A and B together, keyed by Line Item index. Never raises."""
    try:
        from src.evidence.memory import PriceMemory, load, lookup, policy_fingerprint
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
                # Prefer observations from Cases running this same Policy document. The
                # wording key cannot tell two sub-limit regimes apart; see
                # `_restrict_to_policy` in src/evidence/memory.py for the measurement.
                policy_hash=policy_fingerprint(getattr(case, "policy_text", "")),
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


__all__ = ["aggregate_class_discount", "local_evidence", "unit_of", "worthless_evidence"]
