# Historical Field backtesting

This package reconstructs settled WireClaim Games from the public Transaction record and
scores counterfactual submissions against the historical Field. It supports four distinct
workflows:

1. build a content-addressed historical dataset;
2. run fresh strategy tracks or isolated candidate strategies;
3. replay Proposals captured in live decision logs without calling a model; and
4. expose historical Games through a local replacement for the Tournament API.

The tournament rules and payoff arithmetic live in [`docs/GAME-AND-PROOFS.md`](../docs/GAME-AND-PROOFS.md).
That document remains the source of truth for how the game works. This guide explains how to
operate and extend the backtesting package without re-deriving those rules.

## Important interpretation rule

Historical Charges, Limits, Fair Values, and Caps are not always point-identified. The
backtester preserves every identified interval and reports lower, midpoint, and upper payoff
values.

- **Lower/upper are identified-set envelopes**, conditional on the selected Cap mode.
- **Midpoint is a representative counterfactual**, not a measured outcome or confidence
  estimate.
- **The envelopes are not confidence intervals.** A wide envelope means the public record
  cannot conclusively rank the compared strategies.
- `actual` is the authoritative net calculated directly from the settled Transactions.
  `actual_reconstructed` replays representative reconstructed values as a diagnostic. A
  cap-censored historical Charge can make that representative differ from the actual
  submission even when the authoritative Transaction identity is valid (Game 67 item 1 is
  the first observed example).

Never compare only midpoint totals when the score envelopes overlap.

## Prerequisites

Run commands from the repository root. Pixi supplies Python and sets `PYTHONPATH` for the
named tasks.

Dataset synchronization reads the public leaderboard API and needs no credentials. Case
extraction and the historical API's real decryption-key passthrough need `TEAM_API_KEY`.
Fresh execution of model-backed tracks also needs the model configuration used by
[`src/api/llm.py`](../src/api/llm.py), such as `AZURE_OPENAI_API_KEY` or `OPENAI_API_KEY`.

```bash
set -a && . .env && set +a
```

Fresh experiment runs read the decrypted Cases. Extract all currently available Cases first:

```bash
pixi run cases
```

Generated datasets, reports, model draws, and API state are written below
`var/backtesting/`. They are local runtime artifacts and are ignored by Git.

## Quick start

```bash
# 1. Fetch settled Transactions and publish a reconstructed dataset.
pixi run backtest-sync --games all

# 2. Validate the current dataset and inspect identifiability.
pixi run python -m backtesting validate
pixi run python -m backtesting diagnose

# 3. Run the default fresh-track experiment on a bounded window.
# This invokes model-backed strategies and can consume quota.
pixi run backtest-run --games 40-53

# 4. Open the generated Markdown report.
# var/backtesting/runs/<run-id>/report.md
```

For a deterministic comparison that makes no model calls, replay saved live Proposals:

```bash
pixi run python -m backtesting replay-logged --games 40-53 --source winner
```

## Game selectors

Commands accepting `--games` use the same selector syntax:

| Selector | Meaning |
| --- | --- |
| `all` | Every available settled Game, excluding Game 0 by default |
| `latest` | Currently an alias for `all` |
| `40` | One Game |
| `40-53` | Inclusive range |
| `40,42,45-48` | Comma-separated values and ranges |
| `40-` | Every available Game numbered 40 or later |

`sync --include-game-0` includes the permanent test Game. For `run`, set the separate
`include_game_0` spec field. `replay-logged` and `serve-api` exclude Game 0.

## CLI reference

The complete parser help is available with:

```bash
pixi run python -m backtesting --help
pixi run python -m backtesting <command> --help
```

### `sync`: build a historical dataset

```bash
pixi run backtest-sync --games all
pixi run backtest-sync --games 40-53 --request-delay 0.25
pixi run backtest-sync --games 40-53 --refresh-transactions
```

`sync` performs the following checks before publishing a dataset:

1. fetches each selected Game from every team's Transaction view, reusing the local raw cache;
2. normalizes the duplicated issuer/reviewer copies into one unique Transaction;
3. requires every ordered team pair for every Line Item;
4. reconstructs Fair Value brackets and every team's Charge and Limit intervals;
5. reproduces leaderboard nets from the normalized Transactions when matrix data is available;
6. hashes the canonical dataset payload and atomically updates the current-dataset pointer.

