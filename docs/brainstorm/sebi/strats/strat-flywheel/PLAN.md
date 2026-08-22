# Strategy pitch — **The Flywheel**

### Online learning from settled Transactions: the tournament labels its own training set

> Competing plan for QuantCo _Claim to Fame_. Owns the **R9 inversion**, the **Price Memory**,
> and the **feedback loop**. Builds on `README.md` §3 and does not re-derive it — except in
> **F0**, where the README is **wrong**, and the correction is worth about a third of every
> number we would otherwise have learned.
>
> **Every figure below is reproducible right now.**
> `python3 docs/brainstorm/sebi/strat-flywheel/invert.py` — stdlib only, ~28 s, sections F1–F7.
> `python3 docs/brainstorm/sebi/strat-flywheel/invert.py --live 1` — runs the same inverter
> against the **real, settled Game 1** on the public leaderboard. It already passes.

---

## 0. F0 — the finding that pays for this document

**README R9 says: `rejected & amount > 0 ⟹ a = amount / 1.5`. That is wrong.**

Game 1 has settled. 4,896 real Transaction rows across 17 teams and 18 Line Items. Two
independent tests, both decisive:

**Test 1 — same Issuer, same Line Item, one Reviewer accepted and another wrongfully rejected.**
There are 18 such cases in Game 1. If `amount` were the Reviewer's payment, the rejected row
would be exactly `1.5×` the accepted row.

```
ratio rejected/accepted:  n = 18,  min = 1.000000,  max = 1.000000
```

**Test 2 — reconciliation against `/performance`, to the cent, for all 17 teams.**

| team | Σ(amount as Issuer) | API `income` | Σacc + 1.0·Σrejpos | Σacc + **1.5**·Σrejpos | API `costs` |
| --- | --- | --- | --- | --- | --- |
| error404 ai | 37 528.96 | **37 528.96** | 3 974.61 | **4 092.77** | **4 092.77** |
| Codacabana | 19 946.87 | **19 946.87** | 4 657.06 | **6 505.59** | **6 505.59** |
| Bin busy _(us)_ | 19 704.00 | **19 704.00** | 4 510.46 | **6 202.15** | **6 202.15** |
| Non Deterministic | 12 408.00 | **12 408.00** | 4 740.30 | **6 724.97** | **6 724.96** |
| Alpha _(dark)_ | 0.00 | **0.00** | 5 515.80 | **8 273.70** | **8 273.70** |

So, exactly:

```
amount            = what the ISSUER RECEIVES, in BOTH branches
income (per team) = SUM( amount | team is Issuer )
costs  (per team) = SUM( amount | accepted ) + 1.5 * SUM( amount | wrongfully rejected )
```

**The published `amount` is the Charge itself.** The `0.5a` lawyer fee never appears in a
Transaction row — it is applied only in the aggregate `costs`, and the surplus half is
destroyed exactly as R2 says.

**What the error would have cost us.** Every recovered Charge 33.3 % too low. Every `t_lo`
33.3 % too low. A fitted log-bias `β` wrong by `ln 1.5 = 0.405` — **more than twice the bias
F3 models**, in the direction that makes us charge less and reject more. The flywheel would
have spent 100 Games confidently converging on the wrong number, and every diagnostic would
have looked healthy while doing it, because the error is a constant multiplier that a
self-consistent loop cannot see.

**It had already propagated.** [`FIELD-REPORT-01.md`](../review/FIELD-REPORT-01.md) uses the `/1.5`
rule to compute how much Fair-Zone income we forfeit, and its numbers are therefore **1.5× too
small**. Corrected, Game 1 forfeits **1,361.36 per opponent = 21,782** against the 13,502 we
scored — **1.6× our entire score**, not 1.07×. The report's central claim survives and gets
stronger; only its magnitude was wrong. Both `README.md` R9 and the field report have been
corrected at the source.

**The proof on our own rows, which is the one to quote.** We are **Bin busy**. On Game 1
Line Item 2 we were accepted by 1 Reviewer and wrongfully rejected by 15, and the Line Item
paid us exactly `16 × 144.00 = 2 304.00`. Under the `/1.5` reading it would have paid
`144.00 + 15 × 216.00 = 3 384.00`. Our whole Game reconciles as
`16 · A_fair + F = 16 × 1 188.00 + 696.00 = 19 704.00`, matching `/performance` to the cent.
R1 in one line: **every opponent pays the same `a` on a Fair-Zone Charge, accept or reject.**

This is precisely the failure mode `CLAUDE.md` warns about, and it was caught in 40 minutes by
running the inverter against real rows instead of reasoning about them.

Two corollaries fall out of the same reconciliation:

- **The Cap shows up as `amount < a` on an accepted Fraud-Zone charge** — still true, but `a`
  must now be recovered from a _fair_ row, not deduced from a rejected one.
- **`/performance` publishes each team's confusion matrix**: `reviewed_accepted_wrong`
  (Wrongful Acceptances) and `reviewed_penalties` (Wrongful Rejections), per team, per Game.
  That is a calibration signal requiring **no inversion at all** — see §6.3. It is the single
  cheapest thing in this document and it works from Game 1 on our own row only.

---

## 1. The bet in one paragraph

Every 757.6 seconds this tournament hands us a labelled training set for free, and then gives
us **11 minutes 38 seconds of dead time** to learn from it before doing it again, one hundred
times. Nobody else will treat that as the product. The other five tracks each build a machine
that is as good at Game 100 as it was at Game 1: `strat-ops` maximises the number of Games we
play, `strat-adjuster` and `strat-adk` maximise how well we read one Case, `strat-quant`
maximises how well one posterior converts into two numbers, `strat-metagame` reads the Field.
**All five are static estimators.** Our bet is that the derivative matters more than the
level — that a mediocre estimator plus a closed loop beats a good estimator that never finds
out it was wrong, because the settled leaderboard does not give us an opinion about our error,
it gives us **the arithmetic sign of it, per Line Item, 800 times.** The loop is: invert every
settled Game back into (a) a bracket on each Fair Value, (b) every opponent's exact Charge,
(c) every opponent's Limit, (d) the Cap; then fit the two things that actually move money —
the **bias** of our Estimate and the **width** of our posterior (R4b) — and feed them back
before the next Game opens. F0 above is the loop's first output, produced before the loop was
built, and it is already the most valuable single line in this repo.

---

## 2. Why this wins

### 2.1 The label is not weak evidence. It is a point observation in all but name.

The naive worry about R9 is that a bracket `t ∈ [L, U)` is a vague label. Measure it (**F1**,
Monte Carlo, 30-team Field, 2 500 Line Items per row):

| regime | two-sided | p50 log width | pins `t` to | p90 |
| --- | --- | --- | --- | --- |
| Sat 15:00–00:00, Field awake | 100.0 % | 0.069 | **± 3.5 %** | ± 8.1 % |
| Sun 00:00–08:00, 50 % dark | 99.4 % | 0.138 | ± 7.2 % | ± 16.6 % |
| Sun 03:00, 80 % dark | 80.8 % | 0.318 | ± 17.2 % | ± 38.2 % |

