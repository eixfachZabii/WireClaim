# Bin busy — diagnosis from all settled Games (1–13)

Generated from `data/analysis.json` + `data/raw/transactions_game_*.json`
(13 settled Games, 17 teams). All numbers reproducible with
`python3 case_analysis/diagnose.py`. Vocabulary per `docs/CONTEXT.md`:
Charge `a`, Limit `b`, Fair Value `t`.

**Headline: net −274,350 (income 75,116, costs 349,466) — last place territory,
while the top-3 (TakeTheMoneyAndRun +85,802, error404 ai +80,092,
OPUSMOPUS +68,857) all earn 310–354k income on similar cost bases.**
The problem is on *both* sides, but the cost side is dominated by the Limit
and the income side by not showing up and by uncalibrated Charges.

## Money decomposition per Game

Income split: fair Charges accepted / Overcharges accepted / fair-rejected
payouts (Reviewer paid `1.5a`, we still received `a`).
Costs split: fair accepts / Overcharge accepts (pure loss) / `1.5a` lawyer
penalties.

| Game | Income (fair/over/rej-fair) | Costs (fair-acc/over-acc/lawyer) | Net | Dominant loss bucket |
|---:|---|---|---:|---|
| 1 | 19,704 (2,140/696/16,868) | 6,202 (944/183/5,075) | **+13,502** | — |
| 2 | 5,088 (1,914/0/3,174) | 4,366 (601/0/3,765) | **+722** | — |
| 3 | 0 | 0 | 0 | no submission either side |
| 4 | 13,935 (3,570/5,775/4,590) | 10,415 (1,455/4,783/4,177) | **+3,520** | — |
| 5 | 9,075 (0/4,275/4,800) | 19,679 (8,257/11,193/230) | −10,604 | Overcharge accepts |
| 6 | 1,035 (540/315/180) | 4,975 (0/0/4,975) | −3,940 | lawyer fees |
| 7 | 0 | 33,568 (10,555/23,014/0) | −33,568 | Overcharge accepts + zero income |
| 8 | 3,429 (0/3,429/0) | 83,503 (37,936/45,567/0) | −80,074 | Limit wide open |
| 9 | 750 (0/750/0) | 22,147 (3,687/13,647/4,813) | −21,397 | Overcharge accepts |
| 10 | 5,300 (2,850/500/1,950) | 65,806 (0/0/65,806) | −60,506 | lawyer fees (b ≈ 0) |
| 11 | 0 | 36,017 (0/0/36,017) | −36,017 | lawyer fees (dark, R7) |
| 12 | 0 | 43,381 (0/0/43,381) | −43,381 | lawyer fees (dark, R7) |
| 13 | 16,800 (3,600/3,600/9,600) | 19,407 (3,362/193/15,852) | −2,607 | lawyer fees |
| **Σ** | **75,116** (14,614/19,340/41,162) | **349,466** (66,797/98,579/184,090) | **−274,350** | |

Cost buckets: **lawyer penalties 184k (53 %)**, **Overcharge accepts 99k
(28 %, pure loss)**, fair accepts 67k (19 %, the only normal cost — the top-3
pay 64–106k here on 4–5× our income).

## Top problems, prioritized

### P1 — The Limit swings between the two failure modes; 283k of the 274k net loss is Limit-side

The Limit is never *inside* the posterior (CLAUDE.md hard rule 4); it is
either 0 or effectively infinite.

- **b ≈ 0 → 184k of lawyer fees.** Game 10: our `b_hi` on every item was
  the smallest Charge seen (`b ∈ [0, 72]`, `[0, 3]`, …) — we rejected 25 fair
  Charges, 12 of them on item 3 whose Fair Value is **≥ 7,225** (`t_lo`
  from fair rejections), paying 61,302 on that single Line Item plus 4,504 on
  item 4 (`t ≥ 404`). Games 11–12 we were fully dark as Reviewer
  (income 0, every fair Charge rejected): 145 + 92 penalties = 79,398 —
  exactly the R7 money-fountain: a dark team does not score zero, it bleeds
  `1.5a` per fair Charge. Game 13 added 15,852 more (55 penalties).
- **b ≈ ∞ → 99k of Overcharge accepts.** Game 8: our Limit intervals are
  `b_lo` = the *largest* Charge seen with `b_hi = None` on 36 of 39 items
  (e.g. item 29: accepted up to 2,000 against `t ∈ [45, 130]`) — we accepted
  173 Overcharges and paid 83,503 in one Game. For comparison the same Game
  cost OPUSMOPUS 37,522 accepted + 12,615 lawyer, and it *earned* the money
  back as Issuer; we earned 3,429. Game 7 repeated the pattern (96 accepts,
  0 rejects, 23,014 paid on Overcharges); Games 5 and 9 add 11k + 14k.

