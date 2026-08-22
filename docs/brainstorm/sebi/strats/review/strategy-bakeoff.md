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
sixteen opponents held fixed), **Strategy 2 is the only track that makes money, and it is the
right one to have at the top of the router.** It replays at **+7,118** pooled against
**−30,851** for Strategy 1, **−49,535** for Strategy 3 and **−67,170** for the `fast_path`
layer. The Strategy 2 − Strategy 1 gap of **37,969** clears the scaled noise floor of
**20,811** and holds in both draws and under both trustworthy Limit rules. So the Game‑27
snapshot that started this — `strategy1` +21,032 against `strategy2` +7,887 — was **one Game
and one draw**, and the wider measurement reverses it.

The router is nevertheless **wrong in one place**: it ranks `strategy3` **above** `strategy1`,
and Strategy 3 is the worse of the two by **18,684** pooled. That gap does *not* clear the
floor, so the recommendation is a demotion on the balance of evidence rather than a proven
one — and it costs nothing, because Strategy 3 never wins the router anyway while
Strategy 2 answers.

And the honest headline nobody will like: **every track is beaten by what we actually
submitted (+73,420) and all of them are a long way under the oracle ceiling (+251,606).** The
tracks are arguing about a 38,000 gap inside a 245,000 shortfall.

---

## What was measured, and what was not

**Measured.** For each Game 20–30: `read_case`, then `propose(case)` twice per track
(`strategy1`, `strategy2`, `strategy3`, `fast_path.llm_values`), every draw cached to
`var/bakeoff/game_NNN_<source>_draw<k>.json` with its wall clock. Each draw is scored by
`replay_payoffs.replay()` against `snapshot(game_id)`, which reproduces every published net to
the cent. `actual` is `our_actual_submission(snap)` and equals the published net exactly in all
11 Games. `merged` is the router's per‑index priority merge (`standard` → `fast_path` →
priority order), rebuilt per draw.

**Inferred, and flagged as such.** Anything about *why* the model returned what it returned;
the reading of the `actual` column as evidence about today's code (it is not a re‑run — see
the caveats); and the demotion of Strategy 3, which is directionally consistent but inside the
noise floor.

**Not done, deliberately.** No log error anywhere. Every number below is euros. A log error
would treat Game 26's €10 line items exactly like Game 27's €3,000 one, and the entire
difference between these tracks lives in about a dozen expensive items.

**No leakage.** Strategy 2's Price Memory (`var/price_memory.json`) is built from Games 1–14
only (`built_from_games`), so nothing in Games 20–30 is being priced with its own answer.

**No side effects.** `strategy2.propose` writes a decision log, and re-running it for a settled
Game would overwrite `var/decisions/game_NNN.json` — destroying the only record of Game 27's
three Proposals. `_redirect_decision_log()` repoints `DECISIONS_DIR` at `var/bakeoff/decisions`
for the whole run. Nothing under `src/` was touched.

---

## Per-Game replayed net, draw 0 (EUR)

| Game | strategy1 | strategy2 | strategy3 | fast_path | merged | actual | oracle_exact |
| ---- | --------- | --------- | --------- | --------- | ------ | ------ | ------------ |
| 20 | 9,790 | 2,816 | 4,992 | 9,011 | 2,816 | 12,765 | 29,558 |
| 21 | 2,520 | 2,939 | 3,080 | 3,213 | 2,939 | 3,080 | 1,418 |
| 22 | 0 | 0 | *silent* | 0 | 0 | 14,840 | 1,966 |
| 23 | 3,172 | 3,320 | −1,066 | 1,652 | 3,320 | −821 | 7,336 |
| 24 | 16,073 | 18,694 | 25,108 | −52 | 18,694 | 13,013 | 86,704 |
| 25 | −37,172 | −15,945 | −35,840 | *silent* | −15,945 | 1,464 | 42,272 |
| 26 | −21,481 | −4,237 | −4,683 | −22,132 | −4,237 | −3,930 | 15,690 |
| 27 | 10,526 | 7,696 | −11,298 | −11,298 | 7,696 | 11,351 | 40,918 |
| 28 | 1,192 | −7,382 | 0 | 868 | −7,382 | 5,298 | 6,459 |
| 29 | −640 | 131 | −5,345 | 85 | 131 | 19,823 | 6,114 |
| 30 | −10,145 | −3,200 | −2,048 | −15,318 | −3,200 | −3,463 | 13,171 |
| **total** | **−26,165** | **4,833** | **−27,100** | **−83,866** | **4,833** | **73,420** | **251,606** |

