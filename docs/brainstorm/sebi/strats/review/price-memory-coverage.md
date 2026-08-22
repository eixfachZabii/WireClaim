# Price Memory coverage — how far it reaches, and what reaching further is worth

Scope: Games 1–36 (425 invoice Line Items joined to recovered Fair Values via
`scripts/invert_fair_values.py`, all 36 reconstructing to the cent per `replay_payoffs.py`
`--self-check`; `pixi run test` green at 329 tests throughout). New code: one read-only
measurement script, `scripts/pm_measure.py`-equivalent logic reproduced below (kept in the
scratchpad, not committed — nothing under `src/` touched, no network, no LLM calls).

**Bottom line, up front:** Price Memory is correctly seeded from recovered Fair Values, not
our own guesses (item 3, below). The store *was* stale — frozen at Games 1–14 while 22 more
settled Games sat on disk unread — but that fix landed **during this investigation**, from a
concurrent session, not from this report; §1 credits it precisely and validates it
independently. What this report adds on top: the refreshed memory is a robust, held-out-
validated win (clears the noise floor on every fold tested); the per-unit rule is
re-confirmed on the larger dataset after a naive metric made it look shaky; the memory's
reported error (`SIGMA_LOG = 0.43`) is now measurably understated but *correcting it alone
doesn't clearly help*, so it should be left alone for now; and a real, traced, ~14×-magnitude
parsing bug affects exactly the class of item the brief flagged ("Skilled worker hours") —
fixed with a four-line, name-based fallback, diff below, not applied.

---

## 1. Item 3 — recovered truth, or our own guesses? (sent within 20 minutes, reproduced here)

**Not our own guesses.** `scripts/build_price_memory.py` joins invoice wording (POS. number)
directly to `invert_fair_values.brackets(game_id, teams)` — the same ground-truth inversion
`--verify` checks to the cent against the published leaderboard. `src/domain/pricing/memory.py`
never reads a Strategy 2 proposal, a decision log, or anything Strategy 2 itself produced.
The specific failure mode the brief was worried about does not exist in this codebase.

What *was* true when this investigation started (checked at 22:26 CEST): the **committed**
store, `data/price_memory.json` (mirrored into `var/price_memory.json`), carried
`built_from_games: [1..14]` — 192 Line Items joined, 116 proven positive, 98 wordings
stored — and had never been rebuilt. `build_price_memory.py --games` defaults to `"1-14"`;
nothing in `pixi.toml` or `scripts/learn_watch.py` invoked it. By Game 36, Channel B was
answering from roughly 40% of the ground truth already sitting on disk (14 of the ~35
settled Games with recoverable Fair Values). That was reported immediately via SendMessage,
flagged as the most valuable single lever available.

**Between that message and this report, the fix landed** — not written by this investigation,
but by a concurrent session working the same file. As of this writing:

- `scripts/learn_watch.py` now runs `build_price_memory.py --games 1-{latest}` immediately
  after extracting each newly-settled Game, before the learning-loop review step.
- `scripts/build_price_memory.py` gained an atomic write (`os.replace` via a `.tmp` file) so
  a reader mid-rebuild never sees a truncated store — `PriceMemory.load` turns an unreadable
  file into a silently *empty* memory rather than raising, which is exactly the failure mode
  an in-place `write_text` during a live Game would have caused.
- `data/price_memory.json` is now built from Games 1–36: 425 Line Items joined, 278 proven
  positive, 175 wordings stored (up from 98). Not yet committed (`git status` still shows it
  modified) — this report's §2–§5 is the held-out validation that fix deserves before it
  lands for good.

So the correct summary for the record: **the store was seeded correctly from day one; it was
stale, not wrong; and the staleness is now fixed and wired to stay fixed.** Everything below
measures whether that fix is actually worth what it claims, and what is still worth doing
on top of it.

---

## 2. The matching rule, precisely

Two tiers, in `src/domain/pricing/memory.py::PriceMemory.lookup()`:

1. **Exact.** `normalise(name)` — lowercase, unify dash variants, `m²`/`m³` → `m2`/`m3`,
   `°` → `" degree "`, collapse everything non-alphanumeric to single spaces — looked up
   directly against the stored key.
