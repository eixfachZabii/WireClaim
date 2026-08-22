# WireClaim — CLAUDE.md

Agent knowledge file. Rules, conventions, and the mistakes we already paid for.

- [`README.md`](README.md) — the game, the verified schedule, and the fifteen derived results (R1–R10). **The source of truth for anything about how the tournament works.**
- [`CONTEXT.md`](docs/CONTEXT.md) — the ubiquitous language. Use these words; they were chosen to stop the drift that was already happening on day one.
- [`docs/brainstorm/sebi/INDEX.md`](docs/brainstorm/sebi/INDEX.md) — what was pitched, what was picked, who owns what.

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
| "`a = t = b` is optimal."                                           | Only under certainty. But closer than the "therefore `a > b`" correction that replaced it — both sit low, near each other (R6).     | An over-confident correction is still an error.    |

**So: before you act on a claim about this game, check whether `README.md` already proves it. If it doesn't, write the arithmetic down and run it.** Three claims in the table above were written down as fact before a simulation falsified them. A claim without a number behind it is a guess wearing a suit.

---

## Hard rules

**1. The default submission is an incident, never a fallback.** `a = 0, b = 0` does not score zero — `b = 0` wrongfully rejects every fair claim, so we pay `1.5a` to every opponent on every Line Item (R7). A team that goes dark becomes a **money fountain** for everyone awake: `+t` to them, `−1.5t` to us, per item, per Game (R10). Any plausible number beats the default. If the pipeline has nothing, it still submits something.

**1b. The learning loop runs itself. Two terminals, two commands, for the whole tournament.**

```bash
set -a && . .env && set +a          # once per terminal
pixi run start                      # terminal 1: plays every Game on the schedule
pixi run watch                      # terminal 2: analyses each Game as it settles
```

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

That makes one number the gate on everything: **σ, the log error of our Fair Value estimate.** Replaying the real payoff table over Games 1–14 with `a = 0.7·t̂` gives **+131,497 at σ = 0.35, +89,807 at 0.5, +31,725 at 0.75 and −20,915 at 1.0**, so **break-even is σ ≈ 0.85**. Price Memory measures 0.43 and clears it; a blind constant does not. The same sweep shows `a = 0.7·t̂` beating `a = t̂` at every σ ≥ 0.1, which is R5b confirmed on a validated harness rather than argued.

Two traps in measuring it. **Use total log error (RMSLE), not standard deviation** — a stdev cannot see a level error, and our failure mode is precisely a *bias*: median `a/t` was 1.06 when it should be ~0.7. And **an earlier "break-even σ ≈ 0.35" was from a cruder model** that proxied `t` with the field's median Charge and credited nothing for Overcharges; treat 0.35 as a target and 0.85 as the crossing.

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
- **Ideas go in `docs/brainstorm/<member>/`,** one folder each. `README.md` changes only when we learn something about the rules or prove a new result — it is shared understanding, not a scratchpad.
- **ADRs are for decisions that are hard to reverse, surprising without context, and the result of a real trade-off.** All three, or it is not an ADR.
- **When you correct something, correct it at the source.** Every wrong claim in the table above was fixed in `README.md` itself, with the correction recorded. A stale doc is worse than no doc, because someone will build on it at 04:00.

---

## Status

The repository now contains a tested Python case-ingestion runner in `main.py`
with a small read-only API client in `src/api.py`. `pixi run start` watches the
published schedule; `pixi run case-0` processes the permanent test game. The
game analysis, glossary, five strategy pitches (~4,150 lines) under
`docs/brainstorm/sebi/`, and one ADR remain the source of strategy and domain
decisions.

**Still unimplemented:** invoice parsing, policy analysis, pricing, and submission;
the boundary is marked with `TODO(api-submission)` in `src/api.py`. Running the
runner requires `TEAM_API_KEY`, the case archives, and the Pixi environment
described in `README.md`.
