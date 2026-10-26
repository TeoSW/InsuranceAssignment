"""The one command, end to end, on a temp copy of the project: outputs, robustness, and the acceptance
checks on the real 2025 data. Facts are confirmed only in the temp copy, never in config/."""

import csv
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers
import main

OPENED = []  # every file opened while RECORDING is on (Python audit events)
RECORDING = []


def record_open(event, args):
    if event == "open" and RECORDING and isinstance(args[0], str):
        OPENED.append(Path(args[0]).name)


sys.addaudithook(record_open)


@unittest.skipUnless((helpers.DATE / "registru_2025.xlsx").exists(), "date/ lipsește")
class RunCase(unittest.TestCase):
    confirm = False  # confirm the six document facts in the temp copy
    approve = False  # approve section E in the temp copy

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)  # runs even if setUp fails (tearDown would not)
        helpers.project_copy(self.tmp, confirm=self.confirm, approve=self.approve)

    def run_main(self):
        with mock.patch("builtins.print"):
            return main.main(root=self.tmp, folder=self.tmp / "date")

    def output(self, name):
        return (self.tmp / "output" / name).read_text(encoding="utf-8-sig")


class OutputTest(RunCase):
    def test_writes_the_three_files_and_nothing_else(self):
        (self.tmp / "output").mkdir()
        (self.tmp / "output" / "vechi.txt").write_text("de anul trecut")
        self.assertEqual(self.run_main(), 0)
        self.assertEqual(sorted(p.name for p in (self.tmp / "output").iterdir()),
                         ["sectiunea_E_2025.md", "trasabilitate.csv", "verificari.md"])

    def test_config_error_writes_only_verificari_and_stops(self):
        settings = self.tmp / "config" / "settings.toml"
        settings.write_text(settings.read_text(encoding="utf-8").replace("prior_year = 2024", "prior_year = 2023"), encoding="utf-8")
        self.assertEqual(self.run_main(), 1)
        self.assertEqual([p.name for p in (self.tmp / "output").iterdir()], ["verificari.md"])
        self.assertIn("prior_year", self.output("verificari.md"))

    def test_config_of_the_wrong_type_is_explained_not_a_traceback(self):
        figures = self.tmp / "config" / "figures.toml"
        figures.write_text(figures.read_text(encoding="utf-8").replace('labels = ["MCR"]', 'labels = "MCR"'), encoding="utf-8")
        self.assertEqual(self.run_main(), 1)
        self.assertIn("labels", self.output("verificari.md"))

    def test_an_unexpected_error_is_not_called_a_config_error(self):
        with mock.patch.object(main, "render_section", side_effect=RuntimeError("boom")):
            self.assertEqual(self.run_main(), 1)
        checks = self.output("verificari.md")
        self.assertIn("Eroare neprevăzută", checks)
        self.assertNotIn("Configurația are erori", checks)
        self.assertEqual([p.name for p in (self.tmp / "output").iterdir()], ["verificari.md"])

    def test_damaged_workbook_does_not_crash(self):
        (self.tmp / "date" / "registru_2025.xlsx").write_bytes(b"not a workbook")
        self.assertEqual(self.run_main(), 0)
        self.assertIn("[de completat: fișierul registru_2025.xlsx nu poate fi citit", self.output("sectiunea_E_2025.md"))

    def test_output_that_cannot_be_emptied_stops_with_a_message(self):
        (self.tmp / "output").mkdir()
        with mock.patch("shutil.rmtree", side_effect=PermissionError("trasabilitate.csv este deschis")):
            self.assertEqual(self.run_main(), 1)

    def test_only_allowed_files_are_opened(self):
        RECORDING.append(True)
        try:
            self.run_main()
        finally:
            RECORDING.clear()
        allowed = {"registru_2025.xlsx", "registru_2024.xlsx", "situatii_financiare_2025_extras.pdf",
                   "proces_verbal_AGA_2025-04-24.txt", "nota_functia_actuariala_2026-02-02.docx",
                   "proces_verbal_CA_2025-02-18_scanat.pdf"}
        from_date = {name for name in OPENED if (helpers.DATE / name).exists()}
        self.assertNotIn("raport_Asigurari_Dunarea_2024_extras.txt", OPENED)
        self.assertLessEqual(from_date, allowed)


