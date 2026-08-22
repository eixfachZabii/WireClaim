# Strategy pitch — **The Metagame**
### Opponent modelling and adaptive aggression

> Competing pitch. Assumes README §1–§7 as given; builds on R1–R9, never re-derives them.
> New results in this document are labelled **M1–M11**. Every number below is either read
> off the README or produced by `docs/strat-metagame/derive.py` (stdlib only, reproduced inline); none are vibes.

---

## 1. The bet in one paragraph

The other teams are not scenery, they are **~35 adaptive agents with a sleep schedule**,
and the single most decision-relevant number in this tournament — the share of the field
that will accept a charge of size `a` — is **published on the leaderboard every 12 minutes
and 37 seconds** (R9). Our bet is that we build one thing nobody else will: a *field
model*. After every settled game we invert the Transactions view into the full `b`-vector
of every opponent, collapse it to three scalars (**generosity** `m₅₀ = median(bⱼ/t)`,
**coverage-miss rate** `κ`, **participation** `ρ`), forecast them one game ahead using a
clock prior, and feed them into a single argmax that sets `a`. That is it. The claim is
not "we will find a clever exploit" — it is that **the same honest valuation, priced
against a measured field instead of a guessed one, is worth +12% (strict field) to +56%
(generous field) of gross income (M11)**, plus a further +3% to +15% from the one exploit
that never closes (M5: charging on items the policy excludes). And critically, the whole
layer is a **free option**: it sits on top of a strategy that is already correct when the
field is unreadable, so if the metagame evaporates we lose nothing but the six dev-hours
that built it (§7).

---

## 2. Why this wins

**On the leaderboard.** Three quantified claims, in descending confidence:

| Play | Mechanism | Worth | Confidence |
| --- | --- | --- | --- |
| Field-priced charge level | M11 — knowing `p(a)` moves `a*` from `0.75·t̂` to `0.83–1.4·t̂` | **+12% … +56%** income | High. Works in *every* regime, including a strict field. |
| Charging on excluded items | M5 — on `t=0`, break-even is `p>0`, not `p>25%` | **+3% … +15%** income | High. Durable — it does not deplete (M9). |
| Cap-jump (`a ≈ c`) | M4 — bar is `p(c) > 0.62·t/c ≈ 15.6%`, not 25% | **0% … +120%** | Low. Only fires if `m₅₀ > 2.8`. Treat as a lottery ticket, not a plan. |

**On style — and this is the half we actually expect to win.** QuantCo is a company whose
business *is* pricing insurance claims econometrically. The write-up we can hand them is
not "we prompted an LLM for prices." It is:

1. **Four corrections to the naive analysis, with the arithmetic** (M2, M3, M4, M10). Two
   of them correct the README's own R4 and R5b. One of them (M3) says the field-blind
   optimum is the **17th percentile** of your posterior, not the median — a result most
   teams will get exactly backwards.
2. **A measured decay curve of `m₅₀` over 100 games** — an empirical picture of ~35 teams
   *learning to be an insurer in real time*. Nobody else in the room will have that chart.
3. **A fraud-detection benchmark on the field.** `κ` is literally "what fraction of teams
   pay a claim the policy excludes." We will have measured it, per game, for a whole
   weekend, on a population of 35 automated claims handlers. That is a QuantCo slide.
4. **A counterfactual replay harness**: our controller re-run over every settled game
   against the *realised* field, versus an honest baseline and a naive baseline, with the
   income difference plotted game by game. Causal, auditable, and it is how a quant shop
   would ask us to prove the strategy worked.

The framing matters and we should choose it deliberately: **we are not "committing fraud
for points."** We are pricing an option that the organisers' own payoff matrix creates
(R5), and the by-product is a measurement of how well the field detects it. Lead with the
measurement, not the extraction.

**Where this ranks against the rest of the plan.** Honestly: fourth. Uptime (README §5.1),
dual-submit (§5.2) and `t`-estimation (§5.3) all beat it. Sharpening the valuation
posterior from `σ_log = 0.5` to `0.2` is worth `0.539 → 0.697` = **+29%** on its own — about
the same as the entire field model. Take both. If forced to choose, take the valuation.

---

## 3. Model of the field

### 3.0 The one equation

Everything in this document is a corollary of a single line. Per line item, per opponent:

```
honest income  = t                      (risk-free, R1)
fraud income   = min(a, c) · p(a)       (free option, R5)

⟹  overcharge to a  ⟺  p(a) > t / a
```

**M1 — the unified charge rule.** The bar you must clear scales with `t/a`. On a covered
item with a well-known fair value, `t/a` is high and the bar is brutal (to justify `a = 2t`
you need half the field to accept a 100%-over charge). On an item the policy **excludes**,
`t = 0` and **the bar is zero** — any `p > 0` makes charging strictly better than not
charging. Same equation, opposite conclusions. The metagame is: measure `p(·)`, know where
the bar is.

### 3.1 The three scalars we track

Everything about the field compresses to three transportable numbers, all recovered from
R9 after every settled game:

| Symbol | Definition | Estimated from | Noise (n = 34 teams) |
| --- | --- | --- | --- |
| **`ρ`** | share of opponents who submitted anything (`a > 0` or `b > 0`) | count distinct issuers in the settled game | ±0.05, effectively exact |
| **`m₅₀`, `σ_g`** | median and log-sd of the *generosity ratio* `g_j = b_j / t` | bracket each `b_j`, divide by the recovered `t` | ±0.09 on any quantile |
| **`κ(a)`** | share of opponents who accept a charge `a` on an item with `t = 0` | items where **no** rejected row has `amount > 0` | ±0.06–0.09 |

Opponent `j`'s acceptance limit is modelled as `b_j = g_j · t̂_j`, so
`p(a) = ρ · S_g(a / t̂)` on covered items and `p(a) = κ · S_g(a / v)` on excluded ones,
where `v` is the item's market value and `S_g` is the survival function of `g`. The **same
generosity distribution transports across both cases** — only the scale changes from `t̂`
to `v`. That is what makes the model small enough to fit and refit in 12 minutes.

