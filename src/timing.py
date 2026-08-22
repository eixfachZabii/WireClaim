from __future__ import annotations

import logging
from time import perf_counter
from typing import Any


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
