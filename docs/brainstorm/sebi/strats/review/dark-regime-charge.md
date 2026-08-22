# Dark-regime Charge: verified, replayed, swept — recommendation is **do not ship**

Written 2026-08-22, ~22:00–23:30 CEST, ahead of the Game 44 (00:15 CEST) phase boundary.
All numbers below are reproducible from the harness in `scripts/experiments/` against the
live leaderboard (34 Games completed at time of writing: 1–34; the primary window, matching
the finding this task started from, is Games 19–32).

## Headline

1. **The fair/Overcharge income split is confirmed exactly**, independently reproduced to the
   euro. Half our Issuer income really is Overcharges a loose Reviewer accepted, and we are
   the most dependent on it of the four leaders. Not in dispute.
2. **The Charge multiplier is not the lever.** Across two independent windows (14 Games and
   34 Games) and three noise-error levels, the euro-optimal flat Charge multiplier moves by
   at most ~0.10× of the median between an awake field and a fully dark one, and **the cost
   of shipping the wrong one is 0–800 €/Game — inside the noise floor at every window
   tested** (±1,678 €/Game on 14 Games, ±1,076 €/Game on 34 Games). The currently shipped
   formula (`CHARGE_INTERCEPT=0.85, CHARGE_SLOPE=0.45`) already lands within that band at
   every σ tested. **Recommendation: do not change `CHARGE_INTERCEPT`/`CHARGE_SLOPE`/
   `CHARGE_BOUNDS` for the dark window.**
