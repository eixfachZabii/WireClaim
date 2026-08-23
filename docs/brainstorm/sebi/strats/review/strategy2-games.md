# Strategy 2, Games 21–25 — why we lost, item by item

Strategy 2 went live at `c9634a8`; **Game 21 onward is the first data that measures it**
([`live-changelog.md`](live-changelog.md)). Games 1–20 ran older code and are used here only
as a baseline. Everything below is reconstructed from public settled Transactions with
[`scripts/analyse_game.py`](../../../../../scripts/analyse_game.py):

```bash
PYTHONPATH=. pixi run python scripts/analyse_game.py --games 21-  --names --field --detail --sweep
PYTHONPATH=. pixi run python scripts/analyse_game.py --games 8-8  --names          # baseline
```

**Self-check.** The three realised mechanisms (income collected, cash paid on accepted
claims, cash paid as `1.5a` penalties) reproduce the published net **to the cent in every
Game the leaderboard still publishes** — `max |residual| = 0.00` across all 19 of them
(Games 6–25; the window has already dropped 1–5). Nothing below is netted or smoothed.

~~**Game 16 is excluded**: its rows do not reconstruct.~~ **Corrected — Game 16 was never
broken.** −4,721.32 *is* Game 16's true net and −63,789.25 is **Game 17's**; the mismatch came
from reading `matrix()[us][game_id - 1]` against the sliding window described below, and the
wrong figure was then frozen into a cached snapshot. Case 16 genuinely has 2 Line Items.
Verified independently here: `--games 16-16` closes at −0.00. `BROKEN_GAMES` in
`analyse_game.py` is therefore **empty**, with the reasoning recorded next to it — a Game is
only excluded when there is a residual to show for it.

**Two traps handled, not avoided.** The `/matrix` `cells` array is a **sliding window over
the last twenty Games**, aligned with the `game_ids` array in the same payload (it moved from
`[4 … 23]` to `[6 … 25]` while this was being written), *not* indexed by game id.
`published_nets()` zips the two, which is why the cross-check lands at 0.00 instead of being
off by three — and why every net here is derived from Transactions with the matrix only as a
cross-check. And `transactions()` pages to the end: a 480-row Game reads as a 100-row Game
otherwise.

---

## 1. Headline

Games 21–25 are the completed Strategy-2-era Games at the time of writing (Game 25 settled
while this was being written and is included; Game 26 had not).

| | measured over Games 21–25 |
| --- | ---: |
| income collected | **+124,256.82** |
| cash paid on accepted claims | **−7,928.45** |
| cash paid as `1.5a` wrongful-rejection penalties | **−84,752.10** |
| **net (= published, residual 0.00)** | **+31,576.27** |
| of the reviewer cost: unavoidable (the oracle pays this too) | 64,116.37 |
| **avoidable excess from strictness** | **28,250.70** |
| avoidable excess from leniency | 313.48 |
| income forfeited because `a` was above `t` | 43,768.22 |
| income forfeited because `a` was below `t` | 35,786.88 |
| income at `a = t` / at `a = 0.7t` (R5b) vs collected | 203,812 / 142,668 vs 124,257 |

**The accept-rate answer, in one line: there is no single right accept rate, and the number
that decides it is the Case's *fair share*, not the leaders' behaviour.** Accepting a Charge
costs `a` whichever side of `t` it sits; rejecting costs `1.5a` if it was fair and nothing if
it was not — so accept iff `P(a ≤ t) > 2/3`. The share of the Charges in front of us that
were actually fair:

| Game | 21 | 22 | 23 | 24 | 25 | pooled 21–25 | baseline (G8/10/17) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fair share = **oracle accept rate** | 12.5 % | 6.2 % | 70.8 % | 59.7 % | **83.3 %** | **67.2 %** | 67.4 % |
| our accept rate | 12.5 % | 6.2 % | 18.8 % | 16.5 % | 33.3 % | 24.0 % | 82.5 % |

**Pooled, the field sits within half a point of the 2/3 break-even (67.2 % against 66.7 %),
which means a blind Limit is a coin flip and all the value is in telling the Cases apart.**
In Games 21–22 rejecting everything was exactly optimal and we did exactly that; in Games
23–25 it was wrong and cost **28,251**. The strictness bill by Game: 0, 0, 1,849, 13,577,
12,824.

**The euros behind the recommendation.** Perfect knowledge of `t` would save **28,564** at a
67 % accept rate. A **single scalar** `b = λ × our own Charge` recovers *nothing*: the best
factor over the five Games is 0.50 and it is **1,429 worse** than what we actually did, and
`b = a` is **48,390 worse** because the leniency it buys (63,518) dwarfs the penalties it
avoids (18,621). But **one factor chosen per Game** costs 81,631 against our 92,681 — worth
**11,050, and 12,478 of that gap is pure Case-discrimination** (per-Game optima: 0.00, 0.00,
0.75, 0.50, **1.50**). So: **do not move the Limit as a level; make it move with the Case.**
And the Charge side is still the larger prize — Game 24 alone forfeited **52,562** by charging
above `t`, against 13,577 of Limit excess in the same Game.

