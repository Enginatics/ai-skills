---
name: br-ap-close-readiness
description: >
  Assess Oracle EBS Accounts Payable period-close readiness in Excel: have the
  br-run-reports skill extract "AP Period Close Exceptions", summarise the
  blockers by exception type, give a red/amber/green readiness verdict with the remediation
  for each blocker, and build an AP close-readiness scorecard. Use when the user asks "can
  we close AP for {period}", "AP period close readiness", "what's blocking the AP close",
  unaccounted invoices/payments, or untransferred AP accounting.
# Trigger: Slash command + auto
---

# AP Period Close Readiness (br-ap-close-readiness)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Produce an AP period-close readiness scorecard in one Excel workbook. You own the
orchestration, the readiness scoring, and the written verdict; the specialist skills do the
extraction and the dashboard build. Run steps **in order**, on separate turns, keeping every
intermediate sheet so the user can audit.

**Requires:** br-run-reports (extraction). **Optional:** br-data-dashboard (dashboard
build — if it doesn't fire, build the dashboard inline per Step 6); br-ap-holds-analysis (hold exposure).

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** All extraction is performed by the
**br-run-reports** skill, which owns add-in connection, authentication,
asynchronous execution, completion polling, and deterministic cell population.
- Never call `br_*` add-in functions directly.
- Never rename the result sheet, read its values, sum a column, or start any analysis
  **until extraction is confirmed complete** — touching the workbook while the add-in's run
  is still in flight can stall it and the run will never finish.
- Your job is only: (1) ask br-run-reports to fetch the data, then (2) once it
  has fully landed, score and present it.

**This skill is read-and-recommend only.** It does NOT execute any fix (no Create Accounting,
no Transfer to GL, no hold release). It reports what is blocking and the recommended action;
performing the action is a separate, human-approved step (closed-loop is on the roadmap).

## When to use
The user wants to know whether AP can be closed, or what is blocking it: "are we ready to
close AP for May", "AP period close readiness", "what's stopping the AP close", unaccounted
invoices/payments, untransferred AP accounting, unconfirmed payment batches.

## Inputs
- **Operating Unit** *or* **Ledger** (required) — ask if not supplied.
- **Period Name** (required, e.g. `May-26`) — or a From/To accounting-date range.
- *Optional:* Supplier filter; "also reconcile AP to GL"; "also show hold exposure".

## Reports used  (authoritative names — do NOT broad-search for them)
These exact report names are known. When you ask br-run-reports to run one, pass the
**documented name directly** — do NOT run a `br_report_list_external` discovery search first. Inspect
parameters only if you need an exact LOV spelling. **Fallback:** only if a run returns
`#BLITZ_REPORT_NOT_FOUND` (the instance renamed it, or the module isn't installed) do a name search.

| Report (exact name) | Run with | Notes / module dependency |
|---|---|---|
| `AP Period Close Exceptions` | Operating Unit (or Ledger) + Period Name; the From/To accounting dates **derive** from the period — don't set them | **The verdict driver.** Payables (always present) |
| `CAC Accounting Period Status` | **Functional Area = Payables** (the param is `Functional Area`, NOT `Application`) + Ledger/OU + Period | Period-status check (Step 1c). **Costing/CAC** — may be absent → note it and skip |
| `AP Invoice on Hold` *(optional)* | Operating Unit; then filter **in-sheet** to Accounting Allowed = No + invoice date ≤ period end | No accounting-allowed parameter, so filter post-run |
| `AP Trial Balance` *(optional)* | Ledger + Period | AP↔GL tie-out (Step 4) |

---

## CONFIG  — edit to match the customer; logic below reads from here

### Exception types → class + remediation
Each row's `exception_type` from the report maps to a blocker class and a recommended action:
| exception_type | Class | Recommended remediation |
|---|---|---|
| Unaccounted Invoice Distributions | **Blocker** | Run **Create Accounting** (Payables) in Final mode |
| Unaccounted Payments | **Blocker** | Run **Create Accounting** (Payables) in Final mode |
| Untransferred XLA Events | **Blocker** | Run **Create Accounting** with Transfer to GL = Yes (or Transfer Journal Entries to GL) |
| Unprocessed Events | **Blocker** | Run **Create Accounting** (events not yet accounted) |
| Invoices Without Distributions | **Blocker (manual)** | Open the invoice and generate/validate distributions — cannot be auto-run |
| Unconfirmed Payment Batches | **Blocker** | Confirm or cancel the Payment Process Request |
| Future Dated Payments | **Review** | Expected for maturity-dated payments; confirm none should be matured before close |

Anything not listed → treat as **Blocker** and recommend "investigate".

### Readiness (RAG) rule
- **Green** — no rows, or only `Review`-class rows.
- **Amber** — only `Review`-class rows remain **and** the user flagged them as expected; or AP↔GL
  tie-out (if run) is within the materiality threshold but non-zero.
- **Red** — any `Blocker`-class row with a non-zero count.

### Sheets  (don't fight what br-run-reports creates)
- Leave each extracted report on the sheet br-run-reports created it on (its **report
  name**, e.g. `AP Period Close Exceptions`, `AP Invoice on Hold`) — do NOT rename it; the dashboard
  links to it by that name. Renaming risks breaking links and wastes a turn.
- Build the dashboard on a NEW sheet named **`AP Close Readiness`**, inserted at **position 0** so it
  is the first tab (this satisfies "dashboard first" with no separate reorder pass).

---

## Pipeline

### Step 1 — Extract  (DELEGATE to br-run-reports — do not run it yourself)
Ask **br-run-reports** to run **"AP Period Close Exceptions"** with Operating Unit
(or Ledger) = {input} and Period Name = {input}. Let that skill drive the run to completion and
fully populate the cells. While it runs, do **nothing** — no add-in calls, no sheet renames, no
reads.
- If `#BLITZ_NOT_CONNECTED`, relay it, ask the user to connect via the Blitz Report ribbon, retry.
- **Fallback:** if the hand-off does not fire or the data never lands, tell the user to run "AP
  Period Close Exceptions" themselves and then ask you to assess it; resume from Step 1b.

### Step 1b — Anchor  (ONLY after extraction is confirmed complete)
The data is on the sheet br-run-reports created (named after the report, e.g.
`AP Period Close Exceptions`) — **do not rename it**; refer to it by that name. Record the row
**count** and the **SUM of `invoice_amount`** — both are reconciliation anchors. **If zero rows:**
AP has no exceptions for the period — skip to the scorecard (Steps 6–7) and produce a **Green**
verdict stating "no AP close exceptions for {period}".

### Step 1c — Confirm the period is open  (recommended)
Delegate to br-run-reports to run **"CAC Accounting Period Status"** (**Functional Area
= Payables** — the param is `Functional Area`, not `Application` — for the Ledger/OU + Period). Confirm the AP period is **Open** — a "ready to close" verdict
is meaningless if it's already Closed or still Future. Show the current status on the scorecard. If
the report isn't found on the instance, note that and proceed (don't block on it).

### Step 2 — Summarise by exception type  *(single `execute_office_js` call)*
In one call: read the `exception_type` and `invoice_amount` columns, compute the **count** and
**SUM(invoice_amount)** by `exception_type`, add a `Class` and `Remediation` per the CONFIG map,
and write the summary pivot — all in one JS block. Trust the JS return value for the per-type
totals; confirm the total equals the Step-1b anchor.

### Step 3 — Readiness verdict  (you)
Apply the CONFIG RAG rule. List the blocking items ranked by amount, each with its recommended
remediation, and whether it is auto-runnable (Create Accounting / Transfer to GL / confirm batch)
or **manual** (Invoices Without Distributions).

### Step 4 — AP↔GL tie-out  *(optional — only if the user asks)*
Delegate to br-run-reports to run **"AP Trial Balance"** for the period; compare the
AP ending balance to the GL liability balance and note the variance on `AP_TB_Recon`.

### Step 5 — Hold exposure  *(optional — secondary context, NEVER the verdict driver)*
**Holds do NOT block the period close** — only the Step 2 exception types do. If you show holds, keep
them a **compact context panel**, not a headline, and restrict to the **close-relevant subset**:
`Accounting Allowed = No` (these block accounting) **AND** invoice date ≤ the period end. This avoids
the misleading large "Qty Ord"/payment-matching total — those have `Accounting Allowed = Yes` and
block only *payment*, not accounting (on the test run this produced a ~$2.1B headline that had to be
caveated). Run **"AP Invoice on Hold"** via br-run-reports (or invoke **br-ap-holds-analysis**),
aggregate by hold name, and show count + amount-remaining for the accounting-blocking, period-relevant rows only.

### Step 6 — Scorecard  *(single `execute_office_js` call)*  (delegate to br-data-dashboard if it fires; else build inline)
Write all scorecard sections to the **`AP Close Readiness`** sheet (new, at position 0) in one call:
a big **RAG status banner** (period + OU + current period status); a table of exception types with
count, $ amount, class, and remediation; the ranked blocking-items list (linked live to the report
sheet); and, if Steps 4–5 ran, the AP↔GL variance and the close-relevant holds panel. **Every KPI
must be a formula referencing the report sheet** (COUNTIFS/SUMIFS) so the dashboard refreshes when
the report is re-run. Any charts follow in a second call.
- **Build-mechanics caveats (learned on a real run):**
  - **Do NOT use a multi-row `copyToRange` to fill formula rows** — it can latch onto the wrong
    source bounding box and duplicate header rows into the data, leaving stray cells (this misfired
    twice on the test run). Write each row's formula explicitly, or copy a single one-row source and
    verify the result.
  - Leave the report sheet(s) untouched; build only on the new dashboard sheet.
  - After building, scan **beyond** the dashboard's column range and clear any stray cells, and widen
    amount columns so values don't render as `######`.

### Step 7 — Verdict narrative  (you)
Write a ≤5-bullet summary on the `AP Close Readiness` sheet: the overall RAG call (plus the current
period status from Step 1c), the single biggest blocker ($ and type), total unaccounted $, the
recommended next action (which concurrent program to run, or which rows need manual fixing), and
anything that legitimately may remain (review-class). If you couldn't confirm period status, say so.

### Step 8 — Finalise + final validation  (final)
The dashboard is already first (built at position 0). Make **`AP Close Readiness`** the active sheet
so the workbook opens on it. Don't reorder or disturb the report sheet(s).

**Then do the one permitted verification read:** confirm the scorecard's total exception count and
SUM(invoice_amount) equal the Step-1b anchors. This is the only explicit re-read allowed in the
entire pipeline outside of Step 1b.

---

## Validation (before declaring done)
- **Reconcile:** the scorecard's total exception count = the Step-1b row count, and the per-type
  counts/amounts sum to the totals. (Holds, if shown, reconcile separately: blocking + non-blocking = total.)
- **Verdict sanity:** Red only if a Blocker-class row exists; Green only if no Blocker rows.
- **No stray cells and no `######`** outside the intended dashboard range.

## Re-run / refresh
On "check the next period" / "rebuild", re-drive from Step 1 (delegating the extract again),
overwriting the sheets.

## Closed-loop (roadmap, not executed here)
Hold release is deliverable via a Blitz Upload; running Create Accounting / Transfer to GL is a
concurrent-program submit (a future capability). For now this skill recommends; a human runs it.
