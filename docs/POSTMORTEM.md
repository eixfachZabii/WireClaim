# Post-mortem — 100 Games, 5th of 17, +238,255.07

Written after the last Game settled, against the complete public record. Every number here is
reconstructed from the 315,792 settled Transactions and agrees with the published leaderboard
**to the cent** for all seventeen teams; the reconstruction is the gate, and
`scripts/archive_tournament.py` refuses to write the archive if any team disagrees.

The measurements live in [`data/tournament/`](../data/tournament/standings.md) and the
hypotheses they settle are **H21–H25** in the
[hypothesis ledger](brainstorm/sebi/strats/review/hypothesis-ledger.md).

---

## 1. Where we finished

| # | team | final net | Games 1–80 | Games 81–100 (unweighted) |
| ---: | --- | ---: | ---: | ---: |
| 1 | Codacabana | 830,035.57 | 207,369 | 207,555 |
| 2 | eyay | 737,480.94 | 285,827 | 150,551 |
| 3 | TakeTheMoneyAndRun | 571,101.10 | −28,300 | 199,800 |
| 4 | error404 ai | 427,410.74 | 339,051 | 29,453 |
| **5** | **Bin busy (us)** | **238,255.07** | **−55,744** | **97,999** |
| 6 | Non Deterministic | 146,689.59 | −111,526 | 86,072 |
| … | | | | |
| 17 | makalu | −4,052,816.56 | −2,404,212 | −549,535 |

Games 81–100 pay **3×**. That weighting appears in no handout we were given; it is the unique
factor that makes the settled rows reproduce all seventeen published totals simultaneously,
which is a stronger form of evidence than being told.

Eleven of seventeen teams finished negative, four of them past −1.5 M. The default submission is
not a floor — `b = 0` wrongfully rejects every fair Charge and pays `1.5a` for it, so a team
that goes dark becomes a money fountain. Replaying our own Games under `a = 0, b = 0` gives
**−3,737,366**. Simply showing up was worth 3.96 M.

---

## 2. Where the money went

Every euro that moved sits in exactly one branch of the payoff table
(`scripts/postmortem.py`, all 100 Games, unweighted):

| as Issuer | rows | money |
| --- | ---: | ---: |
| charged at or below `t` — paid by all sixteen | 17,041 | 2,225,531 |
| charged above `t` — paid only by the loose | 1,535 | 488,981 |
| **total income** | | **2,714,513** |

| as Reviewer | rows | money |
| --- | ---: | ---: |
| paid a fair claim — correct, unavoidable | 2,817 | 515,304 |
| **wrongful rejection — paid `1.5a`** | **3,873** | **1,972,147** |
| Overcharge accepted — fraud let through | 897 | 184,806 |
| rightly rejected — paid nothing | 10,989 | 0 |
| **total cost** | | **2,672,257** |

The headline is the third row. **We rejected 3,873 fair claims and accepted 2,817** — we turned
away 58 % of every honest claim shown to us — and the pure-penalty half of that bill,
the `0.5a` surcharge, is **657,382**. That is fifteen times our entire unweighted net.

It does not follow that the Limit was simply too low, and the obvious fix does not survive
contact with the folds. Scaling our real Limit by λ over all 99 reconstructable Games:

| λ | 1.0 | 1.1 | 1.25 | 1.4 | 1.5 | 1.75 | 2.0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 0 | +54,625 | +113,382 | +129,874 | **+133,888** | +109,019 | +72,000 |
| odd ids | 0 | +8,936 | +1,496 | +6,302 | +6,455 | −1,058 | −27,071 |
| awake 1–43 | 0 | +2,458 | −4,873 | −8,105 | −11,863 | −15,777 | −45,402 |
| recal 82–100 | 0 | +39,719 | +95,908 | +119,803 | +128,831 | +121,565 | +116,609 |

The whole gain is in the last third of the tournament, which the 3× weight then triples. On odd
ids it is nothing; in the awake regime it is negative. **The Limit is not uniformly too low —
it fails to discriminate**, and a scalar cannot fix a ranking problem.

---

