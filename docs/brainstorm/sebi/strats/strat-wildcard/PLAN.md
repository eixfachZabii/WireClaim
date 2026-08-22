# Strategy pitch — **The Wildcard**
### Close the loop on the scoreboard, not on the truth

> The contrarian slot. Assumes `README.md` (R1–R10) and `CONTEXT.md` as read. It does not
> re-pitch the machine (`strat-ops`), the Estimate (`strat-adjuster`), the posterior
> (`strat-quant`), the Field model (`strat-metagame`), the cockpit (`strat-warroom`) or the
> ADK wiring (`strat-adk-adjudication`). Everything below is orthogonal to all six.
>
> New results are numbered **X1–X13** to avoid colliding with R#, M#, F#.
> Numerics: `wild.py` … `wild6.py` beside this file (stdlib only; every table is reproducible).
> `game1.py` re-derives §0 from the four published Net values and nothing else.
> **All arithmetic in §0 is against real Game 1 data and is exact.**

---

## 0. Game 1 happened, and it settles three arguments

17 teams. **13 scored exactly `−8,273.70`** — the default Submission, to the cent, thirteen
times. Four teams submitted: `error404 ai +33,436.19`, `Bin busy +13,501.85`,
`Codacabana +13,441.28`, `Non Deterministic +5,683.04`. Four Line Items. Two Charges
recovered by inversion on Line Item 1: **81.96** and **35.53**, both in the Fair Zone, both
Wrongfully Rejected.

From those numbers alone — **no Transactions view, no per-Line-Item data, nothing but the
scoreboard** — the entire Game inverts. This is X1 (§3.1) applied for the first time:

| Quantity | Value | How |
| --- | --- | --- |
| Field's total Fair-Zone Charge volume, 4 Line Items | **5,515.80** | a dark team's Net is exactly `−1.5 × A_total` |
| Total Wrongfully Rejected volume `W` | **82,991.48** | `W = −2 × Σ net` (X1, exact) |
| … by the 13 dark teams | 71,705.40 | `13 × A_total` |
| … by the 4 awake teams | 11,286.08 | residual — and it reconciles to the cent |
| Fair Charge volume *offered* | 88,252.80 | `16 × A_total` |
| **Field acceptance rate `p̄`** | **5.96 %** | `1 − W / 88,252.80` |
| Acceptance rate *among the four awake teams* | **31.80 %** | `1 − 11,286.08 / (3 × A_total)` |
| `error404 ai`'s Fair-Zone Charge total | **2,291 – 2,383** | bracketed by X1; ~584 per Line Item |
| `Bin busy` / `Codacabana` | 1,119 – 1,244 | ~295 per Line Item |
| `Non Deterministic` | 659 – 798 | ~182 per Line Item |
| **Break-even Charge total** | **324 – 473** (81–118/Line Item) | Net = 0 |

**Three things are now settled, not argued.**

**(a) `p̄ = 6 %`. The Overcharge is dead on arrival.** R5's break-even is 25 %;
`strat-metagame`'s P1 prior was `S(1) = 0.66`, `m₅₀ = 1.8`. The measurement is **6 %** —
an order of magnitude below the prior, and a third of the way below even its P0 cold-start
number. R5c's guardrail (`p = 0` until measured) was right and should stay latched. Note the
two rates are *both* useful: `p̄ = 6 %` is what an Overcharge actually faces; `31.8 %` is what
it would face if the whole Field woke up. Neither reaches 25 % except in the second case.

**(b) The Field's error distribution right now is one atom: 76 % at the default.** Not a
lognormal, not a mixture of convention bugs — a spike at zero. Every subtlety below is
second-order to "submit a number". `strat-ops` is right and this document concedes the
priority order immediately.

**(c) Net is almost exactly linear in your own daring.** With 13 opponents at `a = 0`:

```
net_i  =  17·A_i  −  5,515.80  −  0.5·W_i          [X1, exact, Game 1]
             ↑           ↑            ↑
   your Fair-Zone    a constant   your own Wrongful
   Charge total      everyone     Rejections — and only
   × the team count  pays         3 opponents can charge you
```

The Limit was worth almost nothing in Game 1 (only 3 opponents ever invoiced anybody). The
Charge was worth everything. `error404 ai` beat `Non Deterministic` by **27,753** purely by
charging **3.2× more while staying fair**.

### 0.1 The VAT trap, priced on real data

The brief asked for the gross/net trap quantified. Here it is, on Game 1, holding the
winner's Estimate fixed and applying each convention error to it:

| Convention error | Factor | Game 1 Net | vs the winner |
| --- | --- | --- | --- |
| correct (gross, whole Line Item) | 1.00 | ~+32,800 | — |
| **net instead of gross** (forgot 19 % VAT) | ÷1.19 | ~+26,500 | **−6,960** |
| VAT applied twice (gross rate card × 1.19) | ×1.19 | ~+40,400 *if still fair* | +6,930 **or −41,700 if it crosses `t`** |
| **per-unit instead of Line-Item total, `q = 4`** | ÷4 | ~+3,000 | **−30,400** |
| **per-unit instead of Line-Item total, `q = 18`** | ÷18 | ~−4,700 | **−38,100** |
| going dark entirely | ×0 | −8,273.70 | −41,710 |

**X2 — the quantity error is 5.5× the VAT error, and 91 % as bad as not playing at all.**
The brief's hypothesis was that VAT is "the single largest exploitable error". It is not, and
the gap is not close. `÷1.19` costs 17 % of the winner's score; `÷q` costs 73–91 % of it. A
per-unit Charge on a `q = 18` Line Item scores **worse than the default Submission**.

