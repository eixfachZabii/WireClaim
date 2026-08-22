# Act now — four changes, measured against Games 1–3

**These are black-box findings.** Every number is inverted from what our submissions
*did* on settled Games — nobody needs to read the runner to act on them, and they hold
whatever is generating the numbers. Ordered by
euros-per-minute-of-work. Together they are worth roughly **20,000 per Game** against
what we are currently doing, and none of them needs a better price model.

---

## 1. Never submit `charge_price = 0`. Ever.

**Evidence.** Game 1: we charged 0 on **8 of 18** Line Items. Two of them were live —
item 1 (`t ≥ 122.94`) and item 18 (`t ≥ 98.02`). Game 2: 0 on **5 of 7**. Game 3: 0 on
**both**.

**Why it is never right.** If the item is covered, a Charge at or below `t` is paid to us
*with certainty*, accepted or not (R1) — a zero forfeits it outright. If the item is
**not** covered then `t = 0`, the honest branch pays exactly zero anyway, and a rejected
Overcharge costs **nothing** (R5). So charging is weakly dominant in both branches.

**Game 3 is the proof, in money.** Both Line Items were uncovered. Nearly every team
scored exactly **0**. `error404 ai` charged anyway and made **+403**; `Non Deterministic`
made **+400**. We made 0.

**Change.** Floor every Line Item. If the pipeline has no opinion, submit *something*.
On items we believe are uncovered, charge toward the Cap floor rather than zero — it is
a free lottery ticket, every Game, including overnight.

---

## 2. Multiply the Charge by ~2.5×

**Evidence.** Our Charge was the minimum of the entire Field on nearly every item.
Measured `t_lower / our_charge`, where `t_lower` is a *hard lower bound*:

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

Median **2.5×**, and the true `t` is *higher* than every bound above.

**Do not apply R5b's 0.7 multiple on top of this yet.** R5b hedges uncertainty around a
*calibrated* centre. Ours is biased low by 2.5×, so `0.7 × biased` compounds to ~0.28×`t`
— which is what we have been doing. **Fix the centre first, then re-introduce the hedge.**

**Change.** Apply a global multiplier of **2.2–2.5** to the Charge immediately, then let
the flywheel replace the constant with a fitted one. Keep it a single named constant so
it is one edit to revise.

---

## 3. Make the Limit finite on every item

**Evidence.** Inverting our own reviewer behaviour, several Game 1 items show
`b ∈ [x, ∞)` — we never rejected anything, so our Limit is above every Charge the Field
made. Items 8, 14, 16 and 17 all show this, and on items 8, 16 and 17 the Fair Value was
*below* the Charges we accepted.

This is the expensive direction: a wrongful acceptance costs `min(a,c)` with `c ≥ 4t`,
against `0.5a` for a wrongful rejection — **~8× worse**.

**Change.** Cap the Limit at roughly the bottom third of the posterior (R4/R6), and never
leave it unbounded.

> **Updated after Game 5 — this is now the #1 item, not the #3.** We lost **−10,604** in
> Game 5 and **99 % of the cost was acceptances** (19,450 across 246 accepted
> Transactions, versus 230 on rejections). The earlier line here — "do not spend the
> afternoon on `b`" — was written when we were losing to timidity as Issuer. It is wrong
> now. R6's "the Limit is flat" holds only once `b` is *inside* the posterior; ours is
> outside it. **Coverage verdict must drive `b`: not covered ⇒ `b = 0`.**
> See [`field-findings.md`](field-findings.md) and [`trackplan.md`](trackplan.md).

---

## 4. Turn the Overcharge off

**Evidence.** Field acceptance measured at **5.96 %** in Game 1 (31.8 % among the four
awake teams), against a break-even of ~25 %. Our own Game 1 Overcharges — items 8, 16,
17 — were all rejected and all settled at exactly 0.

**Change.** Keep R5c's `p = 0` latch shut. Charge *up to* our estimate of `t` and stop.
The Overcharge is not being declined on principle — the Field has priced it at 6 % and we
measured it. Revisit only if a settled Game shows acceptance above ~20 %, and never carry
a `p` estimate across a phase boundary.

---

## Sanity checks before shipping

- **Gross total, whole Line Item.** Never net (÷1.19), never per-unit (÷quantity). On
  Game 1 a per-unit slip costs 30,400–38,100 versus 6,960 for a VAT slip — **the quantity
  column is 5.5× more dangerous than VAT.**
- **Submit for every index**, not just the ones we have an opinion on. Omitted items
  default to `0/0` and still participate — the handbook says so explicitly.
- **Submit late in the window, not early.** `PUT` is last-write-wins, so a cheap early
  submission plus a considered overwrite is free insurance.
- **Re-run the inversion after each Settlement** and watch the `t/a` ratio move toward
  1.0. If it does not, the multiplier is wrong — not the model.


---

# Learned from Game 5 (net −10,604, 3rd → 5th)

`actnow` items 1–4 went in for Game 5. Here is what the data says next, in order.

## 5. Most Line Items are legitimate — default to COVERED

**Only 2 of 17 Line Items in Game 5 were genuinely uncovered.** The rest were real work
by a real tradesperson, and we charged **0** on several of them — item 3 sits in
`[497.94, 773.50)` and we asked for nothing.

An invoice is not a fraud attempt. It is mostly honest work with a *minority* of traps,
and the traps announce themselves in the text (see `field-findings.md`): "no confirmed
water contact", "upgrade from pre-loss ceramic tiling", "was already failing before the
storm", "no diagnostic report provided". Whole-Case exclusions announce themselves too, in
the policy's scope clause — Case 3's buildings-only policy versus a suitcase stolen from a
car.

**Change.** Make COVERED the default and require *positive textual evidence* to overturn
it: a quoted policy exclusion, or a disqualifier in the Line Item's own wording. No quote,
no "uncovered" verdict. A false "uncovered" is the most expensive mistake in the pipeline
because it costs twice — we forfeit the Charge *and* we then fund the Field's Charges on
the same item.

## 6. One verdict, two outputs, opposite directions

The coverage verdict must drive both numbers, and it pushes them apart:

| verdict | Charge `a` | Limit `b` |
| --- | --- | --- |
| covered | at `t̂` | bottom third of the posterior |
| **not covered** | **high** — free option toward the Cap floor (R6c) | **0** |
| unsure | mid | low; never above `t̂` |

Game 5 did the opposite of this on both axes simultaneously: `a = 0` *and* an unbounded
`b` on the same Line Items.

## 7. Stop tuning the global multiplier — the problem is variance now

Item 2's 2.5× was fitted on Games 1–2, where we were uniformly the Field minimum. After it
shipped, Game 5 shows **zeros and overshoots in the same Case**: item 1 `t < 875` (we
charged 875), item 2 `t < 199` (charged 450), item 5 `t < 131` (charged 600) — alongside
the zeros above. That is not bias any more, it is variance, and no global constant fixes
it. Per-item verdict quality is the only lever left.

## 8. Bracket `t` from several teams' rows, never just ours

Our own Transaction rows only bound `t` where *we* were a counterparty. That is exactly
what made an earlier read of Game 5 conclude those items were uncovered — they were not.
Pulling five teams' rows (2,380 Transactions) gave two-sided brackets and reversed the
diagnosis. **Any analyser that reads only our own rows will produce confidently wrong
brackets.**
