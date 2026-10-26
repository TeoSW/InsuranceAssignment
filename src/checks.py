"""Checks that run before any figure reaches the text.

cross_checks compares each figure with the same figure from another source: last year's workbook with
this year's "an anterior" column, and the same label in another sheet. Same-value checks must match
exactly. A different value makes the figure a conflict: a gap until a person decides.
"""

from decimal import Decimal

from common import Value, exact, gap

# A difference of exactly this many times means a unit was mislabelled (lei, mii lei, milioane lei).
UNIT_FACTORS = {Decimal(1000), Decimal(1000000)}


def parse_check(check):
    return None, "TODO", None


def run_relations(figures, relations):
    return [{"result": "TODO"} for relation in relations]


def apply_decisions(figures, decisions):
    return [{"applied": "TODO"} for decision in decisions]


def direction(current, prior):
    return "TODO"


def change(current, prior):
    return Value("TODO", "count", Decimal(-1), "TODO", status="TODO", reason=("TODO", {}))


def prior_ids(values):
    """Last year's figures, renamed "prior:<id>" so they can never take this year's place."""
    renamed = {}
    for figure_id, value in values.items():
        value.id = "prior:" + figure_id
        renamed[value.id] = value
    return renamed


def cross_checks(figures, prior_column, elsewhere, settings):
    """Compare figures with their other sources, mark conflicts and doubtful units.
    figures holds this year's figures and last year's ("prior:<id>"); it is updated in place.
    Returns one line per comparison, for verificari.md."""
    current_book, prior_year = settings["workbooks"]["current"], settings["prior_year"]
    lines, doubtful_sheets = [], set()

    for figure_id, others in elsewhere.items():  # the same label in another sheet
        for other in others:
            line = compare(figures[figure_id], other, f"aceeași etichetă în foaia {other.sheet}")
            if line["result"] == "unit":
                doubtful_sheets |= {figures[figure_id].sheet, other.sheet}
            lines.append(line)

    for figure_id, column_value in prior_column.items():  # this year's "an anterior" column
        last_year = figures.get("prior:" + figure_id)
        if last_year is not None and column_value.status == "ok":
            line = compare(last_year, column_value, f"coloana „an anterior” din {current_book}")
            if line["result"] == "unit":
                doubtful_sheets.add(column_value.sheet)  # last year's workbook is the published one
            lines.append(line)

    for figure_id, value in figures.items():  # identical to last year: maybe copied (D6)
        last_year = figures.get("prior:" + figure_id)
        if value.status != "gap" and last_year is not None and last_year.status == "ok" \
                and value.value == last_year.value != 0:
            same_as_prior(value, last_year, prior_year)
            lines.append({"check": f"identică cu {prior_year}", "figure": figure_id, "result": "conflict"})

    for figure_id, value in figures.items():  # a mislabelled unit spoils every amount of its sheet (D5)
        if value.kind == "amount" and value.sheet in doubtful_sheets and not figure_id.startswith("prior:"):
            figures[figure_id] = gap({"id": figure_id, "kind": value.kind}, "unit_doubt", value.source,
                                     label=value.label, sheet=value.sheet, file=current_book)
    return lines


def compare(value, other, check):
    """The same figure from a second source: ok, conflict, unit (off by exactly 1.000), or not_checked."""
    line = {"check": check, "figure": value.id, "result": "ok"}
    if value.status == "gap":
        line["result"] = "not_checked"
    elif value.value != other.value:
        if differs_by_a_unit(value.value, other.value):
            line["result"] = "unit"
        else:
            add_candidate(value, other.value, other.source)
            line["result"] = "conflict"
    return line


def differs_by_a_unit(a, b):
    """One value is exactly 1.000 or 1.000.000 times the other."""
    if a == 0 or b == 0:
        return False
    return abs(a / b) in UNIT_FACTORS or abs(b / a) in UNIT_FACTORS


def add_candidate(value, number, source):
    """A second source gives another number for the same figure: it waits for a decision."""
    if not value.candidates:
        value.candidates = [(exact(value.value), value.source)]
    if (exact(number), source) not in value.candidates:
        value.candidates.append((exact(number), source))
    value.status = "conflict"
    value.reason = ("conflict", {"label": value.label or value.id})


def same_as_prior(value, last_year, prior_year):
    """A non-zero value identical to last year's may have been copied: it waits for a decision."""
    if not value.candidates:
        value.candidates = [(exact(value.value), value.source)]
    value.status = "conflict"
    if len(value.candidates) == 1:  # no other conflict to report
        value.reason = ("same_as_prior", {"label": value.label or value.id, "prior_year": prior_year,
                                          "prior_source": last_year.source})
