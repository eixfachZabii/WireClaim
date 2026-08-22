# Track plan — four owners, checkable tasks

Live as of **Game 6** (Sat ~16:10). We are **5th, 3,199**, having been 3rd. Games 5 and 6
both lost, by *opposite* failures. ~94 Games and ~20 hours remain.

**Four owners. Matthi has P0.** Tick boxes as they land. Everything in P0 is worth more
than everything below it combined.

---

## Markus's design — agreed, with three gaps

```
case lands -> unzip -> OUR STRATEGY (act as if no fraud) --------\
                    -> AI fault detector (parallel) -------------> merge -> submit
```
Fraud items get `b = 0` but still get a realistic Charge. No fraud found ⇒ the strategy
runs unchanged.

**Agreed, and it fixes Game 5.** Three parts are right on the evidence:

- **"Act as if no fraud" as the baseline.** Matches the base rate — only 2 of 17 Line
  Items in Game 5 were genuinely uncovered. Our current gate over-flags, and a false
  "uncovered" costs twice.
- **Fraud ⇒ `b = 0`.** The single fix for Game 5's −10,604.
- **Still charge a realistic `t` on fraud items.** Confirmed by Game 3, where every item
  was uncovered: `error404 ai` charged 101.32, `Non Deterministic` 100.00, each accepted
  by 2 of 16 for ~200. This corrects my earlier "charge high toward the Cap floor" — the
  only buyers are teams that mis-classified the item as covered, and their Limit is set
  for a plausible price.

**Three gaps:**

1. **It does not fix Game 6.** That loss was `b` too *low* on **covered** items — 4,975 in
   wrongful-rejection penalties, 0 % of costs from accepting. The design says what `b` is
   when fraud is found and nothing about when it is not. **`b` on covered items must be
   `Q₁ᐟ₃(t̂)` — finite, and above zero.**
2. **Betterment is not binary.** Cases 1 and 5 carry "upgrade from pre-loss ceramic
   tiling", "premium solid-oak … higher specification than the original". These are
   *covered at a reduced basis*, not fraud and not full price. A fraud/no-fraud detector
   gets them wrong whichever way it answers. Needs a third verdict.
3. **Quantity inflation is invisible to it.** "Technician call-out" at 3 pcs, one kitchen
   table at 3 pcs, 14 hrs for a leak detection. The item is covered; the *quantity* is
   not. That should reduce `t̂`, not zero `b`.

**Also:** the detector must not race the submit. Send the strategy's answer early and let
the fraud-adjusted version overwrite it (`PUT` is last-write-wins) — never block the
Submission on the detector.

---

## P0 — stop the bleeding (tonight, before anything else) · **Matthi**

- [ ] **Coverage verdict drives the Limit.** `not covered ⇒ b = 0`. Owner: ______
- [ ] **Cap the Limit globally.** Never unbounded, never above `t̂`. Target the bottom
      third of the posterior. Owner: ______
- [ ] **Invert the "not covered ⇒ a = 0" rule.** Not covered ⇒ charge **high** (toward
      the Cap floor), because it is free (R6c). Owner: **Matthi**
- [ ] **Audit the coverage gate — it is emitting false "uncovered" on covered items.**
      Only 2 of 17 Game 5 Line Items were truly uncovered; we charged 0 on ones worth
      500+. This is now the #1 root cause. Owner: ______
- [ ] **Never submit `a = 0`** on any Line Item, for any reason. Owner: ______
- [ ] **Verify on the next settled Game**: paid-on-ACCEPT should fall below paid-on-REJECT.

## P1 — the measurement loop (needed to know if P0 worked)

- [ ] **Post-Settlement analyser.** One script, run after every Game: income; costs split
      accept vs reject; per-Line-Item `t` bracket vs our `a` and `b`; count of Charges we
      accepted above the bracket. *This is the dashboard* — it is what found the Game 5
      bug, and without it we are flying blind. Owner: ______
- [ ] **Append each Game's numbers to `field-findings.md`.** Owner: ______
- [ ] **Alarm**: if accept-share of costs > 60 %, or if we accept anything above `t̂`,
      shout in Discord. Owner: ______

## P2 — the estimate (the 2.5× undercharge is still unfixed)

- [ ] **Coverage/relatedness gate reads the policy scope clause first.** Case 3 was
      entirely uncovered; Case 1 has betterment items covered only at the pre-loss
      standard. Owner: ______
- [ ] **Exploit self-labelling Line Items** — the disqualifier is in the text
      ("no confirmed water contact", "upgrade from pre-loss ceramic tiling", "was already
      failing before the storm", "no diagnostic report provided"). Owner: ______
- [ ] **Few-shot from past Cases.** All played Cases stay decryptable; pair them with
      settled brackets. Owner: ______
- [ ] **Stop tuning the global multiplier.** After Game 5 the Charge is high-*variance*,
      not low-*bias*: zeros on covered items and 2× overshoots in the same Case. A global
      constant cannot fix that. Owner: ______

## P3 — resilience and the pitch (do not skip; half the prize)

- [ ] **Two-phase submit** — cheap at T+3 s, considered at T+50 s, merged per Line Item.
- [ ] **Never go dark.** 13 teams took exactly −8,273.70 in Game 1 for doing so.
- [ ] **Start the write-up now**, not Sunday morning. `strat-warroom/PLAN.md` has a timed
      5-minute script already written.
- [ ] **Freeze the pricing algorithm 08:00 Sunday.** Games 82–100 are worth less than a
      botched deploy costs.

---

## What "done" looks like

| signal | now | target |
| --- | --- | --- |
| share of costs from accepting | **99 %** | < 40 % |
| Line Items with `a = 0` | many | **0** |
| Limit on uncovered items | up to 1,121 | **0** |
| our Charge ÷ `t` on covered items | ~0.4 | 0.8–1.0 |
| Games missed | 1 (Game 2) | 0 |
