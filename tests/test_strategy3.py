import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.data.models import CaseData, Proposal
from src.services.strategies.strategy3.strategy import LUNA_MODEL, STRATEGY_NAME, propose


class Strategy3Tests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_strategy1_pipeline_with_luna_model(self) -> None:
        case = CaseData(game_id=3, case_dir=Path("var/cases/case_03"))
        expected = Proposal(source=STRATEGY_NAME, prices=())
        runner = AsyncMock(return_value=expected)

        with patch("src.services.strategies.strategy3.strategy.propose_with_model", runner):
            proposal = await propose(case)

        self.assertIs(proposal, expected)
        runner.assert_awaited_once_with(case, model=LUNA_MODEL, source=STRATEGY_NAME)
        self.assertEqual(LUNA_MODEL, "luna")


if __name__ == "__main__":
    unittest.main()
