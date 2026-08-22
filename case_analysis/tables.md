# Case Analysis — Number Tables

The number-only tables, regenerated automatically with the same workflow as
[`dashboard.md`](dashboard.md).

## Derived t per line item — last 5 games

For every line item: the derived t bracket/point, then per team a block of
`a | b | a/t | b/t | net` — the Charge, the reconstructed Limit (interval midpoint),
their ratios to the derived t, and the net income/payment on that item (received as
Issuer minus paid as Reviewer incl. 1.5a penalties). Bin busy first (highlighted),
then the best performers of these games. Full data in `data/tvalues.csv`.

![t values per line item](data/tvalues.png)

## Best teams per game — what to copy

Top 3 by net each game (+ Bin busy's row highlighted): income split (fair accepts /
swallowed Overcharges / 1.5a penalties), cost leaks, Charge aggressiveness (med a/t),
and a one-line verdict of why it worked. Full per-team data in `data/teams.csv`.

![Best teams per game](data/teams.png)
