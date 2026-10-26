"""Writing the text: number format (report rule 5), direction and size of change, sentence variants,
one gap per sentence with reasons from the catalog."""

import copy
import unittest
from decimal import Decimal

import helpers
from config import load_config
from read import Value
from render import change, direction, display, format_number, render_section

CFG = load_config(helpers.ROOT / "config")[0]
FORMATS = CFG["settings"]["format"]
D = Decimal


def amount(figure_id, number, label=None):
    return Value(figure_id, "amount", D(number), f"registru_2025.xlsx, {figure_id}", label=label or figure_id)


def missing(figure_id, reason="value_missing", **args):
    args = {"label": figure_id, "file": "registru_2025.xlsx", "sheet": "Capital", **args}
    return Value(figure_id, "amount", status="gap", reason=(reason, args), label=figure_id)


def render(sentences, figures, facts=(), problems=None, cfg=CFG):
    text, calculated, gaps = render_section("{s}", sentences, figures, list(facts), problems or {}, cfg)
    return text


class FormatTest(unittest.TestCase):
    def test_half_up_not_half_even(self):
        self.assertEqual(format_number(D("0.25"), 1), "0,3")  # ROUND_HALF_EVEN would give 0,2

    def test_exact_decimal_not_float(self):
        self.assertEqual(format_number(D("0.35"), 1), "0,4")  # the float 0.35 would round to 0,3

    def test_rounds_once_on_the_unrounded_value(self):
        self.assertEqual(display("amount", D("45549999"), FORMATS), "45,5 mil. lei")  # twice would give 45,6

    def test_no_negative_zero(self):
        self.assertEqual(format_number(D("-0.04"), 1), "0,0")

    def test_report_formats(self):
        cases = [("amount", "412350000", "412,4 mil. lei"), ("amount", "1234560000", "1.234,6 mil. lei"),
                 ("count", "18420", "18.420"), ("percent", "1.874", "187,4 %"),
                 ("points", "0.1", "10,0 puncte procentuale")]
        for kind, number, shown in cases:
            with self.subTest(kind=kind, number=number):
                self.assertEqual(display(kind, D(number), FORMATS), shown)


class DirectionTest(unittest.TestCase):
    def test_scr_down_by_2_1_percent(self):
        now, before = amount("scr", "148763200"), amount("prior:scr", "151900000")
        self.assertEqual(direction(now, before), "down")
        size = change(now, before)
        self.assertEqual((size.id, display(size.kind, size.value, FORMATS)), ("change:scr", "2,1 %"))
        self.assertIn("151900000", size.source)

    def test_up(self):
        self.assertEqual(direction(amount("scr", "151900000"), amount("prior:scr", "140200000")), "up")

    def test_no_direction_when_the_displayed_values_are_equal(self):
        self.assertIsNone(direction(amount("scr", "148763200"), amount("prior:scr", "148790000")))  # both 148,8

    def test_no_direction_when_a_value_is_a_gap(self):
        self.assertIsNone(direction(amount("scr", "148763200"), missing("prior:scr")))

    def test_change_of_a_percentage_is_in_points(self):
        size = change(Value("r", "percent", D("1.974")), Value("prior:r", "percent", D("1.874")))
        self.assertEqual(display(size.kind, size.value, FORMATS), "10,0 puncte procentuale")

    def test_change_from_zero_is_a_gap(self):
        size = change(amount("own_funds_t3", "5000000"), amount("prior:own_funds_t3", "0"))
        self.assertEqual((size.status, size.reason[0]), ("gap", "change_from_zero"))


TIERS = [{"id": "s", "when": "own_funds_t3 == 0", "text": "Nivel 1: {own_funds_t1}. Fără nivel 3."},
         {"id": "s", "text": "Nivel 1: {own_funds_t1}, nivel 3: {own_funds_t3}."}]
SCR = [{"id": "s", "when": "fact cause", "text": "SCR {scr}, {direction:scr} cu {change:scr} față de {prior:scr} în {prior_year}, din cauza pieței."},
       {"id": "s", "when": "changed scr", "text": "SCR {scr}, {direction:scr} cu {change:scr} față de {prior:scr} în {prior_year}."},
       {"id": "s", "text": "SCR {scr}."}]
CAUSE = {"id": "cause", "statement": "SCR a scăzut din cauza pieței", "document": "nota.docx", "page": 1,
         "about": "scr", "direction": "scădere"}


# The SCR sentences name the fact "cause"; the config check guarantees it exists. Unconfirmed here.
NO_CAUSE = ([CAUSE], {"cause": ("fact_unconfirmed", {"statement": CAUSE["statement"]})})


def scr(prior="151900000"):
    figures = {"scr": amount("scr", "148763200", "SCR")}
    figures["prior:scr"] = amount("prior:scr", prior) if prior else missing("prior:scr")
    return figures


