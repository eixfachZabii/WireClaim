# Hypothesis ledger

One Game is far inside the **26,622** noise floor measured over 18 Games, so no single Game
can justify a constant change. This file is how evidence accumulates instead of being
re-derived from whichever Game settled most recently.

**After every Game:** run `pixi run learn`, then add a line to the relevant hypothesis saying
whether that Game supported it, contradicted it, or said nothing — with euros. Promote a
hypothesis to a change only when the replay over **all** settled Games agrees, or it clears
the noise floor on a held-out split.

Statuses: 🔬 open · ✅ confirmed and shipped · ❌ falsified · ⚠️ partly falsified, read the
amendment first · 💤 dormant (no evidence either way)

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

**Two thirds of that question are now answered (H4, Game 55).** A better coverage read is worth
**+41,076** over 55 Games — 33 Games won to 3 lost, +21,416 with its two best Games stripped,
positive on both held-out windows. A *second opinion* is not the way to get it: where the two
independent Policy readings disagree, Channel C is right 19 of 54 and `coverage.py` 12 of 39,
both worse than a coin flip. The prize is real and it needs evidence Channel C does not have —
the discarded verbatim `clause` is the nearest untested candidate. See H4.

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

## H4 ⚠️ Coverage — half falsified at Game 55: the lever is real, `coverage.py` is still not it

**Read this section before the one below it.** H4 was decided at Game 30 and its central
number was measured through a pricing engine we stopped running seven Games later. Re-run
over 55 Games with the engine we actually ship, **a perfect coverage oracle is worth
+41,076**, not the +10,557 recorded below — and unlike that figure it is robust:

| window | n | oracle | noise floor |
| --- | ---: | ---: | ---: |
| all | 55 | **+41,076** | ±46,536 |
| G31–45, never seen by the original verdict | 15 | **+5,893** | ±24,302 |
| G46–55, held out | 10 | **+4,607** | ±19,843 |

It wins **33 Games and loses 3**, and stripping its two best Games still leaves **+21,416**.
The "inside the noise floor" objection that closed H4 does not survive that split — and that
floor is calibrated on unpaired Game-to-Game variation, while this is a paired counterfactual
on identical Games against an identical Field.

### What was actually wrong: `memory_backed` was never passed

H4's whole argument was one sentence — *un-collapsing a Limit recovers nothing, because the
Limit that replaces the zero is still `min(0.45 × median, 708)`, which sits below the Field's
Charges on exactly those items.* That was true when it was written and stopped being true
eighty-two minutes later:

| when | Game | what landed |
| --- | ---: | --- |
| 22-08 21:26 `b21f3a7` | **30** | H4's verdict recorded; dump window ends at 30 |
| 22-08 22:48 `be2361f` | **37** | `LIMIT_CEILING_MEMORY`: 0.45 → **0.75** on memory-backed items |
| 22-08 23:36 `6589feb` | **40** | `LIMIT_CAP` (708) **removed** from memory-backed items |

The original entry's own worked example is the proof. It reported *Game 10: Limit 0 → 708
against 61,302 of penalty, recovers 282.* Re-run through today's engine, that item — the
stolen watch, `t ≥ 7,225` — goes **Limit 0 → 5,228 and recovers 10,872**, because 708 was
`LIMIT_CAP` and the cap is gone on memory-backed items. Same Case, same Field, same coverage
verdict; a 38× difference in what the collapse costs.

`coverage_bakeoff.submission()` called `price_item(evidence, confirmed_uncovered=...)` and
never passed `memory_backed` — its `Row` did not even carry `channels` to pass. **51 % of
graded rows are memory-backed.** On those rows the thing that made un-collapsing worthless is
gone, so every euro in the table was computed against an engine that no longer exists. Same
30 Games, same rows, same estimators, the flag being the only difference:

| estimator | `memory_backed` omitted | as we actually price |
| --- | ---: | ---: |
| channel C (shipped) | +0 | +0 |
| `coverage.py` | +50 | +14,844 |
| oracle | +10,849 | **+30,575** |

Fixed at `scripts/coverage_bakeoff.py` (`Row.channels`, `Row.memory_backed`, both row
builders, `submission`). Two adjacent traps found with it and also fixed: `--games` defaulted
to the literal `"1-30"` and silently held every table at 30 Games after `ALL_GAMES` grew, and
the euro table's window labels were hardcoded strings that survived the windows moving.

**The reusable mistake is not the flag, it is the shelf life.** A euro measurement is taken
against a specific pricing function. Change a constant in that function and every recorded
verdict downstream of it is stale, silently, with no test to fail. `submission` now prices
through exactly the flags `strategy.build_proposal` passes, so it moves when the engine moves.

### `coverage.py` still does not capture it — and this half is now better evidenced

The parked parallel Policy reader was the obvious candidate for the reopened prize. It is not:

| estimator | all 55 | ex-best-2 | won/lost | G31–45 | G46–55 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `coverage.py` | +13,065 | **−4,754** | 17/18 | −1,473 | −306 |
| `max(C, coverage.py)` | +11,643 | −240 | 18/8 | +696 | +103 |
| `mean` | +945 | −3,059 | 14/9 | −2,220 | +44 |
| `min` | +1,422 | −6,535 | 8/15 | −2,169 | −409 |
| `flat 0.9` | −5,433 | −17,157 | 13/27 | −5,683 | −5,839 |
| **oracle** | **+41,076** | **+21,416** | **33/3** | **+5,893** | **+4,607** |

`coverage.py`'s entire total is **one Game** (G10, +10,873); it loses more Games than it wins
and is negative on both windows it had never seen. `max` is the only variant that holds out at
all, and it holds out at +696 and +103 — a rounding error on a 334,440 baseline.

The confusion matrix says why, and it is the cleanest result here. At the 2/3 threshold that
actually zeroes the Limit, over 626 Line Items of which 201 are truly worthless:

| cell | n | correct |
| --- | ---: | ---: |
| both readings flag | 136 | 130 (**96 %**) |
| only Channel C flags | 54 | 19 (**35 %**) |
| only `coverage.py` flags | 39 | 12 (**31 %**) |
| neither flags | 397 | 357 (**90 %**) |

Where the two readings agree they are 90–96 % right; where they disagree **both are worse than
a coin flip**. A second independent read of the same Policy produces disagreement, not
accuracy, so no blend of the two can reach the oracle's +41,076. `flat 0.9` at −5,433 rules out
the opposite reading: Channel C's verdict is doing real work, it is just not doing enough.

**Status.** "Coverage is not the lever" — **falsified**. "`coverage.py` is not the tool" —
**confirmed, and on a wider sample than the original**. The +41,076 belongs to H3: it needs
evidence Channel C does not currently have, not a second opinion on the evidence it has.

**The nearest untested candidate.** Strategy 2 asks the model for `clause` — "the Policy
sentence that decides coverage, quoted verbatim" — and `model.parse_items` discards the field
without reading it. Graded against `is_policy_quote` over the 149 clauses in the logged raw
replies (G48–55): **91 are verbatim in the Policy, 58 are not**, and only 19 carry exclusion
language at all, because the model quotes the *indemnifying* clause by default. So there is a
free per-item confidence signal on the coverage verdict, already generated, already logged,
never parsed — and it is untested in euros. Ask for `exclusion_quote` separately before
concluding anything about the gate's recall.

### Original entry (Game 30), superseded above and kept for its method

Its measurements are sound *for the engine of the time* and its reasoning on the
false-collapse conflation is still the reusable part. Its euro verdict is not.


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

## H10 ❌ "Combined position" wording flags the big items that are worth nothing — real signal, no money