### 3.2 The phases, with numbers

Game index ↔ clock (cadence 757.575 s from Sat 15:00 CEST):

| Phase | Games | Clock | `ρ` | `m₅₀` | `S(1)` | `S(1.5)` | `S(2)` | `S(4)` | `κ` | Our `a` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **P0 Cold start** | 1–5 | Sat 15:00–15:50 | 0.45 | 1.3 | .32 | .20 | .13 | .05 | .30 | `0.80·t̂` |
| **P1 Naive generosity** | 6–22 | Sat 16:03–19:25 | 0.85 | **1.8** | .66 | .52 | .38 | .14 | **.40** | `1.05–1.25·t̂` |
| **P2 First recalibration** | 23–39 | Sat 19:37–22:59 | 0.90 | 1.3 | .60 | .34 | .20 | .06 | .30 | `0.97·t̂` |
| **P3 Deep night** | 40–72 | Sat 23:12–Sun 05:56 | **0.50** | 1.4 | .36 | .22 | .13 | .04 | .22 | `0.85·t̂` |
| **P4 Wake-up** | 73–85 | Sun 06:09–08:40 | 0.80 | 1.2 | .55 | .28 | .16 | .05 | .25 | `0.93·t̂` |
| **P5 Endgame** | 86–100 | Sun 08:53–11:49 | 0.85 | 1.1 | .50 | .22 | .11 | .03 | .20 | `0.89·t̂`, no shrink |

*These are priors, not predictions. Every one is replaced by a measurement within two
games of the tournament starting.* What matters is the shape of the argument:

**P0 — cold start is NOT the exploit window, contra the README.** The README says the
exploit window is Saturday afternoon because teams read "wrongful rejection is penalised"
and set `b` high. Half right. In games 1–5 most teams have not finished plumbing 7-Zip and
the API; a team that does not submit sits at `b = 0` and *rejects everything*, which drags
`p` down. `ρ ≈ 0.45` means `p` is halved before generosity even enters. **Play honest and
build.** The one thing to do in P0 is measure `c_floor` (§3.5) — it is the highest-value
unknown in the game and someone will overshoot in game 1.

**P1 — this is the real window, and it is ~17 games wide.** The field is online, and
`b`-setting is being done by an LLM that has read a handout in which the *only* ⚠️ callout
is the wrongful-rejection penalty and the *only* worked example ends with "Beta set its
acceptance limit too low and got punished twice." The modal prompt is going to say
something like *"set b generously above your estimate."* Prior: `m₅₀ ≈ 1.8`, `σ_g ≈ 0.5`.
At `m₅₀ = 1.8` the argmax charge is ≈ `1.25·t̂` and income is **+31%** over the field-blind
baseline. It does **not** justify a cap-jump (`p(4t) ≈ 0.04`). Anyone who charges `4t` in
P1 will earn nothing and will teach the whole field to tighten (M9).

**P2 — the first recalibration.** Somewhere around Sat 19:00–21:00 the better teams read
their own transaction rows, notice they paid `4t` to somebody, and cut `b`. Expect `m₅₀`
to fall ~0.5 in three or four games. This is the phase transition our detector must catch
(§3.4).

**P3 — deep night is a THIRD of the tournament (33 games, 23:12–05:56).** Two facts fight
each other and we must not confuse them:

- `ρ` collapses to ~0.5 (teams without a cron are at `b = 0`), which halves `p`. Price
  aggression dies. ✔ README is right.
- **But our honest income is completely insensitive to `ρ` (R1).** A charge at `a ≤ t` pays
  `a` whether accepted or wrongfully rejected. The overnight field state is *irrelevant* to
  the honest branch. What collapses overnight is not our income, it is the *option value*
  on top of it.
- **And `κ` does not collapse the way `S(m)` does.** A sleeping team is at `b = 0` and does
  not pay us on an excluded item either — so `κ` scales with `ρ` too — but the excluded-item
  play has break-even `p > 0`, so it *stays profitable at any `ρ`* (M5). **Overnight policy
  is not "pure honesty"; it is honest on covered items and always-charging on excluded
  ones.** That is a materially different overnight bot from the one the README implies.

**P4 — the wake-up, Sun ~06:10–08:40.** `ρ` climbs back. Teams that were asleep return with
*yesterday afternoon's* `b` policy and get farmed for an hour before they recalibrate.
There is a real, short, second exploit window here — perhaps games 73–80 — and it is the
one our clock prior lets us anticipate rather than merely detect.

**P5 — the endgame.** From ~G95 (Sun 10:46) the field stops updating: everyone is writing
their pitch for the 12:00 deadline. `p` becomes *stationary*, our lag-1 estimate becomes
exact, and there is no future field to protect from our own advertising. **From G95 on:
shrinkage → 0, stealth tiebreak off, take the raw argmax.** Five free games.

### 3.3 What the leaderboard inversion actually yields

Per settled game we pull `(line_item_index, issuer, reviewer, accepted, amount)` and apply:

| accepted | amount | Inference |
| --- | --- | --- |
| false | `> 0` | `aᵢ = amount / 1.5`; **`aᵢ ≤ t`** (fair witness); **`b_j < aᵢ`** |
| false | `0` | **`aᵢ > t`** (fraud witness, `aᵢ` unidentified); **`b_j < aᵢ`** |
| true | `> 0` | `aᵢ ≥ amount`; **`b_j ≥ amount`**; if two issuers top out at the same value → **`c = amount`** |

Crossing the two: an issuer accepted by one reviewer at 300 and rejected-at-zero by
another has `aᵢ = 300` **and** `aᵢ > t`, so `t < 300`. Combined with a fair witness at 240,
`t ∈ [240, 300)`. With ~35 issuers spread over the price range the bracket is tight.

