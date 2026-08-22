# WAR ROOM — the cockpit plan

> Competing pitch for QuantCo *Claim to Fame*. Angle: **human-in-the-loop as the product,
> and the pitch as a first-class deliverable instrumented from hour one.**
>
> Builds on `README.md` R1–R9. Nothing here re-derives them. Written Sat 13:40 CEST,
> **80 minutes before game 1**.

---

## 1. The bet in one paragraph

We build a **claims cockpit**: a keyboard-driven console in which one human adjudicates an
entire insurance case in under 60 seconds, correcting a machine that has already priced it —
and we let that cockpit trade 100 rounds of real money against 20-odd other teams, half of
them while we are asleep. The bet is that this wins *both* halves of QuantCo's stated
judging criterion at once. It wins the **leaderboard** half because the parts that actually
make money (never missing a game, `a = t̂`, `b = Q₁ᐟ₃`, a price memory that compounds over
100 rounds) are exactly the parts a cockpit forces you to build properly — you cannot show a
human a number you cannot justify. It wins the **style** half because slide 2 of QuantCo's
own challenge deck is a three-box pipeline whose right-hand box reads *"Human In the Loop
Workplace — Speed up humans & Feedback for AI"*, with an arrow feeding back to the left. We
are going to build that box, run it for 21 hours, and then measure — with a pre-registered
counterfactual, not a vibe — exactly how many euros the human was worth and exactly where
the human made things worse. And because the write-up is one of the two stated criteria, every artifact
the story needs is written to disk from game 1, so that at 11:50 Sunday, forty minutes after
the last game settles, the deck assembles itself with one command.

---

## 2. Why this wins — the hard-nosed judging argument

**The scoring is two-dimensional and everyone will optimise one axis.** QuantCo said it
twice: the slide has *"Your methodology also counts (style)!"* stamped diagonally across the
leaderboard screenshot, and the handout says *"We will assess your approach and look at how
well it performed."* Approach **and** performance. Most teams will treat the write-up as a
tax paid at 11:00 Sunday. A handful will treat it as the deliverable and under-build the bot.
The plan below is the only one that treats them as the *same* artifact: the cockpit is
simultaneously the thing that makes money and the thing that demos.

**Four arguments, in descending order of hard-nosedness.**

1. **The style axis is a tiebreaker among performers, so we spend on it second, not first.**
   §8 puts the cockpit behind the money pipeline in the build order and §9 kills it outright
   at 18:30 if the pipeline is not green. We are not betting UI *instead of* net. We are
   betting UI *after* net, funded by the fact that the money pipeline is genuinely small —
   fetch, decrypt, parse, one LLM call, two arithmetic rules from R4/R5b, submit twice. That
   is one developer-day, not five. The other four developer-days have to go somewhere.

2. **A cockpit is the highest-fidelity demo available and it survives the tournament ending.**
   Game 100 settles at 11:50; we pitch at 12:30. Nobody can demo a live tournament. Every
   other team will show a static leaderboard screenshot and a chart. We hand a laptop to a
   QuantCo data scientist and let them adjudicate a real case in 45 seconds, on stage, with a
   visible countdown, against ground truth we already know. That is unfakeable, it is
   interactive, and it does not care that the games are over.

3. **It is the only angle that turns "we lost" into a good talk.** If we finish 5th, a pure
   performance pitch has nothing to say. A pitch whose spine is *"the machine made ~600
   pricing decisions, a human touched 61 of them, here is what those 61 were worth and here
   are the 9 where the human was wrong"* is a talk QuantCo actually needs to hear, because
   deciding where to spend scarce human attention is literally their product problem. Slide
   2 of their deck exists because *"a lot of Claim Handlers will retire and not many young
   people choose this vocation."* You cannot hire out of that. You can only make the handler
   you still have faster. Our headline number is rank-robust.

4. **It makes us honest, which reads as senior.** The cockpit forces the machine to expose,
   per line item, a point estimate, an interval, the policy clause it matched, and a price
   build-up — because a human cannot correct a black box in four seconds. That plumbing is
   also the write-up. Calibration curves, ablations, and a confidence interval on our own
   headline claim are things a QuantCo data scientist will look for and will not find in the
   other twenty write-ups.

**What we are explicitly NOT betting on:** that a pretty UI compensates for bad net. See §9.

---

## 3. The cockpit

### 3.1 The real time budget — the human gets 30 seconds, not 60

Say this number out loud in the pitch; it is more impressive than 60 and it is true.

```
T+0.0s   case released
T+0.6s   key fetched
T+2.5s   7z decrypt + unzip done, PDF text extracted (pdfplumber)
T+3.0s   PRIOR-ONLY SUBMISSION FIRED  ← memory + heuristics, never a zero (R7)
T+3.0s   cockpit renders skeleton: item rows from PDF, prior estimates, greyed
T+8–20s  LLM returns structured judgement; rows fill in and re-sort by VOI
T+20s    ── HUMAN WINDOW OPENS ──
T+50s    auto-submit of current cockpit state, human input or not; UI locks
T+55s    read-back verify; one retry on failure
T+57s    heartbeat written; watchdog stands down
```

**Thirty seconds, four to eight line items.** ~4 s per item is not enough to think about all
of them. Therefore the cockpit's first job is not display, it is **triage**.

### 3.2 Information hierarchy — sort by money at risk, not by invoice order

Every row carries an **attention score**:

```
voi_eur(item) ≈ σ(t̂) · (1 + coverage_ambiguity) · n_opponents_equivalent
```

i.e. how many euros ride on the part we are least sure about. Rows are sorted descending and
the top row is auto-focused. Rows below a confidence floor (σ/t̂ < 10 % **and** unambiguous
coverage **and** ≥5 settled observations in memory) collapse under a single fold line —
the human is *prevented* from spending their 30 seconds on a solved item.

