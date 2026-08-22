# Track plan — who does what

Refreshed Sat ~18:15 CEST, current through **Game 14**. Numbers in
[`report.md`](report.md); read that first if you only read one file.

**`Bin busy`, 16th of 17, −276,950.** One place above a team that has never submitted.
The leaders make **4.7× our income** on identical Cases. Markus runs the runner on `main`.

---

## The one thing everyone should know

**We lose on the Issuer side.** Forfeited income is **298,379** — more than both Limit
failures combined (162,252). Our median `a/t` is **1.06** and only **27 %** of our Charges
land in the fair zone; the leaders sit at `a/t ≈ 0.73–0.85` with 58–67 %.

Income is `a` whenever `a ≤ t`, collected from **every** opponent — a wrongful rejection
still owes it. One euro above `t` and it all disappears. That cliff is the whole game.

---

## Status of the four quick wins (all shipped)

- [x] **Blind floor** — a Submission goes out before the Case even loads. G10–12 submitted
      nothing and cost **139,904**.
- [x] **Quote gate hardened** — 60 characters plus exclusion language, now in one module
      (`src/policy_quote.py`) instead of two copies.
- [x] **Fraud allowance** — a share (35 %) with a floor of 2, on the *correct* denominator.
- [x] **Constants fitted** to the reconstructed `t`, not guessed. `standard_values` no
      longer scales by invoice quantity (it measurably hurt).

---

## Lukas — the fraud / coverage detector

The single most valuable verdict you can produce is **`t = 0` vs `t > 0`**: 76 of 192
settled Line Items are uncovered, and getting that one bit right sets `b = 0` (no
exposure) while we still Charge freely (R6c — an uncovered item's Charge is a free option).

- [ ] **Quoted evidence only.** No verbatim policy clause, no verdict. The gate is already
      in `src/policy_quote.py` — use it, don't reimplement it.
- [ ] **There is no safe prior.** Uncovered density ranges **0 %–67 % per Case**: Case 12
      has **zero** uncovered items, Case 10 has 4 of 6. A detector that always finds
      something to exclude is wrong on Case 12; one that defaults to clean is wrong on
      Case 10. Calibrate per Case, not globally.
- [ ] **Beware the anti-traps** — 5 Cases plant a line that *looks* excluded and is
      expressly covered. Case 8 POS 4: the robot vacuum is `t = 0`, but §7.1.7(i)
      indemnifies its inspection *"even where the property investigated turns out not to
      be indemnified"*. An exclusion ending *"the head of cost under X remains
      unaffected"* is a **pointer, not an exclusion**.
- [ ] **Betterment is not always a haircut.** Case 9 §7.1.10: where any element of a
      *combined position* is not indemnifiable, the whole position is zero. Mixed **grade**
      ⇒ haircut; mixed **scope in one undifferentiated line** ⇒ zero.
- [ ] **Quantity plausibility, carefully.** Real vector (6 Cases) but Case 8 POS 19 shows
      drying *stages* are legitimately separate items of cost. Flag, don't zero.
- [ ] Never block the Submission. Late verdicts overwrite via `PUT`.

**Done when:** on Cases 1–14 the detector's `t = 0` calls match the inverted brackets
(`scripts/invert_fair_values.py`) better than the 40 % base rate, and every flag carries a
quote. **You can grade yourself against ground truth — use it.**

## Sebi — the strategy (Strategy 2)

Owns how evidence becomes `a` and `b`. Strategy 1 is retired once this lands.

- [ ] **Hit σ < 0.35.** Simulated against real charges, `a = β·t̂` / `b = α·t̂` nets **+18**
      per transaction at σ = 0.25 and **−14** at σ = 0.5. Above σ ≈ 0.35 we lose money
      whatever the multipliers. A blind constant is σ ≈ 1.12. **Replay against the 148
      bounded Line Items and show the number before shipping.**
- [ ] Then `β ≈ 0.7` and `α ≈ 0.5–0.7`, with **`b < a`** and `b` never above `t̂`.
- [ ] **Take the free signals first.** `– –` quantity ⇒ `t = 0` (**20/20** validated).
      Index = invoice POS, gaps included (Case 11 has no POS 12). `grep "^PART 11"` on
      Case 10 collapses 823 lines to the operative two dozen.
- [ ] **Fix the latency.** Strategy 1 exceeds the 60 s window, so nothing lands. Publish
      **per Line Item as each estimate arrives** rather than one Proposal at the end — the
      coordinator already supports it.

## Matthi & Markus — measurement and the read on the Field

- [x] `scripts/pull_transactions.py` — pages to the end, raises on a short read.
- [x] `scripts/invert_fair_values.py` — exact `t` brackets, `--verify` reproduces all 238
      published nets.
- [ ] **Run it after every Game** and append a row to [`field-findings.md`](field-findings.md):
      per-item `t` bracket vs our `a` and `b`, income, accept-vs-reject split, and **σ**.
- [ ] **Alarm** if any `b > t̂`, any `a = 0`, accept-share of costs > 60 %, or σ > 0.35.
- [ ] **Price Memory.** The trade roster repeats verbatim — `7 U-Bend Boulevard,
      Pipeville` is the plumber in Cases 1, 5, 8, 11, 13 — and Cases 11 and 13 share a
      parts list almost line for line. Key settled brackets on item wording + peril; a
      settled bracket is a *direct read*, not an estimate.
- [ ] Keep extracting Cases every Game (CLAUDE.md rule 2).

---

## Non-negotiables

1. **Never `a = 0`.** Covered ⇒ forfeited guaranteed income. Uncovered ⇒ charging is free.
2. **Never `b` above `t̂`, never unbounded.** G8 alone: 45,567 paid above `t`.
3. **Never absent.** The blind floor is the cheapest 139,904 we will ever save.
4. **Gross total for the whole Line Item.** Never net (÷1.19), never per-unit.
5. **Page to the end of every API list.** A 100-row page made a 39-item Case look like 4.

## Health scoreboard

| signal | G8 | G12 | G13 | G14 | target |
| --- | ---: | ---: | ---: | ---: | --- |
| net | −80,074 | −43,381 | −2,607 | −2,599 | positive |
| items at `a = 0` | some | **all** | some | some | 0 |
| accept share | **100 %** | 13 % | 65 % | 72 % | ≈ 60 % |
| σ of `t̂` | — | — | — | — | **< 0.35** |
