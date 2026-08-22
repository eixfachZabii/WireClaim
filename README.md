# WireClaim

Minimal Python setup for the QuantCo Claim to Fame challenge.

`main.py` contains the complete flow:

1. Read the game schedule.
2. Notice when a game's UTC start time arrives.
3. Fetch its decryption key.
4. Extract the matching ZIP to `var/cases/case_XX`.
5. Call `process_case()`, where the analysis code will be added.

Submission is intentionally not implemented yet.

## Setup

```bash
pixi install
cp .env.example .env
# Add TEAM_API_KEY to .env
pixi run start
```

Process the permanent test game directly:

```bash
pixi run case-0
```

The watcher polls every two seconds. A short retry handles a key endpoint that is
a fraction late. Keys are never printed or stored.
