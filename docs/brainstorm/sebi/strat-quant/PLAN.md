# Strategy pitch — **The Decision-Theoretic Pricing Engine**

> Competing plan for QuantCo *Claim to Fame*. Builds on `README.md` §3 (R1–R9); does not
> re-derive them. Where our numerics **sharpen or correct** a README result, it is flagged
> `[Δ R5]` etc. and the correction is in §8. **Every number below is reproducible right now:
> `python3 docs/strat-quant/sweep.py` (stdlib only, no deps).** They were computed, not asserted.
> That script becomes `sim/sweep.py` (§3.7) once the package exists.

---

## 1. The bet in one paragraph

Every other team will build a *point estimator*: ask an LLM "what is this line item worth",
get €280, submit `a = b = 280`, iterate on the prompt. **We believe the point estimate is
the wrong object entirely.** Both of our decisions are *quantiles* of a distribution, not
functions of a mean: R4 puts `b` at `Q₁ᐟ₃(t)` and R5b puts `a` at the argmax of an expected-value
integral over `G(a) = P(t ≥ a)`. A team holding only `t̂` cannot evaluate either expression —
it can only guess a fudge factor. So the whole engineering effort goes into one artefact that
nobody else will build: a **calibrated posterior over `t` per line item**, obtained not by
asking a model how confident it is (models are terrible at this) but by *measuring the
disagreement of an ensemble of deliberately different framings* and then rescaling that
dispersion against ground truth that the leaderboard hands us every 12 minutes 37 seconds.
The second bet is that **calibration is learnable inside the tournament**: the settled
leaderboard yields interval-censored labels on `t` (R9), and two scalars — a log-bias `β` and a
spread multiplier `γ` — are enough to turn a badly overconfident LLM ensemble into a usable
posterior after roughly a dozen games. By 03:00 we are running on ~4,000 labelled line items
while the field is still hand-tuning prompts, asleep.

---

## 2. Why this wins

### 2.1 The reviewer side is where the money is, and it is pure quantile arithmetic

`sweep.py`, field of opponent charges clustered near fair value with a fat right tail,
posterior spread `σ = 0.40`, cost in units of `t̂` per opponent-item (lower is better):

| Reviewer policy | `b` | E[cost] | vs optimal |
| --- | --- | --- | --- |
| **`b = Q₁ᐟ₃(t)` (this plan)** | 0.842 | **0.5804** | — |
| `b = Q₁ᐟ₃` with `σ` under-stated 2× (overconfident LLM) | 0.917 | 0.5922 | +2.0 % |
| `b = 0` (panic mode / **team is asleep**) | 0 | 0.6047 | +4.2 % |
| `b = t̂` (naive point estimate) | 1.000 | 0.6322 | **+8.9 %** |
| `b = Q₂ᐟ₃` ("be a bit generous") | 1.188 | 0.6839 | +17.8 % |
| `b = Q₀.₉` ("never wrongfully reject") | 1.670 | 0.8604 | +48.3 % |

Three things fall out, all of them robust across `σ ∈ [0.25, 0.60]` and across three modelled
field regimes (Saturday-aggressive / baseline / Sunday-recalibrated):

1. **The naive point estimator loses 8–10 % of reviewer cost, everywhere.** Not a corner case —
   it is the single most stable number we computed.
2. **For `σ ≳ 0.3`, a team that goes to bed with `b = 0` beats a team that submits `b = t̂`.**
   This is R7's flip side made numerical, and it is the most quotable line in our write-up.
3. **The intuition R4b warns against is expensive and we can price it exactly**: +17.8 % for
   mild generosity, +48.3 % for the "wrongful rejection is penalised, so be safe" reading that
   a large part of the field will adopt on Saturday afternoon. We are on the other side of that
   trade, deliberately, with the arithmetic to defend it.

Note the asymmetry in row 2 vs row 4: **being over-confident about a correct centre costs 2 %;
having no distribution at all costs 9 %.** That ratio is the entire justification for this plan.

### 2.2 The issuer side pays most exactly when the field is asleep

`a* = argmax_a [ a·G(a) + min(a,c)·(1−G(a))·p(a) ]`, evaluated against a modelled field:

| σ | field state | `p(4×)` | `a*/t̂` | `J(a*)` | `J(a = t̂)` naive | edge |
| --- | --- | --- | --- | --- | --- | --- |
| 0.25 | awake, defensive | 0.00 | 0.88 | 0.776 | 0.737 | +5.2 % |
| 0.25 | **overnight, ~55 % dark** | 0.04 | 0.82 | 0.704 | 0.625 | **+12.6 %** |
| 0.40 | awake, defensive | 0.00 | 0.91 | 0.753 | 0.737 | +2.1 % |
| 0.40 | **overnight, ~55 % dark** | 0.04 | 0.85 | 0.653 | 0.625 | **+4.4 %** |
| 0.40 | awake, 25 % over-generous | 0.20 | 1.00 | 0.800 | 0.800 | −0.0 % |

