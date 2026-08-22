# Rivals study — does eyay do anything we can copy?

Commissioned because our deficit is entirely Games 0–18 (unrecoverable) and over Games
19–32 we already out-earn eyay per Game (**+115,405 vs +100,295**). The only question that
matters for the remaining 68 Games: what, specifically, could we adopt from eyay (or
anyone else) that would beat what we already do? Answered with the public leaderboard —
allowed per CLAUDE.md, R9 — and nothing else.

**Headline answer: no. Copying eyay's Charge ratio is a decisive loss (−177,777 over 14
Games, worse in all 14/14). Their Limit ratio initially looked like a gain too small to
prove — that number turned out to be computed against the wrong `t` (see the correction in
§6/§8) and the corrected, actionable version says the opposite: our Limit should be
*tightened*, not loosened. The real, proven lever is not a multiplier at all — it is `t̂`
carrying two opposite biases (overestimated on cheap bounded items, underestimated on
uncertain/high items), which no single multiplier on either Charge or Limit can fix.**

All figures below are reproducible:

```bash
PYTHONPATH=. python scripts/rivals_study.py --decompose --games 19-32
PYTHONPATH=. python scripts/rivals_study.py --decompose --games 1-32
PYTHONPATH=. python scripts/rivals_study.py --counterfactual --games 19-32 --donor eyay --per-game
PYTHONPATH=. python scripts/rivals_study.py --counterfactual --games 19-32 --donor "error404 ai"
PYTHONPATH=. python scripts/rivals_study.py --counterfactual --games 19-32 --donor TakeTheMoneyAndRun
PYTHONPATH=. python scripts/rivals_study.py --sweep --games 19-32
PYTHONPATH=. python scripts/rivals_study.py --calibration --games 19-32
```

`scripts/rivals_study.py` is a **new** script, not an edit to `scripts/rivals.py`.
`rivals.py`'s `measure()` currently has an uncommitted mid-edit that leaves `seen`/`acc`
referenced before assignment (`game_acc` was introduced, the four lines using bare
`seen`/`acc` below it were not updated) — confirmed by calling it directly:
`UnboundLocalError: local variable 'seen' referenced before assignment`. That breaks
`--income`, `--review`, `--anchor`, `--fountain`, `--breaks`. `rivals_study.py` reuses only
the parts of `rivals.py` that are not broken (`load_book`, `Book`, `cap_of`) and the parts
of `replay_payoffs.py` that were never touched (`snapshot`, `our_actual_submission`), and
re-derives income/cost tallying independently. Every reconciliation check below passed
(buckets sum to `identity_net` to the cent), so the independent tallying is not itself a
source of error.

---

## 1. Methodology and verification

- Transactions pulled via `scripts/pull_transactions.py` (paginated to the end, cached,
  self-validating — see its own docstring). 32 Games completed at time of writing
  (`GET /leaderboard/api/games` → 32/100), cache already covered all 17 teams × Games 1–32.
- Fair Value brackets via `scripts/invert_fair_values.py --verify`: **all 20 Games with a
  published `/matrix` cell (13–32) reproduce every team's net to the cent**; Games 1–12 have
  no published cell (outside the trailing 20-Game window) and are trusted on the identity
  alone, which is how `snapshot()` already treats them — confirmed all 32 Games are
  `usable` under `replay_payoffs.reconstruction_report`.
- The Cap is **not** treated as infinite here. `rivals.py`'s own findings (ties at
  `2,000.00` and at non-round `4t` values, corroborated against our own decision log)
  establish `c = max(4t, 2000)` fits every settled row with zero counterexamples. All
  replays below enforce it (`rivals_study.replay_capped`, reimplemented locally so this
  script has no dependency on the broken half of `rivals.py`). This makes every
  Overcharge-side number in this report **conservative**, not inflated.
- Every reconciliation check (`(i)+(ii)-(iii)-(iv) == identity_net`) passed to the cent for
  all four focus teams, in both windows below.
- Noise floor: **26,622 over 18 Games**, scaled `× √(n/18)`. Over the 14 Games in the
  G19–32 window that is **±23,478**.

---

## 2. Charge and Limit placement, Games 19–32

