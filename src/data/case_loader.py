from __future__ import annotations

import asyncio
import re
from pathlib import Path

from src.api import APIError, get_decryption_key
from src.data.models import CaseData, LineItem

ARCHIVE_DIR = Path("[PUBLIC] EHL Cases/cases")
OUTPUT_DIR = Path("var/cases")
_NUMBERED_LINE_ITEM = re.compile(r"^\s*(?P<index>[1-9]\d{0,2})\s*(?:[.)]|[-–])\s*(?P<name>\S.*)$")
_SPACED_LINE_ITEM = re.compile(r"^\s*(?P<index>[1-9]\d{0,2})\s+(?P<name>\S.*)$")
_TRAILING_QUANTITY = re.compile(
    r"\s+(?P<quantity>\d+(?:[.,]\d+)?)\s+(?P<unit>pcs|hrs?|m2|m\u00b2|m|days?|units?|flat rate)\s*$",
    re.IGNORECASE,
)
_TRAILING_DASHES = re.compile(r"\s+[-\u2013]\s+[-\u2013]\s*$")
_UNIT_ONLY = re.compile(r"^(?:pcs|hrs?|m2|m\u00b2|m|days?|units?|flat rate)$", re.IGNORECASE)


async def load_case(game_id: int, deadline: float) -> CaseData:
    key = await get_released_key(game_id, deadline)
    case_dir = await extract_case(game_id, key, deadline)
    return await read_case(game_id, case_dir)


async def get_released_key(game_id: int, deadline: float) -> str:
    loop = asyncio.get_running_loop()
    while loop.time() < deadline:
        try:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            return await asyncio.to_thread(
                get_decryption_key,
                game_id,
                timeout=remaining,
            )
        except APIError as error:
            if error.status_code != 403:
                raise
            await asyncio.sleep(min(0.5, max(deadline - loop.time(), 0.0)))
    raise TimeoutError(f"Game {game_id} did not release its decryption key in time.")


async def extract_case(game_id: int, key: str, deadline: float) -> Path:
    archive = find_archive(game_id)
    case_dir = OUTPUT_DIR / f"case_{game_id:02d}"
    case_dir.mkdir(parents=True, exist_ok=True)
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise TimeoutError(f"Game {game_id} reached its deadline before extraction.")
    process = await asyncio.create_subprocess_exec(
        "7z",
        "x",
        "-y",
        f"-p{key}",
        f"-o{case_dir}",
        str(archive),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=remaining)
    except (asyncio.CancelledError, TimeoutError):
        process.kill()
        await process.wait()
        raise
    if process.returncode != 0:
        output = (stderr or stdout).decode("utf-8", errors="replace")
        raise RuntimeError(f"Could not extract Game {game_id}: {output}")
    return case_dir


def find_archive(game_id: int) -> Path:
    name = f"case_{game_id:02d}.zip"
    candidates = (ARCHIVE_DIR / name, Path("cases") / name, Path(name))
    archive = next((candidate for candidate in candidates if candidate.exists()), None)
    if archive is None:
        raise FileNotFoundError(f"Missing case archive {name}.")
    return archive


async def read_case(game_id: int, case_dir: Path) -> CaseData:
    policy_path = case_dir / "policy.txt"
    description_path = case_dir / "description.txt"
    invoice_path = case_dir / "invoices.pdf"
    policy_text, description_text, line_items = await asyncio.gather(
        asyncio.to_thread(policy_path.read_text, encoding="utf-8"),
        asyncio.to_thread(description_path.read_text, encoding="utf-8"),
        asyncio.to_thread(read_invoice_line_items, invoice_path),
    )
    return CaseData(
        game_id=game_id,
        case_dir=case_dir,
        policy_text=policy_text,
        description_text=description_text,
        line_items=tuple(line_items),
        image_paths=tuple(
            sorted(
                path
                for path in case_dir.iterdir()
                if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
            )
        ),
    )


def read_invoice_line_items(invoice_path: Path) -> list[LineItem]:
    from pypdf import PdfReader

    text = "\n".join(page.extract_text() or "" for page in PdfReader(invoice_path).pages)
    line_items: dict[int, LineItem] = {}
    last_index: int | None = None
    in_items_section = not any("DESCRIPTION" in line for line in text.splitlines())
    for line in text.splitlines():
        stripped = line.strip()
        if "POS." in stripped and "DESCRIPTION" in stripped:
            in_items_section = True
            continue
        if stripped.startswith(("INVOICE", "Created on", "Page ")):
            in_items_section = False
            continue
        if not in_items_section:
            continue
        match = _NUMBERED_LINE_ITEM.match(line) or _SPACED_LINE_ITEM.match(line)
        if match:
            index = int(match.group("index"))
            name = match.group("name").strip()
            if _UNIT_ONLY.match(name):
                # Wrapped quantity fragment (e.g. "12 m\u00b2") of the previous item.
                if last_index is not None and last_index in line_items:
                    previous = line_items[last_index]
                    line_items[last_index] = LineItem(
                        index=previous.index,
                        name=f"{previous.name} ({index} {name})",
                        quantity=float(index),
                    )
                continue
            quantity = 1.0
            quantity_match = _TRAILING_QUANTITY.search(name)
            if quantity_match:
                quantity = float(quantity_match.group("quantity").replace(",", "."))
                name = f"{name[: quantity_match.start()]} ({quantity_match.group(0).strip()})"
            else:
                name = _TRAILING_DASHES.sub("", name)
            if not name or not any(char.isalpha() for char in name):
                continue
            line_items.setdefault(index, LineItem(index=index, name=name, quantity=quantity))
            last_index = index
    if not line_items:
        raise ValueError(f"Could not identify numbered Line Items in {invoice_path}.")
    return list(line_items.values())
