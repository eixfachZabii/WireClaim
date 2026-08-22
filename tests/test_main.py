import unittest
from pathlib import Path
from unittest.mock import patch

import main
from src.api import APIError


class MainTests(unittest.TestCase):
    @patch.object(main, "process_case")
    @patch.object(main, "extract_case", return_value=Path("var/cases/case_01"))
    @patch.object(main.time, "sleep")
    @patch.object(
        main,
        "get_decryption_key",
        side_effect=[APIError(403, "not ready"), "released-key"],
    )
    def test_handle_game_retries_then_triggers_processing(
        self, get_key, sleep, extract_case, process_case
    ) -> None:
        main.handle_game(1)

        self.assertEqual(get_key.call_count, 2)
        sleep.assert_called_once_with(0.5)
        extract_case.assert_called_once_with(1, "released-key")
        process_case.assert_called_once_with(1, Path("var/cases/case_01"))


if __name__ == "__main__":
    unittest.main()