The issuer edge is small when the field is awake — because a naive `a = t̂` accidentally
harvests the "fraudulent but accepted anyway" term — and **large overnight, when `p → 0` and
the only income is the risk-free `a·G(a)` term, which is maximised strictly below the median.**
48 of 100 games run overnight (README §1). This is where the posterior earns its keep on the
issuer side, and it is exactly the window where no competitor is watching.

### 2.3 It composes coverage doubt into the price, which no point estimator can do

`t = 0` for uncovered items (handout), so the posterior is **spike-and-slab**, not lognormal:

```
F(x) = π₀·1{x ≥ 0} + (1 − π₀)·LogNormal(μ, σ²)(x)          π₀ = P(item not covered / unrelated)
Q_q(t) = 0                                     if q ≤ π₀
       = exp(μ + σ·Φ⁻¹((q − π₀)/(1 − π₀)))     otherwise
```

At `σ = 0.40`, median €100:

| `π₀` | 0.00 | 0.05 | 0.10 | 0.20 | 0.30 | ≥ 1/3 |
| --- | --- | --- | --- | --- | --- | --- |
| `b = Q₁ᐟ₃(t)` | €84 | €81 | €77 | €68 | €51 | **€0** |

**A one-in-three chance the item is uncovered drives `b` to exactly zero** — and R4 says that
is optimal, not paranoid. Rejecting an uncovered item is *free* (`a > t = 0` always, so the
rejection is rightful and costs nothing), while accepting one costs the cap floor. Coverage
errors are therefore the most expensive errors in the game, and they are a *classification*
problem that a price-only prompt never even asks. This single mechanism is worth more than any
amount of prompt-tuning on prices, and it is unavailable to anyone holding one number.

### 2.4 It ties directly to the "style" criterion

QuantCo is a pricing firm. The write-up they will read is a desk note, and this plan produces
one as a by-product rather than as a Sunday-morning scramble:

- **A derivation** (R1–R9 + the corrections in §8) — the maths came first, the machine second.
- **A calibration record.** Randomised-PIT histograms and the realised `Q₁ᐟ₃` hit rate, game by
  game, converging to 1/3 through the night. This is the money slide: *watch our posterior
  become honest.*
- **A backtest on real data.** The counterfactual evaluator (§3.7) replays every settled game
  under alternative policies **exactly** — payoffs are deterministic given `(a, b)`, the
  opponents' `b`, and the `t` bracket. We can say "policy X would have earned Y" and mean it.
- **A risk book.** Hard position limits, a fallback ladder, and a documented panic mode.
- **A finding about their own game.** R5's free option is real: charging above `t` costs
  exactly zero on rejection. We can hand QuantCo the break-even acceptance rate at which their
  cap stops protecting them (§8, ≈ 24 %) and tell them where their field actually sat. A
  pricing firm being shown the mispriced option in its own payoff matrix, with numbers, is the
  best 60 seconds of our pitch.

---

## 3. Architecture

### 3.0 The minimum viable core is 200 lines

Before the module list, the honest scoping statement: **`core/posterior.py` + `core/decide.py`
are ~200 lines and deliver most of §2.** Everything else is amplification. If we are at 02:00
with three things broken, those two files plus the fallback ladder are what must still run.

```
wireclaim/
  core/
    types.py        LineItem, Draw, Posterior, Decision, GameContext
    posterior.py    SpikeLogNormal: quantile(q), survival(a), from_draws(...)   [MVC]
    decide.py       choose_b(post), choose_a(post, field)                        [MVC]
    field.py        FieldModel: p(r) acceptance curve in ratio space
    calibrate.py    interval-censored MLE for (β, γ, δ₀, δ₁); PIT; reliability
  ingest/
    keys.py         key poll + retry            archive.py   7z / py7zr decrypt to tmpfs
    parse.py        PDF → LineItem[]; policy.txt; description.txt; images
  elicit/
    prompts/        six framing templates       ensemble.py  async fan-out, partial aggregation
    schema.py       strict JSON schema + one-shot repair
  memory/
    store.py        SQLite (schema in §5.3)     priceindex.py  norm-desc → unit-price posterior
  loop/
    runner.py       the 60 s state machine      watchdog.py   independent submitter of last resort
    settle.py       leaderboard pull + R9 inversion
  sim/
    counterfactual.py  exact replay of a settled game under alternative (a,b)
    sweep.py           policy sweeps — produced every table in this document
  ops/dashboard.py  live posterior / calibration / net / field-curve panels
```

### 3.1 The posterior, and how we get calibrated uncertainty out of an LLM

The problem: LLMs are bad at introspecting uncertainty. Asking "how confident are you?" yields
a number uncorrelated with error. Our answer has four layers, in increasing order of
importance.

**Layer 1 — structural decomposition.** Never ask for a price. Ask for the factors, because
uncertainty is compositional and each factor is elicited where the model is most reliable:

