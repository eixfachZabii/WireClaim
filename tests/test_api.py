import io
import os
import unittest
from unittest.mock import patch

from src import api
from src.api.llm import DEFAULT_MODEL, DEFAULT_SERVICE_TIER, get_model_name, get_service_tier, warm_llm_resources


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class APITests(unittest.TestCase):
    def test_default_model_is_gpt_5_6_terra(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_model_name(), "gpt-5.6-terra")
            self.assertEqual(DEFAULT_MODEL, "gpt-5.6-terra")

    def test_model_environment_override_wins(self) -> None:
        with patch.dict(os.environ, {"AZURE_OPENAI_MODEL": "custom-deployment"}, clear=True):
            self.assertEqual(get_model_name(), "custom-deployment")

    def test_default_service_tier_is_fast(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_service_tier(), "fast")
            self.assertEqual(DEFAULT_SERVICE_TIER, "fast")

    def test_service_tier_environment_override_wins(self) -> None:
        with patch.dict(os.environ, {"AZURE_OPENAI_SERVICE_TIER": "priority"}, clear=True):
            self.assertEqual(get_service_tier(), "priority")

    def test_warm_llm_resources(self) -> None:
        warm_llm_resources()

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

    def test_submit_price(self) -> None:
        response = Response(
            b'[{"game_id": 1, "team_id": 3, "line_item_index": 1, "charge_price": 50.0, "acceptance_limit": 80.0, "submitted_at": "2026-08-22T12:00:00Z"}]'
        )
        with patch.dict(os.environ, {"TEAM_API_KEY": "test-key"}), patch.object(
            api, "urlopen", return_value=response
        ):
            result = api.submit_price(1, 50.0, 80.0)
            self.assertEqual(result["charge_price"], 50.0)
            self.assertEqual(result["acceptance_limit"], 80.0)


if __name__ == "__main__":
    unittest.main()
