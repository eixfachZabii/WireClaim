# Current winners, Games 34-38: what changed, and is any of it copyable

Written 2026-08-22, ~22:50-23:15 CEST, 39 Games completed at time of writing. Commissioned
because ranking by the last five settled Games instead of the season total inverts the
leaderboard: Non Deterministic and Codacabana are winning right now while eyay and error404
ai — the two teams the earlier `rivals_study.py` benchmarked against (and beat, on their
Charge ratio) — are losing per Game. The brief's working hypothesis was that an early
overnight **Dark Window** (opponents going `a=0,b=0`) had begun around Game 33-34, based on
two identical-net observations (G34 makalu/AsianSuperNerds both -50,380; G35
makalu/TBD/OPUSMOPUS all -55,267).

**That hypothesis does not survive measurement.** Both identical-net observations are real
and independently confirmed, but they are not part of a new trend — see §1. The actual
story is a field-wide rise in how much of the honest ceiling everyone (not just the current
top five) captures as fair income, plus one huge single Game for Non Deterministic, plus a
genuine but small issuer-side improvement for Non Deterministic specifically that mostly
just re-confirms a rule this repo already knows (R5b, `a* ≈ 0.7·t̂`). Along the way this
surfaced a bigger, more certain, and more actionable finding about **us**: our own
reviewer-side cost ratio degraded more than anyone else's between the two windows (§4).

All numbers below are reproducible:

```bash
PYTHONPATH=. python scripts/experiments/dark_team_census.py --games 1-38 --json var/experiments/dark_census.json
PYTHONPATH=. python scripts/experiments/current_winners_study.py --per-game --decompose --exposure --games 34-38
PYTHONPATH=. python scripts/experiments/current_winners_study.py --decompose --games 19-32
PYTHONPATH=. python scripts/experiments/current_winners_study.py --counterfactual --donor "Non Deterministic"
PYTHONPATH=. python scripts/experiments/current_winners_study.py --counterfactual --donor Codacabana
PYTHONPATH=. python scripts/invert_fair_values.py --verify --games 19-38
```

Data integrity: `invert_fair_values.py --verify` reproduces every published net to the cent
for Games 20-38 (Game 19 has no published `/matrix` cell — outside the trailing 20-Game
window at fetch time — and is trusted on the identity alone, exactly as `replay_payoffs.py`
already treats it). Every four-bucket decomposition below reconciles to `identity_net` to
the cent (`_verify_reconciliation`, printed as "reconciliation OK" on every run). Noise
floor: **26,622 over 18 Games, scaled × √(n/18)** — **±14,031 over the 5-Game focus window**,
**±12,551 over 4 Games** (the drop-G35 sensitivity check).

---

## 1. The regime-change claim, measured and refuted

**Per-team darkness** (`a=0` as Issuer, `b=0` as Reviewer — literally never paid a cent as
Issuer and never accepted a positive Charge as Reviewer, over every cached Transaction for
that team in that Game) was computed for all 17 teams across all 38 completed Games, cross-
checked against the identical-net signature. Both cited examples corroborate exactly:

```
G34: ['AsianSuperNerds', 'makalu'] all net -50,380.07 -- all independently dark-flagged
G35: ['OPUSMOPUS', 'TBD', 'makalu'] all net -55,266.61 -- all independently dark-flagged
```

But plotted over the full history, there is no rising trend — if anything the opposite:

```
G  1 [13] #############
G  2 [ 7] #######
G  3 [13] #############
G  4 [ 5] #####
G  5 [ 5] #####
G  6 [ 3] ###
G  7 [ 5] #####
G  8 [ 4] ####
G  9 [ 3] ###
G 10 [ 3] ###
G 11 [ 4] ####
G 12 [ 3] ###
G 13 [ 1] #
G 14 [ 5] #####
G 15 [ 3] ###
G 16 [ 8] ########
G 17 [ 2] ##
G 18 [ 3] ###
G 19 [ 4] ####  <- old window (19-32) starts
G 20 [ 1] #
G 21 [ 2] ##
G 22 [ 1] #
G 23 [ 3] ###
G 24 [ 2] ##
G 25 [ 2] ##
G 26 [ 1] #
G 27 [ 1] #
G 28 [ 7] #######
G 29 [ 1] #
G 30 [ 1] #
G 31 [ 3] ###
G 32 [ 1] #        old window (19-32) ends ->
G 33 [ 1] #
G 34 [ 2] ##   <- FOCUS (34-38) starts
G 35 [ 3] ###
G 36 [ 5] #####
G 37 [ 1] #
G 38 [ 1] #        FOCUS (34-38) ends ->
```

