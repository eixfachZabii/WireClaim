from __future__ import annotations

from src.data.models import CaseData, ItemPrice, Proposal
from src.services.t_calc import estimate_fair_values

CHARGE_FRACTION = 0.95
LIMIT_FACTOR = 1.2


async def propose(case: CaseData) -> Proposal | None:
    estimates = await estimate_fair_values(case, strategy_name="strategy_1")
    if estimates is None or not estimates.values:
        return None
    return Proposal(
        source="strategy_1",
        prices=tuple(
            ItemPrice(
                index=estimate.line_item_index,
                charge_price=round(CHARGE_FRACTION * estimate.median, 2),
                acceptance_limit=round(
                    max(LIMIT_FACTOR * estimate.upper, estimate.median), 2
                ),
                source="strategy_1",
            )
            for estimate in estimates.values
        ),
    )
