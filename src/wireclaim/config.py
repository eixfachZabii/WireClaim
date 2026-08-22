from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    base_url: str
    team_api_key: str | None
    archive_dir: Path
    runtime_dir: Path
    processor: str
    schedule_refresh_seconds: float
    key_retry_seconds: float
    game_duration_seconds: float
    seven_zip_executable: str

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> Settings:
        root = (project_root or Path.cwd()).resolve()

        def configured_path(name: str, default: str) -> Path:
            path = Path(os.environ.get(name, default))
            return path.resolve() if path.is_absolute() else (root / path).resolve()

        return cls(
            base_url=os.environ.get(
                "WIRECLAIM_BASE_URL", "https://c2f.public.quantco.cloud"
            ).rstrip("/"),
            team_api_key=os.environ.get("TEAM_API_KEY") or None,
            archive_dir=configured_path(
                "WIRECLAIM_ARCHIVE_DIR", "[PUBLIC] EHL Cases/cases"
            ),
            runtime_dir=configured_path("WIRECLAIM_RUNTIME_DIR", "var"),
            processor=os.environ.get(
                "WIRECLAIM_PROCESSOR",
                "wireclaim.pipeline.placeholder:process_case",
            ),
            schedule_refresh_seconds=_positive_float(
                "WIRECLAIM_SCHEDULE_REFRESH_SECONDS", 15.0
            ),
            key_retry_seconds=_positive_float("WIRECLAIM_KEY_RETRY_SECONDS", 10.0),
            game_duration_seconds=_positive_float(
                "WIRECLAIM_GAME_DURATION_SECONDS", 60.0
            ),
            seven_zip_executable=os.environ.get("WIRECLAIM_7Z_EXECUTABLE", "7z"),
        )

