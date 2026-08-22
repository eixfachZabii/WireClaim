# Field findings — what settled Games actually measured

Append a block per Game. Everything here is inverted from the public leaderboard
(confirmed allowed). Conclusions live in [`report.md`](report.md); the fixes in
[`trackplan.md`](trackplan.md).

**Inversion rules.** `amount` is what the **Issuer receives**, in *both* branches — so
`a = amount`, never `amount/1.5` (verified: accepted/rejected ratio exactly 1.0000 across
7 independent pairs in Game 1). Rejected with `amount > 0` ⇒ the Charge was Fair, so the
largest such Charge on a Line Item is a hard **lower bound** on Fair Value. Rejected with
`amount = 0` ⇒ Fraud Zone.

## Games 15–19: the Limit fix landing, and overshooting

| Game | Line Items | income | paid on accepts | penalties | net | accept rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 15 | 29 | 17,200 | 21,056 | 14,946 | **-18,802** | 77% |
| 16 | 2 | 0 | 4,721 | 0 | **-4,721** | 97% |
| 17 | 20 | 20,580 | 70,736 | 13,633 | **-63,789** | 71% |
| 18 | 14 | 14,469 | 419 | 51,132 | **-37,082** | 32% |
| 19 | 9 | 54,618 | 58 | 20,152 | **34,408** | 33% |
| 20 | 6 | 38,202 | 51 | 25,387 | **12,765** | 29% |

The `max(coverage_probability, 0.9)` fix (commit `c147ce9`) is visible in one number: the
accept rate falls from **71 % in G17 to 32–33 %**, and with it the 70,736 we paid out on
accepted claims in G17. It then **overshot** — G18 lost 51,132 purely to wrongful
rejections while paying 419 on accepts. G19 was the first clear win, **+34,408 on income
of 54,618**, and is the first Game where the Charge side carried us.

## Strategy 2, replayed against the real field

Feeding the cached model evidence (`scripts/dump_evidence.py`) through `src/pricing.py`
and scoring with `scripts/replay_payoffs.py`, which reproduces every published net to the
cent. **Price Memory is excluded**, so this is the honest number and not a leak:

| Limit multiplier | 0.5 | **1.0 (shipped)** | 1.5 | 2.0 | 3.0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| net over G5, 8, 10, 13, 14, 15, 17, 18, 19 | +33,793 | **+46,421** | +38,663 | +4,125 | −15,697 |

**We actually scored −241,655 on those nine Games.** G17 replays at ≈0 instead of −63,789
and G18 at ≈+1,000 instead of −37,082. The shipped Limit is already at the optimum, so the
bottom-third quantile is confirmed on real data rather than argued — scaling it in either
direction loses money.

Remaining weakness is the heavy tail: G10 still replays at only +1,000 because its Line
Item worth `t ≥ 7,225` is priced like an ordinary one.

### Do not "fix" the undercharging with a multiplier

Over 15 Games (1, 2, 4, 5, 8–15, 17–19) where we actually scored **−324,706**, scaling
every Charge by a single factor:

| Charge × | 0.7 | **1.0 (shipped)** | 1.3 | 1.6 | 2.0 | 3.0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| net | −17,164 | **+62,814** | +32,098 | −63,807 | −238,384 | −383,211 |

**The shipped level is already the global optimum, worth +387,521 against what we
actually did.** Raising Charges across the board loses money quickly, because most Line
Items are cheap — median `t` is ~59 — and pushing them above `t` forfeits income that was
otherwise collected from *every* opponent.

So the tail problem is **item-specific, not a level problem**, and no multiplier can fix
it. It needs the estimate itself to recognise an expensive item. The counter-example is
Game 20, where Strategy 2 replays at +5,473 against our actual +12,765: it charged 1,281
on an air-conditioning unit we charged 2,345 for, and the item was worth more than both.

---

## Every settled Game, current through Game 14

Generated with `scripts/pull_transactions.py` (which pages to the end) and
`scripts/invert_fair_values.py`. **`/transactions` paginates at 100 rows** — any Line
Item count written earlier in this file that is lower than the one here was a short
read, not a small Case. `income` includes what a wrongful rejection still owes us.

