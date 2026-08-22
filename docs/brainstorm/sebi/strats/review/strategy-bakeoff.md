# Strategy bake-off — which track would actually have made the money?

**Script:** `scripts/strat_bakeoff.py` · **Cache:** `var/bakeoff/` · **Harness:**
`scripts/replay_payoffs.py`

```bash
set -a && . .env && set +a && pixi run cases
PYTHONPATH=. pixi run python scripts/strat_bakeoff.py --games 20- --draws 2
PYTHONPATH=. pixi run python scripts/strat_bakeoff.py --games 20-30 --draws 2 --offline   # re-score cache
```

---

## The answer, in one paragraph

Over **Games 20–30** (11 settled Games, two independent model draws of every track, all
sixteen opponents held fixed, judged in euros): **Strategy 2 is the only track that makes
money, and it belongs at the top of the router.** It replays at **+33,025** pooled against
**−30,851** for Strategy 1, **−49,535** for Strategy 3 and **−67,170** for the `fast_path`
layer. The Strategy 2 − Strategy 1 gap of **63,876** is three times the scaled noise floor of
**20,811**, holds in both draws separately, and holds under every opponent-Limit rule. The
Game‑27 snapshot that started this — `strategy1` +21,032 against `strategy2` +7,887 — was
**one Game and one draw**, and the wider measurement reverses it decisively.

The router is nevertheless **wrong in one place**: it ranks `strategy3` **above** `strategy1`,
and Strategy 3 is the worse of the two by **18,684** pooled, in both draws, at three times the
runtime. That gap is *inside* the floor, so the recommendation is a demotion on the balance of
evidence rather than a proven one — and it is free, because Strategy 3 has never won the router
while Strategy 2 answers.

Everything else is still under the ceiling: `actual` (the published net) is **+73,420** and the
per-item oracle is **+251,606**. The tracks are arguing about a 64,000 gap inside a 218,000
shortfall.

---

## What was measured, and what was not

**Measured.** For each Game 20–30: `read_case`, then `propose(case)` twice per track
(`strategy1`, `strategy2`, `strategy3`, `fast_path.llm_values`), each draw cached to
`var/bakeoff/game_NNN_<source>_draw<k>.json` with its wall clock. Each draw scored by
`replay_payoffs.replay()` against `snapshot(game_id)`. `actual` is `our_actual_submission(snap)`
and reproduces the published net **to the cent in all 11 Games**. `merged` is the router's
per-index priority merge (`standard` → `fast_path` → priority order), rebuilt per draw.

**Inferred, and flagged.** Why the model returned what it returned. The reading of the `actual`
column as evidence about today's code (it is not a re-run — see below). The demotion of
Strategy 3, whose direction is consistent but whose magnitude is inside the floor.

**Not done, deliberately.** No log error anywhere; every number here is euros. A log error would
weight Game 26's €10 Line Items exactly like Game 27's €3,000 one, and the entire difference
between these tracks lives in about a dozen expensive items.

**No leakage.** Strategy 2's Price Memory is built from Games 1–14 only
(`var/price_memory.json`, `built_from_games`), so nothing in Games 20–30 is priced with its own
answer.

**No side effects.** `strategy2.propose` writes a decision log, and re-running a settled Game
would overwrite `var/decisions/game_NNN.json` — destroying the only record of Game 27's three
Proposals. `_redirect_decision_log()` repoints `DECISIONS_DIR` at `var/bakeoff/decisions` for
the run. Nothing under `src/` was modified by this work.

**One code vintage.** `src/pricing.py` gained an absolute Limit cap and a looser
`LIMIT_CEILING` mid-session (commit `815725b`). Every Strategy 2 draw was **re-drawn after
that change**, so all 11 Games are one vintage; the pre-cap draws are kept in
`var/bakeoff/pre_limitcap/`. Strategies 1 and 3 and `fast_path` do not import `src/pricing.py`
and were unaffected. The difference is quantified at the end of the Limit section.

---

## Per-Game replayed net, draw 0 (EUR)

