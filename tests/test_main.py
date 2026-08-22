import unittest

from main import RunManager
from src.data.models import FraudDecision, ItemPrice, Proposal


def proposal(source: str, prices: list[tuple[int, float, float]]) -> Proposal:
    return Proposal(
        source=source,
        prices=tuple(ItemPrice(index, charge, limit_, source) for index, charge, limit_ in prices),
    )


class RunManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        base = proposal("standard", [(1, 100.0, 75.0), (2, 200.0, 150.0)])
        self.manager = RunManager(base)

    def test_fraud_lock_keeps_strategy_charge(self) -> None:
        self.manager.set_strategy(proposal("strategy1", [(1, 120.0, 90.0), (2, 250.0, 190.0)]))
        self.manager.apply_fraud(FraudDecision(frozenset({2})))

        prices = {price.index: price for price in self.manager.snapshot()}

        self.assertEqual((prices[1].charge_price, prices[1].acceptance_limit), (120.0, 90.0))
        self.assertEqual((prices[2].charge_price, prices[2].acceptance_limit), (250.0, 0.0))

    def test_strategy_has_priority_over_fast_path(self) -> None:
        self.manager.set_fast_path(proposal("fast_path_llm", [(1, 110.0, 80.0)]))
        self.manager.set_strategy(proposal("strategy1", [(1, 120.0, 90.0)]))

        prices = {price.index: price for price in self.manager.snapshot()}

        self.assertEqual((prices[1].charge_price, prices[1].acceptance_limit), (120.0, 90.0))
        self.assertEqual((prices[2].charge_price, prices[2].acceptance_limit), (200.0, 150.0))


if __name__ == "__main__":
    unittest.main()
