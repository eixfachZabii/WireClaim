"""Drop-in HTTP replacement for the live tournament API backed by historical Games."""

from __future__ import annotations

import json
import math
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from backtesting.data import load_dataset, parse_games
from backtesting.models import HistoricalDataset, Submission
from backtesting.paths import STATE
from backtesting.scoring import score_game
from src.api.tournament import DEFAULT_BASE_URL, APIError, get_decryption_key


@dataclass
class GameState:
    game_id: int
    starts_at: datetime
    duration_seconds: float
    submissions: dict[int, Submission] = field(default_factory=dict)
    updates: list[dict[str, Any]] = field(default_factory=list)
    finalized: bool = False

    @property
    def deadline(self) -> datetime:
        return self.starts_at + timedelta(seconds=self.duration_seconds)

    def status(self, now: datetime) -> str:
        if now < self.starts_at:
            return "scheduled"
        if now <= self.deadline:
            return "active"
        return "completed"


class BacktestTournament:
    def __init__(
        self,
        dataset: HistoricalDataset,
        game_ids: Sequence[int],
        *,
        release_delay: float = 3.0,
        spacing: float = 65.0,
        duration_seconds: float = 3600.0,
        state_dir: Path | None = None,
    ) -> None:
        if spacing <= 0 or duration_seconds <= 0:
            raise ValueError("Game spacing and duration must be positive")
        missing = sorted(set(game_ids) - set(dataset.games))
        if missing:
            raise ValueError(f"Games missing from dataset: {missing}")
        first = datetime.now(timezone.utc) + timedelta(seconds=release_delay)
        self.dataset = dataset
        self.states = {
            game_id: GameState(
                game_id=game_id,
                starts_at=first + timedelta(seconds=position * spacing),
                duration_seconds=duration_seconds,
            )
            for position, game_id in enumerate(game_ids)
        }
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.state_dir = state_dir or STATE / "api_runs" / f"{stamp}-g{'-'.join(map(str, game_ids))}"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._keys: dict[int, str] = {}
        self._request_sequence = 0
        self.requests_path = self.state_dir / "api_requests.jsonl"

    def record_request(
        self,
        *,
        method: str,
        path: str,
        status: int,
        client: str,
        elapsed_seconds: float,
        payload: Any = None,
    ) -> None:
        with self.lock:
            self._request_sequence += 1
            record = {
                "sequence": self._request_sequence,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "method": method,
                "path": path,
                "status": int(status),
                "client": client,
                "elapsed_seconds": round(elapsed_seconds, 6),
            }
            if payload is not None:
                record["payload"] = payload
            with self.requests_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        print(
            f"API #{record['sequence']:04d} {method:3s} {path} -> {int(status)} "
            f"{elapsed_seconds:.3f}s client={client}",
            flush=True,
        )

    def games(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        return [
            {
                "id": state.game_id,
                "start_time": state.starts_at.isoformat().replace("+00:00", "Z"),
                "status": state.status(now),
                "duration_seconds": state.duration_seconds,
            }
            for state in self.states.values()
        ]

    def key(self, game_id: int, api_key: str) -> str:
        state = self._state(game_id)
        if datetime.now(timezone.utc) < state.starts_at:
            raise APIError(HTTPStatus.FORBIDDEN, "Game key has not been released")
        with self.lock:
            cached = self._keys.get(game_id)
        if cached is not None:
            return cached
        key = get_decryption_key(
            game_id,
            api_key=api_key,
            base_url=DEFAULT_BASE_URL,
            timeout=30.0,
        )
        with self.lock:
            self._keys[game_id] = key
        return key

    def submit(self, game_id: int, payload: Any) -> list[dict[str, Any]]:
        state = self._state(game_id)
        now = datetime.now(timezone.utc)
        if now < state.starts_at:
            raise APIError(HTTPStatus.FORBIDDEN, "Game has not started")
        if now > state.deadline:
            raise APIError(HTTPStatus.CONFLICT, "Submission window has closed")
        if not isinstance(payload, list):
            raise APIError(HTTPStatus.BAD_REQUEST, "Submission body must be a list")
        received = []
        with self.lock:
            for position, raw in enumerate(payload, start=1):
                if not isinstance(raw, Mapping):
                    raise APIError(HTTPStatus.BAD_REQUEST, f"Submission {position} is not an object")
                try:
                    index = int(raw.get("index", position))
                    charge = float(raw.get("charge_price", 0.0))
                    limit = float(raw.get("acceptance_limit", 0.0))
                except (TypeError, ValueError) as error:
                    raise APIError(HTTPStatus.BAD_REQUEST, f"Invalid submission {position}") from error
                if index <= 0 or not math.isfinite(charge) or not math.isfinite(limit) or charge < 0 or limit < 0:
                    raise APIError(HTTPStatus.BAD_REQUEST, f"Invalid values for Line Item {index}")
                state.submissions[index] = Submission(charge, limit)
                row = {
                    "game_id": game_id,
                    "line_item_index": index,
                    "index": index,
                    "charge_price": charge,
                    "acceptance_limit": limit,
                    "submitted_at": now.isoformat(),
                }
                received.append(row)
            state.updates.append(
                {
                    "sequence": len(state.updates) + 1,
                    "received_at": now.isoformat(),
                    "submissions": received,
                    "score": self._score_payload(state),
                }
            )
            self._persist(state)
        return received

    def result(self, game_id: int) -> dict[str, Any]:
        state = self._state(game_id)
        with self.lock:
            return self._result_payload(state)

    def finalize_due(self) -> list[dict[str, Any]]:
        finalized = []
        now = datetime.now(timezone.utc)
        with self.lock:
            for state in self.states.values():
                if state.finalized or now <= state.deadline:
                    continue
                state.finalized = True
                payload = self._result_payload(state)
                self._persist(state)
                finalized.append(payload)
        return finalized

    def _state(self, game_id: int) -> GameState:
        try:
            return self.states[game_id]
        except KeyError as error:
            raise APIError(HTTPStatus.NOT_FOUND, f"Unknown Game {game_id}") from error

    def _score_payload(self, state: GameState) -> dict[str, Any]:
        game = self.dataset.games[state.game_id]
        score = score_game(game, state.submissions)
        return {
            "income": asdict(score.income),
            "cost": asdict(score.cost),
            "net": asdict(score.net),
            "actual_net": game.authoritative_nets.get("Bin busy"),
            "submitted_items": len(state.submissions),
            "expected_items": len(game.items),
        }

    def _result_payload(self, state: GameState) -> dict[str, Any]:
        return {
            "game_id": state.game_id,
            "status": state.status(datetime.now(timezone.utc)),
            "starts_at": state.starts_at.isoformat(),
            "deadline": state.deadline.isoformat(),
            "finalized": state.finalized,
            "updates": len(state.updates),
            "submissions": {
                str(index): {"charge_price": value.charge, "acceptance_limit": value.limit}
                for index, value in sorted(state.submissions.items())
            },
            "score": self._score_payload(state),
        }

    def _persist(self, state: GameState) -> None:
        payload = self._result_payload(state)
        payload["update_log"] = state.updates
        path = self.state_dir / f"game_{state.game_id:03d}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2))
        temporary.replace(path)


class BacktestAPIHandler(BaseHTTPRequestHandler):
    tournament: BacktestTournament

    def do_GET(self) -> None:
        self._start_request()
        try:
            path = urlsplit(self.path).path
            if path == "/health":
                self._json(HTTPStatus.OK, {"status": "ok"})
                return
            self._require_key()
            if path == "/api/games/list":
                self._json(HTTPStatus.OK, self.tournament.games())
                return
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "games"] and parts[3] == "key":
                game_id = int(parts[2])
                key = self.tournament.key(game_id, self.headers["X-API-Key"])
                self._json(HTTPStatus.OK, {"decryption_key": key})
                return
            if len(parts) == 3 and parts[:2] == ["backtesting", "results"]:
                self._json(HTTPStatus.OK, self.tournament.result(int(parts[2])))
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except APIError as error:
            self._json(error.status_code, {"error": error.message})
        except (TypeError, ValueError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid request"})

    def do_PUT(self) -> None:
        self._start_request()
        try:
            self._require_key()
            parts = urlsplit(self.path).path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api", "games"] or parts[3] != "submissions":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"null")
            self._request_payload = _safe_submission_payload(payload)
            self._json(HTTPStatus.OK, self.tournament.submit(int(parts[2]), payload))
        except APIError as error:
            self._json(error.status_code, {"error": error.message})
        except (json.JSONDecodeError, TypeError, ValueError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid request"})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _start_request(self) -> None:
        self._request_started = time.monotonic()
        self._request_payload = None

    def _require_key(self) -> None:
        if not (self.headers.get("X-API-Key") or "").strip():
            raise APIError(HTTPStatus.UNAUTHORIZED, "X-API-Key is required")

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode()
        try:
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        finally:
            self.tournament.record_request(
                method=self.command,
                path=self.path,
                status=int(status),
                client=self.client_address[0],
                elapsed_seconds=time.monotonic() - self._request_started,
                payload=self._request_payload,
            )


def _safe_submission_payload(payload: Any) -> Any:
    if not isinstance(payload, list):
        return None
    safe = []
    for item in payload:
        if not isinstance(item, Mapping):
            safe.append({"invalid_type": type(item).__name__})
            continue
        safe.append(
            {
                key: item[key]
                for key in ("index", "charge_price", "acceptance_limit")
                if key in item
            }
        )
    return safe


def serve(
    games: str,
    *,
    dataset_id: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    release_delay: float = 3.0,
    spacing: float = 65.0,
    duration_seconds: float = 3600.0,
) -> None:
    dataset = load_dataset(dataset_id)
    game_ids = parse_games(games, sorted(dataset.games))
    tournament = BacktestTournament(
        dataset,
        game_ids,
        release_delay=release_delay,
        spacing=spacing,
        duration_seconds=duration_seconds,
    )
    handler = type("ConfiguredBacktestAPIHandler", (BacktestAPIHandler,), {"tournament": tournament})
    server = ThreadingHTTPServer((host, port), handler)
    monitor = threading.Thread(target=_monitor, args=(tournament,), daemon=True)
    console = threading.Thread(target=_console_monitor, args=(tournament,), daemon=True)
    monitor.start()
    console.start()
    print(f"Backtesting Tournament API: http://{host}:{port}", flush=True)
    print(f"Games: {game_ids}; state: {tournament.state_dir}", flush=True)
    for state in tournament.states.values():
        print(
            f"  Game {state.game_id}: {state.starts_at.isoformat()} to {state.deadline.isoformat()}",
            flush=True,
        )
    print(f"Client .env: BASE_URL=http://{host}:{port}", flush=True)
    print("Press Enter at any time to print the current result.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


def _monitor(tournament: BacktestTournament) -> None:
    while True:
        for result in tournament.finalize_due():
            print(_result_line(result, "finalized"), flush=True)
        time.sleep(0.25)


def _console_monitor(tournament: BacktestTournament) -> None:
    while True:
        if sys.stdin.readline() == "":
            return
        print_current_results(tournament)


def print_current_results(tournament: BacktestTournament) -> None:
    for game_id in tournament.states:
        print(_result_line(tournament.result(game_id), "current"), flush=True)


def _result_line(result: Mapping[str, Any], label: str) -> str:
    score = result["score"]
    net = score["net"]
    return (
        f"Game {result['game_id']} {label}: status={result['status']} "
        f"updates={result['updates']} items={score['submitted_items']}/{score['expected_items']} "
        f"net [{net['lower']:,.2f}, {net['midpoint']:,.2f}, {net['upper']:,.2f}], "
        f"actual {score['actual_net']:,.2f}"
    )
