# CLAUDE.md: SFCR 2025 for Asigurări Carpați (BlueberryX assessment)

## Goal

- A Python program that produces the 2025 SFCR draft from the published 2024 report, the 2025 workbook and the client's official documents.
- Output covers section E only (own funds, SCR, MCR, solvency ratio). The engine is designed for the whole SFCR: a section is config and templates, not code.
- One command, run from `date/`, writes everything to `output/`.
- The program will be run UNCHANGED (code and config) on another version of `registru_2025.xlsx`.
- Materials and report text are in Romanian. The report keeps its Romanian wording and number format. `DESIGN.md` (Romanian) holds the design decisions; the code must match it.

## Design priority

The biggest risk is next year's run without us. Code must be simple and config even simpler, so a newcomer understands both alone. Plain functions, no clever abstractions, a short comment on every config field. If a feature makes the program harder to explain, leave it out and tell me.

## The domain rule

A wrong figure or an unsupported sentence is far worse than a visible gap. When in doubt, write `[de completat: <reason>]`.

## The 5 report rules (non-negotiable)

1. Traceability: every figure has a source that can be shown (a workbook cell, a document with its page, or a calculation on unrounded values). Last year's figure never replaces this year's. It may appear only as a comparison, labelled, with its source.
2. No unsupported statements: facts, direction of change and explanations ("ca urmare a", "datorită"). This applies to new text and to text inherited from 2024.
3. Visible gaps: `[de completat: <reason>]`.
4. No text or information from another company.
5. Number format: `284,6 mil. lei`, `187,4 %`, `18.420`. Round once, to one decimal, on the unrounded value, ROUND_HALF_UP. A total comes from its own cell, never from adding rounded values.

## Reading the data

- Nothing about the workbook layout is written in code or config: no cell addresses, columns, sheet order, units or years. Config holds labels, label aliases, relations and the reporting year.
- Sheets are found by name, with aliases from config. Sheets with `sheet_state != "visible"` are never read and are reported.
- A figure is accepted only if its normalized label (ş/ș, ţ/ț, case, whitespace) appears exactly once in the expected sheet. Zero or two or more matches: gap. The same label in another sheet is a cross-check.
- The column is found by its header ("an curent", "an anterior"). The unit is read from the sheet header, including per-row exceptions ("cu excepția numărului de dosare"). Unknown unit: gap.
- Label found but the value is empty or text: gap, with the reason taken from the row's other cells.
- Formulas: the cached value is checked by recalculating from relations. Missing and not recalculable: gap.
- Money: `Decimal(str(x))`, never float. ROUND_HALF_UP set explicitly.
- Allowed sources: only the list in config (workbooks, financial statements, AGA minutes, board minutes, actuarial note). The Asigurări Dunărea report is never opened.

## Checks, conflicts, decisions

- Relations live in config and are checked before any figure reaches the text:
  - the tiers add up to total own funds;
  - modules minus diversification (sign handled by label) give the basic SCR, plus operational risk give the SCR;
  - the SCR is the same in every sheet where it appears;
  - the stated ratio equals own funds / SCR, with a 0,05 tolerance on the displayed value;
  - last year's SCR equals the figure published in 2024;
  - MCR < SCR;
  - dividends in the financial statements equal the amount approved by the AGA.
- Conflicts are never resolved silently. Only a config decision resolves one, with source, reason, the exact conflicting values, `proposed_by`, `approved_by` and date. If the current values differ from the stored ones, the decision does not apply: gap.
- Four eyes: `proposed_by` must differ from `approved_by`. A decision without source or reason, with "last year's figure" as source, or with the same person in both fields is rejected.
- Facts from documents live in a separate file: statement, document, page, exact quote, `confirmed_by`. On every run the program searches for the quote in the document. Not found: gap.
- Config self-check at start: schema valid, decisions valid, no label alias that matches more than one row in its sheet. If the config fails this check, no draft is written and `verificari.md` says why. Problems in the workbook never block the run: they become gaps.

## Text

- The program never composes text. All report text (headings and sentences, sections A to E and the summary) lives in human-approved templates, with who approved them, when and a sha256. Wording changes with legislation, EU rules or the company, and only a human changes it.
- The program only fills placeholders (figures, years), picks direction words from a closed list ("în creștere" / "în scădere"), picks between human-written sentence variants by rule, and inserts gaps whose reasons come from a fixed catalog in config.
- Direction is computed from unrounded figures and written only if the displayed values differ. The approved rule may add the size of the change, also on unrounded values, comparison year from config: "în scădere cu 2,1 % față de 2024". Ratios change in percentage points ("puncte procentuale"). The size of the change is a calculated figure with its own line in `trasabilitate.csv`.
- A cause is a human-written variant. It appears only if a confirmed fact supports it and the direction in the document matches the computed one.
- A template whose sha256 differs from its approval record is reported, and the draft is marked as not approved.
- Only the sections listed in config are rendered: E for this delivery. Adding a section needs config and templates only.

## Current decisions and assumptions (from DESIGN.md)

- The 2025 solvency ratio stays a gap until a human decision: the workbook states 187,4 % (same as 2024), the calculation gives 197,4 %.
- Dividends (15,0 mil. lei) come from the audited financial statements (page 1), confirmed by the AGA of 24.04.2025, recorded as a fact with a quote.
- The reporting year comes from config. The 2024 mapping is a hint, not a source.
- No LLM inside the program.

## Output (fully generated by the program)

- `sectiunea_E_<year>.md`: the draft, with gaps.
- `trasabilitate.csv`: for each figure, value, source, label, unit, status and reason.
- `verificari.md`: input checksums, hidden sheets, checks, conflicts, decisions (with who approved and when), facts.
- The program empties `output/` at start and never crashes on an unexpected workbook.

## Tests

- Known traps become tests, not special cases in code. No sheet name or cell address appears in `src/` or `config/`.
- Rounding: 0,25 → 0,3 and 0,35 → 0,4.
- 2024 round trip: the mapping plus the 2024 workbook reproduce the published figures, and the test reports the known mapping defect ("12,6"). DESIGN.md cites this test, so it must exist.
- Mutation tests with metrics: wrong figures reaching the text (must be 0), detection rate, unnecessary gaps.

## Working rules

- Python 3.11+, `openpyxl` and `pypdf` only. No pandas, no system binaries.
- Work on copies of the workbooks. Never open and save the originals in Excel or LibreOffice.
- Never write decisions, fact confirmations or template approvals yourself. Show them to me and wait.
- Never edit files in `ai/conversations/`. Export the conversation before any `/compact`.
- Humanizer only on DESIGN.md, AI.md and README.md.
- Archive: README.md, DESIGN.md, ai/AI.md, ai/conversations/, config/, output/, src/, tests/.
