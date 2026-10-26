"""Reading the sources: figures from a workbook (sheet by name, column by header, unit from the sheet
header, row by label) and quotes from documents. Every problem becomes a gap, never a wrong number."""

import shutil
import tempfile
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path
from unittest import mock

import helpers
from helpers import make_book, table
import read
from config import load_config
from read import check_fact, fact_figure, label_key, normalize, read_workbook, to_decimal

CONFIG = load_config(helpers.ROOT / "config")[0]
SETTINGS = CONFIG["settings"]
HAS_DATE = (helpers.DATE / "registru_2025.xlsx").exists()

SCR = {"id": "scr", "kind": "amount", "sheets": ["Capital"], "labels": ["SCR"]}
MCR = {"id": "mcr", "kind": "amount", "sheets": ["Capital"], "labels": ["MCR"]}
RATIO = {"id": "solvency_ratio", "kind": "percent", "sheets": ["Capital"], "labels": ["Rata de solvabilitate"]}


class TextTest(unittest.TestCase):
    def test_cedilla_and_spaces(self):
        # ţ with a cedilla, a double space, a non-breaking space, a newline
        self.assertEqual(normalize(" Risc  de\xa0piaţă \n"), "Risc de piață")

    def test_labels_compared_ignoring_case(self):
        self.assertEqual(label_key("Risc de PIAŢĂ"), "risc de piață")

    def test_float_keeps_the_digits_written_in_the_file(self):
        # Decimal(231450.6) would be 231450.600000000005820766...
        self.assertEqual(to_decimal(231450.6), Decimal("231450.6"))

    def test_excel_float_noise_is_dropped(self):
        # Excel saves a total of one-decimal values as 293699.39999999997; it keeps only 15 significant digits
        self.assertEqual(to_decimal(293699.39999999997), Decimal("293699.4"))
        self.assertEqual(to_decimal(0.1 + 0.2), Decimal("0.3"))

    def test_digits_beyond_15_are_cut_like_excel_does(self):
        self.assertEqual(to_decimal(1.974273879561612), Decimal("1.97427387956161"))
        self.assertEqual(to_decimal(12345678901234), Decimal("12345678901234"))  # whole numbers are kept as they are

    def test_not_a_number_gives_none(self):
        for value in (True, "12", None, float("nan")):
            with self.subTest(value=value):
                self.assertIsNone(to_decimal(value))


class WorkbookCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def read(self, sheets, figures, column="current"):
        return read_workbook(make_book(self.tmp / "registru.xlsx", sheets), figures, SETTINGS, column)

    def assertGap(self, value, reason):
        self.assertEqual((value.status, value.value, value.reason[0]), ("gap", None, reason))


class FindTest(WorkbookCase):
    def test_amount_in_thousands_of_lei(self):
        values, _ = self.read([("Capital", table([["SCR", 148763.2, 151900]]))], [SCR])
        self.assertEqual((values["scr"].value, values["scr"].unit), (Decimal("148763200"), "mii lei"))
        self.assertIn("Capital, celula C4", values["scr"].source)

    def test_prior_column(self):
        values, _ = self.read([("Capital", table([["SCR", 148763.2, 151900]]))], [SCR], column="prior")
        self.assertEqual(values["scr"].value, Decimal("151900000"))

    def test_sheet_found_by_name_in_any_position_ignoring_case(self):
        values, _ = self.read([("Note", [["x"]]), ("CAPITAL ", table([["SCR", 1]], "Valori în lei"))], [SCR])
        self.assertEqual(values["scr"].value, Decimal("1"))

    def test_column_found_by_header_when_columns_are_swapped(self):
        rows = [["Valori în lei"], [None, "Indicator", "31.12 an anterior", "31.12 an curent"], [None, "SCR", 2, 1]]
        values, _ = self.read([("Capital", rows)], [SCR])
        self.assertEqual(values["scr"].value, Decimal("1"))

    def test_label_with_cedilla_and_other_case_matches(self):
        figure = {"id": "scr_market", "kind": "amount", "sheets": ["SCR_module"], "labels": ["Risc de piață"]}
        values, _ = self.read([("SCR_module", table([["RISC de piaţă", 41902.6]]))], [figure])
        self.assertEqual(values["scr_market"].value, Decimal("41902600"))

    def test_label_stored_negative_gives_a_positive_amount(self):
        figure = {"id": "div", "kind": "amount", "sheets": ["SCR_module"], "labels": ["Efect de diversificare (se scade)"],
                  "labels_stored_negative": ["Diversificare (valoare negativă)"]}
        values, _ = self.read([("SCR_module", table([["Diversificare (valoare negativă)", -28500000]], "Valori în lei"))], [figure])
        self.assertEqual(values["div"].value, Decimal("28500000"))

    def test_a_total_saved_by_excel_with_float_noise(self):
        # Excel writes 17 significant digits ("293699.39999999997"); openpyxl would write "293699.4"
        path = make_book(self.tmp / "registru.xlsx", [("Capital", table([["SCR", 293699.4]]))])
        with zipfile.ZipFile(path) as book:
            files = {name: book.read(name) for name in book.namelist()}
        sheet = "xl/worksheets/sheet1.xml"
        self.assertEqual(files[sheet].count(b"<v>293699.4</v>"), 1)
        files[sheet] = files[sheet].replace(b"<v>293699.4</v>", b"<v>293699.39999999997</v>")
        with zipfile.ZipFile(path, "w") as book:
            for name, data in files.items():
                book.writestr(name, data)
        values, _ = read_workbook(path, [SCR], SETTINGS)
        self.assertEqual(values["scr"].value, Decimal("293699400"))

    def test_label_above_the_header_is_not_a_row(self):
        rows = [["SCR"], ["Valori în lei"], [None, "Indicator", "31.12 an curent"], [None, "SCR", 5]]
        values, _ = self.read([("Capital", rows)], [SCR])
        self.assertEqual(values["scr"].value, Decimal("5"))