And the ×1.19 error has an *ambiguous sign*: in a simulated Field (`wild2.py` W2) a team that
forgot VAT scored **+0.23 t better** than a correct team, because R5b already prescribes
charging ~0.7 × `t̂` and the VAT slip is a hedge in the same direction. It only turns
catastrophic when it goes the *other* way and pushes a Charge across `t` — the double-VAT row
above is a coin flip between +6,930 and −41,700, which is the real reason to care.

> **The one-line version: the ×1.19 is a rounding error; the ×q is the whole tournament.
> Spend the paranoia on the quantity column, not the VAT column.**

### 0.2 Do the observed Charges show a convention error? No — and here is the test

`81.96` and `35.53` on the same Line Item. If one team submitted gross and the other net, the
ratio would be **1.19**. If one submitted per-unit, the ratio would be the printed quantity —
an integer like 4, 8, 18, 25. The observed ratio is **2.307** (log-ratio 0.836). It matches
neither. Both teams' implied per-Line-Item averages (295 and 182) also sit in the same order
of magnitude as the winner's 584.

**Verdict: no evidence of a units or VAT convention error in the Game 1 data.** What the two
Charges show instead is **Estimate dispersion**: two teams pricing the same Line Item 2.3×
apart, i.e. `σ_log ≳ 0.6` between just two draws. That is the real Field defect, and it is the
one §3.4 attacks.

**The standing test (3 lines, run after every Settlement).** For every pair of recovered
Charges on the same Line Item, compute `ln(a_i / a_j)`. A convention-error Field produces a
*multimodal* histogram with spikes at `ln 1.19 = 0.174` and `ln q`. A merely-noisy Field
produces one smooth mode. Watch which one appears. **One histogram, and it decides whether
the whole convention-error thesis is real.** Right now the honest answer is: unproven,
one observation, smooth.

---

## 1. Headline

> **Everything we need to steer is already published on the scoreboard, in closed form.
> The two columns the leaderboard prints for every team — `income` and `costs` — invert
> algebraically into the Field's acceptance rate, every team's Fair-Zone Charge total, and
> our own Wrongful Rejection volume. From our own income alone we get a per-Line-Item bit
> telling us whether each Charge was above or below the secret `t`. Build two ~15-line
> controllers on that, and the pipeline self-calibrates against the truth it can never see.**

Two identities, both pure algebra from the payoff matrix, both verified exactly against
Game 1:

```
X1    Σ costs − Σ income  =  0.5 · (total Wrongfully Rejected Charge volume)
X2    income_i            =  (N−1) · A_i  +  F_i
                              where A_i = team i's Fair-Zone Charge total
                                    F_i = what it collected on accepted Overcharges
```

Why this is the contrarian bet: every other track closes its loop on **`t`** — a quantity we
never observe, that must be inferred from a PDF by a language model in 60 seconds, and whose
error is the single largest term in our Net. This track closes the loop on **the scoreboard**,
which is observed, exact, free, published every 12.6 minutes, and unambiguously inside fair
play. It does not replace the Estimate. It makes the Estimate's *bias* stop mattering.

The demonstration (§3.4, `wild5.py`): a pipeline whose `t̂` is **19 % too high** because it
grossed up an already-gross rate card scores `+0.95 t` frozen and `+2.09 t` with the
controller — **the controller more than doubles the Net of a broken pipeline, without ever
learning that it was broken.**

---

## 2. The idea catalogue

Ranked by (EV × confidence) ÷ build cost. "EV" is per unit of true Fair Value against the
simulated Field of `wild2.py` unless a Game 1 figure is given.

| # | Idea | Mechanism | EV | Build | Risk | Fair play |
| --- | --- | --- | --- | --- | --- | --- |
| **X1** | **Scoreboard Inversion** | `Σcosts − Σincome = 0.5·W`; `income_i/(N−1) = A_i` | **the `p̄` gate + `ā` benchmark**; Game 1 fully inverted from 4 numbers | **1.5 h** | none — it is arithmetic | **clean** (it is the leaderboard) |
| **X3** | **Fair-Rate Controller** | our own income identifies Fair vs Fraud per Line Item; Robbins–Monro on the Charge multiplier | lands on the oracle multiplier at σ ≤ 0.35; **+120 % of Net on a 19 %-biased pipeline** | **2 h** | mis-set target costs ~15 % | **clean** (our own score) |
| **X4** | **Convention Guard** | hard pre-Submission unit/gross assertions; the invoice is its own control group | **−38,100 in Game 1 terms** if it fires once | **2 h** | false positives clamp a good number | clean |
| **X5** | **Limit Alarm** | `W_us` from X1; Wrongful-Rejection share must sit in `[0.20, 0.40]` | detects a broken `b` in **one Game** (share 0.999 vs 0.311) | **0.5 h** | needs `N` | clean |
| **X6** | **50-line no-LLM baseline** | `qty × unit-rate-card × 1.19`, no model at all | beats the default by **41,700 per Game**; §4 | **2 h** | sits on the calibration cliff | clean |
| **X7** | **Saturation Escape** | 3 consecutive 100 %-fair Games ⇒ multiply the Charge by 1.6 | repairs an 18× units error in **6 Games**; −15.6 → −2.7 | **0.5 h** | costs ~2 t if left armed — arm Games 1–10 only | clean |
| **X8** | **Cap-floor option ladder** | `c = max(4t, F)` ⇒ break-even is `t/F`, not 25 %, on cheap Line Items | **+1.3 % … +3.7 %** of Net | 1.5 h | needs `F`; `p̄ = 6 %` currently kills it | clean |
| **X9** | **Round-number snapping** | the Field's `b` clusters on 50/100/500; charge `R − 0.01` | ~+1 % when Overcharging, 0 otherwise | **0.5 h** | none | clean |
| **X10** | **Policy-hash memo** | SHA-256 `policy.txt` on decrypt → reuse the whole coverage verdict | seconds of latency + consistency; unknown hit rate | 1 h | may never hit | clean |
| **X11** | **Repetition experiment** | measure the share of repeated Line-Item text after 10 Games | a **build-plan branch point**, not income | 1 h | none | clean |
| **X12** | **Endgame variance policy** | rank is a step function ⇒ terminal variance is free when behind | 8 %/26 %/47 % comeback odds at `p` = .10/.20/.30 | 1 h | only fires if we are close | clean |
| **X13** | **Rank-vs-Net Overcharge bar** | maximising rank, not Net, raises the bar by **1.02–1.18×** | a correction, ~0 income | 0.2 h | none | clean |
| **X14** | Archive metadata (`7z l`) | ZIP central directories are not encrypted — file names, sizes, CRC32 of *all 100 Cases* readable now | potentially decisive; unquantified | 0.5 h | reputational | **ASK THE ORGANISERS** |

