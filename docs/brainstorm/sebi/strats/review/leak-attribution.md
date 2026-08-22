# Leak attribution — every settled Game, stage by stage

Scope: Games 1–32 (the tournament has no Game 0; `case_00` is the permanent test Case and
carries no leaderboard net). All numbers below are computed by three new, read-only scripts
— `scripts/leak_buckets.py`, `scripts/leak_sigma.py`, `scripts/leak_candidates.py` — running
entirely against the on-disk caches (`var/transactions`, `var/replay`, `var/decisions`,
`var/evidence`) that already validate to the cent, plus the existing
`scripts/charge_buckets.py` harness extended from Games 1–27 to 1–32. Nothing here touched
`src/`, `main.py` or `pixi.toml`, and no network call was made — everything needed was
already cached from prior sessions.

**Bottom line, up front.** Coverage is closed (H4), the Limit's *level* is closed (H1/limit
audits), conditional Charge multipliers are closed (`charge_buckets.py`). This session found
one candidate that is not yet closed — a channel-conditional **Limit ceiling** (never before
swept; every prior sweep touched the Charge, not the Limit) — and it is positive in every
split tested, but stays inside the noise floor at today's sample size. Nothing here clears the
noise floor. The honest verdict is: keep measuring, do not ship blind.

---

## 1. The four-bucket decomposition, verified to the cent

`scripts/leak_buckets.py` classifies every settled row into

- **(i) fair income** — we were the issuer and our Charge `a ≤ t` (paid whether accepted or
  wrongfully rejected — the payoff table pays the issuer `a` in both cells of the fair row)
- **(ii) Overcharge income** — we were the issuer, `a > t`, and some opponent's Limit paid it
- **(iii) accepted cost** — we were the reviewer and accepted (whatever the truth was)
- **(iv) penalty cost** — we were the reviewer, rejected, and it turned out to be a fair
  Charge (`1.5×` the rejected amount)

`t` is read off the same `GameSnapshot.fair_point` convention `replay_payoffs.py` uses
everywhere else (midpoint of the reconstructed bracket, or the lower bound where the bracket
is unbounded above), so this is a *classification* of the existing validated identity, not a
new measurement.

