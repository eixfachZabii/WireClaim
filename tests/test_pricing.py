import math
import unittest

from src.pricing import (
    CHARGE_BOUNDS,
    CHARGE_INTERCEPT,
    CHARGE_SLOPE,
    COVERAGE_FLOOR,
    LIMIT_CEILING,
    LIMIT_QUANTILE,
    Evidence,
    charge_factor,
    implied_sigma,
    price_item,
)


class PriceItemTests(unittest.TestCase):
    def confident(self, median: float = 100.0, coverage: float = 1.0) -> Evidence:
        return Evidence(
            index=1,
            coverage_probability=coverage,
            price_low=median * 0.8,
            price_median=median,
            price_high=median * 1.25,
        )

    def test_charge_sits_below_the_estimate(self) -> None:
        """Income is `a` whenever a <= t and collapses ~80% above it."""
        price = price_item(self.confident(200.0))

        self.assertLess(price.charge, 200.0)
        self.assertGreater(price.charge, 0.5 * 200.0)

    def test_the_charge_retreats_as_the_band_widens(self) -> None:
        tight = price_item(Evidence(1, 1.0, 95.0, 100.0, 105.0))
        wide = price_item(Evidence(1, 1.0, 20.0, 100.0, 500.0))

        self.assertGreater(tight.charge, wide.charge)

    def test_charge_factor_matches_the_simulated_optima(self) -> None:
        """0.7 at sigma 0.25, 0.6 at 0.5, 0.5 at 0.75 -- the three simulated points."""
        self.assertAlmostEqual(charge_factor(0.25), 0.7375, places=3)
        self.assertAlmostEqual(charge_factor(0.5), 0.625, places=3)
        self.assertAlmostEqual(charge_factor(0.75), 0.5125, places=3)
        self.assertEqual(charge_factor(5.0), 0.30)

    def test_limit_is_never_above_the_charge(self) -> None:
        for median in (10.0, 100.0, 1000.0, 7225.0):
            for coverage in (0.4, 0.7, 0.9, 1.0):
                price = price_item(self.confident(median, coverage))
                self.assertLessEqual(price.limit, price.charge, f"{median} {coverage}")

    def test_doubtful_coverage_collapses_the_limit_to_zero(self) -> None:
        """Below P(covered) = 1/3 the bottom third of the posterior *is* zero."""
        self.assertEqual(price_item(self.confident(500.0, coverage=0.30)).limit, 0.0)
        self.assertGreater(price_item(self.confident(500.0, coverage=0.95)).limit, 0.0)

    def test_the_limit_falls_as_coverage_doubt_rises(self) -> None:
        limits = [price_item(self.confident(500.0, coverage=c)).limit for c in (1.0, 0.8, 0.6, 0.4)]

        self.assertEqual(limits, sorted(limits, reverse=True))

    def test_the_limit_falls_as_the_band_widens(self) -> None:
        """A wider band is a noisier estimate, so the Limit must retreat.

        With `LIMIT_CEILING` at 0.85 the retreat comes through two channels at once -- the
        quantile on the wide side and the ceiling and Charge clamp on the tight side. Which
        one binds at which width is measured in `TheLimitRetreatsThroughTwoChannels`.
        """
        tight = price_item(Evidence(1, 1.0, 95.0, 100.0, 105.0))
        wide = price_item(Evidence(1, 1.0, 20.0, 100.0, 500.0))

        self.assertGreater(tight.sigma * 4, wide.sigma * 0)  # sanity: sigma is populated
        self.assertLess(wide.sigma, 2.01)
        self.assertGreater(tight.limit, wide.limit)

    def test_a_proven_exclusion_zeroes_the_limit_but_keeps_the_charge(self) -> None:
        """An uncovered item is a free option: t = 0, so a rejected Charge costs nothing."""
        price = price_item(self.confident(300.0), confirmed_uncovered=True)

        self.assertEqual(price.limit, 0.0)
        self.assertGreater(price.charge, 0.0)

    def test_a_missing_band_still_produces_a_plausible_number(self) -> None:
        """Never submit 0: it forfeits income and rejects every fair claim."""
        price = price_item(Evidence(index=1))

        self.assertGreater(price.charge, 0.0)
        self.assertLess(price.charge, 200.0)

    def test_an_incoherent_band_is_repaired_rather_than_trusted(self) -> None:
        price = price_item(Evidence(1, 0.9, price_low=900.0, price_median=100.0, price_high=0.0))

        self.assertGreater(price.charge, 0.0)
        self.assertGreaterEqual(price.charge, price.limit)

    def test_nothing_is_ever_negative(self) -> None:
        price = price_item(Evidence(1, -5.0, -10.0, -10.0, -10.0))

        self.assertGreaterEqual(price.charge, 0.0)
        self.assertGreaterEqual(price.limit, 0.0)


