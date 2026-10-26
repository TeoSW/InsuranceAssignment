"""Write the text. The program only fills placeholders, picks a sentence variant by its condition,
picks direction words from settings.toml and writes gaps whose reasons come from gap_reasons.toml."""

import csv
import re
from decimal import ROUND_HALF_UP, Decimal

from checks import exact
from config import PLACEHOLDER
from read import Value, gap

DECIMALS = {"amount": 1, "percent": 1, "points": 1, "count": 0}  # report rule 5
SCALE = {"amount": Decimal("0.000001"), "percent": 100, "points": 100, "count": 1}  # lei to millions, fraction to %
FACT_DIRECTION = {"up": "creștere", "down": "scădere"}


class Missing(dict):
    def __missing__(self, key):  # a placeholder a person added to a reason without the program filling it
        return "?"


def format_number(value, decimals):
    """Round once, half up, then write it with a dot for thousands and a comma for decimals."""
    rounded = value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    english = f"{abs(rounded) if rounded == 0 else rounded:,.{decimals}f}"  # 1,234.6 (and no "-0.0")
    return english.replace(",", " ").replace(".", ",").replace(" ", ".")


def rounded(kind, value):
    """The number as the report writes it, without its unit: "412,4", "187,4", "18.420"."""
    return format_number(value * SCALE[kind], DECIMALS[kind])


def display(kind, value, formats):
    """A figure as the report shows it: "412,4 mil. lei", "187,4 %", "18.420"."""
    return rounded(kind, value) if kind == "count" else formats[kind].format(number=rounded(kind, value))


def usable(value):
    return value is not None and value.status in ("ok", "decision")


def direction(current, prior):
    """"up" or "down", from the unrounded values, only when the displayed values differ; otherwise None."""
    if not (usable(current) and usable(prior)) or rounded(current.kind, current.value) == rounded(prior.kind, prior.value):
        return None
    return "up" if current.value > prior.value else "down"


def change(current, prior):
    """The size of the change, as its own calculated figure: percent for amounts, points for percents."""
    figure_id, now, before = "change:" + current.id, current.value, prior.value
    if current.kind == "percent":
        return Value(figure_id, "points", abs(now - before), f"calcul: |{exact(now)} − {exact(before)}|", current.label)
    if before == 0:
        return gap({"id": figure_id, "kind": "percent"}, "change_from_zero", label=current.label)
    return Value(figure_id, "percent", abs(now - before) / abs(before),
                 f"calcul: |{exact(now)} − {exact(before)}| / {exact(before)}", current.label)


def reason_text(value, cfg, explanations):
    """The catalog text of a figure's gap reason, plus what the documents say about it."""
    name, args = value.reason
    args = Missing(args)
    if name == "conflict":
        args["values"] = "; ".join(f"{display(value.kind, Decimal(text), cfg['settings']['format'])} în {source}"
                                   for text, source in value.candidates)
    return "; ".join([cfg["gap_reasons"][name].format_map(args)] + explanations.get(value.id, []))


def render_section(template, sentences, figures, facts, problems, cfg):
    """The section: each {sentence id} in the template becomes its sentence or one gap.
    Returns (text, the calculated sizes of change, which get their own line in trasabilitate.csv)."""
    variants, calculated = {}, {}
    for sentence in sentences:
        variants.setdefault(sentence["id"], []).append(sentence)
    facts = {fact["id"]: fact for fact in facts}
    explanations = {}
    for fact in facts.values():
        if "explains" in fact and problems.get(fact["id"]) is None:
            text = cfg["gap_reasons"]["fact_explains"].format_map(Missing(fact))
            explanations.setdefault(fact["explains"], []).append(text)
    context = (figures, facts, problems, cfg, explanations, calculated)
    text = re.sub(r"\{(\w+)\}", lambda match: write_sentence(variants[match.group(1)], *context), template)
    return text, calculated


def write_sentence(variants, figures, facts, problems, cfg, explanations, calculated):
    """The first variant whose condition holds, filled; or one gap with every reason."""
    gap_words = cfg["settings"]["words"]["gap"]
    for variant in variants:
        holds = condition(variant.get("when", ""), figures, facts, problems)
        if holds is None:  # the condition needs a figure that is a gap
            missing = figures[condition_figure(variant["when"].split())]
            return gap_words.format(reason=reason_text(missing, cfg, explanations))
        if holds:
            break
    reasons = [cfg["gap_reasons"][problems[name][0]].format_map(Missing(problems[name][1]))
               for name in variant.get("needs", []) if problems.get(name)]

    def fill(match):
        prefix, name = match.groups()
        if name in ("year", "prior_year") and not prefix:
            return str(cfg["settings"]["reporting_year" if name == "year" else "prior_year"])
        value = figures.get("prior:" + name if prefix == "prior" else name)
        if prefix == "direction":
            return cfg["settings"]["words"][direction(value, figures.get("prior:" + name))]
        if prefix == "change":
            value = calculated["change:" + name] = change(value, figures["prior:" + name])
        if usable(value):
            return display(value.kind, value.value, cfg["settings"]["format"])
        reasons.append(reason_text(value, cfg, explanations))
        return ""

    text = PLACEHOLDER.sub(fill, variant["text"])
    return gap_words.format(reason="; ".join(reasons)) if reasons else text