**Game 56 raised it.** Its policy names the device explicitly: a *combined position* is
"a single line of an invoice that covers more than one operation, more than one kind of
material, or more than one part of the insured property, and that does not state separately
what falls to each" (1.3), and 7.1.10 declines the whole line if any element fails —
"The indemnifiable elements are not extracted from it and are not estimated, because the
position does not state what falls to each." We priced Case 56's items 2–4 to zero correctly
on exactly this reading.

**The observable**, computable at submission time from the wording alone: the Line Item name
matches `flat rate` or `incl.|including|combined|together with`.

**It separates, and significantly — but only inside the big band.** Over Games 26–53,
bucketed on our own `t_hat` (never on the answer):

| band | signature | n | worth nothing (`t_hi < 100`) | distinct Games |
| --- | --- | ---: | ---: | ---: |
| `t_hat >= 1k` | yes | 9 | 5 (56%) | 6 |
| `t_hat >= 1k` | no | 16 | **0 (0%)** | 13 |
| `t_hat 100–1k` | yes | 20 | 3 (15%) | 13 |
| `t_hat 100–1k` | no | 149 | 36 (24%) | 22 |

Fisher one-sided **p = 0.0024** on the big band, carried by 6 distinct Games, and it fires on
**none** of the four too-low items that hold the 242,027 of penalty. So it is not a disguised
restatement of H9's two-item overfit.

**And it cannot pay, because it is a strict subset of something already measured.**
`big_item_coverage.py`'s `+oracle` arm replaces coverage with *the truth* on every
`t_hat >= BIG_ITEM_THRESHOLD` item — the perfect version of this rule. Re-run at Game 56:

```
637 Line Items over 56 Games; 50 with t_hat >= 1,000
noise floor over 56 Games: +/-46,957
+oracle coverage         +23,021   (odd +9,473, even +13,548, <=40 +20,906, >40 +2,115)
```

**+23,021 against a ±46,957 floor.** Perfect coverage on big items is inside the noise floor,
so an imperfect proxy for it — 5 right and 4 wrong out of 9 flagged — has a ceiling strictly
below a number that already does not clear. Confirmed independently by the Issuer side: the
total penalty on all five flagged worth-nothing items is **exactly 0**, which is R6c working
as designed. Being high on a worthless item is free.

The only live sliver is the Reviewer side — we carried a Limit of 2,141.59 on G29 i2
(`t_hi = 57`) and `LIMIT_CAP` 708 twice in G33 on items worth ≤50 — but `+cap off (big)` is
**−62,278**, negative on all four folds, so that door is already shut from the other side.

**No `src/` change proposed.** The value of this entry is the inversion: it is the fourth
independent confirmation that the *too-high* half of the big-item bucket is capped at noise.
Whatever closes the gap is on the too-low, censored, magnitude side. Stop looking here.

---

## H11 ✅ Price Memory keys on wording; the Policy text is the key it was missing

**The failure, exactly.** One entry of 239 pools observations from two different Policies:

```
'compensation for robbery damage'  ->  games [27, 41]   values [3011.08, 11130.90]
pooled geometric mean the store returns: 5,789
   vs 3,011 (G27) = 1.92x too HIGH      vs 11,131 (G41) = 0.52x too LOW
```

Byte-identical wording, a 3.70x spread, and the pooled anchor is wrong in **both** directions.
At Game 41 the store held only G27's 3,011, and that is the anchor that pulled a correct read
down to 5,524 — **81,673 of penalty on one Line Item.**

**Why the wording cannot separate them, and what can.** Cases 10, 41, 44 and 53 share
`policy.txt` byte for byte (`md5 4fa9117f`); Case 27 is a different document (`fa547b5e`).
That hash partitions exactly along Part 11.1: the shared Policy says the affected items belong
"partly to classes for which sub-limits are agreed ... **and partly to the general class under
4.2.1**", and 11.2 pays a class carrying no sub-limit **in full**; Case 27's says only
"classes of property for which sub-limits are agreed". The settlements follow with no overlap —
3,000 (bounded, at the cap) against 7,225 / 8,626 / 9,361 / 11,131 (all unbounded).

**Measured, `scripts/experiments/policy_hash_memory.py`, leave-one-out over all 57 Cases:**

| arm | n | recall | sigma | mean abs log | bias |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline (wording only) | 309 | 69% | 0.453 | 0.274 | +0.049 |
| same-hash only | 196 | 44% | **0.389** | 0.234 | **+0.009** |
| **prefer-hash** | 309 | **69%** | **0.425** | 0.252 | +0.038 |

`prefer-hash` — same-Policy observations when they hit, the full store when they miss — is
better than baseline on sigma in **all four folds at identical recall**: ODD 0.530→0.521,
EVEN 0.361→0.300, EARLY 0.452→0.435, LATE 0.455→**0.416**. The gain is largest LATE because
the store accrues same-hash priors as it grows, so it improves over the remaining Games.
`same-hash` alone nearly eliminates the channel's upward bias (+0.049 → +0.009).

**Scope, honestly.** This is leave-one-out sigma on the memory channel, not net euros. By the
sigma-sensitivity table (~2,780 per 0.01) 0.028 is worth roughly 8k, inside the noise floor
**as a total**. Its value is that it removes a catastrophic mechanism rather than moving a
level. **15 Policy hashes are shared across 43 of 57 Cases**, and the invoice sweep found
independently that **76% of all identified damage sits in Games whose Policy text had already
appeared in an earlier settled Case** — including Game 44's watch, estimated at 6,840 when
Case 10, same hash and settled 34 Games earlier, had already proven a floor of **7,225** on
the identically-named line.

**Proposed `src/` change:** prefer same-`md5(policy.txt)` observations in
`src/evidence/memory.py`, falling back to the pooled store. One change, validated 4/4 folds,
no recall cost. Not yet priced through `replay_payoffs.py`.

---

## H12 ❌ The three-regime model — Games 44–81 are **not** "mostly dark"

`CLAUDE.md` rule 9 states the tournament has three regimes and that Games ~44–81 the Field is
"mostly dark", which would make an honest harvest the only play and overcharging worthless
against `b = 0`. **Measured, and it is inverted.**

Dark = a reviewer whose total accepted **amount** is zero for the whole Game. (Counting
*accepts* instead is wrong: a team with `b = 0` still accepts every `a = 0` Charge, so a
count-based filter reports zero dark teams everywhere. That mistake was made and caught here.)

| Game | dark of 17 | | Game | dark of 17 |
| ---: | ---: | --- | ---: | ---: |
| **28** | **13** | | 50 | 2 |
| **36** | **15** | | 53 | 6 |
| 41 | 8 | | 54 | 2 |
| 46 | 2 | | 55 | 4 |
| 47–50 | 2–3 | | 56, 57 | 3, 3 |

The two genuinely dark Games in the record are **28 and 36 — both inside the window rule 9
calls "awake"** — and the 44+ window the rule calls "mostly dark" runs at a median of **3 of
17**. Reproduced independently from the cached Transactions of all 17 teams, row counts
verified against `17 x 16 x 2 x n_line_items` for every Game.

**The action does not change, but the reason does.** An acceptance curve measured over the last
five Games shows `p(accept)` falling smoothly and significantly across `a/t` 0.5 → 1.5
(non-overlapping CIs in every window), which is what correctly-pricing awake reviewers produce —
not an asleep field. Above 1.5x the buckets hold 8–149 unique Charges and are inflated by
**survivorship bias**: a Charge rejected by all 16 reviewers is unrecoverable and drops out of
every bucket rather than counting as a zero. Correcting for the real-money share pulls
`p(>2.5x)` from 17.2% to 13.8% (last five), 21.9% to 13.7% (G26–40), 25.8% to 19.2% (G41–50).

