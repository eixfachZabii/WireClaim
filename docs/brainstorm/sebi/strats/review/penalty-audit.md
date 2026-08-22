# The wrongful-rejection fees: the cliff is one Line Item, and the fix is not the ceiling

Audit of `LIMIT_CEILING` and the 162,965 of wrongful-rejection penalties, at Game 27.
Everything is euros through `scripts/replay_payoffs.py`; reproduce with

```bash
PYTHONPATH=. pixi run python scripts/penalty_audit.py all --through 27
```

Owner of this document: no code was changed. `src/pricing.py` belongs to another agent;
this is a recommendation with the euros behind it, precise enough to hand over.

---

## TL;DR

1. **The cliff is one Line Item.** The reported "0.35 → 0.40 costs 17,492 over six Games"
   is, at 0.01 resolution, a **0.37 → 0.38** step of −17,591 of which **Game 22 item 1 is
   −19,892 (109%)**. Leave Game 22 out and the same step is **+1,592** — a gain. Game 22 has
   exactly one Line Item, its Fair Value is under 245.70, our estimate's median was 5,400,
   and **ten opponents charged exactly 2,000.00**. The cliff is our Limit crossing a cluster
   of placeholder Charges on one item where the estimator failed by 22×.
2. **But the previous audit's conclusion about *levels* survives, for a better reason than
   the cliff.** At our estimate quality the best single ceiling in 0.05–2.00 is worth
   **+300 over 27 Games** — 0% of the 216,179 of oracle headroom. There is nothing for a
   level to discriminate on.
3. **`LIMIT_QUANTILE` binds on 0 of 320 Line Items.** It is decorative. The shipped rule has
   one knob, not three.
4. **A ceiling cannot bound what we pay, because it is a multiple of the number that broke.**
   Proven out of sample by **Game 29**, which settled while this was being written: median
   7,138 against a Fair Value under 57.30, thirteen opponents at exactly 2,000.00,
   `b = 0.30 × 7,138 = 2,142`, and the *shipped* strict ceiling bought all thirteen for
   **24,157 of pure loss**.
5. **Recommendation: add a hard euro cap on the Limit, then let the ceiling be loose.**
   `LIMIT_CAP = 12 × SETTLED_MEDIAN = 708` and `LIMIT_CEILING = 0.70` (from 0.30). Worth
   **+17,525 over 27 Games**, +7,414 over 21–27, +10,111 over 1–20, and **+21,289 on Games
   28–29, which were not used to choose it**. Positive in 7 of 7 independent estimator draws
   and 27 of 27 leave-one-Game-out folds. **If only one change is acceptable, ship the cap
   alone and leave the ceiling at 0.30**: +4,203 over 27 Games, +24,000 on the held-out two,
   and no existing constant touched.
6. **The 54,322 is not recovered and mostly cannot be by any Limit.** Move the estimate a
   quarter of the way to the truth and the best ceiling jumps from +300 to **+134,459**. The
   cap reaches ~8% of the 27-Game headroom. It bounds a known failure; it does not fix the
   estimator.

---

## 0. The harness agrees with your arithmetic exactly

Replaying our real submissions over Games 19–27:

| | this audit | your figure |
|---|---:|---:|
| income | 260,245 | 260,245 |
| paid on accepted claims | 11,110 (10,499 fair + 611 over) | 11,110 |
| wrongful-rejection penalties | 162,965 | 162,965 |
| net | +86,170 | +86,170 |

and `2/3 × 162,965 = 108,643`, so the saving ceiling is **54,322**. Every Game 1–27 replays
to its published net to the cent.

Two provenance notes:

* **Games 27+ are scored here for the first time.** They have no
  `var/evidence/case_NN_model.json`, which is why every earlier sweep stopped at 26.
  `var/decisions/game_0NN.json` records the *blended* band that actually decided the number,
  and `price(that band, Params())` reproduces the shipped `(charge, limit)` **to the cent for
  all 31 logged Line Items of Games 26, 27, 28, 29 and 42**. That is asserted on every run
  (`check_decision_logs`). It is stronger provenance than the model cache, not weaker: the
  logged band *is* the input to `price_item`, not a reconstruction of it.
