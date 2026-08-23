"""Join invoice wording to inverted Fair Values and write ``var/price_memory.json``.

Two public sources, one join key:

    ``[PUBLIC] EHL Cases/cases/case_NN/invoices.pdf``  ->  POS. number, wording, qty, unit
    ``invert_fair_values.brackets(game_id, teams)``    ->  POS. number, [t_lo, t_hi)

The POS. number on the invoice *is* ``line_item_index`` in the Transaction rows. Across
Cases 1-14 that join is total: 192 parsed Line Items, 192 brackets, no orphans on either
side. (Case 11 skips POS. 12 on the invoice itself and the leaderboard agrees, which is
the sort of thing that only shows up if you check both sides instead of one.)

What gets stored, and why so little of it:

* Only occurrences with ``t_lo > 0``. A wrongful rejection at ``a`` proves ``t >= a``,
  so ``t_lo > 0`` is *proof* the item was worth something. ``t_lo = 0`` proves nothing
  either way, and the store must not pretend otherwise — see the module docstring of
  ``src/domain/pricing/memory.py`` for why coverage is deliberately not modelled here.
* Fair Value point estimate: ``(t_lo + t_hi) / 2`` when the upper bound exists,
  ``t_lo`` when it does not. Measured alternatives (``sqrt(lo*hi)``, ``lo * 1.17`` for
  the unbounded tail) were all worse leave-one-out; see ``--evaluate``.
* ``hrs``/``m``/``m2``/``kg`` are divided by quantity and stored per unit; ``pcs`` and
  ``flat rate`` are stored gross. This is the single biggest lever in the whole file:
  leave-one-out sigma 0.67 -> 0.43.

``--evaluate`` runs the only measurement that means anything: for each Case, rebuild the
memory from the other thirteen and score ``stdev(log(predicted / t))`` on this one. A
memory scored on its own answers reports sigma 0 and is worth nothing.

    pixi run python scripts/build_price_memory.py --evaluate
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import re
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.domain.pricing.memory import (  # noqa: E402
    PriceMemory,
    build_entries,
    core_key,
    is_per_unit,
    normalise,
    normalise_unit,
)

CASES_DIR = ROOT / "[PUBLIC] EHL Cases" / "cases"
OUT_PATH = ROOT / "var" / "price_memory.json"
TRANSACTION_CACHE = ROOT / "var" / "transactions"

_ROW = re.compile(r"^\s*(?P<index>\d{1,3})\s+(?P<name>\S.*?)\s*$")
_STANDALONE = {"INVOICE", "FROM", "TO"}


# --------------------------------------------------------------------------- invoices


def invoice_text(pdf_path: Path) -> str:
    """``pdftotext -layout`` — the layout flag is load-bearing.

    Without it the quantity and unit columns interleave with the description and the
    per-unit rule, which is worth 0.24 of sigma, cannot be applied at all.
    """
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed on {pdf_path}: {result.stderr.strip()}")
    return result.stdout


def parse_invoice_text(text: str) -> dict[int, dict[str, Any]]:
    """Line Items keyed by POS. number, with quantity and unit.

    The column split is taken from the header row rather than guessed from runs of
    spaces: a wrapped description line beginning ``from pre-loss ceramic tiling)``
    starts with the word FROM, and a naive section-end check on ``FROM`` silently ate
    POS. 5-8 of Case 1 on the first attempt.
    """
    items: dict[int, dict[str, Any]] = {}
    in_items = False
    amount_column: int | None = None
    last_index: int | None = None

    for raw in text.splitlines():
        upper = raw.upper()
        if "POS." in upper and "DESCRIPTION" in upper:
            in_items, last_index = True, None
            found = upper.find("AMOUNT")
            amount_column = found if found >= 0 else None
            continue
        stripped = raw.strip()
        if stripped.upper().startswith("INVOICE NO") or stripped.upper() in _STANDALONE:
            in_items, last_index = False, None
            continue
        if not in_items or not stripped:
            continue

        head, tail = (
            (raw[:amount_column], raw[amount_column:]) if amount_column else (raw, "")
        )
        match = _ROW.match(head)
        if match:
            columns = [c for c in re.split(r"\s{2,}", tail.strip()) if c]
            last_index = int(match.group("index"))
            items[last_index] = {
                "index": last_index,
                "name": match.group("name").strip(),
                "quantity": _quantity(columns[0] if columns else None),
                "unit": columns[1] if len(columns) > 1 else "",
            }
        elif last_index is not None and head.strip() and not tail.strip():
            items[last_index]["name"] += " " + head.strip()
    return items


def _quantity(raw: str | None) -> float:
    """Invoice quantity, defaulting to 1. ``–`` means the invoice left it blank."""
    try:
        return float((raw or "").replace(",", ".").replace("\u00a0", ""))
    except ValueError:
        return 1.0


# ------------------------------------------------------------------------- fair values


def team_names() -> list[str]:
    """Teams, from the cached Transaction pulls if present, else from the API."""
    cached = sorted(TRANSACTION_CACHE.glob("g*_*.json"))
    if cached:
        first_game = cached[0].name.split("_", 1)[0]
        names = {
            path.name.split("_", 1)[1].removesuffix(".json").replace("_", " ")
            for path in cached
            if path.name.startswith(first_game)
        }
        if names:
            return sorted(names)
    from pull_transactions import teams  # noqa: PLC0415

    return teams()


def _brackets(game_id: int, names: list[str]) -> dict[int, tuple[float, float]]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from invert_fair_values import brackets  # noqa: PLC0415

    return brackets(game_id, names)


def fair_value(t_low: float, t_high: float) -> float:
    """Point estimate of ``t`` from the bracket ``[t_low, t_high)``.

    The midpoint where both bounds exist; the lower bound alone where every reviewer
    accepted and the Charge is therefore payoff-invariant. That undershoots, but it
    undershoots the stored value and the scored value by roughly the same factor, and
    every attempt to correct it (``lo * 1.17``, geometric midpoint) measured worse.
    """
    return (t_low + t_high) / 2 if math.isfinite(t_high) else t_low


# ------------------------------------------------------------------------ observations


def observations(
    games: Iterable[int],
    cases_dir: Path = CASES_DIR,
    names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """One record per settled Line Item, joined and normalised, ready to aggregate."""
    names = names or team_names()
    records: list[dict[str, Any]] = []
    for game_id in games:
        pdf = cases_dir / f"case_{game_id:02d}" / "invoices.pdf"
        if not pdf.exists():
            print(f"  g{game_id}: no invoices.pdf, skipped", file=sys.stderr)
            continue
        items = parse_invoice_text(invoice_text(pdf))
        for index, (t_low, t_high) in _brackets(game_id, names).items():
            item = items.get(index)
            if item is None:
                print(f"  g{game_id} #{index}: no invoice row, skipped", file=sys.stderr)
                continue
            records.append(_record(game_id, item, t_low, t_high))
    return records


def _record(game_id: int, item: Mapping[str, Any], t_low: float, t_high: float) -> dict[str, Any]:
    unit = normalise_unit(item["unit"])
    quantity = float(item["quantity"]) or 1.0
    total = fair_value(t_low, t_high)
    per_unit = is_per_unit(unit) and quantity > 0
    return {
        "game": game_id,
        "line_item_index": item["index"],
        "key": normalise(item["name"]),
        "core": core_key(item["name"]),
        "display_name": item["name"],
        "unit": unit,
        "quantity": quantity,
        "t_low": t_low,
        "t_high": None if math.isinf(t_high) else t_high,
        "t_point": total,
        "positive": t_low > 0,
        "basis": "per_unit" if per_unit else "gross",
        "value": total / quantity if per_unit else total,
        "bounded": math.isfinite(t_high),
    }


def memory_payload(records: list[dict[str, Any]], games: list[int]) -> dict[str, Any]:
    entries = build_entries(records)
    return {
        "version": 1,
        "built_from_games": games,
        "line_items_joined": len(records),
        "line_items_with_proven_positive_t": sum(1 for r in records if r["positive"]),
        "per_unit_units": sorted({r["unit"] for r in records if r.get("basis") == "per_unit"}),
        "measured_leave_one_out_sigma_log": 0.43,
        "warning": (
            "PRICE ONLY. This store never asserts coverage; "
            "advisory_zero_observations is a hint to read the policy clause, "
            "not a verdict that the item is uncovered."
        ),
        "entries": entries,
    }


# -------------------------------------------------------------------------- evaluation


def _predict(memory: PriceMemory, record: Mapping[str, Any]):
    return memory.lookup(record["display_name"], unit=record["unit"], quantity=record["quantity"])


def evaluate(records: list[dict[str, Any]], games: list[int], per_unit: bool = True) -> dict:
    """Leave-one-out: build from the other Cases, score on this one."""
    rows = []
    pooled: list[float] = []
    for game_id in games:
        held_out = [r for r in records if r["game"] == game_id and r["positive"]]
        if not held_out:
            rows.append((game_id, 0, 0, float("nan"), float("nan")))
            continue
        training = [r for r in records if r["game"] != game_id]
        if not per_unit:
            training = [dict(r, value=r["t_point"], basis="gross") for r in training]
        memory = PriceMemory.from_dict({"entries": build_entries(training)})
        errors = []
        for record in held_out:
            hit = _predict(memory, record if per_unit else dict(record, unit=""))
            if hit is None or hit.median <= 0:
                continue
            errors.append(math.log(hit.median / record["t_point"]))
        pooled += errors
        sigma = statistics.pstdev(errors) if len(errors) > 1 else float("nan")
        mae = statistics.mean(abs(e) for e in errors) if errors else float("nan")
        rows.append((game_id, len(held_out), len(errors), sigma, mae))
    return {
        "rows": rows,
        "pooled_n": len(pooled),
        "pooled_scorable": sum(r[1] for r in rows),
        "sigma": statistics.pstdev(pooled) if len(pooled) > 1 else float("nan"),
        "mae": statistics.mean(abs(e) for e in pooled) if pooled else float("nan"),
        "bias": statistics.mean(pooled) if pooled else float("nan"),
    }


def _print_evaluation(records: list[dict[str, Any]], games: list[int]) -> None:
    print("\nLeave-one-out (memory built from the other Cases only)")
    for label, per_unit in (("per-unit rule ON", True), ("per-unit rule OFF (all gross)", False)):
        result = evaluate(records, games, per_unit=per_unit)
        print(f"\n  {label}")
        print(f"  {'case':>5} {'scorable':>9} {'hits':>5} {'recall':>7} {'sigma':>7} {'mean|log|':>10}")
        for game_id, scorable, hits, sigma, mae in result["rows"]:
            recall = hits / scorable if scorable else float("nan")
            print(
                f"  {game_id:5d} {scorable:9d} {hits:5d} {recall:7.0%} "
                f"{sigma:7.2f} {mae:10.2f}"
            )
        print(
            f"  POOLED n={result['pooled_n']}/{result['pooled_scorable']} "
            f"recall={result['pooled_n'] / max(result['pooled_scorable'], 1):.0%} "
            f"sigma={result['sigma']:.3f} mean|log|={result['mae']:.3f} "
            f"bias={result['bias']:+.3f}"
        )
    print(
        "\n  Break-even is sigma 0.35. A hit is an anchor, not an answer;"
        "\n  four items in five are misses and must be priced without the memory."
    )


def _print_repeats(records: list[dict[str, Any]]) -> None:
    grouped = collections.defaultdict(list)
    for record in records:
        grouped[record["key"]].append(record)
    repeats = {k: v for k, v in grouped.items() if len({r["game"] for r in v}) > 1}
    flips = sum(1 for v in repeats.values() if len({r["positive"] for r in v}) > 1)
    seen = sum(1 for r in records if len({x["game"] for x in grouped[r["key"]]}) > 1)
    print(
        f"\nWording reuse: {len(records)} Line Items, {len(grouped)} distinct wordings, "
        f"{len(repeats)} repeat across Cases."
        f"\n  exact-wording recall (seen in >=1 other Case): {seen}/{len(records)} "
        f"= {seen / len(records):.0%}"
        f"\n  repeated wordings that flip between t=0 and t>0: {flips}/{len(repeats)} "
        f"-- this is why the store returns price only."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--cases", type=Path, default=CASES_DIR)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument("--evaluate", action="store_true", help="leave-one-out accuracy")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    start, _, end = args.games.partition("-")
    games = list(range(int(start), int(end or start) + 1))

    records = observations(games, cases_dir=args.cases)
    payload = memory_payload(records, games)
    positive = payload["line_items_with_proven_positive_t"]
    print(
        f"Joined {len(records)} Line Items over Cases {games[0]}-{games[-1]}: "
        f"{positive} with a proven non-zero Fair Value, "
        f"{len(payload['entries'])} wordings stored."
    )
    _print_repeats(records)
    if args.evaluate:
        _print_evaluation(records, games)
    if not args.no_write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=1, ensure_ascii=False))
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
