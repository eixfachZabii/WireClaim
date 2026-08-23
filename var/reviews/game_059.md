<!-- scripts/review_game.py · model sonnet · 2026-08-23T01:14:18Z -->

### Review — Game 59

- **what happened**: Net −7,371 (income 43,792 vs. penalties 45,418, of which 15,139 was pure lawyer waste). Item 3 (skirting) alone forfeited 7,907.97 from every opponent.
- **stage**: charge-far-below-t — Charged 321.94 against a proven floor `t ≥ 1036.19`.
- **case evidence**: invoice pos. 3: *"Supply and install skirting boards (premium solid oak, upgrade) — 25 linear m"* (invoices.pdf). The decision log records `quantity: 1.0, quantity_missing: false` for index 3 — every other m²-denominated item (1,2,4,5,7,8,9: 18/18/6/6/20/15/8) parsed correctly, but the one "linear m" unit was read as qty 1 instead of 25. `price_median` 464.75 × ~25 lands near the observed floor; × 1 does not.
- **verdict**: signal — the euros (7,907.97) clear the single-Game noise floor (~6,275), and the mismatch is a concrete, quotable parsing error, not a fuzzy estimation miss.
- **candidate**: across every settled Game, check whether Line Items whose invoice unit is *not* "m²" or "flat rate" (e.g. "linear m", "pcs", "kg") systematically get `quantity=1` recorded despite a stated non-1 amount — i.e. does quantity extraction only key off the m² pattern?