Only the focused row expands. Three detail lines, never more: **clause, build-up, memory.**
Those three answer the only three questions a claims handler asks — *is it covered, how did
you get that number, have we seen it before.*

### 3.3 Wireframe

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ GAME 63 · Wasserschaden Küche · 6 items    SAFE SUBMIT ✓ T+3.1s         27s ▓▓▓▓▓▓░░░│
├──────────────────────────────────────────────────────────────────────────────────────┤
│ CASE   Wasserleitung Küche geplatzt. Unterschrank + Laminat 18 m² durchnässt.        │
│ POLICY Leitungswasser ✓ · SB 150 € · Aufräumkosten ✗ nicht mitversichert             │
├──────────────────────────────────────────────────────────────────────────────────────┤
│  #  ITEM                          t̂ ± σ      a       b   CONF  WHY                   │
│ >1  Trocknungsgerät 7 Tage      210 ± 95    250     118   ▁▃    first sighting,      │
│     ! €190 at risk · coverage?                                  no comparables       │
│     ├ clause    §4.2 "Trocknung nach Leitungswasserschaden mitversichert" ✓          │
│     ├ build-up  7 Tage × 30,00 €/Tag = 210,00 netto  +19 % USt = 249,90 brutto       │
│     └ memory    0 obs · nearest "Bautrockner Miete/Tag" 3 obs, t ∈ [24, 33]          │
│                                                                                      │
│   2  Laminat entfernen 18 m²    342 ± 14    342     318   ▃▅▇   18 m² × 15,95        │
│   3  Laminat verlegen 18 m²     680 ± 22    680     642   ▃▅▇   memory 9 obs         │
│   4  Sockelleisten 25 lfm       178 ± 11    178     167   ▃▅▇   memory 4 obs         │
│   5  Unterschrank Ersatz          0          0        0   ▇▇▇   NICHT GEDECKT §2.1   │
│······ 1 row hidden (solved) ······································ press f to unfold │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ FIELD  accept-share p(a) last 5:  0.71 0.66 0.58 0.31 0.29    ! REGIME BREAK g59     │
│ MODE   NIGHT-SAFE · aggression 0.15 · width ×1.30 · coverage 68 % / 71 % realised    │
│ TOTAL  a 1450,00 €    b 1245,00 €    Δ vs machine-only   a +0    b −118              │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ j/k move   ␣ confirm   ↑↓ nudge t̂ ±10 %   x not covered   c covered   q qty          │
│ w widen (unsure)   f unfold   ⏎ submit now   ⎋ revert row   ?  why-this-number       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 The one design decision that matters: **the human edits the belief, not the price**

There is no keystroke that sets `a`. There is no keystroke that sets `b`. Ever.

The human manipulates the **posterior on `t`** — its median (`↑`/`↓`), its support (`x` / `c`
drive `t → 0` or lift it back), its inputs (`q` fixes a quantity), or its width (`w`). The
pricing layer then re-derives `a` and `b` from R1 / R4 / R5b and the current aggression dial,
and the totals row animates. This is the whole architecture in one sentence, and it has three
consequences:

- **It structurally prevents the human's worst instinct.** Loss aversion about the visible
  `1.5a` lawyer penalty makes humans set `b` too high. R4 says generosity costs up to `4t`
  and strictness costs `0.5t` — an ~8× asymmetry no human can feel in 4 seconds. So we do not
  let them feel it. They express doubt; the machine converts doubt into defence.
- **`w` (widen) is the most elegant key on the board.** Widening the posterior lowers
  `Q₁ᐟ₃` — so `b` falls sharply — while barely moving `a`, which per R5b sits at or above the
  median. One keystroke meaning *"I'm not sure"* makes us simultaneously **timid as reviewer
  and unchanged as issuer**. R6, implemented as a single key.
- **It is QuantCo's feedback arrow, literally.** The human is not correcting an output. The
  human is correcting a belief, and beliefs persist (§4.3).

### 3.5 The feedback loop closes in 12 minutes

When game *N* settles (~12.6 min later), the cockpit re-renders game *N* with the settled
truth overlaid: green where our bracket contained `t`, red where it did not, and the euros
won or lost per item. A real insurer's feedback loop closes in months. **Ours closes in 12
minutes, 100 times.** That is a pitch line and it is the reason the model gets better
overnight while nobody is watching.

---

### 3.6 What the uncertainty display is *for* — exploration pricing (R10 candidate)

The intervals on screen are not decoration; they are the input to a bandit. R5 says a rejected
inflated charge costs **exactly zero** in penalties — the only cost of charging above `t` is the
risk-free `t` we forgo *on that item, in that one game*. R9 says our **own** settlement labels
that charge fair or fraudulent for free. Put those together and a deliberately high charge on a
wide-posterior item is a **paid experiment with a known, bounded, one-round price** that returns
a hard bracket on `t` for every future game in which that item recurs.

So: for roughly games 1–30, on the single widest-posterior item per case, we price `a` at the
posterior ~65th percentile rather than the optimum and tag it `probe: true`. Per R5b the optimum
already sits at or above the median, so the forgone expectation is small; the information is not.
By game 60 the same item should be priced from five settled brackets with σ/µ under 10 %. That is
what makes `posterior_tightening.svg` an *active* result rather than a passive one.

The human's `w` (widen) key feeds this directly: pressing "I'm not sure" both lowers `b` and
**nominates the item as a probe candidate** for the next case that contains it.

> ⚠️ **Not proven — this is an R10 candidate, not an R1–R9 result.** It needs a 15-minute
> expected-value sanity check against `p(a)` before it ships, and it must be off by default in
> NIGHT-SAFE mode. If the check does not clear by 20:00 Saturday, drop it; nothing else depends
> on it.

