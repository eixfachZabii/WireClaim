# Where we actually stand — Games 1–14, measured

Rewritten Sat ~18:15 CEST. Everything here is derived from settled Transactions or from a
Case we opened. Nothing is inferred from intuition, and the places where the previous
version of this file was wrong are marked rather than deleted.

**We are `Bin busy`, 16th of 17, at −276,950.** 86 Games remain.

| | net | mechanism |
| --- | ---: | --- |
| TakeTheMoneyAndRun | **+86,394** | income 355,996 — they win on the Issuer side |
| error404 ai | +81,284 | income 354,394 |
| **Bin busy** | **−276,950** | income **75,566** |
| makalu | −290,624 | income **0** — never submitted anything |

We are one place above a team that has never submitted. That is the whole story: **the
leaders earn 4.7× our income on the identical Cases.** We are not losing because we pay
too much. We are losing because we do not get paid.

---

## 1. The measurement that unlocked everything

The secret Fair Value `t` is **exactly recoverable** from the public leaderboard. No
model, no LLM, no estimation. The payoff table leaks it:

| Transaction row | what it means | what it proves |
| --- | --- | --- |
| `accepted`, `amount = x` | both sides move `x` | `x = min(a, c)` — nothing about `t` |
| `rejected`, **`amount = x > 0`** | **wrongful** rejection: reviewer pays `1.5x`, issuer still gets `x` | `x` **is** the Charge **and `a ≤ t`** |
| `rejected`, `amount = 0` | rightful rejection, nothing flows | **`a > t`** |

So per Line Item, `t ≥ max{a wrongfully rejected}` and `t < min{a rightfully rejected}`.

**This is checkable, and it checks out.** Summing `+amount` as issuer and
`−(amount if accepted else 1.5·amount)` as reviewer reproduces **all 238 published
team-Game nets to the cent**. Run `python scripts/invert_fair_values.py --verify`.

> ### The trap that cost us two hours: `/transactions` paginates at 100 rows
> Page one of a 544-row Game is 32 rows for each of the first three Line Items and 4 of
> the fourth — which reads exactly like a 4-item Case. On that false reading we set
> `BLIND_LINE_ITEMS = 8` and justified the fraud allowance on a 2–4 item denominator.
> Games actually carry **2 to 39 Line Items, median 15**. `scripts/pull_transactions.py`
> pages to the end and raises on a short read. Full evidence in
> [`t-inversion.md`](t-inversion.md).

**The settled `t` distribution** (148 items with both bounds, bracket midpoints):
median **≈ 59**, p25 ≈ 19, p75 ≈ 127, p90 ≈ 365, max **7,225**. Also: **76 of 192 items
have `t = 0`.** `t` is small, heavy-tailed, and very often zero.

---

## 2. Where the 276,950 went

| mechanism | cost | kind |
| --- | ---: | --- |
| **`a` too low → forfeited income** | **298,379** | opportunity |
| `b` too high → overpaying | 100,664 | cash |
| `b` too low → the `0.5a` wrongful-rejection surcharge | 61,588 | cash |
| `a` too high → overcharges rejected | 23,194 | opportunity |

Worst Games: **G8 −80,074** (accepted 100 %; 45,567 of 83,503 paid was above `t`),
**G10 −60,506**, **G12 −43,381**, **G11 −36,017** (the last three: *submitted nothing*,
so `b = 0` converted every fair charge into `1.5a` — 139,904 across the three),
**G7 −33,568**, **G9 −21,397**, **G5 −10,604**. Only G1, G2, G4 were positive.

**Our positioning, over the 78 fully-bounded items with `t > 0`:** median **`a/t = 1.06`**,
median **`b/t = 1.16`**, and only **27 %** of our Charges landed in the fair zone — worst
in the field apart from the team that submits nothing. We charge just above `t`, so we
collect nothing, *and* we accept just above `t`, so the field farms us.

### What the winners do

| team | `a/t` median | `b/t` median | fair-zone % | accept rate |
| --- | ---: | ---: | ---: | ---: |
| TakeTheMoneyAndRun | **0.73** | **0.58** | 67 % | 65 % |
| error404 ai | 0.85 | 0.81 | 58 % | 63 % |
| Non Deterministic | 0.67 | 0.48 | 59 % | 57 % |
| **Bin busy** | **1.06** | **1.16** | **27 %** | 69 % |
| Oasis (−114,959) | 0.79 | **1.37** | 41 % | 72 % |

The winning shape is narrow and consistent: **`a ≈ 0.7–0.85 t`, `b ≈ 0.5–0.8 t`, and
`b < a`.** Our accept *rate* (69 %) is close to theirs (63–65 %) — the rate was never the
problem. The *level* is. Oasis is the control group for generosity; makalu for absence.

