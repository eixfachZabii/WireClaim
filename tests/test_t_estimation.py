"""
t-estimation checks against the shipped test case (case_00: stolen mountain bike).

- Sanitization tests run offline.
- The estimator test calls the LLM API and is skipped when no API key
  (AZURE_OPENAI_API_KEY / OPENAI_API_KEY / OPENAI_KEY) is configured. The case
  description states the bike was worth 420 EUR and the policy covers market
  value, so the estimated t should be close to 420 and the item must be
  classified as covered.
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


def test_sanitize_forces_uncovered_to_zero() -> None:
    estimate = _sanitize(
        {
            "covered": False,
            "t_estimate": 250.0,
            "t_low": 200.0,
            "t_high": 300.0,
            "confidence": 0.9,
            "reasoning": "not covered",
        }
    )
    assert estimate.t_estimate == 0.0
    assert estimate.t_low == 0.0
    assert estimate.t_high == 0.0


def test_sanitize_clamps_estimate_into_interval() -> None:
    estimate = _sanitize(
        {
            "covered": True,
            "t_estimate": 900.0,
            "t_low": 380.0,
            "t_high": 430.0,
            "confidence": 1.7,
            "reasoning": "anchored at market value",
        }
    )
    assert estimate.t_estimate == 430.0
    assert estimate.confidence == 1.0


@pytest.mark.skipif(not HAS_API_KEY, reason="LLM API key not configured")
def test_estimate_case00() -> None:
    estimate = estimate_t(
        {"index": 1, "description": "New Bike", "quantity": 1, "unit": "unit"},
        policy_path=CASE_00_DIR / "policy.txt",
        description_path=CASE_00_DIR / "description.txt",
    )

    assert estimate.covered, f"case_00 bike should be covered: {estimate.reasoning}"
    # The description anchors the bike's market value at 420 EUR.
    assert 300 <= estimate.t_estimate <= 450, (
        f"t={estimate.t_estimate}: {estimate.reasoning}"
    )
    assert estimate.t_low <= estimate.t_estimate <= estimate.t_high
