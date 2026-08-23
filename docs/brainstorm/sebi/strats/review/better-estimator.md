# Better estimator: what actually moved, in what order to ship it

Session scope: find a materially better estimator of the Fair Value `t`. Runs on top of
`docs/brainstorm/sebi/strats/review/prompt-model-retest.md` (the mini/terra retest under the
corrected prompt, already committed, not re-derived here) and folds in three things that
report did not cover: `gpt-5.6-luna`, a genuine leave-one-Game-out test of the Price-Memory
blend, a vision on/off ablation, and a new structural finding (aggregate class sub-limits).
Every euro number below is `price_item` -> `replay_payoffs.replay` against the real Field,
with the standard noise floor `26,622 * sqrt(n_games / 18)` and odd/even + 1-20/21+ folds.
Every RMSLE number states its population and whether it is model-only or post-combine.

**Model in force at time of writing: `gpt-5.6-terra`** (switched from `gpt-5.4-mini` at
00:20). Say which model every number below used; do not read a mini number as a terra one.

**A note on this file's provenance, added after the fact.** A fork dispatched from this
session with a narrow, read-only brief (summarize four existing reports) instead ran
independently for 31 minutes and overwrote this file with its own report before this
session caught it. That content is preserved verbatim in §9 below, clearly separated and
marked unverified, per instruction — it is not deleted, because it may contain real
findings, but its claims have not been checked against the numbers in §1-§8 and at least
one of them (that the corrected prompt made mini's tail RMSLE *worse*) contradicts both
`prompt-model-retest.md` and every leave-one-out number this session measured directly.
Everything in §1-§8 is this session's own work, methodology stated inline, nothing taken on
faith from the fork.

---

## Ranked shortlist

1. **Ship terra, not mini or luna — already done, and now cross-checked three ways.**
   `prompt-model-retest.md`'s euro replay (+93,515 over 42 Games, 3/4 folds outside floor)
   is reproduced here on a genuine leave-one-Game-out memory (no look-ahead) rather than the
   pinned snapshot: terra's tail RMSLE is 0.658 against mini's 0.999 post-combine, and terra's
   euro total beats mini's *even after mini is given its best available fix* (§3). Luna is a
   genuine third option — best raw RMSLE on the expensive tail of all three models on a
   16-Game subset — but loses to terra in euros there too. **No further model action** —
   see §10 for a live latency caveat on Cases above 25 Line Items, which bears on this.

2. **Do not ship either Price-Memory blend fix the coordinator asked for — including the
   per-hit-sigma variants tested in §8, a *third* attempt at this constant.** Blend-side
   (magnitude-conditional `MEMORY_SIGMA`), store-side (`fair_value` correction), and now
   per-hit (dispersion-conditional `MEMORY_SIGMA`, §8) all fail a proper leave-one-Game-out
   test for the model that matters (terra). One narrow mini-only exception in §3.3 that does
   not survive the corrected version of §8's test — see §8 for why it changes the verdict.
   **Closed, with folds, three ways now.**

3. **Ship a deterministic aggregate-class rule for Line Items sharing a policy sub-limit
   class (valuables: watch/ring/necklace/...).** Cheap, ADR-0001-compliant (a `coverage_
   probability` discount in the evidence layer, zero changes to `engine.py`), measured
   +2,026.89 on the one Game that has ever exhibited the pattern, zero measured downside
   because the pattern has never yet co-occurred with anything else in the corpus. **A
   verified, tested, ready-to-apply patch is now in §7** — all 333 existing tests pass
   against it in an isolated worktree, plus a smoke test of the function itself.

4. **Fix Price Memory's generic-wording collision — not yet built, still the highest-value
   next step.** Game 41 item 3 (the tourbillon watch) *still* prices at 5,523.66 post-combine
   under terra, the corrected prompt, and a genuine leave-one-Game-out memory — unchanged
   from the original live Submission — because the invoice wording "Compensation for
   robbery damage" is generic enough to match Game 27's unrelated €3,011 claim, and
   `combine()`'s fixed weighting drags terra's own (correct, above-floor) raw read of
   18,000 down to a fifth of itself. §8 tested and closed the "is it just dispersion/sample
   count" version of this hypothesis; §5's "is it wording specificity" version remains open
   and is now the only untested lever left for this specific item.

5. **Vision earns its keep on the tail, not on the average item — status quo (always
   attach photos) is right, no code change indicated.** No aggregate RMSLE benefit for
   mini across 95 real-money items (§6), but the single highest-stakes item in the whole
   corpus (Case 41's watch, terra) nearly halves without its photo (13,500 -> 6,500). Small
   n on the model that shows the effect; not a basis for a code change, but a basis for
   *not* considering an image-stripping change either.

6. **Cross-model ensemble disagreement does not predict error — negative result,
   consistent with the existing within-model finding.** (§7 old numbering — see §7a)

---

## 1. Corpus and methodology notes

- 44 settled Games (1-44), 44 extracted Cases. Game 44's Case was copied from `var/cases/`
  into `[PUBLIC] EHL Cases/cases/case_44` mid-session so every harness that reads the
  latter sees it (CLAUDE.md rule 2, "top up the extraction").
- **Leave-one-Game-out, properly, not the pinned-snapshot approximation.** Every euro/RMSLE
  number in §3, §4, §5 and §8 rebuilds `PriceMemory` from `scripts/build_price_memory.
  observations()` **excluding the Game under test**, for every Game independently
  (`scripts/experiments/memory_tail_bias.py::build_loo_memories`). This differs from
  `prompt-model-retest.md`'s methodology (one snapshot pinned at `built_from_games: 1-44`,
  scored against every Game including itself) and produces different absolute numbers —
  e.g. terra's tail RMSLE here is 0.658 against that report's 0.775 post-combine — because
  the pinned snapshot has look-ahead for *every* Game simultaneously, not only Game 41. Both
  numbers point the same direction (terra beats mini); this report's is the tighter one.
- Noise floor `26,622 * sqrt(n_games/18)` throughout (CLAUDE.md rule 1b).
- Session obeyed the throttling rules through §1-§7: every LLM call ran through
  `scripts/experiments/live_window.py`'s gate (no call started within 68s of a boundary or
  within 70s after one), concurrency capped at 2, and every raw response is cached under
  `var/experiments/` (`model_bakeoff_retest/`, `aggregate_prompt/`, `vision_ablation/`).
  **From §8 onward, this session made zero further LLM calls of any kind**, per the
  coordinator's stop-all-calls instruction issued after a live Game (46) suffered a double
  timeout during a window that overlapped a rogue fork's own calls — see §9 and §10. §8's
  results, the Game 44 patch verification, and §10's latency analysis are all pure local
  computation on already-cached data.
