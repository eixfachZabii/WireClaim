"""The single test for "does this quote prove the Policy excludes this Line Item?".

This lives in one module on purpose. It used to be copy-pasted into
`services/fraud_detection.py` and `services/strategies/strategy1/strategy.py`, which is
the same duplication class that has already cost us money once: the two copies decide
whether a Limit goes to zero, and a Limit outside the posterior is an open tap.

The gate is deliberately hard to pass. Its failure mode is asymmetric -- wrongly zeroing
a Limit turns every fair claim into a 1.5a wrongful-rejection penalty, which is how
Game 10 lost 65,806 -- so it refuses far more than it admits.
"""

from __future__ import annotations

# Against a ~63,000-character Policy a 12-character substring test is not a test at all:
# "the schedule", "is not covered" and "the policyholder" all passed, and Game 10 flagged
# every Line Item as a result.
#
# 60 is measured rather than guessed. Splitting all 14 extracted policy.txt files into
# sentences containing exclusion language gives a median length of 112 characters, and
# nearly every such sentence under 60 characters is a *heading* -- "3.1 general
# exclusions", "3.2 exclusions within the fire group" -- which names a section without
# excluding anything. A 60-character floor drops the headings and keeps ~81% of real
# clauses.
MIN_QUOTE_LENGTH = 60

# Length alone only proves specificity, not exclusion. The quote also has to say that
# something is *not* covered, otherwise ordinary indemnity boilerplate qualifies.
EXCLUSION_MARKERS = (
    "not covered",
    "no cover",
    "excluded",
    "exclusion",
    "does not cover",
    "is not insured",
    "no indemnity",
    "not indemnified",
    "does not extend",
    "not apply",
    "shall not",
)


def normalize(text: str) -> str:
    """Casefold and collapse whitespace, so line wrapping cannot defeat a match."""
    return " ".join(text.casefold().split())


def is_policy_quote(quote: str, policy_text: str) -> bool:
    """True only if `quote` is specific, states an exclusion, and is verbatim Policy text.

    All three conditions are load-bearing. Case 7 dangles "a couple of metres from the
    hob" in the Damage Description while the Policy says in terms that proximity to
    another appliance does not remove cover -- so a verdict sourced from the description
    is not evidence, and only a quotable clause is.
    """
    normalized_quote = normalize(quote)
    if len(normalized_quote) < MIN_QUOTE_LENGTH:
        return False
    if not any(marker in normalized_quote for marker in EXCLUSION_MARKERS):
        return False
    return normalized_quote in normalize(policy_text)
