---
name: learn-from-runs
description: Turn settled Games into one validated improvement to Strategy 2. Use at the start of any WireClaim session, whenever the user says a Game has settled or shares runner output, or before changing any pricing constant. Keywords: game settled, run finished, why did we lose, analyse the run, tune strategy2, leaderboard dropped.
---

# Learn from settled Games

A settled Game is the only honest feedback this project has. This is the loop that converts
one into a change, and the guardrails exist because every one of them was learned by getting
it wrong and paying for it.

## Run this first, always

```bash
cd "<repo root>"
set -a && . .env && set +a
pixi run cases                                    # unzip newly released Cases
PYTHONPATH=. pixi run python scripts/learn_from_game.py       # every Game not yet analysed
```

`learn_from_game.py` joins the **decision log** written at submission time
(`var/decisions/game_NNN.json`) against the **reconstructed Fair Value**, so it names the
stage that was wrong rather than the amount that was lost. Read its digest in full.

**If it says "No decision log for this Game", stop and check whether Strategy 2 actually
landed before interpreting anything else.** In Games 21–24 it had not: the submitted Limit
was 35 on every Line Item, which is `STANDARD_LIMIT`, and an hour went into inferring what
one log line now states.

## The five stages, in the order money is lost

Attribute to a stage. "We lost 5,548" is not actionable; "coverage on item 3 came back 0.25
and the item was worth at least 150" is.

1. **Did Strategy 2 land at all?** No decision log, or a submitted Limit of exactly 35 or
   a Charge of exactly 300, means a lower layer won. Fix that before anything else.
2. **Coverage.** `p_covered <= 2/3` collapses the Limit to zero. Wrong in either direction
   is expensive: too low forfeits income *and* invites `1.5a` penalties; too high pays for
   items worth nothing.
3. **Level.** Compare the estimate's median against the bracket. Note the direction per item;
   do not aggregate yet (see the conditioning trap below).
4. **Charge.** Above `t` earns nothing at all from anybody. Below `t` forfeits the difference
   from *every* opponent, because a wrongfully rejected fair Charge is still owed.
5. **Limit.** Only after the four above, because a Limit derived from a wrong median is not
   a Limit problem.

## Four traps that have each produced a wrong conclusion here

- **Judge in euros, never in log error.** Log error weights a €10 Line Item like a €7,000
  one, and the settled distribution reaches 7,225.
- **Condition on our own estimate, never on the true value.** Bucketing `t_hat/t` by *true*
  `t` says we are 4× too high on cheap items; bucketing the same items by *`t_hat`* says we
  are 46% too low. Both are regression artefacts and only the second is available at decision
  time. A correction fitted the first way lost **54,713**.
- **Respect the noise floor.** Two draws of the identical prompt differ by **26,622** over 18
  Games. **One Game can never justify a constant change.** Accumulate evidence in the ledger
  instead.
- **Never index the leaderboard positionally.** `/matrix` `cells` is a trailing 20-Game
  window aligned to `game_ids`. Derive nets from the Transaction identity.

## Then, and only then, propose one change

Dispatch a subagent for the analysis so the reading is independent of whoever wrote the code:

> Read `var/lessons/game_*.json` for Games N..M and `docs/brainstorm/sebi/strats/review/hypothesis-ledger.md`.
> For each standing hypothesis, say whether these Games support, contradict or do not address
> it, with euros. Propose at most **one** change, name the file, and state what would falsify
> it. Do not edit `src/`.

Update the **ledger** with what each Game added. That is the point of the loop: evidence
accumulates across Games instead of being re-derived from the latest one.

## Validate before shipping, and verify after

```bash
# does the change pay across every Game, not just the recent one?
PYTHONPATH=. pixi run python scripts/replay_payoffs.py --games all --self-check
PYTHONPATH=. pixi run python scripts/backtest.py
pixi run test
```

A change is only shipped if it wins over **all** settled Games or clears the noise floor on
a held-out split. Then:

```bash
git show HEAD:src/domain/pricing/engine.py | grep -E "^LIMIT_CEILING|^COVERAGE_FLOOR"
```

**Verify `git show HEAD:`, not the working tree.** A revert that lived only locally once let a
change measured at −127,312 reach a live Game. And record the commit against the Game range
in `live-changelog.md`, because a leaderboard number whose code you cannot name teaches
nothing.

Finally: **the runner holds the code in memory.** Tell the user to restart it, or the change
does not exist.