* **`--through` pins the window.** A Game settles every 12.6 minutes; Games 28 and 29 landed
  mid-session. They are excluded from every total and reported separately as held out.

---

## 1. The cliff, decomposed

### First, the previous audit's exact number, split by Game

Reproducing `limit_audit.py`'s cell exactly — same window (21–26), same evidence source
(`var/evidence/case_NN_model.json`), same constants:

```
0.35 → +14,720      0.40 → −2,772      step = −17,492      ✓ matches the published figure
```

and that −17,492 splits over the six Games as

| G21 | **G22** | G23 | G24 | G25 | G26 |
|---:|---:|---:|---:|---:|---:|
| −47 | **−19,892** | +114 | +879 | +989 | +466 |

**One Line Item in one Game supplies −19,892 of a −17,492 step. The other five Games sum to
+2,400 — they prefer the looser ceiling.** This reconciliation runs on every invocation
(`reconcile_limit_audit`, section 1z) and asserts the match against the published figure, so
it cannot silently drift.

### At 0.01 resolution the step is not even where it was reported

Over Games 21–27, the cliff is at **0.37 → 0.38**, not 0.35 → 0.40. A 0.05 grid cannot tell
a cliff from a ramp:

| ceiling | net | Δ | penalty | pay_over |
|---|---:|---:|---:|---:|
| 0.35 | 22,663 | +248 | 116,259 | 6,519 |
| 0.36 | 20,968 | −1,695 | 115,667 | 8,412 |
| 0.37 | 21,239 | +271 | 112,940 | 9,050 |
| **0.38** | **3,648** | **−17,591** | 111,714 | **27,050** |
| 0.39 | 3,999 | +351 | 110,662 | 27,050 |
| 0.40 | 4,363 | +364 | 109,570 | 27,050 |

Note that `pay_over` is flat at 27,050 from 0.38 to 0.40: the whole step is one discrete
event, not a trend. Per Game over 21–27 the 0.35 → 0.40 step of −18,301 splits as:

| G21 | G22 | G23 | G24 | G25 | G26 | G27 |
|---:|---:|---:|---:|---:|---:|---:|
| −47 | **−19,892** | +114 | +879 | +989 | −343 | 0 |

Per Line Item, 18 of 48 items move at all, and one carries **109%** of the step. Jackknifed:

| dropped | step | dropped | step |
|---|---:|---|---:|
| −G21 | −18,254 | **−G22** | **+1,592** |
| −G23 | −18,415 | −G24 | −19,180 |
| −G25 | −19,290 | −G26 | −17,958 |
| −G27 | −18,301 | | |

### The item

```
G22, one Line Item.  t ∈ [0, 245.70).  our median 5,400 (band 3,900–7,500), coverage 0.97.
Charges: makalu 0 · Claims Renaissance 245.70 · AsianSuperNerds 990 · harissa eagles 1,035
         Codacabana 1,559 · us 1,855 · error404 ai 1,892
         Alpha, Non Deterministic, Nullpointer Naan, OPUSMOPUS, Oasis, TBD,
         TakeTheMoneyAndRun, Trust Nobody, eyay  →  2,000.00 each
         Teamers → unrecoverable
```