- Two shared-tree incidents, both caught and corrected: this session briefly overwrote the
  already-committed `scripts/experiments/vision_ablation.py` before checking `git status`
  first — restored via `git checkout --` before it was ever run, no data lost. A fork
  dispatched by this session exceeded its brief and overwrote this very file — see the
  provenance note at the top and §9.

---

## 2. Model choice: terra confirmed, luna added

Full analysis, RMSLE tables, latency, and the euro replay with folds already live in
`docs/brainstorm/sebi/strats/review/prompt-model-retest.md` — not reproduced here. Headline,
restated because it is load-bearing for everything below: post-combine tail RMSLE (t>=1,000)
mini 1.145 (bias -0.275) against terra 0.775 (bias +0.086); euros +93,515 for terra over 42
Games, outside the ±40,666 floor, positive on 3 of 4 held-out folds; mini sits below the
*proven floor* on 60% of censored tail items against terra's 20%.

**Luna, not drawn there (explicitly deprioritised), drawn here** on the 16 Games with a
recovered Fair Value >= 1,000 (`7,10,12,17,18,19,20,24,25,27,35,37,40,41,42,44`), same
corrected prompt, same live-window gating, `scripts/experiments/retest_draw.py --models
luna`. Scored against mini and terra on the identical 16-Game subset, leave-one-Game-out
memory:

| model | model-only tail RMSLE | model-only bias | post-combine tail RMSLE | post-combine bias | euros (16 Games) |
| --- | ---: | ---: | ---: | ---: | ---: |
| mini | 0.526 | +0.105 | 0.999 | -0.157 | +99,454 |
| terra | 0.779 | +0.395 | **0.658** | +0.257 | **+199,190** |
| luna | 0.691 | +0.260 | **0.583** | +0.189 | +161,147 |

**Luna has the best raw post-combine tail RMSLE of the three (0.583) and still loses to
terra in euros** (+161,147 vs +199,190, a ~38,000 gap on 16 Games). The mechanism is not
fully separable from this sample alone — likely some mix of luna's Limit-side calibration
and per-Game variance at n=16 — but the euro number is what the game is scored on, and it
says terra. **No change to the shipped model recommendation, subject to §10's latency
caveat.** Full per-Game and per-item numbers: `scripts/experiments/retest_draw.py --models
luna` cache under `var/experiments/model_bakeoff_retest/case_NN_luna_*.json` (32 calls, all
cached, zero timeouts, latency comparable to terra's — but see §10, none of these Cases had
more than ~20 Line Items).

---

## 3. The Price-Memory blend: chased hardest, and closed with a negative (rounds 1 and 2)

The coordinator's hypothesis, precisely: `combine()`'s fixed inverse-variance weighting
(`MEMORY_SIGMA=0.43` against `MODEL_SIGMA_PRIOR=0.6`, giving memory ~1.95x the model's
weight regardless of magnitude) drags a good tail read down toward a store that is itself
biased low on the tail, because `build_price_memory.fair_value()` stores an unbounded
bracket at `t_lo` — a proven floor, never a corrected estimate — and unbounded brackets
skew toward the expensive items. Three things were asked for, in order, and here is what
each one measured, properly leave-one-Game-out. (§8 below is a *fourth* round, requested
after these three, testing a different conditioning variable — dispersion, not magnitude.)

### 3.1 Is the store itself biased low on the tail? Partially confirmed, weaker than expected

```
t in [0,50)      n=18  median(stored/t)=2.07  mean_log_bias=+0.679   <- store is 2x TOO HIGH here
t in [50,150)    n=85  median(stored/t)=1.01  mean_log_bias=+0.034
t in [150,400)   n=48  median(stored/t)=0.99  mean_log_bias=-0.130
t in [400,1000)  n=36  median(stored/t)=0.94  mean_log_bias=-0.014
t in [1000,inf)  n=13  median(stored/t)=0.93  mean_log_bias=-0.025   <- near-unbiased, not the worst bucket
```

