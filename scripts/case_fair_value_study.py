from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data.case_loader import read_invoice_line_items

RAW_DIR = ROOT / "case_analysis" / "data" / "raw"
CASES_DIR = ROOT / "[PUBLIC] EHL Cases" / "cases"
PENALTY_MULTIPLIER = 1.5


def _as_float(value: object) -> float:
    return float(value)


def _raw_path(game_id: int) -> Path:
    return RAW_DIR / f"transactions_game_{game_id:03d}.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _available_games() -> list[int]:
    return sorted(int(path.stem.rsplit("_", 1)[1]) for path in RAW_DIR.glob("transactions_game_*.json"))


def _parse_games(spec: str, available: list[int]) -> list[int]:
    if spec == "all":
        return available
    requested: set[int] = set()
    for part in spec.split(","):
        start, separator, end = part.strip().partition("-")
        if not start:
            raise ValueError(f"Invalid game specification: {part!r}")
        first = int(start)
        last = int(end) if separator and end else first
        if last < first:
            raise ValueError(f"Invalid descending game range: {part!r}")
        requested.update(range(first, last + 1))
    missing = sorted(requested - set(available))
    if missing:
        raise ValueError(f"No downloaded Transactions for Games {missing}")
    return sorted(requested)


def _matrix_cells() -> dict[str, dict[int, float]]:
    path = RAW_DIR / "matrix.json"
    if not path.exists():
        return {}
    payload = _load_json(path)
    game_ids = payload.get("game_ids")
    if not isinstance(game_ids, list):
        return {}
    return {
        str(row["team_name"]): {int(game_id): _as_float(net) for game_id, net in zip(game_ids, row["cells"])}
        for row in payload.get("items", [])
    }


def _team_names() -> list[str]:
    path = RAW_DIR / "matrix.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}; run case_analysis/fetch_data.py first.")
    payload = _load_json(path)
    names = [str(row["team_name"]) for row in payload.get("items", [])]
    if not names:
        raise ValueError("matrix.json contains no team names")
    return names


def _identity_net(rows: Iterable[dict[str, object]], team: str) -> float:
    income = sum(_as_float(row["amount"]) for row in rows if row["issuer"] == team)
    costs = sum(
        _as_float(row["amount"]) if bool(row["accepted"]) else PENALTY_MULTIPLIER * _as_float(row["amount"])
        for row in rows
        if row["reviewer"] == team
    )
    return income - costs


def _verify(rows: list[dict[str, object]], team_names: list[str], cells: dict[str, dict[int, float]], game_id: int) -> dict[str, object]:
    compared = 0
    mismatches: list[dict[str, object]] = []
    for team in team_names:
        published = cells.get(team, {}).get(game_id)
        if published is None:
            continue
        compared += 1
        identity = _identity_net(rows, team)
        if abs(identity - published) > 0.01:
            mismatches.append({"team": team, "identity_net": identity, "matrix_net": published})
    return {
        "method": "transaction_identity",
        "matrix_teams_compared": compared,
        "matrix_matches": not mismatches,
        "mismatches": mismatches,
    }


def _case_dir(game_id: int) -> Path:
    return CASES_DIR / f"case_{game_id:02d}"


def _invoice_items(game_id: int) -> tuple[list[dict[str, object]], list[str]]:
    directory = _case_dir(game_id)
    errors: list[str] = []
    try:
        items = read_invoice_line_items(directory / "invoices.pdf")
    except Exception as error:
        return [], [f"invoice parse failed: {error}"]
    return [item.to_dict() for item in items], errors


def _upper(value: float | None, relation: str | None) -> dict[str, object]:
    return {"value": value, "relation": relation}


def _is_definitely_above(value: float, upper: float | None, relation: str | None) -> bool:
    if upper is None:
        return False
    return value >= upper if relation == "lt" else value > upper


def _is_definitely_below(value: float, lower: float) -> bool:
    return value < lower


