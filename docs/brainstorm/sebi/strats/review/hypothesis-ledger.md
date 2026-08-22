# Hypothesis ledger

One Game is far inside the **26,622** noise floor measured over 18 Games, so no single Game
can justify a constant change. This file is how evidence accumulates instead of being
re-derived from whichever Game settled most recently.

**After every Game:** run `pixi run learn`, then add a line to the relevant hypothesis saying
whether that Game supported it, contradicted it, or said nothing — with euros. Promote a
hypothesis to a change only when the replay over **all** settled Games agrees, or it clears
the noise floor on a held-out split.

Statuses: 🔬 open · ✅ confirmed and shipped · ❌ falsified · 💤 dormant (no evidence either way)

---

## H1 ✅ The Limit belongs low, and the ceiling is what binds

**Claim.** `LIMIT_CEILING` near 0.30 beats anything looser, because a loose Limit buys volume
of accepted Overcharges rather than protection.

- Games 1–24, replay: 0.25 → +109,047, **0.30 → +108,399**, 0.45 → +92,602, 0.85 → +72,694.
- Decomposition 0.30 → 0.85: penalties saved 222,098, but 109,738 of that is paid on accepted
  Overcharges — pure loss — and 148,065 is money owed anyway. Net −35,705.
- Every window agrees in direction; the Games 15–19 inversion that once bought 0.85 was a
  four-Game fluctuation, reversed by the next five.
- **Shipped** at `cb00fed`. Caveat recorded: the full-sample gain (1,553/Game) is inside the
  noise floor; only the recent windows clear it.

## H2 ❌ The estimator's level can be corrected by a function of `t_hat`

**Falsified, expensively.** A fitted log-linear recalibration lost **54,713** in sample and
−14,104 / 0 / −183,048 across three held-out folds whose exponents disagree on the *sign*.
Rewritten price anchors lost 104,515; a sigma floor at the measured error lost 247,443;
per-trade and per-unit multipliers survived no fold.

The diagnosis that motivated it was a regression artefact: median `t_hat/t` is 6.01 in the
"under 50" bucket by *true* `t` and 0.46 in the same bucket by *`t_hat`*. Do not revisit
without conditioning on `t_hat`.

## H3 🔬 The remaining prize is item accuracy, reachable only through better evidence

Moving each median to its own true Fair Value, band and coverage untouched, takes Games 1–24
from 127,292 to **228,987**. So **+101,695** exists and H2 proves none of it is a function of
the number we already have. Charging and accepting at `t` outright would be 811,569.

Open question: which *evidence* closes it — a better coverage read, a second opinion on the
expensive items only, or Price Memory reaching further than 22% of items.

## H5b ❌ "41% of our Charges are unrecoverable" — mostly an artefact, and the fix loses money

**The headline was mine and it was wrong.** `scripts/charge_buckets.py` split the 320 scored
Line Items by whether the item was worth anything at all:

- **103 of 320 have `t_lo = 0`.** Nobody was ever owed money on them, so a Charge there is
  above `t` *by construction* — and a rejected Overcharge on a worthless item costs exactly
  nothing (R6c). That is the free option we take **deliberately**. Those items supply **98 of
  the 135 unrecoverable Charges and 0 euros of forgone income.**
- On the **217 items actually worth something** we over-charge **37 times (17%)**, at median
  `a/t` **0.68** — which is the very number the ledger was holding up as eyay's target.
- Every charging team in the Field, eyay included, is "over" on **all ten** worthless items of
  Games 21-27. Our real gap on real-money items is **0.78 vs eyay's 0.70** over Games 21-27 —
  mid-field, next to Teamers at 1.00 and harissa eagles at 0.94.
- The "7 of 316 versus our 19 of 46" comparison was apples to oranges: eyay's figure counted
  Charges rejected by all sixteen reviewers. Ours in the same sense is **2 of 48**.

So the Issuer side is roughly *at* the field's level, not an outlier, and there is no headline
defect to fix. The original entry follows, kept because its measurements are correct even
though its framing was not.

### What the conditional search did find

