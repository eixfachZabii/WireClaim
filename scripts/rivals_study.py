"""The rivals study CLAUDE.md's review process asked for: reconstruct eyay, error404 ai,
TakeTheMoneyAndRun and our own (Charge, Limit) placement per Line Item from the public
leaderboard, decompose net into the four buckets that separate the Issuer side from the
Reviewer side, and replay the counterfactual "eyay's a/t and b/t ratios, our own t-hat" over
Games 19-32 -- the window in which we already out-earned eyay per Game.

Why this is a new script and not an edit to `rivals.py`
---------------------------------------------------------
`rivals.py` has an uncommitted, mid-edit `measure()`: a `game_acc = [0, 0, 0, 0]` list was
introduced but the four lines below it still reference bare `seen`/`acc`, which were never
assigned in this version of the function.

    >>> measure(load_book(30, teams), "eyay", Stat(team="eyay"))
    UnboundLocalError: local variable 'seen' referenced before assignment

That takes out `--income`, `--review`, `--anchor`, `--fountain` and `--breaks` -- everything
that calls `measure_all()`. It is somebody else's work in progress; this script does not
touch it. It reuses only the parts of `rivals.py` that are *not* broken -- `load_book`
(the Book reconstruction, Cap-aware), `cap_of`, `noise_floor` -- and the parts of
`replay_payoffs.py` that were never touched -- `snapshot`, `our_actual_submission`. No new
inversion logic is added; every number here is arithmetic over `Book`/`GameSnapshot`
objects those two files already build correctly.

What is measured
-----------------
1. `a/t` and `b/t` distributions per team (median, p25, p75), over items with a bounded
   Fair Value denominator, split by how trustworthy the recovered Charge is (a `capped` or
   `censored` Charge is excluded from the ratio -- it is a lower bound or unknown, not a
   value).
2. The four-bucket net decomposition: income from fair Charges, income from accepted
   Overcharges, cost from everything we (or they) accepted as Reviewer, and the 1.5x
   wrongful-rejection penalty. These four sum to `identity_net` exactly by construction
   (see `_verify_reconciliation`), which is the check that the bucket definitions are not
   just plausible but *complete*.
3. Behaviour on `t_lo = 0` items (the best available proxy for "uncovered": nobody has ever
   been proven owed money on it -- not proof of `t = 0`, since it is also consistent with
   nobody's Charge ever landing at or below a low but positive `t`; flagged as such
   everywhere it is used).
4. The counterfactual: replace our Charge and/or Limit with `eyay's measured a/t and b/t
   ratio (over the same window) times OUR OWN reconstructed t-hat`, then replay Cap-aware
   over Games 19-32 and compare to our actual net over the same window. `t-hat` here is the
   bracket midpoint from `invert_fair_values.brackets` -- the same quantity used as "the
   true Fair Value" throughout this file. Using it as "our estimate" is optimistic: it
   assumes our real-time estimator is as good as retrospective reconstruction, so it
   isolates the *placement rule* (the ratio) from *estimation error*. The isolation, not the
   absolute number, is the finding.

Everything is labelled against the noise floor: 26,622 over 18 Games, scaled sqrt(n/18)
(CLAUDE.md, `rivals.py`).

Usage
-----
    PYTHONPATH=. python scripts/rivals_study.py --decompose --games 1-32
    PYTHONPATH=. python scripts/rivals_study.py --decompose --games 19-32
    PYTHONPATH=. python scripts/rivals_study.py --counterfactual --games 19-32
    PYTHONPATH=. python scripts/rivals_study.py --all
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rivals import Book, cap_of, load_book, noise_floor  # noqa: E402
from pull_transactions import completed_games, identity_net, teams  # noqa: E402
from replay_payoffs import (  # noqa: E402
    UnreconstructableGame,
    our_actual_submission,
    snapshot,
)

INF = math.inf
US = "Bin busy"

FOCUS_TEAMS = ("eyay", "error404 ai", "TakeTheMoneyAndRun", US)

#: Charges/limits recovered with this status are real values; `capped` is a lower bound and
#: `censored` is unknown (`a = inf`), so both are excluded from ratio statistics.
TRUSTED_STATES = ("exact", "exact-acc", "zero", "uncapped?")


def parse_games(spec: str) -> list[int]:
    done = set(completed_games())
    out: list[int] = []
    for chunk in spec.split(","):
        start, _, end = chunk.partition("-")
        out += list(range(int(start), int(end or start) + 1))
    return [g for g in sorted(set(out)) if g in done]


def q(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(int(p * len(ordered)), len(ordered) - 1)]


def pct(num: float, den: float) -> str:
    return "   n/a" if not den else f"{100.0 * num / den:5.1f}%"


def money(value: float) -> str:
    return f"{value:12,.0f}"


# ------------------------------------------------------------------------- decomposition


@dataclass
class TeamMetrics:
    team: str
    games: int = 0
    n_items: int = 0
    n_trusted: int = 0
    n_capped: int = 0
    n_censored: int = 0
    a_over_t: list[float] = dc_field(default_factory=list)
    b_over_t: list[float] = dc_field(default_factory=list)

    income_fair: float = 0.0
    income_over: float = 0.0
    cost_accept: float = 0.0
    penalty: float = 0.0

    # t_lo == 0 items ("plausibly uncovered")
    t0_items: int = 0
    t0_charged: int = 0  # a > 0 and recoverable
    t0_charge_income: float = 0.0  # money actually collected on them (always "over" bucket)

    net_identity: float = 0.0  # from identity_net, per-row -- the ground truth to check against

    @property
    def net_buckets(self) -> float:
        return self.income_fair + self.income_over - self.cost_accept - self.penalty


def measure_team(books: list[Book], team: str) -> TeamMetrics:
    m = TeamMetrics(team=team)
    for book in books:
        if team not in book.team_names:
            continue
        m.games += 1
        for index in book.items:
            a = book.charge[index][team]
            state = book.status[index][team]
            t = book.t(index)
            m.n_items += 1
            if state == "censored":
                m.n_censored += 1
            elif state == "capped":
                m.n_capped += 1
            elif t > 0:
                m.n_trusted += 1
                m.a_over_t.append(a / t)

            lo, _hi = book.fair[index]
            if lo == 0.0:
                m.t0_items += 1
                if a != INF and a > 0:
                    m.t0_charged += 1

            if t > 0:
                m.b_over_t.append(book.b(index, team) / t)

        for row in book.rows[team]:
            index = row["line_item_index"]
            t = book.t(index)
            if row["issuer"] == team and row["amount"] > 0:
                if row["amount"] <= t:
                    m.income_fair += row["amount"]
                else:
                    m.income_over += row["amount"]
                    lo, _hi = book.fair[index]
                    if lo == 0.0:
                        m.t0_charge_income += row["amount"]
            if row["reviewer"] == team:
                if row["accepted"]:
                    m.cost_accept += row["amount"]
                else:
                    m.penalty += 1.5 * row["amount"]
        m.net_identity += identity_net(book.rows[team], team)
    return m


def _verify_reconciliation(metrics: dict[str, TeamMetrics]) -> list[str]:
    """The four buckets must sum to `identity_net` exactly. If they do not, a bucket
    definition double-counts or drops rows and nothing downstream can be trusted."""
    bad = []
    for team, m in metrics.items():
        if abs(m.net_buckets - m.net_identity) > 0.01:
            bad.append(
                f"{team}: buckets sum to {m.net_buckets:,.2f}, identity says "
                f"{m.net_identity:,.2f} (off by {m.net_buckets - m.net_identity:,.2f})"
            )
    return bad


def print_ratio_table(metrics: dict[str, TeamMetrics], title: str) -> None:
    print(f"\n=== {title}: Charge and Limit placement relative to Fair Value ===")
    print(
        f"{'team':22s} {'items':>6s} {'trusted':>8s} {'capped':>7s} {'censor':>7s} "
        f"{'a/t p25':>8s} {'a/t med':>8s} {'a/t p75':>8s} "
        f"{'b/t p25':>8s} {'b/t med':>8s} {'b/t p75':>8s}"
    )
    for team, m in metrics.items():
        print(
            f"{team:22s} {m.n_items:6d} {m.n_trusted:8d} {m.n_capped:7d} {m.n_censored:7d} "
            f"{q(m.a_over_t, .25):8.2f} {q(m.a_over_t, .50):8.2f} {q(m.a_over_t, .75):8.2f} "
            f"{q(m.b_over_t, .25):8.2f} {q(m.b_over_t, .50):8.2f} {q(m.b_over_t, .75):8.2f}"
        )
    print("  `a/t`, `b/t` over items with t > 0 and a recoverable (non-capped, non-censored)")
    print("  Charge; `b/t` uses the bracket midpoint, or the lower bound `b_lo` when the")
    print("  team never rightfully rejected anything on that item (Limit could be higher).")


def print_bucket_table(metrics: dict[str, TeamMetrics], title: str) -> None:
    print(f"\n=== {title}: the four-bucket net decomposition ===")
    print(
        f"{'team':22s} {'net':>12s} | {'(i) inc fair':>13s} {'(ii) inc over':>13s} "
        f"{'(iii) cost acc':>14s} {'(iv) penalty':>13s}"
    )
    for team, m in metrics.items():
        print(
            f"{team:22s} {money(m.net_identity)} | {money(m.income_fair):>13s} "
            f"{money(m.income_over):>13s} {money(m.cost_accept):>14s} {money(m.penalty):>13s}"
        )
    print("  (i)+(ii) = income as Issuer.  (iii)+(iv) = cost as Reviewer.  net = (i)+(ii)-(iii)-(iv).")
    print("  (i) is owed by every opponent regardless of their Limit -- structural.")
    print("  (ii) needs a generous opponent's Limit -- it is not ours to keep if the field tightens.")
    print("  (iii) is every euro paid out on an accepted claim, fair or not -- the Reviewer's spend.")
    print("  (iv) is the self-inflicted 1.5x paid on Charges we (or they) wrongfully rejected.")


def print_t0_table(metrics: dict[str, TeamMetrics], title: str) -> None:
    print(f"\n=== {title}: behaviour on t_lo = 0 items (plausibly uncovered) ===")
    print(
        f"{'team':22s} {'t0 items':>9s} {'charged>0':>10s} {'charge%':>8s} "
        f"{'income collected':>17s}"
    )
    for team, m in metrics.items():
        print(
            f"{team:22s} {m.t0_items:9d} {m.t0_charged:10d} {pct(m.t0_charged, m.t0_items):>8s} "
            f"{money(m.t0_charge_income):>17s}"
        )
    print("  `t_lo = 0` means no team's Charge on this item was ever wrongfully rejected -- it")
    print("  is consistent with an uncovered item (t = 0) but not proof; treat as a lower bound.")
    print("  `income collected` is always in bucket (ii): any positive Charge here is > t_lo by")
    print("  construction, so if it was ever accepted it counts as an Overcharge, per R6c.")


# ------------------------------------------------------------------------ counterfactual


@dataclass
class CFResult:
    label: str
    per_game: dict[int, float]

    @property
    def total(self) -> float:
        return sum(self.per_game.values())

    @property
    def games(self) -> int:
        return len(self.per_game)


def replay_capped(snap, submission: dict[int, tuple[float, float]]) -> float:
    """Our net had we submitted `submission`, Cap enforced (`c = max(4t, 2000)`, floored by
    what was actually observed paid on the item). Identical model to `rivals.replay_capped`;
    reimplemented here so this script has no dependency on the broken half of `rivals.py`."""
    income = 0.0
    cost = 0.0
    for index in snap.line_items:
        charge, limit = submission.get(index, (0.0, 0.0))
        t = snap.fair_point(index)
        observed = max((a for a in snap.charges[index].values() if a != INF), default=0.0)
        c = max(cap_of(t), observed)
        for team in snap.opponents:
            b = snap.limit_point(index, team, "mid")
            if charge <= b:
                income += min(charge, c)
            elif charge <= t:
                income += charge
            their_a = snap.charges[index][team]
            if their_a <= limit:
                cost += min(their_a, c)
            elif their_a <= t:
                cost += 1.5 * their_a
    return income - cost


def measure_eyay_ratios(books: list[Book], donor: str) -> tuple[float, float, int]:
    """Median a/t and b/t for `donor` over exactly this set of Games -- never carried over
    from a different window (CLAUDE.md: a field measurement does not survive unchanged)."""
    a_over_t: list[float] = []
    b_over_t: list[float] = []
    n = 0
    for book in books:
        if donor not in book.team_names:
            continue
        for index in book.items:
            t = book.t(index)
            if t <= 0:
                continue
            a = book.charge[index][donor]
            state = book.status[index][donor]
            if state in TRUSTED_STATES:
                a_over_t.append(a / t)
                n += 1
            b_over_t.append(book.b(index, donor) / t)
    return q(a_over_t, 0.5), q(b_over_t, 0.5), n


def counterfactual_study(game_ids: list[int], donor: str, k_a: float, k_b: float) -> list[CFResult]:
    labels = {
        "us (actual)": None,
        f"{donor} ratios: a+b (a={k_a:.2f}t, b={k_b:.2f}t)": "a+b",
        f"{donor} ratio a only (a={k_a:.2f}t, our b)": "a",
        f"{donor} ratio b only (our a, b={k_b:.2f}t)": "b",
    }
    per_game: dict[str, dict[int, float]] = {label: {} for label in labels}
    skipped: list[int] = []
    for gid in game_ids:
        try:
            snap = snapshot(gid, US)
        except UnreconstructableGame as exc:
            skipped.append(gid)
            print(f"  skipping G{gid}: {exc}")
            continue
        ours = our_actual_submission(snap)
        for label, mode in labels.items():
            if mode is None:
                submission = ours
            else:
                submission = {}
                for index in snap.line_items:
                    t_hat = snap.fair_point(index)
                    our_a, our_b = ours[index]
                    a = k_a * t_hat if mode in ("a+b", "a") else our_a
                    b = k_b * t_hat if mode in ("a+b", "b") else our_b
                    submission[index] = (a, b)
            per_game[label][gid] = replay_capped(snap, submission)
    return [CFResult(label, per_game[label]) for label in labels]


def multiplier_sweep(
    game_ids: list[int], *, betas: list[float], alpha: float | None = None
) -> list[CFResult]:
    """Flat `a = beta * t_true` (oracle t as the "our own t-hat" stand-in), Limit held at our
    own actual `b` unless `alpha` is given (`b = alpha * t_true` instead). Isolates the *level*
    of the Charge multiplier from any particular donor's per-item shape -- the question the
    three-donor counterfactual raises but cannot answer on its own: is a ratio below 1.0 what
    matters (R5b, structural income preserved), or is it specifically eyay/TakeTheMoneyAndRun's
    per-item judgement?
    """
    per_game: dict[float, dict[int, float]] = {b: {} for b in betas}
    for gid in game_ids:
        try:
            snap = snapshot(gid, US)
        except UnreconstructableGame as exc:
            print(f"  skipping G{gid}: {exc}")
            continue
        ours = our_actual_submission(snap)
        for beta in betas:
            submission = {}
            for index in snap.line_items:
                t_hat = snap.fair_point(index)
                our_a, our_b = ours[index]
                b = (alpha * t_hat) if alpha is not None else our_b
                submission[index] = (beta * t_hat, b)
            per_game[beta][gid] = replay_capped(snap, submission)
    limit_desc = "our actual b" if alpha is None else f"b = {alpha:.2f}t"
    return [CFResult(f"a = {beta:.2f}t, {limit_desc}", per_game[beta]) for beta in betas]


def print_counterfactual(results: list[CFResult], donor: str, *, per_game: bool = False) -> None:
    base = next(r for r in results if r.label == "us (actual)")
    floor = noise_floor(base.games)
    print(f"\n=== counterfactual: adopt {donor}'s (a/t, b/t) with our own t-hat, "
          f"over {base.games} Games ===")
    print(f"{'submission':50s} {'total':>13s} {'delta vs us':>13s} {'per Game':>10s}  verdict")
    for r in sorted(results, key=lambda r: -r.total):
        delta = r.total - base.total
        if r.label == "us (actual)":
            verdict = "baseline"
        elif abs(delta) < floor:
            verdict = f"inside noise (+-{floor:,.0f})"
        else:
            verdict = "GAIN" if delta > 0 else "LOSS"
        print(
            f"{r.label:50s} {r.total:13,.0f} {delta:13,.0f} "
            f"{delta / max(r.games, 1):10,.0f}  {verdict}"
        )
    print(f"  noise floor = 26,622 * sqrt({base.games}/18) = {floor:,.0f} euros over the window.")
    if per_game:
        gids = sorted(base.per_game)
        print("\n  per-Game net:")
        print("    " + f"{'submission':50s}" + "".join(f"{g:>10d}" for g in gids))
        for r in sorted(results, key=lambda r: -r.total):
            print("    " + f"{r.label:50s}" + "".join(f"{r.per_game.get(g, float('nan')):10,.0f}" for g in gids))


# --------------------------------------------------------------------------------- cli


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teams", default=",".join(FOCUS_TEAMS))
    parser.add_argument("--games", default="all")
    parser.add_argument("--decompose", action="store_true")
    parser.add_argument("--counterfactual", action="store_true")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--calibration", action="store_true")
    parser.add_argument("--donor", default="eyay")
    parser.add_argument("--per-game", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all:
        args.decompose = args.counterfactual = args.sweep = args.calibration = True

    all_teams = teams()
    wanted = [t.strip() for t in args.teams.split(",") if t.strip()]
    game_ids = parse_games(args.games) if args.games != "all" else completed_games()

    if args.decompose:
        print(f"loading {len(game_ids)} Games x {len(all_teams)} teams ...", file=sys.stderr)
        books = [load_book(g, all_teams) for g in game_ids]
        metrics = {t: measure_team(books, t) for t in wanted}
        title = f"G{args.games}"
        bad = _verify_reconciliation(metrics)
        if bad:
            print("\nRECONCILIATION FAILURE (do not trust the tables below):")
            for line in bad:
                print(f"  {line}")
        else:
            print(f"\nreconciliation OK: buckets sum to identity_net to the cent for all {len(wanted)} teams")
        print_ratio_table(metrics, title)
        print_bucket_table(metrics, title)
        print_t0_table(metrics, title)

    if args.counterfactual:
        print(f"\nloading books for {args.donor} ratio measurement over G{args.games} ...", file=sys.stderr)
        books = [load_book(g, all_teams) for g in game_ids]
        k_a, k_b, n = measure_eyay_ratios(books, args.donor)
        print(f"\n{args.donor}'s median a/t = {k_a:.3f}, median b/t = {k_b:.3f}, "
              f"measured on {n} trusted Charges over G{args.games}")
        results = counterfactual_study(game_ids, args.donor, k_a, k_b)
        print_counterfactual(results, args.donor, per_game=args.per_game)

    if args.sweep:
        betas = [0.4, 0.5, 0.6, 0.7, 0.8, 0.86, 0.9, 1.0, 1.04, 1.1, 1.2]
        print(f"\n=== flat Charge-multiplier sweep, our own b, over G{args.games} "
              f"(t = oracle/true, i.e. \"our own t-hat\" under perfect estimation) ===")
        results = multiplier_sweep(game_ids, betas=betas)
        print(f"{'submission':30s} {'total':>13s} {'per Game':>10s}")
        for r in sorted(results, key=lambda r: -r.total):
            print(f"{r.label:30s} {r.total:13,.0f} {r.total / max(r.games, 1):10,.0f}")

    if args.calibration:
        ks = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5]
        results, matched, total = limit_multiplier_sweep_matched(game_ids, ks)
        print(f"\nmatched items (t-hat recoverable): {matched}/{total}"
              + (f" ({100.0 * matched / total:.1f}%)" if total else ""))
        print_limit_sweep_matched(results, f"G{args.games}", len(game_ids))
        t_hat_bias_by_magnitude(game_ids)
        extra_accepts_breakdown(game_ids, k_loose=1.0, k_tight=0.3)




# ------------------------------------------------------------------- t-hat calibration
#
# Added to answer a direct challenge: the Limit sweep in §7 of the write-up used the
# reconstructed TRUE `t` as the multiplier's base ("oracle"), which is not actionable --
# it measures the value of already knowing `t`, not the value of loosening a multiplier
# on our own estimate. This section redoes it on `t-hat` as it was *actually available at
# decision time*: `price_median` from `var/decisions/game_NNN.json` where a decision log
# exists (Games 26+), and `combine(model, memory)` fed the cached evidence in
# `var/evidence/case_NN_{model,memory}.json` otherwise (Games without a log). No new
# inversion logic -- `combine` is imported unmodified from `blend.py`.
#
# Caveat carried into every table this section prints: `var/evidence/*_memory.json` is
# unconditionally overwritten every time `dump_evidence.py` runs (see its source), and the
# file mtimes show at least one case (case_29, evidence at 21:08 vs. its decision log at
# 20:53 -- AFTER the decision) where the cache was refreshed later than the live decision.
# So the memory-channel evidence for Games without a log may reflect a Price Memory state
# richer than what genuinely existed when that Game was decided. This can only make the
# reconstructed t-hat look BETTER than it really was (more settled Games behind the memory
# anchor), never worse -- so it is a bias against finding "our estimate is the problem",
# not for it.

from src.pricing import Evidence as _Evidence  # noqa: E402
from src.services.strategies.strategy2.blend import combine as _combine  # noqa: E402

EVIDENCE_DIR = Path("var/evidence")
DECISIONS_DIR = Path("var/decisions")


def _load_evidence_tag(game_id: int, tag: str) -> dict[int, _Evidence]:
    path = EVIDENCE_DIR / f"case_{game_id:02d}_{tag}.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {int(k): _Evidence(index=int(k), **v) for k, v in raw.items()}


def reconstruct_t_hat(game_id: int) -> dict[int, float]:
    """`{line_item_index: t-hat}` as it was actually available at decision time.

    Ground truth where a decision log exists (`price_median`, logged at submission time,
    no reconstruction at all). Reconstructed via `combine(model, memory)` on the cached
    evidence otherwise. Returns `{}` if neither source exists for this Game.
    """
    log_path = DECISIONS_DIR / f"game_{game_id:03d}.json"
    if log_path.exists():
        blob = json.loads(log_path.read_text())
        return {
            int(item["index"]): float(item["price_median"])
            for item in blob["items"]
            if item.get("price_median") is not None
        }
    model_ev = _load_evidence_tag(game_id, "model")
    memory_ev = _load_evidence_tag(game_id, "memory")
    if not model_ev and not memory_ev:
        return {}
    out: dict[int, float] = {}
    for idx in set(model_ev) | set(memory_ev):
        combined = _combine(model_ev.get(idx), memory_ev.get(idx))
        if combined is not None and combined.price_median > 0:
            out[idx] = combined.price_median
    return out


@dataclass
class LimitSweepResult:
    k: float
    that_total: float
    that_per_game: dict[int, float]
    true_total: float
    true_per_game: dict[int, float]


def limit_multiplier_sweep_matched(
    game_ids: list[int], ks: list[float]
) -> tuple[list[LimitSweepResult], int, int]:
    """`b = k * t-hat` vs `b = k * t_true`, on the SAME matched item set in both columns.

    An item is in the matched set only if `reconstruct_t_hat` produced a value for it; for
    every other item (t-hat unrecoverable) both columns fall back to our own actual `b`, so
    the two columns differ only on items where the comparison is meaningful and the gap
    between them isolates the value of the estimate, not of item coverage.
    """
    that_per_game: dict[float, dict[int, float]] = {k: {} for k in ks}
    true_per_game: dict[float, dict[int, float]] = {k: {} for k in ks}
    matched_items = 0
    total_items = 0
    for gid in game_ids:
        try:
            snap = snapshot(gid, US)
        except UnreconstructableGame as exc:
            print(f"  skipping G{gid}: {exc}")
            continue
        ours = our_actual_submission(snap)
        t_hats = reconstruct_t_hat(gid)
        matched = {i for i in snap.line_items if i in t_hats}
        matched_items += len(matched)
        total_items += len(snap.line_items)
        for k in ks:
            sub_hat: dict[int, tuple[float, float]] = {}
            sub_true: dict[int, tuple[float, float]] = {}
            for idx in snap.line_items:
                our_a, our_b = ours[idx]
                if idx in matched:
                    sub_hat[idx] = (our_a, k * t_hats[idx])
                    sub_true[idx] = (our_a, k * snap.fair_point(idx))
                else:
                    sub_hat[idx] = (our_a, our_b)
                    sub_true[idx] = (our_a, our_b)
            that_per_game[k][gid] = replay_capped(snap, sub_hat)
            true_per_game[k][gid] = replay_capped(snap, sub_true)
    results = [
        LimitSweepResult(
            k=k,
            that_total=sum(that_per_game[k].values()),
            that_per_game=that_per_game[k],
            true_total=sum(true_per_game[k].values()),
            true_per_game=true_per_game[k],
        )
        for k in ks
    ]
    return results, matched_items, total_items


def print_limit_sweep_matched(results: list[LimitSweepResult], title: str, n_games: int) -> None:
    floor = noise_floor(n_games)
    print(f"\n=== {title}: b = k*that (actionable) vs b = k*t_true (oracle), matched items ===")
    print(f"{'k':>6s} {'b=k*that':>13s} {'per game':>10s} | {'b=k*t_true':>13s} {'per game':>10s} | {'gap (value of a better estimate)':>16s}")
    for r in results:
        gap = r.true_total - r.that_total
        print(
            f"{r.k:6.2f} {r.that_total:13,.0f} {r.that_total/max(n_games,1):10,.0f} | "
            f"{r.true_total:13,.0f} {r.true_total/max(n_games,1):10,.0f} | {gap:16,.0f}"
        )
    print(f"  noise floor over {n_games} Games: +-{floor:,.0f}")


def t_hat_bias_by_magnitude(game_ids: list[int]) -> None:
    """Median t-hat/t_true, split by the magnitude of the TRUE t -- to test directly
    whether the underestimate concentrates in the expensive tercile."""
    buckets: dict[str, list[float]] = {"t<100": [], "100<=t<500": [], "t>=500": []}
    n_missing = 0
    n_total = 0
    for gid in game_ids:
        try:
            snap = snapshot(gid, US)
        except UnreconstructableGame:
            continue
        t_hats = reconstruct_t_hat(gid)
        for idx in snap.line_items:
            n_total += 1
            if idx not in t_hats:
                n_missing += 1
                continue
            t_true = snap.fair_point(idx)
            if t_true <= 0:
                continue
            ratio = t_hats[idx] / t_true
            bucket = "t<100" if t_true < 100 else ("100<=t<500" if t_true < 500 else "t>=500")
            buckets[bucket].append(ratio)
    print(f"\n=== median t-hat / t_true, by magnitude of the TRUE t ===")
    print(f"{'t bucket':>12s} {'n':>5s} {'p25':>8s} {'median':>8s} {'p75':>8s}")
    for name, values in buckets.items():
        print(f"{name:>12s} {len(values):5d} {q(values,.25):8.2f} {q(values,.50):8.2f} {q(values,.75):8.2f}")
    print(f"  t-hat unrecoverable for {n_missing}/{n_total} items (no decision log and no evidence cache).")


def extra_accepts_breakdown(game_ids: list[int], k_loose: float, k_tight: float) -> None:
    """Of the extra Transactions a looser t-hat-based Limit accepts (vs a tighter one),
    how many are fair Charges (saving 0.5a in penalty) vs Overcharges (costing up to the
    Cap)? This is what actually decides whether loosening pays."""
    fair_gained = over_gained = 0
    fair_euros = over_euros = 0.0
    for gid in game_ids:
        try:
            snap = snapshot(gid, US)
        except UnreconstructableGame:
            continue
        t_hats = reconstruct_t_hat(gid)
        for idx in snap.line_items:
            if idx not in t_hats:
                continue
            t_hat = t_hats[idx]
            t_true = snap.fair_point(idx)
            b_tight = k_tight * t_hat
            b_loose = k_loose * t_hat
            if b_loose <= b_tight:
                continue
            for team in snap.opponents:
                a = snap.charges[idx].get(team, INF)
                if a == INF:
                    continue
                if b_tight < a <= b_loose:  # this extra accept is what loosening buys
                    if a <= t_true:
                        fair_gained += 1
                        fair_euros += 0.5 * a  # penalty saved
                    else:
                        over_gained += 1
                        c = max(cap_of(t_true), max((x for x in snap.charges[idx].values() if x != INF), default=0.0))
                        over_euros += min(a, c)  # cost incurred
    print(f"\n=== what a looser t-hat Limit (k={k_loose}) buys over a tighter one (k={k_tight}) ===")
    print(f"  extra accepts that were fair Charges:  {fair_gained:5d}  (penalty saved: {fair_euros:12,.0f})")
    print(f"  extra accepts that were Overcharges:   {over_gained:5d}  (cost incurred: {over_euros:12,.0f})")
    net = fair_euros - over_euros
    print(f"  net of this swap alone: {net:,.0f}  ({'loosening wins' if net > 0 else 'tightening wins'})")


if __name__ == "__main__":
    main()