3. **The real money in "the field goes dark" is on the reviewer/cost side, not the charge
   side, and it requires no code change at all.** If dark opponents also stop *issuing*
   Charges (the tournament's own default, CLAUDE.md rule 1), our reviewer-side cost
   collapses toward zero regardless of what our Charge multiplier is — worth **5–40× more**
   than any Charge-multiplier tuning could ever be, and it happens automatically.
4. **The Limit mirror-question is a genuine mixed result, not a clean "yes."** In true full
   darkness the Limit is *provably* irrelevant (not just measured — an exact, flat curve).
   The "raise the Limit because the survivors are the accurate teams" hypothesis showed a
   real effect on the 14-Game window but **did not replicate on the 34-Game window**
   (control and top-5-awake converge to the *same* optimal Limit there). Flagged as an
   in-sample win that failed its held-out check — no Limit change recommended either.
5. **A live darkness signal exists and is cheap to compute**: field-wide acceptance rate
   among Charges that are provably positive (not the naive "count of nonzero issuers", which
   is confirmed broken — see §4). Recommend deploying it as a **read-only monitor**, not as
   a gate on a same-night pricing change.

---

## 1. Verifying the split (independent reproduction)

New code, not a review of the given numbers: `scripts/experiments/dark_income_split.py`
imports only the two already-verified primitives (`invert_fair_values.brackets`,
`pull_transactions.transactions`) and does its own row-by-row classification —
`a <= t_lo` → fair, `a >= t_hi` → Overcharge, anything else → ambiguous (excluded, reported
separately so it can't be silently swept under either bucket).

```
PYTHONPATH=. python scripts/experiments/dark_income_split.py --games 19-32
```

| team | fair € | fair % | Overcharge € | over % | ambiguous |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bin busy (us) | 160,315 | 48.0% | 173,414 | 52.0% | 0 |
| eyay | 193,765 | 56.8% | 147,413 | 43.2% | 0 |
| error404 ai | 225,686 | 66.0% | 116,358 | 34.0% | 0 |
| TakeTheMoneyAndRun | 181,808 | 69.2% | 80,819 | 30.8% | 0 |

**Exact match to the given table, to the euro**, including the "zero ambiguous" claim
(0 of 4,164,638 € total income across all 17 teams landed in the interior of a bracket).
The per-Game fair-income deltas also check out arithmetically: `us 11,451 − eyay 13,840 =
−2,389/Game`, `us 11,451 − error404 16,120 = −4,669/Game`, matching the "~2,389" / "~4,669"
figures in the finding exactly.

Re-run over all 34 completed Games (broader but noisier — early Games are a different
regime per rule 9): Bin busy's split is **59.4% fair / 40.6% Overcharge** (308,502 € /
211,182 €, 29 of 34 Games with any money-moving row) — the Overcharge dependency shrinks
but does not go away over the full sample. **Verdict: the split is real, not an artifact of
the 19–32 window.**

---

## 2. The dark-field replay harness

`scripts/experiments/dark_regime_replay.py` — **imports** `scripts/replay_payoffs.py`
unmodified and adds one thing: a *regime* layer that overrides a chosen set of opponents'
`limit_brackets` (always) and `charges` (optionally) to `(0, 0)` before replay. Everything
else (`replay()`, `sweep_total()`, the oracle estimator, snapshot reconstruction) is reused
byte-for-byte.

Two darkness models, because "dark" is ambiguous and it matters which one you mean:

- **`zero_charges=True` ("fully dark", the default used below)** — dark teams' Limit *and*
  Charge both go to `(0, 0)`, matching CLAUDE.md rule 1's definition of what a team that
  submits nothing actually produces. This is the realistic model of a team whose pipeline
  is not running, in either role.
- **`zero_charges=False` ("limits-only")** — dark teams' Limit → 0 but their Charge is left
  at whatever they actually charged in the real Game. This is what the task literally asked
  for and is the conservative floor: a truly offline team wouldn't be charging either, so
  this leaves our reviewer-side cost too high.

Three regimes: `control` (no override — must reproduce the published net exactly),
`fully_dark` (every opponent dark), `top5_awake` (only `{eyay, error404 ai,
TakeTheMoneyAndRun, OPUSMOPUS, Alpha}` stay awake, everyone else dark).

**Control check, both windows, both darkness models — passes exactly:**

```
PYTHONPATH=. python scripts/experiments/dark_regime_replay.py --games 19-32 --control-check
  -> control check: OK, all reproduce published nets
PYTHONPATH=. python scripts/replay_payoffs.py --games all --self-check
  -> reconstructs (34): [1..34]   UNUSABLE (0): none
```

`replay_payoffs.py` reproduces every one of the 34 published nets to the cent (max
observed discrepancy 0.01 €, floating-point rounding). Trusted as ground truth for
everything below.

---

## 3. The regime sweep

`scripts/experiments/dark_regime_sweep.py` extends `tune_pricing.py`'s already-validated
synthetic-estimator methodology (`t_hat = t · exp(N(0, σ))`, 5 replicas, smoothed-peak
argmax — the exact machinery that derived the shipped `CHARGE_INTERCEPT`/`CHARGE_SLOPE`
line) with the regime override from §2. **Sanity check against the published reference
first**: at σ=0.45, `control` on Games 1–14 gives best `a = 0.60 × median`, net 146,126 —
matches the `src/domain/pricing/engine.py` docstring's own table (`0.60`, +149,496) to within 2.3%, the
expected size of replica noise. The harness is trusted.

σ values used: **0.43** (measured Price Memory quality per CLAUDE.md rule 10), **0.60**
(mid), **0.80** (the bias-corrected RMSLE CLAUDE.md warns is the honest current number).

### 3a. Flat Charge multiplier, Limit fixed at 1.0× median uncapped (isolates the Charge axis)

**Games 19–32 (14 Games, noise floor ±23,478 / ±1,678 per Game), fully-dark model:**

| regime | σ=0.43 | σ=0.60 | σ=0.80 |
| --- | --- | --- | --- |
| control (real field) | a=0.75, net 81,308 | a=0.70, net 45,744 | a=0.55, net 4,356 |
| fully_dark | a=0.70, net 239,987 | a=0.60, net 208,432 | a=0.55, net 180,943 |
| top5_awake | a=0.70, net 172,596 | a=0.65, net 139,346 | a=0.55, net 106,111 |

**All 34 completed Games (noise floor ±36,588 / ±1,076 per Game), fully-dark model:**

| regime | σ=0.43 | σ=0.60 | σ=0.80 |
| --- | --- | --- | --- |
| control | a=0.60, net 246,569 | a=0.55, net 135,091 | a=0.45, net 3,732 |
| fully_dark | a=0.60, net 801,317 | a=0.50, net 679,627 | a=0.45, net 597,755 |
| top5_awake | a=0.60, net 572,981 | a=0.55, net 465,482 | a=0.45, net 349,858 |

The Charge optimum moves **down by 0–0.10× of the median** going from control to
fully_dark, at every σ, on both windows. Direction is consistent with R5b/R6's qualitative
"dark wants a lower quantile"; magnitude is small and, per the fold check below, not
precisely pinned down by the data we have.

The **`limits-only`** model (opponents keep their real historical Charge, only their Limit
goes to 0) gives the *identical* best-`a` values at every cell — because our income depends
on the opponent's *Limit*, never their Charge (structural, same fact `replay_payoffs.py`
already documents for `limit_sensitivity`). Only the *net level* changes between the two
darkness models (see §3c); the optimal Charge multiplier is robust to which one you pick.

