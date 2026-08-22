import asyncio
import os
from pathlib import Path

import pytest

from src.data.models import CaseData, LineItem
from src.services.t_calc import _sanitize, estimate_fair_values

CASE_00_DIR = Path(__file__).resolve().parent.parent / "var" / "cases" / "case_00"

HAS_API_KEY = bool(
    os.environ.get("AZURE_OPENAI_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or os.environ.get("OPENAI_KEY")
)


def test_sanitize_computes_total_from_unit_price_and_quantity() -> None:
    estimate = _sanitize(
        1,
        {
            "unit_price": 80.0,
            "quantity": 5.0,
            "t_low": 300.0,
            "t_high": 500.0,
            "confidence": 0.9,
            "flags": [],
            "reasoning": "5 hours at 80 EUR/h",
        },
    )
    assert estimate.median == 400.0
    assert estimate.line_item_index == 1


def test_sanitize_clamps_total_into_interval() -> None:
    estimate = _sanitize(
        2,
        {
            "unit_price": 900.0,
            "quantity": 1.0,
            "t_low": 380.0,
            "t_high": 430.0,
            "confidence": 0.8,
            "flags": ["upgrade"],
            "reasoning": "anchored at market value",
        },
    )
    assert estimate.median == 430.0
    assert (estimate.lower, estimate.upper) == (380.0, 430.0)


@pytest.mark.skipif(not HAS_API_KEY, reason="LLM API key not configured")
@pytest.mark.skipif(not CASE_00_DIR.exists(), reason="case_00 not extracted")
def test_estimate_case00() -> None:
    case = CaseData(
        game_id=0,
        case_dir=CASE_00_DIR,
        policy_text=(CASE_00_DIR / "policy.txt").read_text(encoding="utf-8"),
        description_text=(CASE_00_DIR / "description.txt").read_text(encoding="utf-8"),
        line_items=(LineItem(index=1, name="New Bike", quantity=1.0),),
    )
    estimates = asyncio.run(estimate_fair_values(case, strategy_name="test"))
    assert estimates is not None
    estimate = estimates.values[0]
    assert 300.0 <= estimate.median <= 450.0
