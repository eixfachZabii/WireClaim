"""Comparative retrieval estimation: the model chooses an anchor, the engine does the arithmetic.

The hypothesis
--------------
Our model channel prices a Line Item in euros from the invoice wording and reaches a log error
near **1.0**. H28 measured what that costs and what it would take to fix: on the Line Items Price
Memory misses, an estimator must reach **sigma < 0.60** to be worth anything and about **0.458**
to be worth +118,864 weighted. So the model is being asked the wrong question.

"What is this worth in euros?" is an absolute judgement with no reference point. "Which of these
eight settled Line Items is this most like, and by what multiple?" is a *relative* one against
grounded prices -- and the anchors are not guesses, they are Fair Values recovered exactly from
settled Games. The model supplies a comparison; the engine supplies the level. That is ADR 0001's
division of labour applied to the one number it was never applied to.

Why this is not the falsified fuzzy-matching idea
-------------------------------------------------
`memory.core_key` records that looser *string* matching made sigma worse (0.43 -> 0.72), and
`scripts/experiments/retrieval_ceiling.py` reproduces it: picking the single most lexically
similar entry scores **1.348**, worse than the model channel it would replace. Lexical similarity
is used here only to *shortlist*, never to decide. Inside that same shortlist of eight an oracle
reaches 0.358, so the shortlist usually contains something usable -- what lexical ranking cannot
do is tell which one, and that is precisely a judgement rather than a string operation.

The honest caveat on the shortlist: retrieval_ceiling's controls show those oracle figures are
inflated by candidate-set *size* (a random 30 beats the lexical top 8). The shortlist is a
plausible place to look, not a proven one.

What the model is never allowed to do
-------------------------------------
Emit a price. `Comparison` carries an anchor index, a ratio and a confidence; `estimate()` turns
those into euros. A model that returns a euro figure is doing the engine's job, and every time
this repository has let it, the number has been worse than an anchored one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Anchor:
    """One settled Line Item offered to the model as a reference point."""

    label: str
    #: The Fair Value recovered from settled Transactions, for this quantity. Not an estimate.
    price: float
    unit: str = ""
    quantity: float = 1.0

    def render(self, index: int) -> str:
        quantity = f"{self.quantity:g} {self.unit}".strip() or "1"
        return f"[{index}] {self.label} ({quantity}) — settled at EUR {self.price:,.2f}"


class Comparison(BaseModel):
    """What the model is allowed to say. No euros anywhere in this contract."""

    anchor: int = Field(description="1-based index of the closest economic analogue in the list")
    ratio: float = Field(
        description=(
            "How many times the chosen anchor's total price this item is worth, for the whole "
            "line and the stated quantity. 1.0 means the same. Must be > 0."
        )
    )
    confidence: float = Field(
        default=0.5, description="0..1, how comparable the chosen anchor really is"
    )
    reason: str = Field(default="", description="one short clause naming what makes it comparable")


class DirectPrice(BaseModel):
    """The control arm's contract: the *old* architecture, so the comparison is like for like."""

    price: float = Field(description="Total EUR for the whole line item, gross, all quantity")
    confidence: float = Field(default=0.5)


#: A ratio outside this range means the model rejected the shortlist rather than used it, and the
#: anchoring has bought nothing. Clamped rather than discarded -- the anchor still carries a level.
RATIO_BOUNDS = (0.02, 50.0)

INSTRUCTION = """\
You price line items on German insurance repair invoices.

You are given ONE line item to value and a numbered list of reference line items whose true
settled values are known exactly. Your job is comparison, not pricing.

Choose the reference that is the closest ECONOMIC analogue — same trade, same kind of work or
material, similar scale of effort — and state what multiple of that reference's total the target
line item is worth. Account for the quantities shown: both totals are for the whole line.

Rules:
- Never output a price in euros. Output an anchor index and a ratio.
- The ratio compares TOTALS, not unit rates.
- If nothing in the list is a good analogue, still choose the least bad one, set the ratio as
  best you can, and report a low confidence.
- Prefer a reference from the same trade over one that merely shares words.
"""

DIRECT_INSTRUCTION = """\
You price line items on German insurance repair invoices.

Given one line item, estimate its total gross value in EUR for the whole line and the stated
quantity. Be realistic for the German repair market. Output only the number and a confidence.
"""


def render_prompt(
    name: str, quantity: float, unit: str, anchors: Sequence[Anchor], context: str = ""
) -> str:
    """The comparison prompt. Anchors are numbered from 1 to match `Comparison.anchor`."""
    lines = [f"TARGET LINE ITEM: {name}", f"QUANTITY: {quantity:g} {unit}".rstrip()]
    if context:
        lines.append(f"CONTEXT: {context}")
    lines.append("")
    lines.append("REFERENCE LINE ITEMS WITH KNOWN SETTLED VALUES:")
    lines.extend(anchor.render(i) for i, anchor in enumerate(anchors, start=1))
    return "\n".join(lines)


def render_direct_prompt(name: str, quantity: float, unit: str, context: str = "") -> str:
    lines = [f"LINE ITEM: {name}", f"QUANTITY: {quantity:g} {unit}".rstrip()]
    if context:
        lines.append(f"CONTEXT: {context}")
    return "\n".join(lines)


def estimate(comparison: Comparison, anchors: Sequence[Anchor]) -> float | None:
    """Turn a comparison into euros. `None` when the model's answer cannot be used.

    The index is validated rather than trusted: a model that names anchor 11 out of eight has
    not made a judgement about anchor 11, and silently clamping to the last one would invent an
    anchor it never chose.
    """
    if not anchors:
        return None
    index = comparison.anchor
    if not 1 <= index <= len(anchors):
        return None
    ratio = comparison.ratio
    if not math.isfinite(ratio) or ratio <= 0:
        return None
    ratio = min(max(ratio, RATIO_BOUNDS[0]), RATIO_BOUNDS[1])
    price = anchors[index - 1].price * ratio
    return price if price > 0 and math.isfinite(price) else None


__all__ = [
    "Anchor",
    "Comparison",
    "DIRECT_INSTRUCTION",
    "DirectPrice",
    "INSTRUCTION",
    "RATIO_BOUNDS",
    "estimate",
    "render_direct_prompt",
    "render_prompt",
]
