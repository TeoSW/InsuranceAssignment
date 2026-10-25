"""Shared helpers: text normalization, exact numbers, the report number format,
the Value record that carries one figure, and the names of the gap reasons."""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# Old Romanian letters with a cedilla, mapped to the correct comma-below letters.
CEDILLA_TO_COMMA = str.maketrans({"ş": "ș", "Ş": "Ș", "ţ": "ț", "Ţ": "Ț"})

# Decimals shown in the report, per kind of figure (report rule 5).
DECIMALS = {"amount": 1, "percent": 1, "count": 0}

# Every gap reason the program can give. config/gap_reasons.toml must have a text for each.
GAP_REASONS = (
    "file_missing", "file_unreadable", "unexpected_error",
    "sheet_not_found", "sheet_hidden", "sheet_ambiguous", "header_not_found", "header_ambiguous",
    "unit_not_found", "unit_unknown", "label_not_found", "label_repeated", "alias_two_rows", "row_two_figures",
    "value_missing", "value_missing_note", "value_text", "formula_no_value",
)


@dataclass
class Value:
    """One figure: its exact value, where it was found, and why it is a gap if it is one."""
    id: str
    kind: str                       # amount (in lei) | percent (a fraction) | count
    value: Decimal | None = None    # None when the figure is a gap
    source: str = ""                # file, sheet and cell; document and page; or the calculation
    label: str = ""                 # the row label as written in the workbook
    unit: str = ""                  # the unit read from the sheet, for amounts
    status: str = "ok"              # ok | gap | conflict | decision
    reason: tuple = ()              # (gap reason name, {placeholder: text}) when not ok
    formula: bool = False           # the cell has a formula but no saved value (a relation may fill it)


def gap(figure, reason, source="", **args):
    """A figure that cannot be filled, with a reason name from gap_reasons.toml and its placeholders."""
    return Value(figure["id"], figure["kind"], source=source, label=args.get("label", ""),
                 status="gap", reason=(reason, args))


def normalize_text(text):
    """Comma-below ș and ț, one space between words, no spaces at the ends."""
    return re.sub(r"\s+", " ", text.translate(CEDILLA_TO_COMMA)).strip()


def normalize_label(text):
    """Like normalize_text, ignoring case. Used to compare labels and names."""
    return normalize_text(text).casefold()


def to_decimal(cell_value):
    """A number read from a workbook, as an exact Decimal. Anything else gives None."""
    if isinstance(cell_value, bool) or not isinstance(cell_value, (int, float)):
        return None
    number = Decimal(str(cell_value))  # str() keeps the digits stored in the file
    return number if number.is_finite() else None


def parse_ro_number(text):
    """A number written the Romanian way ("15.000.000", "1.234,5") as a Decimal."""
    return Decimal(text.replace(".", "").replace(",", "."))


def format_number(value, decimals):
    """Round once, half up, then write it with a dot for thousands and a comma for decimals."""
    rounded = value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = abs(rounded)  # no "-0,0"
    english = f"{rounded:,.{decimals}f}"  # 1,234.6
    return english.replace(",", " ").replace(".", ",").replace(" ", ".")


def in_report_units(kind, value):
    """Lei become millions of lei, a fraction becomes a percentage, a count stays as it is."""
    if kind == "amount":
        return value / 1_000_000
    if kind == "percent":
        return value * 100
    return value


def display(kind, value, formats):
    """A figure as the report shows it: "412,4 mil. lei", "187,4 %", "18.420"."""
    number = format_number(in_report_units(kind, value), DECIMALS[kind])
    if kind == "count":
        return number
    return formats[kind].format(number=number)
