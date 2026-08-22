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

**Addendum, folded in before completion.** Mid-task, a second measurement arrived
(`docs/brainstorm/sebi/strats/review/sigma-calibration.md`, written independently the same
night) proposing a different mechanism: not a Charge multiplier, but a **measured sigma**
substituted for the model-asserted band width that currently feeds `charge_factor` and the
Limit's quantile. §7 tests it, on the same replay harness, with its own vintage stated
(Game 39 settled between §1–6 and §7; §7 uses Games 1–39, §1–6 keep their original 38-Game
numbers unchanged rather than being silently redone).

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
6. **The measured-sigma reframe does not rescue this, and independently confirms
   `sigma-calibration.md`'s own verdict.** Substituting the true measured error for the
   model's asserted band width — the fix the reframe proposed, tested here through a
   line-for-line, sanity-checked reimplementation of `price_item` itself, on the real
   `LIMIT_CEILING_MEMORY`-aware baseline, over Games 1–39 — loses **−64,727 to −80,738**
   across three tested configurations, **unanimously negative in all four held-out folds,
   for every config**, dominated 20:1 by the Charge side over the Limit side. It *does* fix
   the backwards ordering `engine.py`'s docstring names as the falsifier (narrow-measured-σ
   items now forfeit 4% of oracle income against wide's 10%, the correct sign) — and loses
   money anyway, because `CHARGE_SLOPE`/`CHARGE_INTERCEPT` were tuned against the asserted
   band's scale, not the true one, so a more honest sigma just pushes an already-tuned
   formula off the point it was tuned at. See §7.

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

## 7. The measured-sigma reframe

A second measurement arrived mid-task, proposing a different mechanism entirely: not a
Charge multiplier, but replacing the sigma that `price_item` feeds into `charge_factor` and
the Limit's quantile — currently the model-*asserted* band width, `implied_sigma(...)`,
already measured to carry no signal — with a *measured* error, looked up by channel
(`B:memory` vs `C:model`) and basis (per-unit vs gross), both readable from the decision log.

**Does §2 already falsify this?** No — the opposite. §2 found channel (72% vs 57%
underpriced) and metered wording (84% vs 64%, a close proxy for per-unit) are the only two
decision-time splits that separate under- from over-priced items at all. That is
*consistent* with this reframe, not a contradiction of it: §2 asked whether a split predicts
which *side of `t`* a Charge lands on; this section asks whether the same split predicts the
estimate's *error magnitude*, a related but distinct question. It survives to be tested.

```
PYTHONPATH=. python scripts/experiments/measured_sigma_core.py       # faithfulness check
PYTHONPATH=. python scripts/experiments/measured_sigma_replay.py     # everything below
```

