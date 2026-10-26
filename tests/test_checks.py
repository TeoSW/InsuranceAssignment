"""Checks before the text: the seven relations, last year's column, a value identical to last year's (D6),
and decisions that resolve conflicts only while their stored values still match."""

import unittest
from decimal import Decimal

import helpers
from checks import apply_decisions, as_prior, check_prior_column, check_same_as_prior, run_relations
from config import load_config
from read import Value, read_workbook

CONFIG = load_config(helpers.ROOT / "config")[0]
SETTINGS = CONFIG["settings"]
D = Decimal
RATIO_2025 = "1.974273879561612011572754552"


def amount(figure_id, number, source=None):
    return Value(figure_id, "amount", D(number), source or f"registru, {figure_id}", label=figure_id)


def missing(figure_id, reason="value_missing"):
    return Value(figure_id, "amount", status="gap", reason=(reason, {}), label=figure_id)


def ratio(number):
    return Value("solvency_ratio", "percent", D(number), "registru_2025.xlsx, foaia Capital, celula C12", label="Rata de solvabilitate")


def tiers(t1="262449600", t2="31249700", t3="0", total="293699300"):
    return {"own_funds_t1": amount("own_funds_t1", t1), "own_funds_t2": amount("own_funds_t2", t2),
            "own_funds_t3": amount("own_funds_t3", t3), "own_funds_total": amount("own_funds_total", total)}


SUM_TIERS = {"type": "sum", "total": "own_funds_total", "parts": ["own_funds_t1", "own_funds_t2", "own_funds_t3"]}
SUM_BASIC = {"type": "sum", "total": "scr_basic", "parts": ["scr_underwriting", "scr_market", "scr_counterparty"],
             "minus": ["scr_diversification"]}
SUM_SCR = {"type": "sum", "total": "scr_in_modules", "parts": ["scr_basic", "scr_operational"]}
EQUAL_SCR = {"type": "equal", "a": "scr", "b": "scr_in_modules"}
RATIO = {"type": "ratio", "r": "solvency_ratio", "a": "own_funds_total", "b": "scr"}
LESS = {"type": "less", "a": "mcr", "b": "scr"}
POSITIVE_SCR = {"type": "positive", "a": "scr"}
POSITIVE_MCR = {"type": "positive", "a": "mcr"}


def modules(basic="135493000", diversification="22431900"):
    return {"scr_underwriting": amount("scr_underwriting", "104215000"), "scr_market": amount("scr_market", "41902600"),
            "scr_counterparty": amount("scr_counterparty", "11807300"),
            "scr_diversification": amount("scr_diversification", diversification),
            "scr_basic": amount("scr_basic", basic) if basic else missing("scr_basic", "formula_no_value"),
            "scr_operational": amount("scr_operational", "13270200"), "scr_in_modules": amount("scr_in_modules", "148763200")}


