<!-- scripts/review_game.py · model sonnet · 2026-08-22T22:43:46Z -->

### Review — Game 47

- **what happened**: Net +9,486.81 (income 41,387.34 vs. costs 31,900.53), but 19,769.49 of the 25,233.11 in penalties came from underestimating the two identical "Service technician hours (9 labor units)" lines (items 7, 12).
- **stage**: estimate-too-low — Charge and Limit both drawn from a median (816.64) that sat just below the proven floor (t ≥ 837.90) on both duplicate lines.
- **case evidence**: "Took a few visits." (description.txt) with policy.txt 7.1.7(g) "the labour of the trades engaged, at rates customary for that trade and locality and limited to the time the work reasonably required" — confirms both service-hour lines are genuinely separate, fully billable visits, not a duplicate to haircut; the model just undershot the going rate for both by ~5%.
- **verdict**: signal — a 5% median miss cost 18,852 in counterfactual delta on these two lines alone, ~3× the ~6,275 single-Game noise floor, and it sharpens the existing estimate-quality hypothesis (H3/H8) rather than introducing a new claim.
- **candidate**: across all settled Games, does labor/technician-hour estimate bias skew lower specifically when the same line description repeats verbatim within one invoice, versus singly-appearing lines?
