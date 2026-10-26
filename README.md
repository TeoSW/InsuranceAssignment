# SFCR 2025, section E: Asigurări Carpați

This program writes the 2025 draft of SFCR section E (own funds, SCR, MCR, solvency ratio). It uses the approved wording taken from the published 2024 report, the figures from the 2025 workbook and the facts from the client's documents. Where it cannot fill something in correctly, it leaves a visible gap: `[de completat: reason]`. `DESIGN.md` (in Romanian) explains the design and the decisions behind it.

## Install

You need Python 3.11 or newer.

```bash
python -m venv .venv
```

Activate the environment (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` elsewhere), then install the dependencies:

```bash
pip install -r requirements.txt
```

## Run

From the `date/` folder:

```bash
python ../src/main.py
```

The program assumes that `date/` holds the client's files and sits in the project root, next to `src/`, `config/` and `output/`. It reads its inputs from the folder you run it from and finds `config/` and `output/` from its own location. To run it on another version of `registru_2025.xlsx`, put the new file in `date/` under the same name and run the same command; the code and config stay as they are.

Exit code 0 means the draft was written. Exit code 1 means nothing was drafted: the config has an error, the program met an error it did not expect, or `output/` could not be emptied because one of its files is open. In the first two cases `output/verificari.md` says what went wrong, and no half-written draft is left behind.

## What it writes

`output/` is emptied at the start of every run, so everything in it comes from the latest run.

- `sectiunea_E_2025.md`: the draft. Every sentence comes from `config/sentences.toml`; every number comes from the workbook, a document, or a calculation on them. If the first line reads "ȘABLON NEAPROBAT", the text has not been approved in `config/approvals.toml`, or it has changed since its approval.
- `trasabilitate.csv`: one line per figure, with its exact value, what the text shows, its source (file, sheet and cell; document and page; or the calculation), label, unit, status (`ok`, `gol`, `conflict`, `decizie`) and, for a gap, the reason. It opens in Excel (UTF-8, `;`).
- `verificari.md`: checksums of the input files, hidden sheets (never read), every check and its result, the gaps in the draft, conflicts with their exact values, decisions with who proposed and approved them and when, the facts and whether they were used, and the text approval.

## What people do

Everything a person decides lives in `config/`, so git keeps it too. Each file explains its own fields.

- `facts.toml`: confirm a fact after checking its quote in the document (`confirmed_by`, `confirmed_on`).
- `decisions.toml`: resolve a conflict. Copy the exact values from `verificari.md`, then choose one of them or `"gap"`, with a source, a reason, and two different people.
- `approvals.toml`: approve a section's wording by entering who, when, and the sha256 that `verificari.md` prints for the text in use.
- `figures.toml`, `relations.toml`, `sentences.toml`, `templates/`: update these when the workbook or the wording changes. A change to `sentences.toml` or `templates/` needs a new approval.

## Tests

From the project root:

```bash
python -X utf8 -m unittest discover -s tests
```

To print the mutation table (eleven changes to a copy of the 2025 workbook):

```bash
python -X utf8 tests/test_mutations.py
```

Tests that need the client's files are skipped when `date/` is missing.

`tests/input_sha256.txt` records the SHA-256 of the client's files as delivered. No test uses it. From `date/`, `sha256sum -c ../tests/input_sha256.txt` shows whether a file has changed since.
