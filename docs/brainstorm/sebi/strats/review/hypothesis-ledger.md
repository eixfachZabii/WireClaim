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

## H4 🔬 Coverage is the highest-value single bit, and ours is not yet good enough

76 of 192 settled Line Items are worth nothing, and `p_covered <= 2/3` is what collapses the
Limit. The parked detector (`src/services/coverage.py`) measures **61.8%** recall at 1.7%
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