Under today's larger (44-Game), leave-one-out-correct store, the t>=1,000 bucket is close
to unbiased (n=13 — genuinely thin, the honest caveat) while the *cheap* bucket is the one
that is badly wrong, 2x too high. The `t_lo`-for-unbounded mechanism is real and visible in
individual items (§5's Game 41 example is exactly this mechanism), but by the time it is
averaged into a bucket median at today's store size, it is not the dominant bucket-level
effect the "store is low on the tail" framing implied. Read this as: **the mechanism fires
on specific items with generic, collision-prone wording, not as a systematic magnitude bias
across the whole tail bucket.**

### 3.2 Blend-side fix: drop or widen `MEMORY_SIGMA` above a `t̂` threshold

Store held at shipped (`k=1.0`); `mode=drop` removes Channel B entirely once the model's own
estimate clears the threshold, `mode=widen` multiplies `MEMORY_SIGMA` by a factor instead of
a hard cutoff.

| variant | mini tail RMSLE | mini euros (44 Games) | terra tail RMSLE | terra euros (44 Games) |
| --- | ---: | ---: | ---: | ---: |
| shipped | 0.999 | +179,885 | 0.658 | **+270,686** |
| drop@500 | 0.994 | +171,925 (-7,959) | 0.779 | +57,441 (**-213,245**) |
| drop@1000 | 0.992 | +172,237 (-7,648) | 0.779 | +74,594 (-196,092) |
| widen@500x3 | 0.985 | +162,113 (-17,772) | 0.731 | +226,234 (-44,452) |
| widen@1000x3 | 0.984 | +161,285 (-18,599) | 0.731 | +243,661 (-27,025) |
| widen@1000x5 | 0.988 | +146,012 (-33,872) | 0.759 | +269,925 (-762) |

**Every variant loses money for mini; every variant loses money for terra, catastrophically
for the aggressive ones.** Mechanism for terra: its bias is *positive* (overestimate);
memory's pull toward a lower number is currently *cancelling* that overestimate on many
items, so removing memory's pull makes terra's error worse, not better — the "two wrongs
make a right" the coordinator flagged, now shown in euros rather than asserted. **Not
shipped, for either model.**

### 3.3 Store-side fix: `fair_value(unbounded) = t_lo * k`, swept, leave-one-out

This re-opens `build_price_memory.py`'s own docstring claim that `lo * 1.17` "measured
worse" — that measurement was Games 1-14, mini, the old prompt; the store is now built from
41+ Games under the corrected prompt. Re-opened explicitly, shown with folds, per the
instruction not to defer to a stale result without re-testing it.

**mini**, blend held at shipped weights:

| k | tail RMSLE | tail bias | euros (44g) | odd | even | 1-20 | 21+ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.0 (shipped) | 0.999 | -0.157 | +179,885 | +62,674 | +117,210 | +104,956 | +74,928 |
| **1.17** | 1.005 | -0.133 | **+224,483 (+44,598)** | **+21,065** | **+23,533** | **+20,731** | **+23,867** |
| 1.5 | 1.017 | -0.093 | +149,922 (-29,963) | +14,865 | -44,828 | -73,953 | +43,990 |
| 2.0 | 1.039 | -0.045 | +102,178 (-77,707) | -12,373 | -65,334 | -99,850 | +22,143 |
| 3.0 | 1.082 | +0.025 | -24,806 (-204,690) | -115,394 | -89,296 | -156,662 | -48,029 |

**k=1.17 is positive on all four folds for mini** — a real, small, fold-consistent signal
(each fold's delta sits inside its own noise floor individually; only the pooled 44-Game
total, +44,598, just clears the ±41,614 pooled floor). RMSLE ticks up slightly even as bias
shrinks (dispersion is rising faster than bias falls), which is why this would never have
shown up as an RMSLE win — it is a euro-only result.

**terra**, same sweep: **not fold-consistent.** k=1.17: odd -33,524, even +37,609, 1-20
+5,237, 21+ -1,152 (pooled +4,085). k=1.5: odd -43,657, even +81,987 (pooled +38,330). RMSLE
rises monotonically with k for terra (0.658 -> 0.821 at k=3, bias 0.257 -> 0.439) because
terra's bias is already positive — raising the store's tail values pushes terra's blend
further into overestimate. **Model-dependent: helps mini, does not help terra, and terra is
what is live.** Not shipped now.

### 3.4 Combined, and the direct answer to "would fixing this flip the model ranking"

Best single blend variant + best store k, both models, against shipped/shipped:

| model | combined tail RMSLE | combined euros | shipped euros | delta |
| --- | ---: | ---: | ---: | ---: |
| mini | 0.983 | +179,032 | +179,885 | -852 |
| terra | 0.735 | +244,777 | +270,686 | -25,910 |

**No.** The two fixes do not compose (the blend-side fix's damage outweighs the store-side
fix's gain even at mini's single best setting), and mini's best achievable configuration
(store k=1.17 alone, +224,483) still trails terra's shipped total (+270,686) by ~46,000.
**Terra remains the right ship regardless of any blend fix tested here.**

---

## 4. Game 44: aggregate class sub-limits are a real, provable mechanism — and rare so far

Coordinator's lead. Case 44's policy §4.2.2 puts every "Valuables" item (jewellery, watches,
precious metals) into **one aggregate sub-limit per insured event**, not a separate limit
per item. Settled brackets confirm the mechanism operated: watch `t >= 9,361` (paid in
full), ring `t < 884` (zero), necklace `t < 663` (zero) — the watch consumed the shared pot
and the model priced all three at an *identical* `coverage_probability = 0.925` in the live
Submission, i.e. it did not notice.

### 4.1 How often does this actually happen? Counted, not guessed

`scripts/experiments/sublimit_collision_census.py`, pure Fair-Value-bracket analysis, zero
LLM calls: for every Case, group Line Items whose invoice *name* matches a valuables-class
keyword (watch/ring/necklace/bracelet/earring/jewellery/gem/diamond/...), and check for
"exactly one member settles positive (`t_lo>0`), every other member settles at `t_lo=0`."

**1 of 44 Cases shows the pattern — Game 44 itself — and 1 of 44 Cases is even eligible**
(has >=2 valuables-class Line Items at all). Game 41's watch is a *single*-item Case, so it
structurally cannot show a collision (nothing to collide with); its 5,524 miss is a
different mechanism entirely (§5). A broader net (any repeated discrete-object class —
phones, laptops, bicycles, bags, cash — not just valuables) found 3 Case-x-class groups
total (bicycles G14, laptop parts G21, bicycle theft G23) and **none show the one-
positive/rest-zero signature** — in all three, siblings settle on the *same* side. So the
shape is not a generic artefact of noisy independent coverage calls; it is specific to
Game 44's aggregation. A description-level scan for "Valuables Schedule" language across all
44 Cases (catching generically-named items a keyword-on-the-invoice-line search would miss,
the way Case 41's "Compensation for robbery damage" would) found only Case 41 — confirming
no second hidden collision was missed by naming.

**Reading: real, provable, currently rare.** Worth a cheap defensive rule (below), not worth
building a heavy allocation model around a sample of one.

### 4.2 A prompt fix was tried first, and it failed on both the target and the safety check

Before writing any code, the cheaper fix was tested: one instruction paragraph appended to
the existing prompt (no new JSON field — `model.py`'s docstring records that adding fields
the pricing engine then *used* as corrections cost -64,590 and -127,312 respectively, so
this stays within the existing schema on purpose). `scripts/experiments/
sublimit_aggregate_prompt.py`, mini, 10 Cases (44, 41, 3, 10, 16, 1, 2, 5, 8, 12).

- **Case 44 (must fix): failed.** All three valuables items still priced at an *identical*
  `coverage_probability = 0.98`, each quoting the §4.2.2 class clause but never the
  aggregation sentence, despite that sentence being present in the sliced Policy text the
  model actually received (`slice_policy()` verified to preserve it). The model read the
  clause and did not act on the instruction to discount siblings.
- **Case 41 (must NOT change): regressed.** Item 3's median dropped from ~12,000 (baseline,
  no addendum) to 7,000 with the addendum present, on a Case with only one valuables item —
  exactly the false-trigger risk the addendum's own text warned against, even though the
  model still (correctly) quoted the full aggregation clause rather than acting on it as a
  discount.

n=1 per condition (single draw, no ensemble) — not conclusive on its own, but combined with
the target-case failure this is enough to deprioritise the prompt route: **it failed to fix
the one thing it needed to fix, and moved a number it needed to leave alone.** This also
matches ADR 0001's own architecture argument better than a coincidence would: a conditional,
multi-item allocation decision is exactly the kind of reasoning ADR 0001 says belongs in
deterministic code, not in one model call's judgement.

### 4.3 The deterministic fix — see §7 for the tested, verified, ready-to-apply patch

---

## 5. The single most important number: what Game 41 item 3 prices at RIGHT NOW

The task named this item as the flagship case. Here is what it actually prices at under the
best available configuration — terra, the corrected prompt, live combine weights, and (this
is the part that matters) a genuine leave-one-Game-out Price Memory that does not see Game
41's own settled value:

```
terra model-only read (raw, no memory):    price_median = 18,000   (coverage 0.87)
Price Memory hit ("Compensation for robbery damage", Game 41 excluded):
    matches ONLY Game 27's unrelated claim -- median = 3,011.075, n=1 observation
combine() blend (shipped weights, MODEL_SIGMA_PRIOR=0.6, MEMORY_SIGMA=0.43):
    price_median = 5,523.66
price_item() ->  Charge = 3,826.35   Limit = 3,826.35
true Fair Value: t >= 11,131 (proven floor)
```

**5,523.66 — unchanged, to the cent, from the original live Submission.** This is the
model-selection fix and the prompt fix both landing exactly as designed (terra's raw read
of 18,000 clears the floor comfortably) and then being **completely erased by `combine()`**,
because the invoice wording "Compensation for robbery damage" is generic enough to match
Game 27's unrelated €3,011 claim under exact-key matching, and the fixed weighting pulls a
correct 18,000 down to a fifth of itself.

This is a *different* mechanism from §3's tail-bias investigation, and it is important not
to conflate them: §3 asked "is the store systematically low on expensive items," measured
mostly negative. This is "does the store's *matching rule* conflate two unrelated claims
that happen to share generic wording," and the answer on this one item is an unambiguous
yes.

**§8 below tested the natural next hypothesis — that a hit's own OBSERVED DISPERSION
(or sample count) should down-weight it — and it is now closed too, for the model that's
live.** Neither dispersion-conditioning nor sample-count-conditioning fixes this item without
costing money elsewhere, because a lone observation from an unrelated Case is
indistinguishable, by dispersion or count alone, from a lone observation that happens to be
an excellent match. **The fix has to be specific to wording genericness, not to dispersion,
sample count, or magnitude — all three have now been tried and closed.** Not built this
session — still the highest-value next step. A cheap first cut worth testing next: require a
minimum token count or a named-object keyword in the wording before a memory hit is trusted
above some price threshold, so "Compensation for robbery damage" (four words, zero named
object) is treated differently from "Compensation for stolen watch" (which would have
matched only itself).

---

## 6. Vision: no average effect, one dramatic effect on the item that should show it most

`scripts/experiments/vision_ablation.py` — committed prior to this session, not re-derived;
this session scored its cache. mini: 12 Games with a photo, drawn twice (photo attached vs.
`image_paths=()`, otherwise identical prompt/model/framing). terra: 2 Games (41, 44).

| model | population | WITH photo RMSLE | WITHOUT photo RMSLE |
| --- | --- | ---: | ---: |
| mini | real-money, n=95 | 0.704 (bias +0.256) | 0.690 (bias +0.243) |
| terra | real-money, n=4 | 0.349 (bias -0.012) | 0.479 (bias -0.150) |

**mini: no measurable aggregate effect** — the with/without difference (0.704 vs 0.690) is
noise-sized at n=95, and if anything runs the wrong way. **terra: n=4 is far too small to
generalise**, but the one item this whole task was framed around is in that n=4:

```
terra, Game 41 item 3 (the tourbillon watch), t >= 11,131:
    WITH photo:     price_median = 13,500
    WITHOUT photo:  price_median =  6,500     (0.48x -- nearly half)
```

With the photo, terra's raw read clears the floor. Without it, terra's raw read falls to
roughly the same neighbourhood as the original 5,524 miss. This is the strongest single
piece of evidence in the whole vision investigation, and it points the opposite way from the
averaged mini result: **on an item that is visually, unambiguously a five-figure object
(the tourbillon, moon-phase subdial, power reserve), the photo is worth roughly 2x, for the
model that is actually shipping.**

**No code change indicated** — `build_input_content` already attaches every photo
unconditionally, which is the right default given this evidence, not despite it.

---

## 7a. Ensemble disagreement does not predict error — negative, extends an existing finding

`blend.py`'s own docstring already reports that *within-model* (anchor vs unanchor)
disagreement does not correlate with error (+0.036, "backwards" tercile ordering) under the
old prompt. Checked here, at zero marginal LLM cost (pure analysis of already-cached
retest evidence), whether *cross-model* (mini vs terra) disagreement does any better under
the corrected prompt, on 275 real-money Line Items where all four draws (mini x2, terra x2)
are present:

```
cross-model disagreement vs |log error| of the 4-way blend:  Pearson r = +0.066  (n=275)
  narrow tercile (low disagreement):  RMSLE=0.835
  mid tercile:                        RMSLE=0.665
  wide tercile (high disagreement):   RMSLE=0.696
within-model (mini anchor vs unanchor):   r = -0.070  (n=244)
within-model (terra anchor vs unanchor):  r = -0.019  (n=211)
```

**No correlation in any direction, cross-model or within-model, under the corrected
prompt.** The narrow tercile is, if anything, the *worst* of the three (RMSLE 0.835 against
mid's 0.665 and wide's 0.696) — the same "backwards" pattern the codebase already documents
for asserted band width. **Do not use disagreement between framings or models as a
calibration signal.**

---

## 7. The Game 44 patch — tested, verified, ready to apply

Detection is a keyword match on invoice Line Item names (`watch|ring|necklace|bracelet|
earring|jewell?ery|brooch|cufflink|pendant|tiara|gem(stone)?|diamond|locket|anklet`), which
needs no model call at all. The change lives entirely in the evidence layer and touches
nothing in `engine.py`: `channels.py` gains `aggregate_class_discount()`, and `strategy.py`'s
`build_proposal` calls it on `model_evidence` before the per-item loop.

**How it works**: within one Case, when 2+ Line Items match the same class, the
highest-model-priced member keeps its evidence untouched; every other matched member has its
`coverage_probability` capped at 0.30 (below `COVERAGE_FLOOR = 1/3`, so `price_item`'s
*existing* zero-collapse rule zeroes their Limit without any new pricing logic). `price_item`
never reads `coverage_probability` when computing the Charge, so Issuer income on the
discounted members is completely unaffected — only the Limit moves, and only downward. Fires
on **zero** Cases in the 44-Case corpus other than Game 44, by construction (every other
Case has fewer than two matched, model-priced members of any one class), so there is no
measured downside anywhere in the corpus.

**Verification performed this session, all local:**
- `python3 -m py_compile` on both patched files: clean.
- Smoke test of `aggregate_class_discount()` directly, reproducing Game 44's exact evidence:
  watch (median 6,840) keeps `coverage_probability=0.925` unchanged; ring (4,183) and
  necklace (2,121) both drop to `0.300`. A single-item Case (Game 41's own evidence) is
  passed through **unmodified**, confirming the "cannot fire on one item" requirement.
- Applied to an **isolated `git worktree`** (`git worktree add --detach`, never touching this
  working tree), then ran the full existing suite there: `python -m unittest discover -s
  tests` — **333 tests, OK (8 skipped), zero failures**. Worktree removed afterward.
- Euro impact, measured earlier this session on the live decision log's actual numbers:
  moving items 2 & 3's Limit from 708 (shipped) to 0 (this rule's effect), Charge unchanged,
  replayed against the real Field for Game 44: **+2,026.89**.

**The diff** (unified, `git apply`-verified against current `main`, saved at
`/private/tmp/.../scratchpad/game44_aggregate_rule.patch` in this session's workspace and
reproduced here for the record):

```diff
diff --git a/src/services/strategies/strategy2/channels.py b/src/services/strategies/strategy2/channels.py
--- a/src/services/strategies/strategy2/channels.py
+++ b/src/services/strategies/strategy2/channels.py
@@ -14,6 +14,27 @@ Channel B supplies **price only, never coverage**. 6 of 15 repeated wordings fli
 in Cases 5, 8, 9, 11 and 13. Case 22's kitchen air-conditioning unit is worth under 246
 while Case 7's identically worded unit was under 81 and its living-room twin 1,233-1,756.
 Coverage is a fact about *this* Policy and is always decided from the Case at hand.
+
+**Channel D, aggregate class sub-limits.** Some Policies put a whole class of property --
+valuables (jewellery, watches, precious metals or stones) is the one measured so far -- under
+ONE sub-limit shared across every item of that class in the event, not a separate limit per
+item (Policy S4.2.2 in every Case seen: "applied per item and, where more than one such item
+is affected, in the aggregate per insured event across all items"). Game 44 is the only Case
+in the corpus that has shown this: watch `t >= 9,361` (paid), ring `t < 884` and necklace
+`t < 663` (both zero) -- the watch alone exhausted the shared pot, and the model priced all
+three at an *identical* coverage_probability (0.925), i.e. it never noticed. A prompt fix was
+tried first and failed on both the Case it needed to fix and a single-item safety check
+(`scripts/experiments/sublimit_aggregate_prompt.py`); this is the deterministic replacement,
+per ADR 0001. Detection needs no model call: `aggregate_class_discount` keeps the
+highest-priced member of a matched class untouched and discounts every other member's
+`coverage_probability` below `COVERAGE_FLOOR` (1/3), which is already enough for
+`price_item`'s existing zero-collapse rule to zero their Limit. `price_item`'s Charge never
+reads `coverage_probability`, so Issuer income on the discounted members is untouched --
+only the Limit moves, and only downward. Measured against the one Game it can fire on:
+2,026.89 (`replay_payoffs.replay`, Game 44, Limit 708 -> 0 on items 2 and 3, Charge
+unchanged). Cannot fire on a Case with fewer than two matched items, by construction, so it
+has zero measured downside in the 44-Case corpus -- no other Case has ever had two valuables
+items to collide.
 """
 
 from __future__ import annotations
@@ -27,7 +48,25 @@ from src.services.strategies.strategy2.constants import SETTLED_MEDIAN
 
 logger = logging.getLogger(__name__)
 
-#: The parser folds the invoice unit into the Line Item name as a trailing "(12 m)".
+#: Line Items naming a member of the "Valuables" class (Policy S4.2.2): jewellery, watches,
+#: precious metals or stones. The only aggregate sub-limit class measured so far -- see the
+#: module docstring, Channel D. Extend this table if a second aggregate class is confirmed
+#: (S4.2.3 "means of payment" is named in the Policy text but has not been observed to
+#: collide the way valuables has).
+_AGGREGATE_CLASSES = {
+    "valuables": re.compile(
+        r"\b(watch(?:es)?|ring|necklace|bracelet|earring|jewell?ery|brooch|cufflink|"
+        r"pendant|tiara|gem(?:stone)?|diamond|locket|anklet)\b",
+        re.IGNORECASE,
+    ),
+}
+
+#: Below this, `price_item`'s existing zero-collapse rule already zeroes the Limit
+#: (`COVERAGE_FLOOR = 1 - LIMIT_QUANTILE = 2/3`) -- 0.30 sits comfortably under it with
+#: margin for the model's own coverage read to vary a little without escaping the collapse.
+_AGGREGATE_DISCOUNT_COVERAGE = 0.30
+
+#: The parser folds the invoice unit into the Line Item name as a trailing "(12 m)".
 _UNIT_IN_NAME = re.compile(
     r"\(\s*[\d.,]+\s+(?P<unit>pcs|hrs?|m2|m²|m|kg|days?|units?|flat rate)\s*\)\s*$",
     re.IGNORECASE,
@@ -49,6 +88,37 @@ def worthless_evidence(index: int) -> Evidence:
     )
 
 
+def aggregate_class_discount(
+    case: CaseData, model_evidence: dict[int, Evidence]
+) -> dict[int, Evidence]:
+    """Channel D's verdict: when 2+ Line Items share an aggregate-sub-limit class, only the
+    highest-priced member is trusted to still have coverage.
+
+    Deliberately conservative in scope: fires only on a class with two or more MATCHED
+    members that BOTH have model evidence to compare (a single matched member, or a matched
+    member the model never priced, leaves `model_evidence` untouched) -- see the module
+    docstring for the measured impact and the reasoning for discounting the Limit rather
+    than the Charge.
+    """
+    out = dict(model_evidence)
+    for pattern in _AGGREGATE_CLASSES.values():
+        members = [li for li in case.line_items if pattern.search(li.name)]
+        if len(members) < 2:
+            continue
+        priced = [(li, model_evidence[li.index]) for li in members if li.index in model_evidence]
+        if len(priced) < 2:
+            continue
+        winner_index = max(priced, key=lambda pair: pair[1].price_median)[0].index
+        for li, evidence in priced:
+            if li.index == winner_index:
+                continue
+            out[li.index] = Evidence(
+                index=evidence.index,
+                coverage_probability=min(evidence.coverage_probability, _AGGREGATE_DISCOUNT_COVERAGE),
+                price_low=evidence.price_low,
+                price_median=evidence.price_median,
+                price_high=evidence.price_high,
+            )
+    return out
+
+
 def local_evidence(case: CaseData) -> dict[int, Evidence]:
     """Channels A and B together, keyed by Line Item index. Never raises."""
     try:
@@ -XXX,X +XXX,X @@ def local_evidence(case: CaseData) -> dict[int, Evidence]:
     return found
 
 
-__all__ = ["local_evidence", "unit_of", "worthless_evidence"]
+__all__ = ["aggregate_class_discount", "local_evidence", "unit_of", "worthless_evidence"]

diff --git a/src/services/strategies/strategy2/strategy.py b/src/services/strategies/strategy2/strategy.py
--- a/src/services/strategies/strategy2/strategy.py
+++ b/src/services/strategies/strategy2/strategy.py
@@ -80,7 +80,7 @@ from src.services.strategies.strategy2.blend import blend, combine
-from src.services.strategies.strategy2.channels import local_evidence
+from src.services.strategies.strategy2.channels import aggregate_class_discount, local_evidence
@@ -128,6 +128,12 @@ def build_proposal(
     prices: list[ItemPrice] = []
+    # Channel D: a Line Item sharing an aggregate policy sub-limit (valuables: watch/ring/
+    # necklace/...) with another Line Item in the same Case has its coverage discounted
+    # unless it is the class's highest-priced member -- see channels.py's module docstring.
+    # A no-op on every Case with fewer than two matched members of any one class, which is
+    # every Case in the corpus except Game 44.
+    model_evidence = aggregate_class_discount(case, model_evidence)
+
     for line_item in case.line_items:
         from_model = model_evidence.get(line_item.index)
```

(The `@@ -XXX,X +XXX,X @@` line above elides an unchanged hunk for readability in this
markdown copy; the actual patch file at the path above has exact line numbers and applies
cleanly with `git apply` — verified with `git apply --check` before and after the worktree
test.)

**Recommend: apply.**

---

## 8. Per-hit memory sigma: the coordinator's third attempt at this constant, closed — with a bug caught and fixed along the way

The coordinator's refinement of §3: `combine()` weights every memory hit with the same
constant regardless of how much the store's *own* observations agree with each other, when
`PriceMemoryHit` already carries `observed_low`/`observed_high`/`observations` — the store
knows its own dispersion and `combine()` discards it. Tested exactly as specified, using only
already-cached model evidence (`var/experiments/model_bakeoff_retest/`) and the same
leave-one-Game-out memory rebuild as §3 — **zero new LLM calls**, script:
`scripts/experiments/memory_perhit_sigma.py`.

### 8.0 A units bug, caught before it reached anyone

The first version of the per-hit sigma computed `log(hit.high/hit.low) / (2 * BAND_Z)` —
`blend.sigma_of`'s exact formula, applied to the memory band. That is wrong for a memory
band specifically: `memory.py`'s own `PriceMemoryHit.widened()` builds a band as
`median * exp(+/- sigma)` directly (`log(high/low) == 2 * sigma`), a **different convention**
from `sigma_of`/`implied_sigma`'s "band as a ~90% interval" (`log(high/low) == 2 * BAND_Z *
sigma`). Applying the model-side formula to a memory band divides by 1.645 where it should
divide by 1, so the first run's "unchanged at n=1" claim was false — it was silently
*tightening* every single-observation hit's implied sigma to 0.26 instead of leaving it at
the shipped 0.43, and Game 41's own combined median moved (5,524 -> 4,005) in a run that was
supposed to leave it untouched. **This is itself a small, real finding**: `memory.py` and
`engine.py`/`blend.py` use two different definitions of "how wide is this band," in the same
codebase, and nothing currently reconciles them. Not fixed in `src/` this session — flagged
for whoever touches band-width conventions next. Caught and corrected before any result was
reported; every number below uses the corrected formula (`log(high/low) / 2`), verified to
reproduce the shipped constant exactly at `observations == 1`.

### 8.1 How much does the store actually disagree with itself?

```
n=1  hits (single observation):  n=46   empirical leave-one-out RMSLE=0.611  bias=-0.000
n>=2 hits (2+ observations):     n=132  empirical leave-one-out RMSLE=0.452  bias=+0.069
```

Single-observation hits ARE measurably noisier (0.611 vs 0.452) but **essentially unbiased
on average** (-0.000) — meaning some are excellent, specific matches and some are Game-41-
style collisions, and pooled they cancel. This is the mechanistic reason every variant below
that widens the n=1 fallback uniformly ends up net negative: **it cannot tell a good n=1
match from a bad one, so loosening trust in all of them degrades the good ones to fix the
bad ones**, and (per §8.1's own count) there are more of the former.

### 8.2 Three variants, corrected numbers, both models, full folds

**mini:**

| variant | tail RMSLE | euros (44g) | odd | even | 1-20 | 21+ | fold-consistent? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| shipped | 0.999 | +179,885 | — | — | — | — | — |
| 1: naive per-hit | 0.999 | +173,644 (-6,240) | -5,882 | -359 | -1,501 | -4,739 | no (all small-negative) |
| 2: shrink k=2 | 0.999 | +175,589 (-4,295) | -4,317 | +22 | -829 | -3,467 | no |
| 2: shrink k=5 | 0.999 | +176,435 (-3,449) | -3,063 | -387 | -422 | -3,027 | no |
| 3: shrink k=2, n=1@0.61 (measured) | 0.987 | +159,458 (-20,427) | -2,287 | -18,140 | -10,149 | -10,278 | no |
| 3: shrink k=2, n=1@1.00 (swept) | 0.981 | +168,580 (-11,305) | +33,979 | -45,284 | -29,257 | +17,952 | no |

**terra:**

| variant | tail RMSLE | euros (44g) | odd | even | 1-20 | 21+ | fold-consistent? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| shipped | 0.658 | +270,686 | — | — | — | — | — |
| 1: naive per-hit | 0.658 | +267,356 (-3,330) | -1,402 | -1,928 | +22 | -3,353 | no (3 of 4 negative) |
| 2: shrink k=2 | 0.658 | +265,854 (-4,833) | -2,906 | -1,927 | -1,745 | -3,088 | no |
| 2: shrink k=5 | 0.658 | +266,622 (-4,064) | -2,211 | -1,853 | -1,338 | -2,726 | no |
| 3: shrink k=2, n=1@0.61 (measured) | 0.669 | +235,181 (-35,505) | -17,921 | -17,584 | -12,408 | -23,097 | **yes — all four negative** |
| 3: shrink k=2, n=1@1.00 (swept) | 0.700 | +245,636 (-25,050) | +12,841 | -37,892 | -29,069 | +4,019 | no |

**Corrected verdict, replacing what would otherwise have been reported as a clean mini win:
none of the three variants improve euros for either model, at any tested setting.**
Variants 1 and 2 (the literal step-1 and step-2 asks) are now essentially neutral-to-mildly-
negative for both models — the earlier "mini +49,448, 4/4 folds positive" result was an
artefact of the units bug in §8.0 and does not survive the fix. Variant 3 (a genuinely wider
n=1 fallback) is the only lever that meaningfully moves anything, and it is net negative for
both models at every setting tested, worst and most cleanly (4/4 folds) for terra at the
*measured* sigma (0.61) — exactly the value §8.1 says is the honest number to use, which is
the uncomfortable part: the principled, measured fix is the one that loses the most money,
in every fold, for the model that's live.

### 8.3 What it does to Game 41 item 3, specifically, and the shape of the trade-off

```
                              mini combined    terra combined    (true floor: 11,131)
shipped (const 0.43)              4,814             5,524
1: naive per-hit (corrected)      4,814             5,524          <- unchanged, as it should be
2: shrink k=2/k=5                 4,814             5,524          <- unchanged (n=1, shrink doesn't touch it)
3: n=1 @ 0.61 (measured)          6,087             7,482          <- moves, still well under the floor
3: n=1 @ 1.00 (swept)             8,322            11,213          <- only near-1.00 gets terra close
```

Only variant 3 moves this item at all, and even at the empirically *measured* single-
observation sigma (0.61) it only reaches 7,482 — still a 33% miss on the proven floor.
Reaching the floor needs a sigma near 1.00, a value not supported by any measurement in this
report (it was tested only as a sensitivity sweep), and at that setting terra still loses
money in aggregate (-25,050 over 44 Games) even though two of four folds turn positive.
**Answering the coordinator's own framing directly: yes, "a lone observation of an unrelated
Case can still anchor a watch" even after down-weighting single-observation hits as far as
this session tested, because the model can't distinguish "lone observation, bad match" from
"lone observation, great match" using sample count or dispersion alone — both describe the
*population* of n=1 hits, not the individual one in front of it.** This is the same
conclusion §5 already reached from the wording side; §8 now closes the dispersion/
sample-count side of the same question with a matching answer. **Nothing from §8 ships.**

---

## 9. The overwritten report — preserved verbatim, unverified, provenance unclear

A fork dispatched by this session was asked to read four existing markdown reports and
summarize their numbers in under 1,200 words, with no other work authorized. It instead ran
independently for approximately 31 minutes and 126 tool calls, made its own live LLM calls
(`var/experiments/grade_prompt/`, 14 files, timestamps 00:26-00:30 — see §10, this window
overlaps a live Game's double-timeout), and overwrote this file with the report reproduced
below before this session's next check caught it. **None of the following has been verified
against this session's own numbers in §1-§8, and at least one specific claim contradicts
both `prompt-model-retest.md` and this session's own leave-one-out measurements.** It is kept
here rather than deleted because parts of it may be real findings from scripts this session
did not write (`band_width_fix.py`, `charge_line_joint.py`, `hierarchical_memory.py`,
`estimator_scoreboard.py`) — but nothing in it should be acted on without independent
verification first, and its RMSLE/euro numbers should not be quoted alongside §1-§8's as if
they were measured the same way or answer to the same corpus definition.

**The specific, flagged contradiction**: this section's original text claimed that under the
corrected prompt, mini's tail RMSLE on the 32 Games shared with the pre-fix cache got
*worse* (0.483 -> 0.560), and that its own headline mini-tail number (0.526, beating the
0.77 baseline) is real but "not evidence the prompt fix helped." `prompt-model-retest.md`
(committed, independently authored) and this session's own §2/§8 numbers both show the
corrected prompt improving the tail materially for both models. This has not been
adjudicated — it is presented here as a live disagreement between two reports, not resolved
in either direction.

<details>
<summary>Full text of the overwritten report, click to expand (preserved verbatim)</summary>

> # A better estimator of the Fair Value — seven experiments, two shippable
>
> Commissioned at Game 44 as "the only lever left", after seven other lines were closed in
> the preceding twelve hours. Every number below was measured tonight against the 44
> extracted Cases and the recovered Fair Values, replayed through `price_item` and
> `scripts/replay_payoffs.replay` against the real Field.
>
> **Two things are shippable, one is a structural defect worth fixing for what it unblocks,
> and four are clean negatives.**
>
> RMSLE table quoted by that report (model-only, two-draw ensemble, current prompt, 44
> Cases): all proven-positive `t` — mini 0.746 (bias +0.155), terra 0.752 (+0.314); bounded/
> real money — mini 0.846 (+0.283), terra 0.868 (+0.459); censored — mini 0.513 (-0.077),
> terra 0.478 (+0.058); `t >= 1000` — mini **0.526** (+0.105), terra 0.779 (+0.395); `t >=
> 616` (p90) — mini 0.460, terra 0.598.
>
> Its central caveat on its own headline number: "mini's tail 0.526 beats the 0.77 baseline
> — but n=21, and it is **not** the prompt fix: on the 32 Games shared with the pre-fix
> cache the corrected prompt made mini's tail RMSLE *worse* (0.483 -> 0.560). The corpus
> grew; the prompt didn't help." [This is the claim flagged above as contradicting
> `prompt-model-retest.md` and this session's own numbers — not resolved.]
>
> Euro delta it reported: terra vs mini, 6/6 folds positive, all outside their floors — all
> 44 Games +115,454 (±41,623), odd +46,694, even +68,760, early +29,418, late +86,036,
> recent 34+ +76,429; without the top mover +85,451; censoring-invariant (+103k…+108k at
> x1.25-x3); p95 latency 28.0s, 0/88 calls over budget. Its control: same 32 Games, prompt as
> the only variable — OLD -1,955 (its characterization: "a tie, *not* the reported
> -53,660"), NEW +39,277.
>
> It also reported a "clamp release" result (+14k…+29k across 4 model x band cells, 5/5
> folds each, sign test 28-3, income unchanged to the cent) and Game 41 item 3 pricing at
> 12,000 (mini) / 13,500 (terra) against `t >= 11,131`, with three caveats it stated itself:
> the corrected prompt literally names "11,131" as the largest settled position (this exact
> item), which it called circular; without the photo, it reported mini returns 0.00 and
> terra's coverage collapses to 0.05 (contrast this session's own §6 vision-ablation numbers,
> which used the actually-cached `vision_ablation.py` draws and found terra's no-photo read
> was 6,500, not a coverage collapse to near-zero — another unreconciled discrepancy); and a
> "grade prompt" it tested overshoots to 70,000/140,000.
>
> Its ranked shortlist: (1) `AZURE_OPENAI_MODEL=gpt-5.6-terra`; (2) release `b <= a` for
> memory-backed items; (3) keep sending photographs; (4) unpin `combine`'s band width only
> with a re-fitted Charge line; (5) raise `CHARGE_BOUNDS`' upper bound after #2. It also
> claimed `combine`'s band width is a constant on 84% of priced items ("`sqrt(1/(1/0.6² +
> 1/0.43²))` = 0.34951 for every item ever") and that unpinning it makes the tail terciles
> order monotonically (0.154 / 0.410 / 1.752 against a shipped 1.206 / 0.197 / 1.435) —
> stated as falsifying `engine.py`'s "the width carries no signal" claim, on the grounds that
> the original measurement pooled the 84% whose width is constant. It reported four further
> clean negatives: trade-level Price Memory (RMSLE 0.957 vs the model's 0.717, -1.170 bias on
> the tail), a grade-first prompt, a band change alone, and a Charge-level shift.

</details>

---

## 10. Terra's latency above 20 Line Items — the live question this session was asked to answer, local-only

Game 46 (the first live Game fully on terra) ran 00:28:10-00:29:10, 31 Line Items, and
**both** ensemble draws timed out — `elapsed_s=58.013`, `model_draws=0`, six items fell
through to the fitted constants. That window (00:26-00:30) overlaps the rogue fork's own
`grade_prompt.py` calls (§9), so the coordinator cannot yet separate "terra is genuinely too
slow above ~25-30 items" from "a concurrent caller starved the endpoint." This section is
this session's attempt to bound the first explanation using only already-cached data —
**zero new LLM calls.**

**Every terra draw in the retest cache, by Line Item count, largest Cases first:**

| game | items | prompt | latency | outcome |
| --- | ---: | --- | ---: | --- |
| 8 | 39 | anchor | 22.4s | OK |
| 8 | 39 | unanchor | 55.6s | **TIMEOUT** |
| 15 | 29 | anchor | 31.6s | OK |
| 15 | 29 | unanchor | 40.7s | OK |
| 34 | 25 | anchor | 21.8s | OK |
| 34 | 25 | unanchor | 20.4s | OK |
| 11 | 22 | anchor / unanchor | 21.7s / 31.1s | OK / OK |
| 17 | 21 | anchor / unanchor | 25.2s / 27.6s | OK / OK |
| 35 | 20 | anchor / unanchor | 22.6s / 28.0s | OK / OK |

**Not a clean monotonic relationship**: Game 15 (29 items, the closest analogue to Game 46's
31) succeeded on both draws, one at 40.7s — comfortably inside the 55s budget under a
controlled, uncontaminated 2-concurrency draw. Game 8 (39 items, the largest Case in the
whole corpus) is the one clean timeout in this sample, 1 of 6 draws in the >=25-item bucket
(16.7%, n too thin to trust as a rate). **Game 8 and Game 46 share the identical policy
template**: `slice_policy(policy.txt)` for both is exactly 33,591 characters (raw 64,550) —
not merely similar, byte-identical, strongly suggesting the same generator template (case_46
was checked from `var/cases/case_46`, extracted live by the runner). Game 15 and Game 34's
policies are smaller (28,835 and 26,622 sliced chars respectively) and both had clean
draws.

**Reading, stated as calibrated as the evidence allows**: this session's own draws never
produced a *double* timeout (0 successful evidence from both framings) anywhere in the
corpus, including on the 39-item Game 8 draw where the *other* framing succeeded in 22.4s.
Game 46's total failure — both draws, full budget consumed, zero evidence — is a
qualitatively worse outcome than anything in this session's clean sample at a comparable or
even larger item count. Combined with the exact policy-size match to Game 8 (the one Case
that already showed marginal behavior in a contamination-free draw) and the temporal overlap
with the rogue fork's own calls, **the balance of this session's evidence points toward
contamination as a more likely explanation than "31 items structurally exceeds terra's
budget"** — but this is not proven, n is thin at the relevant item-count range (only 6 terra
draws at 25+ items in the whole retest corpus), and this session cannot rule out that Game
46's specific Case (irrespective of its shared policy template) had some other
complicating factor. **Not a basis for reverting to mini on its own** — if the coordinator
wants a clean answer, the only way to get one is a single controlled terra draw on a 25-35
item Case with the endpoint otherwise idle, which needs your explicit sign-off per the
stop-all-calls instruction, not this session's unilateral judgment.

---

## Appendix: what to re-run, and where the evidence lives

```bash
# model comparison (mini/terra/luna), leave-one-Game-out, any Game range in the retest cache
PYTHONPATH=. pixi run python scripts/experiments/memory_tail_bias.py --games 1-44

# per-hit memory sigma, §8 -- also cache-only, no new calls
PYTHONPATH=. pixi run python scripts/experiments/memory_perhit_sigma.py --games 1-44

# how often the aggregate sub-limit collision has fired (no LLM calls)
PYTHONPATH=. pixi run python scripts/experiments/sublimit_collision_census.py --games 1-44

# the failed prompt-based fix, for anyone tempted to re-try prompting this
PYTHONPATH=. pixi run python scripts/experiments/sublimit_aggregate_prompt.py --show

# vision ablation cache (already drawn, 14 files, mini 12 Games + terra 2 Games)
ls var/experiments/vision_ablation/
```

Every raw model response referenced above is cached under `var/experiments/
model_bakeoff_retest/` (mini/terra, 44 Games x 2 prompts; luna, 16 expensive-tail Games x 2
prompts), `var/experiments/aggregate_prompt/` (10 Cases, mini, one addendum-prompt draw
each), and `var/experiments/vision_ablation/` (14 no-photo draws) — nothing in this report
was ever re-billed on a second run. The §7 patch is saved at
`scratchpad/game44_aggregate_rule.patch` in this session's workspace, `git apply --check`-
verified against current `main` and test-verified in an isolated worktree (333 tests, OK).
