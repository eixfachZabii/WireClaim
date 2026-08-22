import io
import os
import unittest
from unittest.mock import patch

from src import api


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class APITests(unittest.TestCase):
    def test_list_games(self) -> None:
        response = Response(b'[{"id": 1, "start_time": "2026-08-22T12:00:00Z"}]')
        with patch.dict(os.environ, {"TEAM_API_KEY": "test-key"}), patch.object(
            api, "urlopen", return_value=response
        ):
            self.assertEqual(api.list_games()[0]["id"], 1)

    def test_key(self) -> None:
        response = Response(b'{"decryption_key": "released"}')
        with patch.dict(os.environ, {"TEAM_API_KEY": "test-key"}), patch.object(
            api, "urlopen", return_value=response
        ):
            self.assertEqual(api.get_decryption_key(7), "released")

    def test_missing_team_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            api.list_games()

    def test_submission_is_not_implemented(self) -> None:
        self.assertFalse(hasattr(api, "submit_price"))


if __name__ == "__main__":
    unittest.main()