```
team                    items  trusted  capped  censor  a/t p25  a/t med  a/t p75  b/t p25  b/t med  b/t p75
eyay                      107       98       3       6     0.56     1.04     2.99     0.25     0.65     1.00
error404 ai               107       94       2      11     0.68     1.10     2.63     0.47     1.00     1.00
TakeTheMoneyAndRun        107       96       3       8     0.52     0.86     2.19     0.46     0.93     1.00
Bin busy                  107       95       2      10     0.66     1.08     2.47     0.16     0.41     1.00
```

Two things jump out before any counterfactual is run:

- **All four teams' median `a/t` is at or above 1.0.** Nobody in this comparison is
  running R5b's `a* ≈ 0.7·t̂` discipline as measured against the *true* `t`. Ours (1.08) is
  the highest except error404's (1.10) — this reconfirms the bias CLAUDE.md already
  flagged ("median `a/t` was 1.06 when it should be ~0.7") with fresh data from the
  current window, not a new finding but corroboration that it persists.
- **Our median `b/t` (0.41) is the lowest of the four**, and by a wide margin — eyay's is
  0.65, TakeTheMoneyAndRun's 0.93, error404's 1.00. This is the one placement dimension
  where we are the outlier, and it is the one the counterfactual below can actually price.

## 3. The four-bucket net decomposition, Games 19–32

```
team                            net |  (i) inc fair (ii) inc over (iii) cost acc  (iv) penalty
eyay                        100,295 |       193,765       147,413         66,217       174,665
error404 ai                  35,226 |       225,686       116,358        179,376       127,441
TakeTheMoneyAndRun          -26,704 |       181,808        80,819        149,831       139,501
Bin busy                    115,405 |       160,315       173,414         13,925       204,399
```

(i) = income from Charges at or below `t` (structural, owed regardless of the opponent's
Limit). (ii) = income from Overcharges an opponent's Limit happened to admit. (iii) =
every euro paid out as Reviewer on an accepted claim, fair or not. (iv) = the 1.5× penalty
paid on our own wrongful rejections.

Reading it head to head against eyay:

| bucket | eyay | us | our edge |
| --- | ---: | ---: | ---: |
| (i) income fair | 193,765 | 160,315 | **−33,450** (they collect more structural income) |
| (ii) income over | 147,413 | 173,414 | **+26,001** (we collect more from generous opponents) |
| (iii) cost accept | 66,217 | 13,925 | **+52,292** (we pay far less — we accept far less) |
| (iv) penalty | 174,665 | 204,399 | **−29,734** (we wrongfully reject more, and pay for it) |
| **net edge** | | | **+15,110** ≈ our actual +15,110 margin over eyay |

**We already beat eyay on the Reviewer side, not the Issuer side.** Our +52,292 saved on
accept-cost outweighs the extra +29,734 we pay in wrongful-rejection penalty for being
strict — net +22,558 in our favour from Reviewer behaviour alone. We lose ground on the
Issuer side: eyay's (i) is 33,450 higher (they place Charges that land in the fair zone
more often relative to the true value, even though their median ratio is *also* above 1 —
their spread does more of the work), only partly offset by our +26,001 edge in (ii).

**This is the opposite of "eyay must be beating us as Issuer."** They are not, on net — our
issue is the Reviewer side leaves 33,450 on the table relative to them, not that our Charge
placement is worse in aggregate.

## 4. Behaviour on `t_lo = 0` items (plausibly uncovered)

```
team                    t0 items  charged>0  charge%  income collected
eyay                          35         29    82.9%            37,470
error404 ai                   35         25    71.4%            37,064
TakeTheMoneyAndRun            35         28    80.0%            24,636
Bin busy                      35         29    82.9%            49,111
```

