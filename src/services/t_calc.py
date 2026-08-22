from __future__ import annotations

from src.data.models import CaseData, FairValueEstimates


async def estimate_fair_values(
    case: CaseData,
    strategy_name: str,
) -> FairValueEstimates | None:
    return None
