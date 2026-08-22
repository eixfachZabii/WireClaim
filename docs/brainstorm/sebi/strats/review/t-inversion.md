# `t` inversion of *Claim to Fame* — 14 settled Games, 17 teams

Generated from the public leaderboard API. Repo untouched; all artefacts in `/tmp`.

Machine-readable companion: `/tmp/t_data.json`.

## 0. Data and the exact transaction semantics (verified, not assumed)

`GET /leaderboard/api/transactions` is **paginated** (`page_size` default 100, hard cap 1000). The first pull silently truncated every Game to ~4 Line Items; the real Games have up to **39**. Re-pulled with `page_size=1000` (+ page 2 for Game 8) → **52,224 unique rows**, and every Game has exactly `n_items x 17 x 16` rows, i.e. the record is complete.

The `amount` field is **not** "0 on every rejected row". Verified semantics:

| row | meaning | what it reveals |
|---|---|---|
| `accepted=true`, `amount=x` | I pays x, H gets x | `x = min(a, c)` — normally the Charge `a` |
| `accepted=false`, `amount=x>0` | **wrongful** rejection: I pays `1.5x`, H gets `x` | `x = a` exactly **and `a <= t`** |
| `accepted=false`, `amount=0` | rightful rejection, nothing flows | **`a > t`** |

1,979 rejected rows carry a non-zero amount, so rejected rows *do* leak both the Charge and the side of `t`. This is the whole inversion.

**Net identity check.** Summing `+amount` for the issuer and `-(amount if accepted else 1.5*amount)` for the reviewer reproduces **238 / 238** published `cells` exactly (max abs error < 1e-6). The semantics above are therefore proven, not inferred.

## 1. Reconstructed Charges `a` and Limits `b`

- Line Items across the 14 settled Games: **192** (Game 1: 18, Game 8: 39, Games 3/6: 2 ...).
- (team, Line Item) Charge slots: **3264**. Recovered exactly: **2992**; unrecoverable: **272**.
- A Charge is unrecoverable exactly when the team was rejected by *all 16* reviewers **and** every rejection was rightful (`amount=0`). For those slots we still know `a > t` and `a > max_rv b_rv`, and — decisively — they contribute **exactly 0** to every net, so they cannot be identified and do not need to be.
- No Charge conflicts: for every (Game, Item, issuer) all non-zero amounts agree, so the Cap `c` never bound anywhere in the observed data (else accepted rows would read `c` while wrongful-rejection rows read `a`).
- Limits are bracketed per (Game, Item, reviewer): `b >= max(a it accepted)` and `b < min(a it rejected)`. Full table in `t_data.json -> b_brackets` (3264 entries). `null` upper bound = accepted everything on that item.

## 2. `t` brackets — the logic

For every Line Item, from the row semantics above:
```
t >= max { a : a was WRONGFULLY rejected (rejected, amount>0) }      -> t_lo
t <  min { a : a was RIGHTFULLY rejected (rejected, amount=0), a known } -> t_hi

```

No other information about `t` exists in the data: a Charge that every reviewer accepted pays `a` on both sides of `t`, so it is payoff-invariant and carries zero information.

- Both bounds finite: **148 / 192** items.
- Lower bound only (`t_hi = inf`): **44** items. This is genuinely undetermined above — verified by setting `t = 1e12` on those items and re-simulating: nets are unchanged.
- `t_lo = 0` on **76** items (mostly policy-uncovered Line Items where `t = 0`).
- Every one of the 2,992 known Charges has its **side of `t` exactly determined** (no ambiguous cases).

### Per-Game brackets