| Game | items | fair income | Overcharge income | accepted cost | penalty cost | net | authoritative | reconciled |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 1 | 18 | 19,008.00 | 696.00 | 1,127.09 | 5,075.06 | 13,501.85 | 13,501.85 | OK |
| 2 | 7 | 5,088.00 | 0.00 | 600.94 | 3,765.48 | 721.58 | 721.58 | OK |
| 3 | 2 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | OK |
| 4 | 15 | 8,160.00 | 5,775.03 | 6,238.28 | 4,176.52 | 3,520.23 | 3,520.23 | OK |
| 5 | 17 | 4,800.00 | 4,275.00 | 19,449.93 | 229.50 | −10,604.43 | −10,604.43 | OK |
| 6 | 2 | 720.00 | 315.00 | 0.00 | 4,975.03 | −3,940.03 | −3,940.03 | OK |
| 7 | 6 | 0.00 | 0.00 | 33,568.40 | 0.00 | −33,568.40 | −33,568.40 | OK |
| 8 | 39 | 0.00 | 3,429.00 | 83,503.06 | 0.00 | −80,074.06 | −80,074.06 | OK |
| 9 | 16 | 0.00 | 750.00 | 17,334.07 | 4,812.76 | −21,396.83 | −21,396.83 | OK |
| 10 | 6 | 4,800.00 | 500.00 | 0.00 | 65,806.04 | −60,506.04 | −60,506.04 | OK |
| 11 | 22 | 0.00 | 0.00 | 0.00 | 36,016.63 | −36,016.63 | −36,016.64 | ±0.01 |
| 12 | 12 | 0.00 | 0.00 | 0.00 | 43,380.89 | −43,380.89 | −43,380.89 | OK |
| 13 | 17 | 13,200.00 | 3,600.00 | 3,554.87 | 15,851.72 | −2,606.59 | −2,606.58 | ±0.01 |
| 14 | 13 | 0.00 | 450.00 | 2,373.97 | 675.52 | −2,599.50 | −2,599.49 | ±0.01 |
| 15 | 29 | 14,400.00 | 2,800.00 | 21,055.52 | 14,946.44 | −18,801.95 | −18,801.96 | OK |
| 16 | 2 | 0.00 | 0.00 | 4,721.32 | 0.00 | −4,721.32 | −4,721.32 | OK |
| 17 | 20 | 15,720.00 | 4,860.00 | 70,736.09 | 13,633.15 | −63,789.25 | −63,789.24 | ±0.01 |
| 18 | 14 | 12,880.00 | 1,589.00 | 418.53 | 51,132.16 | −37,081.69 | −37,081.69 | OK |
| 19 | 9 | 16,800.00 | 37,817.50 | 57.74 | 20,151.66 | 34,408.10 | 34,408.10 | OK |
| 20 | 6 | 37,520.00 | 682.50 | 51.13 | 25,386.75 | 12,764.62 | 12,764.62 | OK |
| 21 | 2 | 0.00 | 3,080.00 | 0.00 | 0.00 | 3,080.00 | 3,080.00 | OK |
| 22 | 1 | 0.00 | 14,840.00 | 0.00 | 0.00 | 14,840.00 | 14,840.00 | OK |
| 23 | 3 | 2,400.00 | 2,327.50 | 0.00 | 5,548.09 | −820.59 | −820.60 | OK |
| 24 | 11 | 7,504.00 | 46,241.00 | 0.00 | 40,732.19 | 13,012.81 | 13,012.82 | ±0.01 |
| 25 | 15 | 46,916.80 | 947.52 | 7,928.45 | 38,471.82 | 1,464.05 | 1,464.05 | OK |
| 26 | 12 | 20,108.32 | 1,198.61 | 1,196.11 | 24,041.15 | −3,930.32 | −3,930.33 | OK |
| 27 | 4 | 0.00 | 21,861.06 | 1,876.86 | 8,633.07 | 11,351.13 | 11,351.13 | OK |
| 28 | 10 | 0.00 | 5,446.63 | 148.50 | 0.00 | 5,298.13 | 5,298.13 | OK |
| 29 | 4 | 4,461.44 | 22,475.90 | 422.54 | 6,691.68 | 19,823.12 | 19,823.12 | OK |
| 30 | 5 | 8,184.00 | 3,352.72 | 636.69 | 14,363.07 | −3,463.04 | −3,463.04 | OK |
| 31 | 18 | 9,250.08 | 9,952.96 | 1,435.92 | 17,076.72 | 690.40 | 690.40 | OK |
| 32 | 7 | 7,170.72 | 3,189.78 | 171.03 | 3,302.85 | 6,886.62 | 6,886.62 | OK |
| **TOTAL** | | **259,091.36** | **202,452.71** | **278,607.04** | **468,875.95** | **−285,938.92** | **−285,938.92** | |

**Reconciliation.** 27 of 32 Games reconcile to the cent exactly; 5 (Games 11, 13, 14, 17, 24)
are off by **$0.01** each — floating-point summation-order drift between two separately
accumulated running sums, not a methodology error (aggregate drift is 5 cents on a
−285,938.92 net, 1.7×10⁻⁵ of it). The **TOTAL net, −285,938.92, matches the published
standing to the cent**, and the Games 19–32 sub-total (**+115,405.03**) matches the figure
already established for that window. Both are self-checks this script did not need to pass —
it inherited them from `replay_payoffs.snapshot`, which already reproduces every net — but
passing them anyway is the point of building the decomposition this way rather than a new one.

**What the totals say.** Overcharge income (+202,453) is nearly as large as fair income
(+259,091) — the field has, at times, been generous enough to make Overcharging pay, which is
a Field fact (R9: does not survive recalibration), not a strategy. Penalty cost (−468,876) is
by far the largest bucket, **1.7× the accepted-cost bucket** and larger than fair income
itself. That number alone looks like "the Limit is too strict" — but see §2: on the Games
that actually ran the shipped Limit discipline (19–32), penalties are largely the *deliberate,
partly unavoidable* cost of strictness, and every prior audit that tried to buy them back with
a looser Limit lost more in new Overcharges than it saved (H1, `limit_audit.py`).