**Verdict: do not raise the Charge.** The Field's own median `a/t` is 0.68 / 0.74 / 0.71 across
the three windows, matching the standing ~0.73 measurement, and our shipped `0.7 * t_hat` sits
inside the only region of this data that is trustworthy. Rule 9's *conclusion* for this stretch
survives; its *premise* does not, and a wrong reason in a shared doc propagates.

---

## H13 ❌ `LIMIT_CEILING = 0.45` is fitted to the wrong estimator — no, it still holds

**Game 59 raised it, and it looked damning.** Four expensive, correctly-priced Line Items drew
45,418 of lawyer waste with **zero** rightful rejections between them. Item 2 held a Limit of
701.77 — exactly `0.45 x 1559.49`, the ceiling binding — against a true `t >= 1451`, and
wrongly rejected **12 of 16** fair Charges. The Game's Limit ledger was **0.2 : 1**
saved-to-wasted against a 2.2–2.6 : 1 record average.

The suspicion was reasonable: 0.45 was fitted before the Price Memory basis fix (5f6dcc3),
the Policy key (d0ef2c6) and the parser reconciliation (c6a079f, which changed nine
quantities and removed two invented Line Items). A ceiling swept on a biased estimator
absorbs that bias.

**Measured — `scripts/experiments/limit_ceiling_sweep.py`, 60 Games, noise floor ±48,605:**

| ceiling | all | odd | even | ≤40 | >40 | last8 | folds+ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.40 | −1,080 | −481 | −599 | −69 | −1,011 | −451 | 0/4 |
| **0.45 (shipped)** | — | — | — | — | — | — | — |
| 0.50 | +902 | +348 | +553 | +1,939 | **−1,038** | −228 | 3/4 |
| 0.60 | +3,803 | −2,403 | +6,207 | +5,737 | **−1,934** | +931 | 2/4 |
| 0.80 | +4,593 | −2,119 | +6,712 | +4,759 | **−166** | +1,937 | 2/4 |

**Nothing passes four folds, and every value above 0.45 is negative on `>40` — the recent
half, which is exactly the window the suspicion was about.** The largest total gain, +4,593,
is an order of magnitude inside the noise floor. On `last8` (Games 53–60, the window
containing Game 59 itself) the best available is +1,937 against the 45,418 that prompted the
question.

The engine docstring states its own falsification condition — "three or four consecutive
settled Games where 0.60 beats 0.45 on that window alone". It is **not met**: 0.60 scores
−1,934 on `>40` and +931 on `last8`.

Loosening the Price Memory ceiling was tested in the same sweep and is worse: 0.75 → 0.60
costs **−28,854**, and 0.90 reaches +3,538 on 2/4 folds.

**Game 59 was a bad draw, not a mis-set constant.** A Case whose expensive items are all
covered *and* correctly priced is the exact shape this ceiling is worst at, and such Cases are
rare enough that paying for them beats loosening for everyone. No `src/` change.

Worth recording separately from the verdict: the baseline replay is **+243,635 over Games
≤40 and only +15,563 over the twenty Games after**, with `last8` at **−6,135**. Whatever is
draining the recent window, this constant is not it.

---

## H14 ✅ Above `t` the income is not nothing — `BIG_ITEM_CHARGE_SCALE` was betting that it is

**Shipped: `1.25 → 1.0` at Game 63.** The largest single change of the night, and the reason it
was found is that the payoff table has a clause everyone here had underweighted.

The issuer is paid on a **wrongful rejection too**. So for `a <= t` the income is `a` from
*every* opponent, whatever their Limits — a Reviewer who rejects a fair Charge still owes it,
plus the lawyer. Above `t` a rejection is rightful and pays nothing, so the income is `a`
times only the handful who accept. Measured on Game 62: **16 payers versus 3.** Crossing `t`
costs about 5× the income, and raising the Charge is precisely the operation that moves
in-band items across.

The constant's own justification was the opposite: *"on an item already above `t` the income
is ~0 whatever we Charge, so raising it costs nothing."* It even conceded the exposure — *"the
in-band items are the only real risk, since a scale can push them across the cliff. At 1.25
most stay in band"* — and that is the half that was wrong.

**Game 62, Line Item 1, "Renew boiler system including flue gas system", `t ∈ [8505, 10350)`:**

| team | Charge | payers | income on that one item |
| --- | ---: | ---: | ---: |
| `error404 ai` | 8,504.71 | **16 of 16** | **136,075** — 87% of their whole Game |
| us | 10,349.89 | 3 of 16 | 31,050 |

The unscaled Charge was `charge_factor(σ) × 11,736.69 = 8,280` — fair. The 1.25 lifted it one
step past the ceiling. Their net that Game was +101,531; ours was −17,276.

**Measured — `scripts/experiments/big_charge_floor_sweep.py`, 63 Games, noise floor ±49,805
(±35,496 within a half-fold), delta against the shipped 1.25:**

| rule | all | odd | even | ≤40 | >40 | crossings |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| scale 0.90 | +25,869 | −2,168 | +28,037 | +1,821 | +24,049 | 11→fair, 0→over |
| **scale 1.00 (shipped)** | **+79,240** | −6,318 | +85,559 | +5,490 | +73,750 | **9→fair, 0→over** |
| scale 1.10 | +72,900 | −19,201 | +92,100 | −5,355 | +78,255 | 4→fair, 0→over |
| scale 1.25 (was) | — | — | — | — | — | — |
| floor 0.20 | +90,273 | +3,314 | +86,959 | +15,123 | +75,151 | 9→fair, 1→over |
| floor 0.30 | +109,198 | +24,527 | +84,671 | +28,635 | +80,563 | 9→fair, 1→over |
| floor 0.35 | +85,594 | +22,037 | +63,557 | +4,804 | +80,790 | 9→fair, 1→over |
| floor 0.40 | +103,492 | +41,284 | +62,208 | +8,418 | +95,074 | 9→fair, 1→over |
| scale+floor 0.30 | +20,215 | +19,048 | +1,167 | +19,048 | +1,167 | 0→fair, 1→over |

+79,240 clears the floor, and the mechanism is one-directional: **nine Line Items move from
Overcharge to fair, none the other way.** The odd fold is −6,318 against ±35,496 — 18% of its
own noise floor, which is flat, not negative. The fit that chose 1.25 was +36,525 at n=26
against ±31,996; it only just passed then and it reverses on 2.4× the sample.

**The documented falsifier was not what tripped.** It said to revert if "proven too high" fell
near 50%. Re-measured over Games 26–63 the tail is still **67% proven too high, 15% too low,
n=33, median `t_hat/t` 3.03** — the shape it was fitted on. The prose above the number was
wrong, not the direction balance. Worth remembering: a constant can be right about its data
and wrong about its mechanism.

**Read `big_charge_sweep.py`'s `floor` family carefully before quoting it.** Its `price()`
never applies `BIG_ITEM_CHARGE_SCALE` in that branch, so `floor f` means "*drop the 1.25* and
add a floor at `f × price_high`", and `floor 0.0` is exactly `scale 1.0`. Its headline
+109,198 is therefore mostly the multiplier, not the floor: keeping the 1.25 *and* adding the
floor (`scale+floor 0.30`) collapses to +20,215.

### Two negatives from the same session, recorded so they are not re-argued

**❌ The infinite Cap in `replay_payoffs.py` is not biasing our Charge constants.** Its
docstring justifies `c = ∞` on "zero cap_conflicts in Games 1–14", which expired —
`rivals.py` pins `c = max(4t, 2000)`, and Game 62 item 7 shows it binding (we Charged
8,617.22, the one acceptor paid exactly 4,840.00 = `4t`, so `t = 1,210` against our `t_hat` of
9,500). It looked like every Charge-raising rule was being flattered. It is not:
`scripts/experiments/big_charge_sweep_capped.py` scores all 12 rules × 5 folds with the Cap
enforced and the tables are **identical to the cent**. The Cap can only bind on an *accepted*
Overcharge, and the reconstructed Field's Limits essentially never accept one that large.
Only one (Game, Line Item) in the whole record has our recovered Charge above `max(4t, 2000)`.

