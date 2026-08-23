"""Measured constants for Strategy 5's coherent Fair-Value estimate."""

from __future__ import annotations

STRATEGY_NAME = "strategy5"

# A missing model/memory estimate is not evidence that t=0. Strategy 2's flat fallback is
# (300, 35), which violates Strategy 5's geometry. In no-model, past-only replays the first
# invoice position behaves as the primary capital-loss row, while later positions behave as
# parts/labour. Games 43-61 independently select about 8,625 and exactly 275; 8,500 is used
# for the primary row because it has the stronger identified lower bound on Games 62-67.
PRIMARY_UNINFORMED_FAIR_VALUE = 8_500.0
UNINFORMED_FAIR_VALUE = 275.0

# Strategy 2's median has magnitude-dependent error. Coarse tiers are used instead of a
# fitted curve so every branch remains inspectable and has enough historical support.
LOW_VALUE_THRESHOLD = 100.0
LOW_VALUE_FACTOR = 0.75
MID_VALUE_THRESHOLD = 500.0
MID_VALUE_FACTOR = 0.50
FAIR_VALUE_FACTOR = 0.70

# Strategy 2 already treats large estimates as a separate tail: losing all income by sitting
# one euro above t is close to free on this bucket, while undercalling a genuinely large loss
# is extremely expensive. Under the stricter a=b geometry, the historical calibration moves
# that breakpoint to 3,000 and selects 1.35. The deliberately coarse tier is retained while
# the later slices contain no estimates in this bucket; finer subdivisions would be overfit.
BIG_ITEM_THRESHOLD = 3_000.0
BIG_ITEM_FACTOR = 1.35

__all__ = [
    "BIG_ITEM_FACTOR",
    "BIG_ITEM_THRESHOLD",
    "FAIR_VALUE_FACTOR",
    "LOW_VALUE_FACTOR",
    "LOW_VALUE_THRESHOLD",
    "MID_VALUE_FACTOR",
    "MID_VALUE_THRESHOLD",
    "PRIMARY_UNINFORMED_FAIR_VALUE",
    "STRATEGY_NAME",
    "UNINFORMED_FAIR_VALUE",
]
