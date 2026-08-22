"""Data models for WireClaim."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LineItem:
    """Represents a single line item on an invoice."""

    index: int
    name: str = ""
    quantity: float = 1.0
    unit_price: float = 0.0
    total_gross: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total_gross": self.total_gross,
        }


@dataclass(frozen=True)
class CaseData:
    """Holds all extracted files and metadata for a single Game."""

    game_id: int
    case_dir: Path
    policy_text: str = ""
    description_text: str = ""
    line_items: tuple[LineItem, ...] = field(default_factory=tuple)
    image_paths: tuple[Path, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ItemPrice:
    """Represents one Charge and Limit pair for a Line Item."""

    index: int
    charge_price: float
    acceptance_limit: float
    source: str = "standard"

    def with_limit(self, acceptance_limit: float) -> ItemPrice:
        return replace(self, acceptance_limit=acceptance_limit)

    def to_submission_dict(self) -> dict[str, float | int]:
        return {
            "index": self.index,
            "charge_price": float(self.charge_price),
            "acceptance_limit": float(self.acceptance_limit),
        }


@dataclass(frozen=True)
class Proposal:
    """A pricing candidate produced by one source."""

    source: str
    prices: tuple[ItemPrice, ...]

    @property
    def is_empty(self) -> bool:
        return not self.prices

    def by_index(self) -> dict[int, ItemPrice]:
        return {price.index: price for price in self.prices}


@dataclass(frozen=True)
class FraudDecision:
    """Identifies Line Items whose Limit must be locked to zero."""

    fraud_indices: frozenset[int] = field(default_factory=frozenset)


@dataclass(frozen=True)
class FairValueEstimate:
    """A strategy-local estimate of a Line Item Fair Value."""

    line_item_index: int
    median: float
    lower: float
    upper: float


@dataclass(frozen=True)
class FairValueEstimates:
    """All Fair Value estimates produced for one Case by one strategy."""

    values: tuple[FairValueEstimate, ...] = field(default_factory=tuple)
