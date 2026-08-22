# LIMIT_CAP audit — the absolute cap is already right; the ceiling is the lever

Scope: every settled Game at time of writing — **§§1–3 and §6 use Games 1–36** (425 priced
rows via `scripts/charge_buckets.dataset()`); **§4a and §5 were re-run one game later, against
Games 1–37 (442 rows)**, because `data/price_memory.json`/`var/price_memory.json` was rebuilt
mid-session (~22:29, `scripts/build_price_memory.py`, going from a Games-1–14/98-entry store
to a **Games-1–36/175-entry store**) and the memory-conditional ceiling — the headline result
— had to be re-measured against the store it will actually ship with. **Every table below
states which store it used; that ambiguity is exactly what made the two measurements hard to
compare, so it is called out explicitly rather than silently reconciled.** The store now
regrows roughly every 12.6 minutes via `learn_watch`; §4a/§5 pin a copy
(`scripts/experiments/memory_refresh_sweep.py::pin_store`) before sweeping so the numbers
don't drift mid-run.

Five new, read-only scripts, all under `scripts/experiments/`, none touching `src/`,
`main.py` or `pixi.toml`, no network/LLM calls beyond what `replay_payoffs`'s own disk cache
already needed (the memory-refresh re-run below calls a local JSON lookup, never the model):

- `limit_binding_audit.py` — which of `LIMIT_QUANTILE` / `LIMIT_CEILING` / `LIMIT_CAP` /
  the `b ≤ a` charge-clamp is the *binding* constraint on each row, and what wrongful-
  rejection penalty sits behind each, on today's shipped constants.
- `cap_ceiling_sweep.py` — `LIMIT_CAP` swept in isolation, and `LIMIT_CEILING` swept
  conditioned on estimate confidence (memory channel, band width, coverage probability),
  in euros against the real Field, with held-out folds. (Against the **stale** store —
  superseded for the memory candidate by the next script, kept as the "before" baseline.)
- `memory_refresh_sweep.py` — re-runs the memory-conditional ceiling sweep and the
  fair-vs-Overcharge split against the **refreshed** store, without calling the model:
  rows already memory-backed keep their original (already-correctly-blended) evidence;
  rows that were model-only get a fresh local Channel B lookup and, on a hit, a
  `combine()` blend exactly as the shipped pipeline would produce. Also splits the
  memory-backed population into *already-reachable* (had a hit before) and
  *newly-reachable* (hit only under the rebuilt store).
- `fair_vs_overcharge_split.py`, `coverage_collapse_breakdown.py`, `prize_verify.py` —
  supporting analyses referenced below.

**Bottom line, up front, in the words the brief asked for:** the absolute cap is already
right. Leave `LIMIT_CAP` at 708. The lever this audit actually found is a **memory-channel-
conditional `LIMIT_CEILING`** — not the cap the brief opened with. Against the store the repo
now ships (Games 1–36, re-measured on Games 1–37), it is worth an estimated **+40,791 over 37
Games (≈1,103/Game)**, positive on every held-out fold tried in both windows, with a
fair-to-Overcharge ratio of **7.53:1** — and the previously-unreachable items the bigger store
newly covers are priced *better*, not worse, than the ones it already covered (14.63:1 on the
newly-reachable slice against 5.85:1 on the rest). It is a real, well-attested, and now
larger edge — still inside the noise floor, still not the 10,009-a-item prize the motivating
example implied, but roughly 1.8× the size measured against the store this audit started
with.

---

## 0. Baseline, verified before anything else was compared

Per the standing rule: nothing below is trustworthy until the harness itself is.

```
PYTHONPATH=. pixi run python scripts/replay_payoffs.py --self-check
PYTHONPATH=. pixi run python scripts/invert_fair_values.py --verify
```

- `replay_payoffs.py --self-check`: **all 36 usable Games reproduce their published net to
  the cent.** (`reconstructs (36): [1..36]`, `UNUSABLE (0): none`.)
