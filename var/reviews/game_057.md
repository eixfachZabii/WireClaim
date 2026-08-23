<!-- scripts/review_game.py · model sonnet · 2026-08-23T00:50:58Z -->

### Review — Game 57

- **what happened**: Net −€177.40 (income €7,012.09, paid-on-accepts €5,335.50, penalties €1,853.99). All €1,853.99 of penalties came from items 5 and 10 ("Assembly costs," both tagged `ok`), where our Limit bracket topped out at 119.00/118.00 — below the true `t_lo` of 130.00 for both.
- **stage**: `ok` (as tagged) — but the tag masks a Limit-below-posterior miss the taxonomy has no name for; coverage and estimate were correct, only the Limit undershot.
- **case evidence**: "the assembly, fitting, mounting, adjustment, alignment and functional testing of those replacement parts on the item, this being part of the repair and not a separate supply service" (policy.txt, 7.1.7(c)) — confirms Assembly costs are legitimately indemnifiable, so `t_lo=130` is real and the `ok` diagnosis on coverage/estimate is correct; the loss is purely a Limit set outside the posterior (CLAUDE.md rule 4's "open tap").
- **verdict**: noise — €1,853.99 sits below the ~€6,275 single-Game floor, even though it explains the whole net.
- **candidate**: Across all settled Games, do `ok`-tagged items whose `limit_bracket` upper bound is finite and below `t_lo` account for a disproportionate share of `penalties_here` — i.e. should the taxonomy split a `limit-below-t` stage out of `ok`?
