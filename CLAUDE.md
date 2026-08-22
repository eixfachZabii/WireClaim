# WireClaim — CLAUDE.md

Agent knowledge file. Rules, conventions, and the mistakes we already paid for.

- [`README.md`](README.md) — the game, the verified schedule, and the fifteen derived results (R1–R10). **The source of truth for anything about how the tournament works.**
- [`CONTEXT.md`](CONTEXT.md) — the ubiquitous language. Use these words; they were chosen to stop the drift that was already happening on day one.
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

**So: before you act on a claim about this game, check whether `README.md` already proves it. If it doesn't, write the arithmetic down and run it.** `docs/brainstorm/sebi/evidence/sim.py` exists solely because it caught three errors that had already been written down as fact. A claim without a number behind it is a guess wearing a suit.

---

## Hard rules

**1. The default submission is an incident, never a fallback.** `a = 0, b = 0` does not score zero — `b = 0` wrongfully rejects every fair claim, so we pay `1.5a` to every opponent on every Line Item (R7). A team that goes dark becomes a **money fountain** for everyone awake: `+t` to them, `−1.5t` to us, per item, per Game (R10). Any plausible number beats the default. If the pipeline has nothing, it still submits something.

**2. The model reads; the engine prices.** [ADR 0001](docs/brainstorm/sebi/adr/0001-the-model-reads-the-engine-prices.md). No agent emits a Charge, a Limit, or a Fair Value — agents emit _structured evidence_ (coverage verdict + the policy clause quoted verbatim, relatedness, quantity/unit/trade, a price **band with named anchors**), and deterministic code turns evidence into a posterior and the posterior into numbers. This is SampleRepo's ADR 0021 applied where it matters more: there an unanchored model verdict was one word on a card; here it is the number we are scored on, 100 times, unattended. _Two regenerates over one invoice must not disagree._

**3. Spend the effort on the Charge, not the Limit.** The Limit is nearly flat anywhere in the bottom third of the posterior (`Q₀.₀₅`–`Q₀.₃₃` differ by ~2 % of net). The Charge is ~3× more sensitive and its optimum moves with the tournament phase. Get `b` into the bottom third and stop touching it (R6).

**4. What we need is a distribution, not a number.** The score depends on the _width_ of the posterior, not just its centre — `Q₁ᐟ₃` is only safe if the interval is calibrated (R4b). A model asked for "a fair price" returns a point; a model asked for "a price and an interval" returns a point and a fabricated interval. The width has to come from somewhere real — disagreement between framings, and calibration against settled Games.

**5. On items the policy does not cover, always Charge.** `t = 0`, so the honest branch pays exactly zero and a rejected overcharge costs nothing. Break-even is `p > 0`, not 25 % — charging is weakly dominant in every phase, including overnight (R6c). But drive it from an explicit coverage _probability_, not a binary guess: if the item turns out covered, a high Charge forfeits guaranteed income.

**6. Always gross, always the whole Line Item.** The handout warns twice, in bold. Never net (a factor of 1.19), never per-unit (a factor of the quantity, often 10–30×). This is the most likely way for a working pipeline to silently score nothing.

**7. Uptime outranks accuracy.** Break-even uptime is **71 %** — an all-or-nothing smart bot needs that much merely to tie a dumb bot that never misses. Rescuing one Game is worth `93t`; improving one Game is worth `37t`. **Showing up is 2.5× being right.** Two-phase submit (cheap at T+3 s, smart overwrite at T+50 s, merged _per Line Item_ so partial output is never discarded) is worth more than five points of uptime, for about forty lines of code.

**8. The tournament has three regimes, and the right play differs in each.** Games ~1–43 the Field is awake and probably generous (measure `p`, Limit discipline matters most); ~44–81 it is mostly dark (honest harvest — accuracy is the only lever, and overcharging earns nothing against `b = 0`); ~82–100 it wakes recalibrated. Never carry a `p` estimate across a phase boundary.

---

## Fair play — the line, and which side we sit on

Allowed: any tooling, LLMs, manual work, domain research, anything inside our own team. Forbidden and disqualifying: cross-team coordination, sharing or using another team's key, obtaining decryption keys before release, reading other teams' unsettled submissions, and probing or overloading the API.

**The open question is R9.** The public leaderboard publishes settled Transactions (`line_item_index, issuer, reviewer, accepted, amount`), which invert to bracket the Fair Value and reconstruct every opponent's Limit. The handout explicitly points us at the leaderboard, and inference from published results is not the same as "extracting the secret thresholds" — but it is close enough to the line that **we ask in `#❓-ask-orgateam` before building on it.** The rules say to ask when unsure. If the answer is no, R1–R8 stand untouched and self-calibration on our own settled results is unaffected.

Read the leaderboard at the rate a browser would. Do not enumerate endpoints that the leaderboard page itself does not call.

---

## Conventions

- **Vocabulary is not optional.** Charge / Limit / Fair Value / Estimate / Line Item / Case / Game / Issuer / Reviewer / Price Memory / Field. See [`CONTEXT.md`](CONTEXT.md). "Track" always means a Strategy Track — the hackathon's QuantCo/Viktor/Cognition tracks are **Challenges**.
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
