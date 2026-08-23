"""The self-check that makes the counterfactual harness worth anything.

`scripts/replay_payoffs.py` claims it can tell us what our net *would* have been in a
settled Game under a different submission. The only evidence that such a claim is not
fiction is that feeding it our **real** submission reproduces our **published** net -- for
every Game, to the cent. That is what `test_self_check_reproduces_published_net` asserts for
Games 1-14, and `AllCompletedGamesTests` for every Game that has settled since.

Everything else here guards the pieces that self-check leans on: the payoff table (checked
against the worked example in docs/GAME_DESCRIPTION.md), the Cap never binding, and the
`backtest` metrics that are computed on top.

Two of these tests exist because of specific, expensive mistakes:

* `MatrixIndexingTests` pins that `/matrix` `cells` is **not** positional. It is a trailing
  window of the twenty most recently completed Games, published as `game_ids` in the same
  payload. `matrix()` therefore returns `{team: {game_id: net}}`, and these tests assert that
  it cannot be indexed by position and refuses to guess when the mapping is unresolvable.
* `GameSixteenTests` pins Game 16, which was reported as "does not reconstruct: -4,721
  against a published -63,789, and only 2 Line Items". Game 16 reconstructs perfectly;
  -63,789 is **Game 17's** net, handed over by the stale positional index, and Case 16's
  invoice really does have exactly 2 Line Items. The Game is pinned here so nobody scores
  against it under a wrong published number again -- in either direction.

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
import pull_transactions as pt  # noqa: E402
import replay_payoffs as rp  # noqa: E402

GAMES = tuple(range(1, 15))
#: Facts about Games 1-14 that other tooling quotes; if they move, the tooling is stale.
TOTAL_LINE_ITEMS = 192
BOUNDED_LINE_ITEMS = 148
WORTHLESS_LINE_ITEMS = 76

#: Game 16, pinned. `line_items` and `net` come from the rows (`total = 64` for us, fetched
#: in full), and the Case 16 invoice lists exactly these two: "Clothing and jewellery stolen
#: from the car" and "Vehicle costs". `not_net` is Game 17's, which the old positional
#: `/matrix` index misattributed to Game 16.
GAME_16 = {"game_id": 16, "line_items": 2, "net": -4721.32, "not_net": -63789.245}

#: How wide `/matrix` `cells` is. Not a Game count -- a window length.
MATRIX_WINDOW = 20


def _load() -> list[rp.GameSnapshot] | None:
    try:
        return [rp.snapshot(game_id) for game_id in GAMES]
    except Exception:  # pragma: no cover - no cache and no leaderboard
        return None


def _load_all() -> list[rp.Reconstruction] | None:
    """Every completed Game, labelled usable or not. Needs `/games`, so network-gated."""
    try:
        return rp.reconstruction_report()
    except Exception:  # pragma: no cover - leaderboard unreachable
        return None


def _load_matrix() -> tuple[dict, list[int]] | None:
    try:
        return pt.matrix(), pt.completed_games()
    except Exception:  # pragma: no cover - leaderboard unreachable
        return None


SNAPSHOTS = _load()
requires_data = unittest.skipIf(
    SNAPSHOTS is None, "settled leaderboard data is neither cached nor reachable"
)

ALL_GAMES = _load_all() if SNAPSHOTS is not None else None
requires_all_games = unittest.skipIf(
    not ALL_GAMES, "the completed-Game list needs a reachable leaderboard"
)

MATRIX = _load_matrix() if SNAPSHOTS is not None else None
requires_matrix = unittest.skipIf(MATRIX is None, "/matrix is not reachable")


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
        """Justifies treating `c` as infinite: no (Line Item, issuer) reports two amounts.

        The team list comes from the snapshot rather than `teams()` so the test stays offline
        once `var/replay` is warm -- a red suite for a missing network tells us nothing.
        """
        conflicts = [
            c
            for snap in SNAPSHOTS or []
            for c in rp.cap_conflicts(snap.game_id, [snap.us, *snap.opponents])
        ]
        self.assertEqual(conflicts, [])


@requires_matrix
class MatrixIndexingTests(unittest.TestCase):
    """`/matrix` `cells` is a trailing window, not a list indexed by Game id.

    We assumed `cells[k]` was Game `k+1` and it silently gave Game 16 Game 17's money. These
    tests make the wrong reading impossible to write: `matrix()` hands back a mapping, and
    the mapping is cross-checked against `/games`.
    """

    def test_matrix_is_keyed_by_game_id_not_by_position(self) -> None:
        table, _ = MATRIX or ({}, [])
        cells = table[rp.US]
        self.assertIsInstance(cells, dict)
        for key in cells:
            self.assertIsInstance(key, int)

    def test_cells_are_narrower_than_the_completed_games_once_the_window_slides(self) -> None:
        """The bug's precondition: as soon as this holds, `cells[g - 1]` is the wrong Game."""
        _, completed = MATRIX or ({}, [])
        ids = pt.matrix_game_ids()
        self.assertLessEqual(len(ids), len(completed))
        if len(completed) > MATRIX_WINDOW:
            self.assertEqual(len(ids), MATRIX_WINDOW)
            self.assertNotEqual(ids[0], 1)  # the window has moved off Game 1

    def test_every_published_game_id_is_a_completed_game(self) -> None:
        _, completed = MATRIX or ({}, [])
        self.assertTrue(set(pt.matrix_game_ids()).issubset(set(completed)))

    def test_the_window_is_the_most_recent_completed_games(self) -> None:
        _, completed = MATRIX or ({}, [])
        ids = pt.matrix_game_ids()
        self.assertEqual(ids, completed[-len(ids) :])

    def test_a_game_outside_the_window_is_absent_not_someone_elses_number(self) -> None:
        """The whole point of a dict: a missing Game is missing, not silently substituted."""
        table, _ = MATRIX or ({}, [])
        ids = pt.matrix_game_ids()
        if min(ids) == 1:
            self.skipTest("the window still starts at Game 1; nothing has fallen out of it yet")
        self.assertIsNone(pt.published_net(rp.US, min(ids) - 1, table))

    def test_matrix_refuses_to_guess_when_the_mapping_is_unresolvable(self) -> None:
        payload = {"items": [{"team_name": "a", "cells": [1.0, 2.0]}]}  # no game_ids at all
        with self.assertRaises(pt.AmbiguousMatrix):
            pt.matrix_game_ids(payload)

    def test_matrix_uses_published_game_ids_when_they_fit(self) -> None:
        payload = {"items": [{"team_name": "a", "cells": [1.0, 2.0]}], "game_ids": [7, 8]}
        self.assertEqual(pt.matrix_game_ids(payload), [7, 8])

    def test_matrix_rejects_rows_that_disagree_on_width(self) -> None:
        payload = {
            "items": [{"team_name": "a", "cells": [1.0]}, {"team_name": "b", "cells": [1.0, 2.0]}],
            "game_ids": [1],
        }
        with self.assertRaises(pt.AmbiguousMatrix):
            pt.matrix_game_ids(payload)

    def test_every_published_cell_equals_the_identity_over_the_rows(self) -> None:
        """The identity is authoritative; agreeing with it is what makes a cell trustworthy."""
        table, _ = MATRIX or ({}, [])
        for game_id in pt.matrix_game_ids():
            with self.subTest(game=game_id):
                rows = pt.transactions(rp.US, game_id)
                self.assertAlmostEqual(
                    pt.identity_net(rows, rp.US), table[rp.US][game_id], places=1
                )


