"""The self-check that makes the counterfactual harness worth anything.

`scripts/replay_payoffs.py` claims it can tell us what our net *would* have been in a
settled Game under a different submission. The only evidence that such a claim is not
fiction is that feeding it our **real** submission reproduces our **published** net -- for
every Game, to the cent. That is what `test_self_check_reproduces_published_net` asserts,
for all fourteen settled Games.

Everything else here guards the pieces that self-check leans on: the payoff table (checked
against the worked example in docs/GAME_DESCRIPTION.md), the Cap never binding, and the
`backtest` metrics that are computed on top.

These tests read the settled leaderboard. They are offline once `var/replay` and
`var/transactions` are warm; if neither the cache nor the network is available the module
skips rather than fails, because a red suite for a missing network tells us nothing.
"""

from __future__ import annotations

import math
import statistics as st
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import backtest  # noqa: E402
import replay_payoffs as rp  # noqa: E402

GAMES = tuple(range(1, 15))
#: Facts about Games 1-14 that other tooling quotes; if they move, the tooling is stale.
TOTAL_LINE_ITEMS = 192
BOUNDED_LINE_ITEMS = 148
WORTHLESS_LINE_ITEMS = 76


def _load() -> list[rp.GameSnapshot] | None:
    try:
        return [rp.snapshot(game_id) for game_id in GAMES]
    except Exception:  # pragma: no cover - no cache and no leaderboard
        return None


SNAPSHOTS = _load()
requires_data = unittest.skipIf(
    SNAPSHOTS is None, "settled leaderboard data is neither cached nor reachable"
)


class PayoffTableTests(unittest.TestCase):
    """The four cells of the payoff table, against the handout's worked example."""

    def test_fair_and_accepted_pays_the_charge(self) -> None:
        self.assertEqual(rp.issuer_payoff(100, 110, 100), 100)
        self.assertEqual(rp.reviewer_payoff(100, 110, 100), 100)

    def test_fair_and_rejected_costs_the_reviewer_a_lawyer(self) -> None:
        self.assertEqual(rp.issuer_payoff(100, 90, 100), 100)
        self.assertEqual(rp.reviewer_payoff(100, 90, 100), 150)

    def test_overcharge_accepted_pays_the_overcharge(self) -> None:
        self.assertEqual(rp.issuer_payoff(150, 200, 100), 150)
        self.assertEqual(rp.reviewer_payoff(150, 200, 100), 150)

    def test_overcharge_rejected_moves_nothing(self) -> None:
        self.assertEqual(rp.issuer_payoff(150, 110, 100), 0)
        self.assertEqual(rp.reviewer_payoff(150, 110, 100), 0)

    def test_the_handout_example_round(self) -> None:
        """Alpha +100, Delta +100, Beta -300 (docs/GAME_DESCRIPTION.md)."""
        submissions = {"Alpha": (100, 130), "Beta": (150, 90), "Delta": (100, 110)}
        t = 100
        nets = {}
        for team, (charge, limit) in submissions.items():
            income = sum(
                rp.issuer_payoff(charge, other_limit, t)
                for other, (_, other_limit) in submissions.items()
                if other != team
            )
            cost = sum(
                rp.reviewer_payoff(other_charge, limit, t)
                for other, (other_charge, _) in submissions.items()
                if other != team
            )
            nets[team] = income - cost
        self.assertEqual(nets, {"Alpha": 100, "Beta": -300, "Delta": 100})

    def test_an_unrecoverable_charge_never_moves_money(self) -> None:
        """A Charge every reviewer rejected is stored as `inf`; it must stay inert."""
        self.assertEqual(rp.reviewer_payoff(math.inf, 10_000, 500), 0.0)


