# Strategy index — what we pitched, what we picked

> **Read [`FIELD-REPORT-01.md`](FIELD-REPORT-01.md) first.** Games 1–2 have settled and
> the data overturns the priority order below: we are undercharging by 2–3× inside the
> Fair Zone (worth more than our entire score), while the Overcharge the Field was
> assumed to reward is measured at 6 % acceptance. All of the money is below `t`.

Eight pitches were commissioned. **All eight landed** (~7,600 lines).

| Track                                                      | Status                  | Owns                                                                         | Headline finding                                                                                                                                                                                                                                              |
| ---------------------------------------------------------- | ----------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`strat-ops`](strat-ops/PLAN.md)                           | ✅ 772 ln + `ev.py`     | the machine                                                                  | Break-even uptime **71 %**. Rescuing one Game = `93t`; improving one Game = `37t`. **Showing up is 2.5× being right.**                                                                                                                                        |
| [`strat-adjuster`](strat-adjuster/PLAN.md)                 | ✅ 1254 ln              | the Estimate `t̂`                                                             | Builds the number every other track consumes. German trade price grounding.                                                                                                                                                                                   |
| [`strat-quant`](strat-quant/PLAN.md)                       | ✅ 615 ln + `sweep.py`  | posterior → `(a,b)`                                                          | Calibration from _disagreement, not introspection_: 6 framings, robust MAD, `σ_floor`. A naive `b = t̂` costs **+8–10 %**.                                                                                                                                     |
| [`strat-metagame`](strat-metagame/PLAN.md)                 | ✅ 741 ln + `derive.py` | the Field                                                                    | Found **R6c** (always charge on uncovered items — free). Cap-jump bar is ~15.6 %, not 25 %. Tit-for-tat structurally impossible.                                                                                                                              |
| [`strat-warroom`](strat-warroom/PLAN.md)                   | ✅ 776 ln               | human loop + pitch                                                           | Human edits the **belief, never the price**. Full 5-min script, timed.                                                                                                                                                                                        |
| [`strat-flywheel`](strat-flywheel/PLAN.md)                 | ✅ 877 ln + `invert.py`  | R9 inversion, Price Memory, the feedback loop                                 | **Corrected R9 against real Game 1: `amount` IS the Charge, not `1.5×` it** — the old rule made every recovered Charge 33 % too low, and had already propagated into `FIELD-REPORT-01`, whose forfeited-income figure is really **21,782 (1.6× our whole score)**, not 14,417. 0 Guttman violations on 4,896 live rows; one Game's bracket pins `t` to **± 3.5 %**; bias learned by Game 10. |
| [`strat-wildcard`](strat-wildcard/PLAN.md)                 | ✅ 733 ln + 7 scripts   | contrarian angles                                                            | **The scoreboard inverts in closed form.** `Σcosts − Σincome = 0.5·W` and `income_i = (N−1)·A_i` — verified exactly on Game 1: Field acceptance `p̄` = **5.96 %**, so the Overcharge is dead. Our own income is a per-Line-Item oracle on the sign of `a − t`. **The ×q error is 5.5× the ×1.19 error.** |
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
[`strat-flywheel`](strat-flywheel/PLAN.md), and the thing that compounds: scrape settled
Games, invert `(line_item, issuer, reviewer, accepted, amount)` back to every team's
Charge, bracket Fair Value, discover the Cap, fit calibration. Everything else gets
better as a by-product. **The inverter is already written and already validated against
real Game 1** (`python3 strat-flywheel/invert.py --live 1`) — it is a pure function with
no dependencies, so it was finished before the pricing pipeline existed.

**Its first output is a correction to `README.md` R9 itself**, and every other track was
about to build on the wrong version — see [`strat-flywheel/PLAN.md`](strat-flywheel/PLAN.md) §0.

Pitch instrumentation (`strat-warroom` §5) is not a track — it is a rule: every run
writes its artifacts from Game 1, or the story cannot be assembled at 11:00 Sunday.

## Order of operations, from now

1. **Procurement** — `TEAM_API_KEY`, case folder, `API_HANDBOOK.md`, `starter_script.py`, case 0. _Blocking everything._
2. **Round-trip on case 0** before 15:00. A submission that is merely _not the default_
   already beats going dark (README R7).
3. **Game 1 with the Fast Path only.** Do not wait for the good pipeline.
4. **Flywheel online by ~Game 8**, so calibration starts compounding early.
5. **Re-commission `strat-wildcard` at 18:10**, or drop it — by then the
   tournament will have taught us more than they would have.
