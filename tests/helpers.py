"""Shared test setup: project paths, the import path to src/ and small workbooks for tests."""

import re
import shutil
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
DATE = ROOT / "date"  # the client's files; tests that need them are skipped when it is missing
sys.path.insert(0, str(ROOT / "src"))

from config import text_sha256  # noqa: E402  (after src/ is on the path)


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


def project_copy(tmp, confirm=False, approve=False):
    """config/ and date/ copied into tmp, to run main.main(root=tmp, folder=tmp / "date").
    The copy does not keep the real confirmations and approval: every fact starts unconfirmed and
    section E unapproved. confirm=True confirms the six facts that have a quote in a document (as at
    checkpoint 2; legal_basis and mcr_covered stay unconfirmed); approve=True approves section E."""
    shutil.copytree(ROOT / "config", tmp / "config")
    shutil.copytree(DATE, tmp / "date")
    facts = tmp / "config" / "facts.toml"
    entries = re.sub(r'confirmed_by = "[^"]*"', 'confirmed_by = ""', facts.read_text(encoding="utf-8")).split("[[fact]]")
    if confirm:
        entries = [entry if 'document = ""' in entry else entry.replace('confirmed_by = ""', 'confirmed_by = "Test"')
                   for entry in entries]
    facts.write_text("[[fact]]".join(entries), encoding="utf-8")
    approvals = tmp / "config" / "approvals.toml"
    text = re.sub(r'approved_by = "[^"]*"', 'approved_by = "Test"' if approve else 'approved_by = ""',
                  approvals.read_text(encoding="utf-8"))
    sha = text_sha256(tmp / "config", "E") if approve else ""
    approvals.write_text(re.sub(r'sha256 = "[^"]*"', f'sha256 = "{sha}"', text), encoding="utf-8")
