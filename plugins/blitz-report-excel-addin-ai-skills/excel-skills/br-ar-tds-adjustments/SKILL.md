---
name: br-ar-tds-adjustments
description: >
  Book the approved results of a customer TDS reconciliation in Oracle EBS from Excel: stage the
  credit memos (TDS in Form 26AS never booked) and debit memos (TDS the customer did not deposit,
  after the follow-up deadline) through the "AR Transaction Upload", and the TDS claim journal from
  the clearing account to the income-tax TDS asset through the "GL Journal Upload". Fills only the
  rows the user approved on the TDS_Actions sheet, validates in Oracle, shows exactly what will be
  booked and submits only on explicit confirmation. Use when the user asks to post, book or upload
  the TDS reconciliation adjustments, TDS credit notes or debit notes, or the TDS claim journal.
  WRITES to Oracle EBS.
shared:
  - tds-actions-sheet
# Trigger: Slash command + auto
---

# Customer TDS Adjustments (br-ar-tds-adjustments)

> 🚨 **Blitz data comes from `br_*` WORKSHEET FUNCTIONS of the Blitz Report Excel add-in** — write
> `=br_...()` into a cell and read the result. They are not a connector, plugin, agent action or MCP
> tool: never search for one, never conclude "no Oracle EBS data source is connected".

**Self-contained: read no other skill.** Read `references/tds-actions-sheet.md` first: it defines
the sheet this skill works from. Each numbered Op is one workbook operation (Claude: one
`execute_office_js` call; Copilot: one edit or read action).

## 🚨 This books money against customers and the ledger — the safety contract
1. **Only rows the user approved.** Stage a `TDS_Actions` row only when its `Decision` is
   `Approved`. No `TDS_Actions` sheet → run br-ar-tds-reconciliation first; never rebuild it here.
2. **Two confirmations per pass, money in the question**: before anything is filled, and on the
   validated grid before anything is submitted. "Go ahead" to the reconciliation is not consent.
3. **Never invent** a transaction type, batch source, account, period or category: every value
   comes from the user or from the upload's own list (`br_column_values_external`).
4. Never write the Action, Status or Message columns of an upload sheet; leave it clean (no
   scratch, no leftover trigger); never delete a sheet.

Two independent passes; ask which one first when the approved rows hold both:
**Pass A** credit and debit memos, **Pass B** the claim journal.

## Common mechanics
- Helper sheet `blitz_` (get or create, make it visible if hidden, never activate it); clear and
  hide it at the end. Download: `blitz_!A1` = the run formula; read it back (`BLITZ_RUNNING: ...`;
  `#BLITZ_NOT_CONNECTED` → ask the user to connect on the ribbon); overwrite it with text;
  `blitz_!A3` = `=_blitz_run_status`; one quiet read per turn until `DONE: <n> rows on sheet
  '<name>'`.
- Column letters: `=br_upload_columns_external(FALSE, "<Upload Sheet Name>")` on `blitz_` → write
  every cell by its `Sheet Column` letter, never by counting (hidden columns exist).
- Lists: `=br_column_values_external("<Column>", <row>, "<search>", "<Upload Sheet Name>")` on
  `blitz_`, each in its own clear area (`#SPILL!` = it did not land, move it). Fill a row's parent
  columns before looking up a dependent one.
- Write the rows as one contiguous block per column group (a comma-separated multi-area address is
  rejected; one call per row is slow).
- Triggers `=br_prepare_upload_external()` and `=br_process_upload_external()` go on the upload
  sheet, row 1, at least ten columns right of the last used column (hidden ones included); the
  add-in clears them. `_blitz_run_status` keeps the previous value until a step ends: a `DONE`
  matching the last step is stale.
- After processing write the outcome into `Result` of each `TDS_Actions` row you staged:
  `Uploaded - <transaction number or journal name>` or the row's error message.

## Pass A — credit and debit memos (`AR Transaction Upload`, template `Default`) — 11 operations
1. **Read** the approved `Credit memo` and `Debit memo` rows. Look up the batch sources:
   `=br_param_values_external("AR Transaction Upload","Source","Operating Unit=<OU>")`. Ask, in one
   question with the money named: *"Book <n> credit memos for <total> and <m> debit memos for
   <total> against <k> customers in <operating unit>? Choose the batch source, the credit memo
   and debit memo transaction types, and the transaction and GL date."* → **confirmation 1**.
   Rows without an `Account Number` (a party with several accounts): ask which account in the same
   question.