- **G1** (18 items): 1: [122.94, inf), 2: [227.66, inf), 3: [0, inf), 4: [0, inf), 5: [0, inf), 6: [569.16, inf), 7: [182.13, inf), 8: [0, 28), 9: [409.79, inf), 10: [0, inf), 11: [0, inf), 12: [0, inf), 13: [227.66, inf), 14: [105.78, inf), 15: [606.22, inf), 16: [0, 176), 17: [0, 144), 18: [98.02, inf)
- **G2** (7 items): 1: [310, 425), 2: [0, 12), 3: [0, 43.97), 4: [555, 600), 5: [0, 43.97), 6: [0, 18), 7: [0, 21)
- **G3** (2 items): 1: [0, 100), 2: [0, 100)
- **G4** (15 items): 1: [199.25, 530), 2: [229.5, 335), 3: [532.5, inf), 4: [28, 31.88), 5: [0, 36), 6: [0, 27), 7: [0, 36), 8: [0, 38.3), 9: [0, 9), 10: [0, 45), 11: [0, 45), 12: [0, 18), 13: [0, 38.3), 14: [0, 12), 15: [0, 20)
- **G5** (17 items): 1: [402.5, 875), 2: [150, 199.25), 3: [497.94, 773.5), 4: [0, 38.25), 5: [108.44, 130.5), 6: [153, 300), 7: [130.5, 180), 8: [53.56, 114.75), 9: [42.75, 180), 10: [0, 122.4), 11: [0, 92.16), 12: [42.75, 150), 13: [150, 229.5), 14: [360, inf), 15: [300, inf), 16: [0, 42.5), 17: [42.75, 135)
- **G6** (2 items): 1: [765, 900), 2: [0, 45)
- **G7** (6 items): 1: [1232.54, 1756.44), 2: [0, 80.83), 3: [467.5, 522.36), 4: [0, 123.63), 5: [53.6, 74.18), 6: [21.98, 43.06)
- **G8** (39 items): 1: [53, 60), 2: [765, inf), 3: [200.16, inf), 4: [114.12, 132.54), 5: [0, 55), 6: [339.15, 396), 7: [200, inf), 8: [452.2, inf), 9: [454.5, 488.33), 10: [0, 84.33), 11: [368.85, 488.33), 12: [0, 1), 13: [542.64, 628), 14: [339.45, 372.78), 15: [0, 1), 16: [90, 95.58), 17: [0, 101.2), 18: [45, 105), 19: [184.32, 222.05), 20: [90, 128.41), 21: [0, 34.5), 22: [0, 24), 23: [145.48, 169.57), 24: [113.15, 130.14), 25: [573, 703.04), 26: [45, 150), 27: [60, 134.52), 28: [157.83, 183.16), 29: [45, 130.14), 30: [507, inf), 31: [89.95, 158.27), 32: [0, 38.3), 33: [401.93, 421.42), 34: [199.25, 304.24), 35: [113.05, 133.14), 36: [100, 137), 37: [210.64, 254.36), 38: [34, 45), 39: [0, 1)
- **G9** (16 items): 1: [0, 38.3), 2: [0, 1.18), 3: [0, 1.18), 4: [0, 1.18), 5: [0, 96.29), 6: [0, 1.18), 7: [81.95, 90), 8: [0, 1.18), 9: [0, 1.18), 10: [862.59, 1076.07), 11: [576.4, 600), 12: [82.31, 90), 13: [87.3, 113.4), 14: [0, 113.4), 15: [0, 113.4), 16: [0, 1.18)
- **G10** (6 items): 1: [0, 72), 2: [0, 3), 3: [7225, inf), 4: [404.11, inf), 5: [0, 38.3), 6: [0, 9)
- **G11** (22 items): 1: [357.38, inf), 2: [754.28, inf), 3: [44.08, 61.5), 4: [80.24, inf), 5: [250.13, 336), 6: [0, 57.3), 7: [19.51, 26), 8: [75.65, 103.5), 9: [224.7, 358.13), 10: [0, 99.84), 11: [0, 21.53), 13: [44, 63.25), 14: [44, 107.95), 15: [0, 6.8), 16: [32.53, inf), 17: [199, inf), 18: [94, inf), 19: [44.01, inf), 20: [379.5, inf), 21: [986, inf), 22: [69.35, 112), 23: [57.5, inf)
- **G12** (12 items): 1: [93.45, 109.78), 2: [135.66, 153.99), 3: [69, 80), 4: [119.2, 150), 5: [113.05, 121.8), 6: [232.15, 263), 7: [48.96, 92.16), 8: [200, 238.3), 9: [145.5, 160), 10: [400, inf), 11: [650.01, inf), 12: [2321.48, inf)
- **G13** (17 items): 1: [38.4, 88.19), 2: [96, 184.44), 3: [18, 38.28), 4: [8, 12), 5: [20, 600), 6: [90.44, inf), 7: [593.37, inf), 8: [386.54, inf), 9: [50.75, inf), 10: [18, inf), 11: [27.08, 150), 12: [64.46, inf), 13: [56.44, 80), 14: [0, 130), 15: [0, 130), 16: [0, 43.2), 17: [0, 12)
- **G14** (13 items): 1: [0, 130), 2: [0, 48), 3: [0, 7.12), 4: [0, 22.84), 5: [0, 25), 6: [0, 12), 7: [0, 17.48), 8: [0, 36.15), 9: [24.9, 40), 10: [130, 150), 11: [0, 6), 12: [35.51, 37.48), 13: [0, 51)

