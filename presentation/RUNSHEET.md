# 5 minutes + 3 minutes Q&A — the run sheet

**Deck:** `presentation/index.html` (arrow keys / space). **Paper:** `presentation/writeup.pdf`.
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

## Timing — 5:00

| min | slides | what you actually say |
| --- | --- | --- |
| 0:00–0:40 | title, 01, 02 | The game in two sentences. Then the row everyone skips: **a wrongfully rejected fair claim still pays the issuer.** So a fair Charge is owed by all 16; an Overcharge by the 3 who accept. Game 62: they charged 22 % lower and took 136,075 off one item — 87 % of their Game. **The Charge is a cliff.** |
| 0:40–1:30 | 03, 04 | **The unlock.** A rejection carrying money proves `a ≤ t`; a rejection at zero proves `a > t`. That brackets `t` for every Line Item ever played — 52,224 rows, every published net reproduced to the cent. So we can replay any hypothetical submission against the real Field with all sixteen opponents held fixed. *Every number in this pitch is a measurement, not an argument.* |
| 1:30–2:20 | 05, 06 | **The architecture.** No model output is ever a price — models emit evidence (coverage probability + the clause quoted verbatim + a price band), deterministic code prices it. A prompt that emits a number can't be swept or replayed; one that emits evidence can. And it degrades: Games 82–89, eight triple-weighted Games, the model 401'd on every call — **+254,092 anyway.** Then the four lines of arithmetic. Point at the ⅓: *derived, not tuned.* |
| 2:20–2:50 | 07 | **60 seconds, 100 times, unattended, half of it overnight.** Blind floor at T+0 before we even have the key. Break-even uptime is 71 % — showing up is 2.5× being right. |
| 2:50–4:00 | 08, 09, 10, 11 | **The bar.** Four folds, and a *measured* noise floor of 26,622 — ±6,275 for one Game, so no single Game ever justified a change. Two constants moved money; the control (same change on the model channel, −95,061, 0/4) is what makes it a channel effect. Then: **12 of 20 hypotheses killed**, one of them **reverted 20 minutes after it shipped** because the mechanism check showed it touched 4 items in 573. |
| 4:00–4:40 | 13, 13b | **Standing.** 17th of 17 after nine Games. 5th now. The whole deficit is Games 1–25, before the estimator existed. Last twenty Games: 2nd by rate. **And the variance is the part we'd defend — 2 losing Games in 20, worst −3,941, 2nd-best risk-adjusted return in the field.** |
| 4:40–5:00 | 15, close | What we'd do next, and the one we diagnosed and deliberately did not ship. Land on: *the model reads, the engine prices, the record decides.* |

## If you are running long — cut these, in this order

1. **12** (the two traps) — the best content in the deck and the first to go; it is in the paper.
2. **13c** (makalu / R10) — a great story, but 08–11 already carry the discipline argument.
3. **11** (the reverted constant) — keep it if you can, it is the single most persuasive slide.
4. **02** — you can tell the Game 62 story over slide 01 without the table.

Never cut **03** (the inversion) or **05** (the dark Games). Those are the entry.

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

**If asked what is broken:** clause 7.1.5. The model reads the first half and misses the
whole-room drying provision. Game 74 lost €41,710 to it. Perfect coverage is worth +1,173/Game.
We diagnosed it, could not validate a prompt change before the 3× window, and did not ship it.
