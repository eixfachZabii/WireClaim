# WireClaim — our approach

**Team `Bin busy` · QuantCo _Claim to Fame_ (Track 1) · Munich Agentic Hackathon, 22–23 Aug 2026**

Per Line Item we submit a Charge `a` and an acceptance Limit `b` against a secret fair value `t`.
Every number below is reproducible from a script in this repository; the deeper version is
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md), and the appendix with every table is
[`docs/methodology-full.md`](docs/methodology-full.md).

## 1. The clause that decides the game

The payoff table has one row people skip: **when a reviewer wrongfully rejects a fair claim, the
issuer is still paid** (and the reviewer pays `1.5a`). So a fair Charge is owed by *every*
opponent regardless of their Limits, while an Overcharge is paid only by the few who accept.
Measured on Game 62: **16 payers versus 3.**

The Charge is therefore **a cliff, not a slope**, and crossing `t` costs roughly 5× the income.
Game 62, Line Item 1, `t ∈ [8505, 10350)`: `error404 ai` charged 8,504.71, was paid by 16 of 16,
and collected **136,075 — 87 % of their entire Game**. We charged 10,349.89, were paid by 3, and
collected 31,050. They did not out-read the policy. They charged 22 % lower and landed on the
right side of a cliff.

## 2. The unlock: `t` is secret, but it is exactly recoverable

A settled Transaction *rejected while carrying a non-zero amount* is a wrongful rejection, which
proves `a ≤ t` and reveals the Charge; a rejection at zero proves `a > t`. Together they bracket
`t` for **every Line Item ever played**. `scripts/invert_fair_values.py --verify` reproduces every
published net to the cent across 52,224 settled rows.

That turns the whole tournament into a measurement instrument.
`scripts/replay_payoffs.py` scores any hypothetical submission against the real Field with all
sixteen opponents held fixed, and its self-check asserts that our *actual* submission reproduces
the authoritative net for every settled Game — a test, not a comment, because without it none of
our numbers mean anything. **Every claim in this write-up is a measurement rather than an
argument.** (Inference from the published leaderboard is permitted; we asked the organisers.)

## 3. The architecture, in one rule: the model reads, the engine prices

No model output is ever a price ([ADR 0001](docs/brainstorm/sebi/adr/0001-the-model-reads-the-engine-prices.md)).
Models emit **structured evidence** — a coverage probability with the policy clause quoted
verbatim, a price band, a quantity — and deterministic code turns evidence into a posterior over
`t` and the posterior into `(a, b)`:

```
blend      log m = Σ wᵢ·log mᵢ / Σ wᵢ,  wᵢ = 1/σᵢ²        (two model draws + Price Memory)
posterior  P(t) = (1−p)·δ(0) + p·LogNormal(log m, σ)      coverage is mass at zero, not a branch
Charge     a = k(σ)·m,   k = clamp(0.85 − 0.45·σ, 0.30, 0.80)     maximises k·P(t ≥ k·m)
Limit      b = Q⅓(P), then min(b, ceiling·m, a)           accept iff P(fair) > ⅔, so b is the ⅓ quantile
```

The `⅓` is derived, not tuned: rejecting a fair claim costs `1.5a`, rejecting a fraudulent one
costs nothing, so indifference sits at exactly two-thirds. Four separate attacks on it were
measured and lost.

The reason for the seam is auditability under repetition — this ran unattended 100 times, once
every 12.6 minutes, inside a 60-second window. **A prompt that emits a number cannot be swept,
folded or replayed; a prompt that emits evidence can.** It also means something is underneath when
the model goes away, and it did: **Games 82–89, eight consecutive triple-weighted Games, ran with
`model_draws=0`** because the endpoint returned 401 on every call. The blind floor posted at T+0,
Price Memory priced what it recognised, the fitted constants covered the rest, and those Games
banked **+254,092 weighted**. We did not notice until afterwards, which is the point.