```
ln t  =  ln q  +  ln u  +  ln(1+τ)  +  ln κ
         qty     net unit  VAT        expert haircut (depreciation "neu für alt",
         (on the  price    (0.19 /    policy sub-limit, deductible)
         invoice) (hard)   0.07)

σ²_struct = σ²_q + σ²_u + σ²_τ + σ²_κ        (factors ≈ independent on the log scale)
```

Quantity is usually printed and near-deterministic; VAT is near-deterministic once the regime
is identified; the whole estimation problem collapses onto `u`, where domain knowledge is
strongest and where the **price memory** (§3.5) can substitute outright. Crucially, `u` is
*reusable across games* while the coverage question is not — so the decomposition is also what
makes memory work.

**Layer 2 — three-point elicitation, not a point.** Each call returns `p10 / p50 / p90` for
`u`, for `κ`, and (as a consistency check) for the gross total. Fit a lognormal by matching
quantiles:

```
μ_k = ln(p50_k)          σ_k = (ln p90_k − ln p10_k) / (2 × 1.2816) = Δln / 2.5631
```

Forecasting practice is unambiguous that "give me a plausible low and high" is better elicited
than "state your confidence". It is still badly too narrow — which is what layer 4 fixes.

**Layer 3 — disagreement, not introspection.** Six deliberately *different* framings, because
between-framing variance is a far better proxy for epistemic error than any self-report:

| | framing | why it is a different estimator |
| --- | --- | --- |
| F1 | court-appointed **Sachverständiger**, "maximum defensible gross amount" | closest to the literal definition of `t` |
| F2 | the **Handwerker** writing this invoice | anchors on market billing, not defensibility |
| F3 | **procurement analyst**: wholesaler list price + tariff labour rate | bottom-up, ignores billing convention |
| F4 | **Regulierer** applying *this* policy: deductible, sub-limits, depreciation | the only framing that sees the policy properly |
| F5 | **decomposer**: forced to emit `q`, `u`, `τ`, `κ` separately | exposes the arithmetic |
| F6 | **comparator**: given 3 anchor items from memory with known `t` brackets, price *relative* to them | relative judgement > absolute; **strengthens every game** |

Also varied: temperature (0.2 / 0.7 / 1.0), and whether sibling line items are visible
(anchoring control). F6 is the compounding one — it is weak at 15:00 and the best estimator by
03:00, because it converts our accumulated `t` brackets into a ruler.

**One rule that matters:** every framing prices the item **conditional on it being covered**
("if this item were covered, what is the maximum defensible amount?"). Coverage is asked
separately, as a classification. Otherwise a framing that decides "not covered" pollutes the
price average with a zero and the mixture collapses.

**Layer 4 — aggregation and global calibration.** Per line item, over the `K` draws that landed:

```
μ_raw = median_k(μ_k)                                  # robust to one rogue framing
s²_b  = (1.4826 · MAD_k(μ_k))²                         # between-framing, robust
σ̄²    = mean_k(σ_k²)                                   # within-draw self-report
ι     = mean_k |ln(gross_direct_k) − ln(q·u·(1+τ)·κ)_k|  # internal inconsistency
σ_raw = sqrt(s²_b + λ·σ̄² + ι²)                         # λ starts at 1, fitted later
π_raw = 1 − mean_k(P(covered)_k · P(related)_k)

μ = μ_raw + β                                          # ← global log-bias      (fitted)
σ = max(γ · σ_raw, σ_floor)                            # ← global spread mult.  (fitted)
logit π₀ = δ₀ + δ₁ · logit π_raw                       # ← Platt scaling        (fitted)
```

`σ_floor = 0.18` is **mandatory and non-negotiable**. Six framings agreeing is not evidence of
accuracy — they share training data, and correlated error is invisible to between-draw
variance. The floor is the one guard against the failure mode that would otherwise quietly
bankrupt us on the reviewer side.

Cold-start prior before any label exists: `β = 0`, `γ = 2.0`, `δ = (0, 1)`. `γ₀ = 2.0` is
deliberately wide, and the direction is chosen from **R4b**: a too-wide posterior pushes
`Q₁ᐟ₃` down, we reject more, and we bleed a *bounded* `0.5a`; a too-narrow one lets an
exploiter parked at the cap take `4t`. When uncertain about calibration, **err wide**. The
table in §2.1 prices this: over-wide costs at most the `b = 0` row (+4.2 %), over-narrow is
unbounded.

### 3.2 Fitting `(β, γ, δ)` on interval-censored labels

R9 does not give us `t`. It gives us a **bracket** `t ∈ [L, U)` per line item — and that is
exactly what maximum likelihood on censored data eats. The likelihood of one settled item is
the posterior mass inside its bracket:

```
ℓ_i(θ) = log[ F_i(U_i; θ) − F_i(L_i; θ) ]        θ = (β, γ, δ₀, δ₁)
θ̂ = argmax Σ_i ℓ_i(θ)  −  ridge·‖θ − θ_prior‖²
```