| Game | strategy1 | strategy2 | strategy3 | fast_path | merged | actual | oracle_exact |
| ---- | --------- | --------- | --------- | --------- | ------ | ------ | ------------ |
| 20 | 9,790 | 3,962 | 4,992 | 9,011 | 3,962 | 12,765 | 29,558 |
| 21 | 2,520 | 2,172 | 3,080 | 3,213 | 2,172 | 3,080 | 1,418 |
| 22 | 0 | 634 | *silent* | 0 | 634 | 14,840 | 1,966 |
| 23 | 3,172 | 2,205 | −1,066 | 1,652 | 2,205 | −821 | 7,336 |
| 24 | 16,073 | **38,162** | 25,108 | −52 | 38,162 | 13,013 | 86,704 |
| 25 | −37,172 | −15,992 | −35,840 | *silent* | −15,992 | 1,464 | 42,272 |
| 26 | −21,481 | −1,818 | −4,683 | −22,132 | −1,818 | −3,930 | 15,690 |
| 27 | 10,526 | 9,619 | −11,298 | −11,298 | 9,619 | 11,351 | 40,918 |
| 28 | 1,192 | 2,359 | 0 | 868 | 2,359 | 5,298 | 6,459 |
| 29 | −640 | 131 | −5,345 | 85 | 131 | 19,823 | 6,114 |
| 30 | −10,145 | −3,200 | −2,048 | −15,318 | −3,200 | −3,463 | 13,171 |
| **total** | **−26,165** | **+38,233** | **−27,100** | **−83,866** | **+38,233** | **+73,420** | **+251,606** |

`merged` is **identical to `strategy2` in all 11 Games and all 22 draws.** Say that plainly:
**the router is currently a one-track router.** Strategy 2 always answers, always prices every
Line Item, and always outranks the others, so Strategies 1 and 3 have contributed exactly zero
euros to any submission since Game 21. The ensemble is a log, not an ensemble — which is
precisely why this measurement had to be made off-line.

---

## Pooled totals, one column per draw (opponent Limit rule `mid`)

| variant | draw 0 | draw 1 | mean of draws | per Game | own pooled draw spread |
| ------- | ------ | ------ | ------------- | -------- | ---------------------- |
| strategy1 | −26,165 | −35,537 | **−30,851** | −2,805 | 9,373 |
| **strategy2** | 38,233 | 27,817 | **+33,025** | **+3,002** | 10,416 |
| strategy3 | −27,100 | −71,970 | **−49,535** | −4,503 | 44,869 |
| fast_path | −83,866 | −50,473 | **−67,170** | −6,106 | 33,393 |
| merged | 38,233 | 27,817 | **+33,025** | +3,002 | 10,416 |
| actual (published) | 73,420 | 73,420 | **+73,420** | +6,675 | 0 |
| hybrid: **S2 Charge + S1 Limit** | 32,992 | 22,330 *(10/11 G)* | **+27,661** | +2,515 | 10,662 |
| hybrid: **S1 Charge + S2 Limit** | −20,924 | −30,514 *(10/11 G)* | **−25,719** | −2,338 | 9,590 |
| hybrid: S1 Charge + S3 Limit | −25,815 *(10/11)* | −35,537 *(10/11)* | **−30,676** | −2,789 | 9,721 |
| hybrid: S3 Charge + S1 Limit | −27,450 *(10/11)* | −71,970 *(10/11)* | **−49,710** | −4,519 | 44,521 |
| oracle `a = t_lo, b = t_hi` | 194,700 | 194,700 | **+194,700** | +17,700 | 0 |
| oracle `a = b = t` (ceiling) | 251,606 | 251,606 | **+251,606** | +22,873 | 0 |

`(10/11 G)` marks a variant undefined in one Game: Strategy 1 and Strategy 3 both hit an
`APITimeoutError` at 55 s on Game 28 draw 1, so any hybrid with either as a parent has no value
there. Totals over 10 Games are never silently compared against totals over 11 — the matched
comparisons below restrict to the 21 Game-draws where every variant exists.

**Noise floor: 26,622 · √(11/18) = 20,811 EUR.**