## 4. Human / machine division of labour

### 4.1 Where the human genuinely beats the model — ranked by euros per second

1. **Coverage and relatedness.** One bit that moves `t` from 342 to 0 and `a` from 342 to 0.
   The LLM skims exclusion clauses; a human reading *"Aufräumkosten nicht mitversichert"* next
   to a line item called *"Entsorgung Bauschutt"* gets it in under a second. Highest-leverage
   keystroke in the game, which is why it has its own key (`x`) and its own flag (`! coverage?`).
2. **Quantity plausibility against the narrative and the photo.** *"18 m² room, invoice says
   180 m² of laminate."* Order-of-magnitude PDF/extraction errors are the single biggest tail
   risk on `a`, and they are trivially visible to a person and invisible to a model that is
   dutifully multiplying whatever number it was handed.
3. **Extraction-failure detection.** The PDF shows seven rows, the cockpit shows six. A human
   notices a missing or merged row instantly. The model has no way to know what it did not see.
4. **First-sighting price sanity.** For an exotic item with zero memory and a ±45 % posterior,
   a person who has ever paid a German tradesman has a real prior. This is the only case where
   the human should touch the median at all.
5. **Regime-break override.** The CUSUM detector (§5) flips us to NIGHT-SAFE automatically,
   but a human watching the field collapse at 20:00 can pull the aggression dial down one game
   earlier. Costs nothing, occasionally saves a lot.

### 4.2 Where the human must stay out — enforced in code, not in a wiki

| # | Prohibition | Why | Enforcement |
|---|---|---|---|
| H1 | Never set `b`. | R4: `b = Q₁ᐟ₃`. Humans over-set `b` because the `1.5a` penalty is salient and the `4t` exposure is not. | No keybinding exists. |
| H2 | Never raise the aggression dial. | `p(a)` is measured every 12.6 min from settled data. Human "feel" for the field is strictly worse than the CUSUM. | Dial is machine-set; human key clamps it **down** only. |
| H3 | Never do arithmetic. | quantity × unit × VAT. Humans typo under a countdown. | No free-text price field anywhere. |
| H4 | Never touch a solved row. | σ/t̂ < 10 % with ≥5 settled brackets — model is empirically better than a 4-second glance. | Row is folded; `f` to unfold logs an override-of-override. |
| H5 | Never override memory on a repeat item. | The ledger has ≥5 labelled observations; the human has one anchored memory. | Human weight in the prior blend decays to 0 as settled evidence accumulates (§4.3). |
| H6 | Never adjudicate after T+50 s. | A late edit risks the submission entirely. Uptime dominates accuracy (README §5.1). | UI locks and greys; keystrokes discarded and logged. |
| H7 | Never touch night games. | See §4.4. | Cockpit refuses input in NIGHT-SAFE mode without a two-key unlock. |

H4 and H5 are the ones that will feel wrong at 02:00 and are the ones we will be proudest of
in the write-up: **we built a UI whose main job is to stop the human from helping.**

### 4.3 How a 16:00 override reaches a 04:00 case — three channels, increasing durability

1. **Numeric — prior update.** Every belief edit writes an observation to
   `memory/item_priors.json[canonical_key]` as `{mu, sigma, n, source: "human", game, ts}`.
   The estimator blends LLM output, settled brackets, and human observations by precision.
   **Human weight decays as settled evidence arrives** — at ≥5 brackets it is zero. The
   ledger is allowed to outrank the person. This is deliberate and we say so.
2. **Symbolic — coverage rule.** An `x` pressed on coverage grounds pops a single optional
   line ("why?", 5 s, skippable, Esc to skip). If filled it appends a timestamped line to
   `memory/coverage_rules.md`, which is injected **verbatim** into the estimator's system
   prompt for every subsequent game. One line generalises across *cases and policies*, not
   just items. This is the highest-leverage channel and it is exactly *"Feedback for AI"*.
3. **Global — calibration scalar.** Aggregated `w` presses plus realised coverage from settled
   data update `memory/calib.json.width_scale`, which moves every `b` in the tournament.

And we **measure the reach**: `metrics/propagation.csv` records, per override,
`n_downstream_items_touched` and `eur_downstream`. That produces the best single sentence in
the pitch: *"one four-second keystroke at 16:12 changed 23 decisions between midnight and 6 a.m."*

### 4.4 The handover ritual — 23:20 Sat, 20 minutes, read aloud, two people

Not a review. A **drill**. One person reads the list, a second types, nobody else speaks.

1. `make replay` — re-price the last 20 settled games with the current model. Net must be
   ≥ what we actually scored. If it regressed, revert the prompt. No debate.
2. `make ablate` — the four ablations (§5.4) run clean end to end.
3. Freeze the estimator prompt. `git tag night-0`. Print the prompt hash, tape it to the monitor.
4. Set `mode = NIGHT-SAFE`: aggression ← measured `p(a)` over last 5 games, clamped to [0, 0.3];
   `width_scale` ← the value whose realised coverage is nearest target.
5. **Autopilot proof:** three consecutive live games, all hands off keyboards, verified
   submitted at both T+3 and T+50.
6. **Watchdog proof:** deliberately `kill -9` the primary mid-game. The secondary must submit.
   Do it for real, once, and watch the leaderboard confirm it.
7. **Pager proof:** trigger the alarm. Both on-call phones must scream. If a phone is on
   silent the drill fails.
8. Commit and push `memory/`. The night's learning must survive a laptop dying.
9. Two on-call names, shifts, and phone numbers on the whiteboard: **D1 23:40–03:40,
   D4 03:40–07:40.** The other three sleep, in beds, on purpose.
10. Whiteboard, in capitals: **THE ON-CALL MAY RESTART, REVERT, OR CLAMP. NOTHING ELSE.**
    Three verbs. No improvements at 03:00, however small, however obvious.