def _issuer_view(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    by_issuer: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_issuer[str(row["issuer"])].append(row)
    views: dict[str, dict[str, object]] = {}
    for issuer, issuer_rows in by_issuer.items():
        wrongful = [
            _as_float(row["amount"])
            for row in issuer_rows
            if not bool(row["accepted"]) and _as_float(row["amount"]) > 0
        ]
        rightful = [
            row
            for row in issuer_rows
            if not bool(row["accepted"]) and _as_float(row["amount"]) == 0
        ]
        accepted = [_as_float(row["amount"]) for row in issuer_rows if bool(row["accepted"])]
        paid_accepted = [amount for amount in accepted if amount > 0]
        exact_charge = max(wrongful) if wrongful else None
        side = "fair_or_at" if wrongful else "overcharge" if rightful else "unobserved"
        if wrongful and rightful:
            side = "contradictory"
        cap = None
        if exact_charge is not None and paid_accepted and min(paid_accepted) < exact_charge:
            cap = min(paid_accepted)
        views[issuer] = {
            "issuer": issuer,
            "side": side,
            "charge": exact_charge,
            "payment_lower_bound": max(paid_accepted) if paid_accepted else None,
            "accepted_count": len(accepted),
            "wrongful_rejection_count": len(wrongful),
            "rightful_rejection_count": len(rightful),
            "cap": cap,
        }
    return views


def _derive_zero_charges(issuers: dict[str, dict[str, object]], fair_lower: float) -> None:
    if fair_lower <= 0:
        return
    for view in issuers.values():
        if (
            view["side"] == "unobserved"
            and _as_float(view["accepted_count"]) > 0
            and view["payment_lower_bound"] is None
        ):
            view["side"] = "fair_or_at"
            view["charge"] = 0.0


def _fair_value(rows: list[dict[str, object]], issuers: dict[str, dict[str, object]]) -> dict[str, object]:
    lower_evidence = [
        _as_float(row["amount"])
        for row in rows
        if not bool(row["accepted"]) and _as_float(row["amount"]) > 0
    ]
    upper_candidates: list[tuple[float, str, str]] = []
    for view in issuers.values():
        if view["side"] == "overcharge" and view["payment_lower_bound"] is not None:
            upper_candidates.append((_as_float(view["payment_lower_bound"]), "lt", "accepted_overcharge"))
        if view["cap"] is not None:
            upper_candidates.append((_as_float(view["cap"]) / 4.0, "le", "cap_over_four_t"))
    lower = max(lower_evidence, default=0.0)
    upper_value: float | None = None
    upper_relation: str | None = None
    upper_sources: list[str] = []
    if upper_candidates:
        upper_value = min(candidate[0] for candidate in upper_candidates)
        tied = [candidate for candidate in upper_candidates if math.isclose(candidate[0], upper_value)]
        upper_relation = "lt" if any(candidate[1] == "lt" for candidate in tied) else "le"
        upper_sources = sorted({candidate[2] for candidate in tied})
    contradiction = upper_value is not None and (
        lower >= upper_value if upper_relation == "lt" else lower > upper_value
    )
    return {
        "lower": lower,
        "upper": _upper(upper_value, upper_relation),
        "identified_set": "inconsistent" if contradiction else "bounded" if upper_value is not None else "lower_bounded",
        "evidence": {
            "wrongful_rejections": len(lower_evidence),
            "max_wrongfully_rejected_charge": lower if lower_evidence else None,
            "upper_sources": upper_sources,
            "overcharge_issuers": sum(1 for view in issuers.values() if view["side"] == "overcharge"),
            "cap_observations": sum(1 for view in issuers.values() if view["cap"] is not None),
        },
    }


def _charge_direction(view: dict[str, object], lower: float, upper: float | None, relation: str | None) -> str:
    side = view["side"]
    if side == "overcharge":
        return "overcharge"
    charge = view["charge"]
    if charge is None:
        payment = view["payment_lower_bound"]
        if payment is not None and _is_definitely_above(_as_float(payment), upper, relation):
            return "overcharge_from_payment_bound"
        return "unknown"
    value = _as_float(charge)
    if _is_definitely_below(value, lower):
        return "certainly_below_fair_value"
    if _is_definitely_above(value, upper, relation):
        return "overcharge_from_interval"
    return "fair_or_at_fair_value" if side == "fair_or_at" else "ambiguous"


def _limit_views(rows: list[dict[str, object]], issuers: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    by_reviewer: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_reviewer[str(row["reviewer"])].append(row)
    out: dict[str, dict[str, object]] = {}
    for reviewer, reviewer_rows in by_reviewer.items():
        accepted_payments = [_as_float(row["amount"]) for row in reviewer_rows if bool(row["accepted"])]
        rejected_exact_charges = [
            _as_float(issuers[str(row["issuer"])]["charge"])
            for row in reviewer_rows
            if not bool(row["accepted"]) and issuers[str(row["issuer"])]["charge"] is not None
        ]
        out[reviewer] = {
            "reviewer": reviewer,
            "lower": max(accepted_payments, default=0.0),
            "upper": min(rejected_exact_charges) if rejected_exact_charges else None,
        }
    return out


def _limit_direction(view: dict[str, object], lower: float, upper: float | None, relation: str | None) -> str:
    limit_lower = _as_float(view["lower"])
    limit_upper = view["upper"]
    if _is_definitely_above(limit_lower, upper, relation):
        return "certainly_above_fair_value"
    if limit_upper is not None and _as_float(limit_upper) <= lower:
        return "certainly_below_fair_value"
    return "ambiguous"


def _mean_relation(value: float | None, lower: float, upper: float | None, relation: str | None) -> str:
    if value is None:
        return "unavailable"
    if _is_definitely_below(value, lower):
        return "certainly_below_fair_value"
    if _is_definitely_above(value, upper, relation):
        return "certainly_above_fair_value"
    return "ambiguous"


def _field_summary(
    issuers: dict[str, dict[str, object]],
    limits: dict[str, dict[str, object]],
    fair: dict[str, object],
) -> dict[str, object]:
    lower = _as_float(fair["lower"])
    upper_data = fair["upper"]
    upper = upper_data["value"]
    relation = upper_data["relation"]
    charge_counts: dict[str, int] = defaultdict(int)
    exact_charges: list[float] = []
    payment_bounds: list[float] = []
    hidden_overcharges = 0
    for view in issuers.values():
        direction = _charge_direction(view, lower, upper, relation)
        charge_counts[direction] += 1
        if view["charge"] is not None:
            exact_charges.append(_as_float(view["charge"]))
        if view["payment_lower_bound"] is not None:
            payment_bounds.append(_as_float(view["payment_lower_bound"]))
        if view["side"] == "overcharge" and view["payment_lower_bound"] is None:
            hidden_overcharges += 1
    limit_counts: dict[str, int] = defaultdict(int)
    limit_lowers: list[float] = []
    for view in limits.values():
        limit_counts[_limit_direction(view, lower, upper, relation)] += 1
        limit_lowers.append(_as_float(view["lower"]))
    mean_charge = sum(exact_charges) / len(exact_charges) if exact_charges else None
    mean_limit_lower = sum(limit_lowers) / len(limit_lowers) if limit_lowers else None
    return {
        "issuer_count": len(issuers),
        "charge_direction_counts": dict(sorted(charge_counts.items())),
        "hidden_overcharges": hidden_overcharges,
        "exact_charge_count": len(exact_charges),
        "mean_exact_charge": mean_charge,
        "mean_exact_charge_relation": _mean_relation(mean_charge, lower, upper, relation),
        "payment_lower_bound_count": len(payment_bounds),
        "mean_payment_lower_bound": sum(payment_bounds) / len(payment_bounds) if payment_bounds else None,
        "reviewer_count": len(limits),
        "limit_direction_counts": dict(sorted(limit_counts.items())),
        "mean_limit_lower_bound": mean_limit_lower,
        "mean_limit_lower_bound_relation": _mean_relation(mean_limit_lower, lower, upper, relation),
        "caution": (
            "Charges are exact only after a wrongful rejection; accepted payments are lower "
            "bounds when the Cap might bind. Limits are intervals, so no midpoint is used."
        ),
    }


def _item_record(index: int, rows: list[dict[str, object]], invoice: dict[str, object] | None) -> dict[str, object]:
    issuers = _issuer_view(rows)
    fair = _fair_value(rows, issuers)
    _derive_zero_charges(issuers, _as_float(fair["lower"]))
    limits = _limit_views(rows, issuers)
    return {
        "index": index,
        "invoice": invoice,
        "fair_value": fair,
        "field": _field_summary(issuers, limits, fair),
        "issuers": sorted(issuers.values(), key=lambda value: str(value["issuer"])),
        "limits": sorted(limits.values(), key=lambda value: str(value["reviewer"])),
    }


def _game_record(game_id: int, team_names: list[str], cells: dict[str, dict[int, float]]) -> dict[str, object]:
    rows = _load_json(_raw_path(game_id))
    by_index: dict[int, list[dict[str, object]]] = defaultdict(list)
    for raw in rows:
        row = {
            "issuer": str(raw["issuer"]),
            "reviewer": str(raw["reviewer"]),
            "line_item_index": int(raw["line_item_index"]),
            "accepted": bool(raw["accepted"]),
            "amount": _as_float(raw["amount"]),
        }
        by_index[row["line_item_index"]].append(row)
    invoice_items, errors = _invoice_items(game_id)
    invoice_by_index = {int(item["index"]): item for item in invoice_items}
    transaction_indices = sorted(by_index)
    invoice_indices = sorted(invoice_by_index)
    if invoice_indices and transaction_indices != invoice_indices:
        errors.append(
            f"invoice indices {invoice_indices} differ from Transaction indices {transaction_indices}"
        )
    return {
        "game_id": game_id,
        "case_directory": str(_case_dir(game_id).relative_to(ROOT)),
        "transaction_rows": len(rows),
        "verification": _verify(rows, team_names, cells, game_id),
        "invoice_item_count": len(invoice_indices),
        "transaction_item_count": len(transaction_indices),
        "item_count_matches": invoice_indices == transaction_indices,
        "invoice_indices": invoice_indices,
        "transaction_indices": transaction_indices,
        "errors": errors,
        "line_items": [_item_record(index, by_index[index], invoice_by_index.get(index)) for index in transaction_indices],
    }


def build(games: list[int]) -> dict[str, object]:
    team_names = _team_names()
    cells = _matrix_cells()
    return {
        "schema": 1,
        "source": {
            "transactions": "case_analysis/data/raw/transactions_game_XXX.json",
            "cases": "[PUBLIC] EHL Cases/cases/case_XX",
            "fair_value_bounds": "settled Transaction payoff inversion",
            "confidence_note": (
                "fair_value is an identified set from deterministic payoff constraints, not a "
                "statistical confidence interval or an LLM-estimated point value"
            ),
        },
        "team_names": team_names,
        "games": [_game_record(game_id, team_names, cells) for game_id in games],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="all", help="e.g. 1-31, 7, or all downloaded Games")
    parser.add_argument(
        "--output",
        default="case_analysis/data/fair_value_study.json",
        help="JSON destination relative to the repository root",
    )
    args = parser.parse_args()
    available = _available_games()
    if not available:
        raise SystemExit("No downloaded Transaction data; run case_analysis/fetch_data.py first.")
    games = _parse_games(args.games, available)
    payload = build(games)
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    bounded = sum(
        item["fair_value"]["identified_set"] == "bounded"
        for game in payload["games"]
        for item in game["line_items"]
    )
    items = sum(len(game["line_items"]) for game in payload["games"])
    failures = [game["game_id"] for game in payload["games"] if game["errors"]]
    print(
        f"wrote {output.relative_to(ROOT)}: {len(games)} Games, {items} Line Items, "
        f"{bounded} bounded Fair Value sets, invoice/index failures={failures or 'none'}"
    )


if __name__ == "__main__":
    main()
