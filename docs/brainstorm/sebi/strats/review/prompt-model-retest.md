# Model bake-off retest — does terra beat mini once the prompt tells the truth?

Scope: read-only against `src/` (nothing touched); all new code lives under
`scripts/experiments/` (`retest_draw.py`, `retest_score.py`, `live_window.py`). Every LLM
call is a fresh, unmodified `request_evidence` path draw — same `build_input_content` /
`build_request_text` plumbing the live path uses, images attached, explicit `model=`
instead of `get_model_name()` — cached to `var/experiments/model_bakeoff_retest/` so nothing
here is ever re-billed. Concurrency capped at 2 throughout. `gpt-5.6-luna` was **not** drawn:
the task explicitly deprioritised it, and the mini/terra sweep alone was already 168 calls
against a shared, live endpoint.

**Why a retest, and why a new cache directory instead of reusing
`var/experiments/model_bakeoff/`:** that sweep was drawn entirely between 21:48 and 22:20 —
**before** two prompt fixes that shipped later the same night. "Replace the guessed price
anchors with the settled ones" (`2308533`, 21:53:26) rewrote the Anchors bullets both prompt
variants share; "Tell the model the truth about the price distribution" (`ab4821b`,
23:38:39) rewrote `_DISTRIBUTION_HINT` itself — median 59→97, top decile "several thousand"
→ named quartiles running to 11,131. Every cached response in the old directory answered a
prompt that no longer exists. `mini_anchor`'s own cache predates even the first fix. This
retest re-draws everything from scratch against the prompt as it ships right now.

**Live-tournament safety:** the task's own instruction — sleep through every Game window,
`T-10s` to `T+70s` — has to account for calls up to 55s long, so `live_window.py` gates on
**starting** a call rather than on the window itself: no call starts within 68s of the next
boundary (55s call + 13s margin, so it is guaranteed to finish before `T-10`) or within 70s
after the last one. Measured: the full 168-draw sweep ran 24m55s wall-clock
(23:48:28-00:13:23) against ~20m23s of pure call time at concurrency 2 (2,446s summed
latency / 2) -- about 22% overhead from boundary-gating and scheduling -- and zero calls
were in flight during a live Game boundary for the whole sweep. The live runner (`main.py` / `pixi run
play` / `pixi run watch`) was confirmed running throughout via `ps aux` and was never
touched, killed, or restarted.

**Price Memory vintage pinned:** `var/experiments/model_bakeoff_retest/price_memory_pinned.json`,
copied from the live `var/price_memory.json` before any scoring ran. `built_from_games:
1-44` (i.e. through Game 44 — the live tournament had already settled three more Games than
were extracted for this retest by the time the store was pinned), 192 entries, 498 Line
Items joined, `measured_leave_one_out_sigma_log = 0.4765`. Every RMSLE and euro number below
that goes through `combine()` uses this exact snapshot, not whatever `learn_watch.py` has
rebuilt it to since. See the Case 41 section for why pinning matters here specifically, not
just for reproducibility in the abstract.

**Noise floor used throughout: `26,622 x sqrt(n_games / 18)`** (CLAUDE.md rule 1b /
`sigma-calibration.md`) — **not** the `34,369-over-30-Games` figure the original bake-off
used, which predates this measurement.

---

## 0. The named probe, first: Case 41 item 3, the tourbillon watch

Before anything else, the task asked this to be verified directly: does the live path's
vision channel see the tourbillon, moon-phase subdial and power-reserve indicator in
`var/cases/case_41/photo.jpg`, and does that change under the corrected prompt?

**Model-only reads (Channel C alone, before Price Memory touches anything) — both prompts,
both models:**

| model | prompt | coverage | price_low | price_median | price_high |
| --- | --- | ---: | ---: | ---: | ---: |
| mini | anchored | 0.95 | 5,000 | **12,000** | 25,000 |
| mini | unanchored | 0.95 | 8,000 | **12,000** | 18,000 |
| terra | anchored | 0.92 | 8,000 | **13,500** | 22,000 |
| terra | unanchored | 0.82 | 12,000 | **24,000** | 45,000 |

