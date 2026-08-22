# Field study — what the profitable teams do differently, and what it is worth to copy

**Tool:** `scripts/field_study.py` (`--teams`, `--games`, `--split`, `--control`, `--per-game`,
`--adopt`, `--verify-nets`). Reproduce everything below with

```bash
PYTHONPATH=. python scripts/field_study.py --games 1-26 --split 15 --control --per-game --adopt
```

**Window:** Games 1–26, the window the brief supplied. Game 27 settled during the study and is
noted where it matters but excluded from the tables so the numbers stay quotable.
**Everything in "Measured" is arithmetic over published Transactions.** Fair Values come from
`invert_fair_values.brackets` (`t` = bracket midpoint, or `t_lo` where the bracket is unbounded
above), Charges and Limits from `replay_payoffs._charges_and_limits`. Nothing here is modelled.
The "Inferred" sections are clearly separated and are argument, not measurement.

---

## 0. The published table checks out — and the totals are not the story

`--verify-nets` recomputes every per-Game net from the rows via the payoff identity and compares
it against the `/matrix` cell. **Every one of the 20 values in the brief's table reproduces to the
euro, for both teams, and both totals reproduce exactly** (eyay 98,989; TakeTheMoneyAndRun 63,826)
once Games 1–6 are included. Games 1–6 cost eyay −38,649 and TakeTheMoneyAndRun −16,737, which is
why the G7–26 subtotals (137,638 and 80,563) are larger than the published totals.

The leaderboard total is, however, measuring a tournament that no longer exists. Ranked by
window:

| window | 1st | 2nd | 3rd | **our rank** | our net |
|---|---|---|---|---|---|
| G1–26 | eyay 98,989 | TakeTheMoneyAndRun 63,826 | OPUSMOPUS 42,848 | **15 / 17** | −326,525 |
| G1–14 | TakeTheMoneyAndRun 86,394 | error404 ai 81,284 | OPUSMOPUS 67,748 | **16 / 17** | −276,950 |
| G15–26 | eyay 72,830 | Codacabana 12,063 | *(everyone else negative)* | **11 / 17** | −49,576 |
| **G19–26** | **Bin busy 74,819** | Codacabana 67,909 | eyay 56,764 | **1 / 17** | **+74,819** |
| G23–26 | Codacabana 30,847 | TakeTheMoneyAndRun 23,643 | TBD 10,070 | **4 / 17** | +9,726 |

**Measured:** the premise "two teams are profitable and we are not" is true *cumulatively* and
false *currently*. Our entire deficit is Games 5–18 (**−419,088** over fourteen Games); Games 1–4
were +17,744 and Games 19–27 are **+86,170** over nine Games, and we top that window. Any adopt-list computed over Games 1–26 is
therefore mostly a verdict on a pipeline we have already replaced, which is why `--adopt` now
prints the whole window *and* each regime separately.

---

## 1. Charge and Limit against the true Fair Value

Pooled over Games 1–26 (316 team-items each). `fair%` is the share of Charges with `a <= t` —
the region where income is owed by all sixteen opponents whether they accept or not. `unrec` is
Charges no reviewer ever paid, so `a` is censored, not zero.

| team | a/t p25 | a/t med | a/t p75 | fair% | a=0 | unrec | b/t p25 | b/t med | b/t p75 |
|---|---|---|---|---|---|---|---|---|---|
| eyay | 0.31 | **0.68** | 1.51 | **67.6 %** | 61 | **7** | 0.21 | **0.57** | 1.00 |
| TakeTheMoneyAndRun | 0.34 | 0.74 | 2.00 | 66.2 % | 48 | 29 | 0.33 | 0.93 | 1.00 |
| OPUSMOPUS | 0.00 | 0.38 | 0.86 | 82.2 % | 145 | 1 | 0.52 | 1.00 | 1.00 |
| error404 ai | 0.48 | 0.84 | 2.37 | 60.5 % | 24 | 30 | 0.35 | 0.92 | 1.00 |
| Codacabana | 0.33 | 0.80 | 1.76 | 63.7 % | 55 | 32 | 0.30 | 0.89 | 1.00 |
| **Bin busy** | 0.29 | **1.00** | **2.50** | **54.0 %** | 48 | **116** | 0.30 | 1.00 | 1.37 |
| makalu *(control)* | 0.00 | 0.00 | 0.00 | 100 % | 316 | 0 | 0.12 | 0.21 | 1.00 |

