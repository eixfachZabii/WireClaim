# sebi — strategy work

**Start here → [`strats/review/report.md`](strats/review/report.md)** (which pitch to
follow, ranked against real data) and
**[`strats/review/actnow.md`](strats/review/actnow.md)** (the four changes worth
~20,000 per Game).

The game itself, and the sixteen derived results, live in the root
[`README.md`](../../../README.md). Vocabulary in [`CONTEXT.md`](../../CONTEXT.md).

## The eight pitches

Ranked by effect on leaderboard net — see `report.md` for the reasoning.

| | Track | Owns | Headline |
| --- | --- | --- | --- |
| 1 | [`strat-flywheel`](strats/strat-flywheel/PLAN.md) | the feedback loop | Corrected R9 on live data (`amount` **is** the Charge). 0 Guttman violations on 4,896 real rows; one Game pins `t` to ±3.5 % |
| 2 | [`strat-wildcard`](strats/strat-wildcard/PLAN.md) | contrarian angles | Scoreboard inverts in closed form. Field acceptance **5.96 %** ⇒ the Overcharge is dead. Our own income is an oracle on `sign(a − t)` |
| 3 | [`strat-adjuster`](strats/strat-adjuster/PLAN.md) | the Estimate `t̂` | The root-cause fix, and the heaviest build. German trade grounding |
| 4 | [`strat-ops`](strats/strat-ops/PLAN.md) | the machine | Break-even uptime **71 %**. Showing up is 2.5× being right |
| 5 | [`strat-adk-adjudication`](strats/strat-adk-adjudication/PLAN.md) | [ADR 0001](adr/0001-the-model-reads-the-engine-prices.md) | Evidence contract with no field for a Charge, Limit or Fair Value. ADK 2.7.1 drives OpenAI natively |
| 6 | [`strat-warroom`](strats/strat-warroom/PLAN.md) | human loop + pitch | Human edits the **belief**, never the price. 5-min script written and timed |
| 7 | [`strat-quant`](strats/strat-quant/PLAN.md) | posterior → `(a,b)` | Mostly absorbed into R1–R10. Keep the counterfactual replay evaluator |
| 8 | [`strat-metagame`](strats/strat-metagame/PLAN.md) | the Field | Core thesis **falsified** (assumed ~66 % acceptance, measured 5.96 %). R6c survives and is excellent |

## Also here

- [`adr/0001`](adr/0001-the-model-reads-the-engine-prices.md) — the model reads, the engine prices
- [`strats/review/field-findings.md`](strats/review/field-findings.md) — the Games 1–3 inversion the ranking rests on