**Excluded-item detection is near-perfect.** If `t > 0`, then out of 35 issuers somebody
charges below `t` and somebody has `b = 0`, so at least one row will be `rejected` with
`amount > 0`. Therefore: **an item where no rejected row anywhere in the field has
`amount > 0` is `t = 0`.** That gives us ground truth on coverage every single game — which
lets us *score our own coverage classifier* and measure `κ` exactly.

Volume: 35 × 34 × ~8 ≈ 9.5k rows/game, ~1M over the tournament. SQLite is fine; the fetch
must be **incremental, once per settled game, with backoff** — fair play forbids probing or
overloading the API (README §6), and there is no reason to poll faster than the cadence.

### 3.4 Detecting a phase transition

Effective sample size is the number of **teams** (34), not transactions, because `b` is one
number per team. `se(p̂) = √(p(1−p)/34)` ≈ 0.061–0.086. Two-sample z for a shift `Δ`:

| Shift | 1 game | 2 games | 3 games |
| --- | --- | --- | --- |
| `Δ = 0.15` (mild recalibration) | 1.2–1.7σ | 1.8–2.5σ | 2.1–3.0σ |
| `Δ = 0.25` (real recalibration) | 2.1–2.9σ | 2.9–4.1σ | 3.6–5.0σ |
| `Δ = 0.40` (overnight collapse) | 3.3–4.6σ | 4.7–6.5σ | 5.7–8.0σ |

So, honestly: **big transitions in one game, mild ones in three or four (≈45 minutes).**
Two things close that gap:

1. **`ρ` is measured with almost no noise.** We literally count distinct participating
   teams. The overnight collapse (`Δρ ≈ 0.35`) is detected in **one game, with certainty**,
   and `ρ` multiplies `p`. The slow-to-detect part is conditional generosity, which moves
   less.
2. **The clock is a strong prior and it is exogenous.** Phase transitions here are driven by
   human sleep, which is the most predictable thing at any hackathon. A Bayesian prior
   centred on 23:00–01:00 (down) and 07:00–09:00 (up) means we need far less evidence at
   those times and *more* evidence at 03:00 when a shift is implausible. Encoding the clock
   is three lines of code and buys more than any change detector.
3. **Test the decision, not the distribution.** We do not need "did `p` change." We need
   "is `p(a*)` still above `t/a*`." A one-sided SPRT on that single hypothesis is far more
   powerful than a two-sided change test, and it is what the controller actually consumes.

### 3.5 Discovering `c` — and why it is the highest-value unknown

`c = max(4t, floor)`. On covered items `c ≥ 4t` and the cap essentially never binds for us,
because the argmax only reaches `4t̂` when `m₅₀ > 2.8` (verified). **But on excluded items
`t = 0`, so `c = floor` — and the floor governs the entire excluded-item play**, which is
our most durable edge. Charging `v = 200` on an excluded item earns `min(200, floor)·κ`. If
the floor is 20 the play is worth a tenth of what it is worth if the floor is 200.

**We do not probe for it. We read it.** Detection rule, from R9:

```
For each line item in a settled game:
    accepted_amounts[issuer] = { amount : rows where accepted }
    if ≥ 2 distinct issuers have all their accepted amounts equal to the same value v
       and v == max(all accepted amounts on this item):
           ĉ = v                                    # different issuers, identical payout ⟹ capped
```

Two issuers charging 900 and 5000 both pay out exactly `c`. With 35 teams, someone
overshoots in game 1. **Zero rounds spent, one passive detector, answer by G3.**

Contingency if the field is too disciplined to overshoot by G10: probe on **one line item**
(the lowest-EV item in the case), not a whole game. Cost: 1 item per game × 10 games = 10 of
~800 items ≈ 0.5% of income. Payoff: pins a number that governs ~10% of income. **20:1.**
Note the reframe that makes this cheap — the exploration ladder runs over **line items
within a round**, of which there are ~800, not over rounds, of which there are 100.

### 3.6 Opponent clustering — what is and is not actionable

Clusters we can identify from transaction rows: **dark** (`a = b = 0`), **naive-generous**
(`g > 1.5`), **calibrated** (`g ≈ 0.8–1.3`), **exploiter** (`aᵢ ≫ t̂`, `g` low), **broken**.

Per **R3** we submit one `a` against the whole field, so per-opponent knowledge can only
reach our submission through the aggregate. Be exact about the three channels:

**Actionable ✔ — forecasting.** This is the real payoff. We act on lag-1 data, so what we
need is `p̂_{k+1}`, not `p̂_k`, and the clusters have *different dynamics*: dark teams switch
on a clock, calibrated teams drift monotonically tighter, naive teams take a step change
when they first read their own transaction rows, exploiters never soften. A cluster-wise
transition model beats a pooled EWMA at exactly the moments that matter (the transitions).

**Actionable ✔ — weighting `t`-recovery.** Rank teams by how well their historical charges
predicted realised `t` brackets. Weight the recovered bracket toward the accurate ones.
That tightens the `t` labels our valuation model trains on, which is worth more than the
field model itself (§2, last paragraph).

**Actionable ✔ — excluding ourselves** from the field statistics. Trivial; must not be
forgotten, or we chase our own tail.

**NOT actionable ✘ — targeting, punishing, signalling, price discrimination.** All dead by
R3. Knowing *which* team is generous buys nothing over knowing *how many* are. If you
catch yourself writing "team X is exploiting us, so let's…", stop: there is no "so."

---

## 4. The aggression controller

### 4.0 The scope discipline

**Only `a` is a metagame variable. `b` is not.** R4b is exact: the accept/reject decision is
separable per transaction, so the threshold sits at the same posterior quantile whatever
the field charges. `b` adapts to **our own calibration error** — measured against 800
realised `t` brackets — and to `ĉ`, and to nothing else. Any instinct to move `b` because
"the field is being aggressive" is wrong, and lowering `b` punitively is strictly dominated
(§6).