class UnconfirmedTest(RunCase):
    """The shipped config: no fact is confirmed and the template is not approved."""

    def test_unconfirmed_facts_leave_gaps_and_no_cause(self):
        self.run_main()
        draft = self.output("sectiunea_E_2025.md")
        self.assertTrue(draft.startswith("> ȘABLON NEAPROBAT"))
        self.assertIn("în scădere cu 2,1 % față de 151,9 mil. lei", draft)
        self.assertNotIn("ca urmare a", draft)
        self.assertIn("[de completat: afirmația „fondurile proprii sunt clasificate", draft)


class ApprovedTest(RunCase):
    confirm, approve = True, True

    def test_an_approved_section_has_no_banner(self):
        self.run_main()
        self.assertTrue(self.output("sectiunea_E_2025.md").startswith("# E. GESTIONAREA CAPITALULUI"))
        self.assertIn("- E: aprobat de Test la", self.output("verificari.md"))

    def test_text_changed_after_approval_is_not_approved(self):
        sentences = self.tmp / "config" / "sentences.toml"
        sentences.write_text(sentences.read_text(encoding="utf-8").replace(
            "în principal ca urmare a scăderii riscului de piață", "datorită programului de reasigurare"), encoding="utf-8")
        self.run_main()
        self.assertTrue(self.output("sectiunea_E_2025.md").startswith("> ȘABLON NEAPROBAT"))
        self.assertIn("textul s-a schimbat după aprobare", self.output("verificari.md"))

    def test_verificari_lists_every_gap_of_the_draft(self):
        self.run_main()
        checks = self.output("verificari.md")
        block = checks[checks.index("## Goluri în draft"):checks.index("## Conflicte")]
        self.assertEqual(self.output("sectiunea_E_2025.md").count("[de completat:"), sum(line.startswith("- E, ") for line in block.splitlines()))
        for sentence in ("E1_legal_basis", "E2_ratio", "E2_mcr"):
            self.assertIn(f"- E, {sentence}: ", block)


class AcceptanceTest(RunCase):
    """Master prompt acceptance list, on the real 2025 data, with the document facts confirmed."""
    confirm = True

    def setUp(self):
        super().setUp()
        self.assertEqual(self.run_main(), 0)
        self.draft = self.output("sectiunea_E_2025.md")

    def test_own_funds_from_the_total_row_and_tiers(self):
        self.assertIn("au fost de 293,7 mil. lei, din care fonduri proprii de nivel 1 de 262,4 mil. lei "
                      "și fonduri proprii de nivel 2 de 31,2 mil. lei. Societatea nu a deținut fonduri proprii de nivel 3.", self.draft)

    def test_scr_direction_size_and_cause(self):
        self.assertIn("SCR a fost de 148,8 mil. lei, în scădere cu 2,1 % față de 151,9 mil. lei la sfârșitul anului 2024, "
                      "în principal ca urmare a scăderii riscului de piață.", self.draft)

    def test_no_reinsurance_cause_and_no_2024_cause(self):
        # "reasigurare" does appear, legitimately, in the name of Legea nr. 237/2015
        self.assertNotRegex(self.draft, r"program\w* de reasigurare")
        self.assertNotIn("îmbunătățit", self.draft)
        self.assertNotIn("volumului de prime", self.draft)

    def test_ratio_is_a_gap_showing_both_values(self):
        start = self.draft.index("[de completat: pentru „Rata de solvabilitate”")
        gap = self.draft[start:self.draft.index("]", start)]
        self.assertIn("187,4 %", gap)
        self.assertIn("197,4 %", gap)

    def test_mcr_gap_from_the_row_note_and_the_actuarial_note(self):
        self.assertIn("nota din rând: „în lucru, actuariat”", self.draft)
        self.assertIn("calculul MCR nu este finalizat", self.draft)
        self.assertNotIn("acoperită integral", self.draft.replace("[de completat", "\n[").split("\n[")[0])

    def test_dividends_from_the_financial_statements(self):
        self.assertIn("Societatea a plătit dividende de 15,0 mil. lei", self.draft)

    def test_hidden_sheet_reported_and_its_values_never_used(self):
        self.assertIn("Capital_vechi", self.output("verificari.md"))
        self.assertNotIn("45,6", self.draft)

    def test_size_of_change_has_its_own_trace_line(self):
        with open(self.tmp / "output" / "trasabilitate.csv", encoding="utf-8-sig", newline="") as file:
            rows = {row["cifra"]: row for row in csv.DictReader(file, delimiter=";")}
        self.assertEqual(rows["change:scr"]["afisat"], "2,1 %")
        self.assertEqual((rows["solvency_ratio"]["stare"], rows["mcr"]["stare"]), ("conflict", "gol"))
        self.assertIn("formulă", rows["own_funds_total"]["sursa"])


if __name__ == "__main__":
    unittest.main()
