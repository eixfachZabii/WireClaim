<!-- scripts/review_game.py · model sonnet · 2026-08-22T21:41:15Z -->

### Review — Game 42

- **what happened**: Net +8,279.07 (income 52,818.33 vs. penalties 29,308.53). 28,612.97 of those penalties (97.6%) sit on 16 of 17 Line Items that Strategy 2 logged zero evidence for — only item 1 has a recorded channel/rule.
- **stage**: no-decision-log — items 2–17, including the two biggest euro drivers (14, 15), were charged/limited with no model output on record.
- **case evidence**: policy 5.2.6: "the insurer reimburses the costs of securing and conserving that item: its examination by a qualified specialist, its transport to and from that specialist, measures to dry, stabilise or otherwise arrest its deterioration, and its restoration... Where it was not individually notified and recorded in that way, reimbursement is limited to [amount]." This exact clause governs invoice items 12–15 (the hallway painting's transport/assessment/drying/restoration) — the single largest driver in the Game (delta −5,250) — yet nothing shows how coverage or the cap was actually read.
- **verdict**: signal — attribution is unambiguous (16/17 items literally tagged) and 28,612.97 clears both the single-Game (6,275) and 18-Game (26,622) noise floors.
- **candidate**: does evidence-logging drop specifically on Cases split across multiple invoice PDFs (here: 3 separate invoices, 17 items) versus single-invoice Cases — check `items_priced` vs. items-with-channels across all settled Games for that correlation.
