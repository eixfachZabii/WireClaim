# Field report 01 — Games 1–2, and the one number we are getting wrong

Written Sat ~15:20 CEST, after Games 1 and 2 settled. We are **Bin busy**.

## Standing

| | G1 | G2 | total |
| --- | ---: | ---: | ---: |
| error404 ai | 33,436 | 4,803 | **38,239** |
| Codacabana | 13,441 | 10,355 | **23,797** |
| **Bin busy (us)** | **13,502** | **722** | **14,223** |
| AsianSuperNerds | −8,274 | 11,651 | 3,377 |
| *…7 teams still defaulting* | −8,274 | −5,144 | −13,418 |

3rd of 17. Two facts already visible: **the default is catastrophic and repeatable**
(13 teams at exactly −8,273.70 in G1; 7 still there in G2 — R7 and R10 confirmed on
real money), and **a team that wakes up scores immediately** (AsianSuperNerds went
−8,274 → +11,651 in one Game).

> ⚠️ **Correction, verified against Game 1 (`strat-flywheel` §0).** The tables below use
> `a = amount / 1.5`. **That rule is wrong** — the published `amount` is the Charge itself,
> so **every `t ≥` bound and every "our Charge" figure below is 1.5× too low.** The finding
> is not weakened, it is understated: corrected, Game 1 forfeits **1,361.36 per opponent =
> 21,782**, against the 13,502 we actually scored — **1.6× our entire score**, not 1.07×.
> Proof on our own rows: item 2 had 1 acceptance and 15 wrongful rejections and paid exactly
> `16 × 144.00 = 2,304.00`; under the `/1.5` reading it would have paid 3,384.00. Our income
> reconciles to `16 · A_fair + F = 19,704.00` on the nose. `README.md` R9 has been corrected.

## The finding: we are undercharging by 2–3×, and it is costing more than we earn

The leaderboard inverts (R9). For a rejected Transaction with `amount > 0`, the charge
was Fair and `a = amount / 1.5`. Take the largest Fair charge anyone made on a Line
Item and you get a hard **lower bound** on Fair Value. Against our own submissions:

**Game 1**

| item | `t` ≥ | our Charge | forfeited | ratio |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 81.96 | **0.00** | 81.96 | ∞ |
| 2 | 151.77 | 96.00 | 55.77 | 1.6× |
| 6 | 379.44 | 186.67 | 192.77 | 2.0× |
| 7 | 121.42 | 40.00 | 81.42 | 3.0× |
| 9 | 273.19 | 117.33 | 155.86 | 2.3× |
| 13 | 151.77 | 48.00 | 103.77 | 3.2× |
| 15 | 404.15 | 240.00 | 164.15 | 1.7× |
| 18 | 65.35 | **0.00** | 65.35 | ∞ |
| | | **per opponent** | **901.05** | |

**× 16 opponents = 14,417 of guaranteed, risk-free income forfeited in Game 1 —
more than the 13,502 we actually scored.** Game 2: 5,835 forfeited against +722 earned.

And these are *lower* bounds. True Fair Value is higher, so the real loss is larger.

This is not a modelling subtlety. By R1, every euro of Charge at or below Fair Value is
paid to us **with certainty, whether or not the reviewer accepts**. The gap between our
Charge and `t` is money nobody had to be fooled into giving us. We simply did not ask.

## Three separate errors, in priority order

**1. We submit `Charge = 0` on live Line Items.** G1 items 1, 3, 4, 5, 10, 12, 18 and
G2 items 2, 3, 5, 6, 7. On item 1 alone `t ≥ 81.96`. A zero Charge is never right: if
the item is covered we forfeit guaranteed income, and if it is *not* covered then
`t = 0` and charging is free anyway (R6c). **There is no case in this game where
`a = 0` is the correct answer.** This is the highest-value fix in the repo and it is
one line of code.

**2. Our Estimate is biased low by roughly 2–3×, not merely noisy.** Our Charge was the
*minimum of the entire field* on nearly every item where we charged at all. That is not
the R5b hedge — R5b says charge ≈ 0.7 × the median of a *calibrated* posterior. If the
posterior itself is low by 2.5×, multiplying by 0.7 compounds the error to ~0.28 × `t`.
**Fix the centre before touching the multiple.** R6b (shrinkage) is pulling the wrong
way if the prior is also low.

**3. Where we did overcharge, it cost exactly nothing.** G1 items 8, 16, 17 had
`t <` our Charge; every one was rejected and every one settled at 0. R5 confirmed with
real money: **a failed Overcharge is free.** Which makes error 1 worse — we were timid
in precisely the direction that has no downside.

## What I would change now

- **Floor the Charge.** Never submit 0. Even a crude per-item floor beats it.
- **Recalibrate the centre upward from settled Games**, not by guesswork — every Game
  publishes a fresh lower bound on `t` for every Line Item. Fit the multiplicative bias
  on `log(t_lower / our_estimate)`; two Games already give ~11 usable observations.
- **Use the Field's boldest Fair charge as a free prior.** After settlement it is a
  published lower bound on `t`. It cannot be read live, but across 100 Games it
  calibrates our estimator continuously — this is exactly the flywheel
  (`strat-flywheel/PLAN.md`), and it now has real labels to run on.
- **Leave the Limit alone for now.** R6 says it is flat in the bottom third and ~3×
  less sensitive than the Charge. Every hour spent on `b` this afternoon is an hour not
  spent on the 2–3× error in `a`.

## Method

Built by inverting the **public, settled** leaderboard. Confirmed allowed by the
organisers — we asked.
