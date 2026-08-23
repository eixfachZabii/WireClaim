import tempfile
import unittest
from pathlib import Path

from backtesting.candidates.tail_aware import (
    _Inputs,
    _confirms_tail,
    _conflicts,
    _contextually_weak,
    _mixture_submission,
    _write_trace,
)
from backtesting.history import HistoryView
from backtesting.models import Submission
from backtesting.strategies import StrategyContext
from src.data.models import CaseData, LineItem
from src.evidence.memory import PriceMemoryHit
from src.pricing.engine import Evidence


def hit(name: str, *, match: str = "exact") -> PriceMemoryHit:
    return PriceMemoryHit(
        name=name,
        key=name.lower(),
        match=match,
        low=1_500,
        median=2_000,
        high=2_800,
        observations=1,
        games=(27,),
        basis="gross",
    )


class TailAwareCandidateTests(unittest.TestCase):
    def test_generic_exact_wording_can_trigger_large_upside_conflict(self) -> None:
        name = "Compensation for robbery damage (1 pcs)"
        case = CaseData(41, Path("case"), line_items=(LineItem(3, name),))
        model = {3: Evidence(3, 0.95, 9_000, 15_000, 22_000)}
        memory = {3: Evidence(3, 0.9, 1_500, 2_000, 2_800)}
        memory_hit = hit(name)

        conflicts = _conflicts(
            case,
            model,
            memory,
            {3: memory_hit},
            conflict_ratio=3.0,
            tail_threshold=1_000,
        )

        self.assertTrue(_contextually_weak(name, memory_hit))
        self.assertEqual(conflicts, {3: memory_hit})

    def test_specific_exact_wording_does_not_trigger_context_gate(self) -> None:
        name = "Replace insured tourbillon watch (1 pcs)"
        self.assertFalse(_contextually_weak(name, hit(name)))

    def test_confirmation_requires_two_current_case_reads_to_agree(self) -> None:
        remembered = Evidence(3, 0.9, 1_500, 2_000, 2_800)
        current = Evidence(3, 0.95, 9_000, 15_000, 22_000)
        agreeing = Evidence(3, 0.94, 8_000, 12_000, 18_000)
        disagreeing = Evidence(3, 0.94, 2_000, 3_000, 4_000)

        self.assertTrue(
            _confirms_tail(
                current,
                remembered,
                agreeing,
                confirmation_ratio=2.0,
                agreement_ratio=2.0,
            )
        )
        self.assertFalse(
            _confirms_tail(
                current,
                remembered,
                disagreeing,
                confirmation_ratio=2.0,
                agreement_ratio=2.0,
            )
        )

    def test_confirmed_mixture_can_represent_the_tail_in_both_numbers(self) -> None:
        submission = _mixture_submission(
            Evidence(3, 0.9, 1_500, 2_000, 2_800),
            Evidence(3, 0.95, 8_000, 12_000, 18_000),
            covered=0.95,
            tail_probability=0.70,
            limit_ceiling=0.75,
        )

        self.assertGreater(submission.charge, 2_000)
        self.assertGreater(submission.limit, 708)
        self.assertLessEqual(submission.limit, submission.charge)

    def test_trace_records_why_a_submission_changed(self) -> None:
        name = "Compensation for robbery damage (1 pcs)"
        case = CaseData(41, Path("case"), line_items=(LineItem(3, name),))
        remembered = Evidence(3, 0.9, 1_500, 2_000, 2_800)
        current = Evidence(3, 0.95, 9_000, 15_000, 22_000)
        reread = Evidence(3, 0.94, 8_000, 12_000, 18_000)
        memory_hit = hit(name)

        with tempfile.TemporaryDirectory() as directory:
            context = StrategyContext(
                case,
                HistoryView(41, {}),
                7,
                Path(directory),
            )
            _write_trace(
                context,
                {"tail_probability": 0.7},
                _Inputs({3: current}, {3: remembered}, {3: memory_hit}),
                {3: current},
                {3: Submission(1_200, 708)},
                {3: Submission(7_000, 3_000)},
                {3: memory_hit},
                {3: reread},
                {3},
            )

            trace = Path(directory) / "tail_aware" / "game_041.json"
            self.assertTrue(trace.exists())
            text = trace.read_text()
            self.assertIn('"confirmed": true', text)
            self.assertIn('"charge": 7000', text)


if __name__ == "__main__":
    unittest.main()
