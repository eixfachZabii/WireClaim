# strat-ops — *Reliability is the strategy*

> A competing pitch for the QuantCo **Claim to Fame** game plan.
> Builds on the README's R1–R9; does not re-derive them.
> Status: proposal. Owner: unassigned. Written before procurement.

---

## 1. The bet in one paragraph

We bet that this tournament is decided by **how many of the 100 games we submit a
sane answer to**, not by how good the answer is. The reasoning is R7 plus a clock:
`a = 0` forfeits *all* issuer income while `b = 0` still pays `1.5a` to every
opponent on every line item, so a missed game is not a zero — it is the single
worst score available in the game, and roughly half the tournament runs while five
humans are asleep. So we build the machine first and the model second: a scheduler
that never misses a start, a **two-phase submit** that puts a cheap, LLM-free
answer on file at T+3 s and overwrites it with the considered answer at T+50 s, and
a **fallback ladder** where every conceivable failure — dead key endpoint, missing
`7z`, unparseable PDF, rate-limited model, sleeping laptop, drifting clock — has a
named degradation that still ends in a submission with `a > 0`. The arithmetic in
§2 says the cheap path alone captures **~71 %** of everything on the table and that
a brilliant bot needs **≥71 % uptime just to draw** with a dumb one. Modelling is
the remaining 29 %, and we spend the whole Sunday morning on it — from a position
where we have 50 settled games of data because we did not miss any.

---

## 2. Why this wins — the arithmetic

### 2.1 The model

All figures in units of `t` (the secret fair value of one line item), per line
item, per game. Assumptions, all stated so they can be attacked:

| Parameter | Value | Note |
| --- | --- | --- |
| Opponents `M−1` | 19 | field size unknown; **result is exactly invariant** (§2.4) |
| Line items per case `L` | 8 | unknown; **result is exactly invariant** (§2.4) |
| Fraction of field charging in the fair zone `f` | 0.8 | swept 0.5–1.0 |
| Field's charge distribution | lognormal, median `0.85t`, log-sd `0.35` | swept |
| Our posterior on `t` | lognormal, correctly centred, log-sd `σ` | |
| "smart" path | `σ = 0.2` | LLM + policy + price memory |
| "cheap" path | `σ = 0.6` | regex + seed table + priors, **no LLM** |

