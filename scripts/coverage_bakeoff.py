"""Two coverage estimators, head to head: Channel C's, and `src/evidence/policy/coverage.py`'s.

The finding this answers
-----------------------
Our Limit collapses to zero on ~30% of priced Line Items, because `src.pricing.price_item`
zeroes it whenever `coverage_probability <= COVERAGE_FLOOR = 2/3`. Two fixes have already
been measured and both failed:

* **Raising `LIMIT_CEILING`** -- 0.45 shipped, 0.70 and 0.85 both worse on Games 28-30.
* **Moving `COVERAGE_FLOOR`** -- the whole 0.0-0.8 sweep spans 77 euros over 29 Games,
  because below the floor the one-third quantile of the posterior is already ~0. A posterior
  with 60% of its mass at zero genuinely has a zero bottom third.

So the collapse *rule* is right and its **input** is suspect. `src/evidence/policy/coverage.py` is a
second, independent reading of the same question -- one call per 8 Line Items, two samples
averaged, a verbatim Policy quote required before a verdict may go below 1/3 -- and it is
imported by nothing. This script decides whether it should be, in the only two currencies
that count: a confusion matrix against the recovered Fair Values, and euros.

    PYTHONPATH=. python scripts/coverage_bakeoff.py grade
    PYTHONPATH=. python scripts/coverage_bakeoff.py euros
    PYTHONPATH=. python scripts/coverage_bakeoff.py timing
    PYTHONPATH=. python scripts/coverage_bakeoff.py all

**A better confusion matrix that loses money does not ship**, so `euros` is the verdict and
`grade` is the diagnosis. The euro column is `scripts/replay_payoffs.replay` against the real
Field, with the band, the Charge, `LIMIT_CEILING`, `LIMIT_CAP` and Channel A's dash flag all
held **exactly** fixed -- the only thing that varies between rows of the table is the number
handed to `Evidence.coverage_probability`.

What the sample is
------------------
One row per (Game, Line Item) for every settled Game, carrying

* the band and the Channel C coverage probability that were available at decision time,
* `src/evidence/policy/coverage.py`'s `p_covered` for the same item (`scripts/coverage_dump.py`),
* the Fair Value bracket recovered afterwards from the settled Transactions.

Ground truth is `t_lo == 0`, i.e. **nobody was ever owed a euro on this Line Item**, which is
the only observable signature of a worthless position (`invert_fair_values.brackets`). It is
one-sided in a way worth remembering when reading the recall column: an item can have
`t_lo = 0` because it is genuinely worth nothing *or* because every team happened to Charge
above `t` on it, so the "truly worthless" set is a slight over-count.

Games 26+ are **logged** (`var/decisions/game_0NN.json`, schema 2). Games 1-25 are
**reconstructed** from the cached single model draw plus the cached Price Memory channel
through `blend.combine` and `price_item`, exactly as `scripts/charge_buckets.py` does it, so
the two scripts' samples are comparable. Reconstructed rows are what today's pricing would
have done, which is the right counterfactual for a change to today's pricing.

The noise floor is **26,622 over 18 Games**, scaled as `26,622 * sqrt(n/18)`; `euros` prints
it per window so a small number is not read as a win.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import math
import statistics
import sys
from dataclasses import dataclass, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.case_loader import read_case  # noqa: E402
from src.pricing.engine import COVERAGE_FLOOR, Evidence, price_item  # noqa: E402
from src.evidence.policy.coverage import (  # noqa: E402
    DEFAULT_P_COVERED,
    LIMIT_COLLAPSE,
)
from src.strategies.strategy2.blend import combine  # noqa: E402
from scripts.coverage_dump import load as load_coverage  # noqa: E402
from scripts.coverage_dump import seconds as coverage_seconds  # noqa: E402
from scripts.dump_evidence import load as load_evidence  # noqa: E402
from scripts.replay_payoffs import UnreconstructableGame, replay  # noqa: E402
from scripts.replay_payoffs import snapshot as _snapshot  # noqa: E402

snapshot = functools.lru_cache(maxsize=None)(_snapshot)

DECISIONS = Path("var/decisions")
CASES = Path("[PUBLIC] EHL Cases/cases")
INF = float("inf")

#: Every Game with a settled snapshot. Games that do not reconstruct are dropped loudly by
#: `dataset()` rather than scored against.
ALL_GAMES = tuple(range(1, 31))
RECENT = tuple(range(21, 28))
HELD_OUT = (28, 29, 30)

#: `26,622 * sqrt(n / 18)` -- the measured spread of the replay over 18 Games. Any euro
#: delta smaller than this is not a result.
NOISE_18 = 26_622.0


def noise_floor(n: int) -> float:
    return NOISE_18 * math.sqrt(n / 18.0)


# --------------------------------------------------------------------------- the sample


@dataclass(frozen=True)
class Row:
    game: int
    index: int
    origin: str  #: "logged" | "recon"
    evidence: Evidence  #: band + Channel C coverage, as priced
    uncovered: bool  #: Channel A -- the invoice printed a dash
    name: str
    t_lo: float
    t_hi: float
    #: `src/evidence/policy/coverage.py`'s reading, or None when the Case was not dumped
    p_coverage_module: float | None = None

    @property
    def worthless(self) -> bool:
        """Ground truth: nobody was ever owed a euro on this Line Item."""
        return self.t_lo <= 0.0

    @property
    def p_channel_c(self) -> float:
        return self.evidence.coverage_probability


def _line_items(game_id: int) -> dict[int, tuple[str, bool]]:
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return {}
    case = asyncio.run(read_case(game_id, case_dir))
    return {
        item.index: (item.name, bool(item.quantity_missing)) for item in case.line_items
    }


def _logged_rows(game_id: int, brackets: dict[int, tuple[float, float]]) -> list[Row]:
    path = DECISIONS / f"game_{game_id:03d}.json"
    if not path.exists():
        return []
    blob = json.loads(path.read_text())
    rows = []
    for item in blob.get("items") or ():
        index = item["index"]
        if index not in brackets or item.get("coverage_probability") is None:
            continue
        rows.append(
            Row(
                game=game_id,
                index=index,
                origin="logged",
                evidence=Evidence(
                    index=index,
                    coverage_probability=item["coverage_probability"],
                    price_low=item.get("price_low") or 0.0,
                    price_median=item.get("price_median") or 0.0,
                    price_high=item.get("price_high") or 0.0,
                ),
                uncovered=bool(item.get("quantity_missing")),
                name=item.get("name") or "",
                t_lo=brackets[index][0],
                t_hi=brackets[index][1],
            )
        )
    return rows


def _recon_rows(game_id: int, brackets: dict[int, tuple[float, float]]) -> list[Row]:
    model = load_evidence(game_id, "model")
    if model is None:
        return []
    memory = load_evidence(game_id, "memory") or {}
    items = _line_items(game_id)
    rows = []
    for index, bracket in brackets.items():
        name, uncovered = items.get(index, ("", False))
        merged = combine(model.get(index), memory.get(index))
        if merged is None:
            continue  # uninformed constants: not priced by the engine, so not ours to move
        rows.append(
            Row(
                game=game_id,
                index=index,
                origin="recon",
                evidence=merged,
                uncovered=uncovered,
                name=name,
                t_lo=bracket[0],
                t_hi=bracket[1],
            )
        )
    return rows


def dataset(games=ALL_GAMES, *, require_coverage: bool = True) -> list[Row]:
    """Prefer the decision log; fall back to reconstruction from the evidence cache.

    With `require_coverage` (the default) a Game whose coverage dump is missing is dropped
    **entirely**, because a table that grades one estimator on 30 Games and the other on 24
    compares two samples rather than two estimators.
    """
    rows: list[Row] = []
    for game_id in games:
        try:
            brackets = snapshot(game_id).fair_brackets
        except UnreconstructableGame as error:
            print(f"  skipping G{game_id}: {error}", file=sys.stderr)
            continue
        verdicts = load_coverage(game_id)
        if verdicts is None and require_coverage:
            print(f"  skipping G{game_id}: no coverage dump", file=sys.stderr)
            continue
        got = _logged_rows(game_id, brackets) or _recon_rows(game_id, brackets)
        for row in got:
            verdict = (verdicts or {}).get(row.index)
            rows.append(
                replace(
                    row,
                    p_coverage_module=None if verdict is None else verdict.p_covered,
                )
            )
    return rows


def graded(rows: list[Row]) -> list[Row]:
    """The rows both estimators have an opinion on -- the only fair comparison."""
    return [row for row in rows if row.p_coverage_module is not None]


# ---------------------------------------------------------------------- the estimators


#: name -> (row -> p_covered). Every one of these is fed to the *same* `price_item` with the
#: *same* band, so the euro table below isolates this number and nothing else.
#:
#: The three blends are here because averaging two independent readings is what made Channel
#: C's price band usable (+28,625), and because the cost of being wrong is **asymmetric**: a
#: false "uncovered" collapses the Limit and pays 1.5a in wrongful-rejection penalties on
#: every fair Charge, while a false "covered" only pays a claim. `max` is the cautious
#: direction and `min` the aggressive one, and the table is the only way to find out which
#: side of that asymmetry we are currently on.
ESTIMATORS: dict[str, object] = {
    "channel C (shipped)": lambda row: row.p_channel_c,
    "coverage.py": lambda row: row.p_coverage_module,
    "mean": lambda row: (row.p_channel_c + row.p_coverage_module) / 2.0,
    "min": lambda row: min(row.p_channel_c, row.p_coverage_module),
    "max": lambda row: max(row.p_channel_c, row.p_coverage_module),
    "flat 0.9": lambda _row: DEFAULT_P_COVERED,
    # The two bounds. `oracle` is the ceiling on what *any* coverage estimator can be worth,
    # because it knows the answer: 1 where the Line Item was worth something, 0 where it was
    # not. If the oracle's delta is inside the noise floor, no reading of the Policy -- ours,
    # a better one, or a perfect one -- can pay for itself, and that is the whole question
    # settled without arguing about a confusion matrix.
    "oracle": lambda row: 0.0 if row.worthless else 1.0,
    "flat 0.0 (collapse all)": lambda _row: 0.0,
}


# ------------------------------------------------------------------------- the grading


@dataclass(frozen=True)
class Confusion:
    n: int
    worthless: int
    #: of the truly worthless items, the share pushed at or below the threshold
    recall: float
    #: of the genuinely valuable items, the share pushed at or below the threshold
    false_positive: float
    brier: float
    flagged: int


def confusion(rows: list[Row], estimator, threshold: float) -> Confusion:
    hits = misses = false_pos = true_neg = 0
    squared = []
    for row in rows:
        p = float(estimator(row))
        truth = 0.0 if row.worthless else 1.0
        squared.append((p - truth) ** 2)
        flagged = p <= threshold
        if row.worthless:
            hits += flagged
            misses += not flagged
        else:
            false_pos += flagged
            true_neg += not flagged
    worthless = hits + misses
    valuable = false_pos + true_neg
    return Confusion(
        n=len(rows),
        worthless=worthless,
        recall=hits / worthless if worthless else 0.0,
        false_positive=false_pos / valuable if valuable else 0.0,
        brier=statistics.fmean(squared) if squared else 0.0,
        flagged=hits + false_pos,
    )


def grade(rows: list[Row]) -> None:
    rows = graded(rows)
    games = sorted({row.game for row in rows})
    print(
        f"\n{len(rows)} Line Items over {len(games)} Games "
        f"(G{games[0]}-G{games[-1]}), "
        f"{sum(1 for r in rows if r.worthless)} of them truly worthless (t_lo = 0)"
    )
    for threshold, label in (
        (LIMIT_COLLAPSE, "1/3 (coverage.py's LIMIT_COLLAPSE)"),
        (COVERAGE_FLOOR, "2/3 (pricing.COVERAGE_FLOOR -- what actually zeroes the Limit)"),
    ):
        print(f"\n  flagged when p_covered <= {label}")
        print(
            f"    {'estimator':<22}{'recall':>9}{'false pos':>11}{'brier':>9}"
            f"{'flagged':>9}"
        )
        for name, estimator in ESTIMATORS.items():
            c = confusion(rows, estimator, threshold)
            print(
                f"    {name:<22}{c.recall:>9.1%}{c.false_positive:>11.1%}"
                f"{c.brier:>9.3f}{c.flagged:>9d}"
            )

    # Where the two readings *disagree* is the only place a blend can help, so the hit rate
    # inside each disagreement cell is what decides whether a blend is worth testing at all.
    print("\n  agreement between the two readings, on the 2/3 threshold that decides")
    print(f"    {'cell':<18}{'n':>5}{'correct':>10}")
    flags_c = {id(r): r.p_channel_c <= COVERAGE_FLOOR for r in rows}
    flags_m = {id(r): r.p_coverage_module <= COVERAGE_FLOOR for r in rows}
    cells = {
        "both flag": [r for r in rows if flags_c[id(r)] and flags_m[id(r)]],
        "only channel C": [r for r in rows if flags_c[id(r)] and not flags_m[id(r)]],
        "only coverage.py": [r for r in rows if not flags_c[id(r)] and flags_m[id(r)]],
        "neither": [r for r in rows if not flags_c[id(r)] and not flags_m[id(r)]],
    }
    for label, group in cells.items():
        if not group:
            print(f"    {label:<18}{0:>5}")
            continue
        # "Correct" means the flag matched the truth: a flagged item was worthless, an
        # unflagged one was worth something.
        right = sum(
            1 for r in group if r.worthless == (label != "neither")
        )
        print(
            f"    {label:<18}{len(group):>5}"
            f"{f'{right}/{len(group)}':>10}  ({right / len(group):.0%})"
        )


# --------------------------------------------------------------------------- the euros


def submission(rows: list[Row], estimator) -> dict[int, dict[int, tuple[float, float]]]:
    """`{game: {index: (charge, limit)}}` -- the shipped pricing with one number swapped."""
    out: dict[int, dict[int, tuple[float, float]]] = {}
    for row in rows:
        p = float(estimator(row))
        evidence = replace(row.evidence, coverage_probability=p)
        price = price_item(evidence, confirmed_uncovered=row.uncovered)
        out.setdefault(row.game, {})[row.index] = (price.charge, price.limit)
    return out


def euros(rows: list[Row], estimator, games) -> dict[int, float]:
    """Net per Game from replaying `estimator`'s submission against the real Field."""
    priced = submission(rows, estimator)
    out: dict[int, float] = {}
    for game_id in games:
        snap = snapshot(game_id)
        # Line Items we have no evidence row for keep their real submitted numbers, so the
        # comparison isolates the estimator instead of scoring a partial submission.
        full = {
            index: (snap.charges[index][snap.us], snap.limit_point(index, snap.us))
            for index in snap.line_items
        }
        full.update(priced.get(game_id, {}))
        out[game_id] = replay(snap, full).net
    return out


