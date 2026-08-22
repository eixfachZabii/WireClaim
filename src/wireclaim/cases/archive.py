from __future__ import annotations

import logging
import shutil
import stat
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

from wireclaim.cases.manifest import (
    MANIFEST_VERSION,
    build_manifest,
    load_manifest,
    sha256_file,
    write_manifest,
)
from wireclaim.cases.repository import CaseRepository, case_name

LOGGER = logging.getLogger(__name__)
REQUIRED_FILES = frozenset({"policy.txt", "description.txt", "invoices.pdf"})
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})


class ExtractionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExtractedCase:
    game_id: int
    case_dir: Path
    input_dir: Path
    manifest_path: Path
    policy_path: Path
    description_path: Path
    invoices_path: Path
    image_paths: tuple[Path, ...]


CommandRunner = Callable[..., Any]


class ArchiveExtractor:
    def __init__(
        self,
        repository: CaseRepository,
        *,
        seven_zip_executable: str = "7z",
        command_runner: CommandRunner = subprocess.run,
    ) -> None:
        self._repository = repository
        self._seven_zip = seven_zip_executable
        self._run_command = command_runner

    def extract(self, game_id: int, decryption_key: str) -> ExtractedCase:
        if not decryption_key:
            raise ValueError("decryption key must not be empty")
        archive_path = self._repository.archive_path(game_id)
        if not archive_path.is_file():
            raise ExtractionError(f"archive not found: {archive_path}")

        declared_files = self._inspect_archive(archive_path)
        archive_sha256 = sha256_file(archive_path)
        final_dir = self._repository.case_dir(game_id)
        existing = self._load_valid_existing(
            game_id=game_id,
            case_dir=final_dir,
            archive_sha256=archive_sha256,
        )
        if existing is not None:
            LOGGER.info("game %s is already extracted and verified", game_id)
            return existing
        if final_dir.exists():
            raise ExtractionError(
                f"refusing to replace unverified existing case directory: {final_dir}"
            )

        cases_dir = self._repository.cases_dir
        cases_dir.mkdir(parents=True, exist_ok=True)
        staging_dir = cases_dir / f".{case_name(game_id)}-{uuid.uuid4().hex}.extracting"
        input_dir = staging_dir / "input"
        input_dir.mkdir(parents=True)

        try:
            command = [
                self._seven_zip,
                "x",
                "-y",
                f"-p{decryption_key}",
                f"-o{input_dir}",
                str(archive_path),
            ]
            try:
                result = self._run_command(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise ExtractionError(
                    f"7-Zip executable not found: {self._seven_zip!r}"
                ) from exc
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "unknown 7-Zip error").strip()
                raise ExtractionError(f"decrypting {archive_path.name} failed: {detail[:1000]}")

            self._validate_extracted(input_dir, declared_files)
            manifest = build_manifest(
                game_id=game_id,
                archive_path=archive_path,
                archive_sha256=archive_sha256,
                input_dir=input_dir,
            )
            write_manifest(staging_dir / "manifest.json", manifest)
            staging_dir.rename(final_dir)
        except Exception:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            raise

        extracted = self._case_from_directory(game_id, final_dir)
        LOGGER.info("extracted and verified game %s into %s", game_id, final_dir)
        return extracted

    def load_existing(self, game_id: int) -> ExtractedCase:
        case_dir = self._repository.case_dir(game_id)
        archive_path = self._repository.archive_path(game_id)
        archive_sha = sha256_file(archive_path) if archive_path.is_file() else None
        existing = self._load_valid_existing(
            game_id=game_id, case_dir=case_dir, archive_sha256=archive_sha
        )
        if existing is None:
            raise ExtractionError(f"game {game_id} has no valid extracted case")
        return existing

    @staticmethod
    def _inspect_archive(archive_path: Path) -> set[str]:
        try:
            with ZipFile(archive_path) as archive:
                infos = archive.infolist()
        except BadZipFile as exc:
            raise ExtractionError(f"invalid ZIP archive: {archive_path}") from exc
        if not infos:
            raise ExtractionError(f"empty ZIP archive: {archive_path}")

        names: set[str] = set()
        for info in infos:
            normalized = info.filename.replace("\\", "/")
            path = PurePosixPath(normalized)
            mode = info.external_attr >> 16
            unsafe = (
                not normalized
                or "\x00" in normalized
                or path.is_absolute()
                or ".." in path.parts
                or (path.parts and ":" in path.parts[0])
                or stat.S_ISLNK(mode)
            )
            if unsafe:
                raise ExtractionError(f"unsafe archive member: {info.filename!r}")
            if info.is_dir():
                continue
            if not (info.flag_bits & 0x1) or info.compress_type != 99:
                raise ExtractionError(
                    f"archive member is not AES encrypted: {info.filename!r}"
                )
            names.add(path.as_posix())

        missing = REQUIRED_FILES - names
        if missing:
            raise ExtractionError(
                f"archive is missing required files: {', '.join(sorted(missing))}"
            )
        return names

    @staticmethod
    def _validate_extracted(input_dir: Path, declared_files: set[str]) -> None:
        actual_files = {
            path.relative_to(input_dir).as_posix()
            for path in input_dir.rglob("*")
            if path.is_file()
        }
        if actual_files != declared_files:
            missing = sorted(declared_files - actual_files)
            extra = sorted(actual_files - declared_files)
            raise ExtractionError(
                f"extracted files do not match archive; missing={missing}, extra={extra}"
            )
        for path in input_dir.rglob("*"):
            if path.is_symlink():
                raise ExtractionError(f"extraction produced a symlink: {path}")

    def _load_valid_existing(
        self, *, game_id: int, case_dir: Path, archive_sha256: str | None
    ) -> ExtractedCase | None:
        manifest_path = case_dir / "manifest.json"
        input_dir = case_dir / "input"
        if not manifest_path.is_file() or not input_dir.is_dir():
            return None
        try:
            manifest = load_manifest(manifest_path)
            if manifest.get("version") != MANIFEST_VERSION:
                return None
            if manifest.get("game_id") != game_id:
                return None
            if archive_sha256 and manifest.get("archive_sha256") != archive_sha256:
                return None
            files = manifest.get("files")
            if not isinstance(files, list) or not files:
                return None
            for item in files:
                if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                    return None
                relative = PurePosixPath(item["path"])
                if relative.is_absolute() or ".." in relative.parts:
                    return None
                path = case_dir.joinpath(*relative.parts)
                if not path.is_file() or path.is_symlink():
                    return None
                if path.stat().st_size != item.get("size"):
                    return None
                if sha256_file(path) != item.get("sha256"):
                    return None
            return self._case_from_directory(game_id, case_dir)
        except (OSError, ValueError, TypeError):
            return None

    @staticmethod
    def _case_from_directory(game_id: int, case_dir: Path) -> ExtractedCase:
        input_dir = case_dir / "input"
        required = {name: input_dir / name for name in REQUIRED_FILES}
        missing = [name for name, path in required.items() if not path.is_file()]
        if missing:
            raise ExtractionError(
                f"extracted case is missing required files: {', '.join(sorted(missing))}"
            )
        images = tuple(
            sorted(
                path
                for path in input_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
            )
        )
        return ExtractedCase(
            game_id=game_id,
            case_dir=case_dir,
            input_dir=input_dir,
            manifest_path=case_dir / "manifest.json",
            policy_path=required["policy.txt"],
            description_path=required["description.txt"],
            invoices_path=required["invoices.pdf"],
            image_paths=images,
        )

