"""Watch for settled Games and analyse each one as it lands.

    pixi run watch          # leave this running in a second terminal

`pixi run start` is the runner: it plays the Games. This is the other half of the loop, and
it exists because the analysis cannot run at the same moment as the Game — the Transactions
that reveal the Fair Value only appear once the Game settles, a minute or two after it ends.

So: one terminal plays, one terminal learns. Nothing has to be remembered, which is the
point. The alternative is that a Game's evidence is available for twelve minutes and then
buried under the next one.

It also tops up the Case extraction, since a Case whose archive is never unzipped cannot be
read, and reading the Case is what turns a number into a diagnosis (CLAUDE.md rule 2).

Safe to leave running for the whole tournament: it polls at a browser's pace, only analyses
a Game once, and never touches the runner or the submission path.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LESSONS = Path("var/lessons")
POLL_SECONDS = 90


def _completed() -> list[int]:
    """Game ids the leaderboard reports as finished. Empty on any failure."""
    try:
        from pull_transactions import completed_games  # type: ignore

        return list(completed_games())
    except Exception:
        try:
            from pull_transactions import games  # type: ignore

            return [g["id"] for g in games() if g.get("status") == "completed"]
        except Exception:
            return []


def _analysed() -> set[int]:
    return {int(path.stem.split("_")[1]) for path in LESSONS.glob("game_*.json")}


def _child_env() -> dict[str, str]:
    """The repo root on `PYTHONPATH`, so a child can `import src`.

    Without this the child dies on `ModuleNotFoundError: No module named 'src'`, but only
    when it is spawned — which is exactly the path nobody exercises by hand, because a human
    running the script directly usually has `PYTHONPATH=.` set already.
    """
    root = str(Path(__file__).resolve().parents[1])
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{root}{os.pathsep}{existing}" if existing else root
    return env


def _run(command: list[str]) -> None:
    result = subprocess.run(
        command, capture_output=True, text=True, check=False, env=_child_env()
    )
    output = (result.stdout or "") + (result.stderr or "")
    if output.strip():
        print(output.rstrip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll", type=int, default=POLL_SECONDS, help="seconds between checks")
    parser.add_argument("--once", action="store_true", help="check once and exit")
    args = parser.parse_args()

    python = sys.executable
    print(f"Watching for settled Games (every {args.poll}s). Ctrl-C to stop.")
    while True:
        try:
            pending = sorted(set(_completed()) - _analysed())
            if pending:
                print(f"\n=== {len(pending)} newly settled: {pending} ===")
                # Unzip first: a Case nobody can read cannot be diagnosed.
                _run([python, "scripts/extract_cases.py", "--quiet"])
                _run([python, "scripts/learn_from_game.py", "--games", f"{pending[0]}-{pending[-1]}"])
        except KeyboardInterrupt:
            raise
        except Exception as error:  # never die on a transient failure
            print(f"watch: skipped a cycle ({type(error).__name__}: {error})")
        if args.once:
            return
        try:
            time.sleep(args.poll)
        except KeyboardInterrupt:
            print("\nStopped.")
            return


if __name__ == "__main__":
    main()
