"""Config load and self-check. Only pure config errors are reported here; they stop the draft."""

import shutil
import tempfile
import unittest
from pathlib import Path

import helpers
from config import load_config

CONFIG = helpers.ROOT / "config"

VALID_DECISION = """
[[decision]]
figure = "solvency_ratio"
values = ["1.874", "1.974273879561612011572754552"]
chosen = "gap"
source = "registru_2025.xlsx, foaia Capital"
reason = "rata din registru nu se potrivește cu calculul"
proposed_by = "Ana Pop"
approved_by = "Ion Ionescu"
date = "2026-10-26"
"""

VALID_RELATION = """
[[relation]]
id = "test_relation"
check = "scr == scr_basic + scr_operational"
tolerance = "0"
marks = ["scr"]
"""

VALID_FACT = """
[[fact]]
id = "test_fact"
statement = "test"
document = "proces_verbal_AGA_2025-04-24.txt"
page = 1
quote = "în valoare totală de 15.000.000 lei"
figure = "test_amount"
value = "15.000.000"
unit = "lei"
confirmed_by = ""
confirmed_on = ""
"""


class ShippedConfigTest(unittest.TestCase):
    def test_shipped_config_has_no_errors(self):
        cfg, errors = load_config(CONFIG)
        self.assertEqual(errors, [])
        self.assertIn("scr", [figure["id"] for figure in cfg["figures"]])