We sleep deliberately, and we say so in the pitch: *"we tested the autonomy claim by actually
going to bed."* A rested presenter at 12:30 is worth more than any tuning at 04:00.

### 4.5 Morning re-entry — 07:40 Sun, 15 minutes

Read the night's `runs/` before touching anything: uptime bar (must be 40/40), the calibration
drift, the top 5 items by posterior width, and the CUSUM trace to find the moment the field
woke up. Then and only then flip to DAY mode and re-raise aggression to measured `p(a)`.
Sunday-morning games are attended and are where the last human-delta data points come from.

---

## 5. Instrumentation for the pitch — exact artifacts

**Rule zero: `runs/` is append-only and written from game 1.** No artifact is ever
reconstructed after the fact. If it is not on disk during the tournament, it does not exist
in the pitch.

### 5.1 Per-game tree

```
runs/games/<game_id>/
  case/                 policy.txt · description.txt · invoices.pdf · images.png (decrypted)
  extract.json          {rows:[{idx,text,qty,unit,canonical_key}], pdf_text, parser, ms}
  model_v1.json         AUTONOMOUS submission — WRITTEN BEFORE ANY HUMAN INPUT  ★
  model_v2.json         post-human state (what we actually sent at T+50)
  submitted.json        both payloads, HTTP status, request/response ts, retries
  keystrokes.jsonl      {ts_rel, item_idx, key, field, before, after, focused_ms}
  settled.json          per-item outcome from the leaderboard: accepted/rejected, amount
  timeline.json         t_release t_key t_decrypt t_extract t_llm t_safe t_final t_verified
```

★ `model_v1.json` is the single most important file in the repository. It is the
**pre-registered counterfactual**: what the machine would have submitted with no human. It is
written to disk before the cockpit accepts a single keystroke, which is why the human-delta
claim in §7 Q2 is a measurement and not a story.

### 5.2 Ledger (R9 inversion) and memory

```
runs/ledger/
  t_brackets.jsonl      {game, canonical_key, t_lo, t_hi, n_obs, source: own|field}
  own_labels.jsonl      OUR charges labelled fair/fraud by our own settlements — no
                        dependence on other teams' data (see §7 Q4 fallback)
  opponents.jsonl       {game, team, item_idx, implied_b_lo, implied_b_hi}
  field_accept.jsonl    {game, a_over_t_bucket, accept_share}          → p(a) curve
  cap_obs.jsonl         {game, item, observed_c}  when amount < a, c is pinned exactly
runs/memory/
  item_priors.json      canonical_key → {mu, sigma, n, sources, last_game}
  coverage_rules.md     human-authored prompt deltas, timestamped, diffable
  calib.json            {width_scale, coverage_target, realised, per_bucket}
```

### 5.3 Metrics — one row per game, written at settlement

```
runs/metrics/
  net_by_game.csv       game, our_net, rank, field_median_net, field_best_net
  calibration.csv       game, nominal_q, empirical_coverage, n
  posterior_width.csv   game, canonical_key, sigma_over_mu
  human_delta.csv       game, item, v1_a, v1_b, v2_a, v2_b, settled_t, delta_net_eur, kind
  propagation.csv       override_id, game, n_downstream_items, eur_downstream
  uptime.csv            game, submitted, latency_ms, path(safe|final), retries
  regime.csv            game, accept_share, cusum_stat, mode, aggression
  ablation.csv          variant, replayed_net, delta_vs_actual
```

### 5.4 The four ablations — replayed post-hoc from settled data

| Variant | What it removes | The question it answers |
|---|---|---|
| A1 `honest` | issuer aggression → 0, `a = t̂` always | *"What is your net if you never charge above `t`?"* (§7 Q1) |
| A2 `naive-b` | `b = t̂` instead of `Q₁ᐟ₃` | Is R4 worth real money, or is it decoration? |
| A3 `no-memory` | LLM only, no price memory, no ledger | How much of us is the model vs. the compounding? |
| A4 `no-human` | replay `model_v1` for all 100 games | **The headline number.** |

A1 and A4 are the two that arm the hardest questions. They must exist by 09:00 Sunday.

### 5.5 The six charts — `pitch/build.py`, cron every 10 minutes from hour 3

1. `net_vs_field.svg` — cumulative net, us vs field median vs field best, with two vertical
   rules annotated *"we go autonomous 23:40"* and *"field regime break, game 59"*.
2. `posterior_tightening.svg` — median σ/µ per game, decaying. One line. "The machine learned."
3. `calibration.svg` — nominal vs empirical coverage at three snapshots (g1–20, 40–60, 80–100)
   converging on the diagonal. The R4b money chart.
4. `human_delta.svg` — cumulative € attributable to overrides, split *coverage flips* vs
   *quantity fixes* vs *median nudges*, with a bootstrap CI band. **Plotted honestly, band
   crossing zero if it crosses zero.**
5. `regime.svg` — `p(a)` over 100 games with our aggression dial overlaid.
6. `uptime.svg` — 100 bars. The most boring chart and the one we put on screen first.

**The whole point of the cron:** the deck is never more than 10 minutes stale. At 11:50 we run
`make pitch` once more and we are done at 11:53. That is what "instrumented from hour one"
actually buys — not nicer charts, but **37 minutes of rehearsal instead of 37 minutes of
matplotlib.**

### 5.6 The write-up itself

**Length: 1,200–1,800 words, 6 charts, 2 tables, one link to the raw artifacts.** Long enough
to show rigour, short enough that a judge finishes it. The maths lives in `README.md` (R1–R9)
and is *linked*, not repeated — that link is itself a signal.

