import argparse
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


def load_env() -> None:
    """Load the KEY=value pairs from .env using python-dotenv or stdlib fallback."""
    try:
        from dotenv import find_dotenv, load_dotenv

        env_file = find_dotenv(usecwd=True) or (Path(__file__).resolve().parent / ".env")
        load_dotenv(dotenv_path=env_file, override=True)
    except ImportError:
        path = Path(".env")
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                if name.strip():
                    os.environ.setdefault(name.strip(), value.strip().strip('"\''))


load_env()

from src.api import APIError, get_decryption_key, list_games, query_llm, submit_price

ARCHIVE_DIR = Path("[PUBLIC] EHL Cases/cases")
OUTPUT_DIR = Path("var/cases")


def parse_time(value: str) -> datetime:
    """Parse ISO timestamp to UTC datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def extract_case(game_id: int, key: str) -> Path:
    """Decrypt one case into var/cases/case_XX."""
    name = f"case_{game_id:02d}"
    candidate_archives = [
        ARCHIVE_DIR / f"{name}.zip",
        Path("cases") / f"{name}.zip",
        Path(f"{name}.zip"),
    ]
    archive = next((a for a in candidate_archives if a.exists()), None)
    if not archive:
        raise FileNotFoundError(f"Missing case archive for {name} in candidate locations.")

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
    """Entry point for pricing analysis and submission."""
    print(f"Game {game_id} is ready: {case_dir}")

    # Submitting default pricing decision
    result = submit_price(
        game_id=game_id,
        charge_price=410.0,
        acceptance_limit=430.0,
    )
    print(f"Game {game_id} Submission confirmed:", result)


def handle_game(game_id: int) -> None:
    """Fetch the released key, decrypt the archive, and trigger processing."""
    key = None
    for attempt in range(10):
        try:
            key = get_decryption_key(game_id)
            break
        except APIError as error:
            if error.status_code != 403 or attempt == 9:
                raise
            time.sleep(0.5)

    if not key:
        raise RuntimeError(f"Could not retrieve decryption key for game {game_id}")

    print(f"Decryption key for game {game_id}: {key}")
    case_dir = extract_case(game_id, key)
    process_case(game_id, case_dir)


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
    parser = argparse.ArgumentParser(description="WireClaim - QuantCo Claim-to-Fame Runner")
    parser.add_argument(
        "--game-id",
        type=int,
        default=None,
        help="Process one game immediately instead of watching the schedule",
    )
    parser.add_argument(
        "--test-llm",
        action="store_true",
        help="Test LLM connection and exit",
    )
    args = parser.parse_args()

    if args.test_llm:
        print("Testing LLM...")
        llm_response = query_llm("Answer only with: API works")
        print("LLM Response:", llm_response)
        return

    if args.game_id is not None:
        handle_game(args.game_id)
    else:
        watch_games()


if __name__ == "__main__":
    main()
