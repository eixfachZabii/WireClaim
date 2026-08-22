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
import re
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


#: ANSI, and only where a terminal will read it. Colour is not decoration here: the digest is
#: read at speed between Games, and the three things that matter -- a Game's net, the stage
#: that failed, and the noise-floor warning -- have to be findable without reading prose.
_ANSI = {
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "off": "\033[0m",
}


def _colour_enabled() -> bool:
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


def _paint(text: str, *styles: str) -> str:
    if not _colour_enabled():
        return text
    return "".join(_ANSI[s] for s in styles) + text + _ANSI["off"]


def _rule(label: str = "", width: int = 74) -> str:
    if not label:
        return _paint("─" * width, "dim")
    bar = "─" * max(width - len(label) - 3, 0)
    return _paint(f"── {label} {bar}", "dim")


#: The digest prints a Unicode minus (U+2212) as well as ASCII, so match both or half the
#: costs stay uncoloured -- which is the half that matters.
_MONEY = re.compile(r"(?<![\w.])([+\-\u2212][\d,]+(?:\.\d+)?)(?![\w])")


def _prettify(line: str) -> str:
    """Markdown-ish digest -> something readable in a terminal at a glance."""
    stripped = line.strip()

    # `## Game 30  net -3,463` becomes the banner for the Game.
    if stripped.startswith("## "):
        title = stripped[3:]
        return "\n" + _rule() + "\n  " + _paint(title, "bold", "cyan") + "\n" + _rule()
    if stripped.startswith("### "):
        return "\n" + _rule(stripped[4:])
    # The noise-floor caveat. Dim, because it must be present without shouting.
    if stripped.startswith(">"):
        return _paint("  " + stripped.lstrip("> "), "dim")
    if stripped.startswith("_") and stripped.endswith("_"):
        return _paint("  " + stripped.strip("_"), "dim")

    # Signed euro amounts: green earns, red costs. This is the whole point of the colour.
    def money(match: "re.Match[str]") -> str:
        value = match.group(1)
        return _paint(value, "green" if value.startswith("+") else "red")

    painted = _MONEY.sub(money, line)
    # Stage names arrive as **bold**; make them stand out rather than showing the asterisks.
    painted = re.sub(r"\*\*(.+?)\*\*", lambda m: _paint(m.group(1), "bold", "yellow"), painted)
    # Line Item names arrive as *italics*; the terminal has no italics worth relying on.
    painted = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", lambda m: _paint(m.group(1), "cyan"), painted)
    if stripped.startswith("- "):
        return painted.replace("- ", "  • ", 1)
    # A wrapped continuation of the bullet above it, e.g. the stage and its explanation.
    if line.startswith("  ") and stripped:
        return "    " + painted.strip()
    return painted


def _run(command: list[str], pretty: bool = False) -> None:
    result = subprocess.run(
        command, capture_output=True, text=True, check=False, env=_child_env()
    )
    output = (result.stdout or "") + (result.stderr or "")
    if not output.strip():
        return
    if not pretty:
        print(output.rstrip())
        return
    for line in output.rstrip().splitlines():
        print(_prettify(line))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll", type=int, default=POLL_SECONDS, help="seconds between checks")
    parser.add_argument("--once", action="store_true", help="check once and exit")
    args = parser.parse_args()

    python = sys.executable
    print()
    print(_rule("wireclaim · learning loop"))
    print(_paint(f"  polling every {args.poll}s · Ctrl-C to stop", "dim"))
    print(_rule())
    while True:
        try:
            pending = sorted(set(_completed()) - _analysed())
            if pending:
                games = ", ".join(str(g) for g in pending)
                print()
                print(_paint(f"  ▸ {len(pending)} newly settled: {games}", "bold", "cyan"))
                # Unzip first: a Case nobody can read cannot be diagnosed.
                _run([python, "scripts/extract_cases.py", "--quiet"])
                _run(
                    [python, "scripts/learn_from_game.py", "--games", f"{pending[0]}-{pending[-1]}"],
                    pretty=True,
                )
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
