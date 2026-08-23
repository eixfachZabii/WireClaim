# WireClaim — our approach

QuantCo *Claim to Fame*, team **Bin busy**. One page; the long version with every table is
[`methodology-full.md`](methodology-full.md), and every number below is reproducible from a
script in this repo.

## The clause that decides the game

Per Line Item we submit a Charge `a` and a Limit `b`, against a secret Fair Value `t`. The payoff
table has one row people miss: **when a reviewer wrongfully rejects a fair claim, the issuer is
still paid** (and the reviewer pays `1.5a`). So a fair Charge is owed by *every* opponent, while
an Overcharge is paid only by the few who accept. Measured on Game 62: **16 payers versus 3.**

The Charge is therefore a cliff, not a slope. Game 62, Line Item 1, `t ∈ [8505, 10350)`:

| | Charge | payers | income, one item |
| --- | ---: | ---: | ---: |
| `error404 ai` | 8,504.71 | **16/16** | **136,075** — 87 % of their Game |
| us | 10,349.89 | 3/16 | 31,050 |

They did not out-read the policy. They charged 22 % lower and landed on the right side of a cliff.

## The architecture, in one rule

**The model reads; the engine prices.** No model output is ever a price. Models emit *structured
evidence* — a coverage probability with the policy clause quoted verbatim, a price band, a
quantity — and deterministic code turns evidence into a posterior and the posterior into `(a, b)`.
This ran unattended 100 times, once every 12.6 minutes, in a 60-second window. A prompt that
emits a number cannot be swept, folded or replayed; a prompt that emits evidence can, because the
pricing is then a pure function we can re-run over the whole record in a minute.

It also means there is something underneath when the model goes away — and it did. **Games 82–89,
eight consecutive triple-weighted Games, ran with `model_draws=0`**: the model endpoint returned
401 on every call for both draws and the fast path. The blind floor still posted at T+0, Price
Memory priced what it recognised, the fitted constants covered the rest, and those eight Games
banked **+254,092 weighted**. We did not notice until afterwards, which is the point.

## Why our counterfactuals are measurements, not arguments

**The Fair Value is exactly recoverable.** A settled Transaction *rejected while carrying a
non-zero amount* is a wrongful rejection, which proves `a ≤ t` and reveals the Charge; a rejection
at zero proves `a > t`. Together they bracket `t` for every Line Item ever played.

So `scripts/replay_payoffs.py` can score any hypothetical submission against the real Field, with
all sixteen opponents held fixed. Its self-check asserts that our *actual* submission reproduces
the authoritative net for every settled Game — that property is a test, not a comment, because
without it none of the numbers mean anything.

**The bar:** positive on **all four folds** (odd, even, early, late), not merely positive in
total. The noise floor is measured, not assumed: **26,622 over 18 Games** with an identical
prompt, scaling as `√n`. That is ±6,275 for one Game, which is why no single Game ever justified
a change, however vivid.

## What moved money

Both fixes were to the Charge, both found by asking why a *specific* Line Item lost.

- **`BIG_ITEM_CHARGE_SCALE` 1.25 → 1.0**: **+79,240** over 63 Games. Nine Line Items move from
  Overcharge to fair and none move the other way.
- **`CHARGE_TRUST_MEMORY = 1.15`** — raise the Charge only where a wording has been *watched
  settle* (measured log error 0.43, against 0.6 for the model): **+80,613, four folds.** The
  control makes it a channel effect rather than "charge more": doing the same to the model
  channel is **−95,061 and 0/4**.

Replayed over the last 10 Games: **−80,266 → +102,817.**

## The negatives, which are the actual methodology

**11 of 19 numbered hypotheses were measured and rejected**, each with the script that killed it:
a global Charge multiplier (monotone loss), the exact expected-income argmax (loses in all 15
cells), four separate attacks on the Limit (⅓ is the argmax), copying the best rival's ratios
(−280k to −380k), more ensemble draws (draw noise is 1.1 % of the error).

The sharpest example happened in the last hour. We shipped a coverage recalibration on a genuine
calibration table and a clean four-fold sweep — then **reverted it twenty minutes later**, because
checking the *mechanism* showed the model's coverage output is bimodal, so the correction changed
**4 Line Items in 573**. Its +5,057 was not the documented effect at all but an incidental Limit
nudge, and the four-fold test had given false confidence: folds catch a result driven by a few
*Games*, not one driven by a few *items*. A constant can be right about its data and wrong about
its mechanism, and only the mechanism check catches it.

That was not the only one. The eight dark Games above *look* like proof the model channel is dead
weight — capture against the oracle ceiling was 28.4 % dark against 17.5 % live. A permutation test
over 200,000 shuffles returns **p = 0.208**: capture has a standard deviation of 75 %, and one
split in five is that lopsided by chance. Price Memory is measurably the better channel (log error
0.43 against the model's realised 1.66–2.20), but "measurably better channel" and "switch the other
one off" are different claims and only the first is evidenced.

The two traps that each cost a working session: **conditioning on the outcome** (bucketing by what
items turned out to be worth suggests raising the Limit on expensive items; bucketing by `t̂`, the
only thing knowable at submission time, collapses the gradient — of 23 items we believed were
worth over 2,000, **14 were worth under half that**), and **censoring** (an unbounded bracket is
unbounded *because* nobody rightfully rejected, which is selection on the answer).

## Where we stand, honestly

Rank lags the strategy. Games 1–25 ran before the current estimator existed and cost **322,595** —
the whole of our deficit. Over the last twenty settled Games we are **2nd in the field by rate**
(+17,302 per Game) while sitting 5th on season total, and the four teams above us on total are
1st, 3rd, 4th and 5th by rate. We are not claiming that wins; we are saying the total measures
when we started working and the rate measures what we built.

The remaining gap is entirely `t̂`: **`a = b = t` reaches 100.3 % of the best possible play and is
within 3 % on 70 of 70 Games**, while `a = b = t̂` scores −50,140. The 2,498,118 between them is
not strategy, it is estimation error — which is why we stopped looking for cleverness in the
decision rules. The largest measured lever still open is coverage, worth **+1,173/Game** if
perfect; it is a prompt problem, not a pricing one, and no pricing rule we tried reached it.
