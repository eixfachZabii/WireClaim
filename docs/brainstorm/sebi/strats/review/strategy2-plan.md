# Strategy 2 — the full process, front to back

Written Sat ~18:45 CEST after grilling the design against Games 1–14. This is the strategy
that replaces Strategy 1 and Strategy 3. Every number below is measured; where something
is still unmeasured it says so.

Read [`report.md`](report.md) for the standing and the loss accounting, and
[`t-inversion.md`](t-inversion.md) for the reconstruction the numbers come from.

---

## 0. The two facts that determine the whole design

**Fact 1 — the income cliff.** As Issuer, a Charge at or below `t` is paid by **every**
opponent, because a wrongful rejection still owes us `a`. One euro above `t` and the only
buyers are the few teams whose Limit is loose. Measured on our own settled Charges:

| our `a/t` | opponents who pay | expected income |
| --- | ---: | ---: |
| ≤ 1.0 | **all 16** | **1.00 × t** |
| 1.0–1.3 | 17 % | 0.20 × t |
| 1.3–2.0 | 7 % | 0.15 × t |
| > 2.0 | ~10 % | 0.17–0.30 × t |

Overcharging forfeits ~80 % of income. **We never overcharge deliberately.** The leaders'
`a/t` p75 above 1 is the upper tail of their estimate noise, not an exploit.

**Fact 2 — accuracy is the only lever.** Simulating `a = β·t̂`, `b = α·t̂` with
`t̂ = t·lognormal(σ)` against the real Charges:

| σ | net per transaction |
| ---: | ---: |
| 0.25 | **+18** |
| 0.35 | ≈ 0 |
| 0.50 | −14 |
| 0.75 | −33 |

**Break-even is σ ≈ 0.35.** A blind constant is σ ≈ 1.12. A perfect per-item Limit costs
65.0 per transaction against 97.5 for rejecting everything and 195.7 for accepting
everything — so no constant recovers any of the prize, and tuning multipliers without
first fixing σ is theatre. **σ is the acceptance gate for this strategy.**

---

## 1. Pricing: one posterior, two quantiles

The engine builds **one posterior distribution over `t` per Line Item** and reads both
numbers off it. Coverage uncertainty is not a separate branch — it is **probability mass
at zero**.

```
posterior(t)  =  (1 - p_covered) · δ(0)  +  p_covered · Lognormal(median = t̂, σ)
```

### The Limit is the 1/3 quantile — derived, not asserted

Accepting a Charge costs `a`. Rejecting it costs `1.5a` **only if it was fair**, and
nothing otherwise. So accept iff

```
a  <  1.5a · P(fair)      ->      accept iff P(fair) > 2/3
```

Therefore **`b = Q₁ᐟ₃(posterior)`**. This is README R6's "bottom third" with a proof
attached, and coverage falls out for free: if `p_covered < 2/3` the 1/3 quantile *is* zero,
so `b = 0` automatically with no threshold or special case.

Then shade it down once more, because the Cap makes an accepted Overcharge cost up to
`min(a, c)` with `c ≥ 4t`, which the 2/3 rule above ignores. Empirically the best `α` is
**0.5–0.7 of the median** at σ = 0.25–0.5. Ship `b = min(Q₁ᐟ₃, 0.6·t̂)`.

### The Charge maximises `k · P(t ≥ k·t̂)`

Directly from Fact 1. On the settled distribution this peaks at **β ≈ 0.7** for σ = 0.25
and **0.6** for σ = 0.5, so the Charge is *also* a low quantile of the same posterior —
just a higher one than the Limit. Invariant: **`b < a`**, which is what the leaders do
(`a/t ≈ 0.73–0.85`, `b/t ≈ 0.48–0.81`).

### Uncovered items are a free option

`t = 0` ⇒ any Charge is above `t`, so the honest branch pays nothing and a rejected
Overcharge costs nothing (R6c). **Charge a plausible price anyway** — in Game 3, where
every item was uncovered, two teams charged ~100 and were paid by 2 of 16 while the rest
of the field scored 0. Plausible, not cap-seeking: the only buyers are teams that
mis-classified the item as covered, so their Limit is set for a realistic price.

| verdict | `a` | `b` |
| --- | --- | --- |
| covered, confident | `0.7 · t̂` | `min(Q₁ᐟ₃, 0.6 · t̂)` |
| covered, doubtful (`p < 2/3`) | `0.7 · t̂` | **0** (falls out of the quantile) |
| uncovered / dash-quantity | plausible price as if covered | **0** |
| betterment (grade) | `0.7 · t̂` at the pre-loss standard | `Q₁ᐟ₃` of that |
| combined position with any excluded element | plausible price | **0** (Case 9 §7.1.10) |