`--refresh-transactions` bypasses the Transaction cache. `--request-delay` controls the pause
after a newly fetched team/Game view.

Datasets are stored under:

```text
var/backtesting/datasets/
├── current.json
└── <dataset-id-prefix>/
    ├── manifest.json
    ├── games.json
    ├── transactions.{json,csv}
    ├── decisions.{json,csv}
    ├── fair_values.{json,csv}
    ├── line_items.{json,csv}
    ├── games.csv
    └── validation.json
```

The default for later commands is the dataset named by `current.json`. Pass an unambiguous
hash prefix with `--dataset` to pin an older dataset.

### `validate` and `diagnose`: check data quality

```bash
pixi run python -m backtesting validate
pixi run python -m backtesting validate --dataset 0123abcd
pixi run python -m backtesting diagnose
pixi run python -m backtesting diagnose --json
```

`validate` rejects any reconstructed Game whose validation status is not `ok`, then prints the
dataset diagnostics as JSON. `diagnose` prints the same identifiability summary in a compact
table or JSON, including:

- unique Transactions and reconstructed team decisions;
- exact Charge share;
- bounded Limit and Fair Value shares;
- median interval widths; and
- Charge and Cap status counts.

### `run`: execute an experiment

```bash
pixi run backtest-run
pixi run backtest-run --games 40-53
pixi run python -m backtesting run \
  --spec backtesting/specs/default.json \
  --dataset 0123abcd \
  --games 40-53
```

`--games` overrides the Game selector in the spec for scoring while retaining earlier Games
from the dataset as past-only history. A run always loads each selected Case and creates fixed
baselines (`actual`, `actual_reconstructed`, `standard`, `oracle_bracket`, and `oracle_point`).
It then executes the configured repository tracks and candidates.

The default spec runs four fresh tracks three times per Game:

- `strategy1`
- `strategy2`
- `strategy3`
- `fast_path`

Track calls within one draw are concurrent. Draw rounds are sequential. Each call has its own
timeout; failures and missing outputs are recorded instead of aborting all other tracks.
The `merged` result applies the same priority layering as the live runtime over the standard
fallback.

Fresh model-backed tracks call the configured model and can consume significant quota. Set
`"tracks": []` in a separate experiment spec when only deterministic candidates or imported
JSON submissions are needed.

### `replay-logged`: score saved live Proposals

```bash
pixi run python -m backtesting replay-logged --games 40-53 --source winner
pixi run python -m backtesting replay-logged --games 40-53 --source all
pixi run python -m backtesting replay-logged --games 40-53 --source strategy2
pixi run python -m backtesting replay-logged --games 26-41,43-53,55 --source strategy2,strategy5
pixi run python -m backtesting replay-logged --games 62-67 \
  --source strategy2,strategy5 \
  --decisions-dir var/backtesting/runs/<fresh-run-id>/decisions
```

This command reads zero-padded logs such as `var/decisions/game_040.json` and does not call a
model. `--source` accepts:

- `winner`: replay the Proposal selected by the live coordinator;
- `all`: replay every Proposal recorded in the log; or
- a strategy name such as `strategy1` or `strategy2`;
- a comma-separated list for a side-by-side comparison. Historical `strategy5` values are
  deterministically derived from the combined Strategy 2 price evidence in each decision
  log. Strategy 5 estimates one `t` (including its large-item tier) and submits that value as
  both `a` and `b`, so this comparison makes no model calls and changes only the pricing
  policy.

`--decisions-dir` reads the same log schema from an isolated fresh experiment instead of
`var/decisions`. This is useful for extending a comparison without overwriting the live
record. Logged parser rows whose indices are absent from the settled Game are reported and
ignored; a missing settled Line Item remains fatal.

Every selected Game must have a readable decision log, and every selected Proposal must cover
all expected Line Items. The replay checks that logged Charges and Limits lie inside the
intervals reconstructed from actual behavior. It writes the normal report artifacts plus
`logged_replay.json`, including compatibility errors and whether the representative replay
reproduces actual net to the cent.

