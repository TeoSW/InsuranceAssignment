"""2024 round trip: last year's mapping plus registru_2024.xlsx must reproduce the figures published in
raport_2024.txt. Cell addresses appear only here, read from the client's mapping file; the program
itself never uses them. DESIGN.md (section 7) cites this test: it reports the known mapping defect."""

import re
import tomllib
import unittest
from decimal import Decimal

import openpyxl

import helpers
from read import to_decimal
from render import format_number

FILES = ["mapping_2024.toml", "registru_2024.xlsx", "raport_2024.txt"]


def mapped_text(entry, book):
    """The figure as the 2024 report would write it, from the cell the mapping names."""
    value = to_decimal(book[entry["sheet"]][entry["cell"]].value)
    if entry.get("derived") == "share":
        value = value / to_decimal(book[entry["sheet"]][entry["total_cell"]].value)
    if entry["format"] == "mil_lei_1_abs":  # the mapping writes diversification without its minus sign
        value = abs(value)
    if entry["format"] in ("mil_lei_1", "mil_lei_1_abs"):
        return format_number(value / 1_000_000, 1)
    if entry["format"] == "pct_1":
        return format_number(value * 100, 1)
    return format_number(value, 0)  # count


def round_trip(entries):
    """(text, occurrence, what the cell gives) for every mapping entry that does not reproduce the report."""
    book = openpyxl.load_workbook(helpers.DATE / "registru_2024.xlsx", data_only=True)
    report = (helpers.DATE / "raport_2024.txt").read_text(encoding="utf-8")
    tokens = re.findall(r"\d+(?:[.,]\d+)*", report)  # whole numbers: "412,4" is one token, never "12,4"
    mismatches = []
    for entry in entries:
        found = [i for i, token in enumerate(tokens) if token == entry["text"]]
        got = mapped_text(entry, book)
        if len(found) < entry["occurrence"] or got != entry["text"]:
            mismatches.append((entry["text"], entry["occurrence"], f"{entry['sheet']}!{entry['cell']} dă {got}"))
    return mismatches


@unittest.skipUnless(all((helpers.DATE / name).exists() for name in FILES), "date/ lipsește")
class RoundTrip2024Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(helpers.DATE / "mapping_2024.toml", "rb") as file:
            cls.entries = tomllib.load(file)["figure"]

    def test_the_only_figure_not_reproduced_is_the_known_mapping_defect(self):
        mismatches = round_trip(self.entries)
        # "12,6" (investment income) points to Investitii!C7, which holds the share of government bonds
        self.assertEqual(mismatches, [("12,6", 1, "Investitii!C7 dă 0,0")])

    def test_every_other_figure_is_reproduced(self):
        self.assertEqual(len(self.entries) - len(round_trip(self.entries)), 32)

    def test_with_the_defect_fixed_every_figure_is_reproduced(self):
        fixed = [dict(e, cell="C6") if (e["text"], e["cell"]) == ("12,6", "C7") else e for e in self.entries]
        self.assertEqual(round_trip(fixed), [])

    def test_whole_numbers_not_substrings(self):
        report = (helpers.DATE / "raport_2024.txt").read_text(encoding="utf-8")
        self.assertEqual((report.count("12,4"), re.findall(r"\d+(?:[.,]\d+)*", report).count("12,4")), (3, 1))


if __name__ == "__main__":
    unittest.main()
