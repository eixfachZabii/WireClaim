"""Narrow, auditable constants for the tail-aware live comparison."""

STRATEGY_NAME = "strategy4"

# A conflict needs a material disagreement, not ordinary estimator noise.
CONFLICT_RATIO = 3.0
TAIL_THRESHOLD = 1_000.0

# Two independent current-Case readings must both stay well above Price Memory and agree
# with one another before Strategy 4 changes Strategy 2's numbers.
CONFIRMATION_RATIO = 2.0
AGREEMENT_RATIO = 2.0

# Mixture weights from the isolated experiment. These are not promoted live constants:
# Strategy 4 remains comparison-only until settlement evidence supports them.
TAIL_PROBABILITY = 0.70
TRUSTED_TAIL_LIMIT_CEILING = 0.75

# The extra adjudication happens after Strategy 2. It must leave the same final PUT reserve
# and is skipped outright if fewer than this many seconds remain.
MIN_ADJUDICATION_SECONDS = 1.0

__all__ = [
    "AGREEMENT_RATIO",
    "CONFIRMATION_RATIO",
    "CONFLICT_RATIO",
    "MIN_ADJUDICATION_SECONDS",
    "STRATEGY_NAME",
    "TAIL_PROBABILITY",
    "TAIL_THRESHOLD",
    "TRUSTED_TAIL_LIMIT_CEILING",
]
