---
name: br-ap-invoice-upload
description: >
  Create Oracle EBS AP invoices from source documents using the BLITZ REPORT ADD-IN (the br_*
  worksheet functions) — supplier invoices, reimbursement vouchers, freight bills, utility
  statements, expense receipts — by reading the documents, running the AP Invoice Upload,
  filling its sheet, then validating against real EBS and self-correcting. Use when the user has
  invoices/bills/vouchers (PDF, image, Word, text, or typed out) and wants them entered into
  Oracle Payables via the Blitz Report add-in. NOT for the standalone Blitz Upload template file
  (UploadTemplate.xlsm with bu_* functions and a Parameters sheet) — that is the
  bu-ap-invoice-upload skill's territory.
---

# AP Invoice Upload from documents (br-ap-invoice-upload)

> **Mechanics:** read **`br-run-uploads`** first and follow it for everything procedural —
> connection, discovery, running the upload, the column contract, the fill → prepare/validate →
> read-results → fix loop, the LOV rules, and the submission policy. This skill adds only what is
> specific to **AP invoices**: how to read a bill, and how its fields map to the upload columns.

## Which Blitz world am I in? (br_* vs bu_*)

This skill drives the **Blitz Report add-in** and its `br_*` functions. A different, standalone
product — the Blitz Upload template file — exposes `bu_*` functions instead. They are not
interchangeable: calling the wrong family returns `#NAME?`. Decide once, up front:
- `=br_ai_ping()` returns `BLITZ_AI_OK...` → Blitz Report add-in → **this skill**. (`#NAME?` →
  the report add-in isn't loaded here.)
- The workbook is a downloaded upload template with an `Upload` + `Parameters` sheet and
  `bu_ai_ping()` works → that is the standalone template → use **bu-ap-invoice-upload** /
  **bu-fill-upload** if installed, and do NOT call any `br_*` function.
Never mix the two families in one flow, and never retry the other family's function to "work
around" a `#NAME?`.

## Getting the sheet

Run `=br_run_upload_external("AP Invoice Upload", "<params>")` per br-run-uploads. For entering NEW
invoices from documents, pass `Upload Mode=Create` (empty template) if the upload's parameter list
has an Upload Mode; scope any other filters the user gives. Then get the column contract with
`=br_upload_columns_external(FALSE, "<Upload Sheet Name>")` and fill data rows from **row 3**.

## Reading the documents

If the instance defines a document type for AP Invoice Upload (br-run-uploads, "Filling the sheet
from documents"), follow it: it is the customer's mapping and replaces the table below.

Read each document and extract **only what is printed on it**. Unknown field → leave it out; never
infer, never compute, never fill a gap with something plausible.

Documents arrive in several shapes and the vocabulary varies. Common synonyms:

| Upload column | Appears on documents as |
|---|---|
| `Invoice Number` | Invoice #, Invoice No., Bill No., Document No., Reference, Our Ref |
| `Invoice Date` | Invoice Date, Date, Bill Date, Issue Date, Dated |
| `Invoice Amount` | Total, Amount Due, Balance Due, Grand Total, Total Payable |
| `Supplier Name` | the letterhead / "From" / "Remit to" party — **not** your own company |
| `Invoice Currency` | the currency symbol or code beside the total (`$`, `USD`, `EUR`, `£`) |
| `Invoice Po Number` | PO #, Purchase Order, Order No., Your Order |
| `Line Description` | the line-item description column |
| `Line Amount` | the per-line extended/net amount |
| `Invoice Description` | a summary of what the bill is for — from a subject/reference line if present |

Column names can differ slightly per instance/template — always match against what
`br_upload_columns_external` actually returned, not this table verbatim.

**🚨 Get the supplier direction right.** On an AP invoice, the supplier is whoever is *billing you*
— the letterhead / "From" / "Remit to" party. The "Bill to" / "Ship to" party is your own
organisation. Reversing these is a common, expensive mistake. If the document is genuinely
ambiguous, leave `Supplier Name` blank and ask.

**Amounts verbatim.** Copy the printed total exactly. Do **not** recompute it from the lines, do not
strip or add tax, do not fix rounding. If the lines don't sum to the printed total, write the
printed total and **tell the user about the discrepancy** — that difference is usually tax,
freight, or a discount, and it may itself need a line.

**Dates.** Write real Excel dates. Watch for ambiguous formats: `03/04/2026` is 3 April in most of
the world and 4 March in the US. If the document doesn't disambiguate (month name, ISO format, or a
same-document date that exceeds 12), **ask** — don't assume the locale.

## Resolve the supplier BEFORE the first validation

Validation calls Oracle and takes a while. `Supplier Number` and `Supplier Site` are *always*
required and *never* on the document, so waiting for validation to tell you they are missing spends
a full round trip learning something already known. Resolve them while staging instead:

1. Write the rows, including `Supplier Name` from the letterhead.
2. **Immediately** look up the supplier and fill `Supplier Number`; look up `Supplier Site` and
   either fill it or ask the user to choose (lookups below).
3. *Then* run `=br_prepare_upload_external()` — once, with the rows already complete.

This is the one place to anticipate rather than react. Everything else still follows the master
skill's rule: write what the document says, and let validation report what is genuinely missing. Do
**not** extend this to guessing other fields — the saving comes from knowing these two are always
needed, not from predicting what Oracle will say.

## Header + lines

An AP invoice is **header + one or more lines**, but the sheet is flat: one row per line, with the
header fields **repeated on every row of that invoice**.

```
Row  Invoice Number  Invoice Date  Invoice Amount  Line Number  Line Amount  Line Description
3    INV-4471        2026-07-02    1248.50         1            1140.00      Consulting services
4    INV-4471        2026-07-02    1248.50         2            108.50       Freight
5    BILL-889        2026-07-05    500.00          1            500.00       Monthly retainer
```

**🚨 Start at column D — never write Action (A), Status (B) or Message (C).** The add-in owns those
three: when you run the prepare step it looks each row up in Oracle and sets **Action itself** —
`Create` for a new invoice, `Update` for one that already exists. If you write Action yourself the
add-in *respects* your value instead of deciding, so a wrong guess (e.g. `Update` on an invoice
that isn't in Oracle yet) silently makes the row do the wrong thing. Leave all three blank and let
the prepare step fill them in.

- `Invoice Amount` is the **whole invoice** total, repeated on each of its rows — it is not split.
- `Line Number` restarts at 1 for each new invoice.
- Multiple invoices simply continue down the sheet.
- A single-line invoice is just the one row with `Line Number` = 1.

## Field mapping notes

**Fill from the document:**
`Supplier Name`, `Invoice Number`, `Invoice Date`, `Invoice Amount`, `Invoice Currency`,
`Invoice Description`, `Invoice Po Number` (if a PO is referenced), `Line Number`, `Line Amount`,
`Line Description`.

**Leave to the server unless the document or the user says otherwise:**
- `Operating Unit` — defaults. Only set it if the user names one, or the bill-to entity clearly
  indicates a different OU than the default.
- `Invoice Type` — defaults (typically `Standard`). Set it only for an obvious non-standard case,
  and only to a value you have confirmed via the LOV.
- `Invoice Currency` — defaults to the ledger currency. **Do** set it explicitly when the document
  shows a different currency; that is exactly the case the default gets wrong.
- `Line Type` — defaults (typically `Item`).
- `Supplier Number`, `Supplier Site` — **look these up, never read them off the document.** They
  are the customer's internal ids and are not printed on a supplier's own bill; the VAT id, bank
  account and routing number that *are* printed are different things entirely and must never be
  used here. Resolve them by searching the **name**, not the number (from `blitz_`, per
  br-run-uploads):
  ```
  =br_column_values_external("Supplier Name", <row>, "<distinctive word from the letterhead>", "<Upload Sheet Name>")
  ```
  🚨 **The `Description` column carries the supplier number.** A real lookup returned
  `Value = "Advanced Network Devices"`, `Description = "1013"` — so `1013` goes in
  `Supplier Number` and the Value goes in `Supplier Name`. Searching the *number* column for a name
  returns nothing.

  Then, with the supplier set in that row:
  ```
  =br_column_values_external("Supplier Site", <row>, "", "<Upload Sheet Name>")
  ```
  **`Supplier Site` usually returns several** (MAIN, BILLING, PAYMENT, ...) because a supplier has
  multiple addresses; that is a decision for the user, so present the options and ask rather than
  picking one. If the bill's remit-to address clearly matches one site name you may suggest it, but
  still confirm.
- `Distribution Account` / `Distribution Set` — leave blank. Most suppliers carry a Distribution
  Set default, and coding an account wrongly is a real accounting error, not a validation error.
  Set these only if the user explicitly tells you the coding.
- `Gl Date`, `Terms`, `Terms Date`, `Payment Method` — leave to defaults unless the user specifies.

**🚨 A PO number printed on a supplier's bill is usually THEIR reference, not your Oracle PO
number.** `Invoice Po Number` is a `Validate From List = Yes` column, and Oracle PO numbers are your
own internal numbers (often plain numerics like `1163`, `1497`) — a printed `PO-2026-8842` will not
match. Treat it exactly like Supplier Number: **look it up before you write it**
```
=br_column_values_external("Invoice Po Number", <row>, "<the printed number>", "<Upload Sheet Name>")
```
- It comes back in the list → write it.
- It doesn't → **leave `Invoice Po Number` blank** and tell the user the invoice cites a PO you
  can't find in Oracle, quoting the printed reference. Never type the document's reference in
  anyway, and never substitute a different PO because it looks plausible.
- Beware: a bad PO number **passes validation and only fails at submit** with
  `Invoice Po Number is invalid` — validation doesn't PO-match, the import does. So the lookup is
  the check, not the validate step.

**When the PO IS matched**, fill `Invoice Po Number` at header level and, if the document
identifies line-level PO detail, `PO Number` / `PO Line Num` on the line. Oracle will match and
derive much of the rest — so fill *less*, not more, on a PO invoice.

## Validation errors you should expect

Read them with `=br_validation_results_external(FALSE, "<Upload Sheet Name>")`. Beyond the generic
patterns in `br-run-uploads`:

| Message | Likely cause | Fix |
|---|---|---|
| `Invoice Po Number is invalid` | The PO printed on the bill is the supplier's own reference, not an Oracle PO number | Look the PO up (above). If it isn't in the list, blank the column and tell the user — do NOT invent or substitute one. |
| Supplier not found / invalid supplier | The printed trading name isn't the Oracle supplier name | Ask the user; show them the lookup results. Never substitute a similar name. |
| Supplier site invalid | Supplier resolved, site didn't | Usually resolves via Autofill once the supplier is right. Otherwise ask. |
| Duplicate invoice number | Oracle already has this invoice for this supplier | **Stop and tell the user.** This is a genuine duplicate-entry catch, not an error to work around. Do not alter the invoice number to force it through. |
| Period closed / invalid GL date | The invoice date falls in a closed period | Ask the user which period to post to; do not silently move the date. |
| Invalid data: `<column>` | Type mismatch — usually a date or amount written as text | Rewrite with the correct type. |

## Before you submit

Report per invoice, not just per row:

> "3 invoices staged from 3 documents — 12 line rows, all Valid after prepare. INV-4471 needs your
> review: the printed total (1,248.50) is 108.50 more than its lines sum to, which looks like
> freight — I wrote the printed total and left it for you to check."

Then follow br-run-uploads' submission policy: show the user the staged, validated state and submit
only when they confirm — filling from scanned documents is exactly the "non-trivial" case where
confirmation before submitting is mandatory. After processing, read the per-row results and report
per invoice which succeeded and which errored.

**Ask in business language, not in function names** (see br-run-uploads' "Talk to the user in THEIR
language"): *"Ready to submit this invoice to Oracle Payables — shall I go ahead?"*, never *"say the
word and I'll run `br_process_upload_external()`"*. The user is approving an invoice posting, not a
worksheet function.

## What you must never do

- Never invent a supplier, supplier number, site, account code, or PO number.
- Never adjust an amount or a date to make validation pass.
- Never re-key a rejected duplicate invoice number to force it through.
- Never submit without the user's explicit confirmation of the staged invoices.