Two real signals on the 217 real-money items, by share of that bucket's reachable income
forgone: **the channel** — model-only forfeits **11%** against memory-backed **3%** — and
**σ with its sign inverted**: the *narrow* third over-charges more often and forfeits **3×**
the share of the wide third. `CHARGE_SLOPE` is discounting on a width that does not order the
error, in euros as well as in log space.

**Nothing shipped, and every candidate failed the bar.** Downward multipliers on any bucket
lose, because 373,980 of the 450,622 oracle gap is the deliberate discount on *correctly*
priced items, and any bucket wide enough to catch the 37 Overcharges also holds ~180 items
where `a <= t`. The two in-sample winners — a flat factor (`slope = 0`) and memory ×1.15 with
model ×0.9 — are jagged in their own parameter, want opposite corners in the two windows, and
held out sum to **−15,354** (odd→even) and **−29,279** (1-20→21-27). The +42,197 peak is Games
7 and 1 crossing a Limit cluster.

**The one thing worth acting on later:** if the band is ever calibrated, `CHARGE_SLOPE = 0` is
what the paired comparison already argues for — 6 of 7 pairs on both windows.

### Original entry (measurements sound, framing wrong)


**Measured, on-policy.** Over the Strategy 2 era (Games 21-27), **19 of 46 Charges sat above
the Fair Value**, so not one of sixteen reviewers could owe us anything on them. Median `a/t`
is **0.99**. eyay, over the same corpus, runs median `a/t` **0.68** with **7 of 316**
unrecoverable, and takes 574,774 of structural income against our 230,025.

This is a structural fact rather than a fitted one, and it survives the regime split (51% of
Charges unrecoverable over Games 1-18, 41% over 19-26, 41% over 21-27). It is the clearest
remaining defect on the Issuer side.

**But the obvious fix is not shippable, and the reason matters.** Scaling our own Charges and
replaying gives a *jagged* surface, not a curve:

| Charge × | 0.55 | 0.65 | 0.75 | 0.85 | 1.00 | 1.15 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Games 21-27 | +39,893 | **+69,756** | +45,097 | +55,676 | +38,997 | +10,041 |
| Games 19-27 | +60,408 | **+102,301** | +79,184 | +98,639 | +86,170 | +2,752 |

Non-monotone in both windows, with 0.75 *worse* than both its neighbours. The Field's Limits
are clustered, so the total jumps whenever our Charge crosses a cluster — any peak here is a
fact about sixteen specific opponents, and R9 says it does not survive their next
recalibration. **Do not ship 0.65.**

Two things the table does say, and both are robust to the jaggedness: **1.15 is clearly bad**
in both windows, so nothing argues for charging more; and 1.00 is below several lower points
in both, so the level is more likely too high than too low.

**The open question, and the next measurement.** Is the over-charging *conditional* on
something we observe at decision time? `charge_factor` is already `clamp(0.85 - 0.45σ, 0.30,
0.80)`, so the model's own stated confidence is priced in — but that width is known to be
uninformative (median implied σ 0.375 against a real log error near 0.8, and the narrow third
scores *worse* than the wide third). If the unrecoverable Charges concentrate in an
observable bucket — a unit, a magnitude, a channel, a coverage band — then a conditional rule
exists and it is worth more than any multiplier. If they are scattered uniformly, this reduces
to H3 and only better evidence closes it.

Note the tension to respect: on *penalised* items our median is **0.74×** the true Fair Value,
i.e. too low, while on charged items `a/t` is 0.99, i.e. too high. **The estimator is
scattered, not biased**, which is precisely why a global multiplier cannot win and why 0.75
lands in a trough.

## H4 ❌ Coverage is **not** the lever, and my own case for it was arithmetic I got wrong

**A perfect coverage oracle is worth +10,557 over 30 Games**, inside the ±34,369 noise floor at
that sample size. Nothing about coverage can pay at today's constants. `coverage.py` stays
unwired, and that is now a decision rather than an omission.

**The parked detector does not reproduce out of sample.** Its advertised 61.8 % / 1.7 % / 0.122
was Games 1-14. Over all 30 settled Games, at the 2/3 threshold `src/pricing.py` actually uses:

