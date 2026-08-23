"""The calibration layer, and above all the censored fit it is built on.

`turnbull()` is the only piece of new mathematics in the pricing path, and every number the
calibration produces is downstream of it. It is tested against the three cases where the NPMLE
has a known closed form -- exact data, nested censoring, and disjoint intervals -- so a wrong
answer shows up as a failing assertion rather than as a plausible-looking quantile.
"""

from __future__ import annotations

import math
import unittest

from src.pricing.calibration import (
    Calibration,
    MIN_STRATUM,
    Stratum,
    bucket_of,
    channel_key,
    stratum_of,
    turnbull,
)


def cdf(support, mass, x):
    return sum(m for p, m in zip(support, mass) if p <= x)


class TurnbullTest(unittest.TestCase):
    def test_exact_observations_reduce_to_the_empirical_cdf(self):
        """With no censoring the NPMLE *is* the empirical distribution. Nothing is lost."""
        points = [-1.0, -0.5, 0.0, 0.0, 0.5, 1.0]
        support, mass = turnbull([(p, p) for p in points])
        self.assertAlmostEqual(sum(mass), 1.0, places=9)
        for x in points:
            expected = sum(1 for p in points if p <= x) / len(points)
            self.assertAlmostEqual(cdf(support, mass, x), expected, places=6)

    def test_mass_sums_to_one_under_heavy_right_censoring(self):
        support, mass = turnbull([(0.0, math.inf)] * 5 + [(1.0, 1.0)] * 5)
        self.assertAlmostEqual(sum(mass), 1.0, places=9)

    def test_right_censored_mass_is_not_dragged_below_its_floor(self):
        """The fix the whole module exists for: `t >= t_lo` must not read as `t = t_lo`.

        Five observations known to be exactly -1, and five known only to be **at least +1**.
        A fit that drops the censored half puts the median at -1. A fit that honours the floor
        cannot put more than half the mass below zero, because five of the ten observations are
        provably above it.
        """
        support, mass = turnbull([(-1.0, -1.0)] * 5 + [(1.0, 4.0)] * 5)
        self.assertLessEqual(cdf(support, mass, 0.0), 0.5 + 1e-6)
        self.assertGreaterEqual(cdf(support, mass, 0.0), 0.5 - 1e-6)
        # and no mass may sit below the censored observations' proven floor except the exact ones
        self.assertAlmostEqual(cdf(support, mass, -1.0), 0.5, places=6)

    def test_disjoint_intervals_split_mass_evenly(self):
        """Two non-overlapping groups, equally sized: each must carry half the mass."""
        support, mass = turnbull([(0.0, 1.0)] * 4 + [(2.0, 3.0)] * 4)
        self.assertAlmostEqual(cdf(support, mass, 1.0), 0.5, places=6)
        self.assertAlmostEqual(sum(mass), 1.0, places=9)

    def test_empty_input_is_answerable(self):
        support, mass = turnbull([])
        self.assertEqual(support, [])
        self.assertEqual(mass, [])


class StratumTest(unittest.TestCase):
    def test_quantile_is_monotone_and_clamped_to_the_support(self):
        support, mass = turnbull([(float(i), float(i)) for i in range(10)])
        stratum = Stratum("s", tuple(support), tuple(mass), n=10, n_bounded=10)
        values = [stratum.quantile(q / 20) for q in range(21)]
        self.assertEqual(values, sorted(values))
        self.assertGreaterEqual(min(values), support[0])
        self.assertLessEqual(max(values), support[-1])

    def test_empty_stratum_is_the_identity(self):
        stratum = Stratum("empty")
        self.assertEqual(stratum.quantile(0.33), 0.0)
        self.assertEqual(stratum.bias, 1.0)


class StratificationTest(unittest.TestCase):
    def test_bucket_edges(self):
        self.assertEqual(bucket_of(10), "<50")
        self.assertEqual(bucket_of(50), "<50")       # edge is inclusive below
        self.assertEqual(bucket_of(50.01), "50-200")
        self.assertEqual(bucket_of(999), "400-1k")
        self.assertEqual(bucket_of(5000), ">1k")

    def test_channel_key_is_order_free_and_format_free(self):
        """The live log writes a list, the export writes a pipe-joined string. One key."""
        self.assertEqual(channel_key(["C:model", "B:memory"]), "B:memory|C:model")
        self.assertEqual(channel_key("B:memory|C:model"), "B:memory|C:model")
        self.assertEqual(channel_key([]), "none")
        self.assertEqual(channel_key(None), "none")

    def test_back_off_chain_is_most_specific_first(self):
        self.assertEqual(
            stratum_of(300, ["B:memory"]), ("B:memory@200-400", "B:memory", "*")
        )