`rivals.changepoint()` (max-separation split, min side 3) on the full series puts the
break at **G4** — mean **11.00 before, 2.86 after** — i.e. darkness was highest while the
field was still booting and fell from there. Restricted to the window that actually
matters (G19-38, i.e. old-window-plus-focus), the same search finds a "break" at G29 with
**gap/spread = 0.31**, far under the ~1 threshold this repo already uses to call something
real. Mean dark-team count is **2.40 before G29, 1.90 after** — flat to declining, not
rising.

**One team dominates the raw count and is not a regime signal: "makalu" is dark-flagged in
38 of 38 completed Games (100%)** — a team whose pipeline has apparently never run, not a
seasonal pattern. Excluding makalu, the mean simultaneously-dark-team count is **1.07/Game
over G19-33** and **1.4/Game over G34-38** — indistinguishable given n=5, and the gap is
driven by one Game (G36, 4 non-makalu dark teams, itself inside the noisy range already
seen at G16 and G28 in the "old" window).

**Verdict: there is no Dark Window onset around Game 33-34.** The two cited identical-net
observations are correctly diagnosed as dark teams, but they are ordinary background noise
of the kind this tournament has shown since Game 1, not evidence of a trend. Any
explanation of the leaderboard inversion has to come from somewhere else.

---

## 2. Non Deterministic went fully dark in one of its own five focus Games

Before decomposing anything, the per-Game record for the new top five plus the two
declining old leaders (`*` = team itself fully dark that Game):

```
team                              34            35            36            37            38         total
Non Deterministic            1,240        16,675             0 *       1,658         4,081          23,654
Codacabana                  -6,135         4,366         2,010         7,938         3,557          11,736
Claims Renaissance           7,337        -6,634       -12,697        12,823         2,610           3,439
Teamers                     -8,755         8,387         2,061           550           876           3,119
Bin busy                    -3,949         3,301         2,307         1,939          -504           3,094
error404 ai                  1,026         1,943         1,752        -5,264          -638          -1,181
eyay                        -7,065         7,692         1,797           571        -4,363          -1,368
```

Two things worth flagging before the decomposition:

- **Non Deterministic's own Game 35 is 16,675 of their 23,654 five-Game total — 70.5%.**
  Drop that one Game and the remaining four-Game total is **6,979**, well inside the
  **±12,551** noise floor for n=4. The raw "current winner" ranking is fragile.
- **Non Deterministic itself was fully dark on Game 36** (net exactly 0.00 — not a "smart"
  strategic choice, just their pipeline not submitting). Their own dark rate is **21.4%
  over G19-32 (3/14 Games: 23, 28, 31) and 20.0% over G34-38 (1/5: Game 36)** — essentially
  unchanged, and this habit predates the "surge." G36 also happens to be a Case where
  `invert_fair_values.brackets()` puts `t_lo = 0` on **all 10 Line Items** (nobody's Charge
  was ever wrongfully rejected by anyone, field-wide) — the same signature already
  documented for Games 21, 22 and 28 in `dark-regime-charge.md` as a genuinely low-value
  Case, not a sleeping field. Going dark there cost Non Deterministic nothing.

---

## 3. Four-bucket decomposition of the current top five (Games 34-38)

Reconciles to `identity_net` to the cent for all 7 teams.

