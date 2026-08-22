import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.services.t_calc import _sanitize, encode_case_images


class FairValueCalculationTests(unittest.TestCase):
    def test_sanitize_computes_total_from_unit_price_and_quantity(self) -> None:
        estimate = _sanitize(
            1,
            {
                "unit_price": 80.0,
                "quantity": 5.0,
                "total_low": 300.0,
                "total_high": 500.0,
            },
        )

        self.assertEqual(estimate.line_item_index, 1)
        self.assertEqual(estimate.median, 400.0)
        self.assertEqual((estimate.lower, estimate.upper), (300.0, 500.0))

    def test_sanitize_clamps_total_to_price_band(self) -> None:
        estimate = _sanitize(
            2,
            {
                "unit_price": 900.0,
                "quantity": 1.0,
                "total_low": 380.0,
                "total_high": 430.0,
            },
        )

        self.assertEqual(estimate.median, 430.0)
        self.assertEqual((estimate.lower, estimate.upper), (380.0, 430.0))

    def test_encode_case_images_downscales_valid_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "damage.png"
            Image.new("RGB", (2048, 1200), color="red").save(image_path)

            encoded = encode_case_images((image_path,))

        self.assertEqual(len(encoded), 1)
        self.assertTrue(encoded[0])


if __name__ == "__main__":
    unittest.main()
