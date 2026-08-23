<!-- scripts/review_game.py · model sonnet · 2026-08-22T23:33:37Z -->

### Review — Game 51

- **what happened**: Net −€2,484 across 6 line items; the loss is almost entirely one item — without it the game would have closed solidly positive, matching strategy3's +€1,509.
- **stage**: charge-far-below-t (item 2, "Technical room drying of the affected basement area," 6 pcs) — charged €902.67 against a proven floor t ≥ €2,539.45, forfeiting €28,027 in penalties, the single largest driver in the whole game (~€18,549 worse than the best alternative).
- **case evidence**: "allowing water to spread into the surrounding walls and floor across a significant part of the affected rooms" (description.txt) — signals a large, multi-room drying job. Policy 7.1.7(b) covers "the drying, dehumidification and moisture-removal measures necessary... to the extent of the affected parts established under 7.1.5," tying drying cost to scope. Our estimate median (€1,325) undershot the proven floor by ~2×; the 6-pcs quantity and "significant part of the affected rooms" language both pointed toward a bigger job than we priced.
- **verdict**: signal — one item caused 92% of this game's loss and the stage tag is unambiguous, clearing the ~6,275 single-Game noise floor by itself.
- **candidate**: across all settled Games, does t̂/t_lo error on drying/remediation items grow with invoice quantity (pcs > 1) — i.e., is scope-scaling underweighted when quantity signals a larger job?
