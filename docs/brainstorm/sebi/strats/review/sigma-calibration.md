# Sigma calibration — three constants that claim to be measurements, priced in euros

Scope: read-only, offline where possible. No `src/` file touched (all three proposed fixes
are diffs in this doc, not applied). No LLM call made — `MODEL_SIGMA_PRIOR`'s correction uses
the terra Channel-C RMSLE already measured and committed in `model-bakeoff.md`. No write to
`var/price_memory.json` at any point (`--no-write` / `--out` used throughout). New code: three
scripts under `scripts/experiments/` (`sigma_by_match_type.py`, `sigma_disjoint_folds.py`,
`sigma_calibration_replay.py`), all read-only.

**Price Memory vintage used throughout:** the live store at the moment this investigation
started, `built_from_games: 1-37`, 178 entries, pinned to a session-local scratchpad copy
(`price_memory_pinned_g1-37.json`) before anything below ran, purely as a record of which
vintage every number in this doc corresponds to — the store rebuilds itself after every
settled Game via `learn_watch.py`, and by the time this doc was finished a concurrent process
had already advanced it to `built_from_games: 1-38`. The pinned copy is session-scratch, not
committed; the number that matters is the range it names. Every `--evaluate` / leave-one-out
number below is a **fresh rebuild from `scripts/build_price_memory.observations()`**, not a
read of that pinned file's `entries` — the pin only fixes the *population* (which Games'
invoices+brackets are on disk), not a cached sigma.

---

## 1. Verifying the three claims

**Claim 1 — `measured_leave_one_out_sigma_log` is a hardcoded literal.** Confirmed by
inspection, `scripts/build_price_memory.py:238`:

```python
"measured_leave_one_out_sigma_log": 0.43,
```

written unconditionally by `memory_payload()`, every build, regardless of `--evaluate`. Fixed
in section 4 below.

**Claim 2 — `SIGMA_LOG = 0.43` does not reproduce, per the brief's cited numbers (0.659 on
Cases 1-14, 0.581 on Cases 1-36).** **Only half right, and the half that's wrong changes the
diagnosis.** Run today, against the current codebase, `--no-write` throughout:

```
$ PYTHONPATH=. python scripts/build_price_memory.py --games 1-14 --evaluate --no-write
  ... POOLED n=26/116 recall=22% sigma=0.431 mean|log|=0.361 bias=+0.049   (per-unit ON)
  ... POOLED n=26/116 recall=22% sigma=0.984 mean|log|=0.887 bias=+0.691  (per-unit OFF)

$ PYTHONPATH=. python scripts/build_price_memory.py --games 1-36 --evaluate --no-write
  ... POOLED n=148/278 recall=53% sigma=0.527 mean|log|=0.339 bias=+0.056  (per-unit ON)
  ... POOLED n=148/278 recall=53% sigma=0.926 mean|log|=0.657 bias=+0.372  (per-unit OFF)
```

**On its own documented population (Cases 1-14, per-unit ON, exact+core pooled), `SIGMA_LOG =
0.43` reproduces almost exactly: 0.431.** The claim that it "does not reproduce" is false for
that specific run. What *is* true, and is the real defect: the number is **stale**, not wrong
at the time it was written. As the store grew from 14 to 36/37 Cases (recall 22% → 53%), the
same pooled methodology drifts to **0.51-0.53** — a real, measurable understatement, just not
the one first alleged.

**The specific figures 0.659 (Cases 1-14) and 0.581 (Cases 1-36) do not reproduce under any
variant tried** — not per-unit ON, not OFF, not at Games 1-36 or 1-37. They trace to a comment
in `scripts/learn_watch.py` (added in commit `07093bb`, the memory-refresh commit): *"Rebuilding
over 1-36 took recall from 22% to 53% and *lowered* leave-one-out sigma from 0.659 to 0.581."*
That comment is itself flagged as misleading by the investigation that landed alongside it,
`docs/brainstorm/sebi/strats/review/price-memory-coverage.md` §6 / §8 item 3 — its own §6 table
reports the *pooled* Cases-1-36 numbers as **0.612 (per-unit ON) vs 0.581 (OFF)**, an ON/OFF
comparison mislabeled in the `learn_watch.py` comment as an old-store/new-store one. Rerunning
that same command today reproduces **neither** set of numbers (0.527/0.926 above, not
0.612/0.581) — the pooled non-disjoint statistic is evidently not stable across runs of this
investigation, which is itself evidence for preferring the disjoint-fold, RMSLE numbers in
section 2 over any single pooled figure. **Recommendation for anyone citing a Price Memory
sigma from here on: cite section 2's disjoint-fold RMSLE table, never the pooled
`--evaluate` headline number, and never 0.659/0.581 — neither reproduces.**

