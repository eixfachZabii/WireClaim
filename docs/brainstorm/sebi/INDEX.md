# Strategy index — what we pitched, what we picked

Seven pitches were commissioned. **Six landed** (~5,970 lines). Two were lost to a
model session limit that resets **18:10 CEST** and can be re-commissioned then.

| Track                                                      | Status                  | Owns                                                                         | Headline finding                                                                                                                                                                                                                                              |
| ---------------------------------------------------------- | ----------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`strat-ops`](strat-ops/PLAN.md)                           | ✅ 772 ln + `ev.py`     | the machine                                                                  | Break-even uptime **71 %**. Rescuing one Game = `93t`; improving one Game = `37t`. **Showing up is 2.5× being right.**                                                                                                                                        |
| [`strat-adjuster`](strat-adjuster/PLAN.md)                 | ✅ 1254 ln              | the Estimate `t̂`                                                             | Builds the number every other track consumes. German trade price grounding.                                                                                                                                                                                   |
| [`strat-quant`](strat-quant/PLAN.md)                       | ✅ 615 ln + `sweep.py`  | posterior → `(a,b)`                                                          | Calibration from _disagreement, not introspection_: 6 framings, robust MAD, `σ_floor`. A naive `b = t̂` costs **+8–10 %**.                                                                                                                                     |
| [`strat-metagame`](strat-metagame/PLAN.md)                 | ✅ 741 ln + `derive.py` | the Field                                                                    | Found **R6c** (always charge on uncovered items — free). Cap-jump bar is ~15.6 %, not 25 %. Tit-for-tat structurally impossible.                                                                                                                              |
| [`strat-warroom`](strat-warroom/PLAN.md)                   | ✅ 776 ln               | human loop + pitch                                                           | Human edits the **belief, never the price**. Full 5-min script, timed.                                                                                                                                                                                        |
| `strat-flywheel`                                           | ❌ lost                 | R9 inversion, Price Memory                                                   | — re-commission 18:10, or hand-build (see below)                                                                                                                                                                                                              |
| `strat-wildcard`                                           | ❌ lost                 | contrarian angles                                                            | — the gross/net VAT trap is still unexamined                                                                                                                                                                                                                  |
| [`strat-adk-adjudication`](strat-adk-adjudication/PLAN.md) | ✅ 1824 ln              | ADK realisation of [ADR 0001](adr/0001-the-model-reads-the-engine-prices.md) | Evidence contract with **no field for a Charge, a Limit or a Fair Value**. σ comes from _measured_ disagreement — the named anchors are a second estimate, not a footnote. ADK 2.7.1 drives **OpenAI natively** (`labs.openai.OpenAILlm`); ~45 min migration. |

## What the pitches agree on

Three independent methods put the optimal Charge **below the median** of the posterior
(README R5b) — my own first draft had it at or above, and was wrong. They disagree on
the multiple (`0.7` / `0.75` / `0.82–1.09` × `t̂`), which is a calibration question to
settle on real data, not by argument.

They also agree on the priority order, and it is not the interesting one:
**the machine outranks the model.** `strat-ops` puts one missed Game at 9–13 Games'
worth of `strat-quant`'s entire edge. `strat-quant` concedes it and ranks itself third.

## The assignment — 5 devs, 2 lead tracks

**Lead track A — The Machine** (`strat-ops`) · **2 devs**
Fetch → decrypt → parse → price → submit, inside 60 s. Two-phase submit (cheap at T+3,
smart overwrite at T+50, **per-line-item merge** so partial output is never discarded).
The 21-step fallback ladder, floored at a stdlib-only `panic.py`. Pre-stage the
encrypted archives — the handout says the folder is published in advance and only the
key drops at T0, which deletes an entire failure class.

**Lead track B — The Estimate** (`strat-adjuster` + ADK) · **2 devs**
The adjudication pipeline under [ADR 0001](adr/0001-the-model-reads-the-engine-prices.md):
agents read, the engine prices. Coverage → relatedness → price band with named anchors.
One dev on the ADK agent team (mirror `SampleRepo/server/app/services/ai/agents.py`),
one on the deterministic engine (posterior, shrinkage R6b, quantile rules R5b/R6).

**Supporting — The Flywheel** (R9) · **1 dev**
The lost pitch, and the thing that compounds: scrape settled Games, invert
`(line_item, issuer, reviewer, accepted, amount)` back to every team's Charge, bracket
Fair Value, discover the Cap, fit calibration. Everything else gets better as a
by-product. **Blocked on nothing but a working submit path.**

Pitch instrumentation (`strat-warroom` §5) is not a track — it is a rule: every run
writes its artifacts from Game 1, or the story cannot be assembled at 11:00 Sunday.

## Order of operations, from now

1. **Procurement** — `TEAM_API_KEY`, case folder, `API_HANDBOOK.md`, `starter_script.py`, case 0. _Blocking everything._
2. **Round-trip on case 0** before 15:00. A submission that is merely _not the default_
   already beats going dark (README R7).
3. **Game 1 with the Fast Path only.** Do not wait for the good pipeline.
4. **Flywheel online by ~Game 8**, so calibration starts compounding early.
5. **Re-commission the two lost pitches at 18:10**, or drop them — by then the
   tournament will have taught us more than they would have.