Over the same window the three teams named as leaders scored **+17,302 (eyay), −28,738
(error404 ai), −47,834 (OPUSMOPUS)** against our **+31,576** — we are **3rd of 17 in the
Strategy 2 era** — and their losses are overwhelmingly leniency: error404 paid 102,032 on
accepted claims and OPUSMOPUS 133,159, against our 7,928.

---

## 2. Per-Game attribution

`t` brackets are exact (`t ∈ [t_lo, t_hi)`); ratios use the bracket midpoint. Our `a` is
recovered from any row where we are issuer and money moved (a wrongful rejection pays
exactly `a`); our `b` is bracketed by `max(accepted Charge) ≤ b < min(rejected Charge)`.
"side" is the **observed** side of `t` — a rejected row paying money proves the Charge was
fair, a rejected row at 0 proves it was not — so it is measured, not inferred.

### Game 21 — cracked laptop, portable electronics cover (Case 21). Net **+3,080**

| item | Line Item | `t` bracket | our `a` | `a/t` | our `b` | income | penalties | net |
| ---: | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| 1 | Diagnostic inspection of the cracked laptop | `[0, 11)` | — (never paid) | — | `b < 11` | 0 | 0 | 0 |
| 2 | Laptop screen and lower-right corner repair | `[0, 166)` | 385 | 4.63 | `b < 166` | 3,080 | 0 | **+3,080** |

Mechanisms: income 3,080, paid on accepts 0, penalties 0. Reviewer cost **0.00** — every
Charge we rejected was above `t`, so the 12.5 % accept rate was **exactly the oracle rate**.
The whole net is 8 of 16 opponents accepting a Charge 4.6× the Fair Value (R6c, the free
option, working as designed).

### Game 22 — surge on the kitchen air-conditioning unit (Case 22). Net **+14,840**

| item | Line Item | `t` bracket | our `a` | `a/t` | our `b` | income | penalties | net |
| ---: | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| 1 | Kitchen air conditioning unit – replacement incl. installation and delivery (3 pcs) | `[0, 246)` | 1,855 | 15.1 | `b < 246` | 14,840 | 0 | **+14,840** |

Reviewer cost **0.00**, accept rate 6.2 % = the oracle rate. Income is 8 acceptances of a
Charge at ~15× `t`. **This Game was won by the Limit, not by the Charge:** OPUSMOPUS
accepted 12 of 16 on the same item and paid **17,578** (net −9,578); error404 paid 9,685.

### Game 23 — stolen bicycle recovery (Case 23). Net **−820.60**

| item | Line Item | `t` bracket | our `a` | `a/t` | our `b` | income | penalties | net |
| ---: | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| 1 | Recover stolen bicycle, incl. locksmith call-out and cutting of seized lock (3 pcs) | `[143, 165)` | 175 | 1.13 | `b < 137` | 1,750 | 421 | +1,329 |
| 2 | Repair theft damage to bicycle (frame and brakes) (2 pcs) | `[374, 396)` | 578 | 1.50 | `b < 133` | 578 | **3,731** | **−3,153** |
| 3 | Labour and sundries (1 flat rate) | `[150, ∞)` | 150 | 1.00 | `b < 36` | 2,400 | 1,397 | +1,003 |

Mechanisms: income 4,727.50, penalties 5,548.10, paid on accepts 0.00 → net −820.60.
Oracle reviewer cost 3,698.73, **strictness excess 1,849.36**, leniency excess 0.
Oracle accept rate **70.8 %** against our 18.8 %.

The whole loss is penalties, but only a third of them was avoidable: 3,699 of the 5,548 is
the cost of the fair Charges themselves, which we would have paid on acceptance too. And
the Charge side gave away more than the Limit did — at `a = t` this Game collects **11,034**
against the 4,728 we took, so **6,307 was forfeited by charging above `t` on items 1 and 2**.

### Game 24 — multi-floor escape of water, billiard table and robot vacuum (Case 24). Net **+13,012.82**

