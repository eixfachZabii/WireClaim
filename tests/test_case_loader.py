import tempfile
import unittest
from pathlib import Path

from src.data.case_loader import find_image_paths


class CaseLoaderTests(unittest.TestCase):
    def test_discovers_all_supported_case_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case_dir = Path(directory)
            for name in ("damage.png", "overview.JPG", "receipt.webp", "notes.txt", "scan.gif"):
                (case_dir / name).write_bytes(b"data")

            image_names = [path.name for path in find_image_paths(case_dir)]

        self.assertEqual(image_names, ["damage.png", "overview.JPG", "receipt.webp"])


if __name__ == "__main__":
    unittest.main()
