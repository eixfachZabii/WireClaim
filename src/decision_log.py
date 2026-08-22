"""Record *why* we submitted each number, so a settled Game can teach us something.

Without this, a post-mortem can only see what the field saw: our Charge and a bracket on
our Limit. That is enough to say we lost money and not enough to say which stage was wrong,
and the two questions have different answers. In Games 21-24 the submitted Limit was 35 on
every Line Item — `STANDARD_LIMIT`, not anything the pricing engine emits — and it took an
hour of inference to establish that Strategy 2 had not landed at all. A log line would have
said so instantly.

So each run writes one file per Game holding, per Line Item, the evidence that went in and
the price that came out:

    var/decisions/game_026.json

`scripts/learn_from_game.py` joins it against the reconstructed Fair Value once the Game
settles, which turns "we lost 5,548" into "the coverage probability on item 3 was 0.25 and
the item was worth at least 150".

Two rules, because this runs inside a 60-second window:

* **It must never raise.** A logging failure that costs a Submission is a catastrophe; a
  missing log costs one Game's worth of learning.
* **It must never block.** Writes are small, local and synchronous, and happen after the
  Proposal is built rather than before it is published.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DECISIONS_DIR = Path("var/decisions")

#: Bumped when the shape changes, so an analyser can refuse a file it cannot read rather
#: than silently mis-attribute an old run.
SCHEMA_VERSION = 1


@dataclass
class ItemDecision:
    """Everything that determined one Line Item's two numbers."""

    index: int
    name: str = ""
    quantity: float = 1.0
    quantity_missing: bool = False

    # Which channels spoke. This is the field that would have caught Games 21-24 at once.
    channels: tuple[str, ...] = ()

    # The evidence the engine actually priced, after blending.
    coverage_probability: float | None = None
    price_low: float | None = None
    price_median: float | None = None
    price_high: float | None = None
    sigma: float | None = None

    # What we submitted, and by which rule.
    charge: float = 0.0
    limit: float = 0.0
    rule: str = "priced"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GameDecisions:
    game_id: int
    strategy: str
    schema: int = SCHEMA_VERSION
    recorded_at: float = field(default_factory=time.time)
    model_draws: int = 0
    model_items: int = 0
    memory_items: int = 0
    items: list[ItemDecision] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "game_id": self.game_id,
            "strategy": self.strategy,
            "recorded_at": self.recorded_at,
            "model_draws": self.model_draws,
            "model_items": self.model_items,
            "memory_items": self.memory_items,
            "items": [item.to_dict() for item in self.items],
        }


def path_for(game_id: int) -> Path:
    return DECISIONS_DIR / f"game_{game_id:03d}.json"


def record(decisions: GameDecisions) -> None:
    """Write the decision log. Swallows every error on purpose — see the module docstring."""
    try:
        DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
        path_for(decisions.game_id).write_text(
            json.dumps(decisions.to_dict(), indent=2, sort_keys=True)
        )
    except Exception as error:  # pragma: no cover - must never break a Game
        logger.warning("Could not write the decision log for Game %s: %s", decisions.game_id, error)


def load(game_id: int) -> dict[str, Any] | None:
    """Read a decision log back, or None if it is absent or unreadable."""
    try:
        payload = json.loads(path_for(game_id).read_text())
    except (OSError, ValueError):
        return None
    if payload.get("schema") != SCHEMA_VERSION:
        logger.warning(
            "Decision log for Game %s has schema %s, expected %s — ignoring.",
            game_id,
            payload.get("schema"),
            SCHEMA_VERSION,
        )
        return None
    return payload


__all__ = [
    "DECISIONS_DIR",
    "SCHEMA_VERSION",
    "GameDecisions",
    "ItemDecision",
    "load",
    "path_for",
    "record",
]
