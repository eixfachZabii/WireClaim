"""Versioned experiment specification parsing and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from backtesting.paths import SPEC_SCHEMA_VERSION


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    entrypoint: str | None = None
    submissions: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)
    allow_missing: bool = False


@dataclass(frozen=True)
class SweepSpec:
    candidate: str
    grid: Mapping[str, tuple[Any, ...]]
    objective: str = "midpoint_net"


@dataclass(frozen=True)
class ExperimentSpec:
    version: int
    name: str
    games: str = "all"
    seat: str = "Bin busy"
    draws: int = 3
    timeout_seconds: float = 60.0
    cap_mode: str = "fitted"
    include_game_0: bool = False
    seed: int = 20260822
    tracks: tuple[str, ...] = ("strategy1", "strategy2", "strategy3", "fast_path")
    candidates: tuple[CandidateSpec, ...] = ()
    sweeps: tuple[SweepSpec, ...] = ()
    holdout_fraction: float = 0.3
    walk_forward_min_train: int = 5
    walk_forward_step: int = 1
    regimes: tuple[tuple[str, int, int], ...] = (
        ("awake", 1, 43),
        ("dark", 44, 81),
        ("recalibrated", 82, 100),
    )


def load_spec(path: str | Path) -> ExperimentSpec:
    raw = json.loads(Path(path).read_text())
    version = int(raw.get("version", 1))
    if version != SPEC_SCHEMA_VERSION:
        raise ValueError(f"unsupported experiment spec version {version}")
    candidates = tuple(
        CandidateSpec(
            name=value["name"],
            entrypoint=value.get("entrypoint"),
            submissions=value.get("submissions"),
            params=dict(value.get("params", {})),
            allow_missing=bool(value.get("allow_missing", False)),
        )
        for value in raw.get("candidates", ())
    )
    for candidate in candidates:
        if bool(candidate.entrypoint) == bool(candidate.submissions):
            raise ValueError(f"candidate {candidate.name!r} needs exactly one input interface")
    sweeps = tuple(
        SweepSpec(
            candidate=value["candidate"],
            grid={key: tuple(items) for key, items in value["grid"].items()},
            objective=value.get("objective", "midpoint_net"),
        )
        for value in raw.get("sweeps", ())
    )
    empty_axes = [
        f"{sweep.candidate}.{key}"
        for sweep in sweeps
        for key, values in sweep.grid.items()
        if not values
    ]
    if empty_axes:
        raise ValueError(f"sweep axes have no values: {empty_axes}")
    names = {candidate.name for candidate in candidates}
    unknown = [sweep.candidate for sweep in sweeps if sweep.candidate not in names]
    if unknown:
        raise ValueError(f"sweeps reference unknown candidates {unknown}")
    validation = raw.get("validation", {})
    spec = ExperimentSpec(
        version=version,
        name=raw.get("name", Path(path).stem),
        games=raw.get("games", "all"),
        seat=raw.get("seat", "Bin busy"),
        draws=int(raw.get("draws", 3)),
        timeout_seconds=float(raw.get("timeout_seconds", 60.0)),
        cap_mode=raw.get("cap_mode", "fitted"),
        include_game_0=bool(raw.get("include_game_0", False)),
        seed=int(raw.get("seed", 20260822)),
        tracks=tuple(raw.get("tracks", ("strategy1", "strategy2", "strategy3", "fast_path"))),
        candidates=candidates,
        sweeps=sweeps,
        holdout_fraction=float(validation.get("holdout_fraction", 0.3)),
        walk_forward_min_train=int(validation.get("walk_forward_min_train", 5)),
        walk_forward_step=int(validation.get("walk_forward_step", 1)),
        regimes=tuple(
            (str(value["name"]), int(value["start"]), int(value["end"]))
            for value in raw.get(
                "regimes",
                (
                    {"name": "awake", "start": 1, "end": 43},
                    {"name": "dark", "start": 44, "end": 81},
                    {"name": "recalibrated", "start": 82, "end": 100},
                ),
            )
        ),
    )
    if spec.draws < 1 or not 0 < spec.holdout_fraction < 1:
        raise ValueError("draws must be positive and holdout_fraction must be inside (0, 1)")
    if spec.walk_forward_min_train < 1 or spec.walk_forward_step < 1:
        raise ValueError("walk-forward minimum training Games and step must be positive")
    if spec.cap_mode not in {"fitted", "rules_only"}:
        raise ValueError("cap_mode must be fitted or rules_only")
    return spec
