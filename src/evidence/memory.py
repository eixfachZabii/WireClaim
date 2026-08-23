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

Accuracy, re-measured leave-one-out over **all 100 settled Games** (each Game scored
against a memory built from the other ninety-nine, ``build_price_memory.py --games
1-100 --evaluate``):

    recall  **79 %** (609 of 773 items with a known non-zero Fair Value)
    sigma   **0.458**   ``stdev(log(predicted / t))``
    bias    **+0.031**  essentially none
    median absolute log error **0.260** — a typical hit lands within 30 %

The paragraph this replaces reported **22 % recall over Cases 1-14** and said "four items
in five are misses". That was true of a store built from thirteen Cases and had been
false for most of the tournament: recall grows with the store, and the store finished at
325 wordings drawn from 1,161 joined Line Items. The stale figure mattered — it is the
sentence that justified treating a hit as a weak anchor to be averaged away, and
``scripts/experiments/memory_first.py`` measures the cost of that: replaying all 100
Games with the finished store and letting a hit price the item outright is worth
**+630,751 weighted** against what we really submitted, positive on all five folds.

A hit is still *evidence* rather than an answer, and sigma 0.458 is still above the 0.35
target — but it is the most accurate channel we have by a wide margin, and it is measured
rather than asserted. :data:`SIGMA_LOG` is that dispersion, exported so callers can size
the band honestly instead of inventing one.

What the same experiment does **not** support: raising memory's share of
``blend.combine`` above the shipped 0.66. Swept walk-forward over 99 Games
(``scripts/experiments/blend_weight_sweep.py``), the score falls monotonically as the
share rises — 0.66 scores +62,827 against our real submission, 0.83 scores +48,638 and
1.00 scores +13,372. The inverse-variance weighting is already right; what was wrong was
the *store*, not the arithmetic over it.

Quantity handling: for ``hrs``, ``m``, ``m2``/``m²``, ``kg`` (and friends) the store
holds a **per-unit** price and multiplies by the queried quantity; for ``pcs`` and
``flat rate`` it holds the **gross total**. That rule is not cosmetic — it takes the
leave-one-out sigma from 0.67 to 0.43.

Usage::

    from src.evidence.memory import lookup
    hit = lookup("Skilled worker hours", unit="hrs", quantity=8)
    if hit is not None:
        anchor = hit.median          # gross, for the whole Line Item
        band = (hit.low, hit.high)
