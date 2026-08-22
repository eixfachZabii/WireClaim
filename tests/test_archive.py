from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from wireclaim.cases.archive import ArchiveExtractor, ExtractionError
from wireclaim.cases.repository import CaseRepository


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CASES = REPOSITORY_ROOT / "[PUBLIC] EHL Cases" / "cases"


class ArchiveExtractorTests(unittest.TestCase):
    def test_extracts_atomically_and_reuses_verified_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archives = root / "archives"
            archives.mkdir()
            shutil.copy2(PUBLIC_CASES / "case_00.zip", archives / "case_00.zip")
            calls: list[list[str]] = []

            def fake_7z(command, **kwargs):
                calls.append(command)
                output = Path(next(arg[2:] for arg in command if arg.startswith("-o")))
                for source in (PUBLIC_CASES / "case_00").iterdir():
                    shutil.copy2(source, output / source.name)
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            extractor = ArchiveExtractor(
                CaseRepository(archives, root / "runtime"), command_runner=fake_7z
            )
            first = extractor.extract(0, "decryption-key")
            second = extractor.extract(0, "different-key-is-not-used")

            self.assertEqual(first, second)
            self.assertEqual(len(calls), 1)
            self.assertTrue(first.policy_path.is_file())
            self.assertTrue(first.description_path.is_file())
            self.assertTrue(first.invoices_path.is_file())
            self.assertTrue(first.manifest_path.is_file())
            self.assertFalse(
                list((root / "runtime" / "cases").glob("*.extracting"))
            )

    def test_rejects_traversal_before_running_7z(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archives = root / "archives"
            archives.mkdir()
            with ZipFile(archives / "case_01.zip", "w") as archive:
                archive.writestr("../escape.txt", "bad")
            extractor = ArchiveExtractor(CaseRepository(archives, root / "runtime"))

            with self.assertRaisesRegex(ExtractionError, "unsafe archive member"):
                extractor.extract(1, "key")

    def test_refuses_to_overwrite_tampered_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archives = root / "archives"
            archives.mkdir()
            shutil.copy2(PUBLIC_CASES / "case_00.zip", archives / "case_00.zip")

            def fake_7z(command, **kwargs):
                output = Path(next(arg[2:] for arg in command if arg.startswith("-o")))
                for source in (PUBLIC_CASES / "case_00").iterdir():
                    shutil.copy2(source, output / source.name)
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            extractor = ArchiveExtractor(
                CaseRepository(archives, root / "runtime"), command_runner=fake_7z
            )
            extracted = extractor.extract(0, "key")
            extracted.policy_path.write_text("tampered", encoding="utf-8")

            with self.assertRaisesRegex(ExtractionError, "refusing to replace"):
                extractor.extract(0, "key")


if __name__ == "__main__":
    unittest.main()
