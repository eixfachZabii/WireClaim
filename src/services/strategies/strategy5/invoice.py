from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from src.data.case_loader import read_invoice_line_items
from src.data.models import CaseData, LineItem

_NUMBERED_ITEM = re.compile(
    r"^\s*(?P<index>[1-9]\d{0,2})\s*(?:\.(?!\d)|\)|[-–])\s*(?P<name>\S.*)$"
)
_SPACED_ITEM = re.compile(r"^\s*(?P<index>[1-9]\d{0,2})\s+(?P<name>\S.*)$")
_UNIT_PATTERN = r"flat\s+rate|linear\s+m|pcs|hrs?|h|m2|m²|m�|m|kg|days?|units?|kwh|lines|�"
_TRAILING_AMOUNT = re.compile(
    rf"(?P<amount>\d[\d.,]*)\s*(?P<unit>{_UNIT_PATTERN})\s*$",
    re.IGNORECASE,
)
_PARENTHESIZED_AMOUNT = re.compile(
    rf"\s*\((?P<amount>\d[\d.,]*)\s*(?P<unit>{_UNIT_PATTERN})\)\s*$",
    re.IGNORECASE,
)
_TRAILING_DASHES = re.compile(r"\s+[-–—]\s+[-–—]\s*$")
_DASH_ONLY_ROW = re.compile(r"^[-–—]\s+[-–—]$")


@dataclass(frozen=True)
class InvoiceItem:
    index: int
    description: str
    amount: float | None
    unit: str | None
    quantity_missing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "description": self.description,
            "amount": self.amount,
            "unit": self.unit,
            "quantity_missing": self.quantity_missing,
        }


@dataclass(frozen=True)
class InvoiceDocument:
    items: tuple[InvoiceItem, ...]
    line_items: tuple[LineItem, ...]
    text: str


def read_invoice_text(invoice_path: Path) -> str:
    from pypdf import PdfReader

    return "\n".join(page.extract_text() or "" for page in PdfReader(invoice_path).pages)


def _amount(value: str) -> float:
    if "," in value and "." in value:
        value = value.replace(",", "")
    elif value.count(",") == 1:
        value = value.replace(",", ".")
    else:
        value = value.replace(",", "")
    return float(value)


def _unit(value: str) -> str:
    normalized = " ".join(value.split())
    folded = normalized.casefold()
    if folded in {"m2", "m²", "m�"}:
        return "m²"
    if folded == "kwh":
        return "kWh"
    if folded == "�":
        return "unknown"
    return normalized


def _split_amount(value: str) -> tuple[str, float, str] | None:
    match = _TRAILING_AMOUNT.search(value)
    if match is None:
        return None
    return value[: match.start()].strip(), _amount(match.group("amount")), _unit(match.group("unit"))


def parse_invoice_items(text: str) -> tuple[InvoiceItem, ...]:
    found: dict[int, InvoiceItem] = {}
    last_index: int | None = None
    lines = text.splitlines()
    in_items_section = not any("DESCRIPTION" in line.upper() for line in lines)
    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if "POS." in upper and "DESCRIPTION" in upper:
            in_items_section = True
            last_index = None
            continue
        if upper.startswith(("INVOICE", "CREATED ON", "PAGE ", "SUBTOTAL", "TOTAL")):
            in_items_section = False
            last_index = None
            continue
        if not in_items_section or not stripped:
            continue
        if _DASH_ONLY_ROW.fullmatch(stripped):
            if last_index is not None and last_index in found:
                found[last_index] = replace(
                    found[last_index], amount=None, unit=None, quantity_missing=True
                )
            continue
        amount_row = _TRAILING_AMOUNT.fullmatch(stripped)
        if amount_row is not None and last_index is not None and last_index in found:
            found[last_index] = replace(
                found[last_index],
                amount=_amount(amount_row.group("amount")),
                unit=_unit(amount_row.group("unit")),
                quantity_missing=False,
            )
            continue
        match = _NUMBERED_ITEM.match(line) or _SPACED_ITEM.match(line)
        if match is None:
            if last_index is not None and last_index in found and any(character.isalpha() for character in stripped):
                previous = found[last_index]
                found[last_index] = replace(
                    previous,
                    description=f"{previous.description} {stripped}".strip(),
                )
            continue
        index = int(match.group("index"))
        value = match.group("name").strip()
        without_dashes = _TRAILING_DASHES.sub("", value).strip()
        if without_dashes != value:
            item = InvoiceItem(index, without_dashes, None, None, True)
        else:
            split = _split_amount(value)
            item = (
                InvoiceItem(index, value, None, None)
                if split is None
                else InvoiceItem(index, split[0], split[1], split[2])
            )
        if not item.description or not any(character.isalpha() for character in item.description):
            continue
        found.setdefault(index, item)
        last_index = index
    return tuple(found[index] for index in sorted(found))


def _normalise_line_items(items: Iterable[LineItem]) -> tuple[LineItem, ...]:
    indexed: dict[int, LineItem] = {}
    for item in items:
        if item.index > 0:
            indexed.setdefault(item.index, item)
    return tuple(indexed[index] for index in sorted(indexed))


def _fallback_item(item: LineItem) -> InvoiceItem:
    if item.quantity_missing:
        return InvoiceItem(item.index, item.name.strip(), None, None, True)
    parenthesized = _PARENTHESIZED_AMOUNT.search(item.name)
    if parenthesized is not None:
        return InvoiceItem(
            item.index,
            item.name[: parenthesized.start()].strip(),
            _amount(parenthesized.group("amount")),
            _unit(parenthesized.group("unit")),
        )
    split = _split_amount(item.name)
    if split is not None:
        return InvoiceItem(item.index, split[0], split[1], split[2])
    return InvoiceItem(item.index, item.name.strip(), float(item.quantity), "unknown")


def _complete_item(parsed: InvoiceItem | None, fallback: InvoiceItem) -> InvoiceItem:
    if parsed is None:
        return fallback
    if parsed.quantity_missing or parsed.amount is not None:
        return parsed
    return replace(
        parsed,
        amount=fallback.amount if fallback.amount is not None else 1.0,
        unit=fallback.unit or "unknown",
    )


def extract_invoice_document(case: CaseData) -> InvoiceDocument:
    invoice_path = case.case_dir / "invoices.pdf"
    try:
        text = read_invoice_text(invoice_path)
    except Exception:
        text = ""
    try:
        line_items = _normalise_line_items(read_invoice_line_items(invoice_path))
    except Exception:
        line_items = _normalise_line_items(case.line_items)
    parsed = {item.index: item for item in parse_invoice_items(text)}
    if line_items:
        items = tuple(
            _complete_item(parsed.get(line_item.index), _fallback_item(line_item))
            for line_item in line_items
        )
    else:
        items = tuple(parsed.values())
        line_items = tuple(
            LineItem(
                index=item.index,
                name=item.description,
                quantity=1.0 if item.amount is None else item.amount,
                quantity_missing=item.quantity_missing,
            )
            for item in items
        )
    return InvoiceDocument(items=items, line_items=line_items, text=text)


def extract_invoice_items(case: CaseData) -> tuple[InvoiceItem, ...]:
    return extract_invoice_document(case).items


__all__ = [
    "InvoiceDocument",
    "InvoiceItem",
    "extract_invoice_document",
    "extract_invoice_items",
    "parse_invoice_items",
    "read_invoice_text",
]
