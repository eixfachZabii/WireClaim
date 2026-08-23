"""Tests for the Price Memory store and its builder.

Everything here is offline and hermetic: no network, no case archives, no pdftotext.
The builder's two impure edges -- ``pdftotext`` and the leaderboard -- are isolated in
``invoice_text`` and ``_brackets``, so the parsing and aggregation that actually decide
the numbers can be tested on inline fixtures.

The behavioural tests that matter are the negative ones. This store must never claim an
item is uncovered, and it must never explode when ``var/`` is empty.
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for extra in (str(ROOT), str(ROOT / "scripts")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from src.evidence.memory import (  # noqa: E402
    SIGMA_LOG,
    PriceMemory,
    build_entries,
    core_key,
    is_per_unit,
    normalise,
    normalise_unit,
)

import build_price_memory as builder  # noqa: E402


INVOICE_FIXTURE = """\
                                                                         INVOICE

         Invoice
INVOICE NO.                  DATE            DUE               TRADE
2026-0161                    3 Mar 2026      17 Mar 2026       Plumbing

  FROM                                        TO

  Soggy Bottom Plumbing Ltd                   European Hackathon
  7 U-Bend Boulevard                          Main Street 1
  23456 Pipeville                             80331 Munich

ITEMS
 POS.    DESCRIPTION                                     AMOUNT   UNIT        TOTAL

 1       Skilled worker hours                                 8   hrs

 2       Upgrade to high-quality natural stone floor (upgrade  12   m²
         from pre-loss ceramic tiling)

 3       Preventive replacement of plant-room components       –   –

 4       Vehicle costs                                         1   pcs

 5       Room drying 30 m\u00b2                                 1   flat rate


