"""Invoice parsing interface."""

from pathlib import Path
from typing import Any

LineItem = dict[str, Any]


def parse_invoice(invoice_path: Path) -> list[LineItem]:
    """Return the invoice line items in a structured format."""
    raise NotImplementedError
