from __future__ import annotations

from src.data.models import CaseData, Proposal
from src.services.strategies.strategy1.strategy import propose_with_model

STRATEGY_NAME = "strategy3"
LUNA_MODEL = "gpt-5.6-luna"


async def propose(case: CaseData, deadline: float | None = None) -> Proposal | None:
    if deadline is None:
        return await propose_with_model(case, model=LUNA_MODEL, source=STRATEGY_NAME)
    return await propose_with_model(case, model=LUNA_MODEL, source=STRATEGY_NAME, deadline=deadline)
