"""Load the config files and check them before any figure is read (the self-check).

load_config returns the config and a list of errors. Any error stops the run before a draft is
written. Only pure config problems are checked here. Problems that depend on the workbook (an
alias matching two rows, two figures on one row) are found while reading and become gaps.
"""

import re
import tomllib
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from common import DECIMALS, GAP_REASONS, normalize_label, normalize_text, parse_ro_number

# Figure, fact and relation ids: lower-case letters, digits and "_", so a check can use them.
ID = re.compile(r"[a-z][a-z0-9_]*$")
NAME_IN_CHECK = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
DIRECTIONS = ("creștere", "scădere")


def is_text(value):
    return isinstance(value, str)


def is_texts(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def is_whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


def is_table(value):
    return isinstance(value, dict)


def is_date(value):
    if isinstance(value, date):  # a TOML date written without quotes
        return True
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def is_date_or_empty(value):
    return value == "" or is_date(value)


TYPE_NAMES = {is_text: "text", is_texts: "listă de texte", is_whole: "număr întreg", is_table: "tabel",
              is_date: "dată AAAA-LL-ZZ", is_date_or_empty: "dată AAAA-LL-ZZ sau gol"}

# Schemas: field -> (type check, required?)
SETTINGS = {"reporting_year": (is_whole, True), "prior_year": (is_whole, True), "sections": (is_texts, True),
            "workbooks": (is_table, True), "documents": (is_table, True), "reading": (is_table, True),
            "units": (is_table, True), "words": (is_table, True), "format": (is_table, True),
            "decisions": (is_table, True), "output": (is_table, True)}
SETTINGS_TABLES = {"workbooks": ["current", "prior"],
                   "reading": ["current_column", "prior_column", "unit_prefix"],
                   "words": ["up", "down", "gap", "not_approved"],
                   "format": ["amount", "percent", "points"],
                   "output": ["draft", "trace", "checks"]}
FIGURE = {"id": (is_text, True), "sheets": (is_texts, True), "labels": (is_texts, True), "kind": (is_text, True),
          "labels_stored_negative": (is_texts, False)}
RELATION = {"id": (is_text, True), "check": (is_text, True), "marks": (is_texts, True),
            "tolerance": (is_text, False), "fills": (is_text, False)}
FACT = {"id": (is_text, True), "statement": (is_text, True), "document": (is_text, True), "page": (is_whole, True),
        "quote": (is_text, True), "confirmed_by": (is_text, True), "confirmed_on": (is_date_or_empty, True),
        "about": (is_text, False), "direction": (is_text, False), "explains_gap": (is_text, False),
        "figure": (is_text, False), "value": (is_text, False), "unit": (is_text, False)}
DECISION = {"figure": (is_text, True), "values": (is_texts, True), "chosen": (is_text, True),
            "source": (is_text, True), "reason": (is_text, True), "proposed_by": (is_text, True),
            "approved_by": (is_text, True), "date": (is_date, True)}


def load_config(config_dir):
    """Read config/*.toml and run the self-check. Returns (config, errors)."""
    cfg, errors = {}, []
    for name in ("settings", "figures", "relations", "facts", "decisions", "gap_reasons"):
        try:
            with open(Path(config_dir) / f"{name}.toml", "rb") as file:
                cfg[name] = tomllib.load(file)
        except FileNotFoundError:
            errors.append(f"lipsește fișierul config/{name}.toml")
        except tomllib.TOMLDecodeError as error:
            errors.append(f"config/{name}.toml nu poate fi citit: {error}")
    if errors:
        return cfg, errors
    for name, key in (("figures", "figure"), ("relations", "relation"), ("facts", "fact"), ("decisions", "decision")):
        cfg[name] = cfg[name].get(key, [])
        if not (isinstance(cfg[name], list) and all(is_table(entry) for entry in cfg[name])):
            errors.append(f"{name}.toml: fiecare intrare se scrie [[{key}]]")
    if errors:
        return cfg, errors

    errors = check_settings(cfg["settings"])
    if errors:
        return cfg, errors  # the other checks need valid settings
    errors += check_figures(cfg["figures"])
    workbook_ids = {figure.get("id") for figure in cfg["figures"]}
    errors += check_facts(cfg["facts"], cfg["settings"], workbook_ids)
    known_ids = workbook_ids | {fact["figure"] for fact in cfg["facts"] if is_text(fact.get("figure"))}
    errors += check_relations(cfg["relations"], known_ids)
    errors += check_decisions(cfg["decisions"], known_ids, cfg["settings"])
    errors += check_gap_reasons(cfg["gap_reasons"])
    return cfg, errors


def check_fields(entry, schema, where):
    """Missing required fields, fields of the wrong type, unknown fields."""
    errors = []
    for name, (is_type, required) in schema.items():
        if name not in entry:
            if required:
                errors.append(f"{where}: lipsește câmpul „{name}”")
        elif not is_type(entry[name]):
            errors.append(f"{where}: câmpul „{name}” trebuie să fie {TYPE_NAMES[is_type]}")
    errors += [f"{where}: câmp necunoscut „{name}”" for name in entry if name not in schema]
    return errors


def where(file, number, entry, key):
    return f"{file}, intrarea {number} („{entry.get(key, '?')}”)"


def check_settings(settings):
    errors = check_fields(settings, SETTINGS, "settings.toml")
    if errors:
        return errors
    for table, keys in SETTINGS_TABLES.items():
        errors += check_fields(settings[table], {key: (is_text, True) for key in keys}, f"settings.toml [{table}]")
    errors += check_fields(settings["decisions"], {"forbidden_sources": (is_texts, True)}, "settings.toml [decisions]")
    if settings["prior_year"] != settings["reporting_year"] - 1:
        errors.append("settings.toml: prior_year trebuie să fie reporting_year - 1")
    if not settings["sections"]:
        errors.append("settings.toml: sections nu poate fi gol")
    errors += [f"settings.toml [units]: „{name}” trebuie să fie un număr întreg pozitiv"
               for name, lei in settings["units"].items() if not (is_whole(lei) and lei > 0)]
    return errors


def check_figures(figures):
    errors, seen = [], set()
    for number, figure in enumerate(figures, 1):
        here = where("figures.toml", number, figure, "id")
        problems = check_fields(figure, FIGURE, here)
        if problems:
            errors += problems
            continue
        if not ID.match(figure["id"]):
            errors.append(f"{here}: id poate avea doar litere mici, cifre și _")
        if figure["id"] in seen:
            errors.append(f"{here}: id apare de două ori")
        seen.add(figure["id"])
        if figure["kind"] not in DECIMALS:
            errors.append(f"{here}: kind „{figure['kind']}” nu există (amount, percent, count)")
        if not figure["sheets"] or not figure["labels"]:
            errors.append(f"{here}: sheets și labels nu pot fi goale")
    return errors


def check_facts(facts, settings, workbook_ids):
    errors, seen, fact_figures = [], set(), set()
    for number, fact in enumerate(facts, 1):
        here = where("facts.toml", number, fact, "id")
        problems = check_fields(fact, FACT, here)
        if problems:
            errors += problems
            continue
        if not ID.match(fact["id"]) or fact["id"] in seen:
            errors.append(f"{here}: id lipsește, apare de două ori sau are alte caractere decât litere mici, cifre și _")
        seen.add(fact["id"])
        if fact["document"] and fact["document"] not in settings["documents"]:
            errors.append(f"{here}: documentul „{fact['document']}” nu este în settings.toml [documents]")
        if fact["document"] and not fact["quote"].strip():
            errors.append(f"{here}: un fapt cu document are nevoie de quote")
        if fact["page"] < 1:
            errors.append(f"{here}: page începe de la 1")
        if "direction" in fact and fact["direction"] not in DIRECTIONS:
            errors.append(f"{here}: direction „{fact['direction']}” nu există ({', '.join(DIRECTIONS)})")
        if "direction" in fact and "about" not in fact:
            errors.append(f"{here}: direction are nevoie de about (cifra a cărei schimbare o explică)")
        for key in ("about", "explains_gap"):
            if key in fact and fact[key] not in workbook_ids:
                errors.append(f"{here}: {key} „{fact[key]}” nu este o cifră din figures.toml")
        errors += check_fact_figure(fact, here, settings, workbook_ids, fact_figures)
    return errors


def check_fact_figure(fact, here, settings, workbook_ids, fact_figures):
    """A fact may supply a figure: figure, value and unit go together; the value is in the quote."""
    present = [key for key in ("figure", "value", "unit") if key in fact]
    if not present:
        return []
    if len(present) < 3:
        return [f"{here}: figure, value și unit se scriu împreună (unit, value sau figure lipsește)"]
    errors = []
    if not ID.match(fact["figure"]) or fact["figure"] in workbook_ids | fact_figures:
        errors.append(f"{here}: figure „{fact['figure']}” are alte caractere sau există deja")
    fact_figures.add(fact["figure"])
    if normalize_text(fact["value"]) not in normalize_text(fact["quote"]):
        errors.append(f"{here}: value „{fact['value']}” nu apare în quote")
    try:
        parse_ro_number(fact["value"])
    except InvalidOperation:
        errors.append(f"{here}: value „{fact['value']}” nu este un număr scris românește")
    if fact["unit"] not in settings["units"]:
        errors.append(f"{here}: unit „{fact['unit']}” nu este în settings.toml [units]")
    return errors


def check_relations(relations, known_ids):
    errors, seen = [], set()
    for number, relation in enumerate(relations, 1):
        here = where("relations.toml", number, relation, "id")
        problems = check_fields(relation, RELATION, here)
        if problems:
            errors += problems
            continue
        if not ID.match(relation["id"]) or relation["id"] in seen:
            errors.append(f"{here}: id lipsește, apare de două ori sau are alte caractere decât litere mici, cifre și _")
        seen.add(relation["id"])
        names = set(NAME_IN_CHECK.findall(relation["check"]))
        errors += [f"{here}: cifra „{name}” nu există" for name in sorted(names - known_ids)]
        errors += [f"{here}: marks conține „{name}”, care nu apare în check" for name in relation["marks"] if name not in names]
        if not relation["marks"]:
            errors.append(f"{here}: marks nu poate fi gol")
        if "fills" in relation and relation["fills"] not in names:
            errors.append(f"{here}: fills „{relation['fills']}” nu apare în check")
        if "tolerance" in relation:
            try:
                if Decimal(relation["tolerance"]) < 0:
                    raise InvalidOperation
            except InvalidOperation:
                errors.append(f"{here}: tolerance „{relation['tolerance']}” trebuie să fie un număr ≥ 0")
    return errors


def check_decisions(decisions, known_ids, settings):
    errors = []
    figure_ids = known_ids | {"prior:" + figure_id for figure_id in known_ids}
    forbidden = [normalize_label(text) for text in settings["decisions"]["forbidden_sources"]]
    for number, decision in enumerate(decisions, 1):
        here = where("decisions.toml", number, decision, "figure")
        problems = check_fields(decision, DECISION, here)
        if problems:
            errors += problems
            continue
        if decision["figure"] not in figure_ids:
            errors.append(f"{here}: cifra „{decision['figure']}” nu există")
        if decision["chosen"] != "gap" and decision["chosen"] not in decision["values"]:
            errors.append(f"{here}: chosen trebuie să fie una dintre values sau „gap”")
        source = normalize_label(decision["source"])
        if not source:
            errors.append(f"{here}: lipsește source")
        elif any(text in source for text in forbidden):
            errors.append(f"{here}: source nu poate fi cifra de anul trecut")
        if not decision["reason"].strip():
            errors.append(f"{here}: lipsește reason")
        proposer, approver = normalize_label(decision["proposed_by"]), normalize_label(decision["approved_by"])
        if not proposer or not approver or proposer == approver:
            errors.append(f"{here}: proposed_by și approved_by trebuie să fie două persoane diferite")
    return errors


def check_gap_reasons(catalog):
    errors = [f"gap_reasons.toml: lipsește motivul „{name}”" for name in GAP_REASONS if name not in catalog]
    errors += [f"gap_reasons.toml: motivul „{name}” trebuie să fie text" for name, text in catalog.items() if not is_text(text)]
    return errors