| estimator | recall of worthless | false pos | Brier |
| --- | ---: | ---: | ---: |
| **Channel C (shipped)** | **69.6 %** | 9.8 % | **0.145** |
| `coverage.py` | 59.1 % | 7.1 % | 0.151 |
| mean of the two | 71.3 % | 10.7 % | 0.125 |
| min | 75.7 % | 16.1 % | 0.140 |
| max | 53.0 % | 0.9 % | 0.157 |

Channel C is better on recall *and* Brier. Where the two disagree, `coverage.py`'s unique flags
are right **7 of 21** — worse than a coin flip. In euros every variant lands within ±800 over
30 Games and **every one loses on Games 21-27**; `min`'s +341 is a single Game against five
losses. The blend with the best Brier has the worst euros.

### Where my reasoning failed, because the mistake is the reusable part

I measured that 24 falsely collapsed items carried **83,577 of penalties** and treated that as
the prize. It is not. **Un-collapsing those items recovers almost none of it**, because the
Limit that replaces the zero is still `min(0.45 x median, 708)` — which sits *below* the
Field's Charges on exactly those items:

- Game 10 item 5: Limit 0 → 708 against **61,302** of penalty. Recovers **282**.
- Game 30 item 5, the one I quoted at you: Limit 0 → **34**. Recovers **exactly nothing**.

Handing all 22 real-money collapsed items a *perfect* coverage probability costs **477 more**
than shipping. I had conflated "penalties paid on items with a false collapse" with "penalties
recoverable by fixing the collapse". They are different quantities and only the second is a
prize. **A cost attributed to a cause is not a cost the cause can return.**

The oracle's +10,557 comes from the *opposite* direction — declining to pay on worthless items
we call covered — and Channel C already catches 70 % of those.

**So the binding constraint on the Reviewer side is the Limit's level, not the coverage verdict**
— and `LIMIT_CEILING`'s own note records that every loosening measured so far loses more on
accepted Overcharges than it saves. Both halves are blocked, which leaves H3.

Timing, for the record, since it would otherwise look like the reason: `assess_coverage` fits
comfortably — Case 8's 39 Line Items in 8.0 s, slowest of thirty 13.1 s, concurrent with the
existing draws rather than added to them. It fits; it just is not worth the tokens.

**Operational trap for anyone re-running this:** `assess_coverage` degrades silently to 0.9 on a
failed chunk, which is right for a Submission and fatal for a measurement. A 16-way concurrent
dump was ~40 % rate-limited into files of pure 0.9 that graded exactly like a flat prior.
`scripts/coverage_dump.py` now refuses to write a degraded file. Keep that guard.

### Original entry, kept because its measurements are sound and its conclusion was not


**Graded head to head on 334 settled Line Items**, ground truth `t_lo == 0`, a verdict counted
as "kills the Limit" when `p_covered <= 2/3` (which is what `src/pricing.py` actually does):

| | recall of worthless | false positives | Brier |
| --- | ---: | ---: | ---: |
| **Channel C (live)** | 67.6 % (75/111) | **10.8 % (24/223)** | 0.155 |
| **`coverage.py` (parked)** | 61.8 % | **1.7 %** | **0.122** |
| a flat 0.9 | 0 % | 0 % | 0.276 |

Channel C catches slightly *more* worthless items and wrongly collapses **six times as many
covered ones**. Priced over every settled Game:

- **24 false collapses cost 83,577** in wrongful-rejection penalties.
- **36 missed worthless items cost 37,298** in payments.

**But the first number is one item.** Game 10 item 3 — coverage **0.22** on an item worth
**≥ 7,225** — carries **61,302** of the 83,577 by itself. Excluding it, false collapses cost
**22,275** against 37,298 for the misses, which points the *other* way. Anyone quoting the
83,577 without that caveat is quoting one Line Item.

What does tilt it back: **`LIMIT_CAP` now bounds the missed-worthless side.** Every payment on
an item we wrongly call covered is capped at 708, where Game 29's Limit reached 2,142. The
historical 37,298 could not recur at today's constants; the 22,275 of penalties can, because
a penalty is `1.5 x` the *opponent's* Charge and nothing we set bounds it.

