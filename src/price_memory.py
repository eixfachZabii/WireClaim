"""Price Memory — what settled Games say a Line Item wording was worth.

**This store answers one question and refuses the other one.**

    "How much was this wording worth, on the occasions it was worth anything?"

It will not tell you whether the item is covered. Coverage is a property of *this*
Case's policy, not of the wording, and the data says so loudly: of the wordings that
repeat across Cases 1-14, six flip between a Fair Value of zero and a Fair Value in the
tens or hundreds. ``vehicle costs`` is 0 in Cases 1, 2, 3, 4 and 32-111 in Cases 5, 8,
9, 11, 13 — the same three words, same trade, opposite answers. A memory that reported
"this wording is usually free" would be wrong five times out of seventeen on that
wording alone, and wrong in the expensive direction (see R7: a Charge of 0 on a covered
item forfeits guaranteed income; a Limit of 0 wrongfully rejects and pays 1.5a).

So the store is built **only from occurrences with a proven non-zero Fair Value**, and a
:class:`PriceMemoryHit` carries a price band and nothing else. ``zero_observations`` is
recorded as an **advisory** count — how often this wording settled at zero elsewhere —
and is explicitly not a coverage verdict. Read it as "other policies have excluded this
before, go and check the clause", never as "skip this item".

Accuracy, measured leave-one-out over Cases 1-14 (each Case scored against a memory
built from the other thirteen): recall 22 % of the items with a known non-zero Fair
Value, and ``sigma = stdev(log(predicted / t))`` of **0.43**. That is worse than the
0.35 break-even, so a hit is *evidence*, not an answer — hand it to the estimator as one
anchor among several and let the posterior widen it. :data:`SIGMA_LOG` is that measured
dispersion, exported so callers can size the band honestly instead of inventing one.

Quantity handling: for ``hrs``, ``m``, ``m2``/``m²``, ``kg`` (and friends) the store
holds a **per-unit** price and multiplies by the queried quantity; for ``pcs`` and
``flat rate`` it holds the **gross total**. That rule is not cosmetic — it takes the
leave-one-out sigma from 0.67 to 0.43.

Usage::

    from src.price_memory import lookup
    hit = lookup("Skilled worker hours", unit="hrs", quantity=8)
    if hit is not None:
        anchor = hit.median          # gross, for the whole Line Item
        band = (hit.low, hit.high)
"""

from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

__all__ = [
    "DEFAULT_PATH",
    "PER_UNIT_UNITS",
    "SIGMA_LOG",
    "PriceMemory",
    "PriceMemoryHit",
    "core_key",
    "is_per_unit",
    "load",
    "lookup",
    "normalise",
    "normalise_unit",
]

DEFAULT_PATH = Path("var/price_memory.json")

#: Units priced per unit of quantity. Everything else is priced as a gross total.
PER_UNIT_UNITS = frozenset({"hrs", "hr", "h", "hours", "m", "m2", "m3", "kg", "l", "km"})

#: Leave-one-out dispersion of ``log(predicted / t)`` over Cases 1-14, exact-wording
#: hits, per-unit rule on. Use it to widen a band, not to pretend one is tight.
SIGMA_LOG = 0.43

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212\u2043"), "-")
_ALNUM = re.compile(r"[^a-z0-9]+")
_QUALIFIER_SPLIT = re.compile(r"[,;:]\s|\s-\s|\s\u2013\s")


def normalise(name: str) -> str:
    """Fold a Line Item description to its comparison key.

    Case, punctuation, dash flavour and the ``m²``/``m2`` spelling all vary between
    invoices for the same wording, and none of them carry price information.
    """
    folded = (name or "").lower().translate(_DASHES)
    folded = folded.replace("m²", "m2").replace("m³", "m3").replace("°", " degree ")
    return " ".join(_ALNUM.sub(" ", folded).split())


def core_key(name: str) -> str:
    """The wording with its trailing qualifier dropped.

    ``"Condensation dryer for the kitchen, rental for the drying period"`` and
    ``"Condensation dryer"`` are the same purchase described by two invoice clerks.
    This is the second and last matching tier; anything looser (token overlap, nearest
    neighbour) was measured and made sigma *worse* — 0.43 to 0.72 at a Jaccard
    threshold of 0.7, 1.19 at 0.25 — so it is deliberately not implemented.
    """
    head = (name or "").split("(")[0]
    return normalise(_QUALIFIER_SPLIT.split(head)[0])


def normalise_unit(unit: str | None) -> str:
    folded = normalise(unit or "")
    return {"hour": "hrs", "hours": "hrs", "hr": "hrs", "h": "hrs", "sqm": "m2"}.get(
        folded, folded
    )


