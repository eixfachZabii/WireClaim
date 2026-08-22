# Model bake-off: does the frontier model beat the mini we're running?

`.env` set `AZURE_OPENAI_MODEL=gpt-5.4-mini` when this measurement started. `src/api/llm.py`'s
own `DEFAULT_MODEL` is `gpt-5.6-terra`, and probing the endpoint
(`https://claim-to-fame-ai.openai.azure.com/openai/v1/`) turns up exactly three deployments
that actually answer out of 412 listed: `gpt-5.4-mini`, `gpt-5.6-terra` and `gpt-5.6-luna`.
Nobody had ever measured whether the bigger model reads a Case better. This is that
measurement.

**Mid-measurement update:** `.env` was swapped to `gpt-5.6-terra` and the runner restarted at
21:48, before this harness had produced any result — so the question this document actually
answers is no longer "should we ship the swap tonight" but "should the swap that already
happened stand." `LLM_TIMEOUT_SECONDS` was also raised 40 → 50 at 22:00 in response to this
harness's own early latency numbers. Both changes are reflected in the numbers below (the
latency section reports against the 50s budget) and in the verdict.

**The context that makes this the highest-value open question in the repo:** every constant
in `src/pricing.py` has been swept to exhaustion — the coverage verdict, the Limit's level,
every conditional Charge rule — and each either doesn't move money outside the noise floor or
fails held out. The module's own docstring says it outright: *"the band is not calibrated,
and that is the real problem… Fixing the band is worth more than any constant in this file,
and it belongs in the evidence layer, not here."* H3 in the hypothesis ledger puts a number on
the prize: **+101,695** over Games 1–24 is reachable by item accuracy alone (moving each
median to its own true Fair Value, band and coverage held fixed) — and none of it is reachable
by a function of the number we already have (H2, falsified). The only lever left is better
evidence, and the model is the evidence layer's biggest unexamined variable.

## Method

Real, unmodified Strategy 2 evidence prompts (`ENSEMBLE_PROMPTS` — `PROMPT` anchored,
`PROMPT_UNANCHORED` un-anchored — from `src/services/strategies/strategy2/prompts.py`), the
same `build_input_content` / `build_request_text` plumbing the live path uses
(`src/services/strategies/strategy2/model.py`), fired at each of the three deployments with an
explicit `model=` instead of `get_model_name()`. Nothing in `src/` was touched; the harness
lives in `scripts/experiments/model_bakeoff_draw.py` (draws, caches every raw response to
`var/experiments/model_bakeoff/`) and `scripts/experiments/model_bakeoff_score.py` (scores the
cache — RMSLE, band calibration, coverage confusion, latency, euro replay).