`merged` is identical to `strategy2` in all 11 Games and both draws. That is worth stating
plainly: **the router is currently a one-track router.** Strategy 2 always answers, always
prices every Line Item, and always outranks the others, so Strategies 1 and 3 have contributed
exactly zero euros to any submission since Game 21. The ensemble is a log, not an ensemble.

---

## Pooled totals, one column per draw (Limit rule `mid`)

| variant | draw 0 | draw 1 | mean of draws | per Game | own draw spread |
| ------- | ------ | ------ | ------------- | -------- | --------------- |
| strategy1 | −26,165 | −35,537 | **−30,851** | −2,805 | 9,373 |
| **strategy2** | 4,833 | 9,403 | **+7,118** | +647 | 4,571 |
| strategy3 | −27,100 | −71,970 | **−49,535** | −4,503 | 44,869 |
| fast_path | −83,866 | −50,473 | **−67,170** | −6,106 | 33,393 |
| merged | 4,833 | 9,403 | **+7,118** | +647 | 4,571 |
| actual (published) | 73,420 | 73,420 | **+73,420** | +6,675 | 0 |
| hybrid: S2 Charge + S1 Limit | 12,642 | 14,336 *(10/11 G)* | **+13,489** | +1,226 | 1,694 |
| hybrid: S1 Charge + S2 Limit | −33,974 | −33,168 *(10/11 G)* | **−33,571** | −3,052 | 807 |
| hybrid: S1 Charge + S3 Limit | −25,815 *(10/11)* | −35,537 *(10/11)* | **−30,676** | −2,789 | 9,721 |
| hybrid: S3 Charge + S1 Limit | −27,450 *(10/11)* | −71,970 *(10/11)* | **−49,710** | −4,519 | 44,521 |
| oracle `a=t_lo, b=t_hi` | 194,700 | 194,700 | **+194,700** | +17,700 | 0 |
| oracle `a=b=t` (ceiling) | 251,606 | 251,606 | **+251,606** | +22,873 | 0 |

`(10/11 G)` marks a variant that is undefined in one Game: Strategy 1 and Strategy 3 both hit
an `APITimeoutError` at 55 s on Game 28 draw 1, so a hybrid with either as a parent has no
value there. Totals over 10 Games are never silently compared against totals over 11.

**Noise floor: 26,622 · √(11/18) = 20,811 EUR.**

| comparison | pooled gap | clears the 20,811 floor? |
| ---------- | ---------- | ------------------------ |
| strategy2 − strategy1 | **37,969** | **yes** |
| strategy2 − strategy3 | **56,653** | **yes** |
| strategy1 − strategy3 | 18,684 | **no** |
| strategy3 − fast_path | 17,634 | **no** |
| (S2 Charge + S1 Limit) − strategy2 | 2,720 *(matched)* | **no**, nowhere near |

---

## Per-Game wins — and why they are useless here

| | draw 0 | draw 1 |
| --- | --- | --- |
| strategy1 | 3 | 1 |
| strategy2 | **4** | 3 |
| strategy3 | 2 | 3 |
| fast_path | 1 | **4** |
| all four tied | 1 (Game 22) | 0 |

Head to head against Strategy 2, over 11 Games: Strategy 1 wins 3 then 4; Strategy 3 wins 5
then 4; `fast_path` wins 3 then 5. **On win counts the four tracks are indistinguishable, and
`fast_path` — which loses 67,170 euros — "wins" the most Games in draw 1.**

That is the finding, not a nuisance. Strategy 2's advantage is **not** that it wins Games; it
is that **it never has a catastrophe**. Worst single Game-draw in the window: Strategy 2
**−15,945**, Strategy 1 −37,172, Strategy 3 −38,664, `fast_path` −49,894. Any ranking rule
built on "which track won last Game" would have picked the wrong track roughly half the time.
Count euros.

Game 22 is the tie: one Line Item, every track charged above `t` and every reviewer rejected,
so nobody earned and nobody paid. Counting that as four wins is how a tie gets dressed up as
evidence; `win_counts()` reports it separately.

---

## Where the difference comes from: it is the **Charge**, not the Limit

Income depends only on our Charge; cost depends only on our Limit. Split them and the argument
ends (pooled, mean over draws, 11 Games):