Total build for X1+X3+X4+X5+X6+X7 — the six that matter — is **8.5 dev-hours**, one dev,
no dependency on the LLM pipeline, no dependency on the Transactions view.

---

## 3. The five developed

### 3.1 X1 — The Scoreboard Inversion

**Derivation.** Sum the payoff matrix over all ordered (Issuer, Reviewer) pairs. For each
pair, compare what the Issuer receives with what the Reviewer pays:

| Case | Issuer gets | Reviewer pays | difference |
| --- | --- | --- | --- |
| Fair, accepted | `a` | `a` | 0 |
| **Fair, rejected** | `a` | `1.5a` | **`0.5a`** |
| Fraud, accepted | `min(a,c)` | `min(a,c)` | 0 |
| Fraud, rejected | 0 | 0 | 0 |

Every row cancels except the Wrongful Rejection, so

```
Σ costs − Σ income  =  0.5 · Σ (Wrongfully Rejected Charges)   ≡  0.5 · W      [exact]
```

and, because a Fair-Zone Charge is paid by **every** opponent whether accepted or wrongfully
rejected (R1),

```
income_i  =  (N−1) · A_i  +  F_i          A_i = Σ_items a_i · 1{a_i ≤ t}
                                          F_i = accepted-Overcharge receipts ≥ 0
```

**Verification.** Handout worked example: `Σincome = 400`, `Σcosts = 500`, `W = 200` ✓;
`Alpha income 200 = 2 × 100` ✓. Simulated: max relative error **6.2 × 10⁻¹⁵** over 200 Games
with a mixed Field including Overcharges, Caps and uncovered items (`wild2.py` W1).
Real Game 1: reconciles to the cent (§0).

**What it yields, every Game, from four numbers:**

```python
# leaderboard rows: [(team, income, costs)] ; N = number of registered teams
SI, SC   = sum(r.income), sum(r.costs)
W        = 2 * (SC - SI)                       # Field's Wrongful Rejection volume  [exact]
p_bar    = 1 - W / SI                          # Field acceptance rate    [upper bound; see below]
A        = {r.team: r.income / (N - 1) for r in rows}   # every team's Fair-Zone Charge total
a_bar    = mean(A.values())                    # the Field's Charge level — the bar we must clear
W_us     = 2 * (costs_us - (SI - income_us) / (N - 1))  # OUR OWN Wrongful Rejection volume
```

**Two honest caveats.**

1. `p̄` uses `SI` where the denominator should be `SI − ΣF`. It is therefore an **upper bound**,
   biased optimistic by exactly `(1 − p̄) · ΣF / SI`. Measured bias in simulation: **+0.027**
   against a Field where accepted Overcharges were 5.4 % of income (`wild2.py` W1). Given R5c
   — a spuriously high `p` cost 60 % of Net — **apply the haircut and use `p̄ − 0.05` as the
   gate.** In Game 1 the gate reads 6 % and would read 1 % after the haircut. Either way: no.
2. `p̄` is volume-weighted at the Field's *own* Charge levels. It is a scalar, not the curve
   `p(a)`. It gates the aggression switch; it does not size the Overcharge. The curve still
   needs `strat-flywheel`'s Transactions inversion.

**Why this matters beyond convenience.** README R9 flags the Transactions inversion as
close enough to the fair-play line that we must ask first. **X1 needs none of it.** It reads
the two columns that constitute the scoreboard itself. If the answer in `#❓-ask-orgateam`
comes back *no*, R9's entire measurement programme collapses to X1 — and X1 still delivers the
acceptance rate, the Field's Charge level, and our own rejection volume. **This is the
insurance policy on the single largest open question in the repo.**

**Bonus — `N` for free.** On any Game where our Charges are certainly Fair (the Fast Path
deliberately lowballs Game 1), `N − 1 = income_us / Σ a_us` exactly. Three lines, and it
settles whether non-submitting registered teams count as opponents. Game 1 says they do:
`5,515.80 × 1.5 = 8,273.70`, the dark Net, to the cent.

---

### 3.2 X2/X3 — The Fair-Rate Controller

**The observation nobody has made.** A Fair-Zone Charge is paid by all `N−1` opponents. An
Overcharge is paid only by those who accept it. Therefore

```
income_from_item / (N−1)  ==  a     ⟺   a ≤ t     (Fair Zone)
income_from_item / (N−1)   <  a     ⟺   a >  t     (Fraud Zone)
```

**Our own income column is a per-Line-Item oracle on the sign of `a − t`.** Not a bracket, not
an inference — an exact bit, delivered every Game, for free, from our own scoreboard. Verified
consistent on **2,400/2,400** simulated Line Items (`wild5.py` A).

If the leaderboard reports income per Game rather than per Line Item, the graded form works
just as well:

```
φ  =  income_us / ((N−1) · Σ a_us)      ∈ (0, 1]        realised Fair share
φ = 1  ⟺  every Charge was Fair.   And with p̄ from X1:   s_fair ≈ (φ − p̄) / (1 − p̄)
```