def is_per_unit(unit: str | None) -> bool:
    """True when the price scales with quantity (labour, area, length, mass)."""
    return normalise_unit(unit) in PER_UNIT_UNITS


@dataclass(frozen=True)
class PriceMemoryHit:
    """A price band for one wording. **Price only — never a coverage verdict.**"""

    name: str
    key: str
    match: str
    """``"exact"`` (normalised wording) or ``"core"`` (wording minus its qualifier)."""

    low: float
    median: float
    high: float
    """The honest band: the observed spread widened to at least the measured
    leave-one-out dispersion of :data:`SIGMA_LOG`. The raw spread alone
    (:attr:`observed_low` / :attr:`observed_high`) contained the true Fair Value on only
    42 % of leave-one-out hits — with one to three observations, two prices that happen
    to agree are a small sample, not a tight posterior. Widened, it covers 65 %."""

    observations: int
    """How many settled Line Items with a proven non-zero Fair Value back this band."""

    games: tuple[int, ...]
    basis: str
    """``"per_unit"`` if the band was scaled by the queried quantity, else ``"gross"``."""

    quantity: float = 1.0
    unit: str = ""
    observed_low: float = 0.0
    observed_high: float = 0.0
    """The raw min and max of the stored observations, before widening."""

    advisory_zero_observations: int = 0
    """ADVISORY ONLY. How often this wording settled at a Fair Value of zero in other
    Cases, i.e. how often some other policy excluded it. It is **not** a coverage
    signal for this Case — six of the fifteen repeated wordings flip. Use it to decide
    which policy clause to go and read, never to decide a Charge."""

    advisory_zero_games: tuple[int, ...] = ()
    samples: tuple[Mapping[str, Any], ...] = field(default=(), repr=False)

    @property
    def band(self) -> tuple[float, float, float]:
        return (self.low, self.median, self.high)

    def widened(self, sigma: float = SIGMA_LOG) -> tuple[float, float]:
        """The band stretched to the measured leave-one-out dispersion.

        A band built from two observations that happened to agree is not a tight
        posterior, it is a small sample. This is the honest width.
        """
        return (self.median * math.exp(-sigma), self.median * math.exp(sigma))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "key": self.key,
            "match": self.match,
            "low": self.low,
            "median": self.median,
            "high": self.high,
            "observed_low": self.observed_low,
            "observed_high": self.observed_high,
            "observations": self.observations,
            "games": list(self.games),
            "basis": self.basis,
            "quantity": self.quantity,
            "unit": self.unit,
            "advisory_zero_observations": self.advisory_zero_observations,
            "advisory_zero_games": list(self.advisory_zero_games),
        }


@dataclass(frozen=True)
class _Entry:
    key: str
    display_name: str
    values: tuple[float, ...]
    games: tuple[int, ...]
    units: tuple[str, ...]
    advisory_zero_observations: int
    advisory_zero_games: tuple[int, ...]
    samples: tuple[Mapping[str, Any], ...]


