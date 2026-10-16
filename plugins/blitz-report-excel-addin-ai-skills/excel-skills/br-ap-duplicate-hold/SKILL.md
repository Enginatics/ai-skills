---
name: br-ap-duplicate-hold
description: >
  Stop payment of suspected duplicate AP invoices from Excel: take the unpaid duplicates a
  br-ap-duplicate-payments run identified, place a payment-blocking hold on each suspect copy via the
  "AP Invoice Hold Upload", and record the duplicate evidence in the hold reason — only on the user's
  explicit confirmation. Use when the user asks to block the duplicates, hold the suspect invoices,
  stop the double payment, or action a duplicate-payments analysis. WRITES to Oracle EBS.
# Trigger: Slash command + auto
---

# AP Duplicate Invoice Hold Placement (br-ap-duplicate-hold)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected).

> **Read `br-run-uploads` FIRST** (`read_skill("br-run-uploads")`) — it owns the upload mechanics
> (the `blitz_` helper sheet, sheet layout, column contract, trigger-cell placement,
> `_blitz_run_status` polling, the talk-in-the-user's-language rule). This skill only adds what is
> specific to placing duplicate-suspect holds.

## 🚨 This blocks payment of real invoices — the safety contract
1. **Hold the SUSPECT copy only, never both twins.** A duplicate pair has one legitimate invoice and
   one suspect. Holding both blocks the payment that *should* go out. The suspect is the
   later-entered copy unless the user says otherwise.
2. **Only the PREVENTABLE set qualifies.** br-ap-duplicate-payments splits pairs into *recoverable*
   (both already paid — a hold does nothing; recovery is a supplier credit/refund process, out of
   scope here) and *preventable* (the twin is still unpaid). Propose holds ONLY on unpaid suspects.
3. **Never submit without an explicit, informed confirmation** — count, $, suppliers, shown first.
   "Block the duplicates" at analysis time is not consent to the specific list.
4. **A placed hold is reversible** — release later via **br-ap-hold-release** — but until released it
   delays a payment. Say that in the confirmation.

**This skill places holds only.** It never writes `Release Name` / `Release Reason` — releasing is
br-ap-hold-release's job, and mixing the two actions on one grid is how the wrong thing gets
submitted.

## When to use
"Block the duplicate invoices", "put the suspects on hold", "stop the second payment", "action the
duplicate analysis". For finding duplicates, use **br-ap-duplicate-payments**; for releasing holds,
**br-ap-hold-release**.

## Inputs
- **A `Dup_Candidates` sheet** from a br-ap-duplicate-payments run in this workbook — the normal
  entry. If absent, either run that skill first or accept an explicit user list of
  (Operating Unit, Supplier, Invoice Number) triples. **Never scan for duplicates yourself.**
- **Operating Unit** — from the candidates sheet; ask if mixed and the user wants a subset.
- **Hold Name** — see the lookup rule below; the user picks it, once.

## The upload  (authoritative — do NOT broad-search for it)
**`AP Invoice Hold Upload`** (Type `U`, no templates — omit the template argument). Placement means
**adding NEW rows** to the grid, so download with `Upload Mode=Create` (an empty grid with the column
contract) — you do not need the existing holds:
`=br_run_upload_external("AP Invoice Hold Upload","Operating Unit=<OU>; Upload Mode=Create")`

### The column contract — what a PLACEMENT row carries
Confirm with `=br_upload_columns_external(FALSE, "<Upload Sheet Name>")` and write by the returned
Sheet Column letter. Per new row:

| Column | Write | Notes |
|---|---|---|
| `Operating Unit` | YES | From the candidate pair |
| `Supplier` or `Supplier Number` | YES | Disambiguates the invoice — an invoice number can exist for more than one supplier |
| `Invoice Number` | YES | The SUSPECT copy's number |
| **`Hold Name`** | **YES — this is the action** | LOV, row-context dependent (see below) |
| **`Hold Reason`** | **YES — the evidence** | e.g. `Suspected duplicate of <other invoice> (<match rule>, $<amt>) — Blitz duplicate analysis <date>` — this is what the AP reviewer sees in the Holds tab |
| `Release Name`, `Release Reason` | **NO — never** | That is a release, not a placement |
| Action / Status / Message / everything else | NO | The add-in owns them |

### `Hold Name` is a per-invoice LOV — look it up, never hardcode
The list offers only **manual, user-releasable** hold types not already open on that invoice. Call
`=br_column_values_external("Hold Name", <row>, "", "<Upload Sheet Name>")` for the first filled row,
show the list, and **ask the user which hold their AP process uses for duplicate suspects** — sites
differ (some use a seeded manual hold, some a custom one). Use the same choice for every row; if a
later row rejects it ("already on hold"), that invoice is already blocked — drop it and say so.

## Pipeline

### Step 1 — Build the proposal set  *(single `execute_office_js` call, read-only)*
From `Dup_Candidates`: keep pairs classified **preventable**, take each pair's **unpaid suspect**,
drop any the user excluded, and de-duplicate (one invoice can appear in several pairs — one hold per
invoice). Carry per row: OU, Supplier, Invoice Number, $ amount, the paired invoice, match rule and
confidence.

### Step 2 — Confirm the SET  *(one `ask_user_question`)*
> "Place a payment hold on <n> suspected duplicate invoices worth $<X> across <m> suppliers in
> <OU>? Payment stays blocked until each hold is released. Nothing goes to Oracle until you confirm
> again after validation." → `Yes — fill the grid` / `Let me narrow it` / `Cancel`

Show the list (invoice, supplier, $, paired invoice, rule) before asking. Narrowed → re-ask.

### Step 3 — Download the empty grid + fill  *(then one write call)*
Run the upload (Create mode, above), poll `_blitz_run_status`. Resolve `Hold Name` per the lookup
rule. Then in ONE call paste the confirmed rows — identity columns + Hold Name + Hold Reason, by
Sheet Column letter. Write nothing else.

### Step 4 — Validate
`=br_prepare_upload_external()` in row 1, a few columns right of the sheet's **used range** (hidden
columns extend past the contract — a trigger inside them is left behind as junk). Poll, then read
`=br_validation_results_external(FALSE, "<Upload Sheet Name>")`.

