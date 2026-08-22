# Runner Workflow

This document describes the event-driven Game runner implemented in `main.py`.
It is the technical execution model; tournament mechanics and pricing rules remain in
[`README.md`](../README.md).

## Architecture

```text
Published Game schedule
          │
          ▼
┌──────────────────────────────────────────────────────┐
│ main.py                                                │
│ Run Manager: deadline, state, event handling          │
└──────────────────────────────────────────────────────┘
          │
          │ get released key → extract archive → read files
          ▼
┌──────────────────────────────────────────────────────┐
│ src/data/case_loader.py                               │
│ CaseData: Policy, Damage Description, Line Items,     │
│           Images                                      │
└──────────────────────────────────────────────────────┘
     │                         │
     │ standard_values          │ parallel work
     ▼                         ▼
┌───────────────────┐   ┌─────────────────────────────────────────┐
│ Base Proposal     │   │ fast_path.llm_values                     │
│ every Line Item   │   │ fraud_detection.detect_fraud             │
└─────────┬─────────┘   │ StrategyRouter                           │
          │             │  ├─ strategy1/strategy.py              │
          │             │  │   evidence + local estimator         │
          │             │  └─ strategy2/strategy.py              │
          │             └──────────────────┬──────────────────────┘
          │                                │ completed results
          │                                ▼
          │                     ┌──────────────────────────┐
          └────────────────────►│ asyncio event queue      │
                                └────────────┬─────────────┘
                                             ▼
                                ┌──────────────────────────┐
                                │ RunManager snapshot      │
                                │ Standard → Fast Path →   │
                                │ active Strategy →        │
                                │ Fraud Limit lock b = 0   │
                                └────────────┬─────────────┘
                                             ▼
                                ┌──────────────────────────┐
                                │ SubmissionCoordinator    │
                                │ one serial POST worker   │
                                └────────────┬─────────────┘
                                             ▼
                                  src/api.submit_prices()
                                             ▼
                                  Tournament API
```

## Responsibilities

| Component | Responsibility | Does not do |
| --- | --- | --- |
| `main.py` / `RunManager` | Owns one Game deadline, merges all results, enforces the final Limit lock, and publishes snapshots. | Does not estimate Fair Value or call strategy internals. |
| `case_loader.py` | Retrieves a released decryption key, extracts the archive with 7-Zip, reads policy/description/images, and reads numbered Line Items from the invoice PDF. | Does not price Line Items. |
| `fast_path.py` | Produces complete Standard values immediately after `CaseData` is available. | Does not post directly. |
| `StrategyRouter` | Runs Strategy Tracks in parallel and exposes the latest valid Strategy Proposal. | Does not know Fraud Decisions, deadlines, or the API. |
| `strategy1/strategy.py`, `strategy2/strategy.py` | Each owns its local Fair Value estimation path. Strategy 1 reads all Case documents, invoice PDF, and images before deterministically producing a Proposal. | Does not post directly. |
| `fraud_detection.py` | Emits a `FraudDecision` containing affected Line Item indices. | Does not set Charges or post directly. |
| `SubmissionCoordinator` | Serializes `submit_prices` calls and only sends changed complete snapshots. | Does not decide which values are correct. |

## One Game

1. `watch_games()` waits for a scheduled Game start and calls `run_game(game_id)`.
2. `run_game()` sets one absolute 60-second deadline.
3. `load_case()` waits for the released key, extracts the matching archive, then reads the Case files and Line Items.
4. `standard_values(case)` creates one base `(Charge, Limit)` pair for every detected Line Item. `main.py` immediately gives this complete snapshot to the `SubmissionCoordinator`.
5. The following work starts in parallel:
   - `fast_path.llm_values(case)`
   - `fraud_detection.detect_fraud(case)`
   - `StrategyRouter.start_strategies(case)`, which starts both Strategy Track packages; each owns its local estimation path.
6. Every completed result is sent to the `asyncio` event queue. `main.py` consumes one event at a time, rebuilds the complete snapshot, and tells the coordinator to post it if it changed.
7. At T+60, unfinished work is cancelled and the coordinator is closed. A failed or late API request is logged and does not block the next scheduled Game.

## Selection Rules

The manager resolves values independently for every Line Item:

```text
base Standard values
  <- Fast-Path proposal, if it contains this Line Item
    <- active Strategy Proposal, if it contains this Line Item
      <- FraudDecision Limit lock: Limit = 0
```

The active Strategy Proposal is the latest valid Strategy Track result received by the `StrategyRouter`. This makes later completed Strategies replace earlier completed Strategies without allowing any Strategy to post on its own.

A `FraudDecision` is an irreversible per-Game Limit lock. If a Strategy already supplied `Charge=250, Limit=190` and the Line Item is subsequently identified by `FraudDecision`, the next complete Submission contains `Charge=250, Limit=0`. A later Strategy may change the Charge, but cannot lift the Limit lock.

## Submission Ordering

All sources only produce data. `SubmissionCoordinator` is the single writer to the tournament API:

1. It keeps the newest requested complete snapshot.
2. It sends at most one `submit_prices` request at a time.
3. If a new result arrives while a request is active, it posts the newer snapshot immediately after the active request completes.
4. It does not repost an unchanged snapshot.

This prevents a delayed Strategy request from arriving after and overwriting a newer Limit lock.

## Current Skeleton Status

The workflow and arbitration are active. `strategy1/strategy.py` reads every text document, the invoice PDF, and every supported image from `CaseData`; it requests structured evidence and deterministically turns that evidence into a Proposal. It is the only strategy that currently produces values after a successful model call.

The following paths remain intentional skeletons:

- `fast_path.llm_values()` returns no Proposal.
- `strategy2/strategy.py` returns no Proposal after its local estimator call.
- `fraud_detection.detect_fraud()` returns an empty decision.

The runner always posts complete Standard values after Case loading. A successful Strategy 1 Proposal overwrites its covered Line Items, while all other Line Items retain their current valid values. No strategy may add direct API calls outside `SubmissionCoordinator`.
