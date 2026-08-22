"""Ask a Claude agent to read a settled Game's lesson and judge it, so the overnight loop
does not need a human awake to read every digest.

    PYTHONPATH=. pixi run review-game 42        # review one Game by hand

`learn_from_game.py` already joins the decision log against the reconstructed Fair Value and
names the stage that was wrong (CLAUDE.md rule 1b). What it cannot do is *open the Case* the
way CLAUDE.md rule 2 requires, or hold itself to the evidentiary bar the hypothesis ledger
runs on -- that one Game is far inside the noise floor and a lesson is at most a *candidate*.
This is that missing judgement, produced by an agent instructed to do both.

It shells out to the installed `claude` CLI in print mode, restricted to the Read tool (the
only thing it is ever asked to do is open three Case files), on Sonnet rather than the
account's default model (a three-paragraph review does not need Opus), with a dollar cap so
a model that starts reasoning in circles overnight cannot run up a bill nobody is watching.

It must never be able to hurt the watch loop it is called from: a missing `claude` binary, a
timeout, a non-zero exit, a malformed reply -- every one of those degrades to a short printed
notice and a `None` return, never an exception. A Game the review skips is no worse off than
one nobody wrote a review for; a poll cycle the review blocks would be worse than either.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.observability.decisions import load as load_decisions  # noqa: E402

LESSONS_DIR = Path("var/lessons")
REVIEWS_DIR = Path("var/reviews")
#: Where `main.py`'s own pipeline extracts a Case as it plays a Game (CLAUDE.md rule 2's
#: example paths). `scripts/extract_cases.py` also keeps a copy under
#: "[PUBLIC] EHL Cases/cases", but this is the one guaranteed to exist for any Game the
#: watcher has already turned into a lesson, because the runner had to read it to play.
CASES_DIR = Path("var/cases")

#: A review that runs away is worse than a poll cycle it delays, so both ends are capped:
#: wall clock (a hung or slow `claude` cannot stall the watcher past this) and dollars (a
#: model that starts reasoning in circles cannot run up a bill nobody is watching overnight).
TIMEOUT_SECONDS = 180
MAX_BUDGET_USD = "0.50"

#: A review is a read of three files and a judgement call, not a coding task -- Sonnet is the
#: right size, and it keeps the unattended, all-night cost well under what the account's
#: interactive default (Opus, observed at ~$0.19 for a one-line "say hi") would charge on
#: every settled Game for the rest of the tournament.
MODEL = "sonnet"

#: The five-stage taxonomy `.devin/skills/learn-from-runs/SKILL.md` and `_stage()` in
#: `learn_from_game.py` already use. Handed to the reviewer so it names one of *these*
#: rather than inventing new vocabulary the ledger would then have to reconcile.
STAGE_TAXONOMY = (
    "no-decision-log, no-evidence, no-channel, coverage-too-low, coverage-too-high, "
    "charge-above-t, charge-far-below-t, estimate-too-high, ok"
)


def claude_binary() -> str | None:
    return shutil.which("claude")


def _case_dir(game_id: int) -> Path | None:
    directory = CASES_DIR / f"case_{game_id:02d}"
    return directory if (directory / "policy.txt").exists() else None


def _decision_log_section(game_id: int) -> str:
    """The raw decision log, or the exact diagnosis CLAUDE.md rule 1b names for its absence.

    A missing log is not silence to fill in around -- it is itself the finding (Strategy 2
    did not land), and the reviewer is told that explicitly rather than left to guess why
    every item below reads `no-decision-log`.
    """
    log = load_decisions(game_id)
    if log is None:
        return (
            "No decision log was recorded for this Game "
            f"(`var/decisions/game_{game_id:03d}.json` is absent or failed schema "
            "validation). Per CLAUDE.md rule 1b this means Strategy 2 may not have landed -- "
            "say that plainly rather than attributing to coverage, level, charge or limit."
        )
    return "```json\n" + json.dumps(log, indent=2) + "\n```"


def build_prompt(game_id: int, lesson: dict, case_dir: Path | None) -> str:
    lesson_json = json.dumps(lesson, indent=2)
    decision_section = _decision_log_section(game_id)

    if case_dir is not None:
        case_section = (
            f"- {case_dir}/policy.txt\n"
            f"- {case_dir}/description.txt\n"
            f"- {case_dir}/invoices.pdf\n\n"
            "Open all three with the Read tool before writing your review. If one is "
            "missing or unreadable, say so under \"case evidence\" instead of inventing a "
            "quote."
        )
    else:
        case_section = (
            f"No extracted Case directory was found for Game {game_id} under `{CASES_DIR}`. "
            "Say this plainly under \"case evidence\" -- do not fabricate a clause."
        )

    return f"""You are the automated overnight reviewer for WireClaim, a project that plays an
insurance-pricing tournament: every settled Game earns or loses real euros, and this repo's
CLAUDE.md is the accumulated cost of every wrong intuition anyone has had about it. Game
{game_id} has just settled and `scripts/learn_from_game.py` has already joined the decision
log against the reconstructed Fair Value. Your job is to read that lesson, open the Case, and
write a short review -- you do not change any code, and you do not propose any number.

## Rules you are held to, quoted from this repo's CLAUDE.md

