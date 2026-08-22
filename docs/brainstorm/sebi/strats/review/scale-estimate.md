# Scaling the estimate: reproduces the earlier evidence, loses money anyway — do not ship

Written 2026-08-23. All numbers below are reproducible from
`scripts/experiments/scale_estimate.py` against the 19 Games that carry a decision log
(`var/decisions/game_026.json` … `game_045.json`) at the time this was measured, minus one
excluded (Game 42, corrupted log — see §1). `src/`, `main.py`, `pixi.toml` and `.env` were
left untouched, no running process was touched, and no LLM call was made: everything here
reprices already-logged evidence through the real `price_item` and replays it against the
real Field via `scripts/replay_payoffs.replay`.

**Vintage, pinned.** `var/price_memory.json` at measurement time read
`built_from_games=[1..44]`. A copy is pinned at
`scripts/experiments/pinned/price_memory_vintage_g44.json`. It is pinned for the record only
— this experiment never touches Price Memory directly; every item's evidence (including any
memory contribution) comes frozen from the decision log, exactly as it was blended and
submitted at the time.

## Headline

1. **The hypothesis is structurally different from every prior lever, and the harness proves
   it moves both numbers.** `price_median -> f(price_median)`, repriced through the
   unmodified `price_item`, moves the Charge *and* the Limit together (§3) — no multiplier
   swept before this could do that.
2. **The "evidence for it" reproduces — but the strongest-sounding numbers in that evidence
   are the biased-direction ones, and this was already flagged.** The 6.01× / 1.17×
   magnitude bias and the 73%-censored-below-`t_lo` proof both check out (§6) — but
   `level_fit.py`'s own docstring already warns that bucketing by the *true* `t` is the
   direction that "manufactures regression-to-the-mean", and its own actionable-direction
   table (bucketed by `t_hat` itself) already showed the top bucket running 1.95× *too high*,
   not too low. That inversion predicts exactly what this harness measures.
3. **A uniform scale is noise-floor-flat where it is small and a clear loss where it is
   large.** λ = 1.1–1.3 never clears the ±27,352 noise floor on either window and flips sign
   between the odd and even folds; λ = 1.5 and 2.0 are unambiguous, fold-robust losses (§4–5).
4. **Every magnitude-conditional variant that touches the 500–1,000 band loses money in
   every configuration tested.** `threshold>500` is negative at every λ, on both windows,
   confirming the "evidence against a uniform scale" directly: `t_hat` is *not* uniformly
   low in that band, so stretching it there is pure forfeited income plus newly admitted
   Overcharges (§4, §7).
5. **The one configuration that nominally clears the noise floor on 3 of 4 folds
   (`threshold>1000, λ=2.0`, +86,773 in-sample) is carried entirely by two Line Items in two
   Games.** Removing exactly those two Games turns every threshold-over-1000 configuration
   negative or flat (§8). This is the seventh negative, and it is the honest answer: the
   apparent win is not a rule, it is two anecdotes with a large price tag attached.
6. **Power-law stretching (γ > 1) is catastrophic and gets worse monotonically with γ**,
   replicating — in the opposite exponent direction — `level_fit.py`'s "the whole family's
   argmax is `c1 = 1`, the identity" finding, now on the current engine and the current
   window (§4, §5).
7. **Recommendation: no `src/` change.** No configuration survives the fold test broadly
   enough to ship. The gap belongs to the evidence layer (a genuinely better `t_hat` on the
   specific items that are wrong), not to any deterministic function of the `t_hat` we
   already have — the same conclusion `tests/test_strategy2.py::UncorrectedLevelTests`,
   `level_fit.py` and `upward-charge.md` each already reached from a different angle (§10).

---

## 0. Ground truth, verified first

```
PYTHONPATH=. python scripts/invert_fair_values.py --verify --games all
PYTHONPATH=. python scripts/replay_payoffs.py --games all --self-check
```

Both reproduce clean: **44/44 completed Games reconstruct**, every net matches the published
`/matrix` cell (or, for Games 1–24, falls outside the trailing 20-Game window and is taken on
the identity alone — never a mismatch). This is the same check the rest of the codebase
relies on; it was re-run, not assumed, before anything below.

## 1. Data: the decision-log window, and why Game 42 is excluded

`scripts/experiments/scale_estimate.py::discover_games()` scans every
`var/decisions/game_NNN.json`, reconstructs the real Line Item count for that Game from the
settled Transactions (`replay_payoffs.snapshot(g).line_items`), and keeps the Game only if
the logged item count matches. One Game fails this check:

