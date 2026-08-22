# Phase-timing and uptime audit

Measurement only — nothing in `src/`, `main.py` or `pixi.toml` was touched, and no running
process was restarted. Produced while `pixi run start` and `pixi run watch` were live;
Game 33 settled and Game 42's throwaway test file was rewritten *during* this audit, so a
few numbers below were captured mid-flight and are timestamped accordingly.

**Bottom line up front.** The two-phase submit design works in every Game where it can be
checked — 6 clean live Games (28–33), zero uncaught-evidence fallbacks, landing at 10–70 %
of the 60 s window. But that check has only existed for 8 Games total (26–33), because the
decision log itself is six hours younger than the tournament. The single largest uptime risk
found is not in the pricing logic at all: `watch_games()` has no exception boundary around a
Game, so a bug that has never fired yet — most likely to trigger on the largest Cases, which
the current code has never seen — would end the tournament for every remaining Game, not just
one. A four-line fix closes it. Full reasoning and diffs below.

---

## 1. Decision-log inventory — which of Games 0–33 have one, and why the rest don't

`var/lessons/game_NNN.json`'s `had_decision_log` field (written by `scripts/learn_from_game.py`
each time it joins `var/decisions/game_NNN.json` against the settled Transactions) gives a
clean per-Game answer without guessing:

| Games | `had_decision_log` | Why |
| --- | --- | --- |
| 1–25 | **False**, all 25 | `src/decision_log.py` did not exist yet. |
| 26 | True (schema 1) | Exists, but **not the live submission** — see §2. |
| 27 | True (schema 2) | Exists, but **not the live submission** — see §2. |
| 28–33 | True (schema 2) | Clean, live, in-window. Trustworthy sample, n=6. |
| 42 | True (schema 2) | **Not a real Game run** — see §2. |

CLAUDE.md rule 1b treats a missing decision log as evidence Strategy 2 didn't land and says
to stop until you know why. Here the "why" is dated, not diagnostic: `git log --diff-filter=A
-- src/decision_log.py` shows it was added at commit `9088128`, **2026-08-22 18:22:30 UTC**
("Close the learning loop: log the decision, then learn from the settlement"), and the
`proposals`/`winner` section (schema 2) was added at `cb7b74b`, **18:37:31 UTC** ("Score every
strategy's counterfactual, and settle the Limit question"). Game 25 ended at 18:04:01 UTC,
eighteen minutes before the feature existed. **Games 1–25 have no decision log because nobody
had written one yet, not because the pipeline failed.** Strategy 2 itself has been the
top-priority strategy since `f620caf`, 16:53:31 UTC — live since roughly Game 20 — this file
just couldn't see it working until Game 26.

---

## 2. Data-quality triage — three of the eight logs are not what they look like

Before trusting a `recorded_at` timestamp, cross-check the decision log's `charge` per index
against `our_charge` in the matching `var/lessons/game_NNN.json` (which is reconstructed from
the *actual settled Transactions*, independent of the decision log). If a decision log
describes a run that was never submitted, the two will disagree.

| Game | items matching real submission | `recorded_at` − start | Verdict |
| --- | --- | --- | --- |
| 26 | **0 / 12** | +266.4 s (4.4× the 60 s window) | **Not live.** |
| 27 | 3 / 4 | +445.0 s (7.4× the window) | **Not live.** |
| 28 | 9 / 10 | +10.7 s | Live |
| 29 | 3 / 4 | +6.9 s | Live |
| 30 | 5 / 5 | +17.6 s | Live |
| 31 | 17 / 18 | +16.7 s | Live |
| 32 | 6 / 7 | +41.7 s | Live |
| 33 | not settled yet | +9.5 s | Live (timing only) |
| 42 | n/a | n/a | **Not a real Game** |

Reading Game 26 and 27: a `recorded_at` past T+60 s is *impossible* from a genuine
`run_game()` invocation — `RUN_SECONDS = 60.0` cancels every task at the deadline. Both are
explained exactly by the commit timestamps in §1: `decision_log.py` landed at 18:22:30 UTC,
2m25s **after** Game 26's file was written (18:20:05 UTC) — someone tested the new logging
locally against the just-expired Game 26 before committing it. The `proposals` feature landed
at 18:37:31 UTC, 1m33s after Game 27's `proposals_recorded_at` (18:35:58 UTC) — same pattern,
one commit later. Both re-ran Strategy 2 standalone against an already-expired Case, which is
why the numbers don't match what was actually submitted (a second, independent LLM call on
non-deterministic input produces different prices). **Their settled `net` (from real
Transactions) is still trustworthy; their evidence trail (`channels`, `coverage_probability`,
`price_median`) is not** — `learn_from_game.py`'s `stage` classification uses the true
`our_charge`/`t_lo`/`t_hi` and is fine, but its `why` narrative and channel attribution for
these two Games is diagnosing a different run than the one that scored.

