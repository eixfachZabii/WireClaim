# Upward Charge: the finding reproduces, no live signal converts it into euros — do not ship

Written 2026-08-22, ~23:00 CEST. All numbers below are reproducible from
`scripts/experiments/upward_charge_*.py` against 38 completed Games (1–38, confirmed live
via `pull_transactions.completed_games()` at the start of this measurement). `main.py`,
`pixi.toml`, `.env` and every running process were left untouched; no LLM call was made —
everything here replays already-settled Transactions and already-cached model/memory
evidence (`var/evidence/`, `var/decisions/`).

**Vintage, pinned.** `var/price_memory.json` rebuilds after every settled Game and had
already moved past the brief's own reference point (Games 1–37, 178 wordings, σ 0.509) by
the time this started: at measurement time it read `built_from_games=[1..38]`, **181
entries, leave-one-out σ 0.43**. A copy is pinned at
`scripts/experiments/pinned/price_memory_vintage_g38.json` and every number below either
reads cached `var/evidence/*.json` (frozen whenever `dump_evidence.py` last ran for that
Game — a real staleness caveat, see §1 note) or the Games 26–38 decision logs, never the
live file.

## Headline

1. **The finding reproduces, directionally and at comparable magnitude, on independent
   code.** Bounded (fully-known) Fair Values run Charged *above* `t`; unbounded (censored)
   ones run Charged *below* it — the same dispersion error, not a level error. See §1.
2. **The continuous decision-time signals separate nothing.** `t_hat`, `sigma`,
   `coverage_probability` and `quantity` each score AUC 0.44–0.56 against "is this item
   provably underpriced" — inside the noise of a 216-item sample, indistinguishable from a
   coin flip. Only two **categorical** splits show a real gap: channel (memory-backed 72%
   underpriced vs model-only 57%) and metered wording (84% vs 64%, n=31). See §2.
3. **Neither gap converts into a shippable multiplier.** The memory-channel family repeats
   the exact failure mode already documented in `src/domain/pricing/engine.py` — a real,
   large in-sample peak (+43,439 over 38 Games at ×1.15) that is **not monotone in its own
   parameter** and whose only forward-looking held-out fold (train on Games 1–20, score on
   21–38) lands at +9,632 against a ±26,622 noise floor — inside it. The metered family
   (new, never swept before) is worse: its only survivable point (×1.1) is noise-floor-flat
   in every window and every fold, and one step further (×1.2) is catastrophic
   (−16,398 / −60,061). See §3–4.
4. **The regime caveat does not change the call, because there is nothing to change it
   from.** Under a simulated fully-dark Field the memory-×1.15 candidate's gain shrinks from
   +43,439 to +25,284 (58% retained), exactly as the payoff table predicts — but since the
   candidate already fails the held-out bar in the awake regime, this is confirmatory, not
   decisive. See §5.
5. **Recommendation: ship nothing.** The honest reading is the one CLAUDE.md's evidence
   rules ask for directly: underpricing is real, provable after the fact, and *not
   observable from anything in the decision log at submission time* strongly enough to act
   on. The gap belongs to the evidence layer (a better `t_hat`), not to a conditional
   multiplier — the same conclusion `engine.py`'s docstring already reached for the
   downward direction, now confirmed for the upward one too.

---

## 1. Verifying the table

`scripts/experiments/upward_charge_verify.py` does **not** reuse `charge_buckets.py`'s
counterfactual `Rule` — that recomputes what *today's* shipped constants would have charged
on cached evidence, the right tool for tuning but the wrong one for "what did we actually
charge". Games 1–20ish ran earlier pricing code and Games 21–24 are documented (CLAUDE.md
rule 1b) to have submitted `STANDARD_LIMIT = 35` when Strategy 2 did not land. So this reads
the **actual submitted Charge** straight from the reconstructed Transactions
(`replay_payoffs.snapshot(g).charges[index][US]`), which is authoritative regardless of
which pipeline produced it, and joins it to `t_hat` via `charge_buckets.dataset()`.

```
PYTHONPATH=. python scripts/experiments/upward_charge_verify.py
```

Over Games 1–38 (446 recoverable Charges, 123 unrecoverable, 216 on items with `t_lo > 0`):

