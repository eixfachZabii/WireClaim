import math
import unittest

from src.pricing.engine import (
    BIG_ITEM_CHARGE_SCALE,
    BIG_ITEM_THRESHOLD,
    CHARGE_BOUNDS,
    LIMIT_CAP,
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

    def test_a_memory_backed_item_gets_a_looser_ceiling(self) -> None:
        """Channel B's error is measured at half the model's, so its Limit may sit higher.

        Worth +40,791 over 37 Games with all eight fold cells positive, and 7.53 fair
        Charges accepted for every Overcharge let in. See `LIMIT_CEILING_MEMORY`.
        """
        evidence = self.confident(1000.0)

        model_only = price_item(evidence)
        memory = price_item(evidence, memory_backed=True)

        self.assertGreater(memory.limit, model_only.limit)

    def test_the_looser_ceiling_moves_the_limit_and_nothing_else(self) -> None:
        """It is a Limit-side rule. A Charge that moved with the channel would be a
        conditional Charge rule, and every one of those failed out of sample."""
        evidence = self.confident(1000.0)

        self.assertEqual(
            price_item(evidence).charge,
            price_item(evidence, memory_backed=True).charge,
        )

    def test_a_memory_hit_never_resurrects_the_limit_on_an_uncovered_item(self) -> None:
        """A proven exclusion outranks the channel. `t = 0`, so any Limit above zero is a
        pure loss -- but the Charge stays, because a rejected Overcharge is free (R6c)."""
        price = price_item(
            self.confident(1000.0), confirmed_uncovered=True, memory_backed=True
        )

        self.assertEqual(price.limit, 0.0)
        self.assertGreater(price.charge, 0.0)

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
        """At P(covered) <= 1 - q = 2/3 the bottom third of the posterior *is* zero.

        The threshold is `1 - LIMIT_QUANTILE`, not `LIMIT_QUANTILE`: the posterior carries
        mass `1 - covered` at zero, so that mass alone fills the bottom third as soon as
        `1 - covered >= q`. Coverage of 0.60 is therefore a collapse, which is the case the
        old floor of 1/3 got right only by accident -- via the -8 clamp in
        `_normal_quantile` -- and now gets right by construction. Worth +21 euros over 23
        Games, i.e. nothing; shipped for the exactness, not the money.
        """
        self.assertEqual(price_item(self.confident(500.0, coverage=0.30)).limit, 0.0)
        self.assertEqual(price_item(self.confident(500.0, coverage=0.60)).limit, 0.0)
        self.assertEqual(price_item(self.confident(500.0, coverage=2.0 / 3.0)).limit, 0.0)
        self.assertGreater(price_item(self.confident(500.0, coverage=0.95)).limit, 0.0)

    def test_the_limit_falls_as_coverage_doubt_rises(self) -> None:
        limits = [price_item(self.confident(500.0, coverage=c)).limit for c in (1.0, 0.8, 0.6, 0.4)]

        self.assertEqual(limits, sorted(limits, reverse=True))

    def test_a_wider_band_retreats_through_the_charge_not_the_limit(self) -> None:
        """A wider band is a noisier estimate. Which number retreats changed at Game 24.

        This test used to assert that the Limit falls as the band widens. At a ceiling of
        0.85 that was true, because the 1/3 quantile sat under the ceiling on wide bands.
        At the measured 0.30 the ceiling binds at *every* width the real model produces --
        the quantile only drops below 0.30 x median above sigma ~2.8, which never happens --
        so the Limit is a flat fraction of the median and the band acts on the Charge alone.

        That is a real loss of a signal, and it is worth naming rather than papering over:
        the band was measured to be uncalibrated anyway (implied median sigma 0.375 against
        an actual RMSLE of 0.80, and the width ranks the errors slightly *backwards* -- see
        `ImpliedSigmaTests`), so a Limit that ignores it is not obviously worse, and in euros
        it is 35,726 better over 23 Games. If the band is ever fixed, the ceiling should rise
        and this channel comes back; re-run `scripts/accept_limit_sweep.py recommend`.
        """
        tight = price_item(Evidence(1, 1.0, 95.0, 100.0, 105.0))
        wide = price_item(Evidence(1, 1.0, 20.0, 100.0, 500.0))

        self.assertLess(wide.sigma, 2.01)
        self.assertGreater(wide.sigma, tight.sigma)
        # The Charge still retreats with the band; that channel is untouched.
        self.assertGreater(tight.charge, wide.charge)
        # And so does the Limit, again. At a ceiling of 0.30 this was flat -- the ceiling
        # bound at every width we see, so the band could not move the Limit at all. At 0.45
        # the quantile binds on the narrow bands again, which is the point of pairing the
        # ceiling with an absolute cap: the cap bounds the disaster, so the multiplicative
        # term is free to sit where the posterior actually wants it.
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
        """The ceiling has been argued in both directions, and both were partly artefacts.

        Games 1-14 preferred 0.45 over 0.85; Games 15-19 inverted it; Games 20-24 reversed the
        reversal and 0.30 shipped. Then `scripts/penalty_audit.py cliff` decomposed the step
        that justified 0.30 -- 0.35 to 0.40 costing 17,492 -- and found **Game 22 alone
        supplies -19,892 of it while the other five Games prefer the looser ceiling**. At 0.01
        resolution the step is at 0.37 to 0.38, because one Line Item worth under 245.70 was
        priced at a median of 5,400 and ten opponents Charged exactly 2,000.00: 0.37 rejects
        all ten, 0.38 buys all ten. A live constant was set by one item and one round number.

        With `LIMIT_CAP` bounding the disaster the pair was re-swept on fresh evidence:

            config                 all 27     21-27     28-29
            0.30, no cap           83,030    15,300        84
            0.45 + cap             93,951    23,590       138   <- this
            0.70 + cap            101,300    23,459    -1,261
            0.70, no cap           51,138   -23,396   -35,261

        0.45 is the only setting positive on all three windows. The last row is why the cap
        exists rather than the ceiling being loosened on its own.
        """
        self.assertEqual(LIMIT_CEILING, 0.45)


    def test_the_derived_constants_were_not_fitted_away(self) -> None:
        """The quantile stays where the theory put it; the floor moves to where it implies.

        The quantile is flat in euros -- under 125 over Games 1-14 and 2,600 over all 23,
        with every value above 0.30 worse than the derived 1/3 -- so it keeps its derivation
        rather than a sweep's argmax.

        The coverage floor is equally flat (137 euros over all 23 Games) but it was *wrong*:
        the bottom `q` of a posterior carrying mass `1 - covered` at zero is zero exactly
        when `covered <= 1 - q`, which is 2/3, not 1/3. The old value only reached the right
        answer through the -8 clamp inside `_normal_quantile`, leaving a Limit of
        `median * exp(-8 * sigma)` where the derivation says zero. Making it exact is worth
        +21 euros over 23 Games: shipped because it is derived, not because it pays.

        Re-examined at Game 26, because the floor makes the Limit discontinuous -- an item
        called 60% covered gets a Limit of exactly zero, and 93 of the 316 settled Line Items
        are collapsed that way -- so it was a live candidate for "the ceiling is fine and this
        cliff is the real cost". It is not. Sweeping the *threshold* cannot answer the
        question (below the floor the quantile already saturates at -8 sigma, so a lower
        threshold buys a rounding error, not a Limit, which is why that sweep is flat).
        Replacing the *rule* answers it: removing the collapse entirely is worth **-1,049
        over 26 Games and -57 over the on-policy six**, and a continuous
        `b = covered * ceiling * median` is worth -426. It recovers 47 euros of the 113,238
        penalty on Games 21-26, because `0.30 * median` is below the Field's Charges on those
        items anyway. The cliff pays for itself and is derived; it stays.
        """
        self.assertAlmostEqual(LIMIT_QUANTILE, 1.0 / 3.0)
        self.assertAlmostEqual(COVERAGE_FLOOR, 2.0 / 3.0)
        self.assertAlmostEqual(COVERAGE_FLOOR, 1.0 - LIMIT_QUANTILE)

    def test_two_thirds_of_a_penalty_is_money_we_owed_anyway(self) -> None:
        """The arithmetic that settles "our penalties prove the Limit is too strict".

        Games 21-26 paid 108,793 in wrongful-rejection penalties against 145,564 of income,
        which reads as a Limit set far too low. It is not, and the reason is a payoff-table
        identity rather than a measurement: rejecting a fair Charge costs `1.5a` while
        accepting the same Charge costs `a`, so a Limit that avoided the rejection would
        still have paid `2/3` of what the penalty cost. Only the `0.5a` surcharge -- one third
        -- is money strictness wasted.

        Confirmed against a per-item oracle Limit `b = t` in `scripts/limit_audit.py
        avoidable`, which is the tightest possible bound: the oracle's reviewer cost over
        those six Games is 81,127 against our 117,918, i.e. 36,791 of headroom, of which
        36,264 is this surcharge and 526 is Overcharges we accepted. The oracle needs `t`
        per item, so none of it is reachable by moving `LIMIT_CEILING`.

        This test pins the identity, not the euros, so that the 2/3 quoted throughout
        `src/pricing/engine.py` cannot drift if the payoff table is ever restated.
        """
        charge = 1_000.0
        cost_of_rejecting_a_fair_charge = 1.5 * charge
        cost_of_accepting_it = charge

        avoidable = cost_of_rejecting_a_fair_charge - cost_of_accepting_it

        self.assertAlmostEqual(avoidable / cost_of_rejecting_a_fair_charge, 1.0 / 3.0)
        self.assertAlmostEqual(cost_of_accepting_it / cost_of_rejecting_a_fair_charge, 2.0 / 3.0)
        # The measured split of the six on-policy Games, to the euro.
        penalty = 108_793.0
        self.assertAlmostEqual(penalty * 2.0 / 3.0, 72_528.67, places=2)
        self.assertAlmostEqual(penalty / 3.0, 36_264.33, places=2)


class TheCeilingIsWhatBinds(unittest.TestCase):
    """Exercise the Limit across the band widths the real model actually produces.

    This class was called `TheLimitRetreatsThroughTwoChannels`, after a docstring claiming
    the ceiling "only binds below sigma ~0.38, so for the widths we actually see the band
    still drives the Limit". Measured over Games 1-19 the model's implied sigma has median
    0.375 and spans 0.148 to 0.668, so the ceiling was already doing more of the work than
    the derivation suggested. At the ceiling measured over Games 1-24 (0.30) there is only
    one channel left: the ceiling binds at every width in that range and well beyond it.

    So the name is now the finding. The tests below pin it, and pin the invariants at the
    widths where they are least obvious -- `b <= a`, nothing negative, and the Limit
    collapsing to exactly zero once coverage is doubtful.

    The bigger caveat is that `sigma` is not what it claims to be at all: the bands imply a
    median 0.375 while the estimator's actual RMSLE is 0.80, and band width does not rank
    the errors. See `ImpliedSigmaTests`. A Limit that ignores an uncalibrated width is not a
    loss of information so much as a refusal to trust a number that has not earned it.
    """

    #: The real model's implied sigma over Games 1-19: median 0.375, spanning this range.
    OBSERVED_SIGMAS = (0.15, 0.25, 0.375, 0.50, 0.67)

    def band(self, sigma: float, median: float = 400.0) -> Evidence:
        spread = math.exp(1.645 * sigma)
        return Evidence(1, 1.0, median / spread, median, median * spread)

    def test_the_ceiling_binds_across_the_whole_observed_range(self) -> None:
        """Not merely "binds" -- it *is* the Limit at every width the model produces."""
        for sigma in self.OBSERVED_SIGMAS:
            price = price_item(self.band(sigma))

            self.assertAlmostEqual(price.sigma, sigma, places=2)
            self.assertAlmostEqual(price.limit, LIMIT_CEILING * 400.0, places=2, msg=str(sigma))

    def test_the_limit_stays_far_under_the_estimate(self) -> None:
        """The failure a loose Limit invites: the Cap has never bound in 52,224 rows.

        Game 7 item 2 was priced at 2,200 against a true Fair Value of 40, at coverage
        0.98. A Limit near the median accepts every opponent's Charge on such an item and
        pays it in full, and no Cap stops that -- zero conflicts in 52,224 settled rows.

        Measured over all 23 scoreable Games, that risk is realised, but not in the shape
        the argument assumed. It is not one catastrophic row: the worst single accepted
        Overcharge anywhere in the replay is 2,573 euros (G24 item 3), and it is the same
        2,573 whether the Limit sits at 0.30 x median or at the full median. What the loose
        Limit actually buys is *volume* -- 121,927 euros of accepted Overcharges across the
        Field at a ceiling of 0.85 against 12,189 at 0.30. So the honest version of the
        asymmetry argument is aggregate, not tail: many moderate Overcharges, each one
        cheap, and no Cap to stop any of them.

        Still true with Games 25-26 added (127,397 at 0.85 against 12,168 at 0.30 over all
        26), and it is what makes the Games 21-26 penalties the cheaper of the two evils:
        loosening there recovers 52,272 of penalty and buys 54,969 of Overcharges to do it.
        """
        for sigma in self.OBSERVED_SIGMAS:
            price = price_item(self.band(sigma, median=2200.0))

            # Bounded by the ceiling and by the Charge, so never the full estimate.
            self.assertLessEqual(price.limit, LIMIT_CEILING * 2200.0 + 0.01, sigma)
            self.assertLessEqual(price.limit, price.charge, sigma)

    def test_the_invariants_survive_the_new_ceiling(self) -> None:
        for sigma in self.OBSERVED_SIGMAS:
            for coverage in (0.0, 0.2, 1.0 / 3.0, 0.5, 0.6, 2.0 / 3.0, 0.9, 1.0):
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


class TheChargeIsUnconditional(unittest.TestCase):
    """Guard the negative result behind `CHARGE_INTERCEPT`: no conditional Charge shipped.

    `scripts/charge_buckets.py` joined the evidence available at decision time -- sigma, the
    channels that spoke, the coverage probability, the magnitude of the estimate, the invoice
    unit and the quantity -- to the recovered Fair Value over all 27 settled Games, and asked
    whether the unrecoverable Charges concentrate anywhere a rule could see. They do (the
    channel, and sigma with the *wrong* sign), and no conditioning on it earns a euro: every
    downward multiplier loses on both windows, the one that pays in sample is jagged in its
    own parameter, and the honest held-out split gives up 19,092 in a fold. The full table is
    in the note above these constants.

    The tests below are the machine-checkable half of that. They exist because the *next*
    person to read the complaint "our median a/t is 0.99" will reach for exactly one of these
    conditionings, and a failing test with the measurement in its docstring is the cheapest
    way to hand them the answer.
    """

    def band(self, median: float, *, width: float = 1.25, coverage: float = 1.0) -> Evidence:
        return Evidence(
            index=1,
            coverage_probability=coverage,
            price_low=median / width,
            price_median=median,
            price_high=median * width,
        )

    def test_the_charge_is_scale_free_in_the_estimate(self) -> None:
        """No `t_hat` bucket. Conditioning on magnitude was measured and it loses money.

        `t_hat >= 500` carries 57,955 of the 76,642 euros of forgone income, which is the
        most tempting cell in the whole bucket table -- and only 8% of that bucket's
        recoverable income against 4% for the middle bucket, i.e. mostly a statement that
        expensive items carry more euros. Discounting it scores -144,502 (x0.6), -43,584
        (x0.8) and -102 (x0.9) over 27 Games and is negative on Games 21-27 at every value.
        Doubling the estimate must therefore double both numbers exactly -- everywhere
        below `BIG_ITEM_THRESHOLD`. The one exception is measured in the opposite
        direction to everything above: those figures are all *downward* multipliers on
        `t_hat >= 500`, and re-running that exact cell today still loses (-17,033 at 1.25).
        `BIG_ITEM_CHARGE_SCALE` used to raise the Charge on `t_hat >= 1,000` instead, on
        the argument that two thirds of our estimates there are already above `t` and
        earning nothing. It is **1.0 as of Game 63**: income above `t` is not nothing (a
        wrongful rejection still owes the issuer the full Charge, so a fair Charge is paid
        by all 16 opponents and an Overcharge by about 3), and raising the Charge moved
        nine Line Items across `t` for -79,240. See the constant's own note. The branch
        below is kept, and multiplies by the constant rather than by a literal, so this
        test states the invariant for whatever value that constant next takes.
        """
        for median in (10.0, 49.0, 51.0, 499.0, 501.0, 999.0):
            one = price_item(self.band(median))
            two = price_item(self.band(median * 2))
            # delta rather than places: both numbers are rounded to the cent.
            expected = one.charge * 2
            if median * 2 >= BIG_ITEM_THRESHOLD:
                expected *= BIG_ITEM_CHARGE_SCALE
            self.assertAlmostEqual(two.charge, expected, delta=0.02, msg=str(median))

    def test_the_limit_is_deliberately_not_scale_free(self) -> None:
        """`LIMIT_CAP` breaks the scaling on purpose, and that is the whole point of it.

        A multiplicative ceiling cannot bound what we pay, because it is a multiple of the
        number that broke: when the estimate explodes the ceiling explodes with it. Game 29
        priced a Line Item worth under 57.30 at a median of 7,138, thirteen opponents Charged
        exactly 2,000.00, and a Limit of 2,142 accepted all thirteen for 24,157 of pure loss.
        An absolute cap is the only term in the rule that does not scale with the estimate.
        """
        small = price_item(self.band(200.0))
        huge = price_item(self.band(20_000.0))

        # delta scaled by the factor: both numbers are rounded to the cent first.
        self.assertAlmostEqual(
            huge.charge, small.charge * 100 * BIG_ITEM_CHARGE_SCALE, delta=1.0
        )
        self.assertLess(huge.limit, small.limit * 100)
        self.assertLessEqual(huge.limit, LIMIT_CAP + 0.01)

    def test_the_charge_reads_only_the_band(self) -> None:
        """The Charge is a function of the band alone -- not of coverage, not of a channel.

        Coverage moves the Limit and must not move the Charge: an uncovered item has `t = 0`,
        so a rejected Overcharge costs nothing and shading for doubt forfeits guaranteed
        income (R6c). Measured as well as derived: discounting the items the model calls less
        than 90% covered scores -49,562 (x0.6) to -863 (x0.9) over 27 Games, negative in both
        windows. 98 of our 135 unrecoverable Charges are on Line Items nobody was ever owed
        money for, and all 98 are free.
        """
        charges = {
            price_item(self.band(300.0, coverage=coverage)).charge
            for coverage in (0.05, 0.2, 0.5, 0.66, 0.7, 0.9, 1.0)
        }

        self.assertEqual(len(charges), 1, charges)

    def test_the_sigma_slope_still_points_the_way_it_was_fitted(self) -> None:
        """A wider band still charges less -- deliberately, and now against a measurement.

        This is the constant the measurement argues with rather than for. On the 217 Line
        Items with a recoverable positive Fair Value, the *narrow* sigma tercile over-charges
        on 20% of items and forfeits 12% of its recoverable income, against 16% and 4% for
        the wide tercile: the ordering `CHARGE_SLOPE` assumes is backwards, which is the euro
        version of the RMSLE result above (0.847 narrow, 0.733 wide).

        Removing the ordering pays in sample -- a flat factor beats the level-matched line
        `(L + 0.17) - 0.45 * sigma` in six of seven pairs on the record and six of seven on
        Games 21-27 -- but the flat level has to be chosen on the non-monotone Field surface
        (-18,449 at 0.60, +38,922 at 0.69, +6,764 at 0.80) and it fails the held-out split by
        8,363. Inverting the sign is worse: `0.55 + 0.45 * sigma` scores -10,830 on Games
        21-27. So the slope stays, and this test records why it is not evidence of anything
        except that nobody has fixed the band yet.
        """
        self.assertEqual(CHARGE_SLOPE, 0.45)
        self.assertGreater(charge_factor(0.2), charge_factor(0.6))

    def test_a_negative_slope_could_not_even_be_measured_here(self) -> None:
        """Why the sweep over `CHARGE_SLOPE` reads flat below zero rather than falling.

        `CHARGE_BOUNDS` caps the factor at 0.80, and `CHARGE_INTERCEPT` is 0.85, so every
        negative slope collapses onto `slope = 0` on the sigmas we actually see. The replay
        agrees to the euro: slope -0.45, -0.225 and 0.0 all score +178,063 over 27 Games.
        Anyone testing "discount the narrow bands" has to move the intercept too -- see the
        `inverted` rows in `charge_buckets.py rules`.
        """
        low, high = CHARGE_BOUNDS
        for slope in (-0.45, -0.225, 0.0):
            for sigma in (0.0, 0.1, 0.2, 0.35, 0.5, 1.0):
                clamped = min(max(CHARGE_INTERCEPT - slope * sigma, low), high)
                self.assertEqual(clamped, high, (slope, sigma))


if __name__ == "__main__":
    unittest.main()
