"""Load the config files and check them before anything is read (the self-check).

load_config returns the config and a list of errors. Any error stops the run before a draft is
written. Only config problems are checked here; problems in the workbook become gaps later.
"""

import hashlib
import re
import tomllib
from datetime import date
from pathlib import Path

from read import label_key, normalize, ro_number

# Every gap reason the program can give. config/gap_reasons.toml must have a text for each.
GAP_REASONS = """file_missing file_unreadable unexpected_error sheet_not_found header_not_found label_not_found
label_not_unique unit_unknown formula_no_value value_text value_missing value_missing_note fact_unconfirmed
fact_not_found conflict same_as_prior unverified depends_on_conflict decision_gap decision_stale change_from_zero
fact_explains fact_direction""".split()
# A placeholder in a sentence: {X}, {prior:X}, {direction:X}, {change:X}, {year}, {prior_year}.
PLACEHOLDER = re.compile(r"\{(?:(prior|direction|change):)?(\w+)\}")

# Required fields of each kind of entry, and of settings.toml.
REQUIRED = {
    "figure": ["id", "sheets", "labels", "kind"],
    "relation": ["type"],
    "fact": ["id", "statement", "document", "page", "quote", "confirmed_by", "confirmed_on"],
    "decision": ["figure", "values", "chosen", "source", "reason", "proposed_by", "approved_by", "date"],
    "sentence": ["id", "text"],
    "settings": ["reporting_year", "prior_year", "sections", "workbooks", "documents", "reading", "units",
                 "words", "format", "decisions", "output"],
}
# The type of every field that may appear in an entry or in settings.toml. A list holds texts.
TEXT, TEXTS, WHOLE, TABLE, DAY = str, list, int, dict, (str, date)
TYPES = {"id": TEXT, "sheets": TEXTS, "labels": TEXTS, "labels_stored_negative": TEXTS, "kind": TEXT,
         "type": TEXT, "total": TEXT, "parts": TEXTS, "minus": TEXTS, "a": TEXT, "b": TEXT, "r": TEXT,
         "statement": TEXT, "document": TEXT, "page": WHOLE, "quote": TEXT, "confirmed_by": TEXT, "confirmed_on": DAY,
         "about": TEXT, "direction": TEXT, "explains": TEXT, "figure": TEXT, "value": TEXT, "unit": TEXT,
         "values": TEXTS, "chosen": TEXT, "source": TEXT, "reason": TEXT, "proposed_by": TEXT, "approved_by": TEXT,
         "date": DAY, "text": TEXT, "when": TEXT, "needs": TEXTS, "reporting_year": WHOLE, "prior_year": WHOLE,
         "sections": TEXTS, "workbooks": TABLE, "documents": TABLE, "reading": TABLE, "units": TABLE, "words": TABLE,
         "format": TABLE, "decisions": TABLE, "output": TABLE}
# The fields that name figures, for each type of relation ("minus" is optional).
RELATION_FIELDS = {"sum": ["total", "parts"], "equal": ["a", "b"], "less": ["a", "b"], "ratio": ["r", "a", "b"],
                   "positive": ["a"]}
KINDS = ("amount", "percent", "count")
DIRECTIONS = ("creștere", "scădere")


def figures_in(relation):
    """The figure ids a relation names: total, parts and minus of a sum; a, b (and r) of the others."""
    single = [relation[key] for key in ("total", "a", "b", "r") if key in relation]
    return single[:1] + relation.get("parts", []) + relation.get("minus", []) + single[1:]