2. **Core** (fallback, only on an exact miss). `core_key(name)` drops the trailing
   parenthetical (`"... (8 hrs)"`) and then everything after the first qualifier separator
   (`,` `;` `:` ` - ` ` – `), then normalises what's left. All wordings sharing a core key are
   merged (pooled) at lookup time.

Nothing looser is implemented **on purpose**: the `core_key` docstring records that token-
overlap / nearest-neighbour matching was already measured and made things worse — sigma 0.43
→ 0.72 at a Jaccard threshold of 0.7, → 1.19 at 0.25. That is the brief's candidate "matching
on trade/unit rather than the full description" — already tried, already rejected, with
numbers, before this investigation started. Not re-run here (CLAUDE.md: don't re-open a
lever already measured shut) beyond confirming the code path is unchanged.

**Quantity handling** (also already implemented, not a candidate): `is_per_unit(unit)` checks
the invoice unit against `PER_UNIT_UNITS = {hrs, hr, h, hours, m, m2, m3, kg, l, km}`. A
per-unit hit stores/queries a *rate*, scaled by the invoice quantity; everything else (`pcs`,
`flat rate`, …) is gross. §4 re-validates this on the expanded dataset.

**German morphological variants** (brief's candidate): not applicable. Every invoice checked
across all 36 Cases is English throughout — a full-text grep for `und|für|arbeiter|std|
stunde|reinigung|entsorgung|handwerker` across all 36 `invoices.pdf` returned nothing.

---

## 3. Hit rate and error, properly held out (no look-ahead)

Method: `PriceMemory` rebuilt from a **train** set of Games via
`build_price_memory.observations()` → `build_entries()`, scored against the **score** set's
recovered Fair Values (`t_point`, from the same brackets `invert_fair_values` produces).
Error is `log(predicted_median / t_point)` on Line Items with a proven positive Fair Value
(`t_lo > 0`); reported as **RMSLE** = `sqrt(bias² + sigma²)` per CLAUDE.md's instruction to
use total log error, not stdev alone (a stdev-only view is what made the per-unit rule look
borderline in §4 below — it wasn't).

| fold | train games | score games | scorable (t>0) | hits | recall | bias | sigma | **RMSLE** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| odd → even | 18 | 18 | 113 | 34 | 30% | +0.163 | 0.533 | **0.558** |
| even → odd | 18 | 18 | 165 | 61 | 37% | −0.148 | 0.680 | **0.696** |
| 1–20 → 21–32 | 20 | 12 | 61 | 32 | 52% | −0.136 | 0.593 | **0.609** |

Against the stale baseline this replaces (Cases 1–14 only, leave-one-out, module docstring):
**recall 22%, sigma 0.43.** The refreshed, properly-disjoint folds show recall **1.4×–2.4×
higher** (30–52% vs 22%) at a real, honest cost: **RMSLE 0.56–0.70, not 0.43** — a wider net
catches worse matches, exactly as the brief warned. All three folds still clear the
system-level break-even (σ ≈ 0.85, README/CLAUDE.md) and still beat the model channel's
measured range (0.76–0.78 RMSLE) in every fold. Channel B remains the better channel; it is
no longer quite as good as the Cases-1–14 number implied, because that number was measured
on an easier, smaller, more homogeneous slice.

---

## 4. Euro impact — Channel B alone, isolated via `price_item` + `replay`

Methodology: for every Line Item in a score Game, build an `Evidence` from a memory hit
(`coverage_probability = 0.9`, the constant `channels.py` uses; band = median ×
`exp(±sigma_log)`) or, on a miss, from `Evidence(index).with_defaults()` — the same fallback
in **both** scenarios being compared, so it cancels in the delta. Run `price_item()` →
`(charge, limit)` for every Line Item, build the full submission map, replay it against the
real Field via `replay_payoffs.replay(snapshot, submission)`, sum net over the score Games.
This isolates Channel B's own contribution; it does not exercise `blend.combine()` (which
needs a real model reading — no LLM calls were made, per the hard rule). Noise floor:
`26,622·√(n_games/18)`.

**Channel B vs. no memory at all** (fallback-only baseline), at the current `SIGMA_LOG = 0.43`:

| fold | n games | net, no memory | net, with memory | **delta** | floor |
|---|---:|---:|---:|---:|---:|
| odd → even | 18 | −313,888 | −261,096 | **+52,792** | ±26,622 |
| even → odd | 18 | −302,464 | −200,588 | **+101,876** | ±26,622 |
| 1–20 → 21–32 | 12 | −134,256 | −73,783 | **+60,473** | ±21,737 |

**Clears the noise floor on every fold, by 2×–4.8×.** This is the strongest, most robust
result in this report: the just-applied refresh (§1) is a real, validated win, not an
artifact of scoring a memory on the Games it was built from. Recommend: **commit
`data/price_memory.json` and the `learn_watch.py` wiring.**

At the corrected sigma (§3's measured RMSLE per fold, instead of the constant 0.43), the same
comparison drops slightly (+49,553 / +93,829 / +56,284) but the conclusion is unchanged —
Channel B is worth tens of thousands per fold regardless of which sigma feeds the band width.

---

## 5. `SIGMA_LOG` / `MEMORY_SIGMA` — measurably wrong, but correcting it doesn't clearly help

`src/domain/pricing/memory.py:81` (`SIGMA_LOG = 0.43`) and
`src/services/strategies/strategy2/constants.py:48` (`MEMORY_SIGMA = 0.43`) are both still
**0.43** after the refresh — unchanged by the concurrent fix in §1. §3 measures the store's
true held-out RMSLE at **0.56–0.70** depending on fold, i.e. the constant now understates the
memory's real error by roughly 1.3×–1.6×. `SIGMA_LOG` sets the band width `lookup()` reports
(`low/high = median × exp(∓SIGMA_LOG)`), which `price_item()` reads via `implied_sigma()` to
set both the Charge shading (`charge_factor`) and the Limit quantile — a band that's too
narrow means both numbers sit closer to the median than the evidence justifies.

Tested directly: same isolated harness as §4, holding the memory fixed per fold and only
swapping `SIGMA_LOG` from 0.43 to that fold's measured RMSLE.

| fold | net @ 0.43 (current) | net @ measured sigma | **delta** | floor |
|---|---:|---:|---:|---:|
| odd → even | −261,096 | −264,335 | **−3,239** | ±26,622 |
| even → odd | −200,588 | −208,635 | **−8,047** | ±26,622 |
| 1–20 → 21–32 | −73,783 | −77,972 | **−4,189** | ±21,737 |

Small, consistently negative, but **inside the noise floor on every fold** — not distinguishable
from noise, and if anything mildly against widening. Mechanically this is plausible: a wider
band lowers `charge_factor` (more conservative Charge, forfeiting some correct-hit income)
*and* lowers the Limit quantile (more wrongful rejections at `1.5×` cost on the hits that were
actually right). Those two effects partly cancel the benefit of hedging against the worse
hits. **Recommendation: leave `SIGMA_LOG` and `MEMORY_SIGMA` at 0.43 for now** — this is a
tested, negative-to-neutral result, not an unmeasured guess, and CLAUDE.md's rule is to change
at most one thing per validated result; this one doesn't clear that bar.

Caveat: this test only exercises `price_item(memory_evidence)` directly, i.e. Channel B
answering alone. `MEMORY_SIGMA` also feeds `blend.combine()`'s inverse-variance weighting
against a real model reading, which this report did not test (would need cached model
`Evidence`, e.g. from `var/decisions/*.json` or `var/bakeoff/*.json` — only 13 decision logs
exist, likely too small a sample to clear its own noise floor). Flagged as follow-up, not
executed here.

---

## 6. Per-unit rule — re-confirmed, the naive metric was misleading

`build_price_memory.py --evaluate`'s own pooled leave-one-out output over 1–36 (non-disjoint,
simple stdev) made the per-unit rule look borderline-negative on the larger dataset: pooled
sigma 0.612 (per-unit ON) vs 0.581 (OFF), i.e. OFF nominally *better* by that one metric. That
number is what's currently quoted in the `learn_watch.py` comment. **It is misleading** — the
disjoint-fold, RMSLE, euro-replayed test (§3/§4's harness, same three folds) is unambiguous
in the other direction:

| fold | per-unit ON: hits/scorable, RMSLE, net | per-unit OFF: hits/scorable, RMSLE, net | **delta (ON − OFF)** | floor |
|---|---|---|---:|---:|
| odd → even | 34/113, 0.558, −264,335 | 34/113, 1.010, −295,942 | **+31,607** | ±26,622 |
| even → odd | 61/165, 0.696, −208,635 | 61/165, 1.119, −258,665 | **+50,030** | ±26,622 |
| 1–20 → 21–32 | 32/61, 0.609, −77,972 | 32/61, 0.868, −105,988 | **+28,016** | ±21,737 |

Per-unit ON clears the noise floor on every fold, by margins of 1.2×–1.9×. Hit count is
identical between ON/OFF (the rule only changes the *value* stored/queried, not whether a
wording matches), so this delta is purely accuracy, not coverage. **No code change** — the
rule is already ON in the deployed `is_per_unit`/`PER_UNIT_UNITS` path — this is a
confirmation, and a correction to the misleading pooled-stdev reading currently sitting in
the `learn_watch.py` comment.

---

## 7. The dash-unit bug — the named "worst items," traced to source

The brief named exactly these as the worst, memory-resistant items: *Skilled worker hours,
Service technician hours, Helper hours, Installation hours – tiler, Room drying 30 m²*. A
strict causal check (train on Games 1..g−1, score Game g) over the last several Games:

- **Game 33:** no line items of these kinds.
- **Game 34:** Service technician hours and Helper hours both **hit**, reasonably
  (log-error −0.20, −0.29). Installation hours – tiler **missed** — genuinely cold-start
  (its only occurrence anywhere in Games 1–36 *is* Game 34; nothing to fix).
- **Game 35:** Skilled worker hours, Room drying 30 m², Room drying 50 m² all **hit**
  reasonably (log-error −0.11 to −0.29) — except **item #18, Skilled worker hours, log-error
  −2.64** (predicted 78.60 against a true ≈1,099.50 — **14× under**).
- **Game 36:** Skilled worker hours **hit** but the item is `positive=False` (plausibly
  uncovered in this Case's policy) — the known, by-design "6 of 15 repeated wordings flip"
  limitation, not a new bug; Channel B never asserts coverage and isn't expected to catch this.

**Root cause of the 14× miss, traced exactly.** `invoices.pdf` for Case 35, row 18:

```
 18      Skilled worker hours                              14   –
```

The unit column is a literal dash, not `hrs`. `normalise_unit("–")` → `""`; `is_per_unit("")`
is `False`; the item is priced as a **gross total** instead of an hourly rate — both when this
row is *stored* (it enters training as a raw value ≈1,099, contaminating the "skilled worker
hours" per-hour bucket with one 14×-too-large entry) and when it is later *queried* (a query
with the same dash-unit artifact gets `scale = 1` instead of `scale = 14`).

This is not a one-off: the identical pattern (`qty  –` where a real unit belongs) occurs
**4 times in 36 Games** — Game 25 #13 (`Skilled worker hours`, qty 14, same 14× failure mode)
and Game 35 #18 above; the other two (`Dispose of the old boiler system`, qty 1, Games 28/29)
are gross-priced items where the miscategorisation happens to be a no-op. Expect roughly one
more genuine occurrence per ~18 further Games at the observed rate.

**Fix — name-based fallback when the parsed unit is blank**, in
`src/domain/pricing/memory.py` (shared by both the training path and the live query path,
so `scripts/build_price_memory.py` needs one matching one-line change and `channels.py`
needs none):

```diff
--- a/src/domain/pricing/memory.py
+++ b/src/domain/pricing/memory.py
@@
 _DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212\u2043"), "-")
 _ALNUM = re.compile(r"[^a-z0-9]+")
 _QUALIFIER_SPLIT = re.compile(r"[,;:]\s|\s-\s|\s\u2013\s")
+#: A quantity with no readable unit -- the invoice prints a dash where "hrs" belongs, at
+#: least twice in Games 1-36 ("Skilled worker hours   14   –"). Falls back to the
+#: wording itself only when the parsed unit is genuinely blank; never overrides a real one.
+_HOUR_WORDING = re.compile(r"\bhours?\b", re.IGNORECASE)
@@
 def normalise_unit(unit: str | None) -> str:
     folded = normalise(unit or "")
     return {"hour": "hrs", "hours": "hrs", "hr": "hrs", "h": "hrs", "sqm": "m2"}.get(
         folded, folded
     )
 
 
 def is_per_unit(unit: str | None) -> bool:
     """True when the price scales with quantity (labour, area, length, mass)."""
     return normalise_unit(unit) in PER_UNIT_UNITS
+
+
+def infer_unit(name: str, unit: str | None) -> str:
+    """Fall back to a wording-based guess when the invoice's unit column is blank.
+
+    Two Line Items across Games 1-36 print a quantity with no readable unit -- the invoice
+    literally has a dash where "hrs" belongs ("Skilled worker hours   14   –", Games 25
+    and 35). ``normalise_unit`` turns that into ``""``, ``is_per_unit("")`` is False, and the
+    item is priced as a *gross* total instead of an hourly rate -- both when it is stored
+    (contaminating the wording's per-hour bucket with one value ~14x too large) and when it
+    is queried (scaling by 1 instead of the real quantity). Measured log-error on both known
+    occurrences: -2.61 and -2.64 before this fallback, +0.03 and -0.00 after.
+
+    Only fires when the parsed unit is already blank, and only for wordings that name their
+    own unit -- it cannot relabel a real, different unit, and it does not fire on the other
+    two dash-unit rows in the data ("Dispose of the old boiler system"), which are correctly
+    gross-priced items where a unit guess would be groundless.
+    """
+    folded = normalise_unit(unit)
+    if folded:
+        return folded
+    if _HOUR_WORDING.search(name or ""):
+        return "hrs"
+    return folded
@@
     def lookup(
         self,
         name: str,
         unit: str | None = None,
         quantity: float = 1.0,
     ) -> PriceMemoryHit | None:
         """Price band for this wording, or ``None`` on a miss.
 
         A miss means "no settled Line Item used these words" -- it does **not** mean the
         item is worthless, uncovered, or cheap. Recall is 22 %; four items in five are
         misses and must be priced by the estimator as if the memory did not exist.
         """
         key = normalise(name)
         entry, match = self._entries.get(key), "exact"
         if entry is None:
             candidates = self._core.get(core_key(name), [])
             if candidates:
                 entry, match = self._merge(candidates), "core"
         if entry is None or not entry.values:
             return None
 
-        per_unit = is_per_unit(unit)
+        unit = infer_unit(name, unit)
+        per_unit = is_per_unit(unit)
         scale = quantity if per_unit and quantity and quantity > 0 else 1.0
         values = sorted(v * scale for v in entry.values)
         median = statistics.median(values)
         return PriceMemoryHit(
             name=entry.display_name,
             key=entry.key,
             match=match,
             low=min(values[0], median * math.exp(-SIGMA_LOG)),
             median=median,
             high=max(values[-1], median * math.exp(SIGMA_LOG)),
             observed_low=values[0],
             observed_high=values[-1],
             observations=len(values),
             games=entry.games,
             basis="per_unit" if per_unit else "gross",
             quantity=float(quantity),
-            unit=normalise_unit(unit),
+            unit=unit,
             advisory_zero_observations=entry.advisory_zero_observations,
             advisory_zero_games=entry.advisory_zero_games,
             samples=entry.samples,
         )
```

```diff
--- a/scripts/build_price_memory.py
+++ b/scripts/build_price_memory.py
@@
 from src.domain.pricing.memory import (  # noqa: E402
     PriceMemory,
     build_entries,
     core_key,
+    infer_unit,
     is_per_unit,
     normalise,
     normalise_unit,
 )
@@
 def _record(game_id: int, item: Mapping[str, Any], t_low: float, t_high: float) -> dict[str, Any]:
-    unit = normalise_unit(item["unit"])
+    unit = infer_unit(item["name"], item["unit"])
     quantity = float(item["quantity"]) or 1.0
```

**Also add `"infer_unit"` to `memory.py`'s `__all__`.**

**Item-level effect** (train on 1..g−1, the realistic causal case):

| item | true t | before | after |
|---|---:|---:|---:|
| Game 25 #13, Skilled worker hours | 1,097.15 | median 80.93 (log-err −2.61) | median 1,133.01 (log-err **+0.03**) |
| Game 35 #18, Skilled worker hours | 1,099.50 | median 78.60 (log-err −2.64) | median 1,097.15 (log-err **−0.00**) |

**Euro impact**, same isolated `price_item` + `replay` harness as §4/§5, before vs after this
one fix (`SIGMA_LOG` held at 0.43 in both):

| fold | n games | net before | net after | **delta** | floor |
|---|---:|---:|---:|---:|---:|
| even → odd (has both #25, #35 in score) | 18 | −200,588 | −179,174 | **+21,414** | ±26,622 |
| 1–20 → 21–32 (has #25 in score) | 12 | −73,783 | −60,890 | **+12,893** | ±21,737 |
| 1–24 → 25–36 (has both, cleanest causal fold) | 12 | −84,264 | −59,042 | **+25,221** | ±21,737 |

Clears the floor on the cleanest fold (1–24 → 25–36, the one that mirrors what actually
happens live: train on everything settled so far, score on what comes next); close under it
on the other two. **Recommend applying regardless of whether every individual fold clears
the statistical floor** — unlike §5's sigma question, this is not a noisy multiple-comparisons
result fished out of many candidates. It is one fully-traced, deterministic parsing bug with
a known, narrow, four-line fix and a measured near-total error correction (−2.6 → ~0.0 log-
error) on both known occurrences, at zero risk to any other wording (the fallback only fires
when the parsed unit is already blank and the item names its own unit).

---

## 8. Ranked recommendations

1. **Commit the already-applied memory refresh** (`data/price_memory.json`,
   `scripts/learn_watch.py` wiring, `build_price_memory.py`'s atomic write). Independently
   validated here on genuinely held-out folds (§4): clears the noise floor by 2×–4.8× on
   every fold tested. This is not this report's work, but it is now this report's evidence
   that it should land.
2. **Apply the dash-unit fallback** (§7 diff, `infer_unit` in `memory.py` +
   one-line call-site change in `build_price_memory.py`). Fully traced root cause, near-total
   error correction on both known occurrences, positive on all three folds tested (clears the
   floor on the cleanest one), essentially zero blast radius.
3. **Correct the misleading `learn_watch.py` comment** citing pooled sigma 0.581 as the
   per-unit justification — the disjoint-fold euro test (§6) shows per-unit ON beating OFF by
   28k–50k per fold, the opposite conclusion from what the pooled-stdev number suggests in
   isolation. No code change, just don't let a misleading number sit next to the correct
   decision.
4. **Do not touch `SIGMA_LOG` / `MEMORY_SIGMA`** (§5). Measurably stale (0.43 vs a true
   0.56–0.70) but correcting it in isolation shows a small, consistent, floor-internal
   *negative* delta — a tested, documented non-lever, not an oversight to "obviously" fix.
   Worth one follow-up: test `MEMORY_SIGMA`'s effect inside `blend.combine()` against real
   cached model `Evidence` (`var/decisions/*.json`, `var/bakeoff/*.json` — no new LLM calls
   needed), which this report did not do (only 13 decision logs exist; likely too small a
   sample on its own, would need combining with earlier bakeoff logs to clear its own floor).

Noise floor reference used throughout: `26,622 · √(n_games / 18)`.

| n games | 12 | 13 | 16 | 18 | 20 | 32 | 36 |
|---|---:|---:|---:|---:|---:|---:|---:|
| floor | ±21,737 | ±22,624 | ±25,099 | ±26,622 | ±28,062 | ±35,496 | ±37,649 |
