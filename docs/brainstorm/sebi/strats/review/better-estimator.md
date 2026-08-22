# A better estimator of the Fair Value — seven experiments, two shippable

Commissioned at Game 44 as "the only lever left", after seven other lines were closed in the
preceding twelve hours. Every number below was measured tonight against the 44 extracted
Cases and the recovered Fair Values, replayed through `price_item` and
`scripts/replay_payoffs.replay` against the real Field.

**Two things are shippable, one is a structural defect worth fixing for what it unblocks, and
four are clean negatives.** The two shippable ones do not touch the estimator's prompt at all,
which is itself the finding: the prompt was re-tested end to end and is not where the money is.

---

## Provenance, so nothing here is unattributable

| | |
| --- | --- |
| corpus | 44 extracted Cases (1–44), 45 settled Games' Transactions |
| ground truth | `scripts/invert_fair_values.py`, 348 Line Items with a proven-positive `t` |
| model draws | `var/experiments/model_bakeoff_retest/` — **re-drawn tonight under the current prompt** |
| Price Memory | `var/price_memory.json`, 198 entries, Games 1–45, read live |
| noise floor | 26,622 · √(n/18) — quoted beside every delta |
| harnesses | `scripts/experiments/{retest_score,band_width_fix,charge_line_joint,hierarchical_memory,estimator_scoreboard,grade_prompt}.py` |

`scripts/experiments/` was being edited by another agent the same night, and `vision_ablation.py`
was rewritten under this work mid-session. §5's numbers therefore come from the **cache**, not
from whatever that file now contains: the 14 draws this report scores are the ones carrying
`"source": "vision-ablation"` in `var/experiments/vision_ablation/`, each recording its model,
its 55 s budget and its latency. `estimator_scoreboard.py` discovers them from disk rather than
importing a peer's game list, for the same reason.

**Live-tournament discipline.** Every LLM call went through
`scripts/experiments/live_window.wait_for_safe_window`, which refuses to *start* a call within
68 s of a Game boundary (55 s max call + 13 s margin) and holds until T+70 s after one, so no
call was ever in flight during the instructed T−10 s…T+70 s window. Concurrency was capped at
2, and the harness was never run alongside the other agent's `luna` draw. Every response is
cached under `var/experiments/`; nothing re-bills.

**The look-ahead this carries, stated once.** Price Memory is built from all settled Games,
including the ones being replayed. Every *comparison* below holds the memory channel identical
across arms, so it cancels; the *absolute* totals are inflated and are not quoted as forecasts.

---

## 1. ✅ SHIP — `gpt-5.6-terra` beats `gpt-5.4-mini` by +115,454, and the earlier verdict was a prompt artefact

Full live path — `blend` two framings → `combine` with Price Memory → `price_item` →
`replay` against the real Field, 44 Games:

| fold | n | mini | terra | terra − mini | floor | |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| **all** | 44 | 359,950 | 475,404 | **+115,454** | ±41,623 | outside |
| odd | 22 | 151,831 | 198,525 | +46,694 | ±29,432 | outside |
| even | 22 | 208,119 | 276,879 | +68,760 | ±29,432 | outside |
| early 1–20 | 20 | 195,610 | 225,028 | +29,418 | ±28,062 | outside |
| late 21+ | 24 | 164,340 | 250,376 | +86,036 | ±30,740 | outside |
| **recent 34+** | 11 | 79,372 | 155,802 | **+76,429** | ±20,811 | outside |

**Six of six folds positive, every one outside its own floor.** terra wins 25 of 44 Games.

Three robustness checks, because a total this size is exactly the shape this repo has been
burnt by:

- **Not one Case.** Dropping the largest single mover (g18, +30,003) leaves **+85,451 over 43
  Games**, still outside ±41,147.
- **Censoring-invariant.** Inflating unbounded `t_lo` by ×1.25 / 1.5 / 2 / 3 gives
  **+108,323 / +103,112 / +108,339 / +108,339**. The conclusion does not depend on how the
  censored half is read.