| item | Line Item | `t` bracket | our `a` | `a/t` | our `b` | income | penalties | net |
| ---: | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| 1 | Leak detection and moisture survey across affected rooms (2 pcs) | `[490, 700)` | 315 | 0.53 | `b < 137` | 5,040 | 4,941 | +99 |
| 2 | Strip-out and drying of guest WC, stairwell, living room, hobby room | `[1365, 1676)` | 3,430 | 2.26 | `b < 57` | 20,580 | 4,146 | **+16,434** |
| 3 | Reinstate parquet, skirting and floor coverings on the water's path | `[240, 884)` | 3,360 | 5.98 | `b < 57` | 6,720 | 446 | +6,274 |
| 4 | Restore and refinish plasterboard ceilings and wall surfaces | `[1024, 1620)` | 2,450 | 1.85 | `b < 57` | 7,350 | 4,113 | +3,237 |
| 5 | Replace fill valve in toilet cistern | `[240, ∞)` | 154 | 0.64 | `b < 57` | 2,464 | 3,027 | −563 |
| 6 | Final site cleaning | `[91, 121)` | — | — | `b < 91` | 0 | 136 | −136 |
| 7 | Billiard table inspection, disassembly, re-covering and reassembly (3 pcs) | `[922, 1080)` | 1,085 | 1.08 | `b < 240` | 4,340 | **9,470** | **−5,130** |
| 8 | Replace billiard cloth, cue sets and overhead lighting fixture (3 pcs) | `[1072, 1505)` | 1,505 | 1.17 | `b < 240` | 4,515 | **10,022** | **−5,507** |
| 9 | Specialist cleaning and removal of water-damaged rug (2 pcs) | `[258, 290)` | 290 | 1.06 | `b < 167` | 2,034 | 3,365 | −1,332 |
| 10 | Electrical inspection of robot vacuum cleaner | `[103, 150)` | 150 | 1.19 | `b < 36` | 300 | 1,066 | −766 |
| 11 | Replacement robot vacuum cleaner (total loss) | `[0, 162)` | 402 | 4.97 | `b < 162` | 402 | 0 | +402 |

Mechanisms: income 53,745.00, penalties 40,732.18, paid on accepts 0.00 → net +13,012.82.
Oracle reviewer cost 27,154.79, **strictness excess 13,577.39**, leniency 0. Oracle accept
rate **59.7 %** against our 16.5 %. Income at `a = t` would have been **113,859** and at the
R5b target `a = 0.7t` **79,701**, against 53,745 collected — **52,562 forfeited by charging
above `t`**, four times the Limit's avoidable cost.

### Game 25 — cellar leak, five trades, 15 Line Items (Case 25). Net **+1,464.05**

The first Game in this window where our Limit was **not** pinned at ~0, and the first where
the Case is ordinary covered trade work rather than padded items: **83.3 % of the Charges we
reviewed were fair.**

| item | Line Item | `t` bracket | our `a` | `a/t` | our `b` | income | paid | penalties | net |
| ---: | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 1 | Skilled worker hours (8 hrs) | `[629, ∞)` | 429 | ≤0.68 | `b < 256` | 6,871 | 0 | **8,644** | **−1,773** |
| 2 | Material for the work | `[118, 139)` | 59 | 0.46 | `b < 41` | 937 | 0 | 771 | +166 |
| 3 | Vehicle costs | `[81, ∞)` | 59 | ≤0.73 | `b < 24` | 949 | 0 | 1,011 | −61 |
| 4 | Indoor leak detection | `[471, ∞)` | 214 | ≤0.45 | `[206, 218)` | 3,429 | 825 | 3,764 | **−1,161** |
| 5 | Room drying 30 m² | `[425, 486)` | 359 | 0.79 | `[273, 360)` | 5,738 | 779 | 1,783 | +3,176 |
| 6 | Room dryer unit | `[408, 524)` | 198 | 0.42 | `b < 47` | 3,167 | 0 | 3,790 | −623 |
| 7 | Wet insulation wool from basement | `[198, 256)` | 76 | 0.34 | `b < 65` | 1,220 | 0 | 2,212 | −992 |
| 8 | Profipress elbow 90° copper 28 mm (5 pcs) | `[82, 125)` | 19 | 0.18 | `b < 43` | 304 | 0 | 1,057 | −753 |
| 9 | Transition piece 15×19 mm (3 pcs) | `[65, 124)` | 11 | 0.12 | `b < 15` | 176 | 0 | 519 | −343 |
| 10 | Helper hours (5 hrs) | `[229, 238)` | 205 | 0.88 | `[202, 212)` | 3,287 | 1,046 | 1,002 | +1,240 |
| 11 | Service technician hours (5.5 hrs) | `[449, 471)` | 306 | 0.66 | `[266, 328)` | 4,888 | 643 | **4,519** | −274 |
| 12 | Vehicle costs (2 pcs) | `[163, ∞)` | 73 | ≤0.45 | `[70, 80)` | 1,164 | 284 | 1,111 | −232 |
| 13 | Skilled worker hours (14 –) | `[1097, ∞)` | 865 | ≤0.79 | `[802, 900)` | 13,838 | 4,038 | **7,405** | +2,394 |
| 14 | Material costs | `[0, 59)` | 118 | 4.03 | `[93, 136)` | 948 | 313 | 0 | +634 |
| 15 | Vehicle costs | `[81, ∞)` | 59 | ≤0.73 | `b < 24` | 949 | 0 | 884 | +65 |

Mechanisms: income 47,864.32, paid on accepts 7,928.45, penalties 38,471.82 → net +1,464.05.
Oracle reviewer cost 33,262.85, **strictness excess 12,823.94**, leniency excess 313.48.
Accept rate 33.3 % against an oracle rate of **83.3 %**.

