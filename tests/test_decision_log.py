import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import decision_log
from src.data.models import CaseData, LineItem
from src.decision_log import GameDecisions, ItemDecision, load, record
from src.pricing import Evidence
from src.services.strategies.strategy2.strategy import build_proposal


class RecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(decision_log, "DECISIONS_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_a_round_trip_keeps_every_field(self) -> None:
        record(
            GameDecisions(
                game_id=26,
                strategy="strategy2",
                model_draws=2,
                items=[ItemDecision(index=1, name="Drying fan", charge=100.0, limit=30.0)],
            )
        )

        payload = load(26)

        self.assertEqual(payload["game_id"], 26)
        self.assertEqual(payload["model_draws"], 2)
        self.assertEqual(payload["items"][0]["name"], "Drying fan")

    def test_a_write_failure_is_swallowed(self) -> None:
        """A logging problem must never cost a Submission."""
        with patch.object(decision_log, "DECISIONS_DIR", Path("/nonexistent/nope")):
            record(GameDecisions(game_id=1, strategy="strategy2"))  # must not raise

    def test_a_missing_log_reads_as_none(self) -> None:
        self.assertIsNone(load(999))

    def test_a_log_from_a_future_schema_is_refused(self) -> None:
        """Better no attribution than a silently mis-read one."""
        path = Path(self.tmp.name) / "game_007.json"
        path.write_text(json.dumps({"schema": 999, "game_id": 7, "items": []}))

        self.assertIsNone(load(7))


class BuildProposalLoggingTests(unittest.TestCase):
    def case(self, *items: LineItem) -> CaseData:
        return CaseData(
            game_id=26,
            case_dir=Path(tempfile.gettempdir()),
            policy_text="",
            description_text="",
            line_items=items,
        )

    def test_it_records_which_channels_spoke(self) -> None:
        """The field that would have diagnosed Games 21-24 in one glance."""
        case = self.case(
            LineItem(1, "Priced by the model"),
            LineItem(2, "Vehicle costs", quantity_missing=True),
            LineItem(3, "Nothing knows this one"),
        )
        decisions: list[ItemDecision] = []

        build_proposal(
            case,
            {1: Evidence(1, 0.95, 80.0, 100.0, 125.0)},
            {2: Evidence(2, 0.0, 30.0, 59.0, 118.0)},
            decisions,
        )

        by_index = {d.index: d for d in decisions}
        self.assertEqual(by_index[1].channels, ("C:model",))
        self.assertEqual(by_index[2].channels, ("A:no-quantity",))
        self.assertEqual(by_index[3].channels, ())
        self.assertEqual(by_index[3].rule, "uninformed-constants")

    def test_it_records_the_evidence_that_was_priced(self) -> None:
        case = self.case(LineItem(1, "Drying fan"))
        decisions: list[ItemDecision] = []

        proposal = build_proposal(case, {1: Evidence(1, 0.95, 80.0, 100.0, 125.0)}, {}, decisions)

        entry = decisions[0]
        self.assertAlmostEqual(entry.coverage_probability, 0.95)
        self.assertAlmostEqual(entry.price_median, 100.0)
        self.assertIsNotNone(entry.sigma)
        self.assertEqual(entry.charge, proposal.prices[0].charge_price)
        self.assertEqual(entry.limit, proposal.prices[0].acceptance_limit)

    def test_a_zero_limit_is_labelled_as_the_free_option(self) -> None:
        case = self.case(LineItem(1, "Vehicle costs", quantity_missing=True))
        decisions: list[ItemDecision] = []

        build_proposal(case, {}, {1: Evidence(1, 0.0, 30.0, 59.0, 118.0)}, decisions)

        self.assertEqual(decisions[0].rule, "uncovered-free-option")
        self.assertEqual(decisions[0].limit, 0.0)

    def test_logging_is_optional(self) -> None:
        """The runner must work identically if nobody passes a list."""
        case = self.case(LineItem(1, "Drying fan"))

        self.assertIsNotNone(build_proposal(case, {1: Evidence(1, 0.9, 80.0, 100.0, 125.0)}, {}))


if __name__ == "__main__":
    unittest.main()