`0.37 × 5,400 = 1,998 < 2,000` → reject all ten. `0.38 × 5,400 = 2,052 ≥ 2,000` → buy all
ten, 20,000 of pure loss. This is precisely the artefact `src/pricing.py` warns about
("the Field's Limits are clustered … any peak found there is a fact about sixteen specific
opponents"), with the Field's *Charges* clustered instead.

### It is not a one-off, and that is what makes it actionable

Counting every Charge above 500 euros in the record:

| charge | rows | Games |
|---:|---:|---|
| **2,000.00** | **28** | G7, G8, G22, G28, G29 |
| 600.00 | 7 | G2, G7, G8, G9, G12 |
| 3,848.48 | 4 | G19 |
| 834.04 | 3 | G5, G11, G26 |

`2,000.00` is the most common large Charge in the tournament by a factor of four. It looks
like a self-imposed cap several teams apply to their own Charge, and it recurs.

**So the answer to the question as put is: yes, the cliff is one Line Item in one Game, and
the sweep's verdict is much weaker than it looks. But a moderately looser Limit is *not*
free — it is exposed to a recurring Field cluster, and the right response is to bound the
exposure, not to move the level.**

---

## 2. What we reject, and why no threshold can sort it

For every fair Charge we rejected, `a`, `t` and our own median are recovered. **Every error
statistic below is conditioned on our own estimate, never on `t`.**

Over 27 Games: 4,810 recoverable Charges reviewed, 3,555 fair; at the shipped ceiling
**1,595 fair Charges are rejected**, carrying 612,033 of penalty (204,011 avoidable
surcharge). How far below the Charge our Limit sat, as a fraction of the Charge: p25 0.43,
median **0.59**, p75 0.72; and in 130 of 1,595 cases our Limit was exactly zero.

A ceiling sees exactly one number, `a / our_median`, and accepts precisely the Charges below
it. So "can a ceiling work?" is "do fair and unfair Charges separate in that number?" —
recent window:

| | n | euros | p10 | p25 | median | p75 | p90 |
|---|---:|---:|---:|---:|---:|---:|---:|
| fair (`a ≤ t`) | 497 | 88,759 | 0.00 | 0.00 | **0.47** | 0.79 | 1.25 |
| over (`a > t`) | 244 | 191,003 | 0.28 | 0.47 | **0.74** | 1.26 | 2.23 |

They overlap almost completely. The euro trade at threshold `k` — capturing a fair Charge we
were rejecting saves `0.5a`; capturing an Overcharge costs the full `a` — is negative
everywhere:

| k | fair captured | of fair | over bought | of over | `0.5·fair − over` |
|---|---:|---:|---:|---:|---:|
| 0.30 | 9,163 | 10% | 5,587 | 3% | −1,005 |
| 0.35 | 11,257 | 13% | 7,148 | 4% | −1,519 |
| 0.40 | 15,716 | 18% | 28,020 | 15% | −20,162 |
| 0.85 | 59,024 | 66% | 85,841 | 45% | −56,329 |

**There is no threshold that accepts most fair Charges while rejecting most Overcharges.**
To accept 66% of fair Charges by value you buy 45% of the Overcharges, and the Overcharges
are worth more in euros than the fair Charges (191,003 against 88,759).

---

## 3. Which term binds: the quantile never does

`b = min(quantile, LIMIT_CEILING × median, charge)`, plus the coverage collapse. Per Line
Item, and weighted by the penalty each item actually carries:

| term | items (all 27G) | share | penalty carried | share |
|---|---:|---:|---:|---:|
| coverage collapse (`b = 0`) | 94 | 29.4% | 90,976 | 14.9% |
| **`LIMIT_QUANTILE`** | **0** | **0.0%** | **0** | **0.0%** |
| `LIMIT_CEILING × median` | 226 | 70.6% | 521,057 | 85.1% |
| `charge` | 0 | 0.0% | 0 | 0.0% |

**Answer to the question as put: yes — the ceiling binds everywhere the Limit is non-zero,
the derived quantile is decorative, and the real parameters are `LIMIT_CEILING` and
`COVERAGE_FLOOR`.** The 1/3 quantile is sound arithmetic on the payoff table and never
touches a submitted number. Worth stating in `pricing.py` more bluntly than it currently is:
the existing note says the quantile "does not bind"; the measurement is that it binds on
*exactly zero* of 320 items, which is a stronger statement.

One consequence for whoever ships this: at `LIMIT_CEILING ≥ 0.80` the ceiling also stops
binding, because the Charge factor is capped at `CHARGE_BOUNDS[1] = 0.80`, so `b = min(charge,
…)` and the Limit becomes a pure function of the Charge constants. 0.85, 1.00 and 1.20 score
*identically*. That is why the recommendation below prefers **0.70**, where the ceiling still
binds on 72 of 320 items and the Limit stays decoupled from `CHARGE_INTERCEPT`/`CHARGE_SLOPE`.

---

## 4. Limit versus estimate: the split, in euros

Reference points on the same Games with the same Field. `lam` moves the estimate a fraction
of the way to the truth in log space (`median' = median·(t/median)^lam`) — an oracle
experiment, labelled as one, used only as a denominator.

**All 27 Games.** Shipped net +90,908 (penalty 612,033, pay_over 12,168). Oracle `b = t`:
+307,087. **Total headroom +216,179 (+8,007/Game).**

| lam | best k | net at best k | vs shipped | share of headroom a ceiling captures |
|---|---:|---:|---:|---:|
| **0.00 (us)** | **0.25** | **91,207** | **+300** | **0%** |
| 0.25 | 0.80 | 225,367 | +134,459 | 47% |
| 0.50 | 0.80 | 294,744 | +203,836 | 61% |
| 1.00 | 0.80 | 335,955 | +245,048 | 65% |

**Games 21–27.** Shipped +23,177; oracle +67,936; headroom **+44,758 (+6,394/Game)**.
`lam = 0` → best k 0.15, +1,179 (**3%**); `lam = 0.25` → best k 0.70, +29,405 (47%).

**So of the 54,322: essentially none of it is reachable by a Limit *level*, and roughly half
of it becomes reachable by a level the moment the estimate improves by a quarter of its log
error.** The estimate is the binding constraint, exactly as `pricing.py` says. The one thing
that *is* reachable now is a bound on the estimator's failure mode — section 5.

---

## 5. Rules that discriminate

Every rule conditions only on evidence we had at submission time: the band, the coverage
probability, and whether Price Memory had a wording hit (`var/evidence/case_NN_memory.json`
for Games 1–26, the decision log's `channels` for 27+ — keyed on wording, which is in the
Case, so it was knowable). Nothing reads `t`.

| rule | all 27G | vs 0.30 | 21–27 | vs 0.30 | accept | pay_over | penalty |
|---|---:|---:|---:|---:|---:|---:|---:|
| shipped 0.30 | 90,908 | — | 23,177 | — | 25.1% | 4,958 | 119,399 |
| flat 0.40 | 74,407 | −16,501 | 4,363 | −18,815 | 31.5% | 27,050 | 109,570 |
| flat 0.85 | 58,813 | −32,095 | −15,168 | −38,346 | 52.0% | 60,914 | 66,569 |
| coverage-split 0.60/0.20 | 47,456 | −43,451 | −15,980 | −39,158 | 38.4% | 52,944 | 92,916 |
| `0.85 − 1.0σ` | 77,442 | −13,466 | 2,451 | −20,727 | 37.5% | 31,868 | 100,849 |
| anchor `price_low` 0.85 | 78,023 | −12,885 | 3,811 | −19,366 | 35.5% | 29,022 | 105,309 |
| floor `1.0 × 59` | 93,069 | +2,161 | 23,436 | +259 | 29.8% | 5,228 | 117,815 |
| **memory 0.85 / model 0.30** | **101,076** | **+10,168** | **27,331** | **+4,153** | 36.3% | 9,797 | 92,424 |
| **0.30 + cap 12×59** | **95,110** | **+4,203** | **26,929** | **+3,752** | 24.3% | 490 | 121,549 |
| **0.70 + cap 12×59** | **108,433** | **+17,525** | **30,592** | **+7,414** | 46.5% | 10,195 | 81,448 |
| **0.85 + cap 12×59** | **108,573** | **+17,665** | **31,743** | **+8,566** | 47.1% | 10,195 | 77,994 |

The last three columns are the **21–27** window, so `accept`, `pay_over` and `penalty` read
against the shipped row's 25.1% / 4,958 / 119,399. Note the proposed rule's shape: penalty
falls 119,399 → 81,448 (−37,951) while `pay_over` rises only 4,958 → 10,195 (+5,237). That is
the trade a flat 0.40 could not make (penalty −9,829 for `pay_over` +22,092).

Three things fail, and the failures are informative:

* **Coverage-conditional ceilings are the worst rule tested.** Coverage is a good signal for
  `t = 0` and carries no information about *magnitude*, which is what the loss depends on.
* **`0.85 − k·σ` cannot work, and section 3 says why**: `implied_sigma` has median 0.375
  against a measured RMSLE of 0.80 and its width is slightly *anti*-correlated with accuracy.
  Multiplying a ceiling by a number that does not measure precision cannot buy precision.
* **`price_low` as the anchor** is just a smaller multiple of the same blown-up median.

Two things work, and both discriminate on something real:

* **Price Memory as a trust flag** (+10,168 / +4,153). Memory's measured log error is 0.43
  against the model's ~0.80, and it is the only per-item trust signal in the pipeline with a
  number behind it. Worth flagging to whoever owns the evidence layer independently of the
  Limit.
* **A hard euro cap.** The recommendation.

---

## 6. Is 0.30's win a pricing fact or a Game 22 fact?

Per-Game gains against the shipped 0.30, over all 27 Games:

| ceiling | net 27G | vs 0.30 | per Game | win/loss | median | trimmed mean | worst Game |
|---|---:|---:|---:|---:|---:|---:|---|
| 0.25 | 91,207 | +300 | +11 | 3/16 | −28 | −75 | G24 −710 |
| **0.30** | 90,908 | 0 | 0 | — | 0 | 0 | — |
| 0.35 | 90,367 | −541 | −20 | 11/8 | 0 | **+32** | G24 −1,203 |
| 0.40 | 74,407 | −16,501 | −611 | **14/9** | **+41** | **+150** | **G22 −19,892** |
| 0.45 | 76,635 | −14,273 | −529 | 13/10 | 0 | **+166** | G22 −19,892 |
| 0.60 | 56,297 | −34,611 | −1,282 | 10/13 | 0 | −402 | G22 −19,892 |

Read this carefully, because it cuts both ways. **The typical Game prefers a looser
ceiling** — 0.40 improves 14 Games and worsens 9, with a positive median and a positive
10%-trimmed mean. The total prefers 0.30 only because one Game costs 19,892. So the shape of
the truth is: *loosening the level is a small, broad, positive drift bought at the price of
exposure to a rare, large, one-sided loss.* Amortised, that exposure is 19,892/27 ≈ 737 a
Game against a trimmed gain of +150 to +166 a Game, so **strictness still wins on the
record** — but the ratio rests on a single observed tail event, and a rate estimated from one
event has a 95% interval spanning two orders of magnitude. That is not a foundation for a
constant; it is a reason to remove the exposure.

---

## 7. The recommendation

Add one term to `price_item`:

```python
# The Limit is a multiple of our own median, so it cannot bound what we pay: when the
# estimate blows up the ceiling blows up with it. Game 29 is the proof -- median 7,138
# against a Fair Value under 57.30, thirteen opponents Charging exactly 2,000.00, and the
# strict 0.30 ceiling put b at 2,142 and bought all thirteen for 24,157 of pure loss.
# 2,000.00 is the most common Charge above 500 euros in the record (28 rows, 5 Games), so
# the exposure recurs. A cap in euros is the only term that bounds it, because it is the
# only one that does not scale with the number that broke.
#
# 12 x SETTLED_MEDIAN. The settled Fair Value distribution has median 59, p90 606, p95 986:
# a Limit above ~1,400 asserts the item is in the top 2.5% of everything we have ever seen,
# which our band cannot support (implied_sigma median 0.375 against a measured RMSLE 0.80,
# width uncorrelated with accuracy). 7.2% of settled Line Items have t > 708; the fair
# Charges on those are forfeited deliberately and are priced into the numbers below.
LIMIT_CAP = 12.0 * SETTLED_MEDIAN          # 708.00
```

and, once the cap is in, loosen the ceiling:

```python
LIMIT_CEILING = 0.70                        # was 0.30
```

### What it is worth, on which window

| rule | 1–20 (20G) | 21–27 (7G) | all (27G) | **held out: 28–29** |
|---|---:|---:|---:|---:|
| shipped 0.30, no cap | 67,730 | 23,177 | 90,908 | −20,879 |
| 0.30 + cap 708 | 68,181 **+451** | 26,929 **+3,752** | 95,110 **+4,203** | 3,121 **+24,000** |
| **0.70 + cap 708** | 77,841 **+10,111** | 30,592 **+7,414** | **108,433 +17,525** | 410 **+21,289** |
| 0.85 + cap 708 | 76,830 +9,100 | 31,743 +8,566 | 108,573 +17,665 | 410 +21,289 |

Games 28 and 29 settled after the rule was chosen and were used for nothing. G29 alone:
shipped −24,177 (pay_over 24,157) → proposed −155 (pay_over 434) = **+24,022**. G28 goes the
other way: shipped +3,298 → proposed +566 = **−2,733**, because Game 28 is a Game where our
estimate is 10× too *high* on small items and there were no penalties to save. Both directions
are in the record.

**If only one change is acceptable, ship the cap alone at 0.30.** It is +4,203 over 27 Games
and +24,000 on the two held-out Games, it touches no existing constant, and it is the term
that carries the mechanism. The loose ceiling is the bonus, and it depends on the cap.

### Why this is not the previous mistake in a new coordinate

A euro cap is exactly the kind of parameter that can be fitted to one cluster of Charges.
Four independent checks:

**It is a plateau, and both disjoint windows agree.** Net by (ceiling, cap), thousands:

| window, ceiling | 6× | 8× | 12× | 16× | 24× | 32× | 40× | none |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1–20**, 0.70 | 76.1 | 77.6 | 77.8 | 76.6 | 77.9 | **79.7** | 74.5 | 74.5 |
| **1–20**, 0.85 | 74.1 | 75.8 | 76.8 | 74.4 | 75.7 | **79.1** | 74.0 | 74.0 |
| **21–27**, 0.70 | 26.7 | 27.4 | 30.6 | **31.7** | 29.3 | 21.2 | −11.2 | −16.3 |
| **21–27**, 0.85 | 26.7 | 27.8 | 31.7 | **32.8** | 30.5 | 22.3 | −10.1 | −15.2 |
| **all 27**, 0.70 | 102.8 | 105.0 | **108.4** | 108.3 | 107.3 | 100.9 | 63.3 | 58.2 |
| **all 27**, 0.85 | 100.8 | 103.6 | **108.6** | 107.2 | 106.2 | 101.5 | 63.9 | 58.8 |

Every cell from 6× to 24× (354 to 1,416 euros — a factor of four) beats the uncapped column in
every window; 8×–24× is one flat region. The edge is at 40× = 2,360, which is exactly where
2,000.00 gets through, and it costs 21–27 more than 40k. **Note the 1–20 rows contain no Game
22**, so the cap's value there — +2 to +5k over the uncapped column — is entirely independent
of the item that started this.

**It survives redrawing the estimator — measured, not asserted.** The 26,622 noise floor is a
statement about re-drawing the model's evidence. We have seven cached prompt framings, i.e.
seven independent draws over the same Cases. Re-scoring the *difference* on each:

| draw | Games | cap only | proposed |
|---|---:|---:|---:|
| model | 26 | +4,563 | **+18,410** |
| nohint | 24 | +1,059 | **+21,530** |
| nohint2 | 19 | −1,145 | **+13,964** |
| anchor | 24 | +2,632 | **+20,266** |
| anchornohint | 24 | +23,560 | **+47,168** |
| mag | 19 | +1,669 | **+15,074** |
| rate | 19 | 0 | **+16,313** |

(Those columns are the `0.85 + cap` variant, which is what `PROPOSED` is set to in the script.
The recommended **`0.70 + cap`** passes identically: **7 of 7**, +12,339 to +44,171, and
leave-one-out positive in **27 of 27** folds, range +13,119 to +20,139, worst Game G21 −2,614.)

Positive in **7 of 7**, +13,964 to +47,168. The absolute +17,665 sits inside the 32,605
noise band for 27 Games and I am not claiming otherwise — but a quantity that moves the same
way under every redraw of the noise is not being produced by the noise. (The cap *alone* is
genuinely marginal on this test: 6 of 7, one negative. Another reason to prefer the pair, and
to be honest that the cap-only variant is the safe change rather than the strong one.)

**No Game carries it.** Leave-one-Game-out on the difference is positive in **27 of 27**
folds, range +13,259 to +20,279. Five worst Games: G21 −2,614, G7 −2,281, G4 −1,270,
G8 −1,233, G5 −1,054. Five best: G15 +2,879, G13 +3,116, G22 +3,584, G18 +3,797, G24 +4,406.
Compare flat-0.40, whose worst Game is −19,892.

**It reverses the previous audit's decisive out-of-sample result.** Disjoint train/test:

| trained on | picks | scored on | result | vs shipped |
|---|---|---|---:|---:|
| 1–20, ceiling alone | 0.70 | 21–27 | −16,320 | **−39,497** |
| 1–20, (ceiling, cap) | (0.70, 32×) | 21–27 | +21,198 | −1,980 |
| 21–27, ceiling alone | 0.15 | 1–20 | +64,686 | −3,045 |
| 21–27, (ceiling, cap) | (0.85, 16×) | 1–20 | **+74,388** | **+6,658** |

"Train on the old window, pick a loose ceiling, lose 22–39k on the new one" — the argument
that settled the question last time — **is an argument about the ceiling alone.** With the cap
present the same procedure costs 1,980 in one direction and gains 6,658 in the other.

**Censoring and opponent-Limit reconstruction do not drive it.** 86 of 320 Line Items have no
upper bracket, so `t` falls back to a lower bound and an accepted Charge above it is scored as
an Overcharge that may have been fair — a bias *toward* strictness. Pushing every open bracket
to `+∞` (maximally generous to a loose Limit) gives +27,141 rather than +17,665; the hostile
`t_rule=lo` gives +17,665. Invariant to `limit_rule ∈ {lo, mid, hi}` to the cent, as it must
be structurally.

### What would falsify it

1. **`pay_over` rising under the proposed rule while `penalty` does not fall** — the Field
   starting to Charge just under 708. Two columns in section 5, checkable every Game.
2. **The 2,000.00 cluster disappearing.** It is the mechanism. Without it the cap is worth
   much less and the 8×–24× plateau should visibly narrow.
3. **The band becoming calibrated** (RMSLE 0.80 → ~0.40). Section 4 says the ceiling alone
   then becomes worth six figures and the cap becomes a tax on the top 7% of items. Re-run
   and raise the ceiling toward 0.80, then consider dropping the cap.
4. **A Cap `c` that finally binds.** Zero conflicts in the settled rows so far; if one
   appears, an accepted Overcharge becomes cheaper than `a` and everything here shifts
   toward generosity.

### Honest residual

The accept rate under the proposal is 56% over all 27 Games and 47% recent, against 25%
today. `pricing.py` currently argues that the leaders' 63–65% "costs 60–75k over four Games
in this Field". That measurement replayed opponents' *reconstructed Limits* wholesale, which
imports their generosity **without any cap**; it is not evidence against a capped 56%. But it
is also not evidence *for* it, and the accept rate rising by 30 points is the single biggest
behavioural change in this recommendation. If it is shipped, watch `pay_over` per Game rather
than the accept rate.

---

## 8. `case_analysis/` reviewed at Game 27 — what still holds, what is now false

Not edited, as instructed. Reported here. My harness independently reproduces
`diagnose.py`'s Games 1–13 figures **exactly** (net −274,350; income 75,116; pay_fair 66,797;
pay_over 98,579; penalty 184,090; median `a/t` 2.27), so where the two disagree it is because
the world moved, not because the arithmetic differs.

