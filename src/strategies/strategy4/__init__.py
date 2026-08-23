"""Tail-aware live comparison strategy.

Strategy 4 is deliberately lower priority than Strategy 2 and is executed only after
Strategy 2 has already won the router. Its Proposal is recorded for settlement replay but
cannot become the live Submission while the priority table remains unchanged.
"""

from src.strategies.strategy4.constants import STRATEGY_NAME
from src.strategies.strategy4.strategy import propose

__all__ = ["STRATEGY_NAME", "propose"]