- **It fits the window.** terra p50 **13.8 s**, p95 **28.0 s**, max **40.7 s** over 88 real
  Case calls — **0 over the 55 s budget**. 6 transport errors against mini's 3; the blend
  degrades to a single draw when one fails, exactly as live.

### The stale verdict was the prompt, and this is the control

`model-bakeoff.md` reports terra losing 53,660 on a paired n=152. That cache was drawn
21:48–22:20, **before** both prompt fixes (settled anchors 21:53, real distribution quartiles
23:38). Re-scoring both caches on the same 32 Games, with the prompt as the only variable:

| prompt | terra − mini |
| --- | ---: |
| OLD (pre-fix) | **−1,955** (inside ±35,496) |
| NEW (shipping) | **+39,277** |

So under the old prompt the two models were a **tie**, not a 53,660 loss — the older figure
does not reproduce even on its own cache, because that scoring predates `memory_backed` /
`LIMIT_CEILING_MEMORY`. And the corrected prompt is worth ~+41k *to terra specifically*. The
remaining ~+76k of the 44-Game total comes from Games 33–44, which is consistent with the
recent-fold row above.

### Why RMSLE says the opposite, and why euros are right

| population | mini | terra |
| --- | --- | --- |
| real money (bounded, `t_lo>0`), n=212 | **0.466** | 0.522 |
| real money, `t ≥ 1000`, n=12 | **0.394** | 0.564 |
| censored (`t_hi = ∞`), n=119 | 0.545 | **0.370** |
| **censored, `t ≥ 1000`, n=11** | **1.570** (bias −0.833) | **0.926** (bias −0.232) |

mini wins on *bounded* items; terra wins on *censored* ones — and the censored population is
the expensive one, because an item nobody rightfully rejected is one everybody was willing to
pay for. `t_lo` there is a **proven lower bound**, so mini's −0.833 is a *demonstrated* 2.3×
under-price, not an inference. The euro replay weights by magnitude and scores censored items
at `t = t_lo`, the most conservative possible reading — i.e. the replay's own convention works
*against* terra's higher estimates, and terra wins anyway. **+115,454 is a lower bound.**

> Deploying terra means `AZURE_OPENAI_MODEL=gpt-5.6-terra` in `.env`, which this task forbids
> me to edit. It is a one-line change with the table above behind it; `LLM_TIMEOUT_SECONDS` is
> already 55 and the latency row says that is enough.

---

## 2. ✅ SHIP — the `b ≤ a` clamp silently throttles `LIMIT_CEILING_MEMORY`

`price_item` ends with `limit = min(limit, charge)`. For a memory-backed item the intended
ceiling is `LIMIT_CEILING_MEMORY = 0.75 × median`, but `charge_factor` returns ~0.65 at the
observed band widths, so the clamp holds the Limit at **0.65 × median and the 0.75 constant
never binds**. `engine.py` already says this in passing — "above roughly the Charge factor the
Charge sets the Limit and this constant stops binding" — and treats it as a reason 0.75 is a
natural stopping point. It is also a live cost, and it is measurable.

Releasing the clamp **for memory-backed items only** (model-only items keep it, so the
hallucination guard `LIMIT_CAP` and `LIMIT_CEILING` are untouched):

| model | band | delta | Games better | worse | folds positive |
| --- | --- | ---: | ---: | ---: | ---: |
| mini | shipped | +13,997 | 27 | 5 | **5/5** |
| mini | calibrated | +26,658 | 28 | 3 | **5/5** |
| terra | shipped | +21,069 | 25 | 2 | **5/5** |
| terra | calibrated | +28,644 | 27 | 2 | **5/5** |

**Income is identical in every arm** — this is a pure Reviewer-side effect, which is what makes
it mechanistically clean rather than a level nudge. On the mini/calibrated cell, income is
1,429,132 with the clamp and 1,429,132 without it, to the cent, while cost falls
1,073,550 → 1,047,665. (Income and cost are quoted from that one cell; the four rows above
differ in band and model, but the *identity* of income across the clamp arm holds in all four,
because the clamp cannot touch the Charge.)

