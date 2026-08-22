"""The watcher's review wiring: what decides *whether* a Game gets reviewed, and the
guarantee that a broken review can never take the poll loop down with it.

`review_game.py`'s own tests cover what happens inside one `claude` call; these cover the
layer above it -- picking which Games are due, the opt-out knobs, and the second safety net
around a call that (despite `review_game.review`'s own promises) still raises.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import learn_watch  # noqa: E402
import review_game  # noqa: E402


class ReviewPendingSelectionTests(unittest.TestCase):
    """Which Games `_review_pending` actually sends to `claude`."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.lessons_dir = root / "lessons"
        self.reviews_dir = root / "reviews"
        self.lessons_dir.mkdir()
        self.reviews_dir.mkdir()

        patcher_lessons = patch.object(learn_watch, "LESSONS", self.lessons_dir)
        patcher_lessons.start()
        self.addCleanup(patcher_lessons.stop)

        patcher_reviews = patch.object(review_game, "REVIEWS_DIR", self.reviews_dir)
        patcher_reviews.start()
        self.addCleanup(patcher_reviews.stop)

    def _lesson(self, game_id: int) -> None:
        (self.lessons_dir / f"game_{game_id:03d}.json").write_text("{}")

    def _already_reviewed(self, game_id: int) -> None:
        (self.reviews_dir / f"game_{game_id:03d}.md").write_text("done")

    def test_only_analysed_and_not_yet_reviewed_games_are_sent(self) -> None:
        self._lesson(1)
        self._lesson(2)
        self._already_reviewed(2)  # already has a review -- must be skipped
        # Game 3 was in `pending` but `learn_from_game.py` never wrote it a lesson (e.g. it
        # hit its own per-Game exception) -- nothing to review, must be skipped too.

        with patch.object(review_game, "review", return_value="### Review — Game 1\n") as mock_review:
            learn_watch._review_pending([1, 2, 3])

        mock_review.assert_called_once_with(1)

    def test_no_games_due_calls_claude_zero_times(self) -> None:
        with patch.object(review_game, "review") as mock_review:
            learn_watch._review_pending([])

        mock_review.assert_not_called()

    def test_review_returning_none_is_not_printed_and_does_not_raise(self) -> None:
        self._lesson(4)
        with patch.object(review_game, "review", return_value=None):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                learn_watch._review_pending([4])  # must not raise

        self.assertEqual(out.getvalue(), "")

    def test_an_exception_from_review_game_does_not_propagate(self) -> None:
        """`review_game.review` promises never to raise; this is the second net in case it
        does anyway -- the poll loop that called `_review_pending` must survive either way."""
        self._lesson(5)
        with patch.object(review_game, "review", side_effect=RuntimeError("boom")):
            learn_watch._review_pending([5])  # must not raise

    def test_one_games_failure_does_not_stop_the_next_games_review(self) -> None:
        self._lesson(6)
        self._lesson(7)

        def flaky(game_id: int):
            if game_id == 6:
                raise RuntimeError("boom")
            return "### Review — Game 7\n"

        with patch.object(review_game, "review", side_effect=flaky):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                learn_watch._review_pending([6, 7])

        self.assertIn("Review — Game 7", out.getvalue())

    def test_a_successful_review_is_printed_through_the_existing_digest_styling(self) -> None:
        self._lesson(8)
        reply = "### Review — Game 8\n\n- **stage**: ok — nothing obviously wrong.\n"
        with patch.object(review_game, "review", return_value=reply):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                learn_watch._review_pending([8])

        printed = out.getvalue()
        self.assertIn("Review — Game 8", printed)
        self.assertIn("stage", printed)


class ReviewedGlobTests(unittest.TestCase):
    def test_reviewed_reads_game_ids_out_of_the_reviews_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reviews_dir = Path(tmp)
            (reviews_dir / "game_009.md").write_text("x")
            (reviews_dir / "game_042.md").write_text("x")
            with patch.object(review_game, "REVIEWS_DIR", reviews_dir):
                self.assertEqual(learn_watch._reviewed(), {9, 42})

    def test_reviewed_is_empty_when_the_directory_does_not_exist_yet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "not-created-yet"
            with patch.object(review_game, "REVIEWS_DIR", missing):
                self.assertEqual(learn_watch._reviewed(), set())


class MainReviewOptOutTests(unittest.TestCase):
    """The two opt-out knobs (`--no-review`, `WIRECLAIM_NO_REVIEW`), exercised through
    `main()` itself so a future refactor of the flag-parsing can't silently stop honouring
    either one. Every dependency that would touch the network or spawn a real subprocess is
    mocked out; only the review-wiring decision is under test."""

    def setUp(self) -> None:
        patcher_run = patch.object(learn_watch, "_run")  # no real extract/learn subprocesses
        patcher_run.start()
        self.addCleanup(patcher_run.stop)

        patcher_completed = patch.object(learn_watch, "_completed", return_value=[7])
        patcher_completed.start()
        self.addCleanup(patcher_completed.stop)

        patcher_analysed = patch.object(learn_watch, "_analysed", return_value=set())
        patcher_analysed.start()
        self.addCleanup(patcher_analysed.stop)

        patcher_review_pending = patch.object(learn_watch, "_review_pending")
        self.review_pending = patcher_review_pending.start()
        self.addCleanup(patcher_review_pending.stop)

        # Isolate from whatever the real shell happens to have set.
        patcher_env = patch.dict(os.environ, {}, clear=False)
        patcher_env.start()
        self.addCleanup(patcher_env.stop)
        os.environ.pop("WIRECLAIM_NO_REVIEW", None)

    def test_review_runs_by_default_on_a_newly_settled_game(self) -> None:
        with patch.object(sys, "argv", ["learn_watch.py", "--once"]):
            learn_watch.main()

        self.review_pending.assert_called_once_with([7])

    def test_the_no_review_flag_skips_it(self) -> None:
        with patch.object(sys, "argv", ["learn_watch.py", "--once", "--no-review"]):
            learn_watch.main()

        self.review_pending.assert_not_called()

    def test_the_env_var_skips_it_too(self) -> None:
        os.environ["WIRECLAIM_NO_REVIEW"] = "1"
        with patch.object(sys, "argv", ["learn_watch.py", "--once"]):
            learn_watch.main()

        self.review_pending.assert_not_called()

    def test_nothing_pending_never_calls_review_at_all(self) -> None:
        with patch.object(learn_watch, "_completed", return_value=[]), patch.object(
            sys, "argv", ["learn_watch.py", "--once"]
        ):
            learn_watch.main()

        self.review_pending.assert_not_called()


if __name__ == "__main__":
    unittest.main()
