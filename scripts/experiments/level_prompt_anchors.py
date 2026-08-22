"""A prompt whose price anchors are taken from the recovered Fair Values, not from intuition.

`level_anchors.py` checks the four anchors the shipped prompt asserts against the settled
Fair Values, in two disjoint windows (Games 1-14 and 15-24). Three of them are wrong, and
they are wrong in the *same direction in both windows*, which is the only kind of evidence
worth acting on here:

    anchor as shipped                              median true t (1-14 / 15-24)   t_hat/t
    ---------------------------------------------- ------------------------------ -------
    leak detection ... "typically 50-400 EUR"       411 / 561                      0.56 / 0.72
    disposal and hire ... "typically 50-400 EUR"     61 /  71                      3.35 / 2.46
    "small parts ... genuinely cheap: tens of EUR"   86 / 177                      0.54 / 0.25
    drying ... "typically 50-400 EUR"               203 / 564                      2.42 / 1.39

So the sentence that lumps "equipment hire, drying, leak detection and disposal" into one
50-400 EUR range is doing real damage: it is 7x too low at one end of that list and 3x too
high at the other. And "small parts are genuinely cheap" is false -- the settled positions
run to the low hundreds.

Every number below is taken from **Games 1-14 only**, so Games 15-24 are a held-out test of
the rewrite. The variants are dumped in both framings, hinted and unanchored, because the
shipped ensemble is both and an A/B that changes only one member measures the wrong thing.

    pixi run python scripts/level_prompt_anchors.py --games 1-24
    pixi run python scripts/level_fit.py --games 15-24 --tag anchor,anchornohint --apply 0 1
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from level_compat import (  # noqa: E402
    CASES,
    PROMPT,
    PROMPT_UNANCHORED,
    dump_evidence,
    load_evidence,
    request_evidence,
)

from src.data.case_loader import read_case  # noqa: E402

SHIPPED_ANCHORS = """Anchors, since gross totals for a whole Line Item are easy to get wrong by an order of magnitude:
- Tradesman labour runs roughly 60-110 EUR per hour, so an hourly Line Item is that rate multiplied by the hours: 6.75 technician hours is several hundred EUR, not tens.
- Small parts, fittings, screws and consumables are genuinely cheap: tens of EUR for the whole position.
- Equipment hire, drying, leak detection and disposal are typically 50-400 EUR per position.
- Appliances, electronics, restoration and structural work reach the low thousands."""

#: Rewritten from the recovered Fair Values of Games 1-14 (`level_anchors.py`). The ranges
#: are the measured inter-quartile spread of the true Fair Value in each keyword bin, so
#: they are claims about settled outcomes rather than about German retail prices.
MEASURED_ANCHORS = """Anchors from settled positions of exactly this kind, since gross totals for a whole Line Item are easy to get wrong by an order of magnitude:
- Tradesman labour runs roughly 60-110 EUR per hour, so an hourly Line Item is that rate multiplied by the hours: 6.75 technician hours is several hundred EUR, not tens.
- Leak detection, moisture surveys and electro-acoustic tracing settle at 400-650 EUR for the position. They are specialist call-outs, not a small extra: pricing one in the tens or low hundreds is the single most common underestimate.
- Damage assessment, inspection, documentation and reporting positions settle anywhere from 20 to 600 EUR; take the printed scope seriously rather than defaulting to a small fee.
- Disposal, waste removal, skips and equipment hire are genuinely cheap: 50-100 EUR for the whole position, rarely more.
- Drying, dehumidification and air movers settle at 70-300 EUR for a room-sized position and reach the low thousands only for large areas with the square metres printed.
- Small parts, fittings and consumables are not trivial: comparable positions settled at 80-300 EUR gross for the whole position.
- Appliances, electronics, restoration and structural work reach the low thousands, but they are also where overestimates cluster: a replacement is the price of the item, not of the room."""

BASELINE = PROMPT
BASELINE_NOHINT = PROMPT_UNANCHORED

if SHIPPED_ANCHORS not in BASELINE:  # pragma: no cover - guards a silent no-op A/B
    raise SystemExit("the shipped anchor block moved; update SHIPPED_ANCHORS before dumping")

VARIANTS = {
    "anchor": BASELINE.replace(SHIPPED_ANCHORS, MEASURED_ANCHORS),
    "anchornohint": BASELINE_NOHINT.replace(SHIPPED_ANCHORS, MEASURED_ANCHORS),
}


async def one(game_id: int, variant: str, refresh: bool) -> str:
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return f"case {game_id:02d}: not extracted"
    if not refresh and load_evidence(game_id, variant) is not None:
        return f"case {game_id:02d}: {variant} cached"
    case = await read_case(game_id, case_dir)
    evidence = await asyncio.to_thread(request_evidence, case, 60.0, VARIANTS[variant])
    dump_evidence(game_id, variant, evidence)
    return f"case {game_id:02d}: {variant} items={len(evidence)}"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-24")
    parser.add_argument("--variants", default="anchor,anchornohint")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--show", action="store_true", help="print the prompt and exit")
    args = parser.parse_args()
    if args.show:
        print(VARIANTS["anchor"])
        return
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))
    limit = asyncio.Semaphore(args.concurrency)

    async def guarded(game_id: int, variant: str) -> str:
        async with limit:
            try:
                return await one(game_id, variant, args.refresh)
            except Exception as error:
                return f"case {game_id:02d} {variant}: FAILED {error}"

    jobs = [
        guarded(game_id, variant)
        for variant in args.variants.split(",")
        for game_id in game_ids
    ]
    for line in await asyncio.gather(*jobs):
        print(line)


if __name__ == "__main__":
    asyncio.run(main())