Context: cumulative at Game 27 we are **−315,174** on income 388,060, 15th of 17.

### Era table (our real submissions, all replayed to the published net)

| | net | income | pay_fair | pay_over | penalty | accept | median `a/t` |
|---|---:|---:|---:|---:|---:|---:|---:|
| Games 1–13 | −274,350 | 75,116 | 66,797 | 98,579 | 184,090 | 68.8% | 2.27 |
| Games 14–20 | −79,821 | 145,519 | 75,085 | 24,330 | 125,926 | 61.2% | 1.05 |
| **Games 21–27** | **+38,997** | **167,425** | **10,475** | **526** | **117,426** | **25.0%** | **0.99** |

### Still true

* **"Lawyer penalties are the dominant cost bucket."** Stronger now, not weaker: **61%** of
  costs over 27 Games (427,442 of 703,234) against the document's 53%. `DIAGNOSIS_TLDR.md`'s
  headline claim is the one that aged best.
* **"Rejected Overcharges cost nothing" and the count of them.** Confirmed and extended: the
  document's 1,722 rejections-at-zero over Games 1–13 recomputes here as 762 *(item, reviewer)*
  pairs on our own Overcharges — the two count different things, and the document does not say
  which, which is worth a footnote in it. Either way the direct cost is zero, and Games 14–27
  add 524 more.
