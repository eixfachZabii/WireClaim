import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.data.models import CaseData, LineItem
from src.policy_quote import is_policy_quote
from src.services.coverage import (
    DEFAULT_P_COVERED,
    LIMIT_COLLAPSE,
    QUANTITY_MISSING_CEILING,
    SAMPLES,
    CoverageVerdict,
    assess_coverage,
    build_prompt,
    calibrate,
    coverage_probabilities,
    merge_samples,
    repair_quote,
)

# A miniature policy with the shape that breaks a naive quote check: the words that say
# "not paid" live in the lead-in, two sub-paragraphs above the one a model would cite.
POLICY = """PART 1 - PREAMBLE
This contract is concluded between the insurer and the policyholder.

PART 3 - EXCLUSIONS
7.1.8 Outlay that is not an indemnity for property
The following are not indemnified, however they may be described, bundled or
invoiced, by whichever party they are raised:

  (a) measures directed at the general condition, upkeep or improvement of the
      property, as distinct from making good the damage caused by the event;

  (b) carriage, freight, delivery, dispatch, packaging, postage, courier,
      transport, logistics and comparable charges, whether for bringing
      replacement property to the insured location or otherwise;

PART 7 - CALCULATION OF THE INDEMNITY
7.1.7 The insurer indemnifies the cost of investigation, testing and measurement
carried out to establish whether property was affected by the insured event;
this is indemnified even where the property investigated turns out not to be
indemnified.
"""


def _case(*line_items: LineItem, policy: str = POLICY) -> CaseData:
    return CaseData(
        game_id=7,
        case_dir=Path(tempfile.gettempdir()) / "coverage-test-no-such-case",
        policy_text=policy,
        description_text="Water escaped from a supply pipe in the utility room.",
        line_items=line_items,
    )


def _client(payloads: list[dict]) -> MagicMock:
    """A client that returns `payloads` in order and then repeats the last one."""
    client = MagicMock()
    responses = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(payload)))])
        for payload in payloads
    ]
    client.chat.completions.create.side_effect = lambda *_, **__: (
        responses.pop(0) if len(responses) > 1 else responses[0]
    )
    return client


def _payload(*entries: dict) -> dict:
    return {"items": list(entries)}


def _entry(index: int, p: float, clause: str = "", reasoning: str = "") -> dict:
    return {"index": index, "p_covered": p, "clause": clause, "reasoning": reasoning}


class CalibrationTests(unittest.TestCase):
    def test_a_quoted_exclusion_keeps_its_low_probability(self) -> None:
        clause = (
            "The following are not indemnified, however they may be described, bundled or\n"
            "invoiced, by whichever party they are raised:"
        )
        self.assertTrue(is_policy_quote(clause, POLICY))
        probability, verified, shipped = calibrate(0.05, clause, POLICY)
        self.assertEqual(probability, 0.05)
        self.assertTrue(verified)
        self.assertEqual(shipped, clause)

    def test_an_unquoted_doubt_cannot_collapse_a_limit_on_its_own(self) -> None:
        # Case 7: the Damage Description dangles a suspicious detail that no clause
        # supports. The model may believe it; it must not zero the Limit alone.
        probability, verified, _ = calibrate(0.02, "the unit sat a couple of metres from the hob", POLICY)
        self.assertFalse(verified)
        self.assertGreater(probability, LIMIT_COLLAPSE)
        self.assertLess(probability, DEFAULT_P_COVERED)

    def test_a_high_probability_is_passed_through_untouched(self) -> None:
        probability, verified, _ = calibrate(0.9, "", POLICY)
        self.assertEqual(probability, 0.9)
        self.assertFalse(verified)

    def test_a_dash_quantity_caps_the_probability_even_against_the_model(self) -> None:
        # 20 of 20 such positions in the settled Games were worth exactly zero.
        probability, _, _ = calibrate(0.95, "", POLICY, quantity_missing=True)
        self.assertLessEqual(probability, QUANTITY_MISSING_CEILING)
        self.assertLess(probability, LIMIT_COLLAPSE)

    def test_a_nonsense_probability_falls_back_to_the_default(self) -> None:
        probability, _, _ = calibrate("not a number", "", POLICY)
        self.assertEqual(probability, DEFAULT_P_COVERED)
        self.assertEqual(calibrate(float("nan"), "", POLICY)[0], DEFAULT_P_COVERED)
        self.assertEqual(calibrate(4.0, "", POLICY)[0], 1.0)