| Game | Line Items | our income | paid on accepts | penalties | our net | dominant mechanism |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 18 | 19,704 | 1,127 | 5,075 | **13,502** | **positive** — income exceeded both cost sides |
| 2 | 7 | 5,088 | 601 | 3,765 | **722** | **positive** — income exceeded both cost sides |
| 3 | 2 | 0 | 0 | 0 | **0** | submitted nothing, but every `t` was 0 so it cost nothing |
| 4 | 15 | 13,935 | 6,238 | 4,177 | **3,520** | **positive** — income exceeded both cost sides |
| 5 | 17 | 9,075 | 19,450 | 230 | **-10,604** | **`b` unbounded** — paid above `t` |
| 6 | 2 | 1,035 | 0 | 4,975 | **-3,940** | **`b` too low** — wrongful-rejection penalties |
| 7 | 6 | 0 | 33,568 | 0 | **-33,568** | **`b` unbounded** — paid above `t` |
| 8 | 39 | 3,429 | 83,503 | 0 | **-80,074** | **`b` unbounded** — paid above `t` |
| 9 | 16 | 750 | 17,334 | 4,813 | **-21,397** | mixed: `a` above `t` and `b` misaligned |
| 10 | 6 | 5,300 | 0 | 65,806 | **-60,506** | **`b` too low** — wrongful-rejection penalties |
| 11 | 23 | 0 | 0 | 36,017 | **-36,017** | **submitted nothing** — `b`=0 turned every fair claim into `1.5a` |
| 12 | 12 | 0 | 0 | 43,381 | **-43,381** | **submitted nothing** — `b`=0 turned every fair claim into `1.5a` |
| 13 | 17 | 16,800 | 3,555 | 15,852 | **-2,607** | **`b` too low** — wrongful-rejection penalties |
| 14 | 13 | 450 | 2,374 | 676 | **-2,599** | mixed: `a` above `t` and `b` misaligned |

**Totals by mechanism across all 14 Games** (from the reconstruction in
[`t-inversion.md`](t-inversion.md)): forfeited income from `a` below `t` **298,379**;
overpaying with `b` above `t` **100,664**; the `0.5a` surcharge from `b` below `t`
**61,588**; overcharges rejected **23,194**.

---

## Standing after Games 1–3

| | team | G1 | G2 | G3 | total |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | error404 ai | 33,436 | 4,803 | 403 | 38,642 |
| 2 | Codacabana | 13,441 | 10,355 | 0 | 23,797 |
| 3 | **Bin busy (us)** | 13,502 | 722 | 0 | **14,223** |
| 4 | AsianSuperNerds | −8,274 | 11,651 | 0 | 3,377 |
| — | *the default* | −8,274 | −5,144 | 0 | — |

## Measurements

**Undercharging, ~2.5× median.** `t_lower / our Charge`, where `t_lower` is a hard bound:

| Game | item | `t ≥` | our `a` | ratio |
| --- | ---: | ---: | ---: | ---: |
| 1 | 2 | 227.66 | 144.00 | 1.58× |
| 1 | 6 | 569.16 | 280.00 | 2.03× |
| 1 | 7 | 182.13 | 60.00 | 3.04× |
| 1 | 9 | 409.79 | 176.00 | 2.33× |
| 1 | 13 | 227.66 | 72.00 | 3.16× |
| 1 | 15 | 606.22 | 360.00 | 1.68× |
| 2 | 1 | 310.00 | 108.00 | 2.87× |
| 2 | 4 | 555.00 | 210.00 | 2.64× |

Forfeited guaranteed income: **21,625 in Game 1** (1.6× the 13,502 we scored) and
**8,752 in Game 2** (vs +722 scored).

**Zero Charges on live items.** 8 of 18 Line Items in G1, 5 of 7 in G2, 2 of 2 in G3.
G1 items 1 and 18 were covered (`t ≥ 122.94`, `98.02`) and we charged nothing.

**Our Limit is unbounded on several items.** Inverting our own reviewer behaviour, G1
items 8, 14, 16, 17 show `b ∈ [x, ∞)` — we never rejected anything. On 8, 16 and 17 the
Fair Value was *below* Charges we accepted.