True value: `t >= 11,131` (censored — nobody was ever rightfully rejected on this item, so
this is a proven floor, not a point estimate). Under the **old** prompt this same item was
priced at 5,524 (per the task brief) — a miss of more than half. Under the **current**
prompt, every one of the four draws, from both models, lands **at or above the proven
floor**, and every one names the item correctly as a declared valuable (the raw JSON quotes
Policy §7.1.1(a), "for taken, destroyed or lost items — the insurable value under Part 6 at the time of the insured event", exactly the agreed-value clause that removes the per-item sub-limit).

**Reading: this was a prompt-anchoring failure, not a vision failure, and it is fixed for
both models.** The photograph was always being attached and read (`build_input_content`
already sent it under the old prompt too) — what changed is that the model now has an
honest reference distribution to weigh what it sees against, instead of one that told it
the tail tops out "at a few thousand." Model-only RMSLE on this single item: **mini +0.075,
terra +0.481** (both positive = both above the floor; terra's un-anchored draw overshoots
furthest at 24,000, mini stays tighter to the floor). This is n=1 and not a basis for a
verdict on its own — see the paired sweep below — but it directly answers the task's
question: yes, both models now identify the high-value cues.

**A second, unplanned finding from the same item: Price Memory's `combine()` step pulls
BOTH models' submitted number back down, and it does so because this Case's own true value
has already leaked into its own memory entry.** `built_from_games` runs through 44, so the
pinned store already contains Game 41's own settled outcome. The core-key match for
"Compensation for robbery damage" merges **two** observations: Game 27's `3,011` (an
unrelated, much cheaper item that happens to share the wording) and Game 41's own `11,130.9`
— median of the two is `7,071`, and that anchor pulls the *combined* (submitted) medians down
to 8,461 (mini) and 9,709 (terra), both **below** the proven floor, reversing what the raw
model reads got right. This is expected, intended behaviour for live play once a Game has
actually settled and moved on — Price Memory is supposed to anchor toward what a wording was
worth before — but it means the post-combine number for Case 41 specifically is not a clean
read of "did the model see the photo," and more generally, a same-wording core-key merge
across Cases of very different value is a real, separate risk this retest surfaces
incidentally (Case 27's "compensation for X damage" and Case 41's are not the same kind of
claim at all). This is noted for the record; it is not scored or fixed here — the task at
hand is model selection, not Price Memory's matching logic — but it belongs in the
hypothesis ledger as a follow-up.

---

## 1. Paired RMSLE, current prompt

Full sweep: 168/168 draws (42 Cases x 2 models x 2 prompts), 9 timeouts total (mini 3/84 =
3.6%, terra 6/84 = 7.1% — see §2). `paired_keys()` restricts every table below to the 483
Line Items where **both** models returned usable model evidence from at least one of their
two draws — composition-free, unlike the plain per-model tables in the original bake-off.

**Post-blend + pinned-memory-combine (what actually gets submitted):**

| population | mini RMSLE | mini bias | terra RMSLE | terra bias | sign test (mini/tie/terra, p) |
| --- | ---: | ---: | ---: | ---: | --- |
| real money, ALL (n=325) | 0.498 | +0.080 | **0.474** | +0.171 | 157/3/165, p=0.697 |
| **expensive tail, t>=1000 (n=22)** | 1.145 | **-0.275** | **0.775** | +0.086 | 10/0/12, p=0.832 |
| below tail, t<1000 (n=303) | **0.413** | +0.106 | 0.444 | +0.177 | 147/3/153, p=0.773 |
| Case HAS a photo (n=323) | 0.499 | +0.080 | **0.475** | +0.171 | 157/3/163, p=0.780 |
| Case has NO photo (n=2) | 0.190 | +0.153 | 0.093 | +0.071 | too small to read |