**❌ Codacabana's ratios are not copyable — the gap to them is estimate quality.** They lead
the field on the recent window at **+9,848/Game (G42–61) against our +4,597**, and
`current_winners_study.py --decompose` (reconciles to the identity to the cent) splits the
125,881 gap over G42–62 into: **+170,140 more fair income** for them, and an accept-side
policy worth **−4,672** net (they pay 177,400 more on accepts to avoid 172,728 of lawyer —
i.e. nothing, deep inside the noise floor). Their fair capture is 60.4% of the honest ceiling
against our 47.6%. But their `a/t` median is *higher* than ours (1.06 vs 0.98) with a tighter
p25 (0.83 vs 0.72), which is a statement about their **estimate**, not their multiplier —
applying their ratios to our own `t_hat` loses **−279,916 (a only) to −380,338 (a and b)**
over 63 Games. R5c again: a rival's ratio measured against `t` is not a rule you can apply to
`t_hat`.

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

---

## H15 ❌ The lawyer bill means the Limit is too low — no, it is the premium on a policy that pays 4×

Raised at Game 68 on a penalty line of −39,258. Two corrections, then the measurement.

**"Penalties" is not "waste."** Rejecting a fair Charge costs `1.5a` where accepting costs `a`, so
two thirds of any penalty figure is money owed either way. Game 68's actual waste was **13,086**,
which the digest prints beside it. And the other side of the ledger, since the Limit bet shipped
at Game 66: **saved by rightly rejecting 80,986 against 19,813 wasted — 4.1 : 1.** Removing the
waste means accepting the fraudulent claims that produced the 80,986.

**The derived quantile is right.** `LIMIT_QUANTILE = 1/3` follows from the payoff table — accepting
beats rejecting exactly when `P(fair) > 2/3` — but that derivation assumes a calibrated posterior,
and ours is not (implied sigma 0.375 against a realised error near 1.0). So it was worth sweeping,
and it had not been swept tonight. Over 67 Games:

| q | accept if | all | odd | even | ≤45 | >45 | last10 | folds+ |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.200 | P(fair)>0.80 | −27,424 | −9,410 | −18,015 | −23,700 | −3,724 | +2,791 | 0/4 |
| 0.267 | P(fair)>0.73 | −16,328 | −4,872 | −11,456 | −13,350 | −2,979 | +485 | 0/4 |
| **0.333 (shipped)** | P(fair)>0.67 | — | — | — | — | — | — | — |
| 0.400 | P(fair)>0.60 | +3,753 | +1,619 | +2,134 | +2,177 | +1,576 | +765 | 4/4 |
| 0.450 | P(fair)>0.55 | −1,489 | −1,262 | −226 | −764 | −725 | −930 | 0/4 |
| 0.600 | P(fair)>0.40 | −6,425 | +101 | −6,526 | −4,369 | −2,056 | +733 | 1/4 |

q = 0.40 is the argmax and clears four folds, but at **+3,753 it is 7 % of the ±50,977 floor** —
not a result. Everything looser loses. With the global `b` multiplier (H-none: ×1.18 and ×1.50 both
sign-flipping noise) and the ceiling-plus-clamp loosening that *was* shipped, the Limit has now been
attacked from three independent directions and the derived value survives all three. **Stop
proposing it.**

**Game 68's loss was the opposite of a Limit problem.** Income +32,779 against a ceiling of
+100,970, with `charge-far-below-t` at −18,910: item 1 Charged 551 against `t ≥ 1,555`, item 2 223
against `t ≥ 499`, item 4 541 against `t ≥ 2,234` — roughly 47,000 of income forfeited from all
sixteen opponents because `t_hat` was 2–2.5× too *low* on stolen-goods items. Zero of the eleven Line
Items were memory-backed: theft and contents vocabulary that the store, built mostly on
water-damage repair Cases, has never seen.

One caution recorded because it nearly became a false finding. Bucketing the export's
`penalty_on_this_item` by proven direction appears to show being too low costing 10× being too high.
That is **definitional, not empirical**: a low `t_hat` lowers `b` and produces lawyer penalties,
which is what that column measures, while a high `t_hat` produces accept-payments, which land in a
different column. The wording split that prompted it (multi-item aggregate versus single named or
listed article, from Game 68's "several unscheduled" at `t ≥ 2,234` against "one high-value ring
listed" at `t ∈ [2421, 2850)`) reaches **n = 7 and n = 3**. Not testable. §4a stays open.

---

## H16 ❌ "Operation Nightfall" — there is no AFK team to exploit, and a dark Reviewer pays us *less*

Proposed at Game 68: scan the last ten Games for teams that are offline, then run a strategy
that exploits them for quick wins. **Measured on Games 58–68, and it fails on three independent
grounds — the first of which is structural, not economic.**

**1. There is no targeting surface.** The submission payload is
`{"index", "charge_price", "acceptance_limit"}` (`src/api/tournament.py:177`). One Charge and one
Limit per Line Item, broadcast to all sixteen opponents. **The API has no per-team field**, so no
strategy can price one opponent differently from another. "Exploit the AFK teams" can only mean
"move the number everyone sees", which is a global recalibration and is what H12/H14 already
measured.

**2. A dark Reviewer is a *worse* customer than an awake one, not a better one.** The clause that
decides this is `replay_payoffs.py:20` — on a wrongful rejection the reviewer pays `1.5a` but the
**issuer receives `a`**; the `0.5a` is burned by the lawyer and never reaches us. So our income on
a fair Charge is `a` whether they accept or reject, and darkness cannot raise it. It can only
remove the Overcharge-acceptance term. Measured over G58–68, every row where we were the Issuer:

| reviewer | state | income to us | €/row |
| --- | --- | ---: | ---: |
| makalu | DARK | 12,436 | 124.4 |
| OPUSMOPUS | DARK | 12,436 | 124.4 |
| Alpha | reviewer-dark | 12,436 | 124.4 |
| awake mean (13 teams) | awake | 18,725 | 182.5 |

The three figures are **identical to the cent** — the fair floor, exactly what R7 predicts — and a
dark team is worth **32 % less** per row than an awake one. There is no surplus to extract.

**3. The Field is not dark.** `dark_team_census.py --games 58-68`: 3 of 16 median
(3,3,2,3,3,3,3,2,2,4,4), persistently makalu and OPUSMOPUS, corroborated by identical nets in all
eleven Games. This reproduces **H12**'s G44–57 finding on a fresh window; rule 9's "mostly dark"
premise stays falsified.

**The intuitive version of this idea is not neutral, it is the Game 62 loss.** "Dark teams can't
punish an Overcharge, so raise the Charge" is backwards: above `t` a dark Reviewer pays **zero**,
so darkness makes an Overcharge *worse* than against an awake Field that accepts ~17 % of them.
That is H14, where 10,349.89 against `t ∈ [8505, 10350)` drew 3 payers to error404 ai's 8,504.71
drawing 16.

**Where the recent window's money actually goes.** G58–68 net **−4,496** (4th of 17, reconciles to
the published leaderboard to the cent), decomposed over our Reviewer side: income 280,305, paid on
accepts 40,035, **lawyer penalty 244,765 — 86 % of all cost**. The two largest penalty sources are
**Teamers (29,087) and error404 ai (27,558)** — and they are the *only* two teams positive in this
window (+130,039 and +123,251). They are not exploiting anyone's absence; they price just under `t`
and collect `a` from all sixteen. **We are the harvested party, and the harvesters are the accurate
teams, not the awake ones.**