class ConfigCase(unittest.TestCase):
    """Copies the shipped config to a temp folder; each test plants one mistake."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.config = self.tmp / "config"
        shutil.copytree(CONFIG, self.config)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def edit(self, name, old=None, new="", append=""):
        path = self.config / name
        text = path.read_text(encoding="utf-8")
        if old is not None:
            self.assertEqual(text.count(old), 1, f"anchor must appear once: {old}")
            text = text.replace(old, new)
        path.write_text(text + append, encoding="utf-8")

    def errors(self):
        return load_config(self.config)[1]

    def assertError(self, *words):
        """At least one error mentions every word (the shipped config has no errors at all)."""
        errors = self.errors()
        self.assertTrue(any(all(w in e for w in words) for e in errors), f"no error with {words}: {errors}")


class FilesTest(ConfigCase):
    def test_missing_file(self):
        (self.config / "figures.toml").unlink()
        self.assertError("figures.toml")

    def test_toml_syntax_error(self):
        self.edit("settings.toml", append="\n[broken\n")
        self.assertError("settings.toml")

    def test_single_brackets_instead_of_double(self):
        (self.config / "figures.toml").write_text(
            '[figure]\nid = "scr"\nsheets = ["Capital"]\nlabels = ["SCR"]\nkind = "amount"\n', encoding="utf-8")
        self.assertError("figures.toml", "[[figure]]")


class SchemaTest(ConfigCase):
    def test_missing_required_field(self):
        self.edit("figures.toml", append='\n[[figure]]\nid = "extra"\nsheets = ["Capital"]\nkind = "amount"\n')
        self.assertError("extra", "labels")

    def test_unknown_field(self):
        self.edit("decisions.toml", append=VALID_DECISION.replace("approved_by", "aproved_by"))
        self.assertError("aproved_by")

    def test_wrong_type(self):
        self.edit("settings.toml", "reporting_year = 2025", 'reporting_year = "2025"')
        self.assertError("reporting_year")

    def test_unknown_kind(self):
        self.edit("figures.toml", append='\n[[figure]]\nid = "extra"\nsheets = ["Capital"]\nlabels = ["X"]\nkind = "money"\n')
        self.assertError("money")

    def test_id_must_be_a_simple_name(self):
        self.edit("figures.toml", append='\n[[figure]]\nid = "own funds"\nsheets = ["Capital"]\nlabels = ["X"]\nkind = "amount"\n')
        self.assertError("own funds")

    def test_empty_labels(self):
        self.edit("figures.toml", 'labels = ["Rata de solvabilitate"]', "labels = []")
        self.assertError("solvency_ratio", "labels")

    def test_duplicate_figure_id(self):
        self.edit("figures.toml", append='\n[[figure]]\nid = "own_funds_t1"\nsheets = ["Capital"]\nlabels = ["X"]\nkind = "amount"\n')
        self.assertError("figures.toml", "own_funds_t1")


class SettingsTest(ConfigCase):
    def test_prior_year_must_be_the_year_before(self):
        self.edit("settings.toml", "prior_year = 2024", "prior_year = 2023")
        self.assertError("prior_year")

    def test_at_least_one_section(self):
        self.edit("settings.toml", 'sections = ["E"]', "sections = []")
        self.assertError("sections")

    def test_unit_must_be_a_positive_whole_number(self):
        self.edit("settings.toml", '"mii lei" = 1000', '"mii lei" = 0')
        self.assertError("mii lei")


class DecisionTest(ConfigCase):
    def test_valid_decision_accepted(self):
        self.edit("decisions.toml", append=VALID_DECISION)
        self.assertEqual(self.errors(), [])

    def test_toml_date_without_quotes_accepted(self):
        self.edit("decisions.toml", append=VALID_DECISION.replace('"2026-10-26"', "2026-10-26"))
        self.assertEqual(self.errors(), [])

    def test_decision_on_a_prior_year_figure_accepted(self):
        self.edit("decisions.toml", append=VALID_DECISION.replace('"solvency_ratio"', '"prior:scr"'))
        self.assertEqual(self.errors(), [])

    def test_without_source(self):
        self.edit("decisions.toml", append=VALID_DECISION.replace('"registru_2025.xlsx, foaia Capital"', '""'))
        self.assertError("source")

    def test_without_reason(self):
        self.edit("decisions.toml", append=VALID_DECISION.replace('"rata din registru nu se potrivește cu calculul"', '" "'))
        self.assertError("reason")

    def test_last_years_figure_as_source(self):
        self.edit("decisions.toml", append=VALID_DECISION.replace(
            '"registru_2025.xlsx, foaia Capital"', '"Cifra de anul trecut, din raportul publicat"'))
        self.assertError("source")

    def test_same_person_proposes_and_approves(self):
        self.edit("decisions.toml", append=VALID_DECISION.replace('"Ion Ionescu"', '" ana  POP "'))
        self.assertError("approved_by")

    def test_chosen_value_not_among_values(self):
        self.edit("decisions.toml", append=VALID_DECISION.replace('chosen = "gap"', 'chosen = "1.9"'))
        self.assertError("chosen")

    def test_unknown_figure(self):
        self.edit("decisions.toml", append=VALID_DECISION.replace('"solvency_ratio"', '"solvency_rate"'))
        self.assertError("solvency_rate")

    def test_bad_date(self):
        self.edit("decisions.toml", append=VALID_DECISION.replace('"2026-10-26"', '"26.10.2026"'))
        self.assertError("date")


class FactTest(ConfigCase):
    def test_valid_fact_accepted(self):
        self.edit("facts.toml", append=VALID_FACT)
        self.assertEqual(self.errors(), [])

    def test_document_not_in_the_allowed_list(self):
        self.edit("facts.toml", append=VALID_FACT.replace(
            "proces_verbal_AGA_2025-04-24.txt", "raport_Asigurari_Dunarea_2024_extras.txt"))
        self.assertError("raport_Asigurari_Dunarea_2024_extras.txt")

    def test_quote_required_when_there_is_a_document(self):
        self.edit("facts.toml", 'quote = "politica de dividende aprobată de Consiliul de Administrație în 2023 rămâne neschimbată"',
                  'quote = ""')
        self.assertError("dividend_policy", "quote")

    def test_page_starts_at_one(self):
        self.edit("facts.toml", append=VALID_FACT.replace("page = 1", "page = 0"))
        self.assertError("test_fact", "page")

    def test_about_must_be_a_workbook_figure(self):
        self.edit("facts.toml", 'about = "scr"', 'about = "scr_totl"')
        self.assertError("scr_totl")

    def test_value_must_be_inside_the_quote(self):
        self.edit("facts.toml", append=VALID_FACT.replace('value = "15.000.000"', 'value = "16.000.000"'))
        self.assertError("test_fact", "16.000.000")

    def test_unit_must_be_known(self):
        self.edit("facts.toml", append=VALID_FACT.replace('unit = "lei"', 'unit = "euro"'))
        self.assertError("euro")

    def test_figure_value_and_unit_go_together(self):
        self.edit("facts.toml", append=VALID_FACT.replace('unit = "lei"\n', ""))
        self.assertError("test_fact", "unit")

    def test_fact_figure_cannot_reuse_a_workbook_figure_id(self):
        self.edit("facts.toml", append=VALID_FACT.replace('"test_amount"', '"mcr"'))
        self.assertError("test_fact", "mcr")

    def test_direction_needs_the_figure_it_is_about(self):
        self.edit("facts.toml", 'about = "scr"\n', "")
        self.assertError("scr_cause_market", "about")

    def test_direction_must_be_increase_or_decrease(self):
        self.edit("facts.toml", 'direction = "scădere"', 'direction = "stabil"')
        self.assertError("stabil")


class RelationTest(ConfigCase):
    def test_valid_relation_accepted(self):
        self.edit("relations.toml", append=VALID_RELATION)
        self.assertEqual(self.errors(), [])

    def test_unknown_figure_in_check(self):
        self.edit("relations.toml", append=VALID_RELATION.replace("scr_operational", "scr_operationl"))
        self.assertError("scr_operationl")

    def test_marks_a_figure_outside_the_check(self):
        self.edit("relations.toml", append=VALID_RELATION.replace('marks = ["scr"]', 'marks = ["mcr"]'))
        self.assertError("test_relation", "mcr")

    def test_fills_a_figure_outside_the_check(self):
        self.edit("relations.toml", append=VALID_RELATION + 'fills = "mcr"\n')
        self.assertError("test_relation", "fills")

    def test_marks_cannot_be_empty(self):
        self.edit("relations.toml", append=VALID_RELATION.replace('marks = ["scr"]', "marks = []"))
        self.assertError("test_relation", "marks")

    def test_tolerance_must_be_a_number(self):
        self.edit("relations.toml", append=VALID_RELATION.replace('tolerance = "0"', 'tolerance = "zero"'))
        self.assertError("test_relation", "tolerance")

    def test_tolerance_cannot_be_negative(self):
        self.edit("relations.toml", append=VALID_RELATION.replace('tolerance = "0"', 'tolerance = "-0.05"'))
        self.assertError("test_relation", "tolerance")


class GapReasonsTest(ConfigCase):
    def test_every_reason_the_program_uses_has_a_text(self):
        self.edit("gap_reasons.toml", 'file_missing = "fișierul {file} nu există în folderul din care rulează programul"\n', "")
        self.assertError("file_missing")


if __name__ == "__main__":
    unittest.main()