| population | n | Charge ÷ `t_lo` (median, p75) | `t̂` ÷ `t_lo` (median, p75) |
| --- | ---: | ---: | ---: |
| all items worth something | 216 | 0.70, 1.15 | **1.03**, 1.43 |
| bracket bounded (`t` known) | 131 | **1.00**, 1.96 | 1.26, 1.73 |
| bracket unbounded (`t ≥ t_lo`) | 85 | **0.48**, 0.71 | 0.88, 1.00 |

The reported table (271 Charges, 180 with `t_lo > 0`): all 0.80/1.03, bounded 1.13/1.34,
unbounded 0.58/0.80. **Same sign, same shape, close magnitude** — the `t̂/t_lo` figure for
"all items" matches to two decimal places (1.03 both). Restricting to the closest comparable
window, Games 1–27 (the range `engine.py`'s own extensive charge-bucket analysis uses),
brings the binary claim even closer:

| window | provably below `t` (Charge < `t_lo`) | provably above `t` (Charge > `t_hi`, bounded only) |
| --- | ---: | ---: |
| reported | 61% | 33% |
| this measurement, Games 1–27 | 60% | 25% |
| this measurement, Games 1–38 | 67% | 22% |

**Below** reproduces almost exactly at the comparable window (60% vs 61%). **Above** is
directionally confirmed but numerically off by 8pp at every window tried (25–22% here vs
33% reported) — not resolved, and flagged rather than explained away; it did not close by
matching the game range more closely, and the gap *shrinks further* with the 11 extra Games
now available (33 → 25 → 22%), consistent with a mild real improvement in overcharging over
time rather than a bug in either measurement.

**New evidence this adds:** on the 85 unbounded items, `t̂ < t_lo` (the estimate undershoots
a value that is *by construction* a hard lower bound on the truth) for **62 of 85 — 73%**.
That is not an inference, it is a proof, on 73% of the censored population, that the
estimator is too low. This is the single strongest number in this report.

**Staleness caveat, stated rather than ignored:** Games 1–25's rows are reconstructed from
`var/evidence/case_NN_{model,memory}.json`, cached whenever `dump_evidence.py` last ran for
that Game — which may predate later enrichments of `var/price_memory.json`. Concretely,
Game 11 items 2/20/21 ("Skilled worker hours", "Service technician hours") show
`has_memory=True` with healthy median estimates (680, 420, 1250 from the model; 592, 380,
1036 from the cached memory anchor) yet an **actual submitted Charge of 0.00** on all three
— a pre-Strategy-2-era pipeline gap, not a pricing-formula defect, and unrelated to the
upward-charge question. Excluded from interpretation for that reason, but left visible in
the data rather than filtered out, per the "open the Case" rule.

## 2. Is there a live signal?

`scripts/experiments/upward_charge_signals.py` joins the same 216 rows to five
decision-time fields and tests each against the binary target "Charge < `t_lo`" (provable
underpricing), via Mann-Whitney AUC (P(a random underpriced item's signal is higher) — 0.5
is chance) and a tercile table.

```
PYTHONPATH=. python scripts/experiments/upward_charge_signals.py
```

| signal | AUC | direction if any |
| --- | ---: | --- |
| `t_hat` (estimate magnitude) | 0.459 | weak, wrong side of chance to be useful |
| `sigma` (band width) | 0.460 | weak |
| `coverage_probability` | 0.444 | weak |
| `quantity` | 0.556 | weak |

At n=216 (144 positive / 72 negative) the standard error on an AUC is roughly ±0.045 —
**every continuous signal sits inside one standard error of 0.5.** None separates. The
tercile tables confirm it: underpriced share moves by at most 8–11pp across the bottom vs
top third for any of the four, with no consistent monotone trend (`t_hat`: 72%→60%→68%,
U-shaped, not usable as a threshold).

Two categorical splits are real, by contrast:

| split | n | underpriced share |
| --- | ---: | ---: |
| channel: B:memory | 140 | **72%** |
| channel: C:model only | 76 | 57% |
| metered (hr / m² / day / kg wording) | 31 | **84%** |
| not metered | 185 | 64% |
| memory **and** metered (intersection) | 25 | **88%** |
| quantity > 1 | 71 | 72% |
| quantity ≤ 1 | 145 | 64% |

Channel is the signal `engine.py` already tried and buried (Games 1–27, non-monotone,
failed held-out) — the gap is real but the mechanism was already tested and lost. Metered
wording is genuinely new: no upward metered multiplier has ever been swept in this codebase
(`engine.py`'s docstring only shows `metered x0.6` / `x0.9`, both downward).

**Grounded in a Case, per the evidence rule.** Case 35 item 2, "Skilled worker hours
(8 hrs)" — a real labour line for a cellar leak repair (`description.txt`: *"the joint was
sealed, the affected wall tiles were removed and replaced... drying equipment ran for around
two weeks"*), invoiced by a named trades contractor. Policy §5.2.1(g) covers **"the labour
of the trades engaged, at rates customary for that trade."** Our decision log priced
`t_hat = 644.17`, we Charged **446.23**, and the recovered floor is **`t_lo = 705.36`** — our
own estimate undershoots the proven floor, and the Charge undershoots the estimate further
still. This is the metered/labour pattern in miniature: real coverage, real invoice support,
and a Charge that a hard lower bound already proves too low.

## 3. Sweeping the two candidates that survived

`scripts/experiments/upward_charge_sweep.py` sweeps three families through
`charge_buckets.Rule`/`total()` — the same replay surface (`replay_payoffs.replay` against
the real Field) every constant in `engine.py` is measured on. Windows: all 38 Games, and
Games 19–37 (the task's requested window, stopping one short of "whichever Game most
recently settled" for reproducibility).

```
PYTHONPATH=. python scripts/experiments/upward_charge_sweep.py
```

Shipped baseline: **+142,719** (all 38), **+20,378** (19–37).

**Memory (channel), multiplied alone (not paired with a model-side discount):**

| ×m | all 38 | Δ | 19–37 | Δ |
| --- | ---: | ---: | ---: | ---: |
| 1.00 | 142,719 | 0 | 20,378 | 0 |
| 1.05 | 166,909 | +24,189 | 27,767 | +7,390 |
| 1.10 | 174,463 | +31,744 | 27,423 | +7,045 |
| **1.15** | **186,158** | **+43,439** | **34,333** | **+13,956** |
| 1.20 | 165,378 | +22,659 | 26,522 | +6,145 |
| 1.25 | 166,317 | +23,598 | 27,121 | +6,744 |
| 1.30 | 158,590 | +15,871 | 32,117 | +11,740 |
| 1.40 | 121,909 | −20,810 | 20,947 | +569 |

**Not monotone** in either window (rises, falls, rises, falls). This is the identical
symptom `engine.py` names for the related paired family: "the total jumps whenever our
Charge crosses a cluster... a fact about sixteen specific opponents, not about pricing."
Per-Game attribution (not concentrated in one or two Games, unlike the earlier paired
family, where Games 1 and 7 alone supplied two-thirds of the peak): 18 of 38 Games gain,
1 loses more than 5k (Game 6, −7,679), the rest are noise-sized. **But the 11 Games settled
since the last audit (28–38) contribute only +6,133 combined — about 40% of the historical
per-Game average** — a weakening trend, not a strengthening one, despite the larger sample.

**Metered wording, multiplied alone:**

| ×m | all 38 | Δ | 19–37 | Δ |
| --- | ---: | ---: | ---: | ---: |
| 1.00 | 142,719 | 0 | 20,378 | 0 |
| 1.10 | 148,089 | +5,370 | 20,821 | +444 |
| 1.20 | 126,321 | −16,398 | −877 | −21,255 |
| 1.30 | 120,752 | −21,967 | 2,967 | −17,411 |
| 1.40 | 82,658 | −60,061 | −17,505 | −37,883 |

**Not monotone**, and worse than that: it is a cliff after ×1.1, not a curve. Both positive
cells (+5,370, +444) sit far inside the ±38,681 / ±27,352 noise floors for these windows —
statistically zero.

**Memory ∩ metered (n=25):** mostly negative from ×1.1 on, both windows; too small a bucket
(the 88% underpriced share in §2 is 22 of 25 items) to trust, and the sweep agrees.

**Noise floors:** ±38,681 (all 38 Games), ±27,352 (Games 19–37), using the standing
`26,622 × √(n/18)` formula.

## 4. Held-out folds

Same script, `--` odd/even (interleaved, same Field both halves) and 1–20 → 21–38
(disjoint, time-ordered — the harder test, since a Field measurement does not survive a
phase boundary, README R9):

| family | odd→even | even→odd | 1–20→21–38 | 21–38→1–20 |
| --- | ---: | ---: | ---: | ---: |
| memory (channel) | +21,319 (×1.15) | **−19,058** (×1.3) | +9,632 (×1.15) | +33,807 (×1.15) |
| metered | +1,176 (×1.1) | +4,193 (×1.1) | +444 (×1.1) | +4,926 (×1.1) |
| memory ∩ metered | −1,740 (×1.1) | −13,935 (×1.3) | −1,491 (×1.1) | −9,656 (×1.3) |
| **summed** | +20,756 | **−28,799** | +8,584 | +29,077 |

Noise floors: ±27,352 (odd/even, 19 Games each), ±26,622 (test on 18 Games), ±28,062 (test
on 20 Games).

**The fold that predicts the future (1–20 → 21–38) is the one that matters most, and it is
inside the noise floor (+8,584 against ±26,622) for the summed families and +9,632 against
the same floor for memory alone** — indistinguishable from zero. The reverse-time fold
(21–38 → 1–20, training on the *recent* Field to price the *old* one) clears its floor at
+33,807/+29,077, but that direction has no operational meaning — we cannot train on Games
that have not happened yet. `even→odd` is a real loss (−19,058 / −28,799), close to its own
floor. No family is positive in all four columns, and the one family with real magnitude
(memory) is the one already known, from `engine.py`, to owe its peaks to Limit-cluster
crossings rather than to pricing.

## 5. The cliff, in euros

`scripts/experiments/upward_charge_cliff.py` splits every touched row into three buckets
against the point estimate `t` (bracket midpoint if bounded, `t_lo` if not), using
`charge_buckets._income()` — the real Field payoff for a given Charge, not a theoretical one:

```
PYTHONPATH=. python scripts/experiments/upward_charge_cliff.py
```

| candidate | stayed below t (n, €) | crossed above t (n, €) | already above t (n, €) | net |
| --- | --- | --- | --- | --- |
| memory ×1.15 | 146, +76,400 | 18, **−30,120** | 29, +938 | +47,219 |
| metered ×1.1 | 44, +20,196 | 6, **−13,559** | 9, +74 | +6,711 |
| memory∩metered ×1.1 | 30, +12,646 | 5, **−12,300** | 5, +277 | +623 |

For the strongest candidate, roughly **2.5 euros gained (staying below `t`, capturing more
of the deliberate discount) for every 1 euro lost (crossing into an Overcharge)** —
structurally the same story `LIMIT_CEILING_MEMORY`'s 7.53:1 tells on the Limit side, just a
weaker ratio, and one that in-sample profitability alone (§3's non-monotone peak, §4's
failed forward fold) already says not to trust as a stable operating point.

## 6. The dark-window regime

Games 44–81 have not settled (38 Games completed at measurement time), so this reuses the
already-built `dark_regime_replay.py` regime layer — `fully_dark` zeroes every opponent's
Limit **and** Charge, matching CLAUDE.md rule 9's "a dark Reviewer rejects everything" —
rather than waiting for real dark data:

```
PYTHONPATH=. python scripts/experiments/upward_charge_dark.py
```

| regime | shipped net | memory ×1.15 net | Δ |
| --- | ---: | ---: | ---: |
| awake (control = real Games 1–38) | 142,719 | 186,158 | +43,439 |
| fully dark | 917,253 | 942,537 | **+25,284** |

Matches the payoff-table prediction exactly: our income on `a ≤ t` items pays `a` whether
the reviewer accepts or wrongfully rejects, so darkness doesn't touch the "stayed below t"
gains — but an Overcharge that would have earned ~20% against an awake Field earns **0%**
against a dark one, so the "crossed above t" losses get strictly worse. The gain doesn't
flip sign here (58% retained), but this is confirmatory, not decisive: the candidate is
already not being shipped because §3–4 fail on their own. **No regime-dependent
recommendation change is needed, because there is no recommendation to make regime-dependent
in the first place.**

## Recommendation

**Ship nothing.** Every signal available in the decision log at submission time —
`t_hat`, `sigma`, `coverage_probability`, `quantity` — is statistically indistinguishable
from noise (AUC 0.44–0.56) for predicting which items we are underpricing. The two
categorical splits that do show a real gap (channel, metered wording) both produce
multipliers that fail this file's own bar, the same one `engine.py` already applies to every
downward family: **monotone in its own parameter**, and **positive on the held-out fold that
matters for prediction, beyond the noise floor**. Neither clears both. The metered signal is
new and worth remembering — it is a real, un-tried gap (84% vs 64% underpriced) — but its
euro behaviour (noise-floor-flat at the only survivable multiplier, catastrophic one step
further) makes it a cliff, not a lever, at the current sample size (n=31).

**What would change this:** the memory-channel family's per-Game contribution has been
*weakening*, not strengthening, over the last 11 Games (+6,133 combined against a historical
average of ~1,700/Game) — the opposite of what would justify revisiting it. If that reverses
over the next 10–15 Games (concretely: the 1–20→21–38 forward fold clearing +26,622 rather
than sitting at +9,632), it would be worth a second look. Absent that, the honest statement
CLAUDE.md's evidence rules ask for is the right one: **the underpricing is real and provable
after settlement, and nothing available before submission predicts it well enough to act
on.** The gap belongs to the evidence layer — a `t_hat` that is itself proven too low on 73%
of censored items — not to a conditional Charge multiplier.

No `src/` diff is proposed. For completeness, the shape such a change would take if the
weakening trend above ever reverses — **not applied, not recommended at this measurement**:

```diff
--- a/src/domain/pricing/engine.py
+++ b/src/domain/pricing/engine.py
@@ def price_item(
     charge = charge_factor(sigma) * filled.price_median
+    if memory_backed:
+        # See docs/brainstorm/sebi/strats/review/upward-charge.md: in-sample peak only,
+        # non-monotone, forward held-out fold inside the noise floor. Do not ship without
+        # re-measuring and clearing +/-26,622 on a 1-20 -> 21+ split.
+        charge *= MEMORY_CHARGE_MULTIPLIER  # would-be constant, e.g. 1.15
```

---

## Appendix: harness files

- `scripts/experiments/upward_charge_verify.py` — §1, independent reproduction of the
  Charge/`t_lo` and `t̂`/`t_lo` table from actual submitted Charges (not the counterfactual
  Rule).
- `scripts/experiments/upward_charge_signals.py` — §2, AUC and tercile signal-separation
  test against the "provably underpriced" target.
- `scripts/experiments/upward_charge_sweep.py` — §3–4, the three candidate families, swept
  and held out, reusing `charge_buckets.Rule`/`total()`.
- `scripts/experiments/upward_charge_cliff.py` — §5, the stayed/crossed/already-above euro
  decomposition via `charge_buckets._income()`.
- `scripts/experiments/upward_charge_dark.py` — §6, the same candidate replayed under
  `dark_regime_replay.regime_snapshot(..., "fully_dark")`.
- `scripts/experiments/pinned/price_memory_vintage_g38.json` — the pinned Price Memory copy
  every number above is scoped against (built_from_games 1–38, 181 entries, σ 0.43).

Reproduce the headline:

```
PYTHONPATH=. python scripts/experiments/upward_charge_verify.py
PYTHONPATH=. python scripts/experiments/upward_charge_signals.py
PYTHONPATH=. python scripts/experiments/upward_charge_sweep.py
PYTHONPATH=. python scripts/experiments/upward_charge_cliff.py
PYTHONPATH=. python scripts/experiments/upward_charge_dark.py
```

None of these touch `src/`, `main.py`, `pixi.toml`, `.env`, or any running process; all read
cached/public data (`var/transactions`, `var/replay`, `var/evidence`, `var/decisions`, the
pinned `var/price_memory.json` copy).
