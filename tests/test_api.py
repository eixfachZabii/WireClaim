import io
import os
import unittest
from unittest.mock import MagicMock, patch

from src import api
from src.api.llm import (
    DEFAULT_MODEL,
    DEFAULT_SERVICE_TIER,
    get_model_name,
    get_service_tier,
    query_llm,
    warm_llm_resources,
)


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

    def test_default_service_tier_is_priority(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_service_tier(), "priority")
            self.assertEqual(DEFAULT_SERVICE_TIER, "priority")

    def test_service_tier_environment_override_wins(self) -> None:
        with patch.dict(os.environ, {"AZURE_OPENAI_SERVICE_TIER": "priority"}, clear=True):
            self.assertEqual(get_service_tier(), "priority")

    def test_query_llm_forwards_priority_tier_to_responses_api(self) -> None:
        client = MagicMock()
        client.responses.create.return_value.output_text = "response"
        with patch.dict(os.environ, {}, clear=True), patch("src.api.llm.get_llm_client", return_value=client):
            self.assertEqual(query_llm("prompt"), "response")
        client.responses.create.assert_called_once_with(
            model=DEFAULT_MODEL,
            service_tier="priority",
            input="prompt",
        )

    def test_query_llm_forwards_priority_tier_to_chat_api(self) -> None:
        client = MagicMock()
        client.responses = None
        client.chat.completions.create.return_value.choices[0].message.content = "response"
        with patch.dict(os.environ, {}, clear=True), patch("src.api.llm.get_llm_client", return_value=client):
            self.assertEqual(query_llm("prompt"), "response")
        client.chat.completions.create.assert_called_once_with(
            model=DEFAULT_MODEL,
            service_tier="priority",
            messages=[{"role": "user", "content": "prompt"}],
        )

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

    def test_keys_use_base_url_and_submissions_use_backend_url(self) -> None:
        environment = {
            "TEAM_API_KEY": "test-key",
            "BASE_URL": "https://keys.example.test/",
            "BACKEND_URL": "10.183.176.119",
        }
        with patch.dict(os.environ, environment, clear=True), patch.object(
            api,
            "urlopen",
            return_value=Response(b'{"decryption_key": "released"}'),
        ) as key_request:
            self.assertEqual(api.get_decryption_key(7), "released")
        with patch.dict(os.environ, environment, clear=True), patch.object(
            api,
            "urlopen",
            return_value=Response(b'[{"charge_price": 50.0}]'),
        ) as submission_request:
            api.submit_price(7, 50.0, 80.0)

        self.assertEqual(
            key_request.call_args.args[0].full_url,
            "https://keys.example.test/api/games/7/key",
        )
        self.assertEqual(
            submission_request.call_args.args[0].full_url,
            "http://10.183.176.119/api/games/7/submissions",
        )

    def test_network_log_contains_method_and_destination_without_secrets_or_payload(self) -> None:
        environment = {
            "TEAM_API_KEY": "secret-test-key",
            "BASE_URL": "https://keys.example.test",
            "BACKEND_URL": "10.183.176.119:8765",
        }
        with self.assertLogs("src.api.tournament", level="INFO") as logs, patch.dict(
            os.environ, environment, clear=True
        ):
            with patch.object(
                api,
                "urlopen",
                return_value=Response(b'{"decryption_key": "released"}'),
            ):
                api.get_decryption_key(7)
            with patch.object(
                api,
                "urlopen",
                return_value=Response(b'[{"charge_price": 50.0}]'),
            ):
                api.submit_price(7, 50.0, 80.0)

        output = "\n".join(logs.output)
        self.assertIn(
            "network_request method=GET destination=https://keys.example.test/api/games/7/key",
            output,
        )
        self.assertIn(
            "network_request method=PUT destination=http://10.183.176.119:8765/api/games/7/submissions",
            output,
        )
        self.assertNotIn("secret-test-key", output)
        self.assertNotIn("acceptance_limit", output)

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