**The Overcharge is dead.** Field acceptance measured at **5.96 %** (31.8 % among the
four awake teams) against a ~25 % break-even. Our own G1 Overcharges — items 8, 16, 17 —
were all rejected and all settled at exactly 0, confirming a failed Overcharge is free.

**Uncovered items pay, and we are not collecting.** Game 3's Line Items were all `t = 0`.
Nearly every team scored exactly 0; `error404 ai` charged anyway and made **+403**,
`Non Deterministic` **+400**. That is R6c in real money.

**Convention risk is the quantity column, not VAT.** On Game 1, a per-unit (`÷q`) slip
costs 30,400–38,100; a VAT (`÷1.19`) slip costs 6,960 — **5.5× worse**. Going dark
entirely costs 41,710.

## Case structure — read from decrypted Cases 1–4

Keys unlock at each Game's start, so every past Case is readable. Four of them overturn
the assumption that this is a pricing problem.

**Line Items are self-labelling.** The generator puts the disqualifier in the description
text, in parentheses:

| Case | Line Item | The tell |
| --- | --- | --- |
| 1 | "Preventive replacement of plant-room electrical components **(no confirmed water contact)**" | not Related to the damage |
| 1 | "**Upgrade** to high-quality natural stone floor (**upgrade from pre-loss ceramic tiling**)" | betterment — the policy owes the pre-loss standard |
| 1 | "Supply and install **premium hardwood** skirting boards (**upgrade from pre-loss softwood**)" | betterment |
| 4 | "DVD player (**was already failing before the storm, age-related**)" | pre-existing, not caused by the peril |
| 4 | "Router (**no diagnostic report provided**)" | unproven |
| 4 | "**Administrative and claim-processing fee**" | not an indemnifiable loss |

**Whole Cases can be uncovered, and Game 3 was one.** Case 3's policy is buildings-only —
*"an insurance of immovable property at a defined location… it is **not** an insurance of
the movable belongings of the persons who live there, and it is **not** an insurance of
any form of transport."* The claim is a suitcase stolen from a parked car in France. Both
Line Items are `t = 0`. That is why nearly the whole Field scored exactly 0 and the two
teams that charged anyway took ~400 each.

**Consequences.**

- **The coverage/relatedness gate is worth more than any pricing refinement.** `t = 0`
  turns a good price estimate into a wrong answer, and Case 3 shows entire Cases can be
  zero. Reading the policy's scope clause first is the highest-value single step.
- **Betterment is a partial haircut, not a binary.** Items 4 and 18 in Case 1 are covered
  *at the pre-loss standard* — stone priced as ceramic, hardwood as softwood. A binary
  covered/not-covered verdict gets both wrong in opposite directions.
- **"Vehicle costs" recurs in all four Cases** and is the most repeated Line Item seen so
  far — worth pinning down once, since Price Memory will hit it constantly.
- **Some Line Items carry `– –` for quantity and unit.** Any parser that assumes a numeric
  quantity will produce a wrong gross total on exactly the items designed to be traps.
- This is a **reading** task before it is a pricing task, which is the empirical case for
  [ADR 0001](../../adr/0001-the-model-reads-the-engine-prices.md): agents read and quote
  the clause, deterministic code prices.

## Past Cases are a permanent, growing, labelled corpus

A Game's decryption key never expires. Every Case we have played stays readable, so:

```bash
# in "[PUBLIC] EHL Cases/cases" -- extracts every Case whose Game has started
for g in $(seq 0 100); do d=case_$(printf %02d $g)
  K=$(curl -s -H "X-API-Key: $TEAM_API_KEY" \
      "https://c2f.public.quantco.cloud/api/games/$g/key" | jq -r .decryption_key)
  [ "$K" = null ] && break
  7z x -y -p"$K" -o"$d" "$d.zip" >/dev/null
done
```

Pair that with the Settlement brackets above and every Game hands us a **labelled
training example we can keep forever**:

| from decryption | from the leaderboard |
| --- | --- |
| policy text, damage description, Line Item wording, photo | `t` lower bound per Line Item |
| | whether the whole Field charged 0 (⇒ almost certainly uncovered) |
| | which Charges were Fair and which were Overcharges |

**The coverage gate can therefore be trained, not just prompted.** Concretely:

