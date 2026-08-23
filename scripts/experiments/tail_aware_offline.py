"""Deterministic ceiling test for the tail-aware Price Memory conflict strategy.

This is the safe local counterpart to ``backtesting.candidates.tail_aware``.  It never
calls a model and never reads a future Game through Price Memory.  Instead it:

1. takes the combined evidence recorded in each live Strategy 2 decision log;
2. rebuilds Price Memory from strictly earlier reconstructed Games;
3. algebraically recovers the model median that preceded Strategy 2's log-space memory
   blend;
4. applies the candidate's generic-wording and price-ratio conflict gate; and
5. lets the settled Fair Value act as a deliberately unshippable confirmation oracle.

The oracle answers a narrower question than a fresh model backtest: if confirmation were
perfect, is there enough payoff behind this gate to justify the extra call?  A negative or
noise-sized ceiling falsifies the idea without sending historical Case contents externally.
A positive ceiling only earns the right to test the real adjudication; it is not evidence
that the adjudicator can achieve it.

Run from the repository root:

    PYTHONPATH=. .venv/bin/python scripts/experiments/tail_aware_offline.py
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from backtesting.candidates.tail_aware import _contextually_weak, _mixture_submission
from backtesting.data import load_dataset, parse_games
from backtesting.history import HistoryStore
from backtesting.models import GameScore, Submission
from backtesting.scoring import score_game
from backtesting.sweeps import chronological_evaluation, parameter_key
from src.evidence.memory import PriceMemoryHit
from src.pricing.engine import Evidence, price_item
from src.strategies.fast_path import STANDARD_CHARGE, STANDARD_LIMIT
from src.strategies.strategy2.channels import unit_of
from src.strategies.strategy2.constants import BAND_Z, MEMORY_SIGMA, MODEL_SIGMA_PRIOR

DECISIONS = Path("var/decisions")
OUTPUT_ROOT = Path("var/backtesting/analyses")
SEAT = "Bin busy"
# Game 42's decision log explicitly records that a historical test fixture overwrote 15 of
# its 17 evidence rows.  The reconstructed Game is valid, but the decision-time evidence
# needed by this analysis is not, so only this Game is excluded.
GAME_SELECTOR = "26-41,43-55"
CONFLICT_RATIO = 3.0
TAIL_THRESHOLD = 1_000.0
CONFIRMATION_RATIO = 2.0
DEFAULT_PARAMS = {"tail_probability": 0.70, "trusted_tail_limit_ceiling": 0.75}
PARAMETERS = tuple(
    {"tail_probability": probability, "trusted_tail_limit_ceiling": ceiling}
    for probability in (0.55, 0.70, 0.85)
    for ceiling in (0.45, 0.75, 1.00)
)
NOISE_FLOOR_18 = 26_622.0


def main() -> None:
    dataset = load_dataset()
    game_ids = parse_games(GAME_SELECTOR, sorted(dataset.games))
    history = HistoryStore(dataset)
    output_dir = OUTPUT_ROOT / f"tail-aware-{dataset.dataset_id[:12]}"
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_submissions: dict[int, dict[int, Submission]] = {}
    cell_submissions: dict[str, dict[int, dict[int, Submission]]] = {
        parameter_key(params): {} for params in PARAMETERS
    }
    oracle_submissions: dict[int, dict[int, Submission]] = {}
    trigger_rows: list[dict[str, Any]] = []

    for game_id in game_ids:
        game = dataset.games[game_id]
        logged = _decision_items(game_id)
        memory = history.memory_before(game_id)
        baseline: dict[int, Submission] = {}
        cells = {parameter_key(params): {} for params in PARAMETERS}
        oracle: dict[int, Submission] = {}

        for index, historical_item in game.items.items():
            if index not in logged:
                raise ValueError(
                    f"Game {game_id} decision log is missing historical Line Item {index}"
                )
            raw = logged[index]
            evidence = _logged_evidence(index, raw)
            memory_backed = "B:memory" in (raw.get("channels") or ())
            uncovered = bool(raw.get("quantity_missing"))
            base = _baseline(evidence, uncovered, memory_backed)
            baseline[index] = base
            oracle[index] = base
            for key in cells:
                cells[key][index] = base

            hit = None
            if memory_backed and not uncovered:
                hit = memory.lookup(
                    str(raw.get("name") or historical_item.name),
                    unit=unit_of(str(raw.get("name") or historical_item.name)),
                    quantity=max(float(raw.get("quantity") or historical_item.quantity), 1.0),
                )
            recovered_model = _recover_model_median(evidence, hit)
            triggered = bool(
                hit is not None
                and recovered_model is not None
                and recovered_model
                >= max(TAIL_THRESHOLD, hit.median * CONFLICT_RATIO)
                and _contextually_weak(str(raw.get("name") or historical_item.name), hit)
            )
            if not triggered:
                continue

            interval = historical_item.fair_value.interval
            confirmation_floor = hit.median * CONFIRMATION_RATIO
            if interval.low >= confirmation_floor:
                truth_class = "proven_tail"
            elif interval.high is not None and interval.high < confirmation_floor:
                truth_class = "proven_ordinary"
            else:
                truth_class = "ambiguous"

            tail = _model_component(index, evidence, recovered_model)
            per_param: dict[str, dict[str, float]] = {}
            if truth_class == "proven_tail":
                representative = interval.representative()
                oracle[index] = Submission(representative, representative)
                for params in PARAMETERS:
                    key = parameter_key(params)
                    candidate = _mixture_submission(
                        _memory_evidence(index, evidence, hit),
                        tail,
                        covered=evidence.coverage_probability,
                        tail_probability=float(params["tail_probability"]),
                        limit_ceiling=float(params["trusted_tail_limit_ceiling"]),
                    )
                    cells[key][index] = candidate
                    per_param[key] = _submission_dict(candidate)

            trigger_rows.append(
                {
                    "game_id": game_id,
                    "line_item_index": index,
                    "name": str(raw.get("name") or historical_item.name),
                    "memory_match": hit.match,
                    "memory_name": hit.name,
                    "memory_low": hit.low,
                    "memory_median": hit.median,
                    "memory_high": hit.high,
                    "combined_low": evidence.price_low,
                    "combined_median": evidence.price_median,
                    "combined_high": evidence.price_high,
                    "recovered_model_median": recovered_model,
                    "coverage_probability": evidence.coverage_probability,
                    "fair_value_low": interval.low,
                    "fair_value_high": interval.high,
                    "truth_class": truth_class,
                    "baseline_charge": base.charge,
                    "baseline_limit": base.limit,
                    "oracle_charge": oracle[index].charge,
                    "oracle_limit": oracle[index].limit,
                    "parameter_submissions": per_param,
                }
            )

        baseline_submissions[game_id] = baseline
        oracle_submissions[game_id] = oracle
        for key, submission in cells.items():
            cell_submissions[key][game_id] = submission

    baseline_scores = _score(dataset.games, baseline_submissions)
    cell_scores = {
        key: _score(dataset.games, submissions)
        for key, submissions in cell_submissions.items()
    }
    oracle_scores = _score(dataset.games, oracle_submissions)
    validation = chronological_evaluation(
        cell_scores,
        game_ids,
        holdout_fraction=0.30,
        min_train=8,
        step=1,
        objective="lower_net",
    )
    summary = _summary(
        dataset.dataset_id,
        game_ids,
        trigger_rows,
        baseline_scores,
        cell_scores,
        oracle_scores,
        validation,
    )
    _attach_item_deltas(
        trigger_rows,
        dataset.games,
        baseline_submissions,
        cell_submissions,
        oracle_submissions,
    )
    _write_outputs(
        output_dir,
        summary,
        trigger_rows,
        baseline_scores,
        cell_scores,
        oracle_scores,
        baseline_submissions,
        cell_submissions,
        oracle_submissions,
    )
    print(json.dumps(summary["decision"], indent=2))
    print(f"Wrote {output_dir}")


def _decision_items(game_id: int) -> dict[int, Mapping[str, Any]]:
    path = DECISIONS / f"game_{game_id:03d}.json"
    payload = json.loads(path.read_text())
    items = {int(item["index"]): item for item in payload.get("items") or ()}
    if not items:
        raise ValueError(f"Game {game_id} decision log has no Strategy 2 items")
    return items


def _logged_evidence(index: int, raw: Mapping[str, Any]) -> Evidence | None:
    values = (
        raw.get("coverage_probability"),
        raw.get("price_low"),
        raw.get("price_median"),
        raw.get("price_high"),
    )
    if all(value is None for value in values):
        return None
    return Evidence(
        index=index,
        coverage_probability=float(raw.get("coverage_probability") or 0.0),
        price_low=float(raw.get("price_low") or 0.0),
        price_median=float(raw.get("price_median") or 0.0),
        price_high=float(raw.get("price_high") or 0.0),
    )


def _baseline(
    evidence: Evidence | None, uncovered: bool, memory_backed: bool
) -> Submission:
    if evidence is None:
        return Submission(STANDARD_CHARGE, STANDARD_LIMIT)
    priced = price_item(
        evidence,
        confirmed_uncovered=uncovered,
        memory_backed=memory_backed and not uncovered,
    )
    return Submission(priced.charge, priced.limit)


def _recover_model_median(
    combined: Evidence | None, hit: PriceMemoryHit | None
) -> float | None:
    if combined is None or hit is None or combined.price_median <= 0 or hit.median <= 0:
        return None
    model_weight = 1.0 / MODEL_SIGMA_PRIOR**2
    memory_weight = 1.0 / MEMORY_SIGMA**2
    recovered_log = (
        (model_weight + memory_weight) * math.log(combined.price_median)
        - memory_weight * math.log(hit.median)
    ) / model_weight
    if recovered_log >= math.log(float.fromhex("0x1.fffffffffffffp+1023")):
        return None
    recovered = math.exp(recovered_log)
    return recovered if math.isfinite(recovered) and recovered > 0 else None


def _model_component(index: int, combined: Evidence, median: float) -> Evidence:
    return Evidence(
        index=index,
        coverage_probability=combined.coverage_probability,
        price_low=median * math.exp(-BAND_Z * MODEL_SIGMA_PRIOR),
        price_median=median,
        price_high=median * math.exp(BAND_Z * MODEL_SIGMA_PRIOR),
    )


def _memory_evidence(index: int, combined: Evidence, hit: PriceMemoryHit) -> Evidence:
    return Evidence(
        index=index,
        coverage_probability=combined.coverage_probability,
        price_low=hit.low,
        price_median=hit.median,
        price_high=hit.high,
    )


def _score(games, submissions) -> dict[int, GameScore]:
    return {
        game_id: score_game(games[game_id], submission, seat=SEAT, cap_mode="fitted")
        for game_id, submission in submissions.items()
    }


def _totals(scores: Mapping[int, GameScore], games) -> dict[str, float]:
    selected = [scores[game_id].net for game_id in games]
    return {
        "lower": sum(value.lower for value in selected),
        "midpoint": sum(value.midpoint for value in selected),
        "upper": sum(value.upper for value in selected),
    }


def _delta(
    candidate: Mapping[int, GameScore], baseline: Mapping[int, GameScore], games
) -> dict[str, float]:
    candidate_total = _totals(candidate, games)
    baseline_total = _totals(baseline, games)
    return {key: candidate_total[key] - baseline_total[key] for key in candidate_total}


def _summary(
    dataset_id: str,
    game_ids: list[int],
    triggers: list[dict[str, Any]],
    baseline: Mapping[int, GameScore],
    cells: Mapping[str, Mapping[int, GameScore]],
    oracle: Mapping[int, GameScore],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    default_key = parameter_key(DEFAULT_PARAMS)
    full_best = max(cells, key=lambda key: _totals(cells[key], game_ids)["lower"])
    selected = str(validation["selected"])
    train_games = list(validation["train_games"])
    test_games = list(validation["test_games"])
    holdout_delta = _delta(cells[selected], baseline, test_games)
    walk_delta = {"lower": 0.0, "midpoint": 0.0, "upper": 0.0}
    for row in validation["walk_forward"]:
        upcoming = row["test_games"]
        chosen = row["selected"]
        current = _delta(cells[chosen], baseline, upcoming)
        for key in walk_delta:
            walk_delta[key] += current[key]

    folds = {
        "odd": [game for game in game_ids if game % 2],
        "even": [game for game in game_ids if not game % 2],
        "early": [game for game in game_ids if game <= 40],
        "late": [game for game in game_ids if game > 40],
    }
    default_folds = {
        name: _delta(cells[default_key], baseline, games) for name, games in folds.items()
    }
    per_game_midpoint = {
        game_id: cells[default_key][game_id].net.midpoint - baseline[game_id].net.midpoint
        for game_id in game_ids
    }
    ordered = sorted(per_game_midpoint.items(), key=lambda pair: abs(pair[1]), reverse=True)
    pooled_default = _delta(cells[default_key], baseline, game_ids)
    top_game_share = (
        abs(ordered[0][1]) / abs(pooled_default["midpoint"])
        if ordered and pooled_default["midpoint"]
        else 0.0
    )
    classes = {
        name: sum(row["truth_class"] == name for row in triggers)
        for name in ("proven_tail", "proven_ordinary", "ambiguous")
    }
    noise_floor = NOISE_FLOOR_18 * math.sqrt(len(game_ids) / 18.0)
    success = bool(
        holdout_delta["lower"] > 0
        and walk_delta["lower"] > 0
        and pooled_default["midpoint"] > noise_floor
        and all(value["midpoint"] > 0 for value in default_folds.values())
        and top_game_share < 0.50
    )
    return {
        "provenance": {
            "dataset_id": dataset_id,
            "git_revision": _git_revision(),
            "games": game_ids,
            "seat": SEAT,
            "cap_mode": "fitted",
            "evidence": "logged Strategy 2 combined evidence plus past-only Price Memory",
            "confirmation": "settled-Fair-Value oracle; not shippable",
            "exclusions": {
                "42": "decision log contains only 2 of 17 evidence rows after historical fixture overwrite"
            },
        },
        "definitions": {
            "trigger": (
                "memory-backed, generic/context-weak wording, recovered model median at "
                f"least {CONFLICT_RATIO:.1f}x memory and at least EUR {TAIL_THRESHOLD:,.0f}"
            ),
            "proven_tail": (
                "reconstructed Fair Value lower bound is at least "
                f"{CONFIRMATION_RATIO:.1f}x the past-only memory median"
            ),
            "success": (
                "positive lower-bound delta on chronological holdout and walk-forward; "
                "default pooled midpoint above noise floor; all four folds positive; "
                "largest Game below 50% of pooled midpoint gain"
            ),
        },
        "trigger_counts": {"total": len(triggers), **classes},
        "baseline": _totals(baseline, game_ids),
        "default_parameters": DEFAULT_PARAMS,
        "default_delta": pooled_default,
        "full_sample_best": {"key": full_best, "delta": _delta(cells[full_best], baseline, game_ids)},
        "chronological_validation": {
            "selected": selected,
            "train_games": train_games,
            "test_games": test_games,
            "holdout_delta": holdout_delta,
            "walk_forward_delta": walk_delta,
        },
        "fold_deltas": default_folds,
        "concentration": {
            "per_game_midpoint_delta": per_game_midpoint,
            "largest_absolute_game": ordered[0] if ordered else None,
            "largest_game_share_of_pooled_midpoint": top_game_share,
        },
        "oracle_on_proven_triggers_delta": _delta(oracle, baseline, game_ids),
        "noise_floor": noise_floor,
        "decision": {
            "passes_success_bar": success,
            "interpretation": (
                "Passes the deterministic promotion bar."
                if success
                else (
                    "Not promotable: the deterministic proxy has no holdout breadth and "
                    "its payoff is unidentified, although the positive oracle ceiling "
                    "shows material value behind the one proven trigger."
                )
            ),
            "external_model_tested": False,
            "external_model_requires_explicit_approval": True,
        },
    }


def _attach_item_deltas(
    triggers: list[dict[str, Any]],
    games,
    baseline_submissions,
    cell_submissions,
    oracle_submissions,
) -> None:
    default_key = parameter_key(DEFAULT_PARAMS)
    for row in triggers:
        game_id, index = int(row["game_id"]), int(row["line_item_index"])
        game = games[game_id]
        baseline = score_game(
            game, {index: baseline_submissions[game_id][index]}, seat=SEAT, cap_mode="fitted"
        ).per_item[index]
        candidate = score_game(
            game,
            {index: cell_submissions[default_key][game_id][index]},
            seat=SEAT,
            cap_mode="fitted",
        ).per_item[index]
        oracle = score_game(
            game, {index: oracle_submissions[game_id][index]}, seat=SEAT, cap_mode="fitted"
        ).per_item[index]
        row["default_candidate_charge"] = cell_submissions[default_key][game_id][index].charge
        row["default_candidate_limit"] = cell_submissions[default_key][game_id][index].limit
        row["default_item_delta_lower"] = candidate.net.lower - baseline.net.lower
        row["default_item_delta_midpoint"] = candidate.net.midpoint - baseline.net.midpoint
        row["default_item_delta_upper"] = candidate.net.upper - baseline.net.upper
        row["oracle_item_delta_midpoint"] = oracle.net.midpoint - baseline.net.midpoint


def _write_outputs(
    output_dir: Path,
    summary,
    triggers,
    baseline_scores,
    cell_scores,
    oracle_scores,
    baseline_submissions,
    cell_submissions,
    oracle_submissions,
) -> None:
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    _csv(output_dir / "triggers.csv", triggers, exclude={"parameter_submissions"})
    parameter_rows = []
    games = summary["provenance"]["games"]
    for key, scores in cell_scores.items():
        params = json.loads(key)
        totals = _totals(scores, games)
        delta = _delta(scores, baseline_scores, games)
        parameter_rows.append({"parameter_key": key, **params, **totals, **{f"delta_{k}": v for k, v in delta.items()}})
    _csv(output_dir / "parameters.csv", parameter_rows)
    per_game_rows = []
    for game_id in games:
        base = baseline_scores[game_id].net
        default = cell_scores[parameter_key(DEFAULT_PARAMS)][game_id].net
        oracle = oracle_scores[game_id].net
        per_game_rows.append(
            {
                "game_id": game_id,
                "baseline_lower": base.lower,
                "baseline_midpoint": base.midpoint,
                "baseline_upper": base.upper,
                "candidate_lower": default.lower,
                "candidate_midpoint": default.midpoint,
                "candidate_upper": default.upper,
                "delta_lower": default.lower - base.lower,
                "delta_midpoint": default.midpoint - base.midpoint,
                "delta_upper": default.upper - base.upper,
                "oracle_delta_midpoint": oracle.midpoint - base.midpoint,
            }
        )
    _csv(output_dir / "per_game.csv", per_game_rows)
    submissions = {
        "version": 1,
        "strategies": {
            "baseline": _serialise_submissions(baseline_submissions),
            "tail_aware_default_oracle_confirmed": _serialise_submissions(
                cell_submissions[parameter_key(DEFAULT_PARAMS)]
            ),
            "oracle_price_on_proven_triggers": _serialise_submissions(oracle_submissions),
        },
    }
    (output_dir / "submissions.json").write_text(json.dumps(submissions, indent=2))
    experiment_spec = {
        "version": 1,
        "name": "tail-aware-deterministic-import",
        "games": GAME_SELECTOR,
        "seat": SEAT,
        "draws": 1,
        "timeout_seconds": 60,
        "cap_mode": "fitted",
        "include_game_0": False,
        "seed": 20260823,
        "tracks": [],
        "candidates": [
            {"name": name, "submissions": str(output_dir / "submissions.json")}
            for name in submissions["strategies"]
        ],
        "sweeps": [],
        "validation": {
            "holdout_fraction": 0.30,
            "walk_forward_min_train": 8,
            "walk_forward_step": 1,
        },
        "regimes": [
            {"name": "pre-tail", "start": 26, "end": 40},
            {"name": "known-tail", "start": 41, "end": 45},
            {"name": "post-tail", "start": 46, "end": 55},
        ],
    }
    (output_dir / "experiment_spec.json").write_text(
        json.dumps(experiment_spec, indent=2)
    )
    (output_dir / "report.md").write_text(_markdown(summary, triggers, parameter_rows))


def _markdown(summary, triggers, parameter_rows) -> str:
    decision = summary["decision"]
    validation = summary["chronological_validation"]
    default = summary["default_delta"]
    counts = summary["trigger_counts"]
    verdict = "PASS" if decision["passes_success_bar"] else "FAIL"
    lines = [
        "# Tail-aware strategy: deterministic ceiling test",
        "",
        "## Technical summary",
        "",
        f"**Promotion verdict: {verdict}.** {decision['interpretation']}",
        "",
        f"The gate triggered on {counts['total']} items: {counts['proven_tail']} proven tail, "
        f"{counts['proven_ordinary']} proven ordinary and {counts['ambiguous']} ambiguous. "
        f"At the default mixture, the payoff delta spans {default['lower']:+,.0f} to "
        f"{default['upper']:+,.0f} EUR. The representative midpoint is "
        f"{default['midpoint']:+,.0f} EUR against a {summary['noise_floor']:,.0f} EUR "
        "noise floor, but it equals the lower bound here because the trigger's Fair Value "
        "has no identified upper bound.",
        "",
        f"Chronological holdout lower-bound delta: {validation['holdout_delta']['lower']:+,.0f} EUR. "
        f"Walk-forward lower-bound delta: {validation['walk_forward_delta']['lower']:+,.0f} EUR.",
        "",
        "## What this test establishes",
        "",
        "This run used recorded Strategy 2 evidence and strictly past-only Price Memory. "
        "The settled Fair Value was used only as an explicit confirmation oracle. It tests "
        "whether the conflict gate contains enough reachable value; it does not test whether "
        "a real model reread can identify those items.",
        "",
        f"The oracle delta is {summary['oracle_on_proven_triggers_delta']['midpoint']:+,.0f} "
        "EUR. That is material headroom, but it comes entirely from one Game and uses the "
        "settled value at test time. It is therefore a reason to preserve the hypothesis, "
        "not evidence that the candidate is safe to deploy.",
        "",
        "## Fold and robustness results",
        "",
        "| fold | lower delta | midpoint delta | upper delta |",
        "|---|---:|---:|---:|",
    ]
    for name, values in summary["fold_deltas"].items():
        lines.append(
            f"| {name} | {values['lower']:+,.0f} | {values['midpoint']:+,.0f} | {values['upper']:+,.0f} |"
        )
    lines += [
        "",
        "## Trigger audit",
        "",
        "| Game | Item | truth class | memory median | recovered model median | default midpoint delta | name |",
        "|---:|---:|---|---:|---:|---:|---|",
    ]
    for row in triggers:
        lines.append(
            f"| {row['game_id']} | {row['line_item_index']} | {row['truth_class']} | "
            f"{row['memory_median']:,.0f} | {row['recovered_model_median']:,.0f} | "
            f"{row.get('default_item_delta_midpoint', 0):+,.0f} | {row['name']} |"
        )
    lines += [
        "",
        "## Parameter surface",
        "",
        "| tail probability | Limit ceiling | lower delta | midpoint delta | upper delta |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(parameter_rows, key=lambda value: (value["tail_probability"], value["trusted_tail_limit_ceiling"])):
        lines.append(
            f"| {row['tail_probability']:.2f} | {row['trusted_tail_limit_ceiling']:.2f} | "
            f"{row['delta_lower']:+,.0f} | {row['delta_midpoint']:+,.0f} | {row['delta_upper']:+,.0f} |"
        )
    lines += [
        "",
        "## Limitations",
        "",
        "- The initial model median is algebraically recovered from the logged combined median and past-only memory median; the original model band is unavailable before Game 48, so the model prior supplies its width.",
        "- Confirmation uses settled Fair Value and is intentionally impossible at execution time. The result is a ceiling, not a deployable estimate.",
        "- Current pricing constants are replayed retrospectively against a fixed historical Field; opponents do not adapt.",
        "- Lower and upper results are identified-set envelopes, not confidence intervals.",
        "",
        "## Recommended next step",
        "",
        "Do not promote this strategy. The remaining informative experiment is one bounded "
        "historical adjudication run on the audited trigger set, comparing its confirmations "
        "with the oracle labels. That run sends historical Case content to the configured "
        "remote model and therefore requires explicit user approval.",
    ]
    return "\n".join(lines) + "\n"


def _csv(path: Path, rows: list[dict[str, Any]], exclude: set[str] | None = None) -> None:
    exclude = exclude or set()
    fields = [key for key in rows[0] if key not in exclude] if rows else []
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fields} for row in rows)


def _serialise_submissions(submissions) -> dict[str, dict[str, dict[str, float]]]:
    return {
        str(game_id): {
            str(index): _submission_dict(value) for index, value in per_item.items()
        }
        for game_id, per_item in submissions.items()
    }


def _submission_dict(value: Submission) -> dict[str, float]:
    return {"charge": value.charge, "limit": value.limit}


def _git_revision() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return None


if __name__ == "__main__":
    main()
