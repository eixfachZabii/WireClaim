# WireClaim — how we decided things (long version)

> The one-page write-up the organisers asked for is [`METHODOLOGY.md`](METHODOLOGY.md).
> This is the appendix: same argument, every table.

Our entry to QuantCo's *Claim to Fame*. This is the methodology document: not what the pipeline
does — [`ARCHITECTURE.md`](ARCHITECTURE.md) covers that — but **how we chose between options,
and how we knew when we were wrong.**

Every number below is reproducible from a script in this repository against the published
Transactions. Where we were wrong, the wrong claim is still in the ledger with the measurement
that killed it. That is deliberate: the count of hypotheses we *rejected* is the best evidence
we have that the ones we kept are real.

---

## 1. The clause that decides the game, and it is easy to miss

Per Line Item each team submits a Charge `a` (what it invoices every other team) and a Limit `b`
(the most it will pay when invoiced the same item). Behind each is a secret Fair Value `t` and a
payment Cap `c = max(4t, 2000)`. Per ordered pair of teams:

```
a <= t, accepted (b >= a)   reviewer pays a          issuer gets a
a <= t, rejected (b <  a)   reviewer pays 1.5a       issuer gets a    <-- issuer is STILL PAID
a >  t, accepted (b >= a)   reviewer pays min(a, c)  issuer gets min(a, c)
a >  t, rejected            nothing
```

Read row two again. **A fair Charge is owed by every opponent whatever their Limits.** An
Overcharge is paid only by the few who accept. Measured on Game 62: **16 payers versus 3.**

So the Charge is a cliff, not a slope. Crossing `t` costs roughly **5× the income**, and any rule
that raises `a` on the items we estimate worst is actively dangerous. This one clause explains
most of what follows, and we underweighted it for 62 Games.

The worked example, from the settled record. Game 62 Line Item 1, `t ∈ [8505, 10350)`:

| team | Charge | payers | income on that one item |
| --- | ---: | ---: | ---: |
| `error404 ai` | 8,504.71 | **16 of 16** | **136,075** — 87 % of their whole Game |
| us | 10,349.89 | 3 of 16 | 31,050 |

They did not out-read the policy. They charged 22 % lower on one item and landed on the right
side of a cliff.

---

## 2. The architecture, in one rule

**The model reads; the engine prices** ([ADR 0001](brainstorm/sebi/adr/0001-the-model-reads-the-engine-prices.md)).

No model output is ever a price. Models emit *structured evidence* — a coverage probability with
the policy clause quoted verbatim, a price band, a quantity and unit — and deterministic code in
`src/pricing/engine.py` turns evidence into a posterior and the posterior into `(a, b)`.

The reason is auditability under repetition: this ran unattended 100 times, once every 12.6
minutes, with a 60-second window. A prompt that emits a number cannot be swept, folded or
replayed. A prompt that emits evidence can, because the pricing is a pure function we can re-run
over the whole record in a minute.

It also means every constant in the engine is a hypothesis with a falsifier written next to it.
Eight constants carry an explicit falsification condition, and two of them now record
their own reversal.

---

## 3. The measurement apparatus — why our counterfactuals are measurements, not arguments

This is the part we would defend hardest.

**The Fair Value is exactly recoverable.** A settled Transaction that was *rejected while
carrying a non-zero amount* is a wrongful rejection, which proves `a <= t` and reveals the
Charge. A rejection at zero proves `a > t`. Together they bracket `t` for every Line Item ever
played. `scripts/invert_fair_values.py --verify` reproduces every published net to the cent.

**So we can replay any hypothetical submission against the real Field.**
`scripts/replay_payoffs.py` holds all sixteen opponents' Charges and Limits fixed and answers
"what would our net have been if we had submitted this instead". Its self-check asserts that our
*real* submission reproduces the authoritative net for every settled Game. Without that property
none of the numbers mean anything, so it is a test, not a comment.

**The bar for shipping.** A change must be positive on **all four folds** — odd Games, even
Games, the early half, the late half — not merely positive in total. The noise floor is a
measured quantity: **26,622 over 18 Games** with an identical prompt, scaled as `√n`. That is
±6,275 for a single Game, which is why no single Game ever justifies a change, however vivid.

**Attribution before amount.** The runner writes a decision log at submission time
(`var/decisions/game_NNN.json`) recording what it believed *before* seeing any outcome — band,
coverage, which channels spoke, which rule fired. Joined against the recovered Fair Value
afterwards, it names *the stage that was wrong* rather than the money that was lost.
"We lost 8,975" is not actionable; `estimate-too-low on item 3` is.

---

## 4. What actually moved money

Two changes, both to the Charge, both found by asking why a *specific* Line Item lost.

**`BIG_ITEM_CHARGE_SCALE`: 1.25 → 1.0.** The constant raised the Charge 25 % on estimates over
1,000, justified by "on an item already above `t` the income is ~0 whatever we Charge, so raising
it costs nothing". §1 says otherwise. Re-swept over 63 Games: **+79,240**, and the mechanism is
visible and one-directional — **nine Line Items move from Overcharge to fair and none move the
other way.**

