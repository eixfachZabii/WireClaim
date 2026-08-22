# Track plan — who does what

**Live as of Game 7, Sat 16:18. We are 12th at −30,369.** Leader `error404 ai` is at
+85,197. Games 5, 6 and 7 all lost: **−10,604, −3,940, −33,568.**

---

## 🔴 STOP THIS FIRST — we are submitting `a = 0, b = ∞`

Game 7: **income 0, costs 33,568, 100 % from accepting, zero rejections.**

| item | true `t` | our Charge | we paid up to |
| ---: | --- | ---: | ---: |
| 1 | `[1232, 1756)` | **0.00** | **3,500** |
| 2 | `< 683` | **0.00** | **2,000** |
| 4 | `< 323` | **0.00** | **765** |

This is **worse than going dark** — the default (`0, 0`) at least rejects everything.
"Act as if no fraud" has been implemented as "accept everything". It does not mean that.
It means *assume the item is covered, price it normally, and set the Limit to the bottom
third of that price*.

**Two hard clamps, in deterministic code, ignoring whatever any model says:**

```
b = clamp(b, 0, t̂)          # never above our own estimate. NEVER unbounded.
a = max(a, FALLBACK)        # never 0. FALLBACK ≈ 150, fitted from settled Games.
```

Ship these before anything else on this page. They are ~4 lines and they are worth more
than the rest of the tournament.

---

## Lukas — the fraud AI

Owns the fault detector.

- [ ] Detect uncovered Line Items from **quoted evidence only** — a policy exclusion
      quoted verbatim, or a disqualifier in the item's own wording ("no confirmed water
      contact", "was already failing before the storm", "no diagnostic report provided").
      **No quote, no verdict.**
- [ ] Emit a **third verdict for betterment**, not just fraud/clean. "Upgrade from
      pre-loss ceramic tiling", "premium solid-oak … higher specification than the
      original" are *covered at the pre-loss standard* — a haircut, not a zero.
- [ ] Emit a **quantity plausibility flag**. One call-out billed at 3 pcs, one kitchen
      table at 3 pcs, 14 hrs for a leak detection. Covered item, implausible quantity.
- [ ] **Default is CLEAN.** Only 2 of 17 Line Items in Game 5 were genuinely uncovered.
      Over-flagging costs twice: we forfeit the Charge and then fund the Field on the
      same item.
- [ ] Never block the Submission. Runs in parallel; a late verdict overwrites via `PUT`.

**Done when:** on Cases 1–7, the detector flags ≤ 20 % of Line Items and every flag
carries a quote.

## Sebi (+ Claude) — the strategy

Owns how verdicts become `a` and `b`.

- [ ] The two clamps above, in code.
- [ ] The decision table:

| verdict | Charge `a` | Limit `b` |
| --- | --- | --- |
| covered | `t̂` | `Q₁ᐟ₃(t̂)` — finite, above 0 |
| betterment | `t̂` at the pre-loss standard | `Q₁ᐟ₃` of that |
| implausible quantity | `t̂` for the plausible quantity | `Q₁ᐟ₃` of that |
| **not covered** | a **realistic** price, ~`t̂` as if covered | **0** |
| unsure | mid | low, never above `t̂` |

- [ ] **Uncovered ⇒ charge realistically, not high.** Game 3: `error404 ai` charged
      101.32 and `Non Deterministic` 100.00 on uncovered items; each was accepted by 2 of
      16 for ~200. The only buyers are teams that mis-classified the item as covered, so
      their Limit is set for a plausible price.
- [ ] Fallback Charge fitted from settled brackets (observed `t` spans 42–900, median
      ~150–230). Log every time it fires.

**Done when:** accept-share of costs < 40 %, no Line Item submitted at `a = 0`, no `b`
above `t̂`.

## Matthi & Markus — analysis

Own the measurement loop and the read on the Field.

- [ ] **Post-Settlement analyser**, run after every Game: income; costs split accept vs
      reject; per-item `t` bracket vs our `a` and `b`; count of Charges accepted above the
      bracket. This is what found Games 5, 6 and 7 — without it we are blind.
- [ ] **Pull several teams' rows, never only ours.** Our own Transactions bound `t` only
      where we were a counterparty; reading Game 5 from our rows alone made covered items
      look uncovered.
- [ ] **Alarm** into Discord if accept-share > 60 %, or any `b` exceeds `t̂`, or any
      Submission has `a = 0`.
- [ ] Append each Game's numbers to [`field-findings.md`](field-findings.md).
- [ ] **What the leaders do.** `error404 ai` is at +85,197 with the same Cases we get.
      Invert their Charges and Limits per item and write down where they differ from ours.
- [ ] Keep extracting new Cases each Game (CLAUDE.md rule 2) and note new trap patterns.

**Done when:** every settled Game has a row in `field-findings.md` within 10 minutes.

---

## Non-negotiables everyone needs to know

1. **Never submit `a = 0`.** Covered ⇒ we forfeit guaranteed income. Uncovered ⇒ charging
   is free. There is no case where 0 is right.
2. **Never submit `b` above `t̂`, and never unbounded.** Generosity costs `min(a,c)` with
   `c ≥ 4t`; strictness costs `0.5a`. ~8× asymmetry.
3. **Gross total for the whole Line Item.** Never net (÷1.19), never per-unit (÷quantity).
4. **Submit twice.** Cheap early, considered at ~T+50 s. `PUT` is last-write-wins.
5. **Most items are legitimate.** COVERED is the default.

## Scoreboard of our own health

| signal | Game 7 | target |
| --- | ---: | --- |
| costs from accepting | **100 %** | < 40 % |
| Line Items at `a = 0` | **6 of 6** | 0 |
| max `b` above `t̂` | **≥ 3,500** | 0 |
| net | **−33,568** | positive |
