"""Strategy bake-off: which track would have made the most money, in hindsight?

Why this exists
---------------
Four things price every Case concurrently -- `strategy1`, `strategy2`, `strategy3` and the
`fast_path` `llm_values` layer -- and only the router's winner is ever submitted. The router
ranks `strategy2 > strategy3 > strategy1` (`src.services.strategies.STRATEGY_PRIORITIES`) and
Strategy 2 has won every Game since 21, so we have never checked that the winner deserved to
win. Game 27 is the only Game where all three Proposals reached disk, and it says the opposite
of the ranking. One Game proves nothing. This script settles it over a range of Games.

What it measures
----------------
For every Game in `--games`:

1. `read_case` the extracted Case (run `pixi run cases` first to top up).
2. Call each selected strategy's `propose(case)` `--draws` times. **Every draw is cached to
   `var/bakeoff/game_NNN_<source>_draw<k>.json`** and never re-requested; these are real model
   calls. Wall clock is recorded per draw, because a track that scores well in 45 s is not a
   usable answer inside the 60-second Game.
3. Score every draw with `scripts/replay_payoffs.py` -- `snapshot(game_id)` then
   `replay(snap, {index: (charge, limit)})` -- which reproduces every published net to the cent
   with all sixteen opponents held fixed.
4. Score the same way: what we **actually** submitted, the **merged** router result (highest
   priority per Line Item, exactly as `RunManager.set_strategy` merges it), the four
   **hybrids** (one track's Charge with another's Limit), and two **oracles** as a ceiling.

Judging rules that are not negotiable
-------------------------------------
* **Euros, never log error.** A log error treats a EUR 10 Line Item like a EUR 7,000 one, and
  every real difference between these tracks lives in the expensive items.
* **The noise floor.** Game-to-game net is dominated by the Case, not by us: the measured
  floor is 26,622 over 18 Games, which scales as `26,622 * sqrt(n/18)`. Over 9 Games that is
  ~18,800. A pooled gap below the floor is **not** a result, and this script prints the floor
  next to the gap rather than leaving the reader to do it.
* **Two draws where affordable.** Model calls are stochastic. With `--draws 2` the script
  reports the between-draw spread of the same track on the same Case beside the between-track
  gap. If they are the same size, the honest answer is "not distinguishable".
* **Never condition on the true Fair Value.** Per-item attribution here buckets items by our
  own estimate and by observable Case features (name, invoice amount), not by `t`. The same
  items read 4x over-priced conditioned on `t` and 46% under-priced conditioned on `t_hat`;
  only the second is knowable at submission time.

Side effects, deliberately suppressed
-------------------------------------
`strategy2.propose` writes a decision log through `src.observability.decisions.record`, and re-running it
for a settled Game would overwrite `var/decisions/game_NNN.json` -- destroying the only place
Game 27's three Proposals are recorded. `_redirect_decision_log()` repoints `DECISIONS_DIR` at
`var/bakeoff/decisions` for the duration of the run. Nothing under `src/` is modified.

Usage
-----
    PYTHONPATH=. python scripts/strat_bakeoff.py --games 20-28 --draws 1
    PYTHONPATH=. python scripts/strat_bakeoff.py --games 20-28 --draws 2 --strategies strategy1,strategy2
    PYTHONPATH=. python scripts/strat_bakeoff.py --games 20-28 --offline      # cache only, no calls
    PYTHONPATH=. python scripts/strat_bakeoff.py --games 20-28 --report-only  # re-score the cache
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from replay_payoffs import (  # noqa: E402
    GameSnapshot,
    UnreconstructableGame,
    our_actual_submission,
    replay,
    snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "[PUBLIC] EHL Cases" / "cases"
CACHE = ROOT / "var" / "bakeoff"

#: The measured Game-to-Game noise floor: 26,622 euros of standard deviation over 18 Games.
#: Scaled as `NOISE_FLOOR_18 * sqrt(n / 18)` for a pooled total over `n` Games.
NOISE_FLOOR_18 = 26_622.0
NOISE_FLOOR_GAMES = 18

SOURCES = ("strategy1", "strategy2", "strategy3", "fast_path")

#: Charge/Limit hybrids worth scoring: (name, charge source, limit source).
HYBRIDS = (
    ("hybrid_c1_l2", "strategy1", "strategy2"),
    ("hybrid_c2_l1", "strategy2", "strategy1"),
    ("hybrid_c1_l3", "strategy1", "strategy3"),
    ("hybrid_c3_l1", "strategy3", "strategy1"),
)


def noise_floor(n_games: int) -> float:
    """The scaled noise floor for a pooled total over `n_games` Games."""
    return NOISE_FLOOR_18 * math.sqrt(n_games / NOISE_FLOOR_GAMES)


# ------------------------------------------------------------------ side-effect isolation


def _redirect_decision_log() -> None:
    """Point `src.observability.decisions` at `var/bakeoff/decisions` so a replay cannot clobber a Game.

    `strategy2.propose` records unconditionally, and `_existing_for_merge` refuses to merge
    with a log older than its merge window -- so a re-run of a settled Game writes a *fresh*
    file and the `proposals` section, which is the only record that Strategy 1 and 3 ever
    answered, is gone. This is the whole reason the bake-off is safe to run repeatedly.
    """
    import src.observability.decisions as decision_log

    decision_log.DECISIONS_DIR = CACHE / "decisions"
    decision_log.DECISIONS_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------------------- proposals


@dataclass
class Draw:
    """One `propose()` result for one Game, plus what it cost in wall clock."""

    game_id: int
    source: str
    draw: int
    #: line item index -> (charge, limit). Empty means the track answered with nothing.
    prices: dict[int, tuple[float, float]]
    elapsed_seconds: float
    error: str | None = None
    recorded_at: float = 0.0

    @property
    def answered(self) -> bool:
        return bool(self.prices)

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "source": self.source,
            "draw": self.draw,
            "prices": {str(i): [a, b] for i, (a, b) in sorted(self.prices.items())},
            "elapsed_seconds": self.elapsed_seconds,
            "error": self.error,
            "recorded_at": self.recorded_at or time.time(),
        }

    @classmethod
    def from_dict(cls, blob: Mapping[str, Any]) -> "Draw":
        return cls(
            game_id=int(blob["game_id"]),
            source=str(blob["source"]),
            draw=int(blob["draw"]),
            prices={
                int(i): (float(v[0]), float(v[1])) for i, v in (blob.get("prices") or {}).items()
            },
            elapsed_seconds=float(blob.get("elapsed_seconds") or 0.0),
            error=blob.get("error"),
            recorded_at=float(blob.get("recorded_at") or 0.0),
        )


def draw_path(game_id: int, source: str, draw: int) -> Path:
    return CACHE / f"game_{game_id:03d}_{source}_draw{draw}.json"


def load_draw(game_id: int, source: str, draw: int) -> Draw | None:
    path = draw_path(game_id, source, draw)
    if not path.exists():
        return None
    try:
        return Draw.from_dict(json.loads(path.read_text()))
    except (OSError, ValueError, KeyError):
        return None


def save_draw(result: Draw) -> None:
    path = draw_path(result.game_id, result.source, result.draw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=1, sort_keys=True))


async def _call(source: str, case: Any) -> Any:
    """Invoke one track on one Case. No `deadline`, so nothing is truncated by the clock."""
    if source == "strategy1":
        from src.services.strategies.strategy1 import propose

        return await propose(case)
    if source == "strategy2":
        from src.services.strategies.strategy2 import propose

        return await propose(case)
    if source == "strategy3":
        from src.services.strategies.strategy3 import propose

        return await propose(case)
    if source == "fast_path":
        from src.services.strategies.fast_path import llm_values

        return await llm_values(case)
    if source == "standard":
        from src.services.strategies.fast_path import standard_values

        return standard_values(case)
    raise ValueError(f"unknown source {source!r}")


async def obtain_draw(
    game_id: int, source: str, draw: int, case_factory, *, offline: bool, refresh: bool
) -> Draw | None:
    """The cached draw, or a fresh one. Returns None when offline and nothing is cached."""
    if not refresh:
        cached = load_draw(game_id, source, draw)
        if cached is not None:
            return cached
    if offline:
        return None
    case = await case_factory()
    started = time.monotonic()
    error: str | None = None
    prices: dict[int, tuple[float, float]] = {}
    try:
        proposal = await _call(source, case)
        if proposal is not None:
            prices = {
                int(p.index): (float(p.charge_price), float(p.acceptance_limit))
                for p in proposal.prices
            }
    except Exception as exc:  # a track that throws is a track that scores (0, 0)
        error = f"{type(exc).__name__}: {exc}"
    result = Draw(
        game_id=game_id,
        source=source,
        draw=draw,
        prices=prices,
        elapsed_seconds=time.monotonic() - started,
        error=error,
        recorded_at=time.time(),
    )
    save_draw(result)
    return result


# ---------------------------------------------------------------------------- submissions


def merged_submission(
    draws: Mapping[str, Draw], line_items: Sequence[int]
) -> dict[int, tuple[float, float]]:
    """The router's result: highest `STRATEGY_PRIORITIES` per Line Item, `fast_path` beneath.

    This mirrors `main.RunManager`: `standard_values` is the floor, `fast_path` overwrites it,
    and the three tracks overwrite that per index in priority order.
    """
    from src.services.strategies import STRATEGY_PRIORITIES

    out: dict[int, tuple[float, float]] = {}
    layers: list[tuple[int, str]] = [(-2, "standard"), (-1, "fast_path")]
    layers += [(STRATEGY_PRIORITIES.get(s, 0), s) for s in ("strategy1", "strategy2", "strategy3")]
    for _, source in sorted(layers, key=lambda kv: kv[0]):
        got = draws.get(source)
        if got is None:
            continue
        for index, pair in got.prices.items():
            if index in line_items or not out:
                out[index] = pair
    return {i: out[i] for i in line_items if i in out}


def hybrid_submission(
    charge_draw: Draw | None, limit_draw: Draw | None, line_items: Sequence[int]
) -> dict[int, tuple[float, float]] | None:
    """One track's Charge with another's Limit. None when either side did not answer."""
    if charge_draw is None or limit_draw is None or not charge_draw.prices or not limit_draw.prices:
        return None
    out: dict[int, tuple[float, float]] = {}
    for index in line_items:
        charge = charge_draw.prices.get(index)
        limit = limit_draw.prices.get(index)
        if charge is None and limit is None:
            continue
        out[index] = (
            charge[0] if charge is not None else 0.0,
            limit[1] if limit is not None else 0.0,
        )
    return out


def oracle_bracket(snap: GameSnapshot) -> dict[int, tuple[float, float]]:
    """`a = t_lo`, `b = t_hi`: the *provable* cheat -- charge the proven floor of the bracket
    and accept anything the bracket proves is fair.

    `t_hi` is `inf` on the 44-odd Line Items nobody rightfully rejected. An infinite Limit is
    not a submittable number, and worse, the reconstruction encodes an unrecoverable opponent
    Charge as `inf` too, so `b = inf` "accepts" an infinite Charge and the replay returns
    `-inf`. The unbounded branch therefore falls back to the bracket's representative point,
    which is `t_lo` exactly when the bracket is unbounded.
    """
    return {
        i: (lo, hi if math.isfinite(hi) else snap.fair_point(i))
        for i, (lo, hi) in snap.fair_brackets.items()
    }


def oracle_exact(snap: GameSnapshot) -> dict[int, tuple[float, float]]:
    """`a = b = t`: the exact ceiling. Charge the Fair Value, reject one cent above it."""
    return {i: (snap.fair_point(i), snap.fair_point(i)) for i in snap.line_items}


# --------------------------------------------------------------------------------- scoring


@dataclass
class Scored:
    label: str
    net: float
    income: float
    cost: float
    per_item: dict[int, tuple[float, float]]
    elapsed_seconds: float | None = None
    answered: bool = True
    covered_items: int = 0

    @property
    def per_item_net(self) -> dict[int, float]:
        return {i: inc - cost for i, (inc, cost) in self.per_item.items()}


def score(
    snap: GameSnapshot,
    label: str,
    submission: Mapping[int, tuple[float, float]] | None,
    *,
    elapsed: float | None = None,
    limit_rule: str = "mid",
) -> Scored | None:
    if submission is None:
        return None
    result = replay(snap, submission, limit_rule=limit_rule)
    return Scored(
        label=label,
        net=result.net,
        income=result.income,
        cost=result.cost,
        per_item=dict(result.per_item),
        elapsed_seconds=elapsed,
        answered=bool(submission),
        covered_items=len(submission),
    )


@dataclass
class GameResult:
    game_id: int
    snap: GameSnapshot
    #: label -> Scored for draw 0: the headline view, and the one the tables print
    scored: dict[str, Scored] = field(default_factory=dict)
    #: draw index -> label -> Scored. Every variant is rebuilt from that draw's Proposals, so
    #: `merged` and the hybrids get a spread of their own rather than borrowing draw 0's.
    by_draw: dict[int, dict[str, Scored]] = field(default_factory=dict)
    #: source -> [net per draw], for the between-draw spread
    draw_nets: dict[str, list[float]] = field(default_factory=dict)
    #: source -> [wall clock per draw]
    draw_times: dict[str, list[float]] = field(default_factory=dict)
    item_names: dict[int, str] = field(default_factory=dict)
    #: index -> {"quantity", "quantity_missing", "total_gross"} straight off the invoice
    item_facts: dict[int, dict[str, Any]] = field(default_factory=dict)
    submissions: dict[str, dict[int, tuple[float, float]]] = field(default_factory=dict)


async def run_game(
    game_id: int,
    sources: Sequence[str],
    draws: int,
    *,
    offline: bool,
    refresh: bool,
    limit_rule: str = "mid",
) -> GameResult | None:
    try:
        snap = snapshot(game_id)
    except (UnreconstructableGame, Exception) as exc:  # noqa: BLE001 - report and skip
        print(f"  G{game_id}: not reconstructable, skipped ({type(exc).__name__}: {exc})")
        return None

    case_holder: dict[str, Any] = {}

    async def case_factory() -> Any:
        if "case" not in case_holder:
            from src.data.case_loader import read_case

            case_dir = CASES_DIR / f"case_{game_id:02d}"
            if not case_dir.exists():
                raise FileNotFoundError(f"{case_dir} is not extracted; run `pixi run cases`")
            case_holder["case"] = await read_case(game_id, case_dir)
        return case_holder["case"]

    result = GameResult(game_id=game_id, snap=snap)

    # Case metadata for the per-item attribution. Never the Fair Value: only what an invoice
    # shows us at submission time.
    try:
        case = await case_factory()
        for line_item in case.line_items:
            result.item_names[int(line_item.index)] = str(line_item.name)
            result.item_facts[int(line_item.index)] = {
                "quantity": float(getattr(line_item, "quantity", 0.0) or 0.0),
                "quantity_missing": bool(getattr(line_item, "quantity_missing", False)),
                "total_gross": float(getattr(line_item, "total_gross", 0.0) or 0.0),
            }
    except Exception as exc:  # noqa: BLE001 - metadata only, never fatal
        print(f"  G{game_id}: Case metadata unavailable ({exc})")

    # `standard_values` is the floor layer `merged_submission` needs. Free: no model call.
    standard = await obtain_draw(
        game_id, "standard", 0, case_factory, offline=offline, refresh=refresh
    )

    per_draw: dict[int, dict[str, Draw]] = {k: {} for k in range(draws)}
    for source in sources:
        for k in range(draws):
            got = await obtain_draw(
                game_id, source, k, case_factory, offline=offline, refresh=refresh
            )
            if got is None:
                continue
            per_draw[k][source] = got
            result.draw_times.setdefault(source, []).append(got.elapsed_seconds)

    for k in range(draws):
        got_draws = dict(per_draw[k])
        if standard is not None:
            got_draws["standard"] = standard
        scored_k: dict[str, Scored] = {}
        for source in sources:
            got = got_draws.get(source)
            if got is None:
                continue
            scored = score(snap, source, got.prices, elapsed=got.elapsed_seconds, limit_rule=limit_rule)
            if scored is None:
                continue
            scored.answered = got.answered
            scored_k[source] = scored
            result.draw_nets.setdefault(source, []).append(scored.net)

        variants: dict[str, dict[int, tuple[float, float]] | None] = {
            "actual": our_actual_submission(snap),
            "merged": merged_submission(got_draws, snap.line_items) or None,
            "oracle_bracket": oracle_bracket(snap),
            "oracle_exact": oracle_exact(snap),
        }
        for name, charge_src, limit_src in HYBRIDS:
            variants[name] = hybrid_submission(
                got_draws.get(charge_src), got_draws.get(limit_src), snap.line_items
            )
        for label, submission in variants.items():
            scored = score(snap, label, submission, limit_rule=limit_rule)
            if scored is not None:
                scored_k[label] = scored
        result.by_draw[k] = scored_k
        if k == 0:
            result.scored = scored_k
            result.submissions = {
                source: dict(got.prices) for source, got in got_draws.items()
            }
            for label, submission in variants.items():
                if submission is not None:
                    result.submissions[label] = dict(submission)
    return result


# --------------------------------------------------------------------------------- reports


def _fmt(value: float | None, width: int = 11) -> str:
    if value is None:
        return "n/a".rjust(width)
    return f"{value:,.0f}".rjust(width)


def per_game_table(results: Sequence[GameResult], labels: Sequence[str]) -> str:
    head = "| Game | " + " | ".join(labels) + " |"
    rule = "|---" * (len(labels) + 1) + "|"
    lines = [head, rule]
    for r in results:
        cells = []
        for label in labels:
            scored = r.scored.get(label)
            if scored is None:
                cells.append("n/a")
            elif not scored.answered:
                cells.append("silent")
            else:
                cells.append(f"{scored.net:,.0f}")
        lines.append(f"| {r.game_id} | " + " | ".join(cells) + " |")
    totals = []
    for label in labels:
        got = [r.scored[label].net for r in results if label in r.scored]
        totals.append(f"**{sum(got):,.0f}**" if got else "n/a")
    lines.append("| **total** | " + " | ".join(totals) + " |")
    return "\n".join(lines)


def runtime_table(results: Sequence[GameResult], sources: Sequence[str]) -> str:
    lines = ["| Game | " + " | ".join(f"{s} s" for s in sources) + " |", "|---" * (len(sources) + 1) + "|"]
    for r in results:
        cells = []
        for s in sources:
            times = r.draw_times.get(s) or []
            cells.append("/".join(f"{t:.1f}" for t in times) if times else "n/a")
        lines.append(f"| {r.game_id} | " + " | ".join(cells) + " |")
    worst, mean = [], []
    for s in sources:
        allt = [t for r in results for t in (r.draw_times.get(s) or [])]
        worst.append(f"{max(allt):.1f}" if allt else "n/a")
        mean.append(f"{statistics.fmean(allt):.1f}" if allt else "n/a")
    lines.append("| **mean** | " + " | ".join(mean) + " |")
    lines.append("| **max** | " + " | ".join(worst) + " |")
    return "\n".join(lines)


def pooled_by_draw(
    results: Sequence[GameResult], labels: Sequence[str], draws: int
) -> dict[str, list[tuple[float, int]]]:
    """label -> `(pooled total, Games contributing)` per draw index.

    This is the comparison that decides the question. Summing per-Game between-draw *gaps*
    overstates the uncertainty in the pooled total, because the gaps partly cancel; the
    pooled total of draw 0 against the pooled total of draw 1 is the honest re-run of the
    whole experiment, and it is what should be held against the between-track gap.

    The Game count is carried because a hybrid is undefined when either parent went silent --
    Strategy 1 and Strategy 3 both timed out on Game 28 draw 1 -- and a total over 8 Games must
    not be quietly compared against a total over 9.
    """
    out: dict[str, list[tuple[float, int]]] = {}
    for label in labels:
        row: list[tuple[float, int]] = []
        for k in range(draws):
            nets = [r.by_draw[k][label].net for r in results if label in r.by_draw.get(k, {})]
            row.append((sum(nets), len(nets)))
        out[label] = row
    return out


def win_counts(
    results: Sequence[GameResult], sources: Sequence[str]
) -> tuple[dict[str, int], int]:
    """Per-Game wins, plus the number of Games where every track scored the same.

    A Game where all four tracks land on exactly the same net -- Game 22, where every track
    overcharged past `t` and every reviewer rejected, so nobody earned and nobody paid -- is a
    win for nobody. Counting it four times is how a tie gets dressed up as evidence.
    """
    counts = {s: 0 for s in sources}
    degenerate = 0
    for r in results:
        available = {s: r.scored[s].net for s in sources if s in r.scored}
        if not available:
            continue
        best, worst = max(available.values()), min(available.values())
        if abs(best - worst) < 0.005:
            degenerate += 1
            continue
        for s, net in available.items():
            if abs(net - best) < 0.005:
                counts[s] += 1
    return counts, degenerate


def draw_spread(results: Sequence[GameResult], sources: Sequence[str]) -> dict[str, dict[str, float]]:
    """Between-draw spread of the same track on the same Case, in euros."""
    out: dict[str, dict[str, float]] = {}
    for s in sources:
        gaps = [
            max(nets) - min(nets)
            for r in results
            if len(nets := r.draw_nets.get(s) or []) > 1
        ]
        if not gaps:
            continue
        out[s] = {
            "games_with_two_draws": float(len(gaps)),
            "mean_gap": statistics.fmean(gaps),
            "max_gap": max(gaps),
            "sum_gap": sum(gaps),
        }
    return out


def item_attribution(
    results: Sequence[GameResult], left: str, right: str, draws: int = 1
) -> list[dict[str, Any]]:
    """Per Line Item and per draw: how much `left` beat `right` by, and what the item was.

    Conditioned on our own submitted numbers and on the invoice, never on the Fair Value: the
    same items read 4x over-priced conditioned on `t` and 46% under-priced conditioned on
    `t_hat`, and only the second is knowable before the Game settles. `charge_bucket` therefore
    buckets on the larger of the two *submitted* Charges, and `labour` on the Line Item name.

    Every draw contributes its own row, so a delta that only exists in one draw is visible as
    such instead of being averaged into a fact.
    """
    rows: list[dict[str, Any]] = []
    for r in results:
        for k in range(draws):
            a, b = r.by_draw.get(k, {}).get(left), r.by_draw.get(k, {}).get(right)
            if a is None or b is None:
                continue
            left_net, right_net = a.per_item_net, b.per_item_net
            for index in r.snap.line_items:
                la = _pair(r, left, index, k)
                lb = _pair(r, right, index, k)
                rows.append(
                    {
                        "game": r.game_id,
                        "draw": k,
                        "index": index,
                        "name": r.item_names.get(index, "?"),
                        "quantity_missing": bool(
                            r.item_facts.get(index, {}).get("quantity_missing", False)
                        ),
                        f"{left}_charge": la[0],
                        f"{left}_limit": la[1],
                        f"{right}_charge": lb[0],
                        f"{right}_limit": lb[1],
                        f"{left}_net": left_net.get(index, 0.0),
                        f"{right}_net": right_net.get(index, 0.0),
                        "delta": left_net.get(index, 0.0) - right_net.get(index, 0.0),
                        "charge_bucket": _bucket(max(la[0], lb[0])),
                        "labour": _is_labour(r.item_names.get(index, "")),
                    }
                )
    rows.sort(key=lambda row: -abs(row["delta"]))
    return rows


def _pair(result: GameResult, source: str, index: int, draw: int) -> tuple[float, float]:
    """The `(a, b)` a source submitted for one Line Item on one draw, `(0, 0)` when absent."""
    cached = load_draw(result.game_id, source, draw)
    if cached is not None and index in cached.prices:
        return cached.prices[index]
    return result.submissions.get(source, {}).get(index, (0.0, 0.0))


def aggregate_items(
    rows: Sequence[Mapping[str, Any]], left: str, right: str
) -> list[dict[str, Any]]:
    """Collapse the per-draw rows to one row per (Game, Line Item), delta averaged over draws."""
    groups: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault((int(row["game"]), int(row["index"])), []).append(row)
    out = []
    for (game, index), members in groups.items():
        deltas = [float(m["delta"]) for m in members]
        out.append(
            {
                "game": game,
                "index": index,
                "name": members[0]["name"],
                "draws": len(members),
                "delta_mean": statistics.fmean(deltas),
                "delta_spread": max(deltas) - min(deltas),
                f"{left}_charge": statistics.fmean(float(m[f"{left}_charge"]) for m in members),
                f"{left}_limit": statistics.fmean(float(m[f"{left}_limit"]) for m in members),
                f"{right}_charge": statistics.fmean(float(m[f"{right}_charge"]) for m in members),
                f"{right}_limit": statistics.fmean(float(m[f"{right}_limit"]) for m in members),
            }
        )
    out.sort(key=lambda row: -abs(row["delta_mean"]))
    return out


def _bucket(charge: float) -> str:
    if charge < 100:
        return "a <100"
    if charge < 500:
        return "b 100-500"
    if charge < 2000:
        return "c 500-2k"
    return "d >2k"


_LABOUR_WORDS = (
    "labour", "labor", "hour", "work", "service", "installation", "install", "fitting",
    "repair", "assembly", "technician", "wage", "arbeit", "stunde", "montage",
)


def _is_labour(name: str) -> bool:
    low = name.lower()
    return any(word in low for word in _LABOUR_WORDS)


def group_attribution(rows: Sequence[Mapping[str, Any]], key: str) -> list[tuple[Any, int, float]]:
    groups: dict[Any, list[float]] = {}
    for row in rows:
        groups.setdefault(row[key], []).append(float(row["delta"]))
    return sorted(
        ((k, len(v), sum(v)) for k, v in groups.items()), key=lambda kv: -abs(kv[2])
    )


# ------------------------------------------------------------------------------------ cli


def _parse_games(spec: str) -> list[int]:
    if spec in {"all", "latest"}:
        from pull_transactions import completed_games

        return [g for g in completed_games() if g >= 20]
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if part.endswith("-"):  # "20-" means 20 to the latest settled Game
            from pull_transactions import completed_games

            start = int(part[:-1])
            out += [g for g in completed_games() if g >= start]
            continue
        start, _, end = part.partition("-")
        out += list(range(int(start), int(end or start) + 1))
    return sorted(set(out))


async def amain() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--games", default="20-", help="'20-28', '20-' (to latest), 'all'")
    parser.add_argument("--strategies", default=",".join(SOURCES))
    parser.add_argument("--draws", type=int, default=1, help="model draws per track per Game")
    parser.add_argument("--offline", action="store_true", help="cache only; make no model call")
    parser.add_argument("--report-only", action="store_true", help="alias for --offline")
    parser.add_argument("--refresh", action="store_true", help="ignore the cache and re-request")
    parser.add_argument(
        "--limit-rule",
        default="mid",
        choices=("mid", "lo", "hi"),
        help="representative point inside each opponent's reconstructed Limit bracket",
    )
    parser.add_argument("--out", default=str(CACHE / "report.json"))
    args = parser.parse_args()

    _redirect_decision_log()
    offline = args.offline or args.report_only
    games = _parse_games(args.games)
    sources = [s.strip() for s in args.strategies.split(",") if s.strip()]

    print(f"Bake-off over Games {games}, tracks {sources}, {args.draws} draw(s), offline={offline}")
    results: list[GameResult] = []
    for game_id in games:
        print(f"G{game_id} ...", flush=True)
        got = await run_game(
            game_id,
            sources,
            args.draws,
            offline=offline,
            refresh=args.refresh,
            limit_rule=args.limit_rule,
        )
        if got is not None:
            results.append(got)
            line = "  ".join(
                f"{s}={got.scored[s].net:,.0f}" for s in sources if s in got.scored
            )
            print(f"  {line}")
    if not results:
        print("No Game produced a result.")
        return

    labels = list(sources) + ["merged", "actual"]
    labels += [name for name, _, _ in HYBRIDS]
    labels += ["oracle_bracket", "oracle_exact"]
    n = len(results)
    floor = noise_floor(n)

    print("\n## Per-Game replayed net (EUR)\n")
    print(per_game_table(results, labels))
    print("\n## Wall clock per draw (s)\n")
    print(runtime_table(results, sources))

    by_draw = pooled_by_draw(results, labels, args.draws)
    print("\n## Pooled totals, one column per draw\n")
    header = " | ".join(f"draw {k}" for k in range(args.draws))
    print(f"| variant | {header} | mean of draws | mean per Game | draw spread |")
    print("|---" * (args.draws + 4) + "|")
    pooled: dict[str, float] = {}
    for label in labels:
        row = [v for v, _ in by_draw.get(label, [])]
        if not row:
            continue
        pooled[label] = statistics.fmean(row)
        cells = " | ".join(
            f"{v:,.0f}" + ("" if count == n else f" ({count}/{n} G)")
            for v, count in by_draw.get(label, [])
        )
        print(
            f"| {label} | {cells} | **{statistics.fmean(row):,.0f}** | "
            f"{statistics.fmean(row) / n:,.0f} | {max(row) - min(row):,.0f} |"
        )

    print(
        f"\nGames pooled: {n}. Noise floor 26,622*sqrt({n}/18) = **{floor:,.0f} EUR**. "
        f"Opponent Limit rule: {args.limit_rule}."
    )
    counts, degenerate = win_counts(results, sources)
    print(f"Per-Game wins (draw 0): {counts}; Games where every track tied: {degenerate}")

    ranked = sorted(((v, k) for k, v in pooled.items() if k in sources), reverse=True)
    for first, second in zip(ranked, ranked[1:]):
        gap = first[0] - second[0]
        own = max(
            (max(v) - min(v)) if (v := [x for x, _ in by_draw.get(name, [])]) else 0.0
            for name in (first[1], second[1])
        )
        verdict = "clears" if gap > floor else "does NOT clear"
        print(
            f"  {first[1]} {first[0]:,.0f} vs {second[1]} {second[0]:,.0f}: gap {gap:,.0f} "
            f"{verdict} the {floor:,.0f} floor; larger of the two own draw spreads {own:,.0f}"
        )

    spreads = draw_spread(results, labels)
    if spreads:
        print("\n## Between-draw spread per Game (same track, same Case)\n")
        for s, stats in spreads.items():
            print(
                f"  {s:>15}: n={stats['games_with_two_draws']:.0f} mean {stats['mean_gap']:>10,.0f} "
                f"max {stats['max_gap']:>10,.0f} summed {stats['sum_gap']:>11,.0f}"
            )

    attribution: dict[str, Any] = {}
    for left, right in (("strategy1", "strategy2"), ("strategy3", "strategy2")):
        if left not in sources or right not in sources:
            continue
        rows = item_attribution(results, left, right, args.draws)
        attribution[f"{left}_vs_{right}"] = rows
        merged_rows = aggregate_items(rows, left, right)
        print(f"\n## Where {left} - {right} comes from, per Line Item\n")
        print(
            f"| game | item | name | {left} (a/b) | {right} (a/b) | mean delta EUR | "
            "delta spread over draws |"
        )
        print("|---|---|---|---|---|---|---|")
        for row in merged_rows[:20]:
            print(
                f"| {row['game']} | {row['index']} | {row['name'][:44]} | "
                f"{row[f'{left}_charge']:,.0f}/{row[f'{left}_limit']:,.0f} | "
                f"{row[f'{right}_charge']:,.0f}/{row[f'{right}_limit']:,.0f} | "
                f"{row['delta_mean']:,.0f} | {row['delta_spread']:,.0f} |"
            )
        for key in ("charge_bucket", "labour", "quantity_missing"):
            print(f"\n  grouped by {key} (conditioned on our own Charge and the invoice, never on t):")
            for value, count, total in group_attribution(rows, key):
                print(
                    f"    {value!s:>12}  item-draws {count:>4}  delta/draw {total / args.draws:>14,.0f}"
                )

    payload = {
        "games": [r.game_id for r in results],
        "sources": sources,
        "draws": args.draws,
        "limit_rule": args.limit_rule,
        "noise_floor": floor,
        "pooled_mean_of_draws": pooled,
        "pooled_by_draw": by_draw,
        "win_counts": counts,
        "degenerate_games": degenerate,
        "draw_spread": spreads,
        "per_game": [
            {
                "game": r.game_id,
                "published_net": r.snap.published_net,
                "nets": {k: v.net for k, v in r.scored.items()},
                "income_cost": {k: [v.income, v.cost] for k, v in r.scored.items()},
                "answered": {k: v.answered for k, v in r.scored.items()},
                "covered_items": {k: v.covered_items for k, v in r.scored.items()},
                "runtimes": r.draw_times,
                "draw_nets": r.draw_nets,
                "nets_by_draw": {
                    str(k): {label: s.net for label, s in scored.items()}
                    for k, scored in r.by_draw.items()
                },
                "income_cost_by_draw": {
                    str(k): {label: [s.income, s.cost] for label, s in scored.items()}
                    for k, scored in r.by_draw.items()
                },
                "line_items": list(r.snap.line_items),
                "item_names": r.item_names,
                "item_facts": r.item_facts,
                "fair_brackets": {
                    str(i): list(r.snap.fair_brackets[i]) for i in r.snap.line_items
                },
                "submissions": {
                    k: {str(i): list(p) for i, p in v.items()} for k, v in r.submissions.items()
                },
                "per_item_net": {
                    k: {str(i): net for i, net in v.per_item_net.items()}
                    for k, v in r.scored.items()
                },
            }
            for r in results
        ],
        "attribution": attribution,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, default=str))
    print(f"\nWrote {out}")


def main() -> None:  # pragma: no cover - CLI
    asyncio.run(amain())


if __name__ == "__main__":  # pragma: no cover - CLI
    main()