### 4.1 The corrected charge rule (M3, M4)

With `p ≡ 0` the objective is `max_a a·P(t ≥ a)`. For a lognormal posterior with median `t̂`
and log-sd `σ_p`, the first-order condition is `h(z) = σ_p`, where `h` is the standard
normal hazard:

| `σ_p` | optimal `a / t̂` | `P(a ≤ t)` | percentile of posterior | `EV / t` |
| --- | --- | --- | --- | --- |
| 0.20 | **0.777** | 0.897 | 10.3% | 0.697 |
| 0.30 | **0.748** | 0.833 | 16.7% | 0.623 |
| 0.40 | **0.748** | 0.766 | 23.4% | 0.573 |
| 0.50 | **0.772** | 0.698 | 30.2% | 0.539 |
| 0.80 | 1.003 | 0.499 | 50.1% | 0.500 |

**M3 — README R5b is wrong for realistic posteriors.** It states the field-blind optimum is
"at or above the median." It is at or above the median only when `σ_p ≥ 0.8` — a 90%
interval spanning a factor of ~14. For any usable posterior the optimum is the **10th–24th
percentile**. And the beautiful part: `a*/t̂ ≈ 0.75` almost *independently of `σ_p`*.

> **Rule of thumb, memorise this one: with `p = 0`, charge 0.75 × your median estimate.**
> Uncertainty changes what you earn; it barely changes what you charge.

**M4 — the cap-jump bar is lower than R5 says.** R5 compares `min(a,c)·p(a)` against
`E[honest] = t`. But under uncertainty the honest branch only yields `0.54–0.70·t`. So the
correct bar is:

```
jump to the cap  ⟺  p(c) > EV_honest · t / c   ≈ 0.62·t/c
                 ⟹  c = 4t : p > 15.6%   (README says 25%)
                     c = 6t : p > 10.4%
```

The exploit window is **wider** than the README thinks, and every unit of `c` we discover
lowers the bar further — another reason §3.5 matters.

**M2 — do not bother with a rank-specific objective.** R8 is right that a wrongful rejection
is 25% better for us head-to-head, but that advantage is diluted by `1/(N−1)`: with 35
teams the rank break-even is **25.07–25.36%** against the absolute 25%. A correction of
under one percentage point. Optimise the absolute net; know why you are allowed to.

### 4.2 What the field is worth (M11)

Full objective `EV(a) = a·Ḡ(a) + min(a,ĉ)·(1−Ḡ(a))·p(a)`, with `σ_p = 0.3`, `σ_g = 0.5`,
`ρ = 0.85`, against the field-blind baseline `a = 0.748·t̂`, `EV = 0.623·t`:

| `m₅₀` (field generosity) | `a*` | `EV / t` | gain vs blind | cap-jump? |
| --- | --- | --- | --- | --- |
| 0.6 (strict, everyone at `Q₁ᐟ₃`) | 0.79·t̂ | 0.662 | **+6%** | no |
| 0.8 | 0.83·t̂ | 0.697 | **+12%** | no |
| 1.0 | 0.89·t̂ | 0.736 | **+18%** | no |
| 1.25 | 0.97·t̂ | 0.787 | **+26%** | no |
| **1.5 (P1 prior)** | **1.07·t̂** | 0.842 | **+35%** | no (`p(4t)=.02`) |
| 2.0 | 1.38·t̂ | 0.972 | **+56%** | no (`p(4t)=.07`) |
| 2.5 | 1.87·t̂ | 1.157 | **+86%** | marginal (`p(4t)=.15`) |
| 3.0 | 2.31·t̂ | 1.376 | **+121%** | **yes** (`p(4t)=.24`) |
| Overnight, `ρ=0.5`, `m₅₀=1.5` | 0.90·t̂ | 0.712 | **+14%** | no |

Read the practical shape off this table: **the entire output of the metagame layer is
"charge somewhere between 0.75× and 1.4× your median estimate, and the field tells you
where."** The `4t` fantasy needs the median opponent to sit at `b = 3t`. It probably will
not happen. The 12–35% is the money.

### 4.3 Pseudocode

