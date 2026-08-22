"""Line-item violation-checking interface."""

from pathlib import Path

from src.parse_invoice import LineItem


def check_violation(
    line_item: LineItem,
    policy_path: Path,
    description_path: Path,
) -> object:
    raise NotImplementedError
