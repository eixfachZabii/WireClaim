"""Parallel orchestration for checks performed on invoice line items."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TypedDict

from src.parse_invoice import LineItem
from src.t_estimation import estimate_t
from src.violation_check import check_violation


class CheckedLineItem(TypedDict):
    line_item: LineItem
    violation: object
    t_estimation: object


def check_line_items(
    line_items: list[LineItem],
    policy_path: Path,
    description_path: Path,
) -> list[CheckedLineItem]:
    """Run violation checking and T-estimation in parallel for each line item."""
    with ThreadPoolExecutor() as executor:
        pending = [
            (
                line_item,
                executor.submit(
                    check_violation,
                    line_item,
                    policy_path,
                    description_path,
                ),
                executor.submit(
                    estimate_t,
                    line_item,
                    policy_path,
                    description_path,
                ),
            )
            for line_item in line_items
        ]

        return [
            {
                "line_item": line_item,
                "violation": violation.result(),
                "t_estimation": estimation.result(),
            }
            for line_item, violation, estimation in pending
        ]
