"""AB-calculation interface."""

from src.lineitem_checks import CheckedLineItem


def calculate_ab(checked_line_items: list[CheckedLineItem]) -> object:
    raise NotImplementedError
