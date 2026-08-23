# Case Analysis — Live Dashboard

Main analysis page for team **Bin busy** in the Claim-to-Fame tournament. Everything below is
regenerated automatically every ~10 minutes from the public settled leaderboard data
(`.github/workflows/case-analysis.yml` runs `case_analysis/run_all.py`).

## How to read this (for an AI strategy optimizer)

Definitions (see `docs/CONTEXT.md` / `docs/GAME-AND-PROOFS.md` for the rules):

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
| 91 | 1 | - | 220.22 | 130.60 | 21.50 | 10.24 | 6.07 | 202.41 | reconstructed |
| 91 | 2 | - | 30.90 | 19.05 | 19.05 | 1.62 | 1.00 | 32.49 | reconstructed |
| 91 | 3 | - | 76.64 | 51.20 | 183.54 | 0.42 | 0.28 | -562.81 | reconstructed |
| 91 | 4 | - | 48.93 | 49.95 | 38.06 | 1.29 | 1.31 | 249.04 | reconstructed |
| 91 | 5 | - | 137.94 | 2.83 | 2.83 | 48.66 | 1.00 | 275.88 | reconstructed |
| 91 | 6 | - | 43.46 | 37.46 | 51.06 | 0.85 | 0.73 | 317.62 | reconstructed |
| 91 | 7 | - | 41.02 | 6.00 | 6.00 | 6.84 | 1.00 | 123.06 | reconstructed |
| 91 | 8 | - | 62.71 | 61.41 | 116.72 | 0.54 | 0.53 | -30.63 | reconstructed |
| 91 | 9 | - | 833.87 | 697.61 | 1,260.00 | 0.66 | 0.55 | -623.97 | reconstructed |
| 91 | 10 | - | 54.46 | 4.00 | 43.72 | 1.25 | 0.09 | -109.25 | reconstructed |
| 91 | 11 | - | 117.50 | 8.84 | 52.73 | 2.23 | 0.17 | 26.48 | reconstructed |
| 91 | 12 | - | 89.11 | 16.12 | 39.50 | 2.26 | 0.41 | 397.19 | reconstructed |
| 91 | 13 | - | 83.33 | 32.50 | 81.22 | 1.03 | 0.40 | 367.01 | reconstructed |
| 91 | 14 | - | 112.97 | 10.00 | 10.00 | 11.30 | 1.00 | 112.97 | reconstructed |
| 91 | 15 | - | 16.21 | 11.25 | 16.61 | 0.98 | 0.68 | 158.64 | reconstructed |
| 91 | 16 | - | 85.51 | 78.72 | 85.20 | 1.00 | 0.92 | -282.92 | reconstructed |
| 91 | 17 | - | 220.71 | 202.89 | 301.16 | 0.73 | 0.67 | -65.87 | reconstructed |
| 91 | 18 | - | 80.54 | 2.48 | 42.87 | 1.88 | 0.06 | 364.15 | reconstructed |
| 91 | 19 | - | 26.39 | 3.30 | 27.70 | 0.95 | 0.12 | 387.50 | reconstructed |
| 91 | 20 | - | 64.30 | 3.96 | 60.95 | 1.05 | 0.06 | -234.53 | reconstructed |
| 92 | 1 | - | 58.21 | 58.17 | 116.72 | 0.50 | 0.50 | -71.23 | reconstructed |
| 92 | 2 | - | 17.10 | 18.93 | 68.33 | 0.25 | 0.28 | 4.82 | reconstructed |
| 92 | 3 | - | 25.04 | 17.28 | 63.35 | 0.40 | 0.27 | -54.10 | reconstructed |
| 92 | 4 | - | 27.95 | 20.09 | 107.10 | 0.26 | 0.19 | -319.87 | reconstructed |
| 92 | 5 | - | 11.15 | 6.58 | 32.99 | 0.34 | 0.20 | -36.79 | reconstructed |
| 92 | 6 | - | 176.72 | 191.25 | 615.03 | 0.29 | 0.31 | -388.25 | reconstructed |
| 92 | 7 | - | 625.04 | 671.50 | 1,969.00 | 0.32 | 0.34 | 237.79 | reconstructed |
| 92 | 8 | - | 321.54 | 396.22 | 585.00 | 0.55 | 0.68 | -1,361.53 | reconstructed |
| 92 | 9 | - | 368.52 | 175.40 | 854.00 | 0.43 | 0.21 | -1,951.38 | reconstructed |
| 93 | 1 | - | 346.70 | 371.44 | 261.67 | 1.32 | 1.42 | 836.75 | reconstructed |
| 93 | 2 | - | 132.54 | 136.50 | 130.27 | 1.02 | 1.05 | -261.37 | reconstructed |
| 93 | 3 | - | 64.06 | 9.50 | 9.50 | 6.74 | 1.00 | 64.06 | reconstructed |
| 93 | 4 | - | 64.06 | 18.50 | 18.50 | 3.46 | 1.00 | 64.06 | reconstructed |
| 93 | 5 | - | 64.06 | 14.50 | 14.50 | 4.42 | 1.00 | 64.06 | reconstructed |
| 93 | 6 | - | 26.11 | 26.50 | 27.05 | 0.97 | 0.98 | 245.48 | reconstructed |
| 93 | 7 | - | 28.39 | 29.00 | 24.20 | 1.17 | 1.20 | 237.55 | reconstructed |
| 93 | 8 | - | 122.03 | 123.85 | 130.64 | 0.93 | 0.95 | 237.34 | reconstructed |
| 93 | 9 | - | 25.72 | 24.82 | 1.53 | 16.81 | 16.22 | -46.64 | reconstructed |
| 93 | 10 | - | 35.81 | 33.21 | 12.48 | 2.87 | 2.66 | -27.11 | reconstructed |
| 93 | 11 | - | 67.29 | 57.01 | 21.38 | 3.15 | 2.67 | 715.73 | reconstructed |
| 93 | 12 | - | 54.23 | 58.42 | 29.12 | 1.86 | 2.01 | 279.86 | reconstructed |
| 93 | 13 | - | 116.59 | 125.03 | 135.66 | 0.86 | 0.92 | 899.96 | reconstructed |
| 93 | 14 | - | 30.96 | 7.12 | 82.80 | 0.37 | 0.09 | -151.10 | reconstructed |
| 93 | 15 | - | 76.75 | 53.41 | 111.00 | 0.69 | 0.48 | 232.95 | reconstructed |
| 93 | 16 | - | 33.27 | 2.88 | 2.88 | 11.55 | 1.00 | 33.27 | reconstructed |
| 93 | 17 | - | 35.81 | 38.68 | 9.16 | 3.91 | 4.22 | -126.34 | reconstructed |
| 93 | 18 | - | 67.82 | 70.72 | 29.25 | 2.32 | 2.42 | 421.25 | reconstructed |
| 94 | 1 | - | 24.43 | 4.32 | 4.32 | 5.66 | 1.00 | 24.43 | reconstructed |
| 94 | 2 | - | 130.83 | 15.68 | 15.68 | 8.35 | 1.00 | 130.83 | reconstructed |
| 94 | 3 | - | - | 10.35 | 10.35 | - | 1.00 | 0.00 | reconstructed |
| 94 | 4 | - | 281.27 | 165.38 | 318.75 | 0.88 | 0.52 | 667.83 | reconstructed |
| 94 | 5 | - | 165.70 | 114.47 | 175.81 | 0.94 | 0.65 | 1,267.43 | reconstructed |
| 94 | 6 | - | 55.68 | 12.99 | 12.99 | 4.28 | 1.00 | 501.12 | reconstructed |
| 95 | 1 | - | 380.14 | 368.35 | 976.54 | 0.39 | 0.38 | 668.72 | reconstructed |
| 95 | 2 | - | 1,024.91 | 1,133.00 | 1,350.80 | 0.76 | 0.84 | 688.12 | reconstructed |
| 95 | 3 | - | 429.35 | 419.50 | 650.00 | 0.66 | 0.65 | 122.06 | reconstructed |
| 95 | 4 | - | - | 2.70 | 2.70 | - | 1.00 | 0.00 | reconstructed |
| 95 | 5 | - | 348.98 | 234.57 | 342.65 | 1.02 | 0.68 | -1,348.44 | reconstructed |
| 95 | 6 | - | 779.01 | 778.58 | 950.85 | 0.82 | 0.82 | 4,881.52 | reconstructed |
| 95 | 7 | - | 511.86 | 299.62 | 633.10 | 0.81 | 0.47 | 2,346.27 | reconstructed |
| 95 | 8 | - | 436.12 | 262.55 | 493.06 | 0.88 | 0.53 | 3,220.40 | reconstructed |
| 96 | 1 | - | 58.19 | 63.48 | 117.03 | 0.50 | 0.54 | 453.02 | reconstructed |
| 96 | 2 | - | 286.36 | 155.49 | 930.21 | 0.31 | 0.17 | -2,645.21 | reconstructed |
| 96 | 3 | - | 60.27 | 47.16 | 112.68 | 0.53 | 0.42 | 132.63 | reconstructed |
| 96 | 4 | - | 382.14 | 362.50 | 585.00 | 0.65 | 0.62 | 107.65 | reconstructed |
| 96 | 5 | - | 392.64 | 350.78 | 638.00 | 0.62 | 0.55 | -652.58 | reconstructed |
| 97 | 1 | - | 53.10 | 9.14 | 248.40 | 0.21 | 0.04 | -477.22 | reconstructed |
| 97 | 2 | - | 37.65 | 5.16 | 94.00 | 0.40 | 0.05 | -112.71 | reconstructed |
| 97 | 3 | - | 126.39 | 9.06 | 214.20 | 0.59 | 0.04 | 667.91 | reconstructed |
| 97 | 4 | - | 24.11 | 3.56 | 45.89 | 0.53 | 0.08 | 153.58 | reconstructed |
| 97 | 5 | - | 8.38 | 0.72 | 9.55 | 0.88 | 0.08 | 64.57 | reconstructed |
| 97 | 6 | - | 23.17 | 2.48 | 21.09 | 1.10 | 0.12 | 24.56 | reconstructed |
| 97 | 7 | - | 74.90 | 2.48 | 24.79 | 3.02 | 0.10 | 46.27 | reconstructed |
| 97 | 8 | - | 487.91 | 353.74 | 742.61 | 0.66 | 0.48 | 1,025.37 | reconstructed |
| 97 | 9 | - | 301.87 | 24.61 | 380.88 | 0.79 | 0.06 | 233.62 | reconstructed |
| 97 | 10 | - | 45.08 | 7.95 | 171.00 | 0.26 | 0.05 | -340.54 | reconstructed |
| 97 | 11 | - | 14.99 | 1.17 | 36.24 | 0.41 | 0.03 | 63.49 | reconstructed |
| 97 | 12 | - | 105.38 | 32.50 | 32.50 | 3.24 | 1.00 | 105.38 | reconstructed |
| 97 | 13 | - | - | 20.50 | 20.50 | - | 1.00 | 0.00 | reconstructed |
| 97 | 14 | - | 45.74 | 36.41 | 48.17 | 0.95 | 0.76 | 482.43 | reconstructed |
| 97 | 15 | - | 58.44 | 44.01 | 116.72 | 0.50 | 0.38 | 122.63 | reconstructed |
| 97 | 16 | - | 59.89 | 32.05 | 58.88 | 1.02 | 0.54 | -417.58 | reconstructed |
| 97 | 17 | - | 17.38 | 2.70 | 2.70 | 6.44 | 1.00 | 34.76 | reconstructed |
| 98 | 1 | - | 20.32 | 21.31 | 72.67 | 0.28 | 0.29 | -62.31 | reconstructed |
| 98 | 2 | - | 92.68 | 57.95 | 14.85 | 6.24 | 3.90 | 336.90 | reconstructed |
| 98 | 3 | - | 131.25 | 77.72 | 23.82 | 5.51 | 3.26 | 690.37 | reconstructed |
| 98 | 4 | - | 53.81 | 51.41 | 9.77 | 5.51 | 5.26 | 348.87 | reconstructed |
| 99 | 1 | - | 152.04 | 124.27 | 432.00 | 0.35 | 0.29 | -708.40 | reconstructed |
| 99 | 2 | - | 387.96 | 224.93 | 539.37 | 0.72 | 0.42 | 1,279.07 | reconstructed |
| 99 | 3 | - | 239.19 | 152.34 | 157.83 | 1.52 | 0.97 | -1,012.56 | reconstructed |
| 99 | 4 | - | 985.94 | 1,007.34 | 629.38 | 1.57 | 1.60 | 1,500.63 | reconstructed |
| 99 | 5 | - | 64.84 | 67.95 | 35.75 | 1.81 | 1.90 | 261.99 | reconstructed |
| 99 | 6 | - | 133.65 | 135.00 | 125.33 | 1.07 | 1.08 | 167.97 | reconstructed |
| 99 | 7 | - | 68.77 | 59.44 | 149.36 | 0.46 | 0.40 | -641.82 | reconstructed |
| 99 | 8 | - | 448.35 | 264.89 | 211.12 | 2.12 | 1.25 | -842.19 | reconstructed |
| 99 | 9 | - | - | 14.00 | 14.00 | - | 1.00 | 0.00 | reconstructed |
| 99 | 10 | - | 117.43 | 110.66 | 52.70 | 2.23 | 2.10 | 217.68 | reconstructed |
| 99 | 11 | - | 153.10 | 132.35 | 122.01 | 1.25 | 1.08 | 663.41 | reconstructed |
| 99 | 12 | - | 97.23 | 15.91 | 45.59 | 2.13 | 0.35 | 288.39 | reconstructed |
| 99 | 13 | - | 74.66 | 30.48 | 80.63 | 0.93 | 0.38 | 656.31 | reconstructed |
| 99 | 14 | - | 64.84 | 70.92 | 89.00 | 0.73 | 0.80 | 298.24 | reconstructed |
| 99 | 15 | - | 106.20 | 117.66 | 57.25 | 1.86 | 2.06 | 77.01 | reconstructed |
| 99 | 16 | - | 118.26 | 50.47 | 95.50 | 1.24 | 0.53 | -67.83 | reconstructed |
| 99 | 17 | - | 327.95 | 335.78 | 354.46 | 0.93 | 0.95 | 3,272.63 | reconstructed |
| 99 | 18 | - | 56.38 | 66.19 | 66.19 | 0.85 | 1.00 | 489.00 | reconstructed |
| 99 | 19 | - | 102.94 | 67.80 | 128.00 | 0.80 | 0.53 | 711.61 | reconstructed |
| 99 | 20 | - | 64.84 | 70.92 | 109.90 | 0.59 | 0.65 | 291.28 | reconstructed |
| 99 | 21 | - | 64.06 | 4.50 | 4.50 | 14.24 | 1.00 | 192.18 | reconstructed |
| 99 | 22 | - | 142.89 | 4.50 | 4.50 | 31.75 | 1.00 | 142.89 | reconstructed |
| 100 | 1 | - | 300.00 | 41.40 | 3,056.20 | 0.10 | 0.01 | -11,584.02 | reconstructed |
| 100 | 2 | - | 300.00 | 41.40 | 1,575.00 | 0.19 | 0.03 | -6,572.43 | reconstructed |
| 100 | 3 | - | 300.00 | 41.40 | 267.50 | 1.12 | 0.15 | 2,273.55 | reconstructed |

Net per round:

| game | net |
|---|---|
| 91 | 1,104.47 |
| 92 | -3,940.55 |
| 93 | 3,719.77 |
| 94 | 2,591.64 |
| 95 | 10,578.64 |
| 96 | -2,604.49 |
| 97 | 1,676.51 |
| 98 | 1,313.84 |
| 99 | 7,237.49 |
| 100 | -15,882.90 |
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