* **"A dark team is a money fountain, not a zero" (R7/R10).** `makalu` has issued **zero**
  income across 27 Games and sits at **−677,542**, last by 180k. This is the single cleanest
  confirmation of anything in the folder.
* **`DATA_LAYOUT.md`'s `amount` semantics** — "always what the Issuer receives; the `0.5a`
  lawyer fee never appears in a row" — is correct and is what `replay_payoffs` relies on.

### Now false, or true for a reason that has changed

* **P1: "the Limit is never inside the posterior; it flips between 0 and ∞; 283k of the loss
  is Limit-side."** **False as stated at Game 27.** The `b ≈ ∞` failure is gone as a policy
  (accepted-Overcharge cost fell from 98,579 over Games 1–13 to **526** over Games 21–27) and
  the Limit is now derived from a posterior. Penalties are still the largest bucket, but the
  cause inverted: it was a Limit *outside* the posterior; it is now a Limit deliberately at
  the posterior's bottom third. **The recommended fix in the document — "hard-floor `b > 0`
  … hard-cap `b` at the known `t_hi`/Cap bound" — is, in current terms, exactly the euro cap
  this audit arrives at from the other end.** That is the one place where the old document is
  ahead of the shipped code.
* **P2 cause 1: "we don't show up; Games 3, 7, 11, 12 had zero Issuer income."** **Resolved.**
  Game 16 was the last zero-income Game; there has been none in eleven Games. The blind floor
  and two-phase submit did what hard rule 8 said they would.
