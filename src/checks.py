"""Checks that run before any figure reaches the text: last year's column, a value identical to last
year's (maybe copied), the relations from relations.toml, and the decisions that resolve conflicts.
A figure in conflict keeps every value found for it (candidates) and waits for a decision."""

from decimal import ROUND_HALF_UP, Decimal

from config import figures_in

RATIO_TOLERANCE = Decimal("0.05")  # percentage points between the displayed ratio and the calculated one


def exact(number):
    """A Decimal as plain digits, the way verificari.md prints it and decisions.toml stores it."""
    return format(number.normalize(), "f")


def as_prior(values):
    """Last year's figures, renamed "prior:<id>" so they can never take this year's place."""
    for value in values.values():
        value.id = "prior:" + value.id
    return {value.id: value for value in values.values()}


def mark_conflict(value, other=None):
    """The figure waits for a decision. other = (another number for it, its source), if there is one."""
    if not value.candidates:
        value.candidates = [(exact(value.value), value.source)]
    if other and (exact(other[0]), other[1]) not in value.candidates:
        value.candidates.append((exact(other[0]), other[1]))
    value.status = "conflict"
    value.reason = ("conflict", {"label": value.label or value.id})


def check_prior_column(figures, prior_column):
    """This year's "an anterior" column must equal last year's workbook, exactly. An empty cell is not
    reported; a comparison that cannot run for any other reason gets a "not_checked" line."""
    lines = []
    for figure_id, column_value in prior_column.items():
        last_year = figures.get("prior:" + figure_id)
        check = f"{figure_id}: coloana „an anterior” = registrul anului trecut"
        if column_value.value is None or last_year is None or last_year.value is None:
            if column_value.reason[:1] not in (("value_missing",), ("value_missing_note",)):
                lines.append({"check": check, "result": "not_checked"})
            continue
        same = column_value.value == last_year.value
        if not same:
            mark_conflict(last_year, (column_value.value, column_value.source))
        lines.append({"check": check, "result": "ok" if same else "conflict"})
    return lines


def check_same_as_prior(figures, prior_year):
    """A non-zero value identical to last year's may have been copied: it waits for a decision."""
    lines = []
    for figure_id, value in figures.items():
        last_year = figures.get("prior:" + figure_id)
        if value.value is not None and last_year and last_year.value is not None and value.value == last_year.value != 0:
            mark_conflict(value)
            value.reason = ("same_as_prior", {"label": value.label or value.id, "prior_year": prior_year,
                                              "prior_source": last_year.source})
            lines.append({"check": f"{figure_id}: identică cu {prior_year}", "result": "conflict"})
    return lines


def marked(relation):
    """The figures that become conflicts if the relation fails, or gaps if it cannot be checked."""
    if relation["type"] in ("sum", "equal"):
        return figures_in(relation)
    return [relation["r"] if relation["type"] == "ratio" else relation["a"]]


def inputs(relation):
    """The figures a relation checks the others against: all of a sum or equal; the rest for ratio, less, positive."""
    return [name for name in figures_in(relation) if relation["type"] in ("sum", "equal") or name not in marked(relation)]


def evaluate(relation, figures):
    """(holds?, {figure id: (the number the other side gives it, source)}) for a relation with all its figures."""
    value = {name: figures[name].value for name in figures_in(relation)}
    if relation["type"] == "sum":
        minus = relation.get("minus", [])
        total = sum(value[name] for name in relation["parts"]) - sum(value[name] for name in minus)
        source = "calcul: " + " + ".join(relation["parts"]) + "".join(" − " + name for name in minus)
        return value[relation["total"]] == total, {relation["total"]: (total, source)}
    if relation["type"] == "equal":
        a, b = relation["a"], relation["b"]
        return value[a] == value[b], {a: (value[b], figures[b].source), b: (value[a], figures[a].source)}
    if relation["type"] == "less":
        return value[relation["a"]] < value[relation["b"]], {}
    if relation["type"] == "positive":
        return value[relation["a"]] > 0, {}
    if value[relation["b"]] == 0:
        return False, {}  # the ratio cannot be calculated
    calculated = value[relation["a"]] / value[relation["b"]]
    displayed = (value[relation["r"]] * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)  # as the text shows it
    holds = abs(displayed - calculated * 100) <= RATIO_TOLERANCE
    a, b = (figures[relation[key]].label or relation[key] for key in ("a", "b"))  # the labels a reader knows
    return holds, {relation["r"]: (calculated, f"calcul: „{a}” / „{b}”")}


def run_relations(figures, relations):
    """Check every relation, in file order. Returns one line per relation for verificari.md."""
    lines = []
    for relation in relations:
        names = figures_in(relation)
        description = relation["type"] + ": " + ", ".join(names)
        total = figures.get(relation.get("total"))
        parts = relation.get("parts", []) + relation.get("minus", [])
        if total is not None and total.reason[:1] == ("formula_no_value",) \
                and all(figures[name].value is not None for name in parts):  # a formula with no saved value
            number, source = evaluate(relation, figures)[1][total.id]
            total.value, total.status, total.reason = number, "ok", ()
            total.source = f"{source} (formula din {total.source} nu are valoare salvată)"
        missing = [name for name in names if figures[name].value is None]
        if missing:
            for name in marked(relation):
                if figures[name].value is not None:
                    figures[name].status, figures[name].value = "gap", None
                    figures[name].reason = ("unverified", {"label": figures[name].label or name,
                                                           "missing": ", ".join(missing)})
            lines.append({"check": description, "result": "not_checked"})
            continue
        disputed = [name for name in inputs(relation) if figures[name].status == "conflict"]
        if disputed:  # a relation cannot confirm figures against a figure in conflict
            for name in marked(relation):
                if figures[name].status == "ok":
                    figures[name].status, figures[name].value = "gap", None
                    figures[name].reason = ("depends_on_conflict", {"label": figures[name].label or name,
                                                                    "conflict": ", ".join(disputed)})
            lines.append({"check": description, "result": "not_checked"})
            continue
        holds, others = evaluate(relation, figures)
        if not holds:
            for name in marked(relation):
                mark_conflict(figures[name], others.get(name))
        lines.append({"check": description, "result": "ok" if holds else "conflict"})
    return lines


def apply_decisions(figures, decisions):
    """A decision applies only while the conflicting values are exactly the ones it stores."""
    lines = []
    for decision in decisions:
        value = figures.get(decision["figure"])
        in_conflict = value is not None and value.status == "conflict"
        applied = in_conflict and sorted({text for text, _ in value.candidates}) == sorted(set(decision["values"]))
        when = {"label": value.label or value.id if value else decision["figure"], "date": str(decision["date"])}
        if applied and decision["chosen"] == "gap":
            value.status, value.value = "gap", None
            value.reason = ("decision_gap", {**when, "approved_by": decision["approved_by"], "reason": decision["reason"]})
        elif applied:
            source = dict(value.candidates)[decision["chosen"]]
            value.status, value.value, value.reason = "decision", Decimal(decision["chosen"]), ()
            value.source = f"{source}; ales prin decizia din {decision['date']}, aprobată de {decision['approved_by']}"
        elif in_conflict:
            value.reason = ("decision_stale", when)
        lines.append({"decision": decision, "applied": applied})
    return lines