| comparison | pooled gap | clears the 20,811 floor? |
| ---------- | ---------- | ------------------------ |
| strategy2 − strategy1 | **63,876** | **yes**, 3.1× the floor |
| strategy2 − strategy3 | **82,560** | **yes**, 4.0× the floor |
| strategy2 − fast_path | **100,195** | **yes** |
| strategy1 − strategy3 | 18,684 | **no** |
| strategy3 − fast_path | 17,634 | **no** |
| (S2 Charge + S1 Limit) − strategy2 | **−5,132** *(matched)* | no — the hybrid is *worse* |

---

## Per-Game wins — and why they were nearly useless

| | draw 0 | draw 1 |
| --- | --- | --- |
| **strategy2** | **6** | **5** |
| strategy1 | 3 | 1 |
| strategy3 | 1 | 3 |
| fast_path | 1 | 2 |

Strategy 2 now wins 6 and 5 of 11, which agrees with the euros. **But the win count was
worthless before the Limit cap landed**: on the pre-cap draws (`var/bakeoff/pre_limitcap/`)
Strategy 2 won 4 then 3, `fast_path` won 1 then 4 — and `fast_path` loses 67,170 euros. Head to
head on those draws Strategy 3 beat Strategy 2 in 5 of 11 Games while losing 56,653 euros over
the window.

So the durable finding is the shape, not the count: **Strategy 2's advantage is that it never
has a catastrophe.** Worst single Game-draw in the window — Strategy 2 **−15,992**, Strategy 1
−37,172, Strategy 3 −38,664, `fast_path` −49,894. Any router rule built on "which track won
last Game" picks the wrong track about half the time. **Count euros, over many Games.**

---

## Where the difference comes from: it is the **Charge**

Income depends only on our Charge; cost depends only on our Limit. Split them (pooled, mean
over draws, 11 Games):

| variant | income | cost | net |
| ------- | ------ | ---- | --- |
| strategy1 | 149,959 | 180,810 | −30,851 |
| **strategy2** | **210,434** | **177,409** | **+33,025** |
| strategy3 | 131,100 | 180,635 | −49,535 |
| fast_path | 113,594 | 180,763 | −67,170 |
| actual | 249,548 | 176,128 | +73,420 |
| oracle `a = b = t` | 372,228 | **120,622** | +251,606 |

**Cost is essentially identical across all four tracks: 177,409 to 180,810, a spread of 3,401
on a 177,000 base — one sixth of the noise floor.** Strategy 1 and Strategy 3 pin the Limit at
`STANDARD_LIMIT = 35` or 0; Strategy 2 derives it per item from its posterior with a ceiling and
an absolute cap. Those are radically different Limit policies buying a 2 % difference in cost.
Even the oracle, which knows `t` and rejects one cent above it, only reaches 120,622 — so
**about 120,000 of the 177,000 is fair Charges we owe and cannot avoid**, and the entire
contestable part of the cost side is ~57,000 over 11 Games.

**Income spans 113,594 → 210,434 across the four tracks, and 372,228 at the ceiling.** Every
euro of difference between these tracks is on the Charge side.

That is R6 and H1 confirmed on an independent measurement: no *constant* Limit beats another
constant Limit by more than a rounding error. It is **not** a claim that the Limit is harmless —
see the next paragraph.

### The one place the Limit did matter: an absolute cap, not a multiplier

On the pre-cap draws (`LIMIT_CEILING = 0.30`, no absolute cap) Strategy 2 pooled **+7,118**
with a cost of **188,918**. After the cap (commit `815725b`) it pools **+33,025** with a cost of
**177,409**. Cost fell **11,509** — that part is attributable to the Limit change, and it is
about half the noise floor. The rest of the +26,000 swing is fresh draws on the Charge side and
should not be credited to the cap. The two Line Items behind the cost saving are exactly the two
the cap was written for: Game 28 item 7 (old Limit 2,230 on `t < 49.50`, paying 10,775) and
Game 29 item 2 (old Limit 2,142 accepting thirteen opponents at exactly 2,000.00 on
`t < 57.30`).

The lesson generalises and is worth keeping: **a multiplicative ceiling is a multiple of the
number that broke.** When the estimate explodes the ceiling explodes with it, so it cannot bound
what we pay. Absolute caps can.

### The hybrids: do not ship one

Matched over the 21 Game-draws where all variants exist:

- **Strategy 2's Charge with Strategy 1's Limit: −5,132** relative to plain Strategy 2.
- **Strategy 1's Charge with Strategy 2's Limit: +5,132** relative to plain Strategy 1.