```
team                            net |  (i) inc fair (ii) inc over (iii) cost acc  (iv) penalty |  issuer side reviewer side   t_available fair capture
Non Deterministic            23,654 |       162,873        11,414         62,964        87,670 |      174,287      -150,633       264,036       61.7%
Codacabana                   11,736 |       140,001        18,532         78,200        68,598 |      158,534      -146,798       264,036       53.0%
Claims Renaissance            3,439 |       149,211         8,090        103,339        50,522 |      157,300      -153,862       264,036       56.5%
Teamers                       3,119 |       141,703        20,784         41,551       117,817 |      162,488      -159,368       264,036       53.7%
Bin busy                      3,094 |       152,662        12,919         10,264       152,222 |      165,581      -162,487       264,036       57.8%
error404 ai                  -1,181 |       131,403        23,883         50,853       105,614 |      155,285      -156,466       264,036       49.8%
eyay                         -1,368 |       140,229        15,933         40,356       117,173 |      156,162      -157,529       264,036       53.1%
```

`t_available` (sum of `t × opponents` over the window's Line Items — the honest ceiling if
everyone charged exactly `a = t` to every opponent, R1) is **identical for every team**
because they all face the same Cases. That makes `fair_capture = income_fair / t_available`
directly comparable across teams and, more importantly, across windows with different
average Case sizes — the raw euro columns are not.

**Answering the brief's direct question — issuer or reviewer side?** Non Deterministic's
issuer-side income (174,287) is only 5.5% above Bin busy's (165,581) and its reviewer-side
cost (-150,633) is 7.3% below Bin busy's (-162,487) — both sides contribute, but neither
margin is dramatic against *this* window alone. The sharper answer comes from comparing
each team against **its own G19-32 self** — see §4, where the issuer side turns out to be
overwhelmingly where the story is.

---

## 4. Did the winners change, or did the field change? — the same teams, G19-32 baseline

Same five-team-plus-two decomposition, replayed over the window the earlier eyay study
used (`t_available = 495,304`, 14 Games):

```
team                            net |  (i) inc fair (ii) inc over (iii) cost acc  (iv) penalty |  issuer side reviewer side   t_available fair capture
Non Deterministic           -87,779 |       165,692        36,970        141,794       148,647 |      202,662      -290,441       495,304       33.5%
Codacabana                   38,372 |       188,673       121,434        168,428       103,306 |      310,107      -271,735       495,304       38.1%
Claims Renaissance         -101,111 |       113,985        92,946        162,924       145,117 |      206,931      -308,041       495,304       23.0%
Teamers                     -63,273 |       183,049       126,195        329,211        43,306 |      309,244      -372,517       495,304       37.0%
Bin busy                    115,405 |       160,315       173,414         13,925       204,399 |      333,729      -218,324       495,304       32.4%
error404 ai                  35,226 |       225,686       116,358        179,376       127,441 |      342,043      -306,817       495,304       45.6%
eyay                        100,295 |       193,765       147,413         66,217       174,665 |      341,177      -240,882       495,304       39.1%
```

`fair_capture` rose for **every one of the seven teams** between windows: Non Deterministic
33.5%→61.7%, Codacabana 38.1%→53.0%, Claims Renaissance 23.0%→56.5%, Teamers 37.0%→53.7%,
Bin busy 32.4%→57.8%, error404 45.6%→49.8%, eyay 39.1%→53.1%. **This is a field-wide
effect, not a Non Deterministic or Codacabana discovery.** The ceiling itself also grew
(average `t_available` per opponent per Game: 2,211 old → 3,300 new, +49%), but the
fair-capture *rate* moved by far more than that scaling alone would produce, so something
about how the whole field's Charges land against `t` genuinely shifted, on top of bigger
Cases. Overcharge income (bucket ii) fell **per Game for all seven teams** in the same
window (down 13.6% to 79.1% depending on the team) — consistent with the already-known
"52% of our income is accepted Overcharges, and a stricter/darker Reviewer collapses that
column" (brief's own prior), just not concentrated in the last five Games specifically.

**Opponent-darkness exposure confirms the field did not get darker around these teams
specifically** — the mechanism the brief hypothesized:

