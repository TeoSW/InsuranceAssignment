"""Cross-checks between sources: last year's workbook, this year's "an anterior" column, the same
label in another sheet, a unit mislabelled by exactly 1.000 (D5), a value identical to last year's (D6)."""

import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import helpers
from helpers import make_book, table
from checks import cross_checks, prior_ids
from common import Value
from config import load_config
from workbook import read_elsewhere, read_figures

CONFIG = load_config(helpers.ROOT / "config")[0]
SETTINGS = CONFIG["settings"]
SCR = {"id": "scr", "kind": "amount", "sheets": ["Capital"], "labels": ["SCR"]}


def amount(figure_id, number, sheet="Capital", source="registru_2025.xlsx, foaia Capital"):
    return Value(figure_id, "amount", Decimal(number), source, label=figure_id, unit="mii lei", sheet=sheet)


def last_year(figure_id, number):
    return amount("prior:" + figure_id, number, source="registru_2024.xlsx, foaia Capital")


class PriorColumnTest(unittest.TestCase):
    def test_agreeing_column_leaves_last_years_figure_ok(self):
        figures = {"scr": amount("scr", "148763200"), "prior:scr": last_year("scr", "151900000")}
        lines = cross_checks(figures, {"scr": amount("scr", "151900000")}, {}, SETTINGS)
        self.assertEqual(figures["prior:scr"].status, "ok")
        self.assertEqual([line["result"] for line in lines], ["ok"])

    def test_different_column_makes_last_years_figure_a_conflict(self):
        figures = {"scr": amount("scr", "148763200"), "prior:scr": last_year("scr", "151900000")}
        cross_checks(figures, {"scr": amount("scr", "150000000")}, {}, SETTINGS)
        self.assertEqual(figures["prior:scr"].status, "conflict")
        self.assertEqual([text for text, source in figures["prior:scr"].candidates], ["151900000", "150000000"])
        self.assertEqual(figures["scr"].status, "ok")

    def test_column_off_by_a_thousand_doubts_every_amount_of_that_sheet(self):
        ratio = Value("solvency_ratio", "percent", Decimal("1.974"), "registru_2025.xlsx, foaia Capital", sheet="Capital")
        figures = {"scr": amount("scr", "148763.2"), "mcr": amount("mcr", "45570"), "solvency_ratio": ratio,
                   "scr_market": amount("scr_market", "41902600", sheet="SCR_module"),
                   "prior:scr": last_year("scr", "151900000")}
        cross_checks(figures, {"scr": amount("scr", "151900")}, {}, SETTINGS)
        self.assertEqual([figures[i].reason[0] for i in ("scr", "mcr")], ["unit_doubt", "unit_doubt"])
        self.assertEqual([figures[i].status for i in ("solvency_ratio", "scr_market", "prior:scr")], ["ok", "ok", "ok"])


class OtherSheetTest(unittest.TestCase):
    def test_same_label_elsewhere_with_another_value_is_a_conflict(self):
        figures = {"scr": amount("scr", "148763200")}
        other = amount("scr", "151900000", sheet="Copie", source="registru_2025.xlsx, foaia Copie")
        cross_checks(figures, {}, {"scr": [other]}, SETTINGS)
        self.assertEqual(figures["scr"].status, "conflict")
        self.assertEqual([text for text, source in figures["scr"].candidates], ["148763200", "151900000"])

    def test_same_label_elsewhere_with_the_same_value_is_fine(self):
        figures = {"scr": amount("scr", "148763200")}
        cross_checks(figures, {}, {"scr": [amount("scr", "148763200.0", sheet="SCR_module")]}, SETTINGS)
        self.assertEqual(figures["scr"].status, "ok")

    def test_other_sheet_off_by_a_thousand_doubts_both_sheets(self):
        figures = {"scr": amount("scr", "148763.2"), "scr_market": amount("scr_market", "41902600", sheet="SCR_module"),
                   "dividends": amount("dividends", "15000000", sheet="Altele")}
        cross_checks(figures, {}, {"scr": [amount("scr", "148763200", sheet="SCR_module")]}, SETTINGS)
        self.assertEqual([figures[i].reason[0] for i in ("scr", "scr_market")], ["unit_doubt", "unit_doubt"])
        self.assertEqual(figures["dividends"].status, "ok")

    def test_a_gap_stays_a_gap(self):
        figures = {"scr": Value("scr", "amount", status="gap", reason=("value_missing", {}))}
        cross_checks(figures, {}, {"scr": [amount("scr", "151900000", sheet="Copie")]}, SETTINGS)
        self.assertEqual((figures["scr"].status, figures["scr"].reason[0]), ("gap", "value_missing"))