So the direction is right and the magnitude is unsettled. **It is decided by the euro replay,
not by the confusion matrix** — that measurement is the open item.

Worst false collapses, as a list of things to check any new estimator against:

| Game | item | coverage said | truly worth | penalties |
| --- | --- | ---: | ---: | ---: |
| 10 | 3 | 0.22 | ≥ 7,225 | 61,302 |
| 25 | 13 | 0.00 | ≥ 1,097 | 7,405 |
| 19 | 7 | 0.22 | ≥ 472 | 5,117 |
| 24 | 5 | 0.15 | ≥ 240 | 3,027 |
| 26 | 6 | 0.08 | ≥ 181 | 2,114 |
| 30 | 5 | 0.08 | ≥ 100 | 1,464 |

### The rule is right; only its input is wrong

Two fixes were measured and both failed, which is what leaves the estimate as the only lever.
**Raising the Limit**: with the cap in place, 0.45 scores −5,289 on the held-out Games 28-30,
0.70 scores −9,034, 0.85 scores −9,618. **Moving the collapse threshold**: sweeping
`COVERAGE_FLOOR` from 0.0 to 0.8 moves the total by **77 euros** over 29 Games, because below
the floor the one-third quantile is already ~0 — a posterior with 60 % of its mass at zero
genuinely has a zero bottom third. And that is the payoff table being correct: accept iff
`P(a <= t) > 2/3`, so on an item believed 40 % covered, rejecting is right **for any** `a`.

### Original entry


76 of 192 settled Line Items are worth nothing, and `p_covered <= 2/3` is what collapses the
Limit. The parked detector (`src/evidence/policy/coverage.py`) measures **61.8%** recall at 1.7%
false positives, Brier 0.122 against 0.327 for a flat 0.9 — but it is unwired, because
swapping estimators needs a euro comparison, not a better confusion matrix.

- G23: coverage 0.98/0.93/0.25 against true `t` of 143–396+, i.e. right on two, wrong on the
  one that mattered.
- **Next evidence needed:** wire it behind a flag and replay it against Channel C's own
  coverage over every Game.

## H5 🔬 Charging above `t` is the largest single leak on the Issuer side

Games 21–25: **43,768 forfeited by charging above `t`**, 35,787 by charging below. Income at
`a = 0.7t` would have been 142,668 against 124,257 collected. Both Games 21 and 22 were paid
*Overcharges* — the field's Limits are loose, which R9 says will not survive a phase boundary.

## H6 💤 Two ensemble draws are worth their cost

Two framings beat one by +28,625 over Games 1–15 and 17–19, which is **at** the noise floor,
so this is not established. A third and fourth member gave no further gain (62,346 vs 80,237).
Kept for a reason independent of the euros: one framing failing costs a draw, not the channel.

The between-draw spread does **not** predict the error (corr +0.036, thirds ordered backwards),
so the quadrature width term in `blend` is a guard, not a signal. Do not present it as one.

## H7 ✅ Coverage leaks into the *Charge* through a zero price band, and Price Memory is thrown away with it

**Asked as "the penalties are coverage's fault". Coverage is not the leak; this is.**

Three measurements say the coverage *estimator* is close to its ceiling, so the hypothesis as
posed is falsified:

- `price_item` never reads `coverage_probability` for the Charge — only for the Limit
  (`src/pricing.py`). Coverage cannot move Issuer income through that path at all.
- `scripts/coverage_bakeoff.py euros`: an **oracle** coverage read is worth **+10,557 over 30
  Games** against a ±34,369 noise floor (+1,187 on held-out G28–30). Every practical
  alternative — `coverage.py`, mean, min, max, flat 0.9 — *loses* against shipped Channel C.
- The calls are directionally sound: 71% of items called `<0.33` really are worth zero,
  against 25% of items called `>0.90`.