* **P2 headline: "75k vs 310–354k for the top-3, out-earned 4–5×."** **Stale by a large
  factor.** At Game 27 our income is **388,060** against 694,885–750,814 for the top four,
  i.e. **1.8×**, not 4–5×. Income starvation is no longer the primary problem, and treating
  it as one now would push the Charge up, which R5b/R5c say is wrong.
* **P2 cause 2/3: "flat 100/150 placeholders; median `a/t` 2.27 against 0.85–1.0 for the
  top-3."** **Fixed.** Median `a/t` is **0.99** over Games 21–27, inside the top teams' band
  and close to R5b's 0.7·t̂ target given estimator bias. The placeholder pathology is gone.
* **The top-3 roster is stale.** `DIAGNOSIS.md` names TakeTheMoneyAndRun / error404 ai /
  OPUSMOPUS. At Game 27 the leader is **`eyay` at +113,482**, more than double second place,
  and it does not appear in the document at all. Anything in `dashboard.md` computed over
  "top-3" is measuring a different set of teams than it did.
* **P3: "no per-Game learning loop."** **Resolved** — `pixi run learn`, `learn_watch.py` and
  `var/decisions/game_NNN.json` exist, and this audit is only possible because they do.
* **Both `DIAGNOSIS.md` and `DIAGNOSIS_TLDR.md` are titled for 13 Games and read as current.**
  They are 14 Games and three strategy generations behind. The single most useful edit anyone
  could make to that folder is a dated banner at the top of each: *"describes Games 1–13; the
  Limit-side diagnosis in P1 was fixed at Game 21, see docs/brainstorm/sebi/strats/review/."*
  A stale doc is worse than no doc, because someone will build on it at 04:00.