| Message | Meaning | Do |
|---|---|---|
| `Invoice "N" exists for more than one supplier.` | Ambiguous number | Fill Supplier Number for that row |
| Invoice already on that hold | Already blocked | Drop the row; report it as already protected |
| `Invoice "N" is currently being validated by request <id>.` | Validation running | Transient — retry after it finishes |
| Hold name invalid / not user-releasable | Wrong hold type for this invoice | Re-look-up that row's LOV; ask if the list differs |

Fix and re-prepare; **stop after ~3 unproductive rounds** and show the exact messages.

### Step 5 — Confirm again, then submit
Show the validated state (rows that will hold, $, drop-outs) and get a **second explicit
confirmation**. Then `=br_process_upload_external()` (same placement rule), poll for
`DONE: <n> succeeded, <n> errored (request <id>)`. The add-in clears the trigger cell itself.

### Step 6 — Report and cross-link
Read `=br_validation_results_external(TRUE, ...)` and report per invoice: held / failed and why, plus
the request id. A `DONE` with errors is a **partial success — the succeeded holds are live in EBS**;
fix only the failed rows, never re-process the whole sheet. Then:
- Annotate `Dup_Candidates` (one status column, e.g. `Held <date>`) so a re-run of the analysis
  doesn't re-propose them.
- Tell the user the paired legitimate invoices remain payable, and that release later goes through
  **br-ap-hold-release** (where these holds will surface as manual, user-releasable).

## Validation (before declaring done)
- Every held invoice was individually visible to the user at Step 2.
- No row carries a Release Name/Reason; no paid invoice was held; no legitimate twin was held.
- Reported held count = rows whose Status came back Success.
- Upload sheet clean; `blitz_` deleted.

## Re-run / refresh
"Hold more from the same analysis" → extend the same grid with the extra rows and repeat Steps 4–6;
do not re-download. A later br-ap-duplicate-payments run for the same OU should treat held invoices
as already-actioned, not as fresh findings.