**But the model zeroes the price band on items it judges uncovered.** All nine zero-band Line
Items in the logged Games came back with coverage ≤ 0.30, and `prompts.py` hands the model a
JSON example with `price_low/median/high = 0.0`. `blend.combine` then discarded the Price
Memory anchor whenever `model.price_median <= 0` — **4 of the 9**, including both items that
were provably worth money — so the item fell through `Evidence.with_defaults` onto
`FALLBACK_MEDIAN = 60` and was Charged a flat **39.62 whatever it was worth**.

- **G31 item 17** "Delivery and assembly of the replacement table": exact memory hit at
  **300** (from Game 5), true `t ≥ 315`, Charged 39.62. −2,842.
- **G29 item 4** "Vehicle costs": exact memory hit at **85.98** on 11 observations across six
  Games, true `t ∈ [80, 86)`, Charged 39.62.

This contradicts the stated design in two places: `price_item`'s docstring ("The Charge
assumes the item is covered. That is deliberate and it is free") and
`channels.worthless_evidence` ("The band is kept plausible rather than zero"). Channel A got
it right; Channel C's band was allowed to overrule it.

**Fix shipped:** `combine` keeps the model's coverage verdict — so the Limit still collapses
exactly as before — and takes the anchor's band. Replayed over every logged Game: **+3,190,
positive in all four Games it touches (27, 28, 29, 31) and neutral in the rest.** No Game is
harmed, no constant moved, no lookahead (every anchor predates the Game it is applied to).
Small in absolute terms, but it is a bug rather than a knob, and it is a lower bound: it fires
only where Price Memory already has an anchor, which is 22% of items and growing.

**Next evidence needed:** the other five zero-band items had no anchor. Stopping the band from
going to zero at all is a `prompts.py` change and must be measured on cached Cases against the
26,622 floor before it ships — do not bundle it with this.

## H8 ❌ The decision rules have headroom left in them — swept at Game 32, and they do not

Asked as "are there improvements to Strategy 2 now". Four candidates, all measured against the
replay harness over every settled Game on reconstructed evidence. **All four are negatives**,
and they are recorded because each one looks obviously right until it is measured.

**The Charge factor is already at its empirical optimum.** `charge_factor` maximises
`k · P(t ≥ k·t̂)` under a lognormal, and `pricing.py` says our error is not lognormal
("5–6 sigma in log space"). Measuring the survival function directly on 217 real-money items,
**censoring handled explicitly** — an item with `t_hi = inf` is `t ≥ t_lo`, and those are the
expensive ones — gives an empirical argmax of **k = 0.70** against the shipped 0.69. The
empirical curve tracks lognormal(0.37) to within 0.02 over `k = 0.6…1.0`. Nothing to win.

**And the "+0.45 median log error" in the watcher digest is a censoring artefact.** Median
`t/t̂` is 0.89 on two-sided brackets, 1.11 on one-sided ones, and **0.99 over both** — a
two-sided bracket only exists where somebody rightfully rejected, which selects cheap items.
The estimator is roughly median-unbiased, exactly as `pricing.py` already claimed. Do not fit
a level correction to the digest's number.

**`LIMIT_CEILING` should not move — and this is the one that nearly shipped.** Loosening to
0.70 is worth +17,835 over 32 Games and is positive in **32 of 32 leave-one-out folds** for
every candidate 0.55–0.85. It is still wrong: leave-one-out cannot see a regime change,
because 31 training Games stay in every fold. Split on *time* instead — train on 1–25, score
on 26+ — and 0.70 scores **−2,274**. +17,218 of the +17,835 is Games 1–19, and every value
above 0.45 loses on Games 28–32. Full table now recorded on the constant itself.

**`FALLBACK_MEDIAN` carries no signal.** The fallback fires on 40 of 364 items (11%), 4 of
which were worth money. Sweeping 30→250 gives −218, −1,089, 0, +2,060, +952, −198, +529: the
forbidden jagged level surface, non-monotone, spanning 3k on 197k.

**A unit-rate prior has no sample.** "What does one hour settle at, pooled over every Game"
would reach every metered item rather than Price Memory's 22% of repeated wordings. Of 364
Line Items, 53 print a unit and **5 are metered, 2 of them gradeable**. There is nothing to
fit. (Loosening Price Memory's *matching* is separately falsified in `price_memory.py`:
sigma 0.43 → 0.72 at Jaccard 0.7, 1.19 at 0.25.)