**The controller.** R5b says the optimal Charge is a *quantile* of our posterior — `Q₀.₀₅` at
`σ = 0.15`, `Q₀.₃₇` at `σ = 0.60`. Equivalently: **we should be in the Fair Zone about 63–95 %
of the time**, decreasing in `σ`. That is a directly observable rate. So stop trying to hit
the quantile by getting `σ` right, and servo onto it:

```python
TARGET = {0.20: 0.90, 0.30: 0.85, 0.45: 0.78, 0.60: 0.68}   # from R5b, interpolated

def after_settlement(state, income_us, charges, N, game_index):
    phi = income_us / max((N - 1) * sum(charges), 1e-9)      # realised Fair share
    tgt = interp(TARGET, state.sigma)
    state.m *= exp(0.06 * (phi - tgt))                       # Robbins–Monro, log space
    state.streak = state.streak + 1 if phi > 0.999 else 0
    if state.streak >= 3 and game_index <= 10:               # X7 saturation escape
        state.m *= 1.6                                       # armed ONLY in the bug window
    state.m = clamp(state.m, 0.05, 60.0)
# and at Submission time:   a = state.m * t_hat
```

**Does it find the right multiplier?** (`wild5.py` B — ladder vs an oracle sweep)

| our σ | ladder settles at | oracle best | ladder Net | oracle Net |
| --- | --- | --- | --- | --- |
| 0.25 | 0.63 | **0.65** | +5.78 | +5.88 |
| 0.35 | 0.55 | **0.55** | +2.46 | +2.92 |
| 0.50 | 0.46 | 0.55 | −0.55 | −0.38 |

Exact at σ ≤ 0.35; it undershoots at σ = 0.50 because the target table flattens. Honest.

**The repair test — the reason this is the headline** (`wild5.py` C, 100 Games):

| our `t̂` carries | frozen `m = 0.70` | with the controller | change |
| --- | --- | --- | --- |
| no bias | +3.18 | +2.46 | −23 % (the cost of servoing) |
| **÷1.19 — net instead of gross** | +2.28 | **+2.52** | **+11 %** |
| **×1.19 — VAT counted twice** | +0.95 | **+2.09** | **+120 %** |
| ÷18 — per-unit (gentle ladder) | −15.74 | −15.61 | **+1 % — it fails** |
| ÷18 — per-unit (**with X7 escape**) | −15.74 | **−2.66** | **83 % of the damage recovered** |

Read the last two rows carefully, because they are the design:

- A **proportional controller repairs small convention errors** (the 19 % family) completely.
  A double-VAT bug stops being a bug.
- A **proportional controller cannot repair an order-of-magnitude error in time.** The Fair
  signal saturates at `φ = 1` — being 18× too low looks exactly like being 2× too low — and a
  6 %-per-Game multiplicative step needs ~50 Games to climb 18×.
- The **saturation escape (X7)** fixes that: three consecutive 100 %-Fair Games is proof we are
  far below `t`, so jump by 1.6× instead of nudging. Trajectory of `m` under an 18× error
  (`wild6.py` A): `0.71 → 1.81 → 4.64 → 11.87` by **Game 6**, settling near 17.5. Repaired in
  **76 minutes**.
- But the escape costs **~2 t** in the no-bug case if left armed (it drifts `m` up to ~1.0 and
  starts crossing `t`). **So: arm it for Games 1–10 only.** Ten percent of the tournament, in
  the window where an undiscovered units bug is both most likely and most expensive. After
  Game 10, disarm and let the gentle ladder run.

**Why the controller is genuinely different from what the other tracks build.**
`strat-quant` calibrates the posterior against recovered `t` brackets — it needs the
Transactions view, it needs enough settled Games, and it fixes *width*. X3 needs neither, works
from Game 2, and fixes **bias** — the failure mode a width calibration cannot see, because a
uniformly-19 %-high posterior is perfectly calibrated in width and perfectly wrong in level.

---

### 3.3 X4/X5 — The Convention Guard and the Limit Alarm

X3 handles ×1.19. Something else has to handle ×q, and it has to be a hard check, not a servo.

**X4 — the Convention Guard.** Four assertions between the pricing engine and the Submission
airlock. Every one is cheap, and every one encodes an error we have already priced:

```python
def guard(items, t_hat, memory):
    for it in items:
        # 1. GROSS, WHOLE LINE ITEM — the two rules the handout bolds
        assert t_hat[it.idx] >= it.qty * 0.9 * memory.floor_unit(it.unit), "looks per-unit"
        # 2. THE INVOICE IS ITS OWN CONTROL GROUP  (X4b)
        med = median(t_hat.values())
        if t_hat[it.idx] > 12 * med or t_hat[it.idx] < med / 25:
            flag(it, "outlier vs siblings"); t_hat[it.idx] = clamp_to_band(t_hat[it.idx], med)
        # 3. UNIT-PRICE SANITY — qty and unit are PRINTED (strat-adjuster F2), so this is free
        implied = t_hat[it.idx] / (it.qty * 1.19)                  # implied NET €/unit
        assert memory.band(it.unit, it.trade).lo <= implied <= memory.band(...).hi
        # 4. NEVER SUBMIT A BARE RATE-CARD NUMBER — the gross-up happens exactly once
        assert t_hat[it.idx] != memory.net_unit(it.kb_id), "un-multiplied, un-grossed"
```

Assertion 2 is the one nobody else has: **a misparse shows up as a Line Item wildly out of
line with its own siblings on the same invoice.** A Case's Line Items share a trade, a
property, a damage event and an order of magnitude. A `25` read as a quantity when it was a
position number, or a `q` applied twice, produces an item 20× its neighbours. That is a
free outlier detector with a sample size of 4–8, refreshed every Game, requiring no domain
knowledge and no history. In Game 1 terms, one caught misparse is worth up to **38,100**.