Use this command for the historical live baseline. Do not replace it with a fresh Strategy 2
draw: a fresh model call is a different sample running current code and prompts.

Strategy 5 uses deliberately coarse point-estimate tiers. With no Strategy 2 price evidence,
the first invoice position uses a primary-loss prior of 8,500 EUR and later positions use a
parts/labour prior of 275 EUR. With evidence, it applies `0.75`, `0.50`, `0.70`, or `1.35`
to Strategy 2's combined median at the 100, 500, and 3,000 EUR breakpoints. Every branch
submits `a = b`, and only a proven dash-quantity exclusion submits zero.

On the 35 Games with reusable live evidence through Game 61 (26-41 and 43-61), its
identified midpoint is **95,989 EUR**, versus **51,620 EUR** for Strategy 2. The later
validation slice 54-61 is independently positive (**13,142 vs 2,448**), after harmless
phantom parser rows in Games 54 and 59 are ignored. The score envelopes still overlap, so
this is a midpoint lead, not an identified-set proof.

Games 62-67 have settled Transaction data and extracted Cases but no live decision logs.
The reproducible extension spec
[`strategy2_games_62_67.json`](specs/strategy2_games_62_67.json) runs Strategy 2 once per
Game with past-only Price Memory and writes isolated decision logs. In the 2026-08-23 local
run, model credentials were unavailable (`model_draws = 0`), so the extension measures the
shared fallback/memory path only. Strategy 5 is positive across the fitted-cap identified
set at **23,583 / 46,278 / 383,439 EUR** (lower/midpoint/upper), while the same-evidence
Strategy 2 baseline is negative at **-86,874 / -79,757 / -52,328 EUR**. These envelopes do
not overlap. The generated Strategy 2 submissions are nevertheless behaviorally incompatible
with the historical live submissions, so do not present this as a victory over the Strategy
2 that actually played Games 62-67; rerun the spec with model credentials to close that
evidence gap.

### `report`: rerender an existing run

```bash
pixi run python -m backtesting report <run-id>
pixi run python -m backtesting report var/backtesting/runs/<run-id>
```

`report` regenerates the CSV and Markdown presentation from an existing `scores.json`. It
makes no Tournament or model calls.

### `serve-api`: replay historical Games through the live client

```bash
pixi run backtest-api \
  --games 40-53 \
  --release-delay 3 \
  --spacing 65 \
  --duration 3600
```