## 4. The bar, and what cleared it

A change shipped only if it was positive on **all four folds** — odd Games, even Games, early
half, late half — never merely positive in total. The noise floor is measured, not assumed:
**26,622 over 18 Games** with an identical prompt, scaling as `√n`, so **±6,275 for a single
Game**. No single Game ever justified a change, however vivid it looked at 4 a.m.

Two changes moved real money, both on the Charge, both found by asking why a *specific* Line Item
lost. `BIG_ITEM_CHARGE_SCALE` 1.25 → 1.0: **+79,240** over 63 Games, with nine Line Items moving
from Overcharge to fair and none moving the other way. `CHARGE_TRUST_MEMORY = 1.15` — raise the
Charge only where a wording has been *watched settle*: **+80,613, four folds.** The control is
what makes it a channel effect rather than "charge more": doing the same to the model channel is
**−95,061 and 0/4**. Replayed over the last 10 Games, the pair moves us **−80,266 → +102,817**.

**12 of our 20 numbered hypotheses were measured and rejected**, each with the script that killed
it — a global Charge multiplier, the exact expected-income argmax, four attacks on the Limit,
copying the best rival's ratios (−280k to −380k), more ensemble draws (draw noise is 1.1 % of the
error). The sharpest one happened in the last hour: we shipped a coverage recalibration on a
genuine calibration table and a clean four-fold sweep, then **reverted it twenty minutes later**,
because checking the *mechanism* showed the model's coverage output is bimodal, so the correction
touched **4 Line Items in 573**. Its +5,057 was an incidental Limit nudge wearing a calibration
costume. A constant can be right about its data and wrong about its mechanism — and folds catch a
result driven by a few *Games*, never one driven by a few *items*.

---

# Why we think we succeeded — and where we did not

## Succeeded

- **We built a measurement instrument before we built a strategy.** Recovering `t` by inversion,
  then replaying counterfactuals against the real Field with all sixteen opponents fixed, meant
  every subsequent decision was settled by a number instead of an argument. Three claims we had
  written down as fact were falsified by it within a day.
- **We climbed from last to 5th.** After nine Games we were **17th of 17**. We are now **5th** on
  +231,298 weighted. Over the last twenty settled Games we are **2nd in the field by rate**
  (+6,897/Game); over the 69 Games since our estimator existed, **3rd of 17** at +5,254/Game —
  within **4.3 %** of the field leader.
- **The distribution is tight, which is the part we would actually defend.** **2 losing Games in
  the last 20, the worst costing 3,941**; 4 losing Games in the last 30, the fewest of any team.
  That is the **2nd-best risk-adjusted return in the field** (mean/σ = 0.72 vs 0.83). Seven teams
  carry a single Game worse than −80,000; our deepest hole in thirty Games is −9,720. In an
  insurance book, the narrow distribution is the number that matters.
- **The architecture degraded instead of failing.** Eight triple-weighted Games ran with the model
  channel completely dark and still banked +254,092, because no scored number ever depended on a
  model being reachable.
- **We priced uptime correctly.** Break-even uptime is 71 %; rescuing a Game is worth `93t` and
  improving one `37t`, so **showing up is 2.5× being right**. A blind floor posts plausible numbers
  at T+0 before the Case is decrypted, submissions merge per Line Item so partial output is never
  discarded, and a supervisor restarts the runner on any crash. R10 was confirmed against a real
  opponent: `makalu` went dark, paid us **179,992.64** across the season, and collected **0.00**
  from anyone.

## Did not succeed

- **We spent the first quarter of the tournament building the instrument instead of scoring.**
  Strategy 2 first went live around Game 20, but Games 21–24 still submitted the fallback Limit
  of 35 on every Line Item, so the estimator was not really working until Game 26. Games 1–25
  cost **−322,595**, which is larger than our entire current season net. Every point of
  our deficit is there. The rate says the decision was right; the total says we paid full price
  for it.