## 3. VALIDATION (independent forward simulation)

Not a re-sum of the rows: for each Game I take the reconstructed `a` (unknown ones set to +inf), a representative `b` from each bracket, a representative `t` from each bracket, `c = inf`, and re-run the full 4-branch payoff table over all `n_items x 17 x 16` ordered pairs.

| Game | items | teams reproduced exactly |
|---|---|---|
| 1 | 18 | **17 / 17** |
| 2 | 7 | **17 / 17** |
| 3 | 2 | **17 / 17** |
| 4 | 15 | **17 / 17** |
| 5 | 17 | **17 / 17** |
| 6 | 2 | **17 / 17** |
| 7 | 6 | **17 / 17** |
| 8 | 39 | **17 / 17** |
| 9 | 16 | **17 / 17** |
| 10 | 6 | **17 / 17** |
| 11 | 22 | **17 / 17** |
| 12 | 12 | **17 / 17** |
| 13 | 17 | **17 / 17** |
| 14 | 13 | **17 / 17** |

**Total 238 / 238 nets reproduced to < 1e-4.** Reproduction holds at `t = t_lo`, at the bracket midpoint, and at `t = t_hi - 1e-6`. Every bracket endpoint is **tight**: perturbing any single item to `t_lo - eps` or to `t = t_hi` breaks the reproduction (checked one item at a time, all 192 items, 0 loose bounds). So `[t_lo, t_hi)` is the exact identified set, not a guess. `c` never binds: `c = inf` reproduces everything.

## 4. Empirical `t` distribution

| statistic | conservative (all 192 items, `t_lo`) | upper (148 bounded items, `t_hi`) | midpoint (148 bounded) | `t_lo` on the same 148 |
|---|---|---|---|---|
| n | 192 | 148 | 148 | 148 |
| min | 0.00 | 1.00 | 0.50 | 0.00 |
| p10 | 0.00 | 9.00 | 4.50 | 0.00 |
| p25 | 0.00 | 36.11 | 19.14 | 0.00 |
| median | 44.54 | 93.87 | 58.95 | 20.99 |
| p75 | 199.06 | 155.06 | 126.73 | 113.08 |
| p90 | 466.20 | 422.49 | 365.49 | 318.75 |
| max | 7225.00 | 1756.44 | 1494.49 | 1232.54 |
| mean | 185.80 | 160.73 | 129.76 | 98.78 |

Caveat: the conservative column includes the 44 unbounded items at their lower bound only, and its upper tail (`max = 7225`, Game 10 item 3) is a true lower bound on a genuinely unbounded `t`. The two columns are **not** bounds on the same population — the "upper" column drops the 44 unbounded items, which are systematically the expensive ones, so it understates the tail.

### Blind fallback constants fitted on this distribution

**Blind Charge.** Maximising the risk-free part of income, `E = a * P(t >= a)` (i.e. crediting nothing for an overcharge that happens to be accepted), over the 192 `t_lo` values:

- `a* = 339` , `E[income] = 60.1` per opponent per Line Item. The curve is flat-ish: `a=200 -> 55`, `a=300 -> 59`, `a=500 -> 56`.
- On the 148 bounded items with `t = midpoint`: `a* = 356`, `E = 40.9`.
- If you instead credit acceptance-of-overcharge using the reconstructed opponent Limits, the "optimum" runs away to the top of the grid (a=7225 → E=622). **Do not use that number.** It is driven by a handful of reviewers with no observed upper bound on `b`, it ignores the Cap `c` (which never bound in the data and is therefore unmeasured), and it is exactly the mis-measured-`p(a)` trap. The defensible blind Charge is **~300–350**.