See [Historical Tournament API](#historical-tournament-api) for the client setup and endpoint
semantics.

## Reconstruction and scoring

### What is reconstructed

For each settled Game, the dataset stores:

- one normalized Transaction per `(game, Line Item, issuer, reviewer)`;
- the identified Fair Value interval for each Line Item;
- each team's exact, bounded, or censored Charge interval;
- each team's Limit interval, with acceptance/rejection witnesses;
- observed and empirical Cap floors;
- authoritative team nets; and
- invoice metadata needed for past-only Price Memory.

The reconstruction does not invent exact hidden decisions where the public record identifies
only an interval. Charge statuses distinguish exact, accepted-exact, zero, right-censored,
possibly capped, and Cap-censored observations.

### Counterfactual scoring

A candidate submission is scored against every historical opponent in both roles. The scorer
evaluates the Fair Value, opponent decision, and Cap values at payoff-relevant boundaries, then
returns three values for income, cost, and net:

- `lower`: worst identified payoff;
- `midpoint`: payoff at representative interval values; and
- `upper`: best identified payoff.

When a candidate omits a Line Item, the scorer applies the Tournament default `(Charge=0,
Limit=0)` and increments `missing_outputs`. This is intentionally not treated as harmless.

### Cap modes

| Mode | Behavior |
| --- | --- |
| `fitted` | Uses the fitted relevant Cap floor: the maximum of `4t`, the empirical floor, and the largest observed payment floor. |
| `rules_only` | Evaluates both that floor and, when larger, the maximum candidate Charge, candidate Limit, or reconstructed opponent Charge lower bound. |

`fitted` is the default. Use `rules_only` to expose sensitivity to Cap uncertainty rather than
treating the fitted floor as the exact hidden Cap.

### Time safety

For Game `g`, `HistoryView` contains only Games with IDs below `g`. Existing fresh tracks also
receive a Price Memory rebuilt only from earlier Games. Future Games are excluded even when
they are present in the selected dataset.

This prevents dynamic history leakage. It does not make current prompts and constants
historical: fresh tracks still evaluate the code checked out at the run's recorded Git
revision against old Cases. The generated report states this distinction explicitly.

## Experiment specifications

[`specs/default.json`](specs/default.json) is the canonical version-1 example:

```json
{
  "version": 1,
  "name": "all-settled-field-backtest",
  "games": "all",
  "seat": "Bin busy",
  "draws": 3,
  "timeout_seconds": 60,
  "cap_mode": "fitted",
  "include_game_0": false,
  "seed": 20260822,
  "tracks": ["strategy1", "strategy2", "strategy3", "fast_path"],
  "candidates": [],
  "sweeps": [],
  "validation": {
    "holdout_fraction": 0.3,
    "walk_forward_min_train": 5,
    "walk_forward_step": 1
  },
  "regimes": [
    {"name": "awake", "start": 1, "end": 43},
    {"name": "dark", "start": 44, "end": 81},
    {"name": "recalibrated", "start": 82, "end": 100}
  ]
}
```

| Field | Meaning |
| --- | --- |
| `version` | Required schema version; currently `1` |
| `name` | Human-readable run name |
| `games` | Game selector used unless the CLI supplies `--games` |
| `seat` | Team whose counterfactual net is scored |
| `draws` | Fresh executions per configured repository track |
| `timeout_seconds` | Timeout for each fresh track call |
| `cap_mode` | `fitted` or `rules_only` |
| `include_game_0` | Include Game 0 when selecting Games |
| `seed` | Base seed exposed to candidate contexts |
| `tracks` | Any subset of the four built-in fresh tracks |
| `candidates` | Isolated Python or JSON candidate definitions |
| `sweeps` | Parameter grids and their selection objective |
| `validation` | Chronological holdout and walk-forward settings |
| `regimes` | Named inclusive Game ranges for report breakdowns |

Copy the default spec to a new JSON file for an experiment. Do not edit the live Strategy 2
implementation merely to define a backtesting candidate.

## Candidate strategies

Candidates are independent of the built-in fresh tracks and support two input interfaces.
Each candidate definition must set exactly one of `entrypoint` or `submissions`.

### Python entry point

A Python candidate is loaded from `module:function`. The callable may be synchronous or
asynchronous and receives:

1. a `StrategyContext` containing the parsed Case, past-only `HistoryView`, and deterministic
   seed; and
2. the candidate's parameter mapping.

For example, a module such as `backtesting/candidates/fixed.py` could expose:

```python
from backtesting.strategies import StrategyContext


def propose(context: StrategyContext, params):
    return {
        item.index: (float(params["charge"]), float(params["limit"]))
        for item in context.case.line_items
    }
```

The spec entry is:

```json
{
  "name": "fixed",
  "entrypoint": "backtesting.candidates.fixed:propose",
  "params": {"charge": 100.0, "limit": 35.0}
}
```

A callable may return:

- a mapping from Line Item index to `(charge, limit)`;
- a mapping to `Submission` objects;
- a mapping to `{"charge": ..., "limit": ...}` objects; or
- a repository `Proposal`.

Unknown Line Item indices fail immediately. Missing indices also fail unless
`"allow_missing": true`; if allowed, they are scored as Tournament defaults `(0, 0)` and
reported as missing outputs.

### JSON submissions

Precomputed submissions can be imported without executing candidate code:

```json
{
  "version": 1,
  "games": {
    "40": {
      "1": {"charge": 100.0, "limit": 35.0},
      "2": [250.0, 80.0]
    }
  }
}
```

Reference the file from the experiment spec:

```json
{
  "name": "offline-candidate",
  "submissions": "path/to/submissions.json"
}
```

A submission file may alternatively contain a top-level `strategies` mapping. In that form,
the candidate's `name` selects the matching strategy key.

### Parameter sweeps

A sweep expands a candidate's base parameters over a Cartesian grid:

```json
{
  "candidates": [
    {
      "name": "fixed",
      "entrypoint": "backtesting.candidates.fixed:propose",
      "params": {"charge": 100.0, "limit": 35.0}
    }
  ],
  "sweeps": [
    {
      "candidate": "fixed",
      "grid": {
        "charge": [70.0, 100.0, 130.0],
        "limit": [20.0, 35.0]
      },
      "objective": "midpoint_net"
    }
  ]
}
```

Supported objectives are `midpoint_net` and `lower_net`. The report contains:

- full-window scores for every grid cell, which are descriptive and in-sample;
- one chronological train/holdout selection; and
- expanding walk-forward selections using only earlier Games to choose parameters.

Only the chronological holdout and walk-forward rows are out-of-sample. Treat gains below the
reported noise floor cautiously, especially for model-backed candidates.

## Run artifacts

Every `run` creates a unique directory under `var/backtesting/runs/` whose name contains a UTC
timestamp and spec hash:

```text
var/backtesting/runs/<run-id>/
├── manifest.json
├── dataset_manifest.json
├── spec.json
├── scores.json
├── scores.csv
├── per_item.csv
├── sweeps.json
├── sweeps.csv
├── diagnostics.json
├── report.md
├── decisions/
└── draws/game_040/<draw>/<track>.json
```

Key files:

| Artifact | Purpose |
| --- | --- |
| `manifest.json` | Dataset ID, Git revision, Games, seat, Cap mode, tracks, and scaled noise floor |
| `scores.json` | Canonical machine-readable run result used by `report` |
| `scores.csv` | Pooled income, cost, and net envelopes by strategy |
| `per_item.csv` | Line Item-level payoff envelopes |
| `sweeps.{json,csv}` | Grid cells and chronological validation results |
| `diagnostics.json` | Dataset identifiability and score ambiguity counts |
| `report.md` | Human-readable strategy, regime, variance, validation, and caveat report |
| `draws/` | Raw output, runtime, timeout, and error for every fresh track draw |
| `decisions/` | Decision logs isolated from the live `var/decisions/` directory |

The spec bytes, dataset manifest, dataset ID, Git revision, and schema versions provide the
provenance needed to audit and rerun an experiment. Fresh model outputs remain nondeterministic.

## Historical Tournament API

`serve-api` schedules selected historical Game IDs at new local times and serves the same
endpoints used by the live client. It is intended for end-to-end testing of the real runner,
including repeated submissions and deadlines.

Start the server in one terminal:

```bash
set -a && . .env && set +a
pixi run backtest-api \
  --games 40-53 \
  --host 127.0.0.1 \
  --port 8765 \
  --release-delay 3 \
  --spacing 65 \
  --duration 3600
```

Point the normal client at it in a second terminal:

```bash
set -a && . .env && set +a
export BASE_URL=http://127.0.0.1:8765
pixi run start
```

Use `pixi run play` instead of `start` for an unattended, supervised replay. Keep a valid
`TEAM_API_KEY`: the local key endpoint deliberately fetches the released decryption key from
the real Tournament API so the normal encrypted Case flow remains intact.

### Timing options

| Option | Default | Meaning |
| --- | ---: | --- |
| `--release-delay` | 3 s | Delay before the first selected Game starts |
| `--spacing` | 65 s | Time between consecutive Game starts |
| `--duration` | 3600 s | Submission window for each Game |

The long default duration allows inspection and repeated submissions; it is not the live
60-second Tournament duration. Durations longer than spacing intentionally allow Games to
overlap.

### Endpoints

| Method and path | Behavior |
| --- | --- |
| `GET /health` | Health check; no API key required |
| `GET /api/games/list` | Locally scheduled Games and status |
| `GET /api/games/{id}/key` | Real released decryption key, gated by local start time |
| `PUT /api/games/{id}/submissions` | Record a full or partial submission update |
| `GET /backtesting/results/{id}` | Current submissions and score envelope |

Every endpoint except `/health` requires a non-empty `X-API-Key` header. The header value and
decryption key are not persisted in the request log.

Updates are last-write-wins per Line Item. Partial updates preserve earlier values for other
Line Items. An item never submitted remains `(0, 0)` when scored. Submissions before start or
after the deadline are rejected.

Press Enter in the server terminal to print every Game's current item coverage, score envelope,
and historical actual net. Games finalize automatically after their deadline.

The server always scores the `Bin busy` seat in `fitted` Cap mode; `serve-api` exposes no
`--seat` or `--cap-mode` override. API state is stored under:

```text
var/backtesting/api_runs/<timestamp-and-games>/
├── api_requests.jsonl
└── game_040.json
```

`api_requests.jsonl` records method, path, response status, client address, elapsed time, and a
sanitized submission payload. Each Game JSON contains the latest state and complete update
log.

## Methodology and caveats

- The historical Field is held fixed. A counterfactual does not model opponents adapting to a
  strategy they did not actually face.
- Current code and prompts are evaluated retrospectively. Only dynamic Game history and Price
  Memory are constrained to information available before each Game.
- Full-sample sweep winners are in-sample. Use chronological holdout and walk-forward results
  before changing a live strategy.
- The measured prompt noise floor is scaled to the selected Game window and recorded in each
  run manifest. Repeat model-backed draws and hold Games out before trusting small gains.
- Cap uncertainty and censored opponent decisions can make a ranking unidentified. Inspect
  envelope widths and ambiguity counts, not only midpoint net.
- A missing candidate output invokes `(0, 0)`, which wrongfully rejects fair claims. Do not use
  `allow_missing` as a routine fallback.
- The default fresh experiment is expensive: Games × tracks × draws determines the number of
  track invocations before any candidate calls.

## Troubleshooting

### `Cases are not extracted`

```bash
pixi run cases
```

Fresh `run` experiments require `policy.txt` for every selected Game, even if the configured
tracks are empty.

### `TEAM_API_KEY is missing`

Load the repository `.env` before extracting Cases or running the historical API with real
key passthrough:

```bash
set -a && . .env && set +a
```

### A dataset prefix matches zero or multiple directories

Use a longer unique prefix from `var/backtesting/datasets/<dataset-id-prefix>/manifest.json`,
or omit `--dataset` to use `current.json`.

### No decision log exists for a replayed Game

`replay-logged` is intentionally strict. Select only Games with a zero-padded log such as
`var/decisions/game_040.json`, or use a fresh `run` if a historical Proposal was never logged.
Do not silently substitute reconstructed values for a missing live decision.

### A candidate omits Line Items

Return every `context.case.line_items` index. Set `allow_missing` only for an explicit failure
experiment, because omitted items are scored as `(0, 0)`.

### A strategy ranking changes between runs

Inspect `tracks` in `scores.json`, pooled score envelopes, and the reported noise floor. Fresh
model calls can vary even with an unchanged prompt. Logged replay and report rerendering are
deterministic; fresh track execution is not.

## Module map

| Module | Responsibility |
| --- | --- |
| [`cli.py`](cli.py) | CLI parsing and dispatch |
| [`data.py`](data.py) | Acquisition, validation, content-addressed dataset persistence |
| [`reconstruction.py`](reconstruction.py) | Fair Value, Charge, Limit, and Cap reconstruction |
| [`models.py`](models.py) | Canonical interval, dataset, submission, and score models |
| [`scoring.py`](scoring.py) | Cap-aware counterfactual payoff envelopes |
| [`history.py`](history.py) | Past-only history and time-safe Price Memory |
| [`tracks.py`](tracks.py) | Fresh isolated execution of built-in repository tracks |
| [`strategies.py`](strategies.py) | Candidate protocol, loading, validation, and fixed baselines |
| [`experiments.py`](experiments.py) | End-to-end experiment orchestration |
| [`sweeps.py`](sweeps.py) | Grid expansion, chronological holdout, and walk-forward selection |
| [`logged.py`](logged.py) | Deterministic replay of live decision logs |
| [`api_server.py`](api_server.py) | Drop-in historical Tournament API |
| [`diagnostics.py`](diagnostics.py) | Dataset identifiability and score ambiguity summaries |
| [`reporting.py`](reporting.py) | JSON, CSV, terminal, and Markdown reports |
| [`paths.py`](paths.py) | Artifact locations and schema versions |

## Tests

Run all focused backtesting tests with:

```bash
pixi run python -m unittest discover -s tests -p 'test_backtesting*.py' -v
```

Run the complete repository suite before promoting a backtested change into the live runtime:

```bash
pixi run test
```
