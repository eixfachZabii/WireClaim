# Orchestrator handoff — WireClaim, Game 56 of 100

You are taking over a live tournament with roughly nine hours left. Your job is not to write
code; it is to **run an improvement loop and win**. You orchestrate: read what settles, find
where money leaks, fan out subagents to investigate in parallel, verify with the replay
harness, ship at most one validated change at a time, and never let the runner go dark.

Read [`CLAUDE.md`](../../CLAUDE.md) first — all ten hard rules bind you. Read
[`README.md`](../../README.md) for the derived results R1–R10. This file is the *situation*,
not a replacement for either.

---

## 1. Where we actually stand

Leaderboard (`https://c2f.public.quantco.cloud/leaderboard/#matrix`, read via
`https://c2f.public.quantco.cloud/leaderboard/api/matrix` — the endpoint the page itself
calls; do not enumerate others):

**7th of 17, at −184,428.** `eyay` leads at +279,327.

The deficit is entirely historical. Per-Game net by window, ours against the top of the field:

| team | G1–25 | G26–40 | G41–55 | per Game, G41–55 |
| --- | ---: | ---: | ---: | ---: |
| **Bin busy** | **−322,595** | +65,442 | +72,725 | **+4,848** |
| eyay | +101,677 | +44,216 | +133,433 | **+8,896** |
| error404 ai | +13,779 | +51,805 | +47,587 | +3,172 |
| TakeTheMoneyAndRun | +67,577 | −37,274 | +73,911 | +4,927 |

Games 1–25 ran before Strategy 2 landed and cost 322,595. Since Game 26 we are profitable and
mid-pack. **That is the whole story of our rank, and it means rank is a lagging indicator —
judge every change on the per-Game rate, never on position.**

### The arithmetic of first place, stated plainly

Closing 463,755 over the ~45 remaining Games requires **beating eyay by ~10,300 per Game**.
We currently trail them by 4,048 per Game. So first place needs our rate to roughly triple,
not improve at the margin.

Is that reachable? `learn_from_game.py` puts the oracle ceiling at **+1,140,327 over the 30
Games with a decision log**, about 38,000 a Game, against our +138,167. So yes, the headroom
exists — and **all of it is estimate quality**. Every decision rule has been swept to its
measured optimum (§3). Do not spend the night on constants.

**Be honest about this in your reporting.** If the rate does not move, say so. A confident
narrative about a change that did not clear the noise floor is worse than no change.

---

## 2. The loop you are here to run

Two terminals stay up for the whole tournament (CLAUDE.md rule 1b):

```bash
set -a && . .env && set +a
pixi run play      # terminal 1 — plays every Game, restarts itself if it dies
pixi run watch     # terminal 2 — extracts Cases, learns, reviews each Game as it settles
```

`watch` already runs `cases`, then `learn_from_game`, then the Claude review. The digest it
prints **is** the learn digest. Every time one appears, run this cycle:

1. **Check Strategy 2 landed.** No decision log, or a Limit of exactly `35`, or a Charge of
   exactly `300`, means a lower layer won and nothing else in the digest can be read. Fix
   that before anything else.
2. **Attribute to a stage**, not an amount. The digest names one: `estimate-too-low`,
   `charge-far-below-t`, `charge-above-t`, `coverage-*`. "We lost 8,975" is not actionable.
3. **Open the Case.** CLAUDE.md rule 2, and it is not optional: *never judge a Game from the
   numbers alone.* `[PUBLIC] EHL Cases/cases/case_NN/` holds `policy.txt`,
   `description.txt` and the invoice. Quote the clause. Three documented diagnoses reversed
   completely once someone actually read the Case.
4. **Compare to the Field.** Pull the settled Transactions for that Game and look at what the
   teams above us Charged and where their Limits sat on the same Line Item. This is allowed
   and organiser-confirmed (R9). It is the fastest way to see whether our number was wrong or
   merely unlucky.
5. **Change at most one thing**, validated across *every* settled Game, never on the strength
   of the Game that just settled. One Game is far inside the **26,622** noise floor
   (≈6,275 for a single Game).
6. **Measure with `scripts/replay_payoffs.py`**, which reproduces every published net to the
   cent. A proposed change is a measurement, not an argument.
7. Record the evidence in
   [`hypothesis-ledger.md`](../brainstorm/sebi/strats/review/hypothesis-ledger.md), then
   follow the [`learn-from-runs`](../../.devin/skills/learn-from-runs/SKILL.md) skill.

**Fold consistency is the bar, not the total.** Every constant currently shipped had to be
positive on all four folds (odd/even, early/late). A big total on one fold is the Field's
Limit clusters, not a result.

---

## 3. Do not re-derive these — they are measured and they are closed