`t_lo = 0` means no team's Charge on this item was ever wrongfully rejected — consistent
with `t = 0` (R6c) but not proof of it (also consistent with nobody's Charge happening to
land at or below a low positive `t`). We tie eyay for the highest Charge rate on these
items (82.9%) and collect the most income from them (49,111) — **R6c ("always Charge on
`t = 0` items, it's free") is already something we execute at least as well as anyone in
this comparison.** Nothing to copy here.

## 5. Full history (Games 1–32) — context for why the deficit is unrecoverable, not a new lever

```
team                    items  trusted  capped  censor  a/t p25  a/t med  a/t p75  b/t p25  b/t med  b/t p75
eyay                      364      345       3      10     0.35     0.75     2.00     0.22     0.62     1.00
error404 ai               364      320       2      37     0.55     0.91     2.86     0.44     1.00     1.00
TakeTheMoneyAndRun        364      321       3      34     0.41     0.77     2.14     0.37     0.99     1.00
Bin busy                  364      239       2     118     0.37     1.05     2.58     0.30     1.00     1.27

team                            net |  (i) inc fair (ii) inc over (iii) cost acc  (iv) penalty
eyay                        142,520 |       602,296       211,412        158,826       512,363
error404 ai                  75,645 |       629,105       194,482        329,197       418,746
TakeTheMoneyAndRun           38,825 |       633,248       136,573        371,109       359,887
Bin busy                   -285,939 |       259,091       202,453        278,607       468,876
```

**118 of our 364 Line-Item Charges over the full history are `censored`** — no reviewer
ever accepted or wrongfully rejected them, meaning nobody in the field would pay it at any
price we set (worst case for reconstruction: the Charge is simply unknown and unaffordable
to everyone). That is **32.4%**, against eyay's 2.7%, error404's 10.2%, TakeTheMoneyAndRun's
9.3%. Restricted to Games 1–18 (254 of our items), censoring is **108/254 = 42.5%** — this
is where the deficit lives, and it collapses to **10/107 = 9.3%** by Games 19–32, in line
with the field. This is old, known-and-fixed territory (the `STANDARD_LIMIT`/decision-log
failures CLAUDE.md already documents for Games 21–24 and earlier), presented here only to
show the −401k deficit is a Games 0–18 artefact and not something the current pipeline is
still doing.

---

## 6. The counterfactual: adopt eyay's `(a/t, b/t)` with our own `t̂`, Games 19–32

`t̂` here is the bracket midpoint from `invert_fair_values.brackets` — the same "true"
Fair Value used as the denominator everywhere above. Using it as our own estimate is
**optimistic**: it assumes our real-time estimator is as good as retrospective
reconstruction, so what remains is purely the effect of the *placement rule* (the ratio),
isolated from *estimation error*. Replayed Cap-aware (`c = max(4t, 2000)`) against our real
opponents in each of the 14 Games.

```
submission                                                 total   delta vs us   per Game  verdict
eyay ratio b only (our a, b=0.65t)                       137,278        21,873      1,562  inside noise (+-23,478)
us (actual)                                              115,405             0          0  baseline
eyay ratios: a+b (a=1.04t, b=0.65t)                      -62,372      -177,777    -12,698  LOSS
eyay ratio a only (a=1.04t, our b)                       -84,245      -199,650    -14,261  LOSS
```

**Adopting eyay's Charge ratio is not a marginal loss — it loses money in all 14/14
Games**, not just on average (checked per-Game; every single Game is worse under `a+b` and
under `a`-only than what we actually submitted). It clears the noise floor by 7.6×.
**Adopting only their Limit ratio is a gain, but it does not clear the noise floor** — call
it suggestive, not proven, on its own.

Robustness check against the other two profitable teams, same method:

```
error404 ai ratio b only (our a, b=1.00t)                185,058        69,653      4,975  GAIN            (clears noise floor, 2.9x)
error404 ai ratios: a+b (a=1.10t, b=1.00t)               -11,774      -127,179     -9,084  LOSS
error404 ai ratio a only (a=1.10t, our b)                -81,427      -196,832    -14,059  LOSS

TakeTheMoneyAndRun ratios: a+b (a=0.86t, b=0.93t)        267,740       152,335     10,881  GAIN            (clears noise floor, 6.5x)
TakeTheMoneyAndRun ratio a only (a=0.86t, our b)          207,474        92,069      6,576  GAIN
TakeTheMoneyAndRun ratio b only (our a, b=0.93t)          175,671        60,266      4,305  GAIN
```

Every Charge-side adoption whose ratio sits **above 1.0** (eyay 1.04, error404 1.10) is a
clear loss. The one whose ratio sits **below 1.0** (TakeTheMoneyAndRun, 0.86) is a clear
gain — even though TakeTheMoneyAndRun's own actual net over this window is **negative**
(−26,704). That is the tell that this is not "TakeTheMoneyAndRun is worth copying" (they
are in the red); it is a level effect.

**Correction, added after review (see §8).** Every `b only` row above (eyay +21,873,
error404 +69,653, TakeTheMoneyAndRun +60,266) computes the counterfactual Limit as
`k_b · t_true` — the same oracle substitution §7's Limit sweep used, not `k_b` applied to
our own `t̂`. §8 shows that mistake reverses the sign on the Limit side: redone on `t̂` as it
was actually available, *tightening*, not loosening, wins in every window tested. **Treat
every `b only` number in this section as unproven and superseded by §8; do not act on any
of them.** The `a only` / `a+b` Charge-side rows are not subject to the same reversal —
their claim ("a ratio above 1.0×true-value forfeits R1's risk-free income and loses") is
confirmed independently by §7's Charge sweep using a method that never needed a donor's
ratio at all, so those verdicts stand.

## 7. Isolating the level effect: a flat Charge-multiplier sweep against the real field

Charge = `β·t̂`, Limit held at our own actual `b`, `t̂` = true `t` (oracle), replayed
Cap-aware over the same 14 Games:

```
submission                             total   per Game
a = 1.00t, our actual b              276,980     19,784
a = 0.90t, our actual b              227,450     16,246
a = 0.86t, our actual b              207,638     14,831
a = 0.80t, our actual b              177,919     12,709
a = 0.70t, our actual b              128,389      9,171
a = 0.60t, our actual b               78,858      5,633
a = 0.50t, our actual b               29,328      2,095
a = 0.40t, our actual b              -20,202     -1,443
a = 1.10t, our actual b              -81,400     -5,814
a = 1.20t, our actual b              -83,588     -5,971
a = 1.04t, our actual b              -84,261     -6,019
```

Under **perfect** knowledge of `t`, the optimum is exactly `a = 1.0·t` — which is just
R1's corollary ("within the fair zone, `a = t` strictly dominates every smaller charge")
confirmed on the live field rather than argued. Return declines roughly linearly below 1.0
(nothing catastrophic — every one of these levels still made money) and **falls off a
cliff above 1.0** (−81k to −84k, matching the eyay/error404 counterfactual almost exactly:
1.04 here gives −84,261 against eyay's measured-ratio test giving −84,245 for the
`a`-only variant — independent confirmation the two methods agree).

**This means R5b's `0.7·t̂` recommendation is a hedge against *our own estimation error*,
not a property of the payoff table itself.** With perfect information there is no error to
hedge against, so `a = t` wins outright — exactly the "under certainty, `a = t = b` is
optimal" statement in `README.md`'s corrections table. The practical read: our real `t̂` is
not perfect, so R5b's shrinkage still applies to *our own* estimator; what this sweep rules
out is copying eyay's or error404's **ratio** as a fix, because both sit above 1.0 and
therefore land on the losing side of this curve regardless of whose estimator produced it.

The matching Limit-multiplier sweep (Charge held at our own actual, `b = α·t_true`, **oracle
`t`, not our own estimate**):

```
limit mult (b=k*t_true)        total   per game
1.00                          185,058     13,218
0.93                          175,671     12,548
1.20                          159,668     11,405
0.80                          156,342     11,167
0.65                          137,311      9,808
0.50                          124,954      8,925
0.41 (≈ our actual)           119,604      8,543
0.30                          114,929      8,209
0.20                          112,464      8,033
1.50                          109,856      7,847
2.00                           63,043      4,503
```

**Retracted conclusion, corrected in §8 below.** This table's flat, broad shape (114,929–
185,058 from 0.20 to 1.20) held here originally read as "moving our Limit multiplier toward
0.65–1.0 is upside with limited downside." **That reading is wrong and has been withdrawn.**
The multiplier here is applied to the reconstructed *true* `t` — a number we cannot know at
decision time — so this table measures the value of *already knowing* `t`, not the value of
loosening a multiplier on our own estimate. It is kept for reference (it is the internal
cross-check that R1's "under certainty, `a = t = b`" corollary reproduces the live field
exactly), but no Limit-multiplier decision should be read out of it. §8 redoes this on `t̂`
as it was actually available at decision time, and the conclusion reverses.