def condition(when, figures, facts, problems):
    """True or False for "X == 0", "X > 0", "changed X", "fact F" (or no condition).
    None when the condition needs figure X and X is a gap."""
    words = when.split()
    if not words:
        return True
    if words[0] == "fact":
        fact = facts[words[1]]
        if problems.get(words[1]) is not None:
            return False
        if "direction" not in fact:
            return True
        found = direction(figures.get(fact["about"]), figures.get("prior:" + fact["about"]))
        return FACT_DIRECTION.get(found) == fact["direction"]
    value = figures.get(condition_figure(words))
    if not usable(value):
        return None
    if words[0] == "changed":
        return direction(value, figures.get("prior:" + words[1])) is not None
    return value.value == 0 if words[1] == "==" else value.value > 0


def condition_figure(words):
    """The figure a condition looks at: X in "X == 0", "X > 0" and "changed X"."""
    return words[1] if words[0] == "changed" else words[0]


STATUS = {"ok": "ok", "gap": "gol", "conflict": "conflict", "decision": "decizie"}
RESULT = {"ok": "ok", "conflict": "CONFLICT", "not_checked": "nu s-a putut verifica"}


def write_trace(path, figures, cfg):
    """trasabilitate.csv: one line per figure, with its exact value, what the text shows, and why."""
    with open(path, "w", encoding="utf-8-sig", newline="") as file:  # BOM and ";" so Excel opens it in columns
        writer = csv.writer(file, delimiter=";")
        writer.writerow(["cifra", "valoare", "afisat", "sursa", "eticheta", "unitate", "stare", "motiv"])
        for value in figures.values():
            shown = display(value.kind, value.value, cfg["settings"]["format"]) if usable(value) else ""
            reason = "" if usable(value) else reason_text(value, cfg, {})
            writer.writerow([value.id, exact(value.value) if value.value is not None else "", shown, value.source,
                             value.label, value.unit, STATUS[value.status], reason])


def approval(cfg, section):
    """"aprobat de X la Y" for a section whose text is approved; None otherwise."""
    record = cfg["approvals"].get(section, {})
    if record.get("approved_by") and record.get("approved_on"):
        return f"aprobat de {record['approved_by']} la {record['approved_on']}"
    return None


def write_checks(path, report, cfg):
    """verificari.md: what was read, checked and decided, so a person can see where every gap comes from."""
    if report.get("errors"):
        blocks = [("Configurația are erori: nu s-a scris niciun draft", [f"- {e}" for e in report["errors"]], None)]
    else:
        conflicts = [f"- {value.id} („{value.label}”): " + "; ".join(f"`{t}` din {s}" for t, s in value.candidates)
                     for value in report["figures"].values() if value.status == "conflict"]
        decisions = []
        for line in report["decisions"]:
            d = line["decision"]
            decisions.append(f"- {d['figure']}: ales `{d['chosen']}` din {d['values']}; sursa: {d['source']}; motiv: {d['reason']}; "
                             f"propusă de {d['proposed_by']}, aprobată de {d['approved_by']} la {d['date']}; "
                             + ("aplicată" if line["applied"] else "NU se aplică (nu există conflictul sau valorile s-au schimbat)"))
        facts = []
        for fact in cfg["facts"]:
            problem = report["problems"][fact["id"]]
            state = "folosit" if problem is None else cfg["gap_reasons"][problem[0]].format_map(Missing(problem[1]))
            where = f"{fact['document']}, pagina {fact['page']}" if fact["document"] else "fără document"
            facts.append(f"- {fact['id']} ({where}; confirmat de: {fact['confirmed_by'] or '-'} {fact['confirmed_on']}): {state}")
        blocks = [
            ("Fișiere de intrare (SHA-256)", [f"- {name}: {sha}" for name, sha in report["checksums"]], None),
            ("Foi ascunse (nu au fost citite)", [f"- {title} ({state})" for title, state in report["hidden"]], "- niciuna"),
            ("Verificări între cifre", [f"- {line['check']}: {RESULT[line['result']]}" for line in report["checks"]], None),
            ("Conflicte (așteaptă o decizie în config/decisions.toml)", conflicts, "- niciunul"),
            ("Decizii", decisions, "- niciuna"),
            ("Fapte din documente", facts, None),
            ("Aprobarea textului", [f"- {s}: {approval(cfg, s) or 'NEAPROBAT'}" for s in cfg["settings"]["sections"]], None),
        ]
    lines = ["# Verificări"]
    for title, items, empty in blocks:
        lines += ["", f"## {title}", ""] + (items or ([empty] if empty else []))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
