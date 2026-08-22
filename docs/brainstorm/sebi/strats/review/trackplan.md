# Track plan — four owners, checkable tasks

Live as of Game 5 (Sat ~16:00). We are **5th, 7,139**, having been 3rd. Game 5 cost us
−10,604. ~95 Games and ~20 hours remain.

**Four owners. Matthi has P0.** Tick boxes as they land. Everything in P0 is worth
more than everything below it combined.

---

## The critique first — Markus's workflow

His shape is right and two details are wrong.

> *Neuer Case: Fallback instant prefillen → unzip → parallel Fault-Detection (KI) +
> Algo-`t` → Strategie. Wenn Fault: `b = 0` und `a` extra Strategie. 1-min-Limit
> vermeiden.*

- ✅ **Instant fallback prefill.** Correct, and it is the Fast Path. **But the fallback
  must be `b = 0`, not a large `b`.** A too-low Limit costs `0.5a`; a too-high one costs
  `min(a,c)` with `c ≥ 4t`. Game 5 is the proof: 99 % of our costs were acceptances.
- ✅ **Fault detection and `t` in parallel.** Correct — they are independent and the gate
  matters more than the number.
- ✅ **`b = 0` on fault.** This is *the* missing fix. It is worth more than every other
  item on this page.
- ❌ **"`a` extra Strategie" on fault — the direction matters.** If not covered then
  `t = 0`, the honest branch pays exactly zero, and a rejected Overcharge costs nothing.
  So `a` must go **up**, toward the Cap floor — not down, and never to 0. Game 3: two
  teams charged on an all-uncovered Case and took ~400 each while the rest of us scored 0.
- ❌ **"1-Minuten-Limit vermeiden" — not possible.** `GET /api/games/{id}/key` returns
  **403 before `start_time`**; I verified it. The window cannot be extended. What *can*
  be removed is everything around it: the archives are **already on disk** (all 100,
  committed), so the only network call at T0 is the key fetch. Then decrypt locally,
  fan out per Line Item, and use `PUT`'s last-write-wins to submit twice — cheap at
  T+3 s, considered at T+50 s. That buys the whole minute for thinking, which is the
  real goal.

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