**Measured, and this is the single sharpest difference:** our median `a/t` is exactly **1.00**
against eyay's **0.68**, our p75 is 2.50 against 1.51, and **116 of our 316 Charges (37 %) were so
high that not one of sixteen reviewers paid a cent** — against 7 for eyay. R5b says `a* ≈ 0.7 t̂`;
eyay sits there and we sit at `t̂`.

In the current regime (G19–26, 59 items) the gap has narrowed but not closed: eyay 0.75 / 64.3 %
fair / 3 unrecoverable, us 1.00 / 54.9 % fair / 8 unrecoverable.

---

## 2. Reviewer behaviour — two different skills

Pooled G1–26, 5,056 reviewed rows each.

| team | accept % | fair seen | fair accepted | Overcharges seen | Overcharges accepted |
|---|---|---|---|---|---|
| eyay | 44.2 % | 3,428 | **61.4 %** | 1,628 | **8.0 %** |
| TakeTheMoneyAndRun | 58.3 % | 3,447 | 74.2 % | 1,609 | 24.2 % |
| OPUSMOPUS | 60.5 % | 3,378 | 81.0 % | 1,678 | 19.3 % |
| error404 ai | 56.1 % | 3,464 | 73.2 % | 1,592 | 18.8 % |
| Codacabana | 55.0 % | 3,456 | 74.2 % | 1,600 | 13.4 % |
| **Bin busy** | 60.3 % | 3,529 | 73.5 % | 1,527 | **29.8 %** |
| makalu | 28.7 % | 3,321 | 43.6 % | 1,735 | 0.0 % |

Current regime (G19–26):

| team | accept % | fair accepted | Overcharges accepted |
|---|---|---|---|
| eyay | 29.1 % | 41.2 % | 7.7 % |
| Codacabana | 57.2 % | 76.3 % | 22.6 % |
| **Bin busy** | 25.8 % | 38.3 % | **2.7 %** |

**Measured — and this corrects the brief.** The claim "our accept rate is 6–19 % against their
63–65 %" is not what the rows say. Per-Game, eyay's accept rate is 84 % in G1 and 18–37 % over
G19–27; ours is 91 % in G1, 6–19 % only in G21–24, and 23–37 % over G23–27. Over the last four
Games the two are within a point of each other. **We no longer have a Limit problem in the
direction the brief assumes; we have the opposite one** — we now reject fair Charges more often
than anyone except makalu, and we accept fewer Overcharges than anyone at all (2.7 %).

---

## 3. Income and cost decomposition

Pooled G1–26. `inc fair` is income from `a <= t` (structural — owed by every opponent regardless
of their Limit). `inc over` needs a generous opponent. `pay over` is pure loss; `penalty` is the
`1.5a` on wrongful rejection.

| team | net | inc fair | inc over | over % | pay fair | pay over | penalty |
|---|---|---|---|---|---|---|---|
| eyay | 98,989 | **574,774** | 141,750 | 19.8 % | 96,764 | **53,709** | 467,062 |
| TakeTheMoneyAndRun | 63,826 | 597,104 | 116,283 | 16.3 % | 195,435 | 137,164 | 316,962 |
| OPUSMOPUS | 42,848 | 570,452 | 112,913 | 16.5 % | 262,808 | 159,308 | 218,401 |
| error404 ai | 7,630 | 553,215 | 153,332 | 21.7 % | 153,863 | 161,619 | 383,435 |
| Codacabana | 6,266 | 474,846 | 123,934 | 20.7 % | 152,562 | 47,218 | 392,734 |
| **Bin busy** | −326,525 | **230,025** | 136,174 | **37.2 %** | 150,480 | 123,435 | 418,809 |
| makalu | −666,094 | 0 | 0 | — | 0 | 0 | **666,094** |

**Measured:** the top four teams all earn 553k–597k of structural income. We earned **230,025** —
**40 % of the field-leading rate** — while relying on Overcharge generosity for 37.2 % of our
income against eyay's 19.8 %. That is the whole story of the deficit: not that we paid too much,
but that **we never got paid**, because our Charges sat above `t`.

Current regime (G19–26):

| team | net | inc fair | inc over | over % | pay fair | pay over | penalty |
|---|---|---|---|---|---|---|---|
| eyay | 56,764 | 166,243 | 77,751 | 31.9 % | 23,080 | 34,785 | 129,365 |
| Codacabana | 67,909 | 164,382 | 57,582 | 25.9 % | 53,186 | 16,489 | 84,380 |
| **Bin busy** | **74,819** | 131,249 | 107,135 | **44.9 %** | 8,623 | **611** | **154,332** |