**Vintage for this section only: Games 1–39** (Game 39 settled between §1–6 and this
section; §1–6's own numbers are left as originally measured at 38 Games rather than
silently redone). `price_item_measured_sigma` in `scripts/experiments/measured_sigma_core.py`
is a line-for-line reimplementation of the real `src/domain/pricing/engine.price_item` —
median, coverage, `LIMIT_CEILING_MEMORY`, `LIMIT_CAP`, the `b<=a` clamp, all untouched — with
only the `sigma = implied_sigma(...)` line replaced by a supplied value. Fed the *original*
`implied_sigma(...)` value, it must reproduce `price_item`'s own output to the cent:
**449/449 rows match exactly** (`measured_sigma_core.py`'s own `sanity_check`). `blend.
MODEL_SIGMA_PRIOR`/`blend.MEMORY_SIGMA` — the *blend-weighting* constants
`sigma-calibration.md` already tested and rejected on their own — are never touched here;
this section only ever changes what reaches `charge_factor`, per the coordinator's caution 2.
Baseline is the **real** `price_item()` (not `charge_buckets.Rule`, which never applies
`LIMIT_CEILING_MEMORY` and would double-count against the ceiling that shipped tonight —
caution 1).

### 7.1 Independent sigma measurement, and why basis is not applied to model-only items

Bounded Line Items only (`t` known exactly, n=185, Games 1–39), RMSLE of `log(t_hat/t)`:

| bucket | n | bias | measured σ |
| --- | ---: | ---: | ---: |
| memory, gross | 99 | +0.048 | 0.431 |
| model, gross | 57 | +0.172 | 0.729 |
| memory, per_unit | 18 | +0.246 | 0.366 |
| model, per_unit | 11 | +0.272 | **0.959** |
| channel alone: memory | 117 | +0.079 | 0.422 |
| channel alone: model | 68 | +0.188 | 0.771 |

**Channel reproduces `sigma-calibration.md`'s figures closely** (memory 0.42, model 0.77,
against their leave-one-out 0.39–0.48 / 0.76–0.78) on an independently-built harness. **Basis
does not generalise to the model channel the way the reframe's table implies**: within
memory, per-unit is tighter than gross (0.366 vs 0.431), matching `sigma-calibration.md`
section 2's dedicated finding — but within model, per-unit is *worse* than gross (0.959 vs
0.729, the opposite sign), on a sample too small to trust either way (n=11). That table's
own 0.32/0.55 split was measured entirely on Price Memory *hits* (`PriceMemoryHit.match`/
`.basis`); extending it to model-only items is the reframe's own extrapolation, unsupported
by either measurement. So the config used here ("mine") splits basis **only within the
memory channel** and uses a flat channel-level figure for model-only items — a more
conservative, better-evidenced version of the reframe's proposal, tested alongside the
literal figures from the coordinator's message ("coordinator") and a channel-only control
with no basis split at all ("channel_only"):

| bucket | n | asserted σ (current) | mine | coordinator | channel_only |
| --- | ---: | ---: | ---: | ---: | ---: |
| model, gross | 191 | 0.407 | 0.77 | 0.78 | 0.77 |
| memory, gross | 187 | 0.352 | 0.43 | 0.55 | 0.42 |
| memory, per_unit | 44 | 0.346 | 0.37 | 0.32 | 0.42 |
| model, per_unit | 27 | 0.322 | 0.77 | 0.78 | 0.77 |

### 7.2 Euro replay — negative, unanimously, in every config tested

Baseline (real `price_item`, current engine, Games 1–39): net **222,964** (income
1,074,806, cost 851,842); Games 19–39: **83,646**.

| config | all 39 net | Δ net | Δ income (Charge side) | Δ −cost (Limit side) | 19–39 net | Δ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mine | 158,237 | **−64,727** | −62,549 | −2,178 | 53,052 | −30,594 |
| coordinator | 142,226 | **−80,738** | −77,417 | −3,321 | 47,672 | −35,973 |
| channel_only | 154,271 | **−68,693** | −65,693 | −3,000 | 50,634 | −33,011 |

Noise floor: ±39,187 (all 39), ±28,755 (Games 19–39). Every config clears the floor —
**these are real losses, not noise.** The Charge side supplies 96–97% of the loss in every
config; the Limit side is small throughout (−2,178 to −3,321), matching
`sigma-calibration.md`'s own finding that the Limit-side effect is the "noisier, weaker
piece." **`channel_only` alone already loses −68,693** — the failure is not an artefact of
the basis refinement; correcting *only* the channel-level sigma (the piece both
measurements agree on) is already enough to lose money.

Held-out folds, delta vs baseline, no fitting (the config is fixed, not chosen per fold):

| config | odd→even | even→odd | 1–20→21–39 | 21–39→1–20 |
| --- | ---: | ---: | ---: | ---: |
| mine | −41,989 | −22,738 | −16,469 | −48,258 |
| coordinator | −60,355 | −20,383 | −19,025 | −61,713 |
| channel_only | −42,929 | −25,763 | −19,095 | −49,597 |

**Negative in all twelve cells.** Noise floors: ±27,352 (odd/even and 21–39, n=19 each),
±28,062 (1–20, n=20). Several cells clear their floor outright (odd→even for every config;
21–39→1–20 for every config). This is the same "unanimous sign across every fold" standard
the repo already trusts when a single cell doesn't individually clear the floor
(`LIMIT_CEILING_MEMORY`'s "eight fold cells, eight positive" is the positive mirror of this
result) — here it is unanimous in the losing direction.

**Monotonicity**, interpolating in log-sigma space from the shipped asserted band (`w=0`) to
the fully measured value (`w=1`):

| config | w=0 | w=0.25 | w=0.5 | w=0.75 | w=1.0 | monotone |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| mine | 0 | −14,692 | −6,262 | −27,350 | −64,727 | No (small wiggle at 0.5) |
| coordinator | 0 | −21,416 | −13,657 | −37,412 | −80,738 | No (same wiggle) |
| channel_only | 0 | −15,685 | −7,987 | −30,487 | −68,693 | No (same wiggle) |

Not strictly monotone, but importantly **a different failure shape than §3's candidates**:
there is no positive peak that later reverses (the artefact CLAUDE.md and `engine.py` warn
about, a fact about which Limit clusters got crossed). This one is negative from the very
first step off `w=0` and gets worse the further it moves, with only a small dip-then-recover
around the midpoint — consistent with a real, gradually-worsening cost rather than a
cluster-crossing artefact. That makes it a *more* trustworthy measurement, not a less
trustworthy one — and it is trustworthy in the losing direction.

### 7.3 The cliff, and why it runs backwards from §5

| config | stayed below t | crossed above t | already above t | net |
| --- | --- | --- | --- | --- |
| mine | n=246, **−110,826** | n=0, +0 | n=52, +39,172 | −71,654 |
| coordinator | n=245, **−140,610** | n=1, −1,942 | n=52, +54,809 | −87,743 |

This is the mechanism, and it is the opposite of §5's multiplier candidates. Widening sigma
*lowers* `charge_factor`, so it pushes Charges **further below `t`**, not closer to it — the
246 items that were already correctly priced below `t` lose money because the discount gets
deeper for no reason, not because anything crosses into an Overcharge (0–1 items ever do).
The only gain (+39,172 / +54,809) is on the 52 items that were *already* Overcharges, where
a lower Charge by chance lands closer to fair — a windfall from the same mechanism that
causes the loss, not a targeted fix.

**Limit side** (loosened vs tightened against the baseline Limit, net cost effect where
positive = cheaper for us):

| config | loosened | tightened | net |
| --- | --- | --- | --- |
| mine | n=0, +0 | n=183, −2,178 | −2,178 |
| coordinator | n=38, +673 | n=146, −3,994 | −3,321 |

`mine`'s buckets are all ≥ the asserted band, so the Limit only ever tightens (never
loosens) under that config — small losses throughout, matching §7.2.

### 7.4 Caution 3, checked directly: does the ordering finally hold?

`engine.py`'s falsifier, run on the *substituted* sigma instead of the asserted band —
terciles by measured σ, forgone income as a share of oracle income per bucket (config
"mine", Games 1–39, `t_lo>0` items):

| tercile | σ range | n | forgone income | share of oracle |
| --- | --- | ---: | ---: | ---: |
| narrow | 0.37–0.43 | 99 | 25,298 | 4% |
| mid | 0.43–0.77 | 99 | 5,505 | 2% |
| wide | 0.77 | 100 | 66,089 | **10%** |

**The ordering flips to the correct sign** — narrow forfeits 4%, wide forfeits 10%, not the
asserted band's backwards 3× (0.847 narrow vs 0.733 wide RMSLE, engine.py's docstring). Per
the falsifier's own stated criterion, this *does* mean the substituted sigma "is measuring
something and its sign can be trusted." **It is not, however, a reason to ship it.** The
ordering being right does not make the level right: `CHARGE_SLOPE`/`CHARGE_INTERCEPT` were
tuned (`tune_pricing.py calibrate`, cited in `engine.py`) against sigma values in the
asserted band's own range (~0.25–0.75); pushing the model channel's sigma to 0.77–0.96 moves
it off the point the formula was tuned at, and the euro numbers in §7.2 say that move costs
money even though the ranking of which items are riskier is now honest. A correct ordering
and a profitable level are different claims, and only the first one holds.

### 7.5 Verdict on the reframe

**Do not ship.** This independently reproduces `sigma-calibration.md`'s own conclusion
(section 3, "the fully calibrated correction... is negative in every fold-half tested") on a
separately-built harness — a faithfulness-checked reimplementation of `price_item` itself
rather than a `blend.combine()` monkeypatch, over Games 1–39 rather than the 29
cached-evidence Games that harness was limited to, and with the Limit side (via
`LIMIT_CEILING_MEMORY`) included rather than tested in isolation — and gets the same
answer: unanimous loss, dominated by the Charge side, real relative to the noise floor. The
two independent investigations agree on both the direction and the mechanism (`CHARGE_SLOPE`
is calibrated against a scale the asserted band supplies and a measured sigma breaks), which
is stronger evidence than either alone. Land `sigma-calibration.md` section 4's honest-field
diff (already applied to `scripts/build_price_memory.py` as of this writing — see that file's
`measured_leave_one_out_sigma_log` line) regardless; do not move `CHARGE_SLOPE`,
`CHARGE_INTERCEPT`, `MODEL_SIGMA_PRIOR`, or `MEMORY_SIGMA`, and do not substitute a measured
sigma into `charge_factor` or the Limit's quantile.

---

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

**The mid-task reframe (§7) does not change this recommendation — it closes the door from
the other side.** It tested a structurally different fix (a measured sigma in place of the
asserted one, rather than a Charge multiplier) and got a cleaner, more decisive negative:
unanimous losses across three configurations and every held-out fold, independently
agreeing with `sigma-calibration.md`'s separately-built harness on both sign and mechanism.
Between the two candidates tested tonight, the reframe is the more informative result
precisely because it *is* clean — no wiggling non-monotone peak to argue about, no fold that
flips sign, just a consistent, mechanistically-explained loss. Combined with §1–6: neither
"multiply the Charge on the items a decision-time signal flags" nor "feed pricing a more
honest sigma keyed on that same signal" survives contact with the real Field.

No `src/` diff is proposed for either candidate. For completeness, the shape the §1–6
Charge-multiplier change would take if its weakening trend ever reverses — **not applied,
not recommended at this measurement**:

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
  §1–6 are scoped against (built_from_games 1–38, 181 entries, σ 0.43).
- `scripts/experiments/measured_sigma_core.py` — §7, the faithfulness-checked
  reimplementation of `price_item` (`price_item_measured_sigma`, `sanity_check`,
  `basis_of`/`channel_of`).
- `scripts/experiments/measured_sigma_replay.py` — §7, the three-config euro replay, folds,
  monotonicity sweep, and the two cliff/ordering checks.

Reproduce the headline:

```
PYTHONPATH=. python scripts/experiments/upward_charge_verify.py
PYTHONPATH=. python scripts/experiments/upward_charge_signals.py
PYTHONPATH=. python scripts/experiments/upward_charge_sweep.py
PYTHONPATH=. python scripts/experiments/upward_charge_cliff.py
PYTHONPATH=. python scripts/experiments/upward_charge_dark.py
PYTHONPATH=. python scripts/experiments/measured_sigma_core.py
PYTHONPATH=. python scripts/experiments/measured_sigma_replay.py
```

None of these touch `src/`, `main.py`, `pixi.toml`, `.env`, or any running process; all read
cached/public data (`var/transactions`, `var/replay`, `var/evidence`, `var/decisions`, the
pinned `var/price_memory.json` copy).