* **One factual slip worth correcting independent of staleness.** `DIAGNOSIS_TLDR.md`
  attributes Game 10's −66k to "Limit ≈ 0 / dark Reviewer". Game 10 was not dark: we issued
  5,300 of income. The Limit was collapsed to near-zero by the coverage rule while the item
  was in fact covered and worth ≥ 7,225 — a *coverage* misclassification, not an absence.
  That distinction matters, because the fix for one is uptime and for the other is the
  evidence layer.

---

## 9. Two things for other owners, found on the way

Neither is mine to change; both are cheap and measured.

1. **Price Memory should widen the Limit, not just the band.** A memory-hit item priced at
   ceiling 0.85 while model-only items stay at 0.30 is worth **+10,168 over 27 Games and
   +4,153 over 21–27**, positive in both windows. Memory's measured log error is 0.43 against
   the model's ~0.80; that gap is currently used for blending the *price* and not at all for
   trusting the *Limit*.
2. **`implied_sigma` is worse than uninformative for this purpose.** Section 5's
   `0.85 − k·σ` rules all lose. Combined with the existing finding that the narrow third of
   bands scores RMSLE 0.847 against the wide third's 0.733, the band width is slightly
   *anti*-correlated with accuracy. Any rule keyed on it will be keyed backwards until the
   evidence layer fixes it.