Note what did *not* trip it. The constant's own documented falsifier was the tail's direction
balance shifting toward 50 % too-high; re-measured, it was still 67 % too high / 15 % too low at
n=33, exactly the shape it was fitted on. **A constant can be right about its data and wrong
about its mechanism**, and only the mechanism check caught it.

**`CHARGE_TRUST_MEMORY = 1.15`.** The Charge was the only number in the engine that ignored
*which channel produced the estimate*. The Limit had trusted Price Memory over the model since
Game 37 (`LIMIT_CEILING_MEMORY` 0.75 against 0.45, worth +40,791) because a memory-backed wording
has been *watched settle*. Measured log errors: **0.43 for memory against 0.6 for the model
prior**, and the model's realised error is worse than its own prior (RMSLE 1.66 / 1.82 / 2.20
over Games 26–40 / 41–55 / 56–64). Raising the Charge 15 % on memory-backed items only:
**+80,613, positive on all four folds.**

The control is what makes it a channel effect rather than "charge more": raising the *model*
channel instead is **−95,061 and 0/4**, and a global ×1.10 is −27,185 and negative on the last
10, 15 and 20 Games separately.

**Together, replayed over the last 10 Games: −80,266 → +102,817.**

---

## 5. The negatives, which are the actual methodology

The ledger holds 19 numbered hypotheses: 4 shipped, **11 measured and rejected**, the rest
open or dormant. A representative selection of the rejections, each with the script that killed
it:

| hypothesis | verdict |
| --- | --- |
| Charge 9 % lower / Limit 18 % higher | −14,577 and noise; negative on all four windows |
| A global Charge multiplier below 1.0 | monotone loss, −118,049 at ×0.9, on the recent window too |
| The exact argmax of expected income | loses in **all 15 cells** of a two-parameter sweep |
| `LIMIT_QUANTILE` away from the derived ⅓ | ⅓ is the argmax; the best alternative is 7 % of the floor |
| Raise the Limit on large items | 10 cells, all lose — the conditioning trap (below) |
| Read the policy's exact EUR caps | the number is exact; the *row* is not identifiable, −5,905 |
| More ensemble draws / "swarm" | draw noise is **1.1 %** of the error; a third draw buys 0.2 % |
| Copy the best rival's `a/t`, `b/t` ratios | **−280,000 to −380,000** applied to our own `t̂` |
| Enforce the payment Cap in the replay | identical to the cent, every rule, every fold |
| `a = b = t̂` (a whole rival track) | −50,140, while `a = b = t` is 100.3 % of optimal |
| A coverage recalibration `p ** 0.7` | shipped, then reverted 20 minutes later — see below |

That last row is the single most instructive result we have. `a = b = t` is **not
approximately** optimal — over 70 Games it reaches **100.3 % of the best possible play and is
within 3 % on 70 of 70 Games.** Substituting our estimate for the truth moves it by
**2,498,118**. None of that is strategy. It is all estimation error, and it is why we stopped
looking for cleverness in the decision rules.

### The one we shipped and took back out

Worth its own section, because it is the clearest demonstration of why the rest of this document
is trustworthy.

Late in the tournament, `coverage-too-low` was the largest attributed penalty stage — 47 % of all
penalty over Games 51–65. Bucketing the model's **stated** coverage probability against proven
outcomes showed real, one-directional miscalibration: items stated 0.20–0.40 were 62 % covered,
items stated 0.60–0.80 were 93 % covered. Correcting it with `p ** 0.7` swept **positive on all
four folds with no negative cell in any window**. It shipped.

Twenty minutes later it was reverted, because a check on the *mechanism* rather than the number
showed the model's output is **bimodal** — it says 0.01 or it says 0.9:

| band | items | share |
| --- | ---: | ---: |
| 0.00–0.05 | 157 | 27.4 % |
| 0.56–0.67 | **4** | **0.7 %** |
| 0.80–1.01 | 333 | 58.1 % |

An item must already sit in (0.560, 0.667] for the correction to lift it across the collapse
threshold, and **4 of 573 do**. The band the calibration table measured is a band the model almost
never outputs. So the +5,057 was not the documented mechanism at all: it came from the same
exponent nudging the Limit up on the 333 confident items — a small across-the-board Limit raise
wearing a calibration costume, in a direction the same table says is wrong, and worth 9 % of the
noise floor.

Two things to take from it. First, **a constant can be right about its data and wrong about its
mechanism** — the identical failure as `BIG_ITEM_CHARGE_SCALE = 1.25`, which we had post-mortemed
that same morning. Second, **the four-fold test is not assumption-free**: folds guard against a
result driven by a handful of *Games*, and this one was driven by a handful of *items*, which
folds cannot see. The bar we had been applying all tournament had a hole in it, and only asking
"how many rows does this actually touch?" found it.

### Two traps, each of which cost us a full working session

**Conditioning on the outcome.** Bucketed by what items *turned out* to be worth, strictness pays
9.9 : 1 on items under 100 and loses 0.3 : 1 above 500 — a compelling case for raising the Limit
on expensive items. Bucketed by `t̂`, the only split available at submission time, the gradient
collapses, and the reason is in one column: **of 23 items we believed were worth over 2,000, 14
turned out to be worth under half that.** Items land in the cheap bucket partly *because* the
Field's Charges on them were low, which is exactly when rejecting is free. Every rule built on
the first table loses.