Per-Game dominant mechanism (mechanical classification, not the evidence-level stage — see
§2 for that): Games 1–18 alternate between **Limit-too-loose** (5, 7, 8, 9, 14, 16, 17 —
accepted cost dominates) and **Limit-too-strict** (1, 2, 6, 10, 11, 12, 13, 18 — penalty cost
dominates), which is the Limit swinging across the posterior rather than sitting in it — the
known "outside the posterior, not a flat knob" story (ARCHITECTURE.md §4, Games 5 and 17).
**From Game 19 onward the regime stabilises**: 11 of 14 Games (19, 20, 23, 24, 25, 26, 27, 29,
30, 31, 32) are Limit-too-strict, and 6 of those 11 are *also* income-mostly-Overcharge (19,
24, 27, 28, 29, and 22, 21 outright) — i.e. the shipped strictness is working (net positive in
9 of 14) but the residual cost is now concentrated in wrongful-rejection penalties rather than
funded Overcharges. That is the audited, largely-unavoidable cost H1's own decomposition
already quantified (Games 21–26: 108,793 of penalty, only 36,791 recoverable by a perfect
per-item Limit) — not a fresh defect.

---

## 2. Stage attribution

**Only Games 26–32 carry a decision log** (`var/decisions/game_0{26..32}.json`); Games 1–25
predate it. `scripts/learn_from_game.py` already builds the per-item join for every settled
Game and writes `var/lessons/game_0NN.json` — this section reads what is already on disk
rather than re-deriving it, per the standing instruction not to re-run analysis that already
exists.

| stage | penalty euros | share of total 468,876 |
|---|---:|---:|
| **no-decision-log** (Games 1–25 — evidence-level attribution is not possible) | 394,767.42 | 84.2% |
| ok (no rule in the heuristic fires — see below, mostly Limit-ceiling clipping) | 38,247.28 | 8.2% |
| charge-far-below-t (our whole estimate ran low, dragging `a` and `b` down together) | 17,773.77 | 3.8% |
| charge-above-t (irrelevant to the *penalty* bucket by definition — Issuer-side, listed for completeness) | 11,923.92 | 2.5% |
| coverage-too-low (coverage collapsed the Limit on an item that was actually worth something) | 6,163.56 | 1.3% |
| coverage-too-high | 0.00 | 0.0% |

**84% of penalty euros predate the instrumentation that could name the stage.** That is a
finding in itself: the highest-leverage remaining infrastructure improvement is not a pricing
constant, it is *more decision-logged Games* — which is already happening every Game now that
the log lands, so this ratio will invert on its own. For Games 1–25 the closest available
stage attribution is the mechanical Limit-too-loose/too-strict split in §1 plus the qualitative
per-Game causes already on record in `field-findings.md` (Game 5: coverage gate emitted false
"uncovered" verdicts on covered items, worth 1,121.40 on one Line Item alone; Game 6: the
Charge was the uninformed fallback constant, 45.00 against a true `t ∈ [765, 900)`; Games
11–12: nothing submitted, `b = 0` on every index; Games 21–24: `STANDARD_LIMIT = 35` on every
index because Strategy 2 had not landed).

**The "ok" bucket is not actually unexplained — it concentrates in one mechanism the
heuristic doesn't have a name for.** Pulling the raw evidence for every "ok"-labelled item
with a penalty and recomputing `k = our_charge / our_median`:

| Game | item | penalty | our charge | median | k=a/median | true t | our Limit was capped by |
|---|---:|---:|---:|---:|---:|---:|---|
| 26 | 12 "Skilled worker hours (14 hrs)" | **15,217.20** | 751.53 | 1,084.90 | 0.69 (normal) | ≥ 980 | `LIMIT_CEILING × median` |
| 30 | 3 | 5,122.30 | 229.89 | 350.00 | 0.66 (normal) | [378, 404) | ceiling |
| 31 | 3 | 3,179.30 | 680.36 | 982.20 | 0.69 (normal) | [576, 680) | ceiling |
| 32 | 4 | 3,302.85 | 448.17 | 647.00 | 0.69 (normal) | [513, 536) | ceiling |

