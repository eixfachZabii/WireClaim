import tempfile
import unittest
from pathlib import Path

from src.data.case_loader import find_image_paths, parse_invoice_text


class CaseLoaderTests(unittest.TestCase):
    def test_discovers_all_supported_case_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case_dir = Path(directory)
            for name in ("damage.png", "overview.JPG", "receipt.webp", "notes.txt", "scan.gif"):
                (case_dir / name).write_bytes(b"data")

            image_names = [path.name for path in find_image_paths(case_dir)]

        self.assertEqual(image_names, ["damage.png", "overview.JPG", "receipt.webp"])


    def test_parser_ignores_invoice_year_and_reads_position_rows(self) -> None:
        line_items = parse_invoice_text(
            "INVOICE 2026\n"
            "POS. DESCRIPTION\n"
            "1 Leak detection 14 hrs\n"
            "2 Technician call-out 3 pcs\n"
            "Created on 2026-08-22\n"
        )

        self.assertEqual([item.index for item in line_items], [1, 2])
        self.assertEqual([item.quantity for item in line_items], [14.0, 3.0])
        self.assertNotIn(2026, [item.index for item in line_items])


if __name__ == "__main__":
    unittest.main()