**Censoring.** A Fair Value bracket with no upper bound means the item is worth *at least* `t_lo`
— and it is unbounded precisely *because* nobody rightfully rejected, which correlates with the
item being expensive. Any statistic conditioned on "censored" is selection on the answer.

---

## 6. Where we stand, honestly

Rank is a lagging indicator: Games 1–25 ran before the current estimator existed and cost
322,595, which is the whole of our deficit. Judge the rate.

Since the Charge fixes went live, the eight settled Games run

```
G66 +19,025   G67 +13,415   G68 −9,720   G69 +7,025
G70  +3,362   G71 +36,877   G72  +7,522  G73  +6,528     = +84,033, or +10,504 per Game
```

against the best per-Game rate anyone in the field managed over the preceding twenty Games
(`error404 ai`, +6,435). Eight Games is still inside the ±17,748 noise floor at that sample size,
and we say so rather than claiming the win.

The gap that remains is entirely `t̂`. The oracle ceiling over the 47 Games with a decision log is
**+1,716,459** against our **+182,025** — about 11 %. Every decision rule has now been swept from
several directions and sits at its measured optimum; none of the remaining headroom is reachable
by a constant.

**What we would do next, in order.** Fix the coverage step's reading of policy clause 7.1.5,
which has two halves: indemnity is confined to the affected parts, *but* "where an affected room
was wetted as a whole, the whole of that room is treated as affected for the purposes of
extraction, drying and the reinstatement of its finishes." The model reads the first half against
a description saying "an area of maybe a square meter or so" and prices a corner of a room the
Field pays out in full. Game 74 returned coverage of 0.01–0.05 on 20 of 31 Line Items for
**€41,710, 87 % of that Game's penalties**, and Game 75 repeated it on a different Case.
Perfect coverage is worth **+1,173 per Game** over 74 Games, positive on all four folds — and no
pricing-side rule reaches it, because memory certifies a price and not a coverage verdict (H18).
We did not attempt it: it is a prompt change, it cannot be validated without spending the
runner's model quota on settled Cases, and it would have landed six Games before the 3× window
with no way to tell a fix from a regression until the weighted Games were underway. Then carry an
invoice id per Line Item, which turns "one travel charge per trade invoice" from a leaky ordinal
heuristic into a deterministic rule (H17). Find an
observable that separates the 9 genuinely-large items from the 14 phantoms in the `t̂ ≥ 2,000`
bucket — a targeted second reading is instrumented and logging as of Game 72, deliberately unable
to change a price until the evidence earns it. And calibrate the band: the model asserts a median
σ of 0.375 against a realised error near 1.0, and the asserted width does not even *order* the
realised error.

---

## 7. Things we did because the tournament was live, not because they were elegant

- **Uptime outranks accuracy.** Break-even uptime is **71 %**: an all-or-nothing smart bot needs
  that much merely to tie a dumb bot that never misses. Rescuing one Game is worth `93t`;
  improving one is worth `37t`. A supervisor restarts the runner on any crash, because
  `watch_games()` has no exception boundary and one uncaught error would end the tournament
  rather than cost one Game.
- **The default submission is an incident, never a fallback.** `a = 0, b = 0` does not score
  zero — `b = 0` wrongfully rejects every fair claim, so a dark team pays `1.5a` to every awake
  opponent on every Line Item. A blind floor posts plausible numbers at T+0 s before the Case is
  even decrypted, and the real submission overwrites it per Line Item.
- **Restart only 60 s after a Game opens, not when it reports finished.** A Game completes in
  10–30 s but its window stays open the full 60, and a restart inside it re-posts the baseline
  over a finished submission. We learned that at Game 66 with 20 seconds to spare.
- **The final 20 Games are weighted 3×**, announced mid-tournament — and the Transactions tab
  stays unweighted while the standings triple. Every cross-check in this repo compares those two,
  so all 20 Games would have been declared unreconstructable and silently dropped from the
  learning loop. It is guarded and tested. No constant changed: a uniform multiplier leaves the
  per-Game argmax identical.

---

## 8. Reproducing any claim here

```bash
set -a && . .env && set +a
pixi run test                                              # 416 tests, including the replay self-check
PYTHONPATH=. pixi run python scripts/invert_fair_values.py --verify        # every net, to the cent
PYTHONPATH=. pixi run python scripts/experiments/big_charge_floor_sweep.py # §4, first change
PYTHONPATH=. pixi run python scripts/experiments/memory_charge_trust.py    # §4, second change
PYTHONPATH=. pixi run python scripts/experiments/strategy5_offline.py      # §5, a = b = t_hat
PYTHONPATH=. pixi run python scripts/experiments/ensemble_width.py         # §5, the swarm question
```

The full hypothesis ledger, including the ones that were shipped and later reversed, is
[`hypothesis-ledger.md`](brainstorm/sebi/strats/review/hypothesis-ledger.md).
