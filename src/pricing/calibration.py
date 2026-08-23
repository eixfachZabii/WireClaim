"""The calibration layer: turn an *asserted* band into a *measured, censoring-aware* one.

**NOT WIRED INTO PRICING. This is a measurement instrument, and it stays one until it beats
the shipped rule.** `scripts/experiments/calibration_backtest.py` scores it leave-one-Game-out
against the real Field over 73 Games and it **loses at every cell of a 42-cell quantile sweep**
-- best -36,050 weighted, worst -2,812,204. Reading a Charge off a residual quantile is simply
worse than `charge_factor(sigma) * median`, and no quantile pair repairs it.

It is kept, and kept here, because the *measurement* it makes is the one that corrected the
diagnosis everything else was built on: the "+19 % estimation bias" that motivated three
experiments does not exist. It is an artefact of scoring on bounded brackets only. Handling the
censoring properly moves the median `t / t_hat` from 0.841 to **0.982** -- we were essentially
unbiased the whole time. Anyone about to correct a level error in this pipeline should run
`Calibration.fit` first and check the level error is real.

The fault this exists to fix
----------------------------
`src/pricing/engine.py` prices from `implied_sigma(low, median, high)` -- the width the model
asserted. Measured over the 844 logged Line Items of Games 26-100
(`scripts/experiments/estimate_calibration.py`):

    median asserted sigma        0.350
    realised RMSLE               0.658      we understate our own error by 1.88x
    truth outside the 90% band   27.5%      an honest band leaves out 10.0%

R4b says the Limit rule is only as good as the posterior it quantiles, so the band is not
repaired here -- it is **replaced** by the measured distribution of the log residual

    r = log(t / t_hat)

taken from settled Games, where `t` is recoverable. Nothing is assumed about its shape: it is
skewed and fat-tailed on the left, and both survive into the quantiles. Fitting a lognormal to
that and reading `Q_(1/3)` off it puts the Limit in the wrong place *by construction*, however
well the sigma is measured.

The censoring, which is the whole difficulty
--------------------------------------------
`t` is never observed. `invert_fair_values.brackets()` returns `[t_lo, t_hi)`, and `t_hi` is
infinite whenever **nobody rightfully rejected** -- which is not missing data, it is data
selected on the outcome. The first version of this module used the bounded brackets only and
**lost 39,022 to 499,440 weighted at every cell of a 42-cell quantile sweep**
(`scripts/experiments/calibration_backtest.py --sweep`). The reason is measurable and total:

    bounded  brackets (342 items)   median  t  = 0.841 x t_hat     we overestimate
    censored brackets (189 items)   median  t >= 1.044 x t_hat     we UNDERestimate, provably

    85.2 % of censored items have a proven floor above the bounded sample's median residual
    60.8 % of censored items are provably worth MORE than our estimate

A bounded bracket exists precisely *because* somebody Charged above `t` and was rightfully
rejected, so the bounded sample is the sub-population on which the Field -- and therefore
usually we -- overestimated. The "+19 % bias" that motivated the first attempt is an artefact
of that selection. CLAUDE.md already records eight experiments lost to this exact trap and
says "never condition on the answer"; the first version conditioned on it anyway.

So the residual is fitted as **interval-censored** data. Every Line Item with a floor
contributes an interval rather than a point:

    bounded    r in [log(t_lo / t_hat), log(t_hi / t_hat))
    censored   r in [log(t_lo / t_hat), +inf)

and the distribution is the nonparametric maximum-likelihood estimate over those intervals --
Turnbull's self-consistency algorithm, the interval-censored generalisation of Kaplan-Meier.
It uses all 531 items instead of 342, it is consistent under exactly the censoring mechanism
we have, and it needs no distributional assumption. Where every observation happens to be
exact it reduces to the empirical CDF, so nothing is lost on a clean sample.

Stratification, and the trap it walks around
--------------------------------------------
Residuals pool per **stratum**, and a stratum may only be built from things known at submission
time. CLAUDE.md documents eight experiments lost to bucketing `t_hat / t` by the *true* `t` --
items land in a high-`t` bucket partly because we underestimated them. `stratum_of` therefore
reads only `t_hat` and the channel mix, both of which exist before the Case settles.

The channel split is the one that matters, and it is large:

    channels             n    median t_hat/t    RMSLE     (bounded sample; see the caveat above)
    B:memory            60          0.995       0.195     watched settle; nearly exact
    B:memory|C:model   180          1.188       0.530
    C:model            102          1.639       0.966     the model alone, adrift

`MODEL_SIGMA_PRIOR` is 0.6 and `MEMORY_SIGMA` is 0.43, so `blend.combine` hands the model 34 %
of the inverse-variance weight. At the measured widths it earns about 4 %.

Fallback, and why it is conservative
------------------------------------
A stratum with fewer than `MIN_STRATUM` observations cannot support a quantile and backs off to
its channel-only parent, then to the global pool. `Stratum.quantile` never extrapolates past the
extreme observed value: outside the data it returns the edge, which understates the tail rather
than inventing one. Uptime outranks accuracy (rule 8), so every path here returns a usable
number rather than raising.
"""

