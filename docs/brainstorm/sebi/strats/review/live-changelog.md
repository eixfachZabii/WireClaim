# What was live for which Game

Every settled Game is an experiment, and its result only means something if we know which
code produced it. The runner pulls `main` and restarts every ~5 minutes, so a push made
between two Games changes the next one.

**Keep this file current. Add a row whenever you push something that changes behaviour.**
Without it, a leaderboard number is unattributable — and we have already been burnt once
by reading a regime boundary as a strategy result.

Game start times are `13:00:00Z + 757.575758 s x (id - 1)`.

| Games | live code | what changed |
| --- | --- | --- |
| 1–9 | pre-diagnosis | Flat placeholder Charges, Limit uncontrolled. Both directions of Limit failure appear here. |
| 10–12 | — | **Submitted nothing at all.** −139,904 across the three. Identical scores to the teams that never showed up. |
| 13–16 | blind floor + hardened quote gate | `blind_floor()` publishes before the Case loads; the policy-quote gate requires 60 chars and exclusion language; fraud allowance on the correct denominator. |
| 17 | still flooring coverage at 0.9 | `max(coverage_probability, 0.9)` meant the Limit could never collapse. Paid **70,736** on accepted claims; net −63,789. |
| 18 | `c147ce9` coverage floor removed | Accept rate falls 71 % → 32 %. Overshot the other way: **51,132** in wrongful-rejection penalties against 419 paid on accepts. Net −37,082. |
| 19–20 | `c147ce9` + fitted constants | First wins: **+34,408** and **+12,765**. G19 income 54,618 — the Charge side working for the first time. |
| **21 →** | **`c9634a8` — Strategy 2 live** | Markus restarted the runner at ~19:03. **From Game 21 (19:12:31 CEST) onwards the leaderboard measures Strategy 2** as of this commit. |

## What Strategy 2 was predicted to do, before Game 21 settled

Written down in advance so the comparison is honest. Replaying the cached model evidence
through `src/pricing/engine.py` and scoring with `scripts/replay_payoffs.py`, **Price Memory
excluded**:

- Over 15 Games where we actually scored **−324,706**, Strategy 2 replays at **+62,814**.
- The Limit and Charge levels are both at the optimum of their sweeps, so neither should
  be tuned further without new evidence.
- Known weakness: the heavy tail. Expensive Line Items are underpriced, and Game 20 is the
  counter-example where Strategy 2 would have *lost* us money (+5,473 replayed against
  +12,765 actual) by charging 1,281 for an item we charged 2,345 for.

**So the honest prediction for Games 21+ is: many small wins, with the risk concentrated in
Cases that contain one expensive Line Item.** If we see a large negative Game from here,
open the Case and check the most expensive item first.

## Games 21-23: what actually happened

Net **+17,099** over the three (+3,080, +14,840, −821), against a historical mean near
−16,000 a Game. But the shape is not what it looks like, and two of the three results are
not evidence that the pricing works.

### Games 21 and 22 were paid Overcharges, not good prices

| Game | item | our Charge | **true Fair Value** | outcome |
| --- | --- | ---: | --- | --- |
| 21 | laptop screen repair | 385 | `[0, 166)` | above `t`; 8 opponents accepted anyway → +3,080 |
| 22 | kitchen AC unit, 3 pcs | 1,855 | `[0, 246)` | above `t`; 8 opponents accepted anyway → **+14,840** |

Both Charges sat **above** the Fair Value, so no opponent owed us anything. We were paid
because their Limits were loose. That is the Field being generous, and README R9 says a
Field measurement does not survive a phase boundary — when the Field tightens or goes dark,
this income disappears entirely. **Do not read these two Games as the pricing working.**

Note also that Case 22's kitchen air-conditioning unit "close to the hob" is worth `< 246`,
while Case 7's identically-worded kitchen unit was `[0, 81)` and its living-room twin was
`[1233, 1756)`. Same wording, opposite values. Price Memory is keyed on wording, so this is
the case for keeping it a price *anchor* and never a coverage verdict.

### Game 23 lost because Strategy 2 never landed

Our submitted Limit was **35 on every Line Item** — that is `STANDARD_LIMIT`, not anything
the pricing engine produces. Strategy 1's Proposal stood. We therefore rejected 25 fair
Charges, some as low as **36.00** on an item worth `t ≥ 150`, and paid **5,548** in
wrongful-rejection penalties.

The cause is the magnitude-prompt bug that was live at the time (removed in `117b395`): with
the prompt asking for fields the pricing path then mishandled, Channel C produced nothing,
Case 23 had **zero** Price Memory hits, so `build_proposal` had no evidence at all and
returned `None`. **The deterministic fallback is only a fallback when it has something to
say** — on a 3-item Case with no dash-quantity items and no memory hits, it is empty, and
Strategy 2 goes silent without erroring.

### Even today's code only reaches −365 on Game 23, and the reason is the level error

Replaying Game 23 with the numbers today's Strategy 2 produces:

| item | our Charge | our Limit | true `t` | what goes wrong |
| --- | ---: | ---: | --- | --- |
| 1 | 244.82 | 244.82 | `[143, 165)` | Charge **1.6× above `t`** — income forfeited entirely |
| 2 | 420.28 | 420.28 | `[374, 396)` | Charge just above `t` — income forfeited |
| 3 | 79.19 | 79.19 | `[150, ∞)` | Charge **0.5× of `t`** — half the income given away, and the Limit rejects 4 fair Charges |

Net −365 against the −821 we took, while `a = t_lo, b = t_hi` scores **+6,577**. So the
Limit fix is worth ~450 here and **the level of the estimate is worth ~7,000 on this one
small Case.** That is the whole remaining lever, and it is the same shrink-to-the-middle
error measured across the corpus: ~4× too high under €50, ~10% too low above €1,000.

## How to attribute a Game

```bash
# what the Game actually did
python scripts/pull_transactions.py --games 21-21
# what the true Fair Values were
python scripts/invert_fair_values.py --games 21-21 --verify
# what Strategy 2 would do with today's code
PYTHONPATH=. pixi run python scripts/dump_evidence.py --games 21-21
```

Then record the outcome in [`field-findings.md`](field-findings.md) with the commit from
the table above, and update σ per CLAUDE.md rule 10.