## 3. The ceiling, and what it rules out

Four submissions, same Games, same Field, weighted (`scripts/experiments/ceiling.py`):

| rung | net |
| --- | ---: |
| DEFAULT `a = 0, b = 0` | −3,737,366 |
| **ACTUAL — what we submitted** | **224,840** |
| BEST-KNOB — best `(α, β)` over 72 cells on our own `t̂` | 109,248 |
| ORACLE `a = b = t` | 4,488,842 |

**The best constant-only strategy available anywhere in the grid scores 115,593 _worse_ than
what we actually shipped.** The pricing rules are not merely near their optimum — a global
multiplier can only make them worse, because the shipped rule already varies its factor with
the band and a constant throws that away.

So of the 4,264,002 still on the table above ACTUAL: **103 % is estimation, −3 % is decision
rules.** We captured 5 % of what perfect knowledge was worth.

### What accuracy costs, in euros

Perturbing the *true* Fair Value by a lognormal of known width and replaying with the shipped
rule (`scripts/experiments/price_of_sigma.py`) turns "improve the estimate" into a price list:

| σ | 0.00 | 0.10 | 0.20 | 0.30 | 0.45 | 0.60 | 0.75 | 0.90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| net | 2,324,912 | 2,090,251 | 1,814,964 | 1,264,589 | 396,211 | −155,324 | −604,370 | −1,013,234 |

Our real submission (224,840) sits at an **effective σ ≈ 0.52**; net crosses zero at σ ≈ 0.57.
The steepest segment in the table, **σ 0.45 → 0.30 = +868,378**, is the one adjacent to where we
stand — roughly **5.8 M weighted per unit of log error**. Any future evidence-layer proposal can
be priced before it is built.

---

## 4. Two things we believed that were not true

### The "+19 % estimation bias" does not exist

Scoring `log(t̂ / t)` on Line Items whose Fair Value bracket is **bounded** gives a median
`t̂ / t` of 1.189, an RMSLE of 0.658, a published band that understates the real error by
**1.88×**, and 27.5 % of truths outside our own stated 90 % interval. Every one of those looks
like a clear, actionable level error.

A bracket is bounded **only when somebody rightfully rejected**, which selects exactly the
sub-population where the Field overestimated. Splitting the 531 usable Line Items:

| | n | median |
| --- | ---: | --- |
| bounded brackets | 342 | `t = 0.841 × t̂` — we overestimate |
| right-censored (`t ≥ t_lo` only) | 189 | `t ≥ 1.044 × t̂` — we **underestimate, provably** |

85.2 % of the censored items have a proven floor above the bounded sample's median residual, and
**60.8 % are provably worth more than our estimate.** Fitting the residual as interval-censored
data instead — Turnbull's NPMLE, `src/pricing/calibration.py`, 17 tests — puts the pooled median
`t / t̂` at **0.982**. We were essentially unbiased the whole time.

The pricing layer built on the bad diagnosis was scored leave-one-Game-out over 73 Games and
**lost at every one of 42 cells** (best −36,050, worst −2,812,204). Handling the censoring
properly recovered +71k of that and it still loses, so `calibration.py` ships as a *measurement
instrument only*, with a banner saying so.

**This is the fifth time this repository has been caught by the same selection** — it is the
mechanism behind CLAUDE.md's `t̂`-bucketing entry, and behind H2 and H16. The tool now exists to
stop the sixth.

### Price Memory should *not* get more of the blend

Rebuilt from all 100 Games and scored leave-one-out: **recall 79 % (609/773), σ 0.458, bias
+0.031, median |log error| 0.260.** Its own docstring claimed **22 % recall** and "four items in
five are misses" — measured over Cases 1–14, and stale for most of the tournament. The tracked
store was worse: **203 entries from Games 1–46**, against 325 available from the full record.

From "memory is far more accurate than the model" it seems to follow that memory should take
more of `blend.combine` than its shipped 66 %. Swept walk-forward over 99 Games:

| memory share | 0.66 (shipped) | 0.75 | 0.83 | 0.92 | 1.00 |
| --- | ---: | ---: | ---: | ---: | ---: |
| gain vs. our submission | **+62,827** | +61,190 | +48,638 | +31,173 | +13,372 |

