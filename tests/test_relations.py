"""Relations, recomputed formulas, conflicts, decisions, direction and size of change."""

import unittest
from decimal import Decimal

import helpers
from checks import apply_decisions, change, direction, parse_check, run_relations
from common import Value, display
from config import load_config

CONFIG = load_config(helpers.ROOT / "config")[0]
RELATIONS = {relation["id"]: relation for relation in CONFIG["relations"]}
FORMATS = CONFIG["settings"]["format"]
D = Decimal
RATIO_2025 = "1.974273879561612011572754552"


def amount(figure_id, number, source=None):
    return Value(figure_id, "amount", D(number), source or f"registru_2025.xlsx, {figure_id}", label=figure_id)


def ratio(number):
    return Value("solvency_ratio", "percent", D(number), "registru_2025.xlsx, foaia Capital, celula C12", label="Rata de solvabilitate")


def missing(figure_id, formula=False):
    return Value(figure_id, "amount", status="gap", reason=("value_missing", {}), label=figure_id, formula=formula)


def tiers(t1="262449600", t2="31249700", t3="0", total="293699300"):
    return {"own_funds_t1": amount("own_funds_t1", t1), "own_funds_t2": amount("own_funds_t2", t2),
            "own_funds_t3": amount("own_funds_t3", t3), "own_funds_total": amount("own_funds_total", total)}


def run(figures, *relation_ids):
    return run_relations(figures, [RELATIONS[i] for i in relation_ids])


class ParseTest(unittest.TestCase):
    def test_a_check_has_two_sides_and_one_comparison(self):
        left, comparison, right = parse_check("scr == scr_basic + scr_operational")
        self.assertEqual(comparison, "==")

    def test_anything_but_arithmetic_is_refused(self):
        for check in ("__import__('os').system('x') == 1", "scr", "a == b == c", "len(a) == 1"):
            with self.subTest(check=check):
                self.assertRaises(ValueError, parse_check, check)


class SumTest(unittest.TestCase):
    def test_tiers_add_up_on_the_real_values(self):
        figures = tiers()
        lines = run(figures, "own_funds_tiers")
        self.assertEqual(lines[0]["result"], "ok")
        self.assertEqual({value.status for value in figures.values()}, {"ok"})

    def test_sums_must_match_exactly(self):
        figures = tiers(total="293699400")  # 100 lei more: invisible at one decimal of a million
        run(figures, "own_funds_tiers")
        self.assertEqual({value.status for value in figures.values()}, {"conflict"})

    def test_failed_sum_gives_the_calculated_total_as_a_second_value(self):
        figures = tiers(total="284600000")
        run(figures, "own_funds_tiers")
        self.assertEqual([text for text, source in figures["own_funds_total"].candidates], ["284600000", "293699300"])
        self.assertEqual(figures["own_funds_t1"].reason[0], "relation_failed")

    def test_relation_that_cannot_be_checked_turns_its_figures_into_gaps(self):
        figures = tiers()
        figures["own_funds_t1"] = missing("own_funds_t1")
        lines = run(figures, "own_funds_tiers")
        self.assertEqual(lines[0]["result"], "not_checked")
        for figure_id in ("own_funds_t2", "own_funds_t3", "own_funds_total"):
            self.assertEqual((figures[figure_id].status, figures[figure_id].reason[0]), ("gap", "unverified"))

    def test_formula_without_saved_value_is_computed(self):
        figures = tiers()
        figures["own_funds_total"] = missing("own_funds_total", formula=True)
        run(figures, "own_funds_tiers")
        total = figures["own_funds_total"]
        self.assertEqual((total.status, total.value), ("ok", D("293699300")))
        self.assertTrue(total.source.startswith("calcul"))

    def test_an_empty_cell_that_is_not_a_formula_is_not_computed(self):
        figures = tiers()
        figures["own_funds_total"] = missing("own_funds_total")
        run(figures, "own_funds_tiers")
        self.assertEqual(figures["own_funds_total"].status, "gap")

    def test_filled_figure_is_used_by_the_next_relation(self):
        figures = {"scr_underwriting": amount("scr_underwriting", "104215000"), "scr_market": amount("scr_market", "41902600"),
                   "scr_counterparty": amount("scr_counterparty", "11807300"),
                   "scr_diversification": amount("scr_diversification", "22431900"),
                   "scr_basic": missing("scr_basic", formula=True), "scr_operational": amount("scr_operational", "13270200"),
                   "scr": amount("scr", "148763200")}
        lines = run(figures, "scr_basic_from_modules", "scr_from_basic")
        self.assertEqual([line["result"] for line in lines], ["filled", "ok"])
        self.assertEqual(figures["scr_basic"].value, D("135493000"))

    def test_diversification_with_the_wrong_sign_is_caught(self):
        figures = {"scr_underwriting": amount("scr_underwriting", "104215000"), "scr_market": amount("scr_market", "41902600"),
                   "scr_counterparty": amount("scr_counterparty", "11807300"),
                   "scr_diversification": amount("scr_diversification", "-22431900"), "scr_basic": amount("scr_basic", "135493000")}
        run(figures, "scr_basic_from_modules")
        self.assertEqual(figures["scr_diversification"].status, "conflict")


