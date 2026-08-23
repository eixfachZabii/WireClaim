<!-- scripts/review_game.py · model sonnet · 2026-08-22T19:55:02Z -->

### Review — Game 32

- **what happened**: Net +€6,886.62 (income €10,360.50 − €171.03 paid − €3,302.85 penalties). Biggest single driver: Speaker system (item 1) charged €318.01 against a reconstructed t of only [171.03, 278.50) — rejected outright, forfeiting ~€1,478 vs. the counterfactual best strategy.
- **stage**: charge-above-t (item 1, Speaker system) — the model's own median estimate (€459.07) already overshot t_hi (278.50), so even the discounted charge cleared the true value.
- **case evidence**: "the appliance sub-limit agreed in the schedule, applied per insured event and in the aggregate across all appliances and all invoices relating to that event" (policy.txt, 2.3.3) — the Speaker and TV set share one event-wide appliance cap, so per-item replacement-cost pricing overstates each item's true payout share; the estimator appears to have priced replacement value, not the shared cap.
- **verdict**: noise — the ~€1,478 item-level driver sits below the ~6,275 single-Game noise floor, even though the stage tag itself is unambiguous. (Separately, item 4's €3,302.85 penalty — the actual biggest cost — was tagged "ok" by the taxonomy, since it stems from a Limit set below t rather than a Charge/estimate error; worth a note, not a conclusion.)
- **candidate**: Across every settled multi-appliance electronics Game, does estimate_median systematically exceed t_hi when a policy 2.3.3-style aggregate appliance sub-limit applies, versus single-appliance Cases?
