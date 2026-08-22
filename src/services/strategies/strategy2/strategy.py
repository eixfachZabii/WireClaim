from __future__ import annotations

from src.data.models import CaseData, Proposal


async def estimate_fair_values(case: CaseData) -> None:
    return None


async def propose(case: CaseData) -> Proposal | None:
    await estimate_fair_values(case)
    return None
