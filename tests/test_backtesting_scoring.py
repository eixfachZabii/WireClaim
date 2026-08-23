import unittest

from backtesting.models import (
    CapEstimate,
    ChargeEstimate,
    FairValueEstimate,
    HistoricalGame,
    HistoricalItem,
    Interval,
    LimitEstimate,
    Submission,
    TeamDecision,
)
from backtesting.scoring import issuer_payoff, reconstructed_submission, reviewer_cost, score_game


class BacktestingScoringTests(unittest.TestCase):
    def test_payoff_table_enforces_the_cap(self) -> None:
        self.assertEqual(issuer_payoff(100, 110, 100, 2000), 100)
        self.assertEqual(issuer_payoff(100, 90, 100, 2000), 100)
        self.assertEqual(issuer_payoff(3000, 4000, 100, 2000), 2000)
        self.assertEqual(issuer_payoff(3000, 100, 100, 2000), 0)
        self.assertEqual(reviewer_cost(100, 90, 100, 2000), 150)

    def test_score_reports_an_envelope_when_the_opponent_limit_is_unknown(self) -> None:
        decisions = {
            "Bin busy": TeamDecision(
                "Bin busy",
                ChargeEstimate(Interval.point(100), "exact"),
                LimitEstimate(Interval.point(100)),
            ),
            "Other": TeamDecision(
                "Other",
                ChargeEstimate(Interval.point(100), "exact"),
                LimitEstimate(Interval(50, 150)),
            ),
        }
        item = HistoricalItem(
            1,
            FairValueEstimate(Interval.point(80)),
            CapEstimate(2000),
            decisions,
        )
        game = HistoricalGame(1, ("Bin busy", "Other"), {1: item}, (), {"Bin busy": 0.0})

        score = score_game(game, {1: Submission(100, 90)})

        self.assertEqual(score.net.lower, 0.0)
        self.assertEqual(score.net.upper, 100.0)
        self.assertLessEqual(score.net.lower, score.net.midpoint)
        self.assertLessEqual(score.net.midpoint, score.net.upper)
        self.assertEqual(score.ambiguity.opponent_limits, 1)

    def test_right_censored_historical_charge_remains_above_fair_value(self) -> None:
        decisions = {
            "Bin busy": TeamDecision("Bin busy", ChargeEstimate(Interval.point(0), "zero"), LimitEstimate(Interval.point(0))),
            "Other": TeamDecision("Other", ChargeEstimate(Interval(50, None, low_strict=True), "right_censored"), LimitEstimate(Interval.point(0))),
        }
        item = HistoricalItem(1, FairValueEstimate(Interval(50, 100)), CapEstimate(2000), decisions)
        game = HistoricalGame(1, ("Bin busy", "Other"), {1: item}, (), {"Bin busy": 0.0})

        scored = score_game(game, {1: Submission(10, 0)})

        self.assertEqual(scored.cost.lower, 0.0)
        self.assertEqual(scored.cost.midpoint, 0.0)
        self.assertEqual(scored.cost.upper, 0.0)

    def test_reconstructed_submission_uses_the_identified_representatives(self) -> None:
        decisions = {
            "Bin busy": TeamDecision("Bin busy", ChargeEstimate(Interval.point(100), "exact"), LimitEstimate(Interval(80, 120))),
            "Other": TeamDecision("Other", ChargeEstimate(Interval.point(100), "exact"), LimitEstimate(Interval.point(100))),
        }
        item = HistoricalItem(1, FairValueEstimate(Interval.point(100)), CapEstimate(2000), decisions)
        game = HistoricalGame(1, ("Bin busy", "Other"), {1: item}, (), {"Bin busy": 0.0})

        submission = reconstructed_submission(game)

        self.assertEqual(submission, {1: Submission(100, 100)})

    def test_missing_item_is_scored_as_tournament_default_and_labelled(self) -> None:
        decisions = {
            "Bin busy": TeamDecision("Bin busy", ChargeEstimate(Interval.point(0), "zero"), LimitEstimate(Interval.point(0))),
            "Other": TeamDecision("Other", ChargeEstimate(Interval.point(100), "exact"), LimitEstimate(Interval.point(0))),
        }
        item = HistoricalItem(1, FairValueEstimate(Interval.point(100)), CapEstimate(2000), decisions)
        game = HistoricalGame(1, ("Bin busy", "Other"), {1: item}, (), {"Bin busy": 0.0})

        score = score_game(game, {})

        self.assertEqual(score.net.midpoint, -150.0)
        self.assertEqual(score.ambiguity.missing_outputs, 1)


if __name__ == "__main__":
    unittest.main()
