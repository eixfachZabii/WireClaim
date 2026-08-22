"""Turn evidence about a Line Item into a Charge and a Limit.

This is the only place in the codebase that decides a number we are scored on. The model
supplies evidence -- a price band and a coverage probability with a quoted clause -- and
this module supplies the arithmetic (ADR 0001: the model reads, the engine prices).

It exists partly to end a duplication: `CHARGE_FACTOR`, `LIMIT_QUANTILE` and the
spike-and-slab formula were copy-pasted into `fast_path.py` and `strategy1/strategy.py`,
and they decide the most expensive number in the pipeline.

## The two decisions, and why they are what they are

Both come out of the payoff table, measured against Games 1-14.

**The Charge.** Income is `a` whenever `a <= t`, and it is collected from *every* opponent,
because a wrongful rejection still owes the issuer `a`. Above `t` the only buyers are the
few teams with a loose Limit. Measured on our own settled Charges:

    a/t <= 1.0   -> paid by all 16 opponents  -> 1.00 x t
    a/t 1.0-1.3  -> 17% accept                -> 0.20 x t
    a/t 1.3-2.0  ->  7% accept                -> 0.15 x t

So an Overcharge forfeits ~80% of income and we never take one deliberately. The Charge
maximises `k * P(t >= k * t_hat)`, which lands at `k ~ 0.7` when the estimate has
lognormal error 0.25 and lower as the error grows.

**The Limit.** Accepting a Charge costs `a`. Rejecting it costs `1.5a` *only if it was
fair*, and nothing otherwise. So accepting is right exactly when

    a < 1.5a * P(fair)      i.e.      P(fair) > 2/3

which makes the Limit the **one-third quantile of the posterior over `t`** -- README R6's
"bottom third", derived rather than asserted.

Coverage uncertainty needs no separate branch: it is probability mass at zero. If an item
is only 50% likely to be covered, the bottom third of its posterior *is* zero, so the
Limit falls out at 0 on its own. That is the correct answer -- 40% of settled Line Items
have `t = 0`, and paying on one is a pure loss. The threshold where that happens is
`P(covered) <= 1 - LIMIT_QUANTILE`, i.e. **2/3**, not 1/3; see `COVERAGE_FLOOR`, which was
half of what the derivation asks for until Game 24.

One empirical shading on top: the 2/3 rule prices an accepted Overcharge at `a`, but the
Cap allows `min(a, c)` with `c >= 4t`, so accepting is worse than the rule assumes. The
best multiplier measured against the real Field is 0.20-0.35 of the median -- it was read as
0.5-0.7 against a simulation and has fallen every time it has been re-measured in euros --
so the Limit is capped at `LIMIT_CEILING * median` as well.

## What the payoff table said when we finally asked it

Everything above was fitted against a simulation. `scripts/tune_pricing.py` re-measures it
in euros: cached model evidence -> `price_item` -> `scripts/replay_payoffs.replay`, which
reproduces all fourteen published nets to the cent. Games 1-14, 192 Line Items. Three
results, one of which contradicts the derivation above.

**The Charge line survived.** Synthesising an *unbiased* estimator of known precision
(`t_hat = t * exp(N(0, sigma))`, band drawn to match) and optimising the multiplier against
the real Field gives 0.70 at sigma 0.25, 0.65 at 0.35, 0.60 at 0.45, 0.50 at 0.60 and 0.45
at 0.75 -- a least-squares line of `0.829 - 0.519 * sigma` against the shipped
`0.85 - 0.45 * sigma`. That is inside the measurement noise, so the constants stay. The
optimum sits far below 1 at every precision, and the penalty above it is brutal (-103k at
`a = t_hat` against +150k at `0.6 t_hat`), so the "paid by every opponent below `t`"
argument is confirmed rather than merely asserted.

**The ceiling was nearly twice too generous.** See `LIMIT_CEILING`; the fix is worth about
+1,280 a Game, and it settles the standing argument about whether the Limit belongs at the
1/3 quantile or at `1.0 x t_hat`. Re-measured over all 24 settled Games at Game 24, with
the reviewer side decomposed into what we pay on accepts versus what we save in penalties,
the same sweep prefers a *stricter* ceiling still (0.30, worth +35,726 over 23 Games and
+41,956 over Strategy 2's own Games 21-24) and the Games 15-19 reversal that had argued for
a generous one is reversed again by Games 20-24. The question "is our Limit too strict"
therefore answers **no, it is still slightly too loose** -- and the accept rate it produces,
24% on the recent Games, is a consequence of that measurement rather than a target to be
matched against the leaders' 63-65%. Copying their Limits outright is measured, in
`LIMIT_CEILING`, at 60-75k of loss over four Games.

Re-audited again at Game 26 against the first Games that actually ran the 0.30 ceiling
(`scripts/limit_audit.py`), and the verdict is unchanged but better founded: over Games
21-26 our penalties are 108,793 against 145,564 of income, which looks exactly like a Limit
set too low, and **it is not one**. Two thirds of a penalty is money we owed anyway -- a
wrongful rejection costs `1.5a` where accepting costs `a` -- so a per-item oracle Limit
`b = t`, the best any rule could do, saves only 36,791 of it, and none of that is reachable
by a multiplier: every looser ceiling buys more Overcharges than it saves in penalties
(0.30 -> 0.85 over those six Games recovers 52,272 of penalty for 54,969 of new Overcharges
and 34,848 of claims we owed). The penalised items are the ones where **our estimate is low**
-- median 0.74 x the true Fair Value -- so the Limit is not what is broken there. See
`LIMIT_CEILING`.

**The band is not calibrated, and that is the real problem.** `implied_sigma` on the
current model's evidence has median 0.375, but the estimator's actual RMSLE against the
recovered Fair Values is **0.80** -- overconfident by a factor of 2.1. Worse, the width
carries no signal: split the items by band width and the narrow third scores RMSLE 0.847
against the wide third's 0.733, i.e. slightly *backwards*. So `CHARGE_SLOPE` multiplies a
number that does not measure what it claims to. The line is right; its input is not.
Fixing the band is worth more than any constant in this file, and it belongs in the
evidence layer, not here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# The Charge maximises k * P(t >= k * median). Simulated against the settled Fair Value
# distribution the optimum falls almost linearly in the estimate's error: 0.7 at sigma
# 0.25, 0.6 at 0.5, 0.5 at 0.75. This line reproduces those three points.
#
# Re-measured in euros (`tune_pricing.py calibrate`, Games 1-14, unbiased estimator of the
# stated precision, replayed against the real Field, 5 replicas):
#
#     sigma  best a/median   this line   net at the optimum
#      0.25       0.70         0.7375              +223,134
#      0.35       0.65         0.6925              +182,852
#      0.45       0.60         0.6475              +149,496
#      0.60       0.50         0.5800               +93,772
#      0.75       0.45         0.5125               +60,200
#
# Least squares through the measured column is `0.829 - 0.519 * sigma`; the shipped line
# runs 0.04-0.06 above it, worth under 3% of net at every sigma and smaller than the spread
# between replicas. Left alone deliberately -- refitting it exactly to 0.83/0.52 was tried
# and *lost* money on both the real evidence (13,599 -> 4,397) and the unbiased simulation
# (145,169 -> 130,900), because a lower Charge also drags the Limit down through the
# `b <= a` clamp at the end of `price_item`. Two constants that look separable are not.
#
# Do NOT tune these against the real cached evidence. That surface is not a curve: the
# per-Game argmax scatters over 0.4-1.1 with no plateau (Game 10 rises monotonically to
# +49,980 at 1.1, Game 7 falls monotonically to -16,044) because the Field's Limits are
# clustered, so the total jumps whenever our Charge crosses a cluster. Any peak found there
# is a fact about sixteen specific opponents, not about pricing.
#
# ## Is the over-charging *conditional*? Measured at Game 27, and the answer is no
#
# The standing complaint against these two constants is that 19 of 46 Charges in Games 21-27
# sat above the Fair Value, that median `a/t` is 0.99 against eyay's 0.68, and that the
# unrecoverable share is ~41-51% in every window and therefore structural. A global
# multiplier is already ruled out (the note above; the replay surface over our own Charge is
# non-monotone). So the remaining question was whether the unrecoverable Charges concentrate
# in a bucket observable *at decision time*, which is something no multiplier could imitate.
# `scripts/charge_buckets.py` asks it over all 27 Games: one row per Line Item, carrying the
# evidence we had, joined to the recovered Fair Value bracket. Games 26-27 come from the
# decision log; Games 1-25 are reconstructed from the cached model evidence plus the cached
# Price Memory channel through `blend.combine` and `price_item`, i.e. what today's pricing
# would have done. 320 rows.
#
# **First, the headline number is two populations added together, and one of them is free.**
# 103 of the 320 Line Items have `t_lo = 0` -- nobody was ever owed money on them. A Charge
# there is above `t` by construction, and a rejected Overcharge costs exactly nothing, so it
# is the free option README R6c tells us to take. It accounts for **98 of the 135
# unrecoverable Charges** and, replayed, for **zero euros** of forgone income. On the 217
# Line Items that are actually worth something, this pricing over-charges **37 times (17%)
# with median `a/t` 0.68** -- the same 0.68 the comparison holds up as the target. Every
# charging team in the Field is "over" on all ten worthless items of Games 21-27, eyay
# included, and eyay's 7-of-316 "unrecoverable" is the *harness* sense of the word (rejected
# by all sixteen), where our own Games 21-27 figure is 2 of 48. `charge_buckets.py field`
# prints the whole Field both ways. Our real gap to eyay on real-money items is 0.72 against
# 0.61 over the record and 0.78 against 0.70 over Games 21-27 -- mid-field, next to Teamers
# at 1.00 and harissa eagles at 0.94, not the 0.99-against-0.68 outlier.
#
# **Second, the residual loss does concentrate, and not where `CHARGE_SLOPE` assumes.**
# Per bucket, over the 217 real-money rows: euros the oracle Charge `a = t_lo` would have
# earned and we did not, on the rows where `a > t`, and the same as a share of that bucket's
# oracle income (which controls for big items carrying big euros):
#
#     bucket                     n   a>t   share   med a/t   forgone   of oracle
#     sigma narrow < 0.35       59    12     20%      0.78    44,862         12%
#     sigma wide  >= 0.35      158    25     16%      0.65    31,781          4%
#     model only                71    16     23%      0.75    53,768         11%
#     model + memory           146    21     14%      0.68    22,874          3%
#     t_hat < 50                19     2     11%      0.58       226          2%
#     t_hat 50-500             155    24     15%      0.66    18,461          4%
#     t_hat >= 500              43    11     26%      0.80    57,955          8%
#     coverage <= 2/3           20     6     30%      0.57     9,284          5%
#     coverage 2/3-0.9          28     5     18%      0.66    10,367         15%
#     coverage >= 0.9          169    26     15%      0.70    56,991          6%
#     metered (hr/m2/day)       48     8     17%      0.72    17,905          7%
#     pcs / flat rate          158    27     17%      0.66    30,284          4%
#     quantity <= 1            144    26     18%      0.70    55,029          7%
#     quantity > 1              73    11     15%      0.64    21,613          6%
#
# Invoice unit and quantity are flat -- no signal, and that is a clean negative. Magnitude
# is weak once normalised (8% against 4%). The two real signals are the channel (model-only
# items forfeit 11% of their recoverable income, memory-backed ones 3%) and **sigma, with
# the sign inverted**: the *narrow* third over-charges more often and forfeits three times
# the share of the wide third. That is the same backwards ordering the module docstring
# reports for RMSLE (0.847 narrow against 0.733 wide), now visible in euros. `CHARGE_SLOPE`
# is discounting on noise.
#
# That is testable directly, holding the *level* fixed so it cannot be confused with the
# multiplier surface: compare a flat factor `L` against the line `(L + 0.17) - 0.45 * sigma`,
# which has the same value at the median observed sigma of 0.375 and differs only in how it
# orders the items. Deltas against the shipped constants:
#
#     L      flat L      matched line       flat, G21-27     line, G21-27
#     0.60   -18,449     -25,452                 +11,628           -7,890
#     0.64    +2,401     -29,843                 +15,718           -1,976
#     0.66   +19,434     -20,612                 +19,013           -3,502
#     0.69   +38,922        -811                 +16,749           +2,452
#     0.72   +24,863     +8,780                  +16,728           -7,278
#     0.75   +34,955     +7,134                   +8,754          -14,628
#     0.80    +6,764    +12,805                  -17,696           -9,538
#
# Flat beats the matched line in six of seven pairs on the record and six of seven on Games
# 21-27, which is the cleanest single result in this measurement: **the sigma ordering is
# not merely uninformative, it is costly.** It still is not shippable, for two reasons. The
# flat column is jagged in its own parameter (-18,449, +2,401, +19,434, +38,922, +24,863,
# +34,955, +6,764) -- it is the forbidden level surface with the sigma dispersion removed,
# not a new curve -- and it fails the held-out split (-8,363 odd->even). Nor is flipping the
# sign the answer: `0.55 + 0.45 * sigma`, which discounts the narrow bands the buckets blame,
# scores +18,657 on the record and **-10,830 on Games 21-27**. Sigma carries no usable
# ordering in either direction, which is a fact about the band and belongs to whoever fixes
# it, not to a constant here.
#
# **Third -- and this is why nothing changes here -- none of it converts into euros.** Every
# candidate below is the shipped rule times one conditional factor, replayed by
# `scripts/replay_payoffs.replay` over all 27 Games against the real Field, as a delta
# against this file's own constants on the same reconstructed evidence (+171,298 over all 27,
# +26,784 over Games 21-27 -- a counterfactual baseline, not the published nets of -315,174
# and +38,997, which were produced by older constants and, in Games 21-24, by `STANDARD_LIMIT`
# when Strategy 2 did not land; every delta below is against the counterfactual, which is the
# only comparison that isolates the rule):
#
#     rule                          all 27    G21-27      rule                  all 27    G21-27
#     model-only x0.6              -79,924   -22,882      metered x0.6         -60,010    -9,239
#     model-only x0.8              -18,407    -7,705      metered x0.9         -10,009    -2,789
#     model-only x0.9               +5,809    -2,331      qty>1 x0.6           -90,480   -20,534
#     t_hat>=500 x0.6             -144,502   -26,870      qty>1 x0.9           -13,640    -2,491
#     t_hat>=500 x0.9                 -102    -3,048      coverage<0.9 x0.6    -49,562    -3,792
#     t_hat<50 x0.6                 -2,299      -273      coverage<0.9 x0.9       -863      -363
#     model-only & big x0.8         -6,004    -7,263      model-only & big x0.9 +12,051    -1,145
#
# Every *downward* conditional multiplier loses money, in both windows, in every bucket the
# concentration points at. The reason is arithmetic rather than bad luck: 373,980 of the
# 450,622-euro gap to an oracle Charge is the **deliberate discount on the items we price
# correctly**, and any bucket wide enough to catch the 37 Overcharges also contains the
# ~180 items where `a <= t` and every euro shaved off is income given away. The 76,642 of
# forgone income is real and it is not reachable by shading a bucket.
#
# The only direction that pays in sample is *upward*, on the memory-backed items, which is
# also what the measured log errors argue for (memory 0.43 against the model's 0.80):
#
#     memory x   model x    all 27    G21-27          memory x   model x    all 27    G21-27
#       1.05        0.90   +24,464      -754            1.15        0.80   +17,980    -4,318
#       1.10        0.90   +33,519      -883            1.15        0.90   +42,197    +1,056
#       1.15        0.90   +42,197    +1,056            1.15        0.95   +26,466    +2,305
#       1.20        0.90   +27,157    +2,972            1.15        1.00   +36,387    +3,387
#       1.25        0.90   +29,916    +4,300            1.30        1.00   +13,553    +8,481
#       1.30        0.90   +19,362    +6,149            1.40        1.00   -17,977    -6,794
#       1.35        0.90    -7,833   -10,391
#
# It fails both remaining bars. It is **not monotone in its own parameter** -- the all-27
# column runs +33,519, +42,197, +27,157, +29,916, +19,362, -7,833 -- and the two windows
# want opposite corners (1.15 on the record, 1.30 on Games 21-27). Per Game, the +42,197
# peak is two Games crossing a Limit cluster: Game 7 alone is +20,037 of it and Game 1
# +8,129, both measured against the neighbouring 1.20, while Game 6 falls from +7,723 to
# -20. That is precisely the artefact the note above forbids fitting to.
#
# And it does not hold out. Fitting each family's parameter on one half of the Games and
# scoring it on the other (delta against these constants; the noise floor is 26,622 *
# sqrt(n/18), i.e. +/-22,624 on half the record and +/-16,602 on Games 21-27):
#
#     family                       odd->even   even->odd   1-20->21-27   21-27->1-20
#     sigma slope                     -8,813      +4,545       -17,696            +0
#     flat level (slope = 0)          -8,363      +4,545        +8,754          +421
#     line level (slope = 0.45)          -64      +2,267        -9,538        -3,262
#     model-only                      -7,652          +0        -2,331            +0
#     t_hat >= 500                   -24,891          +0        -3,048            +0
#     unit / quantity / coverage          +0        -498            +0          -419
#     memory & model, joint fit      +11,239     -19,092        +1,056        +5,072
#
# The joint memory/model fit -- the honest version, fitting both coordinates on the training
# half rather than freezing one at the full-sample argmax -- gives up 19,092 in one fold and
# the two positive cells are inside the noise floor. Summed over every family, the held-out
# delta is -15,354 (odd->even) and -29,279 (1-20->21-27): conditioning loses money out of
# sample in the split that matters.
#
# **So: over-charging is conditional, on the channel and inversely on sigma, and neither
# conditioning is worth a euro. Nothing is shipped.** The concentration on model-only items
# and the inverted sigma ordering are both statements about the *evidence*, not about these
# constants -- a band that does not measure its own error, and a channel whose error we know
# is twice the other's. That is the evidence layer's problem, and it is where the docstring
# already says the money is.
#
# What would falsify this and put a conditional rule back on the table: a band whose width
# actually orders the error (re-run `charge_buckets.py buckets` -- if the narrow tercile
# stops forfeiting 3x the share of the wide one, `CHARGE_SLOPE` is measuring something and
# its sign can be trusted); a memory channel covering enough items that the memory/model
# split stops being 71 rows against 146 (its held-out fold turns on a handful of Games); a
# Field whose Limits stop clustering, which would show up as the multiplier surface in the
# note above becoming monotone; or a level for a flat factor derived from something other
# than this surface -- a calibrated band would supply one, and then `CHARGE_SLOPE = 0` is the
# change the paired table above already argues for. Any of those, re-run
# `charge_buckets.py all`.
#
# One caveat on the sample, stated because it cuts the other way from the conclusion: 304 of
# the 320 rows are reconstructed from cached evidence rather than logged, only Games 26-27
# have decision logs, and the reconstruction blends a single cached model draw where the live
# path blends two prompts. The *logged* rows over-charge more often than the reconstructed
# ones (5 of 11 real-money items against 32 of 206), so the concentration measured here may
# be optimistic. It is the same sample every constant in this file was fitted on, and the
# fix is a decision log per Game rather than a different statistic.
CHARGE_INTERCEPT = 0.85
CHARGE_SLOPE = 0.45
CHARGE_BOUNDS = (0.30, 0.80)

# P(fair) > 2/3, so the Limit is the bottom-third quantile. Derived, not fitted -- and the
# derivation is sound, but on the current evidence it is not what binds. Swept on its own
# against the real Field it is worth almost nothing: every value from 0.20 to 0.90 lands
# within +/-125 euros of the shipped 1/3 over fourteen Games, because `LIMIT_CEILING` sits
# below the quantile at every band width we actually see. Kept at the derived value -- a
# constant that does not bind should be the one the theory chose, not the one a flat sweep
# happened to land on.
#
# Re-swept over all 23 settled Games it is still nearly flat *upwards* -- 0.20 to 0.90 spans
# 2,600 euros on 72,700 and every value above 0.30 is worse -- and what movement there is
# points the same way as the ceiling: 0.15 scores +86,400 against +72,588 at the derived
# 1/3, i.e. the euro-optimal quantile is *lower*, not higher. Leave-one-out picks 0.05-0.20
# in every fold of every window. Left at 1/3 anyway, because the 2/3 rule that produces it
# is exact arithmetic on the payoff table and `LIMIT_CEILING` is the honest place to express
# a Field measurement. Two knobs pulling in one direction only need one of them moved; this
# note exists so that nobody reads the flat sweep as evidence for loosening it.
LIMIT_QUANTILE = 1.0 / 3.0

# A guard against the model claiming precision it does not have. The quantile above is
# the right rule, but it trusts the band: a model returning 95-105 on an item worth 20
# would have us accept nearly the full median.
#
# This is the one constant the payoff table actually moved, and measuring it settles the
# standing question of whether the Limit belongs at the 1/3 quantile or nearer 1.0 x t_hat.
# Swept in euros over Games 1-14 with everything else at its shipped value:
#
#     ceiling   net (real evidence)   net (unbiased, sigma 0.45)
#       0.20             +31,909                      +103,373
#       0.30             +32,100                      +108,453
#       0.40             +32,393  <- argmax           +117,014
#       0.45             +31,514  <- shipped          +124,229
#       0.50             +26,993                      +129,423
#       0.60             +18,300                      +141,118
#       0.85             +13,599  <- was shipped      +145,169
#
# So the change is worth **+17,915 over fourteen Games, about +1,280 a Game**, and
# 0.20-0.45 is a genuine plateau (spread under 900 on 32,000) rather than a peak. Leave-one-
# out is unanimous on the direction: thirteen of fourteen folds trained on the other
# thirteen Games choose 0.20 and one chooses 0.45, for a held-out total of +26,581 against
# the shipped +13,599 -- an in-sample/held-out gap of 5,300 next to an 18,000 gain.
#
# The two answers are both right, of different estimators, and the difference is not bias,
# it is the *tail*:
#
#   * Given an unbiased lognormal estimator the best Limit really is ~1.0-1.15 x median, and
#     flat in sigma (1.05 at sigma 0.25, 1.05 at 0.45, 1.10 at 0.75). For that estimator
#     "1.0 x t_hat" is correct and this ceiling costs about 21,000 over fourteen Games.
#   * Ours is not that estimator. It is roughly median-unbiased (median t_hat/t = 0.97) but
#     it produces occasional catastrophic overprices at full confidence: Game 7 item 2,
#     median 2,200 against a true Fair Value of 40, coverage 0.98; Game 9 item 1, median
#     3,200 against t = 19. Those are 5-6 sigma in log space -- a lognormal does not
#     generate them. A Limit near the median accepts every opponent's Charge on such an item
#     and pays it, and the Cap has never bound (zero conflicts in 52,224 settled rows), so
#     that loss is unbounded, while a strict Limit only ever forfeits 1.5a on genuinely fair
#     Charges. Ten of fourteen Games prefer a Limit at or below 0.5 x median; the three that
#     prefer a loose one gain little.
#
# 0.45 rather than the 0.40 argmax on purpose: it is the last point of the real-evidence
# plateau and so the cheapest place to stand if somebody fixes the estimator's tail -- it
# recovers 7,200 euros of the unbiased case for 900 of the real one. When the tail is
# measured away, re-run `tune_pricing.py calibrate`; this constant should then rise toward
# 1.0, and that is a one-line change with a measurement behind it.
#
# ...and then the Field moved. Re-running the same sweep over every Case we have, the
# ordering **inverts between the old Games and the recent ones**:
#
#     sample                     ceiling 0.85    ceiling 0.45
#     Games 1-14                     +13,599         +31,514   <- the analysis above
#     Games 15-19                    +38,322         +23,210   <- the opposite
#     all 19                         +51,921         +54,724
#
# Games 17 and 18 alone account for the reversal (-8,285 and -5,681 at 0.45). Over the full
# set the two values differ by 2,802 on ~53,000, which is a coin flip, so this constant is
# not really a pricing fact at all -- it is a fact about how generous the Field currently
# is, and README R9 says a Field measurement does not survive a phase boundary. 0.85 was
# shipped on the strength of that four-Game window, "because we are paid on the Games that
# come next".
#
# ## Re-measured at Game 24, and the inversion did not survive its own next five Games
#
# `scripts/accept_limit_sweep.py` scores every settled Game (1-24) and **decomposes the
# reviewer side** instead of netting it, because the netted number hides the entire trade.
# Game 16 is held out of the totals below for comparability with the older measurements,
# not because it is broken: "Game 16's Transactions do not reconstruct" turned out to be the
# `/matrix` window bug in disguise -- the endpoint publishes a trailing twenty-Game window,
# so the harness was comparing Game 16's rows against Game 17's cell. It replays to the cent
# and including it changes the gain below by nothing (+634 of income at every ceiling).
#
#     accept_fair   accepted a <= t   we owed this anyway; rejecting it costs 1.5x
#     accept_over   accepted a >  t   pure loss -- the price of generosity
#     penalty       rejected a <= t   1.5a -- the price of strictness
#
#     ceiling   all 23 Games   Games 15-24   Games 21-24   accept rate (all / 21+)
#       0.20        +106,490       +74,560       +42,842        38.1% / 20.2%
#       0.25        +109,047       +76,212       +42,265        39.4% / 22.1%
#       0.30        +108,399       +76,278       +41,303        40.9% / 24.3%   <- shipped
#       0.35        +107,206       +75,309       +40,136        42.6% / 26.1%
#       0.45         +92,602       +61,067       +21,606        47.9% / 37.9%
#       0.60         +72,446       +54,125        +1,735        54.9% / 51.8%
#       0.85         +72,694       +59,074          -653        59.5% / 56.6%   <- was
#
# That is also the answer to "what accept rate should we run": the leaders' 63-65% is off
# the right-hand end of this table. Every point on it that pays sits between 38% and 43%
# over the whole record and between 20% and 26% on the recent Games, where the Field's
# Charges are further above `t`.
#
# Every sub-window now points the same way, including the one that produced the inversion:
#
#     Games 1-14   0.85 +13,599   0.30 +32,100   (reproduces the sweep above to 20 euros)
#     Games 15-19  0.85 +37,688   0.30 +19,639   (the four Games that bought 0.85)
#     Games 20-24  0.85 +21,386   0.30 +56,639   (the next five reverse them)
#     Games 21-24  0.85    -653   0.30 +41,303   (Strategy 2's own era, on policy)
#
# So the "regime boundary" reading of Games 15-19 was a four-Game fluctuation dominated by
# 17 and 18, not a phase change. **Shipping 0.30: +35,726 over 23 Games, +17,204 over
# Games 15+, +41,956 over Games 21-24 (+10,489 a Game).**
#
# The decomposition is the actual argument, and it is one-sided. Going from 0.30 to 0.85
# over all 23 Games buys back 222,098 of penalties -- and pays 148,065 more on fair claims
# plus **109,738 more on accepted Overcharges**. Two thirds of a penalty avoided is money
# we owed anyway, so the arithmetic is `+74,033 saved` against `-109,738 paid`: strictness
# is not forfeiting income, it is declining to buy other teams' Overcharges at face value.
#
# Reasons to trust it further than the number 0.85 it replaces:
#
#   * **It is a plateau, not a peak.** 0.20-0.35 spans 2,557 euros on 108,000 in the full
#     sample and 2,706 on 42,000 in the on-policy one. Leave-one-out picks inside 0.20-0.40
#     in every one of the 23 folds, and 0.20 or 0.25 in every 21+ fold. Its held-out total
#     is +86,774, which beats the old 0.85 (+72,673) but *loses* to fixing this constant at
#     0.30 (+108,399) -- the usual verdict on 23 samples: take the plateau, do not tune the
#     knob per Game.
#   * **It is not an artefact of censored Fair Values.** 77 of 287 Line Items have no upper
#     bracket, so `t` defaults to a *lower* bound and an accepted Charge above it is scored
#     as an Overcharge that may have been fair. Pushing every open bracket to `t = +inf`
#     (maximally generous) still prefers 0.30 by +17,668 over all Games and +38,684 over
#     Games 21-24.
#   * **The leaders' accept rate is not what makes them profitable.** Replaying our Charge
#     with each opponent's *reconstructed Limit* over Games 21-24: `error404 ai` -34,514,
#     `OPUSMOPUS` -28,250, `Teamers` -36,478 (86.8% accept), against +44,540 for the
#     strictest reviewer in the Field (`makalu`, 15.8%) and +41,303 for this constant.
#     A 63-65% accept rate costs 60-75k over four Games in *this* Field; the leaders earn
#     on the Charge side, and copying their reviewing would import the loss without the
#     income. (That comparison holds our Charge fixed, which is the point: it isolates the
#     reviewing decision from everything else that separates us from them.)
#
# Caveats worth re-reading before moving it again. The full-sample gain is 1,553 a Game,
# which is inside the 30,000-per-18-Games noise floor; only the recent windows clear it.
# 14 of 23 Games improve, 8 worsen, and G22 and G24 supply 39,000 of the 35,700 -- the sign
# test is weak even though the direction is unanimous across windows. And the unbiased
# lognormal estimator still prefers a Limit near 1.0 x median: if somebody fixes the
# estimator's tail, re-run `accept_limit_sweep.py recommend` and this constant should rise.
#
# ## Re-audited at Game 26, because the penalties looked like a Limit set too low
#
# Games 21-26 as played produced **108,793 of wrongful-rejection penalties against 145,564
# of income** -- 75% of income -- while we paid 9,124 on accepted claims. That is the
# textbook signature of a Limit that is too strict, and Games 25-26 are the *first* Games
# played with this 0.30 ceiling, i.e. the only genuinely on-policy evidence there has ever
# been for it. `scripts/limit_audit.py` re-asked the question against them. **Nothing moved,
# and the reason it did not is worth more than the constant.**
#
# All 26 Games reconstruct to the cent, so nothing is excluded -- not even Game 16, which
# older notes here held out. The windows are **disjoint** this time (1-20 against 21-26)
# rather than nested, so neither total can borrow the other's Games:
#
#     ceiling    Games 1-20    Games 21-26      all 26     accept (1-20 / 21-26)
#       0.00        +64,872        +17,441     +82,312       36.9% / 16.1%
#       0.15        +64,686        +17,727     +82,412       38.4% / 17.8%   <- 21-26 argmax
#       0.25        +67,417        +15,819     +83,236       40.6% / 20.0%   <- all argmax
#       0.30        +67,730        +15,300     +83,030       42.0% / 21.9%   <- shipped
#       0.35        +67,704        +14,720     +82,424       43.7% / 23.6%
#       0.40        +70,044         -2,772     +67,272       46.1% / 28.0%
#       0.45        +71,630         -1,287     +70,343       48.5% / 32.2%
#       0.70        +74,533        -23,396     +51,138       58.9% / 46.6%   <- 1-20 argmax
#       0.85        +73,981        -22,244     +51,737       59.6% / 47.3%   <- was shipped
#
# The two windows do disagree about the argmax -- 1-20 wants 0.70, 21-26 wants 0.15 -- and
# the instruction is to weight the recent one because we are paid on the Games that come
# next. **That is an extrapolation from six Games and is stated as one.** But it does not
# matter which way it is weighted, and that is the finding: 0.30 is within 3% of the argmax
# in *all three* windows, both argmaxes are inside the noise floor (+6,803 over 20 Games =
# +340 a Game; +2,427 over 6 = +404 a Game), and 0.00-0.35 is one flat region in every
# window. What is *not* flat is the far side: 0.35 -> 0.40 costs 17,492 over six Games, and
# 0.85 costs 37,544. The knob is flat where we stand and a cliff in the direction the
# penalties seemed to argue for.
#
# The disjoint train/test split says the same thing without a plateau argument. Train the
# ceiling on one window (plateau-smoothed argmax), score it on the other:
#
#     train 1-20  -> 0.85, scored on 21-26:  -22,244  (0.30 scores +15,300; -37,544)
#     train 21-26 -> 0.10, scored on 1-20:   +64,886  (0.30 scores +67,730;  -2,844)
#
# So the old window's preference is *catastrophic* out of sample and the recent window's is
# nearly free. Leave-one-out loses to fixing the constant in every window (+52,858 against
# +67,730 on 1-20; -6,265 against +15,300 on 21-26), which is the usual verdict on samples
# this size: take the plateau, do not tune per Game.
#
# ## The number that settles it: how much of the 108,793 is avoidable?
#
# Against a **per-item oracle Limit `b = t`** -- the best any Limit rule could ever do, since
# it accepts every fair Charge and rejects every Overcharge:
#
#     72,529  we owed anyway. Rejecting a fair Charge costs 1.5a where accepting costs a, so
#             an oracle avoiding a penalty of P still pays 2P/3. This is not a Limit problem
#             and must not be counted as one.
#     36,264  the 0.5a surcharge -- the only part strictness actually wasted.
#     +  526  paid on accepted Overcharges, which the oracle avoids outright.
#     ------
#     36,791  total oracle headroom over six Games (6,132 a Game).
#
# **So reading (2) is right: the penalties are ~2/3 unavoidable, and the remaining third is
# not reachable by this constant.** The oracle headroom is per-item; every multiplier that
# tries to capture it buys Overcharges instead. Loosening 0.30 -> 0.85 over Games 21-26 does
# recover 52,272 of penalty, and pays 34,848 more on fair claims plus **54,969 more on
# accepted Overcharges** to get it. The earlier decomposition's conclusion survives its own
# next two Games, on-policy, with the sign unchanged and the ratio worse.
#
# ## Which is at fault, the estimate or the Limit? The estimate.
#
# On the Line Items where we took penalties, our median sits at **0.74 x the true `t`**
# (0.81 over all 26 Games), and 64% of them had an estimate strictly *below* `t`. The
# ceiling that would have been needed to accept a penalised Charge, `k = their_charge /
# our_median`, has median 0.70 and p90 1.33; **30% of the penalty on Games 21-26 needs
# k > 1.0** and is therefore out of reach of any ceiling at all. Raising the multiplier to
# k ~ 0.70 to reach the median penalised item is exactly the "treating a symptom" case: it
# also raises the Limit on every item where the median is *high*, which is what turns
# +15,300 into -23,396. Anchoring the Limit on `price_high` instead of the median -- the one
# version of "too strict" that survives this -- is worth at best +2,298 over 26 Games and
# the two windows pick different multipliers for it. Inside the noise; not shipped.
#
# **Nothing is shipped here. 0.30 stays, now with on-policy evidence behind it rather than
# an extrapolation from Games 1-24.** What would falsify it: an estimator whose median stops
# sitting below `t` on the items we reject (re-run `limit_audit.py blame` -- if that ratio
# reaches ~1.0 the oracle headroom becomes reachable and this constant should rise), a
# Field that starts Charging below our estimates (watch `pay_over` at 0.45 fall toward
# `pay_fair`), or a Cap that finally binds. Any of those, re-run `limit_audit.py all`.
LIMIT_CEILING = 0.30

# Below this, the bottom third of the posterior is zero anyway; naming it makes the
# threshold visible in logs and tests rather than implicit in the arithmetic.
#
# Swept, and it is the flattest knob in the file: every threshold from 0.10 to 0.70 lands
# within 150 euros of every other over fourteen Games (0.00 costs 133, 0.75 and above cost
# 63). That is not indifference, it is the coverage signal being good enough that the
# threshold hardly matters -- at 1/3 the model calls only 7 of 116 covered items doubtful,
# against 23 of 76 uncovered ones called covered. Re-swept over all 23 settled Games it is
# just as flat: 0.00 to 0.70 spans 137 euros on 72,700.
#
# It was `LIMIT_QUANTILE`, and that was the wrong threshold -- off by a factor of two, in a
# way the flatness of the sweep hid. The posterior carries mass `1 - covered` at zero, so
# its `q` quantile is zero exactly when `1 - covered >= q`, i.e. when
#
#     covered <= 1 - q          = 2/3 at the derived quantile, not 1/3
#
# At 1/3 the branch below never fired for `covered` in (1/3, 2/3], where the correct answer
# is zero. It got there anyway, by accident: `conditional` goes negative, `_normal_quantile`
# clamps at -8, and the Limit comes out as `median * exp(-8 * sigma)` -- 5% of the median at
# sigma 0.375, 0.8% at 0.60. Small, but a clamp is not a derivation, and "the Limit collapses
# when coverage is doubtful" should be exact rather than approximately true by way of a
# saturating rational approximation.
#
# Measured, so the fix is not free-standing taste: making it exact is worth +21 euros over
# 23 Games and leaves the accept rate unchanged at 59.5% (`accept_limit_sweep.py recommend`,
# row `floor=2/3 only`). It is a clarity change with a measurement that says it costs
# nothing, which is the only kind worth making to a constant we are scored on.
#
# ## Is this cliff the real cost, rather than the ceiling? No -- and the sweep above cannot
# ## see that, which is the trap
#
# The threshold makes the Limit discontinuous: an item the model calls 60% covered gets a
# Limit of exactly zero, so *every* fair Charge on it is penalised at 1.5a. Over all 26
# settled Games **93 of 316 Line Items are collapsed this way**, and they are not harmless --
# 24 of Game 25's 148 penalised Charges and 21 of Game 26's 91 are collapsed items, carrying
# 14,347 and 2,757 euros of penalty; Game 10 alone carries 61,302.
#
# But sweeping the *threshold*, which is what the paragraph above does, cannot price any of
# that, and reading its flatness as "the cliff is cheap" would be wrong for the right-sounding
# reason. Below the floor the conditional quantile `(q - (1 - covered)) / covered` is already
# negative, `_normal_quantile` saturates at -8, and the Limit comes out as
# `median * exp(-8 * sigma)`. Lowering the threshold therefore swaps an exact zero for a
# rounding error rather than restoring a usable Limit -- which is exactly why the sweep is
# flat to a few euros from 0.00 to 0.70. **A flat sweep over a parameter that does not change
# the behaviour is not evidence about the behaviour.**
#
# To price the cliff the *rule* has to change. `scripts/limit_audit.py cliff` replaces it
# (net, against the shipped rule, at ceiling 0.30):
#
#     rule                          Games 1-20   Games 21-26     all 26
#     hard zero at 2/3 (shipped)       +67,730       +15,300    +83,030
#     hard zero at 1/2                 +67,730       +15,300    +83,030      +0
#     no collapse at all               +66,738       +15,243    +81,981  -1,049
#     b = covered x ceiling x median   +67,313       +15,291    +82,604    -426
#
# **Removing the cliff entirely loses money** -- 1,049 over 26 Games, 57 over the on-policy
# six -- and the continuous version loses too. The reason is the same one that pins
# `LIMIT_CEILING`: on a collapsed item `0.30 x median` is still below what the Field Charges,
# so un-collapsing recovers only 47 euros of the 113,238 penalty on Games 21-26 while buying
# Overcharges on the items the coverage signal was right about. The collapse pays for itself,
# barely, and it is derived, so it stays. It is not the hidden cost; the estimate is.
COVERAGE_FLOOR = 1.0 - LIMIT_QUANTILE

# Median Fair Value over the 148 settled Line Items with a bounded bracket. Used only when
# there is no band at all -- it is a prior, not an estimate, and it is deliberately low
# because our historic failure was Charging *above* `t` (median a/t was 1.06).
FALLBACK_MEDIAN = 60.0


@dataclass(frozen=True)
class Evidence:
    """What the model is allowed to say about one Line Item.

    No Charge, no Limit, no Fair Value -- a band, a coverage probability, and a spread.
    """

    index: int
    coverage_probability: float = 0.9
    price_low: float = 0.0
    price_median: float = 0.0
    price_high: float = 0.0

    def with_defaults(self) -> Evidence:
        """Fill a missing or incoherent band from whatever is usable."""
        low, median, high = self.price_low, self.price_median, self.price_high
        known = [value for value in (low, median, high) if value > 0]
        if not known:
            low, median, high = FALLBACK_MEDIAN * 0.5, FALLBACK_MEDIAN, FALLBACK_MEDIAN * 2
        else:
            median = median if median > 0 else sorted(known)[len(known) // 2]
            low = low if low > 0 else median * 0.5
            high = high if high > 0 else median * 2
            low, high = min(low, median), max(high, median)
        return Evidence(
            index=self.index,
            coverage_probability=min(max(self.coverage_probability, 0.0), 1.0),
            price_low=low,
            price_median=median,
            price_high=high,
        )


@dataclass(frozen=True)
class Price:
    charge: float
    limit: float
    sigma: float
    covered_probability: float


def implied_sigma(low: float, median: float, high: float) -> float:
    """Lognormal spread implied by a band, treating it as a ~90% interval.

    A band is the only uncertainty signal the model gives us, and the spread is what sets
    both numbers: the wider the band, the further below the median the Charge and Limit
    have to sit.
    """
    if median <= 0 or high <= 0 or low <= 0 or high <= low:
        return 1.0
    # 90% of a lognormal spans +/- 1.645 sigma in log space.
    return min(math.log(high / low) / (2 * 1.645), 2.0)


def charge_factor(sigma: float) -> float:
    """How far below the estimate to Charge, given how much the estimate can be trusted.

    A Charge at or below `t` is paid by every opponent; one euro above it earns almost
    nothing. So the wider the band, the further under the median we have to aim.
    """
    low, high = CHARGE_BOUNDS
    return min(max(CHARGE_INTERCEPT - CHARGE_SLOPE * sigma, low), high)


def _lognormal_quantile(median: float, sigma: float, quantile: float) -> float:
    """Inverse CDF of a lognormal, via a rational approximation of the normal one."""
    if sigma <= 0:
        return median
    return median * math.exp(sigma * _normal_quantile(quantile))


def _normal_quantile(p: float) -> float:
    """Acklam's rational approximation; accurate to ~1e-9 and dependency-free."""
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    a = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
    b = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00)
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def price_item(evidence: Evidence, *, confirmed_uncovered: bool = False) -> Price:
    """The whole pricing decision for one Line Item.

    `confirmed_uncovered` is for a proven exclusion — a policy clause quoted verbatim.
    It zeroes the Limit but never the Charge: an uncovered item has `t = 0`, so the
    honest branch pays nothing and a rejected Overcharge costs nothing, which makes the
    Charge a free option (README R6c). Game 3 is the proof: every Line Item was
    uncovered, two teams Charged ~100 and were paid by 2 of 16, and the rest of the field
    scored zero.
    """
    filled = evidence.with_defaults()
    sigma = implied_sigma(filled.price_low, filled.price_median, filled.price_high)
    covered = 0.0 if confirmed_uncovered else filled.coverage_probability

    # The Charge assumes the item is covered. That is deliberate and it is free: if the
    # item turns out to be worthless the Charge simply gets rejected at no cost, whereas
    # shading it down for doubt forfeits guaranteed income on everything that is covered.
    charge = charge_factor(sigma) * filled.price_median

    # The Limit reads the bottom third of the *whole* posterior, which carries mass
    # (1 - covered) at zero. At P(covered) <= 1 - LIMIT_QUANTILE = 2/3 the zero mass alone
    # fills the bottom third, so the quantile is zero outright -- see `COVERAGE_FLOOR`.
    if covered <= COVERAGE_FLOOR:
        limit = 0.0
    else:
        # Strip the zero mass, then take the quantile that leaves 1/3 of the total below.
        conditional = (LIMIT_QUANTILE - (1.0 - covered)) / covered
        limit = min(
            _lognormal_quantile(filled.price_median, sigma, conditional),
            LIMIT_CEILING * filled.price_median,
        )

    # b < a always: the Limit is a lower quantile of the same posterior than the Charge.
    #
    # Measured, and it is not free. The Charge and the Limit answer different questions --
    # "what will the Field pay me" and "what am I willing to pay" -- and nothing in the
    # payoff table requires the second to sit below the first. Releasing this clamp is
    # worth +16,421 over Games 1-14 against an unbiased estimator at sigma 0.45 (149,496
    # against 133,075), and +14,000 to +18,000 at every sigma from 0.25 to 0.75, because
    # such an estimator wants `b ~ 1.0 x median` while `a ~ 0.6 x median`. Kept anyway:
    # with today's fat-tailed estimator the Limit is held at 0.30 x median and this clamp
    # almost never binds, so releasing it buys nothing now while removing a guard rail that
    # catches genuinely incoherent bands. Revisit together with `LIMIT_CEILING`, not before.
    #
    # At the ceiling measured at Game 24 it binds *never*: the Charge factor bottoms out at
    # 0.30 (`CHARGE_BOUNDS`) and the ceiling is 0.30, so `b <= a` holds by construction on
    # every band. Worth knowing, because it also means the clamp was quietly doing the work
    # of the ceiling at the old 0.85 -- above a ceiling of about 0.80 the sweep is exactly
    # flat, because the Charge, not the ceiling, was setting the Limit.
    limit = min(limit, charge)
    return Price(
        charge=round(max(charge, 0.0), 2),
        limit=round(max(limit, 0.0), 2),
        sigma=sigma,
        covered_probability=covered,
    )
