"""Parallel orchestration for checks performed on invoice line items."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TypedDict

from src.parse_invoice import LineItem
from src.policy_digest import digest_policy
from src.t_estimation import encode_case_images, estimate_t_safe
from src.violation_check import check_violation


class CheckedLineItem(TypedDict):
    line_item: LineItem
    violation: object
    t_estimation: object


def _case_images(case_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in case_dir.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )


def check_line_items(
    line_items: list[LineItem],
    policy_path: Path,
    description_path: Path,
) -> list[CheckedLineItem]:
    """Run violation checking and T-estimation in parallel for each line item."""
    with ThreadPoolExecutor() as executor:
        images_future = executor.submit(_case_images, policy_path.parent)
        digest_future = executor.submit(digest_policy, policy_path)
        encoded_images = encode_case_images(images_future.result())
        try:
            policy_summary = digest_future.result()
        except Exception:  # noqa: BLE001 - fall back, never block the round
            policy_summary = None
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
                    estimate_t_safe,
                    line_item,
                    policy_path,
                    description_path,
                    all_line_items=line_items,
                    encoded_images=encoded_images,
                    policy_summary=policy_summary,
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