- `L_i = max{ a : some team charged a and was rejected with amount > 0 }` (proven fair)
- `U_i = min{ a : some team charged a and was rejected with amount = 0 }` (proven fraudulent)
- extra upper bound `t ≤ ĉ/4` whenever the cap is observed (`amount < a` on an acceptance)
- if every positive charge was proven fraudulent, that is strong evidence for the spike — the
  same likelihood calibrates the coverage classifier, because `F` contains `π₀`. **One
  objective calibrates price and coverage jointly.** No separate machinery.

Four parameters, a few hundred observations, Nelder–Mead: milliseconds. Refit after every
settled game on a recency-weighted window. Guardrails: `γ ∈ [0.5, 4]`, `β ∈ [−0.7, 0.7]`,
require ≥ 40 observations before departing from the prior, keep the previous `θ` on divergence.

**Sub-note on rejections vs acceptances.** They label different things and this is worth stating
because it drives the whole feedback design: *rejected transactions label `t`; accepted
transactions label the reviewer's `b`.* Every one of the ~35k transaction rows per game
(≈30 teams × 29 opponents × ~40 items) is a censored observation of some opponent's `b`, and
the rejected subset additionally reveals `sign(t − a)`. The system is enormously
over-determined for the handful of quantities we need.

### 3.3 Validating calibration with zero labels at 15:00, and many by 03:00

| when | labels | what we run | what we validate |
| --- | --- | --- | --- |
| **pre-15:00** | 0 real | conservative prior `γ₀ = 2.0` | **synthetic case suite** (below) + case 0 round-trip: parse fidelity, schema, latency. Catches pipeline bugs, not calibration. |
| 15:00–15:25 (g1–2) | 0 | prior; deliberate charge dispersion | nothing yet — these games are instrumentation |
| 15:25–17:00 (g3–10) | ~200 items | first `(β, γ)` fit, refit each game | randomised-PIT KS; `Q₁ᐟ₃` hit rate |
| 17:00–00:00 (g10–43) | ~1,500 | per-segment `γ` (labour / material / disposal / uncovered) | counterfactual net vs realised net |
| 00:00–11:50 (g43–100) | ~4,000 | memory-dominated posteriors; framing weights | all of the above, unattended |

**The synthetic suite (built before 15:00, ~1 dev-hour).** Hand-enter 40 German trade line
items with realistic price *ranges* from domain knowledge; sample a hidden `t` from those
ranges; have a *generator* model write a policy + damage description around them; then run the
full pipeline blind and score it. **Stated honestly: this measures a lower bound on `σ` and
nothing more** — the estimator and the generator share a model family, so measured error will
be optimistically small. Its real job is to prove every line of the pipeline executes and to
catch a `σ` that is *absurdly* wrong. We inflate for live regardless.

**Three diagnostics, all decision-relevant, all on the dashboard:**

1. **Randomised PIT.** With censored labels the PIT is an interval; draw `U ~ Unif(F(L), F(U))`.
   Calibrated ⇒ uniform. U-shaped ⇒ overconfident (raise `γ`); humped ⇒ underconfident.
2. **Realised `Q₁ᐟ₃` hit rate** — the fraction of items with `t < b`. If calibrated this is
   *exactly 1/3*, measured at precisely the quantile we actually use. Better than generic
   coverage because it is the decision itself.
3. **Predicted net vs realised net, per game.** The strongest calibration test available: if the
   posterior is right, the EV the optimiser claimed should match the money that arrived. A
   persistent gap means the model is wrong somewhere and points at where.

### 3.4 The 60-second procedure, concretely

Pre-conditions established in hour 1: the encrypted zips for **all** cases are published in
advance (handout: "a folder … one for each case"), so at `T` we need only the key. **Verify
this by 14:00** — if false, insert a ~3 s download and the budget still closes.

```
T−120s  pre-stage: zip on local disk, HTTP + model connections warm, memory index in RAM,
        case-context prompt prefix pre-built for prompt caching, watchdog armed
T−2s    poll key endpoint every 100 ms
T+0.3   key acquired (3 parallel attempts, separate connections, jittered retry)
T+0.6   decrypt to tmpfs (7z; py7zr as a second, pre-tested implementation)
T+1.8   parse: pdfplumber ‖ pdftotext -layout ‖ PyMuPDF raced, first plausible structure wins
T+3.0   ▸ SUBMIT #1  — memory lookup + category prior. Never a default. (R7)
T+3.0   fire the ensemble: 6 framings × ceil(N/5) chunks  ≈ 24 calls, all concurrent
T+20    ▸ SUBMIT #2  — aggregate over whatever has landed
T+35    ▸ SUBMIT #3
T+42    hard aggregation deadline; outstanding calls cancelled
T+43    numerics (vectorised, ~1 ms)
T+44    ▸ SUBMIT #4 (final)          watchdog force-submits best-known at T+52 regardless
T+60→   log draws, posteriors, payload, timings to per-game JSON + SQLite
T+12m   settle: pull leaderboard, invert (R9), update memory, refit θ
```

