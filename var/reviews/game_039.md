<!-- scripts/review_game.py · model sonnet · 2026-08-22T21:02:07Z -->

### Review — Game 39

- **what happened**: Net +€3,677.19. Item 3 (framed print assessment/drying) got coverage_probability 0.495 → Limit collapsed to €0.0, wrongfully rejecting a Line Item the field's settled data puts at t≥€300 (t_hi unbounded — never rightfully rejected). Cost: €2,571.12 of €10,133.51 total penalties.

- **stage**: coverage-too-low — model's near-coin-flip coverage estimate (0.495) undershot the settled floor of ≥€300, driving the Limit to zero.

- **case evidence**: description.txt — "As it was not a high-value item, it only required a brief assessment and drying." This is almost certainly what pushed coverage uncertainty up: it reads like it's testing the 5.2.6 "particular value" carve-out (works of art, antiques), which explicitly wouldn't apply here. But the item is *assessment-and-drying labor* for water-damage mitigation, not item replacement — a different coverage question than the model seems to have answered.

- **verdict**: noise — stage attribution is unambiguous, but €2,571 sits well under the ~€6,275 single-Game noise floor.

- **candidate**: across settled Games, do items whose coverage_probability lands in an ambiguous 0.4–0.6 band, and whose invoice line is service/labor (drying, assessment, investigation) rather than item replacement, systematically resolve to t_lo > 0 — i.e. is the evidence layer conflating "is this object covered" with "is this covered-event labor" on service line items?
