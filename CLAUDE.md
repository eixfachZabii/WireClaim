# WireClaim — CLAUDE.md

Agent knowledge file. Rules, conventions, and the mistakes we already paid for.

- [`docs/GAME-AND-PROOFS.md`](docs/GAME-AND-PROOFS.md) — the game, the verified schedule, and the fifteen derived results (R1–R10). **The source of truth for anything about how the tournament works.** (This was `README.md` until the README became the judge-facing map.)
- [`README.md`](README.md) — the judge-facing entry point: what to read, in what order, and where every file lives. Navigation only; it proves nothing.
- [`CONTEXT.md`](docs/CONTEXT.md) — the ubiquitous language. Use these words; they were chosen to stop the drift that was already happening on day one.
- [`docs/brainstorm/sebi/INDEX.md`](docs/brainstorm/sebi/INDEX.md) — what was pitched, what was picked, who owns what.
- [`docs/POSTMORTEM.md`](docs/POSTMORTEM.md) — **start here if you are picking this up after the tournament.** Where the money went over all 100 Games, what the counterfactuals prove, and the fully re-scored standings. Invocable as `/handoff`.
- [`docs/handoffs/done/Version1.0/ORCHESTRATOR.md`](docs/handoffs/done/Version1.0/ORCHESTRATOR.md) — the archived mid-tournament handoff. Its standings are a Game-62 snapshot and are stale; §3's seven measured-and-closed proposals are not, and are worth reading before reopening any of them.

---

## Project at a glance

**WireClaim** is our entry to QuantCo's _Claim to Fame_ challenge at the Munich Agentic Hackathon (EHL stop #3, 22–23 Aug 2026). Every ~12.6 minutes a Case is released; we have **60 seconds** to decrypt it, read an insurance policy, a damage description and an invoice with no prices, and submit two numbers per Line Item — a **Charge** (what we invoice every other team) and a **Limit** (the most we will pay when invoiced the same item). Behind each Line Item is a secret **Fair Value** `t` and a secret **Cap** `c ≥ 4t`.

- **100 Games**, Sat 15:00:00 → Sun 11:50:00 CEST, exactly `757.575758 s` apart
- **Submission deadline Sun 12:00**, pitch Sun 12:30 (5 min + 3 min jury Q&A)
- **Score:** `net = income as Issuer − costs as Reviewer`, summed over every ordered pair of teams
- **Judged on the leaderboard _and_ the methodology write-up** — "your methodology also counts (style)"
- Submissions are **rejected if we don't use Entire**; challenge selection and final submission both on `ehl.gg`

---

## The most important rule — the arithmetic is derived, do not re-derive it by intuition

Every single time someone reasoned about this game from intuition, they got it wrong, and the errors were not small. All of these were _stated confidently_ before being falsified:

