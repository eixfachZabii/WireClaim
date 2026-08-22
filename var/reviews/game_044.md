<!-- scripts/review_game.py · model sonnet · 2026-08-22T22:07:21Z -->

### Review — Game 44

- **what happened**: Net +28,902.82 (income 115,984.36, penalties 63,900.09). 85% of the penalty (54,534.84) sits on item 1, the stolen watch — tagged "ok" by the auto-classifier, not on the two items it flagged.
- **stage**: charge-far-below-t — charge and limit were both set to 4,738.18 against a confirmed Fair Value floor of `t ≥ 9,361.36` (unbounded above); the low Limit then wrongfully rejected fair claims priced near the true value.
- **case evidence**: policy.txt 4.2.2 — "in the absence of such a schedule the per-item sub-limit applies whatever the actual value of the item, and whatever documentary evidence of a higher value is produced" — and 11.1 confirms "no separate valuables schedule... forms part of this contract." The watch is priced at full per-item value, not a discounted guess; our median estimate (6,839.96) undershot the confirmed floor before the 0.7× factor was even applied.
- **verdict**: signal — single item, unambiguous direction (estimate below `t`, not above — the opposite of every logged failure mode so far), 85% of the Game's penalty.
- **candidate**: across settled Games, does an "ok"-tagged item with `penalties_here > 0` correlate with `price_high` (posterior top) sitting below the eventual `t_lo`? If so, the taxonomy is missing an "estimate-too-low" stage and `cost_by_stage` is undercounting it.