def euro_table(rows: list[Row]) -> None:
    rows = graded(rows)
    games = sorted({row.game for row in rows})
    windows = [
        (f"all {len(games)}", tuple(games)),
        ("G21-27", tuple(g for g in games if g in RECENT)),
        ("held out G28-30", tuple(g for g in games if g in HELD_OUT)),
    ]

    per_game = {name: euros(rows, est, games) for name, est in ESTIMATORS.items()}
    baseline = per_game["channel C (shipped)"]

    print("\n  net in euros, replayed against the real Field; delta is against channel C")
    header = f"    {'estimator':<24}"
    for label, _window in windows:
        header += f"{label:>21}"
    print(header)
    print(f"    {'':<24}" + "".join(f"{'net':>12}{'delta':>9}" for _ in windows))
    for name in ESTIMATORS:
        line = f"    {name:<24}"
        for _label, window in windows:
            total = sum(per_game[name][g] for g in window)
            delta = total - sum(baseline[g] for g in window)
            line += f"{total:>12,.0f}{delta:>+9,.0f}"
        print(line)

    print("\n    noise floor, 26,622 * sqrt(n/18):")
    for label, window in windows:
        print(f"      {label:<18}n={len(window):<3} +/-{noise_floor(len(window)):>10,.0f}")

    print("\n  per Game (net; delta of each variant against channel C)")
    names = ["channel C (shipped)", "coverage.py", "mean", "min", "max", "oracle"]
    print("    game" + "".join(f"{n.split(' ')[0]:>14}" for n in names))
    for game_id in games:
        line = f"    G{game_id:<4}"
        for name in names:
            value = per_game[name][game_id]
            line += f"{value:>14,.0f}" if name == "channel C (shipped)" else (
                f"{value - baseline[game_id]:>+14,.0f}"
            )
        print(line)