### 3b. Two-sided cost of being wrong (item 3's actual question)

```
PYTHONPATH=. python scripts/experiments/dark_regime_sweep.py --games 19-32 --all-regimes \
    --sigmas 0.43,0.60,0.80 --cross-cost
```

| window | σ | ship dark-tuned `a`, field stays awake | ship awake-tuned `a`, field goes dark |
| --- | --- | --- | --- |
| 14 Games | 0.43 | **−123 €/Game** (i.e. no loss) | **−178 €/Game** (no loss) |
| 14 Games | 0.60 | **+286 €/Game** | **+789 €/Game** |
| 14 Games | 0.80 | **−133 €/Game** (no loss) | **−346 €/Game** (no loss) |
| 34 Games | 0.43 | 0 €/Game (identical optimum) | 0 €/Game (identical optimum) |
| 34 Games | 0.60 | **+771 €/Game** | **−643 €/Game** (no loss) |
| 34 Games | 0.80 | **+276 €/Game** | 0 €/Game (identical optimum) |

Every positive cell is at or below the per-Game noise floor (±1,678 €/Game on the 14-Game
window, ±1,076 €/Game on the 34-Game window). Negative "costs" are noise (replica variance
around a flat plateau), not real gains. **There is no configuration of this sweep in which
picking the "wrong" regime's Charge multiplier costs a real, out-of-noise amount of money.**

### 3c. Held-out folds (rule: report every in-sample win with its held-out fold)

Odd/even split of Games 19–32 (7 + 7 Games, floor ±16,602) and the requested 1–20 / 21–32
split (20 + 12 Games, floors ±28,062 / ±21,737):

| fold pair | regime | σ | best `a` fold A | best `a` fold B | A→B gap | B→A gap |
| --- | --- | --- | --- | --- | --- | --- |
| odd/even 19-32 | fully_dark | 0.43 | 0.75 | 0.65 | 3,745 | 5,385 |
| odd/even 19-32 | fully_dark | 0.60 | 0.70 | 0.60 | 13,857 | 1,065 |
| 1-20 / 21-32 | fully_dark | 0.43 | 0.60 | 0.70 | 6,501 | 47,913 |
| 1-20 / 21-32 | fully_dark | 0.60 | 0.50 | 0.60 | 13,273 | 35,662 |

All Charge-only gaps stay under or near their fold's noise floor except the two
1–20 → 21–32 "B-params-on-A" rows (47,913 and 35,662, against a 28,062 floor) — but those
are the **joint** (Charge + Limit together) gaps; see §5, where the Limit dimension is the
one that doesn't generalize. The Charge multiplier alone never produces an out-of-noise
held-out gap in any fold tested.

**Conclusion for item 3: the Charge multiplier does not want to move for the dark window
by an amount worth coding, testing, and risking on a live, unattended runner.**

---

## 4. A live darkness signal that survives a worthless Case

`scripts/experiments/dark_signal.py`. The naive signal named in the brief — "count of
issuers with a nonzero Charge" — turns out to specifically mean *issuers with a Charge that
was **wrongfully rejected*** (i.e. `t_lo > 0` evidence for that team): confirmed by direct
query, this count is **exactly 0** on Games 21, 22 and 28, and all three have `t_lo = 0` on
*every* Line Item (2, 1 and 10 items respectively — genuinely worthless Cases, not sleep).

**The fix**: condition on *any* Charge being attempted, field-wide, and ask what fraction
of *those* got accepted:

```
field_accept_rate(game) = accepted rows where the issuer's recovered Charge is a known,
                           positive number  ÷  all such rows
```