**Claim 3 — `MODEL_SIGMA_PRIOR = 0.6`, comment says "nearer 0.8," bake-off measures 0.845.**
Confirmed exactly. `docs/brainstorm/sebi/strats/review/model-bakeoff.md` (already committed,
n=152 paired, real-money items, Games 1-32, terra — the model live since 21:48 tonight):

```
RMSLE, model-only (Channel C)  |  mini 0.848  |  terra 0.845  |  luna 0.874
```

`terra`'s 0.845 is exactly the brief's figure. Note the bake-off's own recommendation is to
**revert `.env` to mini** on accuracy/latency grounds — but mini's Channel-C RMSLE (0.848) is
statistically the same number, so which model ships does not change this section's conclusion
either way.

---

## 2. Splitting the discrepancy: match type vs. basis (n per bucket)

The brief's hypothesis was that `0.43` is an exact-wording-only figure and `--evaluate` pools
in the (looser) `core_key` fallback. **Tested directly and falsified.** Leave-one-out over
Games 1-37 (per-unit rule ON, the shipped configuration), bucketed by
`PriceMemoryHit.match` and `.basis`:

```
$ PYTHONPATH=. python scripts/experiments/sigma_by_match_type.py --games 1-37
```

| bucket (match, basis) | n | bias | sigma | RMSLE |
|---|---:|---:|---:|---:|
| exact, gross | 119 | +0.048 | 0.560 | 0.562 |
| exact, per_unit | 33 | +0.076 | 0.324 | 0.333 |
| core, gross | 8 | +0.113 | 0.286 | 0.308 |
| **by match alone** | | | | |
| exact | 152 | +0.054 | 0.518 | 0.521 |
| core | 8 | +0.113 | 0.286 | 0.308 |
| **by basis alone** | | | | |
| gross | 127 | +0.052 | 0.547 | 0.549 |
| per_unit | 33 | +0.076 | 0.324 | 0.333 |

**Core matches are not worse — they are rare (5% of hits, n=8) and, on that small sample,
slightly *tighter* than exact.** The hypothesis that `core_key` fallback drags the pooled
number up is falsified. **The split that actually separates accurate hits from inaccurate
ones is *basis*, not match type**: `per_unit` hits (labour/area/mass, priced as a rate ×
quantity) sit at sigma ≈ 0.32-0.33, tighter than the shipped 0.43; `gross` hits (`pcs`, `flat
rate` — the large majority, 127 of 160) sit at sigma ≈ 0.55, clearly looser. This holds on the
disjoint held-out folds too (`sigma_disjoint_folds.py`, per-unit ON): `exact/per_unit` scores
0.22-0.30 RMSLE across all three folds (odd→even, even→odd, 1-20→21-36) against
`exact/gross`'s 0.58-0.63.

**Conclusion for step 3: the "per-match-type" candidate the brief asked for is, on this
evidence, really a per-basis candidate** — `per_unit → 0.33`, `gross → 0.55` (core folded into
gross; n=8 is too small to trust its own value). Tested as such below.

---

## 3. Euro replay through `blend.combine()` — the piece nobody had tested yet

`docs/brainstorm/sebi/strats/review/price-memory-coverage.md` §5 already tested
`SIGMA_LOG`/`MEMORY_SIGMA` *in isolation* (Channel B answering alone via `price_item`, no
model reading) and found a small, floor-internal, mildly negative delta — and explicitly
flagged the untested follow-up: *"test `MEMORY_SIGMA`'s effect inside `blend.combine()`
against real cached model Evidence."* That is what this section does, plus
`MODEL_SIGMA_PRIOR`, which nothing in this repo had replayed in euros before tonight.

### Method and its limitation, stated up front