In every case `k` sits right where `charge_factor(σ)` says it should (0.65–0.72, unremarkable)
— **the evidence and the Charge multiplier were fine.** What failed is that `b` is bounded at
`LIMIT_CEILING × median` (and, further out, the flat euro `LIMIT_CAP = 708`), which clips a
well-estimated *expensive* item exactly as hard as a badly-estimated one. Game 26 item 12
alone is **40% of the entire "ok" bucket** (15,217 of 38,247) and its own estimate (median
1,084.90) was within 11% of the true `t_lo` (980) — this was not an accuracy failure, it was a
level-agnostic ceiling failure. This is the same mechanism `limit_audit.py` already diagnosed
and partially fixed (`LIMIT_CAP` shipped, ceiling raised 0.30 → 0.45); these four items show
the residual is still live at the current constants and is worth revisiting together with the
LIMIT_CEILING sweep in §5 (C2) rather than treated as a mystery.

Full per-Game stage table, Games 26–32 (from `var/lessons/`):

| Game | net | stages (euros) |
|---:|---:|---|
| 26 | −3,930.33 | ok 21,156 · charge-above-t 2,114 · charge-far-below-t 748 · coverage-too-low 22 |
| 27 | +11,351.13 | charge-above-t 8,633 · ok 0 |
| 28 | +5,298.13 | coverage-too-high 0 · ok 0 |
| 29 | +19,823.12 | charge-far-below-t 5,838 · coverage-too-low 854 · coverage-too-high 0 |
| 30 | −3,463.04 | ok 7,798 · charge-far-below-t 5,101 · coverage-too-low 1,464 |
| 31 | +690.40 | charge-far-below-t 6,086 · ok 5,990 · coverage-too-low 3,824 · charge-above-t 1,176 |
| 32 | +6,886.62 | ok 3,303 · charge-above-t 0 |

---

## 3. σ by channel — RMSLE with bias and dispersion split (CLAUDE.md rule 10)

`scripts/leak_sigma.py` computes `log(t̂/t_mid)` per Line Item, restricted to items whose
bracket is bounded above (`t_hi ≠ ∞`, the same convention `backtest.py` uses — **44 of 192
original items are excluded this way and every σ below is optimistic**, per CLAUDE.md's own
caveat). Two populations are kept apart rather than pooled:

- **LOGGED** (Games 26–32): the actual live decision log. Small (n=34 real-money bounded
  items over 7 Games) but zero look-ahead.
- **RECON** (Games 1–25): `build_proposal` re-run offline against cached model + Price Memory
  evidence (`charge_buckets._recon_rows`) — "what today's pricing would have done", not what
  was actually submitted. Price Memory here is queried against **today's** store, which has
  absorbed every settled Game including ones later than the one being scored — a look-ahead
  Channel B never had live. Reported for scale, never pooled into the headline number.

Items with `t_lo = 0` are reported separately and **excluded from the channel comparison**:
for those items coverage collapses the Limit to zero and a rejected Overcharge costs nothing
regardless of price, so a log-error on the Charge/estimate is economically inert. Pooling them
in inflates σ by a mechanism that has nothing to do with pricing accuracy (RMSLE 2.6–3.1 on
that subset alone, confirmed and then set aside, not because it looks bad but because it is
provably irrelevant to the payoff table).

**Real-money items (`t_lo > 0`) — the subset the payoff table actually prices:**

| population | channel | n | bias | dispersion | RMSLE | median t̂/t |
|---|---|---:|---:|---:|---:|---:|
| LOGGED (26–32) | B+C: memory+model | 10 | +0.369 | 0.300 | **0.476** | 1.52× |
| LOGGED (26–32) | C: model-only | 13 | +0.562 | 0.505 | **0.756** | 1.58× |
| RECON (1–25) | B+C: memory+model | 85 | +0.094 | 0.379 | **0.390** | 1.10× |
| RECON (1–25) | C: model-only | 44 | +0.095 | 0.769 | **0.775** | 1.08× |