---

## 3. The number that decides whether Strategy 2 is worth running

Simulating `a = β·t̂` and `b = α·t̂` where `t̂ = t·lognormal(σ)`, against the real charges:

| σ (our estimate error) | best `β` | E[income] | best `α` | E[cost] | **net per transaction** |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.25 | 0.7 | 105 | 0.7 | 87 | **+18** |
| 0.5 | 0.6 | 78 | 0.5 | 92 | **−14** |
| 0.75 | 0.5 | 63 | 0.33 | 96 | **−33** |

**Break-even is around σ ≈ 0.35.** Above that we lose money no matter how we tune the
multipliers; below it the multipliers barely matter. A perfect per-item Limit costs 65.0
per transaction against 97.5 for rejecting everything and 195.7 for accepting everything
— so the entire prize is estimate *accuracy*, and no constant recovers any of it.

This is the acceptance test for Strategy 2, and it is measurable before we ship:
**replay it against the 148 bounded Line Items and show σ < 0.35.** For reference, a blind
constant scores σ ≈ 1.12. R6's "bottom third" (`α ≈ 0.33`) is only optimal at σ ≈ 0.75 —
i.e. it is a confession of a bad estimate, not a target.

---

## 4. Deterministic signals — free accuracy, no model

These are the cheapest wins available and none needs a token.

1. **`– –` in the quantity/unit columns means `t = 0`.** Validated: **20 of 20** such
   Line Items across 6 Cases have `t = 0`, 17 with a tight upper bound under 40, against
   a 33 % base rate for normal items. Our parser currently *strips* the dashes and sets
   `quantity = 1.0`, throwing the signal away. → `b = 0`, and Charge freely (R6c).
2. **The submission index is the invoice POS number, gaps included.** Case 11's invoice
   has no POS 12, and the settled Game has indices 1–11 and 13–23. Never renumber by row
   ordinal.
3. **Invoice quantity does not predict price.** `corr(log quantity, log Charge) = +0.12`;
   scaling a constant by quantity raised log error from 1.12 to 1.32. Eight grub screws
   are not eight technician hours. `standard_values` no longer scales.
4. **Case 10 ships an answer key.** `PART 11 – OPERATIVE PROVISIONS FOR THIS CLAIM`
   enumerates the 24 clauses that decide every line. `grep "^PART 11"` collapses an
   823-line policy to two dozen paragraphs at zero cost.

---

## 5. Corrections to the previous version of this file

| It said | Measured reality |
| --- | --- |
| "We charge **~2.5× too little**" (Games 1–3) | Over all 14 Games our median `a/t` is **1.06** — we charge *above* `t`. True early, false now; the flat 150 fallback overshoots a median `t` of 59. |
| "Field acceptance is 5.96 %, the Overcharge is worthless" | Field accept rate is **63–69 %**. The leaders' `a/t` p75 is **above 1** — they *do* overcharge on roughly a third of items and get paid. Not settled; do not act on it without measuring `p(a)` (R5c). |
| "`b` is flat in the bottom third; not what is costing us" | Half true. Limit errors cost **162,252** (100,664 + 61,588). But it is second: forfeited income is **298,379**. |
| "Uptime is the dominant risk … we are submitting" | Then false, now true: G10–12 submitted nothing and cost **139,904**. |
| Base rate of uncovered items ~12 % ("2 of 17 in Game 5") | **40 %** of all items (76/192) have `t = 0`, ranging **0 %–67 % per Case**. Case 12 has zero uncovered items; Case 10 has 4 of 6. **There is no safe prior.** |

---

## 6. What this implies for the strategy

Ranked by measured euros, not by elegance.

1. **Get income up.** 298,379 of forfeited income dwarfs everything. That means `a` must
   sit *below* `t`, at `β ≈ 0.7`, on every item we believe is covered — and `t̂` must stop
   overshooting on cheap items.
2. **Never be absent.** 139,904 for three Games. The blind floor is in; keep it.
3. **Drive `b` from the same posterior at `α ≈ 0.5–0.7`, never above `t̂`.** Both of our
   Limit failures were the *level*, in opposite directions, in adjacent Games.
4. **Take the free deterministic signals** (§4) before spending a token.
5. **Measure σ every Game.** It is the one number that says whether the pipeline is worth
   running, and it is computable from settled data within minutes of a Game closing.

Evidence: [`t-inversion.md`](t-inversion.md) (full brackets, per-team accounting,
validation) · [`case-findings.md`](case-findings.md) (all 14 Cases read, 22 adversarial
vectors, recurring-template keys) · [`field-findings.md`](field-findings.md) (running log)
· [`trackplan.md`](trackplan.md) (who does what).
