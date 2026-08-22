from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.case_loader import read_case

CASE_NAME = re.compile(r"case_(?P<game_id>\d+)$")


async def main() -> int:
    case_dirs = sorted(path for path in ROOT.joinpath("var/cases").glob("case_*") if path.is_dir())
    if not case_dirs:
        print("No extracted cases found under var/cases.")
        return 1

    failed = False
    for case_dir in case_dirs:
        match = CASE_NAME.fullmatch(case_dir.name)
        if match is None:
            continue
        game_id = int(match.group("game_id"))
        try:
            case = await read_case(game_id, case_dir)
            indices = [line_item.index for line_item in case.line_items]
            expected = list(range(1, len(indices) + 1))
            if indices != expected or any(line_item.quantity <= 0 for line_item in case.line_items):
                raise ValueError(f"indices={indices} quantities={[item.quantity for item in case.line_items]}")
            if any(not path.exists() for path in case.image_paths):
                raise ValueError("missing image path")
        except Exception as error:
            failed = True
            print(f"FAIL game={game_id} case={case_dir.name} error={type(error).__name__}: {error}")
            continue
        print(
            f"OK game={game_id} line_items={len(case.line_items)} "
            f"indices={indices} images={len(case.image_paths)}"
        )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