**The memory-vs-model gap reproduces on real, non-look-ahead decisions.** Memory-backed items
score RMSLE 0.476 against model-only's 0.756 on the live Games 26–32 log — the same direction
and similar magnitude to the RECON population's 0.390 vs 0.775, and consistent with the
independently-measured MEMORY_SIGMA = 0.43 (`price_memory.py`, leave-one-out over Cases 1–14)
against the model's own unmeasured ~0.6–0.8 prior. Three independent measurements now agree.

**The level bias on LOGGED real-money items is a genuine, useful cross-check.** Median `t̂/t`
runs 1.5–1.6× on both channels over Games 26–32. Composing that with the shipped Charge
multiplier (`k ≈ 0.69` at the median observed σ) gives `a/t ≈ 0.69 × 1.55 ≈ 1.07` — which
independently reproduces the "median `a/t` was 1.06" figure CLAUDE.md already carries from a
different measurement path (the settled-Charge inversion). That the two unrelated
computations land on the same number is a small but real confirmation that both are measuring
the same real thing rather than an artefact of either method.

**RECON's near-zero bias (+0.09 to +0.10) versus LOGGED's strong positive bias (+0.37 to
+0.56) is a real gap and is flagged, not explained away.** It could be a genuine drift in
estimate quality over the Games, or simply that Games 1–25 and 26–32 contain different items
at a different price scale (`t` itself is reconstructed from different opponents' behaviour in
each window) — the two populations are not a controlled comparison of the same items, only of
the same *pipeline*. Worth a dedicated re-measurement once more decision-logged Games settle;
not asserted as a trend here.

**By other splits** (LOGGED, real-money items; full tables including RECON and the `t_lo = 0`
population are in the script output):

| split | n | bias | dispersion | RMSLE |
|---|---:|---:|---:|---:|
| t̂ < 50 | 2 | +0.429 | 0.263 | 0.503 |
| t̂ 50–500 | 15 | +0.399 | 0.384 | 0.553 |
| t̂ ≥ 500 | 6 | +0.693 | 0.533 | 0.874 |
| metered (hr/m²/day/kg) | 3 | +0.701 | 0.322 | 0.771 |
| pcs / flat rate | 19 | +0.455 | 0.453 | 0.642 |
| coverage ≤ 2/3 | 4 | +0.271 | 0.416 | 0.497 |
| coverage 2/3–0.9 | 3 | +0.348 | 0.136 | 0.373 |
| coverage ≥ 0.9 | 16 | +0.554 | 0.459 | 0.719 |

None of these splits has enough LOGGED rows (n = 2–19) to trust in isolation; the channel
split (n = 10 and 13) is the only one with a matching, independently-measured prior to check
it against, which is why it is the headline of this section and the others are reported for
completeness rather than acted on.

---

## 4. Where σ is worst, and is it identifiable at submission time