**Why chunks of 5.** One call per line item = 240 calls (rate-limit and latency risk). One call
for the whole invoice = 6 calls but a 25 s single point of failure and degraded per-item
attention. Chunks of 5 give ~24 calls at ~6–10 s each, all parallel, with the case context in
the **cached prompt prefix** (policy + description shared across all chunks — a 5–10× cost and
latency win, and the single highest-leverage API optimisation available here).

**The timeout discipline is the design.** There is no join barrier anywhere:

```python
async def price_case(case, deadline) -> list[Posterior]:
    ctx    = cached_prefix(case.policy, case.description, case.images)
    tasks  = [call(f, ch, ctx, deadline=min(deadline, now()+12))
              for f in FRAMINGS for ch in chunks(case.items, 5)]
    draws  = defaultdict(list)
    async for r in as_completed_until(tasks, deadline):      # cancels stragglers at deadline
        if r.ok:
            for d in r.draws: draws[d.idx].append(d)
    return [aggregate(it, draws[it.idx], memory, theta) for it in case.items]
```

`aggregate` runs the fallback ladder **per item**, so item 7 timing out cannot degrade item 3.
A bad JSON gets exactly one repair retry (with the validation error appended) and is otherwise
dropped — one malformed draw never blocks a submission.

**The numerics — a grid, not a solver.** `J(a)` is potentially bimodal (a local max near the
risk-free optimum, a second one at the cap), so gradient methods are wrong. A 256-point
log-spaced grid is exact enough, unconditionally fast, and has bounded runtime:

```python
r   = np.exp(np.linspace(np.log(0.20), np.log(5.0), 256))     # ratio to median
A   = np.minimum(med[:,None] * r[None,:], cap_hat[:,None])    # (N,256); a > ĉ is dominated
G   = survival(A, posts)                                      # (N,256)
P   = field.p(r)[None,:]                                      # acceptance curve, ratio space
J   = A*G + A*(1-G)*P
a   = A[np.arange(N), J.argmax(1)]
b   = np.minimum(quantiles(posts, 1/3), 2.0*med)              # hard tail-risk limit
```

For `N = 40` this is a 40×256 array: microseconds, deterministic, no solver to fail.
`a ≤ ĉ` is a *free* constraint — charging above the cap has identical payoff and strictly lower
acceptance probability, so it is strictly dominated.

### 3.5 Price memory — where the compounding lives

Store **net unit prices, not totals**, keyed on a normalised description (lowercased, digits
stripped, German-stemmed). Totals do not transfer across invoices; unit prices do, and this
invoice supplies its own quantity.

Two-tier lookup: exact normalised match → item-level posterior; else trigram/embedding
neighbours → category posterior for `u`. And the Bayesian update is trivially exact: **a
bracket observation `t ∈ [L, U)` updates the prior by truncation.** If we have seen the item
before and bracketed it to within 5 %, the posterior *is* that truncated prior, `σ` collapses
to ~0.03, and `Q₁ᐟ₃ ≈ L + (U−L)/3`. The LLM stops mattering for that item entirely.

Open hypothesis with a cheap test, to run at game ~8: **do line items recur across cases with
the same `t`?** Match normalised descriptions across settled games and check bracket
consistency. If yes, memory is the dominant estimator by Sunday. If no, memory still carries at
the category level (`Malerarbeiten je Stunde`, `Entsorgungspauschale`), which is most of the
value anyway.

### 3.6 The field model — `p(a)`, and why it is not a mood dial

`p` lives in **ratio space**: `ρ_j = b_j / t̂_j` per opponent `j`, pooled over line items, so
errors in `t̂` largely cancel between numerator and the `a/t̂` at which we evaluate. Maintain an
EWMA over games with a ~6-game half-life (the field moves fast, especially at bedtime and at
breakfast), plus an explicit "known dark" set for teams whose `b` was 0 in the last `k` games.

`p̂` is fed straight into the grid; **there is no aggression dial and no one has to decide how
bold to be.** The argmax moves on its own as `p̂` moves. Hysteresis: require a ≥10 % EV gap
before switching branches, so we do not flip-flop on noise. In the final 5 games, exploration
off, pure exploit.

**Deliberate price dispersion as experimental design.** Our own transactions appear on the
leaderboard, so charging different `a` across items measures `p(·)` at exactly the points we
charge. Allocate ~15 % of items to a designed probe grid, **but only where `J(a)` is within 5 %
of its max**, so the information is close to free. This is low priority while R9 gives us the
whole field's transactions — and becomes *essential* if the organisers say no (§6, K3), because
our own accept counts are then the only identification of `p`.

### 3.7 The counterfactual evaluator — the highest-value artefact in the repo

`sim/counterfactual.py` replays a settled game under any alternative `(a, b)` policy. This is
not a simulation; the payoff matrix is deterministic, and:

