# Track plan — who does what

**Live as of Game 11, Sat 17:15. We are 17th of 17 at −228,363.** Leader is at +79,705.
Recent Games: −33,568, −80,074, −21,397, −60,506, −36,017. The bleeding is accelerating.

Markus runs the strategy on `main`. Everything in the block below is worth more than
everything under it.

---

## 🔴 QUICK WINS — strategy1 is flagging every Line Item as fraud

**Diagnosis (Games 10 and 11).** `b = 0` on **100 % of Line Items** in both Games, so we
reject everything and pay the `1.5a` penalty on every fair claim: **65,806** and **36,017**
in wrongful-rejection penalties. Game 10's item 3 had `t ≥ 7,225` and we charged 150.
Game 11 submitted `a = 0` *and* `b = 0` everywhere — the raw default.

**Root cause.** `fraud_detection._is_policy_quote` only checks that `exclusion_quote` is a
**≥ 12-character substring of `policy.txt`**. The policies are ~63,000 characters, so
`"the schedule"`, `"is not covered"`, `"the policyholder"` all pass. **The gate verifies
the quote exists, not that it proves an exclusion** — so almost every item is flagged.

Four fixes, in order of euros per line of code:

- [ ] **1. Cap fraud flags per Case.** If the detector flags more than ~35 % of Line Items,
      **discard the whole `FraudDecision`.** The measured base rate is ~12 % (2 of 17 in
      Game 5); a Case where everything is uncovered is possible (Game 3) but a detector
      that says so is far more likely to be broken. One `if` in `RunManager.apply_fraud`.
      *This alone would have prevented both losses above.* Owner: ______
- [ ] **2. Require the quote to look like an exclusion.** Raise `MIN_QUOTE_LENGTH` from 12
      to ~60, and require the normalised quote to contain one of `not covered`, `excluded`,
      `does not`, `no indemnity`, `is not insured`. Owner: ______
- [ ] **3. Never submit `a = 0`.** Game 11 went out as the pure default, which means the
      `standard_values` base layer never published — the Case failed to load, or the first
      `publish()` never ran. Guarantee one Submission per Game before any producer starts.
      Owner: ______
- [ ] **4. Log the flag count per Case** (`flagged/total`) so this is visible in one grep
      rather than needing a leaderboard inversion to find. Owner: ______

**Verify on the next settled Game:** flagged share < 35 %, wrongful-rejection penalties
below income, no Line Item at `a = 0`.

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