from __future__ import annotations

import json
import math
import statistics
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

#: Below this many observations a stratum cannot support a quantile and backs off to its
#: parent. 25 is not tuned -- it is the point at which a 1/3 quantile has ~8 observations
#: under it, the fewest that can move without one Line Item deciding the Limit.
MIN_STRATUM = 25

#: Where `scripts/build_calibration.py` writes the fit. Tracked, because `var/` is gitignored
#: and a pipeline that starts with no calibration prices from the asserted band again -- the
#: exact fault this module removes.
DEFAULT_PATH = Path("data/calibration.json")

#: `t_hat` bucket edges. Chosen on the measurement, not for roundness: the error is flat below
#: 200, degrades through the middle, and blows out above 1,000, which is where the forfeited
#: income lives.
BUCKET_EDGES = (50.0, 200.0, 400.0, 1000.0)
BUCKET_NAMES = ("<50", "50-200", "200-400", "400-1k", ">1k")

#: Turnbull EM stops when no support mass moves by more than this, or after this many rounds.
#: Both are loose: the fit is over a few hundred intervals and converges in tens of rounds.
_TOL = 1e-9
_MAX_ROUNDS = 2_000

#: The residual is clamped into this log range before fitting. `t_hat` can be three orders out
#: on a bad Line Item, and one such observation otherwise drags a stratum's whole upper tail.
#: exp(+-4) is a factor of 55, comfortably outside anything the payoff table cares about.
_CLAMP = 4.0


def bucket_of(t_hat: float) -> str:
    """Which `t_hat` bucket this estimate falls in. Knowable at submission time, by design."""
    return BUCKET_NAMES[bisect_left(BUCKET_EDGES, t_hat)] if t_hat > 0 else BUCKET_NAMES[0]


def channel_key(channels: Iterable[str] | None) -> str:
    """A canonical name for a channel mix, stable across orderings.

    The live decision log writes `["B:memory", "C:model"]`; the export flattens the same thing
    to `"B:memory|C:model"`. Both must land on one key, or the strata split in half and neither
    half clears `MIN_STRATUM`.
    """
    if not channels:
        return "none"
    if isinstance(channels, str):
        parts = [p for p in channels.split("|") if p]
    else:
        parts = [p for c in channels for p in str(c).split("|") if p]
    return "|".join(sorted(set(parts))) or "none"


def stratum_of(t_hat: float, channels: Iterable[str] | None) -> tuple[str, str, str]:
    """`(full, channel-only, global)` -- the back-off chain, most specific first."""
    channel = channel_key(channels)
    return (f"{channel}@{bucket_of(t_hat)}", channel, "*")


# --------------------------------------------------------------------------- Turnbull