Monotonically down. **The inverse-variance weighting was already right; what was wrong was the
store.** Both constants stay as they are.

---

## 5. What actually decided the tournament

Replaying all 100 Games with the *finished* Price Memory, letting a hit price the item outright
(`scripts/experiments/memory_first.py`, leave-one-Game-out): **+855,591 weighted against our
real +224,840** — a gain of **+630,751**, positive on all five folds. That is first place.

The caveat is larger than the result:

- improved 54 Games, worsened 28, unchanged 17
- **median Game gain +190** — the typical Game barely moves
- the top 8 Games carry **611,476 of 630,751**; without them, **+19,275**
- **seven of those eight are Games 7–18**
- walk-forward — a store built only from strictly earlier Games, which is what the live pipeline
  had — the same arm is worth **+13,372**, not +630,751

`scripts/postmortem.py` independently ranks the worst Games of the tournament as G8, G17, G10,
G100, G12, G18, G11, G7. It is very nearly the same list, arrived at from the money rather than
from the counterfactual.

> **Games 1–25 cost −322,595 weighted. Games 26–100 earned +560,850.**

Had Games 1–25 merely scored **zero** we finish 3rd. Had they scored the per-Game average of
Games 26–100 we finish **2nd**. The binding constraint was never steady-state accuracy — in
steady state the finished store moves the median Game by €190. It was the **cold start**: an
empty Price Memory, and a pipeline that did not have Strategy 2 until Game 26.

---

## 6. The counterfactual, scored properly: we would have won

§5 reports *our* net, which is the wrong number for a question about placement. The tournament
is not seventeen independent scores — every euro we are paid is a euro an opponent pays, and
every claim we accept is income for the team that issued it. So the whole table has to move:

    we Charge closer to t   →  our income rises AND sixteen opponents' costs rise
    we accept more claims   →  our costs rise AND sixteen opponents' income rises