**X5 — the Limit Alarm.** X1 gives us `W_us`, our own Wrongful Rejection volume — a number we
otherwise never see. Normalise it:

```
rejection_share  =  W_us / (incoming Fair Charge volume)
                 =  W_us / ((Σ income − income_us) / (N−1))
```

Simulated behaviour (`wild6.py` B):

| our Limit | recovered `W_us` | rejection share | verdict |
| --- | --- | --- | --- |
| `b = Q₁ᐟ₃` (correct) | ±29 % (contaminated by our own accepted Overcharges) | **0.311** | healthy — this is what R4 *should* produce |
| `b` = per-unit bug | exact | **0.999** | **broken. One Game. Unmistakable.** |
| `b` = generous (`2.5 t̂`) | estimator diverges | 0.002 | we are eating Overcharges |

So: **it is an alarm, not an estimator, and its failure modes are themselves diagnostic.**
The rule is three lines and a Slack ping:

```
share > 0.60  →  the Limit is broken (units, or a zero t̂). PAGE SOMEONE.
share < 0.10  →  the Limit is too generous. Lower it.
0.20 ≤ share ≤ 0.40  →  R4 is working as designed. Do not touch it.
```

The `0.311` is worth dwelling on: it is what R4's `Q₁ᐟ₃` rule produces by construction, and
**the four awake teams in Game 1 collectively accepted 31.8 % of Fair Charge volume** — the
same number. Either the Field has independently landed on the `Q₁ᐟ₃` rule, or low Limits are
what a cautious LLM produces anyway. Both readings say the same thing about our Overcharge.

**X4c — `b` is a stop-loss, and the bound is provable.** Per Transaction our Reviewer cost is
`a` if accepted (and `a ≤ b`), `1.5a` if rejected *and Fair* (so `a ≤ t`), and `0` otherwise.
Therefore

```
reviewer cost per Transaction  ≤  max(b, 1.5·t)        [X4c]
```

Confirmed over 300,000 random draws, max violation `−0.006` (`wild2.py` W7). Consequence:
**a Limit below `1.5 · t̂` makes cap-parked exploitation structurally impossible against us** —
not unlikely, impossible, because we can never pay more than our own `b`. The README's "worst
case is an exploiter parked at the Cap" (R4b) is real but it is *bounded by a number we choose*.
That reframing is worth one line of code (`b = min(b, 1.5 * t_hat)`) and one slide.

---

### 3.4 X-cliff — Net is relative, and the cliff is at 1.4× the Field's σ

The most important thing my simulator found, and it is not a tactic — it is the objective
function everyone should be staring at.

**Against a Field of well-calibrated clones, every team's Net is negative** (−1.04 t each,
`wild3.py` B). That is R2 made concrete: the game is negative-sum, so in a perfectly played
tournament everybody loses the burn and the ranking is decided by noise. **Every euro of
positive Net is harvested Field error.** We do not make money by pricing well. We make money
by pricing *less badly than the Field*, and Game 1 says the Field's current error is 76 % of
it not playing.

Which sets up the number to watch. Sweeping our Estimate quality against the Field's
(`wild4.py` A/B, Charge at `0.70 t̂`, Limit at `Q₁ᐟ₃`):

| Field's σ | our σ at which Net = 0 | ratio |
| --- | --- | --- |
| 0.20 | 0.353 | 1.77 |
| 0.25 | 0.397 | 1.59 |
| **0.35** | **0.479** | **1.37** |
| 0.50 | 0.648 | 1.30 |
| 0.70 | 0.889 | 1.27 |

**X-cliff: we are profitable iff our posterior log-sd is under ~1.3–1.5× the Field's.** And the
slope is brutal (Field σ = 0.35):

| our σ | 0.20 | 0.25 | 0.30 | 0.35 | 0.40 | 0.45 | 0.50 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Net / t | +6.65 | +5.38 | +4.23 | +3.01 | +1.89 | +0.57 | −0.28 |
| % of best | 100 | 81 | 64 | **45** | 28 | **9** | −4 |

**Every 0.05 of log-sd is ~17–20 % of Net.** Merely *matching* the Field (σ = 0.35 vs 0.35)
already leaves 55 % of the achievable Net on the table.

Two riders, both important:

- **This cliff does not exist yet.** It comes from Reviewer costs against a Field that
  charges. With 76 % of Game 1 dark, our costs were near zero and *any* σ was profitable. The
  cliff is a Phase-2-and-later phenomenon. Track it: the day the Field wakes up, our required
  accuracy jumps discontinuously.
- **The Field's σ is measurable**, and X1 gives the cheap version: the dispersion of
  `A_i = income_i/(N−1)` across teams *is* the Field's Estimate dispersion at the Charge level,
  published every Game. In Game 1: four Charge totals of 2,337 / 1,182 / 1,178 / 727 — a
  log-sd of **0.53** across just four teams. We need σ < ~0.7 to be profitable against *this*
  Field. That is a low bar, and it is the single most encouraging number in this document.

---

### 3.5 X8/X12/X13 — three small structural results

**X8 — the Cap's absolute floor is a discount on the Overcharge, and it is steepest on the
cheapest Line Items.** The handout: `c ≥ 4t` *and never below an absolute floor*. So
`c = max(4t, F)`. R5's break-even at the Cap is `p > t/c`:

```
p*  =  t / max(4t, F)   =   min( 0.25 , t/F )
```

| `t` \ `F` | 100 | 200 | 500 | 1000 |
| --- | --- | --- | --- | --- |
| 10 | 0.100 | 0.050 | 0.020 | 0.010 |
| 25 | 0.250 | 0.125 | 0.050 | 0.025 |
| 50 | 0.250 | 0.250 | 0.100 | 0.050 |
| 250 | 0.250 | 0.250 | 0.250 | 0.250 |

