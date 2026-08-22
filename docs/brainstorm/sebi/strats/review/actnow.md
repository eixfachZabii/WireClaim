# Act now — current through Game 6

**Black-box findings.** Every number is inverted from settled Games — nobody needs to read
the runner to act on these, and they hold whatever generates the numbers. Ordered by
euros-per-minute. Supersedes the Games 1–3 version; where the data has since reversed a
recommendation, that is marked ⚠️ rather than deleted.

## Where we are

| Game | 1 | 2 | 3 | 4 | 5 | 6 | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| net | 13,502 | 722 | 0 | 3,520 | **−10,604** | **−3,940** | **3,199** |
| costs from *accepting* | — | — | — | 60 % | **99 %** | **0 %** | |

5th of 17. Two losing Games in a row, by **opposite** failures.

---

## 1. The Limit is oscillating between both wrong answers — put it inside the posterior

This is the whole story of Games 5 and 6.

- **Game 5:** `b` effectively unbounded. We accepted 246 of 272 Transactions, paid
  **1,121.40** on a Line Item whose `t` was under 773.50. 99 % of costs from accepting.
  Net −10,604.
- **Game 6:** `b` collapsed to ~0. 21 wrongful rejections, 0 % of costs from accepting,
  **4,975 paid in `1.5a` penalties** on claims that were fair. Net −3,940.

Neither is a tuning error; both are `b` sitting *outside* the posterior. Being generous
costs `min(a,c)` with `c ≥ 4t`; being strict costs `0.5a`. Generosity is ~8× worse, so the
target is the **bottom third of the posterior — finite, and above zero unless the item is
genuinely uncovered**.

**Change.** `b = Q₁ᐟ₃(t̂)`, clamped: never `∞`, never `0` on a covered item. If there is no
posterior, `b` = the fallback estimate, not a constant and not zero.

## 2. The fallback fires too often, and it is an order of magnitude too low

Game 6 submitted `a = 45.00` on **both** Line Items. Item 1's true `t` was
**`[765.00, 900.00)`**. That is not a biased estimate — that is the pricing pipeline not
running and a constant going out instead.

Observed `t` lower bounds so far run 42–900, median roughly **150–230**. A fallback of 45
forfeits nearly everything, and since a Charge above `t` costs *nothing*, the fallback
should sit near the middle of the observed distribution, not at its floor.

**Change.** (a) Log every time the fallback fires — if it is firing on normal Games, that
is the bug. (b) Raise the constant to ~150 and fit it from settled brackets. (c) Scale it
by quantity and unit where the invoice gives them.

## 3. Default to COVERED; only a quoted exclusion overturns it

**Only 2 of 17 Line Items in Game 5 were genuinely uncovered.** We charged 0 on several
that were worth hundreds — item 3 sits in `[497.94, 773.50)`.

An invoice is not a fraud attempt. It is mostly honest work with a *minority* of traps, and
the traps announce themselves in the text: "no confirmed water contact", "upgrade from
pre-loss ceramic tiling", "was already failing before the storm", "no diagnostic report
provided". Whole-Case exclusions announce themselves in the policy's scope clause — Case 3's
buildings-only wording versus a suitcase stolen from a car.

**Change.** COVERED is the default. Require positive textual evidence to overturn it — a
quoted policy exclusion or a disqualifier in the item's own wording. **No quote, no
"uncovered" verdict.** A false "uncovered" costs twice: we forfeit the Charge *and* we then
fund the Field's Charges on the same item.

## 4. One verdict, two outputs, opposite directions

| verdict | Charge `a` | Limit `b` |
| --- | --- | --- |
| covered | at `t̂` | bottom third of the posterior |
| **not covered** | **high** — free option toward the Cap floor (R6c) | **0** |
| unsure | mid | low; never above `t̂` |

Game 5 did the opposite on both axes at once: `a = 0` *and* unbounded `b`, same items.

## 5. Check the Price Memory before reasoning — scenarios repeat

Three of seven readable Cases are storm-surge electronics (2, 4, 6); two are escape of
water (1, 5). Case 6 re-runs Case 2 with fewer Line Items. So the first question on a new
Case is not "what is this worth" but **"have we settled this item before?"**, keyed on Line
Item wording plus peril. A settled bracket is a near-direct read, and it is free.

## 6. Judge the quantity, not just the coverage

The generator inflates quantities as well as prices: "technician call-out" at **3 pcs**,
"removal of the water-damaged kitchen table" at **3 pcs** for one table, **14 hrs** for a
leak detection. A gate that only asks "is this covered?" passes all three. Ask "is this
quantity plausible for this job?" too. We submit the **gross total for the whole Line
Item**, so an inflated quantity and a per-unit submission are the same factor pointing
opposite ways.

## 7. Never submit `charge_price = 0`

If covered, a Charge at or below `t` is paid **with certainty**, accepted or not (R1). If
not covered, `t = 0`, the honest branch pays zero anyway, and a rejected Overcharge costs
**nothing** (R5). Charging is weakly dominant in both branches. Game 3 is the proof: both
Line Items uncovered, nearly the whole Field scored 0, and the two teams that charged
anyway took ~400 each.

## 8. Keep the Overcharge off

Field acceptance measured at **5.96 %** against a ~25 % break-even. Our own Game 1
Overcharges were all rejected and all settled at exactly 0 — confirming a failed Overcharge
is free, and also that nobody is paying for them. Charge up to `t̂` and stop. Revisit only if
a settled Game shows acceptance above ~20 %.

---

## ⚠️ Superseded

**"Multiply the Charge by ~2.5×."** Correct for Games 1–2, where we were uniformly the
Field minimum and the error was a clean *bias*. It shipped for Game 5 and the error is now
*variance*: zeros on covered items and 2× overshoots in the same Case (item 1 `t < 875`,
charged 875; item 2 `t < 199`, charged 450; item 5 `t < 131`, charged 600). **No global
constant fixes variance.** Per-item verdict quality is the lever.

**"Do not spend the afternoon on `b`."** Written when we were losing to timidity as Issuer.
R6's "the Limit is flat in the bottom third" holds only once `b` is *inside* the posterior.
Ours has been outside it in both directions. See §1.

---

## Method note — do not repeat this mistake

**Bracket `t` from several teams' rows, never only ours.** Our own Transactions bound `t`
only where we were a counterparty. Reading Game 5 from our rows alone made covered items
look uncovered; pulling five teams' rows (2,380 Transactions) reversed the diagnosis. Any
analyser reading only our own rows will produce confidently wrong brackets.

## Sanity checks before shipping

- **Gross total, whole Line Item.** Never net (÷1.19), never per-unit (÷quantity). On
  Game 1 a per-unit slip costs 30,400–38,100 versus 6,960 for VAT — the quantity column is
  **5.5× more dangerous**.
- **Submit for every index.** Omitted items default to `0/0` and still participate.
- **Submit late, and twice.** `PUT` is last-write-wins: cheap early, considered at ~T+50 s.
- **After each Settlement, re-run the analyser** and watch two numbers: accept-share of
  costs (target < 40 %) and `t/a` on covered items (target 0.8–1.0).