- **The estimate is the entire remaining gap, and it costs us twice.** Both numbers we submit are
  functions of the *same* `t̂` — `a = k(σ)·t̂`, and `b` is a quantile of a posterior centred on `t̂`.
  So one error is paid in **both** directions at once:
  - `t̂` **too low** → `b` too low → we wrongfully reject a **fair** claim → we pay **1.5a**. That
    is the lawyer fee, our largest single cost line, and it fires *only* on claims that were fair;
    rejecting a genuine Overcharge is free.
  - `t̂` **too high** → `a` crosses `t` → thirteen of sixteen opponents refuse it → we earn
    **nothing** on an item we were owed money for. Crossing `t` costs roughly 5× the income.

  `a = b = t` reaches **100.3 %** of the best possible play; `a = b = t̂` scores **−50,140**. The
  **2,498,118** between them is not strategy and no decision rule reaches it. We optimised the
  rules to their measured argmax and it barely mattered — the best constant available anywhere in
  a full sweep moves the total by ~18k. We worked one layer too low.
- **We diagnosed our largest open lever and deliberately did not ship it.** Policy clause 7.1.5
  has two halves — indemnity is confined to the affected parts, *but* "where an affected room was
  wetted as a whole, the whole of that room is treated as affected". The model reads only the
  first half. Game 74 returned coverage of 0.01–0.05 on 20 of 31 Line Items for **€41,710, 87 % of
  that Game's penalties**. Perfect coverage is worth **+1,173/Game**. It is a prompt change, it
  could not be validated without spending the live runner's quota, and it would have landed six
  Games before the 3× window with no way to tell a fix from a regression. We think the call was
  right and the outcome is still a loss.
- **Eight triple-weighted Games ran with the model dark and we did not notice.** It is the best
  evidence we have that the fallback architecture works, and it is also an operational failure: we
  had no alert on `model_draws=0`, during the most valuable Games of the tournament.
- **We were beaten on the thing we understood best.** We wrote down that the Charge is a cliff and
  we still sat above `t` too often; `error404 ai` took 136,075 off a single Line Item by charging
  22 % lower than us. Knowing the mechanism and calibrating to it are different achievements, and
  we only closed the gap at Game 63.

## What we would build next, in order

1. **Calibrate the band — worth more than any constant in the engine.** The model asserts a median
   σ of **0.375** against a realised RMSLE near **0.80**: overconfident by 2.1×. Worse, the width
   carries *no signal* — split items by band width and the narrow third scores RMSLE 0.847 against
   the wide third's 0.733, i.e. slightly **backwards**. So `k(σ)` multiplies a number that does not
   measure what it claims to. The line is right; its input is not. This belongs in the evidence
   layer, not the pricing engine.
2. **Fix the coverage read.** Clause 7.1.5, second half. **+1,173/Game** if perfect, on all four
   folds. A prompt problem, not a pricing one.
3. **Separate the genuinely large items from the phantoms.** Of 23 items we believed were worth
   over 2,000, **14 were worth under half that**. An observable splitting the 9 real ones would let
   us charge confidently where it is safe — today we cannot, so we charge low everywhere, which is
   correct on average and leaves money on every genuinely expensive item.
4. **Widen Price Memory.** A wording we have watched settle has a measured log error of **0.43**
   against the model's realised **1.66–2.20**, but memory reaches only ~22 % of Line Items. Every
   point of coverage there is a direct reduction in σ — and by item 1, σ is what sets *both*
   numbers.

---

**No claim data is checked into this repository.** Not the Cases, not the invoices, not the
policies — and not the four derived paths that would reproduce them (raw model replies, per-Game
reviews, the decision log and the settled lessons all carry policy wording or invoice Line Item
text). They generate locally and are ignored. Short single-clause quotations appear where the
argument needs them, as citation rather than as an archive.
