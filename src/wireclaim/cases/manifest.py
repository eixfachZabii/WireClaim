from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_VERSION = 1


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    *, game_id: int, archive_path: Path, archive_sha256: str, input_dir: Path
) -> dict[str, Any]:
    files = []
    for path in sorted(input_dir.rglob("*")):
        if path.is_file():
            files.append(
                {
                    "path": path.relative_to(input_dir.parent).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return {
        "version": MANIFEST_VERSION,
        "game_id": game_id,
        "archive_name": archive_path.name,
        "archive_sha256": archive_sha256,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    return payload