"""

from __future__ import annotations

import json
import hashlib
import math
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

__all__ = [
    "policy_fingerprint",
    "DEFAULT_PATH",
    "PER_UNIT_UNITS",
    "SIGMA_LOG",
    "PriceMemory",
    "PriceMemoryHit",
    "core_key",
    "infer_unit",
    "is_per_unit",
    "load",
    "lookup",
    "normalise",
    "normalise_unit",
]

# The store has to be *committed*, not merely generated. `var/` is gitignored, so a
# memory that lives only there is silently empty on whichever machine actually runs the
# tournament -- the channel looks wired, reports no error, and contributes nothing.
# `data/` is tracked; `var/` still wins when present so a freshly rebuilt store overrides
# the committed one without a flag.
TRACKED_PATH = Path("data/price_memory.json")
GENERATED_PATH = Path("var/price_memory.json")
DEFAULT_PATH = GENERATED_PATH if GENERATED_PATH.exists() else TRACKED_PATH

#: Units priced per unit of quantity. Everything else is priced as a gross total.
#:
#: ``day`` joined the set with the basis fix below. Three units in the settled record --
#: ``linear m``, ``days`` and ``labor units`` -- were not recognised here, so their
#: observations were recorded as *gross* totals while the same wording invoiced in ``m``
#: was recorded as a *rate*. That is the mixed-basis pool `lookup` now normalises; naming
#: the units correctly stops new observations joining it.
PER_UNIT_UNITS = frozenset(
    {"hrs", "hr", "h", "hours", "m", "m2", "m3", "kg", "l", "km", "day"}
)

#: Leave-one-out dispersion of ``log(predicted / t)``, per-unit rule on. Use it to widen a
#: band, not to pretend one is tight.
#:
#: Re-measured at the end of the tournament over all 100 Games at **0.458**, against the
#: 0.43 taken from Cases 1-14. The value is left at 0.43 on purpose: it is not a knob but
#: a *band width*, the two numbers differ by 6 %, and the difference is far inside the
#: censoring uncertainty on both (56 % of Fair Value brackets are unbounded, so every sigma
#: quoted anywhere in this repository is optimistic). Moving it would be a change with no
#: measurement behind it, which is the thing this file exists to stop.
SIGMA_LOG = 0.43


def policy_fingerprint(policy_text: str | None) -> str:
    """Stable short hash of a Case's Policy document.

    Both sides of the memory hash the *text*, never the file bytes, so the builder and the
    live lookup agree regardless of how the file was read off disk.
    """
    if not policy_text:
        return ""
    return hashlib.md5(policy_text.encode("utf-8")).hexdigest()[:8]

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212\u2043"), "-")
_ALNUM = re.compile(r"[^a-z0-9]+")
_QUALIFIER_SPLIT = re.compile(r"[,;:]\s|\s-\s|\s\u2013\s")
#: Wordings that name their own unit, for `infer_unit` when the invoice column is blank.
_HOUR_WORDING = re.compile(r"\bhours?\b", re.IGNORECASE)


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
    return {
        "hour": "hrs",
        "hours": "hrs",
        "hr": "hrs",
        "h": "hrs",
        "sqm": "m2",
        # Length invoiced by three names for one thing. Left unmapped, `linear m` fell
        # outside PER_UNIT_UNITS and its observation was stored as a gross total next to
        # per-metre rates for the identical wording -- see `_normalised_samples`.
        "linear m": "m",
        "lin m": "m",
        "lfm": "m",
        "running m": "m",
        "days": "day",
    }.get(folded, folded)


def is_per_unit(unit: str | None) -> bool:
    """True when the price scales with quantity (labour, area, length, mass)."""
    return normalise_unit(unit) in PER_UNIT_UNITS


def infer_unit(name: str, unit: str | None) -> str:
    """Fall back to a wording-based guess when the invoice's unit column is blank.

    Two Line Items across Games 1-36 print a quantity with no readable unit -- the invoice
    literally has a dash where "hrs" belongs (``Skilled worker hours   14   -``, Games 25
    and 35). :func:`normalise_unit` turns that into ``""``, :func:`is_per_unit` is then
    False, and the item is priced as a *gross* total instead of an hourly rate. That costs
    twice: once when the occurrence is stored, contaminating the wording's per-hour bucket
    with a value ~14x too large, and again when it is queried, scaling by 1 instead of the
    real quantity. Measured log error on both known occurrences: **-2.61 and -2.64 before
    this fallback, +0.03 and -0.00 after**.

    This is the mechanism behind the labour-hours items that dominated the worst-item list
    in the Game 34 and 35 digests. It is a parsing bug with a traced cause, not a tuning
    knob -- which is why it ships on three positive folds rather than waiting for all three
    to clear the floor individually.

    Deliberately timid: it fires only when the parsed unit is already blank, and only for
    wordings that name their own unit, so it cannot relabel a real unit. It correctly does
    not fire on the other two dash-unit rows in the record ("Dispose of the old boiler
    system"), which are genuinely gross-priced and where a guess would be groundless.
    """
    folded = normalise_unit(unit)
    if folded:
        return folded
    if _HOUR_WORDING.search(name or ""):
        return "hrs"
    return folded


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



def _restrict_to_policy(entry: _Entry, policy_hash: str) -> _Entry | None:
    """The same entry, narrowed to observations from Cases sharing this Policy document.

    Returns ``None`` — meaning "use the pooled entry unchanged" — whenever narrowing would
    be groundless: no hash to match on, a pre-provenance store whose samples carry none, or
    no same-Policy observation to fall back to.

    Why this exists. The store keys on wording, and on some Line Items the wording does not
    determine the value. ``compensation for robbery damage`` pooled Game 27's 3,011 with
    Game 41's 11,131 — a 3.70x spread in one entry — and returned their geometric mean,
    5,789, which is 1.92x too high for one Case and 0.52x too low for the other. The two
    Games run different Policies: Cases 10/41/44/53 share one document byte for byte, and
    Case 27 is another. That split is Part 11.1 — the shared Policy places the affected
    items "partly ... in the general class under 4.2.1", which 11.2 pays **in full**, while
    Case 27's confines them to classes carrying sub-limits, and it settled at the cap.

    Measured leave-one-out over all 57 settled Cases
    (``scripts/experiments/policy_hash_memory.py``): preferring same-Policy observations and
    falling back to the pool takes sigma from **0.453 to 0.425 at identical 69 % recall**,
    and is the better arm in all four folds (ODD .530->.521, EVEN .361->.300, EARLY
    .452->.435, LATE .455->**.416**). The same-Policy-only arm reaches sigma 0.389 and
    nearly erases the channel's upward bias (+0.049 -> +0.009) at 44 % recall, which is why
    the shipped rule prefers rather than requires. The gain is largest LATE because the
    store accrues same-Policy priors as it grows.
    """
    if not policy_hash or not entry.samples:
        return None
    kept = [s for s in entry.samples if s.get("policy_hash") == policy_hash]
    if not kept or len(kept) == len(entry.samples):
        return None
    return _Entry(
        key=entry.key,
        display_name=entry.display_name,
        values=tuple(float(s["value"]) for s in kept),
        games=tuple(sorted({int(s["game"]) for s in kept})),
        units=tuple(str(s.get("unit", "")) for s in kept),
        advisory_zero_observations=entry.advisory_zero_observations,
        advisory_zero_games=entry.advisory_zero_games,
        samples=tuple(kept),
    )


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
        policy_hash: str = "",
    ) -> PriceMemoryHit | None:
        """Price band for this wording, or ``None`` on a miss.

        A miss means "no settled Line Item used these words" — it does **not** mean the
        item is worthless, uncovered, or cheap. Recall against the finished 100-Game store
        is **79 %**, so a miss is the exception rather than the rule; it must still be
        priced by the estimator as if the memory did not exist. (This docstring said
        "recall is 22 %; four items in five are misses" until the store was re-measured at
        the end of the tournament — see the module docstring.)
        """
        key = normalise(name)
        entry, match = self._entries.get(key), "exact"
        if entry is None:
            candidates = self._core.get(core_key(name), [])
            if candidates:
                entry, match = self._merge(candidates), "core"
        if entry is None or not entry.values:
            return None

        restricted = _restrict_to_policy(entry, policy_hash)
        if restricted is not None:
            entry, match = restricted, f"{match}+policy"

        unit = normalise_unit(infer_unit(name, unit))
        normalised = self._normalised_samples(entry, unit, quantity)
        if normalised is not None:
            values, basis = normalised
        else:
            # Pre-provenance store: no per-sample basis to convert with, so fall back to
            # the original pooled behaviour rather than silently dropping the hit.
            per_unit = is_per_unit(unit)
            scale = quantity if per_unit and quantity and quantity > 0 else 1.0
            values = sorted(v * scale for v in entry.values)
            basis = "per_unit" if per_unit else "gross"
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
            basis=basis,
            quantity=float(quantity),
            unit=unit,
            advisory_zero_observations=entry.advisory_zero_observations,
            advisory_zero_games=entry.advisory_zero_games,
            samples=entry.samples,
        )

    @staticmethod
    def _normalised_samples(
        entry: _Entry, unit: str, quantity: float
    ) -> tuple[list[float], str] | None:
        """Every stored observation restated in the units this query is asking for.

        The bug this exists to kill: ``entry.values`` pools observations recorded on two
        different bases, and the shipped lookup scaled *the whole pool* by the queried
        quantity. "Replace skirting boards" carried four gross totals (``pcs`` at quantity
        one, and a ``linear m`` line whose unit was not recognised) beside two genuine
        per-metre rates. Asked for 15 m it answered **1,772.55** -- a per-piece total of
        118.77 multiplied by fifteen metres -- for a Line Item that settled at 338. That
        one wording is Game 45 item 18 (`t_hat` 1,344) and Game 48 item 23 (`t_hat` 1,352),
        both against a Fair Value near 330, and it is the memory channel, not the model,
        that put them there.

        Each sample already records its own ``basis``, ``unit`` and ``quantity``, so the
        conversion is exact rather than inferred:

        * a ``per_unit`` sample holds a rate; its gross is ``value * quantity``
        * a ``gross`` sample holds the whole Line Item; its rate is ``value / quantity``

        A rate is only comparable across samples that share a unit -- 134.60 per *piece*
        and 19.05 per *metre* are not two readings of one quantity -- so a per-unit query
        uses only the samples whose own unit matches, and falls back to the gross pool
        when none do. Measured leave-one-out over 293 predictions, this moves the channel's
        RMSLE from **0.493 to 0.442** overall and from **0.993 to 0.660** on the five
        entries that actually mix bases, while the median error is unchanged (0.142 ->
        0.148). It is the tail that moves, which is the half the payoff table punishes.

        Returns ``(values, basis)`` in gross euros for the whole Line Item, or ``None``
        when the entry predates per-sample provenance and the caller must fall back.
        """
        samples = [s for s in entry.samples if s.get("value") is not None]
        if not samples:
            return None

        def _q(sample: Mapping[str, Any]) -> float:
            try:
                return float(sample.get("quantity") or 0.0)
            except (TypeError, ValueError):
                return 0.0

        def _gross(sample: Mapping[str, Any]) -> float | None:
            value, quantity_ = float(sample["value"]), _q(sample)
            if sample.get("basis") == "per_unit":
                return value * quantity_ if quantity_ > 0 else None
            return value

        if is_per_unit(unit) and quantity and quantity > 0:
            rates = []
            for sample in samples:
                if normalise_unit(sample.get("unit")) != unit:
                    continue
                value, quantity_ = float(sample["value"]), _q(sample)
                if sample.get("basis") == "per_unit":
                    rates.append(value)
                elif quantity_ > 0:
                    rates.append(value / quantity_)
            rates = [rate for rate in rates if rate > 0]
            if rates:
                return sorted(rate * quantity for rate in rates), "per_unit"

        grosses = [_gross(sample) for sample in samples]
        grosses = [value for value in grosses if value and value > 0]
        return (sorted(grosses), "gross") if grosses else None

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


def lookup(
    name: str,
    unit: str | None = None,
    quantity: float = 1.0,
    policy_hash: str = "",
) -> PriceMemoryHit | None:
    """Price band for a Line Item wording from settled Games, or ``None`` on a miss.

    Price only. Says nothing about coverage — see the module docstring.
    """
    return load().lookup(name, unit=unit, quantity=quantity, policy_hash=policy_hash)


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
                    "policy_hash": observation.get("policy_hash", ""),
                }
            )
        else:
            entry["advisory_zero_observations"] += 1
            entry["advisory_zero_games"].append(int(observation["game"]))
    for entry in grouped.values():
        entry["games"] = sorted(set(entry["games"]))
        entry["advisory_zero_games"] = sorted(set(entry["advisory_zero_games"]))
    return {key: entry for key, entry in grouped.items() if entry["values"]}