`var/decisions/game_042.json` is a distinct problem: single line item ("Drying fan"), no
`proposals`/`winner` section (meaning it never passed through `StrategyRouter`, unlike every
real Game 26–33 log), and it was rewritten again while this audit was running (`recorded_at`
moved from `19:36:39Z` to `19:46:22Z`, same one item). Real Game 42 starts at
`2026-08-22T21:37:40Z` — over two hours after either timestamp. This is a developer's
standing local test harness reusing a live Game's ID as a label, unrelated to the schedule.
**Recommendation (process, not code): don't write test output into `var/decisions/` under a
real Game's filename** — it is exactly indistinguishable from a live log to a script that
doesn't cross-check against settled Transactions, which is what this audit had to do to catch
it.

---

## 3. Per-Game phase timeline — the trustworthy sample (n=6)

Start times from `GET /api/games/list` (`X-API-Key`), all UTC. "Items" = when Strategy 2's
own `record()` fired (its evidence + prices exist and are mergeable). "Proposals" = when the
router recorded all three strategies' outputs and the winner — the point at which the "smart
overwrite" the two-phase design promises is fully informed.

| Game | start (UTC) | items @ Δ | % of 60 s | proposals @ Δ | % of 60 s | model draws | items priced | winner |
| --- | --- | ---: | ---: | ---: | ---: | :---: | ---: | --- |
| 28 | 18:40:54 | +10.7 s | 18 % | +55.1 s | 92 % | 2/2 | 10 | strategy2 |
| 29 | 18:53:32 | +6.9 s | 12 % | +20.4 s | 34 % | 2/2 | 4 | strategy2 |
| 30 | 19:06:10 | +17.6 s | 29 % | +17.6 s | 29 % | 2/2 | 5 | strategy2 |
| 31 | 19:18:47 | +16.7 s | 28 % | +48.0 s | 80 % | 2/2 | 18 | strategy2 |
| 32 | 19:31:25 | +41.7 s | 70 % | +41.7 s | 70 % | **1/2** | 7 | strategy2 |
| 33 | 19:44:02 | +9.5 s | 16 % | +36.4 s | 61 % | 2/2 | 6 | strategy2 |

Every one of the six lands inside the window, with headroom (worst case Game 28 at 92 % —
close, but the final `PUT` still has its reserved seconds per `_SUBMISSION_RESERVE_SECONDS`).
Strategy 2 wins the router in all six, matching its priority-3 design. This is direct evidence
the per-Line-Item merge (`RunManager.set_strategy`, priority-gated, ties-to-newer) is operating
as `docs/ARCHITECTURE.md` §3 describes — for the sample it's been possible to check.

**Caveat that matters more than the table:** this sample has never contained a large Case.
The six items-counts are 10, 4, 5, 18, 7, 6 — max 18. Games 1–14 recorded Cases of up to
**39** Line Items (Games 13, 14), more than double anything the *current* code has been
observed to run against. §6 explains why that specific gap is where the largest untested risk
sits.

---

## 4. Failure-mode counts — Game × mode (n=6 clean Games, 50 items)

Modes requested in the brief, checked directly against each `var/decisions/game_NNN.json`:

| Game | items | LLM draws lost | `quantity_missing` | `rule≠"priced"` (uninformed) | `rule≠"priced"` (uncovered-free-option) | single-channel (model-only) | zero-channel |
| --- | ---: | :---: | ---: | ---: | ---: | ---: | ---: |
| 28 | 10 | 0/2 | 1 | **0** | 5 | 8 | 0 |
| 29 | 4  | 0/2 | 0 | **0** | 1 | 3 | 0 |
| 30 | 5  | 0/2 | 0 | **0** | 1 | 3 | 0 |
| 31 | 18 | 0/2 | 1 | **0** | 8 | 9 | 0 |
| 32 | 7  | **1/2** | 0 | **0** | 5 | 3 | 0 |
| 33 | 6  | 0/2 | 0 | **0** | 2 | 6 | 0 |
| **total** | **50** | **1 draw / 12** | **2** | **0** | **22** | **32** | **0** |