- **as reviewer it is essentially exact.** We observe every opponent's `a_j` directly, and for
  every charge that *anyone* rejected we learn its side of `t` exactly. Only charges that
  literally everyone accepted stay ambiguous — and those are the low ones, which are almost
  certainly fair. **The side where errors cost `4t` is the side we can optimise offline with
  near-certainty.** That is a remarkable gift and it is the reason this plan is buildable in a day.
- **as issuer it is near-exact** outside the `t` bracket; inside it, report both the exact
  bound and the posterior-expected net.

Everything gets tuned against it: `γ`, `σ_floor`, framing weights, the probe budget, the
hysteresis. It is also the source of every table in this document and of the backtest slide.

### 3.8 Framing weights (cheap, and halves cost)

Once ~300 labelled items exist, weight framings by realised log-score under exponential
weights (Hedge). Bad framings decay out; `K = 6` becomes effectively `K = 3` without accuracy
loss — halving both token spend and tail latency, which matters more at 03:00 than at 15:00.

---

## 4. The 24-hour build plan

Five devs. **D1** loop/infra · **D2** ingest/parse · **D3** elicitation · **D4** quant ·
**D5** feedback/ops/write-up. This plan owns **D4** outright and roughly half of D3 and D5.

| window | games | quant-track deliverable | devs | definition of done |
| --- | --- | --- | --- | --- |
| **now → 14:00** | — | **Everything stops for procurement.** API key, case folder, handbook, case 0 round-trip, `p7zip`, Entire gate, ehl.gg selection, Discord question on R9. Confirm zips are pre-published and confirm what the API does with a wrong line-item count. | **5/5** | `starter_script.py` submits successfully on case 0 |
| 14:00 → 15:00 | — | `posterior.py` + `decide.py` + category-prior table (~60 rows) + the fallback ladder. Hard-wired `γ₀ = 2.0`. Synthetic suite if there is slack. | D4 + D3 | **rung-3 payload generated for case 0 in < 5 s** |
| **15:00 → 17:00** | 1–10 | Ensemble live (F1/F4/F5 first — the three most different). `settle.py` inversion + SQLite. First `(β,γ)` fit at ~g8. | D3 + D4; D5 on settle | ≥ 4 draws/item by g5; first `θ̂` printed |
| 17:00 → 20:00 | 10–24 | `counterfactual.py`. `field.py` from real transactions. F2/F3/F6 added. PIT + `Q₁ᐟ₃` hit-rate panels. **Recurrence hypothesis tested.** | D4 + D5 | backtest reproduces our realised net to < 2 % |
| 20:00 → 00:00 | 24–43 | Price memory with truncation update. Per-segment `γ`. Framing weights. Probe grid. Dashboard: posterior width, field curve, predicted-vs-realised net. | D4 + D5 | `Q₁ᐟ₃` hit rate within [0.28, 0.40] over the last 20 games |
| **00:00 → 08:00** | 43–81 | **Autonomy.** Auto-refit, auto-safe-mode on anomaly, alerting. Two devs on rotating 2 h watch; **three sleep — this is a scheduled deliverable, not a nicety.** | 2 on watch | zero missed games; no manual intervention needed |
| 08:00 → 10:30 | 81–95 | Final `γ` tuning against the backtest. Exploration off after g95. | D4 | last-20-game net ≥ first-20-game net, normalised |
| 10:30 → 11:50 | 95–100 | **Feature freeze.** Write-up finished, figures exported, pitch rehearsed twice. | 4/5 (D1 babysits) | write-up submitted before 12:00 |
| 11:50 → 12:30 | — | Submit on ehl.gg, pitch | 5/5 | — |

Two rules that override the table. **(a) Nothing ships to the live loop without a green
counterfactual replay** — after ~17:00 we have a backtest, so there is no excuse for shipping
on vibes at 03:00. **(b) The write-up is written continuously from 17:00.** README §5 point 6 is
correct and the failure mode is real.

---

## 5. What this needs from other tracks

### 5.1 From infra (D1) — blocking, and worth more than everything here

- Pre-staged encrypted zips; key fetch with retry; decrypt to tmpfs.
- The 60 s state machine with **deadline hooks at T+3 / T+20 / T+35 / T+44** and multi-submit
  (README §5 point 2). The quant layer is a pure function called at each hook; it must never own
  the clock.
- **An independent watchdog process** — separate process, separate code path — that submits a
  rung-3 payload if no submission is recorded by T+40. Plus a second host on a different network
  path. Deterministic inputs ⇒ the two agree; later overwrites earlier, so redundancy is free.
- Secrets, systemd/launchd supervision, heartbeat alerting.

### 5.2 From ingest (D2)

`LineItem[]` with `idx`, `description`, `quantity`, `unit`, and a `parse_confidence`. **If the
line items are wrong, every number in this document is meaningless** — see K5.

### 5.3 From the feedback loop (D5) — the fuel

Pull the leaderboard Transactions view for **all** teams after every settled game and invert per
R9. Contract (this is the interface; the quant layer reads nothing else):

