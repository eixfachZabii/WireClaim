# Case Analysis — Live Dashboard

Main analysis page for team **Bin busy** in the Claim-to-Fame tournament. Everything below is
regenerated automatically every ~10 minutes from the public settled leaderboard data
(`.github/workflows/case-analysis.yml` runs `case_analysis/run_all.py`).

## How to read this (for an AI strategy optimizer)

Definitions (see `docs/CONTEXT.md` / `README.md` for the rules):

- `a` = Charge (what we invoice every opponent per Line Item), `b` = Limit (max we pay as Reviewer),
  `t` = hidden Fair Value, `c ≥ 4t` = Cap on accepted payouts.
- Payoffs per opponent pair: accepted → issuer gets `min(a, c)`; rejected fair Charge (`a ≤ t`) →
  issuer still gets `a` AND the reviewer pays an extra `0.5a` (total `1.5a`); rejected Overcharge
  (`a > t`) → nothing moves.
- `t (derived)` is bracketed from settled data: largest rejected-but-paid Charge ≤ t < smallest
  zero-payout rejection. Unbounded brackets mean nobody was caught Overcharging on that item.
- Target policy derived from history: `a ≈ 0.7 × t̂`, `b ≈ 0.5–1.0 × t̂` (never 0, never far above t̂);
  charge high only on items believed uncovered (t = 0) or when the field is dark.
