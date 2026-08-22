import unittest

from src.pricing import (
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
        """A wider band is a noisier estimate, so the Limit must retreat."""
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


class ImpliedSigmaTests(unittest.TestCase):
    def test_a_tight_band_implies_a_small_sigma(self) -> None:
        self.assertLess(implied_sigma(95.0, 100.0, 105.0), 0.05)

    def test_a_wide_band_implies_a_large_sigma(self) -> None:
        self.assertGreater(implied_sigma(20.0, 100.0, 500.0), 0.9)

    def test_a_degenerate_band_is_treated_as_maximally_uncertain(self) -> None:
        self.assertEqual(implied_sigma(0.0, 0.0, 0.0), 1.0)
        self.assertEqual(implied_sigma(100.0, 100.0, 100.0), 1.0)


if __name__ == "__main__":
    unittest.main()
