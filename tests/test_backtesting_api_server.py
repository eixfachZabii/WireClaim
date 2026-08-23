import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from backtesting.api_server import BacktestAPIHandler, BacktestTournament, _result_line
from backtesting.models import (
    CapEstimate,
    ChargeEstimate,
    FairValueEstimate,
    HistoricalDataset,
    HistoricalGame,
    HistoricalItem,
    Interval,
    LimitEstimate,
    TeamDecision,
    Transaction,
)
from http.server import ThreadingHTTPServer
from src.api.tournament import get_decryption_key, list_games, submit_prices


class BacktestingAPIServerTests(unittest.TestCase):
    def setUp(self) -> None:
        decisions = {
            "Bin busy": TeamDecision(
                "Bin busy",
                ChargeEstimate(Interval.point(100), "exact"),
                LimitEstimate(Interval.point(100)),
            ),
            "Other": TeamDecision(
                "Other",
                ChargeEstimate(Interval.point(100), "exact"),
                LimitEstimate(Interval.point(100)),
            ),
        }
        item = HistoricalItem(
            1,
            FairValueEstimate(Interval.point(100)),
            CapEstimate(2000),
            decisions,
        )
        transactions = (
            Transaction(1, 1, "Bin busy", "Other", True, 100, ("Bin busy", "Other")),
            Transaction(1, 1, "Other", "Bin busy", True, 100, ("Bin busy", "Other")),
        )
        game = HistoricalGame(
            1,
            ("Bin busy", "Other"),
            {1: item},
            transactions,
            {"Bin busy": 0.0, "Other": 0.0},
        )
        self.dataset = HistoricalDataset(
            1,
            "dataset",
            "now",
            {1: game},
            ("Bin busy", "Other"),
        )

    def test_live_client_functions_work_by_changing_only_the_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tournament = BacktestTournament(
                self.dataset,
                [1],
                release_delay=-1,
                state_dir=Path(directory),
            )
            handler = type("TestBacktestHandler", (BacktestAPIHandler,), {"tournament": tournament})
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            try:
                with patch("backtesting.api_server.get_decryption_key", return_value="secret-key"):
                    games = list_games(api_key="test", base_url=base_url)
                    key = get_decryption_key(1, api_key="test", base_url=base_url)
                response = submit_prices(
                    1,
                    [{"index": 1, "charge_price": 100, "acceptance_limit": 100}],
                    api_key="test",
                    base_url=base_url,
                )
                result = tournament.result(1)
                with self.assertRaises(urllib.error.HTTPError) as unauthorized:
                    urllib.request.urlopen(f"{base_url}/api/games/list")
                self.assertEqual(unauthorized.exception.code, 401)
                unauthorized.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            request_lines = tournament.requests_path.read_text().splitlines()
            request_log = [json.loads(line) for line in request_lines]

        self.assertEqual(games[0]["id"], 1)
        self.assertEqual(games[0]["duration_seconds"], 3600.0)
        self.assertEqual(key, "secret-key")
        self.assertEqual(response[0]["charge_price"], 100.0)
        self.assertEqual(result["score"]["net"]["midpoint"], 0.0)
        self.assertEqual(result["score"]["submitted_items"], 1)
        self.assertEqual([row["method"] for row in request_log], ["GET", "GET", "PUT", "GET"])
        self.assertEqual([row["status"] for row in request_log], [200, 200, 200, 401])
        self.assertEqual(request_log[2]["payload"][0]["charge_price"], 100)
        serialized = json.dumps(request_log)
        self.assertNotIn("test", serialized)
        self.assertNotIn("secret-key", serialized)
        self.assertNotIn("decryption_key", serialized)

    def test_submissions_are_last_write_wins_per_line_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tournament = BacktestTournament(
                self.dataset,
                [1],
                release_delay=-1,
                state_dir=Path(directory),
            )
            tournament.submit(1, [{"index": 1, "charge_price": 50, "acceptance_limit": 20}])
            tournament.submit(1, [{"index": 1, "charge_price": 80, "acceptance_limit": 30}])
            result = tournament.result(1)

        self.assertEqual(result["updates"], 2)
        self.assertEqual(result["submissions"]["1"]["charge_price"], 80.0)
        self.assertEqual(result["submissions"]["1"]["acceptance_limit"], 30.0)

    def test_console_result_line_contains_live_progress_and_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tournament = BacktestTournament(
                self.dataset,
                [1],
                release_delay=-1,
                state_dir=Path(directory),
            )
            tournament.submit(1, [{"index": 1, "charge_price": 80, "acceptance_limit": 30}])
            line = _result_line(tournament.result(1), "current")

        self.assertIn("Game 1 current: status=active", line)
        self.assertIn("updates=1", line)
        self.assertIn("items=1/1", line)
        self.assertIn("net [", line)
        self.assertIn("actual 0.00", line)


if __name__ == "__main__":
    unittest.main()
