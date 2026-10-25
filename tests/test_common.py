"""Number format (report rule 5) and text normalization."""

import unittest
from decimal import Decimal

import helpers  # noqa: F401  (puts src/ on the import path)
from common import display, format_number, normalize_label, normalize_text, parse_ro_number, to_decimal

FORMATS = {"amount": "{number} mil. lei", "percent": "{number} %"}


class RoundingTest(unittest.TestCase):
    def test_half_up_not_half_even(self):
        # ROUND_HALF_EVEN, Decimal's default, would give 0,2
        self.assertEqual(format_number(Decimal("0.25"), 1), "0,3")

    def test_exact_decimal_not_float(self):
        # the float 0.35 is 0.34999..., which would round to 0,3
        self.assertEqual(format_number(Decimal("0.35"), 1), "0,4")

    def test_rounds_once_on_the_unrounded_value(self):
        # rounding first to 45,55 and then to one decimal would give 45,6
        self.assertEqual(display("amount", Decimal("45549999"), FORMATS), "45,5 mil. lei")

    def test_no_negative_zero(self):
        self.assertEqual(format_number(Decimal("-0.04"), 1), "0,0")


class DisplayTest(unittest.TestCase):
    def test_amount_in_millions_of_lei(self):
        self.assertEqual(display("amount", Decimal("412350000"), FORMATS), "412,4 mil. lei")

    def test_amount_over_a_thousand_millions(self):
        self.assertEqual(display("amount", Decimal("1234560000"), FORMATS), "1.234,6 mil. lei")

    def test_count_with_dot_for_thousands(self):
        self.assertEqual(display("count", Decimal("18420"), FORMATS), "18.420")

    def test_percent_from_a_fraction(self):
        self.assertEqual(display("percent", Decimal("1.874"), FORMATS), "187,4 %")


class ToDecimalTest(unittest.TestCase):
    def test_float_keeps_the_digits_written_in_the_file(self):
        # Decimal(231450.6) would be 231450.600000000005820766...
        self.assertEqual(to_decimal(231450.6), Decimal("231450.6"))

    def test_integer(self):
        self.assertEqual(to_decimal(293699), Decimal("293699"))

    def test_not_a_number_gives_none(self):
        for value in (True, "12", None, float("nan")):
            with self.subTest(value=value):
                self.assertIsNone(to_decimal(value))


class RomanianNumberTest(unittest.TestCase):
    def test_dots_for_thousands(self):
        self.assertEqual(parse_ro_number("15.000.000"), Decimal("15000000"))

    def test_comma_for_decimals(self):
        self.assertEqual(parse_ro_number("1.234,5"), Decimal("1234.5"))


class NormalizeTest(unittest.TestCase):
    def test_text_cedilla_and_spaces(self):
        # ţ with a cedilla, a double space, a non-breaking space, a newline
        self.assertEqual(normalize_text(" Risc  de\xa0piaţă \n"), "Risc de piață")

    def test_label_ignores_case(self):
        self.assertEqual(normalize_label("Risc de PIAŢĂ"), "risc de piață")


if __name__ == "__main__":
    unittest.main()