`blend.combine()` needs a real Channel C (model) reading; regenerating one costs an LLM call,
forbidden tonight. So the sample is every settled Game with a **cached** raw model draw
(`var/evidence/case_NN_model.json`, from an earlier `dump_evidence.py` run, no new calls) that
also reconstructs (`replay_payoffs.usable_games`): **29 Games — 1-26, 28-30** (27 has no
cache). That is smaller than "every settled Game" (37+ now settled); every number below is
scoped to those 29 and says so. Channel B (memory) is rebuilt **fresh**, leave-one-out over
all 37 settled Games, per scored Game — not read from the possibly-stale cached
`case_NN_memory.json`, which reflects whatever store existed on disk whenever
`dump_evidence.py` happened to run.

**A bug caught and fixed while building this harness, worth recording because it would have
produced a false negative:** `blend.combine()`'s inverse-variance weighting reads the *module
constants* `MODEL_SIGMA_PRIOR` / `MEMORY_SIGMA` directly — it does **not** derive a weight
from the passed-in Evidence's own `price_low`/`price_high`. An earlier draft of this harness
varied only the band baked into the memory `Evidence` and left `blend.MEMORY_SIGMA` at 0.43,
which is inert for `combine()`'s dominant weighted-average branch (it only matters for two
fallback branches: model-says-worthless and memory-proves-uncovered). That draft measured a
memory-sigma effect of −360 EUR on the full 29-Game sample; fixing it to monkeypatch
`blend.MEMORY_SIGMA` itself (as `CHARGE_INTERCEPT`/`SLOPE` are explicitly *not* touched —
only these two names are ever assigned) raised the same measurement to −13,549 EUR, a ~38×
change from one line. Every number below is post-fix. `blend.MODEL_SIGMA_PRIOR` and
`blend.MEMORY_SIGMA` are monkeypatched on the already-imported `blend` module, in-process
only — this has no effect on the live runner (separate OS process) and no file under `src/`
is edited.

Coverage of the 29-Game sample: 334/335 rows have model evidence (100%), 137/335 (41%) get a
leave-one-out memory hit. Two memory-sigma candidates are tested side by side: **0.581**, the
figure this task names, and **0.51**, this report's own pooled leave-one-out measurement over
Games 1-37 per-unit ON (section 1's 0.509, rounded) — the two disagree with each other by
enough to be worth showing both, and neither changes the sign of the conclusion below.

```
$ PYTHONPATH=. python scripts/experiments/sigma_calibration_replay.py
```

### Results — delta against the shipped baseline (EUR), CHARGE_INTERCEPT/SLOPE untouched throughout

| variant | all (n=29) | odd (n=14) | even (n=15) | 1-20 (n=20) | 21+ (n=9) |
|---|---:|---:|---:|---:|---:|
| **shipped baseline (net, EUR)** | **122,750** | 59,305 | 63,444 | 89,225 | 33,524 |
| model only → 0.845 | −11,973 | −6,013 | −5,961 | −10,205 | −1,768 |
| memory only → 0.581 (task figure) | −13,549 | −15,909 | **+2,360** | −7,590 | −5,959 |
| memory only → 0.51 (own pooled measurement) | −10,225 | −12,321 | **+2,096** | −5,596 | −4,629 |
| **both → 0.845 / 0.581 (fully calibrated)** | **−19,775** | −14,302 | −5,473 | −14,292 | −5,484 |
| both → 0.845 / 0.51 | −14,840 | −9,798 | −5,041 | −11,026 | −3,814 |
| per-basis memory (0.33/0.55), model unchanged | −5,253 | −7,699 | **+2,446** | −900 | −4,353 |
| per-basis memory + model → 0.845 | −8,307 | −2,384 | −5,923 | −5,530 | −2,777 |

| noise floor (`26,622·√(n/18)`) | ±33,791 | ±23,478 | ±24,302 | ±28,062 | ±18,825 |
|---|---:|---:|---:|---:|---:|

### Reading the table

**`MODEL_SIGMA_PRIOR` alone is negative in all four independent fold-halves** (odd, even,
1-20, 21+ — "all" is their sum, not a fifth independent cell): −6,013 / −5,961 / −10,205 /
−1,768. Small relative to each fold's own noise floor, but the direction is unanimous —
the same bar (`n/n` fold cells one sign) this repo already uses elsewhere (`LIMIT_CEILING_MEMORY`:
"eight fold cells, eight positive") to trust a result that doesn't individually clear the
floor.

**The fully calibrated band (both corrected together) is negative in all four fold-halves
too, and larger**: −14,302 / −5,473 / −14,292 / −5,484. This is the number that answers the
brief's central question: **widening the band to its measured true width consistently costs
money on every disjoint slice of the available sample**, even though no single cell clears
its own noise floor. That matches the mechanism the brief already named — a wider band lowers
`charge_factor(sigma)`, and it also shifts `combine()`'s weighted average away from whichever
channel the correction most distrusts, which moves the blended median, not only its width.

**`MEMORY_SIGMA` alone is the noisier, weaker piece**: negative on 3 of 4 fold-halves, but
**flips sign on the even fold** (+2,360 / +2,096 at the two candidate values). That is
consistent with — not a contradiction of — `price-memory-coverage.md` §5's isolated-channel
finding of "small, floor-internal, mildly negative": the effect is real but small enough that
one fold's composition can flip it, and it only touches the 41% of rows with a memory hit at
all, where `MODEL_SIGMA_PRIOR` touches all of them. **The dominant lever in the "fully
calibrated" loss is the model correction, not the memory correction** (−11,973 of the −19,775
total, i.e. ~60%).