```
0  Abstract — five lines, the four headline numbers, no adjectives
1  The game in one figure — payoff matrix + the two asymmetries (0.5a vs 4t; free option)
2  The result that decides everything — R1 and R4, two-line derivations, nothing more
3  The machine — architecture diagram + uptime chart (100/100)
4  The ledger — R9 inversion, posterior tightening, calibration convergence
5  The human — cockpit screenshot, the H1–H7 table, human_delta with CI,
   and a named paragraph: "where our human made it worse"
6  Ablations — the four-row table
7  What we would build with a week
8  Reproducibility — one command, plus the artifact index
```

Four things that will not appear in the other twenty write-ups and are worth more than
polish: **a negative result, a confidence interval, an ablation table, and a link to raw data.**

Written incrementally: §1–2 are copy-paste from `README.md` (do this Saturday 16:00, it costs
10 minutes); §3 at 20:00; §4–6 are *generated* by `build.py`; §7–8 at 10:30 Sunday. At no point
is more than 20 minutes of writing outstanding.

---

## 6. The 5-minute pitch script

**Format:** 5 slides + the live cockpit, one self-contained `pitch/DECK.html`. Presenter = D5.
Laptop driver = D3, already standing at the machine.

**Verified length: 655 spoken words + a 45-second silent demo clock + one 2-second pause.**
That is **4:55 at 160 wpm, 5:11 at 140 wpm** — so the script is *deliberately* ~10 s over at a
slow pace, and the two lines marked *"only if ahead of the clock"* are the release valve. Do not
add a word without deleting one. Rehearse three times **standing, out loud, with a timer**
(§8.2, 10:30–11:50); if any run exceeds 5:00, cut beat 6's optional paragraph first and beat 3's
second sentence second.

Placeholders `[…]` are filled by `make pitch`. Branch rules at §6.7.

---

### Beat 1 — 0:00 → 0:25 · Hook
*Slide 1: QuantCo's own slide-2 pipeline, redrawn, third box outlined in red.*

> "Your kickoff deck says this: *a lot of claim handlers will retire, and not many young
> people choose this vocation.*
>
> You can't hire your way out of that. You can only make the handler you still have faster.
>
> So we didn't build a bot. We built the third box on your slide two — the human-in-the-loop
> workplace — and made it trade a hundred rounds of real money."

---

### Beat 2 — 0:25 → 0:49 · The one number
*Slide 2: one line of type, nothing else.*

> "Twenty-one hours. **[600] pricing decisions** across a hundred games. A human touched
> **[61]** of them — ten percent — for a median of **four seconds each**.
>
> Those sixty-one touches were worth **[+€X]**. And we can prove it, because we wrote down
> what the machine would have done *before* the human was allowed to look."

*(Pause. Two full seconds. This is the sentence they will remember.)*

---

### Beat 3 — 0:49 → 1:29 · The maths
*Slide 3: the payoff matrix with three annotations. The slide carries the detail — speak less than it shows.*

> "Three things fall out of your payoff matrix.
>
> Below the fair value `t`, we get paid whether or not the other side accepts. No risk at all.
> So estimating `t` *is* the game.
>
> A rejected inflated charge costs exactly zero. So charging above `t` is a free option that
> pays whenever a quarter of the field accepts — and we measured that share every twelve minutes.
>
> And as the *insurer*, being generous costs eight times what being strict costs. So the right
> acceptance limit isn't our best guess at `t`. It's the **one-third quantile** of our belief."

---

### Beat 4 — 1:29 → 2:14 · The machine and the night
*Slide 4: `uptime.svg` left, `net_vs_field.svg` right.*

> "A hundred games, one every twelve and a half minutes, a sixty-second window. Forty-eight ran
> while this room was asleep.
>
> Left: **a hundred out of a hundred submitted.** Two per game — a cheap one at three seconds
> so a slow model can never cost us a round, the considered one at fifty. Doing nothing isn't
> neutral here: a team sitting at zero *pays* one and a half times every fair claim it refuses.
>
> Right: our net against the field. First line is 23:40 — full autonomy, and we went to bed. We
> tested that claim by actually sleeping. Second line is game fifty-nine: the field's acceptance
> rate fell from seventy-one percent to twenty-nine, and our aggression dial followed inside one
> round. Measured, not chosen."

---

### Beat 5 — 2:14 → 3:32 · **The live demo** (34 s speech + 45 s clock)
*No slide. Cockpit full-screen. Local. No network.*

> "Everything so far is a chart. Here's the thing itself.
>
> Real case from this tournament, model state frozen before we saw it, and we already know the
> true answer. Forty-five seconds, one of you, four keys. You don't need to know anything about
> insurance."

