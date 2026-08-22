# case_analysis — data layout

Pipeline: `fetch_data.py` → `data/raw/` → `analyze.py` → `data/analysis.json` → `dashboard.py` → interactive figure / `data/dashboard.png`.

```bash
python3 case_analysis/fetch_data.py      # pull everything settled (incremental; --force re-pulls)
python3 case_analysis/analyze.py         # build data/analysis.json
python3 case_analysis/dashboard.py       # open the trend dashboard (--save writes a PNG)
```

All monetary values are gross totals per Line Item, matching the game rules.
Vocabulary follows `docs/CONTEXT.md`: Charge `a`, Limit `b`, Fair Value `t`.

## `data/raw/` — verbatim leaderboard pulls (gitignored, regenerable)

| File | Source endpoint | Contents |
| --- | --- | --- |
| `games.json` | `/leaderboard/api/games?page_size=1000` | `[{id, start_time, status}]` for all 100 games |
| `matrix.json` | `/leaderboard/api/matrix` | team list + pairwise net matrix |
| `performance.json` | `/leaderboard/api/performance?team=..` | one row per team: `income, costs, net, issued/reviewed counters` |
| `transactions_game_NNN.json` | `/leaderboard/api/transactions?game_id=..&team=..` | every unique settled Transaction row of game NNN: `{issuer, reviewer, line_item_index, accepted, amount}` |

`amount` semantics (README R9, corrected against real data): it is always what
the **Issuer receives** — the `0.5a` lawyer fee never appears in a row.

## `data/analysis.json` — the strategy-ready artifact

```jsonc
{
  "generated_from": { "settled_games": [1, ...], "n_teams": 17, "total_games_scheduled": 100 },
  "teams": ["error404 ai", ...],

  "games": [
    {
      "game_id": 1,
      "n_line_items": 18,
      "line_items": [
        {
          "line_item_index": 1,

          // every team's recovered Charge a (fair rejections publish a exactly;
          // accepted-only issuers show min(a, c), a lower bound on their a)
          "charges_a": { "<team>": 122.94, ... },

          // was the team's charge in the fair zone? true / false / null (undetermined)
          "fair_flags": { "<team>": true, ... },

          // every team's Limit b as an interval reconstructed from its
          // accept (b >= a) / reject (b < a) decisions; b_hi null = unbounded
          "limits_b": { "<team>": { "b_lo": 100.0, "b_hi": 150.0 }, ... },

          "avg_a": 87.1,        // mean of known nonzero Charges across teams
          "avg_b_mid": 95.3,    // mean of bounded Limit-interval midpoints (null if none)

          // the secret Fair Value t, bracketed from the rules:
          //   t_lo = max fair Charge (rejected & amount > 0 => a <= t, a = amount)
          //   t_hi = min amount received by a fraudulent issuer (null if unbounded)
          "t_lo": 122.94,
          "t_hi": null,
          "t_point": 122.94     // working point estimate: bracket midpoint, else t_lo
        }
      ],

      // per team, per line item: the t the team appears to have derived
      "team_t_estimates": [
        {
          "team": "<team>",
          "items": [
            {
              "line_item_index": 1,
              "a": 122.94,            // their Charge (null if unknown / zero-default)
              "b_lo": 100.0, "b_hi": 150.0,
              "t_from_a": 175.6,      // a / 0.7 (deployed R5b charge ratio)
              "t_from_b": 125.0,      // Limit-interval midpoint
              "t_hat": 150.3,         // mean of the available signals
              "true_t_lo": 122.94, "true_t_hi": null
            }
          ]
        }
      ]
    }
  ],

  // cross-game aggregates per team, sorted by net (for strategy targeting)
  "team_summary": [
    {
      "team": "error404 ai",
      "net": 85197.38, "income": 131216.91, "costs": 46019.53,
      "n_nonzero_charges": 50,
      "n_fair_charges": 31,          // line items charged in the fair zone
      "n_fraud_charges": 36,         // line items charged in the fraud zone
      "fraud_rate": 0.54,            // fraud / (fair + fraud)
      "median_a_over_t": 1.64        // charge aggressiveness vs. t_point
    }
  ]
}
```

### How t is estimated from the published rows

Per GAME_DESCRIPTION.md, a wrongful rejection charges the reviewer `1.5a`
while the issuer still receives `a`. The published `amount` is the issuer
side, so:

- `rejected & amount > 0` ⇒ the Charge was **fair** (`a ≤ t`) and `a = amount` → raises `t_lo`
- `rejected & amount = 0` ⇒ the Charge was **fraudulent** (`a > t`)
- `accepted` ⇒ `amount = min(a, c)`; if that issuer was rejected-at-0 by
  someone else, the amount is `> t` and lowers `t_hi`

The bracket `[t_lo, t_hi)` narrows with every settled game; `t_point` is the
single number to feed into pricing when one is needed.

## `data/dashboard.png` — snapshot of the six dashboard panels

Leaderboard, t brackets vs. field Charges, per-game pricing trend, per-team
charge aggressiveness, per-team fraud-zone rate, and the top-5 teams' derived
t̂ against the true bracket.
