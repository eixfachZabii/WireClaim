"""The numbers Strategy 2 is built on, and where each one comes from.

Every value here is either measured against the reconstructed Fair Values of the settled
Games (`scripts/invert_fair_values.py`) or explicitly labelled as an unmeasured prior. If
you change one, re-measure in euros with `scripts/replay_payoffs.py` — not in log error,
which weights a EUR 10 Line Item the same as a EUR 7,000 one.
"""

from __future__ import annotations

#: Must match the key in `src.services.strategies.STRATEGY_PRIORITIES`, since the router
#: reads the priority off `Proposal.source`. A typo here silently demotes the track to 0.
STRATEGY_NAME = "strategy2"

#: Per model call. The Game window is 60 s and the two ensemble draws run concurrently, so
#: the wall clock is one call, not two. `propose` clamps this further against the deadline.
#:
#: Raised from 40 at Game 34, when the evidence model moved from `gpt-5.4-mini` to
#: `gpt-5.6-terra`. Terra is markedly more accurate but far more variable: three runs of the
#: real `request_evidence` path over Case 31 (18 Line Items) took **19.4 s, >40.8 s and
#: 51.1 s**, against 6.5 s for mini. At 40 s a draw that would have landed at 45 s was being
#: discarded for nothing.
#:
#: Raising it cannot overrun the window, and that is the only reason it is safe:
#: `_draw_timeout` in `strategy.py` returns
#: `min(LLM_TIMEOUT_SECONDS, deadline - now - SUBMISSION_RESERVE_SECONDS)`, so the deadline
#: always binds first and this constant can only ever *lower* the real budget. Game 33
#: submitted 9 s after its start, so the Case load leaves ~55 s; the clamp hands a draw ~52 s
#: of that. And a draw that still times out costs nothing beyond itself -- the cheap fast-path
#: submission has already landed, so the floor is the fast path, never the default (rule 1).
LLM_TIMEOUT_SECONDS = 55.0

#: Leave this much of the window for the final PUT after the last draw returns.
SUBMISSION_RESERVE_SECONDS = 3.0

#: Median Fair Value over the 148 settled Line Items with a bounded bracket. Used as a
#: prior in the prompt and as the last-resort price when no channel has anything to say.
SETTLED_MEDIAN = 59.0

#: Assumed log error of the model's own band, used to weight it against Price Memory and as
#: the fallback width when a band is missing or incoherent. **This is a prior, not a
#: measurement** — the one number in this file without evidence behind it. The estimator's
#: real log error is nearer 0.8, so this is optimistic; `scripts/backtest.py` replaces it
#: once a run is scored.
MODEL_SIGMA_PRIOR = 0.6

#: Price Memory's measured leave-one-out log error over Cases 1-14.
MEMORY_SIGMA = 0.43

#: A price band is read as a ~90% interval, so this converts a sigma to a band and back.
BAND_Z = 1.645