**Measured:** we are winning the recent window with a structurally *worse* mix. 44.9 % of our
recent income is Overcharge income (the +14,840 in G22 is 100 % of that kind, exactly as the brief
suspected), and our largest single cost line is now **154,332 of wrongful-rejection penalty** —
the highest of any live team. Codacabana earns nearly the same as eyay with only 84,380 of penalty
and 16,489 of over-payment, which is the most efficient shape in the field.

---

## 4. Consistency, and whether anyone is estimating

| team | games | total | mean | stdev | worst | pos % | pre (G<15) | post (G≥15) |
|---|---|---|---|---|---|---|---|---|
| eyay | 26 | 98,989 | 3,807 | **11,361** | −13,065 | **61.5 %** | 26,159 | **+72,830** |
| TakeTheMoneyAndRun | 26 | 63,826 | 2,455 | 12,976 | −19,008 | 46.2 % | **86,394** | **−22,569** |
| OPUSMOPUS | 26 | 42,848 | 1,648 | 20,432 | −40,192 | 38.5 % | 67,748 | −24,900 |
| error404 ai | 26 | 7,630 | 293 | 17,927 | −52,487 | 57.7 % | 81,284 | −73,654 |
| Codacabana | 26 | 6,266 | 241 | 18,226 | −44,462 | **69.2 %** | −5,796 | +12,063 |
| Bin busy | 26 | −326,525 | −12,559 | 26,787 | −80,074 | 34.6 % | −276,950 | −49,576 |
| makalu | 26 | −666,094 | −25,619 | 24,958 | −98,780 | 0.0 % | −290,624 | −375,470 |

| team | corr(a,t) | corr(log a, log t) | distinct Charges / item | a=0 Games | b=0 Games | (0,0) Games |
|---|---|---|---|---|---|---|
| eyay | 0.72 | 0.50 | 0.76 | 6 | 8 | **6** (G1–6) |
| TakeTheMoneyAndRun | 0.61 | 0.46 | 0.79 | 1 | 5 | 1 (G1) |
| OPUSMOPUS | 0.65 | 0.61 | 0.56 | 9 | 9 | 9 |
| error404 ai | 0.63 | 0.50 | 0.84 | 1 | 4 | 1 (G18) |
| Codacabana | 0.69 | 0.44 | 0.71 | 2 | 5 | 2 |
| Bin busy | 0.72 | 0.28 | 0.54 | 3 | 9 | 3 |
| makalu | n/a | n/a | 0.08 | **26** | 26 | **26** |

Over G19–26 alone, every live team correlates 0.62–0.76 with the true `t` and submits a distinct
Charge on 94–100 % of items.

**Measured:** *everybody* who is awake has a real estimator, and **ours is as good as anyone's**
(corr 0.76 over G19–26, the highest in the table, tied with OPUSMOPUS). Nobody is running a
constant. `makalu` is the pure control: a constant `0` on all 316 items, correlation undefined,
and −666,094 of nothing but `1.5a` penalty — R7 and R10 measured rather than argued.

**eyay was dark for Games 1–6.** All six were the full `(0,0)` default. Its 98,989 is really
137,638 earned from Game 7 onward minus a −38,649 hole from not playing. It did not out-play the
field early; it *arrived* late and has been the most consistent team since (stdev 11,361, the
lowest of any profitable team, 61.5 % positive Games).

---

## 5. The regime question

`--per-game` prints a field-wide table. The interesting columns:

| Game | items | median t | teams with a=0 | teams with b=0 | full (0,0) | modal non-zero Charge | teams sharing it | field median a/t |
|---|---|---|---|---|---|---|---|---|
| 1 | 18 | 93 | 13 | 13 | **13** | 122.94 | 1 | 0.00 |
| 3 | 2 | 50 | 12 | 15 | 12 | 180.00 | 1 | 0.00 |
| 8 | 39 | 123 | 4 | 4 | 4 | 450.00 | 2 | 0.57 |
| 14 | 13 | 18 | 5 | 10 | 5 | 232.67 | 1 | 0.00 |
| 16 | 2 | 39 | 8 | 15 | 8 | 577.56 | 1 | 0.00 |
| 19 | 9 | 401 | 4 | 4 | 4 | 3,848.48 | 4 | 0.73 |
| **22** | **1** | 123 | 1 | 7 | 1 | **2,000.00** | **9** | **16.28** |
| 26 | 12 | 73 | 1 | 1 | 1 | 106.20 | 1 | 0.76 |
| 27 | 4 | 12 | 1 | 3 | 1 | 12,000.00 | 3 | 1.65 |

