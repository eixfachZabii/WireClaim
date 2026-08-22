"""What are the current top-5 (ranked by Games 34-38) actually doing, and is it copyable?

Commissioned because the leaderboard inverts once you rank by the last five settled Games
instead of the season total: Non Deterministic and Codacabana are winning right now while
eyay and error404 ai -- the two teams the earlier `rivals_study.py` benchmarked against and
lost to on Charge ratio -- are now losing per Game. This reuses every already-verified
primitive (`Book`/`load_book`/`cap_of` from `rivals.py`, `measure_team`/`reconstruct_t_hat`/
`replay_capped` from `rivals_study.py`, `snapshot`/`our_actual_submission`/`replay` from
`replay_payoffs.py`) and adds only what none of those compute: per-team darkness exposure of
*opponents*, and a decomposition/counterfactual keyed on the NEW top-5 instead of the old
FOCUS_TEAMS.

Two things this script does differently from the brief's own premise, because the numbers
said so (see `scripts/experiments/dark_team_census.py`, run first):

1. The per-team dark census does **not** show a rising Dark Window starting around Game
   33-34. Excluding "makalu" (dark in 38/38 Games -- a permanently-off team, not a regime
   signal), the mean simultaneously-dark-team count is 1.07/Game over G19-33 and 1.4/Game
   over G34-38 -- indistinguishable given n=5. Darkness was *highest* in G1-3 (field still
   booting) and never trended up afterward. The G34/G35 identical-net examples are real but
   are the same ambient noise the whole tournament has shown, not an onset.
2. Non Deterministic itself was fully dark (`a=0` as issuer, `b=0` as reviewer) in Games 23,
   28, 31 **and 36** -- one of the five focus Games. Their G35 alone is +16,675 of their
   +23,654 five-Game total. Both facts are load-bearing for whether there is anything to
   copy, and neither survives skipping the per-Game breakdown.

Usage
-----
    PYTHONPATH=. python scripts/experiments/current_winners_study.py --decompose --games 34-38
    PYTHONPATH=. python scripts/experiments/current_winners_study.py --decompose --games 19-32
    PYTHONPATH=. python scripts/experiments/current_winners_study.py --exposure
    PYTHONPATH=. python scripts/experiments/current_winners_study.py --counterfactual --donor "Non Deterministic"
    PYTHONPATH=. python scripts/experiments/current_winners_study.py --counterfactual --donor Codacabana
    PYTHONPATH=. python scripts/experiments/current_winners_study.py --all
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root, for `src.*`

from pull_transactions import completed_games, identity_net, teams, transactions  # noqa: E402
from rivals import Book, cap_of, load_book, noise_floor  # noqa: E402
from replay_payoffs import UnreconstructableGame, snapshot, our_actual_submission  # noqa: E402
from dark_team_census import dark_flag  # noqa: E402

INF = math.inf
US = "Bin busy"

# NOTE ON WHY THIS DOES NOT `import rivals_study`
# -------------------------------------------------
# `scripts/rivals_study.py` (the script the earlier eyay-copying study used) has, at
# module level, `from src.pricing import Evidence as _Evidence`. `src/pricing.py` no
# longer exists -- `Evidence` moved to `src.pricing.engine` in a refactor that
# landed after that script was written (confirmed: only a stale `.pyc` remains under
# `src/__pycache__`; `blend.py` itself now imports the new path). Python executes a
# module's entire top level on import, so `import rivals_study` fails *at import time*
# regardless of which name is requested -- there is nothing to partially import around.
# `rivals_study.py` is not touched here (someone else's in-flight script); instead the
# handful of functions this file needs (`TeamMetrics`/`measure_team`/`replay_capped`/
# `reconstruct_t_hat`/formatting helpers) are reproduced below, logic byte-identical to
# `rivals_study.py`, importing `Evidence` from where it actually lives now.
from src.pricing.engine import Evidence as _Evidence  # noqa: E402
from src.strategies.strategy2.blend import combine as _combine  # noqa: E402


# --------------------------------------------------------- reproduced from rivals_study.py

TRUSTED_STATES = ("exact", "exact-acc", "zero", "uncapped?")


def q(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(int(p * len(ordered)), len(ordered) - 1)]


def pct(num: float, den: float) -> str:
    return "   n/a" if not den else f"{100.0 * num / den:5.1f}%"


def money(value: float) -> str:
    return f"{value:12,.0f}"


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

    t0_items: int = 0
    t0_charged: int = 0
    t0_charge_income: float = 0.0

    #: sum over items of t(index) * (opponent count) -- the honest ceiling if this team had
    #: charged exactly `a = t` on every item to every opponent (R1: collected regardless of
    #: accept/reject). Added here (not present in `rivals_study.TeamMetrics`) specifically
    #: to separate "this team got better" from "this window's Cases are worth more" -- see
    #: the module docstring's finding #3.
    t_available: float = 0.0

    net_identity: float = 0.0

    @property
    def net_buckets(self) -> float:
        return self.income_fair + self.income_over - self.cost_accept - self.penalty

    @property
    def fair_capture(self) -> float:
        """`income_fair / t_available` -- the case-size-normalized measure of how much of
        the honest ceiling was actually collected as fair (non-Overcharge) income. Comparable
        across windows with different average Line Item values; raw euro totals are not."""
        return self.income_fair / self.t_available if self.t_available else float("nan")


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
            m.t_available += t * (len(book.team_names) - 1)

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
    bad = []
    for team, m in metrics.items():
        if abs(m.net_buckets - m.net_identity) > 0.01:
            bad.append(
                f"{team}: buckets sum to {m.net_buckets:,.2f}, identity says "
                f"{m.net_identity:,.2f} (off by {m.net_buckets - m.net_identity:,.2f})"
            )
    return bad


def replay_capped(snap, submission: dict[int, tuple[float, float]]) -> float:
    """Our net had we submitted `submission`, Cap enforced (`c = max(4t, 2000)`, floored by
    what was actually observed paid on the item). Identical model to `rivals.replay_capped`
    / `rivals_study.replay_capped` -- reproduced here for the same reason as the block above.
    """
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


EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "var" / "evidence"
DECISIONS_DIR = Path(__file__).resolve().parents[2] / "var" / "decisions"


def _load_evidence_tag(game_id: int, tag: str) -> dict[int, _Evidence]:
    path = EVIDENCE_DIR / f"case_{game_id:02d}_{tag}.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {int(k): _Evidence(index=int(k), **v) for k, v in raw.items()}


def reconstruct_t_hat(game_id: int) -> dict[int, float]:
    """`{line_item_index: t-hat}` as it was actually available at decision time.

    Ground truth where a decision log exists (`price_median`, logged at submission time, no
    reconstruction at all). Reconstructed via `combine(model, memory)` on cached evidence
    otherwise. `{}` if neither source exists for this Game. Same logic as
    `rivals_study.reconstruct_t_hat`; only the `Evidence` import path differs.
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

