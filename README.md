# SFCR 2025, section E: Asigurări Carpați

The program writes the 2025 draft of SFCR section E (own funds, SCR, MCR, solvency ratio). It takes the wording of the published 2024 report, the figures from the 2025 workbook and the facts from the client's documents. Where it cannot fill something correctly, it leaves a visible gap: `[de completat: reason]`. The design and the decisions behind it are in `DESIGN.md` (in Romanian).

## Install

Python 3.11 or newer.

```bash
python -m venv .venv
```

Activate it (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` elsewhere), then:

```bash
pip install -r requirements.txt
```

## Run

From the `date/` folder:

```bash
python ../src/main.py
```

Path assumption: `date/` holds the client's files and sits in the project root, next to `src/`, `config/` and `output/`. The program reads its inputs from the folder you run it from, and finds `config/` and `output/` from its own location. To run it on another version of `registru_2025.xlsx`, put the new file in `date/` under the same name and run the same command. Nothing else changes.

Exit code 0 means the draft was written. Exit code 1 means nothing could be drafted: the config has an error (`output/verificari.md` lists it), or `output/` could not be emptied because a file in it is open.

## What it writes

`output/` is emptied at the start of every run, so everything in it comes from the last run.

- `sectiunea_E_2025.md`: the draft. Every sentence comes from `config/sentences.toml`, every number from the workbook or a document. A first line "ȘABLON NEAPROBAT" means the text has not been approved in `config/approvals.toml`.
- `trasabilitate.csv`: one line per figure, with its exact value, what the text shows, its source (file, sheet and cell; document and page; or the calculation), label, unit, status (`ok`, `gol`, `conflict`, `decizie`) and the reason for a gap. It opens in Excel (UTF-8, `;`).
- `verificari.md`: checksums of the input files, hidden sheets (never read), every check and its result, conflicts with their exact values, decisions with who proposed and approved them and when, the facts and whether they were used, and the text approval.

## What people do

Everything a person decides lives in `config/`, so it is also in git. Each file explains its fields.

- `facts.toml`: confirm a fact after checking its quote in the document (`confirmed_by`, `confirmed_on`).
- `decisions.toml`: resolve a conflict. Copy the exact values from `verificari.md`, then choose one of them or `"gap"`, with a source, a reason, and two different people.
- `approvals.toml`: approve the wording of a section.
- `figures.toml`, `relations.toml`, `sentences.toml`, `templates/`: update these when the workbook or the wording changes.

## Tests

From the project root:

```bash
python -X utf8 -m unittest discover -s tests
```

The mutation table (seven changes to a copy of the 2025 workbook):

```bash
python -X utf8 tests/test_mutations.py
```

Tests that need the client's files are skipped when `date/` is missing.
