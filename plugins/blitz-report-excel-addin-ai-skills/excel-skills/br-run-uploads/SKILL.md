---
name: br-run-uploads
description: Create, load or update Oracle EBS records from Excel with Blitz Uploads via the BLITZ REPORT ADD-IN (the br_* worksheet functions) - journals, invoices, purchase documents, items, suppliers, customers, assets and more (GL, AP, AR, PO, INV, WIP, HR, FA, CE). Use whenever the user says they want to UPLOAD, LOAD, POST, ENTER, CREATE or UPDATE any EBS data or document ("upload a journal entry", "upload journals", "load invoices", "create a PO", "post a journal"). In this add-in "upload" means sending data INTO Oracle EBS - it does NOT mean the user is attaching a file to the chat, so never ask them to attach one and never hand-build a mock table in the sheet instead. NOT for the standalone Blitz Upload template file (UploadTemplate.xlsm with bu_* functions) - that is bu-fill-upload's territory. This WRITES to Oracle EBS.
---

# Run Blitz Uploads in Excel

A **Blitz Upload** loads data INTO Oracle EBS — it creates or updates real records (purchase
documents, invoices, items, journals, etc.). This is the opposite of a Blitz *Report*, which only
reads. **Uploads change EBS data, so treat every upload as consequential:** confirm intent, review
what will be sent, and always read the per-row results afterward.

The Blitz Report add-in must be loaded and **connected to an environment + responsibility** (the user
does this once via the ribbon). `#BLITZ_NOT_CONNECTED` → ask them to connect via the Blitz Report
ribbon first. Environment/responsibility selection works exactly as in the **br-run-reports** skill
(same `br_environments_external()` / `br_responsibilities_external()` discovery, same optional
trailing `environment`/`responsibility` args, same sticky selection) — see that skill for the detail;
this skill covers only what is different for uploads.

## Read vs write — pick the right skill
- The user wants to **see / analyze** existing data → use **br-run-reports**.
- The user wants to **create / update / load** data into EBS → this skill.
Uploads appear in the same catalogue as reports but with **`Type = U`**.

## br_* vs bu_* — two different Blitz products, never mix them
This skill drives the **Blitz Report add-in** (`br_*` functions). The separate standalone Blitz
Upload template file exposes `bu_*` functions and has its own skills (`bu-fill-upload`,
`bu-ap-invoice-upload`). The families are not interchangeable — the wrong one returns `#NAME?`.
If `=br_ai_ping()` returns `#NAME?` but the workbook is a standalone upload template (an `Upload` +
`Parameters` sheet, `bu_ai_ping()` works), switch to the bu skills; otherwise the report add-in
simply isn't loaded — ask the user to load/connect it. Never retry the other family's function to
work around a `#NAME?`.

## Keep the workbook tidy
Do discovery on a throwaway helper sheet named **`blitz_`** (create it, delete it when done), exactly
as in br-run-reports. The **upload grid itself lands on its own new sheet** created by
`br_run_upload_external` — that is the working deliverable the user edits; leave it visible.

**🚨 NEVER activate the `blitz_` sheet.** You can write formulas to it and read their results
without it being the active sheet — so just don't call `activate()` on it. Activating it (a) puts
your scratch sheet in the user's face instead of their deliverable, and (b) leaves it as the ACTIVE
sheet, which breaks the prepare/process step: those run the add-in's Autofill and Validate, which
act on whatever sheet is active. The upload sheet should be the active one throughout.

**Every one of these functions SPILLS**, so give each one clear space below and to the right, and
**always check the returned cell for `#SPILL!`** — it means the result did not land at all
(something is in its way), not that there was nothing to report. Reuse ONE area per purpose and
clear it before re-running, rather than working down the sheet into ground you already used.

## The upload sheet layout (fixed, deterministic — do not probe)
- **Row 1** = the report-name banner + the run formula + a "Last run | Records: N" info cell — NOT data.
- **Row 2** = the column headers.
- **Row 3 onward** = the data rows.
- The first three data columns are always **Action** (A), **Status** (B), **Message** (C) — the
  framework columns. The business columns (e.g. `PO Number`, `Item`, `Quantity`) follow from column D.