Each of these was proposed as *the* fix, measured, and rejected. The scripts are committed so
you can re-run them, but do not re-argue them without new data.

| proposal | measured verdict | script |
| --- | --- | --- |
| Lift `LIMIT_CAP` (708) on big items | **−62,278**, negative on all four folds | `scripts/experiments/big_item_coverage.py` |
| Perfect coverage on big items | +23,021 — inside the ±46,111 floor; worth **89 euros** on Game 53 | same |
| Raise `BIG_ITEM_CHARGE_SCALE` above 1.25 | 1.25 is the argmax; nothing passes four folds | `scripts/experiments/big_charge_sweep.py` |
| A second big-fish tier above the threshold | every cell 2/4 folds or worse | `scripts/experiments/big_fish_tier.py` |
| Hold the Limit off zero in the coverage dead zone | +1,089 over 54 Games; Game 53's share is +88 | `scripts/experiments/big_dead_zone.py` |
| Charge conditioned on channel, sigma, unit, quantity | every downward multiplier loses; held-out delta −15,354 | `engine.py` docstring |
| `b` above `t̂` | flips to a monotone loss when swept against `t̂` rather than `t` | `CLAUDE.md` table |

**Oracle ceilings on big items, for calibration of where effort is worth spending:**
`b = t` is worth **+176,532**; `a = t` is worth **+417,729**. The Charge is the lever, by 2.4×.

Two specific traps that have each cost this project a full session:

- **The conditioning trap.** Bucketing `t̂/t` by the *true* `t` is a regression artefact — items
  land in a high-`t` bucket partly *because* we underestimated them. Bucket by `t̂`, the only
  split knowable at submission time, or the sign flips.
- **Censoring.** 44 of 192 items have no upper bracket; "nobody rightfully rejected" is a
  selection on the outcome. Every σ we quote is optimistic.

---

## 4. The three standing problems, in the order they cost money

### 4a. `t̂` estimation — this is where the entire remaining gap lives

Every measurement above converges here. The digest's own bucketing says it:

> `t_hat >= 1k` — the winner gave away **178,721** to the best alternative and beat it by
> 53,201 elsewhere, over 17 items where they differed.

The population, over 25 settled Line Items where our own estimate said `t̂ ≥ 1,000`:
**14 proven too high, 4 proven too low.** The 4 low ones carry **242,028** of wrongful-rejection
penalty; the 14 high ones carry roughly zero, because being high on an item worth nothing costs
nothing. That asymmetry is why the Charge is scaled *up* on the tail, and why no global
multiplier fixes it.

**Nobody has yet found an observable that separates the two directions at decision time.**
That is the single highest-value open question in the project. Candidates not yet tested:

- Whether the item is a **compensation-for-goods** line (a stolen watch's Fair Value is its
  market value, potentially five figures) versus a **repair/service** line. First pass on the
  wording was 3 low / 3 high — no clean signal — but wording alone is crude; the Case text
  distinguishes them properly.
- Whether an **aggregate or per-item sub-limit** applies (Game 44: the watch settled ≥9,361
  while the diamond ring settled <884 and the gold <663 — that shape is a jewellery sub-limit).
  Channel D exists for this and has fired on exactly one Case.
- **Ensemble disagreement.** Draws disagree on coverage on 15% of big items against 4%
  overall. Only Games 48+ have per-draw logs (`var/ai_log/`), so this becomes testable within
  a few more Games — the sample is the only thing missing.

Recent misses to work from: Game 55 *"Laptop accidental damage repair (cracked screen)"*
charged 380 against `t ≥ 1,125`; Game 54 item 1 estimated 2,018 against `t ≥ 2,090`.

### 4b. The lawyer — the `1.5a` penalty on a wrongful rejection

**It is not what is broken, and the digest can mislead you here.** The strictness ledger over
the record is roughly **2.2–2.6 : 1 saved against wasted**. Two thirds of any penalty is money
we owed anyway, since accepting costs `a` where rejecting a fair claim costs `1.5a`. And
rejecting a *fraudulent* claim is free — the `1.5×` only ever fires on a claim that was fair.

The Limit is derived, not fitted: accepting beats rejecting exactly when `P(fair) > 2/3`, which
makes `b` the one-third quantile of the posterior. Sweeping it prefers *stricter*, not looser.

**When a digest shows a large penalty, the cause is almost always `t̂` being low, not `b` being
low.** Check the direction before you touch the Limit.

### 4c. The Charge, `a`

At its measured optimum: `a ≈ 0.7 · t̂` (R5b), with `0.85 − 0.45σ` shipped and the empirical
argmax at 0.70. Income is `a` whenever `a ≤ t`, collected from all 16 opponents; above `t` only
~17% of the field pays, so an Overcharge forfeits ~80% of income. On items the policy does not
cover, always Charge — `t = 0`, so a rejected Overcharge costs exactly nothing (R6c).

