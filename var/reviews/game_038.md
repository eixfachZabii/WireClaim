<!-- scripts/review_game.py · model sonnet · 2026-08-22T20:50:30Z -->

### Review — Game 38

- **what happened**: Net −503.87 on 4 items. Income 16,997 barely covered 3,374 paid on accepts plus 14,127 in Reviewer-side penalties; two items missed — #3 undercovered, #4 overcharged.
- **stage**: coverage-too-low — item 3 "Vehicle costs" priced at coverage_probability 0.515 (near coin-flip), collapsing its Limit to 0, though t ≥ 71.21.
- **case evidence**: "one travel, mileage or call-out charge per contractor per invoice, irrespective of how many visits were made" (policy.txt, 7.1.7(f)) — the plumber's "Vehicle costs" line (invoice 2026-0126, pos. 3) is exactly this named, explicitly indemnified cost head, not an ambiguous item; the model's near-50/50 verdict undersold a clause that names the item directly.
- **verdict**: noise — 1,018.26 penalty on this item (and 1,840.85 on item 4's charge-above-t) sum to ~2,859, well inside the ~6,275 single-Game noise floor.
- **candidate**: does coverage_probability undershoot specifically on short, generic invoice-line names ("Vehicle costs", "Call-out fee") that map to an explicit 7.1.7 ancillary-cost clause, versus descriptive repair lines — worth a pass over every settled Game's coverage-too-low items to see if this is a recurring pattern rather than one Case's phrasing.
