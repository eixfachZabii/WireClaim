# 5 minutes + 3 minutes Q&A — the run sheet

> **Reading it out loud? Use [`SCRIPT.md`](SCRIPT.md), or press `N` in the deck.**
> That is the only place carrying post-Game-100 numbers. **The timing table below still
> quotes the pre-Game-100 figures** (0.69, −9,720, −354,171) — it is kept for the cutting
> order and the Q&A prep, not for numbers to say on stage.

**Deck:** `presentation/index.html` — **10 slides, cut to 5 minutes** (arrow keys / space). Backup slides for Q&A: `presentation/appendix.html` (20 slides, the full argument). **Paper:** `presentation/writeup.pdf`.
**Judged write-up:** `WRITEUP.md` at the repo root.

> ⚠️ **The kick-off deck says "only use slides submitted on ehl.gg", and the submission
> deadline is 12:00 while Game 100 settles at 11:50.** Export the deck to PDF and upload it
> *before* 12:00 — you cannot edit it afterwards. Any number you quote on stage that moves
> after Game 94 must be spoken, not printed.
> Export: open the deck in Chrome → Print → *Save as PDF*, Landscape, margins **None**,
> **Background graphics ON**.

---

## The spine

One idea, and everything hangs off it: **the hidden fair value `t` is exactly recoverable after
settlement.** That turns a hidden-information game into a measurement problem. The cliff is what
the recovered `t` *revealed*; the twelve dead hypotheses are what the replay harness *killed*;
"the model reads, the engine prices" is the architecture that *made replay possible*.

## Timing — 5:00, ten slides

| min | slide | what you actually say |
| --- | --- | --- |
| 0:00 | **title** | "We stopped guessing what a claim is worth and started measuring what it turned out to be worth." |
| 0:10 | **01 · the cliff** | The row everyone skips: **a wrongfully rejected fair claim still pays the issuer.** So a fair Charge is owed by all 16; an Overcharge by the 3 who accept. Game 62: they charged 22 % lower and took 136,075 off one item — 87 % of their Game. |
| 0:50 | **02 · the unlock** | A rejection carrying money proves `a ≤ t`; a rejection at zero proves `a > t`. That brackets `t` for every Line Item ever played. 52,224 rows, every published net reproduced to the cent. **So every number in this pitch is a measurement, not an argument.** |
| 1:30 | **03 · architecture** | No model output is ever a price. Models emit evidence — coverage probability, the clause quoted verbatim, a price band — deterministic code prices it. A prompt that emits a number can't be replayed; one that emits evidence can. |
| 2:10 | **04 · the arithmetic + the clock** | Four steps, one slide. Point at the ⅓: *derived, not tuned* — rejecting a fair claim costs 1.5a, a fraudulent one costs nothing. Then the 60-second clock, and `makalu`: paid us 179,993, collected 0.00. |
| 2:50 | **05 · last place to 5th** | Let the chart breathe. Every rival is a grey line. **17th of 17 after nine Games.** The deficit is Games 1–25, before the estimator was working. |
| 3:20 | **05b · indexed to Game 20** | The payoff. "Season total asks how much money we ended up with — for us that's mostly a question about Games 1 to 19. Our net at Game 20 was **−354,171**; the whole gap to the leaders is that hole. Zero everyone at Game 20 and ask how we've played *since we started playing*: **2nd of 17.**" |
| 3:35 | **06 · consistency** | "The number we'd actually defend isn't the rate, it's the variance." Over the **last thirty** Games: **best risk-adjusted return in the field** (mean/σ 0.69), second-lowest σ of any team, 4 losing Games, deepest hole **−9,720** against seven teams carrying a Game worse than −80,000. **In an insurance book the narrow distribution is the number that matters.** |
| 4:05 | **07 · the bar** | A *measured* noise floor of 26,622 — ±6,275 for one Game, so no single Game ever justified a change. Four folds. And the control: the same change on the model channel is −95,061 and 0/4, which is what makes it a channel effect rather than "charge more". |
| 4:40 | **08 · what we killed** | 12 of 20 hypotheses rejected — one **twenty minutes after it shipped**, because the mechanism check showed it touched 4 items in 573. |
| 5:00 | **09 · what we'd fix** | "One estimate feeds both numbers, so one error is paid twice. Too low and the Limit wrongfully rejects a *fair* claim and we pay the 1.5× lawyer fee. Too high and the Charge crosses `t` and we earn nothing. **That's the whole remaining gap** — and the first fix is calibrating the band, not another constant." |
| 5:05 | **close** | "The model reads. The engine prices. The record decides." |