@requires_data
class SelfCheckTests(unittest.TestCase):
    """The load-bearing test: our real submission must replay to our published net."""

    def test_self_check_reproduces_published_net(self) -> None:
        for snap in SNAPSHOTS or []:
            with self.subTest(game=snap.game_id):
                replayed, published = rp.self_check(snap.game_id)
                self.assertAlmostEqual(
                    replayed,
                    published,
                    places=2,
                    msg=f"Game {snap.game_id}: replay {replayed:.2f} vs published {published:.2f}",
                )

    def test_self_check_holds_for_every_limit_representative(self) -> None:
        """Any point inside a reconstructed Limit bracket reproduces the real decisions."""
        for rule in ("lo", "mid", "hi"):
            for snap in SNAPSHOTS or []:
                with self.subTest(game=snap.game_id, rule=rule):
                    replayed, published = rp.self_check(snap.game_id, limit_rule=rule)
                    self.assertAlmostEqual(replayed, published, places=2)

    def test_all_fourteen_games_are_covered(self) -> None:
        self.assertEqual(len(SNAPSHOTS or []), 14)
        self.assertEqual(sum(len(snap.line_items) for snap in SNAPSHOTS or []), TOTAL_LINE_ITEMS)

    def test_every_game_has_sixteen_opponents(self) -> None:
        for snap in SNAPSHOTS or []:
            with self.subTest(game=snap.game_id):
                self.assertEqual(len(snap.opponents), 16)
                self.assertNotIn(rp.US, snap.opponents)

    def test_the_cap_never_bound(self) -> None:
        """Justifies treating `c` as infinite: no (Line Item, issuer) reports two amounts."""
        conflicts = [c for snap in SNAPSHOTS or [] for c in rp.cap_conflicts(snap.game_id)]
        self.assertEqual(conflicts, [])


@requires_data
class SnapshotTests(unittest.TestCase):
    def test_cache_round_trip_is_lossless(self) -> None:
        snap = (SNAPSHOTS or [])[0]
        self.assertEqual(rp._decode(rp._encode(snap)), snap)

    def test_infinities_survive_the_cache(self) -> None:
        snap = (SNAPSHOTS or [])[0]
        decoded = rp._decode(rp._encode(snap))
        for index in snap.line_items:
            self.assertEqual(snap.fair_brackets[index], decoded.fair_brackets[index])

    def test_brackets_are_ordered(self) -> None:
        for snap in SNAPSHOTS or []:
            for index in snap.line_items:
                lo, hi = snap.fair_brackets[index]
                with self.subTest(game=snap.game_id, item=index):
                    self.assertLess(lo, hi)
                    self.assertGreaterEqual(lo, 0.0)

    def test_the_default_submission_is_a_money_fountain(self) -> None:
        """`a = 0, b = 0` is not a zero: it wrongfully rejects everything (CLAUDE.md rule 1)."""
        for snap in SNAPSHOTS or []:
            with self.subTest(game=snap.game_id):
                result = rp.replay(snap, {})
                self.assertEqual(result.income, 0.0)
                if any(lo > 0 for lo, _ in snap.fair_brackets.values()):
                    self.assertLess(result.net, 0.0)


@requires_data
class SweepTests(unittest.TestCase):
    def test_oracle_sweep_prefers_charging_the_fair_value(self) -> None:
        grid = rp.sweep_total(
            SNAPSHOTS or [],
            rp.oracle_estimates,
            alphas=(0.5, 1.0, 1.5),
            betas=(0.5, 1.0, 1.5),
        )
        alpha, beta, net = rp.best_multipliers(grid)
        self.assertEqual((alpha, beta), (1.0, 1.0))
        self.assertGreater(net, 0.0)

    def test_multiplier_submission_scales_both_numbers(self) -> None:
        submission = rp.multiplier_submission({1: 100.0, 2: 50.0}, alpha=1.2, beta=0.7)
        self.assertAlmostEqual(submission[1][0], 70.0)
        self.assertAlmostEqual(submission[1][1], 120.0)
        self.assertAlmostEqual(submission[2][0], 35.0)