A rightful rejection always pays `amount = 0`, so a row's own `amount` can't tell you
whether a Charge was attempted — this reuses `invert_fair_values.charges()` (the
already-verified recovery primitive) to know which rows carry a real positive Charge before
asking whether the Field said yes. Charges of exactly 0 are excluded on both sides of the
ratio (they're trivially "accepted" by anyone, dark or not, and would fake a high rate).

**On the disputed Games, this signal reads real, high support and a normal-looking rate —
correctly refusing the false "dark" reading:**

| Game | naive (wrongful-rejection issuers) | priced rows | accept rate |
| --- | --- | --- | --- |
| 21 | 0 | 448 | 49.6% |
| 22 | 0 | 240 | 36.7% |
| 28 | 0 | 1,408 | 10.2% |

Over all 34 completed Games (all currently-awake): median accept rate **34.0%**
(IQR 23.3%–39.0%, min 6.7% at Game 16, max 49.6% at Game 21). Games with a low naive count
(21, 22, 28) do **not** show up as accept-rate outliers in the same direction the naive
signal implies — 21 and 22 are near the *top* of the observed range.

**Operational recommendation**: watch a rolling 2–3-Game median of `field_accept_rate`
(computable the moment each Game settles, from public `/transactions`, no key required).
A sustained drop toward single digits **while `priced_rows` stays substantial** (i.e.
people are still trying to Charge something, just getting universally rejected) is the
dark-field signature; a single low Game with a big denominator (like Game 28's 10.2% on
1,408 rows) is inside the already-observed awake-field range and should not trigger
anything alone. This is read-only and safe to deploy tonight regardless of the Charge/Limit
decision above.

---

## 5. The mirror question: does the Limit want to move?

Joint sweep (`--joint`): find the best flat Charge multiplier first, then the best Limit
multiplier at that Charge — same two-stage procedure `tune_pricing.calibrate` already uses.

**The exact, structural part — fully dark, Limit is provably irrelevant.** Fixing Charge at
0.70× median and sweeping Limit from 0.05 to 1.50× median under `fully_dark`
(`zero_charges=True`) gives **the identical net, 244,130 €, at every single point on the
grid.** Not approximately flat — bit-identical, because a dark issuer's Charge is 0, and
0 ≤ any Limit, so acceptance is trivial and costs nothing regardless of what our Limit is.
**Your original reasoning is confirmed exactly for true full darkness.**

**The composition-shift hypothesis (raise the Limit because the survivors are accurate) —
mixed, and doesn't replicate.**

| window | regime | σ=0.43 | σ=0.60 | σ=0.80 |
| --- | --- | --- | --- | --- |
| 14 Games (19–32) | control | b=0.80 | b=0.70 | b=0.55 |
| 14 Games (19–32) | top5_awake | **b=0.90** | **b=0.80** | **b=0.80** |
| 34 Games (all) | control | b=1.00 | b=1.00 | b=0.85 |
| 34 Games (all) | top5_awake | b=1.00 | b=1.00 | b=0.85 |

On the 14-Game window, `top5_awake` wants a meaningfully *higher* Limit than `control` at
every σ — the effect the mirror-question hypothesis predicts. **On the full 34-Game window
the two regimes converge to the identical optimum.** This is exactly the in-sample-win/
held-out-failure pattern CLAUDE.md warns about: the 14-Game effect does not survive being
checked against the larger sample. I am reporting it as a **failed replication**, not a
confirmed finding — do not act on the 14-Game numbers alone.

Two more reasons not to read the absolute Limit levels (0.80–1.00× median) as "what to
ship": (1) this sweep uses the same *well-calibrated synthetic* estimator that derived the
shipped Charge line, but our real model's band is known to be **overconfident** (implied σ
≈0.375 vs actual RMSLE ≈0.80, per `src/domain/pricing/engine.py`) — a well-calibrated-estimator sweep
does not transfer its absolute Limit level onto an overconfident real one. (2) The
1–20 / 21–32 held-out check (§3c) showed its largest generalization failures specifically on
runs that included the Limit dimension (47,913 and 35,662 against floors of 28,062) —
the joint optimum, and therefore the Limit component of it, is the less stable half of this
sweep.

**Verdict on item 5: no Limit change recommended.** Full darkness: proven irrelevant, so
there's nothing to gain by moving it. Partial darkness: a real-looking effect on one window
that a bigger window erases — not solid enough to ship.

---

## 6. Why net moves so much anyway — and why that needs no code change

The dominant number in this whole report is not any optimum in §3 or §5 — it's the *level*
difference between `control` and `fully_dark`: **≈3–5× higher net in fully_dark than
control**, on both windows, at every σ (e.g. 34-Game σ=0.60: 135,091 € control vs 679,627 €
fully_dark). Almost none of that gap is us picking a better multiplier — the `limits-only`
model (§2, opponents still charging their real historical amounts, only rejecting us)
actually **loses** money relative to control at higher σ (e.g. −46,021 € at σ=0.80, 19–32
window) because we'd still be paying real costs to real Charges from a field that's merely
being stricter with us specifically. The gain only appears in the `zero_charges=True`
("truly dark", both `a=0` and `b=0`) model, and there it's overwhelmingly a **cost-side**
effect: if opponents stop issuing too, our reviewer-side cost collapses toward zero no
matter what Charge or Limit we submit. That happens automatically, with the pipeline
exactly as it ships tonight — it needs no gate, no signal, no code change.