*(D3 hands over the laptop. If nobody moves within 4 seconds, D3's teammate — a mechanical
engineer who has never seen this case — takes it, and the presenter says: "Fine. I'll use our
own claim handler. He's never seen this case either.")*

*(45-second countdown, large, on screen. Presenter narrates keys only, never the answer.)*

> "j and k to move. Space to confirm. **x** if the policy doesn't cover it. Up and down if the
> number looks wrong. Go."

*(45 s. At zero the cockpit locks and the settled truth overlays: green rows, one red.)*

> "You flagged line five as not covered. The model had it covered — the policy excludes
> Aufräumkosten. **[€X]** on that one item, in **[four] seconds.** That's the product."

---

### Beat 6 — 3:32 → 4:20 · What the human was actually worth
*Slide 5: `human_delta.svg` with its CI band + the four-row ablation table.*

> "Now the honest version, because a number without a counterfactual is just a story.
>
> On every attended game we wrote the machine's autonomous answer to disk *before* the cockpit
> accepted a keystroke. **[N]** paired line items, **[+€X]**, confidence interval **[a, b]**.
>
> And it isn't all upside. **[9]** of the **[61]** touches lost us money — every one of them
> someone overruling a repeat item our price memory had already seen five times. So we shipped
> a lockout. The best feature in this interface is the one that stops the human from helping.
>
> Ablations, bottom table. No human: **[−€X]**. Best guess instead of the one-third quantile:
> **[−€Y]**. No price memory: **[−€Z]**."

*(Only if ≥10 s ahead of the clock, add — otherwise it is Q&A answer Q2:
"Before you raise it: not randomised. The human chose which rows to touch and our interface
sorted them, so this is an effect on the treated, not an average treatment effect.")*

---

### Beat 7 — 4:20 → 5:00 · Close
*Slide 6: their pipeline again, third box filled in, three numbers under it.*

> "One last thing, about the loop. A real insurer finds out whether a handler priced something
> correctly in months. Ours found out in **twelve minutes**, a hundred times — and every
> correction a person made didn't stay in its case. It became a prior, or a line in the model's
> prompt. One keystroke at 16:12 changed **[23]** decisions while we were asleep.
>
> That's the arrow on your slide. The one that goes backwards, from the human to the intake.
>
> It's all in the repo — every case, every keystroke, both submissions per game, and the script
> that regenerates every chart you just saw. Thank you."

---

### 6.7 Branch rules for the headline number

Pre-decided now so nobody is optimising a narrative at 11:45.

| Situation | Beat 2 headline | Beat 4 framing |
|---|---|---|
| Rank 1 | the rank, then the human number | "and here is the margin" |
| Rank 2–3 | net € and the gap to first | "here is exactly where we lost it" |
| Rank 4–8 | **the human number and 100/100 uptime** | "we finished [5th]. Here is the first thing we would fix, and we know what it is because we logged it." |
| Human delta ≈ 0 or negative | see §9 KC-6 — beat 6 becomes the spine | "we measured the human and the answer surprised us" |

Leading with a disappointing rank *before the judges find it* is a strength move with data
scientists. Never let them discover it in Q&A.

### 6.8 Demo failure modes, pre-solved

| Risk | Mitigation |
|---|---|
| No network | Replay bundle is a local JSON. The cockpit never calls out during the demo. |
| No jury volunteer | D3's teammate takes it in 4 s; the line is already written and is *better*. |
| Volunteer freezes | Presenter narrates keys only. At 15 s left: "press x on line five." Still their hands. |
| Laptop/display dies | `pitch/replay/demo_40s.mp4` — a 40-second screen capture, cued on slide 4. |
| Demo overruns | Hard 45-second visible countdown. It locks itself. That is the point. |
| Case has no teachable item | Replay case is **chosen Sunday 10:30** from the tournament for exactly one clean coverage flip. A second bundle where the human was *wrong* is loaded and ready for Q&A. |

---

## 7. Jury Q&A — the five hardest questions

Three minutes, so ~35 seconds each. First sentence answers the question. No preamble.

---

**Q1 — the uncomfortable one.** *"You deliberately charge above the fair value. In our
industry that word is 'fraud'. Why would we hire people who built a fraud bot?"*

> "Straight answer, in two halves.
>
> The game half: your matrix says that when an inflated charge is rejected, *nothing happens*.
> No fee, no penalty, no reputation. That makes overcharging a free option, and any team that
> did not take it misread the rules you wrote. That is a statement about the matrix, not about us.
>
> The job half is the one that matters. Which side of this would anyone actually pay for?
> Nobody buys a tool that inflates invoices. They buy the one that catches them. And that is
> the side we were strict about: we set the acceptance limit at the one-third quantile and we
> made it structurally impossible for a human to raise it, because a generous reviewer costs
> four times `t` and a strict one costs half. Ablation A1 — issuer aggression set to zero for
> all hundred games — nets **[€X]**, which is **[N]%** of our total. The reviewer alone is a
> product. The issuer is a correct reading of your payoff table."

---

**Q2 — the methodological one.** *"How do you know the human helped? Show me the counterfactual."*

> "`runs/games/*/model_v1.json`. On every attended game the autonomous submission is written to
> disk before the cockpit accepts a single keystroke; `model_v2.json` is what we actually sent.
> Same case, same model, same prompt — one difference. Both get scored against the settled `t`
> brackets from the leaderboard.
>
> **[N]** paired line items, effect **[+€X]**, bootstrap CI **[a, b]**.
>
> The caveat before you raise it: this is not randomised. The human chose which rows to touch,
> and our interface sorted the rows *for* them by value of information. So it is an effect on
> the treated, not an average treatment effect — it tells you what a human is worth *on the
> rows a good triage system hands them*, which is the number an insurer actually wants. To get
> a clean ATE we would randomise which flagged rows are shown; with a hundred games we did not
> have the power, and I would rather give you the honest estimand than a clean-looking one."

---

**Q3 — the technical one.** *"Your two-thirds acceptance rule assumes the charge is below the
cap. Half the field is probably charging above it. Does your rule survive?"*

> "No, and we handle it. The derivation `q > 2/3` uses `min(a,c) = a`. When the cap binds,
> accepting a fraudulent claim costs `c`, not `a`, so the condition becomes `(1−q)·c < 0.5·q·a`,
> i.e. `q > c/(c + 0.5a)` — a *higher* bar that rises with `a`. Wildly high charges are never
> worth accepting, which is exactly right.
>
> We implement `b` as the minimum of the one-third quantile and that cap-aware bound, plus a
> hard rule: any charge above roughly four times our median estimate is rejected outright
> regardless of the posterior. And we do not have to guess `c`. We detect it as a **plateau**:
> once several teams' *accepted* amounts on the same line item pile up at an identical value,
> that value is the cap — because everyone above it is paid `min(a,c)`. That pins `c` exactly,
> and since `c ≥ 4t` it hands us a free *upper* bound on `t` as well, bracketing it from both
> sides. Somebody overshoots almost every round. `runs/ledger/cap_obs.jsonl`."

---

**Q4 — the fair-play one.** *"Reconstructing `t` and other teams' limits from the leaderboard —
isn't that the 'extract the secret thresholds' your rules forbid?"*

> "We asked you. `#ask-orgateam`, **[Saturday HH:MM]**, before we built it — the answer is
> **[quoted]**. Our reasoning was: the Transactions view is published, settled, post-hoc and
> visible to every team equally. It is the equivalent of an insurer learning from its own
> closed claims. We never pre-fetched a key, never read an unsettled game, never touched a
> submission before it settled.
>
> And the fallback was built first, not second. **Our own transactions label our own charges
> with no reference to anyone else**: if we charged `a`, were rejected, and still received `a`,
> then `a ≤ t`; if we received nothing, `a > t`. That is a free label on every line item we
> issue, every round, from our own data alone. Ablation A3 with `--no-leaderboard` runs on that
> signal only and nets **[€Z]** — [N]% of our result. We would have been fine either way."

---

**Q5 — the sceptical one.** *"If your posterior is calibrated, the human is noise. Isn't the
cockpit just theatre?"*

> "It would be, if the human saw every row. Calibration is a claim about the average and the
> money is in the tail. Our σ/µ is about **[8]%** on items the ledger has seen five times and
> about **[55]%** on first sightings — and the queue is sorted so the human only ever reaches
> the second kind. On solved rows we do not let them in at all; we measured that those edits
> were net-negative and we shipped a lockout at **[21:40]**.
>
> And the corrections are not consumed as one-offs. They become priors and prompt lines, so
> they fire on cases the person never saw — `propagation.csv` says one keystroke at 16:12
> touched **[23]** later decisions overnight. That is the difference between a human *in* the
> loop and a human *doing* the loop. The first scales. The second is the thing your slide says
> is retiring."

---

**Also loaded, one-liners ready:** *biggest single loss and why* (have the game number and the
row); *what a week buys* (randomised triage for a clean ATE; a second model for disagreement-
based routing; item-key embedding instead of a controlled vocabulary); *how much is the LLM vs
the lookup table* (A3); *what happens with 10,000 claims a day* (the queue is already a
priority queue on expected euros — the only change is that the fold threshold becomes a
staffing parameter).

---

## 8. Architecture and the 24-hour build plan

### 8.1 Architecture — one process, five packages

Python throughout (matches the starter script and `pixi.toml`; no time for a second toolchain).

```
wireclaim/
  rails/      scheduler (absolute wall-clock from /games, never sleep-drift) · key fetch ·
              download · 7z decrypt · submit(×2, idempotent) · read-back verify · watchdog
  brain/      extract.py  PDF → rows (pdfplumber, LLM fallback on parse failure)
              estimate.py one structured LLM call → {covered, t_p10, t_p50, t_p90,
                          clause_quote, one_line_reason, canonical_key}
              memory.py   canonical_key blending: LLM ⊕ settled brackets ⊕ human obs
              price.py    posterior → (a, b) via R1 / R4 / R5b + aggression + cap bound
  ledger/     leaderboard poller · R9 inversion · own-label extraction · opponent b ·
              p(a) estimation · CUSUM regime detector
  cockpit/    FastAPI + ONE static HTML page over a websocket. Server pushes state, browser
              sends keystrokes. Monospace, no framework, no build step, works offline. ~400 LOC.
  pitch/      build.py → 6 SVGs + WRITEUP.md assembly + replay bundle export
```

**Deliberate call: no React.** A websocket plus one HTML file is ~2 hours. A React app is ~6.
We are buying 4 hours of tournament time, and the terminal aesthetic is *better* for this demo.

**`canonical_key`:** the estimator returns a key from a controlled vocabulary we grow —
"pick from this list, or propose a new one". Cheap, inspectable, self-organising, no embeddings.

**Watchdog:** a second process on a **second laptop, second network** (phone hotspot). Reads a
heartbeat from a shared private gist via `gh`. If no heartbeat for game *N* by T+55, it submits
a memory-only payload and fires a repeating audio alarm plus a Discord DM. Double submission is
harmless (later overwrites earlier). Proven by drill at 23:20 (§4.4 step 6).

### 8.2 Hour by hour · D1 Rails · D2 Brain · D3 Cockpit · D4 Ledger · D5 Story+float

| Time | Phase | D1 | D2 | D3 | D4 | D5 |
|---|---|---|---|---|---|---|
| 13:30–14:00 | **P0 procure** | **register at desk → API key**; ask orgateam re R9 | pull case folder, run starter on case 0 | `pixi install`, `brew install p7zip` on all 5 machines | scrape `/games` → full 100-game schedule to disk | repo skeleton, `runs/` tree, `make` targets |
| 14:00–15:00 | P0 | scheduler + key fetch + decrypt + **constant submitter** | PDF → rows on case 0 | ehl.gg challenge selection; **Entire gate confirmed** | leaderboard client, Transactions parse | READMEs §1–2 → `WRITEUP.md` (copy, 10 min) |
| **15:00** | ▶ **GAME 1 — 15:00:00 CEST** | — | — | — | — | — |
| 15:00–17:30 | **P1 money** | double-submit T+3/T+50, read-back verify, `uptime.csv` | estimator prompt v1, structured output, `price.py` R1/R4/R5b | join Brain — extraction hardening (this is the risk) | R9 inversion + **own-label** extraction | `build.py` v1: uptime + net charts; cron armed |
| 17:30–18:30 | P1 | watchdog process on laptop 2 | memory.py + canonical_key vocab | cockpit read-only view over websocket | `t_brackets.jsonl` live; first `p(a)` estimate | `model_v1.json` write-before-human wired ★ |
| **18:30** | **KC-1 GATE** | *3 consecutive green games or the cockpit dies* | | | | |
| 18:30–20:30 | **P2 human** | resilience: retries, clock skew, disk, OOM | posterior blending, calib.json | **cockpit v1: j/k, ␣, x, ↑↓, w, ⏎** | opponent-b reconstruction | keystroke logging + `human_delta.csv` |
| **20:30** | **KC-2 GATE** | *cockpit usable on a live game, or ship read-only + `x` only* | | | | |
| 20:30–22:00 | P2 | — | quantity `q` key + re-derivation | VOI sort, fold, settled-overlay replay | CUSUM regime detector + aggression dial | first human-delta read; `propagation.csv` |
| 22:00–23:00 | **P3 harden** | night-safe mode, pager, alarm | prompt freeze candidate; `make replay` | H4/H5 lockouts (**the anti-help features**) | `make ablate` A1–A4 | deck skeleton `DECK.html`, beats 1–4 |
| **23:00** | **KC-3 GATE** | *below field median → all UI frozen; the two on-call shifts become **working** shifts (the other three still sleep — KC-3 does not cancel §4.4)* | | | | |
| 23:00–23:20 | P3 | — | — | — | — | — |
| **23:20–23:40** | **HANDOVER DRILL** (§4.4, all five, read aloud, kill -9 for real) | | | | | |
| 23:40–03:40 | **P4 night** | **on-call** (restart · revert · clamp) | sleep | sleep | sleep | sleep |
| 03:40–07:40 | P4 night | sleep | sleep | sleep | **on-call** | sleep |
| 07:40–08:00 | **P5 re-entry** | 15-min read of the night (§4.5), then DAY mode | | | | |
| 08:00–10:30 | P5 | uptime audit 100/100 | prompt tune **only if `make replay` proves it** | cockpit polish for demo; replay bundle export | run A1–A4 for real; final calibration | beats 5–7, charts final, **3 rehearsals** |
| **10:30** | **KC-5 HARD FREEZE** | *no merges. none. including one-liners.* | | | | |
| 10:30–11:50 | **P6 pitch** | one attendant on the last games, everyone else off code | rehearse | rehearse, **owns the laptop in the demo** | fill every `[…]` placeholder | rehearse ×3 with a timer, out loud, standing |
| **11:50** | ■ **GAME 100 SETTLES** | | | | | |
| 11:50–12:00 | P7 | `make pitch` (≤3 min) · **submit on ehl.gg by 12:00** | | | | |
| 12:00–12:30 | P7 | lunch, one final run-through, walk to stage | | | | |
| **12:30** | ★ **PITCH** | | | | | |

### 8.3 The three things that must be true by 15:00 today

1. An API key exists. *(Blocking everything. D1 walks to the desk at 13:35, not 14:00.)*
2. A process submits a non-zero payload for game 1, even if the numbers are guesses (R7).
3. `runs/games/1/` exists on disk. **Instrumentation starts at game 1 or the pitch has a hole in it.**

---

## 9. Kill criteria and the honest downside

### 9.1 The honest downside, stated plainly

**This plan can lose by being right about the wrong half.** Leaderboard performance is the
objective, unarguable half of the score, and a jury looking at a beautiful cockpit above an
8th-place net will conclude — correctly — that we optimised the part that is easier to fake.
"Style" is a tiebreaker among teams that performed; it is not a substitute for performing.
Every gate in §9.2 exists to enforce that ordering, and three of them kill the cockpit.

Three further honest risks:

- **The human-delta may be zero.** With ~60 attended games and maybe 60 touched line items,
  the CI could easily straddle zero. If we let ourselves need a positive number, we will
  torture the analysis. So: §9.2 KC-6 pre-commits the alternative pitch **now**, while nobody
  knows the answer.
- **The demo depends on a stranger and a laptop.** §6.8 pre-solves six failure modes, and the
  fallback video means the worst case costs 20 seconds, not the pitch.
- **Cockpit development competes with sleep, and a tired presenter at 12:30 costs more than a
  tuned prompt at 04:00.** Hence the mandatory sleep schedule in §4.4 — it is a strategic
  choice, not a comfort.

### 9.2 Kill criteria — thresholds and clocks, decided now

| ID | When | Condition | Action — no discussion, no vote |
|---|---|---|---|
| **KC-1** | 18:30 Sat | Pipeline (decrypt→extract→price→submit×2) not green on **3 consecutive live games** | **Cockpit cancelled entirely.** D3 → rails. Pitch pivots to the maths + the ledger. |
| **KC-2** | 20:30 Sat | Cockpit not usable end-to-end on one live game | Ship **read-only viewer + the `x` key only**. 45 minutes, then stop. A one-key cockpit is still a real demo. |
| **KC-3** | 23:00 Sat | Our net below **field median** | Freeze all UI. The two on-call shifts become **working** shifts on estimation accuracy. The other three still sleep — a rested presenter still outranks a tuned prompt. Rank is the objective half. |
| **KC-4** | any time | Any game missed | **Everything stops.** Nothing else is worked on until the watchdog is proven on 3 consecutive games. |
| **KC-5** | 10:30 Sun | — | **Hard code freeze.** Unmerged branches die. Including one-line fixes. Especially those. |
| **KC-6** | 11:00 Sun | Human-delta CI straddles zero, or is negative | **Do not fake it.** Beat 6 becomes the spine: *"we measured where a human is and is not worth four seconds, and here is the rule we shipped because of it."* Pre-written, in the deck, today. |
| **KC-7** | 10:30 Sun | No replay case with a clean teachable moment | Demo runs on the *chosen* case where the human was **wrong**, framed as *"here is what the lockout rule was built from."* Still live, still unfakeable, arguably better. |

### 9.3 The one-line test for every hour of the next 21

> *Does this line of code change what we submit, or what we can prove at 12:30?*

If neither, do not write it.