def turnbull(intervals: Sequence[tuple[float, float]]) -> tuple[list[float], list[float]]:
    """NPMLE of a distribution from interval-censored observations.

    `intervals` are `(low, high)` bounds on the unobserved value, `high` possibly `inf`.
    Returns `(support, mass)` -- the points carrying probability and how much, summing to 1.

    Turnbull's self-consistency algorithm: mass can only sit on the *innermost* intervals (the
    maximal cliques of the overlap graph, found here as the `[q_j, p_j]` pairs where a left
    endpoint is immediately followed by a right endpoint in the sorted endpoint list), and EM
    iterates "split each observation's mass across the innermost intervals it contains, in
    proportion to the current estimate, then renormalise".

    Where every interval is a point this returns the empirical CDF exactly, so a clean sample
    costs nothing. A representative point is taken at each innermost interval's **left end**,
    which is the conservative choice for us: the left end is the smallest value consistent with
    the data, so both the Charge and the Limit come out no higher than the evidence supports.
    """
    if not intervals:
        return [], []

    # Innermost intervals: scan the merged endpoint list for a left endpoint immediately
    # followed (in sort order, lefts before rights at a tie) by a right endpoint.
    events: list[tuple[float, int]] = []
    for low, high in intervals:
        events.append((low, 0))
        events.append((high, 1))
    events.sort(key=lambda e: (e[0], e[1]))
    inner: list[tuple[float, float]] = []
    for (value, kind), (next_value, next_kind) in zip(events, events[1:]):
        if kind == 0 and next_kind == 1:
            inner.append((value, next_value))
    if not inner:
        inner = [(min(low for low, _ in intervals), min(high for _, high in intervals))]

    size = len(inner)
    mass = [1.0 / size] * size

    # Precompute, per observation, which innermost intervals it covers. `inner` is sorted by
    # left endpoint, and an observation covers a contiguous run of it, so two binary searches
    # replace the O(n * m) membership scan the naive form does every round.
    lefts = [low for low, _ in inner]
    rights = [high for _, high in inner]
    covered: list[tuple[int, int]] = []
    for low, high in intervals:
        start = bisect_left(lefts, low)
        stop = bisect_right(rights, high)
        # `bisect_right` over `rights` is exact only because `inner` is sorted in both
        # coordinates -- innermost intervals are disjoint and ordered, which is what makes the
        # covered set contiguous in the first place.
        while stop < size and rights[stop] <= high:
            stop += 1
        while start > 0 and lefts[start - 1] >= low:
            start -= 1
        if start < stop:
            covered.append((start, stop))

    if not covered:
        return [low for low, _ in inner], mass

    for _ in range(_MAX_ROUNDS):
        nxt = [0.0] * size
        for start, stop in covered:
            total = sum(mass[start:stop])
            if total <= 0.0:
                share = 1.0 / (stop - start)
                for j in range(start, stop):
                    nxt[j] += share
            else:
                for j in range(start, stop):
                    nxt[j] += mass[j] / total
        scale = sum(nxt)
        if scale <= 0.0:
            break
        nxt = [v / scale for v in nxt]
        moved = max(abs(a - b) for a, b in zip(mass, nxt))
        mass = nxt
        if moved < _TOL:
            break

    keep = [(low, m) for (low, _), m in zip(inner, mass) if m > 1e-12]
    if not keep:
        return [low for low, _ in inner], mass
    return [low for low, _ in keep], [m for _, m in keep]


@dataclass(frozen=True)
class Stratum:
    """The fitted residual distribution `log(t / t_hat)` for one stratum."""

    name: str
    #: Ascending support points of the NPMLE.
    support: tuple[float, ...] = ()
    #: Probability mass at each support point; sums to 1.
    mass: tuple[float, ...] = ()
    #: How many Line Items contributed, censored ones included.
    n: int = 0
    #: How many of those had a bounded bracket. The rest were right-censored.
    n_bounded: int = 0

    @property
    def median(self) -> float:
        return self.quantile(0.5)

    @property
    def bias(self) -> float:
        """`median(t_hat / t)`. Above 1 means we overestimate."""
        return math.exp(-self.median)

    @property
    def censored_fraction(self) -> float:
        return 1.0 - (self.n_bounded / self.n) if self.n else 0.0

    def quantile(self, q: float) -> float:
        """Inverse CDF of the fitted residual, clamped to the observed support.

        Steps rather than interpolates between support points, because the NPMLE puts mass at
        points and says nothing about what lies between them. Outside the support it returns
        the edge -- understating the tail rather than inventing one.
        """
        if not self.support:
            return 0.0
        if q <= 0.0:
            return self.support[0]
        cumulative = 0.0
        for point, weight in zip(self.support, self.mass):
            cumulative += weight
            if cumulative >= q:
                return point
        return self.support[-1]

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "n_bounded": self.n_bounded,
            "bias": round(self.bias, 5),
            "support": [round(v, 6) for v in self.support],
            "mass": [round(v, 8) for v in self.mass],
        }

    @classmethod
    def from_dict(cls, name: str, blob: Mapping) -> Stratum:
        return cls(
            name=name,
            support=tuple(blob.get("support", ())),
            mass=tuple(blob.get("mass", ())),
            n=int(blob.get("n", 0)),
            n_bounded=int(blob.get("n_bounded", 0)),
        )


