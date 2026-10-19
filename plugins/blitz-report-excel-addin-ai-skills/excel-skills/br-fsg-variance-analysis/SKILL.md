---
name: br-fsg-variance-analysis
description: Explain why Oracle EBS GL balances moved - compare a financial statement or account balances between two periods, year over year or actual against budget with Blitz FSG, flag the material variances, drill the largest to journal lines and subledger transactions, and draft variance commentary for the user to review. Use for "why did expenses go up", flux analysis, variance analysis, month-over-month or budget-vs-actual review, "explain the movement in this account". Read-only - never writes to Oracle EBS.
---

# GL variance analysis (br-fsg-variance-analysis)

Read `br-analytics-standards` first. Every statement, refresh and drill step runs through the
**br-run-fsg** skill - read its `references/fsg-mechanics.md` before writing any balance formula.
Numbers come only from cells the add-in calculated; commentary says only what the lines show.

## Op 0 — One question message, up front
Ask, with a suggested default for each, in ONE message:
- **What to compare**: an existing statement sheet (name it), or the accounts / lines the user
  cares about on a ledger.
- **Against what**: prior period (default), same period last year, or a budget (name it - the
  budget list comes from br-run-fsg).
- **Materiality**: an amount AND a percentage; suggest 10% and an amount that fits the statement's
  size (say what you suggest and why).
- **Depth**: (a) flag the material lines only; (b) also explain the top 5 from their journal lines
  (default); (c) also drill those to subledger transactions and run detailed reports - slower,
  opt-in.
- If the user's existing statement is used: may you add columns to the right of it (default), or
  should the comparison go on a copy?

## Op 1 — The comparison columns
Beside the current balance column (or on a new statement built with br-run-fsg):
- **Comparison**: the same balance formula with the comparison period
  (`br_period_offset(<period>,-1)` or `(...,-12,,"Exclude")` in a heading cell) or with balance type
  `B` and the budget name.
- **Variance** `=<current>-<comparison>`; **Var %** `=IF(<comparison>=0,"",(<current>-<comparison>)/ABS(<comparison>))`.
- **Flag** `=IF(ABS(<variance>)<<amount cell>,"",IF(<comparison>=0,"Review",IF(ABS(<var %>)>=<pct cell>,"Review","")))`,
  with the two thresholds in labelled cells so the user can change them. Keep the nested IFs:
  `AND`/`OR` evaluate every argument, and `ABS` of the empty Var % of a new line is `#VALUE!`.
- When line kinds are known (income / expense), a **Favourable** column: on natural-sign balances
  (debit +, credit -) a NEGATIVE variance improves profit for both kinds; balance sheet lines get
  no label. If the statement shows revenue positive (multiplier -1), invert accordingly and say so.
Refresh through br-run-fsg; continue only on `DONE` with no cell left without an answer.

## Op 2 — Rank
Flagged lines by absolute variance, largest first (a dynamic-array formula on the analysis sheet,
blanks as 0). Depth (a): go to Op 5.

## Op 3 — Explain the top lines from their journals
For each of the top 5 flagged lines (ask before more than 10 drills): drill the CURRENT balance cell
to `Journals`; for a period comparison also drill the COMPARISON cell (budget has no journals - drill
actual only). One drill at a time. Then on an analysis sheet, per line:
- tie out each drill to its balance (br-run-fsg `drill-and-detail.md`) - report any gap;
- total each drill by Source Name, then Category Name, then Journal Name;
- the change per group between the two drills is the driver list - keep groups that exist in only
  one of the periods (new or vanished activity is often the whole story). The changes must add up to
  the line's variance; report a gap if they do not.

## Op 4 — Subledger and detail reports (depth c only)
For the driver groups from a subledger source, drill those journal rows to `Subledger`, group by
Vendor Or Customer / Transaction Number (lines without either as `No document reference`, so the
groups still add up to the drill), and, if the user wants the documents, run the detailed Blitz
Report per br-run-fsg `drill-and-detail.md`.

## Op 5 — Variance Commentary sheet
One row per flagged line, written in one operation: Line | Current | Comparison | Variance | Var % |
Main drivers (top 3 groups with their change) | Draft explanation | Evidence (sheet and rows) |
Status = `Draft - review`. A draft explanation states the data ("Payables invoices up 60,000, mostly
supplier X, 3 invoices; no manual journals this month against 6,000 last month"), never a business
reason the lines do not show. Lines over the threshold that were not drilled say so in Evidence.

## Op 6 — Reply
The headline movements with their drivers, where the commentary and evidence are, any tie-out gap
or unexplained remainder, and what needs the user: confirming or editing the drafts, and - when
unposted journals or open subledger periods may explain a variance - the GL close-readiness check.