---

## 5. Subagent playbook

Fan out. Send agents in parallel in a single message when the work is independent. Give each a
narrow question and demand **a quoted clause or a number**, never an impression.

**Hard constraint, learned the expensive way: no subagent may make LLM calls to the Azure
endpoint.** A rogue agent's calls cost us both model draws in Game 46, and another caused a 429
in Game 49. The tournament runner owns that quota. Subagents read files, run replays, and
compute — they do not call the model.

### 5a. The invoice sweep (run this first, it is the biggest untapped source)

Send a Sonnet subagent — or several, sharded by Game range — over
`[PUBLIC] EHL Cases/cases/`, **starting at Case 22**, where Strategy 2 began. Earlier Cases
were priced by a pipeline that no longer exists and their lessons do not transfer.

For each Case it must:

1. Read `policy.txt`, `description.txt` and the invoice in full.
2. Join against `var/export/line_items.csv` (our `t̂`, `a`, `b`, coverage, channels, rule) and
   the recovered Fair Value bracket `[t_lo, t_hi)`.
3. For every Line Item where we were materially wrong, say **why**, quoting the clause: was the
   item excluded, sub-limited, betterment-capped, unrelated, or simply mispriced?
4. Return a table of *patterns*, not anecdotes — categories of miss with euros attached and the
   Cases that exhibit them.

Remind it: `t_hi` empty means **unbounded** — worth *at least* `t_lo`, possibly far more. And
a reading of the policy is not an outcome; where a settled Fair Value exists it outranks
anyone's reading, including `CLAUDE.md`'s.

### 5b. Per-digest common-sense check

For every new `pixi run watch` digest, dispatch one agent to open that Game's Case and answer:
*does the invoice, read by a person with common sense, support what we claimed?* Look for the
gaps arithmetic cannot see — an item the policy plainly covers that we collapsed, a quantity
misread, a unit misparsed, a sub-limit nobody modelled.

### 5c. Field comparison

One agent per question, against settled Transactions: on the Line Items where we lost most,
what did `eyay`, `error404 ai` and `TakeTheMoneyAndRun` Charge, and where were their Limits?
`scripts/rivals.py`, `scripts/rivals_study.py` and `scripts/field_study.py` exist for this.
The Field's median Charge is ~0.73 · `t`; 26% of its Charges on real-money items are still
above `t`.

---

## 6. Guardrails

- **Uptime outranks accuracy.** Break-even uptime is 71%. Rescuing one Game is worth `93t`;
  improving one is worth `37t`. Never leave the runner down. Restart only between Games —
  `main.py` loads code at import, so a code change needs a restart, and `supervise.sh`
  relaunches the child automatically when you kill it.
- **The default submission is an incident, never a fallback.** `a = 0, b = 0` pays `1.5a` to
  every opponent on every Line Item. Any plausible number beats it.
- **Always gross, always the whole Line Item.** Never net (÷1.19), never per-unit.
- **Regimes.** Games ~1–43 the Field is awake; ~44–81 mostly dark; ~82–100 it wakes
  recalibrated. Never carry a `p` estimate across a boundary.
- **`--games` defaults to `1-14`** in `scripts/build_price_memory.py`. Rebuilding without
  `--games 1-<latest>` silently truncates the store. This has now bitten twice.
- **Fair play.** Inference from published settled Transactions is allowed and confirmed.
  Forbidden and disqualifying: cross-team coordination, using another team's key, obtaining
  keys before release, reading unsettled submissions, probing or overloading the API. Read the
  leaderboard at a browser's pace and call only the endpoints the page calls.
- **Never commit `TEAM_API_KEY`.** Both API keys were pasted into a chat transcript during this
  session — rotate them after the hackathon.

---

## 7. Open candidates, ranked by expected value

1. **An observable that separates the too-high from the too-low tail** (§4a). Everything else
   is a rounding error next to this.
2. **The invoice sweep** (§5a) — the only systematic look at Cases 22+ nobody has done.
3. **Sub-limit detection.** Channel D exists, has fired once, and Game 44's shape says the
   pattern is real and recurring.
4. **Ensemble disagreement as a signal** — becomes testable once `var/ai_log/` covers ~15 Games.
5. **`FALLBACK_MEDIAN` (60.0) against `SETTLED_MEDIAN` (97.0)** — a known, unfixed drift.
6. **Band calibration.** `implied_sigma` has median 0.375 against a measured RMSLE near 0.80,
   and the width does not order the error — the narrow third scores *worse* than the wide
   third. Every docstring in `engine.py` points here. It is hard and it is real.

The write-up is judged too ("your methodology also counts"). Keep the reasoning trail clean:
every claim with a number, every correction made at the source.
