"""Shared machinery for the measured-sigma candidate (coordinator's mid-task reframe).

`price_item` computes `sigma = implied_sigma(price_low, price_median, price_high)` -- the
width the MODEL ASSERTED -- and feeds it into both `charge_factor` (the Charge) and the
Limit's conditional lognormal quantile. `engine.py`'s own docstring already measured that
asserted width to carry no signal (narrow tercile RMSLE 0.847 vs wide tercile's 0.733,
backwards). This file swaps in a MEASURED sigma, looked up by (channel, basis) -- both
readable from the decision log at submission time -- instead of the asserted band, while
changing nothing else `price_item` does (median, coverage, ceilings, caps, the `b <= a`
clamp all untouched). It deliberately does NOT touch `blend.MODEL_SIGMA_PRIOR` /
`blend.MEMORY_SIGMA` -- those set `combine()`'s blend WEIGHTING (and, through it, the
blended median), a different mechanism already tested and rejected on its own in
`docs/brainstorm/sebi/strats/review/sigma-calibration.md` section 3.

`price_item_measured_sigma` is a line-for-line reimplementation of
`src/domain/pricing/engine.price_item`, with the one line that computes `sigma` replaced by
a caller-supplied value. `sanity_check()` proves it is faithful: called with
`sigma_override = implied_sigma(...)` (i.e. reproducing the original), it must match
`price_item`'s own output to the cent, for every row in the sample.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from charge_buckets import Row  # noqa: E402
from src.domain.pricing.engine import (  # noqa: E402
    COVERAGE_FLOOR,
    LIMIT_CAP,
    LIMIT_CEILING,
    LIMIT_CEILING_MEMORY,
    LIMIT_QUANTILE,
    Evidence,
    Price,
    _lognormal_quantile,
    charge_factor,
    implied_sigma,
    price_item,
)
from src.domain.pricing.memory import is_per_unit  # noqa: E402


def basis_of(row: Row) -> str:
    """'per_unit' (labour/area/length/mass, priced as rate x quantity) or 'gross'.

    Reuses `src.domain.pricing.memory.is_per_unit` directly -- the SAME function
    `build_price_memory.py` uses to bucket its own leave-one-out sigma -- rather than
    `Row.metered`'s ad hoc regex proxy from the earlier upward-multiplier section, so this
    candidate's numbers are comparable to `sigma-calibration.md`'s section 2. It disagrees
    with `Row.metered` on exactly one unit in this sample: 'day' is per-unit under the old
    proxy but gross under the real classifier (n=2, immaterial).
    """
    return "per_unit" if is_per_unit(row.unit) else "gross"


def channel_of(row: Row) -> str:
    return "memory" if row.has_memory else "model"


def price_item_measured_sigma(
    evidence: Evidence,
    *,
    confirmed_uncovered: bool,
    memory_backed: bool,
    sigma_override: float,
) -> Price:
    """`price_item`, verbatim, with `sigma` substituted rather than computed from the band."""
    filled = evidence.with_defaults()
    sigma = sigma_override
    covered = 0.0 if confirmed_uncovered else filled.coverage_probability

    charge = charge_factor(sigma) * filled.price_median

    if covered <= COVERAGE_FLOOR:
        limit = 0.0
    else:
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        ceiling = LIMIT_CEILING_MEMORY if memory_backed else LIMIT_CEILING
        limit = min(
            _lognormal_quantile(filled.price_median, sigma, conditional),
            ceiling * filled.price_median,
            LIMIT_CAP,
        )
    limit = min(limit, charge)
    return Price(
        charge=round(max(charge, 0.0), 2),
        limit=round(max(limit, 0.0), 2),
        sigma=sigma,
        covered_probability=covered,
    )


def sanity_check(rows: list[Row]) -> list[str]:
    """`price_item_measured_sigma` fed the ORIGINAL band-implied sigma must reproduce
    `price_item`'s own output to the cent, for every row. Returns the failures (empty = ok)."""
    failures = []
    for row in rows:
        real = price_item(row.evidence, confirmed_uncovered=row.uncovered, memory_backed=row.has_memory)
        filled = row.evidence.with_defaults()
        band_sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
        reimpl = price_item_measured_sigma(
            row.evidence,
            confirmed_uncovered=row.uncovered,
            memory_backed=row.has_memory,
            sigma_override=band_sigma,
        )
        if abs(real.charge - reimpl.charge) > 0.01 or abs(real.limit - reimpl.limit) > 0.01:
            failures.append(
                f"G{row.game} #{row.index}: price_item={real.charge}/{real.limit} "
                f"reimpl={reimpl.charge}/{reimpl.limit}"
            )
    return failures


if __name__ == "__main__":
    from charge_buckets import dataset

    rows = dataset()
    failures = sanity_check(rows)
    print(f"sanity check over {len(rows)} rows: {len(failures)} mismatches")
    for f in failures[:10]:
        print(" ", f)
