# Model bake-off retest — does terra beat mini once the prompt tells the truth?

Scope: read-only against `src/` (nothing touched); all new code lives under
`scripts/experiments/` (`retest_draw.py`, `retest_score.py`, `live_window.py`). Every LLM
call is a fresh, unmodified `request_evidence` path draw — same `build_input_content` /
`build_request_text` plumbing the live path uses, images attached, explicit `model=`
instead of `get_model_name()` — cached to `var/experiments/model_bakeoff_retest/` so nothing
here is ever re-billed. Concurrency capped at 2 throughout. `gpt-5.6-luna` was **not** drawn:
the task explicitly deprioritised it, and the mini/terra sweep alone was already ~160 calls
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
after the last one. That cost ~18% of the wall clock but meant zero calls were in flight
during a live Game boundary for the whole sweep. The live runner (`main.py` / `pixi run
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
Policy §7.1.1(a)/(b), "the insurable value under Part 6", exactly the agreed-value clause
that removes the per-item sub-limit).

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

*(filled in once the full sweep across all 42 extracted Cases finishes drawing — see
`var/experiments/model_bakeoff_retest/score_summary.json` and the run log for the exact
Games covered.)*

---

## 2. Latency against the live 55s budget

*(pending — see above)*

---

## 3. Euro replay, held-out folds

*(pending — see above)*

---

## 4. The three questions

*(pending full sweep)*
