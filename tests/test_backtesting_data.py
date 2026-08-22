import unittest

from backtesting.data import normalize_transactions, parse_games, validate_complete_game


class BacktestingDataTests(unittest.TestCase):
    def test_normalizes_the_two_team_views_to_one_transaction(self) -> None:
        row = {
            "line_item_index": 4,
            "issuer": "A",
            "reviewer": "B",
            "accepted": True,
            "amount": 125.0,
        }

        result = normalize_transactions(9, {"A": [row], "B": [row]})

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source_teams, ("A", "B"))
        self.assertEqual(result[0].key, (9, 4, "A", "B"))

    def test_disagreeing_duplicate_views_fail_loudly(self) -> None:
        left = {"line_item_index": 1, "issuer": "A", "reviewer": "B", "accepted": True, "amount": 10.0}
        right = dict(left, accepted=False)

        with self.assertRaisesRegex(ValueError, "disagree"):
            normalize_transactions(1, {"A": [left], "B": [right]})

    def test_complete_pair_validation_uses_real_indices_not_maximum_index(self) -> None:
        teams = ("A", "B")
        rows = []
        for index in (1, 3):
            for issuer, reviewer in (("A", "B"), ("B", "A")):
                raw = {"line_item_index": index, "issuer": issuer, "reviewer": reviewer, "accepted": True, "amount": 1.0}
                rows.extend(normalize_transactions(1, {issuer: [raw], reviewer: [raw]}))

        validate_complete_game(1, teams, rows)

    def test_game_parser_excludes_game_zero_by_default(self) -> None:
        self.assertEqual(parse_games("all", [0, 1, 2]), [1, 2])
        self.assertEqual(parse_games("all", [0, 1, 2], include_game_0=True), [0, 1, 2])
        self.assertEqual(parse_games("1-2", [0, 1, 2]), [1, 2])


if __name__ == "__main__":
    unittest.main()
