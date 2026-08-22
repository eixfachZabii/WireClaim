import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.observability import decisions as decision_log
from src.data.models import CaseData, LineItem
from src.observability.decisions import (
    SCHEMA_VERSION,
    GameDecisions,
    ItemDecision,
    load,
    proposals,
    record,
    record_proposals,
)
from src.domain.pricing.engine import Evidence
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

    def test_a_log_with_no_schema_at_all_is_refused(self) -> None:
        (Path(self.tmp.name) / "game_008.json").write_text(json.dumps({"game_id": 8}))

        self.assertIsNone(load(8))

    def test_a_schema_1_log_stays_readable(self) -> None:
        """1 is a subset of 2 — the Strategy 2 attribution we already have must survive."""
        (Path(self.tmp.name) / "game_009.json").write_text(
            json.dumps({"schema": 1, "game_id": 9, "strategy": "strategy2", "items": []})
        )

        payload = load(9)

        self.assertIsNotNone(payload)
        self.assertEqual(payload["strategy"], "strategy2")
        self.assertEqual(proposals(payload), {}, "schema 1 has no Proposal section")


class ProposalRecordingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(decision_log, "DECISIONS_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_every_source_round_trips_with_the_winner(self) -> None:
        record_proposals(
            26,
            {"strategy1": {1: (10.0, 5.0)}, "strategy2": {1: (20.0, 6.0)}},
            winner="strategy2",
        )

        payload = load(26)

        self.assertEqual(payload["schema"], SCHEMA_VERSION)
        self.assertEqual(payload["winner"], "strategy2")
        self.assertEqual(
            proposals(payload),
            {"strategy1": {1: (10.0, 5.0)}, "strategy2": {1: (20.0, 6.0)}},
        )

    def test_an_empty_proposal_is_kept_as_an_empty_mapping(self) -> None:
        """"Answered with nothing" is a different fact from "never ran"."""
        record_proposals(26, {"strategy1": {}}, winner=None)

        self.assertEqual(proposals(load(26)), {"strategy1": {}})
        self.assertNotIn("winner", load(26))

    def test_the_strategy_2_section_and_the_proposals_coexist_in_either_order(self) -> None:
        """Two writers, one file, and no guarantee which of them finishes first."""
        for first, second in (("items", "proposals"), ("proposals", "items")):
            with self.subTest(first=first):
                Path(self.tmp.name, "game_031.json").unlink(missing_ok=True)
                writers = {
                    "items": lambda: record(
                        GameDecisions(
                            game_id=31,
                            strategy="strategy2",
                            items=[ItemDecision(index=1, name="Drying fan", charge=78.9)],
                        )
                    ),
                    "proposals": lambda: record_proposals(
                        31, {"strategy3": {1: (1.0, 2.0)}}, winner="strategy2"
                    ),
                }
                writers[first]()
                writers[second]()

                payload = load(31)
                self.assertEqual(payload["items"][0]["name"], "Drying fan")
                self.assertEqual(proposals(payload), {"strategy3": {1: (1.0, 2.0)}})
                self.assertEqual(payload["winner"], "strategy2")

    def test_repeated_writes_accumulate_sources_rather_than_replacing_them(self) -> None:
        record_proposals(26, {"strategy1": {1: (10.0, 5.0)}}, winner="strategy1")
        record_proposals(26, {"strategy2": {1: (20.0, 6.0)}}, winner="strategy2")

        self.assertEqual(sorted(proposals(load(26))), ["strategy1", "strategy2"])
        self.assertEqual(load(26)["winner"], "strategy2")

    def test_a_log_from_an_earlier_run_is_replaced_rather_than_merged(self) -> None:
        """Mixing two runs of one Game is exactly the mis-attribution to avoid."""
        stale = {
            "schema": SCHEMA_VERSION,
            "game_id": 26,
            "items": [{"index": 9, "name": "from last week"}],
            "recorded_at": 0.0,
            "proposals": {"strategy1": {"9": [1.0, 1.0]}},
        }
        Path(self.tmp.name, "game_026.json").write_text(json.dumps(stale))

        record_proposals(26, {"strategy2": {1: (20.0, 6.0)}}, winner="strategy2")

        payload = load(26)
        self.assertEqual(proposals(payload), {"strategy2": {1: (20.0, 6.0)}})
        self.assertNotIn("items", payload)

    def test_a_write_failure_is_swallowed(self) -> None:
        with patch.object(decision_log, "DECISIONS_DIR", Path("/nonexistent/nope")):
            record_proposals(1, {"strategy1": {1: (1.0, 2.0)}}, winner="strategy1")

    def test_unencodable_numbers_are_swallowed(self) -> None:
        record_proposals(26, {"strategy1": {1: ("nope", None)}}, winner="strategy1")  # type: ignore[dict-item]

        self.assertIsNone(load(26))

    def test_a_corrupt_proposal_section_does_not_stop_the_reader(self) -> None:
        payload = {
            "schema": SCHEMA_VERSION,
            "game_id": 26,
            "proposals": {"strategy1": {"1": [10.0, 5.0], "2": "broken"}},
        }

        self.assertEqual(proposals(payload), {"strategy1": {1: (10.0, 5.0)}})

    def test_no_payload_at_all_reads_as_no_proposals(self) -> None:
        self.assertEqual(proposals(None), {})


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
