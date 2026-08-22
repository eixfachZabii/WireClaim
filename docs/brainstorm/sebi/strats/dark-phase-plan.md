# The Dark Phase — a plan, not yet implemented

**Status: proposal. Nothing here is shipped.** Written at Game 42, 23:45 CEST, with the
hypothesised window opening at Game 44 (00:02:55).

---

## 0. What we actually know, including what I got wrong

I claimed earlier tonight that the Dark Window had already begun, on the strength of three
teams scoring exactly −55,267 on Game 35 and two scoring exactly −50,380 on Game 34.
Identical nets across teams **is** the arithmetic signature of `a = 0, b = 0` — a dark team's
net is `−1.5 × Σ(every fair Charge the awake field sent it)`, the same number for everyone
dark. That inference was sound. Treating two snapshots as a trend was not.

The series, measured properly (`scripts/experiments/dark_team_census.py`):

```
G1-10   13  7 13  5  5  3  5  4  3  3
G11-20   4  3  1  5  3  8  2  3  4  1
G21-30   2  1  3  2  2  1  1  7  1  1
G31-41   3  1  1  2  3  5  1  1  2  ...
```

The only changepoint is **Game 4** — teams finishing their startup. Everything since sits at
a noisy 1–3 baseline, dominated by `makalu`, dark 38 Games out of 38. A changepoint search
over Games 19–38 gives gap/spread 0.31 against a ~1 threshold.

**So the overnight window is untested, not confirmed and not falsified.** CLAUDE.md rule 9
asserts Games ~44–81 go dark; the data simply does not reach that far yet. One straw in the
wind: **`eyay` was dark on Game 39** — the first time the overall leader has submitted
nothing.

This plan is therefore written to be **triggered by measurement, not by the clock.**

---

## 1. The arithmetic, per opponent

From the payoff table. A dark opponent has `a = 0` as Issuer and `b = 0` as Reviewer.

| our position | against an awake opponent | against a **dark** opponent |
| --- | --- | --- |
| our Charge is fair (`a ≤ t`) | we collect `a` (accept or reject alike) | **we collect `a`** — unchanged |
| our Charge is an Overcharge (`a > t`) | ~17 % of the field pays | **we collect nothing** |
| their Charge arrives | we pay `a`, or `1.5a` if we wrongly reject | **nothing arrives; we pay nothing** |

Three consequences, and they are not symmetric:

1. **Fair Charge income is regime-independent.** A wrongly-rejecting Reviewer still owes the
   Issuer `a`. This is the only income that survives.
2. **Overcharge income goes to zero.** We currently derive **52 %** of Issuer income from
   accepted Overcharges (eyay 43 %, error404 34 %, TakeTheMoneyAndRun 31 %). We are the most
   exposed of the four leaders.
3. **Reviewer cost goes to zero**, and with it our single biggest competitive edge. Our
   strictness is worth **+229,600** over 40 Games (582,594 saved by rightly rejecting against
   225,630 of lawyer waste and 127,364 of fraud let through, 2.58 : 1). Against a dark field
   there is nothing to reject and that edge pays nothing.

**Net effect: our per-Game number probably rises** (costs vanish faster than Overcharge
income does) **while our position relative to the other awake teams gets worse**, because the
thing we are best at stops scoring and the thing we are worst at — pricing the expensive tail
— becomes the only thing that does.

Per-Game fair income, Games 19–32: **us 11,451 · eyay 13,840 · error404 16,120.** That is the
league table a fully dark field produces, and we are third of three.

---

## 2. What changes, what does not, and what has already been measured

| candidate | measured verdict |
| --- | --- |
| Lower the Charge multiplier (no Overcharge credit when `p → 0`) | Optimum moves **≤ 0.10 ×** of the median between awake and dark; two-sided cost of guessing wrong is **inside the noise floor** in every window. **Do not change it.** |
| Raise the Limit (surviving Issuers are the accurate teams, so `P(fair)` rises) | Real effect on a 14-Game window, **did not replicate** on 34 Games. Failed held-out check. **Do not ship.** |
| Any Limit change at all, in *full* darkness | Net is **provably flat** — 244,130 at every Limit from 0.05 to 1.50 × median. The Limit is irrelevant, not merely unhelpful. |
| The free option on uncovered items | Earns **zero** against a dark Reviewer, and costs zero. Neutral, not harmful. Leave it. |

**The honest conclusion is that almost nothing about the pricing should change.** That is not
a disappointing result, it is the result: the Dark Phase is not a different game, it is the
same game with the Reviewer column deleted. What changes is *where the leverage is*, not what
the optimal numbers are.

---

## 3. The exploit worth remembering — and exactly when it works

Recorded because it is the largest single behaviour we have observed in the field, and
because its value **inverts** with the regime.

On Game 29 Line Item 2 ("Renew the water-damaged boiler", true `t < 57`) and Game 28 Line
Item 7 ("Renew boiler system", true `t < 50`), **nine and five teams respectively Charged
exactly 2,000.00** — including `eyay` and `error404 ai`. On Game 33 item 5 and Game 41 item 3
the same round number appears again across seven teams. The field has a shared
maximum-Charge constant and points it at items it believes are uncovered.

The mechanics: on an item worth nothing, `t = 0`, so a rejected Overcharge costs the Issuer
exactly nothing and an accepted one pays in full. It is a free lottery ticket, and README R6c
says take it. Whoever's ticket lands inside a loose Reviewer's Limit gets paid; everyone
else gets zero and loses nothing.