```
team                    avg dark opp G19-32  avg dark opp G34-38    delta  own dark rate 19-32  own dark rate 34-38
Non Deterministic                      1.93                 2.20     0.27               21.4%               20.0%
Codacabana                             2.14                 2.40     0.26                0.0%                0.0%
Claims Renaissance                     2.00                 2.40     0.40               14.3%                0.0%
Teamers                                2.14                 2.40     0.26                0.0%                0.0%
Bin busy                               2.14                 2.40     0.26                0.0%                0.0%
error404 ai                            2.14                 2.40     0.26                0.0%                0.0%
eyay                                   2.14                 2.40     0.26                0.0%                0.0%
```

+0.26 to +0.40 dark opponents out of a ~2.1-2.4 baseline (of 16) is noise for n=5 vs n=14 —
it is not the source of anyone's swing.

**Normalizing net by the same ceiling isolates *where* each team's swing actually came
from** (percentage points of `t_available`; `Δnet = Δissuer − Δreviewer_cost` reconciles
exactly):

```
team                    issuer% old  reviewer-cost% old  net% old | issuer% new  reviewer-cost% new  net% new | Δissuer  Δreviewer-cost  Δnet
Non Deterministic             40.9%              58.6%    -17.7% |      66.0%               57.1%      9.0% |  +25.1p          -1.5p  +26.7p
Codacabana                    62.6%              54.9%      7.7% |      60.0%               55.6%      4.4% |   -2.6p          +0.7p   -3.3p
Claims Renaissance            41.8%              62.2%    -20.4% |      59.6%               58.3%      1.3% |  +17.8p          -3.9p  +21.7p
Teamers                       62.4%              75.2%    -12.8% |      61.5%               60.4%      1.2% |   -0.9p         -14.8p  +14.0p
Bin busy                      67.4%              44.1%     23.3% |      62.7%               61.5%      1.2% |   -4.7p         +17.4p  -22.1p
error404 ai                   69.1%              61.9%      7.1% |      58.8%               59.3%     -0.4% | -10.3p          -2.6p   -7.6p
eyay                          68.9%              48.6%     20.2% |      59.1%               59.7%     -0.5% |  -9.7p         +11.1p -20.8p
```

Three different mechanisms, not one "winner's secret":

- **Non Deterministic: issuer-side, decisively** (+25.1pp, reviewer-cost ratio essentially
  flat at -1.5pp). Fair income roughly tripled per Game while their Overcharge income and
  reviewer-side spend barely moved. This is the closest thing to a real, team-specific
  behavioural shift in the whole table.
- **Claims Renaissance: also issuer-side** (+17.8pp) plus a modest reviewer improvement
  (-3.9pp) — but from such a deeply negative starting point (-20.4%) that it only reaches
  breakeven (+1.3%), not a win. Their fair-capture jump (+33.5pp) is actually the *largest*
  of the seven, yet nets the least of the positive movers.
- **Teamers: reviewer-side, decisively** (-14.8pp cost-ratio improvement, issuer flat at
  -0.9pp) — the opposite mechanism from Non Deterministic. Their old reviewer-cost ratio
  (75.2% of ceiling) was the worst of the seven; tightening it toward Bin busy's own
  historical discipline (see below) is what moved them.
- **Codacabana: essentially flat** (-3.3pp net) — a consistently mediocre-but-positive
  performer in both windows, not a riser. Their #2 rank in the last-5 table is more "did
  not get worse while others did" than "improved."

**And the largest single delta in this entire table belongs to us, and it is bad news:
Bin busy's reviewer-cost ratio rose +17.4 percentage points (44.1%→61.5%), the worst
degradation of any of the seven teams, wiping out an issuer side that also softened
slightly (-4.7pp).** We had the *best* net ratio of the group in the old window (+23.3%)
and are now mid-pack (+1.2%). This is not about Non Deterministic or Codacabana at all —
it is the single most actionable, most certain finding in this dataset, and it says our own
Limit/reviewer discipline has slipped, not that we are missing an opponent's trick.

