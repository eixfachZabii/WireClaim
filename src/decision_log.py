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

The same file also holds **every Proposal the router saw, not only the one that won**
(`proposals`, written by `StrategyRouter.results`). Three strategies price every Case
concurrently and only the winner's numbers were ever recorded, so there was no way to ask
whether `strategy1` or `strategy3` would have scored better on the Game we just played.
With the losing Proposals on disk, `scripts/replay_payoffs.py` answers that to the cent.

Out of scope, deliberately: the **`fast_path`** layer is emitted from `main.py` rather than
from the router, so it never passes through here and is *not* in the `proposals` section.
Do not read a missing `fast_path` entry as "the fast path stayed silent".

Two rules, because this runs inside a 60-second window:

* **It must never raise.** A logging failure that costs a Submission is a catastrophe; a
  missing log costs one Game's worth of learning.
* **It must never block.** Writes are small, local and synchronous, and happen after the
  Proposal is built rather than before it is published.

## Schema

    {"schema": 2, "game_id": 26, "strategy": "strategy2", "recorded_at": ...,
     "model_draws": 2, "model_items": 4, "memory_items": 1,
     "items":     [ {index, name, channels, coverage_probability, ..., charge, limit, rule} ],
     "proposals": {"strategy1": {"1": [78.9, 30.0]}, "strategy2": {...}, ...},
     "winner": "strategy2", "proposals_recorded_at": ...}

Schema 1 files have no `proposals`/`winner`; they stay readable, because 2 is a strict
superset and refusing them would throw away the Strategy 2 attribution we already have.
Anything the reader does not recognise — a future version, a missing version — is refused
outright rather than mis-attributed to a run it did not come from.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DECISIONS_DIR = Path("var/decisions")

#: Bumped when the shape changes, so an analyser can refuse a file it cannot read rather
#: than silently mis-attribute an old run. 2 added the `proposals`/`winner` sections.
SCHEMA_VERSION = 2

#: The oldest shape this reader still understands. 1 is a subset of 2 — same `items`, no
#: `proposals` — so a Game played before the router logged its losers keeps its Strategy 2
#: attribution instead of becoming unreadable.
MIN_SCHEMA_VERSION = 1

#: Two writers touch one file per Game (Strategy 2 for `items`, the router for `proposals`)
#: and they finish in either order, so a write merges rather than replaces. Merging is only
#: correct *within one run of one Game*: a file older than this is a previous run's, and
#: blending the two would be exactly the mis-attribution the schema version exists to stop.
#: A Game is 60 seconds; ten minutes covers a retry of the same Game and nothing else.
MERGE_WINDOW_SECONDS = 600.0


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


def _readable(payload: Any) -> bool:
    """True when this blob claims a schema this module actually understands."""
    if not isinstance(payload, dict):
        return False
    schema = payload.get("schema")
    return isinstance(schema, int) and MIN_SCHEMA_VERSION <= schema <= SCHEMA_VERSION


def _existing_for_merge(game_id: int) -> dict[str, Any]:
    """The part of an on-disk log a new write may build on. `{}` whenever in doubt.

    Refuses a file from a different Game, an unreadable schema, or an earlier run — see
    `MERGE_WINDOW_SECONDS`. Being wrong here means blending two runs, which is worse than
    losing one section, so every ambiguous case returns nothing.
    """
    try:
        payload = json.loads(path_for(game_id).read_text())
    except (OSError, ValueError):
        return {}
    if not _readable(payload) or payload.get("game_id") != game_id:
        return {}
    stamps = [
        value
        for key in ("recorded_at", "proposals_recorded_at")
        if isinstance(value := payload.get(key), (int, float))
    ]
    if not stamps or time.time() - max(stamps) > MERGE_WINDOW_SECONDS:
        return {}
    return payload


def _write_merged(game_id: int, patch: dict[str, Any]) -> None:
    """Merge `patch` into this Game's log and write it. Never raises; see the docstring."""
    try:
        payload = _existing_for_merge(game_id)
        merged = dict(payload.get("proposals") or {})
        merged.update(patch.pop("proposals", {}) or {})
        payload.update(patch)
        if merged:
            payload["proposals"] = merged
        payload["game_id"] = game_id
        payload["schema"] = SCHEMA_VERSION
        DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
        path_for(game_id).write_text(json.dumps(payload, indent=2, sort_keys=True))
    except Exception as error:  # pragma: no cover - must never break a Game
        logger.warning("Could not write the decision log for Game %s: %s", game_id, error)


def record(decisions: GameDecisions) -> None:
    """Write the decision log. Swallows every error on purpose — see the module docstring."""
    _write_merged(decisions.game_id, decisions.to_dict())


def record_proposals(
    game_id: int,
    proposals: Mapping[str, Mapping[int, tuple[float, float]]],
    winner: str | None = None,
) -> None:
    """Record every Proposal the router saw, plus which source is currently winning.

    `proposals` maps a source (`"strategy1"`, ...) to `{line item index: (charge, limit)}`.
    An empty mapping for a source is meaningful and kept: it says that strategy answered
    with nothing, which is not the same as never having run. `fast_path` is emitted outside
    the router and therefore never appears here.

    Called from inside the 60-second window, so it swallows everything and merges rather
    than replaces — Strategy 2's `items` section is written by the other writer and may land
    before or after this one.
    """
    try:
        section = {
            str(source): {
                str(index): [float(charge), float(limit)]
                for index, (charge, limit) in (items or {}).items()
            }
            for source, items in proposals.items()
        }
    except Exception as error:  # pragma: no cover - must never break a Game
        logger.warning("Could not encode the Proposals for Game %s: %s", game_id, error)
        return
    patch: dict[str, Any] = {"proposals": section, "proposals_recorded_at": time.time()}
    if winner is not None:
        patch["winner"] = winner
    _write_merged(game_id, patch)


def load(game_id: int) -> dict[str, Any] | None:
    """Read a decision log back, or None if it is absent or unreadable.

    "Unreadable" includes a schema this module does not know: better no attribution than one
    silently taken from a differently-shaped run.
    """
    try:
        payload = json.loads(path_for(game_id).read_text())
    except (OSError, ValueError):
        return None
    if not _readable(payload):
        logger.warning(
            "Decision log for Game %s has schema %s, expected %s..%s — ignoring.",
            game_id,
            payload.get("schema") if isinstance(payload, dict) else None,
            MIN_SCHEMA_VERSION,
            SCHEMA_VERSION,
        )
        return None
    return payload


def proposals(payload: Mapping[str, Any] | None) -> dict[str, dict[int, tuple[float, float]]]:
    """The `proposals` section decoded into `{source: {index: (charge, limit)}}`.

    Empty for a schema 1 log, which predates the section — that is "not recorded", not
    "no strategy proposed anything". Malformed entries are dropped rather than raising,
    because a partial answer beats an analysis that cannot start.
    """
    out: dict[str, dict[int, tuple[float, float]]] = {}
    for source, items in ((payload or {}).get("proposals") or {}).items():
        priced: dict[int, tuple[float, float]] = {}
        for index, pair in (items or {}).items():
            try:
                charge, limit = pair
                priced[int(index)] = (float(charge), float(limit))
            except (TypeError, ValueError):
                continue
        out[str(source)] = priced
    return out


__all__ = [
    "DECISIONS_DIR",
    "MIN_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "GameDecisions",
    "ItemDecision",
    "load",
    "path_for",
    "proposals",
    "record",
    "record_proposals",
]
