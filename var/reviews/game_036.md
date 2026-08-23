<!-- scripts/review_game.py · model sonnet · 2026-08-22T20:25:05Z -->

### Review — Game 36

- **what happened**: Net +€2,307.35 across 10 Line Items, all tagged `uncovered-free-option`; zero penalties, zero paid-on-accepts — every Charge was accepted and nothing came back at us.
- **stage**: ok (all 10 items) — decision log present, schema 2, pipeline's own attribution finds nothing to correct.
- **case evidence**: "It looks like a DIY job from a while back that was never done up properly, so it had been quietly weeping for a long time rather than failing all of a sudden. Basically a bad connection that was loose from the start." (description.txt) — this is squarely policy 3.3(j), "escape attributable to a defect, wear, or an improperly executed installation already present before the event," reinforced by 3.3(i), "water that emerged gradually... rather than suddenly and unforeseeably." Low coverage probabilities (0.04–0.5) and the uncovered-free-option charge-regardless rule are the right response to a claim this cleanly excluded.
- **verdict**: noise — stage attribution is unambiguous but the euros (+2,307) don't approach the ~6,275 single-Game noise floor, and there's no flagged defect to act on.
- **candidate**: does `coverage_probability` correlate with exclusion-clause explicitness — e.g., is item 2 (Construction dryer, p=0.5, the highest here) systematically under-confident on cases where the description contains an explicit disclaimer sentence like "wasn't a sudden accidental thing"? Worth checking across all settled Games before touching the coverage channel.