```python
# ─────────────────────────── persistent state ───────────────────────────
State:
    g_obs:     [(game, team, ratio)]        # b_j / t_recovered, covered items only
    kappa_obs: [(game, team, level, hit)]   # acceptance on t=0 items
    rho_hist:  [(game, participation)]
    c_hat:     {item_signature: value}      # from the passive cap detector
    coverage:  calibration record for our own posterior widths

# ───────────────── after every settled game (12-min timer) ──────────────
def ingest(game_id):
    rows = leaderboard.transactions(game_id)          # fetch ONCE, with backoff
    for item, R in group_by_item(rows):
        A = {}                                        # issuer -> inferred charge
        for r in R:
            if not r.accepted and r.amount > 0: A[r.issuer] = r.amount / 1.5   # fair
            if     r.accepted:                  A[r.issuer] = max(A.get(r.issuer, 0), r.amount)

        # -- cap detector (M/§3.5) --------------------------------------
        top = max((r.amount for r in R if r.accepted), default=None)
        if top and n_distinct_issuers_topping_out_at(R, top) >= 2:
            c_hat[fingerprint(item)] = top

        # -- coverage ground truth (§3.3) -------------------------------
        uncovered = not any(r.amount > 0 for r in R if not r.accepted)

        # -- t bracket --------------------------------------------------
        fair_max  = max((A[i] for i in fair_witnesses(R)),  default=0)
        fraud_min = min((A[i] for i in fraud_witnesses(R)), default=inf)
        t_hat = 0 if uncovered else geometric_mid(fair_max, fraud_min)
        record_label(fingerprint(item), t_hat, fair_max, fraud_min)   # feeds D3

        # -- opponent b brackets ---------------------------------------
        for j in reviewers(R):
            lo = max((A[i] for i in accepted_by(R, j)),  default=0)
            hi = min((A[i] for i in rejected_by(R, j)),  default=inf)
            b_j = geometric_mid(lo, hi) if lo > 0 else (0 if hi < eps else hi / 2)
            if j == US: continue                              # exclude ourselves
            if uncovered: kappa_obs.append((game_id, j, b_j, b_j > 0))
            elif t_hat > 0: g_obs.append((game_id, j, b_j / t_hat))

    rho_hist.append((game_id, n_participating(rows) / n_teams))

# ─────────────────────── one-game-ahead field forecast ───────────────────
def forecast(game_k, halflife_games=6):
    w  = lambda g: 0.5 ** ((game_k - g) / halflife_games)     # EWMA over games
    S  = weighted_survival(g_obs, w)                          # S(m) = P(g >= m)
    m50, sigma_g = fit_lognormal(g_obs, w)
    kappa = weighted_rate(kappa_obs, w)
    rho   = clock_prior_rho(game_k) * 0.5 + observed_rho_ewma() * 0.5

    # non-stationarity: the field only ever tightens. Extrapolate one game.
    drift  = ols_slope(logit(S(1.5)), last_n=8)               # per game, usually < 0
    S      = lambda m, S0=S: inv_logit(logit(S0(m)) + min(drift, 0))

    # regime: clock prior + SPRT on the decision hypothesis
    if sprt_rejects(p_at_target > bar) or clock_says_transition(game_k):
        shrink = 0.6                                          # two games of caution
    else:
        shrink = 1.0
    if game_k >= 95: shrink = 1.0; stealth = False            # endgame, §3.2 P5

    return FieldState(S, m50, sigma_g, kappa, rho, shrink, stealth=True)

# ───────────────────────── the decision (per line item) ──────────────────
def decide(post, F, item):
    """post: t-posterior samples + p_covered + market value v.  F: FieldState."""
    v   = post.market_value
    c   = c_hat.get(fingerprint(item), 4 * post.median_t if post.median_t > 0 else BIG)
    grid = geomspace(0.05 * v, 6 * v, 300)

    # -- lower-confidence-bound the field: EV is linear in p, and p only falls
    def p_of(a):
        raw = F.rho * F.S(a / post.median_t) if post.median_t > 0 else F.kappa * F.S(a / v)
        se  = sqrt(max(raw, 0.02) * (1 - raw) / N_TEAMS)
        return clamp(F.shrink * (raw - 1.0 * se), 0.0, 1.0)

    best_a, best_ev = None, -inf
    for a in grid:
        G  = mean(post.samples >= a)                 # P(a <= t); folds in P(covered)
        ev = a * G + min(a, c) * (1 - G) * p_of(a)
        if ev > best_ev: best_a, best_ev = a, ev

    # -- M9 stealth tiebreak: among a within 3% of the max, take the smallest
    if F.stealth:
        best_a = min(a for a in grid if ev_of(a) >= 0.97 * best_ev)

    # ── guardrails, in priority order ──────────────────────────────────
    a = clamp(best_a, 0.30 * v, 6.0 * post.median_t if post.median_t > 0 else c)
    if post.p_covered < 0.15: a = max(a, min(0.9 * v, c))   # M5: NEVER 0 on an excluded item
    if a <= 0:                a = 0.75 * v                  # R7: a = 0 is never acceptable

    # ── b: NOT a metagame variable (§4.0). R4 with the corrected cap bar (M10) ──
    b = max(x for x in grid if mean(post.samples >= x) > min(x, c) / (min(x, c) + 0.5 * x))
    b *= post.width_calibration                             # the only tunable (R4b)
    return a, b
```

### 4.4 Two corrections to the reviewer side that fell out of this (M10)

Not our lane, but D3 must have them, because they change `b` materially.

**The general reviewer rule is `accept ⟺ q > min(a,c)/(min(a,c) + 0.5a)`.** For `a ≤ c` this
reduces to `q > 2/3` ✔ (R4). For `a > c` the bar **falls**, not rises — README R4's stated
reason ("the bar rises further") is backwards. The intuition: the cap bounds our exposure to
fraud at `c`, while our exposure to a wrongful rejection is `1.5a` and **unbounded in `a`**.
The *conclusion* survives (`q(a)` falls faster than the bar does, so we still reject
absurd charges) but the reason does not, and the reason is what generalises:

**On a suspected-excluded item with a low cap floor, the correct `b` is positive, not zero.**
Verified: with `P(covered) = 0.3`, an excluded item's cap floor at `0.10·v` gives
`b* = 0.93·v`; at `0.25·v` it gives `b* = 0`. So the accept zone opens only when the floor is
small relative to item value. Which means:

> **`c_floor` is the single most valuable unknown in the tournament.** It governs how much
> our excluded-item charge earns *and* whether our excluded-item `b` should be zero.
> Measure it in the first three games (§3.5). Everything else about the metagame is a
> refinement; this is a fact worth ~10% of income on both sides of the book.

### 4.5 Exploration: no ladder, and why "Thompson sampling" is the wrong tool

**This is a full-information problem, not a bandit.** We observe the *entire* reward surface
every round — the whole field's `b`-vector, at every charge level, whether or not we charged
there — because 34 other teams pull the arms for us. There is no exploration/exploitation
trade-off in `a`. Reaching for Thompson sampling here would be cargo-culting.

The genuine difficulty is **non-stationarity**: we observe `p_{k−1}` and need `p_k`, against
an adaptive field. The correct tool class is online prediction with a drift model — EWMA
over games + a monotone (isotonic or lognormal) fit to `S(·)` + a one-game-ahead
extrapolation + a clock prior + a lower confidence bound. That is what §4.3 implements.