> Never judge our algorithm, or a Game's result, from the numbers alone. Open the Case.
> [...] A number without its Case is a symptom without a diagnosis. Read `policy.txt`,
> `description.txt` and the invoice before concluding anything about why a Game went the way
> it did -- and quote the clause when you do.
(CLAUDE.md, rule 2)

> [F]ollow the learn-from-runs skill: attribute to a stage, add the evidence to
> hypothesis-ledger.md, and change at most one thing -- validated across every settled Game,
> never on the strength of the Game that just settled. One Game is far inside the 26,622
> noise floor [measured over 18 Games; the single-Game figure is about 6,275].
(CLAUDE.md, rule 1b)

Concretely, that means:

- Attribute what happened to exactly one stage from this taxonomy: {STAGE_TAXONOMY}. The
  lesson JSON below already tags each Line Item with one of these under `items[].stage` --
  use that vocabulary rather than inventing your own.
- You MUST open the Case files listed below with the Read tool and quote the exact clause
  (from policy.txt or description.txt) that bears on the stage you named. An attribution
  with no quoted clause behind it is not acceptable output.
- You MUST NOT recommend changing any constant, prompt, or line of code. This is one Game,
  and CLAUDE.md rule 1b requires validation across every settled Game before anything is
  changed. The most you may write is a CANDIDATE worth checking against the full history --
  phrase it as a question for the hypothesis ledger, never as an instruction to act on now.
- State plainly whether this Game's result is SIGNAL (sharpens or matches a hypothesis
  already standing in the ledger) or NOISE (one data point that does not clear the noise
  floor on its own and should not move anything). Default to NOISE unless the stage
  attribution is unambiguous and the euros involved are large.
- Keep the whole reply under 200 words. No preamble, no restating these instructions.

## Reply in exactly this shape, nothing else

### Review — Game {game_id}

- **what happened**: <1-2 sentences, in euros>
- **stage**: <one name from the taxonomy> — <one-line reason>
- **case evidence**: "<verbatim clause>" (policy.txt or description.txt) — <why it bears on
  the stage>
- **verdict**: signal | noise — <one line tying it to the noise floor>
- **candidate**: <a specific, falsifiable thing to check across every settled Game, or
  "none — nothing here clears the noise floor">

## Game {game_id}'s lesson (`var/lessons/game_{game_id:03d}.json`)

```json
{lesson_json}
```

## Decision log (`var/decisions/game_{game_id:03d}.json`)

{decision_section}

## Case files to open and quote from

{case_section}
"""


def _run_claude(prompt: str, *, timeout: float) -> str | None:
    """Invoke the CLI and return its reply, or `None` with a printed notice on any failure.

    Every failure mode -- missing binary, timeout, non-zero exit, empty reply -- is handled
    here rather than left to propagate, because this function is called from inside a poll
    loop that must keep polling regardless of what a subprocess does.
    """
    binary = claude_binary()
    if binary is None:
        print("review: `claude` CLI not found on PATH -- skipping the review step.")
        return None

    command = [
        binary,
        "-p",
        prompt,
        "--output-format",
        "text",
        "--model",
        MODEL,
        "--allowedTools",
        "Read",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--max-budget-usd",
        MAX_BUDGET_USD,
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        print(f"review: `claude` did not answer within {timeout:.0f}s -- skipping.")
        return None
    except Exception as error:  # noqa: BLE001 - a review must never break the caller
        print(f"review: could not run `claude` ({type(error).__name__}: {error}) -- skipping.")
        return None

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else f"exit {result.returncode}"
        print(f"review: `claude` exited {result.returncode} ({tail}) -- skipping.")
        return None

    text = (result.stdout or "").strip()
    if not text:
        print("review: `claude` returned an empty reply -- skipping.")
        return None
    return text


def review(game_id: int, *, timeout: float = TIMEOUT_SECONDS) -> str | None:
    """Produce and persist the review for one Game, or `None` if it could not be produced.

    Always safe to call, and always overwrites: the caller (the watcher) decides whether a
    Game is worth reviewing again, this function just does the review when asked.
    """
    lesson_path = LESSONS_DIR / f"game_{game_id:03d}.json"
    try:
        lesson = json.loads(lesson_path.read_text())
    except (OSError, ValueError) as error:
        print(f"review: no readable lesson for Game {game_id} ({error}) -- skipping.")
        return None

    try:
        prompt = build_prompt(game_id, lesson, _case_dir(game_id))
        text = _run_claude(prompt, timeout=timeout)
        if text is None:
            return None

        REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
        header = (
            f"<!-- scripts/review_game.py · model {MODEL} · "
            f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} -->\n\n"
        )
        (REVIEWS_DIR / f"game_{game_id:03d}.md").write_text(header + text + "\n")
        return text
    except Exception as error:  # noqa: BLE001 - see module docstring: never hurt the caller
        print(f"review: Game {game_id} failed unexpectedly ({type(error).__name__}: {error}).")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_id", type=int, help="Game id to review, e.g. 42")
    parser.add_argument(
        "--timeout", type=float, default=TIMEOUT_SECONDS, help="hard cap in seconds"
    )
    args = parser.parse_args()

    text = review(args.game_id, timeout=args.timeout)
    if text is None:
        sys.exit(0)  # the notice was already printed; a review step never fails the caller
    print(text)


if __name__ == "__main__":
    main()
