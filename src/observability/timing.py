from __future__ import annotations

import logging
from collections.abc import Sequence
from time import perf_counter
from typing import Any

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
YELLOW = "\033[93m"
GRAY = "\033[90m"


def _paint(value: object, *styles: str) -> str:
    return f"{''.join(styles)}{value}{RESET}"


def format_error_card(
    event: str,
    error: BaseException,
    game: int,
    action: str,
    elapsed_s: float | None = None,
) -> str:
    title = f"{'!' * 24} {event.replace('_', ' ').upper()} FAILED {'!' * 24}"
    detail = " ".join(str(error).split()) or "No error detail returned."
    lines = [
        f"\n\n\n{_paint(title, BOLD, RED)}",
        "",
        _paint("RUN ERROR", BOLD, RED),
        "",
        f"{_paint('game:', DIM)} {_paint(game, BOLD)}",
    ]
    if elapsed_s is not None:
        lines.append(f"{_paint('elapsed:', DIM)} {_paint(f'{elapsed_s:.2f}s', BOLD, RED)}")
    lines.extend(
        (
            f"{_paint('error:', DIM)} {_paint(type(error).__name__, BOLD, RED)}",
            f"{_paint('detail:', DIM)} {_paint(detail, RED)}",
            f"{_paint('action:', DIM)} {_paint(action, BOLD, YELLOW)}",
            "",
            _paint("!" * len(title), RED),
        )
    )
    return "\n".join(lines)


def format_fraud_lock_card(game: int, items: Sequence[tuple[int, str]]) -> str:
    title = f"{'#' * 20} FRAUD LIMIT LOCKS CONFIRMED {'#' * 20}"
    lines = [
        f"\n\n{_paint(title, BOLD, RED)}",
        "",
        _paint(f"game: {game}", BOLD, RED),
        _paint("The following Line Items are locked at Limit=0.00:", BOLD, RED),
    ]
    lines.extend(_paint(f"  [{index}] {name} -> Limit=0.00", RED) for index, name in items)
    lines.extend(
        (
            "",
            _paint("Later Fast Path and Strategy snapshots retain these locks.", BOLD, YELLOW),
            _paint("#" * len(title), RED),
        )
    )
    return "\n".join(lines)


def format_skipped_strategy_card(
    game: int,
    candidate_source: str,
    candidate_priority: int,
    active_source: str,
    active_priority: int,
    elapsed_s: float,
    prices: Sequence[tuple[int, float, float]],
) -> str:
    title = f"{'#' * 16} {candidate_source.upper()} COMPARISON ONLY {'#' * 16}"
    style = (DIM, GRAY)
    lines = [
        f"\n\n{_paint(title, *style)}",
        "",
        _paint("NOT POSTED — lower-priority Strategy result", *style),
        "",
        _paint(f"game: {game}", *style),
        _paint(f"elapsed: {elapsed_s:.2f}s", *style),
        _paint(f"candidate: {candidate_source} (priority {candidate_priority})", *style),
        _paint(f"active: {active_source} (priority {active_priority})", *style),
        "",
        _paint("line |       charge |        limit", *style),
        _paint("-----+--------------+--------------", *style),
    ]
    lines.extend(
        _paint(f"{index:>4} | {charge:>12.2f} | {limit_:>12.2f}", *style)
        for index, charge, limit_ in sorted(prices)
    )
    lines.extend(("", _paint("#" * len(title), *style)))
    return "\n".join(lines)


def start_timer() -> float:
    return perf_counter()


def log_timing(
    logger: logging.Logger,
    event: str,
    started_at: float,
    status: str = "completed",
    **fields: Any,
) -> None:
    metadata = " ".join(f"{name}={value}" for name, value in fields.items())
    logger.info(
        "timing event=%s status=%s elapsed_s=%.3f%s",
        event,
        status,
        perf_counter() - started_at,
        f" {metadata}" if metadata else "",
    )