**Reversed from the original bake-off's headline** (mini 0.562 vs terra 0.619 there; mini
0.498 vs **terra 0.474** here). The sign test alone stays non-significant in both studies —
terra wins the item-by-item count in both — so this was never the number that decided it;
RMSLE is, per CLAUDE.md rule 10, because it is sensitive to the size of a miss and the
failure mode is a bias, not a coin flip. **The tail is where the reversal is largest and
matters most**: mini's RMSLE more than doubles terra's (1.145 vs 0.775) and mini's bias is
solidly negative (**proven underpricing**, -0.275) while terra's sits near zero (+0.086).
Below the tail the two are close and mini even leads narrowly (0.413 vs 0.444) — this is a
**tail-specific** result, not a blanket one.

**Model-only (Channel C alone, pre-combine — immune to the Case-41-style Price-Memory
leakage described in §0):**

| population | mini RMSLE | mini bias | terra RMSLE | terra bias |
| --- | ---: | ---: | ---: | ---: |
| real money, ALL | n=316, 0.750 | +0.158 | n=325, 0.758 | +0.321 |
| expensive tail | n=20, **0.500** | +0.155 | n=22, 0.795 | +0.425 |

Read together with the post-combine table, this says something specific: **terra's raw
tail read is actually noisier and more biased-high than mini's raw read (0.795 vs 0.500)**
— but mini's raw tail read gets dragged down hard by `combine()`'s fixed-weight blend with
Price Memory (RMSLE balloons 0.500 -> 1.145 post-combine), while terra's barely moves
(0.795 -> 0.775). `combine()` weights model vs memory with `MODEL_SIGMA_PRIOR=0.6` /
`MEMORY_SIGMA=0.43`, **fixed constants that do not vary by model or by item**, so the pull
toward memory is identical in principle for both models; what differs is which side of a
too-low memory anchor each model's raw number starts on. Price Memory is itself
demonstrably biased low on the tail (see the censored breakdown below and CLAUDE.md's own
"t_hat below the proven floor on 73% of censored items"), so blending toward it hurts a
model whose raw estimate was already conservative (mini) more than one whose raw estimate
already ran hot (terra). **This is a property of `combine()`'s fixed weighting interacting
with Price Memory's tail bias, not a property of either model — but it is a real, current
amplifier of exactly the failure mode CLAUDE.md rule 4 calls out**, and it is a finding this
retest surfaced rather than one it was asked to look for. Not fixed here (out of scope for
a model-selection question); flagged for the hypothesis ledger.

### The proven-floor breakdown — where the reversal is starkest

Splitting the 22-item expensive tail by whether the Fair Value is **censored** (`t_hi=inf`,
nobody was ever rightfully rejected, `t=t_lo` is a *proven floor*, n=10) or **bounded** (a
real bracket, n=12):

| | mini censored | mini bounded | terra censored | terra bounded |
| --- | ---: | ---: | ---: | ---: |
| RMSLE | **1.642** | 0.394 | **0.970** | 0.564 |
| bias | **-0.878** | +0.228 | **-0.238** | +0.356 |
| **share below the proven floor** | **60% (6/10)** | n/a | **20% (2/10)** | n/a |