class VariantTest(unittest.TestCase):
    def test_first_variant_whose_condition_holds(self):
        figures = {"own_funds_t1": amount("own_funds_t1", "262449600"), "own_funds_t3": amount("own_funds_t3", "0")}
        self.assertEqual(render(TIERS, figures), "Nivel 1: 262,4 mil. lei. Fără nivel 3.")
        figures["own_funds_t3"] = amount("own_funds_t3", "5000000")
        self.assertEqual(render(TIERS, figures), "Nivel 1: 262,4 mil. lei, nivel 3: 5,0 mil. lei.")

    def test_condition_on_a_figure_that_is_a_gap_makes_one_gap(self):
        figures = {"own_funds_t1": amount("own_funds_t1", "262449600"), "own_funds_t3": missing("own_funds_t3")}
        text = render(TIERS, figures)
        self.assertTrue(text.startswith("[de completat: valoarea pentru „own_funds_t3” lipsește"), text)
        self.assertEqual(text.count("[de completat"), 1)

    def test_a_missing_figure_makes_the_whole_sentence_one_gap(self):
        figures = {"scr": missing("scr", "value_missing_note", note="în lucru, actuariat"), "prior:scr": amount("prior:scr", "1")}
        self.assertEqual(render(SCR, figures, *NO_CAUSE)[:14], "[de completat:")
        self.assertIn("în lucru, actuariat", render(SCR, figures, *NO_CAUSE))

    def test_changed_value_gets_direction_and_size(self):
        self.assertEqual(render(SCR, scr(), *NO_CAUSE), "SCR 148,8 mil. lei, în scădere cu 2,1 % față de 151,9 mil. lei în 2024.")

    def test_size_of_change_is_a_calculated_figure(self):
        text, calculated, gaps = render_section("{s}", SCR, scr(), *NO_CAUSE, CFG)
        self.assertEqual(calculated["change:scr"].value, D("3136800") / D("151900000"))

    def test_same_displayed_value_uses_the_fallback(self):
        self.assertEqual(render(SCR, scr(prior="148790000"), *NO_CAUSE), "SCR 148,8 mil. lei.")

    def test_missing_last_year_uses_the_fallback(self):
        self.assertEqual(render(SCR, scr(prior=None), *NO_CAUSE), "SCR 148,8 mil. lei.")

    def test_cause_when_the_fact_holds_and_its_direction_matches(self):
        self.assertTrue(render(SCR, scr(), [CAUSE], {"cause": None}).endswith("din cauza pieței."))

    def test_no_cause_when_the_document_says_the_opposite(self):
        self.assertNotIn("din cauza", render(SCR, scr(), [dict(CAUSE, direction="creștere")], {"cause": None}))

    def test_no_cause_when_the_fact_is_not_confirmed(self):
        problems = {"cause": ("fact_unconfirmed", {"statement": CAUSE["statement"]})}
        self.assertNotIn("din cauza", render(SCR, scr(), [CAUSE], problems))

    def test_needed_fact_not_confirmed_makes_a_gap(self):
        sentence = [{"id": "s", "needs": ["legal"], "text": "Clasificare conform legii."}]
        problems = {"legal": ("fact_unconfirmed", {"statement": "clasificarea fondurilor proprii"})}
        text = render(sentence, {}, [{"id": "legal"}], problems)
        self.assertEqual(text, "[de completat: afirmația „clasificarea fondurilor proprii” nu a fost confirmată de un om (config/facts.toml)]")

    def test_conflict_gap_lists_each_value_with_its_source(self):
        ratio = Value("solvency_ratio", "percent", D("1.874"), status="conflict", label="Rata de solvabilitate",
                      reason=("conflict", {"label": "Rata de solvabilitate"}),
                      candidates=[("1.874", "registru_2025.xlsx, foaia Capital, celula C12"),
                                  ("1.974273879561612011572754552", "calcul: own_funds_total / scr")])
        text = render([{"id": "s", "text": "Rata: {solvency_ratio}."}], {"solvency_ratio": ratio})
        for part in ("187,4 %", "celula C12", "197,4 %", "own_funds_total / scr"):
            self.assertIn(part, text)

    def test_a_fact_that_explains_a_gap_is_added_to_its_reason(self):
        note = {"id": "note", "statement": "calculul MCR nu este finalizat", "document": "nota.docx", "page": 1,
                "explains": "mcr"}
        text = render([{"id": "s", "text": "MCR {mcr}."}], {"mcr": missing("mcr")}, [note], {"note": None})
        self.assertIn("calculul MCR nu este finalizat (nota.docx)", text)

    def test_every_gap_is_reported_with_its_sentence_and_reason(self):
        sentences = [{"id": "a", "text": "SCR {scr}."}, {"id": "b", "text": "MCR {mcr}."}]
        text, calculated, gaps = render_section("{a} {b}", sentences, {"scr": amount("scr", "1"), "mcr": missing("mcr")},
                                                [], {}, CFG)
        self.assertEqual(gaps, [("b", "valoarea pentru „mcr” lipsește în registru_2025.xlsx, foaia Capital")])

    def test_years_come_from_settings(self):
        cfg = copy.deepcopy(CFG)
        cfg["settings"]["reporting_year"] = 2031
        self.assertEqual(render([{"id": "s", "text": "La 31 decembrie {year}."}], {}, cfg=cfg), "La 31 decembrie 2031.")


if __name__ == "__main__":
    unittest.main()