Cost-benefit of a deliberate exploration ladder: **it does not pay, because we are not
paying for the information.** The only exceptions are `c_floor` (§3.5, ~0.5% of income if
the passive detector fails) and our own posterior-width calibration (free — it comes from
the same brackets).

**One experiment IS worth running.** We cannot A/B across opponents (R3), but we *can* A/B
across **line items within a game**: fire the field-aware charge on a random half of eligible
items and the field-blind `0.75·t̂` on the other half, then compare realised income. n ≈ 4
per arm per game, n ≈ 40 per arm over 10 games. It costs at most half the upside for 10
games (~1% of the tournament) and it produces the single most credible chart in the
write-up: *our own controller, measured against its own control group, on live data.*
**Run it for games 16–25, then switch fully on.**

**Where Thompson sampling *does* become correct:** if the organisers rule leaderboard-derived
calibration out (Kill 1, §7). Then we only observe outcomes at charge levels we ourselves
chose — a true bandit — and the right structure is Beta posteriors on acceptance over a
discretised ladder `m ∈ {0.7, 0.85, 1.0, 1.3, 2.0, 4.0} × t̂` with a 20-game sliding window
for non-stationarity. Write that fallback; do not ship it unless asked.

---

## 5. Architecture and the 21-hour build plan

### 5.1 Modules and owners

```
runner/       D1   scheduler · key fetch · 7z decrypt · dual-submit · watchdog · alerting
case/         D2   pdf/text/image parse → LineItem{fingerprint, desc, qty, unit, raw}
valuation/    D3   posterior_t(item) → {samples, p_covered, market_value v, width_cal}
metagame/     D4   ingest(settled) → FieldState ;  decide(posterior, FieldState) → (a, b)
store/        —    sqlite: games · items · transactions · brackets · field_state · submissions
dash/         D5   read-only view + the replay harness
```

The load-bearing seam is one pure function: **`decide(posterior_t, field_state) → (a, b)`**.
No I/O, no clock, no network. That makes it unit-testable *and* replayable against every
historical game, which is both our best test and our best slide (§2.4). If nothing else in
this pitch survives, keep that signature.

### 5.2 Hour by hour

**Pre-G1 (before Sat 15:00) — blocking, all five people.**
- Procurement checklist (README §7) in parallel: key, case folder, `pixi install`, `7z`,
  Entire installed, ehl.gg challenge selected.
- **D4, first ten minutes:** post the R9 fair-play question in `#❓-ask-orgateam`. It is the
  longest-latency dependency in the whole plan and it gates 70% of this document. Ask
  before you build.
- **D4, next:** hit `/leaderboard/api/games?page_size=1000`, find the Transactions endpoint,
  capture the exact schema and pagination behaviour into `store/`.
- **D1:** `pixi run python starter_script.py` against case 0. This is the critical path.
- **Gate: at 15:00 we submit *something*, by hand if necessary.** `a = 0.75 ×` a plausible
  price, `b = 0.6 ×` a plausible price. R7 — never default.

**G1–G5 · Sat 15:00–15:50 · uptime first.**
- D1: the loop. T−0 fetch key → decrypt → T+5s heuristic submit → T+50s considered submit.
  launchd/systemd on **two** machines, both on mains power, caffeinate on.
- D2: parser MVP — `pdftotext` + regex, gross-total and quantity normalisation.
- D3: one LLM call per item → `(median, 80% interval, p_covered)`. Ship `a = 0.75·median`,
  `b = 0.6·median`. Per §4.1 that stopgap is already near-optimal — do not gold-plate it.
- D4: transactions scraper → SQLite. **Measure settle latency** (is game `k−1` settled before
  game `k` opens? 11.5 min of slack says yes — verify, because the whole controller's lag
  structure depends on it). Start the cap detector.
- D5: human backstop — submit manually for every game until D1's loop is green.

**G6–G15 · Sat 16:03–18:47 · pipeline hardening + first field read.**
- D4: the inversion (§3.3). By ~G10 publish `m₅₀ / κ / ρ / ĉ` to the team channel **every
  game**. This single number stream is what makes the metagame real rather than theoretical.
- D3: price memory keyed on item fingerprint; calibration harness against recovered brackets.
- D1: dual-submit, retries, dead-man switch → phone alerts for all five.
- D2: images, VAT, multi-page invoices, garbage-input fallbacks.
- D5: dashboard v1 — last game's `m₅₀`, `κ`, `ρ`, our net, our rank, next game countdown.

**G16–G25 · Sat 18:59–21:03 · controller live, behind an A/B.**
- D4: `forecast()` + `decide()` + guardrails, shipped **with the within-game A/B of §4.5**.
- D3: split the coverage decision into its own explicit LLM step with its own posterior.
  Per M5 this is the highest-value single component in the valuation stack, and R9 scores it
  for free every game.
- **Decision gate at G25 (~21:00):** is `m₅₀ > 1.3`? is `κ > 0.15`? is `ĉ_floor` known?
  Those three answers set the overnight config.

**G26–G39 · Sat 21:16–22:59 · freeze and soak.**
- **Feature freeze at 22:00.** After that, config changes only. Nothing else.
- Chaos drill, all three, for real: kill the process; pull the wifi; feed it a corrupt PDF.
  The loop must survive all three unattended. If it does not, that is the only work left.
- Overnight config: longer EWMA half-life (10 games), `shrink = 0.7`, aggressive branch
  restricted to high-confidence-excluded items (M5 — safe at any `ρ`).
- On-call rota agreed: 23:00–03:30 and 03:30–08:00. **Responding to alerts, not watching
  screens.** The other three sleep properly — Sunday morning is when judgement is needed.

**G40–G72 · Sat 23:12–Sun 05:56 · autopilot, 33 games, a third of the tournament.**
- Two scheduled human checks, ~01:30 and ~04:30: read `m₅₀ / κ / ρ / rank`, adjust config
  only. No code after 22:00 except to fix an outage.