class SumTest(unittest.TestCase):
    def test_tiers_add_up(self):
        figures = tiers()
        self.assertEqual(run_relations(figures, [SUM_TIERS])[0]["result"], "ok")
        self.assertEqual({value.status for value in figures.values()}, {"ok"})
        self.assertEqual(figures["own_funds_t2"].why,
                         ["verificată: own_funds_total = own_funds_t1 + own_funds_t2 + own_funds_t3"])

    def test_sums_must_match_exactly(self):
        figures = tiers(total="293699400")  # 100 lei more: invisible at one decimal of a million
        run_relations(figures, [SUM_TIERS])
        self.assertEqual({value.status for value in figures.values()}, {"conflict"})

    def test_failed_sum_gives_the_calculated_total_as_a_second_value(self):
        figures = tiers(total="284600000")
        run_relations(figures, [SUM_TIERS])
        self.assertEqual([text for text, source in figures["own_funds_total"].candidates], ["284600000", "293699300"])

    def test_formula_without_a_saved_value_is_computed_from_the_parts(self):
        figures = tiers()
        figures["own_funds_total"] = missing("own_funds_total", "formula_no_value")
        run_relations(figures, [SUM_TIERS])
        total = figures["own_funds_total"]
        self.assertEqual((total.status, total.value), ("ok", D("293699300")))
        self.assertTrue(total.source.startswith("calcul"))
        self.assertEqual(total.why[0], "calculată din valorile nerotunjite ale componentelor (formula nu are valoare salvată)")

    def test_an_empty_cell_that_is_not_a_formula_is_not_computed(self):
        figures = tiers()
        figures["own_funds_total"] = missing("own_funds_total")
        run_relations(figures, [SUM_TIERS])
        self.assertEqual(figures["own_funds_total"].status, "gap")

    def test_relation_that_cannot_be_checked_turns_its_figures_into_gaps(self):
        figures = tiers()
        figures["own_funds_t1"] = missing("own_funds_t1")
        self.assertEqual(run_relations(figures, [SUM_TIERS])[0]["result"], "not_checked")
        for figure_id in ("own_funds_t2", "own_funds_t3", "own_funds_total"):
            self.assertEqual((figures[figure_id].status, figures[figure_id].reason[0]), ("gap", "unverified"))

    def test_a_computed_total_is_checked_by_the_next_relation(self):
        figures = dict(modules(basic=None), scr=amount("scr", "148763200"))
        lines = run_relations(figures, [SUM_BASIC, SUM_SCR, EQUAL_SCR])
        self.assertEqual([line["result"] for line in lines], ["ok", "ok", "ok"])
        self.assertEqual(figures["scr_basic"].value, D("135493000"))

    def test_diversification_with_the_wrong_sign_is_caught(self):
        figures = modules(diversification="-22431900")
        run_relations(figures, [SUM_BASIC])
        self.assertEqual(figures["scr_diversification"].status, "conflict")


class EqualLessRatioTest(unittest.TestCase):
    def test_scr_differs_between_the_two_sheets(self):
        figures = {"scr": amount("scr", "151900000"), "scr_in_modules": amount("scr_in_modules", "148763200")}
        run_relations(figures, [EQUAL_SCR])
        self.assertEqual([text for text, source in figures["scr"].candidates], ["151900000", "148763200"])
        self.assertEqual(figures["scr_in_modules"].status, "conflict")

    def test_2024_ratio_within_the_tolerance(self):
        # 284,6 / 151,9 = 187,36 %, stated 187,4 %
        figures = {"solvency_ratio": ratio("1.874"), "own_funds_total": amount("own_funds_total", "284600000"),
                   "scr": amount("scr", "151900000")}
        run_relations(figures, [RATIO])
        self.assertEqual(figures["solvency_ratio"].status, "ok")

    def test_2025_ratio_conflict_lists_stated_and_calculated(self):
        figures = {"solvency_ratio": ratio("1.874"), "own_funds_total": amount("own_funds_total", "293699300"),
                   "scr": amount("scr", "148763200")}
        run_relations(figures, [RATIO])
        self.assertEqual([text for text, source in figures["solvency_ratio"].candidates], ["1.874", RATIO_2025])
        self.assertEqual((figures["own_funds_total"].status, figures["scr"].status), ("ok", "ok"))

    def test_ratio_is_compared_as_the_text_shows_it(self):
        # stated 1,97475 is printed 197,5 %; the calculation is 197,427 %: 0,073 apart on the displayed value
        figures = {"solvency_ratio": ratio("1.97475"), "own_funds_total": amount("own_funds_total", "293699300"),
                   "scr": amount("scr", "148763200")}
        run_relations(figures, [RATIO])
        self.assertEqual(figures["solvency_ratio"].status, "conflict")

    def test_less_fails(self):
        figures = {"mcr": amount("mcr", "200"), "scr": amount("scr", "100")}
        run_relations(figures, [LESS])
        self.assertEqual((figures["mcr"].status, figures["scr"].status), ("conflict", "ok"))

    def test_missing_mcr_does_not_turn_the_scr_into_a_gap(self):
        figures = {"mcr": missing("mcr"), "scr": amount("scr", "148763200")}
        run_relations(figures, [LESS])
        self.assertEqual(figures["scr"].status, "ok")