Reading this table correctly requires one distinction the brief's mode list conflates:
`rule = "uninformed-constants"` is a genuine failure (`Evidence` was `None` — neither Channel
B nor C spoke, so `strategy2` fell back to the fitted no-information constants,
`STANDARD_CHARGE=300 / STANDARD_LIMIT=35`). `rule = "uncovered-free-option"` is **not** a
failure — it is `price_item`'s correct, deliberate branch when the posterior's coverage mass
puts the Limit at exactly zero (CLAUDE.md rule 6: charge stays, Limit collapses, and that is
the free option working as designed). **Zero genuine `uninformed-constants` fallbacks and zero
zero-channel items occurred in this sample** — every one of the 50 items got at least one
channel's evidence. `SETTLED_MEDIAN` (59.0, the "last-resort price" the constants file
describes) and `FALLBACK_MEDIAN` (60.0, `pricing.py`'s incoherent-band filler) do not appear
as an exact charge/limit value on any item either — neither fallback fired.

The one real anomaly: **Game 32 lost one of its two ensemble draws** (`model_draws: 1`,
`ENSEMBLE_PROMPTS` has two framings). All 7 items still got priced from the surviving draw —
the invariant in `strategy2/strategy.py` ("Strategy 2 prices every Line Item of every Case,
always") held — but the posterior for that Game is a single framing rather than a blended
one, meaning a narrower evidence base than usual. 1 lost draw in 12 (n=6 Games × 2 draws) is
**not** enough to estimate an LLM-timeout rate from — see §7's noise-floor discussion — but it
is the only concrete "something took longer than `LLM_TIMEOUT_SECONDS=40s`" signal in the
whole trustworthy sample.

For completeness, the two contaminated logs (not part of the sample above, shown separately
because their rule/channel data does not describe what was actually submitted):

| Game | items | model draws | uninformed | uncovered-free-option | note |
| --- | ---: | :---: | ---: | ---: | --- |
| 26 | 12 | 2/2 | 0 | 3 | Dev test run, not the live submission |
| 27 | 4 | 2/2 | 0 | 3 | Dev test run, not the live submission |

---

## 5. Euro cost of each mode — with the noise floor next to every number

Costing used `var/lessons/*.json`'s `cost_by_stage` and `counterfactual` sections, which are
`scripts/learn_from_game.py`'s output built directly on `scripts/invert_fair_values.py` (Fair
Value reconstruction) and the same payoff-table replay logic as `scripts/replay_payoffs.py`.
Ground truth was re-verified before trusting any of it:

```
$ python3 scripts/invert_fair_values.py --verify
...
verify summary
  ok        [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33]
  no-cell   [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
```

Every Game from 14 through 33 reproduces its published net to the cent. Games 1–13 aren't
reconstructable by this method (insufficient bracket data) but their settled nets are still
readable directly from `var/lessons`.

**Stage attribution, Games 28–32** (Game 33 unsettled at write time, no cost data yet):

| stage | items | penalties (€) | meaning |
| --- | ---: | ---: | --- |
| `ok` | 22 | 17,091.22 | Correctly priced; penalty is Field variance (an opponent's Limit rejected a fair Charge), not our error. |
| `charge-far-below-t` | 4 | 17,025.40 | Underpriced relative to the true bracket — forfeited income, not a penalty in the strict sense but money left on the table. |
| `coverage-too-low` | 6 | 6,141.24 | Coverage probability under-called a covered item, collapsing the Limit and rejecting a fair Charge. |
| `charge-above-t` | 5 | 1,176.45 | Overpriced past the true bracket — the field correctly rejected. |
| `coverage-too-high` | 7 | 0.00 | Coverage probability over-called an uncovered item; cost zero in this sample because the Charge stayed low regardless. |

**None of these per-stage sums should be read as "this is what a fix is worth."** They are
penalty totals conditioned on a *post-hoc* label, not a counterfactual replay against a fixed
alternative — `ok` items carry the largest sum (€17,091) precisely because "ok" is the most
common stage, not because being "ok" costs money. `learn_from_game.py` does compute a real
counterfactual — `best_alternative_delta`, strategy2's raw proposal replayed against the same
real Field vs. the best of strategy1/strategy3 that the router's priority rule discarded — but
that replay is **pre-mask**: it scores each strategy's numbers in isolation, before the
coverage/fraud gate (layer 4 of the merge, `docs/ARCHITECTURE.md` §3) zeroes any Limits. The
gate applies identically regardless of which strategy wins, so it's a fair strategy-vs-strategy
comparison, but neither side of it equals what was actually banked — do not add this delta to
`actual_net` as if it were the same currency:

| Game | actual net (real, banked) | best alternative (pre-mask replay) | pre-mask delta vs. strategy2 |
| --- | ---: | --- | ---: |
| 28 | 5,298 | strategy1 | −2,238 (strategy2 already ahead) |
| 29 | 19,823 | strategy1 | **+22,909** |
| 30 | −3,463 | strategy1 | +2,465 |
| 31 | 690 | strategy1 | −3,301 (strategy2 already ahead) |
| 32 | 6,887 | strategy3 | −2,876 (strategy2 already ahead) |

Strategy2's pre-mask proposal beat the best alternative in 3 of 5 Games. Game 29 is the
exception worth reading: its single largest item ("Renew the water-damaged boiler...",
`t̂=7,139` against a true `t<57.3`) shows the router's priority-3 default is not a free pass —
one bad overestimate can outweigh every other item in the Game, and strategy1's pre-mask
proposal would have scored 22,909 better on that Game alone had it won instead. Whether the
*actual, masked* Game 29 would also have improved by switching is not answerable from this
data without re-running the mask against strategy1's numbers, which this audit did not do.

**Game-level net, with the noise floor** (formula from `learn_from_game.py`:
`26,622 · √(n/18)`, the measured 18-Game noise floor rescaled):

| sample | n | net sum (€) | noise floor (±€) | inside/outside floor |
| --- | ---: | ---: | ---: | --- |
| Games 1–25 (no decision log) | 25 | **−322,595** | 31,374 | Outside — a real, decisive loss era |
| Games 26–32 (post decision-log) | 7 | +36,656 | 16,602 | Outside, positive |
| Games 28–32 (clean-code-only sample) | 5 | +29,235 | 14,031 | Outside, positive |

The swing from −322,595 to +29,235/5-Games is real (both clear their respective noise
floors), but **this audit cannot attribute that swing to "the decision log landing" or "landing
inside the window."** The same commits that added logging also touched `LIMIT_CEILING`,
coverage handling and Strategy 2's constants (per `git log`, the same evening) — several
things changed together. What this audit *can* say: in every Game where the merge mechanism
is independently checkable, it worked (§3), and the failure modes it's supposed to prevent
(uninformed fallback, silent Strategy, zero-channel items) did not occur (§4). Whether that is
*why* the nets improved is a separate causal question this data doesn't settle.

**No euro figure could be attached to the two structural risks in §6** (thread-pool
starvation, the unguarded exception in `watch_games()`) — neither has been observed to fire in
any settled Game, so there is no counterfactual to replay. They are reported as latent risk,
not measured cost, and should stay labelled that way until (if ever) one fires.

---

## 6. The forward-looking question — 67 Games left, ending through an unattended overnight

As of this audit, Game 33 just settled; **67 Games remain** (34–100), and Games ~44–81 fall in
the overnight "dark field" window CLAUDE.md rule 9 describes — the one where an outage is
most expensive, because nobody else is awake to generate the wrongful-rejection income an
absent competitor normally forfeits to us.

### 6.1 The largest risk: one bug ends the tournament, not the Game

`main.py`'s `watch_games()` (the function `pixi run start` actually runs) has **no exception
boundary around a Game**:

```python
        if wait_seconds > 0:
            logger.info("Game %s starts at %s.", game_id, start_time.isoformat())
            await asyncio.sleep(wait_seconds)
        await run_game(game_id)          # <- line 323, unguarded
```

Everything *inside* `run_game` that talks to the network or an LLM is already caught
somewhere: `load_case` failures fall back to the blind floor (documented, tested); the three
background tasks (`fast_path`, `fraud`, strategy router) are each wrapped in `_emit_result`'s
own `try/except Exception`, and `asyncio.gather(..., return_exceptions=True)` prevents their
failures from propagating. **What is not wrapped** is the merge loop itself —
`RunManager(standard_values(case))` (raises `ValueError` if the Proposal it's built from is
empty — currently unreachable because `read_invoice_line_items` already hard-fails on zero
Line Items, so this exact line is safe today, but it is one refactor away from not being so),
`coordinator.publish(manager.snapshot(), ...)`, and `_apply_event` inside the `while` loop
that drives every subsequent submission. None of these currently throws in the six Games
checked — but none of them is defended, either, and the invariant that keeps them safe today
(Case always has ≥1 Line Item, `ItemPrice` fields are always well-typed floats) is upstream of
this function, not inside it. `main()`'s only exception handler is `except KeyboardInterrupt`
— anything else prints a traceback and the process exits. Since `watch_games()` iterates
sequentially and there is no supervisor restarting `pixi run start`, **a single uncaught
exception on Game N ends Games N+1 through 100.**

This has not fired in 33 real Games so far — but 33 Games under *some* version of this code is
not the same denominator as 33 Games under the *current* code (only 8 have decision-log
visibility at all, §1), and none of those 8 has exercised a Case anywhere near the largest
size seen this tournament (39 items, §3's caveat). A bug that only shows up on an edge case is
exactly the kind that a small, non-adversarial sample won't surface. Sensitivity, not a
point estimate (there is no principled way to turn "0 failures in 8 trials" into a single
probability — CLAUDE.md's own noise-floor discipline applies here too):

| per-Game crash probability | P(survive all 67 remaining Games) |
| ---: | ---: |
| 0.25 % | 84.6 % |
| 0.5 % | 71.5 % |
| 1 % | 51.0 % |
| 2 % | 25.8 % |

Even a *small* per-Game risk compounds badly over 67 tries when the failure mode is "kills
every subsequent Game" rather than "costs this Game." That asymmetry, not the specific
probability, is the finding — and it inverts completely once Games fail independently instead
of fatally (§6.4's diff).

### 6.2 Thread-pool starvation on large Cases (silent, not a crash)

`fraud_detection.detect_fraud` fires **one `asyncio.to_thread` call per Line Item, all at once,
no concurrency limit**:

```python
# src/services/fraud_detection.py:102-105
results = await asyncio.gather(
    *(_timed_check(line_item, case) for line_item in case.line_items),
    return_exceptions=True,
)
```

`asyncio.to_thread` runs on the process's default `ThreadPoolExecutor`, sized by Python at
`min(32, (os.cpu_count() or 1) + 4)` unless the process sets its own. Measured on the machine
this audit ran on: `os.cpu_count() = 8` → **12 workers**. Strategy 2 alone adds 2 more
concurrent `to_thread` calls (its two ensemble draws), fast_path 1, strategy1 and strategy3
one each, plus 3 for the initial case-load file reads — call it ~7 non-fraud concurrent
`to_thread` calls on top of the fraud gate's one-per-item. The largest known Case (39 items,
Games 13/14) would ask for **~46 concurrent blocking I/O calls against as few as 12 worker
threads** on a similarly-sized machine. A queued (not yet started) call's own timeout doesn't
start counting until a worker actually picks it up, so on a big Case this queues roughly 3–4×
as many fraud checks as there are workers — some verdicts simply won't land before the 60 s
deadline, which is the exact failure Game 17 already suffered from a different cause (a
coverage-probability bug, not queueing) at a cost of −63,789. This is a **latent, unmeasured**
risk: the current code has never faced a Case above 18 items (§3), so this queuing has never
been observed to bind — it is derived from reading the code and the machine's own
`os.cpu_count()`, not from a settled Game.

### 6.3 Orphaned threads outlive their asyncio-level timeout

A second, compounding mechanism: `asyncio.wait_for(asyncio.to_thread(blocking_call),
timeout=X)` cannot actually stop `blocking_call` once its thread has started running — Python
threads aren't preemptible, and `concurrent.futures.Future.cancel()` is a no-op on a future
that's already executing. When the asyncio-level timeout fires, the *awaiting* coroutine gets
its `TimeoutError` and moves on (this is why Strategy 2's `draw()` correctly returns `{}`
rather than hanging — verified by reading `strategy2/strategy.py`'s `except Exception`
clause, which does catch `TimeoutError`), but the orphaned thread keeps running in the
background until the LLM client's *own* `timeout=` parameter fires inside the thread (up to
40 s for Strategy 2, per `LLM_TIMEOUT_SECONDS`), or — in the worst case, a hung TCP connection
that the SDK's own timeout doesn't cleanly abort — potentially longer. Combined with §6.2's
undersized pool, a degraded LLM endpoint overnight (exactly the unattended window in
question) could progressively occupy worker slots with threads that have already been given up
on by their own Game, starving later Games' calls with no error message and no crash — just
steadily slower or missing model evidence. This mechanism is consistent with what the timing
data for Games 26/27 would have looked like *if* they had been live (§2) — they weren't, so
this remains a structural read of the code rather than an observed incident, and should be
reported as such.

### 6.4 Cheapest fixes, ranked

**1. Wrap the per-Game call in `watch_games()`.** Converts "one bug ends the tournament" into
"one bug costs one Game" — directly inverts the §6.1 table (a 2 % per-Game crash rate becomes
a 2 % per-Game *cost*, not a 74 % chance of losing the rest of the tournament). Four lines,
zero behavioural change on the non-error path.

```diff
--- a/main.py
+++ b/main.py
@@ -318,7 +318,14 @@ async def watch_games() -> None:
         wait_seconds = (start_time - now).total_seconds()
         if wait_seconds > 0:
             logger.info("Game %s starts at %s.", game_id, start_time.isoformat())
             await asyncio.sleep(wait_seconds)
-        await run_game(game_id)
+        try:
+            await run_game(game_id)
+        except Exception:
+            # An uncaught exception here currently ends the tournament for every
+            # remaining Game, not just this one -- see
+            # docs/brainstorm/sebi/strats/review/phase-timing-audit.md §6.1. Losing one
+            # Game to a bug we haven't found yet is recoverable; losing the rest of an
+            # unattended overnight window is not.
+            logger.exception("Game %s crashed the runner; continuing to the next Game.", game_id)
```

**2. Size the thread pool for the biggest known Case, once, at process start.** Removes the
§6.2 queueing risk with no downside — idle threads cost nothing. Must happen once per process
(not per Game — creating a new executor every Game leaks the old one's threads), so it needs
an explicit loop rather than `asyncio.run()`'s implicit one:

```diff
--- a/main.py
+++ b/main.py
@@ -1,8 +1,9 @@
 from __future__ import annotations
 
 import argparse
 import asyncio
+import concurrent.futures
 import json
 import logging
 from collections.abc import Awaitable
@@ -335,15 +342,21 @@ def main() -> None:
     )
     args = parser.parse_args()
     logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
+    # Default executor is min(32, cpu_count+4) -- 12 workers on an 8-core box. The
+    # fraud gate alone fires one asyncio.to_thread call per Line Item, all at once
+    # (src/services/fraud_detection.py), and the largest known Case is 39 items,
+    # so the default pool queues roughly 3-4x its own size on the biggest Cases.
+    # See phase-timing-audit.md §6.2. Sized once, for the whole process.
+    loop = asyncio.new_event_loop()
+    asyncio.set_event_loop(loop)
+    loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=64))
     try:
         if args.game_id is not None:
-            asyncio.run(run_game(args.game_id, dry_run=args.retry_dry))
+            loop.run_until_complete(run_game(args.game_id, dry_run=args.retry_dry))
         elif args.retry_dry:
-            asyncio.run(retry_expired_games())
+            loop.run_until_complete(retry_expired_games())
         else:
-            asyncio.run(watch_games())
+            loop.run_until_complete(watch_games())
     except KeyboardInterrupt:
         logger.info("Stopping WireClaim runner.")
+    finally:
+        loop.close()
```

**3. (Lower priority — impact is already bounded to one Game.)** `get_released_key`'s retry
loop only retries on `APIError` with `status_code == 403`; a raw network fault
(`URLError`/`socket.timeout`/connection reset — `src/api/tournament.py`'s `_get()` only wraps
`HTTPError` into `APIError`, so anything else propagates as-is) isn't retried, contradicting
the architecture doc's "polls every 0.5 s until it succeeds or the deadline passes." Today
this still only costs the one Game (`run_game`'s outer handler catches it → blind floor
stands), so it's not a tournament-survival fix, just a single-Game resilience gap worth
closing cheaply:

```diff
--- a/src/data/case_loader.py
+++ b/src/data/case_loader.py
@@ -1,10 +1,14 @@
 from __future__ import annotations
 
 import asyncio
+import logging
 import re
 from dataclasses import replace
 from pathlib import Path
+from urllib.error import URLError
 
 from src.api import APIError, get_decryption_key
 from src.data.models import CaseData, LineItem
 
+logger = logging.getLogger(__name__)
+
@@ -30,6 +34,11 @@ async def get_released_key(game_id: int, deadline: float) -> str:
         except APIError as error:
             if error.status_code != 403:
                 raise
             await asyncio.sleep(min(0.5, max(deadline - loop.time(), 0.0)))
+        except (URLError, TimeoutError, OSError) as error:
+            # A DNS blip or dropped connection during overnight polling is not "the
+            # key isn't out yet" -- retry it exactly like a 403 instead of abandoning
+            # the Game to the blind floor over one transient network fault.
+            logger.warning("Game %s key poll failed transiently: %s", game_id, error)
+            await asyncio.sleep(min(0.5, max(deadline - loop.time(), 0.0)))
     raise TimeoutError(f"Game {game_id} did not release its decryption key in time.")
```

### 6.5 Risks checked and ruled out (or not checkable from here)

- **Disk filling.** `var/` is 91 MB after 33 Games plus all development artifacts (`du -sh
  var/`); `var/cases` is ~5.5 MB/Case, `var/transactions` ~22 MB for 33 Games. Projected full
  100-Game growth is well under 1 GB against **97 GB free** on this machine (`df -h`). Not a
  risk here; worth a five-second check on whatever machine actually runs the overnight window
  if it's different hardware.
- **Clock drift.** The in-Game 60 s deadline is driven by `loop.time()` (monotonic,
  `asyncio`'s own clock), immune to wall-clock drift. Only *when to start* a Game
  (`watch_games()` comparing `datetime.now(timezone.utc)` against the API's `start_time`) is
  wall-clock-dependent. All six clean Games' key-fetch/case-load timings looked nominal
  (sub-3-second `case_load`, per §3), so no drift is evident today; low risk on a properly
  NTP-synced machine, not independently verifiable from the repo.
- **LLM token/quota limits.** Not verifiable from filesystem state — requires the provider's
  account dashboard. The diagnostic signature to watch for in future decision logs:
  `model_draws`/`model_items` dropping to 0 or `rule: "uninformed-constants"` appearing across
  **many consecutive** Games (as opposed to Game 32's isolated single-draw loss, which reads
  like an ordinary one-off timeout, not exhaustion).
- **Key fetch 404 / non-403 error.** Already safe today — any `APIError` with a status other
  than 403 propagates immediately out of `get_released_key`, is caught by `run_game`'s
  outer handler, and the Game finishes on the blind floor. Costs one Game, not the tournament.
  (§6.4's fix 3 only extends this same safety to *non*-`APIError` network faults, which
  currently aren't retried at all.)

---

## 7. What this audit could not establish

- **No causal claim about why the net swung positive.** §5's Games 1–25 vs. 26–32 comparison
  clears the noise floor in both directions, but several changes landed the same evening
  (decision logging, `LIMIT_CEILING`, coverage fixes, Strategy 2 constants) — this data cannot
  separate "the merge landed on time" from "the constants got better."
- **No large-Case telemetry under current code.** Every one of the six clean Games maxes out
  at 18 Line Items; the tournament's largest known Case (39) has never been seen by the code
  that's live right now. §6.1 and §6.2's risks are specifically concentrated there and are
  reported as structural findings from reading the code, not as measured incidents.
- **No point-estimate crash probability.** 0 failures observed in 8 (or, loosely, 33)
  Games is not enough trials to turn into a single number — §6.1 gives a sensitivity table
  instead, per the same noise-floor discipline CLAUDE.md applies to euro figures.