class PriceMemory:
    """Loaded Price Memory. Cheap to construct, safe when the store is missing."""

    def __init__(self, entries: Mapping[str, _Entry] | None = None, source: Path | None = None):
        self._entries: dict[str, _Entry] = dict(entries or {})
        self.source = source
        self._core: dict[str, list[str]] = {}
        for key, entry in self._entries.items():
            self._core.setdefault(core_key(entry.display_name), []).append(key)

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, name: str) -> bool:
        return normalise(name) in self._entries

    @property
    def games(self) -> tuple[int, ...]:
        return tuple(sorted({g for e in self._entries.values() for g in e.games}))

    def lookup(
        self,
        name: str,
        unit: str | None = None,
        quantity: float = 1.0,
    ) -> PriceMemoryHit | None:
        """Price band for this wording, or ``None`` on a miss.

        A miss means "no settled Line Item used these words" — it does **not** mean the
        item is worthless, uncovered, or cheap. Recall is 22 %; four items in five are
        misses and must be priced by the estimator as if the memory did not exist.
        """
        key = normalise(name)
        entry, match = self._entries.get(key), "exact"
        if entry is None:
            candidates = self._core.get(core_key(name), [])
            if candidates:
                entry, match = self._merge(candidates), "core"
        if entry is None or not entry.values:
            return None

        per_unit = is_per_unit(unit)
        scale = quantity if per_unit and quantity and quantity > 0 else 1.0
        values = sorted(v * scale for v in entry.values)
        median = statistics.median(values)
        return PriceMemoryHit(
            name=entry.display_name,
            key=entry.key,
            match=match,
            low=min(values[0], median * math.exp(-SIGMA_LOG)),
            median=median,
            high=max(values[-1], median * math.exp(SIGMA_LOG)),
            observed_low=values[0],
            observed_high=values[-1],
            observations=len(values),
            games=entry.games,
            basis="per_unit" if per_unit else "gross",
            quantity=float(quantity),
            unit=normalise_unit(unit),
            advisory_zero_observations=entry.advisory_zero_observations,
            advisory_zero_games=entry.advisory_zero_games,
            samples=entry.samples,
        )

    def _merge(self, keys: list[str]) -> _Entry:
        picked = [self._entries[k] for k in sorted(keys)]
        if len(picked) == 1:
            return picked[0]
        return _Entry(
            key=core_key(picked[0].key),
            display_name=picked[0].display_name,
            values=tuple(v for e in picked for v in e.values),
            games=tuple(sorted({g for e in picked for g in e.games})),
            units=tuple(u for e in picked for u in e.units),
            advisory_zero_observations=sum(e.advisory_zero_observations for e in picked),
            advisory_zero_games=tuple(sorted({g for e in picked for g in e.advisory_zero_games})),
            samples=tuple(s for e in picked for s in e.samples),
        )

    # -- serialisation ---------------------------------------------------------

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], source: Path | None = None) -> PriceMemory:
        entries: dict[str, _Entry] = {}
        for key, raw in (payload.get("entries") or {}).items():
            values = tuple(float(v) for v in raw.get("values", ()))
            if not values:
                continue
            entries[key] = _Entry(
                key=key,
                display_name=raw.get("display_name", key),
                values=values,
                games=tuple(int(g) for g in raw.get("games", ())),
                units=tuple(raw.get("units", ())),
                advisory_zero_observations=int(raw.get("advisory_zero_observations", 0)),
                advisory_zero_games=tuple(int(g) for g in raw.get("advisory_zero_games", ())),
                samples=tuple(raw.get("samples", ())),
            )
        return cls(entries, source=source)

    @classmethod
    def load(cls, path: str | Path | None = None) -> PriceMemory:
        """Load the store. A missing or unreadable file yields an empty memory.

        Rule 1: the pipeline must still submit when an input is absent. A Price Memory
        that raises at 03:00 because ``var/`` was not populated costs a whole Game;
        an empty one costs a few anchors.
        """
        target = Path(path) if path is not None else DEFAULT_PATH
        try:
            payload = json.loads(target.read_text())
        except (OSError, ValueError):
            return cls(source=target)
        return cls.from_dict(payload, source=target)


_DEFAULT: PriceMemory | None = None


def load(path: str | Path | None = None, refresh: bool = False) -> PriceMemory:
    """The process-wide Price Memory, loaded once."""
    global _DEFAULT
    if _DEFAULT is None or refresh or path is not None:
        memory = PriceMemory.load(path)
        if path is None or refresh:
            _DEFAULT = memory
        return memory
    return _DEFAULT


def lookup(name: str, unit: str | None = None, quantity: float = 1.0) -> PriceMemoryHit | None:
    """Price band for a Line Item wording from settled Games, or ``None`` on a miss.

    Price only. Says nothing about coverage — see the module docstring.
    """
    return load().lookup(name, unit=unit, quantity=quantity)


def build_entries(observations: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Group scored observations into the serialisable ``entries`` block.

    Each observation needs ``key``, ``display_name``, ``game``, ``value``, ``unit`` and
    ``positive`` (whether the Fair Value was proven non-zero). Only positive ones reach
    the band; the rest are counted as the advisory zero tally.
    """
    grouped: dict[str, dict[str, Any]] = {}
    for observation in observations:
        key = observation["key"]
        entry = grouped.setdefault(
            key,
            {
                "display_name": observation.get("display_name", key),
                "values": [],
                "games": [],
                "units": [],
                "advisory_zero_observations": 0,
                "advisory_zero_games": [],
                "samples": [],
            },
        )
        if observation.get("positive"):
            entry["values"].append(round(float(observation["value"]), 4))
            entry["games"].append(int(observation["game"]))
            entry["units"].append(observation.get("unit", ""))
            entry["samples"].append(
                {
                    "game": int(observation["game"]),
                    "line_item_index": observation.get("line_item_index"),
                    "unit": observation.get("unit", ""),
                    "quantity": observation.get("quantity", 1.0),
                    "value": round(float(observation["value"]), 4),
                    "t_low": observation.get("t_low"),
                    "t_high": observation.get("t_high"),
                    "basis": observation.get("basis", "gross"),
                }
            )
        else:
            entry["advisory_zero_observations"] += 1
            entry["advisory_zero_games"].append(int(observation["game"]))
    for entry in grouped.values():
        entry["games"] = sorted(set(entry["games"]))
        entry["advisory_zero_games"] = sorted(set(entry["advisory_zero_games"]))
    return {key: entry for key, entry in grouped.items() if entry["values"]}
