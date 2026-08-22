"""Score a Fair Value estimator against Cases 1-14, offline and for free.

An estimator here is just a callable

    estimator(case: CaseView) -> {line_item_index: t_hat}

so anything can be scored: a constant, a heuristic, a deterministic parser, or the output
of a model run recorded to disk. **This module never calls a model itself** -- it takes the
estimator as an argument, and caches everything expensive (leaderboard reconstruction, PDF
text extraction) on disk keyed on Case id, so re-tuning the deterministic layer around a
fixed set of estimates costs nothing to re-run.

What is reported
----------------
1. **sigma** -- the standard deviation of `log(t_hat / t_mid)`, overall and per Case. This
   is the headline number. Our measured break-even is **sigma 0.35**; a blind constant
   scores far worse (see the output). It is a log-scale accuracy measure, so it is
   invariant to a global mis-scaling of the estimator -- which is exactly right, because
   the `alpha`/`beta` multipliers in `replay_payoffs.sweep()` can absorb a global scale but
   cannot absorb per-item dispersion.

   Two numbers to record honestly, because they do not match the figures this harness was
   commissioned against. Under the definition implemented here -- `stdev(log(t_hat/t_mid))`
   over the 148 bounded items, `t_mid = (t_lo + t_hi)/2` -- **the blind constant scores
   1.77, not 1.12**; sigma is a standard deviation, so it is identical for *every* constant
   and cannot be tuned down. The 1.12 figure must come from a different `t_mid` convention
   or a different item subset (for reference: restricting to the 78 bounded items with
   `t_lo > 0` gives 0.96, and the mean of the per-Case sigmas gives 1.38). And running the
   oracle blurred by a known amount of log noise (`lognormal_oracle`, `--sigma-curve`) puts
   **break-even at sigma ~ 0.75** with `a = t_hat`, or ~ 0.9 with `a = 0.7 * t_hat` -- not
   0.35. Take 0.35 as the conservative target and 0.75 as where the simulated net actually
   crosses zero against this Field.

2. **Coverage confusion** against the observed `t = 0` set: 76 of the 192 Line Items in
   Games 1-14 have `t_lo = 0`, i.e. nobody was ever wrongfully rejected on them, which is
   the only observable signature of "not covered by the policy". We report how many items
   we call worthless that are not, and how many we miss.

3. **Simulated net per Game and in total**, via `replay_payoffs.replay()` -- the same
   counterfactual harness whose self-check reproduces all fourteen published nets.

4. Two **reference estimators** so the numbers are anchored: a constant (the value that
   minimises the mean log error, i.e. the geometric mean of `t_mid`) and a cheating oracle
   that returns `t_mid` itself.

The caveat, stated up front rather than buried
----------------------------------------------
**sigma is computed on the 148 of 192 Line Items whose Fair Value bracket is bounded
above.** The bracket is bounded only when *somebody* was rightfully rejected on that item;
the 44 unbounded ones are those that nobody ever rightfully rejected, which plausibly means
they are the expensive tail where every Charge in the Field sat below `t`. Those items are
both the hardest to price and the most valuable to price correctly, and they are excluded.
**So sigma as measured here is optimistic.** Every report printed by this module repeats
that line; do not quote the number without it.

Usage
-----
    python scripts/backtest.py                  # both reference estimators
    python scripts/backtest.py --sweep          # plus the best (alpha, beta) per estimator
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics as st
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from replay_payoffs import (  # noqa: E402
    US,
    GameSnapshot,
    best_multipliers,
    multiplier_submission,
    replay,
    snapshot,
    sweep_total,
)

INF = math.inf
CACHE = Path("var/backtest")
CASE_DIRS = (Path("[PUBLIC] EHL Cases/cases"), Path("var/cases"), Path("cases"))
DEFAULT_GAMES = tuple(range(1, 15))

#: `t_hat = 0` is a legitimate answer ("not covered"), but `log 0` is not a number. Zeroes
#: are clamped to this floor for sigma and counted separately in the report.
ZERO_FLOOR = 0.01
#: An estimate at or below this is read as "we called this worthless".
WORTHLESS_THRESHOLD = 1.0

#: Multiplier grid for `tune()`. The Limit multiplier stays inside a sane range; the Charge
#: multiplier runs out to 10 because a *blind* estimator's best play is not an honest price
#: at all -- it is a lottery ticket aimed at the most generous Limits in the Field, and the
#: optimum for the constant reference sits near beta = 8. Both optima below are interior.
TUNE_ALPHAS = tuple(round(0.1 * k, 2) for k in range(1, 41))
TUNE_BETAS = tuple(round(0.1 * k, 2) for k in range(1, 21)) + tuple(
    round(2.0 + 0.5 * k, 2) for k in range(1, 17)
)

SIGMA_CAVEAT = (
    "sigma covers only Line Items with a bounded Fair Value bracket "
    "({bounded} of {total} here). The {unbounded} unbounded ones are those nobody "
    "rightfully rejected -- plausibly the expensive tail -- so this sigma is OPTIMISTIC."
)


# ------------------------------------------------------------------------- the Case view


@dataclass(frozen=True)
class CaseView:
    """What an estimator gets to see about one Case.

    `policy_text`, `description_text` and `invoice_text` are the real Case material, read
    from the extracted archive when it is present and cached as JSON. `truth` is the
    settled Fair Value bracket per Line Item -- it exists so the reference oracle can cheat
    with it, and **an estimator under test must not touch it**.
    """

    game_id: int
    line_item_indices: tuple[int, ...]
    policy_text: str = ""
    description_text: str = ""
    invoice_text: str = ""
    case_dir: Path | None = None
    truth: Mapping[int, tuple[float, float]] = field(default_factory=dict)

    def t_mid(self, index: int) -> float:
        """Midpoint of the bracket, or its lower bound when unbounded above."""
        lo, hi = self.truth[index]
        return lo if hi == INF else (lo + hi) / 2.0

    def bounded(self, index: int) -> bool:
        return self.truth[index][1] != INF

    def looks_worthless(self, index: int) -> bool:
        """`t_lo = 0`: nobody was ever owed money on this item, consistent with `t = 0`."""
        return self.truth[index][0] == 0.0

    def certainly_worthless(self, index: int, threshold: float = 1.0) -> bool:
        """The bracket itself forces `t` below `threshold` -- proof, not just consistency."""
        lo, hi = self.truth[index]
        return lo == 0.0 and hi <= threshold


def _find_case_dir(game_id: int) -> Path | None:
    for root in CASE_DIRS:
        candidate = root / f"case_{game_id:02d}"
        if candidate.is_dir():
            return candidate
    return None


def _read_invoice_text(case_dir: Path) -> str:
    invoice = case_dir / "invoices.pdf"
    if not invoice.exists():
        return ""
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - pypdf is a project dependency
        return ""
    try:
        return "\n".join(page.extract_text() or "" for page in PdfReader(invoice).pages)
    except Exception:  # pragma: no cover - a damaged archive must not kill a backtest
        return ""


def _case_text(game_id: int) -> dict[str, str]:
    """Case text, cached on disk keyed on Case id -- PDF extraction is the slow part."""
    path = CACHE / f"case_{game_id:02d}_text.json"
    if path.exists():
        return json.loads(path.read_text())
    case_dir = _find_case_dir(game_id)
    blob = {
        "case_dir": str(case_dir) if case_dir else "",
        "policy": "",
        "description": "",
        "invoice": "",
    }
    if case_dir is not None:
        for key, name in (("policy", "policy.txt"), ("description", "description.txt")):
            file = case_dir / name
            if file.exists():
                blob[key] = file.read_text(encoding="utf-8", errors="replace")
        blob["invoice"] = _read_invoice_text(case_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob))
    return blob


def case_view(snap: GameSnapshot) -> CaseView:
    blob = _case_text(snap.game_id)
    return CaseView(
        game_id=snap.game_id,
        line_item_indices=snap.line_items,
        policy_text=blob["policy"],
        description_text=blob["description"],
        invoice_text=blob["invoice"],
        case_dir=Path(blob["case_dir"]) if blob["case_dir"] else None,
        truth=dict(snap.fair_brackets),
    )


def load_cases(
    games: Iterable[int] = DEFAULT_GAMES, us: str = US
) -> list[tuple[GameSnapshot, CaseView]]:
    """Snapshot plus Case view for each Game. Both layers are disk-cached."""
    pairs = []
    for game_id in games:
        snap = snapshot(game_id, us)
        pairs.append((snap, case_view(snap)))
    return pairs


# ------------------------------------------------------------------ reference estimators

Estimator = Callable[[CaseView], Mapping[int, float]]


def oracle(case: CaseView) -> dict[int, float]:
    """Cheating reference: the midpoint of the settled Fair Value bracket."""
    return {index: case.t_mid(index) for index in case.line_item_indices}


def constant(value: float) -> Estimator:
    """Blind reference: the same number for every Line Item of every Case."""

    def estimator(case: CaseView) -> dict[int, float]:
        return {index: value for index in case.line_item_indices}

    return estimator


def lognormal_oracle(sigma: float, seed: int = 0) -> Estimator:
    """The oracle blurred by exactly `sigma` of log noise -- an estimator of known quality.

    This is how the break-even claim is checked rather than asserted: score this at a
    ladder of sigmas (``--sigma-curve``) and read off where the simulated net crosses zero.
    """

    def estimator(case: CaseView) -> dict[int, float]:
        rng = random.Random(seed * 1_000 + case.game_id)
        return {
            index: case.t_mid(index) * math.exp(rng.gauss(0.0, sigma))
            for index in case.line_item_indices
        }

    return estimator


def best_constant(cases: Sequence[CaseView]) -> float:
    """The constant that minimises the mean log error: the geometric mean of `t_mid`.

    Note that sigma cannot choose a constant -- it is a standard deviation, so it is the
    same for every constant. Neither can the simulated net on its own, because a constant
    `C` with multipliers `(alpha, beta)` submits `(beta*C, alpha*C)`; only the products are
    identified. The geometric mean is the value that centres the log error at zero, which
    is the choice that makes `alpha = beta = 1` a meaningful baseline.
    """
    logs = [
        math.log(case.t_mid(i))
        for case in cases
        for i in case.line_item_indices
        if case.bounded(i) and case.t_mid(i) > 0
    ]
    return math.exp(st.fmean(logs)) if logs else 1.0


# ------------------------------------------------------------------------------- scoring


@dataclass(frozen=True)
class CaseScore:
    game_id: int
    items: int
    bounded_items: int
    sigma: float | None
    mean_log_error: float | None
    net: float
    #: called worthless and is not / is worthless and we did not call it
    false_worthless: int
    missed_worthless: int
    true_worthless: int
    true_valuable: int
    proven_worthless: int
    missed_proven: int


@dataclass(frozen=True)
class BacktestReport:
    name: str
    alpha: float
    beta: float
    sigma: float | None
    mean_log_error: float | None
    bounded_items: int
    total_items: int
    unbounded_items: int
    clamped_zeroes: int
    false_worthless: int
    missed_worthless: int
    true_worthless: int
    true_valuable: int
    proven_worthless: int
    missed_proven: int
    total_net: float
    per_case: tuple[CaseScore, ...]

    @property
    def caveat(self) -> str:
        return SIGMA_CAVEAT.format(
            bounded=self.bounded_items,
            total=self.total_items,
            unbounded=self.unbounded_items,
        )

    def render(self) -> str:  # pragma: no cover - display only
        lines = [
            f"=== {self.name}   (alpha={self.alpha}, beta={self.beta}) ===",
            f"sigma (overall) : {self.sigma:.4f}" if self.sigma is not None else "sigma: n/a",
            f"mean log error  : {self.mean_log_error:+.4f}"
            if self.mean_log_error is not None
            else "",
            f"items           : {self.total_items} total, {self.bounded_items} bounded "
            f"(sigma sample), {self.unbounded_items} unbounded"
            + (
                f", {self.clamped_zeroes} zero estimates clamped to {ZERO_FLOOR}"
                if self.clamped_zeroes
                else ""
            ),
            f"coverage        : truth {self.true_worthless} worthless "
            f"(t_lo = 0, of which {self.proven_worthless} proven by a bounded bracket) / "
            f"{self.true_valuable} valuable; "
            f"called worthless but is not: {self.false_worthless}; "
            f"is worthless but we priced it: {self.missed_worthless} "
            f"({self.missed_proven} of them provably worthless)",
            "  note: 't_lo = 0' only means nobody was ever *owed* money on the item, so "
            "the worthless label is a consistency test, not proof; even the oracle 'misses' "
            "the ones whose bracket allows a nonzero t.",
            f"simulated net   : {self.total_net:,.2f} over {len(self.per_case)} Games",
            "",
            f"{'Game':>5} {'items':>6} {'bnd':>4} {'sigma':>8} {'net':>13}"
            f"  {'false-worthless':>15} {'missed-worthless':>16}",
        ]
        for score in self.per_case:
            sigma = f"{score.sigma:8.3f}" if score.sigma is not None else "     n/a"
            lines.append(
                f"{score.game_id:5d} {score.items:6d} {score.bounded_items:4d} {sigma} "
                f"{score.net:13,.2f}  {score.false_worthless:15d} {score.missed_worthless:16d}"
            )
        lines += ["", "CAVEAT: " + self.caveat]
        return "\n".join(line for line in lines if line != "")


def score(
    estimator: Estimator,
    cases: Sequence[tuple[GameSnapshot, CaseView]] | None = None,
    *,
    name: str = "estimator",
    alpha: float = 1.0,
    beta: float = 1.0,
    limit_rule: str = "mid",
    worthless_threshold: float = WORTHLESS_THRESHOLD,
) -> BacktestReport:
    """Run `estimator` over the Cases and produce the full report."""
    cases = cases if cases is not None else load_cases()
    all_logs: list[float] = []
    per_case: list[CaseScore] = []
    clamped = 0
    totals = {"fw": 0, "mw": 0, "tw": 0, "tv": 0, "pw": 0, "mp": 0, "bounded": 0, "items": 0}
    total_net = 0.0

    for snap, case in cases:
        estimates = dict(estimator(case))
        missing = [i for i in case.line_item_indices if i not in estimates]
        if missing:
            raise ValueError(f"estimator returned no t_hat for Game {case.game_id} items {missing}")

        logs: list[float] = []
        counts = {"fw": 0, "mw": 0, "tw": 0, "tv": 0, "pw": 0, "mp": 0}
        for index in case.line_item_indices:
            t_hat = float(estimates[index])
            if case.bounded(index):
                t_mid = case.t_mid(index)
                if t_hat <= 0.0:
                    clamped += 1
                if t_mid > 0:
                    logs.append(math.log(max(t_hat, ZERO_FLOOR) / t_mid))
            worthless = case.looks_worthless(index)
            proven = case.certainly_worthless(index, worthless_threshold)
            called = t_hat <= worthless_threshold
            counts["tw" if worthless else "tv"] += 1
            counts["pw"] += int(proven)
            if called and not worthless:
                counts["fw"] += 1
            if worthless and not called:
                counts["mw"] += 1
            if proven and not called:
                counts["mp"] += 1

        submission = multiplier_submission(estimates, alpha, beta)
        net = replay(snap, submission, limit_rule=limit_rule).net
        total_net += net
        all_logs += logs
        for key in counts:
            totals[key] += counts[key]
        totals["bounded"] += len(logs)
        totals["items"] += len(case.line_item_indices)
        per_case.append(
            CaseScore(
                game_id=case.game_id,
                items=len(case.line_item_indices),
                bounded_items=len(logs),
                sigma=st.stdev(logs) if len(logs) > 1 else None,
                mean_log_error=st.fmean(logs) if logs else None,
                net=net,
                false_worthless=counts["fw"],
                missed_worthless=counts["mw"],
                true_worthless=counts["tw"],
                true_valuable=counts["tv"],
                proven_worthless=counts["pw"],
                missed_proven=counts["mp"],
            )
        )

    return BacktestReport(
        name=name,
        alpha=alpha,
        beta=beta,
        sigma=st.stdev(all_logs) if len(all_logs) > 1 else None,
        mean_log_error=st.fmean(all_logs) if all_logs else None,
        bounded_items=totals["bounded"],
        total_items=totals["items"],
        unbounded_items=totals["items"] - totals["bounded"],
        clamped_zeroes=clamped,
        false_worthless=totals["fw"],
        missed_worthless=totals["mw"],
        true_worthless=totals["tw"],
        true_valuable=totals["tv"],
        proven_worthless=totals["pw"],
        missed_proven=totals["mp"],
        total_net=total_net,
        per_case=tuple(per_case),
    )


def tune(
    estimator: Estimator,
    cases: Sequence[tuple[GameSnapshot, CaseView]] | None = None,
    *,
    alphas: Iterable[float] | None = None,
    betas: Iterable[float] | None = None,
    limit_rule: str = "mid",
) -> tuple[float, float, float]:
    """Best `(alpha, beta, total net)` for this estimator over the Cases."""
    cases = cases if cases is not None else load_cases()
    alphas = tuple(alphas) if alphas is not None else TUNE_ALPHAS
    betas = tuple(betas) if betas is not None else TUNE_BETAS
    lookup = {case.game_id: dict(estimator(case)) for _, case in cases}
    grid = sweep_total(
        [snap for snap, _ in cases],
        lambda snap: lookup[snap.game_id],
        alphas=alphas,
        betas=betas,
        limit_rule=limit_rule,
    )
    return best_multipliers(grid)


def clear_cache() -> None:
    """Drop the on-disk Case-text cache (leaderboard snapshots live in ``var/replay``)."""
    for path in CACHE.glob("case_*_text.json"):
        path.unlink()


# --------------------------------------------------------------------------------- cli


def main() -> None:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-14")
    parser.add_argument("--limit-rule", default="mid", choices=("lo", "mid", "hi"))
    parser.add_argument("--sweep", action="store_true", help="also tune alpha and beta")
    parser.add_argument(
        "--sigma-curve",
        action="store_true",
        help="net against a ladder of known sigmas, to locate the break-even empirically",
    )
    parser.add_argument("--constant", type=float, default=None)
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    games = range(int(start), int(end or start) + 1)

    cases = load_cases(games)
    views = [view for _, view in cases]
    value = args.constant if args.constant is not None else round(best_constant(views), 2)

    references: list[tuple[str, Estimator]] = [
        (f"constant t_hat = {value}", constant(value)),
        ("oracle t_mid (cheating)", oracle),
    ]
    for name, estimator in references:
        report = score(estimator, cases, name=name, limit_rule=args.limit_rule)
        print(report.render())
        if args.sweep:
            alpha, beta, net = tune(estimator, cases, limit_rule=args.limit_rule)
            tuned = score(
                estimator, cases, name=f"{name} tuned", alpha=alpha, beta=beta,
                limit_rule=args.limit_rule,
            )
            print(
                f"  best multipliers: alpha={alpha} beta={beta} -> total net {net:,.2f}"
                f"  (a = {beta} * t_hat, b = {alpha} * t_hat)"
            )
            print(f"  tuned per-Game net total: {tuned.total_net:,.2f}")
            if beta > 1.5:
                print(
                    "  WARNING: beta > 1.5 means the tuned play is a deliberate Overcharge "
                    "aimed at the most generous Limits in the Field. It is only optimal "
                    "because the estimator is too blind to earn honestly, it is measured on "
                    "the awake early regime, and R5c says a mis-measured acceptance rate is "
                    "worse than assuming zero. Do not ship it off this number alone."
                )
        print()

    if args.sigma_curve:
        print("=== net against a known sigma (oracle blurred by log-normal noise) ===")
        print(f"{'sigma':>6} {'measured':>9} {'net a=t_hat':>14} {'net a=0.7 t_hat':>16}")
        for sigma in (0.0, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.0):
            nets_one, nets_seven, measured = [], [], []
            for seed in range(5):
                estimator = lognormal_oracle(sigma, seed)
                one = score(estimator, cases, alpha=1.0, beta=1.0, limit_rule=args.limit_rule)
                seven = score(estimator, cases, alpha=1.0, beta=0.7, limit_rule=args.limit_rule)
                nets_one.append(one.total_net)
                nets_seven.append(seven.total_net)
                measured.append(one.sigma or 0.0)
            print(
                f"{sigma:6.2f} {st.fmean(measured):9.3f} "
                f"{st.fmean(nets_one):14,.0f} {st.fmean(nets_seven):16,.0f}"
            )
        print("(" + SIGMA_CAVEAT.format(bounded=148, total=192, unbounded=44) + ")")


if __name__ == "__main__":  # pragma: no cover
    main()
