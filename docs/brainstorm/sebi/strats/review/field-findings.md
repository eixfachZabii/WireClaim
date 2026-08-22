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
