from __future__ import annotations

from src.data.models import CaseData, FraudDecision


async def detect_fraud(case: CaseData) -> FraudDecision:
    return FraudDecision()
