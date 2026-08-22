from __future__ import annotations

import logging

from src.data.models import CaseData, Proposal
from src.timing import log_timing, start_timer

logger = logging.getLogger(__name__)


async def estimate_fair_values(case: CaseData) -> None:
    return None


async def propose(case: CaseData, deadline: float | None = None) -> Proposal | None:
    started_at = start_timer()
    try:
        await estimate_fair_values(case)
        return None
    finally:
        log_timing(logger, "strategy2", started_at, game=case.game_id)
