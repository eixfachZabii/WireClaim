import logging
import unittest

from src.runtime.timing import (
    format_error_card,
    format_fraud_lock_card,
    format_skipped_strategy_card,
    log_timing,
    start_timer,
)


class TimingTests(unittest.TestCase):
    def test_log_contains_event_status_and_elapsed_seconds(self) -> None:
        logger = logging.getLogger("wireclaim.timing.test")

        with self.assertLogs(logger, level="INFO") as logs:
            log_timing(logger, "strategy1", start_timer(), game=7, line_item=3)

        self.assertIn("event=strategy1", logs.output[0])
        self.assertIn("status=completed", logs.output[0])
        self.assertIn("elapsed_s=", logs.output[0])
        self.assertIn("game=7", logs.output[0])
        self.assertIn("line_item=3", logs.output[0])

    def test_formats_a_colorized_compact_error_card(self) -> None:
        card = format_error_card(
            "fast_path",
            TimeoutError("gateway read timed out"),
            game=25,
            action="Fast Path skipped; Strategies continue.",
            elapsed_s=25.37,
        )

        self.assertIn("\033[91m", card)
        self.assertIn("FAST PATH FAILED", card)
        self.assertIn("game:", card)
        self.assertIn("elapsed:", card)
        self.assertIn("25.37s", card)
        self.assertIn("TimeoutError", card)
        self.assertIn("gateway read timed out", card)
        self.assertIn("Fast Path skipped; Strategies continue.", card)
        self.assertNotIn("Traceback", card)

    def test_formats_a_fraud_lock_card(self) -> None:
        card = format_fraud_lock_card(25, ((2, "Unrelated item"), (7, "Vehicle cost")))

        self.assertIn("\033[91m", card)
        self.assertIn("FRAUD LIMIT LOCKS CONFIRMED", card)
        self.assertIn("[2] Unrelated item -> Limit=0.00", card)
        self.assertIn("[7] Vehicle cost -> Limit=0.00", card)
        self.assertIn("Later Fast Path and Strategy snapshots retain these locks.", card)

    def test_formats_a_gray_skipped_strategy_comparison(self) -> None:
        card = format_skipped_strategy_card(
            game=18,
            candidate_source="strategy1",
            candidate_priority=1,
            active_source="strategy2",
            active_priority=3,
            elapsed_s=32.99,
            prices=((1, 1200.0, 35.0), (2, 150.0, 35.0)),
        )

        self.assertIn("\033[90m", card)
        self.assertIn("STRATEGY1 COMPARISON ONLY", card)
        self.assertIn("NOT POSTED", card)
        self.assertIn("candidate: strategy1 (priority 1)", card)
        self.assertIn("active: strategy2 (priority 3)", card)
        self.assertIn("   1 |      1200.00 |        35.00", card)
        self.assertNotIn("BEFORE", card)
        self.assertNotIn("AFTER", card)


if __name__ == "__main__":
    unittest.main()