**Blind Limit.** Computed exactly, not modelled: over all 2,992 known (item, issuer) Charges with their known side of `t`, avoidable cost per issuer per item is `0.5a` if (`a<=t` and `a>b`) and `a` if (`a>t` and `a<=b`):

| b | 0 | 10 | 30 | 50 | 100 | 200 | 300 | 500 |
|---|---|---|---|---|---|---|---|---|
| avoidable cost | 32.38 | 32.36 | **32.30** | 32.90 | 34.10 | 41.06 | 44.99 | 49.45 |

- Argmin `b* = 35`, but the cost surface is **flat from 0 to ~30 and rises monotonically after**. Against *this* field, generosity is strictly punished: the field overcharges enough that a low blind Limit is nearly free. Recommended blind Limit **~30**, and never above ~50.
- Note the asymmetry this measures directly: penalties cost `0.5a`, over-acceptance costs `a`. That is why `b*` (35) sits far below `a*` (339) and below the median `t_lo` (44.5).

## 5. Where `Bin busy` money went

`t = t_lo` (conservative) throughout. `unavoidable` = what we would have paid even playing perfectly (fair Charges from opponents). `overpay` = accepted Charges that were above `t`. `penalty excess` = the `0.5a` surcharge on our wrongful rejections (the `a` part was owed anyway). `forfeit` = `16*(t-a)` on items where we charged below `t` — a risk-free, certain loss, since `a<=t` earns `16a` regardless of anyone's Limit. `overcharge loss` = `16*t - actual income` on items where we charged above `t` (negative = the overcharge paid off).

| Game | net | income | paid (accepted) | penalties | unavoidable | overpay (`b` too high) | penalty excess (`b` too low) | forfeit (`a` too low) | overcharge loss (`a` too high) | dominant mechanism |
|---|---|---|---|---|---|---|---|---|---|---|
| 8 | -80,074 | 3,429 | 83,503 | 0 | 37,936 | 45,567 | 0 | 0 | 13,044 | b too high overpay |
| 10 | -60,506 | 5,300 | 0 | 65,806 | 43,871 | 0 | 21,935 | 117,266 | -500 | a too low forfeit |
| 12 | -43,381 | 0 | 0 | 43,381 | 28,921 | 0 | 14,460 | 72,455 | 0 | a too low forfeit |
| 11 | -36,017 | 0 | 0 | 36,017 | 24,011 | 0 | 12,006 | 60,094 | 0 | a too low forfeit |
| 7 | -33,568 | 0 | 33,568 | 0 | 10,555 | 23,014 | 0 | 0 | 0 | b too high overpay |
| 9 | -21,397 | 750 | 17,334 | 4,813 | 6,896 | 13,647 | 1,604 | 0 | -750 | b too high overpay |
| 5 | -10,604 | 9,075 | 19,450 | 230 | 8,410 | 11,193 | 76 | 0 | 13,200 | a too high rejected |
| 6 | -3,940 | 1,035 | 0 | 4,975 | 3,317 | 0 | 1,658 | 11,520 | -315 | a too low forfeit |
| 13 | -2,607 | 16,800 | 3,555 | 15,852 | 13,930 | 193 | 5,284 | 2,479 | -280 | b too low penalty excess |
| 14 | -2,599 | 450 | 2,374 | 676 | 740 | 2,085 | 225 | 0 | 1,630 | b too high overpay |
| 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | b too low penalty excess |
| 2 | 722 | 5,088 | 601 | 3,765 | 3,111 | 0 | 1,255 | 8,752 | 0 | a too low forfeit |
| 4 | 3,520 | 13,935 | 6,238 | 4,177 | 4,239 | 4,783 | 1,392 | 4,032 | -2,139 | b too high overpay |
| 1 | 13,502 | 19,704 | 1,127 | 5,075 | 4,328 | 183 | 1,692 | 21,782 | -696 | a too low forfeit |

### Mechanism totals across all 14 Games

| mechanism | total | kind |
|---|---|---|
| `a` too low → forfeited income | **298,379** | opportunity cost (income we could have banked risk-free) |
| `b` too high → overpaying fraud | **100,664** | cash out the door |
| `b` too low → wrongful-rejection surcharge | **61,588** | cash out the door |
| `a` too high → rejected overcharges | **23,194** | opportunity cost |
| (unavoidable payments on fair Charges) | 190,263 | not a loss |