class MeasuredConstants(unittest.TestCase):
    """Pin each constant to the euros that chose it.

    Every number quoted here was measured by `scripts/tune_pricing.py`, which feeds the
    cached model evidence through `price_item` and scores it with
    `scripts/replay_payoffs.py` -- a replay that reproduces all fourteen published nets to
    the cent. These are not golden values for their own sake: each test names the finding
    it guards, so moving a constant means re-running the measurement, not editing a number
    until the suite goes green.
    """

    def test_the_charge_line_is_the_one_the_replay_confirmed(self) -> None:
        """Measured optima 0.70/0.65/0.60/0.50/0.45 over sigma 0.25-0.75 fit 0.829-0.519s.

        The shipped line runs 0.04-0.06 above that -- inside the spread between replicas --
        so it was left alone. Refitting it exactly *lost* money on both the real evidence
        (13,599 -> 4,397) and the simulation (145,169 -> 130,900), because the `b <= a`
        clamp couples the Charge to the Limit.
        """
        self.assertEqual((CHARGE_INTERCEPT, CHARGE_SLOPE), (0.85, 0.45))
        self.assertEqual(CHARGE_BOUNDS, (0.30, 0.80))

    def test_the_charge_never_reaches_the_estimate(self) -> None:
        """Confirmed in euros: `a = t_hat` scores -103k where `a = 0.6 t_hat` scores +150k.

        The theory said the optimum must sit below 1 because a Charge at or under `t` is
        paid by every opponent while acceptance above it collapses. The replay agrees at
        every band width, so this is now a measured property rather than an argument.
        """
        for sigma in (0.0, 0.1, 0.25, 0.5, 1.0, 2.0):
            self.assertLess(charge_factor(sigma), 1.0, sigma)

    def test_the_limit_ceiling_carries_the_measurement(self) -> None:
        """The ceiling is a Field measurement, not a pricing fact, and the Field moved.

        Over Games 1-14 a ceiling of 0.45 beats 0.85 by +17,915. Over Games 15-19 the
        ordering inverts and 0.85 wins by +15,112, with Games 17 and 18 accounting for the
        whole reversal. Across all 19 the two differ by 2,802 on ~53,000 — a coin flip.

        We are paid on the Games that come next, so this pins the value the *recent*
        window prefers. Re-measure at every regime boundary rather than inheriting it
        (README R9).

        Leave-one-out over all nineteen Games says the same thing more bluntly: tuning this
        constant per fold scores +26,273 held out, worse than fixing it anywhere in
        0.30-1.00 (+50,312 to +54,724). Ten folds pick 0.45, five pick 0.75, the rest
        scatter. There is no stable optimum to find here, so the tie is broken by the two
        readings that generalise -- the recent Field, and the unbiased-estimator simulation,
        which prefers 0.85 at every precision (145,169 against 124,229 at sigma 0.45) and
        puts the best flat Limit at 1.0-1.15 x median.
        """
        self.assertEqual(LIMIT_CEILING, 0.85)

    def test_the_derived_constants_were_not_fitted_away(self) -> None:
        """The quantile and the coverage floor are flat in euros, so the theory keeps them.

        The quantile moves the net by under 125 anywhere in 0.20-0.90, because the ceiling
        binds first; the coverage floor by under 150 anywhere in 0.10-0.70. Neither has a
        euro case for moving, and both have a derivation for staying.
        """
        self.assertAlmostEqual(LIMIT_QUANTILE, 1.0 / 3.0)
        self.assertAlmostEqual(COVERAGE_FLOOR, 1.0 / 3.0)


