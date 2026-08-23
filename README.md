# WireClaim — QuantCo _Claim to Fame_

> Munich Agentic Hackathon (EHL stop #3), 22–23 Aug 2026 · Track 1: QuantCo

This repo is our entry to QuantCo's **Claim to Fame** challenge. This README is the
single source of truth for _what the game is_, _how it is scored_, and _what we
proved about how to beat it_. Read this before touching code.

**Judging the submission? Start with [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md)** — how we
decided things, what we measured and rejected, and how to reproduce any number in it. This README
is the reference for the game itself; that one is the argument.

---

## 1. The hard facts (verified against the live API, not the handout)

| Fact                              | Value                                       | Source                                      |
| --------------------------------- | ------------------------------------------- | ------------------------------------------- |
| Total games                       | **100**                                     | `GET /leaderboard/api/games?page_size=1000` |
| Cadence                           | **757.575 s** = 12 min 37.6 s               | derived from schedule                       |
| First game                        | **Sat 15:00:00 CEST** (13:00 UTC)           | API                                         |
| Last game                         | **Sun 11:50:00 CEST**                       | API                                         |
| Submission window per game        | **60 s** (`gameDurationSeconds = 60.0`)     | leaderboard JS                              |
| Games between 00:00 and 11:50 Sun | **~48**                                     | API                                         |
| Hackathon submission deadline     | **Sun 12:00**                               | kickoff deck                                |
| Pitch                             | Sun 12:30 (5 min + 3 min Q&A), finals 14:15 | kickoff deck                                |

> ⏱ **Half the tournament happens while everyone is asleep.** This is the single
> most important fact in this document. See §5.

**Prizes.** QuantCo track 1000 €. Overall hackathon 1st = 1500 € cash + $2500 OpenAI
credits (2nd $1500, 3rd $500). QuantCo winners additionally get, per person, AirPods
Pro 3 + 100 € coding-agent credit. Both are winnable from one codebase.

**Hard gate.** The kickoff deck states submissions are **rejected if you do not use
Entire**. Challenge selection and final submission both happen on `ehl.gg`.

---

## 2. The game in one paragraph

Every 12.6 minutes a _case_ is released — an insurance `policy.txt`, a damage
`description.txt`, an `invoices.pdf` with line items **but no prices**, sometimes
`images.png`. We have 60 seconds to fetch a decryption key, decrypt the archive,
read it, and submit **two numbers per line item**:

- **`a` — charge price.** What we invoice every other team, as _gross total for the
  whole line item_ (quantity × unit price, incl. VAT). Default `0`.
- **`b` — acceptance limit.** The most we will pay when another team invoices us the
  same line item. Default `0`.

Every team is matched against every other team in **both** roles. Behind each line
item sits a secret **fair-value threshold `t`** (the max a real claims expert would
allow; `t = 0` if the policy does not cover the item) and a secret **payment cap `c`
with `c ≥ 4t`**, shared across all teams.

### Payoff matrix

`H` = handyman/issuer, `I` = insurance/reviewer.

|                      | `a ≤ t` — price fair          | `a > t` — price fraudulent               |
| -------------------- | ----------------------------- | ---------------------------------------- |
| **`a ≤ b`** accepted | `I` pays `a`, `H` gets `a`    | `I` pays `min(a,c)`, `H` gets `min(a,c)` |
| **`a > b`** rejected | `I` pays `1.5a`, `H` gets `a` | nothing happens                          |

**Score = `net = income − costs`**, summed over all matchups and all 100 games.
Public leaderboard: <https://c2f.public.quantco.cloud/leaderboard/>

---

## 3. What we proved

Sixteen results. They are the reason the plan looks the way it does.

### R1 — Below `t`, income is risk-free

If `a ≤ t`, `H` receives exactly `a` **whether the reviewer accepts or rejects**.
Acceptance risk exists _only_ above `t`. Corollary: within the fair zone, `a = t`
strictly dominates every smaller charge. Estimating `t` accurately _is_ the game.

### R2 — The game is negative-sum, and the lawyer fee evaporates

On a wrongful rejection `I` pays `1.5a` but `H` only receives `a`. The `0.5a`
goes to nobody. Aggregate net across all teams equals `−0.5 × Σ(wrongfully
rejected fair charges)`. There is no pot to win, only a pot to _avoid burning_.

### R3 — One `a` and one `b` per line item, against the entire field

Submissions are not per-opponent. There is no price discrimination: we choose a
single `a` against the whole distribution of opponents' `b`. All reasoning must be
distributional, never pairwise.

### R4 — The reviewer should accept only at ≥ 2/3 confidence

Let `q = P(a ≤ t)`. Accepting a fair claim saves `0.5a`; accepting a fraudulent one
costs `min(a,c)`. Accept iff `(1−q)·min(a,c) < 0.5·q·a`, which for `a ≤ c` reduces to

```
accept  ⟺  q > 2/3          ⟹      b* = Q₁ᐟ₃(t)
```

**`b` is the one-third quantile of our posterior on `t`** — not the mean, not the
mode.

Above the Cap the algebra actually goes the _other_ way — `q > c/(c + 0.5a)`, which
**falls** toward zero as `a` grows, because the payout is capped at `c` while the
wrongful-rejection penalty `1.5a` keeps growing. An earlier draft claimed the bar
rises; that was wrong. The conclusion survives for a different and stronger reason:
`c ≥ 4t` means `t ≤ c/4`, so any Charge above the Cap is _provably_ in the Fraud Zone,
`q` is exactly zero, and the falling bar is never reached. Reject, always — but reject
it because it cannot be fair, not because the bar is high.

### R4b — The threshold is distribution-free; only _calibration_ matters

The accept/reject decision at each charge level is separable, so a threshold at
`Q₁ᐟ₃` implements the pointwise-optimal rule **exactly, whatever the field charges**.
The field's charge distribution changes how much we gain, never where `b` belongs.

The one thing that can break it is a miscalibrated posterior. Too narrow and `Q₁ᐟ₃`
hugs `t̂` and we get farmed; too wide and we reject everything and bleed `0.5a`. So
the tunable buffer is the **width of the interval, not its centre** — and R9 measures
it: compare predicted quantiles against realised `t` brackets, check empirical
coverage, widen or narrow. Intuition to resist: _"put `b` in the upper half of the CI
so we don't wrongfully reject."_ Being generous is ~8× more expensive than being
strict (`4t` vs `0.5t`), and the worst case is not a slightly-over charge — it is an
exploiter parked at the cap.

### R5 — A failed fraudulent charge costs exactly zero

This is the load-bearing asymmetry on the issuer side. Look again at the matrix:
`a > t` and `a > b` ⟹ **"nothing happens"**. There is _no_ penalty for a rejected
fraudulent claim — not a fee, not a reputation effect, nothing. Charging above `t` is
therefore a **free option**: its only cost is the risk-free `t` we forgo by leaving
the fair zone. Compare per opponent:

```
E[fraud at a] = min(a,c) · p(a)          E[honest] = t
```

so overcharging wins iff `min(a,c)·p(a) > t`. With `c ≥ 4t`, break-even at the cap is

```
p(a) > 25 %
```

If 8 of 10 opponents accept, `4t × 0.8 = 3.2t` versus `t` — **3.2× better**, and that
is a floor, because `c` may exceed `4t`. The two misses genuinely cost nothing.

**But `p(a)` is time-varying, and that is the entire play.** Early rounds, the field
reads "wrongful rejection is penalised" and sets `b` defensively high, so `p` is
plausibly large — the exploit window is **Saturday afternoon**. Overnight, sleeping
teams sit at `b = 0`, `p → 0`, and honest `a = t` strictly dominates. Sunday morning
the field wakes recalibrated. Aggression is not a values dial; it is a **measured
quantity we re-read every 12.6 minutes.**

### R5c — A mis-measured `p(a)` is worse than no `p(a)` at all

Discovered the hard way: an early simulation estimated the
Field's acceptance rate inline from a single stale Line Item. The estimate was
spuriously high, it pushed the Charge above optimum, and it cost **~60 % of net** —
dropping us from 1st to 11th in the simulated Field. Forcing `p = 0` restored 1st.

**Guardrail: `p = 0` (fully honest) is the default, and the Overcharge is only
unlocked by an acceptance curve measured from settled Games (R9) with enough support
to trust it.** Never estimate `p` from a handful of observations, and never carry a
stale `p` across a phase boundary (R10) — the Field's behaviour changes at midnight.

### R5b — The Charge belongs _well below_ the median Estimate

```
a* = argmax_a [ a·G(a) + min(a,c)·(1−G(a))·p(a) ]
       where G(a) = P(t ≥ a)  and  p(a) = share of the Field with b ≥ a
```

The trap: R1 says income below Fair Value is risk-free, which tempts you to charge at
`t̂`. But risk-free is _conditional on `a ≤ t`_ — charging at the median forfeits the
whole claim half the time. Solving `argmax a·G(a)` for a log-normal posterior
(`σ·Φ(−z) = φ(z)`), confirmed by Monte Carlo, and later by settled Games:

| posterior log-sd σ | optimal Charge | as a quantile | E[revenue]/t̂ |
| ------------------ | -------------- | ------------- | ------------ |
| 0.15               | 0.80 · t̂       | ~Q₀.₀₅        | 1.01         |
| 0.30               | 0.69–0.75 · t̂  | ~Q₀.₁₇        | 0.62–0.80    |
| 0.45               | 0.59–0.75 · t̂  | ~Q₀.₂₆        | 0.57–0.66    |
| 0.60               | 0.56–0.82 · t̂  | ~Q₀.₃₇        | 0.52–0.59    |

**Practical rule: charge ≈ 0.7 × t̂, and never above it unless `p(a)` says otherwise.**
The multiple is strikingly stable across σ even though the quantile is not, which makes
it a safe default when calibration is still poor. A measured `p(a) > 0` pushes `a` up
(that is the Overcharge of R5); `p ≈ 0` overnight pulls it back down to ~0.6–0.7 · t̂.

### R6 — Charge and Limit both sit low, and the Charge is the knob that matters

An earlier draft of this document claimed the error asymmetries force `a > b`. **That
was wrong**, and the simulator caught it. Sweeping both quantiles against a mixed
Field:

- the Limit is remarkably **flat** anywhere in the bottom third (`Q₀.₀₅`–`Q₀.₃₃` differ
  by ~2 % of net); only `Q₀.₅₀` and above is clearly bad
- the Charge is **~3× more sensitive**, and its optimum moves with the phase:
  `≈ Q₀.₂₅` while the Field is awake, `≈ Q₀.₁₀` once it goes dark

So: **both low, in the same neighbourhood, and spend the engineering effort on `a`.**
Do not over-tune `b` — get it in the bottom third and move on.

### R6b — Shrink the Estimate before pricing it

The Monte Carlo optimum sits below the analytic one for a reason: the analytic version
assumes the posterior is centred on `t̂`, but a noisy Estimate should regress toward the
category median before use. With prior log-sd `τ` and error log-sd `σ`, shrink in log
space by `τ²/(τ² + σ²)` — at `τ = 0.8, σ = 0.45` that is a factor of 0.76 toward the
category median. Empirical Bayes, and it is why the Price Memory (R9) pays twice: it
supplies both the prior and the calibration.

### R6c — On items the policy does not cover, always Charge. It is free.

When an item is not covered, `t = 0` (stated in the handout). Every possible Charge is
then in the Fraud Zone, so the honest branch of R5b pays **exactly zero**. And R5 says a
rejected Overcharge costs nothing. So:

```
E[honest on an uncovered item] = 0
E[charging x]                  = min(x, c) · p(x)   ≥ 0,  always
```

Charging is **weakly dominant** — break-even is `p > 0`, not R5's 25 %. There is no
phase in which this turns off, including overnight: if even one team in the Field has a
generous Limit, we collect, and if none does, we lose nothing we could have had.

Two constraints on how far to push it. The Cap still binds (`c ≥ 4t = 0`, but "never
below an absolute floor"), so charging past the floor only depresses `p(x)` for no extra
payoff — aim at the estimated floor, not at infinity. And this is conditional on
_actually being right about coverage_: if the item is covered after all, a high Charge
forfeits the guaranteed `a·G(a)`. So it must be driven by an explicit coverage
probability, not a binary guess — which is exactly why ADR 0001 makes the coverage
agent emit a verdict _and_ a confidence, and lets the engine carry `π₀` as a spike at
zero rather than collapsing it early.

### R6d — Fair Value is often *stated in the Case*, not a market-research question
Case 0: the policy sets the indemnity basis ("the market value of the bicycle at the
time of the theft"), the description supplies the number ("the bike was worth 420
Euros"), and the invoice line reads "New Bike, 1 unit". So `t = 420`, and the fraud
vector is **replacement-new vs. market-value** — invoicing a new bike when the policy
owes the depreciated one. Expect the same shape elsewhere: deductibles, sums insured,
"new for old" clauses, exclusion lists. Read the policy for the *basis* and the
description for the *figure* before reaching for a price table; the table is the second
tool, needed mainly for repair cases with quantities.

### R7 — The default submission is the worst possible submission

`a = 0` earns nothing. `b = 0` rejects _every_ fair claim, so we pay `1.5a` to every
opponent on every line item. A team that goes dark does not score zero — it bleeds.
(Confirmed by the demo leaderboard in QuantCo's slides: three teams at
`income 0.00 / costs −3247.38`.)

But note the flip side: **`b = 0` caps our downside at a 50 % surcharge on fair
claims**, while `b` set too high can cost `4t+` per item. So `b = 0` is a _terrible
default but an acceptable panic mode_. `a = 0` is never acceptable — any plausible
number beats it.

### R8 — Relative rank and absolute net agree (and rejection is quietly good)

Ranking is relative, so what matters is `our net − their net`. For `a ≤ t` the swing
per opponent is `2a` if they accept and `2.5a` if they wrongfully reject. Being
rejected is 25 % _better_ for our rank. Both objectives are still maximised at
`a = t`, so we do not need a separate adversarial objective — but it means we should
never soften `a` to be "acceptable" to the field.

### R9 — The public leaderboard inverts to `t`

The Transactions view exposes `line_item_index, issuer, reviewer, accepted, amount`
for **any** team in **any** settled game. That inverts:

- rejected & `amount > 0` ⟹ the charge was **fair**, and **`a = amount`**
- rejected & `amount = 0` ⟹ the charge was **fraudulent**
- accepted ⟹ `amount = a` (or `min(a,c)`)

> ⚠️ **Corrected against real data, Game 1.** This document previously said
> `a = amount / 1.5` on a wrongful rejection. **That was wrong.** The published
> `amount` is what the **Issuer receives**, in *both* branches — the `0.5a` lawyer fee
> appears only in the aggregate `costs` and never in a Transaction row. Verified two ways:
>
> - 18 Issuer–Line-Items in Game 1 had both an acceptance and a wrongful rejection.
>   The ratio of the two amounts was **1.000000** in every case (min = max).
> - `/performance` reconciles to the cent for all 17 teams:
>   `income = Σ(amount | Issuer)` and `costs = Σ(amount | accepted) + 1.5·Σ(amount | wrongfully rejected)`.
>
> Dividing by 1.5 would have made every recovered Charge — and therefore every `t`
> bracket and every fitted bias — **33 % too low**, in the direction that makes us charge
> less and reject more, with every diagnostic still looking healthy. Working and
> reconciliation in
> [`docs/brainstorm/sebi/strats/strat-flywheel/PLAN.md`](docs/brainstorm/sebi/strats/strat-flywheel/PLAN.md) §0;
> re-checked automatically every Game by
> [`invert.py`](docs/brainstorm/sebi/strats/strat-flywheel/invert.py) (`--live`).

So after every settled game we can bracket `t ∈ [max fair a, min fraud a)` for every
line item, and reconstruct **every opponent's `b`** from what they did and did not
accept. That is a labelled training example every 12.6 minutes, 100 times.

**The cap `c` falls out too.** If any team overcharges past `c` and is accepted, the
leaderboard shows `amount < a` — which pins `c` exactly. Since `c ≥ 4t`, that hands us
a free _upper_ bound `t ≤ c/4`, bracketing `t` from above as well as below. With a
field of tens of teams, somebody overshoots every round.

> ✅ **Confirmed allowed.** We asked the organisers. Inference from the published,
> settled leaderboard is sanctioned — it is not "extracting the secret thresholds".
> R9 is cleared to build on.

---

### R10 — A dark team is a one-way money fountain, and overnight is the main event

A team sitting at defaults (`a = 0`, `b = 0`) is not a neutral participant:

- **as Issuer it charges `0`** — trivially in the Fair Zone, so we accept and pay nothing.
  A dark team cannot cost us a cent.
- **as Reviewer it rejects our Charge at `t`** — a Wrongful Rejection, so it pays `1.5t`
  while we collect `t`.

Net **`+t` to us, `−1.5t` to them: a 2.5t relative swing per Line Item, per dark team,
per Game.** Overnight income is linear in _how many others sleep_ × _how accurate `t̂` is_.

It also kills the Overcharge: against `b = 0`, `p(a) → 0`, so charging above Fair Value
earns exactly nothing. **Overnight the honest play strictly dominates.** Hence three
regimes:

| Phase             | Games   | Field                        | What wins                                                  |
| ----------------- | ------- | ---------------------------- | ---------------------------------------------------------- |
| Sat 15:00 → 00:00 | ~1–43   | awake, `b` probably generous | measure `p(a)`; Overcharge window; Limit discipline        |
| 00:00 → 08:00     | ~44–81  | mostly dark                  | **honest harvest at `a = t̂`** — accuracy is the only lever |
| 08:00 → 11:50     | ~82–100 | waking, recalibrated         | back to phase-1 logic                                      |

The phase where accuracy pays most is also the phase where we have accumulated the most
calibration data (R9). The flywheel and the harvest compound.

**We are awake all night.** That converts R7 from a risk to be mitigated into our primary
revenue source — but it does not remove the need for automation. A 60-second window is
too tight for human pricing, and by Game 70 a tired human's intuition is worse than a
Price Memory holding hundreds of settled Line Items. Division of labour: **humans own
coverage and relatedness, the machine owns the number.**

---

## 4. Corrections to our first-pass reasoning

Recorded deliberately, because two of these would have cost us money.

| We initially thought                                                                           | Actually                                                                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Optimal is `a = t = b`."                                                                      | Only under _certainty_. Under uncertainty the error asymmetry forces `a > b` (R4–R6).                                                                                                                                                                       |
| "Charge just above their `t'` so we get the lawyer bonus and claim it."                        | **There is no bonus to claim.** The `0.5a` evaporates (R2). And any `a ≤ t` pays us exactly `a`, so the top of the fair zone is always right (R1).                                                                                                          |
| "If their `t' > t*` we just take `a = t'`."                                                    | Impossible — `a` is one number against the whole field, not per opponent (R3).                                                                                                                                                                              |
| "Find `t` so our claims get paid either way."                                                  | ✅ Correct, and it is the core insight.                                                                                                                                                                                                                     |
| "As insurer always pay up to `t*`, reject above."                                              | ✅ Correct in spirit, but the Limit belongs in the bottom third of the posterior, not at `t̂` (R4, R6).                                                                                                                                                      |
| _(this document, R9, until Game 1 settled)_ "rejected & `amount > 0` ⟹ `a = amount / 1.5`." | **Wrong, and load-bearing.** `amount` is what the **Issuer receives**, in both branches; the lawyer fee never appears in a Transaction row. Ratio measured at exactly `1.000000` on 18 real cases and reconciled to the cent against `/performance` for all 17 teams. Would have made every recovered Charge, `t` bracket and fitted bias 33 % too low. Caught by running the inverter against real rows instead of reasoning about them (`strat-flywheel` §0). |
| _(this document, earlier draft)_ "the optimum Charge sits at or above the median, so `a > b`." | **Wrong, twice.** The optimal Charge is ~0.7 · t̂, well _below_ the median (R5b), and `a` ends up near or below `b`, not above it (R6). The original `a = t = b` intuition was closer than the correction. Caught in simulation before the tournament began. |

---

## 5. How to actually win

**Winning the QuantCo track** = leaderboard net **+** the strategy write-up
("your methodology also counts (style)"). Winners then present to QuantCo.

In priority order:

1. **Never miss a game.** ~48 games run overnight and the default submission is
   actively harmful (R7). A dumb bot that always submits beats a brilliant team that
   sleeps. Uptime is the highest-EV line of code in the repo.
2. **Submit twice per game.** Later submissions overwrite earlier ones. Fire a cheap
   heuristic guess at T+5 s, overwrite with the considered answer at T+50 s. We can
   then never be caught by a slow model, a PDF parse failure, or a rate limit.
3. **Estimate `t` well.** Everything else is second-order. Income is linear in
   accuracy (R1).
4. **Compound over 100 rounds.** Build a price memory keyed on item description; by
   Sunday morning we should be near-exact on repeated trades (R9).
5. **Be aggressive as issuer, timid as reviewer** (R6).
6. **Write the methodology as we go**, not at 11:00 Sunday. R1–R9 _are_ the pitch:
   we did the maths, then built the machine.

**Winning the overall hackathon** additionally needs a 5-minute demo that lands. A
live ops dashboard showing the bot trading itself through the night, with the
posterior tightening game over game, is the demo.

---

## 6. Fair play

Allowed: any tooling, LLMs, manual work, domain research, anything inside our team.
Forbidden: cross-team coordination, sharing keys, pre-release key access, probing or
overloading the API, disqualification if breached. When unsure — ask, don't assume.

---

## 7. Procurement checklist (blocking, do first)

- [ ] Register at the QuantCo desk → obtain `TEAM_API_KEY` (team name + Discord handle)
- [ ] Get the shared case folder link → `API_HANDBOOK.md`, `starter_script.py`, `pixi.toml`, **case 0**
- [ ] `pixi install && pixi run python starter_script.py` — prove the round-trip on case 0
- [ ] Confirm Entire is installed and our submission path satisfies the gate
- [ ] Select the QuantCo challenge for our team on `ehl.gg`
- [x] Leaderboard-derived calibration (R9) — asked, confirmed allowed
- [ ] `brew install p7zip` on every machine that might run the bot

---

## 8. Repo map

```
README.md                  this file — the game, the scoring, the derived results
CONTEXT.md                 domain glossary — the ubiquitous language
CLAUDE.md                  agent knowledge file — conventions and hard-won rules
docs/
  GAME_DESCRIPTION.md      original QuantCo handout
  *.pdf                    kickoff deck + QuantCo slides
  brainstorm/
    sebi/                  strategy pitches, ADRs, verification scripts
      INDEX.md             what was pitched, what was picked, who does what
      strat-*/PLAN.md      competing approaches
      adr/                 architecture decision records
      evidence/            throwaway scripts that back a claim in this README
    jonas/ lukas/
    markus/ matthi/        one folder per member, same shape
data/schedule.json         the 100 Game start times, pinned locally
```

Everyone gets a folder under `docs/brainstorm/`. Put ideas there, not in this
README — this file is the shared understanding of the _game_, and it should only
change when we learn something about the rules or prove a new result.

## 9. Application scaffold

Minimal Python setup for the QuantCo Claim to Fame challenge.

`main.py` contains the complete flow:

1. Read the game schedule.
2. Notice when a game's UTC start time arrives.
3. Fetch its decryption key.
4. Extract the matching ZIP to `var/cases/case_XX`.
5. Call `process_case()`, where the analysis code will be added.

Submission is intentionally not implemented yet.

## For anyone benchmarking this (the learning-loop record)

Four directories under `var/` are committed. Together they say, per settled Game, what we
estimated and why, what actually happened, and what the model literally replied:

| path | one row per | what it carries |
| --- | --- | --- |
| `var/decisions/game_NNN.json` | Line Item | our `t̂`, the price band, coverage probability, which channels spoke, the pricing rule, the submitted Charge and Limit |
| `var/lessons/game_NNN.json` | Game | the four-bucket money decomposition, the recovered Fair Value bracket per item, stage attribution, and what every strategy would have scored |
| `var/reviews/game_NNN.md` | Game | the automated review of that Game's digest, with the Policy clause quoted |
| `var/ai_log/game_NNN_<draw>.json` | model call | the raw reply, the model, the service tier and the wall clock |

The ground truth to score against is **exact, not estimated**: `scripts/invert_fair_values.py`
recovers a `[t_lo, t_hi)` bracket for every settled Line Item from public Transactions, and
`--verify` asserts it reproduces every published net to the cent.

Two things deliberately **not** committed. `var/transactions/` is 35 MB of cached *public*
leaderboard rows — regenerate with `scripts/pull_transactions.py`. `var/cases/` is decrypted
Case material; it is derivable from the archives plus a released key and is not ours to
publish.

## Setup

```bash
pixi install
cp .env.example .env
# Add TEAM_API_KEY to .env
```

## Running it — two terminals, two commands

```bash
pixi run play      # terminal 1: plays every Game on the schedule, restarts itself if it dies
pixi run watch     # terminal 2: analyses each Game as it settles, and learns from it
```

That is the whole tournament loop. Leave both running.

| command | what it does | when you run it |
| --- | --- | --- |
| `pixi run play` | The runner, under a supervisor. **Use this, not `start`.** `watch_games()` has no exception boundary, so an uncaught error ends the tournament rather than costing one Game; the supervisor turns that back into one Game. Logs to `var/runner.log`. | Once. Restart it after any change to `src/`, `.env`, or the constants — **the process caches them at boot and will not pick them up otherwise.** |
| `pixi run watch` | Polls for settled Games, then per Game: tops up the Case extraction, rebuilds Price Memory from the newly recovered Fair Values, prints the learning digest, and runs a Claude review of it. | Once, alongside `play`. |
| `pixi run start` | The bare runner, no supervisor. | Only for a foreground debug session. |
| `pixi run test` | 362 unit tests. | Before any restart, after any edit. Green is the floor. |
| `pixi run case-0` | The permanent test Game — a dry run that costs nothing. | To sanity-check a change without waiting for a real Game. |
| `pixi run cases` | Unzips every Case whose key has been released. | Rarely — `watch` already does it every poll. |
| `pixi run learn` | Re-reads older Games by hand, e.g. `--games 26-33`. | After changing the analysis and wanting the old Games re-scored. |
| `pixi run review-game 33` | Re-runs the Claude review of one Game. | After editing the review prompt. |

**The one rule that bites:** a restart is what makes a change live. `.env`, `LLM_TIMEOUT_SECONDS`, the pricing constants and the Price Memory store are all read into the process at start-up. Editing a file changes nothing until `play` is restarted — do it in the gap between two Games, never in the sixty seconds after one begins.

Process the permanent test game directly:

```bash
pixi run case-0
```

The watcher polls every two seconds. A short retry handles a key endpoint that is
a fraction late. Keys are never printed or stored.
