from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.models import ForbiddenError, Game
from wireclaim.cases.archive import ExtractedCase
from wireclaim.orchestration.runner import GameRunner
from wireclaim.orchestration.scheduler import seconds_until
from wireclaim.state.database import StateStore


class FakeClient:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls = 0

    def get_decryption_key(self, game_id: int) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise ForbiddenError(403, "get key", "not started")
        return "released-key"


class FakeExtractor:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.keys: list[str] = []

    def extract(self, game_id: int, key: str) -> ExtractedCase:
        self.keys.append(key)
        case_dir = self.root / f"case_{game_id:02d}"
        input_dir = case_dir / "input"
        return ExtractedCase(
            game_id=game_id,
            case_dir=case_dir,
            input_dir=input_dir,
            manifest_path=case_dir / "manifest.json",
            policy_path=input_dir / "policy.txt",
            description_path=input_dir / "description.txt",
            invoices_path=input_dir / "invoices.pdf",
            image_paths=(input_dir / "photo.jpg",),
        )


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class OrchestrationTests(unittest.TestCase):
    def test_runner_retries_key_and_triggers_processor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = StateStore(root / "state.sqlite3")
            client = FakeClient(failures=2)
            extractor = FakeExtractor(root)
            processed = []
            clock = Clock()
            runner = GameRunner(
                client=client,
                extractor=extractor,
                processor=processed.append,
                state=state,
                key_retry_seconds=10,
                game_duration_seconds=60,
                monotonic=clock.monotonic,
                sleep=clock.sleep,
            )
            game = Game(
                id=4, start_time=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
            )

            ready = runner.run(game)

            self.assertEqual(client.calls, 3)
            self.assertEqual(extractor.keys, ["released-key"])
            self.assertEqual(processed, [ready])
            self.assertEqual(state.status(4), "completed")
            self.assertEqual(
                ready.deadline, game.start_time + timedelta(seconds=60)
            )
            state.close()

    def test_seconds_until_never_returns_negative(self) -> None:
        now = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(seconds_until(now + timedelta(seconds=3), now), 3)
        self.assertEqual(seconds_until(now - timedelta(seconds=3), now), 0)


if __name__ == "__main__":
    unittest.main()

