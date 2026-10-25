"""Workbook reader: the sheet by its name, the column by its header, the unit from the sheet header,
the row by its label. Every problem becomes a gap with a reason, never a wrong number."""

import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

import helpers
from helpers import make_book, table
import workbook
from config import load_config
from workbook import read_figures

CONFIG = load_config(helpers.ROOT / "config")[0]
SETTINGS = CONFIG["settings"]

SCR = {"id": "scr", "kind": "amount", "sheets": ["Capital"], "labels": ["SCR"]}
MCR = {"id": "mcr", "kind": "amount", "sheets": ["Capital"], "labels": ["MCR"]}
RATIO = {"id": "solvency_ratio", "kind": "percent", "sheets": ["Capital"], "labels": ["Rata de solvabilitate"]}


class ReaderCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def read(self, sheets, figures, column="current"):
        path = make_book(self.tmp / "registru.xlsx", sheets)
        return read_figures(path, figures, SETTINGS, column)

    def assertGap(self, value, reason):
        self.assertEqual((value.status, value.value, value.reason[0]), ("gap", None, reason))


class FindTest(ReaderCase):
    def test_amount_in_thousands_of_lei(self):
        values, _ = self.read([("Capital", table([["SCR", 148763.2, 151900]]))], [SCR])
        self.assertEqual(values["scr"].value, Decimal("148763200"))
        self.assertEqual(values["scr"].unit, "mii lei")
        self.assertIn("Capital", values["scr"].source)
        self.assertIn("C4", values["scr"].source)

    def test_sheet_found_by_name_in_any_position_ignoring_case(self):
        values, _ = self.read([("Note", [["x"]]), ("CAPITAL ", table([["SCR", 1]], "Valori în lei"))], [SCR])
        self.assertEqual(values["scr"].value, Decimal("1"))

    def test_column_found_by_header_when_columns_are_swapped(self):
        rows = [["Titlu"], ["Valori în lei"], [None, "Indicator", "31.12 an anterior", "31.12 an curent"], [None, "SCR", 2, 1]]
        values, _ = self.read([("Capital", rows)], [SCR])
        self.assertEqual(values["scr"].value, Decimal("1"))

    def test_prior_column(self):
        values, _ = self.read([("Capital", table([["SCR", 148763.2, 151900]]))], [SCR], column="prior")
        self.assertEqual(values["scr"].value, Decimal("151900000"))

    def test_label_with_cedilla_and_other_case_matches(self):
        figure = {"id": "scr_market", "kind": "amount", "sheets": ["SCR_module"], "labels": ["Risc de piață"]}
        values, _ = self.read([("SCR_module", table([["RISC de piaţă", 41902.6]]))], [figure])
        self.assertEqual(values["scr_market"].value, Decimal("41902600"))

    def test_label_stored_negative_gives_a_positive_amount(self):
        figure = {"id": "scr_diversification", "kind": "amount", "sheets": ["SCR_module"],
                  "labels": ["Efect de diversificare (se scade)"], "labels_stored_negative": ["Diversificare (valoare negativă)"]}
        values, _ = self.read([("SCR_module", table([["Diversificare (valoare negativă)", -28500000]], "Valori în lei"))], [figure])
        self.assertEqual(values["scr_diversification"].value, Decimal("28500000"))


class UnitTest(ReaderCase):
    def test_count_is_never_multiplied_by_the_unit(self):
        figure = {"id": "claims", "kind": "count", "sheets": ["Daune"], "labels": ["Număr de dosare de daună"]}
        sheet = table([["Număr de dosare de daună", 21037]], "Valori în mii lei, cu excepția numărului de dosare")
        values, _ = self.read([("Daune", sheet)], [figure])
        self.assertEqual(values["claims"].value, Decimal("21037"))

    def test_unknown_unit_gives_a_gap(self):
        values, _ = self.read([("Capital", table([["SCR", 1487.632]], "Valori în sute de mii lei"))], [SCR])
        self.assertGap(values["scr"], "unit_unknown")
        self.assertEqual(values["scr"].reason[1]["unit"], "sute de mii lei")

    def test_missing_unit_gives_a_gap(self):
        rows = [["Titlu"], [None, "Indicator", "31.12 an curent"], [None, "SCR", 1]]
        values, _ = self.read([("Capital", rows)], [SCR])
        self.assertGap(values["scr"], "unit_not_found")

    def test_unit_does_not_matter_for_a_percent(self):
        values, _ = self.read([("Capital", table([["Rata de solvabilitate", 1.874]], "Valori în sute de mii lei"))], [RATIO])
        self.assertEqual(values["solvency_ratio"].value, Decimal("1.874"))


class SheetTest(ReaderCase):
    def test_hidden_sheet_is_not_read_and_is_listed(self):
        sheets = [("Capital", table([["SCR", 151900]]), "hidden"), ("Arhiva", [["x"]], "veryHidden"), ("Altele", [["x"]])]
        values, hidden = self.read(sheets, [SCR])
        self.assertGap(values["scr"], "sheet_hidden")
        self.assertEqual(hidden, [("Capital", "hidden"), ("Arhiva", "veryHidden")])

    def test_sheet_not_found(self):
        values, _ = self.read([("Altele", [["x"]])], [SCR])
        self.assertGap(values["scr"], "sheet_not_found")

    def test_header_missing(self):
        values, _ = self.read([("Capital", [["Valori în lei"], [None, "SCR", 1]])], [SCR])
        self.assertGap(values["scr"], "header_not_found")

    def test_second_table_with_its_own_header_gives_a_gap(self):
        rows = table([["SCR", 1]]) + [[None, "Indicator", "31.12 an curent"], [None, "MCR", 2]]
        values, _ = self.read([("Capital", rows)], [SCR])
        self.assertGap(values["scr"], "header_ambiguous")


