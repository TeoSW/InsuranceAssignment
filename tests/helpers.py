"""Shared test setup: project paths, the import path to src/ and small workbooks for tests."""

import shutil
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
DATE = ROOT / "date"  # the client's files; tests that need them are skipped when it is missing
sys.path.insert(0, str(ROOT / "src"))


def make_book(path, sheets):
    """Write a small .xlsx. sheets = [(title, rows)] or [(title, rows, state)]; rows start at A1."""
    book = openpyxl.Workbook()
    book.remove(book.active)
    for title, rows, *state in sheets:
        sheet = book.create_sheet(title)
        for row in rows:
            sheet.append(row)
        if state:
            sheet.sheet_state = state[0]
    book.save(path)
    return path


def table(rows, unit="Valori în mii lei"):
    """A sheet laid out like the client's: title, unit, header, then one row per label (labels in B)."""
    header = [None, "Indicator", "31.12 an curent", "31.12 an anterior"]
    return [["Titlu"], [unit], header] + [[None, *row] for row in rows]


def project_copy(tmp, confirm=False):
    """config/ and date/ copied into tmp, to run main.main(root=tmp, folder=tmp / "date").
    confirm=True confirms, in the copy only, the six facts that have a quote in a document, as a person
    would at checkpoint 2; legal_basis and mcr_covered (no document) stay unconfirmed."""
    shutil.copytree(ROOT / "config", tmp / "config")
    shutil.copytree(DATE, tmp / "date")
    if confirm:
        facts = tmp / "config" / "facts.toml"
        entries = facts.read_text(encoding="utf-8").split("[[fact]]")
        entries = [entry if 'document = ""' in entry else entry.replace('confirmed_by = ""', 'confirmed_by = "Test"')
                   for entry in entries]
        facts.write_text("[[fact]]".join(entries), encoding="utf-8")
