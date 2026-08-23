<!-- scripts/review_game.py · model sonnet · 2026-08-22T22:57:00Z -->

### Review — Game 48

- **what happened**: Net +677.49 (income 47,343.83 vs penalties 31,512.54). Item 1 (conservatory rug) alone cost 3,495.02: coverage came back 0.425 and the Limit collapsed to 0, so the correctly-priced Charge went unpaid.
- **stage**: coverage-too-low — the rug sat in the room the water is confirmed to have crossed, but our coverage read near coin-flip.
- **case evidence**: description.txt: "the water spread from the pool room into the conservatory and down through the floor into the plant room underneath." policy.txt 11.1: "wetting the floor and wall finishes, the edging elements, **a furnishing item** and part of the building's own technical installations along that path." The Case itself names one furnishing item as wetted on that exact path — the conservatory rug is the only furnishing item on the invoice sitting in that room, so 0.425 undershoots a fact pattern the Case already spells out (coverage still hinges on the 4.4.1/4.2.3 schedule extension, which we can't see — but t_lo = 224.68 confirms it was in fact paid).
- **verdict**: noise — 3,495 sits well under both the 6,275 single-Game and 26,622 pooled noise floor; one item is not a pattern.
- **candidate**: across every settled Game, does coverage probability for a "furnishing item" line item under-fit when description.txt independently names an affected furnishing on the water's path?