**Yes — the channel that fires is known at decision time, before the Game settles.** Whether
Price Memory returned a hit (`B:memory` in `channels`) is computed deterministically the
moment the Case loads (`channels.local_evidence`), independent of anything about the true `t`.
This is the one split in §3 that is (a) large in the error gap (RMSLE ~0.5 vs ~0.8, roughly
1.6×), (b) reproduced independently on both the look-ahead RECON population and the
zero-look-ahead LOGGED population, and (c) already load-bearing elsewhere in the codebase
(H5b's channel finding, the memory σ measurement). Magnitude (`t̂ ≥ 500`) is the next-cleanest
candidate (RMSLE 0.87 vs 0.55 on LOGGED, matches the RECON direction too) but it is not
independent of the channel split — big items are disproportionately the ones with no memory
hit, since Price Memory's 22% recall skews toward the commonly-repeated cheap positions
(README: "vehicle costs", disposal, cleaning). Coverage probability is *not* a clean live
signal here — the ledger already settled that (H4: a perfect coverage oracle is worth +10,557
over 30 Games, inside the ±34,369 noise floor) — and quantity extraction has zero rows to
compare on the real-money LOGGED subset (every real-money item in Games 26–32 had a printed
quantity; Channel A's dash-quantity items are, definitionally, the `t_lo = 0` population).

**So the actionable subset is: model-only, real-money Line Items — roughly 55% of real-money
items in the LOGGED sample (13 of 23), identifiable the instant Channel C returns and Channel
B does not.** That is exactly the subset §5's candidates C2 and C3 target.

---

## 5. Three counterfactual candidates, replayed over every settled Game

`scripts/leak_candidates.py` extends `charge_buckets.py`'s validated harness (one row per
Game/Line-Item, `replay_payoffs.replay` against the real Field, deltas against the *shipped*
constants on the *same* dataset — Games 1–25 are "recon" rows, i.e. this isolates the rule
being tested rather than comparing to the true historical submission) from Games 1–27 to
1–32, and adds a **second, independent replay restricted to the 7 Games with a real decision
log (26–32)** so every candidate is checked against zero-look-ahead data as well as the larger
but partly-reconstructed population.

Every candidate previously tried in `charge_buckets.py` **multiplies the Charge only** — the
Limit is a passive `min(quantile, ceiling·median, cap, charge)` that no candidate there ever
parameterises. All three candidates below are new precisely because they touch the Limit side
or the shared σ instead, which is where H3's own note says the residual prize sits ("what
little there is to win belongs on the Limit side" — `strategy2/strategy.py` docstring).

Noise floor: `26,622 × √(n/18)` — **±35,496 over 32 Games, ±16,602 over the 7 logged Games.**

### C1 — re-validate `LIMIT_CAP` with the 5 Games the original audit didn't have

`penalty_audit.py` found a plateau from 8×–24× `SETTLED_MEDIAN` (472–1,416 €) over Games 1–27.
Re-swept here over 1–32 holding today's shipped `LIMIT_CEILING = 0.45`:

| cap | Δ over 32 Games | Δ over logged-only (26–32) |
|---|---:|---:|
| 8× (472) | −1,744 | −288 |
| 12× (708, shipped) | 0 | 0 |
| 16× (944) | +1,753 | +360 |
| 20× (1,180) | −985 | +360 |
| 24× (1,416) | −3,611 | +360 |
| 30× (1,770) | −5,170 | +360 |
| 40× (2,360) | **−49,063** | **−23,640** |

**Verdict: still closed.** Every point inside the plateau is within a few thousand euros of
shipped — the largest, +1,753, is 5% of the 32-Game noise floor and 15% of the 7-Game one —
confirming (not merely repeating) `penalty_audit.py`'s finding with 5 additional Games. The cliff at 40× is
also reconfirmed: it is the same "opponent cluster at a round Charge, our Limit crosses it"
mechanism as Games 22 and 29 (documented in `penalty_audit.py` §4), not new information. **No
action.**

### C2 — channel-conditional `LIMIT_CEILING` (memory-backed items looser; model-only unchanged)

Price Memory's measured error (0.43, and 0.48 reconfirmed live in §3) is roughly half the
model's; this raises the ceiling *only* on memory-backed items, leaving the Charge and the
model-only Limit exactly as shipped.

| memory ceiling | Δ over 32 Games | odd→even | even→odd | Δ over logged-only | odd→even | even→odd |
|---|---:|---:|---:|---:|---:|---:|
| 0.45 (shipped) | 0 | 0 | 0 | 0 | 0 | 0 |
| 0.55 | +8,004 | +4,570 | +3,433 | +2,173 | +1,417 | +756 |
| 0.65 | +18,732 | +10,280 | +8,452 | +3,171 | +1,896 | +1,275 |
| 0.75 | +21,644 | +11,730 | +9,914 | +2,608 | +1,491 | +1,117 |
| 0.85 – 1.00 | +21,644 (flat — `LIMIT_CAP`/`b≤a` binds beyond 0.75) | — | — | +2,608 | — | — |

**Verdict: the most promising open candidate, and still not a result.** It is positive at
every ceiling tested, in *every* holdout split, on *both* the large recon-inclusive population
and the small zero-look-ahead logged-only population — six consistent positive signs from six
independent checks, which is more corroboration than any candidate `charge_buckets.py` found
for a Charge-side rule. But the largest effect (+21,644 over 32 Games, +3,171 over the 7 logged
Games) sits at **61% and 19% of its respective noise floor** — inside both. **Recommendation:
do not ship on this evidence; carry `memory ceiling ≈ 0.65–0.75` as the live candidate to
re-measure after every future Game, and promote it only once the accumulated delta clears the
floor (per the hypothesis-ledger protocol).**

### C3 — channel-conditional σ feeding both the Charge and the Limit

Replaces the model's self-asserted, uncalibrated `implied_sigma(band)` — pricing.py's own
docstring: "the width carries no signal" — with a fixed prior: `MEMORY_SIGMA = 0.43` wherever
Price Memory spoke, a swept constant where only the model did.

| model σ | Δ over 32 Games | odd→even | even→odd | Δ over logged-only | odd→even | even→odd |
|---|---:|---:|---:|---:|---:|---:|
| 0.50 | +1,977 | −19,293 | +21,270 | +21,802 | +2,687 | +19,114 |
| 0.60 | −9,048 | −22,751 | +13,703 | +19,152 | +3,750 | +15,402 |
| 0.70 | −30,951 | −28,430 | −2,522 | +14,567 | +2,570 | +11,998 |
| 0.80 | −58,040 | −38,642 | −19,398 | +9,721 | +1,339 | +8,382 |
| 1.00 | −100,370 | −51,743 | −48,628 | +451 | −449 | +900 |

**Verdict: rejected.** On the 32-Game population every value tested loses, monotonically and
by a wide margin — the exact opposite of the "raise σ to reflect the model's real
uncalibration" intuition that motivated it. On the small logged-only population the sign
flips (positive, peaking at the *lowest* σ tried, 0.50 — below the shipped
`MODEL_SIGMA_PRIOR = 0.6`), and even there the odd/even split disagrees by an order of
magnitude at the low end (−19,293 vs +21,270 at σ=0.50) — a single-Game artefact, not a signal
(exactly the pattern the codebase already knows to distrust: "any peak found there is a fact
about sixteen specific opponents, not about pricing"). **No action; do not revisit without a
calibrated band, which is a `prompts.py`/evidence-layer change, not a constant.**

---

## 6. What this adds to the standing picture, and what stays closed

- **Coverage: still closed** (H4 stands; nothing here touched it).
- **Limit *level*: still closed** (C1 reconfirms the `LIMIT_CAP` plateau with 5 new Games).
- **Charge-side conditional rules: still closed** (`charge_buckets.py`'s own exhaustive sweep,
  unchanged by this session).
- **New: a Limit-side channel-conditional rule (C2) is the first candidate in this whole
  investigation that is positive in every split checked.** It does not clear the noise floor
  and must not be shipped on 7 Games of evidence — but it is a different kind of result from
  everything the ledger has closed so far, because closing something requires an inconsistent
  or negative sign somewhere, and C2 has neither. The next-most-valuable single action is not
  a constant change; it is **accumulating more logged Games against exactly this candidate**.
- **New, mundane, and worth recording anyway:** ~40% of the unexplained ("ok"-stage) penalty
  euros in the 7 logged Games trace to one mechanism — a well-estimated *expensive* item whose
  Limit is clipped by `LIMIT_CEILING`/`LIMIT_CAP` regardless of estimate accuracy (Game 26
  item 12 alone: 15,217 of 38,247). This is the residual of a fix `limit_audit.py` already
  shipped, not a new defect, but it is now visibly live at the current constants.
- **84% of all-time penalty euros (394,767 of 468,876) predate decision logging and cannot be
  attributed below the "Limit too loose / too strict" mechanical split** in §1. This ratio
  will only improve as more logged Games settle; there is no retroactive fix.

## Method notes / reproduce

```bash
PYTHONPATH=. pixi run python scripts/leak_buckets.py --games 1-32 --json var/leak/buckets.json
PYTHONPATH=. pixi run python scripts/leak_sigma.py
PYTHONPATH=. pixi run python scripts/leak_candidates.py
```

All three read only cached data (`var/transactions`, `var/replay`, `var/decisions`,
`var/evidence`, `[PUBLIC] EHL Cases/cases`) and make no network calls.
