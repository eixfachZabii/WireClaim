from __future__ import annotations

import unittest

from api.client import EHLClient
from api.models import ForbiddenError


class FakeResponse:
    def __init__(self, status_code: int, payload, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class FakeTransport:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, object, dict[str, str]]] = []

    def get(self, url: str, *, headers, timeout):
        self.calls.append((url, timeout, dict(headers)))
        return self.responses.pop(0)


class EHLClientTests(unittest.TestCase):
    def test_lists_games_in_utc_start_order(self) -> None:
        transport = FakeTransport(
            [
                FakeResponse(
                    200,
                    [
                        {"id": 2, "start_time": "2026-08-22T12:05:00Z"},
                        {"id": 1, "start_time": "2026-08-22T14:00:00+02:00"},
                    ],
                )
            ]
        )
        client = EHLClient(
            base_url="https://example.test/", api_key="secret", transport=transport
        )

        games = client.list_games()

        self.assertEqual([game.id for game in games], [1, 2])
        self.assertEqual(games[0].start_time.isoformat(), "2026-08-22T12:00:00+00:00")
        self.assertEqual(transport.calls[0][2]["X-API-Key"], "secret")
        self.assertEqual(transport.calls[0][0], "https://example.test/api/games/list")

    def test_gets_key_without_exposing_it_in_object_representation(self) -> None:
        transport = FakeTransport([FakeResponse(200, {"decryption_key": "case-key"})])
        client = EHLClient(
            base_url="https://example.test", api_key="team-key", transport=transport
        )

        self.assertEqual(client.get_decryption_key(7), "case-key")
        self.assertNotIn("team-key", repr(client))

    def test_maps_key_403_to_forbidden(self) -> None:
        transport = FakeTransport([FakeResponse(403, {}, "not started")])
        client = EHLClient(
            base_url="https://example.test", api_key="secret", transport=transport
        )

        with self.assertRaises(ForbiddenError):
            client.get_decryption_key(7)


if __name__ == "__main__":
    unittest.main()