Our own posterior sd is ~0.45 in log space. **A 0.069-wide bracket is 15 % of one posterior
sd.** Confirmed in Fisher information (**F6**), per label, for `(β, σ)`:

| label source | `I_ββ` | `I_σσ` | Games to `se(β) ≤ 0.05` | Games to `se(σ)/σ ≤ 10 %` |
| --- | --- | --- | --- | --- |
| field-wide bracket, awake (w = 0.07) | 4.93 | 9.81 | **10.2** | **6.4** |
| field-wide bracket, 80 % dark (w = 0.32) | 4.75 | 9.04 | 10.6 | 6.9 |
| _(reference) `ln t` observed exactly_ | 4.94 | 9.88 | 10.1 | 6.4 |

**The censoring costs 1 % of the information.** Treating these labels as vague is the mistake;
they are ground truth with a rounding error. By Game 12 we know our bias to ±0.05 in log space
and our width to ±10 %. `strat-quant` schedules its first fit at ~Game 8 and that is right.

### 2.2 The two things we can learn are worth 12–16 % of income, and they are not the same thing

**F3**, our net per opponent per unit of true Fair Value, against a 30-team Field. The estimator
truth is a `+0.18` log-bias (a units/VAT-shaped error) and a true sd of `0.45`, while the
ensemble self-reports `0.22` — the classic overconfident LLM.

| our state | net | income | costs | Δ net | as % of income |
| --- | --- | --- | --- | --- | --- |
| **Field awake** | | | | | |
| G1 biased and overconfident | 0.0158 | 0.5882 | 0.5724 | — | — |
| + bias corrected only | 0.0571 | 0.6020 | 0.5449 | +0.0414 | **+7.0 %** |
| + width calibrated only | 0.0977 | 0.6254 | 0.5276 | +0.0819 | **+13.9 %** |
| both — the flywheel | 0.0872 | 0.6134 | 0.5262 | +0.0714 | +12.1 % |
| **60 % dark (overnight, R10)** | | | | | |
| G1 biased and overconfident | 0.2933 | 0.5054 | 0.2121 | — | — |
| + bias corrected only | 0.3435 | 0.5452 | 0.2016 | +0.0502 | **+9.9 %** |
| + width calibrated only | 0.3710 | 0.5666 | 0.1957 | +0.0777 | **+15.4 %** |
| both — the flywheel | 0.3734 | 0.5690 | 0.1955 | +0.0801 | **+15.9 %** |

Three readings, and the third is the important one.

1. **Net is a small difference of two large numbers.** Income ≈ 0.59, costs ≈ 0.57, net ≈ 0.02.
   That is R2 made concrete: the game is negative-sum and almost all of the money passes
   straight through. It is exactly why a 3 % error in the Estimate is not a 3 % error in the
   score, and why measuring beats reasoning here.
2. **The gain is larger overnight**, agreeing with `strat-quant` §2.2 and README R10 — and for
   an extra reason they do not state: overnight the Field is dark, dark Reviewers reject
   everything, and **a rejection with `amount > 0` is exactly the fair-witness row the inverter
   needs.** The phase where accuracy pays most is the phase where the labels are cleanest.
3. **Row 3 beats row 4.** Correcting the *width* alone scores better than correcting *both*,
   because a `+0.18` log-bias and a 2× too-narrow posterior happen to cancel at `Q₁ᐟ₃`. Two
   wrongs make one right answer. **This is the entire argument for selecting parameters on
   realised net rather than on likelihood** — see §4.3, where we disagree with `strat-quant`.

### 2.3 The Field publishes its own Charges, and at Game 1 the Field is leaving money on the table

Real Game 1, recovered by the inverter (`--live 1`). Every Charge below is a **recovered**
number, not an estimate; `F` = proven Fair Zone, `X` = proven Fraud Zone.

| item | Bin busy | Codacabana | Non Deterministic | error404 ai | recovered `t_lo` |
| --- | --- | --- | --- | --- | --- |
| 1 | 0 | 53.30 F | 85.00 F | **122.94 F** | ≥ 122.94 |
| 2 | 144.00 F | 97.64 F | 135.00 F | **227.66 F** | ≥ 227.66 |
| 6 | 280.00 F | 317.34 F | 425.00 F | **569.16 F** | ≥ 569.16 |
| 9 | 176.00 F | 245.99 F | — | **409.79 F** | ≥ 409.79 |
| 15 | 360.00 F | 162.74 F | — | **606.22 F** | ≥ 606.22 |
| 8 | 28.00 X | 28.70 X | X | X | `t = 0`, `t < 28.00` |
| 16 | 176.00 X | 273.71 X | — | X | `t = 0`, `t < 176.00` |

**On every covered Line Item, the highest Charge in the entire Field was still proven Fair.**
`t_hi` is `∞` on 11 of 18 items: not one team found the ceiling. error404 ai charged 1.6–2.2×
what Bin busy charged, was never once above `t` on a covered item, and finished the Game on
`+33 436` against Bin busy's `+13 502`. R1 says income below Fair Value is risk-free; the
active Field is pricing at roughly half of it.

This is the flywheel's first tradeable output and it took one Game to produce. It is also a
warning about our own F1 table: **the real Field is 4 active teams, not 30**, so a real bracket
is far looser than the simulation says (§7.2).

### 2.4 The Guttman invariant — a free, total audit of our model of the game

`accepted ⟺ a ≤ b`, with one Charge and one Limit per team per Line Item (R3). That forces the
accept/reject matrix, sorted by Charge and by Limit, to be a **staircase**: no Reviewer may
accept a Charge higher than one it rejected. It is a Guttman scale, and it is checkable.

```
Game 1, 4 896 real Transaction rows, 18 Line Items:   GUTTMAN VIOLATIONS = 0
Issuer+Line Items with inconsistent accepted amounts: 0    (the Cap is per Line Item)
Issuer+Line Items proven both Fair and Fraud:         0    (t is one number per Line Item)
```

Three assertions that would each have caught a different wrong assumption about the game —
per-opponent Limits, a per-Reviewer Cap, a per-Reviewer Fair Value — and all three pass on real
data. **Every settled Game re-runs them.** The day the staircase breaks, something we believe
is false, and we find out in twelve minutes rather than at 04:00.

### 2.5 The style argument — this is the desk note QuantCo would write

QuantCo prices things and then checks whether the price was right. This track produces exactly
that artefact and it is the only one in the repo that produces it _from the tournament's own
data_:

- **A correction to our own published result, found by data, with the arithmetic shown** (F0).
  A judge who sells claims software has seen a hundred teams present a model. Very few present
  a model that caught its own authors being wrong, in public, with a reconciliation table.
- **A calibration curve with honest bounds.** Interval-censored labels do not give a point PIT;
  they give an interval. We report the **sharp identified band** (F5), not a midpoint dressed up
  as a measurement. That is a partial-identification argument, and it is exactly the right
  register for this audience.
- **A counterfactual replay on their own settled Games**, since the payoff matrix is
  deterministic given `(a, b)`, the opponents' Charges and the `t` bracket.
