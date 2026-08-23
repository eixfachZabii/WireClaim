<!-- scripts/review_game.py · model sonnet · 2026-08-23T01:27:54Z -->

### Review — Game 60

- **what happened**: Item 2 (TV) was charged €2,065.13 against t ≤ €588.59 — zero legitimate income on that line since no honest opponent owes above t. Item 1 (speaker) charged exactly at t_hi, no cost either way. Net €2,238 vs oracle €12,711 (~€10,473 gap).
- **stage**: charge-above-t (item 2) — the estimate priced the premium TV's own market value rather than the policy-capped standard-grade equivalent.
- **case evidence**: "Where a higher specification, a larger format, a superior material, a greater capacity or a premium range is chosen instead, indemnity is limited to the cost of an equivalent standard-grade replacement corresponding to what was in place before the loss; the difference is borne by the policyholder." (policy.txt, 7.1.9) — description.txt: "The replacement TV the owner has gone for is a bigger, higher-end model than the one that failed." This invoice line is precisely the betterment case 7.1.9 anticipates, and t_hi=588.59 vs an estimate_median of 2,244.99 reflects that gap.
- **verdict**: signal — the ~€10,473 gap clears the ~€6,275 single-game noise floor, and it matches the already-documented charge-above-t pattern rather than a new failure mode.
- **candidate**: across settled Games, do charge-above-t misses cluster on lines whose invoice/description text flags an upgrade ("larger", "higher-end", "premium") vs. the damaged item — i.e., does the evidence layer apply a 7.1.9-style betterment discount when that language is present?