---

## 8. Correction — the Limit sweep redone on `t̂`, not `t_true`

A challenge from review, quoting `src/pricing.py`'s own Game-26 audit (`0.30 → 0.85` loosens
the Limit and *loses* — 52,272 of penalty recovered against 54,969 of new Overcharges plus
34,848 of claims we owed) against the §7 oracle table's implied "loosen toward 0.65–1.0."
The two cannot both be right on the same knob, and the oracle table is the one at fault:
`price_item` never sees `t_true`, only its own `t̂` (`price_median`, from
`var/decisions/game_NNN.json` where a decision log exists — Games 26–33 — and from
`combine(model, memory)` on the cached evidence in `var/evidence/case_NN_*.json` otherwise).
Redone below with `t̂`, matched item-for-item against the same oracle column so the gap
between them is the value of a better estimate and nothing else (any item without a
recoverable `t̂` falls back to our own actual `b` in *both* columns, so the comparison is
never confounded by coverage differences). `scripts/rivals_study.py --calibration`.

**Caveat on the reconstruction itself:** `var/evidence/*_memory.json` is unconditionally
overwritten every time `dump_evidence.py` runs, and at least one case's mtime (case 29,
evidence at 21:08 vs. its decision log at 20:53 — *after* the decision) shows the cache has
been refreshed later than the live decision. So the Games-without-a-log `t̂` may carry a
richer Price Memory than genuinely existed at decision time. That can only make the
reconstructed `t̂` look *better* than it really was, never worse — a bias against finding
what follows, not for it.