Created on 21 Aug 2026                                                    Page 1 / 1
"""


def memory_from(observations):
    return PriceMemory.from_dict({"entries": build_entries(observations)})


def observation(key_name, game, value, unit="pcs", positive=True, **extra):
    record = {
        "key": normalise(key_name),
        "display_name": key_name,
        "game": game,
        "value": value,
        "unit": unit,
        "positive": positive,
    }
    record.update(extra)
    return record


class TestNormalisation(unittest.TestCase):
    def test_case_punctuation_and_dash_flavour_fold_together(self):
        self.assertEqual(
            normalise("Vehicle costs \u2013 return visit"),
            normalise("vehicle costs - RETURN  visit"),
        )

    def test_square_metres_spelling_folds(self):
        self.assertEqual(normalise("Room drying 30 m\u00b2"), "room drying 30 m2")

    def test_core_key_drops_the_trailing_qualifier(self):
        self.assertEqual(
            core_key("Condensation dryer for the kitchen, rental for the drying period"),
            "condensation dryer for the kitchen",
        )
        self.assertEqual(core_key("Air conditioning unit (surge damaged)"), "air conditioning unit")

    def test_unit_classification(self):
        for unit in ("hrs", "Hours", "m", "m\u00b2", "m2", "kg"):
            self.assertTrue(is_per_unit(unit), unit)
        for unit in ("pcs", "flat rate", "", None):
            self.assertFalse(is_per_unit(unit), unit)
        self.assertEqual(normalise_unit("m\u00b2"), "m2")


class TestLookup(unittest.TestCase):
    def test_miss_returns_none(self):
        memory = memory_from([observation("Vehicle costs", 5, 90.0)])
        self.assertIsNone(memory.lookup("Bespoke koi pond dredging"))

    def test_exact_hit_reports_band_count_and_games(self):
        memory = memory_from(
            [
                observation("Vehicle costs", 5, 100.0),
                observation("Vehicle costs", 9, 86.0),
                observation("vehicle  COSTS", 13, 64.0),
            ]
        )
        hit = memory.lookup("Vehicle costs", unit="pcs", quantity=1)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.match, "exact")
        self.assertEqual(hit.observations, 3)
        self.assertEqual(hit.games, (5, 9, 13))
        self.assertEqual(hit.median, 86.0)
        self.assertEqual((hit.observed_low, hit.observed_high), (64.0, 100.0))
        self.assertLessEqual(hit.low, hit.median)
        self.assertLessEqual(hit.median, hit.high)

    def test_band_is_widened_to_the_measured_dispersion(self):
        """Two observations that happen to agree are a small sample, not certainty."""
        memory = memory_from(
            [observation("Final site cleaning", 1, 100.0), observation("Final site cleaning", 8, 101.0)]
        )
        hit = memory.lookup("Final site cleaning")
        self.assertAlmostEqual(hit.observed_high - hit.observed_low, 1.0)
        self.assertAlmostEqual(hit.low, hit.median * math.exp(-SIGMA_LOG))
        self.assertAlmostEqual(hit.high, hit.median * math.exp(SIGMA_LOG))

    def test_core_tier_matches_across_a_parenthetical(self):
        """Case 4's 'TV set (surge damaged)' and Case 2's bare 'TV set' are one purchase.

        This is the only fallback tier. It is worth exactly two extra hits over Cases
        1-14 and costs nothing in sigma; looser matching was measured and rejected.
        """
        memory = memory_from([observation("TV set (surge damaged)", 4, 364.6)])
        hit = memory.lookup("TV set", unit="pcs", quantity=1)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.match, "core")
        self.assertEqual(hit.median, 364.6)

    def test_core_tier_also_drops_a_trailing_clause(self):
        memory = memory_from([observation("Vehicle costs - return visit", 8, 30.0)])
        self.assertEqual(memory.lookup("Vehicle costs").match, "core")

    def test_exact_wins_over_core(self):
        memory = memory_from(
            [
                observation("TV set (surge damaged)", 4, 364.6),
                observation("TV set", 2, 577.5),
            ]
        )
        hit = memory.lookup("TV set (surge damaged)")
        self.assertEqual(hit.match, "exact")
        self.assertEqual(hit.median, 364.6)


class TestQuantityBasis(unittest.TestCase):
    """Within a template, quantity matters: 219, 232, 754, 986 for skilled worker hours."""

    def test_per_unit_units_scale_with_quantity(self):
        memory = memory_from(
            [
                observation("Skilled worker hours", 8, 77.5, unit="hrs"),
                observation("Skilled worker hours", 12, 54.7, unit="hrs"),
            ]
        )
        one = memory.lookup("Skilled worker hours", unit="hrs", quantity=1)
        eight = memory.lookup("Skilled worker hours", unit="hrs", quantity=8)
        self.assertEqual(eight.basis, "per_unit")
        self.assertAlmostEqual(eight.median, one.median * 8)

    def test_pcs_and_flat_rate_stay_gross(self):
        memory = memory_from([observation("Drying fan", 8, 75.0, unit="pcs")])
        hit = memory.lookup("Drying fan", unit="pcs", quantity=3)
        self.assertEqual(hit.basis, "gross")
        self.assertEqual(hit.median, 75.0)

    def test_a_per_piece_total_is_never_multiplied_by_a_metre_quantity(self):
        """The Game 45/48 regression: one wording, two bases, pooled and rescaled.

        "Replace skirting boards" carried a per-*piece* gross total of 134.60 beside
        genuine per-*metre* rates. Asked for 15 m, the shipped lookup answered 1,772.55 --
        118.77 per piece times fifteen metres -- for a Line Item that settled at 338.
        """
        memory = memory_from(
            [
                observation("Replace skirting boards", 12, 134.6, unit="pcs", quantity=1.0),
                observation(
                    "Replace skirting boards", 45, 19.05,
                    unit="m", quantity=15.0, basis="per_unit",
                ),
                observation(
                    "Replace skirting boards", 48, 21.88,
                    unit="m", quantity=15.0, basis="per_unit",
                ),
            ]
        )
        hit = memory.lookup("Replace skirting boards", unit="m", quantity=15)
        self.assertEqual(hit.basis, "per_unit")
        self.assertAlmostEqual(hit.median, 306.98, places=2)

    def test_linear_metres_join_the_per_metre_rates_instead_of_the_gross_pool(self):
        """`linear m` was outside PER_UNIT_UNITS, so its total was stored as gross."""
        memory = memory_from(
            [
                observation("Replace skirting boards", 18, 393.49, unit="linear m", quantity=25.0),
                observation(
                    "Replace skirting boards", 45, 19.05,
                    unit="m", quantity=15.0, basis="per_unit",
                ),
            ]
        )
        hit = memory.lookup("Replace skirting boards", unit="m", quantity=15)
        # 393.49 over 25 linear metres is 15.7396/m; with 19.05/m the median is 17.3948.
        self.assertAlmostEqual(hit.median, 260.92, places=2)

    def test_a_per_unit_query_with_no_matching_unit_falls_back_to_the_gross_pool(self):
        """134.60 per piece is not a reading of a per-hour rate. Do not convert it."""
        memory = memory_from(
            [
                observation("Make good the wall", 12, 134.6, unit="pcs", quantity=1.0),
                observation("Make good the wall", 13, 150.0, unit="pcs", quantity=1.0),
            ]
        )
        hit = memory.lookup("Make good the wall", unit="hrs", quantity=8)
        self.assertEqual(hit.basis, "gross")
        self.assertAlmostEqual(hit.median, 142.3, places=2)

    def test_an_entry_without_per_sample_provenance_still_returns_a_hit(self):
        """A store written before samples carried a basis must not lose its hits."""
        memory = PriceMemory.from_dict(
            {
                "entries": {
                    "helper hours": {
                        "display_name": "Helper hours",
                        "values": [40.0, 44.0],
                        "games": [3, 4],
                        "units": ["hrs", "hrs"],
                        "advisory_zero_observations": 0,
                        "advisory_zero_games": [],
                    }
                }
            }
        )
        hit = memory.lookup("Helper hours", unit="hrs", quantity=8)
        self.assertEqual(hit.basis, "per_unit")
        self.assertAlmostEqual(hit.median, 336.0)

    def test_zero_or_missing_quantity_does_not_zero_the_price(self):
        memory = memory_from([observation("Helper hours", 11, 40.0, unit="hrs")])
        hit = memory.lookup("Helper hours", unit="hrs", quantity=0)
        self.assertEqual(hit.median, 40.0)


class TestNeverClaimsCoverage(unittest.TestCase):
    """The store is price-only. Six of fifteen repeated wordings flip 0 <-> t>0."""

    def setUp(self):
        self.memory = memory_from(
            [
                observation("Vehicle costs", 1, 14.0, positive=False),
                observation("Vehicle costs", 2, 10.5, positive=False),
                observation("Vehicle costs", 4, 10.0, positive=False),
                observation("Vehicle costs", 9, 86.0),
                observation("Vehicle costs", 11, 80.0),
            ]
        )

    def test_only_proven_positive_occurrences_reach_the_band(self):
        hit = self.memory.lookup("Vehicle costs")
        self.assertEqual(hit.observations, 2)
        self.assertEqual(hit.games, (9, 11))
        self.assertEqual(hit.median, 83.0)

    def test_zero_tally_is_present_but_labelled_advisory(self):
        hit = self.memory.lookup("Vehicle costs")
        self.assertEqual(hit.advisory_zero_observations, 3)
        self.assertEqual(hit.advisory_zero_games, (1, 2, 4))

    def test_a_wording_that_was_always_zero_is_a_miss_not_a_zero_price(self):
        """A miss must never be readable as 'uncovered' or as a price of 0."""
        memory = memory_from(
            [
                observation("Catering for work crew", 8, 0.5, positive=False),
                observation("Catering for work crew", 9, 0.5, positive=False),
            ]
        )
        self.assertIsNone(memory.lookup("Catering for work crew"))

    def test_hit_exposes_no_coverage_field(self):
        hit = self.memory.lookup("Vehicle costs")
        fields = set(hit.to_dict())
        self.assertFalse({"covered", "coverage", "excluded", "is_covered"} & fields)


class TestLoadingIsSafe(unittest.TestCase):
    def test_missing_file_yields_an_empty_memory_not_an_exception(self):
        memory = PriceMemory.load(Path("/nonexistent/price_memory.json"))
        self.assertEqual(len(memory), 0)
        self.assertIsNone(memory.lookup("Vehicle costs"))

    def test_corrupt_file_yields_an_empty_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "price_memory.json"
            path.write_text("{not json")
            self.assertEqual(len(PriceMemory.load(path)), 0)

    def test_round_trip_through_json(self):
        payload = builder.memory_payload(
            [
                dict(
                    observation("Skilled worker hours", 8, 77.5, unit="hrs"),
                    line_item_index=37,
                    quantity=3.0,
                    t_low=211.0,
                    t_high=254.0,
                    basis="per_unit",
                ),
                dict(observation("Vehicle costs", 1, 14.0, unit="pcs", positive=False), quantity=1.0),
            ],
            [1, 8],
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "price_memory.json"
            path.write_text(json.dumps(payload))
            memory = PriceMemory.load(path)
        hit = memory.lookup("Skilled worker hours", unit="hrs", quantity=4)
        self.assertAlmostEqual(hit.median, 310.0)
        self.assertIn("PRICE ONLY", payload["warning"])
        self.assertNotIn(normalise("Vehicle costs"), payload["entries"])


class TestInvoiceParsing(unittest.TestCase):
    def setUp(self):
        self.items = builder.parse_invoice_text(INVOICE_FIXTURE)

    def test_every_pos_number_is_found(self):
        self.assertEqual(sorted(self.items), [1, 2, 3, 4, 5])

    def test_quantity_and_unit_are_read_from_their_own_columns(self):
        self.assertEqual(self.items[1]["quantity"], 8.0)
        self.assertEqual(self.items[1]["unit"], "hrs")
        self.assertEqual(self.items[5]["unit"], "flat rate")

    def test_wrapped_description_starting_with_from_is_not_a_section_break(self):
        """The word FROM opens the address block and also continues POS. 2."""
        self.assertIn("pre-loss ceramic tiling", self.items[2]["name"])
        self.assertIn(4, self.items)

    def test_a_dash_quantity_falls_back_to_one(self):
        self.assertEqual(self.items[3]["quantity"], 1.0)

    def test_address_lines_are_not_line_items(self):
        names = " ".join(item["name"] for item in self.items.values())
        self.assertNotIn("U-Bend Boulevard", names)
        self.assertNotIn("Munich", names)


class TestFairValuePoint(unittest.TestCase):
    def test_midpoint_when_both_bounds_are_known(self):
        self.assertEqual(builder.fair_value(200.0, 240.0), 220.0)

    def test_lower_bound_when_every_reviewer_accepted(self):
        self.assertEqual(builder.fair_value(754.0, math.inf), 754.0)


class TestRecordAndEvaluation(unittest.TestCase):
    def _record(self, name, unit, quantity, lo, hi):
        item = {"index": 1, "name": name, "quantity": quantity, "unit": unit}
        return builder._record(3, item, lo, hi)

    def test_per_unit_record_divides_by_quantity(self):
        record = self._record("Skilled worker hours", "hrs", 4.0, 200.0, 238.0)
        self.assertEqual(record["basis"], "per_unit")
        self.assertAlmostEqual(record["value"], 219.0 / 4)
        self.assertTrue(record["positive"])

    def test_gross_record_keeps_the_total(self):
        record = self._record("Drying fan", "pcs", 3.0, 45.0, 105.0)
        self.assertEqual(record["basis"], "gross")
        self.assertEqual(record["value"], 75.0)

    def test_zero_lower_bound_is_not_proof_of_a_positive_fair_value(self):
        record = self._record("Vehicle costs", "pcs", 1.0, 0.0, 28.0)
        self.assertFalse(record["positive"])

    def test_leave_one_out_never_scores_a_case_against_itself(self):
        records = [
            dict(
                observation("Widget", game, value, unit="pcs"),
                t_point=value,
                display_name="Widget",
                quantity=1.0,
            )
            for game, value in ((1, 100.0), (2, 100.0), (3, 1000.0))
        ]
        result = builder.evaluate(records, [1, 2, 3])
        by_game = {row[0]: row for row in result["rows"]}
        self.assertEqual(by_game[3][2], 1)
        self.assertGreater(result["mae"], 0.5, "a self-scored memory would report ~0")


if __name__ == "__main__":
    unittest.main()