@requires_data
class GameSixteenTests(unittest.TestCase):
    """Game 16, pinned. It reconstructs; the -63,789 it was scored against was Game 17's."""

    def setUp(self) -> None:
        self.snap = rp.snapshot(GAME_16["game_id"])

    def test_game_sixteen_has_exactly_two_line_items(self) -> None:
        """Case 16's invoice lists two, and 64 rows were fetched against `total = 64`."""
        self.assertEqual(len(self.snap.line_items), GAME_16["line_items"])

    def test_game_sixteen_reconstructs(self) -> None:
        replayed, published = rp.self_check(GAME_16["game_id"], strict=True)
        self.assertAlmostEqual(replayed, GAME_16["net"], places=1)
        self.assertAlmostEqual(published, GAME_16["net"], places=1)

    def test_game_sixteen_is_reported_usable(self) -> None:
        status = rp.reconstruction_status(GAME_16["game_id"])
        self.assertEqual(status.status, "ok")
        self.assertTrue(status.usable)

    def test_game_sixteen_is_not_game_seventeens_net(self) -> None:
        """The exact misattribution that started this. Never again, in either direction."""
        self.assertNotAlmostEqual(self.snap.published_net, GAME_16["not_net"], places=1)
        seventeen = rp.snapshot(17)
        self.assertAlmostEqual(seventeen.published_net, GAME_16["not_net"], places=1)

    def test_game_sixteen_was_never_a_short_read(self) -> None:
        rows = pt.transactions(rp.US, GAME_16["game_id"])
        self.assertEqual(sorted({r["line_item_index"] for r in rows}), [1, 2])
        self.assertEqual(pt.cache_status(rp.US, GAME_16["game_id"]), "ok")