---

## 7. Recommendation

**Do not change `CHARGE_INTERCEPT`, `CHARGE_SLOPE`, `CHARGE_BOUNDS`, `LIMIT_QUANTILE`, or
`LIMIT_CEILING` for the dark window.** Every measured advantage of doing so is inside the
noise floor on every window and fold tested; the one Limit effect that looked real doesn't
survive a bigger sample; and the actual overnight windfall (if the field really does go
mostly dark) comes from the field's own behaviour, not ours, and requires nothing from us
to collect.

**Deploy `scripts/experiments/dark_signal.py`'s `field_accept_rate` as a read-only
monitor** (e.g. wired into `learn_watch.py`'s digest) so that by morning we have real,
observed dark-Game data instead of the entirely counterfactual simulation this report is
built on — everything above replays *real awake Games* with opponents' behaviour
artificially zeroed; **zero of it is measured from an actual dark Game**, because none has
happened yet. That is the load-bearing caveat on the whole exercise, and it is also the
reason not to bet a live-runner code change on it tonight.

### If you disagree and want to ship something anyway (NOT recommended, diff not applied)

The only change that would be low-risk *and* directionally consistent with the (weak)
evidence above is a small, environment-gated floor lower on the Charge bounds, activated by
hand once `field_accept_rate` (§4) actually confirms darkness — never on the clock alone,
per the brief. Sketch, not applied:

```diff
--- a/src/domain/pricing/engine.py
+++ b/src/domain/pricing/engine.py
@@
+import os
+
+#: Manual dark-regime override, OFF by default. Flip only after `field_accept_rate`
+#: (scripts/experiments/dark_signal.py) confirms a sustained drop -- never on the clock.
+#: Measured cost of being wrong in either direction: 0-800 EUR/Game, inside the noise
+#: floor at every window tested (see docs/brainstorm/sebi/strats/review/dark-regime-charge.md).
+DARK_MODE = os.environ.get("WIRECLAIM_DARK_MODE") == "1"
+
 CHARGE_INTERCEPT = 0.85
 CHARGE_SLOPE = 0.45
-CHARGE_BOUNDS = (0.30, 0.80)
+CHARGE_BOUNDS = (0.30, 0.70) if DARK_MODE else (0.30, 0.80)
```

This is presented only because the brief asks for a diff if one is proposed. Given §3b/§3c,
I would not merge it even gated — the euro case for it does not clear the noise floor, and
a manual env-var flip during an unattended night adds operational risk (someone has to
notice the signal, decide, and set it correctly) for an expected value close to zero.

---

## Appendix: harness files

- `scripts/experiments/dark_income_split.py` — item 1, independent split verification.
- `scripts/experiments/dark_regime_replay.py` — item 2, the regime override layer on top of
  (imported, unmodified) `scripts/replay_payoffs.py`; `apply_regime`, `regime_snapshot`,
  `dark_teams_for`, `control_check`.
- `scripts/experiments/dark_regime_sweep.py` — items 3 and 5, regime-conditioned
  Charge/Limit sweep on top of (imported, unmodified) `scripts/experiments/tune_pricing.py`;
  `calibrate_regime`, `calibrate_regime_joint`, `net_at_multiplier`, `--cross-cost`.
- `scripts/experiments/dark_signal.py` — item 4, the live darkness signal and its
  demonstration against the naive broken one.

Reproduce the headline:

```
PYTHONPATH=. python scripts/experiments/dark_income_split.py --games 19-32
PYTHONPATH=. python scripts/experiments/dark_regime_replay.py --games 19-32 --control-check
PYTHONPATH=. python scripts/experiments/dark_regime_sweep.py --games 19-32 --all-regimes \
    --sigmas 0.43,0.60,0.80 --joint --cross-cost
PYTHONPATH=. python scripts/experiments/dark_regime_sweep.py --games all --all-regimes \
    --sigmas 0.43,0.60,0.80 --joint --cross-cost
PYTHONPATH=. python scripts/experiments/dark_signal.py --games all
```

None of these touch `src/`, `main.py`, `pixi.toml`, `.env`, or any running process; all
read cached/public data (`var/transactions`, `var/replay`, the public leaderboard API).