Our issuer charge is `a* = argmax a·P(t ≥ a)` (R5b, fair-zone term only — this is
*conservative*, it discards R5's free-option upside). Our acceptance limit is
`b = Q₁ᐟ₃` of the same posterior (R4).

### 2.2 The three worlds

| | charge `a` | limit `b` | income /opp | cost /fair opp | **net /line item** |
| --- | --- | --- | --- | --- | --- |
| **SMART** `σ=0.2` | `0.78t` | `0.92t` | `0.697t` | `1.153t` | **`−4.30`** |
| **CHEAP** `σ=0.6` | `0.82t` | `0.77t` | `0.516t` | `1.235t` | **`−8.97`** |
| **DEFAULT** (miss) | `0` | `0` | `0` | `1.356t` | **`−20.60`** |

All three are negative because the game is negative-sum (R2). Rank is relative;
what matters is the *gaps*.

```
        DEFAULT              CHEAP                          SMART
        −20.60 ──── +11.63 ──── −8.97 ──────── +4.67 ──────── −4.30
                     71.4 %                     28.6 %
                └── bought by a 60-line ──┘  └── bought by 5 devs, ──┘
                    offline function            an LLM, and 21 hours
```

**Showing up with a crude number is worth 2.5× as much as being right.**

The asymmetry has a structural cause, not a numerical one. `b = 0` is bounded
damage — a 50 % surcharge on fair claims, and it correctly rejects every fraud
(R7). `a = 0` is *unbounded* damage: it forfeits `19 × 0.7t = 13.2t` of income that
was **risk-free** (R1 — below `t` we are paid whether or not they accept). Of the
`16.31` total swing between DEFAULT and SMART, `13.23` (**81 %**) lives in the
income column, and every euro of it is unlocked by `a` merely being a plausible
non-zero number.

### 2.3 The two decision-relevant numbers

```
value of RESCUING one game  (DEFAULT → CHEAP, 8 items):   93 t
value of UPGRADING one game (CHEAP  → SMART, 8 items):    37 t
```

Everything follows:

- **Break-even uptime = 71.4 %.** An all-or-nothing smart bot must submit on
  ≥71 % of games merely to *tie* a cheap bot that never misses.
  `u·(−4.30) + (1−u)·(−20.60) = −8.97 ⟹ u = 0.714`.
- **One 5-hour overnight outage (23.8 games) costs `3 105 t`.** The *entire*
  value of tripling our estimation accuracy (σ 0.6 → 0.2) across all 100 games is
  `3 736 t`. **One lid closing at 02:40 burns 83 % of everything the modelling
  team can possibly achieve** — and unlike the modelling, it is a likely event.
- **The two-phase submit is worth more than 5 points of uptime.** Tournament
  totals over 800 item-games:

| Architecture | Total (t) |
| --- | --- |
| never submit | `−16 483` |
| cheap-only, 100 % uptime | `−7 173` |
| all-or-nothing smart, 85 % uptime | `−5 394` |
| all-or-nothing smart, 95 % uptime | `−4 089` |
| **two-phase, smart path succeeds 90 %** | **`−3 810`** |
| two-phase, smart path succeeds 100 % (unreachable) | `−3 437` |

  Two-phase at 90 % smart-success **beats all-or-nothing at 95 % uptime**. And the
  gap from two-phase@90 % to theoretical perfection is only `374 t` — one tenth of
  what the architecture itself buys. *The last 10 % of model reliability is worth
  a fifteenth of the first 71 % of submission reliability.*

### 2.4 Why you cannot argue with the 71 %

Both the income and the cost columns scale **exactly linearly** in `M−1` and in
`L`. They cancel in the ratio. So the recovery fraction — and therefore the
break-even uptime — is *algebraically invariant* to field size and invoice length,
the two parameters we know least about.

The remaining free parameters were swept: field charge median `∈ {0.7, 0.85, 1.0}·t`,
field log-sd `∈ {0.25, 0.35, 0.5}`, `f ∈ {0.5, 0.8, 1.0}`, `M−1 ∈ {5, 19, 39}` —
81 scenarios.

```
recovery fraction:  min 67.7 %   median 72.4 %   max 74.1 %
```

The number is ~71 % under every plausible parameterisation of this game.

### 2.5 A bonus that makes the case stronger than stated

Expected issuer income is remarkably **flat in `σ`**:

| `σ` | 0.2 | 0.4 | 0.6 | 0.8 | 1.0 | 1.2 |
| --- | --- | --- | --- | --- | --- | --- |
| optimal `a` | `0.78t` | `0.75t` | `0.82t` | `1.00t` | `1.35t` | `2.01t` |
| `E[income]/opp` | `0.697t` | `0.573t` | `0.516t` | `0.500t` | `0.516t` | `0.564t` |

Income bottoms out at `σ ≈ 0.8` and then *rises*, because R5 makes a failed
overcharge free, so extreme uncertainty is best answered by taking the free option.
A near-blind but honestly-wide posterior still earns ~72 % of what a sharp one
earns. **Caveat, stated because it cuts both ways:** this leans on the lognormal's
right tail and on R5 holding exactly; a bounded posterior would make income more
`σ`-sensitive. We therefore keep the headline number at the conservative 71 % and
treat this as upside, not as licence to skip the modelling.

### 2.6 What this plan is *not* claiming

It is not claiming estimation does not matter. `37 t` per upgraded game × 100 games
is `3 736 t` and that is real money — it is simply *second* in the ordering, and it
is worth strictly more once uptime is solved, because you cannot calibrate a
posterior (R4b, R9) on games you did not play. Reliability is not the opposite of
modelling here; it is the **input** to it.

---

## 3. The submission state machine

### 3.0 The unlock: the hot path has almost no network in it

Re-read the handout: *"we will provide a link to a folder. The folder will contain
a number of encrypted `.zip` files, **one for each case**."* The archives are
published **in advance**; only the *key* is released at T0. Pre-staging them is
explicitly not the forbidden "obtain decryption keys before a case is released" —
we are downloading files they handed us, and we still cannot open one until T0.

So a **prefetch daemon** syncs that folder every 60 s and keeps every archive on
local disk with a recorded checksum. The critical path at T0 collapses to:

```
1 × GET (key)  →  local decrypt  →  local parse  →  1 × POST (submit)
```

Two network round-trips instead of three-plus-a-large-download. This single
decision removes the entire "zip download is slow / folder link died / we are on
hotel wifi" failure class and pulls the cheap submission from ~T+5 s to ~T+3 s.
**Cost: ~15 minutes of work. Value: an entire rung of the ladder deleted.**

### 3.1 Timeline of one game

`T0` = authoritative game start (§5.2). Window closes at `T0+60`.

| Time | Phase | Action | Fails how |
| --- | --- | --- | --- |
| `T0−120` | **PREFLIGHT** | fork a fresh worker subprocess; verify archive present + checksum; open keep-alive conns to API host and LLM host; resolve DNS; check disk; load price memory into RAM; assert clock offset < 2 s | anything → WARN, continue |
| `T0−30` | **WARM** | 1-token ping to the LLM provider; if 401/429/quota → flip `cheap_only` and WARN **now**, 30 s before it matters | — |
| `T0−3 → T0+3` | **KEY** | poll key endpoint: 1 s cadence until `T0−0.5`, then 250 ms; stop on first 200; hard cap **20 requests/game** | → rung F1 |
| `T0+0.5 → T0+2` | **OPEN** | `7z x -p<key>` on the local archive → tmpfs; fallback `pyzipper` | → rung F3 |
| `T0+1 → T0+2.5` | **PARSE** | PDF → `LineItem[]`; read `policy.txt`, `description.txt` | → rung F4 |
| `T0+2.5` | **CHEAP** | `price_cheap()` — pure, offline, total, deterministic, **cannot raise** | cannot |
| **`T0+3`** | **SUBMIT #1** | airlock → POST tier 1. Hedged: if no response by `+1.5 s`, fire a second identical POST | → retry to `T0+20` |
| `T0+3 → T0+43` | **SMART** | one batched streaming LLM call over the whole invoice, emitting **JSONL, one object per line item, in index order** | partial is fine |
| `T0+43` | **WATCHDOG** | an OS thread (not an asyncio task) fires unconditionally; cancels the LLM stream; assembles best-available | cannot |
| `T0+45` | **MERGE** | per-line-item merge of smart over cheap, then airlock | cannot |
| **`T0+50`** | **SUBMIT #2** | POST tier 3 — **only if tier strictly increased** | → tier-1 stands |
| `T0+55` | **VERIFY** | read our submission back; if any `a == 0` or item count wrong → emergency re-POST the cheap payload | PAGE |
| `T0+90` | **LEARN** | scrape the previous game's settled transactions, invert to `t` brackets (R9), update memory. **Off the hot path, in a different process, allowed to fail.** | INFO |

Two properties make this work and both are non-negotiable:

1. **The cheap path never touches the network, never calls a model, and is a total
   function.** Its type is `(LineItem[], Memory, Priors) → Quote[]` with no
   `Result`, no `Optional`, no exceptions. A property test asserts
   `∀ input (including []): every a > 0 ∧ 0 ≤ b ≤ a`.
2. **The merge is per-line-item, not all-or-nothing.** This is the answer to "what
   if the good path is half done".

### 3.2 What the cheap path actually computes (no LLM, < 50 ms)

A four-rung lookup per line item, first hit wins:

1. **Exact memory hit** — normalised description (lowercase, strip punctuation,
   collapse whitespace, strip quantities/units) hashed against the SQLite price
   memory built from settled leaderboard rounds (R9). By Sunday morning this
   should be the dominant path on repeated trades.
2. **Fuzzy memory hit** — trigram / token-set similarity ≥ 0.75 against known
   descriptions, scaled by quantity ratio.
3. **Seed price table** — a static CSV of ~300 German trade line items
   (Arbeitsstunde Maler / Elektriker / KFZ-Mechatroniker, Windschutzscheibe,
   Trocknungsgerät pro Tag, Entsorgungspauschale, Anfahrtspauschale, …) with a
   plausible unit price and a log-sd. **Built by a human + an LLM on Saturday
   afternoon, offline.** This is a *pre-computed asset*, not a runtime call, which
   is exactly why it survives every runtime failure.
4. **Category prior** — classify to {labour, part, material, disposal, travel,
   fee} by keyword; use the running median unit price of that category from
   memory, × quantity.
5. **Global prior** — the running median `t` over every line item we have ever
   observed. Fires when we know literally nothing.

Then, uniformly: `a = m·exp(−k·σ)` and `b = m·exp(−0.4307·σ)` with the rung's `σ`
(rung 1: 0.15 → rung 5: 1.0). Wider posterior on lower rungs is not a hedge, it is
the *correct* representation of our ignorance, and §2.5 says it is nearly free.

### 3.3 The airlock — every submission passes through one function

`airlock(cheap, smart?, case) → Payload` is the highest-value 200 lines in the
repo. It is pure and it is the only code path that can produce a POST body.

1. **Shape** — one `(a, b)` per parsed line item, indices contiguous from 0,
   count matches the parse. Payload carries `game_id`; assert it equals the game
   we are currently in. *(Pre-staged archives make submitting the wrong game's
   answer a real risk. This assert is the guard.)*
2. **`a` sanity** — finite, `> 0`, `< 100 ×` the category prior. Catches the model
   returning `1e9`, `null`, `"n/a"`, or a negative.
3. **`b` sanity** — finite, `≥ 0`, and **`b ≤ a`** (R6: aggressive as issuer, timid
   as reviewer, *from one belief*). If the model returns `b > a`, it has misread
   the game; clamp and WARN.
4. **Gross-total normalisation.** The handout warns about this twice and it is the
   most likely systematic error in the entire tournament: a team that submits net
   or per-unit is wrong by 19 % or by `quantity×` on **every line item, forever**,
   which dwarfs any modelling refinement. So we never ask the model for a total.
   We ask for `{index, quantity, unit_price_net, vat_rate}` and **compute
   `a = quantity × unit_price_net × (1 + vat)` ourselves**, with `vat` read from
   the invoice (`inkl./zzgl. MwSt`, default 0.19). Deterministic arithmetic beats
   an LLM's arithmetic every time.
5. **Divergence veto** — if smart is `> 20×` or `< 1/20 ×` cheap on any item, use
   cheap for that item and log LOUDLY. Band chosen wide enough to never veto a
   correct-but-surprising answer, narrow enough to catch a unit-confusion bug.
6. **Coverage** — if the model says an item is not covered by the policy (`t = 0`),
   we still submit `a > 0` (R5: a rejected fraudulent charge costs exactly zero,
   so charging is a free option) and `b = 0` (we will not pay for it).

### 3.4 Ordering, idempotency, and never overwriting good with bad

Later submissions overwrite earlier ones, so ordering is a correctness property.

- Every payload carries `(game_id, tier, seq)` with
  `tier ∈ {0 blind, 1 cheap, 2 partial, 3 smart}`.
- The submitter holds a mutex and a monotonic `last_sent_tier` per game. It
  **refuses to POST a tier ≤ the highest already successfully sent.** A retry of
  submit #1 that is still in flight at `T0+50` is cancelled the moment submit #2
  starts.
- Payloads are complete, never patches — so a duplicate POST is harmless and
  retries need no idempotency key.
- If the smart path fails entirely, **we do not re-POST cheap at `T0+50`.** The
  tier-1 submission is already on file. Silence is correct.

---

## 4. The fallback ladder

### 4.0 The four rungs and what each costs

Cost is measured **against the SMART baseline**, in `t`, per line item and per
game (8 items). These are the only four outcomes the system is allowed to produce.

| Rung | What it is | net /item | **cost /item** | **cost /game** |
| --- | --- | --- | --- | --- |
| **T3 SMART** | LLM priced every item | `−4.30` | `0` | `0` |
| **T2 PARTIAL** | some items smart, rest cheap | `−4.3…−9.0` | `0–4.67` | `0–37` |
| **T1 CHEAP** | offline pricing, full item list | `−8.97` | `4.67` | `37` |
| **T0 BLIND** | never opened the case; priors × guessed item count | `≈ −11.1` | `6.76` | `54` |
| ~~DEFAULT~~ | **no submission — forbidden outcome** | `−20.60` | `16.30` | `130` |

The design goal is stated as one invariant:

> **For every game, the system emits a payload with `a > 0` on every line item, or
> it has a bug.** DEFAULT is not a fallback; it is an incident.

**The blind rung is worth building.** 30 lines of code recovering `76 t` per
otherwise-lost game. It needs one thing we do not yet know: does the API accept a
submission with *more* line-item indices than the case has? If it ignores extras,
BLIND always over-submits (e.g. 20 indices) and is nearly as good as CHEAP. If it
400s, BLIND uses the modal item count seen so far. **This is a 10-minute
experiment against case 0 on Saturday afternoon and it should be near the top of
the list.**

### 4.1 Every failure, its degradation, its cost

| # | Failure | Detection | Degradation ladder | Lands on | Cost/game |
| --- | --- | --- | --- | --- | --- |
| F1 | **Key endpoint 500 / times out** | non-200 or > 2 s | retry jittered 0.25/0.5/1/2/4 s to `T0+30` → ask peer instances via shared key cache (first instance to get a key publishes it) → BLIND | T0 | `54` |
| F2 | **Key endpoint 404 past `T0+3`** (release lag) | 404 | keep polling to `T0+30` at 1 s; the window is 60 s, a 10 s release lag still leaves the smart path alive | T3/T1 | `0–37` |
| F3 | **`7z` missing / decrypt fails** | non-zero exit | `7z` → `pyzipper` (pure Python AES) → re-fetch archive once against stored checksum → BLIND. *Two independent decrypt implementations means "7z not on PATH" is not a failure mode at all* | T1 | `37` |
| F4 | **PDF unparseable** | 0 items extracted | `pdfplumber` → `pypdf` → `pdftotext -layout` → render page to PNG + LLM vision (smart path only, +8 s) → regex any text for an item count → BLIND | T1/T0 | `37–54` |
| F5 | **Item count ambiguous** | parsers disagree | take the **max** count; extra indices priced from the category prior. Over-submitting costs a wrong price; under-submitting costs a `−20.60` DEFAULT on the missing items | T2 | `~10` |
| F6 | **LLM 429 rate-limited** | HTTP 429 | retry once on the **second provider key** (round-robin, funded separately) → smaller/faster model → CHEAP | T3/T1 | `0–37` |
| F7 | **LLM timeout / slow** | watchdog at `T0+43` | JSONL streaming means every item that already arrived is kept; the tail falls back to cheap | T2 | `0–37` |
| F8 | **LLM refuses** ("I can't help price fraudulent…") | no JSON in output | reframe prompt as *fair-market claims assessment* and retry once (budget 8 s) → CHEAP. **Prevention: the production prompt never uses the words fraud/overcharge/inflate.** It asks for a fair market valuation and a coverage decision; the *aggression* is applied by our own code afterwards, from the posterior | T3/T1 | `0–37` |
| F9 | **LLM malformed JSON** | parse error | JSONL is naturally tolerant — parse line-wise, drop bad lines, keep good ones → airlock → merge | T2 | `~5` |
| F10 | **Model hallucinates absurd prices** | airlock rules 2/5 | clamp / veto per item, fall back to cheap for that item only | T2 | `~5` |
| F11 | **Network partition (our side)** | POST fails | hedged POST → retry to `T0+55` → the redundant instance on a different network submits | T1–T3 | `0–130` |
| F12 | **Laptop sleeps** | heartbeat gap | *eliminated by not running on a laptop* (§5). If we must: `caffeinate -dimsu`, mains power, Power Nap off, lid open. **A 5 h sleep costs `3 105 t`** | DEFAULT | `130 × n` |
| F13 | **Process crash / OOM / unhandled exception** | supervisor | per-game work runs in a **forked worker subprocess**; a crash kills one game, not the scheduler. `systemd Restart=always RestartSec=2`. All state in SQLite so a restart resumes mid-tournament | T0/T1 | `≤ 130` |
| F14 | **Scheduler itself dies** | external watchdog | second instance takes the lease after 1 missed heartbeat; GitHub Actions cron (5 min) independently checks "was there a submission in the last 13 min?" and pages if not | T1–T3 | `≤ 260` |
| F15 | **Clock drift / VM time jump** | server-`Date` offset > 2 s | schedule against `local + median_offset` (§5.2), never bare local time; `chrony`; PAGE above 5 s | — | `0` |
| F16 | **Wrong game's answer submitted** | airlock rule 1 | `game_id` assert; refuse and re-derive | — | `0` |
| F17 | **Two instances submit different answers** | — | tier discipline + timing stagger (§5.4) | — | `~0` |
| F18 | **LLM credits exhausted at 03:00** | `insufficient_quota` | flip global `cheap_only`, **WARN not PAGE** — a 29 % degradation is not worth waking a human for — top up at 07:00 | T1 | `37 × n` |
| F19 | **Disk full** (100 archives + extracts + logs) | < 2 GB | extracts go to tmpfs and are wiped per game; logs rotate at 50 MB; WARN at 2 GB, auto-purge extracts at 500 MB | — | `0` |
| F20 | **A human deploys broken code at 02:00** | — | **deploy freeze 01:00–07:00** (§7). Outside the freeze, a deploy must pass a replay test on case 0 + the last 5 real cases, and is refused within 4 min of a game start | — | `0` |
| F21 | **Everything is broken and nobody knows why** | despair | **`panic.py`** — one file, stdlib only, ~150 lines, zero third-party imports: schedule → key → `7z` → regex item count → global prior → POST. Lives in every dev's home directory. Deliberately duplicates logic and deliberately imports nothing from the rest of the repo | T0/T1 | `37–54` |

### 4.2 The three defences that do the most work

Ranked by cost avoided per line of code:

1. **The two-phase submit (~40 lines).** Converts every smart-path failure from
   `−130 t/game` into `−37 t/game`. If it rescues 15 games over the tournament
   that is `1 397 t` — 37 % of the entire value of tripling our modelling accuracy.
2. **Two independent implementations of every hot-path step** (decrypt: 7z +
   pyzipper; parse: 4 backends; LLM: 2 provider keys; submit: hedged POST). Each
   one deletes a whole row of the table above rather than mitigating it.
3. **`panic.py` (~150 lines).** The bottom of the ladder must have no
   dependencies, because dependency failure is precisely what puts you there.

### 4.3 What we deliberately do *not* defend against

Stated so it is a decision and not an oversight:

- **The organisers' API being down.** Nothing we can do; everyone suffers equally
  and rank is relative (R8).
- **`t` being drawn from a distribution nothing like our priors.** That is the
  modelling team's risk, not the ops layer's, and §2.5 says a wide honest
  posterior degrades gracefully.
- **Being farmed by an exploiter parked at the cap.** R4b already answers this:
  `b = Q₁ᐟ₃` with honest calibration. We do not add an ops-side hack for it.

---

## 5. Deployment + scheduling

### 5.1 Where this runs overnight

| Option | Setup | Reliability | Debug at 04:00 | Verdict |
| --- | --- | --- | --- | --- |
| **Dev laptop + `caffeinate`** | 0 min | **Poor.** Lid, sleep, wifi roaming, battery, someone `pip install`s into the env, someone closes it to go to bed | You must be physically at the machine | **Secondary only** |
| **Cheap VPS** (Hetzner CX22, Nürnberg, ~€4/mo) | ~20 min | **Excellent.** DC power + network, no sleep state, `systemd`, low latency to a German-hosted API | `ssh` from a phone (Termius/Blink) — but usually the Discord log stream is enough and you never open a terminal | ✅ **PRIMARY** |
| **Cloud VM** (AWS/GCP) | 30–60 min *unless* someone already has a warm account + CLI | Same as VPS | Same, plus console access | Equal to VPS **iff** already warm; otherwise the setup time is the whole argument |
| **GitHub Actions cron** | 15 min | **Disqualifying.** Cron granularity is 5 min, scheduling is best-effort with documented delays of *minutes*, and runners take 20–60 s to boot. You cannot hit a 60 s window every 757.6 s | Log tailing only, no shell | ❌ as primary; ✅ as an **independent watchdog** (F14) |
| **Lambda + EventBridge one-time schedules** | 45 min | Good in principle (100 precise one-shot schedules) | Cold starts, no persistent price memory, CloudWatch archaeology at 04:00 | ❌ — undebuggable when tired |

**Recommendation: one Hetzner VPS in Nürnberg as PRIMARY, one dev laptop under
`caffeinate` as HOT STANDBY on a different network (ideally phone-tethered).**

The deliverable is not the VPS, it is the **rehearsal**: `git clone && ./bootstrap.sh
&& ./run.sh` must stand up a working runner from a bare box in **under 10 minutes**,
with all configuration in env vars and nothing in anyone's shell history. We do
that once, timed, on Saturday evening. If it takes 40 minutes the first time, we
fix it until it takes 10 — because that number *is* our recovery time from any
catastrophic host failure at 03:00.

### 5.2 Scheduling without drift

The cadence is not arbitrary — it is **exactly `75 000 / 99 = 25 000/33` seconds**
(Sat 15:00 → Sun 11:50 is 75 000 s; 100 games is 99 intervals). It is not
representable in integer milliseconds, microseconds, or nanoseconds, which is
precisely how a naive implementation accumulates drift: rounding to 757.6 s and
adding incrementally puts you **2.4 s off after 100 games** — and rounding to 757 s
puts you **57 s off, i.e. outside the window, by game 100.**

Rules:

1. **Authoritative source is the API.** `GET /leaderboard/api/games?page_size=1000`
   at startup and every 10 minutes. Store absolute UTC start instants. Use them.
2. **Never accumulate.** The closed form `t_n = T₀ + n × 25000/33 s` is the
   *fallback* if the schedule endpoint is down, computed from a single anchor with
   `Fraction` or float64 (error ~1e-10 s over the tournament) — never by repeatedly
   adding an interval to the last start.
3. **Never trust the local clock.** On every HTTP response record
   `offset = server_Date − local_recv − rtt/2`; keep a median over the last 20
   samples; schedule against `local_now + offset`. Assert `|offset| < 2 s` at
   every PREFLIGHT, PAGE above 5 s. Run `chrony` as well — belt and braces,
   because a suspended VM can wake with a stale clock and a stale clock is the one
   failure that silently misses *every remaining game*.
4. **Never one long sleep.** `time.sleep(757)` is vulnerable to suspend and clock
   jumps. Sleep in a loop: 5 s granularity until `T−30`, 200 ms until `T−0.5`,
   5 ms for the last half-second, re-reading the corrected clock each iteration.
5. **Poll, don't guess, at the boundary.** Compute the next start from the
   schedule, *then* poll for the key across the boundary. Computing tells you when
   to be ready; polling tells you when it is actually there.

**How early can we fetch the key?** Not one millisecond before release — "do not
try to obtain decryption keys before a case is released" is an explicit fair-play
rule and the downside is disqualification, which is infinitely worse than a slow
submission. We start polling at `T0−3 s` at a 1 s cadence and tighten to 250 ms
across the boundary, stopping on the first 200, capped at **20 requests per game
(~2 000 for the tournament)**. We will state that cadence in the write-up: it is
deliberately light, it is well under anything that could be called probing or
overloading, and showing our own rate-limiting is a style point, not a confession.

### 5.3 Redundancy: how many instances

**Two, with a defined leader.** Three if the VPS was flaky in rehearsal. More than
three multiplies the split-brain surface for no gain.

### 5.4 Split brain — two instances, different answers

"Later submissions overwrite earlier ones" makes concurrent submitters a
correctness hazard: instance B's *cheap* answer landing after instance A's *smart*
answer costs us `37 t` for that game.

Three layers, in order of how much we rely on them:

1. **Timing stagger does most of the work, for free.** Every instance submits
   cheap at `T0+3` and smart at `T0+50`. All cheap submissions therefore land
   ~47 s before any smart one. Cross-instance harm requires instance B to be more
   than 45 s behind instance A — which the clock assertion in §5.2 makes
   impossible. **The schedule discipline is the split-brain fix.**
2. **Tier CAS.** Instances record `(game_id, tier)` in a tiny shared store
   (Redis on the VPS, or an S3 object, or one Postgres row) via compare-and-swap;
   an instance POSTs only if its tier strictly exceeds the recorded one.
3. **Availability beats consistency when the store is unreachable.** If the CAS
   store cannot be read, **submit anyway.** The worst case of a redundant
   submission is `37 t`; the worst case of a suppressed one is `130 t`. The bias is
   always toward submitting.

Two instances both landing tier-3 with *different* smart answers is fine — they are
two draws from the same estimator and last-write-wins picks one. If we want
determinism anyway: only instance A may send tier 3, unless A has missed a
heartbeat for 2 consecutive games, at which point B is promoted.

---

## 6. Observability + on-call

### 6.1 The one dashboard

A single static HTML file, rewritten by the bot after every game, served by
`python -m http.server` and mirrored to a public URL. The top of the page is
**one hundred cells**:

```
 ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██   G001–020
 ██ ██ ██ ██ ██ ██ ██ ▓▓ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ██   G021–040
 ██ ██ ██ ██ ██ ██ ██ ██ ██ ██ ░░ ░░ ██ ██ ██ ██ ██ ██ ██ ██   G041–060
 ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··   G061–080
 ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ·· ··   G081–100

 ██ smart   ▓▓ partial   ░░ cheap   ▒▒ blind   ██(red) NO SUBMISSION   ·· pending
```

**"We are fine" = no red cells.** That is the entire on-call cognitive load, it
renders on a phone, and a groggy human can evaluate it in under two seconds
without reading a single number.

Below the grid: last-10-game timings (key latency, parse ms, LLM s, submit-1 and
submit-2 wall clock), cumulative LLM spend against budget, a clock-offset
sparkline, our leaderboard net, and the posterior-width chart from `learn.py`.

**This is also the pitch demo.** Sunday 12:30, a wall of 100 green cells next to a
chart of the posterior tightening game over game is a far better five minutes than
a slide of equations — it is *evidence that R1–R9 were actually applied 100 times*.
One artefact, built for ops, doing double duty. That is worth saying out loud when
we argue for building it early.

### 6.2 Logging

Structured JSONL, one object per game, to disk and stdout (`journald`):

```json
{"game":47,"t0":"2026-08-23T03:14:12.121Z","offset_ms":312,"key_ms":840,
 "decrypt":"7z","parse":"pdfplumber","items":9,"cheap_at":2.81,
 "llm":{"model":"...","ms":6210,"in":3980,"out":1120,"usd":0.031,"items_returned":9},
 "smart_at":48.10,"tier":3,"vetoed":[],"sum_a":2340.0,"sum_b":1910.0,
 "verify":"ok","rl_remaining_tokens":118400}
```

Note `rl_remaining_tokens` — we log the provider's rate-limit response headers on
every call. Free telemetry that turns F6 from a surprise into a trend line.

### 6.3 Alerting — the rule that keeps it useful

> **An alert that does not name an action a half-asleep person can take is a log
> line, not an alert.**

| Level | Condition | Channel |
| --- | --- | --- |
| **PAGE** | two consecutive games with **no submission at all** | Discord `@here` **+ ntfy.sh push** to the on-call phone |
| **PAGE** | a submission landed containing any `a == 0` (the airlock failed) | same |
| **PAGE** | clock offset > 5 s | same |
| **PAGE** | primary heartbeat missed 2 games *and* standby did not take over | same |
| WARN | smart path failed → cheap used | Discord `#c2f-alarm` only |
| WARN | LLM budget > 70 %, disk < 2 GB, `cheap_only` engaged | Discord only |
| INFO | one line per game (§6.4) | Discord `#c2f-heartbeat` |

Only **four** conditions wake a human, and every one of them is genuinely
unrecoverable-without-hands. Everything else degrades and waits for morning.
`ntfy.sh` is free, needs no account, and takes three minutes to wire up: `curl -d
"msg" ntfy.sh/<random-topic>` and the phone app subscribes.

### 6.4 The heartbeat line

One Discord message per game, ~48 overnight, readable in one glance:

```
G047 ✅ T3  cheap@2.8s  smart@48.1s  9 items  Σa=2,340 Σb=1,910  llm 6.2s $0.031  Δclk +0.3s
G048 ⚠️ T1  cheap@2.9s  smart FAILED (429 x2, both keys)  9 items  Σa=2,110
```

If you wake up at 04:00 and scroll, you can tell in five seconds whether the night
went well without opening a browser.

### 6.5 RUNBOOK.md — exactly five entries, each ≤ 3 commands

Longer than five and nobody reads it at 04:00.

| Symptom | Action |
| --- | --- |
| No submissions for 2 games | `ssh box` · `systemctl restart c2f` · `journalctl -u c2f -n 100` |
| Everything is tier-1 / cheap | check the model key: `curl -sf .../models \|\| echo DEAD` · swap to `LLM_KEY_B` in `/etc/c2f.env` · restart |
| Clock offset alert | `sudo chronyc makestep` · `systemctl restart c2f` |
| Primary unreachable | on the standby laptop: `./bootstrap.sh` · `./run.sh --leader` |
| Red everywhere, cause unknown | `./run.sh --panic` (that is `panic.py`: stdlib only, no LLM, no shared state, always works) |

### 6.6 Rate limits and cost

Per game, one **batched** call over the whole invoice — not one call per line item.
Input ≈ `policy.txt` (1.5 k) + `description.txt` (0.4 k) + invoice text (0.6 k) +
scaffold + price-memory context (1 k) ≈ **4 k tokens**; output ≈ 120 tok/item × 8 ≈
**1 k tokens**. Vision cases add ~1.5 k input.

| Configuration | Tokens over 100 games | Cost @ `$1.25/$10` per M | @ `$3/$15` per M |
| --- | --- | --- | --- |
| 1 call/game | 0.4 M in / 0.1 M out | **$1.50** | **$2.70** |
| 3 parallel samples, median per item | 1.2 M in / 0.3 M out | **$4.50** | **$8.10** |
| 3 samples + heavy reasoning (5× output) | 1.2 M in / 1.5 M out | **$16.50** | **$26.10** |

**The entire tournament costs well under $100 even being extravagant.** The correct
posture follows immediately: *cost must never be the reason we degrade.* Pre-fund
3× the estimate on Saturday afternoon, set a hard provider spend cap at 2× so a
runaway retry loop cannot drain a card, and stop thinking about it. Running 3
parallel samples and taking a per-item median is a genuine accuracy win for
**$5** — take it.

**Rate limits, not money, are the real risk.** A freshly-created org sits in a low
tier with a modest TPM ceiling, and vision requests are token-heavy. Mitigations:
(a) read `x-ratelimit-*` headers Saturday 15:30 and log them on every call
thereafter; (b) **two provider keys, funded separately, round-robin** — a 429 on
one is a 200 on the other; (c) never retry a 429 more than twice inside the
60 s window, fall to cheap instead. If credits genuinely run out at 03:00: the
first `insufficient_quota` flips `cheap_only`, posts a **WARN** (not a page — a
29 % degradation is not worth a wakeup), and someone tops up at 07:00 with 20
games still to play. Cost of that whole incident: ~40 games × `37 t` = `1 500 t`,
recoverable, and strictly better than a human fumbling a billing page at 03:00.

### 6.7 The night shift: there should not be one

**Rota** = humans awake doing work. **On-call** = humans asleep with a loud phone.
We want the second and not the first, for three reasons:

1. Five people awake for twelve hours produces five exhausted people for a 12:30
   pitch that is 50 % of the QuantCo score.
2. The most common cause of overnight outage at a hackathon is not infrastructure,
   it is **a human deploying at 03:00**. A rota manufactures that risk. Hence the
   **01:00–07:00 deploy freeze** — the on-call may run the runbook and nothing else.
3. If the system needs a human every hour, it is not finished, and we should
   discover that at 22:00 rather than at 03:00.

| Window | Who | Duty |
| --- | --- | --- |
| 22:00 **GO/NO-GO** | all 5 | §8 criteria. If GO, three people go to bed by 23:30 |
| 00:00–04:00 | Dev A (built the runner) | phone loud, asleep, expects 0 wakeups |
| 04:00–08:00 | Dev B | same |
| 06:45 | Devs C + D alarm | check the grid, start the write-up while ~25 games still run |

Expected wakeups: **zero**. One wakeup is tolerable. Two means we shipped a system
we should not have gone to bed on, and §8 says what we do about that.

---

## 7. Architecture + 24 h build plan

### 7.1 Modules

Thin interfaces, plain dataclasses at every seam, so five people can work in
parallel for 21 hours without blocking each other.

| Module | Interface | Owner |
| --- | --- | --- |
| `schedule.py` | `next_game() → Game`, `corrected_now() → datetime` | D1 |
| `prefetch.py` | background sync of the case folder → local archives + checksums | D1 |
| `acquire.py` | `Game → Case` (key fetch, decrypt, extract). 2 decrypt backends | D2 |
| `parse.py` | `Case → LineItem[]`. 4 backends in a ladder | D2 |
| `memory.py` | SQLite price memory; `lookup(desc) → (m, σ, rung)` | D3 |
| `price_cheap.py` | `(LineItem[], Memory, Priors) → Quote[]`. **Pure, offline, total, never raises** | D3 |
| `price_smart.py` | `Case → AsyncIterator[Quote]`. Streaming JSONL, timeout-bounded, partial-safe | D4 |
| `airlock.py` | `(cheap, smart?, case) → Payload`. **Pure. The only producer of a POST body** | D3 |
| `submit.py` | `Payload → Receipt`. Tier/seq guard, hedged retry, read-back verify | D1 |
| `learn.py` | leaderboard → `t` brackets + opponent `b` reconstruction (R9) → memory. **Off the hot path, allowed to fail** | D5 |
| `observe.py` | JSONL log, Discord webhook, ntfy push, dashboard HTML | D5 |
| `run.py` | the scheduler loop. Tiny, dependency-light, forks a worker per game, `SIGKILL` at `T0+58` | D1 |
| `panic.py` | stdlib-only single file. **Imports nothing from the above, on purpose** | D1 |

The scheduler never touches untrusted input; all parsing and model I/O happens in
a disposable child process. That is what makes F13 cost one game instead of the
tournament.

### 7.2 Hour by hour

**Roles:** D1 ops/runner · D2 pipeline · D3 cheap+airlock · D4 LLM · D5 observability+learn+write-up

| When | D1 | D2 | D3 | D4 | D5 |
| --- | --- | --- | --- | --- | --- |
| **13:00–13:30** *procurement — nothing else starts until the key exists* | API key at the desk; folder link | `p7zip` on every machine; start prefetch | read case 0's PDF by hand; start the seed price table | read `API_HANDBOOK.md`; confirm exact submission JSON shape | ehl.gg challenge selection; Entire gate; Discord webhook + ntfy topic; **post the R9 question to `#❓-ask-orgateam`** |
| **13:30–14:30** | ← **`panic.py` ships (D1+D2 pair)** → | ← | seed table | run `starter_script.py` on case 0 | **run the 3 API experiments (§7.3)** |
| **14:30–15:00** | dry run on game 1 — *everyone watches* | | | | verify the submission actually landed via the leaderboard |
| **15:00–17:00** | `run.py`, clock offset, subprocess isolation | `acquire.py` + `parse.py` (2 backends) | `price_cheap.py` + `memory.py` schema | `price_smart.py` v1, batched, JSONL | `observe.py`: JSONL + Discord heartbeat |
| **17:00 MILESTONE** | ← **two-phase submit works end-to-end on a live game** → | | | | |
| **17:00–19:00** | fallback ladder wiring, watchdog thread, tier guard | parse backends 3+4 (poppler, vision) | **`airlock.py`** — best person, highest-value 200 lines | prompt iteration on settled cases; gross-total recompute | dashboard v1 (the 100-cell grid) + ntfy paging |
| **19:00 MILESTONE** | ← **VPS provisioned, running the same code, `bootstrap.sh` proven from a bare box in < 10 min** → | | | | |
| **19:00–21:00** | redundancy + tier CAS + standby laptop | F4/F5 hardening on real cases | calibration: invert ~19 settled games to `t` brackets | 3-sample median; coverage check (R4b) | `learn.py` live; **write-up draft** |
| **21:00–22:00** | ← **CHAOS HOUR (§7.4)** → | | | | |
| **22:00** | ← **GO / NO-GO (§8)** → | | | | |
| **22:00–01:00** | standby armed, freeze scheduled | *optional*, non-runner only | *optional* | prompt tuning via replay test only | write-up |
| **01:00–07:00** | ← **FREEZE. Nobody touches the runner. ~29 games run themselves.** → | | | | |
| **07:00–10:00** | verify the night; fix anything red | | ← **recalibrate on ~50 settled games — this is where the modelling payoff lands** → | | ≤ 2 deploys, each through the replay test |
| **10:30** | ← **CODE FREEZE for the last ~8 games** → | | | | |
| **10:30–11:50** | watch | | | | write-up final + dashboard polish + **pitch rehearsal ×2** |
| **12:00** | ← submit on ehl.gg → | | | | |
| **12:30** | ← pitch → | | | | |

### 7.3 The three experiments to run before 14:30

Each is ten minutes and each changes a design decision:

1. **Does the API accept more line-item indices than the case has?** If yes, the
   BLIND rung always over-submits and is worth `76 t` per rescued game. If no, we
   need the modal item count.
2. **Does the API let us read our own submission back?** Determines whether the
   `T0+55` VERIFY step exists. If not, we rely on the leaderboard at `T0+90` and
   accept a one-game detection lag on airlock failures.
3. **Is the key available *exactly* at `T0`, or with a lag?** Determines the poll
   cadence and whether `T0+3` for submit #1 is achievable or needs to be `T0+5`.

### 7.4 Chaos hour (21:00–22:00) — the acceptance test

D1 breaks things on purpose **while real games run**. Each must degrade to a
submitted payload with `a > 0`:

| Injected fault | Expected outcome |
| --- | --- |
| `kill -9` the worker at `T0+20` | supervisor restarts; tier-1 already on file |
| `kill -9` the scheduler | standby takes the lease within 1 game |
| `iptables -j DROP` the model host | F6/F7 → tier 1, WARN only |
| revoke the model key | `cheap_only`, WARN, no page |
| corrupt a local archive | checksum mismatch → re-fetch → decrypt |
| `mv $(which 7z) /tmp` | `pyzipper` backend, tier 3 unaffected |
| feed a scanned/image-only PDF | vision backend or BLIND, never DEFAULT |
| `date -s '+30 seconds'` | offset detected, PAGE, schedule still correct |
| `fallocate` the disk to full | extracts purged, WARN, game completes |
| unplug the standby's network | primary unaffected, no split brain |

**Any fault that produces a DEFAULT submission is a P0 and blocks the 22:00 GO.**

---

## 8. Kill criteria and honest downside

### 8.1 Kill criteria — decided now, in daylight

Written in advance precisely so nobody has to make these judgements while tired.

| Time | Criterion | If it fails |
| --- | --- | --- |
| **15:00** | We submitted *something* on game 1 | **Everything stops.** No modelling work, no prompt tuning, no dashboard, until a submission lands. |
| **17:30** | Two-phase submit works end-to-end on a live game | **Cut the smart path for the night** and ship cheap-only. Cheap at 100 % is worth `−7 173`; all-or-nothing smart at 70 % is worth `−7 351`. Cheap-only *wins*. Re-introduce the LLM path Sunday morning in daylight. |
| **20:00** | VPS up, green, `bootstrap.sh` rehearsed | Stop trying. Commit to two laptops on mains power on separate networks, plus a human alarm every 2 h. Worse — but chosen consciously at 20:00 rather than discovered at 02:00. |
| **22:00 GO/NO-GO** | 3 consecutive games green, **unattended**, with the dev SSH'd out and the laptop lid shut · chaos hour clean · runbook written · on-call phones tested with a real ntfy push | **Nobody sleeps on schedule.** The on-call becomes a real rota until 3 clean unattended games happen. This is the one case where §6.7 is overruled. |
| **01:00** | — | **Deploy freeze.** Runbook only. |
| **10:30** | — | **Code freeze** for the last 8 games. |

### 8.2 Honest downside

**1. We may win reliability and lose the tournament on numbers.** If the field is
strong and everyone posts 100 % uptime, uptime is table stakes and the game is
decided entirely by the 29 % we deprioritised. This is the real risk and I will not
dress it down. Three things blunt it: the ops work is **front-loaded and finite**
(~6 hours, done by 21:00), not a permanent tax; two of five devs are on estimation
from 15:00 onward; and the 07:00–10:00 window hands the modelling team **50 settled
games of labelled data** (R9) that a team which slept through the night simply does
not have. Reliability is how we *buy* the training set.

**2. The 71 % rests on a model, and models are wrong.** It is algebraically
invariant to field size and invoice length (§2.4) and it survived 81 scenarios at
67.7–74.1 %, but it assumes our posterior is roughly centred and the field charges
somewhere near `t`. It is weakest if the field charges **well above** our `b`,
where wrongful-rejection costs blow up and the `b` term starts to dominate — in
which case R4b's calibration work matters more than this plan says. **The tell:
`learn.py` measures the field's realised charge distribution after every game.**
If by 19:00 the field is charging above `1.2t` on average, we re-run §2 with the
measured numbers and re-argue the priority order. The plan should be falsifiable
by its own telemetry, and it is.

**3. We may over-engineer.** 4 parse backends, a tier CAS store, and 21 rows of
fallback table is a lot for 21 hours. Mitigation: the ladder is built in strict
priority order and **every rung ships independently**. If we run out of time at
rung 2, the system is still correct — just less defended. Nothing in §4 is a
prerequisite for anything else in §4.

**4. "Style" may reward cleverness over plumbing.** QuantCo is a data-science firm;
a judge may find "we built a very reliable submitter" boring next to a Bayesian
hierarchical model. Mitigation is framing, and it is honest framing: the write-up
**leads with R1–R9** — the maths is genuinely the interesting part — and closes
with the 100-green-cell grid as *evidence that the maths was applied a hundred
times*. The one-line version we should actually say out loud: **"we did not build
a reliable bot instead of a model; we built it because you cannot calibrate a
posterior on games you did not play."**

**5. The deploy freeze will cost us a real improvement.** Somebody will have a good
idea at 02:30 and be told to write it down and go to bed. Accepted deliberately:
an unshipped improvement costs `37 t` per remaining game; a bad deploy costs
`130 t` per game until someone wakes up. At 02:30 there are ~45 games left, so the
freeze is right unless the improvement is worth more than a 28 % chance of a
two-hour outage. It is not.

**6. Pre-staging archives is a small unknown.** If the organisers publish cases
*incrementally* rather than all at once, the prefetch daemon degrades to a live
download at `T0` and we lose the §3.0 unlock. The daemon handles both; the risk is
that we build the fast path and never get to use it. Cost: ~15 minutes.

### 8.3 The one-sentence version

> Half of this tournament runs while we are asleep, the default submission is the
> worst score in the game, and a crude answer captures 71 % of a perfect one — so
> we spend the first six hours making sure we never miss, and the last four making
> the answer good.

---

### Appendix — reproducing the numbers

Every figure in §2 comes from the model in §2.1: issuer income
`E = max_a a·P(t ≥ a)` under a lognormal posterior (optimum at `λ(k) = σ` where
`λ` is the inverse Mills ratio), reviewer cost
`E[a_j] + ½·E[a_j·1{a_j > b}]` against a lognormal field, `b = Q₁ᐟ₃` per R4.
Sensitivity sweep: 81 scenarios over field median `{0.7, 0.85, 1.0}·t`, field
log-sd `{0.25, 0.35, 0.5}`, `f ∈ {0.5, 0.8, 1.0}`, `M−1 ∈ {5, 19, 39}`.
**Recovery fraction: min 67.7 %, median 72.4 %, max 74.1 %.**
The script is committed alongside this plan as **`docs/strat-ops/ev.py`**
(`python3 docs/strat-ops/ev.py`, stdlib only) so the argument stays falsifiable:
when `learn.py` measures the field's realised charge distribution, edit the
parameters, re-run, and let the numbers re-argue the priority order.
