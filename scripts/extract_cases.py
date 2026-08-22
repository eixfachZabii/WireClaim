"""Unzip every Case whose decryption key has been released.

    pixi run cases          # top up
    pixi run start          # tops up first, then runs the tournament listener

CLAUDE.md rule 2 says reading the Cases is the first thing in any session, and every claim
in this repo that survived contact with reality came from opening one. But the runner never
did it: `case_loader` reads the encrypted archive from `[PUBLIC] EHL Cases/cases` and
extracts into `var/cases/`, so the readable copy only ever contained whatever somebody had
unzipped by hand. It sat three Games behind for exactly that reason.

Decryption keys never expire and are released when a Game starts, so this is safe to run at
any time and is idempotent: it skips what is already extracted and stops at the first Game
whose key the API still withholds.

**It never fails the caller.** It is wired ahead of `start`, and a missing key or a network
blip must not stop us from submitting — going dark has cost us 139,904 in three Games.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api import APIError, get_decryption_key  # noqa: E402

CASES = Path("[PUBLIC] EHL Cases/cases")
LAST_GAME = 100


def extract(game_id: int, key: str) -> bool:
    """Unzip one Case next to its archive. Returns False if 7z is unhappy."""
    archive = CASES / f"case_{game_id:02d}.zip"
    target = CASES / f"case_{game_id:02d}"
    if not archive.exists():
        return False
    result = subprocess.run(
        ["7z", "x", "-y", f"-p{key}", f"-o{target}", str(archive)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # Leave no half-extracted directory behind to confuse a later reader.
        if target.exists() and not any(target.iterdir()):
            target.rmdir()
        return False
    return True


def top_up(first: int = 0, last: int = LAST_GAME, quiet: bool = False) -> tuple[int, int]:
    """Extract every released Case from `first` to `last`. Returns (new, already had)."""
    added = present = 0
    for game_id in range(first, last + 1):
        target = CASES / f"case_{game_id:02d}"
        if (target / "policy.txt").exists():
            present += 1
            continue
        if not (CASES / f"case_{game_id:02d}.zip").exists():
            continue
        try:
            key = get_decryption_key(game_id, timeout=10.0)
        except APIError:
            # 403 until the Game starts. Keys are released in order, so this is the frontier.
            if not quiet:
                print(f"case_{game_id:02d}: not released yet — stopping.")
            break
        except Exception as error:  # network, DNS, anything
            if not quiet:
                print(f"case_{game_id:02d}: could not fetch a key ({error}) — stopping.")
            break
        if extract(game_id, key):
            added += 1
            if not quiet:
                print(f"case_{game_id:02d}: extracted.")
        elif not quiet:
            print(f"case_{game_id:02d}: extraction failed.")
    return added, present


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="first", type=int, default=0)
    parser.add_argument("--to", dest="last", type=int, default=LAST_GAME)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    try:
        added, present = top_up(args.first, args.last, args.quiet)
        if not args.quiet:
            print(f"Cases: {added} newly extracted, {present} already present.")
    except Exception as error:  # pragma: no cover - must never block the runner
        print(f"Case extraction skipped: {error}")


if __name__ == "__main__":
    main()
