# Bin busy — diagnosis TL;DR (13 settled Games)

Full evidence: [`DIAGNOSIS.md`](DIAGNOSIS.md). **Net −274,350**
(income 75k vs. 310–354k for the top-3; costs 349k).

## Where the money goes

| Bucket | Amount | Cause |
|---|---:|---|
| Lawyer penalties (1.5a) | **−184k** (53 % of costs) | Limit ≈ 0 / dark Reviewer (Games 10–13; Game 10 alone −66k, one item with t ≥ 7,225) |
| Overcharge accepts (pure loss) | **−99k** | Limit effectively unbounded (Games 7–8; Game 8 alone −83.5k paid out) |
| Fair accepts | −67k | Normal cost — top-3 pay similar on 4–5× our income |

## Top 3 problems

1. **The Limit is never inside the posterior** — it flips between 0
   (→ lawyer fees) and ∞ (→ Overcharge accepts). 283k of the loss.
   Fix: `b = Q₁ᐟ₃(t̂)` (R4), bottom third is within ~2 % of optimal (R6).
2. **We don't show up.** Games 3, 7, 11, 12 had zero Issuer income
   (`a = 0`) — ~100k foregone. Fix: always submit (R7), cheap-then-smart
   two-phase (hard rule 8).
3. **Charges are uncalibrated.** Flat 100/150 placeholders (Game 9:
   a/t ≈ 254; Game 10: charged 150 against t ≥ 7,225); median a/t = 2.27
   vs. 0.85–1.0 for the top-3 → 1,722 rejections-at-0.
   Fix: `a ≈ 0.7 × t̂` (R5b), `p = 0` until measured (R5c).

## What's working

- Games 1, 2, 4 net-positive (+17.7k) — fair-zone Charges, sane Limit.
- Rejected Overcharges cost nothing (R5); accepted ones earned +19.3k.

**One sentence: close the Limit tap (b = Q₁ᐟ₃), always submit, charge
0.7·t̂ from the R9 Price Memory instead of placeholders.**