def blame(rows: list[Row]) -> None:
    """Why the euro table is flat: what a collapsed Limit actually costs, item by item.

    The premise of this whole exercise is that a wrong coverage probability zeroes the Limit
    on a Line Item that was worth real money, and every fair Charge on it is then penalised at
    `1.5a`. That is true and it is measured below. What is *not* true is that the Limit rule
    would pay those Charges if the collapse were removed: `LIMIT_CEILING x median` (and
    `LIMIT_CAP`) usually still sits under what the Field Charges, so un-collapsing an item
    buys back a small fraction of its penalty. This is the same arithmetic
    `src/pricing.py`'s `COVERAGE_FLOOR` note already reports for the cliff, restated per item
    so the size of the prize is visible before anyone spends a model call on it.
    """
    rows = graded(rows)
    games = sorted({row.game for row in rows})
    shipped = submission(rows, ESTIMATORS["channel C (shipped)"])
    oracle = submission(rows, ESTIMATORS["oracle"])

    wrong = [r for r in rows if r.p_channel_c <= COVERAGE_FLOOR and not r.worthless]
    print(
        f"\n  {len([r for r in rows if r.p_channel_c <= COVERAGE_FLOOR])} of {len(rows)} "
        f"Line Items are collapsed by channel C's coverage "
        f"({len([r for r in rows if r.p_channel_c <= COVERAGE_FLOOR]) / len(rows):.0%}); "
        f"{len(wrong)} of them were worth something"
    )
    print(
        f"\n  the {len(wrong)} wrongly collapsed items -- penalty paid, and what an oracle "
        f"coverage recovers"
    )
    print(
        f"    {'game':>5}{'item':>5}{'t_lo':>10}{'median':>10}{'b ship':>9}"
        f"{'b oracle':>10}{'cost ship':>11}{'cost orcl':>11}  name"
    )
    total_cost = total_oracle = 0.0
    for row in sorted(wrong, key=lambda r: (r.game, r.index)):
        snap = snapshot(row.game)
        t = snap.fair_point(row.index)
        cost_ship = sum(
            _reviewer(snap.charges[row.index][team], shipped[row.game][row.index][1], t)
            for team in snap.opponents
        )
        cost_oracle = sum(
            _reviewer(snap.charges[row.index][team], oracle[row.game][row.index][1], t)
            for team in snap.opponents
        )
        total_cost += cost_ship
        total_oracle += cost_oracle
        print(
            f"    {row.game:>5}{row.index:>5}{row.t_lo:>10,.0f}"
            f"{row.evidence.with_defaults().price_median:>10,.0f}"
            f"{shipped[row.game][row.index][1]:>9,.0f}"
            f"{oracle[row.game][row.index][1]:>10,.0f}"
            f"{cost_ship:>11,.0f}{cost_oracle:>11,.0f}  {row.name[:34]}"
        )
    print(
        f"\n    reviewer cost on those items: {total_cost:>12,.0f} as shipped, "
        f"{total_oracle:,.0f} with oracle coverage -- "
        f"the collapse is worth {total_cost - total_oracle:,.0f} of it, "
        f"over {len(games)} Games"
    )