- `invert_fair_values.py --verify`: **OK on every Game with a published `/matrix` cell**
  (Games 16–35 at time of writing; 36 had not yet reached the trailing 20-Game window).
  Games 1–15 report "no published cell — outside the 20-Game /matrix window", which is the
  tool's own documented limitation, not a failure — there is nothing to verify them against.

Both hold. Everything below is computed on top of this.

---

## 1. Binding-frequency table — how often does each clamp actually bind?

`price_item` computes `b = min(quantile_limit, LIMIT_CEILING·median, LIMIT_CAP, charge)`
(plus the `b=0` coverage collapse below `COVERAGE_FLOOR`). Applying **today's shipped
constants** (`LIMIT_CEILING=0.45`, `LIMIT_CAP=708`, `LIMIT_QUANTILE=1/3`) to every row:

| binding constraint | items | item share | wrongful-rejection penalty | penalty share |
|---|---:|---:|---:|---:|
| `LIMIT_CEILING` (0.45 × median) | 271 | 63.8% | 511,664 | 70.4% |
| coverage-collapse (`b = 0`) | 137 | 32.2% | 102,323 | 14.1% |
| `LIMIT_CAP` (708 flat) | 16 | 3.8% | 112,242 | 15.4% |
| `LIMIT_QUANTILE` | 1 | 0.2% | 503 | 0.1% |
| **total** | **425** | | **726,732** | |

`LIMIT_QUANTILE` binds on effectively nothing (1 item), confirming the earlier finding that
it is decorative — `b = min(CEILING·median, CAP, charge)` in practice. The ceiling does most
of the work by both item count and penalty. **The cap is not negligible** — 3.8% of items,
15.4% of penalty — but it binds on a population that barely overlaps the ceiling's, which is
why it is analysed as a separate, narrower lever below rather than folded into the ceiling
sweep.

### 1a. Correcting the two motivating examples

The brief's own motivating evidence turns out to be ceiling-bound, not cap-bound:

| item | `t̂` | `0.45 × t̂` | `LIMIT_CAP` | binds | true `t` |
|---|---:|---:|---:|---|---:|
| G34 item 20 | 955 | **430** | 708 | ceiling | ≥ 877 |
| G26 item 12 | 1,085 | **326**¹ | 708 | ceiling | ≥ 1,097² |

