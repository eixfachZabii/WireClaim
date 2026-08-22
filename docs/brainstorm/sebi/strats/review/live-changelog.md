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
through `src/pricing.py` and scoring with `scripts/replay_payoffs.py`, **Price Memory
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
