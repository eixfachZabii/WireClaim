from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def case_name(game_id: int) -> str:
    if game_id < 0:
        raise ValueError("game_id must be nonnegative")
    return f"case_{game_id:02d}"


@dataclass(frozen=True, slots=True)
class CaseRepository:
    archive_dir: Path
    runtime_dir: Path

    @property
    def cases_dir(self) -> Path:
        return self.runtime_dir / "cases"

    def archive_path(self, game_id: int) -> Path:
        return self.archive_dir / f"{case_name(game_id)}.zip"

    def case_dir(self, game_id: int) -> Path:
        return self.cases_dir / case_name(game_id)