TOP5 = ["Non Deterministic", "Codacabana", "Claims Renaissance", "Teamers", "Bin busy"]
DECLINING = ["error404 ai", "eyay"]  # last-5 negative despite huge season totals
COMPARE = TOP5 + DECLINING

RECENT = list(range(34, 39))
OLD_WINDOW = list(range(19, 33))  # the window the earlier eyay study used


def _parse_games(spec: str) -> list[int]:
    done = set(completed_games())
    out: list[int] = []
    for chunk in spec.split(","):
        start, _, end = chunk.partition("-")
        out += list(range(int(start), int(end or start) + 1))
    return [g for g in sorted(set(out)) if g in done]


# --------------------------------------------------------------------------- decompose


def print_ratio_table(metrics: dict[str, TeamMetrics], title: str) -> None:
    print(f"\n=== {title}: Charge and Limit placement relative to Fair Value ===")
    print(
        f"{'team':22s} {'games':>6s} {'items':>6s} {'trusted':>8s} "
        f"{'a/t p25':>8s} {'a/t med':>8s} {'a/t p75':>8s} "
        f"{'b/t p25':>8s} {'b/t med':>8s} {'b/t p75':>8s}"
    )
    for team, m in metrics.items():
        print(
            f"{team:22s} {m.games:6d} {m.n_items:6d} {m.n_trusted:8d} "
            f"{q(m.a_over_t, .25):8.2f} {q(m.a_over_t, .50):8.2f} {q(m.a_over_t, .75):8.2f} "
            f"{q(m.b_over_t, .25):8.2f} {q(m.b_over_t, .50):8.2f} {q(m.b_over_t, .75):8.2f}"
        )


def print_bucket_table(metrics: dict[str, TeamMetrics], title: str) -> None:
    print(f"\n=== {title}: four-bucket net decomposition ===")
    print(
        f"{'team':22s} {'net':>12s} | {'(i) inc fair':>13s} {'(ii) inc over':>13s} "
        f"{'(iii) cost acc':>14s} {'(iv) penalty':>13s} | {'issuer side':>12s} {'reviewer side':>13s} "
        f"{'t_available':>13s} {'fair capture':>12s}"
    )
    for team, m in metrics.items():
        issuer_side = m.income_fair + m.income_over
        reviewer_side = -(m.cost_accept + m.penalty)
        print(
            f"{team:22s} {money(m.net_identity)} | {money(m.income_fair):>13s} "
            f"{money(m.income_over):>13s} {money(m.cost_accept):>14s} {money(m.penalty):>13s} | "
            f"{money(issuer_side):>12s} {money(reviewer_side):>13s} {money(m.t_available):>13s} "
            f"{m.fair_capture:11.1%}"
        )
    print("  (i)+(ii) = income as Issuer.  -(iii)-(iv) = cost as Reviewer.  net = (i)+(ii)-(iii)-(iv).")
    print("  t_available = sum(t * opponents) -- the honest ceiling if a=t on every item, every")
    print("  opponent (R1). fair_capture = income_fair / t_available: the case-size-normalized")
    print("  share of that ceiling actually collected as fair income -- comparable across windows")
    print("  with different average Line Item values, unlike the raw euro totals to its left.")


