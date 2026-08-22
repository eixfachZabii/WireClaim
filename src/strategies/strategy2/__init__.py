"""Strategy 2 — the track that prices the Case.

`propose` is the only thing the runner needs. The rest of the package is public so that
`scripts/` can measure the pieces in isolation, which is how every constant in it was
chosen:

    from src.strategies.strategy2 import channels, model, blend, prompts

See `strategy.py` for the module map and the two failure modes the design is built around.
"""

from src.strategies.strategy2 import blend, channels, constants, model, prompts
from src.strategies.strategy2.constants import STRATEGY_NAME
from src.strategies.strategy2.strategy import build_proposal, propose

__all__ = [
    "STRATEGY_NAME",
    "blend",
    "build_proposal",
    "channels",
    "constants",
    "model",
    "prompts",
    "propose",
]