class QuoteRepairTests(unittest.TestCase):
    def test_a_clause_number_glued_onto_a_sub_paragraph_is_repaired(self) -> None:
        # What the model actually returns: the sub-paragraph prefixed with a clause
        # number that sits several lines above it. Nowhere in the Policy verbatim.
        assembled = (
            "7.1.8 (b) carriage, freight, delivery, dispatch, packaging, postage, courier, "
            "transport, logistics and comparable charges"
        )
        self.assertFalse(is_policy_quote(assembled, POLICY))
        repaired = repair_quote(assembled, POLICY)
        self.assertTrue(is_policy_quote(repaired, POLICY))
        self.assertIn(repaired, POLICY)
        self.assertIn("not indemnified", repaired)

    def test_an_invented_quote_is_not_repaired(self) -> None:
        self.assertEqual(repair_quote("Swimming pools are excluded from this contract.", POLICY), "")
        self.assertEqual(repair_quote("", POLICY), "")

    def test_a_quote_without_exclusion_language_stays_rejected_when_none_is_near(self) -> None:
        # Verbatim, long enough, but it grants cover rather than removing it.
        granting = (
            "7.1.7 The insurer indemnifies the cost of investigation, testing and measurement\n"
            "carried out to establish whether property was affected by the insured event;"
        )
        self.assertIn(granting, POLICY)
        self.assertEqual(repair_quote(granting, POLICY), "")


class MergeTests(unittest.TestCase):
    def test_disagreeing_samples_average_into_the_live_middle_band(self) -> None:
        merged = merge_samples(
            (
                CoverageVerdict(3, 0.05, "quoted clause", True, "excluded"),
                CoverageVerdict(3, 0.9, "", False, "covered"),
            )
        )
        self.assertAlmostEqual(merged.p_covered, 0.475)
        self.assertEqual(merged.clause, "quoted clause")
        self.assertTrue(merged.quote_verified)
        self.assertFalse(merged.collapses_limit)

    def test_agreeing_samples_still_collapse_the_limit(self) -> None:
        merged = merge_samples(
            (
                CoverageVerdict(3, 0.05, "quoted clause", True, ""),
                CoverageVerdict(3, 0.1, "another clause", True, ""),
            )
        )
        self.assertTrue(merged.collapses_limit)


class PromptTests(unittest.TestCase):
    def test_the_prompt_carries_the_dash_quantity_flag(self) -> None:
        item = LineItem(index=4, name="Vehicle costs", quantity_missing=True)
        prompt = build_prompt(_case(item), (item,), POLICY)
        self.assertIn('"quantity_missing": true', prompt)
        self.assertIn("Vehicle costs", prompt)

    def test_the_policy_is_sliced_before_it_is_sent(self) -> None:
        item = LineItem(index=1, name="Shipping")
        case = _case(item, policy=POLICY + "x" * 3000)
        sent: list[str] = []
        client = _client([_payload(_entry(1, 0.9))])
        client.chat.completions.create.side_effect = lambda **kwargs: sent.append(
            kwargs["messages"][1]["content"]
        ) or MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(_payload(_entry(1, 0.9)))))])
        with patch("src.services.coverage.get_llm_client", return_value=client):
            asyncio.run(assess_coverage(case))
        self.assertTrue(sent)
        self.assertIn("PART 3 - EXCLUSIONS", sent[0])
        self.assertNotIn("PART 1 - PREAMBLE", sent[0])


class AssessCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.items = (
            LineItem(index=1, name="Leak detection"),
            LineItem(index=3, name="Shipping"),  # a gap in the printed POS numbers
        )
        self.case = _case(*self.items)

    def test_it_returns_one_verdict_per_line_item_keeping_the_printed_numbers(self) -> None:
        client = _client([_payload(_entry(1, 0.95), _entry(3, 0.2, "clause"))])
        with patch("src.services.coverage.get_llm_client", return_value=client):
            verdicts = asyncio.run(assess_coverage(self.case))
        self.assertEqual([verdict.index for verdict in verdicts], [1, 3])
        self.assertEqual(coverage_probabilities(verdicts)[1], 0.95)

    def test_every_sample_is_requested_and_averaged(self) -> None:
        client = _client([])
        contents = [
            json.dumps(_payload(_entry(1, 0.9), _entry(3, 0.1))),
            json.dumps(_payload(_entry(1, 0.9), _entry(3, 0.9))),
        ]
        client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content=content))])
            for content in contents
        ]
        with patch("src.services.coverage.SAMPLES", 2), patch(
            "src.services.coverage.get_llm_client", return_value=client
        ):
            verdicts = asyncio.run(assess_coverage(self.case))
        self.assertEqual(client.chat.completions.create.call_count, 2)
        # 0.1 came without a usable quote, so it is shrunk before it is averaged.
        self.assertGreater(coverage_probabilities(verdicts)[3], 0.1)
        self.assertLess(coverage_probabilities(verdicts)[3], DEFAULT_P_COVERED)

    def test_an_item_the_model_skipped_defaults_to_covered(self) -> None:
        client = _client([_payload(_entry(1, 0.1, "clause"))])
        with patch("src.services.coverage.get_llm_client", return_value=client):
            verdicts = asyncio.run(assess_coverage(self.case))
        self.assertEqual(coverage_probabilities(verdicts)[3], DEFAULT_P_COVERED)

    def test_a_failing_model_never_breaks_the_submission(self) -> None:
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("gateway down")
        with patch("src.services.coverage.get_llm_client", return_value=client):
            verdicts = asyncio.run(assess_coverage(self.case))
        self.assertEqual(len(verdicts), 2)
        self.assertTrue(all(verdict.p_covered == DEFAULT_P_COVERED for verdict in verdicts))
        self.assertFalse(any(verdict.collapses_limit for verdict in verdicts))

    def test_unparseable_output_never_breaks_the_submission(self) -> None:
        client = MagicMock()
        client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json at all"))]
        )
        with patch("src.services.coverage.get_llm_client", return_value=client):
            verdicts = asyncio.run(assess_coverage(self.case))
        self.assertTrue(all(verdict.p_covered == DEFAULT_P_COVERED for verdict in verdicts))

    def test_a_case_without_line_items_yields_nothing(self) -> None:
        self.assertEqual(asyncio.run(assess_coverage(_case())), ())

    def test_an_expired_deadline_does_not_raise(self) -> None:
        client = _client([_payload(_entry(1, 0.9), _entry(3, 0.9))])
        with patch("src.services.coverage.get_llm_client", return_value=client):
            verdicts = asyncio.run(assess_coverage(self.case, deadline=0.0))
        self.assertEqual(len(verdicts), 2)

    def test_a_long_invoice_is_split_into_several_calls(self) -> None:
        items = tuple(LineItem(index=index, name=f"Item {index}") for index in range(1, 18))
        client = _client([_payload(*(_entry(index, 0.9) for index in range(1, 18)))])
        with patch("src.services.coverage.SAMPLES", 1), patch(
            "src.services.coverage.get_llm_client", return_value=client
        ):
            verdicts = asyncio.run(assess_coverage(_case(*items)))
        self.assertEqual(len(verdicts), 17)
        self.assertEqual(client.chat.completions.create.call_count, 3)


if __name__ == "__main__":
    unittest.main()