Fix (proven, don't re-derive): R4 — `b = Q₁ᐟ₃` of the posterior on `t`,
never 0, never unbounded; R6 — anywhere in the bottom third is within ~2 %
of optimal, so a crude `b ≈ 0.6·t̂` beats both failure modes by construction.

### P2 — Income starvation: 75k vs. 310–354k for the top-3

Three causes, in order of size:

1. **Not submitting.** Games 3, 7, 11, 12 produced *zero* Issuer income
   (no nonzero Charge published). Four of 13 Games at `a = 0` — R7: "`a = 0`
   is never acceptable — any plausible number beats it". At the ~26k/Game the
   top-3 average, that alone is roughly −100k of foregone income.
2. **Uncalibrated flat Charges.** When we do charge, it is often a
   placeholder: Game 9 `a = 150` on items whose derived `t ≈ 0.59`
   (a/t ≈ 254); Game 10 `a = 150` on item 3 whose `t ≥ 7,225` — an
   undercharge that forfeits ~7k per accepting opponent while OPUSMOPUS
   took 119,680 income from that Game (we took 5,300). Same flat
   100/150 pattern in Game 8 (median a/t = 8.5 while all three top teams
   sat at 0.93–0.94).
3. **Overcharging into rejection.** Across all Games **1,722** of our issued
   rows were rejected at amount 0 (Overcharge, rejected — costs nothing per
   R5, but earns nothing). Overall median a/t = **2.27** vs. 0.85–1.0 for the
   top-3. Only 14.6k of our 75k income came from fair Charges accepted.
   R5b: the Charge belongs at **≈ 0.7 × t̂**, and R5c: without a measured
   acceptance curve, `p = 0` and the honest Charge strictly dominates.

### P3 — No per-Game learning loop

Every failure above persists across Games: b ≈ ∞ in Game 7 repeats in
Game 8; b ≈ 0 in Game 10 repeats in 11–13; a = 150 placeholders appear in
Games 9 and 10. R9 gives a labelled `t` bracket for every Line Item every
12.6 minutes; nothing in our published behavior shows the Price Memory
feeding back into either knob.

## What's working

- **Games 1, 2, 4 were net-positive (+17,744 combined)** — Charges in or
  near the fair zone (median a/t 0.63 / 0.36 / 2.35) and a Limit that
  wasn't fully open. Game 1's 16,868 of fair-rejected payouts is R1 in
  action: below `t` income is risk-free even when rejected.
- **Rejected Overcharges genuinely cost nothing** (R5): 1,722 rejections at
  amount 0, zero direct cost. The 19,340 of accepted-Overcharge income is
  a free-option payoff. The loss from overcharging is only the foregone
  fair-zone income, not a penalty.
- **The 0-Charge items in Game 8** (items 12/15/39, `t ∈ [0, 1)`): our
  `b ∈ [0, 1]` there was exactly right and cost nothing.

## Recommendations (grounded in proven results — cite, don't re-derive)

1. **Close the Limit tap first** (CLAUDE.md rule 4, R4, R6): set
   `b = Q₁ᐟ₃(t̂ posterior)` from the R9 Price Memory; hard-floor `b > 0`
   whenever any team's published fair Charge for a matching item is > 0, and
   hard-cap `b` at the known `t_hi`/Cap bound. This addresses 283k of loss.
2. **Always submit** (R7, hard rule 1 and 8): a cheap `a, b` at T+3 s from
   category medians, smart overwrite at T+50 s. Four missed Games ≈ 75k of
   foregone income; break-even uptime is 71 %.
3. **Charge at 0.7 × t̂, not flat placeholders** (R5b, R5c): median a/t must
   come down from 2.27 toward 0.7; keep `p = 0` (no Overcharge) until an
   acceptance curve measured from settled Games has real support — the top-3
   all sit at median a/t ≤ 1.0 and out-earn us 4×.
4. **Wire the R9 flywheel into both knobs each Game**: t brackets from
   settled Games are the prior (R6b shrinkage) and the calibration for the
   posterior width (R4b). Game 10 item 3 (`t ≥ 7,225`, we charged 150 and
   rejected everyone) is exactly the error a one-Game-old Price Memory
   prevents.