- **A finding about their Field**: the whole active Field under-charged by roughly 2× at Game 1
  (§2.3), which we can show them, per Line Item, with the recovered numbers.

---

## 3. The inversion algorithm

Reference implementation: `invert.py` §2, ~110 lines, no dependencies. It round-trips 600
synthetic Games with zero errors and runs clean on real Game 1.

### 3.0 Notation and the one structural fact everything rests on

Per Line Item `k` of Game `g`: a secret Fair Value `t`, a secret Cap `c ≥ 4t`, each team `i`
submits one Charge `a_i` and one Limit `b_i` (R3). A row is `(issuer i, reviewer j, accepted, amount)`.

The load-bearing fact, and it is not in the README:

> **The Cap can only ever bind on a Fraud-Zone Charge.**
> If `a ≤ t` then `c ≥ 4t ≥ 4a > a`, so `min(a, c) = a`.

So in the fair branch `amount = a` unconditionally, and any `amount < a` is proof that `a > t`.

### 3.1 Pass 1 — per-Issuer local evidence

For each Issuer `i` on Line Item `k`, gather its ~N−1 rows:

```
fair_vals = { amount : rejected, amount > 0 }      # Wrongful Rejection  ⟹ a ≤ t   (F0: NOT /1.5)
zero_rej  = any( rejected, amount == 0 )           # rightful rejection  ⟹ a > t
acc_amts  = { amount : accepted }                  # each == min(a, c)

if fair_vals:  a_exact = median(fair_vals);  verdict = FAIR       # median, not first: one bad row
elif zero_rej: verdict = FRAUD                                    # a unidentified, so far
a_lower = max(acc_amts) if acc_amts else 0                        # a ≥ a_lower
if a_lower == 0 and acc_amts: a_exact = 0                         # min(a,c)=0 and c>0 ⟹ a = 0 (dark)
```

`fair_vals` should be a singleton — every Reviewer who wrongfully rejects the same Issuer sees
the same Charge. Taking the **median** costs nothing and survives one corrupt row. Real Game 1:
`0 / 306` Issuer-items had inconsistent wrongful-rejection amounts.

### 3.2 Pass 2 — the lower bound

```
t_lo = max{ a_i : verdict_i == FAIR }              # t ≥ t_lo, proven
```

### 3.3 Pass 3 — the Cap, and the ambiguity it creates

An accepted row shows `min(a, c)`, so **an acceptance alone cannot tell us whether we are seeing
the Charge or the Cap.** That is the ambiguous case, and it matters because resolving it is
worth a factor of four (§3.5). Three resolvers, in order of strength:

**(a) The coincidence detector.** `c` is shared across all teams on one Line Item. Two *distinct*
Issuers paying out an *identical maximal* amount is a measure-zero coincidence unless both were
capped:

```
if  ≥2 distinct issuers share the maximal payout v,  and  v ≥ 4·t_lo,
    and they are not known to have charged the same amount:
        ĉ = v                                      # exact
```

**Carry `ĉ` at full precision.** Quantise only for the grouping key. Rounding `ĉ` to the cent
and then dividing by 4 put the recovered upper bound *below* the true `t` in 1 of 600 synthetic
Games — a real bug, found by the round-trip assertion, caused entirely by a `round(x, 6)`.

**(b) The uncapping lemma.** This is the useful one, and it needs no coincidence:

> `c ≥ 4t ≥ 4·t_lo`. Therefore any payout `m < 4·t_lo` **cannot** be the Cap, so `m = a` exactly.

Once `ĉ` is known the test sharpens to `m < ĉ`.

**(c) Fair/Fraud classification of an ambiguous acceptance.** Given `t ∈ [t_lo, t_hi)`:

```
m ≤ t_lo   ⟹ a = m ≤ t_lo ≤ t         ⟹ FAIR,  confirmed
m ≥ t_hi   ⟹ a ≥ m ≥ t_hi >  t        ⟹ FRAUD, confirmed
otherwise  ⟹ undetermined
```

**The residual ambiguity is exactly the bracket, and the bracket is ± 3.5 % wide.** The
ambiguous case collapses onto itself.

### 3.4 Pass 4 — the upper bound

For any Issuer with `verdict = FRAUD` (so `a > t`) **and at least one acceptance**:

| what we know about the acceptance | bound on `t` | |
| --- | --- | --- |
| uncapped (`a_lower < 4·t_lo`, or `< ĉ`) | `t < a_lower` | strict |
| confirmed capped (`a_lower = ĉ`) | `t ≤ a_lower / 4` | **4× tighter**, closed |
| status unknown | `t < a_lower` | safe either way, since `a_lower = c ≥ 4t > t` when capped |

plus, unconditionally, `t ≤ ĉ / 4` whenever the Cap is observed at all. Then
`t_hi = min` over all of these, carrying the open/closed flag — **`c = 4t` exactly is the common
case, so `t ≤ c/4` must be inclusive.** A strict comparison here fails on 5 of 600 synthetic
Games, all of them precisely at `c = 4t`.

An Issuer proven FRAUD with **no** acceptance anywhere contributes nothing numeric: `a` is
unbounded above. Those are the extreme overchargers, and we do not care where they are.

### 3.5 Pass 5 — every Reviewer's Limit

```
b_j ∈ [ max{ a_i : j accepted i },  min{ a_i : j rejected i } )
```

using only Charges recovered exactly. Real Game 1 recovers **288 of 306** Issuer-items exactly
(94.1 %); the misses are Issuers rejected at zero by every Reviewer. A fully dark Reviewer gets
`b_j ∈ [0, min a_i)` — we cannot distinguish `b = 0` from `b = small`, and it does not matter.

### 3.6 Pass 6 — coverage, and why it is exact only with the Field

> If `t > 0`, then out of N Issuers somebody charges in `(0, t]` and somebody rejects them, so
> **at least one rejected row anywhere in the Field carries `amount > 0`.**
> Contrapositive: **no rejected row with a positive amount ⟹ `t = 0`.**

Guarded by `n_rej_zero ≥ 3` to avoid firing on a Line Item nobody rejected. Measured (**F2**,
4 000 items): **precision 100.0 %, recall 100.0 %**, field-wide, awake or dark, zero false
positives in 3 408 covered items. Overnight it is not merely accurate but *structurally* exact,
because a dark Reviewer rejects every Issuer and therefore labels every Charge.

That gives us a free, exact **ground-truth coverage label every Game** — which is what lets us
score and calibrate the coverage classifier that ADR 0001 puts at the front of the pipeline, and
which R6c makes the highest-variance decision in the game. Real Game 1: 7 of 18 Line Items
flagged `t = 0`.

### 3.7 The Guttman audit (§2.4) and the assertion set

Run after every settled Game. Any non-zero count is an alarm, not a metric:

```
assert guttman_violations == 0          # accepted ⟺ a ≤ b, one Limit per team per Line Item
assert inconsistent_accepted == 0       # the Cap is per Line Item, not per Reviewer
assert fair_and_fraud == 0              # t is one number per Line Item
assert lawyer_ratio == 1.0              # F0 — re-verified every Game, cheaply
assert Σ(amount | issuer) == performance.income          # reconciliation, per team
```