class ConflictSpreadsTest(unittest.TestCase):
    """A relation cannot confirm figures against a figure that is already in conflict."""

    def test_a_module_changed_without_its_totals_keeps_the_scr_out_of_the_text(self):
        figures = dict(modules(), scr=amount("scr", "148763200"))
        figures["scr_market"] = amount("scr_market", "51902600")  # +10.000 mii lei, totals unchanged
        run_relations(figures, [SUM_BASIC, SUM_SCR, EQUAL_SCR])
        self.assertEqual(figures["scr_basic"].status, "conflict")
        self.assertEqual((figures["scr_in_modules"].status, figures["scr_in_modules"].reason[0]),
                         ("gap", "depends_on_conflict"))
        self.assertEqual(figures["scr"].status, "gap")

    def test_a_ratio_checked_against_a_total_in_conflict_is_not_confirmed(self):
        figures = tiers(t1="272449600")  # tier 1 +10 m, total unchanged
        figures.update(solvency_ratio=ratio("1.974274"), scr=amount("scr", "148763200"))
        run_relations(figures, [SUM_TIERS, RATIO])
        self.assertEqual(figures["own_funds_total"].status, "conflict")
        self.assertEqual((figures["solvency_ratio"].status, figures["solvency_ratio"].reason[0]),
                         ("gap", "depends_on_conflict"))

    def test_the_figure_being_checked_may_itself_be_in_conflict(self):
        # the 2025 ratio is already a conflict (identical to 2024): it is still compared with the calculation
        figures = {"solvency_ratio": ratio("1.874"), "own_funds_total": amount("own_funds_total", "293699300"),
                   "scr": amount("scr", "148763200")}
        figures["solvency_ratio"].status = "conflict"
        run_relations(figures, [RATIO])
        self.assertEqual([text for text, source in figures["solvency_ratio"].candidates], ["1.874", RATIO_2025])

    def test_scr_and_mcr_must_be_above_zero(self):
        figures = {"scr": amount("scr", "0"), "mcr": amount("mcr", "0")}
        run_relations(figures, [POSITIVE_SCR, POSITIVE_MCR])
        self.assertEqual((figures["scr"].status, figures["mcr"].status), ("conflict", "conflict"))

    def test_scr_zero_does_not_stop_the_run(self):
        figures = {"solvency_ratio": ratio("1.874"), "own_funds_total": amount("own_funds_total", "293699300"),
                   "scr": amount("scr", "0")}
        run_relations(figures, [RATIO])  # would divide by zero
        self.assertEqual(figures["solvency_ratio"].status, "conflict")


class PriorYearTest(unittest.TestCase):
    def test_last_years_figures_are_renamed(self):
        renamed = as_prior({"scr": amount("scr", "151900000")})
        self.assertEqual((list(renamed), renamed["prior:scr"].id), (["prior:scr"], "prior:scr"))

    def test_this_years_prior_column_agrees_with_last_years_workbook(self):
        figures = {"prior:scr": amount("prior:scr", "151900000")}
        lines = check_prior_column(figures, {"scr": amount("scr", "151900000")})
        self.assertEqual((lines[0]["result"], figures["prior:scr"].status), ("ok", "ok"))
        self.assertEqual(figures["prior:scr"].why, ["egală cu registru, scr"])

    def test_a_different_prior_column_is_a_conflict_on_last_years_figure(self):
        figures = {"prior:scr": amount("prior:scr", "151900000")}
        check_prior_column(figures, {"scr": amount("scr", "150000000")})
        self.assertEqual([text for text, source in figures["prior:scr"].candidates], ["151900000", "150000000"])

    def test_a_prior_column_that_cannot_be_read_is_reported(self):
        figures = {"prior:scr": amount("prior:scr", "151900000")}
        unreadable = Value("scr", "amount", status="gap", reason=("header_not_found", {}))
        lines = check_prior_column(figures, {"scr": unreadable})
        self.assertEqual([line["result"] for line in lines], ["not_checked"])

    def test_an_empty_prior_cell_is_not_reported(self):
        figures = {"prior:own_funds_t1": amount("prior:own_funds_t1", "251300000")}
        empty = Value("own_funds_t1", "amount", status="gap", reason=("value_missing", {}))
        self.assertEqual(check_prior_column(figures, {"own_funds_t1": empty}), [])

    def test_value_identical_to_last_year_waits_for_a_decision(self):
        figures = {"mcr": amount("mcr", "45570000"), "prior:mcr": amount("prior:mcr", "45570000")}
        check_same_as_prior(figures, 2024)
        self.assertEqual((figures["mcr"].status, figures["mcr"].reason[0]), ("conflict", "same_as_prior"))

    def test_zero_like_last_year_is_fine(self):
        figures = {"own_funds_t3": amount("own_funds_t3", "0"), "prior:own_funds_t3": amount("prior:own_funds_t3", "0")}
        check_same_as_prior(figures, 2024)
        self.assertEqual(figures["own_funds_t3"].status, "ok")