def load_config(folder):
    """Read config/*.toml and run the self-check. Returns (config, errors)."""
    cfg, errors = {}, []
    for name in ("settings", "figures", "relations", "facts", "decisions", "gap_reasons", "sentences", "approvals"):
        try:
            with open(Path(folder) / f"{name}.toml", "rb") as file:
                cfg[name] = tomllib.load(file)
        except (OSError, ValueError) as error:  # ValueError: not TOML, or not saved as UTF-8
            errors.append(f"config/{name}.toml nu poate fi citit: {error}")
    if errors:
        return cfg, errors
    errors += missing_fields(cfg["settings"], "settings", "settings.toml")
    errors += [f"gap_reasons.toml: motivul „{name}” trebuie scris ca text"
               for name, text in cfg["gap_reasons"].items() if not isinstance(text, str)]
    if errors:
        return cfg, errors
    cfg["templates"], cfg["text_sha256"] = {}, {}
    for section in cfg["settings"].get("sections", []):
        try:
            cfg["templates"][section] = (Path(folder) / "templates" / f"{section}.md").read_text(encoding="utf-8")
            cfg["text_sha256"][section] = text_sha256(folder, section)
        except OSError as error:
            errors.append(f"config/templates/{section}.md nu poate fi citit: {error}")
    for name, key in (("figures", "figure"), ("relations", "relation"), ("facts", "fact"), ("decisions", "decision"),
                      ("sentences", "sentence")):
        cfg[name] = cfg[name].get(key, [])
        if not isinstance(cfg[name], list):
            errors.append(f"{name}.toml: fiecare intrare se scrie [[{key}]]")
            continue
        for number, entry in enumerate(cfg[name], 1):
            names = entry.get("id", entry.get("figure"))  # so the person can find the entry
            errors += missing_fields(entry, key, f"{name}.toml, intrarea {number}" + (f" („{names}”)" if isinstance(names, str) else ""))
    if errors:
        return cfg, errors  # the checks below need every field

    workbook_ids = {figure["id"] for figure in cfg["figures"]}
    ids = workbook_ids | {fact["figure"] for fact in cfg["facts"] if "figure" in fact}
    if cfg["settings"]["prior_year"] != cfg["settings"]["reporting_year"] - 1:
        errors.append("settings.toml: prior_year trebuie să fie reporting_year - 1")
    errors += check_figures(cfg["figures"])
    errors += check_relations(cfg["relations"], ids)
    errors += check_facts(cfg["facts"], cfg["settings"], workbook_ids, ids)
    errors += check_decisions(cfg["decisions"], ids, cfg["settings"])
    errors += check_sentences(cfg["sentences"], cfg["templates"], ids, cfg["facts"])
    errors += [f"gap_reasons.toml: lipsește motivul „{name}”" for name in GAP_REASONS if name not in cfg["gap_reasons"]]
    return cfg, errors


def text_sha256(folder, section):
    """The fingerprint of a section's wording: templates/<section>.md plus sentences.toml.
    Line endings are ignored, so a Windows checkout does not change it; any changed word does."""
    digest = hashlib.sha256()
    for path in (Path(folder) / "templates" / f"{section}.md", Path(folder) / "sentences.toml"):
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def missing_fields(entry, kind, where):
    """Required fields that are missing, and fields of the wrong type (a list must hold texts)."""
    missing = [name for name in REQUIRED[kind] if name not in entry]
    errors = [f"{where}: lipsește {', '.join(missing)}"] if missing else []
    for name, value in entry.items():
        expected = TYPES.get(name, object)
        if not isinstance(value, expected) or isinstance(value, bool) \
                or (expected is TEXTS and not all(isinstance(item, str) for item in value)):
            errors.append(f"{where}: câmpul „{name}” are alt tip (de exemplu text între ghilimele sau listă de texte)")
    return errors


def check_figures(figures):
    """Unique ids, known kinds, and no label shared by two figures in the same sheet."""
    errors, seen, owner = [], set(), {}
    for figure in figures:
        if figure["id"] in seen:
            errors.append(f"figures.toml: cifra „{figure['id']}” apare de două ori")
        seen.add(figure["id"])
        if figure["kind"] not in KINDS:
            errors.append(f"figures.toml, „{figure['id']}”: kind „{figure['kind']}” nu există ({', '.join(KINDS)})")
        for sheet in figure["sheets"]:
            for label in figure["labels"] + figure.get("labels_stored_negative", []):
                key = (label_key(sheet), label_key(label))
                if owner.get(key, figure["id"]) != figure["id"]:
                    errors.append(f"figures.toml: eticheta „{label}” din foaia {sheet} aparține și cifrei „{owner[key]}”")
                owner[key] = figure["id"]
    return errors


def check_relations(relations, ids):
    errors = []
    for number, relation in enumerate(relations, 1):
        here = f"relations.toml, intrarea {number}"
        fields = RELATION_FIELDS.get(relation["type"])
        if fields is None:
            errors.append(f"{here}: type „{relation['type']}” nu există ({', '.join(RELATION_FIELDS)})")
            continue
        errors += [f"{here}: lipsește {name}" for name in fields if name not in relation]
        errors += [f"{here}: cifra „{name}” nu există" for name in figures_in(relation) if name not in ids]
    return errors


