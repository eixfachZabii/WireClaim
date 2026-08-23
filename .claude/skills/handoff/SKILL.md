---
name: handoff
description: Take over WireClaim after the tournament. Use at the start of any session, when asked where the strategy stands, what the 100 Games proved, or what to fix before a rerun. Keywords: handoff, take over, orchestrate, postmortem, leaderboard, standings, what should we fix, bottleneck.
---

# Orchestrate WireClaim

**The tournament is over.** All 100 Games settled; we finished **5th of 17 on +238,255.07**.

Read [`docs/POSTMORTEM.md`](../../../docs/POSTMORTEM.md) in full before acting — it carries the
money decomposition, the ceiling, the price of accuracy, and the fully re-scored counterfactual
standings. The archived mid-tournament handoff
([`docs/handoffs/done/Version1.0/ORCHESTRATOR.md`](../../../docs/handoffs/done/Version1.0/ORCHESTRATOR.md))
is stale on standings but its §3 still records seven proposals measured and closed. This file is
the checklist.

## On taking over

1. **Read the post-mortem's §3 and §7 first.** The decision rules are at their ceiling — the
   best constant available scores *worse* than what we shipped — and 103% of what remains is
   estimation. Do not open a constant sweep.
2. **The record is archived, not live.** `data/tournament/` holds every team's per-Game net,
   verified to the cent; `pixi run archive --offline` re-verifies it without the endpoints.
3. **If a rerun is in prospect, the first move is the warm store.** `data/price_memory.json`
   holds all 325 wordings from 100 Games. Shipping it cold cost us the tournament (§6).

## On every settled Game (if a rerun is live)

1. Confirm Strategy 2 landed — a Limit of exactly `35` or a Charge of exactly `300` means it
   did not, and nothing else in the digest can be interpreted.
2. Attribute to a **stage**, not an amount.
3. **Open the Case** and quote the clause. Never judge a Game from the numbers alone.
4. Compare to what the Field Charged on the same Line Item (allowed, R9).
5. Fan out subagents for anything that needs breadth — they read, replay and compute, and
   **never call the Azure model** (a rogue agent cost us both draws in Game 46).
6. Change **at most one thing**, validated across every settled Game, positive on all four
   folds. One Game is inside the ±6,275 single-Game noise floor.
7. Verify with `scripts/replay_payoffs.py` before shipping. Restart the runner only between
   Games; killing `main.py` makes `supervise.sh` relaunch it with the new code.

## What to work on

`t̂` estimation, and nothing else. `scripts/experiments/price_of_sigma.py` prices it: roughly
**5.8 M weighted per unit of log error**, and we sat at an effective σ ≈ 0.52 on the steepest
part of the curve. Estimate the σ a change buys, read the euros, then build it.

Two standing warnings. **Do not tune a constant** — H21 shows the best one available anywhere is
worse than what we ship. **Do not correct a level error without fitting the residual as
interval-censored** (`src/pricing/calibration.py`) — five findings in this project have died to
conditioning on the outcome, most recently a "+19% bias" that does not exist.

## Reporting

Be critical and specific. Every claim carries a number or a quoted clause. If a change did not
clear the noise floor, say so plainly rather than narrating it as a win. Corrections go at the
source, not in a footnote.