---

## 2. Where `t̂` comes from — three channels, in precedence order

Answering "how do we get `t` without AI": for settled Games, **exactly**, and for live
Games, mostly not — which is why the channels are ranked.

### Channel A — deterministic, free, instant

| signal | evidence |
| --- | --- |
| **`– –` in quantity/unit ⇒ `t = 0`** | **20 of 20** such Line Items across 6 Cases, 17 with a tight upper bound < 40, against a 33 % base rate. Our parser currently *strips* the dashes. |
| **Index = invoice POS number, gaps included** | Case 11's invoice has no POS 12; the settled Game has indices 1–11 and 13–23. Never renumber by row ordinal. |
| **Policy slicer** | All 14 policies share the `PART 1–10` skeleton. Keeping PART 3 (exclusions), 4 (insured property), 5 (insured costs), 7 (indemnity) and 11 keeps **41 %** of the text. **This replaces the 20 s blocking LLM policy digest with zero latency.** |
| **`PART 11` is an answer key** | Present in **6 of 14** Cases: "LOSS DESCRIPTION AND OPERATIVE PROVISIONS FOR THIS CLAIM" enumerates the clauses that decide every line. |
| **Do not scale by quantity across templates** | `corr(log quantity, log Charge) = +0.12`; scaling raised log error 1.12 → 1.32. |

### Channel B — Price Memory, exact where it hits

Settled brackets from `scripts/invert_fair_values.py`. Measured honestly:

- **Recall 23 %** on exact normalised wording (0 % on Case 1, 62 % on Case 14).
- **σ ≈ 0.33 conditioned on both occurrences being covered** — at break-even, so worth
  having, not a silver bullet.
- **7 of 19 repeated wordings flip between `t = 0` and `t > 0`.** "vehicle costs" is `t = 0`
  in Cases 1, 2, 4, 5, 14 and 32–111 in Cases 5, 8, 9, 11, 13. **Memory supplies price
  only. Coverage is always decided from this Case's policy.**
- Within a template, quantity *does* matter: "skilled worker hours" settles at 219, 232,
  754, 986. Store price **per unit** for hour/area/length units, gross total for `pcs`.
- The trade roster is a stable identity key — `7 U-Bend Boulevard, Pipeville` is the
  plumber in Cases 1, 5, 8, 11, 13. Key on `(normalised wording, unit)` with trade as a
  tie-breaker. Cases 11 and 13 share a parts list almost line for line.

### Channel C — the model, for the other 77 %

Highest-quality model, evidence only (ADR 0001: the model reads, the engine prices). It
returns a price **band** and a coverage **probability** with a quoted clause; it never
returns `a`, `b` or `t`. **σ unmeasured — that is what the backtest is for.**

---

## 3. The 60-second timeline

Hard constraint: one minute per claim, and `GET /key` returns 403 before `start_time`.

| when | what | blocking? |
| --- | --- | --- |
| T+0 | blind floor, 40 indices — **already shipped** | no |
| T+0→3 | key fetch, `7z`, PDF parse → `CaseData` | yes, unavoidable |
| T+3 | **deterministic layer publishes**: dash⇒`t=0`, memory hits, settled prior elsewhere | no |
| T+3→25 | **one whole-Case call** on the sliced policy — sees neighbours, so it can catch duplicates, quantity inflation and sub-limit aggregation | no |
| T+3→50 | **per-item calls, fired concurrently with the whole-Case call**, each overwriting only its own item as it lands | no |
| T+50→60 | fraud mask overwrites `b`; final `PUT` | no |

Two rules make this safe:

1. **A real answer exists before any model responds.** The deterministic layer is not a
   placeholder — on dash items and memory hits it is the *best* answer we will get.
2. **Publish per Line Item, never per Case.** One slow item must cost one item. This needs
   a change in `RunManager`: today `set_strategy` replaces a whole `Proposal`, so a
   partial result discards everything else. It needs an **item-wise accumulating layer**.

---

## 4. Division of labour with Markus's detector

Agreed split: **Markus owns the coverage verdict, we own `a`, `b` and `t̂`.** The seam is
one field.

- The detector emits, per Line Item, `p_covered` **and the quoted clause** — not a boolean.
  A probability is what the posterior needs; a boolean throws away exactly the information
  that sets `b`.
