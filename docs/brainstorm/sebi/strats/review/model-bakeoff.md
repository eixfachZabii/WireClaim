# Model bake-off: does the frontier model beat the mini we're running?

`.env` currently sets `AZURE_OPENAI_MODEL=gpt-5.4-mini`. `src/api/llm.py`'s own
`DEFAULT_MODEL` is `gpt-5.6-terra`, and probing the endpoint
(`https://claim-to-fame-ai.openai.azure.com/openai/v1/`) turns up exactly three deployments
that actually answer out of 412 listed: `gpt-5.4-mini` (what we run), `gpt-5.6-terra` and
`gpt-5.6-luna`. Nobody had ever measured whether the bigger model reads a Case better. This
is that measurement.

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

## Headline

**[being finalized as the sweep completes — see the paired comparison below for the number
that actually decides this, and CHANGELOG below for how the mid-run findings changed the live
`.env`]**

An unpaired read on a partial sample (~70 of 192 draws) had terra's real-money RMSLE slightly
better than mini's post-blend (0.544 vs 0.565) and luna slightly worse (0.688, higher bias).
**That comparison was confounded — different Games had completed for each model, so the
difference could be entirely composition, not model quality.** The paired re-run below,
restricted to the identical Line Items all three models actually returned evidence for,
settles it: there is no detectable accuracy difference between any of the three models.
Model-only RMSLE for all three lands close to the shipped estimator's known ~0.77–0.80
(`scripts/leak_sigma.py`), which is the cross-check that the harness itself isn't broken.

## Paired comparison — the number that actually decides this

`scripts/experiments/model_bakeoff_paired.py` restricts to Line Items where **all three
models** returned usable evidence (real-money population: `t_lo > 0`, bounded), so the
comparison is composition-free.

| model | n (paired) | RMSLE | bias |
| --- | ---: | ---: | ---: |
| mini (shipped) | 35 | 0.518 | +0.172 |
| terra | 35 | 0.536 | +0.162 |
| luna | 35 | 0.564 | +0.205 |

Sign test on `|log error|` per Line Item (smaller wins): mini beats terra 19/35, terra beats
mini 16/35 — **p = 0.736**, a coin flip. mini beats luna 16/34, luna beats mini 18/34 — **p =
0.864**, also a coin flip. *(n=35 as of the first full paired pass; re-run after the sweep
completes to firm this up further — the direction has not moved as N grew from the interim
read.)*

**Reading:** neither `gpt-5.6-terra` nor `gpt-5.6-luna` reads a Case more accurately than the
shipped `gpt-5.4-mini`, once the comparison controls for which items each model actually
priced. An earlier informal read (three items on Case 30, terra visibly closer to `t`) did not
survive n=35 — the lesson CLAUDE.md already states about one Game being inside the noise
floor applies at the item level here too: three items is noise, not a signal.

## Latency by Line Item count, against the 50s budget

`LLM_TIMEOUT_SECONDS` was raised 40 → 50 mid-measurement. Bucketed by real Case size (`n`
is call attempts, both ensemble prompts, thin at the extremes — refresh after the full sweep):

| bucket | mini timeout / p95 | terra timeout / p95 | luna timeout / p95 |
| --- | --- | --- | --- |
| 1–5 items | 0% / 8.0s (n=12) | 17% / 10.9s (n=6) | 0% / 16.6s (n=5) |
| 6–10 items | 0% / 5.9s (n=8) | 17% / 15.0s (n=6) | 11% / 23.4s (n=9) |
| 11–20 items | 12% / 26.6s (n=16) | 33% / 25.3s (n=6) | 25% / 27.1s (n=4) |
| 21+ items | 0% / 15.0s (n=5) | 33% / 47.1s (n=3) | 0% / 42.7s (n=4) |

Terra's timeout rate runs 2–3× mini's in every bucket, and on the 21+-item Cases — the ones
carrying the most money (Game 17: 20 items, 145,163 of oracle Issuer income) — terra's **p50
is 47.1s**, i.e. more than half its calls on the largest Cases would still miss even the
raised 50s budget. That cell is n=3 and will firm up as the sweep reaches the remaining large
Cases (8, 11, 15, 17, 31 all run 18–39 items), but every bucket points the same direction.

## The mini+terra hybrid

Ensemble draw A = mini's anchored prompt, draw B = terra's un-anchored prompt, blended by the
unmodified `blend()` (which already tolerates a 1- or 2-draw ensemble — this is exactly what
happens live today when one draw times out).

RMSLE, real-money items, whatever Games each variant had evidence for: mini-only 0.562
(n=140), hybrid 0.568 (n=140) — no gain, consistent with the paired result above.

Euros over 11 common Games: mini 117,420 / terra 129,733 / hybrid 99,355. Delta terra−mini
**+12,313**, delta hybrid−mini **−18,065**, both inside the ±20,811 noise floor for n=11.
Odd/even split holds sign but not magnitude: terra−mini +2,414 / +9,900; hybrid−mini −2,399 /
−15,666. **The hybrid is not rescuing anything** — mixing in terra's draw doesn't add real
information (per the paired test) and forfeits half of mini's own two-draw ensemble benefit
whenever terra's draw times out, which is often (see latency table above).

## Three-model comparison (unpaired, full sample)

*(filled in after the full sweep — see `var/experiments/model_bakeoff/score_summary.json`
for the machine-readable version and re-run
`PYTHONPATH=. pixi run python scripts/experiments/model_bakeoff_score.py --games 1-32` for the
full printout)*

## Euro replay and held-out folds

## Shipping question

**Is `AZURE_OPENAI_MODEL=gpt-5.6-terra` worth shipping tonight?**

## What would change this answer

- More Games (32 is not 100; the dark-regime Games 44–81 have a different Field and this
  measurement does not cross that boundary per README R9).
- A latency fix that isn't available here (higher concurrency, a shorter prompt, a smaller
  service tier) — this measurement used the shipped prompt and the shipped two-phase submit
  design unchanged.
- Re-running this after the tournament, off the clock, with a larger sample and no rate-limit
  constraint, to get the RMSLE confidence intervals tight enough to separate three models
  whose real-money RMSLE differs by less than their own sampling noise.
