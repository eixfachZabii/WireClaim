<!-- scripts/review_game.py · model sonnet · 2026-08-23T00:24:19Z -->

### Review — Game 55

- **what happened**: Single line item (laptop repair). We charged 379.98 against a reconstructed floor of t ≥ 1,125; net −3,282.02, all of it (8,974.95 penalty vs. 6,079.68 income) attributed to one stage.
- **stage**: charge-far-below-t — our price band [337.92, 795.46] never reached t≥1125; even price_high would have undercharged by ~30%.
- **case evidence**: "Where an insured event under 2.6.1 acts on a unit, the indemnity comprises all areas of damage on that unit caused by the same event" (policy.txt, 2.6.3), read against description.txt: "cracking the screen and damaging the lower right corner." Both damage areas settle as one combined loss — a screen-plus-enclosure repair, not a screen-only one — so a band anchored near a screen-only price would structurally undershoot the true combined-repair cost.
- **verdict**: signal — unambiguous single-cause attribution (100% of penalties, one item) and large euros; consistent with the standing status-section hypothesis that estimate quality, not the charge/limit constants, is where net is being left on the table.
- **candidate**: across all settled Games, do invoice lines whose description names ≥2 distinct damage areas on one unit see the model's price_high undershoot the reconstructed t-floor more often than single-area lines?