**G73–G85 · Sun 06:09–08:40 · the wake-up window.**
- Expect `ρ` to jump. The clock prior should already have pre-positioned us; the detector
  confirms within one game. Short second exploit window (§3.2 P4).
- D3 + D4: refit posterior widths against ~240 fresh `t` brackets from overnight. This is a
  real calibration dataset and the biggest single accuracy win available on Sunday.

**G86–G100 · Sun 08:53–11:49 · endgame.**
- 09:00 — final aggression call on 90 games of data.
- **From G95 (10:46): shrink → 0, stealth off, raw argmax.** The field has stopped updating;
  there is no future to protect (§3.2 P5).
- 10:00–11:45 — D5 finalises the write-up (drafted since Saturday, never started Sunday) and
  the replay chart. **Submit at 11:45, not 12:00.**
- 12:30 — pitch. Live dashboard, the `m₅₀` decay curve, the replay counterfactual, M1–M11.

### 5.3 The single highest-leverage artefact

The **replay harness**: `decide()` re-run over every settled game against the realised
field, versus the field-blind baseline and the naive `a = b = t̂` baseline. It is our
regression test, our tuning loop, and the one chart that proves to a room of quants that
the strategy did something. Build it at G16 and keep it green.

---

## 6. Honest assessment of tit-for-tat and other repeated-game ideas

### Tit-for-tat is not weak here. It is structurally impossible.

Reciprocity needs five things. We have two.

| Requirement | Present? | Why |
| --- | --- | --- |
| Repeated interaction with the same partners | ✅ | 100 rounds, same ~35 teams |
| Observability of the partner's action | ✅ | R9, with a one-game lag |
| **Ability to condition my action on their identity** | ❌ | **R3.** One `a`, one `b`, against the entire field |
| **Enough weight in their payoff to change their incentives** | ❌ | Our `b` is 1/34 ≈ **2.9%** of their `p(a)` |
| A commitment or communication channel | ❌ | No labels, no chat — and cross-team coordination is a **DQ** (README §6) |

Three independent kills, any one of which is fatal. Concretely, the two versions people
propose:

- **Punitive TFT ("they exploited us, drop `b`").** Our `b` applies to *everyone*, so the
  punishment lands on the honest teams exactly as hard as on the exploiter — while the
  exploiter, whose charge is fraudulent, pays **nothing** when rejected (R5). We would be
  paying `0.5a` in lawyer fees to fair issuers in order to impose zero cost on the one team
  we meant to hit. And `b` below `Q₁ᐟ₃` is strictly dominated anyway (R4). This is a
  dominated strategy wearing a strategy's clothes.
- **Generous TFT ("raise `b` to encourage an honest equilibrium").** Same 2.9% weight, and
  the downside is `c ≥ 4t` per exploited item against `0.5a` for being strict — an 8:1
  asymmetry (README R4b). We would be paying eight-for-one to cast 2.9% of a vote.

**R3 kills reciprocity in both directions.** There is no punishment channel and no
deterrence channel, because both roles aggregate over the field.

### What actually has repeated-game structure

1. **A depleting commons, not a repeated game.** `p(a)` is a shared resource that shrinks as
   the field recalibrates. Being early has value; abstaining does not preserve it (other
   teams deplete it whether we participate or not). Extraction is individually rational and
   unilateral restraint is pure loss. Say this plainly in the write-up — the honest
   game-theoretic naming of the situation is worth more style points than a bogus TFT
   section would be.
2. **M9 — but the two exploits deplete very differently, and this is actionable.**
   *Price aggression self-advertises*: charge `4t`, get accepted, and every team that reads
   its own rows sees it got farmed and tightens — we pay for our own gain with the field's
   education, and some teams copy us, which accelerates it. *Coverage aggression does not*:
   a market-plausible price on an excluded item looks **identical to an honest charge** to
   anyone who has not done the coverage analysis, and the teams who *have* done it already
   sit at `b = 0` there. The marks cannot see it; the non-marks have already priced it.
   **Therefore: prefer the coverage play, discount the price play by its advertising cost,
   and take the smallest `a` within 3% of the argmax (§4.3 stealth tiebreak).**
3. **Information compounding.** 100 rounds of labelled `t` brackets on repeating item types
   (README §5.4). This is the real repeated game and it is a *learning* problem, not a
   strategic one.
4. **The only reliable opponent model is a wall clock.** Sleep is exogenous, predictable to
   the hour, and moves `ρ` by 35 points. Every hour spent modelling opponent *psychology* is
   an hour not spent on the one variable that actually moves.

### Second order: if the field also reads the leaderboard, does the exploit close?

**Partly — and here is the thing: it closing costs us nothing.**

If every team implemented R4 correctly, `b_j = Q₁ᐟ₃(t)` and so `S(1) ≈ 1/3`, `S(1.5) ≈ 0.1`,
`S(4) ≈ 0.01`. Price aggression dies. Our optimum falls back to ~`0.79·t̂`, `EV = 0.662·t` —
still **+6% over field-blind**, because knowing the field is *strict* is also information.
And we would be wrongfully rejected roughly two-thirds of the time, which by **R1 costs us
exactly nothing**: `a ≤ t` pays `a` either way.

> **That asymmetry is the whole safety argument for this pitch.** The metagame layer is a
> free option written on top of a strategy that is already correct when the option is
> worthless. The bad case is not "we lose money," it is "we gain 6% instead of 35%."

Two things do **not** close, and they are where we should point resources:

- **`κ` is a capability gap, not an information gap.** Reading the leaderboard tells a team
  *that* it paid for an excluded item; fixing it requires correctly reading `policy.txt`
  against the damage description in 60 seconds under LLM latency. That is hard and it stays
  hard. `κ` decays far more slowly than `S(m)`.
- **Our own `b` being observable does not hurt us.** Teams will see we are strict. They
  cannot price-discriminate against us (R3), so they cannot respond. Symmetry works for us
  here.

