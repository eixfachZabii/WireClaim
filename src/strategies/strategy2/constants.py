"""The numbers Strategy 2 is built on, and where each one comes from.

Every value here is either measured against the reconstructed Fair Values of the settled
Games (`scripts/invert_fair_values.py`) or explicitly labelled as an unmeasured prior. If
you change one, re-measure in euros with `scripts/replay_payoffs.py` — not in log error,
which weights a EUR 10 Line Item the same as a EUR 7,000 one.
"""

from __future__ import annotations

#: Must match the key in `src.strategies.STRATEGY_PRIORITIES`, since the router
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
#:
#: Raised from 3.0 after Game 78, which submitted at **T+59.33 s of a 60 s window -- 0.67 s to
#: spare** -- because one draw hung and the guard that was supposed to stop it did not. Had it
#: been a second slower the Fast Path would have stood, and on that Case the Fast Path wanted
#: 1,200.00 on a Line Item Strategy 2 priced at 8.59. A Charge that far above `t` earns nothing
#: from anybody, so the Game would have scored near zero. Games 81-100 pay triple.
SUBMISSION_RESERVE_SECONDS = 5.0

#: How much longer the outer `asyncio.wait_for` waits than the HTTP call it wraps.
#:
#: This exists only so the inner timeout raises first and the log says *why* a draw died rather
#: than "cancelled". It must stay far below `SUBMISSION_RESERVE_SECONDS`, because the outer guard
#: is the one that actually binds when a call hangs without honouring its own timeout.
#:
#: It used to be `SUBMISSION_RESERVE_SECONDS` itself, which silently cancelled the reserve:
#: `_draw_timeout` subtracts the reserve to protect the final PUT, and the outer guard added the
#: same number straight back, so a hung draw was allowed to run to the wire with nothing left for
#: pricing and posting. Game 78 is the arithmetic in full -- `min(55, 60 - 1.3 - 3) = 55`, outer
#: guard `55 + 3 = 58`, draw killed at **58.016 s**, submission at 59.33 s.
DRAW_GRACE_SECONDS = 0.5

#: Median settled Fair Value. Used as the reference distribution in the prompt and as the
#: band for an item we cannot price at all (`channels.worthless_evidence`).
#:
#: Re-measured at Game 41 over **457** settled Line Items, against the 148 the old value of
#: 59.0 was taken from. The true median is **97** -- the old figure understated it by 65%,
#: and it had been telling the model so in every prompt since.
#:
#: `LIMIT_CAP` is written as `12.0 * 59.0` in literals rather than in terms of this constant,
#: so it does not move with it. That is deliberate: the cap is a Field measurement about
#: large Charges, not a multiple of the median, and coupling them would make one measurement
#: silently move the other.
SETTLED_MEDIAN = 97.0

#: Assumed log error of the model's own band, used to weight it against Price Memory and as
#: the fallback width when a band is missing or incoherent. **This is a prior, not a
#: measurement** — the one number in this file without evidence behind it. The estimator's
#: real log error is nearer 0.8, so this is optimistic; `scripts/backtest.py` replaces it
#: once a run is scored.
#:
#: **Re-measured post-tournament at ~1.0**, not 0.8 — the censoring-aware fit puts the model
#: channel's residual at roughly a factor of 12 between its 20th and 90th percentiles
#: (`C:model` stratum, `src/pricing/calibration.py`). So this prior is *more* optimistic than
#: the comment above admits. It is deliberately **left at 0.6 anyway**: the only thing the value
#: does is set memory's share of `blend.combine`, and that share was swept walk-forward over 99
#: Games — 0.66 (what these two constants produce) is the argmax, and every larger share scores
#: strictly worse. Correcting the number here would move a shipped optimum away from its
#: measured peak. See H24 in the hypothesis ledger.
MODEL_SIGMA_PRIOR = 0.6

#: Price Memory's measured leave-one-out log error over Cases 1-14.
MEMORY_SIGMA = 0.43

#: A price band is read as a ~90% interval, so this converts a sigma to a band and back.
BAND_Z = 1.645