¹ at the `LIMIT_CEILING = 0.30` live at that decision (raised to 0.45 the same night this
constant's docstring narrates the "Bound the Limit absolutely" commit — the value shipped at
Game 26 differs from today's).
² recovered Fair Value bracket for Game 26 item 12.

This was verified independently by direct computation (`price_item` on the logged evidence)
before it was raised by the coordinator mid-session, and the two readings matched exactly.
**The cap does still bind elsewhere** — see §3 — just not on either item originally cited.

---

## 2. `LIMIT_CAP` swept in isolation — a clean negative

`LIMIT_CEILING` and `LIMIT_QUANTILE` held at shipped values; only the cap moves. Noise floor
`26,622·√(n/18)`.

**Games 19–32** (shipped net +74,338, noise floor ±23,478):

| cap | net | Δ vs shipped | odd fold | even fold | ≤25 fold | >25 fold |
|---|---:|---:|---:|---:|---:|---:|
| 708 (shipped) | 74,338 | 0 | 0 | 0 | 0 | 0 |
| 1,000 | 74,409 | +71 | +787 | −716 | −289 | +360 |
| 1,500 | 71,260 | −3,078 | −455 | −2,623 | −3,438 | +360 |
| 2,500 | 25,808 | −48,529 | −24,455 | −24,075 | −24,889 | −23,640 |
| ∞ | 25,808 | −48,529 | −24,455 | −24,075 | −24,889 | −23,640 |

**All 36 settled Games** (shipped net +193,313, noise floor ±37,649):

| cap | net | Δ vs shipped | odd fold | even fold | ≤18 fold | >18 fold |
|---|---:|---:|---:|---:|---:|---:|
| 708 (shipped) | 193,313 | 0 | 0 | 0 | 0 | 0 |
| 1,000 | 194,077 | +763 | −85 | +849 | +692 | +71 |
| 1,500 | 188,357 | −4,957 | −3,899 | −1,058 | −533 | −4,424 |
| 2,500 | 141,284 | −52,029 | −29,519 | −22,510 | −533 | −51,496 |
| ∞ | 141,284 | −52,029 | −29,519 | −22,510 | −533 | −51,496 |

**Verdict: a clean negative.** 1,000 is a coin flip (sign-flips between odd and even folds,
in both windows) — noise, not signal. Everything past ~1,500 loses money outright, at roughly
1.4–2× the noise floor. This reproduces and re-confirms the 8×–24× (472–1,416) plateau found
in the original `penalty_audit.py` audit, now re-measured with 9 more settled Games (28–36):
**708 sits inside the plateau and there is no case for moving it.** Leave `LIMIT_CAP` at 708.

---

## 3. The nine cap-bound items with penalty, inspected item by item

Given the cap binds on only 16 items (9 with non-zero penalty), a numeric sweep conditioned
on confidence would not survive a held-out fold at this sample size — the honest answer is
inspection, not a fitted number.

| item | `t̂` | `t` (bracket) | `t̂/t` | sigma | penalty | verdict |
|---|---:|---|---:|---:|---:|---|
| G17 item 16 | 2,300 | [2,600, 2,732] | 0.84–0.88 | 0.24 | 23,238 | well-estimated |
| G20 item 1 | 1,935 | [2,345, ∞) | ≤0.83 | 0.35 | 19,119 | well-estimated |
| G12 item 12 | 2,129 | [2,321, ∞) | 0.92 | 0.35 | 20,930 | well-estimated |
| G7 item 1 | 1,849 | [1,233, 1,756] | 1.05–1.50 | 0.35 | 9,888 | well-estimated |
| G24 item 2 | 1,800 | [1,365, 1,676] | 1.08–1.32 | 0.39 | 3,700 | well-estimated |
| G27 item 3 | 3,795 | [3,000, 3,022] | ~1.26 | **1.22** | 9,713 | decent point estimate, **band flagged huge uncertainty** |
| G24 item 4 | 2,800 | [1,024, 1,620] | 1.73–2.73 | 0.50 | 2,605 | overestimated |
| G19 item 4 | 3,600 | [854, 1,242] | 2.90–4.21 | 0.39 | 1,282 | overestimated |

Five of nine (66,875 of the 112,242 cap-bound penalty) sit on genuinely well-estimated items
— `t̂/t` within roughly 0.8–1.5. This is the original hypothesis, confirmed on a smaller and
different population than the motivating examples pointed to. Two are simple overestimates.
**One is the interesting case**: G27 item 3's point estimate is fine, but its own band
carries `sigma = 1.22` — the evidence layer already flagged this item as unreliable. A
confidence-conditional cap keyed on **sigma, not just channel**, would correctly keep the
five well-estimated items and drop this one along with the two overestimates — that is the
whole hypothesis in miniature. `n = 9` is too small to fit and fold-test a threshold on; this
is reported as an observation, not a shipped rule.

---

## 4. The confidence-conditional `LIMIT_CEILING` sweep — the actual lever

`LIMIT_CAP` held at 708. Ceiling loosened only for a subset of items; the rest keep the
shipped 0.45. All deltas are against the shipped rule, same dataset, same replay.

### 4a. Memory-channel conditional (the strongest candidate)

Price Memory items get a looser ceiling; model-only items stay at 0.45. **Two measurements,
against two store vintages, both reported — the second supersedes the first as the shipping
number.**

**(i) Against the store this audit started with** (Games 1–14, ~98 entries — whatever the
cached/logged evidence already reflected when §§1–3 were run):

**Games 19–32** (noise floor ±23,478):

| memory ceiling | net | Δ | odd fold | even fold | ≤25 fold | >25 fold |
|---|---:|---:|---:|---:|---:|---:|
| 0.45 (shipped) | 74,338 | 0 | 0 | 0 | 0 | 0 |
| 0.65 | 79,963 | +5,626 | +3,004 | +2,621 | +2,455 | +3,171 |
| **0.75** | **80,042** | **+5,704** | **+3,236** | **+2,469** | **+3,096** | **+2,608** |
| 0.85–1.50 | 80,042 | +5,704 | (identical — saturates) | | | |

**All 36 settled Games** (noise floor ±37,649):

| memory ceiling | net | Δ | odd fold | even fold | ≤18 fold | >18 fold |
|---|---:|---:|---:|---:|---:|---:|
| 0.45 (shipped) | 193,313 | 0 | 0 | 0 | 0 | 0 |
| 0.65 | 213,380 | +20,066 | +8,991 | +11,075 | +13,107 | +6,960 |
| **0.75** | **216,464** | **+23,150** | **+10,439** | **+12,711** | **+15,940** | **+7,211** |
| 0.85–1.50 | 216,464 | +23,150 | (identical — saturates) | | | |

**(ii) Against the store the repo now ships** (Games 1–36, 175 entries, pinned copy,
re-measured on 37 settled Games — `memory_refresh_sweep.py`, no model call, see the
provenance note above):

**Games 19–32** (noise floor ±23,478):

| memory ceiling | net | Δ | odd fold | even fold | ≤25 fold | >25 fold |
|---|---:|---:|---:|---:|---:|---:|
| 0.45 (shipped) | 93,423 | 0 | 0 | 0 | 0 | 0 |
| 0.65 | 105,502 | +12,078 | +4,557 | +7,522 | +6,161 | +5,917 |
| **0.75** | **106,021** | **+12,598** | **+4,981** | **+7,617** | **+6,996** | **+5,602** |
| 0.85–1.50 | 106,021 | +12,598 | (identical — saturates) | | | |

**All 37 settled Games** (noise floor ±38,169):

| memory ceiling | net | Δ | odd fold | even fold | ≤19 fold | >19 fold |
|---|---:|---:|---:|---:|---:|---:|
| 0.45 (shipped) | 227,759 | 0 | 0 | 0 | 0 | 0 |
| 0.65 | 262,158 | +34,399 | +13,893 | +20,506 | +16,203 | +18,197 |
| **0.75** | **268,550** | **+40,791** | **+16,935** | **+23,856** | **+20,261** | **+20,530** |
| 0.85–1.50 | 268,550 | +40,791 | (identical — saturates) | | | |

**Positive on all four folds in both windows, in both measurements.** No other candidate in
this audit clears that bar. It saturates exactly at 0.75 in both — some other clamp (the
charge itself, or the cap) takes over past that point, and the saturation point did **not**
move when the store grew — so 0.75 is the natural stopping point, not an arbitrary one, and
it is stable across store vintages.

**The refreshed measurement is roughly 1.75–2.2× the original** (+40,791 vs +23,150 over the
full sample; +12,598 vs +5,704 over Games 19–32) — bigger, and with better-balanced folds
(the all-37-Games split is 16,935/23,856, closer to even than the original 10,439/12,711 was
already, and both clear the bar comfortably). This is the number to plan against.

#### 4a-ii. Already-reachable vs newly-reachable — is the bigger store just noise?

The question that decides whether this ships: do the Line Items the bigger store *newly*
covers behave like the ones it already covered, or are they lower-quality hits dragging the
average down? Split by whether a row had a memory hit before the rebuild ("already") or only
after it ("newly"), same 37-Game population, ceiling 0.75:

| population | items | fair instances | fair saving | Overcharge instances | Overcharge cost | ratio | net |
|---|---:|---:|---:|---:|---:|---:|---:|
| already-reachable | 230 | 433 | 29,598 | 47 | 5,059 | 5.85 : 1 | 24,539 |
| **newly-reachable** | **74** | **185** | **17,444** | **7** | **1,192** | **14.63 : 1** | **16,252** |
| **combined** | **304** | **618** | **47,042** | **54** | **6,251** | **7.53 : 1** | **40,791** |

**The newly-reachable slice is not noise — it is priced better than the slice already in
production**, both in ratio (14.63:1 against 5.85:1) and in the near-total absence of
Overcharges (7 instances against 47). This matches the store's own measured leave-one-out
error falling as it grew (more occurrences per key, better per-unit normalisation on repeat
wordings) rather than being diluted by marginal, noisy entries. It is the difference between
a coincidence and a mechanism, and it points the right way.

One caveat stated rather than smoothed over: "already-reachable" here means "already had a
`B:memory` hit in the dataset this audit's first pass measured" — a workable *before* state
for this specific A/B, but not a verified reproduction of a literal Games-1–14-only store (no
such pinned artifact was rebuilt and diffed for this check). The 52%→69% row-share expansion
measured here is smaller (≈1.3×) than the ≈2.4× implied by the store's own internal recall
metric (22%→53% on a different, positive-`t`-only denominator) — the two are different
measurements of related things, not a contradiction, but they should not be treated as the
same number.

*(§§4b–4e below were run against the stale (1–14) store only and not re-measured against the
refreshed one — they were already negative or redundant findings, and there is no mechanism
by which a bigger memory store would turn a fold-inconsistent or non-independent signal into
a robust one, but this is stated as an assumption, not a re-verified fact.)*

### 4b. Band-width conditional (weak, fold-inconsistent — not recommended)

Ceiling loosened only when `sigma < 0.30` (a "confident" band). All 36 Games: best case
+5,837, but the **odd fold is −503** — sign-flips. On Games 19–32 the effect is a rounding
error either way (−475 flat past 0.60). The band width does not carry a usable signal here,
consistent with `src/domain/pricing/engine.py`'s own finding that `implied_sigma`'s width
does not order the estimator's error.

### 4c. Coverage-probability conditional (same magnitude, not an independent signal)

Ceiling loosened when `coverage_probability ≥ 0.90`. All 36 Games: **+23,568**, almost
identical in size to the memory-conditional candidate — but the fold split is **+1,790 odd /
+21,778 even**, a 12:1 imbalance against memory's near-even 10,439/12,711. The reason: **64%
of memory-backed items already have `coverage_probability ≥ 0.90`, and 59% of high-coverage
items are memory-backed** — this candidate is substantially riding the same population as
4a, just less cleanly. Not recommended as a separate lever; the memory channel is the better-
attested version of the same signal.

### 4d. Combined family — a modest cap raise on top of the memory ceiling

The brief asked to treat the cap and C2-style conditional ceiling as one family and find the
best member. Testing memory-ceiling 0.75 together with a cap raise:

| candidate | 19–32 net (Δ) | folds | 36-Game net (Δ) | folds |
|---|---:|---|---:|---|
| memory 0.75, cap 708 | 80,042 (+5,704) | all 4 positive | 216,464 (+23,150) | all 4 positive |
| memory 0.75, cap 1,000 | **80,851 (+6,514)** | all 4 positive | 216,335 (+23,021) | mixed magnitude, still positive |
| memory 0.75, cap 1,500 | 78,866 (+4,528) | positive | 211,247 (+17,934) | positive but smaller |

A cap of 1,000 adds a little on the recent window and costs nothing on the full sample — but
§2 already showed cap=1,000 **in isolation** sign-flips across folds, so this is reported as
"does not hurt when combined with the memory ceiling," not as a second strong recommendation.
**Leave the cap at 708** and treat this as a note for the next re-measurement, not a change.

### 4e. Guardrail check: global (non-conditional) ceiling loosening stays closed

For completeness, a flat `LIMIT_CEILING = 0.75` applied to **every** item (not just
memory-backed) was checked against the standing guardrail (`b = k·t̂` monotonically
decreasing, k=0.20 → +109,123 down to k=1.00 → −14,452 over Games 19–32 — do not loosen the
multiplier globally). It fails exactly where the guardrail predicts: **Games 19–32, odd fold
−2,749 and the late (>25) fold −2,274**, even though the same flat change looks positive on
the larger 36-Game sample (+25,224). This is the textbook "wins on the bigger in-sample pool,
loses on the fold that matters" pattern this repo has been burned by before. **Not proposed.**
The gain is conditional on the memory channel, not a license to loosen the ceiling in general.

---

## 5. Fair-vs-Overcharge split — the whole decision, made explicit

For the winning candidate (memory ceiling 0.75, cap 708 unchanged), every opponent Charge
that becomes newly acceptable (previously above the shipped Limit, now at or below the
candidate's) was classified. **Refreshed store (Games 1–36, 37 Games replayed) first — this
is the number that ships**; the original stale-store measurement is kept underneath as the
"before" comparison it superseded.

**Refreshed store:**

| | instances | euros | note |
|---|---:|---:|---|
| newly-accepted **fair** Charges (`a ≤ t`) | 618 | **47,042** saved | at `0.5a` each — the fair Charge was already owed; this is the excess between the `1.5a` penalty and the `a` we'd pay outright, **not the full penalty** |
| newly-accepted **Overcharges** (`a > t`) | 54 | **6,251** cost | full `a` — the opponent's own secret Cap has never bound in the settled record, so `min(a, c) ≈ a` |
| **net** | | **+40,791** | matches the sweep total in §4a(ii) exactly |
| **ratio** | | **7.53 : 1** | fair savings : Overcharge cost, up from 5.67:1 on the stale store |

Split further in §4a-ii: the newly-reachable slice alone runs **14.63:1** (185 fair
instances against 7 Overcharge instances) — the store's growth is adding cleaner hits, not
diluting the average.

**Stale store, for comparison (what was originally measured, before the rebuild):**

| | instances | euros |
|---|---:|---:|
| newly-accepted fair Charges | 413 | 28,110 saved |
| newly-accepted Overcharges | 45 | 4,960 cost |
| net | | +23,150 |
| ratio | | 5.67 : 1 |

168 items were widened by the stale-store candidate across 27 of 36 Games; only 3 Games (7,
14, 32) came out net-negative, each by under 1,000. In both measurements this is the concrete
version of the brief's warning against double-counting: the net recovered is **already** the
`0.5a` figure net of the Overcharges it buys — it is not a penalty total, it is the
counterfactual replay delta.

---

## 6. Coverage-collapse — reported as asked, not re-opened as a lever

The coverage verdict itself is a closed lever (a perfect oracle is worth +10,557 over 30
Games, inside the noise floor — not re-measured here). What was asked instead: of the
102,323 penalty sitting on the 137 coverage-collapsed (`b = 0`) items, how much reflects a
**wrong** collapse (true `t > 0`) versus a threshold placed in the wrong spot?

- **100% of the penalty sits on items where `t > 0`.** This is arithmetic, not a
  measurement: a wrongful-rejection penalty under `b = 0` requires an opponent Charge in
  `(0, t]`, which cannot exist when `t = 0`. The 9 collapsed items with confirmed `t = 0`
  carry exactly 0 penalty, as they must.
- **Only 6,097 (6%) of the 102,323 sits on items with `coverage_probability ≥ 0.30`** — close
  enough to `COVERAGE_FLOOR` (0.667) that a different threshold could plausibly have rescued
  them. **The other 94% is on items the model scored far below any reasonable floor**
  (several at 0.00–0.22), including the single largest item in the whole bucket: **G10 item
  3, `coverage_probability = 0.22`, true `t = 7,225`, penalty 61,302 alone (60% of the whole
  bucket).**
- **Conclusion: this is a verdict-accuracy problem, not a threshold-placement problem.**
  Moving `COVERAGE_FLOOR` cannot reach the items that matter — they were scored nowhere near
  the floor to begin with. This is consistent with, and does not contradict, the closed
  coverage-oracle result: large individual misses exist, but they are rare and (per the
  oracle study) roughly offset by false positives elsewhere, so there is little aggregate
  room even though any one miss can be large. Not a lever to reopen.

---

## 7. The oracle gap, verified independently

The coordinator's Reviewer-cost table was replayed independently against
`scripts/replay_payoffs.replay`, holding our Charge at what we actually submitted (Reviewer
cost depends only on our Limit and the opponents' Charges):

| Games 13–35 (n=23, noise floor ±30,100) | Reviewer cost | vs actual |
|---|---:|---:|
| actual (what we did) | 529,850.23 | — |
| reject everything (`b = 0`) | 549,931.57 | +20,081 worse |
| **oracle (`b = t`)** | **366,621.05** | **−163,229 better** |
| accept everything (`b = ∞`) | **unbounded** | see below |

Three of four rows tie the coordinator's figures to the cent (529,850 / 549,932 / 366,621),
confirming the same methodology. **The fourth does not resolve to a finite number by
construction**: some opponent Charges were never revealed by any settled Transaction
(rejected by all sixteen Reviewers with nothing owed), and `snapshot()` correctly codes these
as unrecoverable rather than guessing at zero. Accepting everything therefore has literally
unbounded downside in this replay — a real property of the strategy, not a bug in the
harness. The coordinator's cited 824,284 additionally omits these same rows rather than
coding them as unbounded, which makes it **a known-incomplete floor**, not a point estimate;
the true accept-everything cost is higher, by an unknown amount concentrated in exactly the
population most likely to be Overcharges (nobody paid them). Neither number should be quoted
as precise; both agree that accepting everything is dominated, which is the only claim that
matters here.

The **163,229** oracle gap over Games 13–35 (~7,097/Game) is real and verified, and it is the
right way to size the whole family of Limit levers: `LIMIT_CAP` reaches essentially none of
it (§2, negative past the plateau); the memory-conditional `LIMIT_CEILING`, against the store
the repo now ships, reaches an estimated **~40,791 over the 37-Game window it was
re-measured on** — real, positive on every fold tried, and a bigger but still partial share
of the gap, exactly as expected since it only touches the memory-backed slice of items (now
69% of rows rather than 52%, §4a-ii). Most of the 163,229 remains locked behind the
estimator's accuracy on the model-only slice, not the Limit rule, which matches every other
closed lever in this file.

---

## Recommendation

1. **Leave `LIMIT_CAP` at 708.** The isolated sweep (§2) is a clean negative past ~1,000–
   1,500, in both the brief's window and the full sample. The two items that motivated this
   audit were ceiling-bound, not cap-bound (§1a) — but the cap does bind elsewhere, on a
   real, disjoint, and mostly well-estimated population (§3) too small to fit a rule to.
2. **Ship a memory-channel-conditional `LIMIT_CEILING` of 0.75** (model-only items keep
   0.45), measured against the store the repo now ships (Games 1–36, §4a(ii)). This is the
   one candidate in the whole confidence-conditional family that clears the fold-robustness
   bar in both windows tested, in both store vintages: **+40,791 over 37 Games, +12,598 over
   Games 19–32**, positive on every odd/even and time-split fold. The bigger store's newly-
   reachable items price *better* than the ones already in production (14.63:1 against
   5.85:1, §4a-ii) rather than diluting the signal. Still inside the noise floor, so report
   it as "measured and directionally consistent," not "proven" — but it is the strongest
   result this audit or the prior C2 candidate has produced, and it got stronger, not
   weaker, on re-measurement.
3. **Do not condition on band width or coverage probability instead** — band width is
   fold-inconsistent (§4b) and coverage probability is not independent of the memory signal
   (§4c, 59–64% overlap) while being noticeably less fold-robust. (Measured against the
   stale store only; see the caveat before §4b.)
4. **Do not loosen `LIMIT_CEILING` globally.** Checked directly (§4e) and it fails on
   exactly the window the standing guardrail says it should.
5. A modest cap raise to 1,000 alongside the memory ceiling is a low-stakes maybe (§4d,
   stale-store measurement) — worth re-measuring against the refreshed store after the next
   several Games, not worth shipping on this evidence alone.
6. **State the store vintage next to every future re-measurement.** The gap between +23,150
   and +40,791 is not noise or drift — it is the same rule measured against two different,
   correctly-labelled inputs, and both numbers are right for what they measured. Losing that
   label is what made tonight's figures hard to compare in the first place.