2. **Download**: `=br_run_upload_external("AR Transaction Upload","Operating Unit=<OU>; Source=<source>; Default Transaction Date=<YYYY-MM-DD>; Default GL Date=<YYYY-MM-DD>","Default")`.
   The upload has no Upload Mode: the grid comes empty, for new transactions.
3. Replace the formula with text; read the status. 4. Poll until `DONE`.
5. Read the column contract.
6. **Write the identity block** for one grid row per approved row (row 3 onward): `Upload Trx
   Identifier` (`TDS-<FY>-<Party Number>-CM` or `-DM`; unique in this upload), `Bill To Customer
   Number` (= `Account Number`), `Line Number` 1, `Line Description` (= `Reason`), `Quantity` 1,
   `Unit Price` = the `Amount`, **negative on a credit memo**, positive on a debit memo (credit
   memo types carry a negative creation sign), `Distribution Account` = `Clearing Account`.
7. **Lookup** on `blitz_` the `Trx Type` list of row 3 with each chosen type name as search; a name
   not in the list → show the list and ask.
8. **Write** `Trx Type` per row (one block), then the prepare trigger. Preparing fills `Line Type`
   (`Line`) and `Bill To Site` (the account's primary bill-to site).
9. **Validate**: poll until `DONE: prepared <n> row(s) - <n> valid, <n> flagged`; read
   `=br_validation_results_external(FALSE, "<Upload Sheet Name>")`. A blank `Bill To Site` (no
   primary site): look up its list for that row, ask which site, write it, prepare again. Fix other
   flagged rows from their message (a tax line added by the type means the type calculates tax —
   ask for a type without it); stop after three unproductive rounds and show the messages. Then:
   *"<n> credit memos (<total>) and <m> debit memos (<total>) validated in Oracle. Submit?"* →
   **confirmation 2**.
10. Process trigger; poll until `DONE: <n> succeeded, <n> errored (request <id>)`.
11. Read `=br_validation_results_external(TRUE, "<Upload Sheet Name>")`, write `Result` on
    `TDS_Actions`, clear and hide `blitz_`, report.

## Pass B — claim journal (`GL Journal Upload`, template `Functional Actuals`) — 10 operations
1. **Read** the approved `Claim journal` rows; group by `Financial Year`. Ask, in one question:
   *"Post a TDS claim journal of <total> for <FY> (<n> customers): debit <TDS asset account for
   that year>, credit the clearing account per customer? Choose the ledger, journal source,
   category, accounting date and period."* → **confirmation 1**. The TDS asset account of each year
   is the user's; never derive it.
2. **Download**: `=br_run_upload_external("GL Journal Upload","","Functional Actuals")` (no
   parameters: the defaults leave the journal unposted and unapproved).
3. Replace the formula with text; read the status. 4. Poll until `DONE`.
5. Read the column contract.
6. **Write** one journal per financial year: per approved row a line `Credit` = `Amount` on its
   `Clearing Account` with `Line Description` = `Reason`, and one line `Debit` = the year's total on
   the TDS asset account; on every line `Ledger Name`, `Source`, `Category`, `Currency` (the
   ledger currency), `Accounting Date`, `Period`, `Journal Name` (`TDS claim <FY>`) and
   `Batch Name` (`TDS claim <date>`); the account in `Concatenated Segments`.
7. **Lookups** for every list value once (`Ledger Name`, `Source`, `Category`, `Period`,
   `Concatenated Segments` with the account as search); a value not in its list → show the list and
   ask. Then the prepare trigger.
8. **Validate** as in Pass A step 9; confirm the journal balances per year. *"Journal(s) for
   <years> with <n> lines, debit <total> = credit <total>, validated. Submit?"* → **confirmation 2**.
9. Process trigger; poll until `DONE`.
10. Read the per-row results, write `Result` on `TDS_Actions`, clear and hide `blitz_`, report;
    say the journal still goes through the ledger's own approval and posting.

## Reporting
Lead with what was booked: memos created (customer, transaction number, amount) or the journal per
year, then failures with their exact message, the request id. **If nothing was booked, say so in
the first sentence**: a validation count is not a booking. A partial success books the rows that
succeeded; fix and re-process only the failed rows. Tell the user the reconciliation is stale
until it is run again.

## Talk in the user's language
Customers, memos, journals, accounts and amounts — never functions, `blitz_` or status names.