class RowTest(ReaderCase):
    def test_label_above_the_header_is_not_a_row(self):
        rows = [["SCR"], ["Valori în lei"], [None, "Indicator", "31.12 an curent"], [None, "SCR", 5]]
        values, _ = self.read([("Capital", rows)], [SCR])
        self.assertEqual(values["scr"].value, Decimal("5"))

    def test_label_not_found(self):
        values, _ = self.read([("Capital", table([["SCR total", 1]]))], [SCR])
        self.assertGap(values["scr"], "label_not_found")

    def test_same_label_twice_gives_a_gap(self):
        values, _ = self.read([("Capital", table([["SCR", 148763.2], ["SCR", 151900]]))], [SCR])
        self.assertGap(values["scr"], "label_repeated")
        self.assertEqual(values["scr"].reason[1]["count"], 2)

    def test_two_aliases_matching_two_rows_give_a_gap_not_a_stop(self):
        figure = dict(SCR, labels=["SCR", "SCR total"])
        values, _ = self.read([("Capital", table([["SCR", 148763.2], ["SCR total", 151900]]))], [figure])
        self.assertGap(values["scr"], "alias_two_rows")

    def test_two_figures_on_one_row_give_gaps_not_a_stop(self):
        basic = {"id": "scr_basic", "kind": "amount", "sheets": ["Capital"], "labels": ["SCR de bază", "SCR"]}
        values, _ = self.read([("Capital", table([["SCR", 148763.2], ["MCR", 45570]]))], [SCR, basic, MCR])
        self.assertGap(values["scr"], "row_two_figures")
        self.assertGap(values["scr_basic"], "row_two_figures")
        self.assertEqual(values["mcr"].value, Decimal("45570000"))


class CellTest(ReaderCase):
    def test_empty_value_takes_its_reason_from_the_row(self):
        values, _ = self.read([("Capital", table([["MCR", None, None, "în lucru, actuariat"]]))], [MCR])
        self.assertGap(values["mcr"], "value_missing_note")
        self.assertEqual(values["mcr"].reason[1]["note"], "în lucru, actuariat")

    def test_empty_value_without_a_note(self):
        values, _ = self.read([("Capital", table([["MCR", None]]))], [MCR])
        self.assertGap(values["mcr"], "value_missing")

    def test_text_instead_of_a_number(self):
        values, _ = self.read([("Capital", table([["MCR", "45.570"]]))], [MCR])
        self.assertGap(values["mcr"], "value_text")
        self.assertEqual(values["mcr"].reason[1]["text"], "45.570")

    def test_formula_without_a_saved_value_is_flagged(self):
        # openpyxl saves formulas without their results, like a workbook built by a script
        values, _ = self.read([("Capital", table([["SCR de bază", 135493], ["SCR", "=C4+1"]]))], [SCR])
        self.assertGap(values["scr"], "formula_no_value")
        self.assertTrue(values["scr"].formula)


class FileTest(ReaderCase):
    def test_missing_file(self):
        values, hidden = read_figures(self.tmp / "nu_exista.xlsx", [SCR, MCR], SETTINGS)
        self.assertGap(values["scr"], "file_missing")
        self.assertGap(values["mcr"], "file_missing")
        self.assertEqual(hidden, [])

    def test_damaged_file(self):
        path = self.tmp / "registru.xlsx"
        path.write_bytes(b"this is not a workbook")
        values, _ = read_figures(path, [SCR], SETTINGS)
        self.assertGap(values["scr"], "file_unreadable")

    def test_error_on_one_figure_becomes_a_gap_for_that_figure_only(self):
        real_read_cell = workbook.read_cell

        def read_cell(place, formulas, figure, file):
            if figure["id"] == "scr":
                raise RuntimeError("boom")
            return real_read_cell(place, formulas, figure, file)

        with mock.patch.object(workbook, "read_cell", read_cell):
            values, _ = self.read([("Capital", table([["SCR", 1], ["MCR", 2]]))], [SCR, MCR])
        self.assertGap(values["scr"], "unexpected_error")
        self.assertEqual(values["mcr"].value, Decimal("2000"))


@unittest.skipUnless((helpers.DATE / "registru_2025.xlsx").exists(), "date/registru_2025.xlsx lipsește")
class RealWorkbookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values, cls.hidden = read_figures(helpers.DATE / "registru_2025.xlsx", CONFIG["figures"], SETTINGS)

    def test_own_funds_total_from_its_formula_cell(self):
        total = self.values["own_funds_total"]
        self.assertEqual(total.value, Decimal("293699300"))
        self.assertIn("formulă", total.source)

    def test_diversification_is_positive(self):
        self.assertEqual(self.values["scr_diversification"].value, Decimal("22431900"))

    def test_mcr_is_a_gap_with_the_row_note(self):
        self.assertEqual(self.values["mcr"].reason, ("value_missing_note", self.values["mcr"].reason[1]))
        self.assertEqual(self.values["mcr"].reason[1]["note"], "în lucru, actuariat")

    def test_hidden_sheet_listed(self):
        self.assertEqual(self.hidden, [("Capital_vechi", "hidden")])

    def test_every_other_figure_found(self):
        self.assertEqual([v.id for v in self.values.values() if v.status != "ok"], ["mcr"])


if __name__ == "__main__":
    unittest.main()