Realised net over 14 Games: **-276,950** (matches the leaderboard total). Realised, avoidable cash loss = overpay + penalty excess = **162,252**; the remaining ~115k of the deficit is unavoidable payments minus our (tiny) income — i.e. **we barely issued anything**.

**The single biggest number is `forfeit` = 298,379.** In eight Games we charged 0 (or near 0) on Line Items whose `t` was hundreds. Because `a <= t` earns `16a` unconditionally — a wrongful rejection still pays us — every euro of Charge below `t` is a euro certainly given away. Games 10, 11, 12 (and 6) are pure *we submitted nothing* Games: income ~0, and `b = 0` turned every opponent's fair Charge into a `1.5a` penalty. G10+G11+G12 alone = **-139,904**.

**Games 8, 7, 9 are the opposite failure:** we *did* submit, but the Limit was far too generous — G8 we paid 83,503 on accepted claims of which **45,567 was above `t`**, with zero penalties (we accepted 100%). G7: 23,014 of 33,568 paid was overpay. That is R6/rule-4 in the repo: a Limit outside the posterior is an open tap.

### Our `a` and `b` per Line Item

Full per-item table (`a`, `b_lo`, `b_hi`, `t_lo`, `t_hi`) is in `t_data.json -> bin_busy[].items`. Summary of our positioning on the 78 Line Items with a fully bounded, non-zero `t`: median `a/t = 1.06`, median `b/t = 1.16`, and only **27 %** of our Charges landed in the fair zone — the **worst of all 17 teams bar makalu**. We simultaneously charge too high to get paid and accept too high to avoid being farmed.

## 6. Who is profitable, and what does their strategy look like

Ratios below use the 78 Line Items where `t` is bounded on both sides and `t_lo > 0`; `t` = bracket midpoint, `b` = bracket midpoint. `fair %` = share of that team's Charges provably in the fair zone (`a <= t_lo`).

| team | total | games>0 | a/t p25 | **a/t median** | a/t p75 | b/t p25 | **b/t median** | b/t p75 | fair % | accept rate | income | paid | penalties |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TakeTheMoneyAndRun | 86,394 | 7 | 0.32 | **0.73** | 1.09 | 0.28 | **0.58** | 1.13 | 67% | 65% | 355,996 | 153,169 | 116,432 |
| error404 ai | 81,284 | 10 | 0.47 | **0.85** | 1.40 | 0.29 | **0.81** | 1.17 | 58% | 63% | 354,394 | 105,959 | 167,151 |
| OPUSMOPUS | 67,748 | 5 | 0.00 | **0.55** | 1.17 | 0.32 | **0.81** | 1.57 | 68% | 61% | 309,964 | 137,772 | 104,444 |
| Non Deterministic | 58,755 | 9 | 0.37 | **0.67** | 1.16 | 0.20 | **0.48** | 1.04 | 59% | 57% | 330,095 | 77,917 | 193,423 |
| eyay | 26,159 | 7 | 0.03 | **0.52** | 0.90 | 0.16 | **0.36** | 0.78 | 82% | 50% | 293,789 | 54,586 | 213,044 |
| harissa eagles | 12,729 | 7 | 0.19 | **0.61** | 1.02 | 0.30 | **0.66** | 1.00 | 72% | 56% | 280,090 | 95,558 | 171,802 |
| Codacabana | -5,796 | 10 | 0.38 | **0.88** | 1.39 | 0.22 | **0.55** | 1.13 | 55% | 58% | 258,253 | 80,700 | 183,349 |
| Alpha | -25,070 | 6 | 0.40 | **0.79** | 1.26 | 0.25 | **0.59** | 1.54 | 54% | 59% | 280,854 | 108,103 | 197,821 |
| AsianSuperNerds | -27,064 | 8 | 0.33 | **0.62** | 0.96 | 0.28 | **0.72** | 1.00 | 69% | 55% | 260,139 | 89,350 | 197,853 |
| Nullpointer Naan | -31,104 | 3 | 0.00 | **0.77** | 1.28 | 0.32 | **0.85** | 2.47 | 55% | 62% | 243,511 | 161,505 | 113,110 |
| Teamers | -94,173 | 5 | 0.21 | **0.66** | 1.23 | 0.30 | **0.84** | 1.19 | 62% | 64% | 186,494 | 73,149 | 207,519 |
| Oasis | -114,959 | 3 | 0.46 | **0.79** | 1.67 | 0.54 | **1.37** | 2.47 | 41% | 72% | 182,968 | 103,774 | 194,153 |
| Claims Renaissance | -172,753 | 3 | 0.00 | **0.00** | 0.41 | 0.11 | **0.23** | 0.49 | 87% | 49% | 107,791 | 46,739 | 233,806 |
| Trust Nobody | -178,911 | 2 | 0.00 | **0.00** | 0.06 | 0.10 | **0.21** | 0.54 | 94% | 47% | 95,088 | 34,169 | 239,831 |
| TBD | -201,022 | 2 | 0.00 | **0.00** | 0.19 | 0.10 | **0.19** | 0.34 | 91% | 44% | 94,688 | 48,766 | 246,944 |
| Bin busy | -276,950 | 3 | 0.00 | **1.06** | 2.06 | 0.37 | **1.16** | 2.52 | 27% | 69% | 75,566 | 167,751 | 184,765 |
| makalu | -290,624 | 0 | 0.00 | **0.00** | 0.00 | 0.08 | **0.14** | 0.23 | 100% | 36% | 0 | 0 | 290,624 |