**Our concrete response if `m₅₀` drops below 1.3 for three consecutive games:** shift D4 off
the field model onto (i) `t`-bracket recovery quality and (ii) coverage classifier scoring —
both of which feed D3, which is where the remaining money is (§2, last paragraph).

---

## 7. Kill criteria and honest downside

### Kill criteria — pre-agreed, no debate at 03:00

| # | Trigger | Action |
| --- | --- | --- |
| **K1** | Orgs say leaderboard-derived calibration is **not** allowed | Rip out `ingest()`. Fall back to self-calibration on **our own** rows (still legal, still informative) + the Thompson-sampling bandit of §4.5. Costs ~70% of this document. **Ask in the first ten minutes so we learn this at 14:00, not 22:00.** |
| **K2** | Transactions endpoint exposes only our own team, or paginates unusably | Same fallback as K1. Verify inside the first hour. |
| **K3** | Settle latency > 1 game | Widen EWMA half-life to 12 games, `shrink = 0.6`, lean harder on the clock prior. Controller still works, just blunter. |
| **K4** | Controller not green **and A/B-positive** by **Sat 22:00** | Ship the static `a = 0.75·t̂` rule (§4.1) and go to bed. Do not debug a controller at 02:00 — an outage costs more than the controller earns. |
| **K5** | `m₅₀ < 1.3` for 3 consecutive games | Aggressive branch off. D4 reassigned to `t`-recovery quality (§6). |
| **K6** | Any game missed for reasons traceable to the metagame layer | Layer off for the rest of the tournament, permanently, no appeal. Uptime outranks everything (README §5.1). |
| **K7** | A/B shows the field-aware arm *underperforming* the blind arm over 10 games | Turn it off. We built the experiment precisely so this is a fact and not an argument. |

### Honest downside

**The realistic bad case is not a loss, it is a shrug.** If `m₅₀` never exceeds 1.0, the
controller charges `0.89·t̂` instead of `0.75·t̂`, earns +18%, and the pitch's most
interesting chart is a flat line. That is the modal outcome and it is fine.

**The real risk is a broken estimator firing aggressively.** If `p̂` is wrong high and we
charge above `t`, we lose the *entire* honest income on those items — the option is free
against the field, not against our own bugs. Four mitigations, all in §4.3: the lower
confidence bound on `p̂`, the shrink on regime change, the guardrail `a ≤ 6·t̂`, and the
within-game A/B. Residual exposure after those: bounded by the share of items where the
aggressive branch fires times their honest income. Cap that share at **30% of items per
game** until three consecutive games confirm the regime.

**Complexity risk is the one I would actually worry about.** This layer is the fourth
priority behind uptime, dual-submit and valuation, and it has the highest ratio of
interesting-to-important in the repo. One dev (D4), a hard freeze at 22:00, and K4/K6 as
non-negotiable. If the metagame layer ever competes with the runner for attention, the
runner wins.

**Style risk, stated plainly.** QuantCo's business is detecting inflated and non-covered
claims. A write-up that reads as *"we maximised fraud"* could be marked down by the very
people we are pitching to, however correct the arithmetic. Mitigation is framing, and it is
free: we priced an option the organisers' own payoff matrix creates, and the interesting
output is not the euros — it is **`κ`, the measured rate at which a field of 35 automated
claims handlers pays for items their policy excludes, sampled 100 times over 21 hours.**
Lead every slide with that. It is true, it is theirs, and it is the most QuantCo-shaped
artefact this hackathon can produce.

---

## Appendix — new results in this document

| | Result |
| --- | --- |
| **M1** | Unified charge rule: overcharge to `a` iff `p(a) > t/a`. Everything else is a corollary. |
| **M2** | The rank-vs-absolute correction to the break-even is **<1pp** in a 35-team field (25.07–25.36% vs 25%). R8's head-to-head 25% edge is diluted by `1/(N−1)`. Optimise absolute net. |
| **M3** | **README R5b is wrong for realistic posteriors.** With `p=0` the optimum is the **10th–24th percentile** of the `t`-posterior, not "at or above the median" — the median only becomes optimal at `σ_log ≥ 0.8`. And `a*/t̂ ≈ 0.75` almost independently of `σ_p`. |
| **M4** | Honest income under uncertainty is `0.54–0.70·t`, not `t`, so the cap-jump bar is `p(c) > 0.62·t/c` ≈ **15.6%** at `c=4t`, not R5's 25%. The window is wider than the README thinks. |
| **M5** | On excluded items (`t=0`) the bar is `p > 0`: charging is unconditionally optimal in **every** phase, including overnight. Worth +3% to +15%. |
| **M6** | The `p`-curve is fully observable from R9 — this is a **full-information non-stationary prediction** problem, not a bandit. No exploration ladder. Thompson sampling only under Kill 1. |
| **M7** | Effective `n` is **teams (~34)**, not transactions. `ρ` shifts detect in 1 game; 15pp generosity shifts need 3–4. Close the gap with a clock prior and an SPRT on the decision, not a two-sided change test. |
| **M8** | R3 kills reciprocity in **both** directions. Not a repeated game — a depleting commons plus an information race. |
| **M9** | Price aggression self-advertises and self-depletes; coverage aggression does neither. Prefer coverage; take the smallest `a` within 3% of the argmax. |
| **M10** | The reviewer rule is `accept ⟺ q > min(a,c)/(min(a,c)+0.5a)`. Above the cap the bar **falls**, not rises (README R4's reason is backwards; its conclusion survives). Consequence: on a suspected-excluded item with a **low** cap floor, the correct `b` is **positive**. |
| **M11** | Knowing the field is worth **+6%** (strict) to **+56%** (`m₅₀=2`) of gross income, entirely through moving `a` inside the band `0.75–1.4 × t̂`. The `4t` fantasy needs `m₅₀ > 2.8` and probably never fires. |