For every settled Game 1–32: two ensemble draws per model (anchored + un-anchored) →
`blend()` → `combine()` with the (free, deterministic) Price Memory channel → `price_item()`
— exactly the sequence `strategy2.strategy.propose` runs live. `gpt-5.4-mini`'s anchored draw
reuses the already-cached `var/evidence/case_NN_model.json` (dumped earlier today under the
live `.env`, so it is genuinely today's shipped model) rather than re-billing it; every other
cell is a fresh call. Concurrency capped at 2 throughout, matching the live ensemble's own
fan-out and per this task's rate-limit instruction — this and the live tournament's own
submissions are the only things allowed to hit this endpoint tonight.

Ground truth is `scripts/invert_fair_values.py`'s exactly-recovered `[t_lo, t_hi)` bracket per
Line Item (`--verify` reproduces every published net to the cent). RMSLE population follows
`scripts/leak_sigma.py` exactly — the script that produced the "0.80" figure already in
`src/pricing.py`'s docstring, cross-checked directly against it below — **not** a bare
bounded/unbounded split:

- **real money** (`t_lo > 0`, `t_hi ≠ ∞`) — the only population price accuracy can move the
  payoff on, and the headline RMSLE number.
- **worthless-but-bounded** (`t_lo ≤ 0`, `t_hi ≠ ∞`) — "uneconomic to score": coverage should
  already zero the Limit here, so price accuracy buys nothing. Reported so it never gets
  silently pooled into the headline (it did, once, in an earlier draft of this harness, and
  inflated every model's RMSLE by 2–3×).
- **censored** (`t_hi = ∞`) — nobody was ever rightfully rejected, so `t` defaults to the
  lower bound; optimistic by construction (CLAUDE.md rule 10's censoring caveat).

Euros come from `scripts/replay_payoffs.replay` against the real Field, per Game, per model,
holding every opponent's real Charge and Limit fixed — the same counterfactual harness whose
self-check reproduces all fourteen-plus published nets to the cent. The stated noise floor is
**±34,369 over 30 Games**, scaled as `34,369 × √(n/30)` for any other window size.

### Confound: every latency number here was measured under shared-deployment load

This harness's draw sweep ran concurrently with the live tournament runner for its entire
duration, on the *same* Azure OpenAI resource — and, for the ~50 minutes after 21:48, on the
*same terra deployment* the live runner was also calling every ~12.6 minutes. Direct evidence
this mattered: a side-by-side probe of Case 31 (18 items) run once outside this sweep found
`gpt-5.4-mini` **timing out at 91s on the `fast` tier**, something it never did anywhere else
in this measurement (its p95 elsewhere is ~27s, and the same Case scored 6.5s an hour earlier)
— while `terra`, measured at the same time, came back at 17–20s, markedly *better* than an
earlier same-Case probe of 19.4s/>40.8s/51.1s. Latencies that swing that much in opposite
directions between two probes of the *same Case* are not a property of the models; they are
queueing on a shared deployment.

**Consequence: every timeout rate and p95 in this report is an upper bound on what either
model would show against an unloaded endpoint, not a clean per-model comparison.** The
*relative* ordering (terra and luna both timing out meaningfully more than mini) is probably
still informative, since mini's own calls shared the same contention and still came out
fastest — but the absolute numbers (terra's 47.1s max, its 42.1s p95 on 11–20-item Cases)
should be read as "at least this bad under today's combined load," not as terra's latency in
isolation. This is a real limitation of measuring a live model change with a live tournament
running on the same account, and it could not be fully avoided without either stopping the
sweep (which would have meant a much smaller sample) or stopping the live runner (never on the
table). Concurrency was already capped at 2 for the whole run; once this was identified
mid-measurement the remaining draws were left to finish under the existing cap rather than
restarted with a tighter one, because this harness's standing instruction is not to kill or
restart a running process — the alternative was accepting a small further stretch of shared
load against letting ~50 minutes of already-billed calls go to waste with the sweep 75%+ done.

## Headline

**No. On the complete sweep (192/192 draws, all 32 Games, all three models) neither
`gpt-5.6-terra` nor `gpt-5.6-luna` reads a Case more accurately than the shipped
`gpt-5.4-mini` — both are measurably *worse* on RMSLE, terra's euro loss clears the noise
floor, and terra is also the least reliable inside the 60-second window. Revert `.env` to
`gpt-5.4-mini`.**

Four independent tests now agree, all on the full n=152 paired, 32-Game sample: the paired
same-item RMSLE comparison (mini 0.562 against terra 0.619 and luna 0.613 — mini wins, and
the gap widened rather than closed as the sample grew from n=35 to n=152); the euro replay
(mini 224,276 against terra 170,616, **a −53,660 delta that is now outside the ±35,496 noise
floor** — the first non-noise result in this measurement — and luna's −27,014, inside the
floor but the same direction); the sign-flip that looked like pure noise on odd/even splits at
n=20 Games has *not* resolved into a real regime signal now that all 32 Games are in (see
below); and the mini+terra hybrid, which does not fix terra's RMSLE problem (0.575, still
worse than mini alone) even though its euro total happens to land above mini's inside the
noise floor. The one place the three models visibly differ beyond accuracy is latency and
reliability, and there mini wins outright: terra timed out on 17.2% of its 64 real Case calls
against mini's 4.7%, concentrated on exactly the largest, highest-value Cases.

An earlier unpaired read on a partial sample (~70 of 192 draws) had terra's real-money RMSLE
looking slightly better than mini's (0.544 vs 0.565), and even the first *paired* passes (n=35
to n=99) only showed a non-significant lean toward mini. **The full sample resolved the
direction rather than reversing it:** every checkpoint from n=35 through n=152 has mini in
the lead, and the margin grew as more data arrived, which is the opposite of what a
composition artefact or early-sample noise would do. Model-only RMSLE for all three still
lands close to the shipped estimator's known ~0.77–0.85 (`scripts/leak_sigma.py`, itself
~0.77–0.80) — mini 0.848, terra 0.845, luna 0.874 — essentially tied; the separation between
the models opens up specifically in the *post-blend, post-memory* number, which is the one
that actually matters because it's what gets submitted.

## Paired comparison — the number that actually decides this

`scripts/experiments/model_bakeoff_paired.py` restricts to Line Items where **all three
models** returned usable evidence (real-money population: `t_lo > 0`, bounded), so the
comparison is composition-free. Reported at each checkpoint as the sweep progressed, to show
the direction was not drifting or reversing as N grew — it was firming up:

| n (paired) | mini RMSLE | terra RMSLE | luna RMSLE | mini vs terra (sign test) | mini vs luna (sign test) |
| ---: | ---: | ---: | ---: | --- | --- |
| 35 | 0.518 | 0.536 | 0.564 | 19–0–16, p=0.736 | 16–1–18, p=0.864 |
| 91 | 0.459 | 0.505 | 0.507 | 46–0–45, p=1.000 | 45–2–44, p=1.000 |
| 99 | 0.490 | 0.548 | 0.533 | 51–0–48, p=0.841 | 51–2–46, p=0.685 |
| **152 (final)** | **0.562** | **0.619** | **0.613** | 70–0–82, p=0.372 | 78–4–70, p=0.565 |

The sign test alone never clears significance (mini actually loses the item-by-item count to
terra, 70–82, at the final sample) — but RMSLE is a squared-error statistic, and CLAUDE.md
rule 10 is explicit about why that's the number to trust here: *the failure mode is a bias,
and a count of who-wins-more-often cannot see the size of a miss.* Terra wins more coin
flips and loses the ones it loses much worse — its `bias` term (+0.217 against mini's +0.178)
and `dispersion` (+0.580 against +0.533) are both worse, meaning terra is both more
overconfident-in-the-wrong-direction on average and noisier. **Reading:** an earlier informal
impression (three items on Case 30, terra visibly closer to `t`) did not survive n=35 and has
not reappeared at any later checkpoint, including the final one. Three items is noise, not a
signal, at the item level just as one Game is noise at the Game level.

## Latency by Line Item count, against the 50s budget

`LLM_TIMEOUT_SECONDS` was raised 40 → 50 mid-measurement (commit at 22:00, in response to this
harness's own early numbers). Final numbers, all 32 Cases, `n` is call attempts across both
ensemble prompts (18/14/24/8 per model in each bucket — identical denominators now, since
every model got the same 64 attempts):

| bucket | mini timeout / p50 / p95 | terra timeout / p50 / p95 | luna timeout / p50 / p95 |
| --- | --- | --- | --- |
| 1–5 items | 0% / 4.6s / 10.7s (n=18) | 11% / 9.0s / 16.8s (n=18) | 6% / 12.9s / 16.6s (n=18) |
| 6–10 items | 7% / 6.9s / 9.8s (n=14) | 21% / 10.8s / 22.2s (n=14) | 7% / 18.6s / 23.4s (n=14) |
| 11–20 items | 8% / 9.5s / 26.6s (n=24) | 21% / 21.0s / 42.1s (n=24) | 17% / 26.1s / 45.3s (n=24) |
| 21+ items | 0% / 13.6s / 15.0s (n=8) | 13% / 24.7s / 47.1s (n=8) | 0% / 37.0s / 42.7s (n=8) |
| **all sizes** | **4.7% / 8.1s / 15.0s (n=64)** | **17.2% / 15.1s / 28.4s (n=64)** | **9.4% / 20.8s / 41.9s (n=64)** |

No model is timeout-free once Cases get large, but terra is worse than mini at every size
band and worse overall than both alternatives — **its all-sizes timeout rate (17.2%) is
3.7× mini's (4.7%) and nearly double luna's (9.4%).** Its **p95 on 11–20-item Cases already
sits at 42.1s** — inside the raised 50s budget only by a margin that a slightly slower draw
would erase. Luna is slower in the typical case (higher p50 throughout, and its overall p95
of 41.9s is the closest of the three to the budget) but fails outright less often — it trades
speed for reliability where terra has neither advantage. The 21+ bucket — the Cases carrying
the most money (Game 17 alone: 20 items, 145,163 of oracle Issuer income per the
coordinator's own measurement) — stays the thinnest cell (n=8 per model) even at full sample,
so read it as directional; every model's largest-Case p95 sits uncomfortably close to the
budget there, and terra's max observed latency (47.1s) is again the closest of the three to
blowing through it outright. Beyond outright timeouts, luna produced two malformed-JSON
responses (`JSONDecodeError`) that mini and terra did not — a second, distinct reliability
failure mode neither RMSLE nor latency alone would catch. **Caveat: read the confound note
above before treating any of these absolute numbers as either model's latency in isolation —
the relative ordering (terra worst, then luna, then mini) is the reliable part.**

**Does the two-phase submit protect us if the smart call is slow?** Only partially. The cheap
blind-floor submit at ~T+3s stands regardless, so a slow or failed terra draw never produces a
`(0, 0)` Line Item — invariant 1 holds. But a timed-out draw does not degrade gracefully to
"a worse but present number": it returns **zero evidence for that draw**, so `blend()` either
falls back to the other draw alone (losing the ensemble's variance-reduction benefit, worth
+28,625 over Games 1–15/17–19 when both draws land) or, if both draws on a Case time out,
Strategy 2 falls back further to Channels A/B and the fitted no-information constants. That is
not a crash, but it is a real, measured degradation, and it lands disproportionately on the
Cases with the most money at stake — the opposite of where we want the failure mode to
concentrate.

## The mini+terra hybrid

Ensemble draw A = mini's anchored prompt, draw B = terra's un-anchored prompt, blended by the
unmodified `blend()` (which already tolerates a 1- or 2-draw ensemble — this is exactly what
happens live today whenever one draw times out).

RMSLE, real-money items (n=152 for every variant, full sample): mini-only 0.562, hybrid
0.575, terra-only 0.619 — the hybrid sits between the two but closer to mini, confirming
terra's draw adds mostly noise rather than signal when blended in. Consistent with the paired
result above.

Euros over all 32 common Games: mini 224,276 / terra 170,616 (Δ −53,660, outside the
±35,496 floor) / **hybrid 257,292 (Δ +33,015, inside the floor but the only positive delta
anywhere in this report)**. Odd/even split: hybrid−mini +22,333 (odd) / +10,682 (even) —
**same sign in both halves**, unlike terra-alone which flips (−81,138 odd / +27,478 even).
That consistency is worth noting rather than dismissing, but it doesn't clear its own floor
in either half (±25,100 each), so it is *suggestive, not established* — the honest read is
"adding a terra draw as the second ensemble member, instead of replacing mini outright, does
not hurt and directionally may help a little, but this sample cannot tell the difference from
mini-alone with two anchored/unanchored draws." **It is not a case for running terra alone**,
which is what `.env` currently does, and which loses on every measure in this report.

## Three-model comparison (unpaired, full sample)

Coverage of the sample differs slightly by model because terra and luna both lose calls to
timeouts that mini does not (363/364/364 rows rather than identical, since a handful of mini
calls also failed) — this table is the full unpaired picture; the paired table above is the
one that actually isolates model quality, and both now agree.

| | mini (gpt-5.4-mini) | terra (gpt-5.6-terra) | luna (gpt-5.6-luna) |
| --- | ---: | ---: | ---: |
| priced Line Item rows | 363 | 364 | 364 |
| latency p50 / p95 (completed calls) | 8.1s / 15.0s | 15.1s / 28.4s | 20.8s / 41.9s |
| timeout / error rate (of 64 calls) | 4.7% | 17.2% | 9.4% |
| RMSLE, real money, post-blend+memory | 0.562 | 0.619 | 0.613 |
| bias, real money | +0.178 | +0.217 | +0.285 |
| RMSLE, model-only (Channel C) | 0.848 | 0.845 | 0.874 |
| coverage recall / false-positive / Brier | 72.4% / 14.2% / 0.137 | 78.2% / 18.8% / 0.149 | 78.2% / 17.1% / 0.143 |

Band calibration (RMSLE by the model's own sigma tercile, real-money rows) is **still
backwards for every model**, not just mini: narrow-band RMSLE runs 0.56–0.88 against
wide-band RMSLE of 0.53–0.74, i.e. the width the model asserts still does not order its own
error, for any of the three (mini narrow 0.555 vs wide 0.736; terra narrow 0.875 vs wide
0.549; luna narrow 0.770 vs wide 0.534 — every model's narrow band is *worse*, not better,
than its wide one). If the fix for `pricing.py`'s known-backwards calibration (module
docstring: narrow tercile 0.847 against wide tercile's 0.733) was hoped to be "use a smarter
model," this measurement says no, more clearly than the partial sample did — the
miscalibration is a property of the prompt and the scoring task, not of which model answers
it, and it is if anything *more* backwards for both alternative models than for mini.

The one real trade-off in this table: **terra and luna both catch more of the truly worthless
items** (recall 78.2% against mini's 72.4%), **at the cost of more false positives** (17–19%
against mini's 14.2%) — flagging genuinely valuable items as worthless, which forfeits
guaranteed income (README R6). Both alternative models' Brier scores are worse than mini's
despite the recall gain. Neither is a clear coverage upgrade once the false-positive cost is
priced in, and this reading is itself unpaired and may be partly composition — though with
comparable row counts now (363–364 across all three), composition is a smaller concern here
than it was in the accuracy numbers before pairing.

## Euro replay and held-out folds

All 32 Games now have a submission from all three models — every draw that timed out on both
ensemble members for a given Case still leaves Channels A/B and the fitted no-information
constants to price it, so `build_proposal` never returns nothing (this document's own
argument for invariant 1, confirmed by the data). Noise floor for n=32 is **±35,496**
(scaled from the stated ±34,369 over 30 Games).

| model | total net, all 32 Games | delta vs mini |
| --- | ---: | ---: |
| mini (shipped) | 224,276.11 | — |
| terra | 170,616.10 | **−53,660.01 (OUTSIDE the ±35,496 floor)** |
| luna | 197,261.98 | −27,014.13 (inside floor) |

Held-out splits (sign consistency check, not a fit — nothing here is tunable per Game):

| split | n | noise floor | terra − mini | luna − mini |
| --- | ---: | ---: | ---: | ---: |
| odd Games | 16 | ±25,100 | −81,138 | −52,507 |
| even Games | 16 | ±25,100 | +27,478 | +25,493 |
| Games 1–20 | 20 | ±28,062 | −43,327 | −26,152 |
| Games 21+ | 12 | ±21,737 | −10,333 | −862 |

**This is the update that matters most from finishing the full sweep.** At n=20 (partial
sample) both alternative models flipped sign on both the odd/even *and* the 1–20/21+ splits
together, which read as pure noise driven by one volatile Game (17). At the full n=32, **the
odd/even split still flips** (still one large swing — Game 17 again: mini +14,592, terra
−10,203, luna −22,139, driven by terra/luna reading two borderline items as meaningfully more
likely covered than mini did, raising their Limits into a costly accept — see
`var/experiments/model_bakeoff/case_17_*.json`), **but the 1–20/21+ split no longer does**:
terra is negative in *both* halves (−43,327 and −10,333) and luna is negative in one and
roughly flat in the other (−26,152 and −862). Pulling Game 17 out of the odd/even split
still flips it back to negative-negative, so the odd/even flip really is that one Game; the
1–20/21+ agreement, by contrast, survives Game 17's removal (Game 17 falls in the 1–20 half,
and that half is already the more negative one). **The full sample therefore supports the
headline more strongly than the partial one did — not less:** terra loses money against mini
on the full 32-Game set outside the noise floor, and the one split that looked like a
counter-argument at partial sample turns out to have been driven by a single Game rather than
a real division of the data.

## Shipping question

**Is `gpt-5.6-terra` (already live since 21:48) worth keeping, or should `.env` revert to
`gpt-5.4-mini`? Revert.**

- **Accuracy: mini wins, not a wash.** The paired, composition-controlled RMSLE test — the
  one number built specifically to answer this — put mini ahead at every checkpoint from
  n=35 to the final n=152, and the gap *widened* as the sample grew (0.518 vs 0.536/0.564 at
  n=35; 0.562 vs 0.619/0.613 at n=152). The sign test alone stays non-significant (terra even
  wins the item-by-item count at full sample), but RMSLE is the metric CLAUDE.md rule 10
  specifies for exactly this reason — it is sensitive to the size of a miss, and terra's
  worse bias and dispersion say its wins are small and its losses are large. **There is no
  accuracy case for the swap, and the full sample argues against one more clearly than the
  partial sample did.**
- **Euros: terra's loss clears the noise floor.** −53,660 over all 32 Games against a
  ±35,496 floor — the only OUTSIDE-the-floor result in this entire measurement, and it is a
  loss. Luna's −27,014 stays inside the floor but the same direction. The odd/even split
  still flips sign (traced to one Game, 17), but the 1–20/21+ split — which looked like a
  counter-argument at partial sample — no longer does: terra is negative in both halves at
  full sample. **No held-out fold supports the swap.**
- **Latency and reliability are the other place the models really differ, and mini wins
  there too.** Terra's overall timeout rate (17.2% of 64 real Case calls) is 3.7× mini's
  (4.7%), worst exactly on the 11–20 and 21+-item Cases that carry the most money. A
  timed-out draw is not a slower number, it is **zero evidence for that draw** — a real
  degradation of the posterior on the Cases where being wrong costs the most, and this
  measurement's own confound section says even that gap is probably an *understatement* of
  terra's isolated latency, not an overstatement, since mini shared the same contention and
  still came out fastest.
- **The euro estimate, stated with its uncertainty:** best point estimate for keeping terra
  over reverting to mini is **−53,660 ± 35,496 over the 32-Game sample (roughly −1,677 ±
  1,109 per Game)**, and unlike every other number in this report, this one clears its noise
  floor — it is a measured loss, not noise pretending to be a signal. That is on top of a
  latency-driven downside risk this measurement cannot fully price (a Case whose both draws
  time out gets Channel A/B + fitted constants instead of a model read at all; how often that
  compounds over a full 100-Game tournament, rather than the 32 settled so far, was not
  directly observed here, and the confound section means today's timeout rate may itself be
  inflated by contention that will not persist once the sweep is not sharing the deployment).
- **What makes this more than "no strong opinion either way":** the euro delta alone would
  already be enough — it is the one number in this report that is not noise. README rule 8
  reinforces it rather than being needed to carry it: *uptime outranks accuracy* — break-even
  uptime is 71%, and "showing up is 2.5× being right." A model change that loses money on
  accuracy *and* demonstrably increases the rate of a specific, measured failure mode (an
  ensemble draw returning nothing) is a net downgrade on every axis this repo has measured,
  not a coin flip resolved by a secondary consideration. The dark regime starts at Game 44,
  roughly two hours out at the time of writing, and README rule 9 says a field measurement —
  or, by the same logic, a latency risk profile — does not automatically carry across that
  boundary; better to enter it on the model with the better-understood, better-measured
  failure mode.

**Recommendation: set `AZURE_OPENAI_MODEL=gpt-5.4-mini` and restart the runner now.** It is a
one-line `.env` edit with no code change, reversible in the same thirty seconds it took to
apply, and every number in this measurement points the same direction: worse accuracy, a
euro loss that clears the noise floor, and materially worse latency — the swap should not
have shipped on the evidence this measurement produced, and the full sample only sharpened
that, it did not soften it.

## What would change this answer

- More Games (32 is not 100; the dark-regime Games 44–81 have a different Field and this
  measurement does not cross that boundary per README R9).
- A clean latency re-measurement off an unloaded endpoint (see the confound note above) — if
  terra's timeouts turn out to be mostly self-inflicted contention rather than the model
  itself, the latency case against it weakens; the accuracy case is unaffected either way,
  since RMSLE doesn't depend on how long the call took to return.
- A latency fix that isn't available here (higher concurrency, a shorter prompt, a smaller
  service tier) — this measurement used the shipped prompt and the shipped two-phase submit
  design unchanged.
- Re-running this after the tournament, off the clock, with a larger sample and no rate-limit
  constraint, to get the RMSLE confidence intervals tight enough to separate three models
  whose real-money RMSLE differs by less than their own sampling noise.
