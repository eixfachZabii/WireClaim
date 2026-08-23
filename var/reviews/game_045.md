<!-- scripts/review_game.py · model sonnet · 2026-08-22T22:18:32Z -->

### Review — Game 45

- **what happened**: Net +11,390 (income 57,703 / cost 46,312) — strategy2 beat strategy1/3 by ~20k. Cost split: 9,737 estimate-too-low, 8,185 "ok", 6,955 coverage-too-low, 5,088 charge-far-below-t.
- **stage**: coverage-too-low — items 5, 8, 11, 12 collapsed the Limit to near-zero despite the Case confirming cover.
- **case evidence**: description.txt: "this policyholder does hold the separate Pool Equipment Endorsement and it is attached to the policy, so the pool technology side of the work is not sitting outside cover" — policy 4.4.2(b): "fracture and comparable failure of its pipework, connections and fittings falls under 2.4.3, so that its repair, the labour hours spent on that repair and the materials consumed by it are indemnified." Item 12, "Material for pool pipe repair," is a textbook 4.4.2(b) case with the endorsement explicitly confirmed, yet coverage_probability came back 0.475.
- **verdict**: signal — the stage tag is unambiguous and the clause/description link is direct rather than inferred, and it recurs across 4 items (6,955, the 2nd-largest cost bucket this Game).
- **candidate**: across all settled Games where a description explicitly states an optional extension is "attached"/"recorded in the schedule," does the evidence layer's coverage_probability for items governed by that extension average measurably lower than for base-peril items?