def decompose(game_ids: list[int], wanted: list[str], title: str) -> dict[str, TeamMetrics]:
    all_teams = teams()
    print(f"loading {len(game_ids)} Games x {len(all_teams)} teams ...", file=sys.stderr)
    books = [load_book(g, all_teams) for g in game_ids]
    metrics = {t: measure_team(books, t) for t in wanted}
    bad = _verify_reconciliation(metrics)
    if bad:
        print("RECONCILIATION FAILURE (do not trust the tables below):")
        for line in bad:
            print(f"  {line}")
    else:
        print(f"reconciliation OK: buckets sum to identity_net to the cent for all {len(wanted)} teams")
    print_ratio_table(metrics, title)
    print_bucket_table(metrics, title)
    return metrics


# --------------------------------------------------------------------------- exposure


def opponent_dark_exposure(team: str, game_ids: list[int], all_teams: list[str]) -> tuple[float, float]:
    """Average count of dark OPPONENTS this team faced per Game, and the team's own
    dark-Game rate, over `game_ids`. Answers "did the field change around them" directly:
    if a team's own net rose while the average number of dark opponents they faced also
    rose, the gain is at least partly the field, not the team.
    """
    others = [t for t in all_teams if t != team]
    dark_counts = []
    own_dark = 0
    n = 0
    for g in game_ids:
        rows = transactions(team, g)
        if not rows:
            continue
        n += 1
        c = 0
        for opp in others:
            is_dark, opp_n = dark_flag(opp, g)
            if opp_n and is_dark:
                c += 1
        dark_counts.append(c)
        is_dark, _ = dark_flag(team, g)
        if is_dark:
            own_dark += 1
    avg_dark_opponents = sum(dark_counts) / len(dark_counts) if dark_counts else float("nan")
    own_dark_rate = own_dark / n if n else float("nan")
    return avg_dark_opponents, own_dark_rate


def exposure_report() -> None:
    all_teams = teams()
    print("\n=== opponent-darkness exposure: did the field around each team change? ===")
    print(f"{'team':22s} {'avg dark opp G19-32':>20s} {'avg dark opp G34-38':>20s} {'delta':>8s} "
          f"{'own dark rate 19-32':>20s} {'own dark rate 34-38':>20s}")
    for team in COMPARE:
        old_avg, old_own = opponent_dark_exposure(team, OLD_WINDOW, all_teams)
        new_avg, new_own = opponent_dark_exposure(team, RECENT, all_teams)
        print(
            f"{team:22s} {old_avg:20.2f} {new_avg:20.2f} {new_avg - old_avg:8.2f} "
            f"{old_own:19.1%} {new_own:19.1%}"
        )
    print("  'avg dark opp' = mean count (of 16) of the OTHER teams flagged dark (a=0,b=0) in")
    print("  the Games this team actually played. 'own dark rate' = fraction of the team's own")
    print("  Games in that window where the team itself was fully dark.")


# --------------------------------------------------------------------- per-game table


def per_game_table(game_ids: list[int]) -> None:
    print(f"\n=== per-Game net, dark flag -- Games {game_ids[0]}-{game_ids[-1]} ===")
    header = f"{'team':22s}" + "".join(f"{g:>14d}" for g in game_ids) + f"{'total':>14s}"
    print(header)
    for team in COMPARE:
        cells = []
        total = 0.0
        for g in game_ids:
            rows = transactions(team, g)
            net = identity_net(rows, team) if rows else float("nan")
            is_dark, n = dark_flag(team, g)
            tag = "*" if (n and is_dark) else ""
            cells.append(f"{net:12,.0f}{tag:>2s}")
            if rows:
                total += net
        print(f"{team:22s}" + "".join(f"{c:>14s}" for c in cells) + f"{total:14,.0f}")
    print("  '*' marks a Game where the team itself was fully dark (a=0, b=0).")


# --------------------------------------------------------------------- counterfactual


def donor_ratios(game_ids: list[int], donor: str) -> tuple[float, float, int]:
    all_teams = teams()
    books = [load_book(g, all_teams) for g in game_ids]
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


