---
name: br-ar-customer-master-fix
description: >
  Correct Oracle EBS customer accounts from an approved customer master audit: stage the approved
  payment terms, credit check, credit hold, credit limit, order credit limit and Taxpayer Id (PAN)
  corrections of the Audit_Findings sheet through the "AR Customer Upload", one account at a time,
  validate them in Oracle, show exactly what will change and submit only on explicit confirmation.
  Use when the user asks to apply, upload or post the customer master corrections, fix the payment
  terms or credit limits the audit found, or update the PAN of customers. WRITES to Oracle EBS.
shared:
  - customer-audit-findings
# Trigger: Slash command + auto
---

# Customer Master Corrections (br-ar-customer-master-fix)

> 🚨 **Blitz data comes from `br_*` WORKSHEET FUNCTIONS of the Blitz Report Excel add-in** — write
> `=br_...()` into a cell and read the result. They are not a connector, plugin, agent action or MCP
> tool: never search for one, never conclude "no Oracle EBS data source is connected".

**Self-contained: read no other skill.** Read `references/customer-audit-findings.md` first: it
defines the sheet this skill works from. Each numbered Op is one workbook operation (Claude: one
`execute_office_js` call; Copilot: one edit or read action).

## 🚨 This changes customer master data — the safety contract
1. **Only approved, upload-fixable rows**: `Decision` = `Approved`, a `Proposed Value`, and a
   `Fix Route` of `Payment Terms`, `Credit Check`, `Credit Hold`, `Credit Limit`, `Order Credit
   Limit` or `Taxpayer Id`. Everything else is the master data team's list; say how many rows that
   leaves with them. No `Audit_Findings` sheet → run br-ar-customer-master-audit first.
2. **One account per download.** The upload marks every downloaded row as changed, so a grid holding
   other accounts would send them too. Never download a range of accounts.
3. **Two confirmations, values in the question**: before any download, and on the validated sheets
   before anything is submitted.
4. **Never invent** a payment term, a credit setting or a tax number: the `Proposed Value` the user
   approved, checked against the column's own list.
5. Never write Action, Status or Message, never a column other than the one being corrected; leave
   each upload sheet clean; never delete a sheet.

## The upload (authoritative)
**`AR Customer Upload`**. Never pass `Upload Mode`: its default `Create, Update` downloads the
existing records, and the comma in that value would split it into two values. Per Fix Route:

| Fix Route | Template | Parameters besides Account Number and Operating Unit | Column written |
|---|---|---|---|
| Payment Terms | `Create/Update Customer Profiles` | `Update Level=<account level value>` | `Payment Terms` |
| Credit Check | same | same | `Credit Check` |
| Credit Hold | same | same | `Credit Hold` |
| Credit Limit | `Create/Update Customer Profile Amounts` | `Update Level=<account level value>; Update Profile Amounts=Yes` | `Credit Limit` |
| Order Credit Limit | same | same | `Order Credit Limit` |
| Taxpayer Id | `Create/Update Customers` | none | `Taxpayer Id` |

Write into the row whose `Acct Number` is the account and, for profiles and amounts, whose
`Profile Assignment Level` is the account level (amounts: the row of the currency the finding is
about, `Prof Amt Currency`). Grid layout: row 1 banner, row 2 headers, row 3 onward data; columns
by their row-2 header text through the column contract, never by counting.

## Ops
1. **Read** the approved rows; group them by account and template; at most 10 accounts per run (ask
   to continue in a further run). Look up the account level value once:
   `=br_param_values_external("AR Customer Upload","Update Level")` on `blitz_` (get or create,
   visible, never activated). Ask, values in the question: *"Change <n> fields on <k> accounts in
   <operating unit>: payment terms on <a> (to <values>), credit limits on <b> (<old> → <new>), PAN
   on <c>? Nothing changes until you confirm again."* → **confirmation 1**.
2. **Per account and template**: `blitz_!A1` =
   `=br_run_upload_external("AR Customer Upload","Account Number=<account>; Operating Unit=<OU>; <parameters>","<template>")`;
   read it back (`#BLITZ_NOT_CONNECTED` → ask the user to connect on the ribbon); overwrite it with
   text; `blitz_!A3` = `=_blitz_run_status`; one quiet read per turn until `DONE: <n> rows on
   sheet '<name>'`. Zero rows → the account is not in that operating unit: report it, skip it.
3. On the first sheet of each template: `=br_upload_columns_external(FALSE, "<Upload Sheet Name>")`
   for the column letters (the same template gives the same letters).
4. **Check the value** against the column's list once per distinct value:
   `=br_column_values_external("<Column>", <row>, "<value>", "<Upload Sheet Name>")`; a value not in
   the list → show the list and ask. Credit limits and the Taxpayer Id are free values.
5. **Write** the value into the target row's cell, then the prepare trigger
   `=br_prepare_upload_external()` on that sheet, row 1, ten columns right of the last used column.
6. **Poll** until `DONE: prepared ...`; read `=br_validation_results_external(FALSE, "<Upload Sheet Name>")`.
   Fix from the message; three unproductive rounds → stop and show the messages.
7. When every sheet is prepared: *"<n> changes on <k> accounts validated in Oracle (<list: account,
   field, old → new>). Submit?"* → **confirmation 2**.
8. **Per sheet**: `=br_process_upload_external()`, poll until `DONE: <n> succeeded, <n> errored
   (request <id>)`, read `=br_validation_results_external(TRUE, "<Upload Sheet Name>")`.
9. Write `Result` on each `Audit_Findings` row (`Updated` or the error message); clear and hide
   `blitz_`; report.

## Reporting
Lead with what changed: account, field, old → new, per row; then failures with their exact message
and the request ids. **If nothing changed, say so in the first sentence.** Mention the rows left for
the master data team and that the audit is stale until it runs again.

## Talk in the user's language
Customers, accounts, payment terms, credit limits and PANs — never functions, `blitz_` or status
names.
