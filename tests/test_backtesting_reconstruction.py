import unittest

from backtesting.models import Transaction
from backtesting.reconstruction import reconstruct_game


def transaction(index, issuer, reviewer, accepted, amount):
    return Transaction(1, index, issuer, reviewer, accepted, amount, tuple(sorted((issuer, reviewer))))


class BacktestingReconstructionTests(unittest.TestCase):
    def test_recovers_exact_and_censored_charges_and_limit_brackets(self) -> None:
        teams = ("A", "B", "C")
        rows = (
            transaction(1, "A", "B", True, 100.0),
            transaction(1, "A", "C", False, 100.0),
            transaction(1, "B", "A", False, 0.0),
            transaction(1, "B", "C", False, 0.0),
            transaction(1, "C", "A", False, 0.0),
            transaction(1, "C", "B", False, 0.0),
        )

        game = reconstruct_game(1, teams, rows, {1: (100.0, 200.0)}, {team: 0.0 for team in teams})
        decisions = game.items[1].decisions

        self.assertEqual(decisions["A"].charge.status, "exact")
        self.assertEqual(decisions["A"].charge.interval.low, 100.0)
        self.assertEqual(decisions["B"].charge.status, "right_censored")
        self.assertIsNone(decisions["B"].charge.interval.high)
        self.assertEqual(decisions["B"].limit.interval.low, 100.0)
        self.assertIsNone(decisions["B"].limit.interval.high)
        self.assertEqual(decisions["C"].limit.interval.high, 100.0)

    def test_cap_censored_charge_does_not_tighten_a_reviewer_upper_limit(self) -> None:
        teams = ("A", "B", "C")
        rows = (
            transaction(1, "A", "B", True, 2000.0),
            transaction(1, "A", "C", False, 0.0),
            transaction(1, "B", "A", False, 0.0),
            transaction(1, "B", "C", True, 2000.0),
            transaction(1, "C", "A", False, 0.0),
            transaction(1, "C", "B", False, 0.0),
        )

        game = reconstruct_game(1, teams, rows, {1: (0.0, 100.0)}, {team: 0.0 for team in teams})
        decisions = game.items[1].decisions

        self.assertEqual(decisions["A"].charge.status, "cap_censored")
        self.assertEqual(decisions["B"].charge.status, "cap_censored")
        self.assertIsNone(decisions["C"].limit.interval.high)


if __name__ == "__main__":
    unittest.main()