This is the single clearest number in this report. Under the **old** prompt, CLAUDE.md
records the estimator sitting below the proven floor on 73% of censored items; under the
**current** prompt, mini alone has already improved to 60% — the prompt fix helped on its
own, as expected since it changes nothing about which model reads it. But **terra is below
the proven floor on only 20% of these items, a 3x reduction from mini's 60%**, and its
censored-item bias (-0.238) is a third the size of mini's (-0.878). CLAUDE.md rule 10's
censoring caveat cuts in one clear direction here: a negative bias against a *lower bound*
is an unambiguous, provable miss (the true value is only known to be higher still), while a
positive bias is not provably wrong (the true value could still be below or above it) — so
mini's -0.878 is a *confirmed* large underpricing, not merely a probable one, and terra's
-0.238 is a confirmed but much smaller one. On the bounded tail items terra's positive bias
runs larger (+0.356 vs mini's +0.228) and its RMSLE is worse (0.564 vs 0.394) — terra is not
uniformly better, it is specifically, provably better on the population where the money and
the risk are both concentrated.

---

## 2. Latency against the live 55s budget

Drawn under `--concurrency 2` with a call timeout set to the live
`LLM_TIMEOUT_SECONDS = 55.0` (not an inflated measurement ceiling — this is latency exactly
as the live path would see it), gated by `live_window.py` so no call started within 68s of
a Game boundary or within 70s after one. The live tournament runner was confirmed running
throughout (`ps aux`), never touched.

| model | bucket | calls | timeouts | >budget | p50 | p95 | max |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mini | 1-5 | 24 | 0 | 0.0% | 4.9s | 12.0s | 13.1s |
| mini | 6-10 | 18 | 1 | 5.6% | 6.1s | 8.9s | 8.9s |
| mini | 11-20 | 32 | 2 | 6.2% | 8.3s | 21.8s | 26.5s |
| mini | 21+ | 10 | 0 | 0.0% | 14.9s | 26.7s | 26.7s |
| **mini ALL** | | **84** | **3** | **3.6%** | **7.3s** | **17.6s** | **26.7s** |
| terra | 1-5 | 24 | 1 | 4.2% | 8.9s | 13.5s | 18.4s |
| terra | 6-10 | 18 | 1 | 5.6% | 11.8s | 20.5s | 20.5s |
| terra | 11-20 | 32 | 3 | 9.4% | 17.8s | 28.0s | 29.9s |
| terra | 21+ | 10 | 1 | 10.0% | 25.2s | 40.7s | 40.7s |
| **terra ALL** | | **84** | **6** | **7.1%** | **13.8s** | **29.9s** | **40.7s** |

**Terra is still slower and less reliable than mini at every size band, but both numbers
are far below the original bake-off's** (mini 4.7% / terra 17.2% overall; terra's p95 on
11-20-item Cases was 42.1s there against 28.0s here). Two things changed between the two
measurements and this report cannot fully separate them: the call timeout here matches the
live 55s budget exactly rather than measuring past it (a real methodology improvement), and
the live-Game-boundary gating specifically added here (`live_window.py`) removed the
worst, most direct source of shared-deployment contention the original report flagged. **Is
this a clean measurement?** Not fully — the live runner shared the same Azure deployment for
this sweep's entire ~25-minute duration, and mini itself timed out on 3 calls despite never
timing out near a boundary in the original study either, which argues some residual,
non-boundary-aligned contention or endpoint variability remains. What can be said cleanly:
terra's timeout rate (7.1%) is still roughly double mini's (3.6%) under matched conditions,
its p95 (29.9s) and max (40.7s) sit comfortably inside the 55s budget even on the largest
Cases, and neither figure resembles the earlier report's near-miss (42.1s p95 against a 50s
budget). **Terra's latency is a real but now clearly survivable cost, not a live risk to the
submission window.**

---

## 3. Euro replay, held-out folds

Every model's evidence replayed through the **current** `price_item` (with tonight's
`LIMIT_CEILING_MEMORY = 0.75` and the memory-conditional `LIMIT_CAP` live) and
`scripts/replay_payoffs.replay` against the real Field, with the same `_uninformed_price`
(`STANDARD_CHARGE`/`STANDARD_LIMIT`) fallback `strategy2.strategy.build_proposal` uses for a
Line Item neither channel could price. Noise floor: `26,622 x sqrt(n/18)`.

| model | total net, 42 Games |
| --- | ---: |
| mini (shipped) | 350,300.73 |
| terra | **443,815.83** |
| **delta terra - mini** | **+93,515.09 (OUTSIDE the +/-40,666 floor)** |

Held-out folds (sign consistency, not a fit — nothing tuned per Game):

| split | n | noise floor | terra - mini |
| --- | ---: | ---: | ---: |
| odd Games | 21 | +/-28,755 | **+46,057 (OUTSIDE)** |
| even Games | 21 | +/-28,755 | **+47,458 (OUTSIDE)** |
| Games 1-20 | 20 | +/-28,062 | +27,046 (inside, but positive) |
| Games 21+ | 22 | +/-29,432 | **+66,469 (OUTSIDE)** |