- **Few-shot the coverage agent from decided Line Items.** "Preventive replacement …
  (no confirmed water contact)" with a known verdict is worth more than any amount of
  prompt wording, and the examples cost nothing to collect.
- **Retrieve on Line Item wording.** "Vehicle costs" has now appeared in all four Cases;
  once its verdict is settled under a given policy type, it never has to be reasoned
  about again. Same for "Shipping", "Installation", "Final site cleaning".
- **Keep a held-out validation set.** Prompt and threshold changes can be scored against
  past Cases *offline*, before they touch a live Game — the one place in this tournament
  where we get to test a change without paying for it.
- **The corpus compounds fastest exactly when we need it.** By the small hours we will
  have 40+ Cases and several hundred decided Line Items, which is the phase where
  accuracy is the only lever (README R10).

Extracted Case folders are gitignored — they are derivable from the committed archive
plus a key, so there is no reason to carry them in git.

## Game 5 post-mortem — we lost 10,604, and it was all the Limit

| Game | income | paid on ACCEPT | paid on REJECT | net |
| --- | ---: | ---: | ---: | ---: |
| 4 | 13,935 | 6,238 (150 txns) | 4,177 (90) | +3,520 |
| 5 | 9,075 | **19,450 (246 txns)** | 230 (26) | **−10,604** |

**99 % of Game 5's costs came from accepting.** We accepted 246 of 272 Transactions —
our Limit is effectively infinite.

The mechanism is specific and it is the worst possible pairing. On the Line Items where
our own pipeline decided *"not covered, charge nothing"*, we still accepted the whole
Field's Charges on that same item:

| item | our Charge | we accepted up to |
| ---: | ---: | ---: |
| 3 | **0.00** | **1,121.40** |
| 7 | **0.00** | 522.23 |
| 11 | **0.00** | 510.00 |
| 10 | **0.00** | 365.56 |
| 14 | **0.00** | 360.00 |

We identified `t = 0` for our own issuing and then paid four figures for it as Reviewer.
Forfeiting the free option (R6c) *and* funding everyone else's Overcharge, on the same
Line Item, in the same Submission.

**This reverses the priority in `report.md` and `trackplan.md`.** Those were written when we
were losing to timidity as Issuer; the Charge was the sensitive knob and `b` looked flat.
That was true of the *Field average*, not of a Limit this loose. R6's "spend the effort
on the Charge" holds only once `b` is inside the posterior at all. Ours is outside it.

**The single rule that fixes it: coverage verdict must drive `b`, not just `a`.**
If the item is not covered, `t = 0`, so *every* Charge on it is in the Fraud Zone and the
correct Limit is exactly **0**. The same verdict should push `a` **up**, not down.

| verdict | Charge `a` | Limit `b` |
| --- | --- | --- |
| covered | ~`t̂` (raise it — we still undercharge) | bottom third of the posterior |
| **not covered** | **high** — free option, toward the Cap floor (R6c) | **0** |
| unsure | mid | low, and never above `t̂` |

### Correction — those zero-Charge items were COVERED

The table above was built from **our own** Transaction rows, which only bracket `t` where
*we* were a counterparty. Pulling five teams' rows for Game 5 (2,380 unique Transactions)
gives real two-sided brackets, and it overturns the reading:

| item | true `t` | our Charge | we accepted up to |
| ---: | --- | ---: | ---: |
| 3 | **[497.94, 773.50)** | **0.00** | 1,121.40 |
| 14 | **≥ 360.00** | **0.00** | 360.00 |
| 7 | **[130.50, 180.00)** | **0.00** | 522.23 |
| 4 | `< 38.25` — genuinely uncovered | 31.88 | 67.00 |
| 16 | `< 42.50` — genuinely uncovered | 112.50 | 42.50 |

**Only 2 of 17 Line Items were actually uncovered.** The ones we charged nothing for were
worth hundreds. So this is not "we detected `t = 0` and failed to exploit it" — **the
coverage gate emitted false *uncovered* verdicts on covered items**, and we then paid the
Field's Charges on those same items. Both errors, same Line Item, same Submission.

**And the Charge is no longer biased low — it is high-variance.** In the same Case we
overshot badly: item 1 `t < 875` (charged 875), item 2 `t < 199.25` (charged 450), item 5
`t < 130.50` (charged 600), item 13 `t < 400` (charged 400).