def check_facts(facts, settings, workbook_ids, ids):
    errors, seen = [], set()
    for fact in facts:
        here = f"facts.toml, faptul „{fact['id']}”"
        if fact["id"] in seen:
            errors.append(f"{here}: apare de două ori")
        seen.add(fact["id"])
        if fact["document"] and fact["document"] not in settings["documents"]:
            errors.append(f"{here}: documentul „{fact['document']}” nu este în settings.toml [documents]")
        if fact["document"] and not fact["quote"].strip():
            errors.append(f"{here}: un fapt cu document are nevoie de quote")
        if "figure" in fact and not ("value" in fact and "unit" in fact):
            errors.append(f"{here}: figure are nevoie de value și unit")
        if fact.get("figure") in workbook_ids:
            errors.append(f"{here}: figure „{fact['figure']}” există deja în figures.toml")
        if "value" in fact and normalize(fact["value"]) not in normalize(fact["quote"]):
            errors.append(f"{here}: value „{fact['value']}” nu apare în quote")
        if "value" in fact and ro_number(fact["value"]) is None:
            errors.append(f"{here}: value „{fact['value']}” nu este un număr (scrieți-l ca 15.000.000)")
        if "unit" in fact and fact["unit"] not in settings["units"]:
            errors.append(f"{here}: unit „{fact['unit']}” nu este în settings.toml [units]")
        if ("direction" in fact or "about" in fact) and not (fact.get("direction") in DIRECTIONS and "about" in fact):
            errors.append(f"{here}: about și direction ({' sau '.join(DIRECTIONS)}) se scriu împreună "
                          f"(acum: about „{fact.get('about', '')}”, direction „{fact.get('direction', '')}”)")
        if "direction" in fact and not fact["document"]:
            errors.append(f"{here}: o direcție trebuie să vină dintr-un document (document nu poate fi gol)")
        errors += [f"{here}: {key} „{fact[key]}” nu este o cifră cunoscută"
                   for key in ("about", "explains") if key in fact and fact[key] not in ids]
    return errors


def check_decisions(decisions, ids, settings):
    """Four eyes, a source that is not last year's figure, a reason, and a chosen value among the values."""
    errors = []
    forbidden = [label_key(text) for text in settings["decisions"]["forbidden_sources"]]
    for number, decision in enumerate(decisions, 1):
        here = f"decisions.toml, intrarea {number} („{decision['figure']}”)"
        if decision["figure"].removeprefix("prior:") not in ids:
            errors.append(f"{here}: cifra nu există")
        if decision["chosen"] != "gap" and decision["chosen"] not in decision["values"]:
            errors.append(f"{here}: chosen trebuie să fie una dintre values sau „gap”")
        source = label_key(decision["source"])
        if not source or any(text in source for text in forbidden):
            errors.append(f"{here}: source lipsește sau este cifra de anul trecut")
        if not decision["reason"].strip():
            errors.append(f"{here}: lipsește reason")
        proposer = label_key(decision["proposed_by"])
        if not proposer or proposer == label_key(decision["approved_by"]):
            errors.append(f"{here}: proposed_by și approved_by trebuie să fie două persoane diferite")
        try:
            date.fromisoformat(str(decision["date"]))
        except ValueError:
            errors.append(f"{here}: date trebuie scrisă AAAA-LL-ZZ")
    return errors


def check_sentences(sentences, templates, ids, facts):
    """Template placeholders are sentences; every sentence ends with a fallback (no condition, no direction);
    direction and change only where the condition guarantees a visible change; known figures and facts."""
    from_documents = {fact["figure"] for fact in facts if "figure" in fact}  # they have no last-year value
    errors, variants, facts = [], {}, {fact["id"]: fact for fact in facts}
    for sentence in sentences:
        variants.setdefault(sentence["id"], []).append(sentence)
    for section, text in templates.items():
        errors += [f"templates/{section}.md: „{name}” nu este o propoziție din sentences.toml"
                   for prefix, name in PLACEHOLDER.findall(text) if prefix or name not in variants]
    for sentence_id, group in variants.items():
        here = f"sentences.toml, „{sentence_id}”"
        if "when" in group[-1] or "{direction:" in group[-1]["text"] or "{change:" in group[-1]["text"]:
            errors.append(f"{here}: ultima variantă trebuie să fie fără condiție (when) și fără direction/change")
        for variant in group:
            when = variant.get("when", "").split()
            if when and not (len(when) == 2 and when[0] == "changed" and when[1] in ids
                             or len(when) == 2 and when[0] == "fact" and when[1] in facts
                             or len(when) == 3 and when[0] in ids and when[1] in ("==", ">") and when[2] == "0"):
                errors.append(f"{here}: condiția „{variant['when']}” nu se înțelege")
            for prefix, name in PLACEHOLDER.findall(variant["text"]):
                if name not in ids and (prefix or name not in ("year", "prior_year")):
                    errors.append(f"{here}: „{name}” nu este o cifră cunoscută")
                if prefix and name in from_documents:
                    errors.append(f"{here}: {{{prefix}:{name}}}: o cifră dintr-un document nu are valoare de anul trecut")
                guaranteed = when == ["changed", name] or (when[:1] == ["fact"] and facts.get(when[-1], {}).get("about") == name)
                if prefix in ("direction", "change") and not guaranteed:
                    errors.append(f"{here}: {{{prefix}:{name}}} poate apărea doar într-o variantă „changed {name}” "
                                  f"sau „fact ...” despre {name}")
            errors += [f"{here}: faptul „{name}” nu există" for name in variant.get("needs", []) if name not in facts]
    return errors