**Measured — three separate things are happening, and only one of them is a regime change.**

1. **The field woke up gradually, it did not go dark overnight.** Teams submitting the full
   `(0,0)` default fall monotonically: 13 in G1, 5 in G7, 3–5 through G15–19, and **1 from G20
   onward** (only `makalu`, which has been dark for all 26 Games). Over G1–26 there is **no**
   overnight blackout in the data. R9's "field goes dark and wakes recalibrated" is a prediction
   about Games ~44–81; it has not happened yet, and the window we have is the *opposite* — an
   awakening.
2. **The identical-value signature is `a = 0`, not `b = 0`, and the two are not the same thing.**
   A team Charging nothing earns nothing, so its net is whatever it pays as Reviewer; when the
   field's Charges all sit above a near-zero `t`, its rejections are *rightful* and cost nothing,
   and its net is exactly **0** — identically, for every such team. That is what produced the
   eight `0.00` cells in Game 16 and the twelve in Game 3. `b = 0` on its own is sometimes free
   (G16: seven teams paid nothing at all) and sometimes ruinous (makalu: 666,094 of penalty). The
   script reports the two columns separately for exactly this reason.
3. **The field now converges on identical *non-zero* Charges, which is new and is not a default.**
   In Game 22 — a single Line Item, kitchen air-conditioning replacement, true `t < 245.70` —
   **nine of seventeen teams submitted exactly 2,000.00**, and the field median `a/t` was **16.28**.
   Game 19: four teams at exactly 3,848.48. Game 27: three at exactly 12,000.00. Reading
   `case_22/policy.txt` and `description.txt`, the number 2,000 appears nowhere; the description
   dangles *"close to the hob"*, the same bait CLAUDE.md records for Case 7, and the item was in
   fact worthless. Nine independent teams landing on the same round number to the cent is not
   independent estimation.

**The regime split at Game 14/15 is real, but it is a split in the *field*, not in eyay.**
Pre/post totals: TakeTheMoneyAndRun 86,394 → −22,569; error404 ai 81,284 → −73,654; OPUSMOPUS
67,748 → −24,900; eyay 26,159 → **+72,830**. Only eyay and Codacabana are positive after Game 15.
What changed is measured in the accept-rate tables: **every live team tightened its Limit, and
most of them tightened it on the wrong claims.** Fair-Charge acceptance, G<15 → G≥15: eyay
70.1 % → 48.2 %, TakeTheMoneyAndRun 82.9 % → 60.7 %, OPUSMOPUS 84.7 % → 75.4 %, error404 ai
83.1 % → 58.0 %, us 82.6 % → 59.5 %. Overcharge acceptance over the same split: eyay 10.2 % →
4.4 %, TakeTheMoneyAndRun 27.6 % → 18.8 %, error404 ai 17.9 % → 20.1 %, us 37.9 % → 16.9 % (2.7 %
over G19–26 alone). Only eyay and we moved the *ratio* in the right direction.

**TakeTheMoneyAndRun's collapse is entirely on the Reviewer side, and its income did not fall.**
Pre → post: income 355,996 → 357,391 (flat), but `1.5a` penalty **116,432 → 200,530** and
over-payments **56,296 → 80,868**. Its acceptance of fair Charges fell 82.9 % → 60.7 % while its
acceptance of Overcharges only fell 27.6 % → 18.8 %. It tightened its Limit **non-selectively** —
it started refusing claims it owed without stopping paying claims it did not. That is the exact
failure mode R4/R6 warn about, run in reverse.

**eyay's improvement is entirely on the Issuer side.** Pre → post: income 293,789 → **422,736**
(`inc fair` 256,026 → 318,749, `inc over` 37,763 → 103,987) against costs rising only
267,630 → 349,906. Part of the "pre" figure is simply that eyay was dark for Games 1–6, so read
its pre-regime number as depressed rather than its post-regime number as a step change.

---

## 6. The adopt-list, with euros

