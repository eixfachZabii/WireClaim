<!-- scripts/review_game.py · model sonnet · 2026-08-22T23:47:01Z -->

### Review — Game 52

- **what happened**: Item 1 earned 946.62 income; the two-item Game nets −1,598.32 against an oracle of +6,604.74. Item 2 correctly zeroed.
- **stage**: charge-above-t (item 1) — charged 946.62 against t∈[399.21, 503.50), ~1.9× t_hi; the estimate median (1,299.04) that fed it was ~2.6× t_hi (RMSLE 1.06, the game's only scorable item).
- **case evidence**: "Where a fracture or an escape of water is established or reasonably suspected, the insurer indemnifies the leak location... including the use of measuring or imaging equipment" (policy.txt, 2.4.6) — the invoice bundles "fitting repair including thermal-imaging leak detection" as one flat-rate line, and both components are covered here, so the 0.95 coverage call was right. The fault sits entirely in the price anchor, not coverage.
- **verdict**: noise — one Line Item, |net| 1,598 is well under the ~6,275 single-Game noise floor; nothing here should move a constant.
- **candidate**: On bundled invoice lines that combine a repair with an ancillary service (leak location / thermal imaging) under one flat-rate item, does the estimate skew high versus single-component lines, and is the reported sigma (0.27 here) underconfident about that skew? Worth checking against all settled Games with combined-line items before touching anything.
