"""`review_game.py` must never be able to hurt the loop it is called from.

Every test here is really the same claim in a different costume: a missing `claude` binary,
a hung one, a crashing one, or a mid-flight exception all degrade to a printed notice and a
`None` return -- never an exception the watcher's poll loop would have to catch. The one
positive-path test pins what actually gets shelled out to `claude`, since that command line
(model, allowed tools, budget cap, timeout) *is* the safety mechanism the rest of the module
promises, and a typo in any flag there would silently widen what an unattended review can do.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import review_game  # noqa: E402


def _completed_process(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["claude"], returncode=returncode, stdout=stdout, stderr=stderr)


class ReviewGameTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.lessons_dir = root / "lessons"
        self.reviews_dir = root / "reviews"
        self.cases_dir = root / "cases"
        self.lessons_dir.mkdir()

        patcher_lessons = patch.object(review_game, "LESSONS_DIR", self.lessons_dir)
        patcher_reviews = patch.object(review_game, "REVIEWS_DIR", self.reviews_dir)
        patcher_cases = patch.object(review_game, "CASES_DIR", self.cases_dir)
        for patcher in (patcher_lessons, patcher_reviews, patcher_cases):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

        # A missing decision log is the common case in these tests; individual tests that
        # care about the log's content patch this again themselves.
        patcher_log = patch.object(review_game, "load_decisions", return_value=None)
        patcher_log.start()
        self.addCleanup(patcher_log.stop)

        (self.lessons_dir / "game_032.json").write_text(
            json.dumps({"game_id": 32, "mechanisms": {"net": -3463.0}, "items": []})
        )

    # ---- graceful degradation: nothing here may ever raise or block the caller ----

    def test_a_missing_claude_binary_returns_none_and_writes_nothing(self) -> None:
        with patch.object(review_game, "claude_binary", return_value=None):
            result = review_game.review(32)

        self.assertIsNone(result)
        self.assertFalse((self.reviews_dir / "game_032.md").exists())

    def test_a_missing_lesson_returns_none_without_touching_claude(self) -> None:
        with patch("subprocess.run") as run:
            result = review_game.review(999)  # no lessons/game_999.json written in setUp

        self.assertIsNone(result)
        run.assert_not_called()

    def test_a_timeout_returns_none_and_writes_nothing(self) -> None:
        with patch.object(review_game, "claude_binary", return_value="/usr/bin/claude"), patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["claude"], timeout=180)
        ):
            result = review_game.review(32, timeout=180)

        self.assertIsNone(result)
        self.assertFalse((self.reviews_dir / "game_032.md").exists())

    def test_a_nonzero_exit_returns_none_and_writes_nothing(self) -> None:
        with patch.object(review_game, "claude_binary", return_value="/usr/bin/claude"), patch(
            "subprocess.run", return_value=_completed_process(returncode=1, stderr="auth error")
        ):
            result = review_game.review(32)

        self.assertIsNone(result)
        self.assertFalse((self.reviews_dir / "game_032.md").exists())

    def test_an_empty_reply_returns_none_and_writes_nothing(self) -> None:
        with patch.object(review_game, "claude_binary", return_value="/usr/bin/claude"), patch(
            "subprocess.run", return_value=_completed_process(returncode=0, stdout="   \n")
        ):
            result = review_game.review(32)

        self.assertIsNone(result)
        self.assertFalse((self.reviews_dir / "game_032.md").exists())

    def test_an_unexpected_exception_from_subprocess_is_swallowed(self) -> None:
        """`subprocess.run` can raise things other than `TimeoutExpired` -- e.g. an OSError
        if the binary vanishes between the `which` check and the call. None of them may
        escape `review()`."""
        with patch.object(review_game, "claude_binary", return_value="/usr/bin/claude"), patch(
            "subprocess.run", side_effect=OSError("no such file")
        ):
            result = review_game.review(32)  # must not raise

        self.assertIsNone(result)

    def test_a_write_failure_after_a_good_reply_is_swallowed(self) -> None:
        """The reply came back fine; the disk did not cooperate. Still not the caller's problem."""
        with patch.object(review_game, "claude_binary", return_value="/usr/bin/claude"), patch(
            "subprocess.run", return_value=_completed_process(returncode=0, stdout="### Review — Game 32\n")
        ), patch.object(review_game, "REVIEWS_DIR", Path("/nonexistent/nope/reviews")):
            result = review_game.review(32)  # must not raise

        self.assertIsNone(result)

    # ---- the happy path, and what it actually sends to `claude` ----

    def test_a_successful_review_is_written_to_disk_and_returned(self) -> None:
        reply = "### Review — Game 32\n\n- **what happened**: net -3,463\n"
        with patch.object(review_game, "claude_binary", return_value="/usr/bin/claude"), patch(
            "subprocess.run", return_value=_completed_process(returncode=0, stdout=reply)
        ):
            result = review_game.review(32)

        self.assertEqual(result, reply.strip())
        on_disk = (self.reviews_dir / "game_032.md").read_text()
        self.assertIn(reply.strip(), on_disk)
        self.assertIn("review_game.py", on_disk)  # traceability header

    def test_the_claude_invocation_is_restricted_to_a_read_only_sonnet_review_with_a_budget_cap(
        self,
    ) -> None:
        with patch.object(review_game, "claude_binary", return_value="/usr/bin/claude"), patch(
            "subprocess.run", return_value=_completed_process(returncode=0, stdout="ok")
        ) as run:
            review_game.review(32, timeout=42)

        args, kwargs = run.call_args
        command = args[0]
        self.assertEqual(command[0], "/usr/bin/claude")
        self.assertIn("-p", command)
        self.assertEqual(kwargs["timeout"], 42)
        self.assertFalse(kwargs["check"])
        # The tools this thing is allowed to use, the model it runs on, and the dollar cap
        # are the actual safety mechanism -- assert the flags, not just that *some* command ran.
        self.assertIn("--allowedTools", command)
        self.assertEqual(command[command.index("--allowedTools") + 1], "Read")
        self.assertIn("--model", command)
        self.assertEqual(command[command.index("--model") + 1], review_game.MODEL)
        self.assertIn("--max-budget-usd", command)
        self.assertIn("--strict-mcp-config", command)
        self.assertIn("--disable-slash-commands", command)

    def test_review_overwrites_on_a_second_call(self) -> None:
        """The manual `pixi run review-game` path re-runs on request; only the watcher's own
        `_reviewed()` gate makes it "once per Game"."""
        with patch.object(review_game, "claude_binary", return_value="/usr/bin/claude"), patch(
            "subprocess.run", return_value=_completed_process(returncode=0, stdout="first")
        ):
            review_game.review(32)
        with patch.object(review_game, "claude_binary", return_value="/usr/bin/claude"), patch(
            "subprocess.run", return_value=_completed_process(returncode=0, stdout="second")
        ):
            review_game.review(32)

        self.assertIn("second", (self.reviews_dir / "game_032.md").read_text())

    # ---- the prompt itself: what the reviewer is and is not told to do ----

    def test_the_prompt_embeds_the_lesson_and_the_evidentiary_rules(self) -> None:
        lesson = {"game_id": 32, "mechanisms": {"net": -3463.0}, "items": []}
        prompt = review_game.build_prompt(32, lesson, case_dir=None)

        self.assertIn('"net": -3463.0', prompt)  # the lesson JSON, verbatim
        self.assertIn("26,622", prompt)  # the noise floor, quoted from CLAUDE.md rule 1b
        self.assertIn("Open the Case", prompt)  # CLAUDE.md rule 2, quoted
        self.assertIn("quote the clause", prompt)
        self.assertIn("MUST NOT recommend changing", prompt)
        self.assertIn("signal", prompt)
        self.assertIn("noise", prompt)
        self.assertIn(review_game.STAGE_TAXONOMY, prompt)

    def test_the_prompt_points_at_the_three_case_files_when_a_case_dir_exists(self) -> None:
        case_dir = self.cases_dir / "case_32"
        case_dir.mkdir(parents=True)
        (case_dir / "policy.txt").write_text("policy")

        prompt = review_game.build_prompt(32, {"game_id": 32}, case_dir=case_dir)

        self.assertIn(str(case_dir / "policy.txt"), prompt)
        self.assertIn(str(case_dir / "description.txt"), prompt)
        self.assertIn(str(case_dir / "invoices.pdf"), prompt)

    def test_the_prompt_admits_a_missing_case_rather_than_inventing_paths(self) -> None:
        prompt = review_game.build_prompt(32, {"game_id": 32}, case_dir=None)

        self.assertIn("No extracted Case directory was found", prompt)

    def test_a_missing_decision_log_is_named_as_the_finding_it_is(self) -> None:
        with patch.object(review_game, "load_decisions", return_value=None):
            prompt = review_game.build_prompt(32, {"game_id": 32}, case_dir=None)

        self.assertIn("No decision log was recorded", prompt)
        self.assertIn("Strategy 2 may not have landed", prompt)

    def test_case_dir_lookup_requires_policy_txt_to_exist(self) -> None:
        (self.cases_dir / "case_05").mkdir(parents=True)  # empty: no policy.txt

        self.assertIsNone(review_game._case_dir(5))

        (self.cases_dir / "case_05" / "policy.txt").write_text("x")
        self.assertEqual(review_game._case_dir(5), self.cases_dir / "case_05")


class MainCliTests(unittest.TestCase):
    """The pixi task (`pixi run review-game N`) is `main()`; it must exit cleanly either way."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(review_game, "LESSONS_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_main_does_not_raise_when_claude_is_unavailable(self) -> None:
        with patch.object(sys, "argv", ["review_game.py", "999"]), patch.object(
            review_game, "claude_binary", return_value=None
        ):
            try:
                review_game.main()
            except SystemExit as exit_:
                self.assertEqual(exit_.code, 0)


if __name__ == "__main__":
    unittest.main()