| variant | income | cost | net |
| ------- | ------ | ---- | --- |
| strategy1 | 149,959 | 180,810 | −30,851 |
| strategy2 | **196,036** | 188,918 | +7,118 |
| strategy3 | 131,100 | 180,635 | −49,535 |
| fast_path | 113,594 | 180,763 | −67,170 |
| actual | 249,548 | 176,128 | +73,420 |
| oracle `a=b=t` | 372,228 | **120,622** | +251,606 |

**Cost is flat across every track: 180,635 to 188,918, a spread of 8,283 on a 180,000 base —
under half the noise floor.** Strategy 1 pins its Limit at `STANDARD_LIMIT = 35` or 0; Strategy
2 puts it at roughly 0.43 × its own Charge; Strategy 3 also sits at 35. Those are wildly
different Limit policies and they buy a 4 % difference in cost. Even the oracle, which knows
`t` exactly and rejects one cent above it, only gets cost down to 120,622 — so **60,000 of the
180,000 is fair Charges we owe and cannot avoid**, and the entire contestable part of the
Limit is worth about 60,000 across 11 Games, of which no track captures more than a sliver.

This is R6 and H1 confirmed on a fourth independent measurement: *no constant Limit beats any
other constant Limit by more than a rounding error.* Stop tuning it.

**Income is where the whole 100,000 spread lives:** 113,594 → 196,036 across the four tracks,
and 372,228 at the ceiling.

### The hybrids say the same thing

Swapping Limits between tracks moves the total by **exactly ±2,720** (matched Games and draws)
and — tellingly — by *exactly the same 2,720 under both the `mid` and `lo` opponent Limit
rules, because our own Limit only ever touches our own cost:

- Strategy 2's Charge with Strategy 1's strict Limit: **+2,720** over Strategy 2 alone.
- Strategy 1's Charge with Strategy 2's Limit: **−2,720** relative to Strategy 1 alone.

So "use Strategy 1's Charge and Strategy 2's Limit" is the **worst** available combination
(−33,571) and the reverse is the best (+13,489), but the best is only 2,720 better than plain
Strategy 2 — an eighth of the floor. **Do not ship a hybrid.** And the reason the 2,720 exists
at all is a single item: on Game 28 item 7 Strategy 2's Limit of 2,230 accepted a Charge on a
Line Item worth under 49.50, paying 10,775; Strategy 1's Limit of 35 pays nothing there.
Strategy 1's strictness saves 10,775 on that one item and gives back about 8,000 in wrongful-
rejection penalties elsewhere. That is a real, specific bug in Strategy 2's Limit — worth
fixing on its own merits — not an argument for a hybrid.

### Per Line Item: Strategy 1 − Strategy 2, conditioned on our own Charge

Bucketed on the larger of the two **submitted** Charges and on the invoice text — never on `t`.
(Conditioning on the true `t` is what makes the same items read 4× over-priced when they read
46% under-priced conditioned on `t̂`; only the second is knowable at submission time.)

| bucket (our own Charge) | item-draws | Strategy 1 − Strategy 2, per draw |
| ----------------------- | ---------- | --------------------------------- |
| > 2,000 | 23 | **−18,762** |
| 100–500 | 100 | −11,764 |
| 500–2,000 | 23 | −7,443 |
| **labour lines** (name contains hours/labour/work/service/install/repair…) | 34 | **−26,564** |
| non-labour | 112 | −11,405 |

Two answers to "where does it come from":

1. **Expensive items.** Strategy 1 loses most where it charges above 2,000. Its Charge is a
   multiple of a raw model band with no coverage discount, so on a big item it lands above `t`
   and collects nothing: Game 27 item 3 at 4,375 against `t ∈ [3000, 3022)`; Game 26 item 12 at
   2,100 against `t ≥ 980`; Game 24 item 4 at 2,450 against `t ∈ [1024, 1620)`.
2. **Labour lines specifically.** 34 item-draws whose name is an hours/labour line account for
   −26,564 of the −37,850 total, on 23 % of the items. Strategy 1 prices "Skilled worker hours
   (14 hrs)" by multiplying up, and it is consistently 2–3× above `t`. Strategy 2's coverage-
   and-quantity handling is the thing that saves it.

Strategy 3 is the same failure amplified — it uses Strategy 1's estimator with a different
model and a larger multiplier. Its > 2,000 bucket is **−51,124** per draw against Strategy 2,
with Game 27 item 3 at **25,025** on an item worth 3,000 the single worst line in the window.

