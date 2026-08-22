"""Reconstruct hidden historical decisions while retaining every identified interval."""

from __future__ import annotations

import collections
from typing import Mapping, Sequence

from backtesting.legacy import rivals
from backtesting.models import (
    CapEstimate,
    ChargeEstimate,
    FairValueEstimate,
    HistoricalGame,
    HistoricalItem,
    Interval,
    LimitEstimate,
    TeamDecision,
    Transaction,
)

CAP_FLOOR = float(rivals.CAP_FLOOR)


def reconstruct_game(
    game_id: int,
    teams: Sequence[str],
    transactions: Sequence[Transaction],
    fair_brackets: Mapping[int, tuple[float, float]],
    authoritative_nets: Mapping[str, float],
    leaderboard_nets: Mapping[str, float] | None = None,
    item_metadata: Mapping[int, Mapping[str, object]] | None = None,
) -> HistoricalGame:
    team_names = tuple(sorted(teams))
    indices = tuple(sorted({row.line_item_index for row in transactions}))
    by_issuer: dict[tuple[int, str], list[Transaction]] = collections.defaultdict(list)
    by_reviewer: dict[tuple[int, str], list[Transaction]] = collections.defaultdict(list)
    for row in transactions:
        by_issuer[(row.line_item_index, row.issuer)].append(row)
        by_reviewer[(row.line_item_index, row.reviewer)].append(row)

    fair = {
        index: FairValueEstimate(
            interval=_fair_interval(fair_brackets.get(index, (0.0, float("inf")))),
            lower_witnesses=tuple(
                sorted(
                    f"{row.issuer}:{row.amount:.2f}"
                    for row in transactions
                    if row.line_item_index == index and not row.accepted and row.amount > 0
                )
            ),
            upper_witnesses=(),
        )
        for index in indices
    }
    charges = _reconstruct_charges(indices, team_names, by_issuer, fair)
    limits = _reconstruct_limits(indices, team_names, by_reviewer, charges)
    charges = _tighten_right_censored(indices, team_names, by_issuer, charges, limits, fair)

    metadata = item_metadata or {}
    items: dict[int, HistoricalItem] = {}
    for index in indices:
        accepted_amounts = [
            row.amount
            for row in transactions
            if row.line_item_index == index and row.accepted and row.amount > 0
        ]
        capped_teams = [
            team for team in team_names if charges[index][team].status == "cap_censored"
        ]
        observed = max(accepted_amounts, default=0.0)
        cap = CapEstimate(
            observed_paid_floor=observed,
            status="inferred" if capped_teams else "fitted",
            evidence=tuple(f"cap-censored:{team}" for team in capped_teams),
        )
        decisions = {
            team: TeamDecision(team, charges[index][team], limits[index][team])
            for team in team_names
        }
        meta = metadata.get(index, {})
        items[index] = HistoricalItem(
            index=index,
            fair_value=fair[index],
            cap=cap,
            decisions=decisions,
            name=str(meta.get("name", "")),
            quantity=float(meta.get("quantity", 1.0)),
            quantity_missing=bool(meta.get("quantity_missing", False)),
        )

    return HistoricalGame(
        game_id=game_id,
        teams=team_names,
        items=items,
        transactions=tuple(sorted(transactions, key=lambda row: row.key)),
        authoritative_nets=dict(authoritative_nets),
        leaderboard_nets=dict(leaderboard_nets or {}),
    )


def _fair_interval(bracket: tuple[float, float]) -> Interval:
    low, high = bracket
    return Interval(float(low), None if high == float("inf") else float(high))