@dataclass(frozen=True)
class Calibration:
    """Every stratum's fitted residual, plus the back-off that makes them always answerable."""

    strata: Mapping[str, Stratum] = field(default_factory=dict)
    #: How many settled Line Items this was fitted on. Reported, never used in a decision.
    fitted_on: int = 0
    #: Game ids the observations came from, so a leave-one-out check can prove the exclusion.
    games: tuple[int, ...] = ()

    def resolve(self, t_hat: float, channels: Iterable[str] | None) -> Stratum:
        """The most specific stratum with at least `MIN_STRATUM` observations. Never fails."""
        for name in stratum_of(t_hat, channels):
            found = self.strata.get(name)
            if found is not None and found.n >= MIN_STRATUM:
                return found
        return self.strata.get("*", Stratum("*"))

    def correct(self, t_hat: float, channels: Iterable[str] | None) -> float:
        """`t_hat` with its stratum's measured level error taken out -- centre only, not width."""
        if t_hat <= 0:
            return t_hat
        return t_hat * math.exp(self.resolve(t_hat, channels).median)

    def band(
        self, t_hat: float, channels: Iterable[str] | None, quantiles: Sequence[float]
    ) -> list[float]:
        """`t_hat` read at each requested residual quantile. The replacement for the band.

        Note what is *not* here: no lognormal, no sigma, no `BAND_Z`. `q = 1/3` returns the
        value the truth exceeds two times in three on the fitted distribution, which is exactly
        the quantity R4's acceptance test asks for.
        """
        if t_hat <= 0:
            return [0.0 for _ in quantiles]
        stratum = self.resolve(t_hat, channels)
        return [t_hat * math.exp(stratum.quantile(q)) for q in quantiles]

    # ------------------------------------------------------------------ persistence

    def to_dict(self) -> dict:
        return {
            "version": 2,
            "estimator": "turnbull-npmle-interval-censored",
            "fitted_on": self.fitted_on,
            "games": list(self.games),
            "min_stratum": MIN_STRATUM,
            "strata": {name: s.to_dict() for name, s in sorted(self.strata.items())},
        }

    @classmethod
    def from_dict(cls, blob: Mapping) -> Calibration:
        return cls(
            strata={
                name: Stratum.from_dict(name, body)
                for name, body in blob.get("strata", {}).items()
            },
            fitted_on=int(blob.get("fitted_on", 0)),
            games=tuple(blob.get("games", ())),
        )

    @classmethod
    def fit(cls, observations: Iterable[Mapping]) -> Calibration:
        """Build from `{t_hat, t_lo, t_hi, channels, game_id}` rows.

        `t_hi` may be `None` or `inf`, which is the right-censored case and is *kept*: it is
        60 % of the sample on the channel mixes that matter, and dropping it is what made the
        first version of this module lose money at every cell of a 42-cell sweep. See the
        module docstring for the two medians that prove the selection.
        """
        pools: dict[str, list[tuple[float, float]]] = {}
        bounded_count: dict[str, int] = {}
        games: set[int] = set()
        count = 0
        for row in observations:
            t_hat = float(row.get("t_hat") or 0.0)
            t_lo = row.get("t_lo")
            if t_hat <= 0.0 or t_lo is None:
                continue
            t_lo = float(t_lo)
            if t_lo <= 0.0:
                # `t_lo = 0` says only "nobody proved entitlement", which is consistent with
                # any `t` at all. It is not an observation of the residual and cannot enter.
                continue
            t_hi = row.get("t_hi")
            t_hi = math.inf if t_hi is None else float(t_hi)
            low = max(math.log(t_lo / t_hat), -_CLAMP)
            high = _CLAMP if not math.isfinite(t_hi) else min(math.log(t_hi / t_hat), _CLAMP)
            if high < low:
                high = low
            bounded = math.isfinite(t_hi)
            count += 1
            if row.get("game_id") is not None:
                games.add(int(row["game_id"]))
            for name in stratum_of(t_hat, row.get("channels")):
                pools.setdefault(name, []).append((low, high))
                bounded_count[name] = bounded_count.get(name, 0) + int(bounded)

        strata: dict[str, Stratum] = {}
        for name, intervals in pools.items():
            support, mass = turnbull(intervals)
            strata[name] = Stratum(
                name=name,
                support=tuple(support),
                mass=tuple(mass),
                n=len(intervals),
                n_bounded=bounded_count.get(name, 0),
            )
        return cls(strata=strata, fitted_on=count, games=tuple(sorted(games)))


def load(path: str | Path | None = None) -> Calibration:
    """Read the tracked calibration, or an empty one. Never raises -- rule 8.

    An empty `Calibration` resolves to an empty stratum whose `median` and `quantile` are 0, so
    `correct` is the identity and `band` returns `t_hat` at every quantile: the old behaviour
    minus the fabricated width, which is the right thing for a pipeline that starts before its
    first calibration exists.
    """
    target = Path(path) if path is not None else DEFAULT_PATH
    try:
        return Calibration.from_dict(json.loads(target.read_text()))
    except (OSError, ValueError, KeyError):
        return Calibration()


__all__ = [
    "BUCKET_NAMES",
    "Calibration",
    "DEFAULT_PATH",
    "MIN_STRATUM",
    "Stratum",
    "bucket_of",
    "channel_key",
    "load",
    "stratum_of",
    "turnbull",
]
