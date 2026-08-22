import argparse
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.api import APIError, get_decryption_key, list_games

ARCHIVE_DIR = Path("[PUBLIC] EHL Cases/cases")
OUTPUT_DIR = Path("var/cases")


def load_env() -> None:
    """Load the simple KEY=value pairs used by this project."""
    path = Path(".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip('"\''))


load_env()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def extract_case(game_id: int, key: str) -> Path:
    """Decrypt one case into var/cases/case_XX."""
    name = f"case_{game_id:02d}"
    archive = ARCHIVE_DIR / f"{name}.zip"
    if not archive.exists():
        raise FileNotFoundError(f"Missing case archive: {archive}")
    case_dir = OUTPUT_DIR / name
    case_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["7z", "x", "-y", f"-p{key}", f"-o{case_dir}", str(archive)],
        check=True,
        capture_output=True,
        text=True,
    )
    print(f"Game {game_id} extracted to {case_dir}")
    return case_dir


def process_case(game_id: int, case_dir: Path) -> None:
    """Entry point for the rest of the system."""
    print(f"Game {game_id} is ready: {case_dir}")
    # TODO: Parse invoices.pdf.
    # TODO: Check policy.txt and description.txt per line item.
    # TODO: Estimate prices and hand the result to the future API interface.


def handle_game(game_id: int) -> None:
    """Fetch the released key, decrypt the archive, and trigger processing."""
    for attempt in range(10):
        try:
            key = get_decryption_key(game_id)
            break
        except APIError as error:
            if error.status_code != 403 or attempt == 9:
                raise
            time.sleep(0.5)
    process_case(game_id, extract_case(game_id, key))


def watch_games() -> None:
    """Wait through the published schedule and handle each game at its start."""
    games = sorted(list_games(), key=lambda game: parse_time(game["start_time"]))
    print(f"Loaded {len(games)} scheduled games. Press Ctrl-C to stop.")
    for game in games:
        now = datetime.now(timezone.utc)
        start_time = parse_time(game["start_time"])
        if start_time + timedelta(minutes=1) < now:
            continue
        wait_seconds = (start_time - now).total_seconds()
        if wait_seconds > 0:
            print(f"Game {game['id']} starts at {start_time.isoformat()}")
            time.sleep(wait_seconds)
        handle_game(int(game["id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="WireClaim case watcher")
    parser.add_argument(
        "--game-id",
        type=int,
        help="Process one game immediately instead of watching the schedule",
    )
    args = parser.parse_args()

    if args.game_id is not None:
        handle_game(args.game_id)
    else:
        watch_games()


if __name__ == "__main__":
    main()
