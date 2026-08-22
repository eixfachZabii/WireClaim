from __future__ import annotations

from src.data.models import CaseData, ItemPrice, Proposal

STANDARD_CHARGE = 100.0
STANDARD_LIMIT = 75.0


def standard_values(case: CaseData) -> Proposal:
    return Proposal(
        source="standard",
        prices=tuple(
            ItemPrice(
                index=line_item.index,
                charge_price=STANDARD_CHARGE * max(line_item.quantity, 1.0),
                acceptance_limit=STANDARD_LIMIT * max(line_item.quantity, 1.0),
                source="standard",
            )
            for line_item in case.line_items
        ),
    )


async def llm_values(case: CaseData) -> Proposal | None:
    return None