def _reconstruct_charges(
    indices: Sequence[int],
    teams: Sequence[str],
    by_issuer: Mapping[tuple[int, str], Sequence[Transaction]],
    fair: Mapping[int, FairValueEstimate],
) -> dict[int, dict[str, ChargeEstimate]]:
    ties: dict[tuple[int, float], set[str]] = collections.defaultdict(set)
    for index in indices:
        bracket = fair[index].interval
        raw_bracket = (bracket.low, float("inf") if bracket.high is None else bracket.high)
        for team in teams:
            for row in by_issuer.get((index, team), ()):
                amount = round(row.amount, 2)
                if row.accepted and amount >= CAP_FLOOR - 0.005 and rivals.plausible_cap(amount, raw_bracket):
                    ties[(index, amount)].add(team)

    result: dict[int, dict[str, ChargeEstimate]] = {index: {} for index in indices}
    for index in indices:
        for team in teams:
            rows = tuple(by_issuer.get((index, team), ()))
            positive = sorted({row.amount for row in rows if row.amount > 0})
            rejected_positive = [row for row in rows if not row.accepted and row.amount > 0]
            accepted_zero = any(row.accepted and row.amount == 0 for row in rows)
            accepted = sum(row.accepted for row in rows)
            rejected_zero = sum(not row.accepted and row.amount == 0 for row in rows)
            if rejected_positive:
                value = max(row.amount for row in rejected_positive)
                interval, status = Interval.point(value), "exact"
            elif positive:
                value = max(positive)
                if value < CAP_FLOOR - 0.005:
                    interval, status = Interval.point(value), "exact_accepted"
                elif len(ties[(index, round(value, 2))]) >= 2:
                    interval, status = Interval(value, None), "cap_censored"
                else:
                    interval, status = Interval(value, None), "possibly_capped"
            elif accepted_zero:
                interval, status = Interval.point(0.0), "zero"
            else:
                interval, status = Interval(fair[index].interval.low, None, low_strict=True), "right_censored"
            result[index][team] = ChargeEstimate(
                interval=interval,
                status=status,
                accepted=accepted,
                rejected_positive=len(rejected_positive),
                rejected_zero=rejected_zero,
                observed_amounts=tuple(positive),
            )
    return result


def _reconstruct_limits(
    indices: Sequence[int],
    teams: Sequence[str],
    by_reviewer: Mapping[tuple[int, str], Sequence[Transaction]],
    charges: Mapping[int, Mapping[str, ChargeEstimate]],
) -> dict[int, dict[str, LimitEstimate]]:
    result: dict[int, dict[str, LimitEstimate]] = {index: {} for index in indices}
    for index in indices:
        for team in teams:
            low = 0.0
            high: float | None = None
            low_witness = None
            high_witness = None
            accepted_count = rejected_count = 0
            for row in by_reviewer.get((index, team), ()):
                charge = charges[index][row.issuer]
                if row.accepted:
                    accepted_count += 1
                    lower = charge.interval.low
                    if lower >= low:
                        low = lower
                        low_witness = row.issuer
                else:
                    rejected_count += 1
                    if not charge.exact:
                        continue
                    exact = charge.interval.low
                    if high is None or exact < high:
                        high = exact
                        high_witness = row.issuer
            if high is not None and high < low:
                raise ValueError(
                    f"Game Limit bracket contradiction item {index} team {team}: [{low}, {high})"
                )
            interval = Interval.point(low) if high == low else Interval(low, high)
            result[index][team] = LimitEstimate(
                interval=interval,
                lower_witness=low_witness,
                upper_witness=high_witness,
                accepted_witnesses=accepted_count,
                rejected_witnesses=rejected_count,
            )
    return result


def _tighten_right_censored(
    indices: Sequence[int],
    teams: Sequence[str],
    by_issuer: Mapping[tuple[int, str], Sequence[Transaction]],
    charges: Mapping[int, Mapping[str, ChargeEstimate]],
    limits: Mapping[int, Mapping[str, LimitEstimate]],
    fair: Mapping[int, FairValueEstimate],
) -> dict[int, dict[str, ChargeEstimate]]:
    result = {index: dict(per_team) for index, per_team in charges.items()}
    for index in indices:
        for team in teams:
            current = result[index][team]
            if current.status != "right_censored":
                continue
            lower = fair[index].interval.low
            for row in by_issuer.get((index, team), ()):
                if not row.accepted:
                    lower = max(lower, limits[index][row.reviewer].interval.low)
            result[index][team] = ChargeEstimate(
                interval=Interval(lower, None, low_strict=True),
                status=current.status,
                accepted=current.accepted,
                rejected_positive=current.rejected_positive,
                rejected_zero=current.rejected_zero,
                observed_amounts=current.observed_amounts,
            )
    return result