```sql
CREATE TABLE items       (game_id INT, idx INT, desc TEXT, norm_desc TEXT, qty REAL, unit TEXT,
                          PRIMARY KEY(game_id, idx));
CREATE TABLE draws       (game_id INT, idx INT, framing TEXT, model TEXT,
                          p10 REAL, p50 REAL, p90 REAL, pi_raw REAL, latency_ms INT, raw_json TEXT);
CREATE TABLE posteriors  (game_id INT, idx INT, pi0 REAL, mu REAL, sigma REAL, cap_hat REAL,
                          source TEXT, n_draws INT, rung INT);
CREATE TABLE submissions (game_id INT, idx INT, seq INT, a REAL, b REAL, sent_at REAL, ack INT);
CREATE TABLE transactions(game_id INT, idx INT, issuer TEXT, reviewer TEXT, accepted INT, amount REAL);
CREATE TABLE brackets    (game_id INT, idx INT, t_lo REAL, t_hi REAL, cap_obs REAL, n_evidence INT);
CREATE TABLE field_b     (game_id INT, team TEXT, idx INT, b_lo REAL, b_hi REAL);
CREATE TABLE calib       (fit_at REAL, beta REAL, gamma REAL, d0 REAL, d1 REAL,
                          n_obs INT, ks REAL, q13_hit REAL);
```

Watch the volume: ~35k transaction rows per game. We only ever need per-item aggregates —
paginate, aggregate on write, do not hold it all.

### 5.4 From the organisers

The R9 question in `#❓-ask-orgateam`, **before** we build on it (README §3 R9, §6). Ask at
14:00; the answer changes §3.6 and §6 K3, not the core.

---

## 6. Kill criteria

Falsifiable, with a pre-agreed fallback. No debating in the small hours.

| | trigger | reading | fallback |
| --- | --- | --- | --- |
| **K1** | after 12 settled games: `γ̂ > 3.0` **and** realised `Q₁ᐟ₃` hit rate > 0.5 | the ensemble carries almost no information about `t` | drop to `K = 2` draws, let memory + category priors dominate, redirect D3 to parsing and D4 to the field model |
| **K2** | the counterfactual shows a **constant policy** (`b = 0.7 × category median`, `a = 0.9 ×`) beating the posterior policy for 3 consecutive fit windows | our machinery is losing to a lookup table | ship the constant policy, keep the posterior running in shadow for the write-up. Say so in the write-up — an honest negative result scores better with QuantCo than a dressed-up loss |
| **K3** | organisers disallow leaderboard-derived calibration | no external labels | self-only: our own rejections still bracket `t`, and our own accept counts still identify `p(a)`. Precision drops ~3× in games-to-convergence; the probe grid (§3.6) becomes mandatory, not optional. **Graceful, not fatal.** |
| **K4** | ensemble wall-clock > 40 s at `K = 4` on real item counts | latency budget blown | `K = 2` + a faster model; posterior becomes memory-dominated |
| **K5** | parse accuracy < 90 % on a human spot-check of 3 cases | **we are pricing the wrong items** | freeze all quant work, all hands to `parse.py`. Nothing downstream matters |
| **K6** | realised `Q₁ᐟ₃` hit rate > 0.55 sustained over 20 games | we are being farmed — someone is parked just under our `b` | emergency: `γ ← 1.5·γ`, and enforce `b ≤ 1.3 × median` until the refit stabilises |
| **K7** | Sunday 09:00 and the write-up is < 80 % done | style score at risk | feature freeze immediately; D4 stops coding and writes |

---

## 7. Honest downside

**7.1 Uptime dominates this entire plan, by an order of magnitude.** One missed game costs
≈ 0.68 `t̂` per opponent-item (forgone income plus the `b = 0` excess). The *total* edge of this
plan over a naive-but-always-on point estimator is ≈ 0.07–0.08 `t̂` per opponent-item.
**One missed game ≈ 9 games of everything in this document overnight, and ≈ 13 while the field
is awake.** If forced to choose between an
hour on the posterior and an hour on the watchdog, the watchdog wins every time. README §5 has
the priorities in the right order and this plan does not change them — it slots in at priority 3.

**7.2 The field model may be worth more than the posterior, and it is cheaper.** The issuer
optimum moves from 0.82 to 1.09 × median purely as a function of `p̂`, and the reviewer's cost
varies more across field regimes than across our own `σ`. A rival with a crude `t̂` and a good
read on the field could beat us. Mitigation: `field.py` is scheduled at 17:00, *before* the
sophisticated posterior work — deliberately, against the instinct to finish the Bayesian core
first.

**7.3 Global calibration cannot fix per-item miscalibration.** `γ` is one number; the true error
is heteroskedastic. If all six framings are wrong in the *same* direction on an exotic item —
correlated error from shared training data — between-framing variance under-states the error
and no global rescaling repairs it. Per-segment `γ` helps a little and over-fits quickly.
`σ_floor` is a blunt patch, not a solution. **This is the real technical weakness and we should
say so in the write-up rather than let a judge find it.**