### `b = k·t̂` (actionable) vs `b = k·t_true` (oracle), Games 19–32 — 103/107 items matched (96.3%)

```
     k      b=k*that   per game |    b=k*t_true   per game | gap (value of a better estimate)
  0.20       109,123      7,794 |       114,344      8,167 |            5,222
  0.30        84,792      6,057 |       116,810      8,344 |           32,017
  0.40        62,825      4,487 |       120,757      8,625 |           57,932
  0.50        49,705      3,550 |       126,357      9,026 |           76,652
  0.60        36,754      2,625 |       135,261      9,661 |           98,507
  0.70        27,709      1,979 |       144,119     10,294 |          116,409
  0.80        13,318        951 |       156,291     11,164 |          142,973
  0.90           924         66 |       168,831     12,059 |          167,907
  1.00       -14,452     -1,032 |       182,538     13,038 |          196,990
  1.10       -40,017     -2,858 |       166,955     11,925 |          206,972
  1.20       -58,845     -4,203 |       157,148     11,225 |          215,993
  1.50       -87,050     -6,218 |       107,337      7,667 |          194,387
```
noise floor over 14 Games: ±23,478.

**The actionable column is monotonically decreasing.** `k = 0.20` (the loosest tested is the
*tightest* multiplier, +109,123) beats every looser value, `k = 1.00` is already negative
(−14,452), and `k = 1.50` is the worst tested (−87,050) — the opposite shape from the oracle
column, which peaks at `k = 1.00` (+182,538) exactly as R1 predicts under certainty. **§7's
"loosen toward 0.65–1.0" is wrong; the live field and `t̂` as we actually have it say the
opposite: tighten.** This matches `src/pricing.py`'s own audit in direction.

### `b = k·t̂` vs `b = k·t_true`, all pre-swap settled Games (1–33, 342/370 items matched, 92.4%)

```
     k      b=k*that   per game |    b=k*t_true   per game | gap
  0.20      -244,891     -7,421 |      -235,419     -7,134 |            9,472
  0.30      -269,082     -8,154 |      -227,180     -6,884 |           41,902
  0.50      -296,454     -8,983 |      -193,243     -5,856 |          103,211
  0.70      -311,728     -9,446 |      -131,404     -3,982 |          180,323
  1.00      -334,021    -10,122 |        -7,138       -216 |          326,882
  1.20      -389,645    -11,807 |       -63,419     -1,922 |          326,226
  1.50      -436,343    -13,223 |      -139,952     -4,241 |          296,391
```
noise floor over 33 Games: ±36,046. Same shape, same conclusion, full history: `k = 0.20` is
the best of the tested range on the actionable column and the curve never turns back up.