- **Get the exact column contract from `=br_upload_columns_external()`** (call it on `blitz_` with
  the upload sheet name: `=br_upload_columns_external(FALSE, "<Upload Sheet Name>")`). It spills one
  row per column: `Sheet Column | Column | Type | Required | Read Only | Has LOV | Free Text |
  Comments` — the REAL Excel column letter, the row-2 header text, the flags, and whether the
  list is binding. **Always write cells by the returned `Sheet Column` letter — never derive a
  column's position by counting**, because hidden columns sit between visible ones and counting
  drifts. Hidden columns are excluded from the spill so every listed column is safe to write (except
  the read-only ones).
- **`Has LOV = Yes` with a blank `Free Text` means the value MUST be one from the list** — the server
  rejects anything else, so look it up (below) and never type your own. `Free Text = Yes` means the
  list only assists entry; a value outside it is allowed but still has to make sense to EBS, so
  prefer a looked-up value there too.
- **🚨 The sheet has HIDDEN columns to the RIGHT of the last one the contract lists** (framework
  internals and round-trip ids — often dozens). So "the last column" for the purpose of placing a
  trigger formula is NOT the last row of the contract spill: read the sheet's **used range** and go
  a few columns beyond that. A trigger dropped inside the hidden-column span is inside the grid, so
  the add-in refuses to clean it up and it is left behind as junk on the user's deliverable sheet.
- Fallback on older add-in builds (`#NAME?` from the function): **amber** header = required,
  **grey** data cells = read-only; ignore anything past the visible columns.

## Workflow — follow in order

1. **Find the upload.** On `blitz_`: `=br_report_list_external("<search words>")` and choose a row
   whose **`Type` is `U`**. (If the user gave the exact upload name, skip discovery and go to step 3;
   a wrong name returns `#BLITZ_REPORT_NOT_FOUND` instantly.)

2. **Inspect its parameters** (the *download* parameters, not the data columns):
   `=br_report_params_external("<Upload Name>")`. Same `Must Set?` rules as br-run-reports. The
   parameter list is the source of truth — **only pass parameters that appear in it**; sending one
   the upload doesn't define fails the whole run with `ORA-20001: Parameter "<name>" not found`.

   About **half** of the uploads have an **Upload Mode** parameter; the rest (e.g. `GL Journal
   Upload`) do not. When it IS listed:
   - **`Create, Update`** (the default) downloads the matching EXISTING records so you can edit them.
   - **`Create`** gives an EMPTY template to add brand-new records.
   Set filters (Operating Unit, Document Type, date ranges, etc.) to scope which existing rows come
   down in Create,Update mode. When it is NOT listed, don't pass it — the upload's own default
   applies (these are typically create-only templates).

2b. **Choose the TEMPLATE** — `=br_report_templates_external("<Upload Name>")` on `blitz_`.
   The template decides the **column set** you get, so this matters as much as the parameters. An
   upload often ships several (e.g. `GL Journal Upload` has `Functional Actuals`, `Foreign Actuals`,
   `Budget Journal`, `Encumbrance Journal`, and `(with attachment)` variants).
   - If the user named one ("Functional Actuals"), pass **that exact template name**.
   - If several plausibly match their wording (e.g. plain vs `(with attachment)`), **ASK** which —
     don't guess; this writes to EBS.
   - If they said nothing about a template, you may omit it: the run then uses the upload's
     **default** template (the `Default?` = `Yes` row) automatically.
   Template names are NOT the same thing as parameter values. `Functional Actuals` is a TEMPLATE;
   `Journal Type=Actual` is a PARAMETER. Never tell the user a real template "isn't a template".