class CalibrationTest(unittest.TestCase):
    def _rows(self, n, channel, t_hat, ratio, bounded=True):
        """`n` items whose settled `t` is `ratio * t_hat`, bounded or right-censored."""
        return [
            {
                "game_id": i,
                "t_hat": t_hat,
                "t_lo": t_hat * ratio * 0.99,
                "t_hi": t_hat * ratio * 1.01 if bounded else None,
                "channels": channel,
            }
            for i in range(n)
        ]

    def test_recovers_a_known_level_error(self):
        cal = Calibration.fit(self._rows(60, "B:memory", 100.0, 0.5))
        self.assertAlmostEqual(cal.correct(100.0, "B:memory"), 50.0, delta=1.0)

    def test_censored_observations_are_kept_not_dropped(self):
        """The regression that cost 39k-499k weighted: censored rows must reach the fit."""
        rows = self._rows(40, "C:model", 100.0, 2.0, bounded=False)
        cal = Calibration.fit(rows)
        self.assertEqual(cal.fitted_on, 40)
        stratum = cal.resolve(100.0, "C:model")
        self.assertEqual(stratum.n, 40)
        self.assertEqual(stratum.n_bounded, 0)
        self.assertAlmostEqual(stratum.censored_fraction, 1.0)
        # t >= 2 x t_hat on every observation, so the correction must move UP, never down.
        self.assertGreater(cal.correct(100.0, "C:model"), 100.0)

    def test_strata_below_the_floor_back_off_rather_than_answering_thinly(self):
        rows = self._rows(MIN_STRATUM * 2, "B:memory", 30.0, 0.5)   # all land in "<50"
        rows += self._rows(3, "B:memory", 5000.0, 0.5)              # ">1k", far too few
        cal = Calibration.fit(rows)
        self.assertEqual(cal.resolve(5000.0, "B:memory").name, "B:memory")

    def test_band_is_monotone_in_the_quantile(self):
        cal = Calibration.fit(
            [
                {"game_id": i, "t_hat": 100.0, "t_lo": 20.0 + i, "t_hi": 25.0 + i,
                 "channels": "C:model"}
                for i in range(60)
            ]
        )
        low, mid, high = cal.band(100.0, "C:model", (0.1, 0.5, 0.9))
        self.assertLessEqual(low, mid)
        self.assertLessEqual(mid, high)

    def test_round_trip_through_json(self):
        """`to_dict` rounds the log support to 6 dp, so the band survives to well under a cent.

        Exact equality is the wrong bar and asserting it would only invite someone to widen the
        stored precision for no reason: 1e-6 in log space is a relative error of 1e-6, which on
        the largest Line Item we have ever priced is a hundredth of a cent.
        """
        cal = Calibration.fit(self._rows(60, "B:memory", 100.0, 0.5))
        again = Calibration.from_dict(cal.to_dict())
        for before, after in zip(
            cal.band(100.0, "B:memory", (0.2, 0.5, 0.8)),
            again.band(100.0, "B:memory", (0.2, 0.5, 0.8)),
        ):
            self.assertAlmostEqual(before, after, places=3)

    def test_zero_floor_rows_are_refused(self):
        """`t_lo = 0` is consistent with any `t`; it is not an observation of the residual."""
        cal = Calibration.fit(
            [{"game_id": 1, "t_hat": 100.0, "t_lo": 0.0, "t_hi": None, "channels": "x"}]
        )
        self.assertEqual(cal.fitted_on, 0)

    def test_an_empty_calibration_is_the_identity(self):
        cal = Calibration()
        self.assertEqual(cal.correct(123.0, "anything"), 123.0)
        self.assertEqual(cal.band(123.0, "anything", (0.33,)), [123.0])


if __name__ == "__main__":
    unittest.main()