class SameAsLastYearTest(unittest.TestCase):
    def test_value_identical_to_last_year_waits_for_a_decision(self):
        figures = {"mcr": amount("mcr", "45570000"), "prior:mcr": last_year("mcr", "45570000")}
        cross_checks(figures, {}, {}, SETTINGS)
        self.assertEqual((figures["mcr"].status, figures["mcr"].reason[0]), ("conflict", "same_as_prior"))
        self.assertEqual(figures["mcr"].reason[1]["prior_year"], 2024)

    def test_zero_like_last_year_is_fine(self):
        figures = {"own_funds_t3": amount("own_funds_t3", "0"), "prior:own_funds_t3": last_year("own_funds_t3", "0")}
        cross_checks(figures, {}, {}, SETTINGS)
        self.assertEqual(figures["own_funds_t3"].status, "ok")


class PriorIdsTest(unittest.TestCase):
    def test_last_years_figures_are_renamed(self):
        renamed = prior_ids({"scr": amount("scr", "151900000")})
        self.assertEqual(list(renamed), ["prior:scr"])
        self.assertEqual(renamed["prior:scr"].id, "prior:scr")


class ReadElsewhereTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_finds_the_label_in_other_visible_sheets_only(self):
        path = make_book(self.tmp / "registru.xlsx", [
            ("Capital", table([["SCR", 148763.2]])),
            ("SCR_module", table([["SCR", 148763.2]])),
            ("Capital_vechi", table([["SCR", 151900]], "Valori în lei"), "hidden")])
        found = read_elsewhere(path, [SCR], SETTINGS)
        self.assertEqual([(value.sheet, value.value) for value in found["scr"]], [("SCR_module", Decimal("148763200"))])

    def test_sheet_without_the_label_is_skipped(self):
        path = make_book(self.tmp / "registru.xlsx", [("Capital", table([["SCR", 1]])), ("Prime", table([["Total", 2]]))])
        self.assertEqual(read_elsewhere(path, [SCR], SETTINGS), {})


@unittest.skipUnless((helpers.DATE / "registru_2024.xlsx").exists(), "date/ lipsește")
class RealDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        figures = CONFIG["figures"]
        current_book, prior_book = helpers.DATE / "registru_2025.xlsx", helpers.DATE / "registru_2024.xlsx"
        cls.figures = {**read_figures(current_book, figures, SETTINGS)[0],
                       **prior_ids(read_figures(prior_book, figures, SETTINGS)[0])}
        prior_column = read_figures(current_book, figures, SETTINGS, "prior")[0]
        cls.lines = cross_checks(cls.figures, prior_column, read_elsewhere(current_book, figures, SETTINGS), SETTINGS)

    def test_last_years_scr_comes_from_the_2024_workbook(self):
        scr = self.figures["prior:scr"]
        self.assertEqual((scr.status, scr.value), ("ok", Decimal("151900000")))
        self.assertIn("registru_2024.xlsx", scr.source)

    def test_2024_diversification_stored_negative_reads_positive(self):
        self.assertEqual(self.figures["prior:scr_diversification"].value, Decimal("28500000"))

    def test_scr_is_the_same_in_both_sheets(self):
        self.assertEqual(self.figures["scr"].status, "ok")
        self.assertIn(("scr", "ok"), [(line["figure"], line["result"]) for line in self.lines if "SCR_module" in line["check"]])

    def test_ratio_identical_to_2024_waits_for_a_decision(self):
        ratio = self.figures["solvency_ratio"]
        self.assertEqual((ratio.status, ratio.reason[0]), ("conflict", "same_as_prior"))

    def test_no_other_conflict(self):
        self.assertEqual([i for i, value in self.figures.items() if value.status == "conflict"], ["solvency_ratio"])


if __name__ == "__main__":
    unittest.main()
