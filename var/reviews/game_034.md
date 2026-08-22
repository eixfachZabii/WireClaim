<!-- scripts/review_game.py · model sonnet · 2026-08-22T20:01:33Z -->

### Review — Game 34

- **what happened**: Net −€3,948.56 (income €41,383.88; total cost €45,332.44 — €42,326.13 of that is wrongful-rejection penalty, only €3,006.31 was paid on accepts). Estimate RMSLE 0.56, above our field average (0.43) but under the σ≈0.85 break-even.
- **stage**: ok — 21/25 items tag `ok`; `cost_by_stage` shows 40,795.35 of the 42,326.13 penalty total sits on `ok`-tagged items. Only 4 items got `charge-above-t`, worth just 1,530.78.
- **case evidence**: policy 7.1.7(g): "the labour of the trades engaged, at rates customary for that trade and locality" (policy.txt). This confirms items 8/9/22 (technician, helper, tiler hours — the three biggest cost drivers, t_lo 350–629) are legitimately full repair costs, so coverage wasn't misread; our conservative Limits (R6 buffer-down) simply landed under the settled Fair Value on exactly the labour-hours items.
- **verdict**: noise — a €3,948.56 loss sits well inside the ~6,275 single-Game noise floor; nothing here is large enough to move a standing hypothesis.
- **candidate**: does RMSLE run systematically higher on hours-based labour line items (technician/helper/installation hours) than on material-SKU items, across every settled Game — which would explain why deliberately-low `ok` Limits keep landing under t on exactly this item type?