3. **Run the upload.** On `blitz_`, in an empty cell:
   `=br_run_upload_external("<Upload Name>","<params>","<template or blank>")`
   - `params` format is identical to reports: `"Name=Value; Name2=A,B,C"`. For uploads that HAVE an
     Upload Mode parameter it defaults to `Create, Update` (pass `Upload Mode=Create` for an empty
     template); uploads without that parameter are run untouched, so never add it yourself.
   - The cell returns `BLITZ_RUNNING: ...`; a **new upload sheet** appears with the grid.
   - **Immediately overwrite that formula cell with a plain value** so a recalc can't re-fire a second
     run, then poll `_blitz_run_status` for `DONE: <n> rows on sheet '<name>'` / `ERROR: <message>`.
     Wait for `DONE` before touching the sheet.

4. **Fill / edit the data** on the upload sheet (rows 3+):
   - **Create new records:** write values into the business columns of empty rows (from column D).
     Set only the columns you have values for; **required** columns (amber headers) must be filled.
   - **Update existing records:** change the business-column values in the downloaded rows. Leave the
     key columns that identify the record intact.
   - Do NOT write into read-only (grey) cells, the hidden columns, or the Action/Status/Message
     columns — the add-in manages those.
   - **🚨 Especially never write the Action column (A).** The prepare step looks each row up in
     Oracle and sets Action itself — `Create` when the record is new, `Update` when it already
     exists. If you put a value there the add-in **respects yours instead of deciding**, so a wrong
     guess (`Update` on a record that doesn't exist yet, or `Create` on one that does) silently
     makes the row do the wrong thing. Leave A, B and C blank; they fill themselves.
   - **NEVER invent a value for a list-of-values column — look it up and write only a value that is
     in the list.** Use
     `=br_column_values_external("<Column Header>", <row>, "<search>", "<Upload Sheet Name>")` **on
     the `blitz_` sheet** — always pass the 4th argument naming the upload sheet, so the lookup reads
     that sheet's row context while the returned list lands on `blitz_` and never litters the
     deliverable grid. (Omitting it makes the function read the sheet the formula sits on, which
     answers `#BLITZ_NOT_UPLOAD_SHEET` from `blitz_`.) It returns `Value | Description`, exactly what
     a user gets by double-clicking that cell. This is the grid-column lookup;
     `br_param_values_external` serves the *download parameters* and correctly answers
     `#BLITZ_PARAM_NOT_FOUND` for a grid column like `Ledger Name`.
     - **🚨 The two lookups do NOT take the same arguments.** Grid column:
       `br_column_values_external(column, row, search, sheet)` — 3rd argument is a **search filter**.
       Download parameter: `br_param_values_external(report, parameter, parent_values, environment,
       responsibility)` — its 3rd argument is **parent parameter values** (`"Name=Value; ..."` for a
       dependent LOV), **NOT a search**. Passing a search word there filters nothing and silently
       returns the whole list; read the returned list yourself instead.
     - Column LOVs are **row-context dependent** (Period depends on Ledger, GL segments on the chart
       of accounts), so pass the **row** you are filling and fill that row's PARENT columns first —
       e.g. write `Ledger Name` in row 3, then ask for `Period` with row 3.
     - If the user's wording doesn't match a returned value exactly (their "Manual" vs the actual
       Source values), **show them the list and ask** — don't pick a lookalike. This writes to EBS.
     - `#BLITZ_LOV_TOO_LARGE` → call again with a `search`. `#BLITZ_LOV_EMPTY` → the parent columns
       for that row aren't filled yet (or no values exist for that context).
       `#BLITZ_NOT_LOV_COLUMN` → free text, type the value directly.
   - Some columns auto-fill from others (e.g. entering `Item` fills `Category`, `Unit of Measure`,
     `Price`, `Description`). If a dependent column stays blank after you set its parent, fill it
     yourself with the correct value.

4a. **Filling from source documents** (the user attached or pasted invoices, bills, vouchers,
   statements, receipts — any document whose data should land in EBS):
   - **Fill only what is printed on the document.** Unknown field → leave it blank; never infer,
     never compute, never fill a gap with something plausible. Blank + validate beats guessed.
   - **Amounts and dates verbatim.** Copy the printed total exactly — do not recompute it from the
     lines, strip/add tax, or fix rounding. If the lines don't sum to the printed total, write the
     printed total and TELL THE USER about the discrepancy. Watch ambiguous date formats
     (`03/04/2026` is 3 April in most of the world, 4 March in the US) — if the document doesn't
     disambiguate, ask.
   - **Required ≠ must-type.** A required column may be filled by the server (defaults, autofill
     derivation). Fill what the document gives, run the prepare step, and let the validation
     Message tell you authoritatively what is genuinely missing — don't invent values to satisfy an
     amber header.
   - **Internal ids are never on the document.** Supplier numbers, site codes, account ids etc. are
     the customer's own master data — resolve them with `br_column_values_external` (searching by
     the NAME printed on the document), never read them off the document or invent them.
   - **Stop after ~3 unproductive fix rounds.** If the same rows keep failing validation, show the
     user the exact messages and ask instead of iterating blindly.
   - Document-type specifics (which printed field maps to which column) live in dedicated skills —
     e.g. **br-ap-invoice-upload** for supplier invoices/bills into Oracle Payables.