### 3.8 Identifiability — what is and is not recoverable

**Point-identified:**

- `a_i` for every Issuer wrongfully rejected by anyone (from `amount` directly).
- `a_i` for every Issuer accepted by anyone with payout `< 4·t_lo` (uncapping lemma).
- `c`, exactly, whenever two distinct Issuers are capped at the same value.
- **coverage** (`t = 0` vs `t > 0`), exactly, whenever ≥ 3 rightful rejections are observed.
- the **rank order** of all Charges, from acceptance counts: `a_i < a_{i'} ⟹ r_i ≥ r_{i'}`.

**Set-identified (a bracket, and the bracket is the answer):**

- `t ∈ [t_lo, t_hi)`, width ± 3.5 % awake / ± 17 % at 80 % dark.
- `b_j` per Reviewer, bracketed between the highest Charge it accepted and the lowest it rejected.

**Not identified, ever:**

- `t` exactly. There is no observation that pins it; the bracket _is_ the estimate.
- `a_i` for an Issuer rejected at zero by every Reviewer — bounded below only.
- `c` on a Line Item nobody overcharges past. Real Game 1: **no Cap event in 18 Line Items**,
  because the Field under-charged (§2.3). The Cap may take many Games to appear.
- **Anything at all when the Field agrees.** `t_hi = ∞` on 11 of 18 real Line Items in Game 1
  because not one team crossed `t`. **The labels are informative exactly to the extent that the
  Field disagrees** — and a well-calibrated Field is an uninformative one. This is the single
  most important caveat in the document and §7.2 prices it.

One consolation, and it is genuine: when the whole Field is below `t`, nobody is losing money to
Wrongful Acceptance, so the quantity we cannot measure is also the one that is not currently
costing us. The failure of identification is self-limiting.

### 3.9 A second, independent ground truth: `t` is sometimes written down

`CASE-0-FINDINGS.md` establishes that case 0's Fair Value was **stated in the documents** — the
policy gave the indemnity basis ("market value at the time of the theft") and the description
gave the number ("the bike was worth 420 Euros"), so `t = 420` was readable, not estimable.

If that shape recurs, we hold **two independent estimates of the same quantity**: a
document-derived `t_doc` available at `T+2 s`, and a leaderboard-derived bracket `[t_lo, t_hi)`
available at `T+12 min`. They are worth far more together than separately:

- **`t_doc` inside the bracket** ⟹ the reader is correct, and we may trust `t_doc` directly on
  future Cases of the same shape, collapsing the posterior to near-zero width.
- **`t_doc` outside the bracket** ⟹ a _reading_ bug, localisable: too high by ~1.19 is VAT, by
  the quantity is a per-unit/total confusion, by a round factor is units. This is the highest-value
  diagnostic in the loop, because it points at the defect instead of just measuring it.
- **`t_doc` absent** ⟹ the item is a genuine pricing problem and the trade-price knowledge base
  (`strat-adjuster` §4) carries it.

So the memory stores `(t_doc, bracket)` as a **pair**, and the fraction of items where the two
agree is a headline slide: _we learned to read the policy, and the leaderboard graded us._

---

## 4. The learner

### 4.1 What we fit, and what we deliberately do not

The candidates, and why four of the five lose:

| candidate | verdict |
| --- | --- |
| **Global log-bias `β`** | **ship first, hour one.** One number, converges by Game 10 (F6), worth +7–10 % of income (F3), and it is the only estimator that catches a units/VAT/gross-net bug — F0's cousin, and the most likely single defect in the whole pipeline. |
| **Isotonic on the _probability_ axis** | **ship second**, once ~300 labels exist. See §4.2. |
| Isotonic on the _price_ axis (`t̂ ↦ t`) | **loses.** It fixes the centre, which `β` plus per-trade shrinkage already fixes with 200× fewer parameters, and it cannot touch the width — which F3 says is the bigger half. Monotone in the wrong variable. |
| Quantile regression on `t̂` residuals | **loses on the loss function.** Pinball loss needs a point label; ours are interval-censored, and the censored variants (Powell, Portnoy) are a bad thing to implement at 02:00. §4.2 gets the same object without them. |
| Per-category `γ` | **only above 150 labels in a category** (~Game 25 at 12 trades). Below that it overfits — F4's `sd(η_k)` is still 0.089 at Game 20. Hierarchical shrinkage toward the global `γ`, never a free parameter. |
| kNN over description embeddings (Price Memory) | **build it, but as a prior, not the learner.** §4.4 — it is a bonus channel, not a dependency. |

### 4.2 The headline learner — isotonic recalibration on the censored PIT, with sharp bounds

Both of our decisions are **quantiles** (R4: `b = Q₁ᐟ₃`; R5b: `a` = argmax over `G(a)`). What we
need is not a better centre but a posterior whose quantiles mean what they say. Directly:

For a target level `τ`, realised coverage is `C(τ) = P(t ≤ F⁻¹(τ))`, and calibration means
`C(τ) = τ`. Since `F_i(t_i) ∈ [F_i(L_i), F_i(U_i)]`, the hit indicator `1{F_i(t_i) ≤ τ}` is
**known** unless `τ` lands inside that interval. So `C` is bounded, sharply:

```
Ĉ_lo(τ) = (1/n) · #{ i : F_i(U_i) ≤ τ }        # certainly a hit
Ĉ_hi(τ) = (1/n) · #{ i : F_i(L_i) ≤ τ }        # possibly a hit
                       C(τ) ∈ [Ĉ_lo(τ), Ĉ_hi(τ)]
```

Both are monotone step functions; fit `ψ` inside the band by PAVA (isotonic regression), and
deploy `b = F⁻¹(ψ⁻¹(1/3))`. No distributional family, no imputation of `t`, no fabricated
interval — the censoring shows up as a **band we report** rather than a bias we hide.

How much does censoring actually hide (**F5**, 3 400 items, posterior sd 0.30)?

| `τ` | Field awake: `Ĉ_lo` | `Ĉ_hi` | band | 50 % dark: band |
| --- | --- | --- | --- | --- |
| 0.10 | 0.068 | 0.105 | 0.037 | 0.073 |
| 0.20 | 0.162 | 0.234 | 0.072 | 0.129 |
| **0.333** | 0.274 | 0.374 | **0.100** | 0.202 |
| 0.50 | 0.429 | 0.552 | 0.122 | 0.244 |
| 0.90 | 0.875 | 0.926 | 0.051 | 0.106 |

Mean PIT-interval width **0.082** awake, 0.158 at 50 % dark. **92 % of the calibration curve is
point-identified**, and the ±0.05 band at `τ = 1/3` is narrower than the decision needs — R6
says the Limit is flat across `Q₀.₀₅–Q₀.₃₃`.

### 4.3 Where we agree with `strat-quant`, and where we do not

`strat-quant` §3.2 proposes fitting `(β, γ, δ₀, δ₁)` by MLE on interval-censored bracket mass.
**We adopt it, and we build it first**, because below ~300 labels a 4-parameter model beats a
nonparametric one and F6 says it converges by Game 10. Two disagreements, both concrete:

