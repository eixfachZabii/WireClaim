# WireClaim

Python scaffolding for the QuantCo Claim to Fame challenge. The current scope is
scheduled case ingestion: read the EHL game schedule, retrieve a key at its UTC
start time, decrypt the matching archive, publish verified case files, and invoke
a downstream processing hook.

It deliberately does **not** post submissions. The future submission boundary is
marked with `TODO(api-submission)` under `src/api` and in the placeholder pipeline.

## Runtime flow

```text
GET /api/games/list
    -> wait for start_time
    -> GET /api/games/{id}/key
    -> decrypt case_{id:02d}.zip into a staging directory
    -> validate and checksum files
    -> atomically publish var/cases/case_N/input
    -> invoke WIRECLAIM_PROCESSOR
```

The supplied encrypted archives remain in `[PUBLIC] EHL Cases/cases`; they are
not copied or modified. Decrypted files, manifests, and local state under `var/`
are ignored by Git.

## Setup

The easiest setup uses the included Pixi environment:

```bash
pixi install
export TEAM_API_KEY="..."
pixi run doctor
```

Alternatively, use Python 3.11+ with 7-Zip on `PATH`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
export TEAM_API_KEY="..."
wireclaim doctor
```

Configuration options are documented in `.env.example`. The application reads
environment variables directly; it does not automatically load `.env` files.

## Commands

```bash
wireclaim doctor          # Check credentials, archives, 7-Zip, and hook config
wireclaim games           # Print the authenticated UTC game schedule
wireclaim watch           # Run the long-lived schedule watcher
wireclaim ingest 0        # Ingest and trigger one game immediately
wireclaim process 0       # Re-trigger an already extracted case, offline
wireclaim status          # Inspect durable local lifecycle state
```

The watcher refreshes the schedule every 15 seconds by default, sleeps until the
next known `start_time`, retries briefly if the key endpoint still returns 403,
and catches up unfinished games after restarts. It never stores keys.

## Downstream hook

The hook is configured as `module:function`:

```bash
export WIRECLAIM_PROCESSOR="my_package.claims:process_case"
```

It receives a `wireclaim.domain.CaseReady` value containing the required file
paths, all discovered JPG/PNG images, the game start time, and the derived
one-minute deadline. The default hook in
`wireclaim.pipeline.placeholder:process_case` only logs readiness and contains
TODOs for invoice parsing, policy analysis, pricing, and eventual submission.

## Tests

```bash
pixi run test
```

Tests mock the HTTP API and 7-Zip process; they never retrieve unreleased keys or
send submissions.