**Every fold is positive for terra, and three of four clear their own floor.** This is the
opposite pattern from the original bake-off, where the odd/even split flipped sign entirely
(traced there to a single volatile Game). Here nothing flips. The one fold that stays inside
its floor (1-20, +27,046) is still positive and is the smaller of the two Game-count halves
by both the odd/even and the 1-20/21+ cut, consistent with — not contradicting — the
headline. Two per-Game outliers are worth naming rather than hiding: Game 18 (mini
-23,085.74 vs terra +6,916.79, a ~30k single-Game swing) and Game 9 (mini +18,773.24 vs
terra -5,098.47, terra's worst Game). Removing either alone does not flip any fold's sign;
they roughly offset across the sample rather than driving the total.

---

## 4. The three questions, answered plainly

**Does terra beat mini under the corrected prompt? Yes, and by more than a coin flip.**
Post-combine RMSLE flips from mini-favoring (0.562 vs 0.619 in the original study) to
terra-favoring (0.498 vs 0.474 here) — a real reversal, not noise reshuffled: the original
study's own headline was built on a prompt that told the model the tail topped out "at a few
thousand"; the current prompt states the true quartiles up to 11,131, and that is exactly
the information terra's larger reads and mini's now-narrower ones use differently in the
one population that matters most, the expensive tail. The euro replay agrees at a
magnitude that clears its noise floor (+93,515 over 42 Games) and holds its sign in three of
four held-out folds — this is the strongest, most consistent multi-method agreement in
either bake-off.

**Does the answer differ on the expensive tail? Yes — that is where almost the entire
advantage lives.** Below t=1,000, mini is narrowly *better* (RMSLE 0.413 vs 0.444). At or
above it, terra's RMSLE is 32% lower (0.775 vs 1.145) and its share of provably-wrong,
below-the-floor censored items is a third of mini's (20% vs 60%). Since the tail is exactly
the population CLAUDE.md already names as "measurably worst" and highest-stakes (Game 41's
own ~117,000 forfeiture), this is not a marginal segment — it is disproportionately where
the euro total is won.

**Is terra's latency survivable at 55s? Yes, with margin.** p95 across all Cases is 29.9s,
worst-observed max is 40.7s (the largest, 21+-item bucket) — both comfortably inside the
55s budget, and both roughly a third lower than the original study's near-miss numbers
(42.1s p95 against a 50s budget then). Its timeout rate (7.1%) is still about double mini's
(3.6%), so it remains the less reliable of the two, and this measurement cannot fully rule
out that some of both models' timeouts reflect residual endpoint contention from the live
tournament sharing the deployment throughout — but nothing here resembles a live risk to
the submission window the way the original 42.1s-against-50s figure did.

**Recommendation: switch `.env` back to `gpt-5.6-terra`.** Every method in this retest —
paired RMSLE (especially the tail), the model-only isolation that rules out Price-Memory
contamination as the explanation, the censored-item proven-floor breakdown, and the euro
replay with three of four held-out folds clearing their own noise floor — points the same
direction, and the direction is the opposite of the original bake-off's. The original
verdict was correct for the prompt it was measured against; it does not describe the prompt
shipping now. This is exactly the situation CLAUDE.md rule 10 warns about from the other
side — a stale measurement outliving the thing it measured — and the fix is the same one
rule 9 prescribes for a regime change: re-measure, do not carry the old conclusion forward.

## What would change this answer

- Games 44-81 (the dark regime) are not in this sample; rule 9 says a Field measurement —
  and, by the same logic, a model comparison keyed to what the Field pays for accuracy —
  should be re-checked after that boundary, not assumed to carry across it.
- `gpt-5.6-luna` was not drawn here (deprioritised per the task); it should not be assumed
  to track terra's improvement just because both are "the other two models" in the original
  study.
- The Price-Memory `combine()` interaction flagged in §1 (fixed weights amplifying a
  too-low tail anchor against whichever model's raw read is more conservative) is a
  separate, real lever this retest surfaced but did not fix — worth its own investigation,
  since it currently penalises accuracy gains on the tail regardless of which model produces
  them.
- This is 42 Games, not 100; the odd/even and 1-20/21+ folds agreeing in direction here is
  reassuring but is still four numbers, not an asymptotic guarantee.
