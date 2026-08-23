<!-- scripts/review_game.py · model sonnet · 2026-08-23T00:37:13Z -->

### Review — Game 56

- **what happened**: Net +632.40 (income 936.36, cost 303.96) against an oracle net of 1,898.12 — the gap is entirely item 1, where our estimate median (240) overshot the true band and even the ~0.65× charge factor (156.06) landed above `t_hi` (118.49), forfeiting that item's income entirely. Items 2–4 priced correctly as uncovered free options.
- **stage**: charge-above-t (item 1) — estimate_median 240 vs. true `t ∈ [87.12, 118.49]`; the charge factor did its job, the input to it was already too high.
- **case evidence**: policy.txt 5.2.1(a): "the remains of insured property that the insured event destroyed or damaged" — item 1 is shed roof timber + broken glass from the storm-damaged garden shed, unambiguously covered clearance under this clause, so the miss is a pricing error, not a coverage error. Items 2–4 correctly excluded per 7.1.10 ("Where any element of a combined position is not indemnifiable, the position is not indemnified") — the invoice itself states the root mass exceeded one cubic metre and was hauled mixed with soil, matching this exactly.
- **verdict**: noise — a single scorable item (`n_scorable: 1`, median_log_error 0.85) is far inside both the 6,275 single-Game and 26,622 aggregate noise floors; no basis to move anything from one line.
- **candidate**: does estimate_median systematically overshoot on "storm-damaged structure disposal" (timber/glazing clearance) items specifically, checked across all settled Games with a recovered `t`?