```
EXCLUDED g42: logged 2 items, real run priced 17
```

`invert_fair_values.brackets(42, ...)` and `replay_payoffs.snapshot(42)` both independently
reconstruct 17 Line Items for Game 42 from the settled Transactions (and Game 42's replay
self-check reproduces the published net exactly with 17 items), confirming the real run
priced 17 — the log on disk was corrupted by a stray write and repaired only in the live
merge logic, never on disk. Included as logged, it would silently score a 2-item Game as if
15 Line Items never existed. Excluded, as CLAUDE.md's own account of exactly this failure
mode requires.

That leaves **19 Games**: `[26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41,
43, 44, 45]`, carrying **195 priced (evidence-backed) Line Items**. Game 45 settled live
while this was being written; it is included because the discovery check is automatic, not a
hard-coded range — the number is deliberately "whatever is currently true", stated explicitly
rather than pinned to make the report look tidier.

Two windows are reported throughout, both against this same 19-Game population:

- **ALL19** — every logged, verified Game.
- **LAST15** — the most recent 15: `[30..41, 43, 44, 45]` (the window CLAUDE.md's task
  brief asked for specifically).

## 2. Self-check: reconstruction against the logs

`price_item`'s Charge depends only on `price_median` and the band-implied `sigma` — not on
`confirmed_uncovered` or `memory_backed` — so an exact Charge match validates the Evidence
extraction and confirms `CHARGE_INTERCEPT` / `CHARGE_SLOPE` / `CHARGE_BOUNDS` have not moved
since these Games were played:

```
Charge exact match: 195/195
Limit rule (priced vs uncovered-free-option) match: 195/195
```

The Limit *rule* (zero iff `confirmed_uncovered` or coverage floors it) also matches on all
195 items, validating the `quantity_missing` → `confirmed_uncovered` and `"B:memory" in
channels` → `memory_backed` reconstruction against `strategy.py::build_proposal`'s own logic,
read directly from source.