**This is the exploit that made teams money, and it only works against a generous, awake
field.** Against a dark Reviewer every one of those 2,000 tickets is rejected and pays
nobody. So:

- **During the Dark Phase the 2,000 free-option Charge is dead money** — for us and for
  everyone. It is a third reason the old leaders' per-Game numbers went negative around
  Game 34.
- **When the field wakes at ~Game 82 it comes back to life**, and that is when to think about
  it again. The interesting question then is not whether to take the free option — we already
  do — but whether to sit *just below* the 2,000 cluster. Seven teams on one round number
  means seven tickets competing for the same loose Reviewers; a Charge at, say, 1,950 is
  inside every Limit that 2,000 is inside, plus any that sit between. **Untested. Worth a
  replay before Game 82, not before Game 44.**

---

## 4. Detection — the trigger, not the clock

Two signals, both computable from published data within one Game of the transition.

**Primary — the identical-net signature.** A dark team's net is `−1.5 × Σ(fair Charges sent
to it)`, identical for every dark team in that Game. Cross-check each candidate independently
(no Issuer rows with a non-zero amount, and every Reviewer row rejected). Already implemented
in `scripts/experiments/dark_team_census.py`.

**Secondary — `field_accept_rate`.** The accept rate among Charges *provably positive*, via
the same recovery primitive `invert_fair_values` uses. The naive "count of issuers with a
non-zero Charge" is **broken** and must not be used: it reads zero on Games 21, 22, 28 and 36
because every Line Item there had `t = 0`, not because anyone slept. Field median over 34
Games is 34.0 % (IQR 23–39 %).

**Trigger condition (proposed):** three consecutive Games with the dark count ≥ 6, *or* two
consecutive Games in which both `eyay` and `error404 ai` are dark. Below that, treat the
field as awake and change nothing.

**Deploy as a read-only monitor first.** It should print into the `pixi run watch` digest
next to the strictness line, so the transition is visible without anyone running a script.

---

## 5. The plan

### Phase A — before the trigger (now)
1. **Ship the monitor.** Dark count and `field_accept_rate` per Game, into the digest. No
   behaviour change. This is the only piece I would implement tonight.
2. **Change nothing else.** Every pricing candidate for the dark regime has been measured
   and is inside the noise floor. Acting on an untriggered hypothesis is precisely the error
   R5c prices at 60 % of net.

### Phase B — on trigger
3. **Confirm before acting.** One Game is 6,275 of noise; require the trigger above.
4. **Re-measure the four-bucket decomposition on the first two dark Games** and check the
   prediction: Overcharge income should collapse toward zero while fair income holds. If it
   does not, this whole model is wrong and Phase C is cancelled.
5. **Do not touch the Charge or the Limit.** Both are measured flat or unshippable across the
   regime boundary.

### Phase C — the only lever that pays in the dark
6. **Everything goes into the expensive tail of the estimate.** In a dark field the score is
   `Σ a·1{a ≤ t}` and nothing else, so the entire differential against the surviving awake
   teams is Fair Value accuracy — and the tail is where we are measurably worst:
   - `t̂` sits **below the proven floor `t_lo` on 73 %** of censored (expensive) items.
   - `t̂/t` runs **0.80** on unbounded brackets against **1.23** on bounded ones.
   - The estimator is shrunk toward the middle: `t̂/t` is **6.01** under 50 EUR against
     **1.17** over 1,000.
   Concretely, in priority order: (a) the corrected distribution hint shipped at Game 42
   needs its euro effect measured on fresh draws; (b) the `gpt-5.6-terra` re-test under the
   corrected prompt, with **vision** scored explicitly — Game 41's watch was a tourbillon,
   visible in `photo.jpg`, which we sent and mini priced at half; (c) Price Memory recall,
   already compounding every Game (22 % → 58 % tonight) and the one channel measured twice as
   accurate as the model.

### Phase D — standing, all night
7. **Uptime outranks everything.** Break-even uptime is 71 %; rescuing one Game is worth
   `93t` against `37t` for improving one. The supervisor is running and the blind floor is
   restored. **If we go dark we become the fountain**, paying `1.5a` to every awake team on
   every Line Item, and in a dark field the awake teams are the accurate ones — the most
   expensive possible audience.

---

## 6. What this plan deliberately does not do

- **No Charge multiplier change.** Measured ≤ 0.10 ×, inside the floor, two-sided cost
  symmetric.
- **No Limit change.** Provably flat in full darkness; the ceiling and cap changes shipped
  tonight stand on awake-field evidence and are not re-justified by this.
- **No copying of any rival.** Copying eyay's Charge ratio replays at −177,777 (14 of 14
  Games); Codacabana's at −76,577. Non Deterministic's Games 34–38 surge is 70 % one Game and
  inside its floor once dropped.
- **No clock-based switch.** Rule 9's "Games ~44–81" is an assertion the data does not yet
  support. Trigger on measurement.

---

## 7. What would change this plan

- The dark count rises past 6 and stays there → Phase B starts, and the Limit's irrelevance
  becomes worth re-testing on *real* dark Games rather than a simulation.
- Overcharge income does **not** collapse on the first dark Games → the model in §1 is wrong;
  stop and re-derive.
- `eyay` stays dark for three or more Games → the leader is asleep, our per-Game deficit to
  them inverts, and the arithmetic of catching them changes completely. **Watch this
  specifically.**
- The field wakes at ~82 with a recalibrated Limit distribution → §3's just-below-the-cluster
  question becomes live, and no measurement from tonight survives the boundary (rule 9).