Both hybrids sit strictly between their parents, and the sign says the same thing twice:
**Strategy 2's Limit is now better than Strategy 1's fixed 35, and Strategy 2's Charge is
better than Strategy 1's by an order of magnitude more.** So the answer to "use strategy1's
Charge and strategy2's Limit" is *no* — it is the second-worst variant in the table
(−25,719) — and the reverse is also *no*, because it is 5,132 worse than simply using
Strategy 2 for both. Both differences are well inside the floor. **Take Strategy 2 whole.**

(Before the Limit cap the sign was the other way: Strategy 1's fixed Limit was worth +2,720
over Strategy 2's. The cap absorbed that advantage and then some. Worth recording, because it
is the same measurement giving opposite answers about a constant that changed underneath it —
exactly the drift this repo keeps paying for.)

### Per Line Item: Strategy 1 − Strategy 2

Bucketed on the larger of the two **submitted** Charges and on the invoice text — never on `t`.
(Conditioning on the true `t` is what makes the same items read 4× over-priced when they read
46 % under-priced conditioned on `t̂`; only the second is knowable at submission time.)

| bucket (our own Charge) | item-draws | S1 − S2, per draw |
| ----------------------- | ---------- | ----------------- |
| > 2,000 | 23 | **−31,788** |
| 500–2,000 | 24 | −20,469 |
| 100–500 | 99 | −11,620 |
| **labour lines** (hours / labour / work / service / install / repair …) | 34 | **−36,272** |
| non-labour | 112 | −27,604 |

The single largest lines, mean over draws:

| Game | item | S1 `a/b` | S2 `a/b` | true `t` | S1 − S2 |
| ---- | ---- | -------- | -------- | -------- | ------- |
| 24 | 3 Reinstate parquet, skirting, floor coverings | 3,465 / 35 | 2,410 / 708 | [1024, 1620) *(item 4)* | −15,580 |
| 26 | 12 Skilled worker hours (14 hrs) | 2,100 / 35 | 737 / 479 | [980, ∞) | −12,195 |
| 27 | 3 Compensation for robbery damage | 2,262 / 18 | 1,405 / 708 | [3000, 3022) | −10,927 |
| 24 | 8 Replace billiard cloth, cue sets… | 875 / 35 | 152 / 0 | [1071, 1505) | **+11,562** |
| 20 | 1 Air conditioning unit – living room | 1,925 / 35 | 1,340 / 708 | [2345, ∞) | **+8,646** |

Two answers to "where does it come from":

1. **Expensive items.** Strategy 1 loses most where it charges above 2,000: half of the 63,876
   gap comes from 23 item-draws in that bucket. Its Charge is a multiple of a raw model band
   with no coverage discount, so on a big item it lands above `t` and collects nothing.
2. **Labour lines specifically.** 34 item-draws whose name is an hours/labour line supply
   −36,272 of the −63,876, on 23 % of the items. Strategy 1 prices "Skilled worker hours
   (14 hrs)" by multiplying the rate up and is consistently 2–3× above `t`. Strategy 2's
   quantity and coverage handling is what saves it.

Note rows 4 and 5: **Strategy 1 also wins genuine money** where Strategy 2 under-charges a big
covered item (Game 24 item 8 at 152 against `t ≥ 1071`, Game 20 item 1 at 1,340 against
`t ≥ 2345`). The gap is not one-directional; it is that Strategy 1's losses are twice its wins.

Strategy 3 is the same failure amplified — Strategy 1's estimator, a different model, a larger
multiplier. Its > 2,000 bucket alone is **−63,531** per draw against Strategy 2, and Game 27
item 3 at a Charge of **25,025** on an item worth 3,000 is the single worst Line Item in the
window.

### Where Strategy 2 still leaves money (shortfall against the `a = b = t` ceiling)

