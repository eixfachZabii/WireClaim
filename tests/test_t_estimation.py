"""
t-estimation checks against the shipped test case (case_00: stolen mountain bike).

- Sanitization tests run offline.
- The estimator test calls the LLM API and is skipped when no API key
  (AZURE_OPENAI_API_KEY / OPENAI_API_KEY / OPENAI_KEY) is configured. The case
  description states the bike was worth 420 EUR and the policy covers market
  value, so the estimated t should be close to 420.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.t_estimation import _sanitize, estimate_t

CASE_00_DIR = (
    Path(__file__).resolve().parent.parent / "[PUBLIC] EHL Cases" / "cases" / "case_00"
)

HAS_API_KEY = bool(
    os.environ.get("AZURE_OPENAI_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or os.environ.get("OPENAI_KEY")
)


def test_sanitize_computes_total_from_unit_price_and_quantity() -> None:
    estimate = _sanitize(
        {
            "unit_price": 80.0,
            "quantity": 5.0,
            "t_low": 300.0,
            "t_high": 500.0,
            "confidence": 0.9,
            "flags": [],
            "reasoning": "5 hours at 80 EUR/h",
        }
    )
    assert estimate.t_estimate == 400.0


def test_sanitize_clamps_total_into_interval_and_keeps_flags() -> None:
    estimate = _sanitize(
        {
            "unit_price": 900.0,
            "quantity": 1.0,
            "t_low": 380.0,
            "t_high": 430.0,
            "confidence": 1.7,
            "flags": ["upgrade", "not_a_real_flag"],
            "reasoning": "anchored at market value",
        }
    )
    assert estimate.t_estimate == 430.0
    assert estimate.confidence == 1.0
    assert estimate.flags == ("upgrade",)


@pytest.mark.skipif(not HAS_API_KEY, reason="LLM API key not configured")
def test_estimate_case00() -> None:
    estimate = estimate_t(
        {"index": 1, "description": "New Bike", "quantity": 1, "unit": "unit"},
        policy_path=CASE_00_DIR / "policy.txt",
        description_path=CASE_00_DIR / "description.txt",
    )

    # The description anchors the bike's market value at 420 EUR.
    assert 300 <= estimate.t_estimate <= 450, (
        f"t={estimate.t_estimate}: {estimate.reasoning}"
    )
    assert estimate.t_low <= estimate.t_estimate <= estimate.t_high
