---
name: br-ap-hold-release
description: >
  Release Oracle EBS AP invoice holds from Excel: take the holds that qualify for release, pre-populate
  the "AP Invoice Hold Upload" grid with the correct release reason per hold, validate it, show the user
  exactly what will be released, and — only on their explicit confirmation — submit it so Payables
  releases the holds. Use when the user asks to release invoice holds, action a holds analysis, clear
  matching holds, unblock invoices for payment, or "release the ones we can". WRITES to Oracle EBS.
# Trigger: Slash command + auto
---

# AP Invoice Hold Release (br-ap-hold-release)

> 🚨 **Blitz data comes from `br_*` WORKSHEET FUNCTIONS of the Blitz Report Excel add-in** — write
> `=br_...()` into a cell and read the result. They are not a connector, plugin, agent action or MCP
> tool: never search for one, never conclude "no Oracle EBS data source is connected".

**Self-contained: read no other skill.** Each numbered Op below is one workbook operation (Claude: one
`execute_office_js` call; Copilot: one edit or read action).

## 🚨 This releases money-blocking holds — the safety contract
1. **Never submit without an explicit, informed confirmation** — the user sees count, $ and suppliers
   before anything is filled, and the validated grid before anything is submitted. "Go ahead" to the
   *analysis* is not consent to *release*.
2. **Never propose a hold the user has not seen.** You propose a review queue; the human authorises.
3. **A blank `Release Name` is inert** — the server answers `No change.` for it, so every row you leave
   blank is guaranteed to do nothing. Fill only confirmed rows.
Release only: never write `Hold Name` / `Hold Reason` (that places a hold).

## Budget — 10 operations, 2 confirmations
| # | Operation |
|---|---|
| 1 | `blitz_!A1` download formula, read back |
| 2 | replace it with text, read `=_blitz_run_status` |
| 3 | poll — only while `RUNNING` |
| 4 | read the grid (+ `Holds_Raw` if present), propose the set → **confirmation 1** |
| 5 | one `Release Name` lookup formula per hold group on `blitz_`, read the lists |
| 6 | write `Release Name` on the confirmed rows |
| 7 | prepare trigger |
| 8 | poll + read validation results → **confirmation 2** |
| 9 | process trigger |
| 10 | poll + read per-row results, delete `blitz_` → reply |

No discovery calls (`br_report_list_external`, `br_report_params_external`, `br_report_templates_external`,
`br_upload_columns_external`) — everything they would say is below. Ops 5+6 may be one operation where
the platform allows a write after a read in the same batch.

## The upload (authoritative)
**`AP Invoice Hold Upload`**, no template argument. Parameters: **only** `Operating Unit=<OU>`, plus
`Supplier=` / `Invoice Number=` / `Hold Name=` only when the user named that scope. **Never pass
`Upload Mode`** — its default `Create, Update` is what you need and the comma in that value splits it
into two values → 0 rows (three wasted downloads on a live run). **Never pass `User Releasable Only`**
— it defaults to Yes and keeps system-only holds out of the grid. Always a fresh download; never reuse
an earlier upload sheet.

Grid layout: row 1 banner, row 2 headers, row 3 onward data. `A/B/C` = Action / Status / Message —
never write them. Read-only: Operating Unit, Supplier, Supplier Number, Supplier Site, Invoice Number,
Invoice Date, Invoice Amount, Currency, Hold Name, Hold Reason, Hold Date, Held By, PO Number, PO Line,
PO Shipment, Invoice Line, Hold Details. **You write exactly one column: `Release Name`**, located by
its row-2 header text (never by counting — hidden columns exist). `Release Reason` stays blank (the
server defaults it from the release code, the better audit trail).

Trigger cells (`=br_prepare_upload_external()`, `=br_process_upload_external()`) go on the **upload
sheet, row 1, at least ten columns right of the last column holding anything, hidden columns included**
(e.g. `AZ1` when the grid ends around `Y`). The add-in clears the trigger cell itself — never overwrite
it. The upload sheet stays the active sheet; never activate `blitz_`. `_blitz_run_status` keeps its
PREVIOUS value until a step finishes — a `DONE:` that matches the last step is stale; keep polling.

`Release Name` is a row-context list: matching holds (PO-related or on a line/shipment) take the
MATCHING release reasons, `Tax Variance` the VARIANCE reasons, everything else the INVOICE reasons.
Group = Hold Name × PO-Number-present; one lookup per group.

