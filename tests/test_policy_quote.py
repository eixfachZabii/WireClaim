import unittest

from src.services.policy.quotes import MIN_QUOTE_LENGTH, has_explicit_line_item_exclusion, is_policy_quote, normalize

POLICY = (
    "3.1 general exclusions\n"
    "The insurer indemnifies the policyholder in accordance with the schedule of cover "
    "set out in this document.\n"
    "Damage caused by storm surge is not covered under this section of the policy.\n"
    "Wear and tear is excluded.\n"
)


class PolicyQuoteTests(unittest.TestCase):
    def test_a_real_exclusion_clause_passes(self) -> None:
        self.assertTrue(
            is_policy_quote(
                "Damage caused by storm surge is not covered under this section of the policy.",
                POLICY,
            )
        )

    def test_an_unambiguous_noncoverage_phrase_passes(self) -> None:
        exclusion = "Charges relating to a liability risk fall outside this cover and are not indemnified."

        self.assertTrue(is_policy_quote(exclusion, exclusion))

    def test_property_scope_exclusions_match_the_line_item(self) -> None:
        policy = (
            "This is not an insurance of the movable belongings of people who live there, "
            "and it is not an insurance of any form of transport used by them."
        )

        self.assertTrue(has_explicit_line_item_exclusion("Clothing stolen from a car", policy))
        self.assertTrue(has_explicit_line_item_exclusion("Vehicle costs", policy))
        self.assertFalse(has_explicit_line_item_exclusion("Repair to a building wall", policy))

    def test_line_wrapping_does_not_defeat_the_match(self) -> None:
        """Policies wrap; a quote split across lines is still verbatim."""
        self.assertTrue(
            is_policy_quote(
                "Damage caused by storm surge is not\n   covered under this section of the policy.",
                POLICY,
            )
        )

    def test_a_section_heading_is_too_short_to_prove_anything(self) -> None:
        """"3.1 general exclusions" names a section without excluding an item."""
        self.assertFalse(is_policy_quote("3.1 general exclusions", POLICY))

    def test_indemnity_boilerplate_without_exclusion_language_fails(self) -> None:
        """The Game 10 bug: long, verbatim, and proves nothing."""
        boilerplate = (
            "The insurer indemnifies the policyholder in accordance with the schedule of "
            "cover set out in this document."
        )
        self.assertGreaterEqual(len(boilerplate), MIN_QUOTE_LENGTH)
        self.assertFalse(is_policy_quote(boilerplate, POLICY))

    def test_a_quote_absent_from_the_policy_fails(self) -> None:
        """Exclusion language the model invented is not evidence."""
        self.assertFalse(
            is_policy_quote(
                "Damage caused by nuclear incident is not covered under this policy at all.",
                POLICY,
            )
        )

    def test_short_exclusion_language_fails(self) -> None:
        """"Wear and tear is excluded." is real but too short to be specific."""
        self.assertFalse(is_policy_quote("Wear and tear is excluded.", POLICY))

    def test_empty_quote_fails(self) -> None:
        self.assertFalse(is_policy_quote("", POLICY))

    def test_normalize_casefolds_and_collapses_whitespace(self) -> None:
        self.assertEqual(normalize("  Not   Covered\n Here "), "not covered here")


if __name__ == "__main__":
    unittest.main()
