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
