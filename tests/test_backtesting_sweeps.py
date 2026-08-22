import unittest

from backtesting.models import GameScore, ValueTriple
from backtesting.sweeps import chronological_evaluation, expand_grid, parameter_key


def score(game, net):
    triple = ValueTriple(net, net, net)
    return GameScore(game, triple, ValueTriple(0, 0, 0), triple, {})


class BacktestingSweepTests(unittest.TestCase):
    def test_grid_expansion_is_deterministic(self) -> None:
        cells = expand_grid({"fixed": 1}, {"b": [2, 3], "a": [4, 5]})
        self.assertEqual(len(cells), 4)
        self.assertEqual(cells[0], {"fixed": 1, "a": 4, "b": 2})

    def test_parameter_keys_ignore_mapping_insertion_order(self) -> None:
        self.assertEqual(parameter_key({"a": 1, "b": 2}), parameter_key({"b": 2, "a": 1}))

    def test_chronological_holdout_selects_on_train_only(self) -> None:
        left = parameter_key({"x": 1})
        right = parameter_key({"x": 2})
        scores = {
            left: {1: score(1, 10), 2: score(2, 10), 3: score(3, -100), 4: score(4, -100)},
            right: {1: score(1, 0), 2: score(2, 0), 3: score(3, 100), 4: score(4, 100)},
        }

        result = chronological_evaluation(scores, [1, 2, 3, 4], holdout_fraction=0.5, min_train=2, step=1)

        self.assertEqual(result["selected"], left)
        self.assertEqual(result["train_games"], [1, 2])
        self.assertEqual(result["test_games"], [3, 4])
        self.assertEqual(result["holdout_score"]["midpoint"], -200)


if __name__ == "__main__":
    unittest.main()