The aggregate sits *inside* the 44-Game floor of ±41,623, so the fold consistency and the sign
test are what carry it — 28-vs-3 on the mini/calibrated cell is p < 10⁻⁵ — exactly the standard
`LIMIT_CEILING_MEMORY` itself was shipped on ("eight fold cells, eight positive… it is the fold
consistency carrying this, not the total"). Dropping the top mover (g17, +4,592) leaves
**+21,293**, so it is not one Case.

**Proposed diff** (`src/domain/pricing/engine.py`, in `price_item`):

```diff
-    limit = min(limit, charge)
+    # `b <= a` is a guard against an incoherent band, not a payoff requirement: the two
+    # numbers answer different questions ("what will the Field pay me" and "what am I
+    # willing to pay") and nothing in the payoff table orders them. On a memory-backed
+    # item the ceiling is already the tighter, better-evidenced bound -- the wording was
+    # seen settle and `invert_fair_values` recovered what it was worth -- so the clamp is
+    # pure loss there: it holds the Limit at charge_factor (~0.65) when
+    # LIMIT_CEILING_MEMORY says 0.75, and that constant therefore never binds.
+    #
+    # Measured over 44 Games, memory-backed items only, income unchanged in every arm:
+    #   mini/shipped band +13,997 (27 better, 5 worse)   terra/shipped +21,069 (25/2)
+    #   mini/calib. band  +26,658 (28 better, 3 worse)   terra/calib.  +28,644 (27/2)
+    # 5 of 5 folds positive in all four cells; +21,293 without the top mover.
+    # Inside the 44-Game noise floor, so this ships on fold consistency and the sign test,
+    # the same standard LIMIT_CEILING_MEMORY was shipped on.
+    #
+    # Falsifier: if Price Memory's measured error stops beating the model's, revert -- this
+    # rule's whole warrant is that the memory channel is the better-evidenced one.
+    if not memory_backed:
+        limit = min(limit, charge)
```

---

## 3. 🔬 STRUCTURAL DEFECT — the band width is a **constant** on 80–84 % of priced items

This is the most consequential thing found tonight even though it does not ship on its own.

`blend.combine` merges the model and the memory anchor by inverse-variance weighting **on the
two fixed priors**, then rebuilds the band from the posterior width:

```python
weight_model  = 1.0 / (MODEL_SIGMA_PRIOR ** 2)   # 1 / 0.60²
weight_memory = 1.0 / (MEMORY_SIGMA ** 2)        # 1 / 0.43²
low, median, high = _band_from(median, math.sqrt(1.0 / total))
```

`sqrt(1/(1/0.6² + 1/0.43²))` = **0.34951, for every Line Item that has ever existed.** It is a
function of two constants; nothing about the item enters it. The model's own asserted band and
the memory's observed spread are both computed and then thrown away.

- **277 of 331 scorable priced items (84 %) carry exactly σ = 0.34951.**
- The live decision log for Game 41 item 3 records `"sigma": 0.34951136485680523`.
- Price Memory now reaches 86 % of items, so the share is **rising**.

### This falsifies `engine.py`'s standing claim about the band

`engine.py` reports that width carries no signal — "the narrow third scores RMSLE 0.847 against
the wide third's 0.733, i.e. slightly *backwards*" — and concludes `CHARGE_SLOPE` "multiplies a
number that does not measure what it claims to". **That measurement pooled the 84 % of items
whose width is a constant**, and a constant contributes pure noise to an ordering.

Unpin the width (take it from the model's asserted band plus channel disagreement, in
quadrature, the way `blend` already treats between-draw spread) and the ordering appears:

| band | narrow | middle | wide |
| --- | ---: | ---: | ---: |
| shipped, all items | 0.527 | 0.343 | 0.585 |
| **unpinned, all items** | **0.380** | **0.514** | **0.574** |
| shipped, `t ≥ 1000` | 1.206 | 0.197 | 1.435 |
| **unpinned, `t ≥ 1000`** | **0.154** | **0.410** | **1.752** |

On the expensive tail that is an **11× monotone spread in the correct direction**, against a
shipped ordering that is pure noise. This is precisely the falsifier `engine.py`'s own docstring
names: *"a band whose width actually orders the error … then `CHARGE_SLOPE` is measuring
something and its sign can be trusted."*

### But it does not pay on its own — and that is consistent

| fold | width_only | full |
| --- | ---: | ---: |
| all 44 | −4,368 | +15,388 |
| odd / even | +17,811 / −22,180 | +26,410 / −11,022 |
| early / late | −4,864 / +495 | −9,997 / +25,385 |
| **recent 34+** | **−22,576** (outside floor) | −758 |

`level_width.py` already explained why: `charge_factor = 0.85 − 0.45σ`, so an honest width
*lowers* the Charge, and forfeiting income on the items we price correctly costs more than the
tail it protects. **The band and the Charge line are calibrated as a pair.** Fixing one alone
unpicks the pair — which is the same result that file got, now with the mechanism identified.

**So: do not ship the band change alone. Ship it only with a re-fitted Charge line** — and see
§4, which is why that is not ready either.

---

## 4. 🔬 The open theoretical question is now *half* decidable — the sign agrees, the level does not

With a calibrated σ, `CHARGE_INTERCEPT/SLOPE` vs the closed form becomes testable. The closed
form maximises `k · Φ(−ln k / σ)`:

| σ | closed form `k` | shipped line `0.85 − 0.45σ` |
| ---: | ---: | ---: |
| 0.20 | 0.780 | 0.760 |
| 0.35 | 0.743 | 0.693 |
| 0.50 | 0.772 | 0.625 |
| 0.65 | 0.855 | 0.557 |
| 0.77 | 0.968 | 0.503 |

They agree at σ ≈ 0.2 and diverge badly above it, with **opposite signs in σ**.

Replaying the closed form directly against the real Field on the calibrated band:
**+51,221 over 44 Games**, positive on all six folds, outside the floor on all / even / late /
recent. On the shipped band it is +40,321. So the derivation's *direction* — charge higher, and
do not discount so steeply for width — is confirmed in euros.

**But the level is not shippable, for a reason that only showed up on decomposition.** The
naive sweep cell "raise the Charge to 0.80" scores +63,643, and that number is two effects
added together:

(mini, calibrated band, 44 Games — the four cells share every other constant, so the rows are
directly differenceable.)

| configuration | net | income | cost | delta |
| --- | ---: | ---: | ---: | ---: |
| A shipped line, shipped clamp | 355,582 | 1,429,132 | 1,073,550 | — |
| B Charge 0.80, **clamp held at shipped** | 393,340 | 1,466,890 | 1,073,550 | +37,758 |
| C Charge shipped, **clamp released** | 381,467 | 1,429,132 | 1,047,665 | +25,885 |
| D both (the naive sweep cell) | 419,225 | 1,466,890 | 1,047,665 | +63,643 |

B moves income only, C moves cost only, and D is exactly their sum — which is the point: the
two effects are separable and the naive cell is not one finding.

C is §2 — a Limit-side effect that has nothing to do with the Charge. Isolating the Charge side
(B) gives +37,758, **inside the 44-Game floor**, and it fails two of five folds
(odd −10,377, early −2,176) while winning late +39,934 and recent +56,348.

Two further reasons not to ship a number here. The flat sweep **saturates at 0.80 because
`CHARGE_BOUNDS` clips it** — every value from 0.80 to 1.10 scores identically, so "0.95 − 0.45σ
is worth +123,986" is really "0.80 is worth +63,643" wearing a suit. And the surface has the
forbidden dip (0.65 → 0.70 costs −9,019 before rising again), which is the Field-Limit-cluster
artefact `engine.py` warns twice about.

**Verdict: the direction is now supported by two independent arguments that previously
disagreed, and that is worth recording. The magnitude is not established. Do not move
`CHARGE_INTERCEPT` on this.** What would settle it: `CHARGE_BOUNDS`'s upper bound raised so the
sweep can find an interior optimum, re-run on the calibrated band, with the clamp change from
§2 already in so it cannot be double-counted.

---

## 5. ❌ Vision — the photographs are load-bearing on exactly one Case, and mildly harmful elsewhere

`build_input_content` attaches every image as `input_image`. Ablated by re-drawing the identical
prompt and model with `image_paths=[]`, on the 12 highest-value photo Cases.

**On ordinary items the photo is slightly harmful.** Paired, same Line Items, mini:

| population | photo ON | photo OFF | paired sign test |
| --- | ---: | ---: | --- |
| real money, n=72 | 0.758 | **0.737** | photo OFF better **32–19** |
| real money `t ≥ 1000`, n=8 | 0.676 | **0.646** | photo OFF better 3–2 |
| censored, n=23 | **0.495** | 0.519 | photo OFF better 13–8 |

**On the one declared-valuables Case it is decisive.** Game 41 item 3, the tourbillon watch
(true `t ≥ 11,131`):

| | median | coverage |
| --- | ---: | ---: |
| mini, photo ON | 12,000 | 0.95 |
| **mini, photo OFF** | **0.00** | 0.82 |
| terra, photo ON | 13,500 | 0.92 |
| **terra, photo OFF** | **6,500** | **0.05** |

Without the photograph mini zeroes the band outright and terra collapses coverage to 0.05,
which would zero the Limit and wrongfully reject every one of the ten fair Charges the Field
issued on that item.

**And the whole euro effect is that one Case:**

| model | delta (photo OFF − ON) | without g41 |
| --- | ---: | ---: |
| mini, 12 Games | −13,350 (inside ±21,737) | **+4,499** over 11 |
| terra, 2 Games | −25,703 (outside ±8,874) | −4,222 over 1 |

**Verdict: keep sending the photographs — the downside on one valuables Case dwarfs the small
systematic cost — but there is no general vision lever here and nothing to build on.** The
third valuables Case (27) has no photograph, so the valuables-with-photo family is n=2. Any
claim stronger than "keep the attachment" is unsupported.

---

## 6. ❌ A grade-first prompt — reproduces the documented magnitude-class failure

Asked the model to name an `item_grade` (ordinary / premium / exceptional) and a market
`comparable` **before** the price band. Both are free-text fields `model.parse_items` never
reads, so unlike the two rejected structured schemas nothing mechanical can inflate a number —
the intent was to make the model reason about tier in its own context first. The treatment is
`prompts.PROMPT` verbatim with two request lines spliced in, so the control is the shipped
string, not a paraphrase.

It overshoots catastrophically:

| Game 41 item 3 (true `t ≥ 11,131`) | median |
| --- | ---: |
| mini, shipped prompt | 12,000 |
| **mini, grade prompt** | **70,000** |
| **terra, grade prompt** | **140,000** |

RMSLE improves slightly for mini (0.754 → 0.705; tail 0.652 → 0.603) but the euros are
governed entirely by that overshoot and **the sign depends on which model you pair it with**:
mini +105,296 over 11 Games (of which g41 is +76,755), terra **−87,061** over 2 Games (g41
alone −97,562, because a 140,000 median puts the Charge far above `t` *and* lifts the Limit
enough to buy every opponent's Overcharge).

This is the same failure mode `model.py`'s docstring already records for the order-of-magnitude
class field (−127,312) — a licence to go big, with the euro sign decided by luck. **Clean
negative. Do not revive it.**

> Methodological caveat I introduced myself and must flag: my grade prompt names "tourbillon"
> as an example of an exceptional item, which is the specific feature of the specific test
> item. Game 41 was contaminated by construction. Excluding it, mini is +28,541 over 10 Games
> — but on one model, ten Games, with terra catastrophic on the same prompt.

---

## 7. ❌ Hierarchical Price Memory (item → trade → global) — clean negative

Fuzzy matching is already falsified (σ 0.43 → 0.72 at Jaccard 0.7). This tried a coarser
*semantic* level instead of looser text matching: bin every settled Line Item into one of the
nine `level_anchors.BINS` trades, and answer memory misses with the trade's median (per-unit or
gross as appropriate). Leave-one-Game-out, offline, no LLM cost.

Reach is excellent and accuracy is not: **127 of 131 memory-miss items (97 %) are reachable**,
but

| estimator, on memory-miss items | n | RMSLE | bias |
| --- | ---: | ---: | ---: |
| trade-bin anchor | 128 | 0.957 | −0.235 |
| flat global median | 132 | 1.034 | −0.245 |
| **model-only (mini, current prompt)** | 124 | **0.717** | +0.186 |
| trade-bin, `t ≥ 1000` | 9 | **1.367** | **−1.170** |
| model-only, `t ≥ 1000` | 10 | **0.633** | +0.228 |

It beats a flat guess and loses decisively to the model it would displace — and it is worst
exactly where it would hurt most, under-pricing the expensive tail by e^1.17 ≈ 3.2×, because a
rare expensive item is diluted into a coarse trade average. The bin dispersions say the same
thing: `labour hours` 0.279 and `leak detection` 0.291 are tight, but `other` (122 of 331
observations) is 1.031 and `small parts` 1.194.

**Verdict: not a channel. The two tight bins are already covered by the per-unit rule.**

---

## The σ measurement, recorded per CLAUDE.md rule 10

Model-only (no Price Memory), two-draw ensemble, current prompt, all 44 Cases:

| population | mini | terra |
| --- | --- | --- |
| all proven-positive `t`, n≈325 | 0.746 (bias +0.155) | 0.752 (bias +0.314) |
| bounded / real money | 0.846 (+0.283) | 0.868 (+0.459) |
| censored (`t = t_lo`) | 0.513 (−0.077) | 0.478 (+0.058) |
| **`t ≥ 1000`, all** | **0.526** (+0.105) | 0.779 (+0.395) |
| `t ≥ 616` (p90) | **0.460** (+0.085) | 0.598 (+0.236) |

**mini model-only on the expensive tail is 0.526 against the 0.77 baseline** — the interim
result reported mid-run. Two caveats that keep it honest: n=21, and it is **not** the prompt
fix. On the 32 Games shared with the pre-fix cache, the corrected prompt made mini's tail RMSLE
*worse* (0.483 → 0.560). The tail number improved because the corpus grew, not because the
prompt did.

Break-even is σ ≈ 0.85 (README rule 10); every cell above clears it.

---

## Ranked shortlist

| # | change | evidence | risk |
| --- | --- | --- | --- |
| **1** | `AZURE_OPENAI_MODEL=gpt-5.6-terra` | +115,454 / 44 Games, **6/6 folds outside floor**, censoring-invariant, p95 28 s | Low. One env line, instantly revertible. Latency verified. |
| **2** | Release `b ≤ a` for memory-backed items (§2 diff) | +14k…+29k in 4/4 cells, **5/5 folds each**, sign test 28–3, income unchanged | Low. Reviewer-side only; model-only items untouched. |
| **3** | Keep sending photographs | No general gain, but photo-off zeroes the band on the one valuables Case | None — this is the status quo. Recorded so nobody "optimises" the attachment away. |
| **4** | Unpin `combine`'s band width — **only with a re-fitted Charge line** | Calibration proven (tail terciles 0.154/0.410/1.752 monotone); alone it is −4,368 and −22,576 on recent | Medium. Do **not** ship alone. |
| **5** | Raise `CHARGE_BOUNDS` upper bound, then re-fit the Charge line on the calibrated band | Closed form and euro replay now agree on direction; level confounded by the clamp and by clipping at 0.80 | High. The forbidden level surface. Needs #2 landed first. |

**Do not revive:** the grade-first prompt (§6), trade-level Price Memory (§7), and any band
change without the paired Charge-line change (§3).

### What would falsify the two ship candidates

- **#1**: three or four consecutive settled Games where mini beats terra on that window alone,
  or terra's p95 latency crossing ~45 s. Re-run `scripts/experiments/retest_score.py`.
- **#2**: Price Memory's measured leave-one-out error ceasing to beat the model's — the rule's
  entire warrant is that the memory channel is better evidenced. Re-run
  `scripts/experiments/band_width_fix.py` and `build_price_memory.py --evaluate`.