Two things flipped here relative to Games 21–24. First, **the Charge side is now well
calibrated**: median `a/t` = 0.66 against the R5b target of 0.70, implied `t̂/t` median 0.95,
RMSLE 0.80 — just inside the 0.85 break-even of CLAUDE.md rule 10. Income of 47,864 against
52,874 at the `a = 0.7t` target is a 91 % capture. Second, **the Limit is now the entire
loss**: 12,824 of avoidable penalties against a net of 1,464. On the seven items where our
Limit was above 0 (4, 5, 10, 11, 12, 13, 14) we still rejected fair Charges above it — item 13
alone paid 7,405 in penalties on five fair Charges up to 1,097 while our `b` sat in
`[802, 900)`.

Item 14 is the one place we were the lenient party: `t < 59` (the description names it — *"the
drying bill includes an unexplained material surcharge"*), our `b ∈ [93, 136)` accepted it, and
that is the whole 313.48 of leniency excess in five Games.

---

## 3. Our Limit in Games 21–24 was a flat constant, and that is measurable

`paid on accepted claims = 0.00` in **all four Games**, and in Games 23 and 24 the penalty
total is *exactly* `1.5 ×` the sum of every fair Charge we reviewed (5,548.10 = 1.5 × 3,698.73;
40,732.18 = 1.5 × 27,154.79). **Measured conclusion: we accepted no Charge above 0 in any of
the 17 Line Items of Games 21–24.** The tightest brackets are `b < 11` (G21/1), `b < 36`
(G23/3, G24/10) and `b < 57` (G24/2–5).

**Inferred, not measured:** those bounds are all consistent with a single flat value, and the
only constant in the codebase that fits is `STANDARD_LIMIT = 35.0`
(`src/strategies/fast_path.py:41`), which the fast path applies as a hard cap —
`limit = min(max(limit, 0.0), median, STANDARD_LIMIT)` (`fast_path.py:182`) — and as the
default for any Line Item a Strategy did not price (`fast_path.py:198`). Our `a` on the same
items was 0.5–1.2× `t` on the covered ones, i.e. the price band was roughly right while the
Limit was two orders of magnitude below it (`b/t` = 0.02–0.44). That pattern is what a
constant looks like, not what a posterior quantile looks like.

**Against Games 21–24's field that cost almost nothing.** The comment at `fast_path.py:33-39`
measured avoidable cost as 32.38 at `b = 0`, 32.30 at `b = 30`, 34.10 at `b = 100`, 44.99 at
`b = 300`; my sweep restricted to Games 21–24 agrees — the best achievable scalar is worth
1,695. What it did cost is *attribution*: with `b` pinned to a constant, Games 21–24 do not
test Strategy 2's Limit at all.

**Game 25 breaks the pattern, and nobody wrote down why.** Seven of its 15 items carry a
Limit demonstrably above 0 (`[802, 900)` on item 13, `[266, 328)` on item 11, and so on), all
of them ~0.6–0.9× `t` — that is a posterior quantile, not a constant. Something changed
between Games 24 and 25, and [`live-changelog.md`](live-changelog.md) has **no row for Games
22–25**, so the repo cannot say what. Every conclusion in this document is therefore attributed
to "whatever was live", which is exactly the failure mode that file exists to prevent.

---

## 4. The accept-rate question, answered with numbers

### 4.1 The bar is 2/3, not the leaders' accept rate

Accepting a Charge costs `a` whether or not it was fair. Rejecting costs `1.5a` if it was
fair and nothing if it was not. So accept iff `P(a ≤ t) > 2/3`. The relevant question is
never "what rate do the leaders run" but "what share of the Charges in front of us are fair,
and can we tell which".

| window | fair share of the Charges we reviewed | verdict for a blind reviewer |
| --- | ---: | --- |
| Games 8, 10, 17 (baseline) | **67.4 %** (701/1040) | exactly at break-even |
| Games 21–24 | **52.9 %** (144/272) | reject everything |
| Game 25 alone | **83.3 %** (200/240) | accept nearly everything |
| **Games 21–25 pooled** | **67.2 %** (344/512) | **a coin flip** |

The fair share is not a property of the field, it is a property of the **Case**: Games 21–22
were Cases whose priced items are worth ~0 while everyone charged 4–16× `t`, Game 25 was
ordinary covered trade work where almost every Charge was fair. Pooled it lands on the
break-even, so **a blind Limit — at any level — is worth nothing, and a Limit that reads the
Case is worth 28,564.** That is the whole answer, and it is why our 6–33 % accept rate is
neither the pathology nor the virtue it looks like on its own.

### 4.2 What strictness cost, and what accepting more would have cost

Measured, per Game, against the oracle that accepts exactly the fair Charges:

| Game | our accept rate | oracle rate | our reviewer cost | oracle cost | **strictness excess** | leniency excess |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 21 | 12.5 % | 12.5 % | 0 | 0 | **0** | 0 |
| 22 | 6.2 % | 6.2 % | 0 | 0 | **0** | 0 |
| 23 | 18.8 % | 70.8 % | 5,548 | 3,699 | **1,849** | 0 |
| 24 | 16.5 % | 59.7 % | 40,732 | 27,155 | **13,577** | 0 |
| 25 | 33.3 % | 83.3 % | 46,400 | 33,263 | **12,824** | 313 |
| **total** | **24.0 %** | **67.2 %** | **92,681** | **64,116** | **28,251** | **313** |

And the cost of accepting more, from the sweep `b = factor × our own Charge` replayed against
the real Charges and their observed side of `t` (`--sweep`):

| factor | G21 | G22 | G23 | G24 | G25 | total cost | strictness | leniency | accept rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00 | 0 | 0 | 5,548 | 40,732 | 49,894 | 96,175 | 32,058 | 0 | 20 % |
| 0.25 | 0 | 246 | 5,464 | 39,848 | 49,783 | 95,340 | 30,978 | 246 | 23 % |
| **0.50** | 343 | 246 | 4,478 | 39,519 | 49,525 | **94,110** | 24,506 | 5,488 | 34 % |
| 0.75 | 813 | 2,271 | 4,301 | 66,715 | 47,885 | 121,984 | 18,467 | 39,401 | 48 % |
| 1.00 | 2,148 | 3,830 | 5,184 | 84,552 | 45,357 | 141,071 | 13,437 | 63,518 | 60 % |
| 1.50 | 4,861 | 23,722 | 6,254 | 96,250 | **37,811** | 168,899 | 2,885 | 101,898 | 81 % |
| ∞ (accept all) | 4,861 | 23,722 | 7,583 | 106,264 | 45,620 | 188,051 | 46 | 123,889 | 95 % |
| **ACTUAL** | 0 | 0 | 5,548 | 40,732 | 46,400 | **92,681** | 28,251 | 313 | 24 % |

**So: the optimal accept rate against this field, right now, is 67 % — but only with a Limit
that reads the Case, and it is 0 % / 0 % / 69 % / 42 % / 75 % Game by Game.** The euros:

- **Perfect knowledge of `t`** → 64,116 instead of 92,681, i.e. **28,564 saved** at a 67.2 %
  accept rate. That is the ceiling.
- **One factor per Game, chosen with hindsight** (0.00, 0.00, 0.75, 0.50, 1.50) → 81,631,
  **11,050 saved**, accept rates 16/12/69/42/75 %.
- **One factor for all five Games** → the best is 0.50 at 94,110, which is **1,429 *worse*
  than what we actually did.** A single number buys nothing.
- **Being generous** → `b = a` costs 141,071, **48,390 worse**; accepting everything costs
  188,051, **95,370 worse**.

The gap between the per-Game optimum and the best global factor is **12,478 — that is the
price of not telling the Cases apart**, and it is the largest Limit-side number in this
analysis. It is also the same information the Charge side needs, which is why the fix belongs
in the coverage/Fair Value estimate and not in a constant.

### 4.3 The field, on the same Line Items

Games 21–25 pooled, every team scored the same way (`--field`):

| team | net | accept rate | income | paid on accepts | penalties |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codacabana | +42,214 | 53.7 % | 127,323 | 32,450 | 52,659 |
| TakeTheMoneyAndRun | +36,881 | 41.2 % | 137,752 | 48,254 | 52,618 |
| **Bin busy (us)** | **+31,576** | **24.0 %** | 124,257 | **7,928** | 84,752 |
| eyay | +17,302 | 28.5 % | 135,024 | 42,478 | 75,244 |
| TBD | +10,474 | 53.1 % | 118,275 | 51,823 | 55,978 |
| Oasis | +167 | 66.0 % | 94,699 | 70,427 | 24,105 |
| Teamers | −26,003 | 83.6 % | 143,193 | 161,316 | 7,880 |
| error404 ai | −28,738 | 50.4 % | 130,389 | 102,032 | 57,095 |
| OPUSMOPUS | −47,834 | 68.2 % | 104,979 | 133,159 | 19,653 |
| makalu | −101,502 | 10.7 % | **0** | 0 | 101,502 |

We are **3rd of 17 in the Strategy 2 window** and all three teams the brief calls leaders are
below us. Their 63–65 % accept rate is a whole-tournament figure from the earlier regime; over
Games 21–25 error404 paid 102,032 on accepted claims and OPUSMOPUS 133,159, against our 7,928.
Per Line Item the ratios are instructive — Game 24 item 2 (`t ≈ 1,520`): we charged 3,430 with
`b < 57`, eyay charged 2,902 with `b ∈ [1365, 1676)` (`b/t ≈ 1.0`, the best-calibrated Limit in
the field), OPUSMOPUS 3,610 with `b ∈ [3500, 5969)` (`b/t ≈ 3.1`, three times Fair Value).
eyay's Limit is genuinely good and it still cost them 62,259 in Game 24 against our 40,732,
because accepting fair Charges is itself expensive.

**Caveat on causation.** Strictness alone does not win: makalu accepts 10.7 % and scores
−101,502 because its income is 0, and Claims Renaissance accepts 35.9 % and scores −50,591 on
income of 46,379. A low accept rate only pays when the Charge side is alive — ours produced
124,257 of income, which is the actual difference. Symmetrically, Teamers accepts 83.6 % on the
*highest* income in the field (143,193) and still loses 26,003.

---

## 5. The items that cost real money, with the clause

Repo rule: a number without its Case is a symptom without a diagnosis. Every item below cost
more than ~1,000. Note that **all of them cost it as Reviewer**, not as Issuer — the diagnosis
of each is "the item was covered and worth roughly what we charged for it, and we rejected the
field's fair Charges for it anyway".

**Game 24 items 7 and 8 — the billiard cluster (−5,130 and −5,507).** Covered household
contents, and the Fair Values (`t ≈ 1,001` and `t ≈ 1,288`) are close to our Charges (1,085 and
1,505 → `a/t` 1.08 and 1.17). The cluster is capped as a unit: *"Where the amount applies per
item, it covers everything belonging to that item. Accessories serving the item — its playing
or working surface and the covering of that surface, the implements and pieces used with it,
lighting mounted above it or on it … are included within the amount and are not payable in
addition to it"* (4.8.2), and *"The amount likewise covers the ancillary work performed on such
an item: inspecting it, dismantling it, moving it, cleaning it, re-covering it, levelling,
realigning and reassembling it … All items of cost relating to one such item are added
together, whoever invoices them and under whatever description, and the amount is applied once
to that total"* (4.8.3). Our combined Charge across the two items (2,590) sits 13 % above the
combined `t` (2,289) — the Charge side read this well. **The 10,637 lost here is entirely the
Limit**: `b < 240` against `t ≈ 1,000–1,300`, so we paid 1.5× every fair Charge on both
items. This also confirms `case-findings.md` V10 (sub-limit aggregation) on settled data:
Case 08 spread the same cluster over six Line Items and Case 24 over two, with comparable
totals. (Ten fair Charges rejected on item 7, eleven on item 8.)

**Game 23 item 2 — repair theft damage to bicycle (−3,153).** `t ∈ [374, 396)`; we charged 578
(`a/t` 1.50) *and* set `b < 133`, so we were wrong in both roles on the same item: forfeited
income above `t` and then paid 3,731 in penalties on ten fair Charges between 133 and 374.
Cover is not the issue — theft cover reaches *"the physical damage done to the item in the
course of the theft … and the damage found on it when it is recovered"* (2.3.1(b), with 2.3.2
directing a recovered item to 7.1.1(b)), and cycles are named insured property (4.2.2
Mobility equipment: *"Cycles and comparable means of personal transport propelled by muscle
power …"*). The error is level, not coverage: for an item whose value *"has fallen to a
substantial extent below the replacement value — in particular through age, wear or technical
obsolescence — the current value applies in place of the replacement value"* (6.2.2), and we
charged 1.5× the settled `t`.

**Game 24 item 1 — leak detection and moisture survey (4,941 in penalties, net +99).**
Covered, `t ∈ [490, 700)`, and our Charge of 315 was *under* the bracket (`a/t` 0.53) — good
income (5,040 from all sixteen opponents, since a fair Charge is collected even from the
rejecters). The penalties come from the same `b < 137` against ten fair Charges up to 490.

**Game 24 item 5 — replace fill valve in toilet cistern (−563, 3,027 in penalties).** Worth
recording because the *reading* points the other way: the failed valve is the source of the
escape of water, and a plausible reading excludes the source component. Settled data says
`t ≥ 240` — it is covered, and paid. **Where the settled Fair Value exists it outranks anyone's
reading of the policy** (CLAUDE.md rule 2).

**Game 24 item 3 — reinstate parquet, skirting and floor coverings (+6,274, but `a/t` 5.98).**
The largest single Charge-side error in the window: we charged 3,360 against `t < 884`. Two
clauses set the ceiling. The enlargement of the wetted area by the robot vacuum is only
indemnified where *"the policyholder demonstrates that the enlargement could not reasonably
have been prevented"* (7.1.11, and 3.3(j)) — the household was out, so it is indemnified here,
but the indemnity is *"confined to the area that the insured event would have affected without
the intervening factor"* when it is not. And unaffected floor does not come along:
*"Where only part of a single continuous surface was affected, indemnity extends to the cost of
treating the adjoining unaffected sections of that same surface only where a replacement
material corresponding to the original is no longer obtainable and a visible discontinuity
would otherwise remain"* (7.1.6). A flat-rate "on the water's path" line is priced as the
affected area only, and Case 08's equivalent items settle in the same place (`Renew parquet
floor`, `t ∈ [45, 130)`).

**Game 24 item 11 — replacement robot vacuum, total loss (`t < 162`, we charged 402, +402).**
Correctly treated as near-worthless. The clause is explicit: *"the operation of a movable
appliance or device after it has come into contact with escaping water, insofar as what is in
question is the damage that the appliance or device sustains to itself"* is excluded (3.3(i)),
and 7.1.11 repeats it — *"The damage that the intervening appliance or device sustains to
itself is not indemnified in either case"*. Item 10, the **inspection** of the same vacuum, is
covered (`t ∈ [103, 150)`) — the trap-pair `case-findings.md` flagged on Case 08, now confirmed
on Case 24.

**Game 22 item 1 — kitchen air-conditioning unit (+14,840).** Our best Game, and the reason is
a coverage boundary, so it needs its clause. The unit's position is *not* a ground of exclusion:
*"an affected item does not fall outside the cover because of the room it serves, its position
in that room, its proximity to another appliance or fitting"* (7.1.5) — the classic Case 7 bait,
and reading it as an exclusion is a known error. But the **peril** does not reach this damage:
the policy insures *"Overvoltage caused by lightning — damage arising through overvoltage,
overcurrent or short circuit, brought about by a lightning discharge or by other atmospheric
electricity"* (2.3.3), and the description reports a plain *"electrical surge"* with no
lightning and no storm. `t < 246` on a three-unit replacement is consistent with `t = 0`
(**inferred** — the bracket has no lower bound above 0, so `t = 0` is possible but not proven).
On that reading, our 1,855 was a free option that eight opponents paid, and OPUSMOPUS's
17,578 payout was the mirror image.

**Game 25 items 1 and 13 — skilled worker hours (−1,773 with 8,644 in penalties, and +2,394
with 7,405).** The two labour lines are the largest single penalties in the whole window, and
neither is a coverage question: they are the trade hours of the covered repair, admitted as
*"the labour of the trades engaged, at rates customary for that trade and locality"*
(7.1.7(g)), and both have `t` **above** our own Charge (`t ≥ 629` against `a = 429`;
`t ≥ 1,097` against `a = 865`). We rejected twelve fair Charges on item 1 (up to 629) and five
on item 13 (up to 1,097) with a Limit at ~256 and ~850. **Pure Limit loss on items whose price
we had essentially right** — item 1's `b < 256` is the more damaging of the two, at 0.41× a
`t` we ourselves estimated at ~613 (`a/0.7`).

**Game 25 item 4 — indoor leak detection (−1,161, 3,764 in penalties).** Same shape: `t ≥ 471`,
we charged 214, our Limit `[206, 218)` — the Limit sat at 0.45× `t` while the identical item in
Game 24 settled at `t ∈ [490, 700)`. **This is the strongest single argument for Price Memory
on the Limit side:** the same Line Item description had already settled one Game earlier with a
bracket we could have read off the leaderboard.

**Game 25 item 14 — material costs (the only leniency in five Games, 313).** `t < 59`; we
charged 118 and set `b ∈ [93, 136)`, so we accepted a surcharge the *description itself*
flags — *"the drying bill includes an unexplained material surcharge"* — and the policy
excludes: *"general administrative, handling or processing charges levied in addition to
itemised labour and materials"* (7.1.8(b)). A named red flag
in the damage description should force `b = 0` on the matching Line Item; that is a
deterministic rule and it is not being applied.

---

## 6. Baseline: the three worst pre-Strategy-2 Games

Same script, same identity, residual 0.00.

| Game | items | income | paid on accepts | penalties | net | accept rate | oracle rate | strictness excess | leniency excess |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 39 | 3,429 | 83,503 | 0 | **−80,074** | 95.0 % | 67.3 % | 0 | **45,567** |
| 10 | 6 | 5,300 | 0 | 65,806 | **−60,506** | 40.6 % | 66.7 % | **21,935** | 0 |
| 17 | 20 | 20,580 | 70,736 | 13,633 | **−63,789** | 70.6 % | 67.8 % | 4,544 | 14,954 |

Read against Games 21–25 this is the whole arc in one table. Game 8 is the open tap: `b`
above `t` on 39 items, 16 of 16 acceptances on most of them, 45,567 of pure leniency. Game 10
is the default submission — the Limit at 0 with almost no Charge, so 21,935 of strictness
excess *and* 117,338 of forfeited income. Game 17 is the `max(coverage, 0.9)` floor. Note the
size of the income column in all three: 3,429, 5,300, 20,580 against Fair Values summing into
six figures. **In every losing Game, pre- and post-Strategy 2, the Charge side was the larger
error; the Limit was just the more spectacular one.** Games 21–25 collect 124,257 of income
against 29,309 across those three — that, and not the accept rate, is what turned the sign.

---

## 7. Prioritised list of what to change

1. **Do not move the Limit as a level — make it move with the Case.** Measured: the best global
   factor is *worse* than what we do now (−1,429), one factor per Game is worth 11,050, and
   perfect per-item knowledge is worth 28,564. The whole Limit-side prize is discrimination,
   and 12,478 of the 28,564 is available from Case-level discrimination alone. *(measured)*
2. **Fix the Charge level on the flat-rate lines — 52,562 was forfeited in Game 24 alone.**
   Median `a/t` was 1.18 in G24 and 1.13 in G23 against the R5b target of 0.70 (implied
   `t̂/t` 1.68, RMSLE 1.08 — CLAUDE.md rule 10's σ, above the 0.85 break-even). Game 25 shows
   this is fixable and may already be fixed: median `a/t` 0.66, RMSLE 0.80, 91 % of the
   `a = 0.7t` income captured. Confirm it holds on the next multi-trade Case. *(measured)*
3. **Stop pricing flat-rate and grouped lines like itemised ones.** Every Charge above 2× `t`
   in this window is a `1 flat rate` or a grouped multi-thing line (G24 items 2, 3, 4; G23
   item 2). A flat rate is a whole-job envelope the policy then confines to the affected area
   (7.1.5, 7.1.6) or to a capped cluster (4.8.2, 4.8.3). *(inferred from 6 items; a rule, not
   yet a constant)*
4. **Feed settled brackets back into the Limit (Price Memory on the `b` side).** Game 25 item 4
   (leak detection, `t ≥ 471`) is the same Line Item as Game 24 item 1 (`t ∈ [490, 700)`), one
   Game earlier, and we set `b ≈ 212` on it and paid 3,764. The bracket was public before the
   Game started. Same for the billiard cluster (Case 08 → Case 24) and the robot vacuum.
   *(measured on 3 repeated items)*
5. **Force `b = 0` on Line Items the damage description itself flags.** Case 25's description
   names three: the unexplained material surcharge, the duplicated waste disposal, the
   unrelated attic plaster. We accepted the first (item 14, `t < 59`) — the only leniency in
   five Games. Cheap, deterministic, and 7.1.8(b)/(c) back it. *(measured, small)*
6. **Add the missing rows to `live-changelog.md` for Games 22–25.** Every conclusion here is
   attributed to "whatever was live"; the Limit changed materially between Games 24 and 25 and
   the repo cannot say why. This is the difference between a result and an anecdote.
7. **Re-measure the fair share after every Game.** 52.9 % over Games 21–24, 83.3 % in Game 25,
   67.4 % in the baseline — this is the number that decides the Limit, it swings by 30 points
   between Cases, and CLAUDE.md rule 9 says it will not survive a phase boundary.
   `analyse_game.py --games 21-` prints it.

---

## 8. What is measured and what is inferred

**Measured** (from settled Transactions, self-checked to the cent): every `t` bracket; our
`a` and `b` brackets; income, cash paid on accepts, penalties, and the net per Game and per
Line Item; the observed side of `t` for **425 of the 512** Charges we reviewed (the other 87
were accepted by every reviewer, or are a Charge of 0, and carry no evidence — they fall back
to the bracket midpoint); accept rates and reviewer costs for every team; the fair share
(52.9 % over Games 21–24, 83.3 % in Game 25, 67.2 % pooled, 67.4 % in the baseline Games);
every sweep number.

**Inferred:** that our live Limit in Games 21–24 was the constant 35 rather than some other
value below the bounds; that `t = 0` on Game 22 item 1 (the bracket allows any `t < 246`) and on
Game 21 item 1 (`t < 11`); the reading of which clause set each Fair Value — the clauses are
quoted verbatim, but the generator's arithmetic is not published, so a clause is an explanation
and not a proof; and the claim that the field's leniency, rather than something else, is what
put all three named leaders behind us in this window.

**Known limits of the sample.** Five Games, 32 Line Items, 512 reviewed Charges. Game 21 has
two Line Items and Game 22 has one, so those Games are single anecdotes; Games 24 and 25 carry
81 % of the reviewed Charges between them. Eight brackets have no upper bound (G23 item 3,
G24 item 5, G25 items 1, 3, 4, 12, 13, 15), so `a/t` and `b/t` there use `t = t_lo` and are
*upper* bounds on the ratio — which means the Game 25 undercharging is if anything understated.
The sweep in §4.2 changes only the Limit: it holds the field's Charges and our own Charge fixed,
so it cannot say what happens once we stop overcharging. And five Games is a sample in which
one Case type (Game 25's ordinary trade work) moved the pooled fair share by 14 points; treat
the pooled numbers as provisional and re-run after every Game.

---

Companion work: [`scripts/accept_limit_sweep.py`](../../../../../scripts/accept_limit_sweep.py)
sweeps the pricing constants (`limit_ceiling`, `limit_quantile`, `coverage_floor`) through the
same replay; this document and `scripts/analyse_game.py` are the ground-truth attribution and
Case diagnosis the constants have to answer to.
