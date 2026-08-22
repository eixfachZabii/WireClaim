"""Command-line interface for historical Field data and strategy experiments."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from backtesting.data import load_dataset, sync_dataset
from backtesting.diagnostics import dataset_diagnostics
from backtesting.experiments import rerender, run_experiment
from backtesting.paths import CURRENT_DATASET, RUNS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    sync = commands.add_parser("sync", help="incrementally fetch and reconstruct settled Games")
    sync.add_argument("--games", default="all")
    sync.add_argument("--include-game-0", action="store_true")
    sync.add_argument("--refresh-transactions", action="store_true")
    sync.add_argument("--request-delay", type=float, default=0.25)

    validate = commands.add_parser("validate", help="validate and summarize a reconstructed dataset")
    validate.add_argument("--dataset", help="dataset ID prefix (default: current dataset)")

    diagnose = commands.add_parser("diagnose", help="print dataset identifiability diagnostics")
    diagnose.add_argument("--dataset", help="dataset ID prefix (default: current dataset)")
    diagnose.add_argument("--json", action="store_true")

    run = commands.add_parser("run", help="freshly run strategies and write an experiment report")
    run.add_argument("--spec", default="backtesting/specs/default.json")
    run.add_argument("--dataset", help="dataset ID prefix (default: current dataset)")
    run.add_argument("--games", help="Games to score while retaining the dataset's earlier history")

    report = commands.add_parser("report", help="rerender an existing run without API/model calls")
    report.add_argument("run_id")

    args = parser.parse_args()
    if args.command == "sync":
        dataset = sync_dataset(
            args.games,
            include_game_0=args.include_game_0,
            refresh_transactions=args.refresh_transactions,
            request_delay=args.request_delay,
        )
        print(
            f"Dataset {dataset.dataset_id[:16]}: {len(dataset.games)} Games, "
            f"{sum(len(game.transactions) for game in dataset.games.values())} unique Transactions"
        )
        print(f"Current pointer: {CURRENT_DATASET}")
    elif args.command == "validate":
        dataset = load_dataset(args.dataset)
        bad = [game_id for game_id, game in dataset.games.items() if game.validation_status != "ok"]
        if bad:
            raise SystemExit(f"Unusable Games: {bad}")
        print(json.dumps(dataset_diagnostics(dataset), indent=2))
    elif args.command == "diagnose":
        diagnostics = dataset_diagnostics(load_dataset(args.dataset))
        if args.json:
            print(json.dumps(diagnostics, indent=2))
        else:
            for key, value in diagnostics.items():
                print(f"{key:28s} {value}")
    elif args.command == "run":
        run_dir, _ = asyncio.run(
            run_experiment(args.spec, dataset_id=args.dataset, games_override=args.games)
        )
        print(f"Wrote {run_dir}")
    else:
        path = Path(args.run_id)
        run_dir = path if path.is_dir() else RUNS / args.run_id
        rerender(run_dir)


if __name__ == "__main__":
    main()