**The absolute Limit *value* deliberately does not match on 67 of 127 priced-both-sides
items** (ratio to the logged value: min 0.185, median 0.689, max 3.025; 60 items already
match exactly). This is not a bug: `LIMIT_CEILING` has been re-measured and moved repeatedly
over the tournament (0.20 → 0.30 → 0.40 → 0.45, with 0.85 having shipped earlier still —
see the constant's own history in `src/domain/pricing/engine.py`), and
`LIMIT_CEILING_MEMORY` plus the model-only `LIMIT_CAP` exemption shipped only tonight, after
most of these Games were played. The task brief says to use the current engine, so this
harness's baseline (λ = 1.0) is **"the evidence exactly as logged, priced by today's
engine"** — not "what we actually submitted". That is the correct counterfactual for
deciding whether to ship a *further* change on top of today's engine, and it is why every
delta below is measured against that recomputed baseline, never against the historical
submission.

## 3. The harness moves both `a` and `b` — asserted, not assumed

```
sample: g26 item 1  median=288.44
  lambda=1.0  ->  a=197.59  b=129.80
  lambda=1.5  ->  a=296.38  b=194.70
```

The script asserts `a` strictly increases and `b` increases (or stays clamped to `a`) for
every scale tested. This is the entire structural difference from every multiplier sweep
tried before tonight: a Charge-only multiplier breaks the `b <= a` derivation, a Limit-only multiplier is
`LIMIT_CEILING`/`LIMIT_CAP`, already swept exhaustively; scaling the *estimate* moves both
through the same, real formula.

## 4. The λ / conditional / power sweep, both windows

Noise floor `26,622 * sqrt(n/18)`: **27,352** at n=19, **24,302** at n=15.

| config | ALL19 delta | LAST15 delta |
| --- | ---: | ---: |
| uniform λ=1.0 (baseline) | 0 | 0 |
| uniform λ=1.1 | +9,572 | +6,097 |
| uniform λ=1.2 | +3,996 | −1,246 |
| uniform λ=1.3 | −2,084 | −10,951 |
| uniform λ=1.5 | **−46,063** | **−41,068** |
| uniform λ=2.0 | **−96,625** | **−96,739** |
| threshold>500, λ=1.2 | −2,293 | −8,703 |
| threshold>500, λ=1.5 | **−35,288** | **−32,493** |
| threshold>500, λ=2.0 | **−38,913** | **−44,745** |
| threshold>1000, λ=1.2 | +34,246 | +27,911 |
| threshold>1000, λ=1.5 | +17,505 | +20,491 |
| threshold>1000, λ=2.0 | **+86,773** | **+80,560** |
| power γ=1.1, anchor=50 | −6,548 | −4,933 |
| power γ=1.25, anchor=50 | **−180,672** | **−164,682** |
| power γ=1.5, anchor=50 | **−444,174** | **−430,453** |

Bold = clears the noise floor for that window. Reading this table straight:

- **Every uniform λ from 1.1 to 1.3 is inside the noise floor on both windows.** None of
  these numbers license a conclusion by themselves.
- **λ ≥ 1.5 is an unambiguous, large loss**, well past the noise floor on both windows.
- **`threshold>500` never wins**, at any tested λ, on either window. Scaling the 500–1,000
  band specifically hurts — direct confirmation that `t_hat` is not uniformly low there (the
  "evidence against a uniform scale" the brief asked to confront).
- **`threshold>1000` is the only family that clears the noise floor**, and only at λ=2.0.
  §8 shows why that number should not be trusted at face value.
- **Power-law stretching is catastrophic and monotone in γ.** Already negative at γ=1.1
  (weaker per-item than `threshold>500`'s λ=1.2 but touching *every* item above the anchor,
  not just a band), it is a six-figure loss by γ=1.5.

## 5. Held-out folds (odd/even, early/late), every configuration

Fold sizes: ODD n=10 (nf=19,843), EVEN n=9 (nf=18,825), EARLY n=9 (nf=18,825), LATE n=10
(nf=19,843).

| config | ODD | EVEN | EARLY | LATE |
| --- | ---: | ---: | ---: | ---: |
| uniform λ=1.1 | −13,786 | +23,359 | +7,233 | +2,339 |
| uniform λ=1.2 | −19,057 | +23,053 | −10,359 | +14,355 |
| uniform λ=1.3 | −28,807 | +26,723 | −6,366 | +4,282 |
| uniform λ=1.5 | −29,457 | −16,606 | −31,252 | −14,811 |
| uniform λ=2.0 | −24,336 | −72,289 | −56,042 | −40,582 |
| threshold>500, λ=1.2 | −23,534 | +21,241 | −12,799 | +10,506 |
| threshold>500, λ=1.5 | −27,891 | −7,397 | −26,726 | −8,561 |
| threshold>500, λ=2.0 | −13,272 | −25,641 | −36,660 | −2,253 |
| threshold>1000, λ=1.2 | +758 | +33,487 | +5,293 | +28,952 |
| threshold>1000, λ=1.5 | +11,525 | +5,980 | −4,027 | +21,532 |
| threshold>1000, λ=2.0 | **+51,828** | **+34,945** | +5,172 | **+81,601** |
| power γ=1.1 | −12,774 | +6,226 | −19,871 | +13,323 |
| power γ=1.25 | +13,120 | **−193,792** | **−64,323** | **−116,349** |
| power γ=1.5 | **−207,195** | **−236,979** | **−94,508** | **−349,666** |

**Uniform λ=1.1's in-sample +9,572 flips sign on the odd fold (−13,786 vs +23,359 on
even).** That is the exact signature CLAUDE.md's ledger already names — "six of seven levers
tested tonight died on exactly this test" — and it dies here on the seventh.

**`threshold>1000, λ=2.0` clears the noise floor on 3 of 4 folds** (ODD, EVEN, LATE) and is
the only configuration in the whole sweep that does. Its one weak fold, EARLY (+5,172,
inside the 18,825 floor), is not a coincidence — see §8.