**R6c ("always charge on uncovered items — it is free") is the `t = 0` endpoint of a
continuum.** Every Line Item with `t < F/4` carries a discounted option, and the discount is
`t/F`. That converts `strat-metagame`'s "probe on the lowest-EV item" from an *exploration
cost* into a *steady-state policy*: rank each Case's Line Items by `t̂` ascending and take the
option on the cheapest. Worth **+1.3 % to +3.7 %** of Net at `F = 150` (`wild4.py` C).

**Currently switched off.** At `p̄ = 6 %` even a `t/F` of 0.05 is marginal. This is a
Phase-2 idea that arms itself automatically when X1's gate opens.

**X12 — endgame variance, and why the obvious version fails.** Rank pays a step function:
2nd by €1 and 5th pay the same. So when behind at Game 95, buy variance — and R5 says the
downside is *exactly bounded*, because a rejected Overcharge costs zero, so an all-in costs at
most our forgone Issuer income and never touches our Reviewer costs.

The trap is that it does not work the way you would model it (`wild2.py` W4, 5 Games left,
29 opponents, all-in at the Cap):

| Field's Limits | `p` | mean | **sd** | P(all-in beats honest) |
| --- | --- | --- | --- | --- |
| independent | 0.20 | 4.00 | **0.66** | 6 % |
| independent | 0.30 | 6.00 | 0.76 | 90 % |
| **common factor** | 0.20 | 3.97 | **3.22** | **26 %** |
| **common factor** | 0.30 | 5.99 | 3.69 | 47 % |

With 29 *independent* opponents the law of large numbers destroys the variance you were
trying to buy — the gamble becomes a deterministic EV comparison and is simply worse. The
gamble only exists because the Field's Limits are **correlated**: same LLMs, same prompts,
same public sources, one shared consensus. **The correct model of an endgame all-in is one bet
against the Field's consensus, not 29 independent bets** — and that is the version that offers
a 26 % comeback for a ~20 % cost over the last five Games. Rule: fire only if the leaderboard
gap to the rank above us is under ~1.5 Games' income at Game 95, and never when ahead.

**X13 — the Overcharge bar is higher for rank than for Net.** Per opponent, in the Fair Zone
the relative swing is `2a` if accepted and `2.5a` if wrongfully rejected (R8); in the Fraud
Zone it is `2·min(a,c)` if accepted and `0` otherwise. Setting them equal:

```
Net-optimal:    min(a,c) · p(a)  >  t
Rank-optimal:   min(a,c) · p(a)  >  t · (1.25 − 0.25 · p_fair)
```

so the bar rises by **1.02× to 1.18×** depending on how often our Fair Charges are accepted.
At `c = 4t` the classic 25 % becomes **26–29 %**. Small, but it points the same way as
everything else in this document: **the Overcharge is worth less than it looks.** R8's claim
that "both objectives are maximised at `a = t`" is right for the Fair Zone and silent about
the Fraud Zone; this is the missing half.

---

## 4. The 50-line no-LLM baseline

Taken seriously, because Game 1 says it would have finished **2nd of 17**.

```python
# panic.py — stdlib only. No LLM, no network beyond fetch-key and submit.
import re, statistics as st
RATE = {'m2':60,'m²':60,'sqm':60,'lm':25,'lfm':25,'m':25,'h':85,'std':85,'hour':85,
        'stk':45,'pcs':45,'pc':45,'st':45,'ea':45,'psch':150,'pauschal':150,
        'l':18,'kg':12,'day':70,'tag':70,'km':1.2,'set':120,'pkg':60}      # GROSS €/unit
KEY = [(r'entsorg|disposal|waste|abfall',            0.5),
       (r'demont|remove|abbruch|rückbau|strip',      0.6),
       (r'anfahrt|travel|call-?out|kleinmaterial',   0.4),
       (r'parkett|parquet|fliese|tile|naturstein',   1.6),
       (r'laminat|laminate|vinyl|teppich|carpet',    1.0),
       (r'maler|paint|lackier|tapez|spachtel|putz',  0.7),
       (r'elektr|electric|sanit|plumb|heiz|install', 1.4),
       (r'gerüst|scaffold|trockner|container|miete', 0.8)]

def unit_rate(desc, unit):
    r = RATE.get(unit.lower().strip('. '), 45.0)
    for pat, mul in KEY:
        if re.search(pat, desc, re.I): return r * mul
    return r

def price(items, memory, m=0.75):        # items: [(idx, desc, qty, unit)]
    t = {}
    for idx, desc, qty, unit in items:
        k = re.sub(r'[^a-z]+', ' ', desc.lower()).strip()
        t[idx] = (memory.get(k) or unit_rate(desc, unit)) * qty     # ALWAYS × qty
        t[idx] = max(t[idx], 15.0)
    med = st.median(t.values()) or 1.0
    for idx in t:                                    # X4b: the invoice is its own control
        t[idx] = min(max(t[idx], med / 25), 12 * med)
    out = {}
    for idx, ti in t.items():
        a = round(m * ti, 2); b = round(0.80 * ti, 2)
        out[idx] = {'a': snap(a), 'b': snap(b)}      # X9: land just under a round number
    return out

def snap(x):                                         # 1000 → 999.99, 487 → 487.00
    for R in (1000, 500, 100, 50):
        if 0 < R * round(x / R) - x < 0.03 * x: return R * round(x / R) - 0.01
    return x

def learn(memory, income, charges, N, state):        # X3, five lines, runs at Settlement
    phi = income / max((N - 1) * sum(charges.values()), 1e-9)
    state['m'] *= 2.718 ** (0.06 * (phi - 0.82))
    state['streak'] = state['streak'] + 1 if phi > 0.999 else 0
    if state['streak'] >= 3 and state['g'] <= 10: state['m'] *= 1.6
    state['m'] = min(max(state['m'], 0.05), 60.0); state['g'] += 1
```

