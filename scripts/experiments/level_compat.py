"""One import surface for the `level_*` harnesses, stable across Strategy 2's refactors.

Strategy 2 was a single module and is now six (`constants`, `prompts`, `channels`, `model`,
`blend`, `strategy`). Both layouts existed inside one session, and a sweep that was running
across the change died on `AttributeError: no attribute '_blend'`. Measurements have to
outlive a refactor of the thing they measure, so every name the harnesses need is resolved
here, new layout first and the old private names as a fallback.

It also deliberately does **not** import `tail_replay`, so a broken import anywhere in the
older harness cannot take the level measurements down with it.
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.case_loader import read_case  # noqa: E402
from src.data.models import CaseData  # noqa: E402
from src.pricing import Evidence  # noqa: E402

INF = math.inf
CASES = Path("[PUBLIC] EHL Cases/cases")
EVIDENCE = Path("var/evidence")

_s2 = __import__(
    "src.services.strategies.strategy2.strategy", fromlist=["strategy"]
)


def _resolve(module: str, new: str, old: str):
    """The new module-level name if the refactor landed, else the old private one."""
    try:
        loaded = __import__(f"src.services.strategies.strategy2.{module}", fromlist=[module])
        if hasattr(loaded, new):
            return getattr(loaded, new)
    except ImportError:
        pass
    return getattr(_s2, old)


blend = _resolve("blend", "blend", "_blend")
sigma_of = _resolve("blend", "sigma_of", "_sigma_of")
combine = _resolve("blend", "combine", "_combine")
local_evidence = _resolve("channels", "local_evidence", "_memory_evidence")
unit_of = _resolve("channels", "unit_of", "_unit_of")
request_evidence = _resolve("model", "request_evidence", "_request_evidence")
PROMPT = _resolve("prompts", "PROMPT", "PROMPT")
PROMPT_UNANCHORED = _resolve("prompts", "PROMPT_UNANCHORED", "PROMPT_UNANCHORED")
SETTLED_MEDIAN = _resolve("constants", "SETTLED_MEDIAN", "SETTLED_MEDIAN")
BAND_Z = _resolve("constants", "BAND_Z", "BAND_Z")
build_proposal = _s2.build_proposal


def set_model_sigma_prior(value: float) -> None:
    """Rebind `MODEL_SIGMA_PRIOR` everywhere it is read.

    `blend.py` does `from ... constants import MODEL_SIGMA_PRIOR`, so it holds its own
    reference and patching `constants` alone silently does nothing -- the first sweep of this
    constant after the refactor reported six identical totals, which is how the from-import
    was noticed. Every module that names it has to be rebound.
    """
    for module in ("constants", "blend", "channels", "model", "strategy"):
        try:
            loaded = __import__(
                f"src.services.strategies.strategy2.{module}", fromlist=[module]
            )
        except ImportError:  # pragma: no cover - pre-refactor layout
            continue
        if hasattr(loaded, "MODEL_SIGMA_PRIOR"):
            loaded.MODEL_SIGMA_PRIOR = value
    if hasattr(_s2, "MODEL_SIGMA_PRIOR"):
        _s2.MODEL_SIGMA_PRIOR = value


def model_sigma_prior() -> float:
    loaded = __import__(
        "src.services.strategies.strategy2.constants", fromlist=["constants"]
    )
    return loaded.MODEL_SIGMA_PRIOR


# ------------------------------------------------------------------------------- loading


def parse_games(spec: str) -> list[int]:
    """`1-14`, `10`, or `1-15,17-24`."""
    games: list[int] = []
    for part in spec.split(","):
        start, _, end = part.strip().partition("-")
        games += list(range(int(start), int(end or start) + 1))
    return games


def case_of(game_id: int) -> CaseData | None:
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return None
    return asyncio.run(read_case(game_id, case_dir))


def load_evidence(game_id: int, tag: str = "model") -> dict[int, Evidence] | None:
    path = EVIDENCE / f"case_{game_id:02d}_{tag}.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    return {int(i): Evidence(index=int(i), **values) for i, values in raw.items()}


def dump_evidence(game_id: int, tag: str, evidence: dict[int, Evidence]) -> Path:
    path = EVIDENCE / f"case_{game_id:02d}_{tag}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                str(index): {
                    "coverage_probability": item.coverage_probability,
                    "price_low": item.price_low,
                    "price_median": item.price_median,
                    "price_high": item.price_high,
                }
                for index, item in evidence.items()
            },
            indent=2,
        )
    )
    return path


def channel_a_only(case: CaseData) -> dict[int, Evidence]:
    """Channel A (dash-quantity Line Items) without the leaking Price Memory."""
    return {
        item.index: Evidence(
            index=item.index,
            coverage_probability=0.0,
            price_low=SETTLED_MEDIAN * 0.5,
            price_median=SETTLED_MEDIAN,
            price_high=SETTLED_MEDIAN * 2,
        )
        for item in case.line_items
        if getattr(item, "quantity_missing", False)
    }


def submission_of(
    case: CaseData, model: dict[int, Evidence], *, memory: bool = False
) -> dict[int, tuple[float, float]]:
    """The shipped code path from evidence to `(Charge, Limit)` per Line Item."""
    memory_evidence = local_evidence(case) if memory else channel_a_only(case)
    proposal = build_proposal(case, model, memory_evidence)
    if proposal is None:
        return {}
    return {p.index: (p.charge_price, p.acceptance_limit) for p in proposal.prices}


def inflate(snap, factor: float):
    """Raise the Line Items with no upper bracket to `factor * t_lo`: the censoring check."""
    if factor == 1.0:
        return snap
    return replace(
        snap,
        fair_brackets={
            index: ((lo * factor, hi) if hi == INF and lo > 0 else (lo, hi))
            for index, (lo, hi) in snap.fair_brackets.items()
        },
    )