**Power γ≥1.25 is unanimously, catastrophically negative across every fold** bar one
(ODD at γ=1.25, +13,120, itself dwarfed by the same config's EVEN fold at −193,792). This
is as clean a fold-robust negative as this codebase has produced on any lever.

## 6. Confronting the "evidence for it" directly

The magnitude-conditional evidence quoted in the task brief — `t_hat/t` ≈ 6.01 under 50 EUR,
1.17 over 1,000 — matches `level_fit.py`'s own published table for Games 1–24 **to two
decimal places**, because it is the same table: median `t_hat/t` **bucketed by the true
`t`**. That script's own docstring already carries the warning this report has to repeat:

> "Conditioned on the truth we look 6x too *high* on cheap items; conditioned on our own
> estimate we are 2x too *low* on exactly the same kind of item. Each column is a regression
> artefact of its own conditioning variable and they point opposite ways."

Bucketed by `t_hat` itself — the only direction observable at submission time, and therefore
the only one a scaling rule can act on — the *same* Games 1–24 sample runs **0.46× under 50
EUR and 1.95× above 1,000**: already too high at the top, not too low. That inversion is
exactly why `threshold>500` and the power family lose in this report's own, independently
measured window (Games 26–45): pushing up the top of the *own-estimate* distribution pushes
up a population that, conditioned the actionable way, is already running hot.

The 73%-censored-below-`t_lo` proof (from `upward-charge.md`, written independently the same
night on Games 1–38 evidence) is real and is not a regression artefact — it is a proof, not
an inference, because `t_lo` is a hard lower bound recovered from a wrongful rejection. It
correctly predicts that *some* high-value items are underpriced. It does not predict *which*
items, and §8 shows that the two items actually driving this report's one surviving
configuration are exactly the kind that proof identifies (both unbounded, `t_hi = None`) —
but there is no signal available at decision time to tell them apart from the boiler and
drying items in the same magnitude bucket that are catastrophically *overpriced* (see the
table in §8).

## 7. Two-mechanism decomposition, every configuration (ALL19)

| config | Δ issuer income | penalty saved | Overcharges newly accepted | net Δ |
| --- | ---: | ---: | ---: | ---: |
| uniform λ=1.1 | +4,102 | −8,900 | +3,430 | +9,572 |
| uniform λ=1.2 | −10,132 | −24,120 | +9,991 | +3,996 |
| uniform λ=1.3 | −18,040 | −35,865 | +19,909 | −2,084 |
| uniform λ=1.5 | −58,089 | −51,918 | +39,892 | −46,063 |
| uniform λ=2.0 | −100,682 | −78,882 | +74,825 | −96,625 |
| threshold>500, λ=1.2 | −12,494 | −16,745 | +6,543 | −2,293 |
| threshold>500, λ=1.5 | −42,122 | −33,297 | +26,462 | −35,288 |
| threshold>500, λ=2.0 | −41,797 | −51,510 | +48,626 | −38,913 |
| threshold>1000, λ=1.2 | +26,907 | −7,814 | +475 | +34,246 |
| threshold>1000, λ=1.5 | +5,348 | −12,632 | +475 | +17,505 |
| threshold>1000, λ=2.0 | +66,043 | −24,084 | +3,355 | +86,773 |
| power γ=1.1 | −24,173 | −35,804 | +18,163 | −6,548 |
| power γ=1.25 | −201,003 | −86,427 | +66,069 | −180,672 |
| power γ=1.5 | −453,271 | −102,867 | +93,710 | −444,174 |

(Signs: the "penalty saved" column is printed as a *negative* number because it is shown as
its cost-side contribution — money that stops being paid, i.e. `-0.5a` per crossing added to
the cost delta. So `net Δ = Δ income − (penalty-saved column + Overcharges-newly-accepted
column)`: for uniform λ=1.1, `4,102 − (−8,900 + 3,430) = 9,572`, matching the printed net Δ.)
One structural note, which the task brief
asked to correct explicitly: **the recoverable saving on a wrongful rejection is `0.5a`, not
`1.5a`** — two thirds of every penalty is money owed regardless of whether the Limit accepts
it, and `item_cost_split` in the harness computes exactly the `0.5a` half, per crossing, per
opponent.

**The Limit side worsens faster than the Charge side improves at every λ once the scale
stops being tiny.** In every uniform and `threshold>500` row, "Overcharges newly accepted"
grows roughly in step with "penalty saved" and overtakes it by λ=1.3–1.5 — a widened Limit
does not distinguish a newly-affordable fair Charge from a newly-affordable Overcharge, and
the Field has plenty of both. `threshold>1000` is the one family where this ratio stays
favourable throughout (penalty-saved / Overcharges-newly-accepted is 16.5× at λ=1.2, 26.6×
at λ=1.5, 7.2× at λ=2.0 — never close to 1:1 the way the other families get by λ=1.3–1.5),
which is a real, measured reason it is the only survivor of §4 — but the *income* line, not
the Limit line, is what actually carries its win (§8 shows exactly where that income comes
from).

## 8. The cliff — and why `threshold>1000, λ=2.0`'s win does not generalise

Items crossing from `a <= t` to `a > t` forfeit most of their would-be income immediately:

| config | items crossed up | income at old (under-t) Charge | actual income after crossing | forfeited |
| --- | ---: | ---: | ---: | ---: |
| uniform λ=1.1 | 6 | 45,397 | 8,481 | −36,915 (−81%) |
| uniform λ=1.2 | 20 | 113,790 | 28,328 | −85,462 (−75%) |
| uniform λ=2.0 | 62 | 289,930 | 28,419 | −261,511 (−90%) |
| threshold>1000, λ=2.0 | 4 | 70,322 | 3,606 | −66,716 (−95%) |

Crossing the cliff is expensive even in the one family that nets positive overall — 95% of
the would-be income on the 4 items that cross is forfeited. **`threshold>1000, λ=2.0`'s net
gain of +86,773 is not coming from those 4 crossings; it is coming from the 94 items that
stay under `t`** (income gained there: +149,032, against the −66,716 forfeited above — net
+82,316, essentially the whole story).

So which items, staying under `t`, are worth so much? Every Line Item in the 19-Game sample
with `price_median > 1,000` (the population `threshold>1000` touches at all):

| Game | item | median | t_lo | t_hi | t (point used) | channels |
| --- | --- | ---: | ---: | --- | ---: | --- |
| 29 | Renew the water-damaged boiler… | 7,139 | 0 | 57 | 29 | model only |
| **44** | **Compensation for stolen watch** | **6,840** | **9,361** | **∞** | **9,361** | **memory + model** |
| **41** | **Compensation for robbery damage** | **5,524** | **11,131** | **∞** | **11,131** | **memory + model** |
| 28 | Renew boiler system incl. flue gas… | 4,837 | 0 | 50 | 25 | model only |
| 44 | Compensation for stolen diamond ring | 4,183 | 0 | 884 | 442 | model only |
| 27 | Compensation for robbery damage | 3,795 | 3,000 | 3,022 | 3,011 | model only |
| 33 | Technical drying (large-area…) | 3,666 | 0 | 50 | 25 | model only |
| 40 | Full restoration of the painting | 2,665 | 2,137 | 2,880 | 2,508 | memory + model |
| 44 | Compensation for stolen gold necklace | 2,121 | 0 | 663 | 331 | model only |
| 33 | Floor covering removal | 1,625 | 0 | 50 | 25 | model only |
| … 7 more, medians 1,018–1,344, all within roughly 1.1x–1.3x of `t` | | | | | | |

Of 17 items over 1,000, **exactly two — g44's stolen watch and g41's robbery damage
compensation — are the underpriced, unbounded items the hypothesis is actually about**
(estimate 0.73× and 0.50× the true floor, respectively, both censored so the true value
could be even higher). The rest are either already close to `t` (the "skilled worker hours"
and painting-restoration items, where doubling the estimate would only hurt) or catastrophic
*over*-estimates on effectively worthless items (the two boiler items and the drying/flooring
items, `t <~ 30` against medians of 3,600–7,100 — literally the item the `LIMIT_CAP`
docstring in `engine.py` names as the reason that constant exists). A uniform rule applied to
"everything over 1,000" cannot tell these three populations apart, because nothing in the
decision-time evidence separates them (this is `upward-charge.md`'s §2 finding, independently
reproduced here): `price_median`, `sigma` and `coverage_probability` do not distinguish "our
number is 2× too low" from "our number is 250× too high" within the same magnitude bucket.

**Direct per-Game confirmation** (`scripts/experiments/scale_estimate.py`, STEP 10):

| config | total ALL19 | top-2 Games | top-2 sum | remaining 17 Games |
| --- | ---: | --- | ---: | ---: |
| threshold>1000, λ=1.2 | +34,246 | g44, g37 | +7,618 | **+26,628** |
| threshold>1000, λ=1.5 | +17,505 | g44, g41 | +76,298 | **−58,793** |
| threshold>1000, λ=2.0 | +86,773 | g44, g41 | +139,515 | **−52,743** |

At λ=1.2 the remaining 17 Games are still mildly positive (+26,628, but the total itself
never clears the noise floor at this λ — see §4 — and the ODD fold is +758, essentially
zero). At λ=1.5 and λ=2.0 — the only two λ where `threshold>1000` clears the noise floor on
most folds — **removing exactly Games 41 and 44 turns the result negative**, by more than
the total itself was positive. This is precisely why the EARLY fold (which contains neither
Game 41 nor 44) showed nothing in §5: it is not a weaker version of the same signal, it is
the honest baseline with the two anecdotes removed.

**Conclusion: the one configuration in this entire sweep that nominally beats the noise
floor on 3 of 4 folds does so because of two Line Items in two Games, not because "scale
everything over 1,000 by 2×" is a rule that holds broadly.** Shipping it would mean betting
the whole configuration's expected value on two Games recurring in roughly that shape again,
against a population (§8's table) where most of the neighbouring items in the same bucket are
either near-`t` already or catastrophically overpriced, not underpriced.

## 9. The `b <= a` clamp

```
clamp bound at lambda=1.0 (shipped): 62 / 195 items
<every tested configuration>          clamp bound after: 62 / 195
```

The clamp's binding count does not move under any scale tested. Mechanically this makes
sense as long as `Evidence.with_defaults()` does not need to widen the band: the Charge, the
lognormal quantile and `ceiling * median` all scale linearly with `price_median` at fixed
`sigma`, so their relative ordering — and therefore whether the clamp binds — is invariant to
a level shift alone. `LIMIT_CAP` (an absolute 708 EUR, not scaled by λ) is the one place a
scale *could* change which term binds, but at these λ and on these 195 items it did not flip
the coarse `limit == charge` count. This is a real, measured answer to the task's specific
question ("check whether the clamp starts binding differently") — it does not, at this
granularity, in this sample — but it is not proof the underlying mix of binding terms is
static; a finer instrument (which of {quantile, ceiling, cap} is the argmin) was not built,
because the coarse answer already settles that this is not where the sweep's losses or gains
come from.

## 10. Recommendation

**No `src/` change is proposed.** No diff follows this report, because none of the fifteen
configurations tested — spanning the full family the brief specified (uniform, threshold-
conditional at two thresholds, power-law with `γ > 1`) — survives its own held-out fold
broadly enough to ship:

- Small uniform scales (λ = 1.1–1.3) are inside the noise floor and flip sign between folds.
- Large uniform scales, `threshold>500` at any λ, and the whole power family are clear,
  fold-robust losses.
- `threshold>1000, λ=2.0` is the sole configuration that nominally clears the noise floor
  broadly — and §8 shows that win is two Games, not a rule.

This is the seventh negative, stated plainly per CLAUDE.md's own rule: **scaling the
estimate loses money, or at best is statistically indistinguishable from not scaling it, on
every variant tested.** It reproduces the direction and magnitude of the evidence that
motivated it (§6), and still loses — for the same structural reason `level_fit.py` already
found for the shrinking direction and `upward-charge.md` already found for a Charge-only
conditional multiplier: **the decision-time evidence (`price_median`, `sigma`,
`coverage_probability`, `channels`) does not separate the specific items that are
underpriced from the specific items that are wildly overpriced within the same magnitude
band.** A function applied uniformly to a magnitude band necessarily helps the former and
hurts the latter at the same time, and on this data the latter wins except in the two-Game
anecdote of §8.

**What would change this answer:** a decision-time signal that actually separates "this
`t_hat` is too low" from "this `t_hat` is too high" *within* the same magnitude bucket —
`upward-charge.md` §2 already tried the obvious candidates (`t_hat`, `sigma`,
`coverage_probability`, `quantity` individually: AUC 0.44–0.56, indistinguishable from a coin
flip) and found only two categorical splits with a real gap (memory-backed channel, metered
wording), neither of which converted to euros there either. The next test worth running is
whether a *second opinion specifically on items already estimated above ~1,000* (a targeted
re-ask, not a blanket rule) can supply that separating signal — which is a model-evidence
question, not a pricing-arithmetic one, and therefore out of scope for this report and this
harness.

---

## Appendix: reproduction

```
PYTHONPATH=. pixi run python scripts/invert_fair_values.py --verify --games all
PYTHONPATH=. pixi run python scripts/replay_payoffs.py --games all --self-check
PYTHONPATH=. pixi run python scripts/experiments/scale_estimate.py
```

The harness (`scripts/experiments/scale_estimate.py`) is self-contained: it discovers its own
Game list (STEP 1), self-checks its reconstruction against the logs (STEP 2), asserts the
core mechanism (STEP 3), sweeps every configuration (STEP 4), reports every held-out fold
(STEP 5), decomposes every delta into the two mechanisms (STEP 6), accounts for the cliff
(STEP 7), checks the clamp (STEP 8), ranks configurations and re-tests the winner against
every fold (STEP 9), and — because the winner's fold performance looked too good relative to
everything else in the sweep — breaks its per-Game contribution down explicitly (STEP 10).
`var/price_memory.json` vintage is pinned at
`scripts/experiments/pinned/price_memory_vintage_g44.json` for the record.
