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
    "not a repair cost",
    "do not constitute repair costs",
    "not reimbursed",
    "not indemnifiable",
    "not the subject of this contract",
    "fall outside this cover",
    "not an insurance of",
    "not an insured peril",
)
EXPLICIT_LINE_ITEM_EXCLUSIONS = (
    (
        ("shipping", "delivery", "freight", "carriage", "dispatch", "postage", "transport", "logistics"),
        ("carriage", "freight", "delivery", "dispatch", "packaging", "postage", "transport", "logistics"),
    ),
    (
        ("installation", "install", "fitting", "mounting", "commissioning", "configuration", "connecting"),
        ("fitting", "mounting", "installing", "connecting", "commissioning", "setting up", "configuring", "programming", "pairing"),
    ),
    (("liability",), ("liability risk", "claims of third parties")),
    (("service", "maintenance", "inspection", "support", "warranty"), ("service", "maintenance", "inspection", "support", "warranty")),
    (("vehicle", "car", "transport costs", "travel costs"), ("any form of transport", "conveyance", "means of transport")),
    (("clothing", "clothes", "jewellery", "jewelry", "suitcase", "personal belongings"), ("movable belongings", "movable property")),
    (("stolen", "theft", "burglary"), ("taking away of property", "not an insured peril")),
)


def normalize(text: str) -> str:
    """Casefold and collapse whitespace, so line wrapping cannot defeat a match."""
    return " ".join(text.casefold().split())


def has_explicit_line_item_exclusion(line_item_name: str, policy_text: str) -> bool:
    item_name = normalize(line_item_name)
    policy = normalize(policy_text)
    for item_terms, policy_terms in EXPLICIT_LINE_ITEM_EXCLUSIONS:
        if not any(term in item_name for term in item_terms):
            continue
        for policy_term in policy_terms:
            start = 0
            while (position := policy.find(policy_term, start)) >= 0:
                window = policy[max(position - 600, 0) : position + len(policy_term) + 600]
                if any(marker in window for marker in EXCLUSION_MARKERS):
                    return True
                start = position + len(policy_term)
    return False


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