That is 49 lines, and **the last function is the one that matters.** A rate card alone is a
static guess with `σ ≈ 0.5–0.65` — squarely on the wrong side of the X-cliff once the Field
wakes up. A rate card *plus* the Fair-Rate Controller servos its own level onto the Field's,
and the level is where the money is (§0c).

**Where would it place?**

- **In Game 1's regime: 2nd of 17, with high confidence.** Break-even was a Charge total of
  324–473 across 4 Line Items — about **81–118 per Line Item**. A rate card keyed on the *printed*
  `QTY` and `UNIT` (`strat-adjuster` F2 — the hardest half of pricing is handed to us) does not
  plausibly land below 118 per Line Item on real German trade work. `Non Deterministic` scored
  +5,683 at ~182 per item; `Bin busy` and `Codacabana` scored ~+13,470 at ~295. The baseline
  should land near the 295 cluster and clear **+13,000 per Game**, versus −8,274 for going dark.
- **Once the Field wakes: mid-field, and possibly negative.** At Field σ = 0.35 a σ = 0.55
  estimator nets ≈ −0.4 t. The baseline's insurance value is real and its ceiling is low.
- **The honest framing: it is the floor, not the plan.** It is worth ~41,700 per Game against
  the default (Game 1, measured) and roughly *nothing* against a good pipeline that never
  misses. Given `strat-ops`'s 71 % break-even uptime, that trade is obviously correct — but it
  is an argument for building it in two hours and never touching it again, not for making it
  the strategy.

---

## 5. What I rejected, and why

**The Field's Limit vector is a mixture of convention modes, so price against the mixture.**
This was my intended headline. I built it, and it is **wrong — or rather, true and worthless.**
Sweeping the optimal `(a, b)` against a clean Field of clones versus a Field contaminated with
six convention-error modes (`wild3.py` B/C):

| Field | best Net | at |
| --- | --- | --- |
| clean | −1.04 | `a = 0.7 t̂`, `b = 0.9 t̂` |
| mode-mixture | +4.00 | `a = 0.7 t̂`, `b = 1.0 t̂` |

**The mixture changes the *level* of our Net by 5 t and the *argmax* by essentially nothing.**
Knowing the Field's error modes tells us how much money there is; it does not tell us to
submit different numbers. That is README **R4b** ("the threshold is distribution-free; only
calibration matters") independently rediscovered and now extended to the Charge as well as the
Limit. Anyone about to spend a day building a Field mode-classifier should read this table
first. *(It survives as a pitch artefact — a measured error autopsy of ~17 automated claims
handlers is a QuantCo slide — but not as a lever.)*

**A bonus that falls out: R4 survives contamination.** In the same sweep, the optimal Limit
multiplier at σ = 0.25 was **0.90**, and `Q₁ᐟ₃` of a lognormal is `exp(−0.4307 × 0.25) =`
**0.898**. R4's rule reproduces itself to three digits under a structurally mis-specified
Field. That is a stronger endorsement of R4 than its own derivation, because it did not assume
the Field's shape.

**Overcharging as a strategy.** `p̄ = 6 %`. The break-even is 25 %, or 26–29 % on the rank
objective (X13). Even the four awake teams only reach 31.8 % — and that is the *ceiling* the
Field would have to hold at while we push above `t`. Against that, R5c's warning (a
mis-measured `p` cost 60 % of Net and dropped 1st → 11th) plus a negative-sum game plus a
methodology score judged by a company that sells fraud detection, and the answer is: **honest
Charging at the top of the Fair Zone, plus R6c on uncovered items, and nothing else.** I am
the contrarian slot and my contrarian position is that the Overcharge is over-rated. The one
exception is R6c, where `t = 0` makes it free and the break-even is `p > 0`.

**"Submit five times per Game instead of twice."** `strat-ops` owns the submit ladder and the
per-Line-Item merge; a third and fourth Submission is a config change in their loop, not a
strategy. Handed over, not pitched.

**Detecting Case repetition from pre-published archive metadata (X14).** ZIP central
directories are **not** encrypted — `7z l` on a password-protected `.zip` lists file names,
uncompressed sizes and CRC32 without the password. If the Case folder is published in advance,
that yields, for all 100 Cases, before any of them open: which Cases contain `images.png`,
how large each `invoices.pdf` is, and — via CRC32 collision — **which Cases share a
byte-identical `policy.txt`**. It is local inspection of a file we were legitimately given,
using a standard tool, touching no key and no API. It is also plainly *pre-release information
about an encrypted Case*, which is what the encryption exists to prevent.