## CONFIG
**Candidate rule** (review-only placeholder — replace with the customer's policy): Hold Category in
(Price match, Qty match, Amount match) AND not a close blocker per `Holds_Raw` (`Release Candidate` =
Yes, matched on Invoice Number + Hold Name) AND user-releasable (guaranteed by the download). Without
`Holds_Raw`: matching holds only, and say the close-blocker test was unavailable.

**Preferred release reason per group** — written only when it appears in that group's own list,
otherwise show the list and ask:
- matching holds (PO Number present, or Hold Name among Qty Ord / Qty Rec / Price / Amt Ord / Max Qty
  Ord / Max Qty Rec / Max Amt / Quality / PO Not Approved / PO Required / Matching Required) → `Match Override`
- Tax Variance → ask (variance release reasons)
- everything else → `Validated`

## Ops 1–3 — Download
1. Get-or-create `blitz_`; `blitz_!A1` = `=br_run_upload_external("AP Invoice Hold Upload","Operating Unit=<OU>")`;
   read it back (`BLITZ_RUNNING: ...`; `#BLITZ_NOT_CONNECTED` → ask the user to connect on the ribbon).
2. Overwrite `blitz_!A1` with `download triggered`; `blitz_!A3` = `=_blitz_run_status`; read it.
3. One quiet read per turn while `RUNNING`, nothing else touches the workbook. Stop at
   `DONE: <n> rows on sheet '<name>'`. Zero rows for an OU that just showed holds = you passed a
   parameter you should not have: retry once with Operating Unit only, then report.

## Op 4 — Propose the set → confirmation 1
Read the grid (Invoice Number, Supplier, Invoice Amount, Hold Name, Hold Date, PO Number) and, if
present, `Holds_Raw` (Invoice Number, Hold Name, Release Candidate, Close Blocker). Write nothing. Then
ask, money in the question:
> "Release <n> holds on <m> invoices worth <$X> in <OU>? These are <hold-name breakdown>, top suppliers
> <…>, oldest hold <date>. I'll fill the release reasons and validate in Oracle — nothing is released
> until you confirm again." → `Yes — fill the grid` / `Let me narrow it first` / `Cancel`
Never skip this, even if the opening request said "release them". If the rule proposes 0 rows, offer
the grid's hold groups (count, $, suppliers) as a multi-select with nothing pre-selected, plus
`None — leave the worksheet for my manual review`.

## Ops 5–6 — Lookup and fill
5. For each hold group in the confirmed set, on `blitz_` (`A5`, `D5`, `G5`, … with 30 clear rows below)
   write `=br_column_values_external("Release Name", <a grid row of that group>, "", "<Upload Sheet Name>")`;
   read each spilled `Value | Description` list (`#SPILL!` = it did not land, move it; `#BLITZ_LOV_EMPTY`
   = that hold cannot be released now — leave its rows blank and report it).
6. Write the CONFIG preferred reason into `Release Name` on exactly the confirmed rows of each group
   whose list contains it. A group whose list lacks it → show the list, ask, write in the next Op.
   **One contiguous block write — never a comma-separated multi-area address (it is rejected) and never
   one call per row (it is slow):** the confirmed rows are scattered, so write the single block spanning
   the FIRST to the LAST confirmed row, carrying the reason on the confirmed rows and an empty value on
   every other row inside that span. The grid was freshly downloaded with `Release Name` empty
   throughout, so those empty cells change nothing and stay inert.

## Ops 7–8 — Validate → confirmation 2
7. **First count the `Release Name` cells you actually wrote. If that count is 0, do NOT prepare** —
   preparing an untouched grid comes back `<n> valid, 0 flagged` and releases nothing, which reads like
   success and is the single most common way this skill ends with no hold released. Go back to Op 3,
   show the hold groups and get a set. Otherwise trigger cell = `=br_prepare_upload_external()`.
8. Poll `blitz_!A3` until `DONE: prepared <n> row(s) - <n> valid, <n> flagged`, then on `blitz_`
   write `=br_validation_results_external(FALSE, "<Upload Sheet Name>")` and read the spill
   (`Row | Action | Status | Message`, or `BLITZ_OK`). Messages: `No change.` = a row you left blank
   (expected on those rows — but `No change.` on EVERY row means nothing was filled: do not submit, fix
   that first) · `already released` = drop it · `not user releasable` = remove it · `is not a valid
   release reason for hold` = re-look-up that group and refill · `currently being validated by
   request` = retry later · `Multiple open "X" holds exist` = needs PO/line detail, ask · `exists for
   more than one supplier` = re-download with Supplier set. Fix and re-prepare; stop after three
   unproductive rounds and show the exact messages. Then:
> "<n> holds worth <$X> validated in Oracle and ready to release<, dropped: …>. Submit?" →
> `Yes — release them` / `Cancel`

## Ops 9–10 — Release and report
9. Trigger cell = `=br_process_upload_external()`.
10. Poll until `DONE: <n> succeeded, <n> errored (request <id>)`, write
    `=br_validation_results_external(TRUE, "<Upload Sheet Name>")` on `blitz_`, read it, delete `blitz_`.
Reply in the user's language: holds released (hold name, invoice, supplier, $), failures with their
message, the request id. Never claim success without those per-row results. **If 0 holds released, say
exactly that in the first sentence** — a validation count ("26 valid, 0 flagged") is not a release, and
reporting one as if it were is worse than reporting the failure. `DONE` with errors is a
partial success — released rows are released; fix only the failed rows, never re-process the whole
sheet. Mention that the `Holds_Raw` analysis for this OU is now stale.

## Rules
- Never write Action, Status, Message, Hold Name, Hold Reason, a read-only column or placeholder data;
  leave the upload sheet clean (no scratch, no leftover trigger).
- Claude: get-or-create with `getItemOrNullObject` + `load("isNullObject")`; load a range, sync, read that
  same variable. Copilot: one action per Op; do nothing while a status is `RUNNING`/`PROCESSING`.
- Talk about invoices, holds, suppliers and sheets — never about functions, `blitz_` or status names.