Replayed with `replay_payoffs.replay` on **our** Games, opponents held fixed, donors' Charges and
Limits reconstructed exactly as an opponent would reconstruct ours. Noise floor scaled from
26,622 / 18 Games = 1,479 per Game.

### Over all 26 Games (verdict on the old pipeline)

| submission | total | Δ vs us | verdict |
|---|---|---|---|
| eyay: a + b | 63,970 | **+390,495** | ADOPT |
| TakeTheMoneyAndRun: a + b | 53,322 | +379,848 | ADOPT |
| TakeTheMoneyAndRun: **a only**, our b | 46,157 | +372,682 | ADOPT |
| eyay: **a only**, our b | 21,611 | +348,136 | ADOPT |
| our own a × 0.80 (censored Charges floored) | −44,479 | +282,047 | ADOPT |
| eyay: **b only**, our a | −284,167 | +42,359 | ADOPT |
| makalu: **b only**, our a | −278,330 | +48,195 | ADOPT |
| **us (actual)** | **−326,525** | 0 | baseline |
| TakeTheMoneyAndRun: b only, our a | −319,360 | +7,165 | inside noise (±38,454) |
| OPUSMOPUS: b only, our a | −328,376 | −1,851 | inside noise |
| error404 ai: b only, our a | −372,048 | −45,523 | reject |
| makalu: a + b | −644,529 | −318,004 | reject |

### Over Games 15–26 (the current field)

| submission | total | Δ vs us | verdict |
|---|---|---|---|
| our own a × 0.80, censored Charges floored | 112,777 | **+162,352** | ADOPT |
| our own a × 0.70, censored Charges floored | 87,360 | +136,936 | ADOPT |
| eyay: **a only**, our b | 83,232 | **+132,808** | ADOPT |
| OPUSMOPUS: a only, our b | 61,126 | +110,701 | ADOPT |
| eyay: a + b | 60,658 | +110,233 | ADOPT |
| TakeTheMoneyAndRun: a only, our b | 40,807 | +90,382 | ADOPT |
| eyay: a × 0.75, our b | 33,732 | +83,307 | ADOPT |
| Codacabana: a only, our b | 5,645 | +55,221 | ADOPT |
| **us (actual)** | **−49,576** | 0 | baseline |
| our own a × 0.80 (censored Charges left censored) | −51,638 | −2,062 | inside noise (±17,748) |
| Codacabana: b only, our a | −51,005 | −1,430 | inside noise |
| eyay: **b only**, our a | −72,150 | **−22,574** | **reject** |
| eyay: a × 1.33, our b | −112,141 | −62,565 | reject |
| TakeTheMoneyAndRun: b only, our a | −101,022 | −51,447 | reject |
| error404 ai: b only, our a | −149,762 | −100,186 | reject |

### Over Games 19–26 (the regime we are actually in)

| submission | total | Δ vs us | verdict |
|---|---|---|---|
| eyay: a only, our b | 86,230 | +11,411 | **inside noise (±11,832)** |
| our own a × 0.80, censored floored | 82,797 | +7,978 | inside noise |
| our b × 1.50 | 79,727 | +4,908 | inside noise |
| our own a × 0.80 (censored censored) | 77,386 | +2,567 | inside noise |
| **us (actual)** | **74,819** | 0 | baseline |
| eyay: a + b | 59,545 | −15,273 | reject |
| eyay: **b only**, our a | 48,134 | −26,684 | **reject** |
| TakeTheMoneyAndRun: a + b | 15,897 | −58,922 | reject |
| OPUSMOPUS / error404 ai: b only | −22,850 / −29,014 | −97,668 / −103,832 | reject |

**Measured, ranked, with the euros attached:**

1. **Lower the Charge — the only item that clears the floor in the current field.** Adopting
   eyay's Charge with our own Limit is **+132,808 over Games 15–26** (+11,067 per Game) and
   **+348,136 over Games 1–26**. Over Games 19–26 it is +11,411, marginally *inside* the ±11,832
   floor — real but not yet proven on the current pipeline.
2. **This is a level effect, and the level is ~0.7–0.8, confirmed twice.** Re-levelling eyay's
   Charge up to our aggressiveness destroys the entire gain (`eyay a × 1.33` = **−62,565** on
   G15–26, worse than us), and scaling our *own* Charge to 0.80 gains **+162,352** on the same
   Games once the censored Charges are handled. Both directions agree: the edge is that eyay
   Charges below `t̂` and we Charge at it. `0.80` beats `0.70`, `0.75` and `0.90` in every window
   we tested, so R5b's `0.7` is directionally right and `0.75–0.80` is the measured optimum here.