### Held-out folds, `t̂` column only (does the direction survive a split?)

```
fold                games   k=0.20    k=0.50    k=1.00    k=1.50   shape
G19-32 odd          7       66,370    42,377    14,107   -34,116   monotone decreasing
G19-32 even         7       42,753     7,327   -28,559   -52,935   monotone decreasing
G1-20               20    -309,362  -296,436  -269,178  -325,944   min at k≈0.9, both ends worse
G21-32              12       64,142     3,674   -48,403   -96,556   monotone decreasing
```
Three of four folds are monotone-decreasing over the whole tested range — tightening never
stops helping in the data we have. G1–20 is the one exception: it bottoms out near `k ≈
0.9–1.0` rather than at the low end, but even there `k = 1.0` (−269,178) is worse than `k =
0.30` (−308,402) is *not* true — G1–20 is dominated by the Games-0–18 pipeline failures
already covered in §5 (42.5% of our items censored) and both ends of its curve are deeply
negative regardless of `k`; it is not evidence *for* loosening, it is evidence that no Limit
multiplier fixes a Charge nobody could ever pay. The three folds least contaminated by that
era (odd/even/G21-32) agree with each other and with the pooled result.

### What the extra accepts a looser Limit buys, Games 1–33 (`k: 0.30 → 1.00`)

```
extra accepts that were fair Charges:   1,450  (penalty saved:     174,131)
extra accepts that were Overcharges:      621  (cost incurred:     239,070)
net of this swap alone: -64,939  (tightening wins)
```
Over G19–32 alone the same swap is −99,244 (389 fair / 49,226 saved vs 261 Overcharge /
148,470 incurred). **Loosening the actionable Limit buys more Overcharges than fair claims,
in euros, in every window tested** — the reverse of what a well-calibrated `t̂` would do, and
the direct mechanism behind `pricing.py`'s finding.

### Why: `t̂` is biased, but in two different directions depending on the item

```
                                       n     p25   median    p75
G1-33, t < 100, BOUNDED true t       142    1.32     3.59   10.72   -- wildly OVERestimated
G1-33, t < 100, UNBOUNDED (t_lo)      21    0.80     0.87    1.01
G1-33, 100<=t<500, BOUNDED            77    0.89     1.09    1.42
G1-33, 100<=t<500, UNBOUNDED          45    0.64     0.89    1.02
G1-33, t>=500, BOUNDED                27    0.72     1.14    1.35
G1-33, t>=500, UNBOUNDED (t_lo)       23    0.71     0.90    1.09
```

Two coexisting, opposite biases, not one:

1. **Cheap items with a fully-bounded true `t` (n=142) are overestimated 2–3.6× at the
   median**, up to 10.7× at p75. This is what makes loosening the multiplier expensive: on
   the volume of cheap items, `k·t̂` blows past the true `t` fast, and every one of those
   extra accepts is an Overcharge.
2. **Every "unbounded" bucket — where nobody has ever wrongfully rejected an item, so the
   true `t` is only known to be *at least* `t_lo`, plausibly much higher — sits at a median
   `t̂/t_lo` of 0.87–0.90, i.e. *below even the most conservative lower bound* on the true
   value.** Since the real `t` for these items is ≥ `t_lo` and typically unknown above that,
   the true `t̂/t` ratio is almost certainly lower still. This is the direct mechanism behind
   the live digest's `charge-far-below-t` cases ("we charged 370 against `t ≥ 837`", "238
   against `t ≥ 536`") — the anecdote is not a Charge-stage or Limit-stage failure, it is
   this same underestimate on an uncertain item, showing up once as forgone Issuer income
   and again as a wrongful-rejection penalty when the same low `t̂` sets our own Limit.

