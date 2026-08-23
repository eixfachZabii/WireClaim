import unittest
from pathlib import Path

from src.evidence.policy.slice import (
    CLAIM_SPECIFIC_PART,
    DEFAULT_KEEP,
    MIN_SLICE_CHARS,
    has_claim_specific_part,
    policy_sections,
    slice_policy,
    slice_report,
)

CASES_DIR = Path(__file__).resolve().parents[1] / "[PUBLIC] EHL Cases" / "cases"
STRUCTURED_CASES = tuple(range(1, 15))
#: Cases whose policy carries the claim-specific PART 11 answer key.
CASES_WITH_PART_11 = frozenset({1, 2, 4, 6, 10, 14})

SYNTHETIC = (
    "PREAMBLE - not a numbered part\n"
    "\n"
    "PART 1 - PURPOSE AND KEY CONCEPTS\n"
    "1.1 This policy does things.\n"
    "\n"
    "PART 2 – INSURED PERILS\n"  # en dash on purpose
    "2.1 Perils.\n"
    "\n"
    "PART 3 - EXCLUSIONS\n"
    "3.1 Wear and tear is excluded.\n"
    "\n"
    "PART 11 - LOSS DESCRIPTION AND OPERATIVE PROVISIONS FOR THIS CLAIM\n"
    "11.1 Water escaped.\n"
)


def _policy_path(case_number: int) -> Path:
    return CASES_DIR / f"case_{case_number:02d}" / "policy.txt"


def _read_policy(case_number: int) -> str:
    return _policy_path(case_number).read_text(encoding="utf-8")


def _available_cases() -> list[int]:
    return [number for number in STRUCTURED_CASES if _policy_path(number).exists()]


class PolicySectionsTests(unittest.TestCase):
    def test_sections_are_split_by_part_number(self) -> None:
        sections = policy_sections(SYNTHETIC)
        self.assertEqual(sorted(sections), [1, 2, 3, 11])

    def test_en_dash_headers_are_recognised(self) -> None:
        self.assertIn("2.1 Perils.", policy_sections(SYNTHETIC)[2])

    def test_every_section_is_verbatim(self) -> None:
        for text in policy_sections(SYNTHETIC).values():
            self.assertIn(text, SYNTHETIC)

    def test_sections_keep_their_header(self) -> None:
        self.assertTrue(policy_sections(SYNTHETIC)[3].startswith("PART 3 - EXCLUSIONS"))

    def test_unstructured_text_has_no_sections(self) -> None:
        self.assertEqual(policy_sections("no parts here at all"), {})

    def test_empty_text_has_no_sections(self) -> None:
        self.assertEqual(policy_sections(""), {})


class SlicePolicyTests(unittest.TestCase):
    def test_default_keep_is_the_measured_set(self) -> None:
        self.assertEqual(DEFAULT_KEEP, frozenset({3, 4, 5, 7, 11}))

    def test_dropped_parts_are_gone_and_kept_parts_remain(self) -> None:
        sliced = slice_policy(SYNTHETIC, frozenset({3, 11}))
        self.assertIn("3.1 Wear and tear is excluded.", sliced)
        self.assertIn("11.1 Water escaped.", sliced)
        self.assertNotIn("2.1 Perils.", sliced)
        self.assertNotIn("1.1 This policy does things.", sliced)

    def test_no_part_headers_falls_back_to_the_full_text(self) -> None:
        plain = "1. PURPOSE\nThis policy insures the bicycle described in the schedule.\n"
        self.assertEqual(slice_policy(plain), plain)

    def test_requested_parts_absent_falls_back_to_the_full_text(self) -> None:
        self.assertEqual(slice_policy(SYNTHETIC, frozenset({42})), SYNTHETIC)

    def test_a_suspiciously_small_slice_falls_back(self) -> None:
        """A tiny slice out of a large policy means the parse went wrong."""
        big = SYNTHETIC + ("filler line that is not inside any kept part\n" * 400)
        self.assertGreater(len(big), MIN_SLICE_CHARS)
        self.assertEqual(slice_policy(big, frozenset({3})), big)

    def test_empty_input_is_returned_unchanged(self) -> None:
        self.assertEqual(slice_policy(""), "")

    def test_slicing_is_deterministic(self) -> None:
        self.assertEqual(slice_policy(SYNTHETIC), slice_policy(SYNTHETIC))


