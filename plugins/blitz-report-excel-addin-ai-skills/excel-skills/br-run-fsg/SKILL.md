---
name: br-run-fsg
description: Build, refresh, read and drill Oracle EBS financial statements in Excel with Blitz FSG through the Blitz Report add-in - income statement, balance sheet, trial balance, account balances by period, actual vs budget - and explain a number by drilling it to account balances, journal lines and subledger transactions, then to a detailed Blitz Report of those transactions. Use when the user asks for a financial statement, P&L, balance sheet, a GL or account balance for a period ("what was cash at the end of December"), or to explain, drill, trace or tie out a balance. Read-only - never writes to Oracle EBS.
---

# Financial statements in Excel (br-run-fsg)

A Blitz FSG statement is an ordinary worksheet whose cells hold balance formulas the Blitz
Report add-in calculates from Oracle General Ledger. You write the statement (labels, account
rows, balance formulas, totals); the add-in's `br_fsg_*` worksheet functions give you the ledger's
structure and lists, make the sheet a statement, refresh it and drill a balance. They are Excel
functions you write into a cell - never tools or connectors. `#BLITZ_NOT_CONNECTED` = ask the user
to connect on the Blitz Report ribbon; `#NAME?` = the add-in is not loaded.

**Read `references/fsg-mechanics.md` before your first statement** (functions, balance formula
arguments, segment syntax, statuses). Recipes for common statements: `references/statement-recipes.md`.
Drilling, analysing drilled lines and running detail reports: `references/drill-and-detail.md`.

## Workflow summary

1. **Ledger.** On a helper sheet `blitz_`: `=br_fsg_ledgers_external()`. Use the ledger the user
   names; if several fit, ask.
2. **Ledger profile.** `=br_fsg_ledger_external("<Ledger>")` - functional currency, latest open
   period, the segments in display order with the balance formula argument each goes into, and
   the ready balance formula pattern. Segment values: `=br_fsg_values_external("<Ledger>","<Segment>","<search>")`.
3. **Statement sheet.** `=br_fsg_new_statement_external("<Ledger>","<Sheet name>")` - a new sheet,
   or the user's own sheet claimed as it is. Write the formula and read its return in the SAME
   operation, then replace that cell with plain text. Wait for `=_blitz_run_status` to read
   `DONE: sheet '<name>' ...`. A workbook that already holds the user's statement needs no new sheet.
4. **Write the statement** on that sheet: criteria cells (period, amount type, currency...), one
   row per account or parent value, balance formulas from the pattern referencing those cells,
   descriptions, totals - per the recipes. Nothing is calculated yet: cells show `(pending)`.
5. **Refresh.** `=br_fsg_refresh_external("<Sheet name>")` (same write-read-replace), then poll
   `_blitz_run_status` for `DONE: <n> value(s) refreshed` - it names any cell still without an
   answer; fix those cells and refresh again.
6. **Read and answer** from the cells. Never compute a balance yourself or invent one.
7. **Explain a number** on request: `=br_fsg_drill_external("<cell>","Journals","<Sheet name>")`
   puts the journal lines behind it on a new sheet; drill on to the subledger and run a detailed
   Blitz Report of those transactions per `references/drill-and-detail.md`.

## Core rules

- One action at a time (statement, refresh, drill): wait for `DONE:` or `ERROR:` before the next.
  Poll only `_blitz_run_status`, one check per turn; never re-enter an action formula to check on it.
  A status read before your own trigger is stale - ignore it.
- Every argument of a balance, period or description formula is a quoted literal or a plain cell
  reference - never an expression. Segment values are text: quote them (`"01"`, never `01`) and
  give a cell holding one the Text format before writing it. A literal period such as `Dec-12`
  goes into a Text-format cell, or Excel turns it into a date; a FORMULA never goes into a
  Text-format cell.
- Ask before writing over cells the user already has; build into empty cells or a new sheet.
- Keep `blitz_` for helper formulas, never activate it, delete it when done. The statement and
  drill sheets are the user's deliverables.
- Talk about ledgers, periods, accounts, balances and journals in the user's terms - never name
  the add-in's functions, `blitz_` or the status name.
- Read-only: this skill never posts or changes anything in Oracle EBS.