**Verdict: do not build it. Ask in `#❓-ask-orgateam`, and describe it precisely** ("the ZIP
format leaves the file list and CRCs in the clear; is reading them before release acceptable?").
Asking costs nothing and is what the rules instruct. There is a strictly-clean subset that
needs no ruling and captures much of the value — **X10**: hash `policy.txt` *after* we decrypt
it, and memoise the coverage verdict against that hash. If the generator reuses policies, a
repeat Case resolves its entire coverage gate in microseconds from a hash lookup, with
guaranteed consistency across regenerates (ADR 0001's "two regenerates must not disagree",
achieved by construction). **Build X10. Ask about X14. Assume the answer is no.**

**A separate `b`-controller mirroring X3.** I wanted one and the algebra does not support it.
`W_us` is recoverable (X5) but its decomposition into "we rejected fair claims" versus "we
accepted Overcharges" is not — that genuinely needs the Transactions view. X5 therefore ships
as an alarm with three thresholds, not a servo. Stated so nobody spends an afternoon
rediscovering the obstruction.

---

## 6. The 24-hour build plan

One dev. 8.5 hours of real work. Nothing here blocks or is blocked by the LLM pipeline; the
only dependency is a working Submission path and the ability to read the leaderboard.

| Slot | Hours | Build | Done when |
| --- | --- | --- | --- |
| **Now → +2 h** | 2.0 | **X6 baseline** `panic.py` + **X4 Convention Guard** | `panic.py` prices Case 0 with no network; all four assertions fire on hand-made bad input |
| **+2 → +3.5 h** | 1.5 | **X1 Scoreboard Inversion** — poll the leaderboard once per Settlement, store `(game, team, income, costs)`, emit `W`, `p̄`, `A_i`, `ā`, `W_us` | Game 1's four numbers reproduce §0's table exactly. **This is the acceptance test and it is already runnable.** |
| **+3.5 → +4 h** | 0.5 | **X5 Limit Alarm** on `W_us` | alarm fires on a deliberately broken `b` in one Game |
| **+4 → +6 h** | 2.0 | **X3 Fair-Rate Controller** + **X7 escape**, state in one JSON file, disarm at Game 10 | replay against settled Games shows `m` converging; a synthetic ×1.19 bias is repaired |
| **+6 → +7 h** | 1.0 | **X10 policy-hash memo**, **X9 round-number snap** | hash hit reuses a stored coverage verdict; snapped Charges land at `R − 0.01` |
| **+7 → +8 h** | 1.0 | **X11 repetition experiment** (report only) at Game 10 | one number: share of Line Items whose normalised text we have seen before |
| **+8 → +8.5 h** | 0.5 | **X12 endgame rule** + **X8 cap-floor ladder**, both behind flags, both defaulting **off** | flags exist; `p̄` gate wired; nothing fires |
| **Sat evening** | — | **Ask `#❓-ask-orgateam` about X14** and about R9 | an answer, or an explicit "assume no" |

**Ordering rationale.** X1 first among the analytics because it is the only thing here that
also *insures* another track: if R9's Transactions inversion is ruled out, `strat-flywheel`
loses its measurement channel and X1 becomes the Field model. X3 second because its value
compounds with every Game it runs. Everything after +6 h is optional.

**What I need from the other tracks:** the Submission path (`strat-ops`), `t̂` and `σ` per Line
Item (`strat-adjuster` / `strat-quant`), `N`, and the ability to read the leaderboard at
browser rate. Nothing else. If all of that slips, `panic.py` still submits.

---

## 7. Kill criteria and honest downside

**Kill criteria — decided now, in daylight.**

| # | Check | When | Threshold | Action |
| --- | --- | --- | --- | --- |
| K1 | X1 reproduces a settled Game's numbers | Game 3 | any mismatch > 0.1 % | **kill X1 and everything downstream.** The algebra is exact; a mismatch means the leaderboard's columns are not what we think, and every derived number is void |
| K2 | X3's `φ` is neither always 1 nor always < 1 | Game 8 | `φ = 1` for 8 straight *and* the escape did not fire | the Fair signal is degenerate (we are far below `t`) — fall back to the rate card and X4 |
| K3 | X3's multiplier `m` | continuously | leaves `[0.3, 2.0]` after Game 15 | freeze `m`, page a human. Post-Game-10 drift that large means the input `t̂` is moving, not the Field |
| K4 | X5 rejection share | every Game | > 0.60 | the Limit is broken. Set `b = t̂` and investigate |
| K5 | X1's `p̄` | Game 30, 60 | < 0.20 | the Overcharge stays latched off — including R6c's sizing, which shrinks toward the floor |
| K6 | Net contribution of X3 vs frozen `m` | Game 40 | replay shows X3 losing | disarm the controller, keep the measurement |

**Honest downside, in five parts.**

1. **X1 and X2 are algebra; everything else is my simulator.** The identities cannot be
   wrong — they follow from the payoff table in four lines and they reproduce Game 1 to the
   cent. The EV figures (the cliff, the mode-mixture null result, the endgame odds, the
   convention-error costs) all come from `wild2–6.py` with a Field I invented. **Treat the
   identities as facts and the euros as illustrations.** Where a claim is speculation, I have
   said so; the mode weights in the simulator are the largest single act of invention in this
   document and Game 1 already shows they were wrong in the direction of optimism (17 % dark
   assumed, 76 % observed).
2. **X3 costs 23 % of Net when nothing is broken.** The servo is insurance with a premium.
   It pays for itself only if there is a bias to repair — and we cannot know whether there is
   until it has run. If the pipeline is clean, we have paid a quarter of our Net for nothing.
   K6 exists to catch this, but K6 fires at Game 40, by which point the premium is paid.
3. **The Fair signal needs `N` and needs our own income to be attributable.** If income is
   published only cumulatively, we difference successive snapshots and lose precision. If the
   leaderboard rounds, `φ`'s "= 1" test needs a tolerance and the escape rule gets noisier.
   Neither is fatal; both make the controller slower.
4. **The escape rule is the most dangerous thing here.** It multiplies our Charge by 1.6 on
   evidence that is only three Games deep. Armed outside Games 1–10 it drifts us across `t` and
   costs ~60 % of Net. It is guarded by a game-index check, and that check is one line that
   somebody could delete at 04:00. It should be a constant in a config file with a comment.
5. **Nothing in this document estimates `t`.** That is deliberate — it is `strat-adjuster`'s
   job and it is the largest term in the score. This track makes a *biased* Estimate stop
   mattering and tells us where the Field's Estimate sits. It cannot make a *wide* Estimate
   narrow, and §3.4 says width is worth 17–20 % of Net per 0.05 of log-sd. **If forced to
   choose between this whole plan and one dev tightening the posterior, take the posterior.**

**The one-sentence version.** Everyone else is trying to guess a secret number; the scoreboard
already tells us, exactly and for free, whether last Game's guess was too high or too low —
so build the two controllers that listen to it, put a hard unit check in front of the
Submission, and spend the rest of the weekend making the Estimate narrower.