> **Qualifies `trackplan.md` item 2.** A flat global multiplier is the right instrument for a
> measured *bias* and the wrong one for *variance*. The 2.5× was fitted on Games 1–2,
> where we were uniformly the Field minimum. Game 5 shows zeros and overshoots in the
> same Case. **Stop tuning a global constant; fix the per-item verdict.**

**Revised root-cause ranking after Game 5:**

1. **Coverage gate accuracy** — false "uncovered" on covered items costs the Charge *and*
   invites the Limit failure. 2 of 17 items were truly uncovered; we behaved as if many
   more were.
2. **Limit is unbounded** — 99 % of costs from accepting; we paid 1,121.40 on an item
   whose `t` was under 773.50.
3. **Charge variance**, not Charge bias. Global multipliers cannot fix this.

## Cases 5–6: the generator reuses scenarios, and quantity is a separate fraud vector

**Scenario templates repeat.** Across the seven Cases readable so far:

| peril | Cases |
| --- | --- |
| storm surge, home electronics | **2, 4, 6** |
| escape of water | **1, 5** |
| theft (bicycle / from a car abroad) | 0, 3 |

Case 6 is a stripped-down re-run of Case 2 — same peril, same speaker + TV + technician,
"the claim has been kept simple". Its two Line Items map straight onto Case 2's brackets,
which we already inverted.

**This makes Price Memory the main channel, not a bonus.** `strat-flywheel` assumed the
dominant path was item-agnostic calibration, with exact-item memory worth "+4–10 %". With
templates recurring every few Games that is backwards: a settled `t` for "Speaker system
(surge damaged)" is close to a *direct read* on the next surge Case. Key the memory on
Line Item wording and on peril, and check every new Case against it before reasoning.

**Quantity inflation is a distinct fraud vector from price inflation.** The handout's
third test is "reasonably priced (total = quantity × unit price)", and the generator
attacks the *quantity* side too:

| Case | Line Item | quantity |
| --- | --- | --- |
| 6 | "Diagnostic surge-failure report and technician call-out" | **3 pcs** |
| 5 | "Removal, transport and disposal of the water-damaged wooden kitchen table" | **3 pcs** (one table) |
| 5 | "Service technician hours" for one leak detection | **14 hrs** |

A coverage gate that only asks "is this item covered?" passes all three. The gate has to
ask **"is this quantity plausible for this job?"** as well — one call-out is one call-out.
This is also where the gross-total rule bites hardest: an inflated quantity and a
per-unit submission are the same factor in opposite directions.

**Betterment keeps recurring**, now in three Cases: Case 1 (stone for tile, hardwood for
softwood), Case 5 (item 14, "premium solid-oak designer model, higher specification than
the original"). It is always self-labelled and it is always a *partial* haircut — covered
at the pre-loss standard, not zero.


## Game 6 — the opposite failure, and the fallback exposed

| Game | net | costs from accepting | mechanism |
| --- | ---: | ---: | --- |
| 4 | +3,520 | 60 % | — |
| 5 | −10,604 | **99 %** | `b` unbounded; paid 1,121.40 on an item worth < 773.50 |
| 6 | −3,940 | **0 %** | `b` ≈ 0; **4,975 in `1.5a` wrongful-rejection penalties** |

Two losing Games by opposite mechanisms. `b` is not mis-tuned, it is *outside the
posterior* and swinging across it.

**Worse: Game 6's Charge was the fallback constant.** We submitted `a = 45.00` on both
Line Items while item 1's true `t` was **`[765.00, 900.00)`**. The pricing pipeline did
not run. Observed `t` lower bounds across settled Games span 42–900 with a median around
150–230, so a fallback of 45 forfeits nearly everything — and since a Charge above `t`
costs nothing, the fallback belongs near the middle of that distribution, not at its floor.

**Uncovered items pay a realistic price, not a big one.** Game 3, all Line Items
uncovered: `error404 ai` charged 101.32 and `Non Deterministic` 100.00; each was accepted
by 2 of 16 and collected ~200 per item. Nobody chased the Cap. The buyers of an uncovered
item are exactly the teams that mis-classified it as covered, so their Limit is set for a
plausible price.
