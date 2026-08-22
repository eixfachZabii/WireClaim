# Which strategy actually wins this — a ranking against real data

Written Sat 15:30 CEST, after Games 1–3 settled. **We are Bin busy, 3rd of 17 (14,223).**
~20 hours and ~95 Games remain.

---

## 1. The two prizes are won by different work

Judging is explicitly two halves: **leaderboard net** *and* **the methodology write-up**
("your methodology also counts (style)"). QuantCo track = 1000 €; overall hackathon =
1500 € + $2500 credits; winners present to QuantCo.

Our eight pitches split almost perfectly along that seam, and the mistake to avoid is
letting the leaderboard work eat the write-up. One person owns the story from tonight,
not from 09:00 Sunday.

---

## 2. What the data says the problem actually is

Not what we assumed this morning.

| Belief at 12:00 | What Games 1–3 measured |
| --- | --- |
| The Overcharge above `t` is the prize | **Field acceptance is 5.96 %** vs a ~25 % break-even. Worthless. |
| We need a better price model | We need a **less biased** one — we charge **~2.5× too little** |
| Uptime is the dominant risk | We are submitting. The dominant loss is **timidity**, not absence |
| `b` needs care | `b` is flat in the bottom third; ours is loose but it is not what is costing us |

**The measured loss.** Game 1: `21,625` of *guaranteed* income forfeited by charging
below Fair Value — **1.6× the 13,502 we actually scored**. Game 2: `8,752` against +722
earned. Every euro of that was risk-free (R1): paid whether or not the reviewer accepts.

**Three distinct errors, and only the first is a model problem:**

1. **Undercharging on covered items — ~2.5× median.** Our Charge was the *minimum of the
   entire Field* on nearly every item. Measured ratios `t/a`: 1.58, 2.03, 3.04, 2.33,
   3.16, 1.68, 2.87, 2.64.
2. **Charging 0 on live items.** G1 items 1 and 18 had `t ≥ 122.94` and `98.02`; we
   charged nothing.
3. **Not exercising the free option on uncovered items.** Game 3 is the proof: nearly
   every team scored exactly **0**, while `error404 ai` (+403) and `Non Deterministic`
   (+400) charged on `t = 0` items and got paid. R6c, in real money, for free.

---

## 3. The ranking

Scored on *effect on our leaderboard net between now and Sunday 12:00*, given the above.

### Tier 1 — attacks the measured problem, buildable tonight

**1. `strat-flywheel`** — the highest-value pitch in the repo.
Directly targets the 2.5× bias with labels that are now **confirmed legal**. Ships with
a validated inverter (`invert.py`, 0 Guttman violations on 4,896 real rows, 94 % of
Charges recovered exactly) and it already earned its keep: it caught the `a = amount/1.5`
error that would have made every fitted bias 33 % low *in the direction of charging
less*, with all diagnostics looking healthy. Compounding is front-loaded — σ 0.459 →
0.354 by Game 20, flat after 35 — so **the value is realised tonight or not at all.**
*Risk:* `t_hi = ∞` on 11 of 18 real items — the Field barely straddles `t`, so labels are
one-sided. Its own fallback section addresses this.

**2. `strat-wildcard` (X3 Fair-Rate Controller + X5 Limit Alarm)**
The cleverest idea produced all day: **our own income is a per-item oracle on the sign of
`a − t`** — a Fair Charge is paid by all `N−1` reviewers, an Overcharge only by acceptors.
So we can servo the Charge multiplier upward without a price model, without the
leaderboard, and without knowing we were broken. Simulated: **more than doubles net when
`t̂` is 19 % off.** ~8.5 dev-hours, one dev, no LLM dependency. It is also the insurance
on everything else — X1 inverts the whole scoreboard from the public Net column alone.

### Tier 2 — the root cause, and the floor

**3. `strat-adjuster`** — fixes the *centre* rather than servoing around it. This is the
real fix for error 1, and it owns the coverage gate that error 3 depends on. But it is
the heaviest build in the repo (1254 lines of plan) and Tier 1 buys most of the gain for
a tenth of the effort. **Do it, but behind the controller.** Case 0 also shifted its
centre of gravity: `t` is frequently *stated in the documents* (policy gives the
indemnity basis, description gives the number), so policy reading beats price tables.

**4. `strat-ops`** — insurance, not offence, now that we are submitting. But 48 Games
run overnight and if *we* go dark we become the money fountain (13 teams took exactly
−8,273.70 in Game 1). Break-even uptime 71 %. Cheap, finite, front-loaded. **Ship the
two-phase submit and stop.**

### Tier 3 — architecture, and the other half of the prize

**5. `strat-adk-adjudication`** — the ADR 0001 realisation. Moderate leaderboard value
(it owns coverage, which is error 3), **high write-up value**: "the model reads, the
engine prices" is the single most defensible thing we can say to a room of QuantCo data
scientists, and it is their own ADR 0021 argument applied where the stakes are higher.
Its provider finding is load-bearing and verified: ADK 2.7.1 drives OpenAI natively.

**6. `strat-warroom`** — near-zero leaderboard value, **highest pitch value**. The
5-minute script is already written and timed. Its instrumentation spec must start
tonight or the story cannot be assembled Sunday morning. Treat as a parallel track owned
by one person, not as a thing to do after the code works.

### Tier 4 — absorbed or falsified

**7. `strat-quant`** — most of its content is already distilled into README R1–R10, and
its central concern (posterior *width*) is second-order now that we know the problem is
*bias*. **Keep one thing: the counterfactual replay evaluator**, which lets us test
reviewer-side changes offline against settled data with near-certainty.

**8. `strat-metagame`** — its core thesis, a generous Field worth exploiting, is
**falsified**: it assumed `m₅₀ ≈ 1.8` and acceptance ~66 %; measured is 5.96 %. Its
phase table is also contradicted — 13 of 17 teams were dark at 15:00 *Saturday*, not
overnight. **One idea survives and it is excellent: M5 / R6c**, the free option on
uncovered items, which Game 3 just paid two teams 400 each for.

---

## 4. What I would actually do with the remaining 20 hours

| When | Who | What |
| --- | --- | --- |
| **now → 18:00** | 2 devs | `actnow.md` — the four one-line fixes. Biggest euro-per-minute in the repo by an order of magnitude. |
| now → 20:00 | 1 dev | Flywheel: wire `invert.py` to run each Settlement, fit the bias, feed the multiplier |
| now → 20:00 | 1 dev | Fair-Rate Controller + Limit Alarm (wildcard X3/X5) — the safety net if the flywheel is wrong |
| 18:00 → 00:00 | 1 dev | Adjuster + ADK coverage gate (ADR 0001) — the root-cause fix |
| continuous | 1 dev | Ops floor: two-phase submit, never dark; then instrumentation for the pitch |
| 08:00 → 11:00 Sun | 1–2 | Freeze the algorithm. Assemble the write-up and rehearse the 5 minutes. |

**Freeze the pricing algorithm by 08:00 Sunday.** Games 82–100 are worth less than a
botched deploy costs, and the write-up is half the prize.

---

## 5. The one-sentence version

**Stop being timid inside the Fair Zone.** All of the money is below `t`, we are leaving
~2.5× of it there every Game, the ground above `t` is worth 6 %, and the two cheapest
pitches in the repo — the flywheel's calibration and wildcard's self-correcting
controller — are the ones that fix exactly that.
