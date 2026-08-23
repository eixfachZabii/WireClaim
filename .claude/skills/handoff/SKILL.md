---
name: handoff
description: Take over WireClaim as the orchestrator running the live tournament improvement loop. Use at the start of any session, when a Game settles, when the user shares `pixi run watch` output, or when asked what to fix next. Keywords: handoff, take over, orchestrate, game settled, watch digest, leaderboard, what should we fix, bottleneck.
---

# Orchestrate WireClaim

Read [`docs/handoffs/ORCHESTRATOR.md`](../../../docs/handoffs/ORCHESTRATOR.md) in full before
acting. It carries the standing, the arithmetic of what first place requires, the seven
proposals already measured and closed, and the subagent playbook. This file is the checklist.

## On taking over

1. **Check the runner is alive.** `ps aux | grep -E "main\.py|supervise|learn_watch"`. If
   `main.py` is not running, that is the emergency — nothing else matters until it is back.
   Uptime outranks accuracy; break-even is 71%.
2. **Read the standing**, not the rank: `curl -s https://c2f.public.quantco.cloud/leaderboard/api/matrix`.
   Our deficit is historical (Games 1–25). Judge everything on the **per-Game rate**.
3. **Top up the Cases**: `pixi run cases`. Then read the newest one.

## On every settled Game

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

`t̂` estimation, in the tail. 14 of 25 big estimates are proven too high and 4 too low, and the
4 carry 242,028 of penalty. No observable yet separates them — finding one is the highest-value
open question. The Charge is the lever on big items, worth 2.4× the Limit at the oracle.

Do not re-argue the seven closed proposals in §3 of the handoff without new data. Do not tune a
constant; they are all at their measured optimum and the remaining gap is evidence quality.

## Reporting

Be critical and specific. Every claim carries a number or a quoted clause. If a change did not
clear the noise floor, say so plainly rather than narrating it as a win. Corrections go at the
source, not in a footnote.
