---
name: br-ap-payment-actions
description: >
  Act on a br-ap-payment-optimizer run from Excel: produce the prioritized pay-run list for the
  invoices to pay now (discount capture), and — on explicit confirmation — place payment-blocking
  holds via the "AP Invoice Hold Upload" on the invoices the user chooses to defer. Use when the
  user asks to action the payment optimization, defer the deferrable invoices, block payments we
  want to delay, or prepare the pay run. WRITES to Oracle EBS (defer-holds only).
# Trigger: Slash command + auto
---

# AP Payment Actions (br-ap-payment-actions)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected).

> **Read `br-run-uploads` FIRST** (`read_skill("br-run-uploads")`) for the upload mechanics. This
> skill adds only what is specific to payment actions.

## Honest scope — what each recommendation becomes
A payment-optimizer run produces two action classes, and only one is writable from here:

| Optimizer says | This skill does | Why |
|---|---|---|
| **Pay now** (discount expiring, critical supplier) | **Read-only deliverable**: a prioritized pay-run sheet the AP user takes into Payments (PPR). | There is no shipped upload that executes a payment run — and there should not be; paying money is EBS's own gated flow. |
| **Defer** (no discount, far from due, cash pressure) | **Write**: place a payment-blocking hold per invoice via `AP Invoice Hold Upload`, released later through **br-ap-hold-release** when the user is ready to pay. | A held invoice cannot be selected by a payment run — the standard, reversible way to defer. |

Never present the pay-run sheet as "payments made", and never imply a hold changes terms or due
dates — it only blocks selection until released.

## 🚨 Deferring payments has consequences — the safety contract
1. **Never defer**: an invoice already past due, a supplier flagged critical/under dispute, or
   anything carrying an unexpired discount worth more than the deferral saves. Filter these out
   BEFORE proposing, and say what was filtered.
2. **Show the money and the dates** in the confirmation: count, total $, how far each moves past
   its scheduled date, supplier concentration.
3. **Two confirmations** — one before filling the grid, one after validation before submit.
4. **Every defer-hold must carry its plan in the Hold Reason** — e.g.
   `Deferred to <date> per payment optimization <run date> — release before next pay run` — so an AP
   reviewer in the Holds workbench sees why, and br-ap-hold-release later shows the intent.

## When to use
"Action the payment optimization", "defer what we can", "hold the deferrable invoices", "prep the
pay run". For the analysis itself, use **br-ap-payment-optimizer**; for releasing the defer-holds
when it is time to pay, **br-ap-hold-release**.

## Inputs
- **An `AP_Pay_Run` / deferral recommendation sheet** from a br-ap-payment-optimizer run in this
  workbook — the normal entry. If absent, run the optimizer first; never invent a defer list.
- **Which recommendations to act on** — pay-now list, defer list, or both.
- **Defer horizon** — until when (a date or "next pay run") for the Hold Reason text.
- **Hold Name** — from the LOV, user-picked once (same rule as any hold placement).

## Part A — the pay-run deliverable  *(read-only, always produced)*
One sheet, `Pay_Run_Proposal`: the pay-now invoices ranked by the optimizer's own priority
(discount $ expiring first), with supplier, invoice, gross $, discount $ and date, due date, and a
total row. This is the sheet the user hands to whoever runs Payments. No EBS write.

## Part B — defer-holds  *(the write path)*
**`AP Invoice Hold Upload`** (Type `U`, no templates). Placement = NEW rows on an empty grid:
`=br_run_upload_external("AP Invoice Hold Upload","Operating Unit=<OU>; Upload Mode=Create")`

Per row (by Sheet Column letter from `=br_upload_columns_external(FALSE, ...)`):
`Operating Unit`, `Supplier` or `Supplier Number`, `Invoice Number`, **`Hold Name`** (LOV,
`=br_column_values_external("Hold Name", <row>, "", ...)` — manual user-releasable types only; ask
the user which their site uses for payment deferral), **`Hold Reason`** (the plan text above).
Never write `Release Name`/`Release Reason` or any other column.

### Pipeline for Part B
1. **Proposal set** — from the optimizer's defer list minus the safety filters above; de-duplicate
   per invoice.
2. **Confirm the SET** — list + the money question:
   > "Place defer-holds on <n> invoices worth $<X> across <m> suppliers, blocking them from payment
   > until released (target <date>)?" → `Yes — fill the grid` / `Narrow it` / `Cancel`
3. **Fill** — one write call, confirmed rows only.
4. **Validate** — `=br_prepare_upload_external()` (row 1, right of the used range), poll, read
   `=br_validation_results_external(FALSE, ...)`. Ambiguous invoice → fill Supplier Number; already
   on hold → drop and report as already blocked; invoice under validation → transient, retry.
   Stop after ~3 unproductive rounds.
5. **Confirm again, submit** — `=br_process_upload_external()`, poll for
   `DONE: <n> succeeded, <n> errored (request <id>)`.
6. **Report** — per invoice held/failed + request id; a `DONE` with errors is a **partial success —
   the succeeded holds are live**; fix only failures. Annotate the optimizer sheet
   (`Deferred <date>`), and remind the user: **release before the target pay run via
   br-ap-hold-release**, or the deferral silently becomes a late payment.

## Validation (before declaring done)
- Nothing past due, discounted, or critical was deferred; every held row was user-confirmed.
- Pay-run sheet totals tie to the optimizer's own figures.
- Reported held count = Success rows. Upload sheet clean; `blitz_` deleted.

## Re-run / refresh
A later optimizer run must see the defer-holds as already-actioned (they will appear in its
holds-count columns) — point it at the annotation if it re-proposes them. When the user says "we're
paying now", hand over to **br-ap-hold-release** scoped to the defer-hold's Hold Name + Reason
marker; do not release from here.