That is not a Limit problem either — `limit_ceiling_sweep.py` re-run at Game 68 (67 Games, floor
±51,362) still has nothing passing four folds, best `model 0.50` at **+1,304 = 2.5 % of the floor**,
and every value above 0.45 negative on `>40`. **H13 and H15 confirmed on seven more Games.** Of the
244,765, about 163,177 is money we owed anyway; only the `0.5a` excess is reachable, and no
multiplier reaches it.

**Verdict: no `src/` change. Nothing was shipped.** The lever remains estimate quality on the
Issuer side — H15's Game 68 finding (`t_hat` 2–2.5× too low on theft/contents items, ~47,000 of
income forfeited, zero of eleven Line Items memory-backed) is worth an order of magnitude more than
anything on the Reviewer side, and it is the same conclusion H3 and H8 reached from other
directions.

---

## H16 ❌ The Limit is too low on *large* items — a real diagnosis that does not survive the only split we can act on

The sharpest version of the Limit complaint yet, and the one worth writing up, because the
diagnosis is correct and the rule built from it still loses.

**Bucketed on what the item turned out to be worth**, strictness is wonderful on cheap items and
ruinous on expensive ones. Over every reconstructing Game, our real submissions:

| item worth | items | lawyer paid | saved by rejecting | ratio |
| --- | ---: | ---: | ---: | ---: |
| `t < 100` | 243 | −24,356 | 241,578 | **9.9 : 1** |
| 100–500 | 145 | −225,180 | 251,722 | 1.1 : 1 |
| 500–2k | 60 | **−391,522** | 113,924 | **0.3 : 1** |
| 2k+ | 12 | **−381,554** | 129,302 | **0.3 : 1** |

773,076 of lawyer on items worth ≥500, to save 243,226. It also explains why three global sweeps
found nothing (H15): a global multiplier moves both bands at once and the 9.9:1 gain on cheap
items cancels the 0.3:1 loss on expensive ones.

**Then bucket the identical table on `t_hat`, the only quantity a rule can key on:**

| `t_hat` band | items | lawyer | saved | ratio | `t < t_hat/2` |
| --- | ---: | ---: | ---: | ---: | ---: |
| < 100 | 187 | −88,441 | 111,356 | 1.3 : 1 | 79/187 |
| 100–500 | 166 | −222,076 | 174,464 | 0.8 : 1 | 65/166 |
| 500–2k | 84 | −357,163 | 193,107 | 0.5 : 1 | 31/84 |
| 2k+ | 23 | −354,932 | 257,598 | **0.7 : 1** | **14/23** |

The gradient collapses — 1.3 / 0.8 / 0.5 / 0.7, no clean ordering — and the last column says why.
**Fourteen of the 23 Line Items we believed were worth over 2,000 turned out to be worth less
than half that.** "We think it is big" is not "it is big", so raising `b` there raises it on a
bucket that is mostly our own overestimates, and buys their Overcharges.

The first table is selection on the outcome: an item lands in the low-true-`t` bucket partly
*because* everyone's Charges on it were low, which is exactly when rejecting is cheap.

**Swept anyway, keyed on `t_hat`** — Limit multiplied by `k` above a threshold, with the option
of lifting `LIMIT_CAP` there too. Ten cells, thresholds 500 and 1,000, `k` from 1.0 to 3.0:
**every single one loses**, best case `t_hat >= 1000, k = 1.5, cap kept` at +1,416 on 3/4 folds,
worst −280,775. Lifting the cap alone on large items is −69,548, reproducing the −62,278 already
in `ORCHESTRATOR.md` §3.

So the Limit rule is right and the money is in `t_hat` — the fourth independent route to that
conclusion tonight, after the global multiplier, the ceiling-and-clamp pair, and
`LIMIT_QUANTILE`. What would change it: an observable, knowable at submission time, that
separates the 9 genuinely-large items in the `t_hat >= 2k` bucket from the 14 that are not. That
is §4a, still open.

---

## H17 ❌ Read policy-stated EUR caps instead of estimating them — the number is exact, the *row* is not identifiable

Raised by the Game 72 review, and it looked like the cleanest lead of the night because the
policy states the answer in figures rather than leaving it to be estimated:

> "one travel or vehicle charge per contractor per invoice, **up to EUR 70** net of value added
> tax" — `policy.txt` 5.2.6(c)

`70 × 1.19 = 83.30` gross. And the settled record agrees to a startling degree. Of the 33
vehicle/travel/call-out Line Items with a proven non-zero floor, the floors cluster at
**79, 79, 79, 79, 79, 79, 79, 80, 81, 81, 82, 82, 82, 82**, and **83.30 falls inside every
bounded bracket in the family** — G29 [80,86), G34 [82,86), G35 [82,92), G38 [71,140),
G62 [79,90), G67 [79,86), G72 [79,86). The Fair Value of a covered vehicle charge is not
approximately 83.30; it *is* 83.30. Our `t_hat` on those sits at 67–92 and our Charge at 51–67,
and the family carries **−23,077** of penalty, nearly all of it Limit rather than Charge.

**And pricing it loses anyway.** 80 of 775 Line Items match the wording, and most of them settle
near zero, because the same clause that sets the cap also says only *one* such charge per trade
invoice is indemnified (7.1.8(d)). Overriding the family:

| rule | all | odd | even | ≤45 | >45 | last15 | folds+ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `b = 83.30`, Charge shipped | −5,905 | −1,204 | −4,702 | −1,758 | −4,147 | −1,806 | 0/4 |
| `a = 83.30`, Limit shipped | −21,290 | −14,968 | −6,322 | −12,882 | −8,407 | −4,243 | 0/4 |
| `a = b = 83.30` | −27,195 | −16,172 | −11,023 | −14,641 | −12,554 | −6,049 | 0/4 |

Raising `b` to the exact known value buys the Field's ~83 Charges on the rows worth nothing.

**The discriminator is invoice membership, and we do not record it.** Ordinally the rule is
visible but leaky — the first vehicle row in a Case is high 10 times and low 5, later rows are
high 7 and low 13 — because a Case may contain several trade invoices, each entitled to one
charge. G35 has three legitimate high rows, G37, G51 and G72 two. `case_loader` already parses
positions across several invoices in one PDF (there is a test for it), so the boundary exists at
parse time and is simply not carried into the decision log.

Worth someone's time *if* the tournament were longer: carry an invoice id per Line Item, then
"first vehicle charge per invoice = cap, the rest ≈ 0" becomes deterministic. It is not worth it
at Game 72 with the 3× window opening at 81 — the whole family is ~500/Game of penalty against a
±6,275 single-Game floor, and it needs a parser change, a log schema change and an engine rule
to collect it. Recorded so the size is known rather than guessed at next time.

---

## H18 ⚠️ Coverage is now the largest addressable leak, it is worth +1,173/Game, and no pricing rule reaches it

Two consecutive per-Game reviews landed independently on the same clause, which is the bar this
project sets for taking a pattern seriously.

Game 74: coverage came back **0.01–0.05 on 20 of 31 Line Items**, collapsing the Limit to ~60 on
items whose reconstructed floor ran to 1,505. That is **€41,710 of €47,770 total penalties, 87 %**,
and it clears the ±6,275 single-Game floor by 6.6×. Game 75: item 10, skirting boards over 15 m,
Charged 253 against `t ≥ 609`.

Both trace to `policy.txt` 7.1.5. The model reads its first half — *"Indemnity is confined to
those parts of the insured property that were themselves affected"* — against a description
saying *"an area of maybe a square meter or so"*, and prices the invoice as if only a square
metre were covered. It misses the extension in the same clause: *"Where an affected room was
wetted as a whole, the whole of that room is treated as affected for the purposes of extraction,
drying and the reinstatement of its finishes."* The Field pays the whole room; we price a corner.