def counterfactual_with_that(
    game_ids: list[int], donor: str, k_a: float, k_b: float
) -> dict[str, dict[int, float]]:
    """Replay donor a/t, b/t ratios using OUR OWN reconstructed t-hat (`reconstruct_t_hat`),
    never the true t. Where t-hat is unrecoverable for an item, our own actual (a,b) is kept
    for that item so the comparison never invents information we did not have.
    """
    labels = {
        "us (actual)": None,
        f"{donor} ratio a+b (a={k_a:.2f}that, b={k_b:.2f}that)": "a+b",
        f"{donor} ratio a only (a={k_a:.2f}that, our b)": "a",
        f"{donor} ratio b only (our a, b={k_b:.2f}that)": "b",
    }
    per_game: dict[str, dict[int, float]] = {label: {} for label in labels}
    for gid in game_ids:
        try:
            snap = snapshot(gid, US)
        except UnreconstructableGame as exc:
            print(f"  skipping G{gid}: {exc}")
            continue
        ours = our_actual_submission(snap)
        t_hats = reconstruct_t_hat(gid)
        for label, mode in labels.items():
            if mode is None:
                submission = ours
            else:
                submission = {}
                for index in snap.line_items:
                    our_a, our_b = ours[index]
                    if index in t_hats:
                        t_hat = t_hats[index]
                        a = k_a * t_hat if mode in ("a+b", "a") else our_a
                        b = k_b * t_hat if mode in ("a+b", "b") else our_b
                    else:
                        a, b = our_a, our_b
                    submission[index] = (a, b)
            per_game[label][gid] = replay_capped(snap, submission)
    return per_game


def print_counterfactual(per_game: dict[str, dict[int, float]], donor: str, title: str) -> None:
    base_label = "us (actual)"
    base = per_game[base_label]
    n_games = len(base)
    floor = noise_floor(n_games)
    print(f"\n=== {title}: adopt {donor}'s (a/t, b/t) on OUR OWN t-hat, over {n_games} Games ===")
    print(f"{'submission':50s} {'total':>13s} {'delta vs us':>13s} {'per Game':>10s}  verdict")
    base_total = sum(base.values())
    for label, values in sorted(per_game.items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(values.values())
        delta = total - base_total
        if label == base_label:
            verdict = "baseline"
        elif abs(delta) < floor:
            verdict = f"inside noise (+-{floor:,.0f})"
        else:
            verdict = "GAIN" if delta > 0 else "LOSS"
        print(f"{label:50s} {total:13,.0f} {delta:13,.0f} {delta / max(n_games,1):10,.0f}  {verdict}")
    print(f"  noise floor = 26,622 * sqrt({n_games}/18) = {floor:,.0f} euros over the window.")


def drop_one_check(per_game: dict[str, dict[int, float]], donor: str, drop_game: int) -> None:
    print(f"\n--- sensitivity: same counterfactual with G{drop_game} dropped ---")
    base_label = "us (actual)"
    base_total = sum(v for g, v in per_game[base_label].items() if g != drop_game)
    n = len([g for g in per_game[base_label] if g != drop_game])
    floor = noise_floor(n)
    for label, values in per_game.items():
        if label == base_label:
            continue
        total = sum(v for g, vv in values.items() if g != drop_game for v in [vv])
        delta = total - base_total
        verdict = "inside noise" if abs(delta) < floor else ("GAIN" if delta > 0 else "LOSS")
        print(f"  {label:50s} delta {delta:12,.0f}  {verdict}")


# --------------------------------------------------------------------------------- cli


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="34-38")
    parser.add_argument("--decompose", action="store_true")
    parser.add_argument("--exposure", action="store_true")
    parser.add_argument("--per-game", action="store_true")
    parser.add_argument("--counterfactual", action="store_true")
    parser.add_argument("--donor", default="Non Deterministic")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all:
        args.decompose = args.exposure = args.per_game = args.counterfactual = True

    game_ids = _parse_games(args.games)

    if args.per_game:
        per_game_table(RECENT)

    if args.decompose:
        decompose(game_ids, COMPARE, f"G{args.games}")

    if args.exposure:
        exposure_report()

    if args.counterfactual:
        for donor in (args.donor,):
            print(f"\nloading books for {donor} ratio measurement over G34-38 ...", file=sys.stderr)
            k_a, k_b, n = donor_ratios(RECENT, donor)
            print(f"\n{donor}'s median a/t = {k_a:.3f}, median b/t = {k_b:.3f} (measured on {n} trusted Charges, G34-38)")

            pg_recent = counterfactual_with_that(RECENT, donor, k_a, k_b)
            print_counterfactual(pg_recent, donor, "Games 34-38")
            drop_one_check(pg_recent, donor, 35)

            pg_all = counterfactual_with_that(completed_games(), donor, k_a, k_b)
            print_counterfactual(pg_all, donor, "all completed Games (out-of-window check)")


if __name__ == "__main__":
    main()