3. **Do not copy anybody's Limit.** eyay's Limit on our Charges is **−22,574** over G15–26 and
   **−26,684** over G19–26; TakeTheMoneyAndRun's is −51,447; error404 ai's is −100,186;
   OPUSMOPUS's is −89,432. This confirms the earlier study's 60–75k of imported loss and extends
   it: it is true of *every* donor in the current regime. It was the reverse pre-Game-15 (even
   *makalu's* Limit was worth +48,195 against our old one), which is the measure of how bad our
   Limit used to be and how much it has been fixed.
4. **Our Limit is now a small, unproven upside — loosen it slightly, if anything.** `our b × 1.50`
   is +4,908 over G19–26 and `× 2.00` is +3,684; both inside the floor. Direction: our 154,332 of
   wrongful-rejection penalty is now our largest cost line, and eyay trades 25k of it for 34k of
   over-payment — roughly a wash. Nothing here is worth acting on yet.
5. **Nothing to copy from the Reviewer side at all.** Every hybrid that keeps our Charge and takes
   a donor Limit is ≤ 0 in the current regime. The entire measurable gap is on the **Issuer** side.

### The one caveat that changes a number

A Charge no reviewer ever paid is **censored**, not zero, and scaling `inf` leaves `inf`. So
"scale our own Charge" is bracketed, not point-estimated: with censored Charges left censored,
`our a × 0.80` is **−2,062** on G15–26; with them replaced by the smallest value consistent with
the data (just above the highest Limit in the field, `unrecoverable_floor()`), it is **+162,352**.
The truth is inside that band, and eyay's measured +132,808 sits inside it too. 46 of our 124
post-regime Charges are censored, against 5 of eyay's — the censoring *is* the symptom.

---

## 7. Inferred, not measured

These are arguments from the numbers above, flagged as such.

- **eyay's method is probably "estimate, then discount, then reject".** Its correlation with `t`
  is no better than ours (0.72 vs 0.72 pooled, 0.72 vs 0.76 recently) and its distinct-Charge rate
  is comparable. What differs is a systematic **discount** (median `a/t` 0.68) and a hard line on
  Overcharges (8.0 % accepted pooled, 4.4 % post-15, 7.7 % recently). That is R5b plus R4/R6, both
  of which we already have written down. eyay is not doing something we have not thought of; it is
  doing what our own README proves and we have not fully implemented.
- **TakeTheMoneyAndRun was a beneficiary, not an innovator.** Its pre-15 profit needed a field
  that accepted 27.6 % of Overcharges. When that fell to 18.8 % its net went −22,569 with no
  observable change in its own submission (median `a/t` 0.81 → 0.72, corr 0.44 → 0.64 — if
  anything it got *better* and still lost). This is R5c: a `p(a)` estimate does not survive the
  field, and it is the clearest empirical case for never carrying one across a boundary.
- **The 2,000.00 cluster is probably shared LLM anchoring**, not coordination. Nine teams, one
  round number, an item the policy excludes, and no such number in the Case. If that is right it
  is exploitable in exactly one direction — a **tight** Limit on round numbers — and we already
  had it in G22 (+14,840, the best cell in the field that Game, from rejecting fifteen of fifteen
  Overcharges). It is not exploitable as an *Issuer* strategy, because the same cluster means our
  Overcharge lands against fifteen teams doing the same thing.
- **The `t < 245.70` in Game 22 and `t < 39.62` in Game 27 suggest the field is systematically
  over-pricing items the policy excludes.** Our own median `a/t` in G27 was 8.83 and we still made
  +11,351 because everyone else was worse. That is not a strategy, it is a shared error, and it
  will close.

---

## 8. What to change — one thing

Per CLAUDE.md rule 1b: **change at most one thing.** The one thing with euros behind it in more
than one window and more than one direction of test is the **Charge multiplier: from ~1.0 × t̂ to
0.75–0.80 × t̂**, worth between −2k (pessimistic, censoring left in) and +162k (censoring floored)
over Games 15–26, with eyay's own Charge measuring +132,808 inside that band. Do not touch the
Limit; every donor Limit is a measured loss now, and our own Limit sweep is inside the noise floor
in both directions.

Re-run after every settled Game:

```bash
PYTHONPATH=. python scripts/field_study.py --games all --split 15 --control --per-game --adopt
```