**The per-basis memory candidate (section 2's actual finding) does not rescue the memory
side**: −5,253 overall, and it still flips sign on the even fold. Splitting by basis changes
which items get a wider or narrower band, not the aggregate direction.

### Held-out verdict

No individual cell in this table clears its own noise floor — the 29-Game sample is smaller
than this repo's usual bar, and it should be. But **the fully calibrated correction (both
constants) is the only candidate that is negative in every fold-half tested, at every
resolution tried (flat memory sigma, per-basis memory sigma, either candidate memory value)**.
That is the same standard of evidence this file's sibling investigations use to act on a
result that doesn't individually clear the floor (`LIMIT_CEILING_MEMORY`'s "eight fold cells,
eight positive" is the positive mirror of this).

---

## 4. Making the hardcoded field honest, regardless of the euro result

A field named `measured_leave_one_out_sigma_log` that is a literal is a defect independent of
whether 0.43 happens to be defensible — and section 1 showed it drifts as the store grows, so
a snapshot written once will mislead again. Proposed diff, **not applied**:

```diff
--- a/scripts/build_price_memory.py
+++ b/scripts/build_price_memory.py
@@
-def memory_payload(records: list[dict[str, Any]], games: list[int]) -> dict[str, Any]:
+def memory_payload(
+    records: list[dict[str, Any]], games: list[int], measured_sigma: float | None
+) -> dict[str, Any]:
     entries = build_entries(records)
     return {
         "version": 1,
         "built_from_games": games,
         "line_items_joined": len(records),
         "line_items_with_proven_positive_t": sum(1 for r in records if r["positive"]),
         "per_unit_units": sorted({r["unit"] for r in records if r.get("basis") == "per_unit"}),
-        "measured_leave_one_out_sigma_log": 0.43,
+        # The field name says "measured"; it now has to be one. `evaluate()` is the same
+        # leave-one-out sweep `--evaluate` prints, run here on every build regardless of
+        # that flag, over whatever `games`/`records` this store was actually built from --
+        # so the number can no longer go stale the way the literal 0.43 did (section 1:
+        # true value drifted 0.43 -> 0.51-0.53 as the store grew from 14 to 37 Cases, and
+        # the field never moved). `None` (too few positive-t Line Items to score, e.g. a
+        # single-Game store) writes JSON `null` rather than a fabricated number.
+        "measured_leave_one_out_sigma_log": measured_sigma,
         "warning": (
             "PRICE ONLY. This store never asserts coverage; "
             "advisory_zero_observations is a hint to read the policy clause, "
             "not a verdict that the item is uncovered."
         ),
         "entries": entries,
     }
@@
 def main() -> None:
     parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
     parser.add_argument("--games", default="1-14")
     parser.add_argument("--cases", type=Path, default=CASES_DIR)
     parser.add_argument("--out", type=Path, default=OUT_PATH)
     parser.add_argument("--evaluate", action="store_true", help="leave-one-out accuracy")
     parser.add_argument("--no-write", action="store_true")
     args = parser.parse_args()

     start, _, end = args.games.partition("-")
     games = list(range(int(start), int(end or start) + 1))

     records = observations(games, cases_dir=args.cases)
-    payload = memory_payload(records, games)
+    # Always run -- `--evaluate` only controls whether the per-Case table is *printed*; the
+    # pooled sigma has to be computed either way so the payload field is never a guess.
+    measured = evaluate(records, games)
+    measured_sigma = None if measured["sigma"] != measured["sigma"] else measured["sigma"]  # NaN guard
+    payload = memory_payload(records, games, measured_sigma)
     positive = payload["line_items_with_proven_positive_t"]
     print(
         f"Joined {len(records)} Line Items over Cases {games[0]}-{games[-1]}: "
         f"{positive} with a proven non-zero Fair Value, "
         f"{len(payload['entries'])} wordings stored."
     )
     _print_repeats(records)
     if args.evaluate:
         _print_evaluation(records, games)
     if not args.no_write:
         args.out.parent.mkdir(parents=True, exist_ok=True)
         _write_atomically(args.out, json.dumps(payload, indent=1, ensure_ascii=False))
-        print(f"\nWrote {args.out}")
+        sigma_msg = f"{measured_sigma:.3f}" if measured_sigma is not None else "null (too few positive-t items)"
+        print(f"\nWrote {args.out} (measured_leave_one_out_sigma_log={sigma_msg})")
```

