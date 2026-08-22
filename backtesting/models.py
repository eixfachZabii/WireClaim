"""Canonical, lossless models for reconstructed historical behavior and scores."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class Interval:
    """A non-negative interval. ``high=None`` means unbounded above."""

    low: float = 0.0
    high: float | None = None
    high_inclusive: bool = False
    low_strict: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.low) or self.low < 0:
            raise ValueError(f"invalid interval lower bound {self.low!r}")
        if self.high is not None:
            if not math.isfinite(self.high) or self.high < self.low:
                raise ValueError(f"invalid interval [{self.low}, {self.high}]")
            if self.high == self.low and not self.high_inclusive:
                raise ValueError("a point interval must include its upper endpoint")

    @classmethod
    def point(cls, value: float) -> Interval:
        return cls(float(value), float(value), high_inclusive=True)

    @property
    def bounded(self) -> bool:
        return self.high is not None

    @property
    def exact(self) -> bool:
        return self.high == self.low and self.high_inclusive

    @property
    def width(self) -> float | None:
        return None if self.high is None else self.high - self.low

    def representative(self) -> float:
        if self.high is None:
            return self.low
        if self.exact:
            return self.low
        return (self.low + self.high) / 2.0

    def definitely_at_least(self, value: float) -> bool:
        return self.low >= value if not self.low_strict else self.low >= value

    def definitely_below(self, value: float) -> bool:
        if self.high is None:
            return False
        return self.high < value if self.high_inclusive else self.high <= value

    def to_dict(self) -> dict[str, Any]:
        return {
            "low": self.low,
            "high": self.high,
            "bounded": self.bounded,
            "high_inclusive": self.high_inclusive,
            "low_strict": self.low_strict,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Interval:
        return cls(
            low=float(value["low"]),
            high=None if value.get("high") is None else float(value["high"]),
            high_inclusive=bool(value.get("high_inclusive", False)),
            low_strict=bool(value.get("low_strict", False)),
        )


@dataclass(frozen=True)
class Transaction:
    game_id: int
    line_item_index: int
    issuer: str
    reviewer: str
    accepted: bool
    amount: float
    source_teams: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[int, int, str, str]:
        return (self.game_id, self.line_item_index, self.issuer, self.reviewer)


@dataclass(frozen=True)
class ChargeEstimate:
    interval: Interval
    status: str
    accepted: int = 0
    rejected_positive: int = 0
    rejected_zero: int = 0
    observed_amounts: tuple[float, ...] = ()

    @property
    def exact(self) -> bool:
        return self.interval.exact


@dataclass(frozen=True)
class LimitEstimate:
    interval: Interval
    lower_witness: str | None = None
    upper_witness: str | None = None
    accepted_witnesses: int = 0
    rejected_witnesses: int = 0


@dataclass(frozen=True)
class FairValueEstimate:
    interval: Interval
    lower_witnesses: tuple[str, ...] = ()
    upper_witnesses: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapEstimate:
    observed_paid_floor: float
    empirical_floor: float = 2000.0
    status: str = "fitted"
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class TeamDecision:
    team: str
    charge: ChargeEstimate
    limit: LimitEstimate


@dataclass(frozen=True)
class HistoricalItem:
    index: int
    fair_value: FairValueEstimate
    cap: CapEstimate
    decisions: Mapping[str, TeamDecision]
    name: str = ""
    quantity: float = 1.0
    quantity_missing: bool = False


@dataclass(frozen=True)
class HistoricalGame:
    game_id: int
    teams: tuple[str, ...]
    items: Mapping[int, HistoricalItem]
    transactions: tuple[Transaction, ...]
    authoritative_nets: Mapping[str, float]
    leaderboard_nets: Mapping[str, float] = field(default_factory=dict)
    validation_status: str = "ok"


@dataclass(frozen=True)
class HistoricalDataset:
    schema_version: int
    dataset_id: str
    generated_at: str
    games: Mapping[int, HistoricalGame]
    teams: tuple[str, ...]
    manifest: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Submission:
    charge: float
    limit: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.charge) or not math.isfinite(self.limit):
            raise ValueError("Charge and Limit must be finite")
        if self.charge < 0 or self.limit < 0:
            raise ValueError("Charge and Limit must be non-negative")


@dataclass(frozen=True)
class ValueTriple:
    lower: float
    midpoint: float
    upper: float

    def __post_init__(self) -> None:
        if self.lower > self.midpoint + 1e-9 or self.midpoint > self.upper + 1e-9:
            raise ValueError(f"unordered triple {self}")


@dataclass(frozen=True)
class Ambiguity:
    opponent_limits: int = 0
    opponent_charges: int = 0
    fair_values: int = 0
    caps: int = 0
    missing_outputs: int = 0

    def __add__(self, other: Ambiguity) -> Ambiguity:
        return Ambiguity(**{key: getattr(self, key) + getattr(other, key) for key in asdict(self)})


@dataclass(frozen=True)
class ItemScore:
    index: int
    income: ValueTriple
    cost: ValueTriple
    net: ValueTriple
    ambiguity: Ambiguity = Ambiguity()


@dataclass(frozen=True)
class GameScore:
    game_id: int
    income: ValueTriple
    cost: ValueTriple
    net: ValueTriple
    per_item: Mapping[int, ItemScore]
    ambiguity: Ambiguity = Ambiguity()


def jsonable(value: Any) -> Any:
    """Recursively encode dataclasses/maps with integer keys as strict JSON values."""
    if hasattr(value, "to_dict"):
        return jsonable(value.to_dict())
    if hasattr(value, "__dataclass_fields__"):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