class RatioTest(unittest.TestCase):
    def test_2024_ratio_within_the_tolerance_on_the_displayed_value(self):
        # 284,6 / 151,9 = 187,36 %, stated 187,4 %
        figures = {"solvency_ratio": ratio("1.874"), "own_funds_total": amount("own_funds_total", "284600000"),
                   "scr": amount("scr", "151900000")}
        run(figures, "ratio_from_own_funds")
        self.assertEqual(figures["solvency_ratio"].status, "ok")

    def test_2025_ratio_conflict_lists_stated_and_calculated(self):
        figures = {"solvency_ratio": ratio("1.874"), "own_funds_total": amount("own_funds_total", "293699300"),
                   "scr": amount("scr", "148763200")}
        run(figures, "ratio_from_own_funds")
        self.assertEqual(figures["solvency_ratio"].status, "conflict")
        self.assertEqual([text for text, source in figures["solvency_ratio"].candidates], ["1.874", RATIO_2025])
        self.assertEqual((figures["own_funds_total"].status, figures["scr"].status), ("ok", "ok"))

    def test_less_than(self):
        figures = {"mcr": amount("mcr", "200"), "scr": amount("scr", "100")}
        run(figures, "mcr_below_scr")
        self.assertEqual((figures["mcr"].status, figures["mcr"].reason[0]), ("conflict", "relation_failed"))
        self.assertEqual(figures["scr"].status, "ok")


class DecisionTest(unittest.TestCase):
    def conflict(self):
        figures = {"solvency_ratio": ratio("1.874"), "own_funds_total": amount("own_funds_total", "293699300"),
                   "scr": amount("scr", "148763200")}
        run(figures, "ratio_from_own_funds")
        return figures

    def decision(self, chosen, values=("1.874", RATIO_2025)):
        return {"figure": "solvency_ratio", "values": list(values), "chosen": chosen, "source": "nota actuarială",
                "reason": "test", "proposed_by": "Ana Pop", "approved_by": "Ion Ionescu", "date": "2026-10-26"}

    def test_decision_applies_when_its_values_match(self):
        figures = self.conflict()
        lines = apply_decisions(figures, [self.decision(RATIO_2025)])
        ratio_value = figures["solvency_ratio"]
        self.assertEqual((ratio_value.status, ratio_value.value), ("decision", D(RATIO_2025)))
        self.assertIn("Ion Ionescu", ratio_value.source)
        self.assertTrue(lines[0]["applied"])

    def test_decision_can_keep_the_gap(self):
        figures = self.conflict()
        apply_decisions(figures, [self.decision("gap")])
        self.assertEqual((figures["solvency_ratio"].status, figures["solvency_ratio"].reason[0]), ("gap", "decision_gap"))

    def test_decision_with_other_values_does_not_apply(self):
        figures = self.conflict()
        lines = apply_decisions(figures, [self.decision("1.874", values=("1.874", "1.97"))])
        self.assertEqual((figures["solvency_ratio"].status, figures["solvency_ratio"].reason[0]), ("conflict", "decision_stale"))
        self.assertFalse(lines[0]["applied"])

    def test_decision_without_a_conflict_does_nothing(self):
        figures = {"scr": amount("scr", "148763200")}
        lines = apply_decisions(figures, [dict(self.decision("gap"), figure="scr")])
        self.assertEqual(figures["scr"].status, "ok")
        self.assertFalse(lines[0]["applied"])


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
        # 148,763 and 148,790 both show as 148,8 mil. lei
        self.assertIsNone(direction(amount("scr", "148763200"), amount("prior:scr", "148790000")))

    def test_no_direction_when_a_value_is_a_gap(self):
        self.assertIsNone(direction(amount("scr", "148763200"), missing("prior:scr")))

    def test_change_of_a_percentage_is_in_points(self):
        size = change(ratio("1.974"), Value("prior:solvency_ratio", "percent", D("1.874")))
        self.assertEqual(display(size.kind, size.value, FORMATS), "10,0 puncte procentuale")

    def test_change_from_zero_is_a_gap(self):
        size = change(amount("own_funds_t3", "5000000"), amount("prior:own_funds_t3", "0"))
        self.assertEqual((size.status, size.reason[0]), ("gap", "change_from_zero"))


if __name__ == "__main__":
    unittest.main()
