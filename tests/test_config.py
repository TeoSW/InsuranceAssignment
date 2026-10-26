"""Config self-check. Only config problems are errors here; any error stops the draft."""

import shutil
import tempfile
import unittest
from pathlib import Path

import helpers
from config import load_config, text_sha256

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

FIGURE = '\n[[figure]]\nid = "extra"\nsheets = ["Capital"]\nlabels = ["X"]\nkind = "amount"\n'


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
        (self.config / "figures.toml").write_text(FIGURE.replace("[[figure]]", "[figure]"), encoding="utf-8")
        self.assertError("figures.toml", "[[figure]]")


class FigureTest(ConfigCase):
    def test_missing_required_field(self):
        self.edit("figures.toml", append=FIGURE.replace('labels = ["X"]\n', ""))
        self.assertError("figures.toml", "labels")

    def test_duplicate_id(self):
        self.edit("figures.toml", append=FIGURE.replace('"extra"', '"own_funds_t1"'))
        self.assertError("figures.toml", "own_funds_t1")

    def test_unknown_kind(self):
        self.edit("figures.toml", append=FIGURE.replace('"amount"', '"money"'))
        self.assertError("money")

    def test_one_label_cannot_belong_to_two_figures_in_the_same_sheet(self):
        self.edit("figures.toml", append=FIGURE.replace('labels = ["X"]', 'labels = ["MCR"]'))
        self.assertError("MCR", "mcr")

    def test_same_label_in_two_sheets_is_allowed(self):
        self.edit("figures.toml", append=FIGURE.replace('["Capital"]', '["Daune"]').replace('["X"]', '["MCR"]'))
        self.assertEqual(self.errors(), [])


class SettingsTest(ConfigCase):
    def test_prior_year_must_be_the_year_before(self):
        self.edit("settings.toml", "prior_year = 2024", "prior_year = 2023")
        self.assertError("prior_year")

    def test_missing_table(self):
        self.edit("settings.toml", "[output]", "[outputs]")
        self.assertError("settings.toml", "output")


class RelationTest(ConfigCase):
    def test_unknown_type(self):
        self.edit("relations.toml", append='\n[[relation]]\ntype = "product"\na = "scr"\nb = "mcr"\n')
        self.assertError("product")

    def test_missing_field_for_its_type(self):
        self.edit("relations.toml", append='\n[[relation]]\ntype = "ratio"\nr = "solvency_ratio"\na = "own_funds_total"\n')
        self.assertError("relations.toml", "b")

    def test_unknown_figure(self):
        self.edit("relations.toml", append='\n[[relation]]\ntype = "less"\na = "mcr"\nb = "scr_totl"\n')
        self.assertError("scr_totl")


class FactTest(ConfigCase):
    def test_valid_fact_accepted(self):
        self.edit("facts.toml", append=VALID_FACT)
        self.assertEqual(self.errors(), [])

    def test_document_not_in_the_allowed_list(self):
        self.edit("facts.toml", append=VALID_FACT.replace(
            "proces_verbal_AGA_2025-04-24.txt", "raport_Asigurari_Dunarea_2024_extras.txt"))
        self.assertError("raport_Asigurari_Dunarea_2024_extras.txt")

    def test_value_must_be_inside_the_quote(self):
        # a typo in value would otherwise pass the quote check and reach the text
        self.edit("facts.toml", append=VALID_FACT.replace('value = "15.000.000"', 'value = "16.000.000"'))
        self.assertError("test_fact", "16.000.000")

    def test_figure_needs_value_and_unit(self):
        self.edit("facts.toml", append=VALID_FACT.replace('unit = "lei"\n', ""))
        self.assertError("test_fact", "unit")

    def test_unit_must_be_known(self):
        self.edit("facts.toml", append=VALID_FACT.replace('unit = "lei"', 'unit = "euro"'))
        self.assertError("euro")

    def test_fact_figure_cannot_reuse_a_workbook_figure_id(self):
        self.edit("facts.toml", append=VALID_FACT.replace('"test_amount"', '"mcr"'))
        self.assertError("test_fact", "mcr")

    def test_direction_must_be_increase_or_decrease(self):
        self.edit("facts.toml", 'about = "scr"\ndirection = "scădere"', 'about = "scr"\ndirection = "stabil"')
        self.assertError("stabil")

    def test_about_must_be_a_known_figure(self):
        self.edit("facts.toml", 'about = "scr"', 'about = "scr_totl"')
        self.assertError("scr_totl")


class DecisionTest(ConfigCase):
    def test_valid_decision_accepted(self):
        self.edit("decisions.toml", append=VALID_DECISION)
        self.assertEqual(self.errors(), [])

    def test_toml_date_without_quotes_accepted(self):
        self.edit("decisions.toml", append=VALID_DECISION.replace('"2026-10-26"', "2026-10-26"))
        self.assertEqual(self.errors(), [])

    def test_decision_on_last_years_figure_accepted(self):
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


class SentenceTest(ConfigCase):
    def test_template_placeholder_must_be_a_sentence(self):
        self.edit("templates/E.md", append="\n{E2_unknown}\n")
        self.assertError("E2_unknown")

    def test_every_sentence_ends_with_a_fallback_without_condition(self):
        self.edit("sentences.toml", 'id = "E2_ratio"\ntext', 'id = "E2_ratio"\nwhen = "changed solvency_ratio"\ntext')
        self.assertError("E2_ratio")

    def test_direction_only_in_a_changed_or_fact_variant(self):
        self.edit("sentences.toml", append='\n[[sentence]]\nid = "E2_extra"\nwhen = "mcr > 0"\ntext = "{direction:scr}"\n'
                                           '\n[[sentence]]\nid = "E2_extra"\ntext = "x"\n')
        self.assertError("E2_extra", "direction")

    def test_condition_must_be_understood(self):
        self.edit("sentences.toml", 'when = "own_funds_t3 == 0"', 'when = "own_funds_t3 is zero"')
        self.assertError("own_funds_t3 is zero")

    def test_needed_fact_must_exist(self):
        self.edit("sentences.toml", 'needs = ["standard_formula"]', 'needs = ["standard_formulae"]')
        self.assertError("standard_formulae")


class TextHashTest(ConfigCase):
    def test_line_endings_do_not_change_the_hash(self):
        before = text_sha256(self.config, "E")
        template = self.config / "templates" / "E.md"
        template.write_bytes(template.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(text_sha256(self.config, "E"), before)

    def test_a_changed_word_changes_the_hash(self):
        before = text_sha256(self.config, "E")
        self.edit("sentences.toml", "la sfârșitul anului {prior_year}.", "la finalul anului {prior_year}.")
        self.assertNotEqual(text_sha256(self.config, "E"), before)


class GapReasonsTest(ConfigCase):
    def test_every_reason_the_program_uses_has_a_text(self):
        self.edit("gap_reasons.toml", 'file_missing = "fișierul {file} nu există în folderul din care rulează programul"\n', "")
        self.assertError("file_missing")


if __name__ == "__main__":
    unittest.main()