**The leak is large and it grew.** Penalty attributed to `coverage-too-low`, by window:

| window | coverage-too-low | all penalty | share |
| --- | ---: | ---: | ---: |
| G26–50 | −37,206 | −585,955 | 6 % |
| G51–65 | −157,117 | −331,274 | **47 %** |
| G66–75 | −61,712 | −203,281 | 30 % |

−256,036 over the record, the largest attributed stage after the untagged remainder. Note the
column is one-sided by construction: `coverage-too-high` shows €0 because being generous costs
*accepts*, not penalties. So the honest measure is the oracle, which prices both directions.

**Oracle coverage — the truth substituted for the model's probability — is +86,775 over 74
Games, `+1,173/Game`, positive on all four folds and +22,010 on the last ten**, against a
±53,978 floor. That is a real lever and among the largest still open.

**And no pricing-side rule reaches it.** The natural candidate: 29 of Game 74's 31 items were
memory-backed, so the wording had been *watched settle*, which ought to override a coverage
probability of 0.01. Flooring coverage on memory-backed items, swept:

| floor | all | odd | even | ≤50 | >50 | last10 | folds+ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.40–0.60 | +0 | +0 | +0 | +0 | +0 | +0 | 0/4 |
| 0.70 | −2,974 | −3,443 | +468 | −1,656 | −1,319 | −2,459 | 1/4 |
| 0.80 | −591 | −5,348 | +4,757 | +1,731 | −2,321 | −3,611 | 2/4 |
| 0.90 | +536 | −1,752 | +2,288 | −1,777 | +2,313 | +345 | 2/4 |

Anything under 0.67 is inert — `COVERAGE_FLOOR` is `1 − LIMIT_QUANTILE = 2/3`, so a lower floor
cannot lift the Limit off zero at all. Above it, the gain on wrongly-collapsed items is paid back
in accepts on the items where the low coverage was *right*. Memory certifies price, not coverage;
50 of 158 repeated wordings flip between `t = 0` and `t > 0`, which is why the store returns
price only, and it is why this shortcut cannot work.

**Not attempted, deliberately.** The fix is a coverage-prompt change and it cannot be validated
offline — scoring it needs fresh model calls on settled Cases, which is the runner's quota. At
Game 75 with the 3× weighting opening at 81, the trade is asymmetric: the upside is some fraction
of +1,173/Game, the downside is that coverage already drives 30–47 % of penalties so a regression
is expensive, and we would be unable to tell which we had until the weighted window was underway.
Holding a measured +11k/Game rate beats an unmeasurable swing at it.

**This is the top item for whoever has a validation loop and time.** The specific change: teach
the coverage step that 7.1.5 has two halves, and that a description understating the wetted area
does not narrow the *room-scope* extension for extraction, drying and reinstatement of finishes.

---

## H19 ❌ The model channel was dark for eight triple-weighted Games and we cannot prove it mattered

Games **82-89 all ran with `model_draws=0`**. The Azure endpoint returned `401 - Access denied due
to invalid subscription key or wrong API endpoint` on every call, for both ensemble draws and the
Fast Path, across eight consecutive Games — every one of them weighted 3x. Those Games were priced
by Price Memory and the fitted constants alone. It recovered by itself at Game 90.

**Nothing broke, and that is the first result.** The degradation path held exactly as designed:
the blind floor posted at T+0, Price Memory priced what it recognised, the fitted constants
covered the rest, and eight Games banked **+254,092 weighted**. Rule 1 says the default submission
is an incident and never a fallback; this is the eight-Game proof that the fallback chain beneath
the model is real rather than aspirational.

**The tempting conclusion is that the model channel is dead weight, and it does not survive a
test.** Normalising by the oracle ceiling, because Case value swings twentyfold and raw per-Game
nets cannot be compared:

| | n | mean capture |
| --- | ---: | ---: |
| model dark | 9 | **28.4 %** |
| model live | 57 | 17.5 % |

A +10.8 point gap. But capture has a standard deviation of 34 % dark and **75 %** live, ranging
from −296 % to +434 %, and a permutation test over 200,000 shuffles gives **p = 0.208**. One split
in five is this lopsided by chance. Not actionable.

**What the estimates say, with an honest caveat.** Bucketed on `t̂` — the only split knowable at
submission time — every bucket estimates *high*: 2.36x under 100, 1.87x at 100-400, 1.73x at
400-1000, 4.40x above 1000. That matters because five consecutive per-Game reviews (88, 89, 90,
91, 92) each named `estimate-too-low` as the dominant stage and proposed raising estimates. The
stage fires only when `t̂ < t_lo`, so **it selects the left tail by construction**, and acting on it
would have repeated the regression artefact that already cost eight experiments.

The caveat cuts at our own numbers too: that measurement filters to uncensored brackets, and an
item is uncensored *because* somebody rightfully rejected it, which skews toward low `t`. It is
the mirror image of the same selection. So the *levels* are not trustworthy either. What survives
is the contrast under one filter, where both sides share the bias:

    memory spoke    n=291    1.27x    RMSLE 1.39
    model only      n=206    7.12x    RMSLE 2.30

Consistent with the pre-existing `MEMORY_SIGMA = 0.43` against the model's realised RMSLE of
1.66 / 1.82 / 2.20, and with exact-wording recall having reached **75 %** (807 of 1069 Line Items
now seen in another Case). Coherent, mechanistically plausible, and still not licensed by a
net-effect test at p = 0.208.

**No change shipped.** With eight triple-weighted Games left, an unvalidated change to the channel
blend is a bet against a measured noise floor, and the two changes tonight that looked strongest on
paper — the coverage recalibration and this — were both killed by a second look. The honest summary
is that Price Memory is measurably the better channel and we ran out of evidence, not that the
model should be switched off.

## H20

**The Limit is ~25 % too low, and it is a level error rather than a ranking error.** Measured
over Games 82–97 against the settled cross-section, not simulated.

The payoff table makes the reviewer's decision a single threshold. Rejecting costs `1.5a` when
the Charge was fair and `0` when it was not; accepting costs `a` either way. So with `q = P(fair)`
at the margin:

    accept iff  1.5 * a * q  >  a      i.e.   q > 2/3

Bucketing **our own rejections** by how far the opponent's Charge sat above **our own Limit**
(`a / b`), with `a` recovered from any row where money moved and fairness read off any rejected
row's `amount`:

| `a / b` | n | `q = P(fair)` | cost if we reject | cost if we accept | gain from accepting |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1.00–1.25× | 412 | **83 %** | 170,151 | 136,253 | **+33,898** |
| 1.25–1.50× | 145 | 54 % | 28,814 | 35,258 | −6,444 |
| 1.50–2.00× | 134 | 44 % | 24,307 | 36,804 | −12,497 |
| 2.00–3.00× | 145 | 32 % | 23,394 | 49,160 | −25,767 |
| > 3× | 244 | 25 % | 42,920 | 116,362 | −73,441 |

**`q` falls monotonically, so the Limit ranks claims correctly — it is simply set about 25 % too
low.** Every band above 1.25× is already on the right side of the threshold; we are not too strict
in general, we are too strict in exactly one narrow band. Unweighted that band is **+33,898** over
sixteen Games; these are triple-weighted Games, so **≈ +101,700 weighted, ≈ 6.4k per Game.**

**Why this is not the falsified "put `b` in the upper half" intuition.** That one raised `b` toward
`t̂` as a *buffer*, which is unconditional generosity and stays wrong. This is a threshold crossing
measured at the margin: the top row of the table is the only place the arithmetic flips, and it
flips because `q = 83 % > 2/3` there. The CLAUDE.md line "a high `b` buys no protection from the
lawyer at all, it only converts zeros into payments" is **wrong as stated** and should be corrected
at the source: raising `b` converts a `1.5a` penalty into an `a` payment on every *fair* claim it
newly admits, saving `0.5a` each. It only converts zeros into payments on *fraudulent* claims. Both
effects are real; which dominates is exactly the `q > 2/3` test, and nothing else.

