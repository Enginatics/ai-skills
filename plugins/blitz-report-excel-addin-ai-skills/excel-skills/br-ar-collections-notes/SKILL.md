---
name: br-ar-collections-notes
description: >
  Log collection notes into Oracle EBS Advanced Collections from Excel: take the ranked customers
  and drafted dunning messages a br-ar-collections-worklist run produced, stage one note per
  customer via the "IEX Collection Note Upload", and — on the user's explicit confirmation — submit
  them so the collections team sees the worklist as logged activity. Use when the user asks to log
  the collection notes, post the worklist to Collections, record the dunning messages, or action a
  collections worklist. WRITES to Oracle EBS.
# Trigger: Slash command + auto
---

# AR Collections Note Logging (br-ar-collections-notes)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected).

> **Read `br-run-uploads` FIRST** (`read_skill("br-run-uploads")`) — it owns the upload mechanics
> (the `blitz_` helper sheet, sheet layout, column contract, trigger-cell placement,
> `_blitz_run_status` polling, the talk-in-the-user's-language rule). This skill only adds what is
> specific to collection notes.

## What this writes — and what it deliberately does not
A collection note is an **internal activity record** in Advanced Collections — the lowest-risk write
in the AP/AR family, but permanent and visible to every collector on the account. So:
1. **One note per customer per run.** Never one per invoice — that floods the account history and
   buries real activity. The invoice detail belongs INSIDE the one note's text.
2. **The note is a record, not an outbound dunning email.** This skill never contacts a customer.
   Say so if the user seems to expect sending.
3. **Confirm before submitting** — the user must see which customers get which text. Drafted
   messages come from the worklist's dunning tiers; the user may want to soften wording before it
   becomes a permanent record.
4. **Never log against excluded customers** — anyone the worklist excluded (disputes, legal,
   payment plans) stays excluded here.

## When to use
"Log the collection notes", "post the worklist to Collections", "record these follow-ups in EBS",
"action the collections worklist". For building the worklist, use **br-ar-collections-worklist**.

## Inputs
- **A `Worklist` sheet** from a br-ar-collections-worklist run in this workbook — the normal entry
  (it carries the ranked customers, exposure, dunning tier, and drafted message). If absent, run
  that skill first; do not re-derive a worklist here.
- **Scope** — default: the tier the user names ("log notes for the top tier"); otherwise ask which
  tiers/customers.
- **Note Type** — from the LOV (below); the user picks once for the run.

## The upload  (authoritative — do NOT broad-search for it)
**`IEX Collection Note Upload`** (Type `U`). Logging is **adding NEW rows**, so download an empty
grid: `=br_run_upload_external("IEX Collection Note Upload","Operating Unit=<OU>; Upload Mode=Create")`
(omit the template argument unless the instance shows templates).

### The column contract — per new note row
Confirm with `=br_upload_columns_external(FALSE, "<Upload Sheet Name>")` and write by Sheet Column
letter:

| Column | Write | Notes |
|---|---|---|
| `Account Number` (or `Party` / `Party Number`) | YES | The worklist's customer key — prefer Account Number, it is what the worklist carries |
| `Operating Unit` | YES | From the worklist run |
| `Note Level` | YES | LOV — use the **Account** level for worklist notes. Transaction-level (with `Transaction Number` + `Installment`) only when the user asks for per-invoice notes |
| `Note Type` | YES | LOV — look it up once (`br_column_values_external`), ask the user which their collections process uses |
| `Note Status` | Only if the LOV requires it | Look up; otherwise leave blank for the server default |
| **`Note`** | **YES — the drafted message** | The worklist's dunning text for that customer's tier, with the exposure figures resolved |
| `Note Detail` | Optional | Overflow for long text; keep `Note` self-sufficient |
| `Entered Date` | NO | Leave blank — server defaults it |
| Attribute columns | NO | Unless the customer has a documented DFF convention |
| Action / Status / Message | NO | The add-in owns them |

### Drafting rule for the note text
Per customer, resolve the tier's drafted message with real numbers: total past due $, oldest
invoice ref + days, promised/next action. Prefix with a run marker the collectors can recognise,
e.g. `[Blitz worklist <date>]` — it is also how a later run detects already-logged customers. Keep
each note under ~2000 characters; move overflow to `Note Detail`.

## Pipeline

### Step 1 — Build the proposal  *(single read call)*
From `Worklist`: filter to scope, drop exclusions, resolve each customer's drafted text, and check
for the run marker from a previous logging run — a customer already logged this cycle is skipped
(re-logging is noise, not diligence).

### Step 2 — Confirm  *(one `ask_user_question`)*
Show customer, tier, exposure $, and the exact note text (or a sample plus "same pattern for the
rest" when >10). Then:
> "Log <n> collection notes in <OU> — one per customer, <tier breakdown>? These become permanent
> account activity visible to the collections team." → `Yes` / `Edit the wording first` / `Cancel`

If they edit, apply the edit to the affected tier's text and re-show.

### Step 3 — Fill the grid  *(one write call)*
Look up `Note Level` / `Note Type` (and `Note Status` if required) from the LOVs first — ask, never
guess. Then paste all confirmed rows in ONE call, by Sheet Column letter.

### Step 4 — Validate
`=br_prepare_upload_external()` in row 1, a few columns right of the sheet's **used range**. Poll,
then `=br_validation_results_external(FALSE, ...)`. Typical refusals: an account number not found
(worklist customer merged/renamed — drop and report), a required LOV column blank (fill from its
LOV), an OU mismatch. Fix and re-prepare; stop after ~3 unproductive rounds.

### Step 5 — Confirm again, then submit
Second explicit confirmation on the validated set, then `=br_process_upload_external()`; poll for
`DONE: <n> succeeded, <n> errored (request <id>)`. The add-in clears the trigger cell itself.

### Step 6 — Report and cross-link
Read `=br_validation_results_external(TRUE, ...)`; report logged / failed per customer + request id.
A `DONE` with errors is a **partial success — the succeeded notes are live**; fix only the failures.
Annotate `Worklist` with a `Logged <date>` column so the next worklist run shows follow-up state.

## Validation (before declaring done)
- One note per customer; every one individually visible (or pattern-approved) at Step 2.
- No excluded customer logged; no transaction-level rows unless the user asked.
- Reported count = Success rows. Upload sheet clean; `blitz_` deleted.

## Re-run / refresh
"Log the next tier too" → same grid, append rows, repeat Steps 4–6 (untouched rows already
submitted are inert only if the sheet was not reprocessed — prefer a fresh Create-mode grid for a
second batch). A fresh worklist run supersedes the old sheet; carry the `Logged` markers across by
account number.