@requires_all_games
class AllCompletedGamesTests(unittest.TestCase):
    """Every Game that has settled must either reconstruct or be named as unusable."""

    def test_every_completed_game_reconstructs(self) -> None:
        """...unless the payment Cap has destroyed the Charges on one of its Line Items.

        That exception is narrow and it is checked, not asserted. A Charge recovers from
        `amount`, which on an accepted row is `min(a, c)`, so on a Line Item cheap enough that
        `c = 2000` every issuer who Charged above 2,000 recovers as exactly 2,000.00. Game 67
        Line Item 1 settled at `t < 33`: we Charged 10,343.65, a rival Charged just over 2,000,
        both collapse to 2,000.00, and a reviewer that accepted the rival while rejecting us ends
        up with the bracket `[2000, 2000)` -- inconsistent, and unfixable by any representative.

        Restoring our own true Charge from `var/decisions/` was tried and is worse: it repairs
        Game 67 and breaks six Games that reconstructed to the cent, because the other sixteen
        teams' Charges cannot be restored the same way. See `replay_payoffs.cap_collisions`.

        So a Game may fail the identity **only** with a named Cap collision behind it. Eleven of
        the twelve Games that have one still reconstruct, so this is not a licence to fail: it
        does not widen to anything else, and a Game that breaks for any other reason still fails
        this test.
        """
        broken = [r for r in ALL_GAMES or [] if not r.usable]
        unexplained = [
            (r.game_id, r.status, r.detail)
            for r in broken
            if not rp.cap_collisions(r.game_id)
        ]
        self.assertEqual(
            unexplained, [], f"these Games do not reconstruct and the Cap does not explain it: {unexplained}"
        )
        for r in broken:
            collisions = rp.cap_collisions(r.game_id)
            self.assertTrue(
                collisions,
                f"G{r.game_id} excused without a collision -- the guard has been widened",
            )

    def test_the_report_covers_every_completed_game(self) -> None:
        self.assertEqual([r.game_id for r in ALL_GAMES or []], pt.completed_games())

    def test_usable_games_excludes_nothing_it_should_not(self) -> None:
        self.assertEqual(rp.usable_games(), [r.game_id for r in ALL_GAMES or [] if r.usable])

    def test_a_game_whose_rows_disagree_with_its_cell_is_fatal(self) -> None:
        """The guard itself: a mismatch must raise, never return a wrong number."""
        with self.assertRaises(rp.UnreconstructableGame):
            raise rp.UnreconstructableGame("sentinel")
        status = rp.Reconstruction(99, "mismatch", 0, None, None, None, "sentinel")
        self.assertFalse(status.usable)