**So: did the winners change, or did the field change? Both, and neither is "Non
Deterministic's secret."** The field-wide fair-capture rise (§4, all seven teams) explains
most of why last-5 nets are all closer together and mostly positive; darkness explains none
of it (§1); Non Deterministic's own issuer-side placement genuinely improved beyond the
field-wide rise, but the mechanism (a/t sitting close to R5b's own `0.7·t̂`) is already
prescribed by this repo, not a discovery to import from them.

---

## 5. Testing the three darkness hypotheses explicitly

- **"Winners are simply still awake."** Non Deterministic's own dark rate (20-21%) is
  unchanged between windows, and average opponent darkness barely moved (§4) — uptime is
  not the explanation for *this* window, though it remains true generally (CLAUDE.md rule
  8).
- **"They raised their Limit."** Non Deterministic's `b/t` median moved from **0.79
  (G19-32) to 0.80 (G34-38)** — statistically nothing. The reviewer-cost ratio (§4) is
  flat. **Not what happened.**
- **"They lowered their Charge to stay under `t`."** Non Deterministic's `a/t` median moved
  from **0.52 (G19-32) to 0.72 (G34-38)** — it went *up*, not down, yet fair-capture rose,
  because 0.52 was leaving structural income on the table (R1: `a=t` collects regardless of
  accept/reject) and 0.72 captures more of it while still mostly staying at or below `t`.
  The direction the brief hypothesized is backwards for this team; the level (0.72) lands
  almost exactly on R5b's own `a* ≈ 0.7·t̂`, which we already know and are not fully
  executing.

---

## 6. Counterfactual, replayed on our own reconstructed `t̂` (never the true `t`)

Per CLAUDE.md's explicit warning, `t̂` here is `reconstruct_t_hat()`: `price_median` from
our own `var/decisions/game_NNN.json` where a decision log exists, else `blend.combine`
on cached `var/evidence/case_NN_{model,memory}.json` — **never** the reconstructed true
`t`, which a previous study used and had to retract. Where neither source exists for an
item, that item keeps our own actual `(a,b)` rather than inventing a number.

*(Reimplemented in `scripts/experiments/current_winners_study.py` rather than importing
`scripts/rivals_study.py`: that script's `reconstruct_t_hat` imports
`from src.pricing import Evidence`, and `src/pricing.py` no longer exists — `Evidence`
moved to `src.domain.pricing.engine` in an unrelated refactor. Not our file to fix
mid-tournament; the handful of needed functions are reproduced here, logic unchanged, with
the corrected import — confirmed byte-identical output on the parts that still run, e.g.
`replay_capped`'s Cap model `c = max(4t, 2000)`.)*

### Non Deterministic (median a/t = 0.716, b/t = 0.803, measured on 72 trusted Charges)

```
Games 34-38 (5 Games, floor +-14,031):
  b only (our a, b=0.80*that)        +6,269   inside noise
  a+b    (a=0.72*that, b=0.80*that)  +6,002   inside noise
  a only (a=0.72*that, our b)          -267   inside noise
  -- dropping G35: a+b +1,200, a only -578, b only +1,778 -- all still inside noise

All 39 completed Games (out-of-window check, floor +-39,187):
  a only (a=0.72*that, our b)      +446,105   GAIN (clears noise decisively)
  a+b    (a=0.72*that, b=0.80*that) +428,643   GAIN
  b only (our a, b=0.80*that)       -17,462   inside noise
```

The 5-Game replay of Non Deterministic's actual ratios shows **no gain that clears the
noise floor** — every cell is inside ±14,031, and the sign even flips for the `a`-only
variant. The 39-Game figure for the Charge-ratio variant is large and real, but it is not
new information: **0.72 is R5b's own prescription (`a* ≈ 0.7·t̂`), and the "gain" mostly
comes from replaying it against our own *older* actual submissions, which CLAUDE.md already
documents ran high (median `a/t` ≈ 1.06) before that rule was fully adopted.** This is a
held-out confirmation of R5b, not a new lever borrowed from Non Deterministic. The Limit
variant (`b = 0.80·t̂`) shows no robust gain in either window and flips sign between them —
**not recommended.**

### Codacabana (median a/t = 1.104, b/t = 1.000, measured on 69 trusted Charges)

```
Games 34-38 (5 Games, floor +-14,031):
  b only (our a, b=1.00*that)         +3,700   inside noise
  a+b    (a=1.10*that, b=1.00*that)  -76,577   LOSS
  a only (a=1.10*that, our b)        -80,277   LOSS
  -- dropping G35: a+b -57,617 LOSS, a only -54,395 LOSS, b only -3,222 inside noise

All 39 completed Games (floor +-39,187):
  a only (a=1.10*that, our b)         +2,560   inside noise
  a+b    (a=1.10*that, b=1.00*that)  -38,871   inside noise
  b only (our a, b=1.00*that)        -41,430   LOSS
```

Codacabana's Charge ratio (**above** our own estimate, at 1.10×`t̂`) is a **decisive loss**
when replayed with our own `t̂` over the 5-Game window — consistent with the earlier eyay
study's finding that copying a higher Charge ratio loses money regardless of whose ratio it
is. **Not copyable, on either axis.** Their real-world success is explained by §4's
field-wide rise and their own reviewer-side behaviour (which this counterfactual does not
isolate further, since neither variant clears noise in the direction of a gain), not by a
Charge or Limit rule worth adopting.

---

## Recommendation

**Do not copy Non Deterministic's or Codacabana's Charge or Limit placement tonight.**

1. The premise (a Dark Window starting around G33-34) is refuted by direct per-team
   measurement (§1) — there is nothing to react to on that front.
2. The "current winners" ranking itself is fragile: Non Deterministic's headline +23,654 is
   70% one Game and does not clear the noise floor over the remaining four (§2).
3. What *is* robust — fair-capture rising field-wide (§4) — is not a strategy, it is an
   environmental shift (bigger/clearer Cases in this stretch) that lifted every team's
   issuer-side income roughly in proportion, ours included (32.4%→57.8%, in line with the
   field).
4. The one candidate that looked team-specific (Non Deterministic's `a ≈ 0.72·t̂`) already
   matches R5b, so there is nothing new to import — if anything it is a prompt to check that
   our own shipped `CHARGE_INTERCEPT=0.85, CHARGE_SLOPE=0.45` formula (which outputs
   ≈0.49-0.66× at the σ range this repo has measured, 0.43-0.80) is not sitting *below*
   0.72 more often than intended; that is a calibration question for a different, dedicated
   pass, not a same-night change.
5. Codacabana's Charge ratio is a proven loss on replay (§6) — the opposite of copyable.

**The one number in this whole study worth acting on is not about them — it's about us.**
Our reviewer-side cost ratio degraded by +17.4 percentage points of the honest ceiling
between G19-32 and G34-38 (44.1%→61.5%), the single largest movement of any team in either
direction (§4). We went from the *best* net-to-ceiling ratio of the seven teams examined
(+23.3%) to mid-pack (+1.2%), and the mechanism is reviewer-side, not issuer-side.

One piece of context worth stating precisely rather than leaving implicit: `git log` shows
`LIMIT_CEILING_MEMORY = 0.75` (the "memory-channel-conditional ceiling" CLAUDE.md already
flags as shipped "tonight") landed in commit `be2361f`, **22:48:35 CEST** — essentially the
same minute Game 38 settled (its own cache timestamp: 22:48:44) and *after* every Game in
this report's focus window had already played. So it is not the cause of the G34-38
degradation measured here, but it is aimed at the same lever (the Limit ceiling), and it
had zero chance to affect any Game analysed in this report. **Re-run this same
issuer/reviewer-ratio comparison after a handful of post-be2361f Games settle** — if the
reviewer-cost ratio pulls back toward the old 44-50% range, the fix is working and this
finding is already closed; if it does not, this remains the highest-value open question,
above anything about Non Deterministic or Codacabana.
