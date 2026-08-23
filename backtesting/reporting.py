"""Deterministic JSON, CSV, terminal, and Markdown experiment reporting."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def write_report(run_dir: Path, result: Mapping[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "scores.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    score_rows = _score_rows(result)
    _csv(run_dir / "scores.csv", score_rows)
    _csv(run_dir / "per_item.csv", list(result.get("per_item", ())))
    sweep_rows = []
    for candidate, sweep in result.get("sweeps", {}).items():
        for key, values in sweep.get("cells", {}).items():
            sweep_rows.append({"candidate": candidate, "parameters": key, **values})
    _csv(run_dir / "sweeps.csv", sweep_rows)
    (run_dir / "sweeps.json").write_text(json.dumps(result.get("sweeps", {}), indent=2))
    (run_dir / "diagnostics.json").write_text(json.dumps(result.get("diagnostics", {}), indent=2))
    (run_dir / "report.md").write_text(render_markdown(result))


def render_markdown(result: Mapping[str, Any]) -> str:
    manifest = result["manifest"]
    lines = [
        f"# Backtest: {manifest['name']}",
        "",
        "## Provenance",
        "",
        f"- Run: `{manifest['run_id']}`",
        f"- Dataset: `{manifest['dataset_id']}`",
        f"- Dataset schema: `{manifest['dataset_schema']}`",
        f"- Code revision: `{manifest.get('git_revision') or 'unavailable'}`",
        f"- Cap mode: `{manifest['cap_mode']}`",
        f"- Games: {manifest['games']}",
        f"- Draws per existing track: {manifest['draws']}",
        f"- Measured noise floor over this window: {manifest.get('noise_floor', 0):,.0f} EUR",
        "",
        "Bounds are identified-set envelopes conditional on the selected Cap mode; they are not confidence intervals.",
        "`actual` is the authoritative Transaction identity; `actual_reconstructed` replays interval representatives as an identifiability diagnostic.",
        "Current model prompts/constants are evaluated retrospectively, while dynamic history and Price Memory are restricted to earlier Games.",
        "",
        "## Strategy comparison",
        "",
        "| Strategy | Games | Income lower | Income midpoint | Income upper | Cost lower | Cost midpoint | Cost upper | Net lower | Net midpoint | Net upper |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in _score_rows(result):
        lines.append(
            "| {strategy} | {games} | {income_lower:,.0f} | {income_midpoint:,.0f} | "
            "{income_upper:,.0f} | {cost_lower:,.0f} | {cost_midpoint:,.0f} | "
            "{cost_upper:,.0f} | {net_lower:,.0f} | **{net_midpoint:,.0f}** | {net_upper:,.0f} |".format(**row)
        )
    lines += ["", "## Per-Game midpoint net", ""]
    labels = sorted(result["scores"])
    lines.append("| Game | " + " | ".join(labels) + " |")
    lines.append("|---:" + "|---:" * len(labels) + "|")
    games = sorted({int(game) for scores in result["scores"].values() for game in scores})
    for game in games:
        cells = []
        for label in labels:
            score = result["scores"].get(label, {}).get(str(game))
            cells.append("n/a" if score is None else f"{score['net']['midpoint']:,.0f}")
        lines.append(f"| {game} | " + " | ".join(cells) + " |")

    lines += ["", "## Regime breakdown", ""]
    for regime, strategies in result.get("regimes", {}).items():
        lines += [
            f"### {regime}",
            "",
            "| Strategy | Games | Net lower | Net midpoint | Net upper |",
            "|---|---:|---:|---:|---:|",
        ]
        for strategy, score in sorted(strategies.items()):
            lines.append(
                f"| {strategy} | {len(score['games'])} | {score['lower']:,.0f} | "
                f"**{score['midpoint']:,.0f}** | {score['upper']:,.0f} |"
            )
        lines.append("")

    lines += ["", "## Draw variance and runtime", ""]
    track_rows = result.get("tracks", {})
    if track_rows:
        lines += [
            "| Track | Calls | Failures | Runtime mean s | Runtime max s | Pooled midpoint spread |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for track, row in sorted(track_rows.items()):
            lines.append(
                f"| {track} | {row['calls']} | {row['failures']} | {row['runtime_mean']:.1f} | "
                f"{row['runtime_max']:.1f} | {row['pooled_midpoint_spread']:,.0f} |"
            )
    else:
        lines.append("No model-backed tracks were executed.")

    lines += ["", "## Chronological and walk-forward validation", ""]
    for candidate, sweep in result.get("sweeps", {}).items():
        validation = sweep["validation"]
        held = validation["holdout_score"]
        walk = validation["walk_forward_score"]
        lines += [
            f"### {candidate}",
            "",
            f"- Selected parameters: `{validation['selected']}`",
            f"- Train Games: {validation['train_games']}",
            f"- Holdout Games: {validation['test_games']}",
            f"- Holdout net: [{held['lower']:,.0f}, **{held['midpoint']:,.0f}**, {held['upper']:,.0f}]",
            f"- Walk-forward net: [{walk['lower']:,.0f}, **{walk['midpoint']:,.0f}**, {walk['upper']:,.0f}]",
            "",
        ]

    data = result.get("diagnostics", {}).get("dataset", {})
    lines += [
        "## Identifiability and data quality",
        "",
        f"- Unique Transactions: {data.get('transactions', 0):,}",
        f"- Reconstructed team decisions: {data.get('team_decisions', 0):,}",
        f"- Exact Charge share: {data.get('exact_charge_share', 0):.1%}",
        f"- Bounded Limit share: {data.get('bounded_limit_share', 0):.1%}",
        f"- Bounded Fair Value share: {data.get('bounded_fair_value_share', 0):.1%}",
        f"- Charge statuses: `{data.get('charge_statuses', {})}`",
        f"- Cap statuses: `{data.get('cap_statuses', {})}`",
        "",
        "## Caveats",
        "",
        "- Exact hidden Charges and Limits are not assumed where the public record only identifies an interval.",
        "- Wide score envelopes mean the historical record cannot rank those strategies conclusively.",
        "- Full-sample sweep cells are descriptive; only chronological holdout and walk-forward rows are out-of-sample.",
        "- Game-to-Game Field behavior changes across awake, dark, and recalibrated regimes.",
    ]
    return "\n".join(lines) + "\n"


def print_summary(result: Mapping[str, Any]) -> None:
    print(f"Backtest {result['manifest']['run_id']} on dataset {result['manifest']['dataset_id'][:16]}")
    print(f"{'strategy':24s} {'lower':>14s} {'midpoint':>14s} {'upper':>14s}")
    for row in _score_rows(result):
        print(
            f"{row['strategy'][:24]:24s} {row['net_lower']:14,.0f} "
            f"{row['net_midpoint']:14,.0f} {row['net_upper']:14,.0f}"
        )


def _score_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for strategy, games in result["scores"].items():
        values = list(games.values())
        rows.append(
            {
                "strategy": strategy,
                "games": len(values),
                **{
                    f"{side}_{point}": sum(value[side][point] for value in values)
                    for side in ("income", "cost", "net")
                    for point in ("lower", "midpoint", "upper")
                },
            }
        )
    return sorted(rows, key=lambda row: -row["net_midpoint"])


def _csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