**The censoring cuts the safe way, for once.** 217 of 1,297 rejections never revealed a Charge —
every one of sixteen reviewers rejected them at `amount = 0`, which is the signature of a large
*fraudulent* Charge. Dropping them therefore biases `q` **upward**. The finding breaks only if
**101 of those 217** land in the narrowest, lowest band; they are by construction the largest
Charges in the sample, so they land in `> 3×`. Survives.

**Corroboration from the field, same Games, same Cases, same opponents (88–97, unweighted):**

| | accept rate | wrongful-rejection penalty | claims paid | total Reviewer cost |
| --- | ---: | ---: | ---: | ---: |
| Codacabana (1st) | 61 % | 68,555 | 197,068 | **265,624** |
| Bin busy (us) | 44 % | **259,575** | 65,238 | **324,812** |

We accept the least of any scoring team and still pay the most. Our income over those Games
(378,386) is within 11 % of Codacabana's (422,971) — **the Charge side is competitive and the gap
to first place is 57 % Reviewer-side**, of which the wrongful-rejection penalty is 80 % of our
total cost against their 26 %.

**Not shipped, deliberately.** Found at Game 97 of 100 with two Games left. Maximum capture was
~12.7k weighted against a 185k gap to fourth, so it could not change the standing, while an
unvalidated edit to the pricing engine risked a whole Game — and a Game in this stretch is worth
up to 96,869. Rule 8: uptime outranks accuracy. Recorded here as the measurement, which is what
the next tournament needs from it.

---

# Post-tournament ledger — all 100 Games settled

Everything below was measured **after** the last Game, against the complete public record: 100
Games, 17 teams, 315,792 settled Transactions, reconstructed to the cent
(`scripts/archive_tournament.py`). Final standing **5th of 17, +238,255.07**.

The harness for all of it is `scripts/replay_payoffs.py` — our real Charge and Limit recovered
from the rows, the Field held at what it really did, the real payoff table against the recovered
Fair Value brackets. 99 of 100 Games reconstruct exactly; Game 67 is excluded for the known Cap
collision.

## H21 ✅ 103 % of everything left on the table is the *estimate*; the decision rules are done

**Claim.** Constant-tuning of the Charge and Limit multipliers is exhausted, and every remaining
euro is reachable only through a better Fair Value estimate.

`scripts/experiments/ceiling.py`, four rungs over 99 Games, weighted:

| rung | net |
| --- | ---: |
| DEFAULT `a = 0, b = 0` | −3,737,366 |
| **ACTUAL (what we submitted)** | **224,840** |
| BEST-KNOB — best `(α, β)` over a 72-cell grid on our own `t̂` | 109,248 |
| ORACLE `a = b = t` | 4,488,842 |

The middle rung is the result. **The best constant-only strategy available anywhere in the grid
scores 115,593 *worse* than what we actually shipped** — the pricing rules are not merely near
their optimum, they are past the point where a global multiplier can help, because the shipped
rule varies its factor with the band and a constant cannot. So of the 4,264,002 still above
ACTUAL, 103 % is estimation and −3 % is decision rules.

This confirms what CLAUDE.md's Status section already claimed, on 3× the Games and with the
counterfactual run rather than argued. **Do not open another constant sweep.**

## H22 ✅ What a unit of accuracy is worth — and we sit on the steepest part of the curve

`scripts/experiments/price_of_sigma.py` perturbs the *true* Fair Value by a lognormal of known
width, prices it with the shipped rule, and replays. Weighted, best `β` per row:

| σ | net | | σ | net |
| ---: | ---: | --- | ---: | ---: |
| 0.00 | 2,324,912 | | 0.60 | −155,324 |
| 0.10 | 2,090,251 | | 0.75 | −604,370 |
| 0.20 | 1,814,964 | | 0.90 | −1,013,234 |
| 0.30 | 1,264,589 | | 1.10 | −1,431,169 |
| 0.45 | 396,211 | | 1.40 | −1,934,149 |

Our real submission (224,840) sits at an **effective σ ≈ 0.52**, and net crosses zero at
σ ≈ 0.57 — so the break-even is far tighter than the 0.85 CLAUDE.md rule 10 records, once the
Limit is allowed to move with the estimate.

**σ 0.45 → 0.30 is worth +868,378.** That is the steepest segment in the table and it is the one
adjacent to where we stand. Roughly **5.8 M weighted per unit of log error** in our operating
region. Any evidence-layer proposal can now be priced: estimate the σ it buys, read the euros.

## H23 ❌ "We overestimate the Fair Value by 19 %" — a censoring artefact, and the correction loses money

**The diagnosis was wrong and the fix built on it lost at every cell.** Worth reading in full,
because this is the fourth time this repository has been caught by the same selection.

Scoring `log(t̂ / t)` on Line Items whose Fair Value bracket is **bounded** gives a median
`t̂ / t` of **1.189** and an RMSLE of 0.658 — an apparently clear level error, and the same
diagnostic said our published band understates our real error by **1.88×** and leaves 27.5 % of
truths outside its own 90 % interval.

But a bracket is bounded *only when somebody rightfully rejected*, which selects the
sub-population where the Field — and so usually we — overestimated. Splitting the 531 usable
Line Items:

| | n | median |
| --- | ---: | --- |
| bounded brackets | 342 | `t = 0.841 × t̂` — we overestimate |
| right-censored (`t ≥ t_lo` only) | 189 | `t ≥ 1.044 × t̂` — we **underestimate, provably** |

85.2 % of the censored items have a proven floor above the bounded sample's median residual, and
**60.8 % are provably worth more than our estimate.** Fitting the residual as interval-censored
data instead (Turnbull NPMLE, `src/pricing/calibration.py`, 17 tests) moves the pooled median
`t / t̂` to **0.982**. **We were essentially unbiased the whole time.**

The layer built on the bad diagnosis was scored leave-one-Game-out over 73 Games and **lost at
every one of 42 cells** — best −36,050 weighted, worst −2,812,204. Handling the censoring
properly recovered +71k of that and it still loses. `calibration.py` is kept as a *measurement
instrument only*, with a banner saying so; nothing in the pricing path reads it.

**The rule this earns:** before correcting a level error in the estimator, fit the residual with
the censored observations included. Three of the four intuitions in CLAUDE.md's table and both
H2 and H16 died to conditioning on the outcome. This is the tool that stops it.

## H24 ⚠️ Price Memory is four times bigger than its docstring claims — but the blend weight was already right

**Confirmed.** Rebuilt from all 100 Games and scored leave-one-out
(`build_price_memory.py --games 1-100 --evaluate`): **recall 79 % (609/773), σ 0.458, bias
+0.031, median |log error| 0.260.** The module docstring claimed **22 % recall** and "four items
in five are misses" — measured over Cases 1–14, and stale for most of the tournament. Both the
docstring and the tracked store are fixed; `data/price_memory.json` held **203 entries from
Games 1–46** and now holds **325 from all 100**.

**Falsified, and it was my own hypothesis.** From "memory is far more accurate than the model"
it does *not* follow that memory should take more of `blend.combine`. Swept walk-forward over 99
Games (`scripts/experiments/blend_weight_sweep.py`), memory's share against the gain over our
real submission:

| share | 0.66 (shipped) | 0.75 | 0.83 | 0.92 | 1.00 |
| --- | ---: | ---: | ---: | ---: | ---: |
| gain | **+62,827** | +61,190 | +48,638 | +31,173 | +13,372 |

