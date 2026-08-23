"""Narrow, auditable constants for the tail-aware live comparison."""

STRATEGY_NAME = "strategy4"

# A conflict needs a material disagreement, not ordinary estimator noise.
CONFLICT_RATIO = 3.0
TAIL_THRESHOLD = 1_000.0

# Two independent current-Case readings must both stay well above Price Memory and agree
# with one another before Strategy 4 changes Strategy 2's numbers.
CONFIRMATION_RATIO = 2.0
AGREEMENT_RATIO = 2.0

# Mixture weights from the isolated experiment. These are not promoted live constants:
# Strategy 4 remains comparison-only until settlement evidence supports them.
TAIL_PROBABILITY = 0.70
TRUSTED_TAIL_LIMIT_CEILING = 0.75

# The extra adjudication happens after Strategy 2. It must leave the same final PUT reserve
# and is skipped outright if fewer than this many seconds remain.
MIN_ADJUDICATION_SECONDS = 1.0

# Send a Line Item for a second reading whenever Strategy 2's own estimate is at least this
# large, whether or not Price Memory spoke -- **for the record only, never to reprice.**
#
# The gates above are so narrow that this track has been a no-op: nine Games traced, **zero
# conflicts detected, zero items repriced**, which is why it ties Strategy 2 to the cent every
# Game. They also require a memory hit, so the estimates that have actually cost us could never
# reach them -- Game 67's "Renew boiler system" at 13,730 against a settled `t < 33` and Game
# 68's ring at 8,000 against `t in [2421, 2850)` were both `C:model` alone.
#
# 2,000 is where the record says the estimator is least trustworthy and the stakes are highest:
# of the 23 settled Line Items whose `t_hat` cleared 2,000, **14 turned out to be worth under
# half that** (H16). It selects roughly one Line Item every other Game, so the extra call is
# cheap, and it runs after Strategy 2 has already yielded, so it cannot delay a Submission.
#
# Nothing is repriced on this path and that is deliberate for a first step. `_find_conflicts`
# passes the same Evidence as both the incumbent and the model reading, so `_confirms_tail`
# cannot fire -- it requires the model to sit at twice the incumbent. The Proposal is therefore
# identical to Strategy 2's, and the entire product is `adjudication_median` in
# `var/strategy4/game_NNN.json`, which can be scored against the settled Fair Value once the
# Game closes. Buy the evidence first; change the numbers only if it earns it.
LARGE_ITEM_REREAD_THRESHOLD = 2_000.0

__all__ = [
    "AGREEMENT_RATIO",
    "CONFIRMATION_RATIO",
    "CONFLICT_RATIO",
    "LARGE_ITEM_REREAD_THRESHOLD",
    "MIN_ADJUDICATION_SECONDS",
    "STRATEGY_NAME",
    "TAIL_PROBABILITY",
    "TAIL_THRESHOLD",
    "TRUSTED_TAIL_LIMIT_CEILING",
]
