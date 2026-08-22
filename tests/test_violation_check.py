"""
Violation-check tests against the shipped test case (case_00: stolen mountain bike).

- Sanitization tests run offline.
- The LLM tests are skipped when no API key is configured.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.violation_check import _sanitize, check_violation

CASE_00_DIR = (
    Path(__file__).resolve().parent.parent / "[PUBLIC] EHL Cases" / "cases" / "case_00"
)

HAS_API_KEY = bool(
    os.environ.get("AZURE_OPENAI_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or os.environ.get("OPENAI_KEY")
)


def test_sanitize_marks_unrelated_as_fraudulent() -> None:
    result = _sanitize(
        {
            "covered": True,
            "related": False,
            "confidence": 0.8,
            "reasoning": "not related to the damage",
        }
    )
    assert result.fraudulent


def test_sanitize_marks_covered_and_related_as_legitimate() -> None:
    result = _sanitize(
        {
            "covered": True,
            "related": True,
            "confidence": 1.4,
            "reasoning": "covered replacement",
        }
    )
    assert not result.fraudulent
    assert result.confidence == 1.0


@pytest.mark.skipif(not HAS_API_KEY, reason="LLM API key not configured")
def test_check_violation_case00() -> None:
    result = check_violation(
        {"index": 1, "description": "New Bike", "quantity": 1, "unit": "unit"},
        policy_path=CASE_00_DIR / "policy.txt",
        description_path=CASE_00_DIR / "description.txt",
    )

    assert result.covered, result.reasoning
    assert result.related, result.reasoning
    assert not result.fraudulent