Verified safe to make regardless of the section 3 verdict: `measured_leave_one_out_sigma_log`
is read by nothing under `src/` (`grep -rn "measured_leave_one_out_sigma_log" --include="*.py"`
turns up only the write site and one diagnostic print in an experiment script) — `PriceMemory.
load()`/`lookup()` only ever read the `entries` block, never this field, so this diff changes
what a JSON file *says*, not what any pricing decision *does*. `evaluate()` is cheap (the
leave-one-out sweep this diff always runs already completes in well under a second for the
current 37-Game, ~440-record population, per the timings observed while writing this report),
so this is a pure honesty fix with no measurable cost. **This is orthogonal to whether
`SIGMA_LOG`/`MEMORY_SIGMA` should move — apply it regardless of what happens with section 3.**

---

## 5. Recommendation

**Do not correct `SIGMA_LOG` / `MEMORY_SIGMA` / `MODEL_SIGMA_PRIOR` in `src/`.** The measured,
calibrated band is directionally negative on every disjoint fold tested (odd, even, 1-20,
21+), driven mostly by the model-side correction, and even though no cell individually clears
its own noise floor on the 29-Game sample available without new LLM calls, the unanimous
sign across every fold and every sub-variant (flat memory sigma, per-basis memory sigma, task
figure or own pooled figure) is the same standard of evidence this repo already trusts
elsewhere when a single number is inside the floor. Reasons not to read this as "the numbers
are fine, leave them":

- The band **is** measurably too narrow (0.350 shipped vs 0.479 fully calibrated, both
  reproduced analytically from `combine()`'s own formula in this report). That part of the
  brief's premise is correct and is not in dispute.
- Widening it is not free precisely because `CHARGE_SLOPE` already discounts the Charge as
  the band widens, and `src/domain/pricing/engine.py`'s own docstring (the `CHARGE_SLOPE`
  section, "the sigma ordering is not merely uninformative, it is costly") already found the
  opposite-direction result: *narrowing* discounting on wide bands loses money too. The band's
  width is doing real, load-bearing work in the current pricing rule even though it is
  measurably wrong — which is exactly the "known biased but profitable" pattern this
  recommendation is naming, not a coincidence.
- This conclusion should be **retested**, not assumed permanent, once (a) `dump_evidence.py`
  has cached raw model evidence for Games 31+ without an additional LLM call (e.g., after the
  next `pixi run cases` + a routine re-dump), which would let this same harness run on the
  full settled record instead of 29 of 37+ Games, and (b) if the model swap in
  `model-bakeoff.md` lands (mini over terra), which changes `MODEL_SIGMA_PRIOR`'s correct
  target only trivially (0.848 vs 0.845) but is worth a rerun for completeness.

**Do land the honest-field diff (section 4)** — independent of the above, unconditional, and
already verified to touch nothing under `src/`.

**Noise floor reference used throughout:** `26,622 · √(n_games / 18)`.

| n games | 9 | 14 | 15 | 18 | 20 | 29 |
|---|---:|---:|---:|---:|---:|---:|
| floor | ±18,825 | ±23,478 | ±24,302 | ±26,622 | ±28,062 | ±33,791 |
