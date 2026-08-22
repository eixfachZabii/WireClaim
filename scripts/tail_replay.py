"""Euro-weighted harness for Strategy 2's tail problem.

Scores a candidate pricing of the cached model evidence against the *real* Field with
`scripts/replay_payoffs.replay`, not against a log error. Log error weights a EUR 10 item
exactly like a EUR 7,000 one, and the money is entirely in the second kind.

    pixi run python scripts/tail_replay.py --games 1-14            # net per Game
    pixi run python scripts/tail_replay.py --games 1-14 --worst 25 # where the money leaks

Price Memory is off by default: it contains the very Games this replays, so leaving it on
leaks the answer into the headline number.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dump_evidence import load as load_evidence  # noqa: E402
from replay_payoffs import GameSnapshot, our_actual_submission, replay, snapshot  # noqa: E402

from src.data.case_loader import read_case  # noqa: E402
from src.data.models import CaseData  # noqa: E402
from src.pricing import Evidence  # noqa: E402
from src.services.strategies.strategy2 import strategy as s2  # noqa: E402

INF = math.inf
CASES = Path("[PUBLIC] EHL Cases/cases")


def case_of(game_id: int) -> CaseData | None:
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return None
    return asyncio.run(read_case(game_id, case_dir))


def submission_of(
    case: CaseData,
    model: dict[int, Evidence],
    *,
    memory: bool = False,
) -> dict[int, tuple[float, float]]:
    memory_evidence = s2._memory_evidence(case) if memory else _channel_a_only(case)
    proposal = s2.build_proposal(case, model, memory_evidence)
    if proposal is None:
        return {}
    return {p.index: (p.charge_price, p.acceptance_limit) for p in proposal.prices}


def _channel_a_only(case: CaseData) -> dict[int, Evidence]:
    """Channel A (dash-quantity items) without the leaking Price Memory."""
    return {
        item.index: Evidence(
            index=item.index,
            coverage_probability=0.0,
            price_low=s2.SETTLED_MEDIAN * 0.5,
            price_median=s2.SETTLED_MEDIAN,
            price_high=s2.SETTLED_MEDIAN * 2,
        )
        for item in case.line_items
        if getattr(item, "quantity_missing", False)
    }


def inflate(snap: GameSnapshot, factor: float) -> GameSnapshot:
    """Sensitivity handle for the censored half of the ground truth.

    44 of 192 settled Line Items have no upper bracket -- nobody rightfully rejected them
    -- and `fair_point` then returns `t_lo`, which is only a lower bound. Anything tuned
    on that is biased towards believing the Field Overcharges. This raises the unbounded
    items to `factor * t_lo` so a conclusion can be checked against the other extreme.
    """
    if factor == 1.0:
        return snap
    return replace(
        snap,
        fair_brackets={
            index: ((lo * factor, hi) if hi == INF and lo > 0 else (lo, hi))
            for index, (lo, hi) in snap.fair_brackets.items()
        },
    )


def _fmt(value: float) -> str:
    return "inf" if value == INF else f"{value:,.0f}"


def per_item_report(
    snap: GameSnapshot,
    case: CaseData,
    submission: dict[int, tuple[float, float]],
    model: dict[int, Evidence],
) -> list[tuple[float, str]]:
    """Rows of (money left on the table, description), one per Line Item."""
    result = replay(snap, submission)
    oracle = replay(
        snap, {i: (snap.fair_point(i), snap.fair_point(i)) for i in snap.line_items}
    )
    names = {item.index: item.name for item in case.line_items}
    rows: list[tuple[float, str]] = []
    for index in snap.line_items:
        got = result.per_item[index][0] - result.per_item[index][1]
        best = oracle.per_item[index][0] - oracle.per_item[index][1]
        lo, hi = snap.fair_brackets[index]
        charge, limit = submission.get(index, (0.0, 0.0))
        band = model.get(index)
        band_text = (
            f"band {band.price_low:8,.0f}/{band.price_median:8,.0f}/{band.price_high:9,.0f}"
            f" p={band.coverage_probability:.2f}"
            if band
            else "band -- (no model evidence)"
        )
        rows.append(
            (
                best - got,
                f"G{snap.game_id:2d} i{index:2d} lost {best - got:9,.0f}  "
                f"t=[{_fmt(lo)},{_fmt(hi)})  a={charge:8,.0f} b={limit:8,.0f}  "
                f"{band_text}  {names.get(index, '?')[:52]}",
            )
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--worst", type=int, default=0)
    parser.add_argument("--memory", action="store_true", help="enable Price Memory (leaks)")
    parser.add_argument("--tag", default="model", help="evidence cache tag")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))

    total_new = total_actual = 0.0
    rows: list[tuple[float, str]] = []
    print(f"{'game':>5} {'items':>6} {'actual':>12} {'strategy2':>12} {'delta':>12}")
    for game_id in game_ids:
        model = load_evidence(game_id, args.tag)
        case = case_of(game_id)
        if model is None or case is None:
            print(f"{game_id:5d} {'--':>6} (no cached evidence or case)")
            continue
        try:
            snap = snapshot(game_id)
        except Exception as error:  # pragma: no cover - offline / unsettled Game
            print(f"{game_id:5d} no snapshot: {error}")
            continue
        submission = submission_of(case, model, memory=args.memory)
        new = replay(snap, submission).net
        actual = replay(snap, our_actual_submission(snap)).net
        total_new += new
        total_actual += actual
        print(
            f"{game_id:5d} {len(snap.line_items):6d} {actual:12,.0f} {new:12,.0f} "
            f"{new - actual:12,.0f}"
        )
        if args.worst:
            rows += per_item_report(snap, case, submission, model)
    print(
        f"{'TOTAL':>5} {'':>6} {total_actual:12,.0f} {total_new:12,.0f} "
        f"{total_new - total_actual:12,.0f}"
    )

    if args.worst:
        print(f"\nworst {args.worst} Line Items by money left on the table:")
        for _, text in sorted(rows, reverse=True)[: args.worst]:
            print("  " + text)


if __name__ == "__main__":
    main()
