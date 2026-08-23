<!-- scripts/review_game.py · model sonnet · 2026-08-22T23:58:53Z -->

### Review — Game 53

- **what happened**: Robbery item (watch + cash, `t ≥ 8,626.50`) got Limit collapsed to `[0, 176.75]` on coverage_probability 0.42, so the €8,626+ claim was wrongfully rejected — driving €77,793.15 in lawyer penalties and a Game net of −€4,451.71.
- **stage**: coverage-too-low — the model underweighted a clause that squarely covers this loss.
- **case evidence**: policy 2.3.1: "the taking of insured property from the policyholder... by the use of force... or under the threat of an immediate danger to life or limb" — description.txt: "They were threatened with a weapon at the time." A weapon-threat robbery, reported to police (satisfying 2.3.3), is textbook 2.3.1 cover with none of the 2.3.4 exclusions (no voluntary surrender, no mislaid item) in play. 0.42 is far below what an unambiguous clause match should yield.
- **verdict**: signal — attribution is unambiguous (explicit clause hit) and the euros are large (€77,793 penalty, the whole Game's swing), clearing the single-Game noise floor on its own.
- **candidate**: does coverage_probability systematically under-call items where the description states an explicit force/weapon threat matching peril 2.3.1, across all settled Games with a robbery-type claim?