- Optimization signals: keep `a/t ≤ 1` on covered items (income even when rejected), keep `b/t`
  in 0.5–1.0 (below → 1.5a lawyer-fee leak; above → pay opponents' Overcharges), lawyer fees per
  round < 5k, paid-over ≈ 0.

Machine-readable files (all in `data/`): `analysis.json` (per-game, per-item `charges_a`,
`limits_b` intervals, `t_lo`/`t_hi`/`t_point`, `fair_flags`), `ourvalues.csv`, `tvalues.csv`,
`teams.csv`, `balance.csv`, `binbusy_money.csv`. Layout details: `DATA_LAYOUT.md`.

## Bin busy — actual submitted values vs. derived t (last 10 rounds)

Our real submissions (`charge_decided` / `limit_decided` from `var/export/line_items.csv`;
rows marked `reconstructed` fall back to the public inversion), the derived `t`, the
normalized ratios `a/t` and `b/t`, the net on each item, and the net per round.

<!-- OURVALUES:START -->

Per line item, last 10 settled games (full file: `data/ourvalues.csv`):

| game | item | name | a (actual) | b (actual) | t (derived) | a/t | b/t | item net | source |
|---|---|---|---|---|---|---|---|---|---|
| 81 | 1 | - | - | 5.00 | 5.00 | - | 1.00 | 0.00 | reconstructed |
| 81 | 2 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 81 | 3 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 81 | 4 | - | - | 1.14 | 1.14 | - | 1.00 | 0.00 | reconstructed |
| 82 | 1 | - | 48.99 | 45.45 | 20.81 | 2.35 | 2.18 | 203.33 | reconstructed |
| 82 | 2 | - | 644.30 | 582.85 | 737.10 | 0.87 | 0.79 | 6,792.68 | reconstructed |
| 82 | 3 | - | 173.09 | 175.41 | 38.25 | 4.53 | 4.59 | -400.72 | reconstructed |
| 82 | 4 | - | 106.45 | 106.83 | 115.50 | 0.92 | 0.92 | 951.59 | reconstructed |
| 82 | 5 | - | - | 23.00 | 23.00 | - | 1.00 | 0.00 | reconstructed |
| 82 | 6 | - | 311.11 | 306.42 | 402.60 | 0.77 | 0.76 | 1,065.41 | reconstructed |
| 82 | 7 | - | 190.44 | 191.56 | 242.57 | 0.79 | 0.79 | 567.00 | reconstructed |
| 82 | 8 | - | 380.85 | 369.54 | 568.75 | 0.67 | 0.65 | -325.91 | reconstructed |
| 82 | 9 | - | 300.00 | 45.77 | 62.08 | 4.83 | 0.74 | 179.88 | reconstructed |
| 82 | 10 | - | 353.20 | 343.86 | 428.59 | 0.82 | 0.80 | 557.89 | reconstructed |
| 82 | 11 | - | 487.83 | 485.94 | 572.66 | 0.85 | 0.85 | 1,138.35 | reconstructed |
| 82 | 12 | - | 294.82 | 296.13 | 340.56 | 0.87 | 0.87 | 1,081.50 | reconstructed |
| 82 | 13 | - | 78.15 | 83.75 | 98.45 | 0.79 | 0.85 | 1,013.64 | reconstructed |
| 82 | 14 | - | 60.89 | 60.75 | 68.83 | 0.88 | 0.88 | 721.50 | reconstructed |
| 82 | 15 | - | 164.96 | 163.22 | 191.84 | 0.86 | 0.85 | 715.58 | reconstructed |
| 82 | 16 | - | 94.10 | 95.66 | 124.20 | 0.76 | 0.77 | -35.34 | reconstructed |
| 82 | 17 | - | 135.07 | 134.72 | 170.62 | 0.79 | 0.79 | 887.23 | reconstructed |
| 82 | 18 | - | 105.46 | 107.65 | 124.62 | 0.85 | 0.86 | 658.99 | reconstructed |
| 82 | 19 | - | 507.90 | 483.72 | 588.75 | 0.86 | 0.82 | 2,668.40 | reconstructed |
| 82 | 20 | - | 94.51 | 96.19 | 121.69 | 0.78 | 0.79 | 939.84 | reconstructed |
| 82 | 21 | - | 81.59 | 83.00 | 102.25 | 0.80 | 0.81 | 794.21 | reconstructed |
| 82 | 22 | - | 300.00 | 57.75 | 166.06 | 1.81 | 0.35 | -745.93 | reconstructed |
| 82 | 23 | - | 300.00 | 33.55 | 135.58 | 2.21 | 0.25 | 1,761.48 | reconstructed |
| 82 | 24 | - | - | 24.00 | 24.00 | - | 1.00 | 0.00 | reconstructed |
| 82 | 25 | - | 427.01 | 418.02 | 503.49 | 0.85 | 0.83 | 1,765.48 | reconstructed |
| 82 | 26 | - | 99.80 | 88.40 | 113.06 | 0.88 | 0.78 | 1,216.86 | reconstructed |
| 82 | 27 | - | 343.76 | 347.83 | 433.84 | 0.79 | 0.80 | 1,031.60 | reconstructed |
| 82 | 28 | - | 200.76 | 192.30 | 228.81 | 0.88 | 0.84 | 511.38 | reconstructed |
| 82 | 29 | - | 110.18 | 108.00 | 123.09 | 0.90 | 0.88 | 160.60 | reconstructed |
| 82 | 30 | - | 94.66 | 98.01 | 112.14 | 0.84 | 0.87 | 781.39 | reconstructed |
| 82 | 31 | - | 189.17 | 199.69 | 217.12 | 0.87 | 0.92 | 1,843.62 | reconstructed |
| 82 | 32 | - | 33.17 | 31.44 | 39.50 | 0.84 | 0.80 | 450.84 | reconstructed |
| 83 | 1 | - | 300.00 | 20.00 | 55.65 | 5.39 | 0.36 | 240.00 | reconstructed |
| 83 | 2 | - | 300.00 | 31.88 | 31.88 | 9.41 | 1.00 | 232.70 | reconstructed |
| 83 | 3 | - | 300.00 | 19.50 | 70.31 | 4.27 | 0.28 | 766.50 | reconstructed |
| 83 | 4 | - | 300.00 | 20.50 | 45.50 | 6.59 | 0.45 | 238.50 | reconstructed |
| 83 | 5 | - | - | 46.90 | 13.12 | - | 3.57 | -114.15 | reconstructed |
| 83 | 6 | - | - | 32.13 | 16.07 | - | 2.00 | -32.13 | reconstructed |
| 83 | 7 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 84 | 1 | - | 300.00 | 38.00 | 38.00 | 7.89 | 1.00 | 3,000.00 | reconstructed |
| 84 | 2 | - | 290.39 | 347.38 | 347.38 | 0.84 | 1.00 | 3,776.21 | reconstructed |
| 84 | 3 | - | 511.60 | 536.50 | 750.00 | 0.68 | 0.72 | 2,359.11 | reconstructed |
| 84 | 4 | - | 69.50 | 71.92 | 82.19 | 0.85 | 0.88 | 582.19 | reconstructed |
| 84 | 5 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 84 | 6 | - | 300.00 | 75.00 | 439.83 | 0.68 | 0.17 | 4,138.50 | reconstructed |
| 84 | 7 | - | 36.04 | 34.61 | 39.36 | 0.92 | 0.88 | 456.86 | reconstructed |
| 84 | 8 | - | 300.00 | 51.00 | 51.00 | 5.88 | 1.00 | 1,800.00 | reconstructed |
| 84 | 9 | - | - | 50.00 | 50.00 | - | 1.00 | 0.00 | reconstructed |
| 84 | 10 | - | 69.50 | 71.48 | 15.00 | 4.63 | 4.77 | -144.97 | reconstructed |
| 84 | 11 | - | 64.06 | 8.00 | 8.00 | 8.01 | 1.00 | 64.06 | reconstructed |
| 84 | 12 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 84 | 13 | - | 300.00 | 80.01 | 80.01 | 3.75 | 1.00 | 2,365.00 | reconstructed |
| 85 | 1 | - | 300.00 | 84.50 | 226.50 | 1.32 | 0.37 | 2,139.09 | reconstructed |
| 85 | 2 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 86 | 1 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 86 | 2 | - | - | 35.00 | 17.50 | - | 2.00 | -35.00 | reconstructed |
| 86 | 3 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 86 | 4 | - | 22.28 | 21.25 | 4.00 | 5.57 | 5.31 | -35.87 | reconstructed |
| 86 | 5 | - | 22.18 | 21.90 | 10.50 | 2.11 | 2.09 | 1.18 | reconstructed |
| 86 | 6 | - | - | 118.00 | 20.16 | - | 5.85 | -470.16 | reconstructed |
| 86 | 7 | - | - | 30.00 | 9.38 | - | 3.20 | -102.79 | reconstructed |
| 86 | 8 | - | - | 55.12 | 24.50 | - | 2.25 | -104.12 | reconstructed |
| 86 | 9 | - | - | 46.23 | 46.23 | - | 1.00 | -25.00 | reconstructed |
| 86 | 10 | - | - | 28.50 | 127.01 | - | 0.22 | -1,114.38 | reconstructed |
| 86 | 11 | - | 62.41 | 58.06 | 24.50 | 2.55 | 2.37 | 575.10 | reconstructed |
| 87 | 1 | - | 300.00 | 19.32 | 453.57 | 0.66 | 0.04 | 1,885.94 | reconstructed |
| 87 | 2 | - | 300.00 | 45.08 | 965.02 | 0.31 | 0.05 | 146.07 | reconstructed |
| 87 | 3 | - | 300.00 | 40.51 | 160.79 | 1.87 | 0.25 | -540.34 | reconstructed |
| 87 | 4 | - | 60.78 | 60.45 | 81.00 | 0.75 | 0.75 | 217.81 | reconstructed |
| 87 | 5 | - | 52.54 | 53.10 | 69.82 | 0.75 | 0.76 | 386.67 | reconstructed |
| 87 | 6 | - | - | 19.84 | 1.08 | - | 18.37 | -82.48 | reconstructed |
| 87 | 7 | - | 300.00 | 43.46 | 14.74 | 20.35 | 2.95 | 235.51 | reconstructed |
| 88 | 1 | - | 504.41 | 441.89 | 612.00 | 0.82 | 0.72 | 1,451.38 | reconstructed |
| 88 | 2 | - | 429.01 | 419.75 | 571.00 | 0.75 | 0.74 | 553.24 | reconstructed |
| 88 | 3 | - | 212.17 | 211.95 | 294.50 | 0.72 | 0.72 | 438.01 | reconstructed |
| 88 | 4 | - | 83.05 | 79.45 | 85.69 | 0.97 | 0.93 | 567.80 | reconstructed |
| 88 | 5 | - | 97.12 | 101.10 | 110.87 | 0.88 | 0.91 | 1,012.43 | reconstructed |
| 88 | 6 | - | 300.00 | 75.00 | 500.00 | 0.60 | 0.15 | -579.60 | reconstructed |
| 88 | 7 | - | 130.45 | 131.63 | 150.00 | 0.87 | 0.88 | 715.77 | reconstructed |
| 88 | 8 | - | 1,475.15 | 1,434.74 | 1,691.22 | 0.87 | 0.85 | 7,776.64 | reconstructed |
| 88 | 9 | - | 521.72 | 528.44 | 625.26 | 0.83 | 0.85 | 3,188.23 | reconstructed |
| 88 | 10 | - | - | 43.90 | 4.00 | - | 10.97 | -86.76 | reconstructed |
| 88 | 11 | - | 52.36 | 53.70 | 68.50 | 0.76 | 0.78 | 487.31 | reconstructed |
| 88 | 12 | - | 121.27 | 117.88 | 142.87 | 0.85 | 0.83 | 450.39 | reconstructed |
| 88 | 13 | - | 146.61 | 143.13 | 183.57 | 0.80 | 0.78 | 706.70 | reconstructed |
| 88 | 14 | - | 158.59 | 157.43 | 199.53 | 0.79 | 0.79 | 943.34 | reconstructed |
| 88 | 15 | - | 853.84 | 656.00 | 1,127.16 | 0.76 | 0.58 | 6,567.57 | reconstructed |
| 88 | 16 | - | 2,217.54 | 1,850.80 | 3,768.47 | 0.59 | 0.49 | 7,673.77 | reconstructed |
| 88 | 17 | - | 345.84 | 367.00 | 646.96 | 0.53 | 0.57 | 233.81 | reconstructed |
| 88 | 18 | - | 249.64 | 241.60 | 459.39 | 0.54 | 0.53 | 353.47 | reconstructed |
| 88 | 19 | - | 130.45 | 130.50 | 86.34 | 1.51 | 1.51 | -163.67 | reconstructed |
| 88 | 20 | - | - | 34.50 | 34.50 | - | 1.00 | 0.00 | reconstructed |
| 89 | 1 | - | 66.41 | 67.21 | 81.00 | 0.82 | 0.83 | 133.06 | reconstructed |
| 89 | 2 | - | 19.94 | 19.69 | 21.65 | 0.92 | 0.91 | 64.90 | reconstructed |
| 89 | 3 | - | 37.90 | 34.33 | 54.00 | 0.70 | 0.64 | 10.45 | reconstructed |
| 89 | 4 | - | 27.14 | 28.36 | 35.65 | 0.76 | 0.80 | 201.22 | reconstructed |
| 89 | 5 | - | 174.05 | 154.77 | 410.06 | 0.42 | 0.38 | 12.06 | reconstructed |
| 89 | 6 | - | 690.20 | 680.34 | 838.00 | 0.82 | 0.81 | 557.03 | reconstructed |
| 89 | 7 | - | 492.70 | 495.90 | 585.00 | 0.84 | 0.85 | 2,561.77 | reconstructed |
| 89 | 8 | - | 300.00 | 40.50 | 637.75 | 0.47 | 0.06 | -3,019.17 | reconstructed |
| 89 | 9 | - | 64.06 | 19.41 | 19.41 | 3.30 | 1.00 | 128.12 | reconstructed |
| 89 | 10 | - | - | 22.40 | 22.40 | - | 1.00 | 0.00 | reconstructed |
| 90 | 1 | - | 336.33 | 214.47 | 367.66 | 0.91 | 0.58 | 2,163.61 | reconstructed |
| 90 | 2 | - | 848.57 | 500.19 | 940.50 | 0.90 | 0.53 | 4,828.85 | reconstructed |
| 90 | 3 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 90 | 4 | - | 557.89 | 387.27 | 788.00 | 0.71 | 0.49 | -521.65 | reconstructed |
| 90 | 5 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 90 | 6 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 90 | 7 | - | 388.94 | 404.66 | 490.00 | 0.79 | 0.83 | 979.43 | reconstructed |
| 90 | 8 | - | 1,040.88 | 1,100.11 | 1,305.00 | 0.80 | 0.84 | 2,480.51 | reconstructed |
| 90 | 9 | - | 259.76 | 241.28 | 605.25 | 0.43 | 0.40 | -2,422.63 | reconstructed |

Net per round:

| game | net |
|---|---|
| 81 | 0.00 |
| 82 | 28,952.35 |
| 83 | 1,331.42 |
| 84 | 18,396.96 |
| 85 | 2,139.09 |
| 86 | -1,311.04 |
| 87 | 2,249.19 |
| 88 | 32,289.81 |
| 89 | 649.46 |
| 90 | 7,508.13 |
<!-- OURVALUES:END -->

## Number tables

Per-line-item t values with the best performers, and the best-teams-per-game breakdown:
[`tables.md`](tables.md).

## Total balance per team

Cumulative net per team over all settled games (income as Issuer minus costs as Reviewer,
incl. 1.5a lawyer penalties). Bin busy is the thick black line.

![Total balance per team](data/balance.png)

## Bin busy — money flows & lawyer fees

Income received as Issuer vs. what we paid out as Reviewer (accepted payouts + 1.5a lawyer
penalties), with the net line. Bottom panel: how often per game our Limit wrongly rejected a fair
Charge and what those 1.5a penalties cost.

![Bin busy money flows](data/binbusy_money.png)

## Bin busy — fraud calls vs. reality

Per game: how many Line Items really had a derived t = 0, on how many Bin busy said "fraud"
(rejected every nonzero Charge, i.e. acted as if b = 0), how many of those calls were right,
and the same fraud-call rate averaged over the top-3 / top-5 teams.

![Bin busy fraud calls](data/table_binbusy.png)

## Trend dashboard

Net per team, per-game average a / b / derived t, fraud-zone rate by team, and median Charge
relative to derived t.

![Dashboard](data/dashboard.png)