4b. **Review before submitting (recommended).** In an empty cell **on the upload sheet**, in row 1,
   a few columns to the RIGHT of the sheet's **used range** — NOT the last column the contract
   listed, which is only the last VISIBLE one (see the hidden-column warning above):
   `=br_prepare_upload_external()` — this marks the rows you wrote, runs **Autofill** (deriving the
   dependent columns) and **Validates**, without sending anything to EBS. Poll `_blitz_run_status`
   for `DONE: prepared <n> row(s) - <n> valid, <n> flagged`, then read the per-row outcome with
   `=br_validation_results_external(FALSE, "<Upload Sheet Name>")` on `blitz_` — it spills
   `Row | Action | Status | Message` for exactly the rows that need attention (or
   `BLITZ_OK: no rows need attention`). Fix the flagged rows' values and run the prepare again.
   Show the user this state before you submit anything non-trivial.
   The add-in **clears the trigger cell itself** when it finishes, so do NOT overwrite it with a
   marker value — that would just leave your marker behind as junk on the user's sheet.
   *(Why marking is needed: your writes go through office-js, which does NOT fire the add-in's
   Excel events, so rows you fill have an empty Action/Status until this runs.)*

5. **Process (submit) the upload.** On the upload sheet (or `blitz_`), in an empty cell:
   `=br_process_upload_external()`
   - It performs the same mark → autofill → validate steps itself before submitting, so step 4b is
     an optional review point, never a prerequisite.
   - This runs the SAME circuit as the ribbon **Upload** button: it **validates every row first**
     (invalid rows are flagged and NOT sent), builds the file, submits it to EBS, waits for the
     concurrent request, and **renders the per-row result back into the sheet** (Status + Message),
     then sets `_blitz_run_status` to `DONE: <n> succeeded, <n> errored (request <id>)` or `ERROR:`.
   - Put it in row 1, a few columns to the RIGHT of the sheet's **used range** (hidden columns
     extend past the last column the contract lists). The cell returns
     `BLITZ_PROCESSING: ...`; the add-in **clears that trigger cell itself** when processing ends, so
     do NOT overwrite it with a marker (a leftover `process_triggered` next to the grid is exactly
     the junk this avoids). Just poll `_blitz_run_status`. Processing can take a while for large
     uploads — do ONE lightweight status check per turn and wait between turns (same "go quiet" rule
     as br-run-reports; office-js has no `setTimeout`, and hammering the workbook collides with the
     add-in's background write).
   - **`_blitz_run_status` keeps the PREVIOUS value until the new run finishes** — a `DONE:` that
     matches the last step (e.g. `DONE: prepared ...` right after you triggered a submit) is STALE,
     not a result. Keep polling until it changes to a `DONE:`/`ERROR:` that belongs to this step.
     The same applies BEFORE you start: an `ERROR:` (even a bare `ERROR: ERROR`) found in the
     workbook before you triggered anything is leftover from an earlier run or session — never
     abort, adapt, or report failure because of it; trigger your step and read only what appears
     afterwards.

6. **Report the outcome.** When `DONE`:
   - Read the per-row results with `=br_validation_results_external(FALSE, "<Upload Sheet Name>")`
     on `blitz_` — it lists every row that errored with its Action, Status and exact Message
     (`BLITZ_OK` means everything succeeded). Pass `TRUE` as the first argument to also list the
     succeeded rows when the user wants the full picture.
   - Summarise: how many succeeded, how many errored, and the specific error messages for the failed
     rows. **Never claim success without reading the per-row results.**
   - To retry failures: fix the flagged rows' values and run `=br_process_upload_external()` again
     (only rows that still need processing are sent).

## Filling the sheet from documents (invoices, statements)

The customer can define how a document is read into an upload, as FND lookups maintained with the
FND Lookup Upload. Check for one before reading documents into the sheet:
1. Run the report **FND Lookup Values** with `Type=XXEN_DOCUMENT_TYPES` (as in br-run-reports). No
   rows, or the type is unknown: there are no document types, so read the documents as the
   upload-specific skill says.
2. Take the row whose **Tag** is this upload; if several fit, ask which **Meaning** (the document
   type) the documents are. Its **Description** says how to read them (for example one row per
   invoice line, the header values repeated on every row). Its **Code** is the mapping.
3. Run **FND Lookup Values** with `Type=<that Code>`: one row per upload column the document fills.
   **Code** is the column (`INVOICE_NUMBER` is the header `Invoice Number`), **Description** says
   where the value is on the document, **Tag** is the value when the document does not show it.
4. Fill only those columns, as the descriptions say, with the Tag where the document is silent, and
   leave every other column to the upload's own defaults. The mapping is the customer's, so it wins
   over the generic reading guidance of an upload-specific skill.

## Talk to the user in THEIR language, never in function names
The `br_*` functions, the `blitz_` sheet, trigger cells and `_blitz_run_status` are **your
plumbing**. The user never types them and should never have to read them — quoting a function name
back at them turns a simple confirmation into homework. Describe what you are about to do, or what
happened, in terms of their work:

| Say this | Not this |
|---|---|
| "Ready to submit this invoice to Oracle Payables — shall I go ahead?" | "Say the word and I'll run `br_process_upload_external()` to submit it to EBS." |
| "I validated both lines against Oracle — both passed." | "I ran `br_prepare_upload_external()` and `_blitz_run_status` came back `DONE: prepared 2 row(s) - 2 valid`." |
| "The supplier resolved to Advanced Network Devices, number 1013." | "`br_column_values_external` returned Value/Description 1013." |
| "I couldn't find that PO in Oracle, so I left the PO field blank." | "`Invoice Po Number` has an LOV without `Free Text` and the LOV returned no match." |

**Sheet, column and value names ARE fine** — the user can see those on screen ("I left *Invoice Po
Number* blank", "row 3", "the *AP Invoice Upload* sheet"). It is the add-in's internals that stay
behind the curtain. Same for asking permission: ask about the *action* ("submit these 2 invoice
lines to Oracle?"), never about the mechanism.

## Rules & safety
- **This writes to Oracle EBS.** If the user's request is ambiguous about creating vs updating, or
  about scope, confirm before running `br_process_upload_external`. Prefer showing them the filled
  grid first for anything non-trivial.
- Use upload, parameter, and column names **exactly** as the discovery functions return them.
- **Leave the upload sheet clean.** It is the user's deliverable. Keep every lookup on `blitz_`
  (pass the upload sheet name as the `sheet` argument), put the two trigger formulas well to the
  right of the grid, never write marker text such as `process_triggered`, and clear any scratch you
  did put on the sheet before you report the outcome. Delete `blitz_` when you are finished.
- **Do not write placeholder/sample data into an upload sheet.** If you lack the real values, fill
  what you know, look up the LOV columns, and ask the user for the rest — a grid seeded with invented
  accounts and amounts looks ready to submit and is one `br_process_upload_external()` away from
  hitting EBS.
- `#BLITZ_NOT_CONNECTED` → connect via the ribbon. `#BLITZ_REPORT_NOT_FOUND` → re-check the name with
  `br_report_list_external` (filter to `Type = U`). Environment/responsibility errors → same handling
  as br-run-reports.
- `ORA-20001: Parameter "<name>" not found` → you passed a parameter this upload doesn't define.
  Re-read `br_report_params_external` and drop it. Do NOT retry the same call, and do NOT conclude
  the environment is broken or try a `COPY OF:` variant — the copy has the same parameter list.
- `_blitz_run_status = ERROR: ...` on the RUN → report it, don't invent data. On the PROCESS →
  read the message; `phase/status` failures mean the concurrent request itself failed (report the
  request id so the user can check the request log).
- **A `DONE` with `N errored` is a partial success, not a failure** — the succeeded rows DID commit
  to EBS. Report exactly which rows succeeded and which errored; do not re-process the whole sheet
  blindly (that would resend the already-committed rows).
- Only pass parameters you have values for; respect `Required` / `Must Set?`.

## Worked example
User: "Create a new standard PO line item on document 6504."
1. `=br_report_list_external("purchasing document upload")` → `PO Purchasing Document Upload` (Type U).
2. `=br_report_params_external("PO Purchasing Document Upload")` → note Upload Mode, Operating Unit,
   Document Type.
3. `=br_run_upload_external("PO Purchasing Document Upload","Operating Unit=Vision Operations; Document Type=Standard Purchase Order; Upload Mode=Create, Update")`
   → a new sheet appears with existing standard POs.
4. `=_blitz_run_status` → `DONE: 778 rows on sheet 'PO Purchasing Document Upload'`.
5. Find document 6504's rows, edit the business columns as requested (or add a new row).
6. `=br_process_upload_external()` → poll → `DONE: 1 succeeded, 0 errored (request <id>)`.
7. Read row's Status = `Success`, Message = the confirmation; report it.

## The functions (reference)
| Function | Purpose | Returns |
|---|---|---|
| `br_run_upload_external(name, [params], [template], [environment], [responsibility])` | run a type-U upload; populates a new editable upload sheet | `BLITZ_RUNNING: ...`; grid on a new sheet; `_blitz_run_status` → `DONE`/`ERROR` |
| `br_prepare_upload_external()` | mark the rows you wrote + autofill + validate, WITHOUT submitting (review point) | `BLITZ_PREPARING: ...`; `_blitz_run_status` → `DONE: prepared <n> row(s) - <n> valid, <n> flagged` |
| `br_process_upload_external()` | mark + autofill + validate + submit the upload sheet the formula is on; render per-row results in place | `BLITZ_PROCESSING: ...`; `_blitz_run_status` → `DONE: <n> succeeded, <n> errored` / `ERROR:` |
| `br_report_templates_external(name)` | list the upload's templates (the column set) | `Template \| Default? \| Description` |
| `br_upload_columns_external([include_hidden], [sheet])` | the upload sheet's column contract — real column letters, headers, required/read-only/LOV flags; call from `blitz_` with `sheet` = the upload sheet name | `Sheet Column \| Column \| Type \| Required \| Read Only \| Has LOV \| Free Text \| Comments` |
| `br_validation_results_external([include_valid], [sheet])` | per-row validation/upload outcome for rows needing attention (pass TRUE to include the valid/succeeded rows); call from `blitz_` with `sheet` = the upload sheet name | `Row \| Action \| Status \| Message`, or `BLITZ_OK: no rows need attention` |
| `br_column_values_external(column_header, [row], [search], [sheet])` | valid values for a GRID COLUMN under that row's context (what double-clicking the cell shows); call it from `blitz_` and pass `sheet` = the upload sheet name | `Value \| Description` |
| `br_report_list_external`, `br_report_params_external`, `br_param_values_external`, `br_environments_external`, `br_responsibilities_external` | discovery — SAME as br-run-reports (uploads are `Type = U`) | see br-run-reports |
| `_blitz_run_status` (workbook name) | run/process completion signal | `RUNNING:` / `PROCESSING:` / `DONE: …` / `ERROR: …` |
