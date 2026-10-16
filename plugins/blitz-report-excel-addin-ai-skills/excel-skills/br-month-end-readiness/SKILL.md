---
name: br-month-end-readiness
description: >
  Orchestrate a full Oracle EBS month-end close readiness assessment in Excel: run the per-module
  readiness checks (AP, AR, Inventory/Costing, FA, GL), the close-process monitor, and the
  subledger-to-GL reconciliation, then assemble one master scorecard with a per-module
  red/amber/green status, the ranked blockers, and the recommended close sequence. Use when the
  user asks "are we ready to close {period}", "month-end readiness", or a full close status.
# Trigger: Slash command + auto
---

# Month-End Close Readiness Orchestrator (br-month-end-readiness)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Assemble a single month-end readiness scorecard across every module. You drive the sequence and
the master roll-up; each module's own readiness skill (or its primary report) does the detail. Run
steps in order, keeping every module sheet.

**Requires:** br-run-reports, br-data-dashboard, and the module skills
br-ap-close-readiness, br-ar-close-readiness, br-inv-cost-close-readiness, br-fa-close-readiness,
br-gl-close-readiness, br-close-process-monitor. *(Optional:* br-po-close-readiness, br-ce-recon-readiness,
br-subledger-gl-reconciliation.)*

## Division of responsibility — READ FIRST
- **You do NOT run Blitz reports yourself** — extraction is always via **br-run-reports**
  (directly, or inside the module skills). Do not call the `br_` UDFs *directly from the orchestrator* - delegate extraction to br-run-reports / the module skills, which write the `=br_...()` worksheet UDFs into cells (the `br_` functions ARE the data source: worksheet UDFs, not MCP tools/connectors, so never `refresh_mcp_connectors` looking for Blitz); never touch a result sheet
  until its run is confirmed complete.
- **Delegate one module at a time and wait for it to finish before starting the next.** Do not start
  several module skills at once — the close runs are asynchronous and overlapping them stalls them.
- **Robust hand-off:** invoke each module readiness skill to produce that module's sheet. **If a
  module skill does not fire** (composition can be unreliable), fall back to running that module's
  **primary** report directly via br-run-reports and scoring it inline with the same
  RAG rule. Never skip a module silently — show it as "not assessed" if neither path worked.
- **Read-and-recommend only:** nothing here executes a fix.

## When to use
"Are we ready to close May", "month-end readiness", "full close status", a close-readiness pack for
the controller.

## Inputs (collect up front)
- **Ledger**; **Operating Unit(s)** (AP/AR); **Organization Code(s)** (INV); **FA Book**; **Period**.
- *Optional:* materiality threshold for reconciliations; whether to include CE and the subledger-GL recon.

## CONFIG
### Close sequence (the order the scorecard recommends)
1. Subledgers in parallel: **AP, AR, Inventory/Costing, FA** (each must reach Green).
2. **Subledger-to-GL reconciliation** (optional) — confirm control accounts tie.
3. **GL** — only after subledgers are closed/reconciled.
Throughout: **Close Process Monitor** must show the close programs healthy.

### Module → primary report (fallback if the module skill doesn't fire)
The module skills run their own reports **directly by name** (no broad discovery search). If a
module skill doesn't fire and you run its fallback report yourself, pass the **documented name
below directly** to br-run-reports — do NOT `br_report_list_external`-search first;
only fall back to a search on `#BLITZ_REPORT_NOT_FOUND`.

| Module | Skill | Fallback primary report |
|---|---|---|
| AP | br-ap-close-readiness | `AP Period Close Exceptions` |
| AR | br-ar-close-readiness | `AR Unaccounted Transaction Sweep` (Sweep Now = No) |
| INV/Cost | br-inv-cost-close-readiness | `INV Period Close Pending Transactions` |
| FA | br-fa-close-readiness | `FA Depreciation by period` (+ `FA Unposted Mass Additions`) |
| GL | br-gl-close-readiness | `GL Period Status` |
| Process | br-close-process-monitor | `FND Concurrent Requests` |

