from __future__ import annotations

from src.data.models import CaseData, Proposal
from src.services.t_calc import estimate_fair_values


async def propose(case: CaseData) -> Proposal | None:
    await estimate_fair_values(case, strategy_name="strategy_1")
    return None
