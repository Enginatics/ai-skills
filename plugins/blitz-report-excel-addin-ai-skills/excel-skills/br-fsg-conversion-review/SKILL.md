---
name: br-fsg-conversion-review
description: >
  Finish a financial statement workbook converted from Spreadsheet Server or GL Wand to Blitz FSG:
  read its Conversion Log sheet, fix in the workbook what the converter could not (period cells
  read by other formulas, formula-driven format and segment cells, hierarchy suffixes, unsupported
  currency types, cells left unconverted), ask the user about the rest, and mark every log line.
  Use when the user asks to review, finish, fix or check a converted Spreadsheet Server or GL Wand
  workbook, its conversion log, or "the warnings from the conversion". Edits the workbook only;
  never writes to Oracle EBS.
---

# Finish a Spreadsheet Server / GL Wand conversion (br-fsg-conversion-review)

The Blitz Report add-in has already converted this workbook: every balance, period and segment
description formula now uses the add-in's own functions, and what the converter could not finish is
listed on the **`Conversion Log`** sheet (row 1 headers `Level | Cell | Message`, one line per issue,
`Cell` is `<sheet>!<address>` or blank for a workbook-wide line). Your job is that list, nothing else.

**Self-contained: read no other skill.** Each numbered Op is one workbook operation (Claude: one
`execute_office_js` call; Copilot: one read or edit action).

## Rules
1. **Only what the log names.** Never rewrite a formula the log does not point at, never "tidy" a
   converted formula, never recalculate or refresh balances yourself.
2. **One confirmation before any edit.** Show every change as `cell: before -> after` and ask. A
   line that needs a business decision (which ledger, which currency, which values) is a question
   in that same message, never a guess.
3. **Every argument of a balance, period or description formula is a plain cell reference or a
   quoted literal** — the add-in reads them without Excel calculating. A computed value goes into a
   helper cell, and the formula points at that cell. Never put an expression inside these formulas.
4. **A helper cell must be empty** (read it first) and sit next to the cell it serves; tell the user
   where it went.
5. **Talk about periods, balances, segments, ledgers and cells** in the user's language. Never name
   the add-in's worksheet functions, this skill, or the log's internal wording.

## Op 1 — Read the log
Read `Conversion Log` columns A:C (its whole used range). No such sheet: the conversion finished
clean — say so and stop. Classify every line with `references/log-messages.md`: **Fix**, **Ask**,
**Info**, or **Re-run** (the converter can finish it once the input is corrected).

## Op 2 — Read what the fixes need
In one operation, read the formulas (not values) of every cell the Fix and Ask lines name, plus the
cells those formulas point at that the fix procedure needs (period cells, format cells, the
source cell of a period number). `references/fixes.md` says exactly what each procedure reads.

## Op 3 — Propose → confirmation
One message, grouped:
- **I will change** — per line: the cell, before -> after, one plain sentence why.
- **I need your answer** — the Ask lines, each with the options the procedure lists.
- **For your information** — the Info lines in one sentence each (no action).
- **The converter can finish these** — Re-run lines: what to correct first (you may propose that
  correction above) and that they then run the Spreadsheet Server or GL Wand converter again on
  this workbook from the Blitz Report ribbon (Tools > Converter), which converts only what is
  still unconverted.
Options: `Yes — make the changes` / `Change some first` / `Cancel`. Nothing is written before Yes.

## Op 4 — Apply
Write the confirmed changes, one contiguous block per write (a comma-separated multi-area address is
rejected; retry a rejected write once on that range, then move on). A formula written into a cell
formatted as Text stays text: set that cell's number format to General first.

## Op 5 — Mark the log
Write a `Status` heading in D1 of `Conversion Log` and, in one block write down column D, `Fixed`,
`Needs you`, `Info` or `Run the converter again` for every line. Never delete log lines.

## Op 6 — Reply
What was changed (cell by cell), what still needs the user (with the question), and: "Refresh the
workbook (Blitz Report ribbon > Refresh > Other > Workbook) to calculate the balances." If the user answered an Ask
question, apply it in a further Op 4 + Op 5 round.