### Overall RAG
- **Green** — every module Green and the close-process monitor Green.
- **Amber** — all subledgers Green/Amber but GL or recon still pending.
- **Red** — any module Red.

### Output sheets & tab order (left to right)
`Month_End_Readiness` (master, first), then `AP_Close_Readiness`, `AR_Close_Readiness`,
`INV_Close_Readiness`, `FA_Close_Readiness`, `GL_Close_Readiness`, `Close_Process_Monitor`,
[`CE_Recon_Readiness`], [`Subledger_GL_Recon`] (detail sheets after the master).

## Pipeline
1. **Process health first.** Run br-close-process-monitor (or `FND Concurrent Requests`) — if close programs are erroring, surface that at the top; module results may be stale until they clear.
2. **Per module, in sequence (AP → AR → INV → FA → GL):** invoke the module skill; on no-fire, run its fallback report and score inline. Capture each module's RAG + top blockers into a roll-up table from the **values the sub-skill returned in its own final JS call** — wait for each module to complete before the next, but do **NOT** insert extra `get_cell_ranges` reads between sub-skill invocations to inspect a module's output sheet (Rule 8). Each delegated sub-skill follows the standards within its own pipeline; trust its return values and reconcile only at the final validation read.
   - **Period status is already covered by `GL Period Status`** (it reports every subledger's period status), so in the orchestrated flow you do NOT need to also run `CAC Accounting Period Status` per module.
3. **Optional:** br-po-close-readiness (the purchasing-accrual leg — include when the user runs a full close or names PO/accruals), br-ce-recon-readiness and/or br-subledger-gl-reconciliation.
4. **Master scorecard (delegate to br-data-dashboard if it fires; else build inline)  *(single `execute_office_js` call)*.** In one call, build the entire `Month_End_Readiness` sheet — all sections in the same JS block: the overall RAG banner (ledger+period); the per-module status rows (module, RAG, # blockers, top blocker, recommended action) ordered by the close sequence; the close-process-monitor status; and the "recommended next actions" list ordered subledgers → recon → GL. If any charts are added, they go in a **second** `execute_office_js` call (the one permitted exception). Read the per-module RAG + blockers from the values each sub-skill returned in its own final JS call — do **not** insert `get_cell_ranges` reads against the module sheets to inspect their output here (Rule 8); trust the sub-skill return values / `formula_results`, no re-read needed at this step.
   - **Build mechanics (learned on a real run):** build the master on a NEW sheet at **position 0** (first tab); leave every module's own sheet untouched and **do NOT rename** it (the master links to it by name). **Do NOT use a multi-row `copyToRange`** to fill the per-module rows (it can latch onto the wrong source box and duplicate headers into the data) — write each row's formula explicitly. After building, scan **beyond** the dashboard's column range, clear any stray cells, and widen amount columns so values don't render as `######`.
5. **Verdict narrative  *(single `set_cell_range` call)*.** Write all ≤6 bullets to `Month_End_Readiness` in one call: can we close (overall call), which modules block it, the single most urgent action, and the recommended order to clear the rest. Do not call `set_cell_range` once per bullet.
6. **Arrange tabs + final validation  *(single `execute_office_js` call + one read)*.** In one call, reorder worksheet tabs per CONFIG and make `Month_End_Readiness` active — only after the master scorecard exists. Then do the **one permitted verification read** at the end of the pipeline (the Validation checks below); do not insert any intermediate verification reads between modules.

## Validation
- Every required module appears in the roll-up with a RAG (or an explicit "not assessed").
- Overall RAG is consistent with the module rows (Red if any module Red).
- Per-module figures on the master tie to that module's own sheet.

## Closed-loop (roadmap, not executed here)
Each module's fix (hold release, receipt application, GL journal upload, FA mass additions) is a
Blitz Upload; accounting/posting/depreciation are concurrent submits. This orchestrator recommends
the sequence; a human executes each step.