Only the fixtures that involve us can change — an opponent's games against the other fifteen are
untouched by anything we do — which gives an exact decomposition per team:

    net(T, counterfactual) = net(T, actual) − [T's fixtures vs us, as settled]
                                            + [T's fixtures vs us, under our new submission]

`scripts/experiments/counterfactual_standings.py --validate` computes that middle term two
independent ways — through the replay model and straight from the settled Transaction rows — and
they agree to **0.0000** across every (Game, team) pair. The `ACTUAL` arm reproduces the real
standings exactly, so the first row of its output is a test rather than a result.

### The arms

| arm | weighted | Games 1–25 | Games 26–100 | rank |
| --- | ---: | ---: | ---: | ---: |
| **ACTUAL** — what we submitted | 238,255 | −322,595 | 547,435 | **5th** |
| **NO-BLANKS** — only the blanks repaired | 645,362 | 69,872 | 562,075 | **3rd** |
| **WARM-STORE** — the finished Price Memory from Game 1 | 869,006 | 238,293 | 617,298 | **1st** |
| **FULL-PIPELINE** — warm store + model channel ⁽*⁾ | **885,401** | 254,688 | 617,298 | **1st** |

⁽*⁾ the only arm with a synthetic component. Games 26–100 already *have* the mature model
channel — it is what we really ran, so a miss there keeps our real submission and nothing is
invented. Games 1–25 have no model reading at all, so a miss is priced by drawing from the
residual the model really produced later (`C:model` stratum of the censoring-aware fit).
Averaged over 5 seeds.

**`NO-BLANKS` is the one to read first**, because it assumes no better estimate anywhere. Games
1–25 failed in two ways, both of which produce *zero* income rather than inaccurate income:

- **we Charged exactly nothing** — 22 of 22 Line Items in Game 11, 12 of 12 in Game 12, and all
  of Games 2 and 3;
- **we Charged so far above the Field that no reviewer's Limit reached it** — 27 of 39 Line Items
  in Game 8, 14 of 29 in Game 15, 13 of 20 in Game 17. Game 20's median Charge was 2,345.

Replacing only those with the Field's own median Charge on the same Line Item — no model, no
memory, just what the other sixteen teams thought the item was worth — is worth **+407,107** and
moves us from 5th to **3rd**.

### The final table, every row recomputed

| # | team | FULL-PIPELINE | vs actual | moved |
| ---: | --- | ---: | ---: | --- |
| **1** | **Bin busy (us)** | **885,401** | **+647,146** | **5 → 1** |
| 2 | Codacabana | 818,984 | −11,051 | 1 → 2 |
| 3 | eyay | 733,018 | −4,463 | 2 → 3 |
| 4 | TakeTheMoneyAndRun | 547,290 | −23,811 | 3 → 4 |
| 5 | error404 ai | 436,410 | +8,999 | 4 → 5 |
| 6 | Non Deterministic | 137,456 | −9,234 | — |
| 7 | Teamers | −128,098 | +14,968 | — |

We finish first by **66,417**. Note that five opponents move by less than 12,000 and two of them
*gain* — the second-order effect is real but modest, and it does not rescue anyone.

### Why the arithmetic does not balance, and why that is the point

Under `WARM-STORE` we gain **+630,751** while the other sixteen lose only **−196,827** between
them. The missing **+433,924** is not an error: **the payoff table is not zero-sum.** On a
wrongful rejection the reviewer pays `1.5a` and the issuer receives only `a`, so `0.5a` leaves
the system entirely. Across all seventeen teams the tournament settled at a combined
**−13,862,270** — the Field collectively burned that on lawyers.

So most of what we would have gained was never anyone else's to lose; it was being destroyed.
`NO-BLANKS` is the instructive counter-example: it *increases* total destruction by 80,314,
because Charging the Field median on previously-blank items pushes more claims above opponents'
Limits and burns more surcharge. Charging a *good* estimate at `0.69 ×` stays under most Limits
and burns less.

### What the arms say about where the value is

`FULL-PIPELINE` beats `WARM-STORE` by only **+16,395** — the simulated model channel adds
almost nothing on top of the store. And 89 % of the total gain sits in Games 1–25:

    Games 1-25    -322,595  ->  +254,688     a swing of  577,283
    Games 26-100   547,435  ->   617,298     a swing of   69,863

The finished strategy was worth about seventy thousand over the mature phase, and more than half
a million over the phase where we did not have it yet.

---

## 7. Is `a = t̂ = t = b` the optimal strategy?

Half of it, exactly. And the way the other half fails explains every discount in the pipeline.

Sweeping the oracle over the 99 reconstructable Games — `t` known exactly, the Field held at
what it really did — both `a = t` and `b = t` are the argmax. But the surfaces around them are
nothing alike.

**The Charge is a cliff.**

| `a / t` | 0.70 | 0.90 | 0.99 | **1.00** | **1.01** | 1.10 | 2.00 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| weighted net | 2,394,716 | 3,790,800 | 4,419,038 | **4,488,842** | **−1,549,760** | −1,590,879 | −1,958,844 |

**One per cent over the Fair Value costs 6,038,602.** The mechanism is the payoff table: at
`a ≤ t` the Issuer is paid `a` by **all sixteen** opponents, whether they accept or wrongfully
reject, because a wrongful rejection still owes the money. One cent above `t` and that guarantee
is gone — income collapses to whichever opponents' Limits happen to reach `a`, while our costs
as Reviewer are unchanged. The net goes negative.

**The Limit is an asymmetric valley.**

| `b / t` | 0.50 | 0.90 | 0.99 | **1.00** | 1.01 | 1.10 | 2.00 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| weighted net | 3,480,755 | 4,181,915 | 4,375,315 | **4,488,842** | 4,483,439 | 4,339,686 | 3,644,135 |

1 % low costs 113,527; 1 % high costs 5,403. **Erring high is 21× cheaper**, because a Limit
below `t` pays the `1.5×` surcharge on claims that were fair, while a Limit above `t` merely
pays face value on some Overcharges.

**So the answer is: yes under certainty, and that is exactly why it is wrong in practice.**
`t̂ = t` is the goal, not a choice — and the moment `t̂ ≠ t`, setting `a = t̂` puts us on the wrong
side of a six-million-euro discontinuity on every Line Item we overestimate, which is about half
of them. The `0.7` multiplier is not timidity; it is **the price of insurance against a
cliff**, and R5b's finding that it beats `a = t̂` at every σ ≥ 0.1 follows directly from the
shape above.

The two shapes also say where effort belongs, and they disagree with each other:

- the **Charge** must sit under `t`, the penalty for missing is unbounded, and a deep discount
  is correct;
- the **Limit** is flat near the top and cheap to overshoot, so it belongs at or slightly above
  the estimate — the opposite of the "put the buffer down" instinct.

Recorded as **R11** in [`GAME-AND-PROOFS.md`](GAME-AND-PROOFS.md).

---

## 8. So what do we actually target for `a` and `b`?

R11 gives the boundary condition; this is the working rule at the accuracy we actually have.
Two independent routes, and they agree.

### The Charge: `a ≈ 0.75–0.80 × t̂`, with a shallow σ-slope or none

**Route one, derived.** Income from Charging `a = m · t̂` is `m · P(t ≥ a)` per opponent — at
`a ≤ t` the Issuer is paid by all sixteen whether they accept or wrongfully reject, and R5c says
to credit nothing above `t`. With the residual unbiased (§4) and `σ ≈ 0.52`, maximising
`m · P(r ≥ log m)`:

| σ | 0.15 | 0.25 | 0.35 | 0.458 | **0.52** | 0.60 | 0.75 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| best `m` | 0.805 | 0.760 | 0.745 | 0.760 | **0.780** | 0.820 | 0.945 |
| flat within 1 % | .77–.83 | .71–.80 | .69–.80 | .69–.83 | **.70–.86** | .73–.92 | .82–1.07 |

The striking thing is how **flat in σ** the optimum is: `m` sits at 0.74–0.82 across the entire
practical range. It is *not* monotone — it dips to 0.745 at σ 0.35 and rises again in the
high-σ tail, where the lognormal's long right tail makes a big Charge cheap to try. So the
correct reading is not "better estimates let you charge more"; it is **the multiplier barely
depends on σ at all**, which is a much stronger statement about the rule's shape.

**Route two, swept.** Holding the Limit at what we really submitted and varying only
`a = clamp(A − B·σ̂, 0.30, 0.80) · t̂` over the 73 Games with a logged estimate (baseline
541,018): every competitive cell has a **shallower slope or higher intercept** than the shipped
`A = 0.85, B = 0.45`. The best is `A = 0.85, B = 0.25` at **636,422 (+95,404), positive on all
four folds**; `A = 0.75, B = 0` — a flat 0.75 — reaches 610,956.

**Caveat, and it is why no constant is being changed on this alone.** The swept surface is
*jagged*: `0.85/0.25` scores 636,422 between neighbours at 498,841 and 561,143. A jagged surface
means the argmax is riding specific Charges crossing specific opponents' Limits, not sitting on
a smooth optimum. The cell is in-sample. What survives is the **direction** — the shipped rule's
effective factor of **0.69** at typical σ sits on the low edge of the derived flat zone
(0.70–0.86), and both routes say it belongs nearer **0.78**.

### The Limit: keep the shipped per-item stack — do not flatten it

The one thing measured unambiguously here. Replacing the shipped Limit (a posterior quantile,
capped by `LIMIT_CEILING` / `LIMIT_CEILING_MEMORY`, with the clamp released) by **any** flat
multiple of `t̂` is expensive: `b = 1.0 · t̂`, the best flat value, costs **−141,650** against
what we really submitted. The per-item logic is carrying real information that a constant
discards.

R11 says which way to err if you must: 1 % low costs 113,527 and 1 % high costs 5,403, so the
Limit should sit **at or slightly above** the estimate, never below. The pipeline already
reflects this — `LIMIT_CEILING_MEMORY` is 1.00 and the `b ≤ a` clamp was released at Game 66.

### And `t̂ = t` is still the whole game

Neither of the above is where the money is. §3 puts **103 % of everything still available** in
estimation and §3's price list values it at ~5.8 M weighted per unit of log error. The Charge
multiplier is worth tens of thousands and is nearly flat in σ; the estimate is worth millions.

---

## 9. What to do differently

1. **Ship the store warm.** `data/price_memory.json` now holds all 325 wordings from 1,161
   joined Line Items across 100 Games, not 203 from 46. It is the one asset measured here that
   is worth six figures and cannot be re-derived inside a 60-second window. This is the whole
   fix for the finding in §5.
2. **Stop tuning constants.** §3 shows the best constant available is worse than what we ship.
   Four separate sweeps in the ledger say the same thing. The budget belongs in the evidence
   layer, and `price_of_sigma.py` says what a given improvement there is worth.
3. **Fit residuals with the censored observations in.** §4 is the fifth instance of the same
   error. `src/pricing/calibration.py` exists so the sixth is caught before it costs eight
   experiments.
4. **Get to a working pipeline sooner, and treat early Games as the prize they are.** Games
   1–25 were 25 % of the schedule and −135 % of the final score. Rule 8 already says uptime
   outranks accuracy; §5 says *maturity* outranks accuracy by more.
5. **The Limit still deserves work, but not a multiplier.** §2 shows 657,382 of pure lawyer
   surcharge and §3 shows no constant reaches it. It is a per-item discrimination problem, which
   means it is an evidence problem too.
6. **Any replacement `t̂` estimator has a hard spec: σ < 0.60 on the Line Items Price Memory
   misses.** Below that it pays (0.458 → +118,864; 0.35 → +292,212), above it does not
   (0.60 → −15,587). Robust on 4/4 folds. The model channel is at ~1.0 there.

   Two candidates have now been built and measured against it, and the spec called both in
   advance. **Case-anchored recalibration** improves the estimate (0.887 → 0.756) and does not
   pay. **Comparative retrieval estimation** — a live Gemini 3.1 Pro shown eight settled Line
   Items with their exact Fair Values and asked which the unpriced item resembles and by what
   multiple — reaches **0.867**, beats a same-model direct-pricing control (0.943) on 60 % of
   items, and still costs **−26,988**; stacked on the warm store it makes it *worse*. See
   H28–H29.

   The most useful number in that pair: DIRECT and ANCHORED differ by 0.076 in RMSLE and by
   **262,776 in euros**, because DIRECT's small positive bias walks into R11's Charge cliff.
   **Never rank estimators on log error alone.**

   What it implies is not "the model needs to be smarter". The items memory misses are ones whose
   wording has never settled; pricing those from wording alone looks intrinsically hard, and
   memory clears the bar only because it has seen the answer. That is a data problem, and the
   lever is the one already measured — ship the store warm.

---

## Reproducing any of this

```bash
set -a && . .env && set +a
PYTHONPATH=. python scripts/archive_tournament.py            # verify + freeze the record
PYTHONPATH=. python scripts/postmortem.py                    # §2, the money decomposition
PYTHONPATH=. python scripts/experiments/ceiling.py           # §3, the four rungs
PYTHONPATH=. python scripts/experiments/price_of_sigma.py    # §3, what accuracy is worth
PYTHONPATH=. python scripts/experiments/estimate_calibration.py   # §4, the naive diagnosis
PYTHONPATH=. python scripts/experiments/calibration_backtest.py --sweep   # §4, why it loses
PYTHONPATH=. python scripts/experiments/memory_first.py      # §5, both honesty regimes
PYTHONPATH=. python scripts/experiments/blend_weight_sweep.py     # §4, the blend weight
PYTHONPATH=. python scripts/experiments/counterfactual_standings.py --validate  # §6
PYTHONPATH=. python scripts/replay_payoffs.py --games all --sweep oracle        # §7
PYTHONPATH=. python scripts/experiments/target_multipliers.py                   # §8
```

`replay_payoffs.py --games all --self-check` reconstructs 99 of 100 Games exactly; Game 67 is
excluded throughout for the known Cap collision documented in `cap_collisions()`.