class DecisionTest(unittest.TestCase):
    def conflict(self):
        figures = {"solvency_ratio": ratio("1.874"), "own_funds_total": amount("own_funds_total", "293699300"),
                   "scr": amount("scr", "148763200")}
        run_relations(figures, [RATIO])
        return figures

    def decision(self, chosen, values=("1.874", RATIO_2025)):
        return {"figure": "solvency_ratio", "values": list(values), "chosen": chosen, "source": "nota actuarială",
                "reason": "test", "proposed_by": "Ana Pop", "approved_by": "Ion Ionescu", "date": "2026-10-26"}

    def test_applies_when_its_values_match(self):
        figures = self.conflict()
        lines = apply_decisions(figures, [self.decision(RATIO_2025)])
        value = figures["solvency_ratio"]
        self.assertEqual((value.status, value.value, lines[0]["applied"]), ("decision", D(RATIO_2025), True))
        self.assertIn("Ion Ionescu", value.source)
        self.assertEqual(value.why, ["aleasă prin decizia din 2026-10-26, aprobată de Ion Ionescu"])

    def test_can_keep_the_gap(self):
        figures = self.conflict()
        apply_decisions(figures, [self.decision("gap")])
        self.assertEqual((figures["solvency_ratio"].status, figures["solvency_ratio"].reason[0]), ("gap", "decision_gap"))

    def test_does_not_apply_when_the_values_changed(self):
        figures = self.conflict()
        lines = apply_decisions(figures, [self.decision("1.874", values=("1.874", "1.97"))])
        self.assertEqual((figures["solvency_ratio"].reason[0], lines[0]["applied"]), ("decision_stale", False))

    def test_does_nothing_without_a_conflict(self):
        figures = {"scr": amount("scr", "148763200")}
        lines = apply_decisions(figures, [dict(self.decision("gap"), figure="scr")])
        self.assertEqual((figures["scr"].status, lines[0]["applied"]), ("ok", False))


@unittest.skipUnless((helpers.DATE / "registru_2024.xlsx").exists(), "date/ lipsește")
class RealDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        figures, date = CONFIG["figures"], helpers.DATE
        dividends = {"dividends_paid": amount("dividends_paid", "15000000"),
                     "dividends_approved": amount("dividends_approved", "15000000")}
        cls.figures = {**read_workbook(date / "registru_2025.xlsx", figures, SETTINGS)[0], **dividends,
                       **as_prior(read_workbook(date / "registru_2024.xlsx", figures, SETTINGS)[0])}
        check_prior_column(cls.figures, read_workbook(date / "registru_2025.xlsx", figures, SETTINGS, "prior")[0])
        check_same_as_prior(cls.figures, 2024)
        run_relations(cls.figures, CONFIG["relations"])

    def test_only_the_ratio_is_in_conflict(self):
        self.assertEqual([i for i, value in self.figures.items() if value.status == "conflict"], ["solvency_ratio"])

    def test_ratio_conflict_values(self):
        self.assertEqual([text for text, source in self.figures["solvency_ratio"].candidates], ["1.874", RATIO_2025])

    def test_calculated_ratio_names_its_figures_by_their_labels(self):
        self.assertEqual(self.figures["solvency_ratio"].candidates[1][1],
                         "calcul: „Fonduri proprii eligibile SCR, total” / „SCR”")

    def test_own_funds_scr_and_last_years_scr(self):
        self.assertEqual([self.figures[i].value for i in ("own_funds_total", "scr", "prior:scr")],
                         [D("293699300"), D("148763200"), D("151900000")])

    def test_mcr_stays_a_gap_and_the_scr_survives_it(self):
        self.assertEqual((self.figures["mcr"].status, self.figures["scr"].status), ("gap", "ok"))


if __name__ == "__main__":
    unittest.main()
