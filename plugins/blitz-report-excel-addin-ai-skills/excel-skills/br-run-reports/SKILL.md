---
name: br-run-reports
description: Find, run, and analyze Oracle EBS Blitz Reports in Excel (GL, AP, AR, INV, PO, WIP, FA, HR and concurrent-program data). Use when the user wants to run or analyze an Oracle/EBS report.
---
# Run Blitz Reports in Excel

You can run Oracle EBS **Blitz Reports** directly in this workbook through the custom `br_*`
worksheet functions provided by the Blitz Report Excel add-in (the "Blitz Report" ribbon in
Excel). Write a formula such as `=br_report_list_external("...")` into a cell and read the
spilled result - that is the only way to pull Oracle EBS data here; there is no separate data
connection to look for. The add-in must be loaded and connected to an environment (the user does
this once via the ribbon): `#BLITZ_NOT_CONNECTED` means ask the user to connect first, and
`#NAME?` means the add-in is not loaded.

Financial statements, account balances by period, or explaining a balance down to its journals:
use the **br-run-fsg** skill instead - it builds live statements rather than running a report.

**Read `references/run-mechanics.md` BEFORE your first run.** It carries the full workflow
detail: environment and responsibility selection, parameter and template rules, LOV value
lookups, run monitoring and recovery, error handling, worked examples, and the complete function
reference. This file is only the summary.

## Workflow summary

1. **Find the report** (skip when you already have the exact name):
   `=br_report_list_external("<search words>")` on a helper sheet named `blitz_`.
2. **Inspect parameters**: `=br_report_params_external("<Report Name>")` - set every
   `Must Set? = Yes` parameter and any filters you want; treat everything else as optional (the
   server computes defaults, including ones whose Default column shows blank).
3. **Run it**: `=br_run_report_external("<Report Name>","Name=Value; Name2=A,B,C")` (dates as
   `YYYY-MM-DD`). The cell returns `BLITZ_RUNNING:` and the data populates a NEW sheet.
   **Write the formula and read the cell back in the SAME operation batch, then immediately
   replace that cell with plain text in your next operation** - a separate read of the
   still-present formula can force a second evaluation and start a duplicate run before you
   replace it. Never re-enter the run formula to "check on" a run; poll only `_blitz_run_status`.
4. **Wait**: poll `=_blitz_run_status` (a workbook name) for `DONE: <n> rows on sheet '<name>'`
   or `ERROR: <message>` - one lightweight check per turn, generously spaced, per the reference
   file's monitoring guidance. A status read BEFORE you triggered anything is a stale leftover
   from an earlier run - ignore it and start your run; only values appearing after your trigger
   are yours.
5. **Analyze** the new sheet. The layout is fixed: row 1 = title banner, row 2 = the column
   headers, row 3 onward = the data. Never treat row 1 as headers, and never fabricate values -
   read them from the sheet.

## Core rules (full list in the reference)

- Use report and parameter names EXACTLY as the discovery functions return them.
- Keep every helper formula on `blitz_`; never activate that sheet; delete it when finished. The
  report data lands on its own new sheet - that is the user's deliverable, leave it visible.
- Once a report has produced a data sheet, do not run it again (a second run creates a duplicate
  sheet). `ERROR:` while a populated sheet exists means the data is good and only
  post-processing complained - use the data and note the warning. The same applies when an
  add-in error dialog appears AFTER the sheet populated with the expected rows: a stray
  duplicate run collided with the finished one - the data on the sheet is complete; tell the
  user to dismiss the dialog, and do not re-run.
- Talk to the user in their language ("I'm running the AR Aging report for you"), never in
  function names - the `br_*` functions and `blitz_` are internal plumbing.
