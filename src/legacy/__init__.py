"""The previous generation of whole-Case estimators: `strategy1` and `strategy3`.

Both still run -- `strategy_router.py` still starts them as a free ensemble and
disagreement signal against Strategy 2 -- but neither is fitted to reconstructed Fair
Values, and Strategy 2 outranks both by priority (`src/strategies/__init__.py`,
`STRATEGY_PRIORITIES`) so their output never reaches a Submission on its own. See
`docs/ARCHITECTURE.md`, "Legacy and known weaknesses", for what is still entangled
before either can be deleted outright: Strategy 2 still imports `build_input_content`
from `strategy1.strategy` at request time.
"""
