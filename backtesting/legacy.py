"""Single import boundary around the repository's existing analysis scripts."""

from __future__ import annotations

import sys

from backtesting.paths import SCRIPTS

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import invert_fair_values  # noqa: E402
import pull_transactions  # noqa: E402
import replay_payoffs  # noqa: E402
import rivals  # noqa: E402

__all__ = ["invert_fair_values", "pull_transactions", "replay_payoffs", "rivals"]
