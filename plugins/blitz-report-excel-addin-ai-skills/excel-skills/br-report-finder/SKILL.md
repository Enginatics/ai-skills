---
name: br-report-finder
description: >
  Find the right Oracle EBS Blitz Report by MEANING, not by name: load the full report library once
  into the workbook, then match the user's business question ("which report shows unapplied
  receipts by operating unit?") against every report's name, category and description, explain the
  top candidates, and hand the chosen one to br-run-reports. Use when the user doesn't know a
  report's name, asks "is there a report that...", "which report shows...", or a name search found
  nothing.
# Trigger: Slash command + auto
---

# Blitz Report Finder (br-report-finder)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected).

Turn a business question into the right report. `br_report_list_external(search)` is a plain
substring match over names and descriptions — good when the user knows the name, useless for
"which report shows X". This skill loads the library once and does the matching itself: you read
the catalog and reason over it, which is exactly what a substring search cannot do.

**Requires:** br-run-reports (to run whatever is chosen).

## When to use
"Is there a report that shows …", "which report gives me …", "I can't find the report for …", "what
do you have for <topic>", or after a `br_report_list_external("<name>")` probe came back empty. If
the user names a report exactly, skip this — pass the name straight to br-run-reports.

## Scope honesty — say what the match is based on
The library spill carries **Report Name | Category | Type | Description** — not the SQL, not the
column list. So you match on what the description says, and a poorly-described report can hide.
When confidence is low, say "closest by description" rather than presenting a guess as the answer.
Confirm actual columns before promising a field: `=br_report_params_external("<name>")` shows the
parameters, and a short filtered run shows the columns.

## Step 1 — Load the library  *(once per workbook per environment)*
Look for an existing `BR_Library` sheet first (cell A1 carries `Library: <environment> <date>`). If
present and same environment, reuse it — do not re-pull. Otherwise, on a new sheet `BR_Library`:
write the marker in A1, then `=br_report_list_external()` in A3 (no search argument — the FULL
list) and read the spill: `Report Name | Category | Type | Description`, typically a few thousand
rows. `#BLITZ_NOT_CONNECTED` → ask the user to connect via the Blitz Report ribbon, then retry.

Keep the sheet — it is the cache, and re-runs of this skill in the same workbook must reuse it.

## Step 2 — Translate the question into EBS vocabulary
Users ask in business language; descriptions are written in EBS language. Map before matching —
expand the question with the EBS terms it implies:

| The user says | Match also on |
|---|---|
| unapplied cash / unmatched receipts | receipt, application, on account, AR |
| open invoices we owe | AP invoice, payment schedule, due, aging |
| what customers owe us | AR aging, past due, outstanding, balance |
| stock / on hand | onhand, quantities, subinventory, INV |
| POs not billed yet | uninvoiced receipts, accrual, received not invoiced |
| journals / postings | GL journal, account analysis, balances |
| who changed X | audit, history, last updated |
| jobs on the shop floor | WIP, discrete job, entities |
| duplicate payments | AP invoice, payment, supplier |

Also note the module prefix convention — report names lead with the module (`GL `, `AP `, `AR `,
`INV `, `PO `, `WIP `, `FA `, `CE `, `CST `, `ONT `, `HR `) — and `Type` distinguishes reports from
uploads (`U`): **if the user wants to CHANGE data, filter to uploads and hand over to
br-run-uploads instead.**

## Step 3 — Match and rank  *(read `BR_Library`, reason in-context)*
Read the four columns and score against the expanded question: name hit > description hit >
category hit; prefer reports whose description mentions the user's *dimension* (by operating unit,
by period, by supplier) not just the noun. Produce the **top 3–5**, each with one line of *why* —
quoting the description fragment that matched, never inventing capability. If nothing clears the
bar, say so and show the nearest misses; do not force a winner.

## Step 4 — Confirm the pick and hand over
For the front-runner, show `=br_report_params_external("<name>")` so the user sees the parameters
(the fastest capability check there is). Then offer: run it now → **br-run-reports** with the exact
name; or show the next candidate. Never run anything wide-open from here.

## Validation
- Every recommendation quotes the description it matched — no claimed columns beyond it.
- The library sheet is reused, not re-pulled, within a workbook/environment.
- "No good match" is an allowed and honest answer; it should name what WAS searched (the expanded
  terms) so the user can redirect.

## Roadmap (not this version)
Server-side semantic search — report name + description + SQL text embedded in an Oracle AI
Database vector index, so matching sees what the SQL actually reads, not just what the description
says. This skill's contract (question in, ranked candidates with reasons out) stays the same; only
Step 3's engine changes.
