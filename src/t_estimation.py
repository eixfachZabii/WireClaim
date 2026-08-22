"""Line-item T-estimation interface."""

from src.parse_invoice import LineItem


def estimate_t(line_item: LineItem) -> object:
    raise NotImplementedError