**7.4 Against a very tight posterior, the issuer edge nearly vanishes when the field is awake.**
At `σ = 0.40` with a defensive field it is +2.1 %. Most of the issuer value is concentrated
overnight (+4.4 % to +12.6 %). If the field stays awake all night, half the case for this plan
evaporates and we are left with the reviewer side (which, to be fair, is the robust 8–10 %).

**7.5 Over-engineering risk is the most likely way this fails.** Five devs, 21 hours, and a
tempting module list. The mitigation is §3.0: the minimum viable core is two files, and every
later component must earn its place against the counterfactual evaluator or not ship.

**7.6 A simpler plan that beats us in one specific world.** If line items recur heavily across
cases, then by game 30 a pure memory + bracket-truncation bot with no LLM in the loop at
decision time is *better than us and far more reliable* — near-zero latency, no timeouts, no
token spend. We should be actively hoping for this outcome, testing for it at game 8 (§3.5), and
prepared to demote the ensemble to a cold-start prior. That would not be a defeat; the posterior
machinery is exactly what turns brackets into decisions either way.

---

## 8. Corrections and sharpenings to the README's results

Recorded in the same spirit as README §4 — including one that corrects our own first pass
during this analysis.

**[Δ R5b] "Even with `p ≡ 0` the optimum sits at or above the median" is true only for
`σ ≳ 0.80`.** The exact risk-free optimum maximises `a·S(a)`, giving
`a* = exp(μ + σz*)` where `z*` solves `σ·Φ(−z) = φ(z)`:

| σ | 0.15 | 0.20 | 0.25 | 0.30 | 0.40 | 0.50 | 0.60 | 0.80 | 1.00 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `a*/median` | 0.80 | 0.78 | 0.76 | 0.75 | 0.75 | 0.77 | 0.82 | 1.00 | 1.35 |
| income vs `a = median` | +49 % | +39 % | +31 % | +25 % | +15 % | +8 % | +3 % | 0 % | +3 % |

The crossover is at `σ = 0.798` exactly. For any realistic posterior the risk-free optimum sits
at roughly the **20th–35th percentile**, not the median. Note the direction of the second row:
**the tighter our posterior, the more the quantile choice is worth.** That is the opposite of
the natural intuition and it means our estimation work and our decision-theory work are
complements, not substitutes.

**[Δ R5] The cap gamble is far less attractive than "break-even at `p > 25 %`" makes it sound —
and this corrects our own first pass, not just the README.** Our initial numerics suggested
uncertainty *lowers* the break-even to ~17 %, because uncertainty taxes the honest branch
(income 0.573 `t̂` rather than `t̂`). **That was wrong**: it forgot that the honest branch also
collects the `min(a,c)·(1−G(a))·p(a)` term — near the median, roughly half of our charges are
technically in the fraud zone and get paid anyway when accepted. The honest branch is therefore
worth **0.75–0.85 `t̂`**, not 0.573, and the true break-even is back near **24 %** of the field
accepting `4×` fair value.

The consequence is a genuine change of plan: **the optimiser does not choose between "honest"
and "cap-spam". It chooses a continuous `a` that drifts up as `p̂` rises**, and across every
field we modelled — including a Saturday field with 25 % over-generous reviewers — `a*` stayed
in `[0.82, 1.09] × median`. The cap branch first wins only when ~30 % of the field would accept
`4×`, and even then by under 1 %. We should therefore **not** plan a "Saturday exploit window";
we should plan a smooth `p̂`-driven drift and let the grid decide. This is worth flagging to the
team early, because "hammer the cap on Saturday afternoon" is the intuitive read of R5 and it
appears to be wrong.

**[+ R4] The spike-and-slab consequence.** `Q₁ᐟ₃(t) = 0` exactly when `π₀ ≥ 1/3` (§2.3). R4
is normally read as a statement about price uncertainty; it is equally a statement about
coverage uncertainty, and that reading is the one with the sharp edges.

**[+ R7, quantified] `b = 0` beats `b = t̂`** for `σ ≳ 0.3` and against any field with a fat
right tail of charges (§2.1). A sleeping team outperforms an awake team that submits a point
estimate. Both, of course, lose to submitting `Q₁ᐟ₃`.

**[+ R9] Rejections label `t`; acceptances label `b`.** The clean split (§3.2) is what makes
the reviewer-side counterfactual near-exact and therefore what makes this plan fit in a day.

---

## 9. What we hand the judges

1. This document's derivations, with the corrections in §8 shown as corrections.
2. A PIT / reliability animation across 100 games: the posterior becoming honest overnight.
3. The field acceptance curve `p̂(a)` animated across 100 games — the overnight collapse and
   the Sunday-morning recovery, measured, not assumed. **This is the demo.**
4. The policy sweep table of §2.1, computed on *their* real settled data by our counterfactual
   evaluator rather than on a model.
5. One slide on the free option in their payoff matrix: rejected fraud costs exactly zero, here
   is the break-even acceptance rate (≈24 %), and here is where your field actually sat.