**If you are running long:** drop **04**'s right-hand column (talk over it), then **07**, then **05** (05b carries the standing on its own). **09** can be answered in Q&A instead of presented — but if you have the 20 seconds, present it: "what would you do next" is the question a jury of claims people always asks, and having the answer costed and ordered is worth more than another result. Never cut **02** (the inversion) or **05b** — those are the entry and the payoff.

**Say "top 3 either way", not "2nd".** Rebased at Game 20 we are 2nd of 17 (+403,758); at the conservative Game 26 anchor we are 3rd, where error404 ai leads us by 1,121. If a judge picks the anchor, you want to have picked it first. Useful detail: our per-Game rate is marginally *higher* from Game 26 than from 20, so Game 20 is not the flattering anchor it looks like.

### ⚠️ Numbers that changed at Game 97 — do NOT use the old ones

Three more Games settled and the 20-Game window slid from G75–94 to G78–97, dropping our two best Games. **These claims are dead:**

| dead claim | the truth at G97 |
| --- | --- |
| "2nd in the field by rate over the last 20" | **4th** (+6,067/Game). Codacabana 11,362, TakeTheMoneyAndRun 7,686, eyay 7,197, us. |
| "mean/σ 0.72, 2nd in field" *(20-Game window)* | **0.63, 4th.** eyay now leads at 0.99. |
| "2 losing Games in 20" | **3** — G86, G92, G96. |
| "4 in 30, **fewest** of any team" | count holds, superlative doesn't — **Codacabana has 3.** Say "second fewest". |
| "3rd place rebased is error404 ai" | **eyay**, by €511. |

**What is still true and is now the stronger claim:** over the **last thirty** Games (G68–97) our mean/σ is **0.689 — the best in the field** — on the **second-lowest σ of any team**. Worst Game of the last twenty is still **−3,941** (Game 92). Season **+260,250**, 5th. G26–97 **2nd of 17 by rate**.

**Three margins are knife-edge — do not lean on any of them:** we lead 3rd on the G26–97 rate by **€15/Game**; error404 ai leads us on the G26 rebase by **1,121**; and our "2nd-lowest σ" is 11,041 against error404 ai's **10,931** — a 1 % gap. All three can flip on Games 98–100. The claims that are *not* fragile: **mean/σ 0.689, best in the field** (next is 0.661), **4 losing Games in 30**, and **worst Game −9,720** against a field where the next-shallowest worst is −6,645 and eleven teams are past −27,000.

**Backup slides in `appendix.html`** for Q&A: the two traps (conditioning on the outcome, censoring), the R10/makalu slide in full, the 8 dark Games, the ceiling (`a=b=t` at 100.3 %), and what we would build next.

## Q&A — the three questions you will get

**"Isn't reading the leaderboard cheating?"**
No, and we asked. The published Transactions are settled results; inference from them is not
obtaining secret thresholds. The organisers confirmed it. We never touched another team's key or
an unsettled submission.

**"You're 5th. Why should we care?"**
Because the total measures when we started and the rate measures what we built. Games 1–25 cost
−322,595 with no estimator; over the last twenty we are 2nd in the field by rate. We are not
claiming that wins — we are telling you which number is which.

**"How much of this is the LLM?"**
Less than you would guess, deliberately. The model reads and quotes; it never emits a price.
Eight of our triple-weighted Games ran with it completely offline and still banked +254,092. The
measured log error of a wording we have watched settle is 0.43; the model's realised error over
the same Games is 1.66–2.20. We weight accordingly — and that weighting is itself a measurement,
with the control that proves it (+80,613 on memory, −95,061 doing the same to the model).

**"What would you improve with more time?"** — this is slide 09, and the answer is one idea, not
a list. Both numbers are functions of the same `t̂`: `a = k(σ)·t̂`, and `b` is a quantile of a
posterior centred on `t̂`. So a single estimation error is paid **twice, in opposite directions** —
too low and the Limit wrongfully rejects a *fair* claim so we pay `1.5a` (the lawyer fee, our
biggest cost line, and it only ever fires on claims that were fair); too high and the Charge
crosses `t` so thirteen of sixteen refuse it and we earn nothing. `a = b = t` is 100.3 % of optimal
and `a = b = t̂` is −50,140; the 2,498,118 between them is all estimator. First fix is **calibrating
the band** — the model asserts σ 0.375 against a realised 0.80, and the width does not even *order*
the error, so the Charge factor multiplies a number that measures nothing. Then coverage
(+1,173/Game), then an observable that separates the 9 genuinely large items from the 14 phantoms,
then widening Price Memory past the 22 % of items it reaches.

**If asked what is broken:** clause 7.1.5. The model reads the first half and misses the
whole-room drying provision. Game 74 lost €41,710 to it. Perfect coverage is worth +1,173/Game.
We diagnosed it, could not validate a prompt change before the 3× window, and did not ship it.