**(1) The objective is wrong.** Log-likelihood weights a €30 Line Item and a €2 000 one equally,
and we are paid in euros. Worse, **F3 row 3 vs row 4** shows two mis-specified parameters can
cancel into a better score than either fixed alone — a likelihood-optimal `θ` is not a
money-optimal `θ`, and the gap is 1.8 % of income in the awake phase. Fix: **fit by MLE, then
select the deployed `(β, γ)` by argmax of the counterfactual net** over a 21×21 grid on the last
K settled Games. `J` is piecewise constant in `θ` so gradient methods are wrong — a grid, exactly
as `strat-quant` argues for `J(a)` in its own §3.4. 441 replays of a few thousand rows is
milliseconds. Report both; **the gap between the likelihood optimum and the money optimum is
itself the diagnostic** that the posterior family is mis-specified.

**(2) One global `γ` cannot fix heteroskedastic width**, which `strat-quant` §7.3 concedes is its
real technical weakness. The isotonic band of §4.2 fits the whole shape and needs no family
assumption. So: a **staged learner**, an explicit bias–variance ladder with the switch points
decided now, in daylight:

| labels | estimator | source |
| --- | --- | --- |
| `n < 60` | prior only: `β = 0`, `γ = 2.0` | `strat-quant` §3.1, err wide |
| `60 ≤ n < 300` | 2-parameter censored MLE `(β, γ)` | `strat-quant` §3.2 |
| `n ≥ 300` | isotonic band on the censored PIT + net-selected `(β, γ)` | §4.2, §4.3 |
| `n_k ≥ 150` in a trade | per-trade `γ_k`, shrunk toward global | §4.1 |

Guardrails, non-negotiable: `γ ∈ [0.5, 4]`, `β ∈ [−0.7, 0.7]`, keep the previous `θ` on
divergence, **never carry `θ` across an R10 phase boundary without re-checking it**, and
`σ_floor = 0.18`.

### 4.4 Compounding — and what happens if Line Items never repeat

**This is the question that decides whether the flywheel is a strategy or a nice idea.** Decompose
our log-error into a global bias, a per-trade bias and irreducible item noise:

```
ln t̂ = ln t + β + η_k + ξ          β₀ = 0.18,  sd(η) = 0.25,  sd(ξ) = 0.34,  K = 12 trades
```