| The intuition                                                       | What it actually is                                                                                                                 | How much it cost                                   |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| "Charge at the fair value — below `t` income is risk-free."         | Risk-free **conditional on `a ≤ t`**. Charging at the median forfeits the claim half the time. **`a* ≈ 0.7 × t̂`** (R5b).            | Three independent methods needed to settle it.     |
| "Put `b` in the upper half of the confidence interval as a buffer." | Backwards. Generosity is ~8× more expensive than strictness (`4t` vs `0.5t`). The buffer goes **down** (R4, R6).                    | Would have handed the Cap to every exploiter.      |
| "Estimate how many opponents accept an overcharge, then exploit."   | A **mis-measured** `p(a)` is worse than assuming `p = 0` (R5c).                                                                     | **60 % of net** in simulation; dropped 1st → 11th. |
| "Above the Cap the acceptance bar rises, so never accept."          | The bar _falls_ (`q > c/(c+0.5a)`). Right conclusion, wrong reason — reject because `c ≥ 4t` makes it **provably** fraudulent (R4). | A wrong reason in a shared doc propagates.         |
| "`t̂` is systematically too low on expensive items, so raise it."                  | A **regression artefact**, and it cost eight experiments. Bucketing `t̂/t` by the *true* `t` shows 0.92 in the 400–1,000 band and 1.54 under 50 — items land in a high-`t` bucket partly *because* we underestimated them. Bucket by **`t̂`**, the only split knowable at submission time, and the sign flips: 1.12 at 400–1,000 and 1.11 above 1,000. The "below the proven floor on 73 % of censored items" figure is the same trap: "censored" means nobody rightfully rejected, which is a selection on the outcome. Never condition on the answer. **And that last sentence indicts this row's own conclusion, which was measured post-tournament and is wrong too.** Every ratio above is scored on *bounded* brackets — the sub-population where somebody rightfully rejected, i.e. where the Field overestimated. The 189 right-censored Line Items point the other way: `t ≥ 1.044 × t̂`, and **60.8 % of them are provably worth more than our estimate**. Fitting all 531 as interval-censored data (`src/pricing/calibration.py`, Turnbull's NPMLE) puts the median `t / t̂` at **0.982** — **there is no level error in either direction; we were unbiased the whole time.** The real failures are a handful of individually-diagnosable misses (Game 41's watch: Price Memory matched "compensation for robbery damage" to an unrelated €3,011 claim and pulled a correct 18,000 read down to 5,524), not a level to correct. |
| "The Limit should sit **above** `t̂`, so we never pay the lawyer."                | Right about the target, wrong about the action, and it flips on one substitution. Sweeping `b = m · t` against the **true** `t` gives a V with its minimum at exactly `m = 1.00` — `b = t`, costing more in both directions. Sweeping `b = m · t̂` against **our estimate** turns that V into a monotone increase whose cheapest point is as low as you can push it. **The flip between those two curves is the cost of our estimation error.** Also: rejecting a *fraudulent* claim is free — the `1.5×` only ever fires on a claim that was fair. **The sentence that used to stand here — "so a high `b` buys no protection from the lawyer at all, it only converts zeros into payments" — was itself wrong, and is the fourth intuition in this table to be falsified.** Raising `b` to admit a claim that *was* fair converts a `1.5a` penalty into an `a` payment and **saves `0.5a`**; only on an Overcharge does it convert a zero into a payment. Which effect dominates is exactly R4's `q > 2/3` test, not a blanket "push `b` down". The V-curve above is still the reason `b` sits low — our estimate is noisy — but the reason is estimation error, not an absence of lawyer protection. Measured: the field charges a median of **0.73 × `t`**, and 26 % of its Charges on real-money items are still above `t`. |
| "`a = t = b` is optimal."                                           | **Exactly right under certainty — now measured, not argued (R11).** Sweeping the oracle over 99 Games, `a = t` and `b = t` are both the argmax. But the two fail in wildly different shapes: the Charge is a **cliff** (`a = 1.01·t` costs **−6,038,602**), the Limit a gentle asymmetric valley (1 % low −113,527, 1 % high −5,403). That asymmetry *is* why `a = 0.7·t̂` beats `a = t̂` the moment `t̂ ≠ t`. | The correction that replaced it (`a > b`) was the real error. |

**So: before you act on a claim about this game, check whether `docs/GAME-AND-PROOFS.md` already proves it. If it doesn't, write the arithmetic down and run it.** Three claims in the table above were written down as fact before a simulation falsified them. A claim without a number behind it is a guess wearing a suit.

---

## Hard rules

**1. The default submission is an incident, never a fallback.** `a = 0, b = 0` does not score zero — `b = 0` wrongfully rejects every fair claim, so we pay `1.5a` to every opponent on every Line Item (R7). A team that goes dark becomes a **money fountain** for everyone awake: `+t` to them, `−1.5t` to us, per item, per Game (R10). Any plausible number beats the default. If the pipeline has nothing, it still submits something.

**1a. Never commit claim data, and never commit anything derived that reproduces it.** The
repository is public and the organisers attach a **ranking penalty** to checking in their invoice
PDFs or policies. The Cases are ignored, and so are four derived paths that carry the same content:
`var/ai_log/` (raw model replies — the `clause` field quotes `policy.txt` verbatim, and 805 of them
were once tracked), `var/reviews/`, `var/decisions/` and `var/lessons/` (invoice Line Item names),
plus `var/export/`. All of them stay on disk and regenerate with `pixi run watch` / `pixi run
export`, so the learning loop is unaffected. Two things to know if you are auditing this: a scan for
`"clause"` in the parsed JSON returns **zero** because the clause sits inside an escaped `reply`
string — search for real policy sentences instead — and `git rm --cached` alone is not enough,
because history is exactly what a public repository exposes.

**1b. The learning loop runs itself. Two terminals, two commands, for the whole tournament.**

```bash
set -a && . .env && set +a          # once per terminal
pixi run play                       # terminal 1: plays every Game on the schedule, restarts itself if it dies
pixi run watch                      # terminal 2: analyses each Game as it settles
```

**Use `play`, not `start`, for terminal 1.** `watch_games()` has no exception boundary, so an
uncaught error there ends the whole tournament rather than costing one Game; `scripts/supervise.sh`
(what `play` runs) turns that back into "restart and lose at most one Game." `pixi run start` is
still there for a foreground debug session, never for an unattended stretch.

**`watch` already does `cases` and `learn`** — every poll it runs `extract_cases`, then
`learn_from_game` for the newly settled Games, then the Claude review of the digest
(`scripts/learn_watch.py`). So the digest `watch` prints *is* the learn digest. Do not run
them by hand expecting something extra; there isn't any.

The other tasks are for doing something off the loop, not for the loop:

| task | when you actually need it |
| --- | --- |
| `pixi run learn` | re-read older Games by hand, e.g. `--games 26-33` after changing the analysis |
| `pixi run cases` | top up the extraction without waiting for a poll |
| `pixi run review-game 33` | re-run the Claude review of one Game after editing its prompt |
| `pixi run case-0` | the permanent test Game, for a dry run |
| `pixi run test` | the unit tests |

`pixi run learn` joins the **decision log** Strategy 2 writes at submission time
(`var/decisions/game_NNN.json`) against the reconstructed Fair Value, and names *the stage
that was wrong* rather than the amount that was lost. If it reports **"No decision log for
this Game"**, stop: that means Strategy 2 did not land, and nothing else in the report can be
interpreted until you know why. Games 21–24 submitted a Limit of 35 on every Line Item —
`STANDARD_LIMIT`, from a lower layer — and an hour went into inferring what one log line now
says outright.

Then follow the **`learn-from-runs`** skill (`.devin/skills/learn-from-runs/`): attribute to a
stage, add the evidence to
[`hypothesis-ledger.md`](docs/brainstorm/sebi/strats/review/hypothesis-ledger.md), and change
**at most one thing** — validated across *every* settled Game, never on the strength of the
Game that just settled. One Game is far inside the **26,622** noise floor.

**2. Before anything else, unzip and read the new Cases.** `pixi run start` now does this
first (`pixi run cases`), because the runner extracts to `var/cases/` and used to leave the
readable copy several Games behind. Decryption keys never expire
and every Game whose `start_time` has passed is readable, so at the start of any session —
and before any analysis, any strategy claim, any prompt change — top up the extraction and
look at what is actually in there:

```bash
cd "[PUBLIC] EHL Cases/cases"          # archives are all committed; only the key is gated
for g in $(seq 0 100); do d=case_$(printf %02d $g)
  K=$(curl -s -H "X-API-Key: $TEAM_API_KEY" \
      "https://c2f.public.quantco.cloud/api/games/$g/key" | jq -r .decryption_key)
  [ "$K" = null ] && break
  7z x -y -p"$K" -o"$d" "$d.zip" >/dev/null && echo "$d"
done
```

Every claim in this repo that survived contact with reality came from reading a Case or a
settled Game; every claim that died came from reasoning about the rules in the abstract.
Case 3 being *entirely uncovered*, the Line Items that name their own disqualifier, and
betterment being a partial haircut rather than a binary — none of that was guessable.
Extracted folders are gitignored; they are derivable from the archive plus a key.

**Never judge our algorithm, or a Game's result, from the numbers alone. Open the Case.**
Leaderboard inversion tells you *what* happened; only the Case tells you *why*, and the two
routinely disagree:

- Game 5 read from our own Transaction rows said the Line Items we charged 0 on were
  uncovered. Pulling five teams' rows and reading the Case showed they were covered and
  worth hundreds — item 3 sat in `[497.94, 773.50)`. The diagnosis reversed completely.
- ~~Case 7's brackets alone suggest the kitchen air-conditioning unit was excluded. The Case
  says the opposite: the description dangles *"a couple of metres from the hob"* as bait,
  and the policy states that proximity to another appliance **does not** remove cover.~~
  **Falsified — and the way it was falsified is the lesson.** Reconstructing the Fair Value
  from settled Transactions puts Case 7 item 2 at **`t ∈ [0, 81)`** against `[1233, 1756)`
  for the identical living-room unit. The kitchen unit really was excluded; it was never
  paid. The claim above came from reading the policy and stopping there, which is the same
  error in the opposite direction: *a reading is not an outcome.* The general rule — that
  only a quoted clause is evidence, never a detail in the description — still stands, but
  this Case is no longer the example for it. Where the settled Fair Value exists, it
  outranks anyone's reading of the policy, including this file's.

A number without its Case is a symptom without a diagnosis. Read `policy.txt`,
`description.txt` and the invoice before concluding anything about why a Game went the way
it did — and quote the clause when you do.

**3. The model reads; the engine prices.** [ADR 0001](docs/brainstorm/sebi/adr/0001-the-model-reads-the-engine-prices.md). No agent emits a Charge, a Limit, or a Fair Value — agents emit _structured evidence_ (coverage verdict + the policy clause quoted verbatim, relatedness, quantity/unit/trade, a price **band with named anchors**), and deterministic code turns evidence into a posterior and the posterior into numbers. This is SampleRepo's ADR 0021 applied where it matters more: there an unanchored model verdict was one word on a card; here it is the number we are scored on, 100 times, unattended. _Two regenerates over one invoice must not disagree._

**4. Get the Limit inside the posterior before you tune anything else.** R6 says the Limit is flat anywhere in the bottom third (`Q₀.₀₅`–`Q₀.₃₃` differ by ~2 % of net) and the Charge is ~3× more sensitive — **but that only holds once `b` is inside the posterior at all.** In Game 5 ours was not: we accepted 246 of 272 Transactions, **99 % of our costs came from accepting**, and we paid 1,121.40 on a Line Item whose Fair Value was under 773.50. Net −10,604. A Limit outside the posterior is not a flat knob, it is an open tap. Close it, *then* apply R6 and spend the effort on the Charge.

**5. What we need is a distribution, not a number.** The score depends on the _width_ of the posterior, not just its centre — `Q₁ᐟ₃` is only safe if the interval is calibrated (R4b). A model asked for "a fair price" returns a point; a model asked for "a price and an interval" returns a point and a fabricated interval. The width has to come from somewhere real — disagreement between framings, and calibration against settled Games.

**6. On items the policy does not cover, always Charge.** `t = 0`, so the honest branch pays exactly zero and a rejected overcharge costs nothing. Break-even is `p > 0`, not 25 % — charging is weakly dominant in every phase, including overnight (R6c). But drive it from an explicit coverage _probability_, not a binary guess: if the item turns out covered, a high Charge forfeits guaranteed income.

**7. Always gross, always the whole Line Item.** The handout warns twice, in bold. Never net (a factor of 1.19), never per-unit (a factor of the quantity, often 10–30×). This is the most likely way for a working pipeline to silently score nothing.

**8. Uptime outranks accuracy.** Break-even uptime is **71 %** — an all-or-nothing smart bot needs that much merely to tie a dumb bot that never misses. Rescuing one Game is worth `93t`; improving one Game is worth `37t`. **Showing up is 2.5× being right.** Two-phase submit (cheap at T+3 s, smart overwrite at T+50 s, merged _per Line Item_ so partial output is never discarded) is worth more than five points of uptime, for about forty lines of code.

**9. The tournament has three regimes, and the right play differs in each.** Games ~1–43 the Field is awake and probably generous (measure `p`, Limit discipline matters most); ~44–81 it is mostly dark (honest harvest — accuracy is the only lever, and overcharging earns nothing against `b = 0`); ~82–100 it wakes recalibrated. Never carry a `p` estimate across a phase boundary.

---

**10. Re-measure after every Game, and never tune a knob whose error you have not measured.** The Fair Value is **exactly recoverable** from settled Games: a rejected Transaction carrying a non-zero `amount` is a wrongful rejection, so it reveals the Charge *and* proves `a ≤ t`, while a rejected Transaction at `0` proves `a > t`. `scripts/invert_fair_values.py --verify` reproduces all published nets to the cent, so there is ground truth for every Line Item we have ever played.

That makes one number the gate on everything: **σ, the log error of our Fair Value estimate.**

**Re-measured over all 100 settled Games** (`scripts/experiments/price_of_sigma.py`), perturbing the *true* Fair Value by a lognormal of known width and letting the Limit move with the estimate:

| σ | 0.00 | 0.20 | 0.30 | 0.45 | 0.60 | 0.75 | 0.90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| weighted net | 2,324,912 | 1,814,964 | 1,264,589 | 396,211 | −155,324 | −604,370 | −1,013,234 |

**Break-even is σ ≈ 0.57, not 0.85** — the 0.85 figure came from Games 1–14 with a fixed Limit and is superseded. Our real submission (+224,840 weighted) sits at an **effective σ ≈ 0.52**, i.e. barely the right side of it. Price Memory measures **0.458** over the full record and clears it; a blind constant does not.

The steepest segment is the one adjacent to where we stand: **σ 0.45 → 0.30 is worth +868,378**, roughly **5.8 M weighted per unit of log error**. Price any evidence-layer proposal against that curve before building it. The same harness shows `a = 0.7·t̂` beating `a = t̂` at every σ ≥ 0.1 — R5b confirmed on a validated harness rather than argued, and §R11 below explains *why* the discount has to be that deep.

Three traps in measuring it. **Use total log error (RMSLE), not standard deviation** — a stdev cannot see a level error. **Earlier crossings are superseded**: "σ ≈ 0.35" came from a model that proxied `t` with the field's median Charge, "σ ≈ 0.85" from Games 1–14 with a fixed Limit; **0.57 is the measured crossing over 100 Games**. And above all, **fit the residual with the censored observations in** — see the bias row in the table above. Scoring only on bounded Fair Value brackets says we overestimate by 19 %; handling the censoring says we are unbiased, and the whole "median `a/t` was 1.06 when it should be ~0.7" diagnosis was an artefact of the same selection.

So after every settled Game, recompute and record: **σ** (overall and per channel), the coverage confusion against the true `t = 0` set, income vs. the two cost sides, and the accept share. Append it to `field-findings.md`. Three specific risks stay open and must be watched rather than assumed away:

- **σ is measured on a censored sample.** 44 of 192 items have no upper bracket — nobody rightfully rejected them — and those are plausibly the expensive ones. Treat every σ we quote as **optimistic**.
- **The Cap `c` has never bound** in 52,224 settled rows, so we only know `c > max observed accepted amount`. Any plan leaning on large Charges extrapolates past the data.
- **Regime change** (rule 9): a field measurement does not survive a phase boundary. Re-measure, do not carry it over.

**And page to the end of every API list.** `/transactions` paginates at 100 rows; page one of a 544-row Game reads exactly like a 4-item Case. That single mistake produced a wrong Line Item count, a wrong fraud denominator and a wrong blind-floor range before anyone noticed.

## Fair play — the line, and which side we sit on

Allowed: any tooling, LLMs, manual work, domain research, anything inside our own team. Forbidden and disqualifying: cross-team coordination, sharing or using another team's key, obtaining decryption keys before release, reading other teams' unsettled submissions, and probing or overloading the API.

**R9 is settled: we asked, and it is allowed.** The public leaderboard publishes
settled Transactions (`line_item_index, issuer, reviewer, accepted, amount`), which
invert to bracket the Fair Value and reconstruct every opponent's Limit. Inference from
published results is not "extracting the secret thresholds", and the organisers
confirmed it. Build on it.

Read the leaderboard at the rate a browser would. Do not enumerate endpoints that the leaderboard page itself does not call.

---

## Conventions

- **Vocabulary is not optional.** Charge / Limit / Fair Value / Estimate / Line Item / Case / Game / Issuer / Reviewer / Price Memory / Field. See [`CONTEXT.md`](docs/CONTEXT.md). "Track" always means a Strategy Track — the hackathon's QuantCo/Viktor/Cognition tracks are **Challenges**.
- **Say "Overcharge", not "fraud".** A Charge above Fair Value is a priced bet with a known expected value, and the write-up has to describe it that way to a judge who sells insurance software.
- **Never commit `TEAM_API_KEY`.** It lets anyone trade on our behalf. `.gitignore` covers `.env`, `*.key` and `secrets/`; keep it that way.
- **Ideas go in `docs/brainstorm/<member>/`,** one folder each. `docs/GAME-AND-PROOFS.md` changes only when we learn something about the rules or prove a new result — it is shared understanding, not a scratchpad. `README.md` changes only when the repo's shape changes, because it is what a judge reads first.
- **ADRs are for decisions that are hard to reverse, surprising without context, and the result of a real trade-off.** All three, or it is not an ADR.
- **When you correct something, correct it at the source.** Every wrong claim in the table above was fixed in `docs/GAME-AND-PROOFS.md` itself, with the correction recorded. A stale doc is worse than no doc, because someone will build on it at 04:00.

---

## Status

**The tournament is over. All 100 Games are settled and we finished 5th of 17 on
+238,255.07.** The full record is archived and verified in
[`data/tournament/`](data/tournament/standings.md) — per-Game nets for every team,
reconstructed from 315,792 settled Transactions and agreeing with the published leaderboard
**to the cent** for all seventeen teams (`scripts/archive_tournament.py`). Games 81–100 pay
**3×**; that weighting is not in any handout, it is the unique factor that makes the rows
reproduce the totals.

The post-mortem is [`docs/POSTMORTEM.md`](docs/POSTMORTEM.md), and the measurements behind it
are H21–H25 in the
[hypothesis ledger](docs/brainstorm/sebi/strats/review/hypothesis-ledger.md). The one sentence
worth carrying forward:

> **Games 1–25 cost −322,595 weighted. Games 26–100 earned +560,850.** The tournament was
> decided before the strategy was finished.

Everything the old version of this section called unimplemented — invoice parsing, policy
analysis, pricing, submission — shipped long ago; there is no `TODO(api-submission)` boundary
any more.

What runs, in the order a Game touches it:

| layer | where | what it decides |
| --- | --- | --- |
| schedule + Case load | `main.py`, `src/data/` | unzip, parse the invoice, slice the Policy |
| evidence | `src/strategies/strategy2/{prompts,model,channels}.py`, `src/evidence/policy/` | coverage probability, a price band, the clause quoted verbatim |
| blend | `src/strategies/strategy2/blend.py` | two model draws + the Price Memory anchor, inverse-variance in log space |
| pricing | `src/pricing/engine.py` | the Charge and the Limit — the only place a scored number is decided |
| submission | `src/api/`, `src/runtime/submission_coordinator.py` | four sequenced posts per Game, merged per Line Item |
| learning | `scripts/learn_*.py`, `scripts/replay_payoffs.py`, `src/runtime/` | decision log × recovered Fair Value → the stage that was wrong |

Three strategies price every Case and a router picks one; `strategy2` wins most Games.
`scripts/replay_payoffs.py` reproduces every published net to the cent, so any proposed
change is a **measurement** rather than an argument — use it before touching a constant.

Running it needs `TEAM_API_KEY`, the Azure keys, the Case archives and the Pixi environment
described in `README.md`.

**Where the money still is — settled over all 100 Games, not 33.** Four rungs, weighted
(`scripts/experiments/ceiling.py`):

| rung | net |
| --- | ---: |
| default `a = 0, b = 0` | −3,737,366 |
| **what we submitted** | **224,840** |
| best constant `(α, β)` anywhere in a 72-cell grid on our own `t̂` | 109,248 |
| oracle `a = b = t` | 4,488,842 |

**The best constant-only strategy scores 115,593 _worse_ than what we shipped.** So of
everything above ACTUAL, **103 % is estimation and −3 % is decision rules**. This is no longer
"the decision rules are near their optimum"; it is that a global multiplier can only make them
worse, because the shipped rule already varies its factor with the band. **Do not open another
constant sweep** — H21, and H2/H13/H16/H24 are four more already falsified with numbers.

**What accuracy is worth, so a proposal can be priced before it is built** (H22). Perturbing
the true Fair Value by a known lognormal and replaying puts our real submission at an
**effective σ ≈ 0.52**, with net crossing zero at σ ≈ 0.57. The curve is steepest exactly where
we stand: **σ 0.45 → 0.30 is worth +868,378**, about **5.8 M weighted per unit of log error**.
Estimate the σ your change buys and read the euros off `price_of_sigma.py`.

**And one trap, which has now caught this repository five times** (H23). Every residual scored
on *bounded* Fair Value brackets is scored on the sub-population where somebody rightfully
rejected — a selection on the outcome. It says we overestimate by 19 %; fitting the same data
as interval-censored (`src/pricing/calibration.py`) says the median `t / t̂` is **0.982** and we
were essentially unbiased all along. **Before correcting a level error, fit the residual with
the censored observations in.**
