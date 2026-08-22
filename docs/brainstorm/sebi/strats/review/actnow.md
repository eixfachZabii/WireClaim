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
leave it unbounded. `b` is *flat* across `Q₀.₀₅`–`Q₀.₃₃`, so this needs no tuning — just
a finite number. **Do not spend the afternoon on `b`**; it is ~3× less sensitive than the
Charge. Get it finite and move on.

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