**No single multiplier `k` fixes both.** Scaling `t̂` up helps the underestimated,
high-uncertainty tail and actively worsens the already-overestimated cheap-bounded majority;
scaling it down does the reverse. This reconciles the plateau this study first reported with
`pricing.py`'s conclusion, and points at the estimator, not the multiplier — consistent with
`hypothesis-ledger.md` H2 (a single recalibration function was already tried and falsified),
but sharper: the split is by *censoring status* (bounded vs. unbounded true `t`), not by
price level alone.

### The model swap (Games 33 → 34, gpt-5.4-mini → gpt-5.6-terra at 21:48)

Every table in this section is pre-swap: Game 33's decision log is timestamped 21:44:38,
before the 21:48 swap, and is included. **Game 34 is the only settled post-swap Game as of
this writing** (decision log at 21:57) — one Game is far inside any noise floor (§ noise-
floor convention: ±26,622 scaled `√(n/18)`, undefined and meaningless at `n = 1`), so nothing
here can or does say anything about the new model's calibration. A quick, explicitly
anecdotal look at G34 alone shows the *same* bounded/unbounded split shape (bounded `t<100`
median `t̂/t = 1.54`, p75 = 7.56; unbounded buckets still sit under 1.0) — consistent with,
not yet evidence for, "the swap didn't change this failure mode." **Re-run
`--calibration` once ~10+ post-swap Games settle; nothing in §6–§8 should be assumed to carry
across the boundary until then (CLAUDE.md rule 9).**

---

## 9. What this does and does not license

**Proven (clears the noise floor, and consistent across the Charge sweep, three donors'
ratios, and the four-bucket decomposition):**

- Do **not** import eyay's or error404's Charge ratio. Both sit above 1.0·`t` and both lose
  money on our real field, in every Game tested, not on average — confirmed two independent
  ways (§6's donor replay, §7's donor-free multiplier sweep).
- Do **not** loosen the Limit multiplier. §8's `t̂`-based redo — the one that answers "what
  should we actually submit" rather than "what would knowing `t` have been worth" —
  monotonically favours *tightening*: `k = 0.20` beats every larger `k` tested, in three of
  four held-out folds, over both the G19–32 window and the full pre-swap history, and the
  extra accepts a looser Limit buys are Overcharges more than fair claims in euros in every
  window (§8). This reverses this study's original §7 conclusion; see the correction notes
  in §6 and §8 for what changed and why.

**Proven, mechanism identified:** `t̂` carries two opposite biases, not one — cheap items
with a fully-bounded true `t` are overestimated 2–4× at the median (up to 10.7× at p75),
while every item whose true `t` is only a lower bound (nobody has ever wrongfully rejected
it) sits at a median `t̂/t_lo` of 0.87–0.90, i.e. *underestimated relative to even the most
conservative bound*. No Limit or Charge multiplier fixes both at once; this is an estimator
problem, split by censoring status rather than by price level, and it is the direct
mechanism behind the live digest's `charge-far-below-t` cases.

**Not proven (inside the noise floor):** eyay's own Limit ratio test in §6 specifically —
retracted along with every other `b only` row there; see the correction note in §6.

**Not new, reconfirmed:** our own median `a/t` (1.08 over G19–32) is *already* above 1.0 —
in the loss region of §7's Charge sweep, which is not affected by the oracle-vs-`t̂`
correction (see §6's correction note for why the Charge side is exempt) — matching the bias
CLAUDE.md already tracks (`median a/t was 1.06 when it should be ~0.7`).

**Explicitly not assessed:** anything about Games 34+ (gpt-5.6-terra). One settled Game
post-swap is not evidence in either direction (§8).

**The honest bottom line, corrected:** eyay is not doing anything on the Issuer side that
beats us — we already win that comparison net, because our Reviewer discipline is worth
more than their Issuer placement edge (§3). Nothing in this study says to copy anyone's
Charge or Limit ratio: the Charge-side finding is a clean "don't" (stay disciplined, if
anything tighten our own 1.08 toward R5b's ~0.7), and the Limit-side finding — corrected
after review — is also "don't loosen," for a different, estimator-shaped reason: the fix is
narrowing `t̂`'s two biases, not moving a multiplier in either direction.
