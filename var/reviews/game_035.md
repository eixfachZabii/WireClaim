<!-- scripts/review_game.py · model sonnet · 2026-08-22T20:12:20Z -->

### Review — Game 35

- **what happened**: Net +3,300.91 (income 53,576.21 vs penalties 48,723.42). Biggest error bucket: `charge-far-below-t` at €7,455.44, ahead of `coverage-too-low` (€5,206.05).
- **stage**: charge-far-below-t — items 12/13/14 (copper elbows, transition piece) and 7/18 all charged at 11–48% of settled `t`, all routed through `["C:model"]` alone, no `B:memory` channel.
- **case evidence**: policy.txt 7.1.7(c): "materials of a type, quality, grade and specification corresponding to those in place immediately before the insured event... together with the fixings, fastenings, connecting and transitional components and consumable installation material used in carrying out the repair." This clause puts the elbows/transition piece squarely in covered repair cost — no coverage doubt existed to justify a cautious low charge, so pricing them at 11–12% of `t` was pure forfeited income, not risk management.
- **verdict**: noise — €7,455 barely clears the single-game floor (~6,275), and the Game closed positive; one bucket in one settled Game proves nothing about the pipeline.
- **candidate**: does the absence of the `B:memory` channel correlate with landing in `charge-far-below-t`, specifically for niche hardware/materials, across all settled Games?
