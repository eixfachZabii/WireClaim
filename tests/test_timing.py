import logging
import unittest

from src.timing import log_timing, start_timer


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


if __name__ == "__main__":
    unittest.main()
