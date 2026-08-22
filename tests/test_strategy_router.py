import unittest

from src.data.models import ItemPrice, Proposal
from src.services.strategy_router import StrategyRouter


def proposal(source: str, charge: float) -> Proposal:
    return Proposal(source=source, prices=(ItemPrice(1, charge, charge * 0.75, source),))


class StrategyRouterTests(unittest.TestCase):
    def test_strategy2_has_higher_priority_than_strategy1(self) -> None:
        router = StrategyRouter(strategies=())

        self.assertEqual(router.register(proposal("strategy1", 100.0)).source, "strategy1")
        self.assertEqual(router.register(proposal("strategy2", 200.0)).source, "strategy2")
        self.assertEqual(router.register(proposal("strategy3", 300.0)).source, "strategy3")
        self.assertIsNone(router.register(proposal("strategy1", 400.0)))
        self.assertIsNone(router.register(proposal("strategy2", 500.0)))
        self.assertEqual(router.current.source, "strategy3")

    def test_empty_proposal_does_not_replace_active_strategy(self) -> None:
        router = StrategyRouter(strategies=())
        router.register(proposal("strategy1", 100.0))

        self.assertIsNone(router.register(Proposal(source="strategy2", prices=())))
        self.assertEqual(router.current.source, "strategy1")


if __name__ == "__main__":
    unittest.main()
