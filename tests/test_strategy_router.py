import unittest

from src.data.models import ItemPrice, Proposal
from src.services.strategy_router import StrategyRouter


def proposal(source: str, charge: float) -> Proposal:
    return Proposal(source=source, prices=(ItemPrice(1, charge, charge * 0.75, source),))


class StrategyRouterTests(unittest.TestCase):
    def test_strategy2_outranks_the_others_in_either_arrival_order(self) -> None:
        """Strategy 2 is the only one with constants fitted to the reconstructed Fair
        Values, so it wins regardless of which strategy finishes first."""
        router = StrategyRouter(strategies=())

        self.assertEqual(router.register(proposal("strategy1", 100.0)).source, "strategy1")
        self.assertEqual(router.register(proposal("strategy3", 300.0)).source, "strategy3")
        self.assertEqual(router.register(proposal("strategy2", 200.0)).source, "strategy2")
        self.assertIsNone(router.register(proposal("strategy1", 400.0)))
        self.assertIsNone(router.register(proposal("strategy3", 500.0)))
        self.assertEqual(router.current.source, "strategy2")

    def test_strategy2_wins_even_when_it_lands_first(self) -> None:
        router = StrategyRouter(strategies=())

        self.assertEqual(router.register(proposal("strategy2", 200.0)).source, "strategy2")
        self.assertIsNone(router.register(proposal("strategy3", 300.0)))
        self.assertEqual(router.current.source, "strategy2")

    def test_an_unknown_source_loses_to_every_known_strategy(self) -> None:
        router = StrategyRouter(strategies=())
        router.register(proposal("strategy1", 100.0))

        self.assertIsNone(router.register(proposal("mystery", 900.0)))

    def test_empty_proposal_does_not_replace_active_strategy(self) -> None:
        router = StrategyRouter(strategies=())
        router.register(proposal("strategy1", 100.0))

        self.assertIsNone(router.register(Proposal(source="strategy2", prices=())))
        self.assertEqual(router.current.source, "strategy1")


if __name__ == "__main__":
    unittest.main()
