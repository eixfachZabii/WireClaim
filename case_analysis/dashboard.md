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
| 59 | 1 | Remove water-damaged laminate in living room (18 m²) | 299.23 | 299.23 | 540.00 | 0.55 | 0.55 | -278.41 | submitted |
| 59 | 2 | Supply & install premium oak laminate incl. impact (18 m²) | 1,428.18 | 701.77 | 1,451.09 | 0.98 | 0.48 | 3,211.92 | submitted |
| 59 | 3 | Supply and install skirting boards (premium solid oak, | 321.94 | 321.94 | 1,036.19 | 0.31 | 0.31 | -3,546.22 | submitted |
| 59 | 4 | Disassembly and disposal of damaged floor tiles in (6 m²) | 350.57 | 211.50 | 315.53 | 1.11 | 0.67 | -759.87 | submitted |
| 59 | 5 | Supply & install premium large-format Italian porcelain (6 m²) | 1,200.66 | 569.03 | 1,011.83 | 1.19 | 0.56 | -6,309.06 | submitted |
| 59 | 6 | Cleaning of entire apartment (1 flat rate) | 177.70 | 0.00 | 5.68 | 31.26 | 0.00 | 0.00 | submitted |
| 59 | 7 | Paint lower wall after water damage incl. surface (20 m²) | 524.94 | 320.86 | 619.72 | 0.85 | 0.52 | 311.08 | submitted |
| 59 | 8 | Full ceiling paint living room (15 m²) | 356.65 | 0.00 | 15.60 | 22.86 | 0.00 | 0.00 | submitted |
| 59 | 9 | Wallpapering work hallway (8 m²) | 350.77 | 0.00 | 0.00 | - | - | 0.00 | submitted |
| 60 | 1 | Speaker system (surge damaged) (1 pcs) | 281.49 | 281.49 | 140.75 | 2.00 | 2.00 | 3,659.37 | submitted |
| 60 | 2 | Premium replacement TV set (larger, higher-end than (1 pcs) | 2,065.13 | 708.00 | 544.30 | 3.79 | 1.30 | -1,768.76 | submitted |
| 60 | 3 | HDMI cables and connectors | 64.06 | 0.00 | 2.64 | 24.27 | 0.00 | 0.00 | submitted |
| 60 | 4 | Wall-mount bracket | 64.06 | 0.00 | 2.80 | 22.88 | 0.00 | 0.00 | submitted |
| 60 | 5 | Remote control | 64.06 | 0.00 | 2.28 | 28.10 | 0.00 | 0.00 | submitted |
| 60 | 6 | Games console (switched off and unplugged at the | 64.06 | 0.00 | 0.00 | - | - | 0.00 | submitted |
| 60 | 7 | Shipping (1 pcs) | 26.95 | 0.00 | 0.00 | - | - | 0.00 | submitted |
| 60 | 8 | Installation (1 pcs) | 264.26 | 0.00 | 22.50 | 11.74 | 0.00 | 0.00 | submitted |
| 60 | 9 | Diagnostic inspection and surge-failure report for (2 pcs) | 418.48 | 0.00 | 15.50 | 27.00 | 0.00 | 0.00 | submitted |
| 60 | 10 | Wiring safety check of property distribution board | 64.06 | 0.00 | 13.50 | 4.75 | 0.00 | 192.18 | submitted |
| 60 | 11 | Vehicle costs (1 pcs) | 51.75 | 0.00 | 1.45 | 35.81 | 0.00 | 155.25 | submitted |
| 61 | 1 | Painting the disturbed wall area and closing the wall (1   pcs) | 680.33 | 425.12 | 680.33 | 1.00 | 0.62 | 3,358.26 | submitted |
| 61 | 2 | Vehicle costs (1   flat rate) | 50.34 | 50.34 | 78.85 | 0.64 | 0.64 | -189.54 | submitted |
| 61 | 3 | Sealing material (1   pcs) | 15.98 | 15.98 | 24.46 | 0.65 | 0.65 | 31.33 | submitted |
| 61 | 4 | Stainless steel pipe (1   m) | 26.26 | 26.26 | 45.00 | 0.58 | 0.58 | -251.99 | submitted |
| 61 | 5 | Rock wool pipe insulation (1   m) | 19.17 | 19.17 | 28.87 | 0.66 | 0.66 | 180.57 | submitted |
| 61 | 6 | Installer hours (1   hrs) | 72.71 | 42.75 | 88.30 | 0.82 | 0.48 | -47.77 | submitted |
| 61 | 7 | Measuring device (1   pcs) | 64.12 | 0.00 | 2.55 | 25.15 | 0.00 | 64.12 | submitted |
| 61 | 8 | Service technician hours (9   hrs) | 587.66 | 587.66 | 839.00 | 0.70 | 0.70 | -228.35 | submitted |
| 61 | 9 | Vehicle costs (1   pcs) | 50.34 | 0.00 | 6.14 | 8.20 | 0.00 | 151.02 | submitted |
| 61 | 10 | Construction dryer flat-rate charge (1   flat rate) | 370.53 | 370.53 | 585.00 | 0.63 | 0.63 | 1,030.00 | submitted |
| 61 | 11 | Short saw blade (1   pcs) | 12.39 | 0.00 | 2.12 | 5.83 | 0.00 | 12.39 | submitted |
| 61 | 12 | Gunmetal (2   pcs) | 48.77 | 48.77 | 74.80 | 0.65 | 0.65 | 155.28 | submitted |
| 61 | 13 | Stainless steel pipe (1   m) | 26.26 | 0.00 | 45.00 | 0.58 | 0.00 | -100.60 | submitted |
| 61 | 14 | Pipe insulation shell, 100 cm long (1   m) | 12.28 | 8.54 | 30.60 | 0.40 | 0.28 | -49.43 | submitted |
| 61 | 15 | Service technician hours (9   hrs) | 587.66 | 0.00 | 800.00 | 0.73 | 0.00 | 16.05 | submitted |
| 62 | 1 | Renew boiler system including flue gas system and (1   flat rate) | 10,349.89 | 0.00 | 9,427.30 | 1.10 | 0.00 | -25,468.65 | submitted |
| 62 | 2 | Adjust supply pipework to fit the replacement boiler (1   flat rate) | 597.25 | 0.00 | 214.84 | 2.78 | 0.00 | 836.00 | submitted |
| 62 | 3 | Dispose of the old boiler system (1   flat rate) | 331.59 | 0.00 | 626.33 | 0.53 | 0.00 | -349.50 | submitted |
| 62 | 4 | Vehicle costs (1   flat rate) | 58.95 | 0.00 | 84.42 | 0.70 | 0.00 | 87.59 | submitted |
| 62 | 5 | Installer hours (6   hrs) | 376.23 | 0.00 | 454.84 | 0.83 | 0.00 | 2,728.35 | submitted |
| 62 | 6 | Vehicle costs (1   flat rate) | 58.95 | 0.00 | 40.34 | 1.46 | 0.00 | 360.57 | submitted |
| 62 | 7 | Procurement of a heat pump (1   flat rate) | 8,617.22 | 0.00 | 1,152.81 | 7.47 | 0.00 | 2,278.22 | submitted |
| 62 | 8 | Submersible pump (1   pcs) | 134.79 | 0.00 | 16.50 | 8.17 | 0.00 | 134.79 | submitted |
| 62 | 9 | Vacuum water (1   flat rate) | 255.29 | 0.00 | 16.50 | 15.47 | 0.00 | 1,787.03 | submitted |
| 62 | 10 | Small electrical materials for the rewiring (1   flat rate) | 90.82 | 0.00 | 50.54 | 1.80 | 0.00 | 329.91 | submitted |
| 63 | 1 | Air conditioning unit (kitchen) (1   pcs) | 1,400.64 | 1,213.16 | 27.09 | 51.71 | 44.79 | -2,346.02 | submitted |
| 63 | 2 | Installation (1   pcs) | 419.76 | 419.76 | 38.25 | 10.97 | 10.97 | -1,389.48 | submitted |
| 63 | 3 | Floor console (1   pcs) | 62.90 | 62.90 | 9.75 | 6.45 | 6.45 | 71.77 | submitted |
| 63 | 4 | Freight shipping (1   pcs) | 40.25 | 40.25 | 5.76 | 6.99 | 6.99 | -168.28 | submitted |
| 64 | 1 | Remove & reinstall water-damaged laminate incl. (1   flat rate) | 1,765.28 | 708.00 | 1,933.43 | 0.91 | 0.37 | 3,851.78 | submitted |
| 64 | 2 | Remove & reinstall bathroom floor tiles incl. material (1   flat rate) | 1,746.78 | 708.00 | 1,059.07 | 1.65 | 0.67 | -3,862.19 | submitted |
| 64 | 3 | Prepare & repaint water-damaged lower living-room (20   m²) | 668.86 | 404.37 | 633.38 | 1.06 | 0.64 | -3,416.49 | submitted |
| 65 | 1 | - | 43.63 | 29.95 | 51.80 | 0.84 | 0.58 | 464.82 | reconstructed |
| 65 | 2 | - | 20.98 | 20.95 | 27.54 | 0.76 | 0.76 | 33.85 | reconstructed |
| 65 | 3 | - | 199.01 | 181.58 | 291.34 | 0.68 | 0.62 | -1,930.74 | reconstructed |
| 65 | 4 | - | 24.79 | 18.27 | 3.19 | 7.77 | 5.73 | 109.32 | reconstructed |
| 65 | 5 | - | 31.55 | 31.74 | 42.34 | 0.75 | 0.75 | 398.08 | reconstructed |
| 65 | 6 | - | 450.23 | 258.37 | 28.50 | 15.80 | 9.07 | -1,030.95 | reconstructed |
| 65 | 7 | - | 289.21 | 22.50 | 22.50 | 12.85 | 1.00 | 289.21 | reconstructed |
| 65 | 8 | - | - | 14.53 | 14.53 | - | 1.00 | 0.00 | reconstructed |
| 65 | 9 | - | - | 12.00 | 12.00 | - | 1.00 | 0.00 | reconstructed |
| 65 | 10 | - | - | 22.50 | 22.50 | - | 1.00 | 0.00 | reconstructed |
| 65 | 11 | - | - | 7.50 | 7.50 | - | 1.00 | 0.00 | reconstructed |
| 65 | 12 | - | - | 14.50 | 14.50 | - | 1.00 | 0.00 | reconstructed |
| 65 | 13 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 65 | 14 | - | - | 9.16 | 9.16 | - | 1.00 | 0.00 | reconstructed |
| 65 | 15 | - | 215.88 | 30.55 | 30.55 | 7.07 | 1.00 | 431.76 | reconstructed |
| 65 | 16 | - | 220.36 | 22.50 | 22.50 | 9.79 | 1.00 | 220.36 | reconstructed |
| 66 | 1 | - | 2,207.47 | 759.20 | 2,207.47 | 1.00 | 0.34 | 19,239.91 | reconstructed |
| 66 | 2 | - | 597.29 | 415.69 | 326.66 | 1.83 | 1.27 | -215.14 | reconstructed |
| 67 | 1 | - | 2,000.00 | 1,020.83 | 16.50 | 121.21 | 61.87 | 3,925.35 | reconstructed |
| 67 | 2 | - | 290.57 | 299.50 | 344.78 | 0.84 | 0.87 | 3,901.22 | reconstructed |
| 67 | 3 | - | 401.29 | 410.55 | 698.84 | 0.57 | 0.59 | -492.03 | reconstructed |
| 67 | 4 | - | 66.58 | 68.92 | 82.17 | 0.81 | 0.84 | 710.14 | reconstructed |
| 67 | 5 | - | 860.19 | 563.54 | 563.54 | 1.53 | 1.00 | 4,617.14 | reconstructed |
| 67 | 6 | - | 57.47 | 61.45 | 42.79 | 1.34 | 1.44 | 291.71 | reconstructed |
| 67 | 7 | - | 478.72 | 370.47 | 20.82 | 22.99 | 17.79 | 461.36 | reconstructed |
| 67 | 8 | - | - | 16.50 | 16.50 | - | 1.00 | 0.00 | reconstructed |
| 67 | 9 | - | - | 16.50 | 16.50 | - | 1.00 | 0.00 | reconstructed |
| 67 | 10 | - | - | 8.50 | 8.50 | - | 1.00 | 0.00 | reconstructed |
| 68 | 1 | - | 551.11 | 387.06 | 1,554.59 | 0.35 | 0.25 | -3,676.94 | reconstructed |
| 68 | 2 | - | 223.11 | 142.48 | 499.12 | 0.45 | 0.29 | -827.83 | reconstructed |
| 68 | 3 | - | 256.20 | 224.55 | 855.00 | 0.30 | 0.26 | -66.74 | reconstructed |
| 68 | 4 | - | 540.60 | 48.88 | 2,234.00 | 0.24 | 0.02 | -6,490.81 | reconstructed |
| 68 | 5 | - | 5,941.79 | 525.39 | 2,635.50 | 2.25 | 0.20 | 734.12 | reconstructed |
| 68 | 6 | - | - | 0.00 | 0.00 | - | - | 0.00 | reconstructed |
| 68 | 7 | - | 15.94 | 2.70 | 2.70 | 5.90 | 1.00 | 15.94 | reconstructed |
| 68 | 8 | - | - | 8.00 | 8.00 | - | 1.00 | 0.00 | reconstructed |
| 68 | 9 | - | 309.24 | 226.46 | 177.61 | 1.74 | 1.28 | -25.73 | reconstructed |
| 68 | 10 | - | 266.69 | 179.06 | 140.25 | 1.90 | 1.28 | 618.14 | reconstructed |
| 68 | 11 | - | - | 10.62 | 10.62 | - | 1.00 | 0.00 | reconstructed |

Net per round:

| game | net |
|---|---|
| 59 | -7,370.56 |
| 60 | 2,238.04 |
| 61 | 4,131.32 |
| 62 | -17,275.69 |
| 63 | -3,832.01 |
| 64 | -3,426.91 |
| 65 | -1,014.30 |
| 66 | 19,024.77 |
| 67 | 13,414.89 |
| 68 | -9,719.85 |
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
