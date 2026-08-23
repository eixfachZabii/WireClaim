import tempfile
import unittest
from pathlib import Path

from src.data.case_loader import find_image_paths, parse_invoice_text
from src.data.models import LineItem


class CaseLoaderTests(unittest.TestCase):
    def test_discovers_all_supported_case_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case_dir = Path(directory)
            for name in ("damage.png", "overview.JPG", "receipt.webp", "notes.txt", "scan.gif"):
                (case_dir / name).write_bytes(b"data")

            image_names = [path.name for path in find_image_paths(case_dir)]

        self.assertEqual(image_names, ["damage.png", "overview.JPG", "receipt.webp"])


    def test_parser_ignores_invoice_year_and_reads_position_rows(self) -> None:
        line_items = parse_invoice_text(
            "INVOICE 2026\n"
            "POS. DESCRIPTION\n"
            "1 Leak detection 14 hrs\n"
            "2 Technician call-out 3 pcs\n"
            "Created on 2026-08-22\n"
        )

        self.assertEqual([item.index for item in line_items], [1, 2])
        self.assertEqual([item.quantity for item in line_items], [14.0, 3.0])
        self.assertNotIn(2026, [item.index for item in line_items])

    def test_a_two_word_unit_keeps_its_quantity_and_invents_no_position(self) -> None:
        """Game 59 position 3, verbatim.

        ``linear m`` was missing from the unit alternation, so the quantity fell back to
        1.0 *and* the orphaned ``25`` was then read as a new POS number whose description
        was the unit itself -- a tenth Line Item on a nine-item Case, which we charged on.
        We charged 321.94 against a proven floor of t >= 1,036.19.
        """
        line_items = parse_invoice_text(
            "POS. DESCRIPTION\n"
            "1 Remove water-damaged laminate in living room 18 m²\n"
            "3 Supply and install skirting boards (premium solid oak, 25 linear m\n"
            "Created on 2026-08-21\n"
        )

        self.assertEqual([item.index for item in line_items], [1, 3])
        self.assertEqual([item.quantity for item in line_items], [18.0, 25.0])
        self.assertNotIn(25, [item.index for item in line_items])

    def test_every_two_word_unit_in_the_settled_record_parses(self) -> None:
        """``labor units`` (Case 47) and ``lines`` (Case 27) are the other two."""
        line_items = parse_invoice_text(
            "POS. DESCRIPTION\n"
            "7 Service technician hours 9 labor units\n"
            "8 Translation from Spanish to English 68 lines\n"
            "Created on 2026-08-21\n"
        )

        self.assertEqual([item.quantity for item in line_items], [9.0, 68.0])

    def test_a_dash_in_the_unit_column_still_carries_its_quantity(self) -> None:
        """``Skilled worker hours   14   -`` is qty 14, not qty 1.

        Distinct from the dash *pair*, which really does mean no quantity was given.
        Cases 25, 35 and 37 all print this row.
        """
        line_items = parse_invoice_text(
            "POS. DESCRIPTION\n"
            "13 Skilled worker hours 14 \u2013\n"
            "Created on 2026-08-21\n"
        )

        self.assertEqual([item.quantity for item in line_items], [14.0])
        self.assertFalse(line_items[0].quantity_missing)

    def test_a_wrapped_description_line_is_not_a_position_row(self) -> None:
        """Case 54 wraps as ``         80 kg)``.

        ``^\\s*`` read that as position 80 named ``kg)`` -- a Line Item that does not exist
        and that we posted a Charge on. Case 17 position 82 is the same shape. A genuine POS
        row carries one or two leading spaces; a continuation is indented to the description
        column.
        """
        line_items = parse_invoice_text(
            "POS. DESCRIPTION\n"
            " 1 Recover the tank assembly (cast iron, weighing over 2 pcs\n"
            "         80 kg)\n"
            "Created on 2026-08-21\n"
        )

        self.assertEqual([item.index for item in line_items], [1])
        self.assertNotIn(80, [item.index for item in line_items])

    def test_inline_dash_pair_marks_the_quantity_as_missing(self) -> None:
        line_items = parse_invoice_text(
            "POS. DESCRIPTION AMOUNT UNIT TOTAL\n"
            "1 Bicycle frame replacement 1 pcs\n"
            "4 Vehicle costs – –\n"
        )

        by_index = {item.index: item for item in line_items}
        self.assertEqual(sorted(by_index), [1, 4])
        self.assertFalse(by_index[1].quantity_missing)
        self.assertTrue(by_index[4].quantity_missing)
        self.assertEqual(by_index[4].quantity, 1.0)
        self.assertEqual(by_index[4].name, "Vehicle costs")

    def test_dash_pair_on_its_own_row_marks_the_wrapped_position(self) -> None:
        # pypdf pushes the amount and unit of a wrapped description onto their
        # own row, which is how Case 1 position 3 and Case 9 positions 2 and 16
        # actually extract.
        line_items = parse_invoice_text(
            "POS. DESCRIPTION AMOUNTUNIT TOTAL\n"
            "2 Inspect plant-room electrical systems 1 pcs\n"
            "3 Preventive replacement of plant-room electrical\n"
            "components (no confirmed water contact)\n"
            "– –\n"
            "4 Upgrade to high-quality natural stone floor (upgrade\n"
            "from pre-loss ceramic tiling)\n"
            "12 m²\n"
        )

        by_index = {item.index: item for item in line_items}
        self.assertEqual(sorted(by_index), [2, 3, 4])
        self.assertFalse(by_index[2].quantity_missing)
        self.assertTrue(by_index[3].quantity_missing)
        self.assertEqual(by_index[3].quantity, 1.0)
        self.assertFalse(by_index[4].quantity_missing)
        self.assertEqual(by_index[4].quantity, 12.0)

    def test_a_hyphenated_name_is_not_mistaken_for_a_missing_quantity(self) -> None:
        line_items = parse_invoice_text(
            "POS. DESCRIPTION AMOUNT UNIT TOTAL\n"
            "1 Vehicle costs – return visit 1 pcs\n"
            "2 Vehicle costs – return visit – –\n"
        )

        by_index = {item.index: item for item in line_items}
        self.assertFalse(by_index[1].quantity_missing)
        self.assertTrue(by_index[2].quantity_missing)
        self.assertEqual(by_index[2].name, "Vehicle costs – return visit")

    def test_quantity_missing_is_serialised(self) -> None:
        self.assertIs(LineItem(index=1).to_dict()["quantity_missing"], False)
        self.assertIs(LineItem(index=1, quantity_missing=True).to_dict()["quantity_missing"], True)

    def test_a_gap_in_the_position_numbers_survives_parsing(self) -> None:
        # The submission index IS the printed POS number. Case 11 has no POS 12,
        # and the settled Game has indices 1-11 and 13-23 with no 12, so a parser
        # that renumbered by row ordinal would misprice every item after the gap.
        line_items = parse_invoice_text(
            "POS. DESCRIPTION AMOUNT UNIT TOTAL\n"
            "10 Scaffolding 1 flat rate\n"
            "11 Roof batten replacement 8 m\n"
            "13 Ridge tile bedding 4 pcs\n"
            "23 Final site cleaning 1 pcs\n"
        )

        indices = [item.index for item in line_items]
        self.assertEqual(indices, [10, 11, 13, 23])
        self.assertNotIn(12, indices)
        self.assertEqual(max(indices), 23)
        self.assertEqual(len(line_items), 4)
        self.assertNotEqual(indices, list(range(1, len(line_items) + 1)))

    def test_positions_continue_across_several_invoices_in_one_pdf(self) -> None:
        # A single invoices.pdf holds several trades; POS numbering continues
        # across them (Case 14: 1-8, then 9-13) and must not restart or collide.
        line_items = parse_invoice_text(
            "Invoice\n"
            "POS. DESCRIPTION AMOUNT UNIT TOTAL\n"
            "1 Bicycle frame replacement 1 pcs\n"
            "2 Wheel truing 2 hrs\n"
            "Created on 21 Aug 2026 Page 1 / 1\n"
            "Invoice\n"
            "POS. DESCRIPTION AMOUNT UNIT TOTAL\n"
            "9 Paint touch-up 1 pcs\n"
            "10 Transport 1 flat rate\n"
            "Created on 21 Aug 2026 Page 1 / 1\n"
        )

        self.assertEqual([item.index for item in line_items], [1, 2, 9, 10])


if __name__ == "__main__":
    unittest.main()
