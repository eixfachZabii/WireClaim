from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CaseReady:
    game_id: int
    start_time: datetime
    deadline: datetime
    case_dir: Path
    input_dir: Path
    policy_path: Path
    description_path: Path
    invoices_path: Path
    image_paths: tuple[Path, ...]
    manifest_path: Path