class GapTest(WorkbookCase):
    def test_hidden_sheet_is_not_read_and_is_listed(self):
        sheets = [("Capital", table([["SCR", 151900]]), "hidden"), ("Arhiva", [["x"]], "veryHidden"), ("Altele", [["x"]])]
        values, hidden = self.read(sheets, [SCR])
        self.assertGap(values["scr"], "sheet_not_found")
        self.assertEqual(hidden, [("Capital", "hidden"), ("Arhiva", "veryHidden")])

    def test_header_missing_or_twice(self):
        twice = table([["SCR", 1]]) + [[None, "Indicator", "31.12 an curent"], [None, "MCR", 2]]
        for rows in ([["Valori în lei"], [None, "SCR", 1]], twice):
            values, _ = self.read([("Capital", rows)], [SCR])
            self.assertGap(values["scr"], "header_not_found")

    def test_header_text_inside_another_word_is_not_a_header(self):
        rows = table([["SCR", 1]], "Valori în lei") + [[None, "Notă: plan curent de lucru"]]  # "plan curent"
        values, _ = self.read([("Capital", rows)], [SCR])
        self.assertEqual(values["scr"].value, Decimal("1"))

    def test_label_not_found(self):
        values, _ = self.read([("Capital", table([["SCR total", 1]]))], [SCR])
        self.assertGap(values["scr"], "label_not_found")

    def test_same_label_twice(self):
        values, _ = self.read([("Capital", table([["SCR", 148763.2], ["SCR", 151900]]))], [SCR])
        self.assertGap(values["scr"], "label_not_unique")

    def test_two_aliases_matching_two_rows(self):
        figure = dict(SCR, labels=["SCR", "SCR total"])
        values, _ = self.read([("Capital", table([["SCR", 148763.2], ["SCR total", 151900]]))], [figure])
        self.assertGap(values["scr"], "label_not_unique")

    def test_unknown_unit(self):
        values, _ = self.read([("Capital", table([["SCR", 1487.632]], "Valori în sute de mii lei"))], [SCR])
        self.assertGap(values["scr"], "unit_unknown")

    def test_count_is_never_multiplied_by_the_unit(self):
        figure = {"id": "claims", "kind": "count", "sheets": ["Daune"], "labels": ["Număr de dosare de daună"]}
        sheet = table([["Număr de dosare de daună", 21037]], "Valori în mii lei, cu excepția numărului de dosare")
        values, _ = self.read([("Daune", sheet)], [figure])
        self.assertEqual(values["claims"].value, Decimal("21037"))

    def test_unit_does_not_matter_for_a_percent(self):
        values, _ = self.read([("Capital", table([["Rata de solvabilitate", 1.874]], "Valori în sute de mii lei"))], [RATIO])
        self.assertEqual(values["solvency_ratio"].value, Decimal("1.874"))

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

    def test_formula_without_a_saved_value(self):
        # openpyxl saves formulas without their results, like a workbook built by a script
        values, _ = self.read([("Capital", table([["SCR de bază", 135493], ["SCR", "=C4+1"]]))], [SCR])
        self.assertGap(values["scr"], "formula_no_value")

    def test_missing_file(self):
        values, hidden = read_workbook(self.tmp / "nu_exista.xlsx", [SCR], SETTINGS)
        self.assertGap(values["scr"], "file_missing")

    def test_damaged_file(self):
        path = self.tmp / "registru.xlsx"
        path.write_bytes(b"this is not a workbook")
        values, _ = read_workbook(path, [SCR], SETTINGS)
        self.assertGap(values["scr"], "file_unreadable")

    def test_error_on_one_figure_is_a_gap_for_that_figure_only(self):
        real = read.read_figure

        def read_figure(book, formulas, figure, settings, column, file):
            if figure["id"] == "scr":
                raise RuntimeError("boom")
            return real(book, formulas, figure, settings, column, file)

        with mock.patch.object(read, "read_figure", read_figure):
            values, _ = self.read([("Capital", table([["SCR", 1], ["MCR", 2]]))], [SCR, MCR])
        self.assertGap(values["scr"], "unexpected_error")
        self.assertEqual(values["mcr"].value, Decimal("2000"))