**F4**, 8 labels per Game, bracket measurement sd 0.021 (F1's p50 width over √12 — negligible):

| Game | labels | `sd(β̂)` | `sd(η̂_k)` | **σ** | vs G1 | `E[income]/t` | vs G1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0.180 | 0.250 | 0.459 | 100 % | 0.551 | — |
| 5 | 32 | 0.075 | 0.160 | 0.384 | 84 % | 0.580 | +5.3 % |
| 10 | 72 | 0.050 | 0.121 | 0.365 | 79 % | 0.589 | +6.8 % |
| **20** | 152 | 0.034 | 0.089 | **0.354** | 77 % | 0.594 | **+7.8 %** |
| **50** | 392 | 0.021 | 0.058 | **0.346** | 75 % | 0.598 | **+8.5 %** |
| **90** | 712 | 0.016 | 0.043 | **0.344** | 75 % | 0.599 | **+8.7 %** |

**Be honest about the shape: it is front-loaded and it saturates.** 84 % of the total gain
arrives by Game 20 and the curve is flat after Game 35, because it converges to the irreducible
item-level noise `sd(ξ) = 0.34`. **Anyone promising a posterior that keeps tightening through
Sunday morning is selling something.** What keeps improving after Game 35 is not `σ` — it is the
*calibration* of `σ`, the Field model, and the Cap.

**And if Line Items never repeat?** The flywheel still works, through four channels, ranked by
durability:

1. **Calibration (`β`, `γ`, the isotonic map).** Completely item-agnostic. Works if all 800 Line
   Items in the tournament are unique. **This is the dominant channel** and it is the whole of
   the F3 and F4 tables above — neither uses recurrence.
2. **Per-trade unit prices.** Descriptions differ; `€/h for Malerarbeiten` does not. Requires the
   `q · u · (1+τ) · κ` decomposition (`strat-quant` §3.1, `strat-adjuster` §3.5). There are only
   so many trades, so this channel cannot fail.
3. **Field and Cap.** `p(a)`, the acceptance curve, the Cap floor, the dark-team count — all
   item-agnostic, all from the same rows. Owned by `strat-metagame`; we supply the data.
4. **Exact-item memory.** Only if descriptions repeat. Highest value per hit, least likely.

The fourth channel is a **bonus, not a dependency** — and that is the strongest defensive claim
in this pitch. Priced (F4, a re-seen item's bracket truncates its own prior, collapsing sd to ~0.03):

| recurrence `r` | σ at G20 | σ at G50 | σ at G90 | `E[income]/t` at G90 | vs `r = 0` |
| --- | --- | --- | --- | --- | --- |
| 0 % | 0.354 | 0.346 | 0.344 | 0.599 | — |
| 10 % | 0.336 | 0.329 | 0.326 | 0.608 | +1.5 % |
| 25 % | 0.307 | 0.300 | 0.298 | 0.625 | +4.3 % |
| 50 % | 0.251 | 0.246 | 0.244 | 0.661 | **+10.3 %** |

`strat-quant` §3.5 files recurrence as an open hypothesis to test at Game 8. **We test it at
Game 4** — it is a string match over normalised descriptions across settled Games and costs
nothing — and we plan for `r = 0`. If `r` turns out high, we take the +10 % and say so.

### 4.5 How the learner is evaluated

Four diagnostics, all decision-relevant, all on the dashboard, all written from Game 1:

1. **Realised `Q₁ᐟ₃` hit rate** with its censoring band (§4.2). Calibrated ⟹ 1/3, measured at
   exactly the quantile we deploy. Target `[0.28, 0.40]` over a 20-Game window.
2. **`/performance` confusion matrix**, ours, per Game: `reviewed_accepted_wrong` vs
   `reviewed_penalties`. Free, needs no inversion, available from Game 1, and it is the fallback's
   backbone (§6.3).
3. **Predicted vs realised net**, per Game. If the posterior is right, the EV the optimiser
   claimed should match the money that arrived.
4. **The assertion set of §3.7.** Not a metric — an alarm.

Plus the release gate `strat-quant` states and we adopt verbatim: **nothing ships to the live loop
without a green counterfactual replay.** After ~17:00 there is a backtest, so there is no excuse
for shipping on vibes at 03:00.

---

## 5. Architecture, crash-safe state, and the build plan

### 5.1 Modules — the whole track is ~600 lines

```
wireclaim/feedback/
  invert.py      the R9 algorithm of §3. PURE: rows -> ItemInversion. No I/O, no clock.  [DONE]
  settle.py      pull settled Transactions + /performance, write the event log, invert
  memory.py      Price Memory: normalised description -> (t_doc, bracket, unit price)
  calibrate.py   the staged learner of §4.3; censored MLE, isotonic band, net-selection
  replay.py      counterfactual replay of a settled Game under any alternative (a, b)
  assertions.py  §3.7 — Guttman, reconciliation, lawyer ratio. Runs every Game.
```

`invert.py` is already written, tested against 600 synthetic Games and validated against real
Game 1. **It is a pure function with no dependencies, which is why it could be finished and
proven before the pipeline existed.** Everything else in this track consumes its output.

### 5.2 Crash-safe state — the 04:00 requirement

One invariant, and every design decision below follows from it:

> **All learned state is a pure function of an append-only event log.**
> Nothing is ever incrementally accumulated. A crash can lose the last fit; it can never
> corrupt one.

This is affordable precisely because the data is small: 100 Games × ~18 Line Items = ~1 800
labels for the whole tournament. Recomputing every parameter from scratch takes ~200 ms, so
there is no reason to ever hold mutable derived state. An EWMA that is updated in place is
**not** crash-safe — after a crash you cannot tell whether the last update was applied. Ours is
a windowed function of the log with recency weights computed from Game indices, which is the
same number and is idempotent.

**Layout.** One directory per Game, so a corrupt Game is a corrupt directory and nothing else:

```
runs/
  g001/
    submitted.jsonl      one line per POST ATTEMPT, written BEFORE the request, fsync'd
    parse.json           the Line Items we priced, with parse_confidence
    posteriors.json      mu, sigma, pi0, n_draws, rung, and t_doc if the documents stated it
    transactions.jsonl   raw settled rows, exactly as fetched, never edited
    performance.json     our /performance row: the free confusion matrix
    inversion.json       derived: brackets, recovered Charges, Limits, Cap, assertion results
    SETTLED              zero-byte marker, written LAST via atomic replace
  memory/labels.jsonl    append-only: one line per (canonical_key, game, bracket, t_doc)
  calib/current.json     the deployed theta. ADVISORY. Snapshot, atomically replaced.
```

**Write discipline.**

- **Append-only + `fsync` on the critical path.** `submitted.jsonl` is written and fsync'd
  _before_ the HTTP request, so a crash mid-POST leaves evidence of intent, not a mystery.
- **Atomic replace for whole-file state.** Write `tmp` in the same directory → `fsync` the file
  → `os.replace()` (atomic on POSIX) → `fsync` the directory. Never write in place. A truncated
  `current.json` at 04:00 is a silent, unbounded, undiagnosable error.
- **`SETTLED` is written last.** On boot, any Game with `transactions.jsonl` but no `SETTLED`
  is re-derived. `settle(game_id)` is a pure function of the raw rows, so re-running it is a
  no-op — **idempotent by construction, not by a flag.**
- **SQLite, if used at all, is a derived cache**, rebuildable from the JSONL in seconds
  (`journal_mode=WAL`, local disk only, never a network mount). The event log is the truth.

**Boot sequence — `runner --resume`, target under 10 s:**

1. Load the schedule (API, falling back to `data/schedule.json`).
2. `glob runs/g*/`, find the last Game with a `SETTLED` marker.
3. Rebuild memory and calibration from the event logs. ~1 800 labels: ~200 ms.
4. **If we are inside a submission window right now, emit the Fast Path immediately.** Do not
   wait for the learner. Ever.
5. Backfill missed settlements during the 11 min 38 s of dead time, rate-limited, oldest first.

**The invariant that keeps this track from ever hurting `strat-ops`:**

> **The learner may be arbitrarily stale without being wrong. The submitter may never block on
> the learner.**

`calib/current.json` is read once, at Game start, through a snapshot. Missing, corrupt, stale, or
from a different tournament phase — the engine falls back to the prior and submits. Calibration
is **advisory**. This is the concrete answer to `strat-ops` §8: this track cannot cost a Game.

**Off-box durability.** `rsync runs/ standby:` after every settlement. Free, one line, and it is
also the recovery path if the primary VPS dies at 03:00.

### 5.3 API etiquette — stated here because it goes in the write-up

Fair play forbids probing or overloading (README §6). Our budget, deliberately light:

- **One settlement pull per Game**, in the dead time, never during a submission window.
- 17 teams × ~2 pages, ~0.4 s apart: **~34 requests per 12.6 minutes**, less than opening the
  leaderboard page twice. Only endpoints the leaderboard page itself calls.
- Exponential backoff on any non-200, and a hard cap of 40 requests per Game.
- Nothing is fetched before a Game is `completed`.

### 5.4 Hour by hour — 5 devs

This track is **D5**, one dev, plus a claim on D4 after 20:00. `D1` loop/infra, `D2`
ingest/parse, `D3` elicitation, `D4` quant, `D5` feedback/ops/write-up.

| window | Games | deliverable | dev | done when |
| --- | --- | --- | --- | --- |
| **now → 15:40** | 1–3 | **F0 is landed in `README.md` R9.** Correct `a = amount/1.5` at the source, with the reconciliation table. Nothing else matters until it is done — every other track is about to build on it. | D5 | R9 corrected, team told in Discord |
| 15:40 → 16:30 | 3–7 | `settle.py`: pull, persist, invert, run `assertions.py`. Backfill Games 1–2. Post the recovered Field Charge table (§2.3) to the team. | D5 | `runs/g00N/inversion.json` for every settled Game |
| 16:30 → 17:30 | 7–12 | Event-log layout + `--resume` (§5.2). `memory.py` with `t_doc` extraction (§3.9). **Recurrence test at Game 4.** | D5 | kill the process mid-Game; it resumes clean |
| 17:30 → 19:00 | 12–19 | `calibrate.py` stage 2: censored MLE `(β, γ)`. First `θ̂` printed and **compared against `t_doc`**. | D5 | `β̂` with a standard error, at Game ~12 (F6) |
| 19:00 → 21:00 | 19–29 | `replay.py` counterfactual. Net-selection of `(β, γ)` over the grid (§4.3). Hand the Field data to `strat-metagame`. | D5 + D4 | replay reproduces our realised net to < 2 % |
| 21:00 → 00:00 | 29–43 | Isotonic band (§4.2). Per-trade `γ_k` if any trade has ≥ 150 labels. Dashboard: calibration band, bracket widths, dark-team count, `t_doc` vs bracket agreement. | D5 + D4 | `Q₁ᐟ₃` hit rate in `[0.28, 0.40]` over the last 20 |
| **00:00 → 08:00** | 43–81 | **Autonomy.** Auto-refit after each settlement, auto-revert on assertion failure, phase-boundary guard at 00:00 and 08:00. D5 takes the 02:00–04:00 watch and **sleeps the rest — a scheduled deliverable.** | 2 on rotation | zero missed Games, zero manual refits |
| 08:00 → 10:30 | 81–95 | Final `γ`. Freeze the learner at Game 95 — exploration off, no parameter changes. | D5 | last-20 net ≥ first-20 net, normalised |
| 10:30 → 12:00 | 95–100 | **Feature freeze.** Export the four figures (§7.4). Write-up finished. | D5 | submitted before 12:00 |

Two rules that override the table. **(a)** F0 before anything else — a wrong constant propagating
into four other tracks is worth more than every feature below it. **(b)** The write-up is written
continuously from 17:00, because README §5.6 is right and the failure mode is real.

---

## 6. Cold start, and the fair-play fallback

### 6.1 Games 1–5: what ships with zero labels

- **The prior**, from `strat-adjuster`'s knowledge base and `strat-quant`'s `γ₀ = 2.0`. Deliberately
  wide: R4b says an over-wide posterior costs a bounded `0.5a`, an over-narrow one is unbounded.
- **`t_doc`** (§3.9) — available at `T+2 s`, before any label exists, and on case 0 it was the
  whole answer.
- **The inverter, already built and already validated.** This is the point of writing `invert.py`
  as a pure function: it was finished, round-tripped on 600 synthetic Games, and run against real
  Game 1 **before the pricing pipeline existed**. There is no cold start for the loop itself — only
  for its inputs.
- **Game 1 is an instrumentation Game.** We are our own Rosetta stone: we know our own Charge
  exactly, so our own rows pin the semantics with zero assumptions. That is how F0 was found, and
  it is the first thing to re-run on Game 1 of any future tournament.

### 6.2 If we ever lose field-wide leaderboard data

**The organisers have since confirmed R9 is allowed** (README R9), so this is no longer an open
question — but it stays a live contingency for two reasons: the endpoint could be pulled or
rate-limited, and **K2 is the more likely trigger** — if the Field never straddles `t` (which is
what real Game 1 looks like, §7.2.1), field-wide data exists but carries no upper bound, and the
estimator below becomes the main line rather than the fallback. **So the data source is a flag,
not an architecture** — `settle.py --sources={field,own,self}`. Three tiers:

| tier | data | legality |
| --- | --- | --- |
| **T-A** | every team's Transactions | **confirmed allowed** by the organisers (README R9) |
| **T-B** | rows where we are Issuer or Reviewer | our own settled results — README's own stated fallback |
| **T-C** | our own Submissions + our own `/performance` row | unarguable |

**T-B has a structural problem, and it is a theorem, not a sampling artefact.**

> **Theorem.** Using only our own rows, the bracket on `t` is never two-sided while `a ≤ b`.
> _Proof._ A fair witness among the Issuers we rejected requires some `a_j ∈ (b, t]`, hence `b < t`.
> Our own Charge being a fraud witness requires `a > t`. With `a ≤ b`, `a > t` forces `b ≥ a > t`.
> The two conditions are mutually exclusive. ∎

Measured (**F1**): **0.0 % two-sided** in T-B, against 100 % field-wide — and a one-sided lower
bound on 62.7 % of items. Worse, feeding those one-sided bounds to the same censored MLE gives a
**badly biased** answer, because *which* bound we observe is determined by whether our own Estimate
was high or low. The censoring is informative and the likelihood is mis-specified (**F6b**):

| after Games | field-wide `β̂` / `γ̂` | own-only `β̂` / `γ̂` |
| --- | --- | --- |
| 10 | 0.180 / 2.00 | 0.000 / 3.00 _(pegged)_ |
| 40 | 0.160 / 2.00 | −0.020 / 3.00 |
| 60 | 0.180 / 2.00 | 0.000 / 3.00 |
| **truth** | **0.180 / 2.05** | **0.180 / 2.05** |

Field-wide converges by Game 10. Own-only converges on the wrong number and stays there. **The
naive fallback is worse than no fallback**, which is precisely R5c's lesson in a new place.

### 6.3 The correct fallback: a probit on our own design points

Stop trying to bracket `t`. The right observation is the **binary outcome we already control**:
_was our Charge in the Fair Zone?_ It is readable from our own rows on every Line Item any
Reviewer rejected us on — near 100 % overnight.

```
y_i = 1{ a_i ≤ t_i }        design point  x_i = ln a_i − ln t̂_i   (ours, known exactly)
P(y = 1) = 1 − Φ( (x_i + β) / σ )                     ← a probit with a scale parameter
```

Two-parameter MLE, correctly specified, no censoring bias. Its cost is **efficiency, not
correctness** (**F6**):

| label source | `I_ββ` | `I_σσ` | Games → `se(β)` | Games → `se(σ)` |
| --- | --- | --- | --- | --- |
| T-A field-wide bracket | 4.93 | 9.81 | **10.2** | **6.4** |
| T-C own bit, **no dispersion** (`a = 0.75 t̂`) | 2.71 | 1.11 | **never** | **never** |
| T-C own bit, mild spread .65–.95 | 2.77 | 0.90 | 62.4 | 237.6 |
| T-C own bit, designed spread .5–1.4 | 2.51 | 1.28 | **21.0** | **50.9** |

So, precisely: **the fallback costs ~2× the Games for the bias and ~8× for the width.** Bias is
still learned by Game 21, which is in time to matter. Width is learned by Game 51, which is in
time for the overnight harvest. **Graceful, not fatal** — and it agrees with `strat-quant` K3 and
`strat-metagame`, both of which call the probe grid mandatory in this world, for the same reason.

But note the first T-C row: **with a fixed Charge multiplier, neither parameter is identified at
all.** The design matrix is rank 1. Dispersion is not an optimisation, it is an identification
requirement, and it is not free — raising `a` from the R5b optimum to `1.0 × t̂` costs 25 % of net
(**F7**). Allocate ~20 % of Line Items to the probe grid, and only where `J(a)` is within 5 % of
its maximum.

Two things soften the fallback further, and both are free:

- **`/performance` gives our own confusion matrix every Game** — `reviewed_accepted_wrong` and
  `reviewed_penalties`. That is a direct, aggregate readout of whether our Limit is too high or
  too low, requires no inversion, and is unambiguously our own data. In real Game 1 the four active
  teams read: error404 6 wrong-accepts / 3 penalties, Codacabana 3 / 14, Non Deterministic 0 / 18,
  Alpha (dark) 0 / 27. **Alpha's 27 penalties are R7 in one number.**
- **`t_doc` (§3.9) needs no leaderboard at all.** Where the documents state the Fair Value, we
  have an exact label from our own Case files. If that shape is common, the fallback is barely
  a fallback.

**And the straddle, which we consider and reject.** One could manufacture two-sided own-only
brackets by deliberately setting `b < a` so that `t` sometimes lands in the gap. Priced (**F7**,
30 % dark):

| design (`a/t̂`, `b` quantile) | two-sided | median half-width | net | vs baseline |
| --- | --- | --- | --- | --- |
| R5b optimum, `Q₀.₃₃` _(deployed)_ | **0.0 %** | — | 0.2181 | — |
| R5b optimum, `Q₀.₁₀` | 3.9 % | ± 3.1 % | 0.2162 | −0.8 % |
| `0.90 · t̂`, `Q₀.₁₀` | 21.0 % | ± 8.9 % | 0.2037 | −6.6 % |
| `1.00 · t̂`, `Q₀.₀₅` | 39.5 % | ± 14.5 % | 0.1635 | −25.0 % |
| `1.30 · t̂`, `Q₀.₀₂` | 68.2 % | ± 26.6 % | 0.0492 | −77.4 % |

Row 1 confirms the theorem on 3 000 simulated items. **The straddle is real and it is too
expensive** — the probit gets the same parameters from one-sided bits at a fraction of the cost.
Worth recording that we priced it rather than assumed it.

---

## 7. Kill criteria and honest downside

### 7.1 Kill criteria — thresholds, clocks and fallbacks decided now

| | trigger | reading | action |
| --- | --- | --- | --- |
| **K1** | any assertion in §3.7 fails on a settled Game | our model of the game is wrong, or the API changed | **freeze `θ`, revert to the prior, page a human.** Do not refit on data we cannot explain. |
| **K2** | after 20 settled Games, fewer than 60 two-sided brackets | the Field is not straddling `t` (§3.8, and this is what real Game 1 looks like) | switch the learner to the T-C probit (§6.3), which needs only one-sided bits; enable the 20 % probe grid |
| **K3** | leaderboard data becomes unavailable or rate-limited (R9 itself is **confirmed allowed**) | — | `--sources=own`; ~2× Games for bias, ~8× for width (F6). Pre-planned, not a scramble. |
| **K4** | counterfactual replay shows a **frozen `θ`** beating the fitted one over 3 consecutive windows | the learner is fitting noise | ship the frozen `θ`, keep fitting in shadow, and **say so in the write-up** — an honest negative result reads better to QuantCo than a dressed-up loss |
| **K5** | settlement pull exceeds 40 requests in one Game, or any 429 | approaching the fair-play line | halve the poll rate; drop to 4 sampled teams (which still covers ~50 % of rows) |
| **K6** | `Q₁ᐟ₃` hit rate > 0.55 sustained over 20 Games | we are being farmed — someone is parked just under our Limit | `γ ← 1.5 γ`, cap `b ≤ 1.3 × median` until the refit stabilises. The recovered Charge table names who. |
| **K7** | Sunday 09:00 and the write-up is < 80 % done | style score at risk | D5 stops coding and writes |

### 7.2 The honest downside

**7.2.1 The synthetic bracket widths assume a Field that does not exist.** F1 models 30 active
teams. Real Game 1 had **17 teams, of which 13 were completely dark** — identical net of
`−8 273.70`, the signature of `a = b = 0`. So the informative Field is **four teams**, and the
consequence is visible in the real inversion: `t_hi = ∞` on 11 of 18 Line Items, no Cap event at
all. **The ± 3.5 % bracket of §2.1 is not what Saturday actually looks like.** The lower bound
`t_lo` is still recovered on 11 of 18 items and is still the tightest information anyone has, but
the two-sided bracket may be rare all tournament. K2 exists for exactly this, and the T-C probit
is the answer, which is why §6.3 is not merely a fallback — it may be the main line.

**7.2.2 This also contradicts README R10's phase table**, which puts Games 1–43 as "Field awake,
`b` probably generous". At Game 1, **76 % of the Field was dark at 15:00 on Saturday.** The three
regimes may be one long regime with a dark majority throughout. That is *good* for our net (R10:
`+t` to us, `−1.5t` to them, per dark team, per Line Item) and *bad* for the Overcharge, which
earns nothing against `b = 0`. The phase model should be driven by the **measured** dark-team
count — one number, published, exact — and not by the clock. We supply that number every Game.

**7.2.3 Uptime still dominates everything here, by an order of magnitude.** `strat-ops` puts one
missed Game at 9–13 Games' worth of the entire calibration edge. Nothing in this document changes
that ordering, and §5.2's advisory-calibration invariant exists to guarantee this track can never
cost a Game. **If forced to choose between an hour on the learner and an hour on the watchdog, the
watchdog wins.** This track slots in at README §5 priority 4, behind uptime, two-phase submit, and
the Estimate itself.

**7.2.4 The compounding curve saturates, and we should not oversell it.** F4: 84 % of the gain by
Game 20, flat after Game 35, asymptote at the irreducible `sd(ξ) = 0.34`. The pitch line "watch our
posterior tighten through the night" is only true until about 21:00. What genuinely keeps improving
overnight is calibration, the Field model, and the Cap — which is a less cinematic but more honest
slide.

**7.2.5 The learner can only fix errors that are systematic.** `β` and `γ` are global; the true
error is heteroskedastic. If every framing is wrong in the same direction on one exotic Line Item,
no amount of global rescaling repairs it, and the isotonic map does not either. `σ_floor = 0.18` is
a blunt patch. This is the same weakness `strat-quant` §7.3 admits and we inherit it whole.

**7.2.6 A Field that also reads the leaderboard closes the gap.** Everything here is available to
every team. Our edge is not access, it is that we will have built the inverter, validated it, and
found F0 — and, on the evidence of Game 1, that 13 of 17 teams have not submitted anything at all.

### 7.3 What would make me abandon this track

If by Game 25 the two-sided bracket count is under 60 **and** the T-C probit's `β̂` has not moved
outside `±0.05` **and** `t_doc` is readable on most items, then the leaderboard is telling us
nothing we cannot read off the Case documents, and D5 should go help D2 parse invoices. That is a
falsifiable condition with a date on it.

### 7.4 What we hand the judges

1. **F0**, as a slide: the published result, the two tests, the reconciliation table, the correction.
   _We were wrong in public and the data caught us in forty minutes._
2. The **calibration band** across 100 Games with its censoring bounds shown — the honest version of
   a reliability diagram.
3. The **recovered Field**: every team's Charge on every Line Item, and the fact that nobody found
   the ceiling at Game 1.
4. The **dark-team count** per Game against the clock — R10 measured rather than assumed, with the
   Saturday-afternoon surprise front and centre.

---

## Appendix — reproducing every number

```bash
python3 docs/brainstorm/sebi/strat-flywheel/invert.py            # F1–F7, ~28 s, stdlib only
python3 docs/brainstorm/sebi/strat-flywheel/invert.py --live 1   # F0 + F8 against real Game 1
```

| finding | what it says | where |
| --- | --- | --- |
| **F0** | `amount` is the Charge, not `1.5 ×` it. **README R9 is wrong.** | §0, `--live` |
| **F1** | one Game's bracket pins `t` to ± 3.5 % awake, ± 17 % at 80 % dark | §2.1 |
| **F2** | uncovered-item detection: 100 % precision and recall field-wide; 32 % precision own-only | §3.6 |
| **F3** | bias correction worth +7–10 % of income, width calibration +14–15 % | §2.2 |
| **F4** | σ falls 0.459 → 0.354 by Game 20 and then saturates at `sd(ξ)` | §4.4 |
| **F5** | 92 % of the calibration curve is point-identified despite censoring | §4.2 |
| **F6** | the bracket carries 99 % of a point label's information; the fallback costs 2×/8× | §2.1, §6.3 |
| **F7** | the straddle is real and costs 6.6–25 % of net; reject it | §6.3 |
| **F8** | 0 Guttman violations on 4 896 real rows — our model of the game holds exactly | §2.4 |
| **F9** | 13 of 17 teams dark at Game 1; the active Field under-charged by ~2× | §2.3, §7.2 |