def _reviewer(charge: float, limit: float, fair_value: float) -> float:
    if charge <= limit:
        return charge
    if charge <= fair_value:
        return 1.5 * charge
    return 0.0


# -------------------------------------------------------------------------- the timing


def timing() -> None:
    """Wall clock of the coverage pass per Case, largest Case first.

    Strategy 2 already uses 7-16 s of a 60-second window, so the only admissible way to add
    this is **concurrently with the existing draws** -- the wall clock then becomes
    `max(draws, coverage)` rather than the sum. These numbers are from
    `coverage_dump.py --time`, one Case at a time, so they are the real per-Case cost and not
    an artefact of a saturated deployment.
    """
    rows = []
    for game_id in ALL_GAMES:
        path = Path(f"var/coverage/case_{game_id:02d}.json")
        if not path.exists():
            continue
        blob = json.loads(path.read_text())
        rows.append((blob["items"], game_id, blob["seconds"], len(blob["verdicts"])))
    rows.sort(reverse=True)
    print(f"\n  {'case':>6}{'line items':>12}{'chunks x2':>11}{'seconds':>10}")
    for items, game_id, secs, _n in rows:
        chunks = math.ceil(items / 8) * 2
        print(f"  {game_id:>6}{items:>12}{chunks:>11}{secs:>10.1f}")
    if rows:
        slowest = max(rows, key=lambda r: r[2])
        biggest = max(rows)
        print(
            f"\n  slowest Case {slowest[1]} at {slowest[2]:.1f}s; "
            f"largest Case {biggest[1]} ({biggest[0]} Line Items) at {biggest[2]:.1f}s; "
            f"median {statistics.median(r[2] for r in rows):.1f}s"
        )


# ----------------------------------------------------------------------------- the CLI


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=["grade", "euros", "blame", "timing", "all"],
        default="all",
        nargs="?",
    )
    parser.add_argument("--games", default="1-30")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    games = tuple(range(int(start), int(end or start) + 1))

    if args.mode == "timing":
        timing()
        return

    rows = dataset(games)
    if args.mode in ("grade", "all"):
        grade(rows)
    if args.mode in ("euros", "all"):
        euro_table(rows)
    if args.mode in ("blame", "all"):
        blame(rows)
    if args.mode == "all":
        timing()


if __name__ == "__main__":
    main()