@requires_data
class TransactionCacheTests(unittest.TestCase):
    """A cached file must carry the `total` it was validated against, or be refused."""

    def test_every_cached_game_is_trusted(self) -> None:
        for game_id in GAMES:
            with self.subTest(game=game_id):
                self.assertEqual(pt.cache_status(rp.US, game_id), "ok")

    def test_a_short_read_on_disk_is_refused(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.json"
            path.write_text(
                json.dumps({"version": pt.CACHE_VERSION, "total": 576, "rows": [{"a": 1}]})
            )
            rows, reason = pt._read_cache(path)
            self.assertIsNone(rows)
            self.assertIn("short read", reason)

    def test_an_unstamped_legacy_cache_is_refused(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.json"
            path.write_text(json.dumps([{"a": 1}]))
            rows, reason = pt._read_cache(path)
            self.assertIsNone(rows)
            self.assertIn("legacy", reason)

    def test_a_stamped_cache_that_agrees_with_its_total_is_trusted(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "good.json"
            path.write_text(
                json.dumps({"version": pt.CACHE_VERSION, "total": 1, "rows": [{"a": 1}]})
            )
            rows, reason = pt._read_cache(path)
            self.assertEqual(rows, [{"a": 1}])
            self.assertEqual(reason, "ok")


@requires_data
class LimitRuleSensitivityTests(unittest.TestCase):
    """The `limit_rule="mid"` choice must not be load-bearing for any conclusion."""

    def test_the_rule_cannot_matter_while_we_do_not_overcharge(self) -> None:
        """For `a <= t` the issuer is paid `a` regardless of the reviewer's Limit."""
        report = rp.limit_sensitivity(
            SNAPSHOTS or [], rp.oracle_estimates, alphas=(0.5, 1.0, 2.0), betas=(0.5, 0.7, 1.0)
        )
        totals = {round(row["best"][2], 6) for row in report["rules"].values()}
        self.assertEqual(len(totals), 1, f"the rule moved the sweep total: {totals}")
        self.assertEqual(report["insensitive_betas"], [0.5, 0.7, 1.0])

    def test_our_actual_total_is_identical_under_every_rule(self) -> None:
        report = rp.limit_sensitivity(
            SNAPSHOTS or [], rp.oracle_estimates, alphas=(1.0,), betas=(0.7,)
        )
        actuals = {round(row["actual"], 6) for row in report["rules"].values()}
        self.assertEqual(len(actuals), 1, f"the rule moved our real net: {actuals}")

    def test_the_rule_does_matter_above_the_fair_value(self) -> None:
        """Stated so nobody generalises the invariance into the Overcharge region."""
        report = rp.limit_sensitivity(
            SNAPSHOTS or [], rp.oracle_estimates, alphas=(0.2,), betas=(1.5,)
        )
        self.assertGreater(report["worst_gap"], 0.0)
        self.assertEqual(report["insensitive_betas"], [])


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


class FinalRoundWeightingTests(unittest.TestCase):
    """The organisers triple every payment in the last 20 Games; the Transactions do not change.

    Announced mid-tournament: "the final 20 of our 100 rounds will receive 3x weighting ...
    The weighted amounts will be reflected in the Games and Standings tabs. **The Transactions
    tab will remain unchanged.**"

    So from Game 81 the `/matrix` cell is three times the identity computed from the rows, and
    every cross-check in this repo compares exactly those two. Left alone,
    `replay_payoffs.snapshot` and `invert_fair_values.verify` would have called every one of
    those Games a mismatch and dropped the 20 Games carrying ~35 % of the weighted `t` out of
    `usable_games()`, the pooled counterfactual and every sweep.

    These tests exist because that path cannot be exercised until Game 81, which is precisely
    when it would be most expensive to discover it had been refactored away.
    """

    def test_a_tripled_cell_is_accepted(self) -> None:
        self.assertTrue(pt.cell_agrees(13_414.89, 13_414.89 * 3))
        self.assertTrue(pt.cell_agrees(-9_720.0, -9_720.0 * 3))

    def test_an_unweighted_cell_is_still_accepted(self) -> None:
        self.assertTrue(pt.cell_agrees(13_414.89, 13_414.89))

    def test_a_genuine_disagreement_is_still_rejected(self) -> None:
        """The guard must not become a rubber stamp: only 1x and 3x, nothing between."""
        self.assertFalse(pt.cell_agrees(13_414.89, 12_000.00))
        self.assertFalse(pt.cell_agrees(13_414.89, 13_414.89 * 2))
        self.assertFalse(pt.cell_agrees(13_414.89, 13_414.89 * 4))

    def test_a_zero_net_is_unaffected(self) -> None:
        self.assertTrue(pt.cell_agrees(0.0, 0.0))

    def test_the_weight_switches_at_the_announced_boundary(self) -> None:
        self.assertEqual(pt.game_weight(80), 1.0)
        self.assertEqual(pt.game_weight(81), 3.0)
        self.assertEqual(pt.game_weight(100), 3.0)
        self.assertEqual(len(pt.WEIGHTED_ROUNDS), 20)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
