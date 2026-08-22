# Field findings — what settled Games actually measured

Append a block per Game. Everything here is inverted from the public leaderboard
(confirmed allowed). Conclusions live in [`report.md`](report.md); the fixes in
[`actnow.md`](actnow.md).

**Inversion rules.** `amount` is what the **Issuer receives**, in *both* branches — so
`a = amount`, never `amount/1.5` (verified: accepted/rejected ratio exactly 1.0000 across
7 independent pairs in Game 1). Rejected with `amount > 0` ⇒ the Charge was Fair, so the
largest such Charge on a Line Item is a hard **lower bound** on Fair Value. Rejected with
`amount = 0` ⇒ Fraud Zone.

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

**This reverses the priority in `report.md` and `actnow.md`.** Those were written when we
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

> **Qualifies `actnow.md` item 2.** A flat global multiplier is the right instrument for a
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