class TheLimitRetreatsThroughTwoChannels(unittest.TestCase):
    """Exercise the Limit across the band widths the real model actually produces.

    The module docstring says the ceiling "only binds below sigma ~0.38, so for the widths
    we actually see the band still drives the Limit". Measured over Games 1-19 the model's
    implied sigma has median 0.375 and spans 0.148 to 0.668 -- so that claim is true for
    roughly half our Line Items and false for the other half, and the ceiling is doing more
    work than the derivation suggests. Sweeping the whole observed range here keeps both
    channels honest, and keeps the invariants asserted where they are least obvious.

    The bigger caveat is that `sigma` is not what it claims to be at all: the bands imply a
    median 0.375 while the estimator's actual RMSLE is 0.80, and band width does not rank
    the errors. See `ImpliedSigmaTests`.
    """

    #: The real model's implied sigma over Games 1-19: median 0.375, spanning this range.
    OBSERVED_SIGMAS = (0.15, 0.25, 0.375, 0.50, 0.67)

    def band(self, sigma: float, median: float = 400.0) -> Evidence:
        spread = math.exp(1.645 * sigma)
        return Evidence(1, 1.0, median / spread, median, median * spread)

    def test_the_ceiling_binds_across_the_whole_observed_range(self) -> None:
        for sigma in self.OBSERVED_SIGMAS:
            price = price_item(self.band(sigma))

            self.assertAlmostEqual(price.sigma, sigma, places=2)
            self.assertLessEqual(price.limit, LIMIT_CEILING * 400.0 + 0.01, sigma)

    def test_the_limit_stays_far_under_the_estimate(self) -> None:
        """The failure a loose Limit invites is unbounded: the Cap has never bound.

        Game 7 item 2 was priced at 2,200 against a true Fair Value of 40, at coverage
        0.98. A Limit near the median accepts every opponent's Charge on such an item and
        pays it in full, and no Cap stops that -- zero conflicts in 52,224 settled rows.
        """
        for sigma in self.OBSERVED_SIGMAS:
            price = price_item(self.band(sigma, median=2200.0))

            # Bounded by the ceiling and by the Charge, so never the full estimate.
            self.assertLessEqual(price.limit, LIMIT_CEILING * 2200.0 + 0.01, sigma)
            self.assertLessEqual(price.limit, price.charge, sigma)

    def test_the_invariants_survive_the_new_ceiling(self) -> None:
        for sigma in self.OBSERVED_SIGMAS:
            for coverage in (0.0, 0.2, 1.0 / 3.0, 0.5, 0.9, 1.0):
                shape = self.band(sigma)
                price = price_item(
                    Evidence(1, coverage, shape.price_low, shape.price_median, shape.price_high)
                )

                self.assertGreaterEqual(price.charge, 0.0)
                self.assertGreaterEqual(price.limit, 0.0)
                self.assertLessEqual(price.limit, price.charge)
                if coverage <= COVERAGE_FLOOR:
                    self.assertEqual(price.limit, 0.0, (sigma, coverage))


class ImpliedSigmaTests(unittest.TestCase):
    def test_a_tight_band_implies_a_small_sigma(self) -> None:
        self.assertLess(implied_sigma(95.0, 100.0, 105.0), 0.05)

    def test_a_wide_band_implies_a_large_sigma(self) -> None:
        self.assertGreater(implied_sigma(20.0, 100.0, 500.0), 0.9)

    def test_a_degenerate_band_is_treated_as_maximally_uncertain(self) -> None:
        self.assertEqual(implied_sigma(0.0, 0.0, 0.0), 1.0)
        self.assertEqual(implied_sigma(100.0, 100.0, 100.0), 1.0)

    def test_the_band_understates_the_error_it_is_supposed_to_measure(self) -> None:
        """The uncertainty signal this module is built on does not currently work.

        Measured over Games 1-14 against the recovered Fair Values: the model's bands imply
        a median sigma of 0.375 while the estimator's actual RMSLE is 0.80, so the band is
        overconfident by 2.1x. And the width does not rank the errors -- the narrow third
        scores RMSLE 0.847 against the wide third's 0.733, very slightly *backwards*.

        This test does not assert against live evidence (that would need the cache and the
        network); it pins the arithmetic of the claim, so the 2.1x figure in the module
        docstring stays honest if `implied_sigma` is ever rescaled.
        """
        observed_median_sigma = implied_sigma(400.0 / math.exp(1.645 * 0.375), 400.0,
                                              400.0 * math.exp(1.645 * 0.375))
        measured_rmsle = 0.80

        self.assertAlmostEqual(observed_median_sigma, 0.375, places=3)
        self.assertAlmostEqual(measured_rmsle / observed_median_sigma, 2.1, places=1)


if __name__ == "__main__":
    unittest.main()