### Where Strategy 2 still leaves money (shortfall against the `a=b=t` ceiling)

| bucket (Strategy 2's own Charge) | items | shortfall vs oracle |
| -------------------------------- | ----- | ------------------- |
| 500–2,000 | 8 | −91,761 |
| < 100 | 33 | −86,602 |
| 100–500 | 28 | −57,761 |
| > 2,000 | 4 | −10,649 |
| **total** | 73 | **−246,773** |

The `< 100` bucket is the interesting one. Those are Line Items where Strategy 2 fell back to
its no-information constant of **39.62** because Channel C returned nothing for that index —
and three of them were worth about a thousand euros each:

| Game | item | Strategy 2 `a/b` | true `t` | shortfall |
| ---- | ---- | ---------------- | -------- | --------- |
| 24 | 8 Replace billiard cloth, cue sets… | 40 / 18 | [1071.78, 1505) | −23,321 |
| 25 | 13 Skilled worker hours 14 – | 40 / 0 | [1097.15, ∞) | −21,408 |
| 24 | 7 Billiard table inspection, re-cover… | 40 / 18 | [921.96, 1080) | −18,538 |
| 27 | 3 Compensation for robbery damage | 1,146 / 588 | [3000, 3022) | −33,080 |
| 20 | 1 Air conditioning unit – living room | 1,310 / 568 | [2345, ∞) | −23,612 |
| 28 | 7 Renew boiler system… | 5,387 / 2,230 | [0, 49.5) | −10,908 |

So Strategy 2 loses money in exactly three ways, in order of size: (a) **under-charging a
large covered item** it did price (Games 27, 20, 24 item 4, 26 item 12); (b) **going to the
39.62 constant** when the model omits an index, on an item worth a thousand; (c) **one loose
Limit** on an uncovered item (Game 28 item 7). None of that is fixed by promoting Strategy 1 —
Strategy 1's shortfall against the same ceiling is **−277,771**, worse.

---

## Runtime — Strategy 3 is not a usable answer inside 60 seconds

Wall clock per draw, seconds:

| | mean | max | draws over 20 s | draws over 45 s |
| --- | --- | --- | --- | --- |
| strategy1 | 10.9 | 55.5 | 1 / 22 | 1 |
| **strategy2** | **7.9** | **20.4** | 1 / 22 | 0 |
| strategy3 | **30.6** | 55.5 | **15 / 22** | 2 |
| fast_path | 7.3 | 20.7 | 1 / 22 | 0 |

Strategy 3 averages **30.6 s** and exceeded 45 s twice, timing out entirely on Game 28
draw 1. In a 60-second Game with a submission reserve, a track whose median is half the budget
is a track that will sometimes contribute nothing — and it is the worst-scoring of the three
when it does answer. Strategy 2 is both the cheapest and the best: mean 7.9 s, never above
20.4 s in 22 draws.

(These are measured with `deadline=None`, i.e. each track's own `LLM_TIMEOUT_SECONDS`, run one
at a time. In production all four run concurrently, so the Game's wall clock is the slowest
track, not the sum — but a 30 s median still eats the budget that Strategy 2's revisions want.)

---

## Reproducibility: the draws are noisy, and one comparison is inside that noise

Two independent draws of the same track on the same Case:

| track | mean per-Game gap | max per-Game gap | pooled-total spread |
| ----- | ----------------- | ---------------- | ------------------- |
| strategy1 | 5,634 | 19,274 | 9,373 |
| **strategy2** | **1,286** | **5,801** | **4,571** |
| strategy3 | 5,382 | 30,398 | 44,869 |
| fast_path | 4,317 | 21,840 | 33,393 |

Read the last column, not the first: summing per-Game gaps overstates the uncertainty in a
pooled total because the gaps partly cancel. The pooled total of draw 0 against draw 1 is the
honest re-run of the whole experiment.

- **Strategy 2 vs Strategy 1:** the gap is 37,969, both tracks' own pooled draw spreads are
  under 10,000, and Strategy 2 is ahead in *both* draws (4,833 vs −26,165; 9,403 vs −35,537).
  **Distinguishable.**
- **Strategy 1 vs Strategy 3:** the gap is 18,684 and Strategy 3's own pooled draw spread is
  **44,869** — more than twice the gap. Draw 0 has them essentially level (−27,100 vs −26,165);
  draw 1 has Strategy 3 collapse to −71,970. **Not distinguishable on the euros.** The demotion
  recommendation below rests on the *direction being consistent* plus the runtime evidence, not
  on this number.
- **Strategy 3 vs fast_path:** 17,634, inside both the floor and Strategy 3's own spread.
  **Not distinguishable.** Note what that means: a plain `llm_values` call is not measurably
  worse than Strategy 3.

Strategy 2 is also **the most reproducible track by a factor of four** (pooled spread 4,571 vs
9,373 / 44,869 / 33,393). Its two-framing ensemble and its fitted fallbacks are doing exactly
what ADR 0001 asked for: *two regenerates over one invoice must not disagree.* They nearly do
not. The other three disagree with themselves by more than they disagree with each other.

---

## Sensitivity to the opponent Limit rule

The harness has to pick a representative point inside each opponent's reconstructed Limit
bracket. Pooled totals under each rule:

| variant | `lo` | `mid` | `hi` |
| ------- | ---- | ----- | ---- |
| strategy1 | −34,081 | −30,851 | −27,959 |
| strategy2 | +4,835 | **+7,118** | +19,222 |
| strategy3 | −53,009 | −49,535 | −41,978 |
| fast_path | −69,318 | −67,170 | −60,233 |
| actual | 73,420 | 73,420 | 55,420 ⚠ |
| S2 Charge + S1 Limit | +11,206 | +13,489 | +25,360 |

Every ranking is identical under all three rules and the Strategy 2 − Strategy 1 gap is 38,916
/ 37,969 / 47,181 — it clears the floor in each. **`mid` is the headline** and `lo` is the
conservative bound.

⚠ **`hi` is not trustworthy here and should not be quoted.** Under `hi` the replay of our
*actual* Game 29 submission returns 1,823 against a published 19,823, i.e. it fails the
self-check by 18,000. Cause found: `limit_point(..., "hi")` returns `nextafter(b_hi, 0)`, which
is *below* `b_lo` whenever the bracket is degenerate (`b_lo == b_hi`). Game 29 item 2 has nine
opponents who accepted our Charge of exactly 2,000, giving nine `[2000, 2000]` brackets, and
`hi` turns all nine acceptances into rejections. `mid` and `lo` reproduce all 11 published nets
exactly. *(This is a pre-existing quirk of `replay_payoffs.limit_point`, not of this script; it
is recorded here because someone will otherwise re-derive it. Fixing it belongs to whoever owns
that file.)*

---

## Why `actual` beats every track, and why that is only half a fair fight

The published net over Games 20–30 is **+73,420**; the best track re-run today is **+7,118**.
The 66,000 gap is not diffuse — it is five Line Items:

| Game | item | actual `a/b` | Strategy 2 `a/b` | true `t` | actual − S2 |
| ---- | ---- | ------------ | ---------------- | -------- | ----------- |
| 29 | 2 Renew water-damaged boiler (uncovered) | 2,000 / 1,050 | 5,206 / 708 | [0, 57.3) | **+20,000** |
| 20 | 1 Air conditioning unit | **2,345** / 20 | 1,310 / 568 | [2345, ∞) | +16,533 |
| 25 | 13 Skilled worker hours | 865 / 851 | 40 / 0 | [1097, ∞) | +15,223 |
| 22 | 1 Kitchen A/C (uncovered) | 1,855 / 123 | 2,661 / 0 | [0, 245.7) | **+14,840** |
| 28 | 7 Renew boiler (uncovered) | 2,000 / 25 | 5,387 / 2,230 | [0, 49.5) | +12,512 |

Two of those five are honest and reproducible skill: Game 20 item 1 charged **exactly `t_lo`**
and was therefore paid by all sixteen opponents, and Game 25 item 13 was priced at 865 where
today's draws fell back to 39.62.

**Three of the five (47,352 of the 66,000) are accepted Overcharges on items whose Fair Value
is essentially zero.** Games 22, 28 and 29 all show the field paying us one to two thousand
euros for Line Items worth under €250. That is R6c working — on an uncovered item the honest
branch pays zero, so charging is weakly dominant and a rejected overcharge is free — but it is
also precisely the region R5c says never to *rely* on, because it is income from a
mis-measurable `p(a)`. It is stable in this harness (the acceptances are directly observed, so
`mid` and `lo` agree to the cent), but it is field behaviour, not our accuracy, and rule 9 says
it will not survive the phase boundary at Game ~44.

So the right reading of the `actual` column is: **`actual` is authoritative as a number and
suggestive as a comparison.** It is the published net, exact to the cent. It is *not* a re-run
of today's code — it was produced by an older vintage with different constants and different
model draws — so the 66,000 is not cleanly attributable to a regression. What it does prove is
that the ceiling is nowhere near reached and that Strategy 2's `< 100` fallback bucket is
leaving five figures on the table.

---

## Recommendation on the router priority

Current: `STRATEGY_PRIORITIES = {"strategy1": 1, "strategy3": 2, "strategy2": 3}`.

| | verdict | euros |
| --- | --- | --- |
| **`strategy2` at the top** | **Correct. Keep it.** | +37,969 over Strategy 1, +56,653 over Strategy 3, both clearing the 20,811 floor, in both draws, under both trustworthy Limit rules. It is also the fastest track (mean 7.9 s) and the most reproducible (pooled draw spread 4,571). |
| **`strategy3` above `strategy1`** | **Wrong. Swap them.** | Strategy 3 is 18,684 *worse* than Strategy 1 pooled, is worse in both draws separately, has a mean runtime of 30.6 s against 10.9 s, and produced the single worst Line Item in the window (Game 27 item 3 at 25,025 on `t = 3,000`). |
| Confidence in the swap | **Moderate, not proven.** | 18,684 is inside the 20,811 floor and inside Strategy 3's own 44,869 draw spread. The direction is consistent; the magnitude is not established. |
| Risk of the swap | **Zero measured euros.** | `merged == strategy2` in 11 of 11 Games and 22 of 22 draws. The 1-vs-3 ordering has not decided a single euro since Game 21. It only matters as the fallback if Strategy 2 goes silent — which is exactly the case the swap is for. |

**So: swap 1 and 3 to `{"strategy1": 2, "strategy3": 1, "strategy2": 3}`.** It is a one-line
change to a tie-break that has never fired, it makes the fallback the better and faster of the
two tracks, and the evidence for the direction is consistent even though the magnitude is
inside the floor. Do not touch Strategy 2's position.

**Do not ship a hybrid.** "Strategy 2's Charge with Strategy 1's Limit" is the best variant in
the whole table at +13,489, but its advantage over plain Strategy 2 is **2,720** over 11 Games
— an eighth of the floor — and it comes almost entirely from one Line Item. Take the
underlying lesson instead: **Strategy 2's Limit accepted 2,230 on a Line Item worth under
49.50** (Game 28 item 7). That is a coverage failure leaking into the Limit, it cost 10,775 in
one Game, and it is worth a look on its own.

**Where the next real euros are.** Not in the router and not in the Limit — cost varies by 4 %
across four wildly different Limit policies, and the contestable part of the whole cost side is
~60,000 across 11 Games. Income varies by 100,000 and the ceiling is 372,228 against Strategy
2's 196,036. Inside that, the cheapest identified win is the **39.62 no-information fallback**:
33 of 73 Line Items were priced under €100 and three of them were worth about a thousand
euros, for a −86,602 shortfall in that bucket alone. A second ensemble draw that only has to
cover the indices Channel C omitted would be aimed at real money. That is a hypothesis, not a
result — it belongs in the ledger, measured over all settled Games, one change at a time.

---

## Caveats worth carrying forward

1. **11 Games is not many.** The floor is 20,811 and three of the five comparisons above sit
   inside it. Re-run as Games settle; `--games 20-` picks up new ones automatically and the
   cache means only the new Games cost model calls.
2. **Two draws is not a distribution.** The pooled draw spread is a range over `n = 2`, which
   understates the true variance. `--draws 3` would be better and costs ~90 more model calls.
3. **`t` is bracketed, not known.** 44-odd Line Items across the corpus have no upper bracket,
   so `oracle_exact` uses `t_lo` there and the ceiling of 251,606 is if anything *understated*.
4. **The Cap has never bound**, so both oracles extrapolate past the data on large Charges.
5. **Regime.** Games 20–30 are all inside the first regime (field awake, field generous).
   Three of the five Line Items behind the `actual` column are accepted Overcharges. None of
   that survives the boundary at Game ~44 (rule 9). Re-measure then; do not carry it over.
6. **The comparison is of tracks as they are today,** including today's model behaviour. A
   track that scored differently in Game 24 when Game 24 was live is not evidence that the code
   changed.
