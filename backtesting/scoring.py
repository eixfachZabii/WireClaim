"""Cap-aware counterfactual scoring with identified lower/midpoint/upper outcomes."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from backtesting.models import (
    Ambiguity,
    ChargeEstimate,
    GameScore,
    HistoricalGame,
    HistoricalItem,
    Interval,
    ItemScore,
    Submission,
    ValueTriple,
)


def issuer_payoff(charge: float, limit: float, fair_value: float, cap: float) -> float:
    if charge <= limit:
        return min(charge, cap)
    if charge <= fair_value:
        return charge
    return 0.0


def reviewer_cost(charge: float, limit: float, fair_value: float, cap: float) -> float:
    if charge <= limit:
        return min(charge, cap)
    if charge <= fair_value:
        return 1.5 * charge
    return 0.0


def reconstructed_submission(
    game: HistoricalGame, seat: str = "Bin busy"
) -> dict[int, Submission]:
    result = {}
    for index, item in game.items.items():
        fair_value = _representative(item.fair_value.interval)
        decision = item.decisions[seat]
        result[index] = Submission(
            _representative_charge(decision.charge, fair_value),
            _representative(decision.limit.interval),
        )
    return result


def score_game(
    game: HistoricalGame,
    submissions: Mapping[int, Submission | tuple[float, float]],
    *,
    seat: str = "Bin busy",
    cap_mode: str = "fitted",
) -> GameScore:
    if cap_mode not in {"fitted", "rules_only"}:
        raise ValueError(f"unsupported Cap mode {cap_mode!r}")
    per_item: dict[int, ItemScore] = {}
    missing = 0
    for index, item in game.items.items():
        raw = submissions.get(index)
        if raw is None:
            submission = Submission(0.0, 0.0)
            missing += 1
        elif isinstance(raw, Submission):
            submission = raw
        else:
            submission = Submission(float(raw[0]), float(raw[1]))
        per_item[index] = score_item(item, game.teams, submission, seat=seat, cap_mode=cap_mode)
    if missing:
        per_item = {
            index: ItemScore(
                index=value.index,
                income=value.income,
                cost=value.cost,
                net=value.net,
                ambiguity=value.ambiguity + Ambiguity(missing_outputs=int(index not in submissions)),
            )
            for index, value in per_item.items()
        }
    income = _sum_triples([value.income for value in per_item.values()])
    cost = _sum_triples([value.cost for value in per_item.values()])
    net = _sum_triples([value.net for value in per_item.values()])
    ambiguity = Ambiguity()
    for value in per_item.values():
        ambiguity += value.ambiguity
    return GameScore(game.game_id, income, cost, net, per_item, ambiguity)


def score_item(
    item: HistoricalItem,
    teams: Sequence[str],
    submission: Submission,
    *,
    seat: str,
    cap_mode: str,
) -> ItemScore:
    opponents = [team for team in teams if team != seat]
    t_values = _critical_t_values(item, submission, opponents)
    scenario_rows: list[tuple[float, float, float, float]] = []
    limit_ambiguity = sum(
        len(_acceptance_options(item.decisions[team].limit.interval, submission.charge)) > 1
        for team in opponents
    )
    charge_ambiguity = sum(
        not item.decisions[team].charge.interval.exact for team in opponents
    )
    fair_ambiguity = int(len(t_values) > 1)
    cap_ambiguity = 0

    for t in t_values:
        caps = _cap_values(item, t, submission, opponents, cap_mode)
        cap_ambiguity = max(cap_ambiguity, int(len(caps) > 1))
        for cap in caps:
            income_ranges = [
                _issuer_income_range(submission.charge, item.decisions[team].limit.interval, t, cap)
                for team in opponents
            ]
            cost_ranges = [
                _reviewer_cost_range(
                    item.decisions[team].charge, submission.limit, t, cap
                )
                for team in opponents
            ]
            scenario_rows.append(
                (
                    sum(value[0] for value in income_ranges),
                    sum(value[1] for value in income_ranges),
                    sum(value[0] for value in cost_ranges),
                    sum(value[1] for value in cost_ranges),
                )
            )

    t_mid = _representative(item.fair_value.interval)
    cap_mid = _cap_values(item, t_mid, submission, opponents, cap_mode)[0]
    income_mid = sum(
        issuer_payoff(
            submission.charge,
            _representative(item.decisions[team].limit.interval),
            t_mid,
            cap_mid,
        )
        for team in opponents
    )
    cost_mid = sum(
        reviewer_cost(
            _representative_charge(item.decisions[team].charge, t_mid),
            submission.limit,
            t_mid,
            cap_mid,
        )
        for team in opponents
    )
    income_low = min(row[0] for row in scenario_rows)
    income_high = max(row[1] for row in scenario_rows)
    cost_low = min(row[2] for row in scenario_rows)
    cost_high = max(row[3] for row in scenario_rows)
    income_mid = min(max(income_mid, income_low), income_high)
    cost_mid = min(max(cost_mid, cost_low), cost_high)
    income = ValueTriple(income_low, income_mid, income_high)
    cost = ValueTriple(cost_low, cost_mid, cost_high)
    net_low = min(row[0] - row[3] for row in scenario_rows)
    net_high = max(row[1] - row[2] for row in scenario_rows)
    net_mid = min(max(income_mid - cost_mid, net_low), net_high)
    return ItemScore(
        index=item.index,
        income=income,
        cost=cost,
        net=ValueTriple(net_low, net_mid, net_high),
        ambiguity=Ambiguity(
            opponent_limits=limit_ambiguity,
            opponent_charges=charge_ambiguity,
            fair_values=fair_ambiguity,
            caps=cap_ambiguity,
        ),
    )


def _issuer_income_range(
    charge: float, limit: Interval, fair_value: float, cap: float
) -> tuple[float, float]:
    values = [
        min(charge, cap) if accepted else (charge if charge <= fair_value else 0.0)
        for accepted in _acceptance_options(limit, charge)
    ]
    return min(values), max(values)


def _reviewer_cost_range(
    charge: ChargeEstimate, limit: float, fair_value: float, cap: float
) -> tuple[float, float]:
    candidates = _critical_interval_values(charge.interval, limit, fair_value, cap)
    if charge.status == "right_censored":
        candidates = tuple(value for value in candidates if value > fair_value)
        if not candidates:
            lower = max(charge.interval.low, fair_value)
            candidates = (math.nextafter(lower, math.inf),)
    values = [reviewer_cost(value, limit, fair_value, cap) for value in candidates]
    return min(values), max(values)


def _acceptance_options(limit: Interval, charge: float) -> tuple[bool, ...]:
    if limit.low >= charge:
        return (True,)
    if limit.high is not None and charge >= limit.high:
        return (False,)
    return (False, True)


def _critical_interval_values(interval: Interval, *thresholds: float) -> tuple[float, ...]:
    low = math.nextafter(interval.low, math.inf) if interval.low_strict else interval.low
    candidates = {low}
    if interval.high is not None:
        high = interval.high if interval.high_inclusive else math.nextafter(interval.high, interval.low)
        candidates.add(max(high, low))
    else:
        candidates.add(max((low, *thresholds), default=low) + 1.0)
    for threshold in thresholds:
        for value in (math.nextafter(threshold, 0.0), threshold, math.nextafter(threshold, math.inf)):
            if _contains(interval, value):
                candidates.add(value)
    return tuple(sorted(value for value in candidates if value >= 0 and math.isfinite(value)))


def _contains(interval: Interval, value: float) -> bool:
    if value < interval.low or (interval.low_strict and value <= interval.low):
        return False
    if interval.high is None:
        return True
    return value <= interval.high if interval.high_inclusive else value < interval.high


def _critical_t_values(
    item: HistoricalItem, submission: Submission, opponents: Sequence[str]
) -> tuple[float, ...]:
    interval = item.fair_value.interval
    thresholds = [submission.charge, submission.limit]
    for team in opponents:
        charge = item.decisions[team].charge.interval
        thresholds.append(charge.low)
        if charge.high is not None:
            thresholds.append(charge.high)
    return _critical_interval_values(interval, *thresholds)


def _cap_values(
    item: HistoricalItem,
    fair_value: float,
    submission: Submission,
    opponents: Sequence[str],
    mode: str,
) -> tuple[float, ...]:
    lower = max(4.0 * fair_value, item.cap.empirical_floor, item.cap.observed_paid_floor)
    if mode == "fitted":
        return (lower,)
    highest = max(
        [submission.charge, submission.limit, lower]
        + [item.decisions[team].charge.interval.low for team in opponents]
    )
    return (lower,) if highest <= lower else (lower, highest)


def _representative(interval: Interval) -> float:
    value = interval.representative()
    if interval.low_strict and value <= interval.low:
        return math.nextafter(interval.low, math.inf)
    return value


def _representative_charge(charge: ChargeEstimate, fair_value: float) -> float:
    value = _representative(charge.interval)
    if charge.status == "right_censored" and value <= fair_value:
        return math.nextafter(fair_value, math.inf)
    return value


def _sum_triples(values: Sequence[ValueTriple]) -> ValueTriple:
    return ValueTriple(
        sum(value.lower for value in values),
        sum(value.midpoint for value in values),
        sum(value.upper for value in values),
    )