@requires_data
class BacktestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = backtest.load_cases(GAMES)
        cls.views = [view for _, view in cls.cases]

    def test_the_sigma_sample_is_the_bounded_subset(self) -> None:
        report = backtest.score(backtest.oracle, self.cases, name="oracle")
        self.assertEqual(report.total_items, TOTAL_LINE_ITEMS)
        self.assertEqual(report.bounded_items, BOUNDED_LINE_ITEMS)
        self.assertEqual(report.unbounded_items, TOTAL_LINE_ITEMS - BOUNDED_LINE_ITEMS)

    def test_the_optimistic_caveat_is_always_surfaced(self) -> None:
        report = backtest.score(backtest.oracle, self.cases, name="oracle")
        self.assertIn("OPTIMISTIC", report.caveat)
        self.assertIn("OPTIMISTIC", report.render())

    def test_oracle_scores_sigma_zero_and_a_large_positive_net(self) -> None:
        report = backtest.score(backtest.oracle, self.cases, name="oracle")
        self.assertIsNotNone(report.sigma)
        self.assertAlmostEqual(report.sigma, 0.0, places=9)
        self.assertGreater(report.total_net, 0.0)

    def test_a_blind_constant_is_far_past_the_break_even_sigma(self) -> None:
        value = backtest.best_constant(self.views)
        report = backtest.score(backtest.constant(value), self.cases, name="constant")
        self.assertGreater(report.sigma or 0.0, 0.35)  # break-even is sigma 0.35
        self.assertLess(report.total_net, 0.0)

    def test_sigma_is_invariant_to_the_constant_chosen(self) -> None:
        """A standard deviation cannot pick the level -- only the multipliers can."""
        first = backtest.score(backtest.constant(10.0), self.cases).sigma
        second = backtest.score(backtest.constant(1000.0), self.cases).sigma
        self.assertAlmostEqual(first or 0.0, second or 1.0, places=9)

    def test_sigma_measures_back_the_noise_it_was_given(self) -> None:
        """Inject a known log-noise and the metric must report it -- the metric's own check."""
        for injected in (0.2, 0.5, 1.0):
            measured = st.fmean(
                [
                    backtest.score(
                        backtest.lognormal_oracle(injected, seed), self.cases
                    ).sigma or 0.0
                    for seed in range(5)
                ]
            )
            with self.subTest(sigma=injected):
                self.assertAlmostEqual(measured, injected, delta=0.1 * injected)

    def test_a_blurred_oracle_earns_less_than_a_sharp_one(self) -> None:
        sharp = backtest.score(backtest.oracle, self.cases).total_net
        blurred = backtest.score(backtest.lognormal_oracle(1.0, 1), self.cases).total_net
        self.assertLess(blurred, sharp)

    def test_the_worthless_set_is_the_seventy_six_items_nobody_was_owed_on(self) -> None:
        report = backtest.score(backtest.constant(1000.0), self.cases)
        self.assertEqual(report.true_worthless, WORTHLESS_LINE_ITEMS)
        self.assertEqual(report.true_worthless + report.true_valuable, TOTAL_LINE_ITEMS)
        self.assertEqual(report.missed_worthless, WORTHLESS_LINE_ITEMS)
        self.assertEqual(report.false_worthless, 0)

    def test_calling_everything_worthless_inverts_the_confusion(self) -> None:
        report = backtest.score(backtest.constant(0.0), self.cases)
        self.assertEqual(report.missed_worthless, 0)
        self.assertEqual(report.false_worthless, TOTAL_LINE_ITEMS - WORTHLESS_LINE_ITEMS)
        self.assertEqual(report.clamped_zeroes, BOUNDED_LINE_ITEMS)

    def test_an_estimator_that_skips_a_line_item_is_an_error_not_a_zero(self) -> None:
        with self.assertRaises(ValueError):
            backtest.score(lambda case: {}, self.cases)

    def test_per_case_scores_cover_every_game(self) -> None:
        report = backtest.score(backtest.oracle, self.cases, name="oracle")
        self.assertEqual([s.game_id for s in report.per_case], list(GAMES))
        self.assertAlmostEqual(sum(s.net for s in report.per_case), report.total_net, places=6)

    def test_the_scored_net_agrees_with_a_direct_replay(self) -> None:
        report = backtest.score(backtest.oracle, self.cases, name="oracle", alpha=1.0, beta=0.7)
        for snap, view in self.cases:
            direct = rp.replay(snap, rp.multiplier_submission(backtest.oracle(view), 1.0, 0.7)).net
            scored = next(s.net for s in report.per_case if s.game_id == snap.game_id)
            with self.subTest(game=snap.game_id):
                self.assertAlmostEqual(direct, scored, places=6)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