| bucket (Strategy 2's own Charge) | items | shortfall vs oracle |
| -------------------------------- | ----- | ------------------- |
| 500–2,000 | 8 | −90,556 |
| 100–500 | 30 | −85,488 |
| < 100 | 32 | −45,371 |
| > 2,000 | 3 | **+8,041** |
| **total** | 73 | **−213,373** |

| Game | item | S2 `a/b` | true `t` | shortfall |
| ---- | ---- | -------- | -------- | --------- |
| 27 | 3 Compensation for robbery damage | 1,273 / 708 | [3000, 3022) | −31,047 |
| 20 | 1 Air conditioning unit – living room | 1,340 / 708 | [2345, ∞) | −22,446 |
| 24 | 8 Replace billiard cloth, cue sets… | 145 / 0 | [1071, 1505) | −21,635 |
| 25 | 13 Skilled worker hours 14 – | 40 / 0 | [1097, ∞) | −21,408 |
| 24 | 4 Restore and refinish plasterboard ceilings | 1,446 / 708 | [1024, 1620) | −10,456 |

Strategy 2 loses money in two ways now, both on the Charge:

1. **Under-charging a large covered item it did price** (Games 27, 20, 24 item 4, 26 item 12).
   Its Charge sits at `0.7 · t̂` and its `t̂` is low on the big items — the same direction R5b
   asks for, but too far.
2. **Falling back to the no-information constant of 39.62** when Channel C omits an index.
   32 of 73 Line Items were priced under €100 and two of them were worth about a thousand euros
   (Game 24 item 8, Game 25 item 13) for a −43,000 combined shortfall.

The `> 2,000` bucket being **positive** is worth noting: on the three items where Strategy 2
charged above 2,000 it beat the honest oracle, because the field accepted the Overcharge. That
is field generosity, not accuracy (see the `actual` section).

---

## Runtime — Strategy 3 is not a usable answer inside 60 seconds

| | mean | median | max | draws > 20 s | draws > 45 s |
| --- | --- | --- | --- | --- | --- |
| strategy1 | 10.9 | 8.8 | 55.5 | 1 / 22 | 1 |
| **strategy2** | **9.1** | **7.4** | 37.5 | 1 / 22 | 0 |
| strategy3 | **30.6** | **32.8** | 55.5 | **15 / 22** | 2 |
| fast_path | 7.3 | 7.0 | 20.7 | 1 / 22 | 0 |

Strategy 3's **median is 32.8 s** — more than half the Game — it exceeded 20 s in 15 of 22
draws, and it timed out entirely on Game 28 draw 1. A track that eats half the budget and is
the worst-scoring of the three when it answers has no claim on being the first fallback.
Strategy 2 is both the cheapest *and* the best: median 7.4 s, never above 37.5 s in 22 draws.

(Measured with `deadline=None`, i.e. each track's own `LLM_TIMEOUT_SECONDS`, one track at a
time. In production all four run concurrently so a Game's wall clock is the slowest track, not
the sum — but a 32.8 s median still eats the budget Strategy 2's per-item revisions want.)

---

## Reproducibility: two draws of the same track on the same Case

| track | mean per-Game gap | max per-Game gap | **pooled-total spread** |
| ----- | ----------------- | ---------------- | ----------------------- |
| strategy1 | 5,634 | 19,274 | 9,373 |
| **strategy2** | **2,096** | **9,484** | **10,416** |
| strategy3 | 5,382 | 30,398 | **44,869** |
| fast_path | 4,317 | 21,840 | 33,393 |

Read the last column, not the first: summing per-Game gaps overstates the uncertainty in a
pooled total because the gaps partly cancel. Draw 0's pooled total against draw 1's is the
honest re-run of the whole experiment.

- **Strategy 2 vs Strategy 1:** gap 63,876; both own pooled spreads under 10,500; Strategy 2
  ahead in *both* draws (38,233 vs −26,165 and 27,817 vs −35,537). **Distinguishable, clearly.**
- **Strategy 2 vs Strategy 3:** gap 82,560, ahead in both draws. **Distinguishable.**
- **Strategy 1 vs Strategy 3:** gap 18,684, and Strategy 3's own pooled spread is **44,869** —
  2.4× the gap. Draw 0 has them level (−27,100 vs −26,165); draw 1 has Strategy 3 collapse to
  −71,970. **Not distinguishable on euros alone.** The demotion below rests on direction plus
  runtime, not on this number.
- **Strategy 3 vs fast_path:** 17,634 — inside both the floor and Strategy 3's own spread.
  **Not distinguishable.** A plain `llm_values` call is not measurably worse than Strategy 3.

Strategy 2 is also the most reproducible track per Game by a factor of ~2.5 (mean gap 2,096 vs
5,634 / 5,382 / 4,317). Its two-framing ensemble plus fitted fallbacks are doing what ADR 0001
asked: *two regenerates over one invoice must not disagree.* Strategies 1 and 3 disagree with
themselves by more than they disagree with each other.

---

## Sensitivity to the opponent Limit rule

| variant | `lo` | `mid` | `hi` |
| ------- | ---- | ----- | ---- |
| strategy1 | −34,081 | −30,851 | −27,959 |
| **strategy2** | **+28,033** | **+33,025** | **+43,372** |
| strategy3 | −53,009 | −49,535 | −41,978 |
| fast_path | −69,318 | −67,170 | −60,233 |
| actual | 73,420 | 73,420 | 55,420 ⚠ |
| S2 Charge + S1 Limit | +22,669 | +27,661 | +37,760 |

Every ranking is identical under all three rules; the Strategy 2 − Strategy 1 gap is
**62,114 / 63,876 / 71,331** and clears the floor in each. **`mid` is the headline, `lo` is the
conservative bound.**

⚠ **`hi` should not be quoted.** Under `hi` the replay of our *actual* Game 29 submission
returns 1,823 against a published 19,823 — it fails the self-check by 18,000. Cause:
`replay_payoffs.limit_point(..., "hi")` returns `nextafter(b_hi, 0)`, which falls *below* `b_lo`
whenever the bracket is degenerate (`b_lo == b_hi`). Game 29 item 2 has nine opponents who
accepted our Charge of exactly 2,000.00, giving nine `[2000, 2000]` brackets, and `hi` turns all
nine acceptances into rejections. `mid` and `lo` reproduce all 11 published nets exactly.
*(Pre-existing quirk of `replay_payoffs`, not of this script; recorded so nobody re-derives it.
Fixing it belongs to whoever owns that file.)*

---

## Why `actual` beats every track, and why that is only half a fair fight

Published net over Games 20–30: **+73,420**. Best track re-run today: **+33,025**. The 40,000
gap is not diffuse — four Line Items carry it:

| Game | item | actual `a/b` | Strategy 2 `a/b` | true `t` | actual − S2 |
| ---- | ---- | ------------ | ---------------- | -------- | ----------- |
| 29 | 2 Renew water-damaged boiler *(uncovered)* | 2,000 / 1,050 | 5,206 / 708 | [0, 57.3) | **+20,000** |
| 20 | 1 Air conditioning unit | **2,345** / 20 | 1,340 / 708 | [2345, ∞) | +15,366 |
| 25 | 13 Skilled worker hours | 865 / 851 | 40 / 0 | [1097, ∞) | +15,223 |
| 22 | 1 Kitchen A/C *(uncovered)* | 1,855 / 123 | 40 / 0 | [0, 245.7) | **+14,206** |

Two are honest, reproducible skill: Game 20 item 1 charged **exactly `t_lo`** and was therefore
paid by all sixteen opponents; Game 25 item 13 was priced at 865 where both of today's draws
fell back to 39.62.

**Two of the four (34,206) are accepted Overcharges on items whose Fair Value is essentially
zero.** Games 22 and 29 show the field paying us one to two thousand euros for Line Items worth
under €250. That is R6c working — on an uncovered item the honest branch pays zero, so charging
is weakly dominant and a rejected Overcharge costs nothing — but it is exactly the region R5c
says never to *rely* on, because the income comes from a mis-measurable `p(a)`. It is stable in
this harness (the acceptances are directly observed, so `mid` and `lo` agree to the cent), but
it is field behaviour rather than our accuracy, and rule 9 says it will not survive the phase
boundary around Game 44.

So: **`actual` is authoritative as a number and only suggestive as a comparison.** It is the
published net, exact to the cent. It is *not* a re-run of today's code — different vintage,
different draws — so the 40,000 is not cleanly a regression. What it does prove is that the
ceiling is nowhere near reached and that Strategy 2's `< 100` fallback bucket is leaving five
figures on the table.

---

## Recommendation on the router priority

Current: `STRATEGY_PRIORITIES = {"strategy1": 1, "strategy3": 2, "strategy2": 3}`.

| | verdict | euros |
| --- | --- | --- |
| **`strategy2` at the top** | **Correct. Keep it, and stop treating it as provisional.** | +63,876 over Strategy 1 and +82,560 over Strategy 3 pooled — 3.1× and 4.0× the 20,811 floor — ahead in **both** draws and under **every** Limit rule. Also the fastest track (median 7.4 s) and the most reproducible per Game. |
| **`strategy3` above `strategy1`** | **Wrong. Swap them.** | Strategy 3 is 18,684 *worse* than Strategy 1 pooled, worse in both draws separately, median runtime 32.8 s against 8.8 s, and it produced the single worst Line Item in the window (Game 27 item 3, Charge 25,025 on `t = 3,000`). |
| Confidence in the swap | **Moderate, not proven.** | 18,684 is inside the 20,811 floor and well inside Strategy 3's own 44,869 draw spread. The direction is consistent across draws and corroborated by runtime; the magnitude is not established. |
| Risk of the swap | **Zero measured euros.** | `merged == strategy2` in 11 of 11 Games and 22 of 22 draws. The 1-vs-3 ordering has not decided a single euro since Game 21. It only matters when Strategy 2 goes silent — which is precisely the case the swap is for. |

**Change to make:** `STRATEGY_PRIORITIES = {"strategy3": 1, "strategy1": 2, "strategy2": 3}`.
One line, a tie-break that has never fired, makes the fallback the better and faster of the two,
and the evidence for the direction is consistent even where the magnitude is inside the floor.
**Do not touch Strategy 2's position.**

**Do not ship a hybrid.** "Strategy 1's Charge with Strategy 2's Limit" is −25,719, the
second-worst variant. The reverse, "Strategy 2's Charge with Strategy 1's Limit", is +27,661 —
still **5,132 worse than simply using Strategy 2 for both.** There is no Charge/Limit
recombination worth the complexity.

**Where the next real euros are.** Not the router and not a constant Limit — cost varies by 2 %
across four radically different Limit policies, and the whole contestable cost side is ~57,000
over 11 Games. Income varies by 97,000 between tracks and the ceiling is 372,228 against
Strategy 2's 210,434. Inside that, two candidates, both hypotheses rather than results:

1. **The 39.62 no-information fallback.** 32 of 73 Line Items were priced under €100 and two
   were worth about a thousand euros each. A cheap second pass that only has to cover the
   indices Channel C omitted is aimed at real money.
2. **Under-charging large covered items.** The five biggest shortfalls against the ceiling are
   all items Strategy 2 *did* price, at roughly 40–55 % of `t`. That is the level question H2
   was falsified on, so it must be attacked through better evidence (rule 5, ADR 0001) rather
   than another correction fitted to `t̂`.

Both belong in the hypothesis ledger, validated over **every** settled Game, one change at a
time.

---

## Caveats worth carrying forward

1. **11 Games is not many.** The floor is 20,811 and two of the five comparisons sit inside it.
   Re-run as Games settle: `--games 20-` picks up new ones automatically and the cache means
   only the new Games cost model calls.
2. **Two draws is a range, not a distribution.** The pooled draw spread over `n = 2` understates
   the true variance. `--draws 3` would be better and costs ~90 more model calls.
3. **`t` is bracketed, not known.** Line Items with no upper bracket use `t_lo`, so the
   251,606 ceiling is if anything *understated*.
4. **The Cap has never bound** in the observed rows, so both oracles extrapolate past the data
   on large Charges.
5. **Regime.** Games 20–30 are all in the first regime (field awake, field generous). Two of the
   four Line Items behind the `actual` column are accepted Overcharges, and Strategy 2's own
   `> 2,000` bucket beats the honest oracle for the same reason. None of that survives the
   boundary near Game 44 (rule 9). Re-measure there; do not carry it over.
6. **This compares the tracks as they are today.** A track scoring differently in Game 24 than
   it did when Game 24 was live is not by itself evidence that the code changed — `src/pricing.py`
   did change mid-session, which is why every Strategy 2 draw was re-taken afterwards.