**So the rules are at their measured optimum and the remaining gap is estimate quality.** That
is H3, unchanged and now better bounded: today's pricing replayed over all 32 Games nets
**+197,716** against an oracle **+966,294**, and the best constant available anywhere in this
sweep moves it by ~18k. The other ~750k is the estimate. Only the evidence layer reaches it.

**Tooling defect found and fixed en route:** `charge_buckets.ALL_GAMES` was the literal
`range(1, 28)` and stayed there while Games 28–32 settled, so every sweep run through that
module was scoring five Games short — the five that matter most, since a Field measurement
does not survive a phase boundary. It now derives from `usable_games`.

## H9 ❌ Scale `t_hat` itself (uniform, threshold-conditional, power-law) so `a` and `b` move together

Full report: [`scale-estimate.md`](scale-estimate.md). Different in kind from H2 and H8: those
moved a multiplier on top of a fixed `t_hat`; this scales `price_median` and reprices through
the real `price_item`, so the Charge *and* the Limit move together — asserted directly in the
harness, not assumed.

**Reproduces the motivating evidence and still loses.** The 6.01×/1.17× magnitude bias quoted
as support is `level_fit.py`'s own *by-true-`t`* table — the biased conditioning direction its
own docstring already flags. Bucketed by `t_hat` itself (the only actionable direction), the
same sample runs 0.46× under 50 EUR and **1.95× over 1,000 — already too high, not too low**,
which is exactly why the loss shows up where it does. The 73%-censored-below-`t_lo` proof
(`upward-charge.md`) is real but does not say *which* items — nothing in the decision-time
evidence (`t_hat`, `sigma`, `coverage_probability`, `channels`) separates a genuinely
underpriced censored item from a catastrophically overpriced one in the same magnitude band.

- Uniform λ 1.1–1.3: inside the ±27,352 (n=19) / ±24,302 (n=15) noise floor on both windows,
  and λ=1.1's in-sample +9,572 flips sign odd (−13,786) vs even (+23,359). λ ≥ 1.5: clear,
  fold-robust losses (−46,063 to −96,739).
- `threshold>500` (only items above 500 scaled): negative at every λ tested, every window —
  direct confirmation `t_hat` is not uniformly low there.
- `threshold>1000, λ=2.0`: the only configuration that clears the noise floor on 3 of 4 folds
  (+86,773 ALL19, +80,560 LAST15) — **entirely two Line Items in two Games** (g44 stolen
  watch, g41 robbery compensation, both censored/unbounded, estimate 0.73×/0.50× the proven
  floor). Removing exactly those two Games: −52,743 (λ=2.0), −58,793 (λ=1.5). The weak EARLY
  fold (+5,172, inside noise) was the tell before the by-Game breakdown confirmed why.
- Power-law (γ > 1, low anchor, the *stretch* direction): catastrophic and monotone in γ
  (−6,548 at γ=1.1 to −444,174 at γ=1.5), replicating — in the opposite exponent direction —
  H2's "the whole `exp(c0)·t̂^c1` family's argmax is `c1 = 1`" finding, now on the current
  engine and window.

**No `src/` change proposed.** Third independent confirmation tonight (after H2's fitted
recalibration and `upward-charge.md`'s conditional Charge multiplier) that no deterministic
function of the `t_hat` we already have closes the gap — it belongs to the evidence layer.

---

## Standing measurements worth not re-deriving

| quantity | value |
| --- | --- |
| Fair Value distribution (148 bounded items) | p25 19, median ~59, p75 127, p90 365, max 7,225 |
| items worth exactly nothing | 76 of 192 (**0%–67% per Case** — no safe prior) |
| noise floor, 18 Games, identical prompt | **26,622** |
| dash quantity ⇒ `t = 0` | 20 of 20, against a 33% base rate |
| Price Memory | 22% recall, leave-one-out log error 0.43 |
| our accept rate vs the leaders | 6–19% vs 63–65% — and copying theirs imports 60–75k of loss |
| fair share of Charges we face | 67.2% pooled, against a 66.7% break-even |