- We fold `p_covered` in as mass at zero (§1). Below 2/3 the Limit vanishes on its own.
- The existing `FraudDecision` mask (`b := 0`) stays as a **belt-and-braces override** for
  proven exclusions, with the 35 % allowance and the floor of 2.
- The mask never touches `a` — uncovered items are a free option.
- The detector never blocks the Submission; a late verdict overwrites via `PUT`.

**He can grade himself against ground truth**: `scripts/invert_fair_values.py` gives the
true `t = 0` set for 192 settled items. The base rate to beat is 40 %, and it ranges
**0 %–67 % per Case** — Case 12 has zero uncovered items, Case 10 has 4 of 6. There is no
safe global prior; a detector that always finds something to exclude is wrong on Case 12.

Watch the **anti-traps** (5 Cases): a line that looks excluded and is expressly covered.
Case 8 POS 4 — the robot vacuum is `t = 0`, but §7.1.7(i) indemnifies its inspection
*"even where the property investigated turns out not to be indemnified"*. An exclusion
ending *"the head of cost under X remains unaffected"* is a **pointer, not an exclusion**.

---

## 5. The backtest harness — the gate, not a nice-to-have

`scripts/backtest.py`, offline, over Cases 1–14 against the 148 bounded brackets.

- Runs the full estimator per Case and **caches raw model output to disk**, so re-tuning
  the deterministic layer costs no further quota.
- Reports **σ** = stdev of `log(t̂ / t_mid)`, overall and split by channel (deterministic /
  memory / model), plus coverage confusion against the true `t = 0` set.
- Replays the payoff table to give **simulated net per Game** against the real field —
  the same machinery that produced Fact 2.
- **Gate: do not cut over to Strategy 2 until σ < 0.35 and simulated net is positive.**
- Leave-one-out on the memory channel, or it will score itself on its own answers.

Then keep it running: after every settled Game, recompute σ and append to
`field-findings.md`. σ is the early-warning signal that a prompt or model change broke
something, and it is available minutes after a Game closes.

---

## 6. Parallel work split

Four workstreams, disjoint files, so nothing collides on a live `main`.

| # | workstream | owns these files |
| --- | --- | --- |
| 1 | **Deterministic layer + latency** | `src/policy_slice.py`, `src/data/case_loader.py` (dash + POS), `main.py` item-wise merge |
| 2 | **Backtest harness** | `scripts/backtest.py`, `scripts/replay_payoffs.py` |
| 3 | **Price Memory** | `src/price_memory.py`, `var/price_memory.json` |
| 4 | **Strategy 2 engine** | `src/services/strategies/strategy2/` |

Integration order: 1 lands first (it is free and stops bleeding), then 3 and 4 behind 2's
verdict. Nobody else edits `fast_path.py`, `fraud_detection.py` or `policy_quote.py`.

## 7. Retiring Strategy 1 and 3

`STRATEGY_PRIORITIES = {"strategy1": 1, "strategy2": 2, "strategy3": 3}` — note **3
currently outranks 2**, so Strategy 3 would win even once 2 is good. Cutover:

1. Strategy 2 ships behind the σ gate at priority 2, with 1 and 3 still running.
2. Compare σ per channel across a few live Games — three estimates of the same quantity is
   a free ensemble and a free disagreement signal.
3. When Strategy 2 wins on σ, raise it to the top priority and delete 1 and 3. Not before:
   Strategy 1 is bad, but a dark runner is worse (139,904 across G10–12).

## 8. Risks and what is still unmeasured

1. **The model's σ is unknown.** Everything hinges on it. If it lands above 0.5, the honest
   answer is to lean on the deterministic and memory channels and keep `b` near zero.
2. **`t̂` overshoots on cheap items.** Median `t` is ~59 and our flat 150 fallback sits well
   above it. This is where our `a/t = 1.06` comes from, and it is the single biggest
   accuracy fix available.
3. **The Cap `c` never bound in 52,224 rows.** We only know `c > max observed accepted
   amount`. Any strategy that leans on large Charges extrapolates past the data.
4. **44 of 192 items have no upper bound on `t`.** Backtest σ is computed on the 148 that
   do, so it is measured on a *censored* sample that excludes items nobody rightfully
   rejected — plausibly the expensive ones. Treat σ as optimistic.
5. **Regime change.** README's three phases: the field may go dark overnight, at which
   point Overcharging earns nothing against `b = 0` and only the Limit matters. Never carry
   a field measurement across a phase boundary.