class RealPolicyTests(unittest.TestCase):
    """Checks against the 14 extracted policies (skipped when not extracted)."""

    def setUp(self) -> None:
        self.cases = _available_cases()
        if len(self.cases) < len(STRUCTURED_CASES):
            self.skipTest("policies not extracted; run the 7z extraction from CLAUDE.md")

    def test_every_policy_has_the_ten_part_skeleton(self) -> None:
        for case_number in self.cases:
            with self.subTest(case=case_number):
                parts = sorted(policy_sections(_read_policy(case_number)))
                self.assertEqual(parts[:10], list(range(1, 11)))

    def test_part_11_is_present_in_exactly_the_expected_cases(self) -> None:
        found = {n for n in self.cases if has_claim_specific_part(_read_policy(n))}
        self.assertEqual(found, CASES_WITH_PART_11)

    def test_part_11_is_always_kept_when_present(self) -> None:
        for case_number in sorted(CASES_WITH_PART_11):
            with self.subTest(case=case_number):
                text = _read_policy(case_number)
                sliced = slice_policy(text)
                self.assertIn(
                    "PART 11 - LOSS DESCRIPTION AND OPERATIVE PROVISIONS FOR THIS CLAIM",
                    sliced,
                )
                self.assertIn(policy_sections(text)[CLAIM_SPECIFIC_PART], sliced)

    def test_every_kept_section_is_a_verbatim_substring(self) -> None:
        for case_number in self.cases:
            with self.subTest(case=case_number):
                text = _read_policy(case_number)
                for number, section in policy_sections(text).items():
                    self.assertIn(section, text, f"part {number} was altered")

    def test_no_real_policy_falls_back(self) -> None:
        for case_number in self.cases:
            with self.subTest(case=case_number):
                report = slice_report(_read_policy(case_number))
                self.assertFalse(report["fell_back"])
                self.assertGreater(report["sliced_chars"], MIN_SLICE_CHARS)

    def test_parts_3_5_7_11_retain_about_41_percent(self) -> None:
        """The measured 41% figure is for {3, 5, 7, 11} — without PART 4."""
        original = sum(len(_read_policy(n)) for n in self.cases)
        sliced = sum(len(slice_policy(_read_policy(n), frozenset({3, 5, 7, 11}))) for n in self.cases)
        self.assertAlmostEqual(sliced / original, 0.415, delta=0.02)

    def test_default_keep_retains_about_52_percent(self) -> None:
        """Adding PART 4 (insured property) costs ~10 points of retention."""
        original = sum(len(_read_policy(n)) for n in self.cases)
        sliced = sum(len(slice_policy(_read_policy(n))) for n in self.cases)
        self.assertAlmostEqual(sliced / original, 0.52, delta=0.02)

    def test_case_00_has_no_part_headers_and_is_returned_whole(self) -> None:
        path = _policy_path(0)
        if not path.exists():
            self.skipTest("case_00 not extracted")
        text = path.read_text(encoding="utf-8")
        self.assertEqual(policy_sections(text), {})
        self.assertEqual(slice_policy(text), text)


if __name__ == "__main__":  # pragma: no cover - manual verification helper
    for number in _available_cases():
        rep = slice_report(_read_policy(number))
        print(
            f"case {number:>2}: {rep['original_chars']:>6} -> {rep['sliced_chars']:>6} "
            f"({rep['ratio']:>5.1%})  kept={rep['kept_parts']}"
        )
    unittest.main()
