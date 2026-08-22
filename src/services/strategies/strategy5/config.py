from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).with_name("config.json")
DEFAULT_MODELS = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.4-mini")
ZERO_LIMIT_VIOLATION_THRESHOLD = 1.0 / 3.0


@dataclass(frozen=True)
class Strategy5Config:
    models: tuple[str, ...] = DEFAULT_MODELS
    coverage_model: str = "gpt-5.6-terra"
    zero_limit_violation_threshold: float = 1.0 / 3.0
    default_policy_violation_probability: float = 0.1
    alpha_factor: float = 1.0
    beta_factor: float = 1.0
    factor_step: float = 0.1
    factor_min: float = 0.5
    factor_max: float = 1.5
    minimum_calibration_games: int = 8
    noise_floor_18_games: float = 26_622.0


def _finite(value: Any, name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{name} must be finite")
    return parsed


def _probability(value: Any, name: str) -> float:
    parsed = _finite(value, name)
    if not 0.0 <= parsed <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return parsed


def load_config(path: Path = CONFIG_PATH) -> Strategy5Config:
    payload = json.loads(path.read_text(encoding="utf-8"))
    models = tuple(str(model).strip() for model in payload.get("models", DEFAULT_MODELS))
    if len(models) != 3 or any(not model for model in models):
        raise ValueError("Strategy 5 requires exactly three non-empty model names")
    zero_limit_threshold = _probability(
        payload.get("zero_limit_violation_threshold", ZERO_LIMIT_VIOLATION_THRESHOLD),
        "zero_limit_violation_threshold",
    )
    if not math.isclose(zero_limit_threshold, ZERO_LIMIT_VIOLATION_THRESHOLD):
        raise ValueError("zero_limit_violation_threshold is derived and cannot be tuned")
    factor_min = _finite(payload.get("factor_min", 0.5), "factor_min")
    factor_max = _finite(payload.get("factor_max", 1.5), "factor_max")
    if factor_min <= 0 or factor_max < factor_min:
        raise ValueError("Strategy 5 factor bounds are invalid")
    alpha = _finite(payload.get("ALPHA_FAC", 1.0), "ALPHA_FAC")
    beta = _finite(payload.get("BETA_FAC", 1.0), "BETA_FAC")
    if not factor_min <= alpha <= factor_max or not factor_min <= beta <= factor_max:
        raise ValueError("Strategy 5 factors must stay inside their configured bounds")
    return Strategy5Config(
        models=models,
        coverage_model=str(payload.get("coverage_model", "gpt-5.6-terra")).strip(),
        zero_limit_violation_threshold=zero_limit_threshold,
        default_policy_violation_probability=_probability(
            payload.get("default_policy_violation_probability", 0.1),
            "default_policy_violation_probability",
        ),
        alpha_factor=alpha,
        beta_factor=beta,
        factor_step=_probability(payload.get("factor_step", 0.1), "factor_step"),
        factor_min=factor_min,
        factor_max=factor_max,
        minimum_calibration_games=max(int(payload.get("minimum_calibration_games", 8)), 1),
        noise_floor_18_games=max(
            _finite(payload.get("noise_floor_18_games", 26_622.0), "noise_floor_18_games"),
            0.0,
        ),
    )


def save_factors(
    alpha_factor: float,
    beta_factor: float,
    path: Path = CONFIG_PATH,
) -> Strategy5Config:
    current = load_config(path)
    alpha = min(max(_finite(alpha_factor, "ALPHA_FAC"), current.factor_min), current.factor_max)
    beta = min(max(_finite(beta_factor, "BETA_FAC"), current.factor_min), current.factor_max)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["ALPHA_FAC"] = round(alpha, 10)
    payload["BETA_FAC"] = round(beta, 10)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return replace(current, alpha_factor=alpha, beta_factor=beta)


__all__ = [
    "CONFIG_PATH",
    "DEFAULT_MODELS",
    "Strategy5Config",
    "ZERO_LIMIT_VIOLATION_THRESHOLD",
    "load_config",
    "save_factors",
]