@unittest.skipUnless(HAS_DATE, "date/ lipsește")
class RealWorkbookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values, cls.hidden = read_workbook(helpers.DATE / "registru_2025.xlsx", CONFIG["figures"], SETTINGS)

    def test_own_funds_total_from_its_formula_cell(self):
        self.assertEqual(self.values["own_funds_total"].value, Decimal("293699300"))
        self.assertIn("formulă", self.values["own_funds_total"].source)

    def test_diversification_is_positive(self):
        self.assertEqual(self.values["scr_diversification"].value, Decimal("22431900"))

    def test_mcr_is_a_gap_with_the_row_note(self):
        self.assertEqual(self.values["mcr"].reason[1]["note"], "în lucru, actuariat")

    def test_hidden_sheet_listed(self):
        self.assertEqual(self.hidden, [("Capital_vechi", "hidden")])

    def test_every_other_figure_found(self):
        self.assertEqual([v.id for v in self.values.values() if v.status != "ok"], ["mcr"])


def fact(**changes):
    base = {"id": "f", "statement": "AGA a aprobat dividende", "document": "proces_verbal_AGA_2025-04-24.txt", "page": 1,
            "quote": "distribuirea de dividende în valoare totală de 15.000.000 lei", "confirmed_by": "Ana Pop",
            "confirmed_on": "2026-10-26"}
    return {**base, **changes}


@unittest.skipUnless(HAS_DATE, "date/ lipsește")
class FactTest(unittest.TestCase):
    def test_confirmed_quote_found_in_a_text_file(self):
        self.assertIsNone(check_fact(fact(), helpers.DATE))

    def test_quote_found_on_its_pdf_page_only(self):
        quote = "Dividende plătite (fluxuri de numerar din activitatea de finanțare) (15.000.000)"
        on_page = fact(document="situatii_financiare_2025_extras.pdf", quote=quote)
        self.assertIsNone(check_fact(on_page, helpers.DATE))
        self.assertEqual(check_fact(dict(on_page, page=2), helpers.DATE)[0], "fact_not_found")

    def test_quote_found_in_a_word_document(self):
        note = fact(document="nota_functia_actuariala_2026-02-02.docx",
                    quote="Calculele folosesc formula standard. Societatea nu utilizează parametri specifici proprii.")
        self.assertIsNone(check_fact(note, helpers.DATE))

    def test_quote_not_in_the_document(self):
        self.assertEqual(check_fact(fact(quote="dividende de 16.000.000 lei"), helpers.DATE)[0], "fact_not_found")

    def test_scanned_pdf_has_no_text(self):
        minutes = fact(document="proces_verbal_CA_2025-02-18_scanat.pdf", quote="Numărul membrilor Consiliului crește")
        self.assertEqual(check_fact(minutes, helpers.DATE)[0], "fact_not_found")

    def test_unconfirmed_fact_is_not_used(self):
        self.assertEqual(check_fact(fact(confirmed_by=" "), helpers.DATE)[0], "fact_unconfirmed")

    def test_fact_without_a_document_rests_on_its_confirmation(self):
        self.assertIsNone(check_fact(fact(document="", quote=""), helpers.DATE))

    def test_fact_gives_a_figure_in_lei(self):
        dividends = fact(figure="dividends_approved", value="15.000.000", unit="lei")
        value = fact_figure(dividends, None, SETTINGS)
        self.assertEqual((value.id, value.value, value.status), ("dividends_approved", Decimal("15000000"), "ok"))
        self.assertIn("proces_verbal_AGA_2025-04-24.txt, pagina 1", value.source)

    def test_fact_that_fails_gives_a_gap_figure(self):
        dividends = fact(figure="dividends_approved", value="15.000.000", unit="lei", confirmed_by="")
        value = fact_figure(dividends, check_fact(dividends, helpers.DATE), SETTINGS)
        self.assertEqual((value.status, value.reason[0]), ("gap", "fact_unconfirmed"))


class QuoteNormalizationTest(unittest.TestCase):
    def test_line_breaks_and_cedillas_do_not_hide_a_quote(self):
        folder = Path(tempfile.mkdtemp())
        try:
            (folder / "pv.txt").write_text("politica de dividende\naprobată de Consiliul de Administraţie", encoding="utf-8")
            note = fact(document="pv.txt", quote="politica de dividende aprobată de Consiliul de Administrație")
            self.assertIsNone(check_fact(note, folder))
        finally:
            shutil.rmtree(folder)


if __name__ == "__main__":
    unittest.main()