Monotonically **down**. The shipped inverse-variance weighting is already at its optimum; what
was wrong was the *store*, not the arithmetic over it. `MEMORY_SIGMA` and `MODEL_SIGMA_PRIOR`
stay as they are.

## H25 ⚠️ Replaying with the finished store scores first place — but 97 % of it is eight Games

**The arithmetic.** `scripts/experiments/memory_first.py`, leave-one-Game-out, memory hit prices
the item outright: **+855,591 weighted against our real +224,840**, a gain of **+630,751**, and
positive on all five folds (odd +226,457, even +404,293, 1–43 +554,723, 44–81 +33,724, 82–100
+42,304). Codacabana won on 830,036.

**The caveat, which is larger than the result.** The gain is not distributed:

- improved 54 Games, worsened 28, unchanged 17
- **median Game gain +190** — the typical Game barely moves
- top 8 Games carry **611,476 of 630,751**; without them the gain is **+19,275**
- those 8 are G10, G8, G17, G100, G12, G68, G18, G7 — **seven of the eight are Games 7–18**

And walk-forward — a store built only from *strictly earlier* Games, which is what the live
pipeline had — the same arm is worth **+13,372**, not +630,751. The difference is the whole
size of the hindsight.

**What this actually says**, corroborated by `scripts/postmortem.py` independently ranking G8,
G17, G10, G100, G12, G18, G11, G7 as the eight worst Games of the tournament:

> **Games 1–25 cost −322,595 weighted. Games 26–100 earned +560,850.**

The tournament was decided before the strategy was finished. Had Games 1–25 merely scored
**zero** we finish 3rd; had they scored the per-Game average of Games 26–100 we finish **2nd**.
The binding constraint was never steady-state accuracy — in steady state the finished store
moves the median Game by €190 — it was the **cold start**: an empty Price Memory, and a pipeline
that did not have Strategy 2 until Game 26.

**The change this earns is not a constant, it is an asset.** Ship `data/price_memory.json` warm.
It is the one thing measured here that is worth six figures and cannot be re-derived in sixty
seconds.

## H26 ✅ Run from Game 1, the finished strategy wins — and the whole table has to be re-scored to say so

**The methodological point first, because it invalidates every earlier counterfactual in this
file as a statement about *placement*.** H25 and everything before it report **our** net. That is
not enough to claim a rank: the tournament is seventeen interlocking scores, not seventeen
independent ones. Every euro we are paid is a euro an opponent pays, and every claim we accept
is income for whoever issued it.

    we Charge closer to `t`  ->  our income rises AND sixteen opponents' costs rise
    we accept more claims     ->  our costs rise AND sixteen opponents' income rises

Only fixtures involving us can move, so each opponent decomposes exactly:

    net(T, counterfactual) = net(T, actual) - [T's fixtures vs us, as settled]
                                            + [T's fixtures vs us, under our new submission]

`scripts/experiments/counterfactual_standings.py --validate` computes the middle term through
the replay model **and** straight from the settled Transaction rows: they agree to **0.0000**
across every (Game, team) pair, and the `ACTUAL` arm reproduces the published standings exactly.

**The arms**, weighted, rank recomputed against all sixteen opponents:

| arm | weighted | Games 1-25 | Games 26-100 | rank |
| --- | ---: | ---: | ---: | ---: |
| ACTUAL | 238,255 | -322,595 | 547,435 | 5th |
| NO-BLANKS | 645,362 | 69,872 | 562,075 | **3rd** |
| WARM-STORE | 869,006 | 238,293 | 617,298 | **1st** |
| FULL-PIPELINE * | **885,401** | 254,688 | 617,298 | **1st** |

`*` the only arm with a synthetic component: Games 26-100 keep our real submission on a memory
miss (that *is* the mature model channel), while Games 1-25 misses are drawn from the `C:model`
residual measured later. Averaged over 5 seeds.

Final table under FULL-PIPELINE: **Bin busy 885,401 (1st)**, Codacabana 818,984, eyay 733,018,
TakeTheMoneyAndRun 547,290, error404 ai 436,410. First by **66,417**.

**NO-BLANKS is the row that matters most**, because it assumes no better estimate anywhere.
Games 1-25 failed in two ways that both produce *zero* income rather than inaccurate income:
we Charged **exactly nothing** (22 of 22 Line Items in Game 11, 12 of 12 in Game 12, all of
Games 2 and 3), and we Charged **so far above the Field that no reviewer's Limit reached it**
(27 of 39 in Game 8, 13 of 20 in Game 17; Game 20's median Charge was 2,345). Replacing only
those with the Field's own median Charge on the same item -- no model, no memory -- is worth
**+407,107** and moves us to third. That is rule 1 (`the default submission is an incident`)
priced.

**The payoff table is not zero-sum, and it explains the residual.** Under WARM-STORE we gain
+630,751 while the other sixteen lose only -196,827 between them; the missing **+433,924** was
being *destroyed*, not transferred -- on a wrongful rejection the reviewer pays `1.5a` and the
issuer receives `a`, so `0.5a` leaves the system. Across all seventeen teams the tournament
settled at **-13,862,270**. NO-BLANKS is the instructive counter-example: it *increases* total
destruction by 80,314, because Charging the Field median on previously-blank items pushes more
claims above opponents' Limits. Charging a *good* estimate at 0.69x stays under most Limits and
burns less. **Playing well destroys less for everyone, not only more for us.**

**Where the value is, one last time.** FULL-PIPELINE beats WARM-STORE by only **+16,395** -- the
model channel adds almost nothing on top of the store -- and **89 % of the gain is in Games
1-25** (a swing of 577,283, against 69,863 across the other seventy-five). The finished strategy
was worth about seventy thousand over the mature phase and more than half a million over the
phase where we did not yet have it. Which is H25's conclusion, now with a rank attached.


## H27 ⚠️ The Charge factor sits on the low edge of its optimum; the Limit must stay per-item

**Two findings, opposite verdicts, from the same sweep** (`scripts/experiments/target_multipliers.py`,
73 Games with a logged estimate, baseline 541,018 weighted).

**The Limit: confirmed as-is, and emphatically.** Replacing the shipped stack (posterior quantile,
capped by `LIMIT_CEILING` / `LIMIT_CEILING_MEMORY`, clamp released) with **any** flat multiple of
`t_hat` loses money. The best flat value, `b = 1.0 * t_hat`, costs **-141,650**. The per-item
logic carries real information a constant discards. R11 adds which way to err if forced: 1 % low
costs 113,527, 1 % high costs 5,403, so **at or slightly above** the estimate, never below.

**The Charge: the direction is supported, the value is not.** Derived, the argmax of
`m * P(r >= log m)` at our measured sigma ~0.52 is **m = 0.78**, flat within 1 % over 0.70-0.86;
the shipped rule yields **0.69** at a typical band -- inside the zone, on its bottom edge. Swept,
every competitive cell has a shallower slope or higher intercept than `A=0.85, B=0.45`; the best
is `A=0.85, B=0.25` at 636,422 (**+95,404**), positive on 4/4 folds, and a flat 0.75 reaches
610,956.

**Not shipped.** The surface is *jagged* -- 0.85/0.25 sits at 636,422 between neighbours at
498,841 and 561,143 -- which is what an argmax riding specific Charges across specific opponents'
Limits looks like, and the cell was selected in sample. Also of note: `m` is **nearly flat in
sigma** (0.74-0.82 from 0.15 to 0.60, non-monotone), which is a direct argument against
`CHARGE_SLOPE = 0.45` being that steep. A fold-clean fit of `(A, B)` is the open work; the grid
here is not it.

**Perspective.** All of this is worth tens of thousands. H21 puts 103 % of what remains in
estimation and H22 prices it at ~5.8 M per unit of log error. The multiplier is nearly flat in
sigma; the estimate is not.