### `TakeTheMoneyAndRun` (+86,394) and `error404 ai` (+81,284)

- **They are not honest players.** TTMAR keeps only 67 % of Charges in the fair zone, error404 only 58 %. Their median `a/t` is 0.73 and 0.85 — i.e. the *typical* Charge is a disciplined ~3/4 of `t` — but the p75 is 1.09 / 1.40: roughly a third of their Line Items are deliberate overcharges, priced as options that cost nothing when rejected.
- **Income is where they win, not thrift.** TTMAR income 355,996 / error404 354,394, the two highest in the field (makalu: 0, `Bin busy`: 75,566). They *always submit something*.
- **Their Limits are the tightest among high scorers.** median `b/t` 0.58 (TTMAR) and 0.81 (error404), with the lowest wrongful-rejection counts in the field (357 and 356 vs a field median of ~470). They sit just below `t`: low enough that almost no overcharge gets through, high enough that they rarely eat the 0.5a surcharge. TTMAR paid only 153,169 on accepted claims while earning 355,996.
- **The shape of the winning strategy, numerically:** `a ~ 0.7-0.9 t` on items you can price, an aggressive overcharge on the ~1/3 you judge worthless (`t = 0` items cost nothing to bluff on), `b ~ 0.6-0.8 t`, and 100 % submission uptime. Note `b < a` for both — exactly the asymmetry in section 4.
- **Counterexample worth reading:** `Oasis` (-114,959) has the *highest* median `b/t` (1.37) and the highest accept rate (72 %). Generosity, not penalties, is what sank them. `makalu` (-290,624) is the pure null submission: `a = 0` on all 192 items, income 0, 888 wrongful rejections, 290,624 paid in penalties — the "money fountain" case, and almost exactly what `Bin busy` did in Games 10-12.

## 7. What could NOT be determined

1. **`t_hi` on 44 of 192 Line Items** (Game 1 is the worst: 13 of 18 unbounded). No team rightfully rejected a *known* Charge on those items, so the data contains no upper bound. Verified undetermined, not merely unfound.
2. **272 of 3264 Charges** (8.3 %) — teams rejected by all 16 reviewers with no money flowing. Known only to satisfy `a > t` and `a > max b`. Payoff-irrelevant. `Bin busy` has 70 such slots, `Oasis` 44.
3. **The Cap `c`.** It never bound in 52,224 rows, so the data gives only `c > max observed accepted amount` per item. Any strategy that relies on a very large Charge being accepted is extrapolating past the data.
4. **Exact Limits.** `b` is bracketed between adjacent field Charges, never point-identified. Brackets are wide where the field clustered.
5. **Whether an accepted-by-everyone Charge was fair or fraudulent** — payoff-invariant, hence unidentifiable. This does not affect any net, but it means the `fair %` column is computed on the provable subset (which happens to be all 2,992 known Charges: every one of them *is* decided).
6. Games 15-100 are `scheduled`, not settled — nothing here extrapolates to them beyond the `t` distribution.
