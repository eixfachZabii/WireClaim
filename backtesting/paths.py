"""Filesystem locations and schema versions for backtesting artifacts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CASES = ROOT / "[PUBLIC] EHL Cases" / "cases"
RAW_TRANSACTION_CACHE = ROOT / "var" / "transactions"
STATE = ROOT / "var" / "backtesting"
DATASETS = STATE / "datasets"
RUNS = STATE / "runs"
CURRENT_DATASET = DATASETS / "current.json"

DATASET_SCHEMA_VERSION = 1
RUN_SCHEMA_VERSION = 1
SPEC_SCHEMA_VERSION = 1
