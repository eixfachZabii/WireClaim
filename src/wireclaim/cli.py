from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from api.client import EHLClient
from api.models import Game
from wireclaim.cases.archive import ArchiveExtractor
from wireclaim.cases.repository import CaseRepository
from wireclaim.config import Settings
from wireclaim.logging import configure_logging
from wireclaim.orchestration.runner import GameRunner
from wireclaim.orchestration.scheduler import ScheduleWatcher
from wireclaim.pipeline.loader import load_processor
from wireclaim.state.database import StateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wireclaim", description="Ingest EHL cases when their keys are released"
    )
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="check local configuration and dependencies")
    subparsers.add_parser("games", help="list the API game schedule")
    subparsers.add_parser("status", help="show local processing state")
    subparsers.add_parser("watch", help="watch the schedule and ingest due cases")

    ingest = subparsers.add_parser("ingest", help="ingest and trigger one API game")
    ingest.add_argument("game_id", type=int)

    process = subparsers.add_parser(
        "process", help="manually trigger processing for an extracted case"
    )
    process.add_argument("game_id", type=int)
    return parser


def _client(settings: Settings) -> EHLClient:
    if not settings.team_api_key:
        raise RuntimeError("TEAM_API_KEY is not set; see .env.example")
    return EHLClient(base_url=settings.base_url, api_key=settings.team_api_key)


def _runtime(settings: Settings, *, require_client: bool = True):
    repository = CaseRepository(settings.archive_dir, settings.runtime_dir)
    extractor = ArchiveExtractor(
        repository, seven_zip_executable=settings.seven_zip_executable
    )
    state = StateStore(settings.runtime_dir / "wireclaim.sqlite3")
    processor = load_processor(settings.processor)
    client = _client(settings) if require_client else None
    runner = (
        GameRunner(
            client=client,
            extractor=extractor,
            processor=processor,
            state=state,
            key_retry_seconds=settings.key_retry_seconds,
            game_duration_seconds=settings.game_duration_seconds,
        )
        if client is not None
        else None
    )
    return client, extractor, state, processor, runner


def _doctor(settings: Settings) -> int:
    archives = sorted(settings.archive_dir.glob("case_*.zip"))
    seven_zip = shutil.which(settings.seven_zip_executable)
    checks = [
        ("TEAM_API_KEY", bool(settings.team_api_key), "configured"),
        (
            "archive directory",
            settings.archive_dir.is_dir(),
            f"{settings.archive_dir} ({len(archives)} archives)",
        ),
        (
            "7-Zip",
            seven_zip is not None,
            seven_zip or f"{settings.seven_zip_executable!r} not found",
        ),
        ("processor", True, settings.processor),
        ("runtime directory", True, str(settings.runtime_dir)),
    ]
    for label, passed, detail in checks:
        print(f"{'OK' if passed else 'MISSING':>7}  {label}: {detail}")
    return 0 if all(passed for _, passed, _ in checks) else 1


def _find_game(client: EHLClient, game_id: int) -> Game:
    for game in client.list_games():
        if game.id == game_id:
            return game
    raise RuntimeError(f"game {game_id} was not returned by the API")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    try:
        settings = Settings.from_env()
        if args.command == "doctor":
            return _doctor(settings)
        if args.command == "games":
            client = _client(settings)
            for game in client.list_games():
                print(f"{game.id:>3}  {game.start_time.isoformat()}")
            return 0

        require_client = args.command in {"watch", "ingest"}
        client, extractor, state, processor, runner = _runtime(
            settings, require_client=require_client
        )
        try:
            if args.command == "status":
                rows = state.rows()
                if not rows:
                    print("No games have been recorded locally.")
                for row in rows:
                    error = f"  error={row['last_error']}" if row["last_error"] else ""
                    print(
                        f"{row['game_id']:>3}  {row['start_time']}  "
                        f"{row['status']:<13} attempts={row['attempts']}{error}"
                    )
                return 0
            if args.command == "watch":
                assert client is not None and runner is not None
                ScheduleWatcher(
                    client=client,
                    runner=runner,
                    state=state,
                    refresh_seconds=settings.schedule_refresh_seconds,
                ).run_forever()
                return 0
            if args.command == "ingest":
                assert client is not None and runner is not None
                runner.run(_find_game(client, args.game_id))
                return 0
            if args.command == "process":
                start_time = state.start_time(args.game_id) or datetime.now(timezone.utc)
                game = Game(id=args.game_id, start_time=start_time)
                existing = extractor.load_existing(args.game_id)
                # Build the same context as GameRunner without requiring API credentials.
                from datetime import timedelta
                from wireclaim.domain.models import CaseReady

                ready = CaseReady(
                    game_id=game.id,
                    start_time=game.start_time,
                    deadline=game.start_time
                    + timedelta(seconds=settings.game_duration_seconds),
                    case_dir=existing.case_dir,
                    input_dir=existing.input_dir,
                    policy_path=existing.policy_path,
                    description_path=existing.description_path,
                    invoices_path=existing.invoices_path,
                    image_paths=existing.image_paths,
                    manifest_path=existing.manifest_path,
                )
                processor(ready)
                state.transition(game, "completed")
                return 0
        finally:
            state.close()
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"wireclaim: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

