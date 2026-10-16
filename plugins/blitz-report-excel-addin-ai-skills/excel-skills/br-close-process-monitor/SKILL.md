---
name: br-close-process-monitor
description: >
  Monitor the Oracle EBS concurrent programs that drive a period close in Excel: have the
  br-run-reports skill extract recent Create Accounting / Transfer to GL / Cost
  Manager / Depreciation / Journal Import / AutoInvoice request status, flag errored, stuck, and
  long-running close jobs, and build a close-process monitor dashboard. Use when the user asks
  whether the close programs are running/erroring, "CP manager status", or stuck concurrent requests.
# Trigger: Slash command + auto
---

# Close Process Monitor (br-close-process-monitor)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Produce a close-process health dashboard in one workbook — are the programs that *perform* the
close completing, erroring, or stuck? You own orchestration, scoring, and the verdict;
br-run-reports does extraction and br-data-dashboard the build. Run steps in order,
keeping intermediate sheets.

**Requires:** br-run-reports, br-data-dashboard.

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** All extraction is done by **br-run-reports**
(connection, auth, async run, completion, cell population). Never call `br_*` functions, and never
rename/read/sum the result sheet or start analysis until extraction is confirmed complete. This
skill is **read-and-recommend only**: it never resubmits requests; it reports status and the
recommended action.

## When to use
"Are the close programs running", "CP manager status", stuck/errored concurrent requests during
close, Create Accounting / Transfer to GL / Cost Manager / Depreciation / Journal Import / AutoInvoice failures.

## Inputs
- *Optional:* **Started within Days** (default 3), a program-name filter, Phase/Status. With no
  filter, focus on the close program family in CONFIG.

## Reports used (authoritative names — do NOT broad-search for them)
These exact report names are known. When you ask br-run-reports to run one, pass the
**documented name directly** — do NOT run a `br_report_list_external` discovery search first. Inspect
parameters only if you need an exact LOV spelling. **Fallback:** only if a run returns
`#BLITZ_REPORT_NOT_FOUND` (the instance renamed it, or the module isn't installed) do a name search.

| Report (exact name) | Run with | Notes |
|---|---|---|
| `FND Concurrent Requests` | Started within Days (default 3) | **The verdict driver** — close-program request status |
| `FND SOA Runtime Error` *(optional)* | — | ISG/SOA close-time failures |

## CONFIG
### Close program family (match by name; case-insensitive contains)
Create Accounting, Transfer Journal Entries to GL, Journal Import, Posting, Cost Manager,
Material Cost Distribution, Depreciation, Generate Accounts, AutoInvoice Import/Master,
Payables Accounting Process, Receivables Accounting, Revaluation, Translation, Mass Additions.

### Status → class + recommendation
| Concurrent request state | Class | Recommendation |
|---|---|---|
| Completed = Error | **Blocker** | Open the request log; fix the cause and resubmit |
| Completed = Warning | **Review** | Check the log; usually proceed |
| Running far longer than normal | **Watch** | Check for locks/contention before assuming it will finish |
| Pending / Inactive (no manager) | **Blocker** | Check the concurrent manager is up |
| Completed = Normal | OK | — |

### Readiness (RAG)
- **Red** — any close-family request in Error or Pending-no-manager.
- **Amber** — Warnings or abnormally long-running close requests.
- **Green** — all recent close-family requests completed Normal.

### Output sheets & tab order (left to right)
`Close_Process_Monitor` (first), `SOA_Errors` (optional), `Close_Requests` (last).

## Pipeline
1. **Extract — DELEGATE.** br-run-reports runs **"FND Concurrent Requests"** with **Started within Days** = {input/3} → `Close_Requests`. Optionally **"FND SOA Runtime Error"** → `SOA_Errors` for ISG/SOA close-time failures. Wait for completion; do nothing mid-run.
2. **Filter, anchor & score** *(single `execute_office_js` call)*. In one call: read the `Close_Requests` columns, keep only the close-program family (CONFIG), record counts by status (Error / Warning / Running / Pending / Normal) — the **reconciliation anchor** for the final step (none errored/stuck → Green) — apply CONFIG scoring, and write back the errored & stuck list sorted first, each with request id, program, phase/status, and the recommendation. Trust formula_results from the write call. No re-read needed here.
3. **Dashboard** *(single `execute_office_js` call)* (delegate to br-data-dashboard if it fires; else build inline). Write all sections to `Close_Process_Monitor` in one call: RAG banner, close-family request status counts, and the errored/stuck list with request ids.
   - **Build mechanics (learned on a real run):** build on a NEW sheet at **position 0** (first tab); leave each report on the sheet br-run-reports created (its report name) — do NOT rename it, the dashboard links to it. **Do NOT use a multi-row `copyToRange`** to fill formula rows (it can latch onto the wrong source box and duplicate headers into the data) — write each row's formula explicitly. After building, scan **beyond** the dashboard's column range, clear any stray cells, and widen amount columns so values don't render as `######`.
4. **Narrative** *(single `set_cell_range` call)*. Write all ≤5 bullets in one call: overall health, which close program failed and why (from completion text), recommended next action.
5. **Arrange tabs + final validation** *(single `execute_office_js` call + one read)*. In one call: reorder tabs per CONFIG and make `Close_Process_Monitor` active. Only after the dashboard. **Then do the one permitted verification read:** confirm the dashboard status counts tie to the Step-2 anchor.

## Validation
Status counts tie to the filtered `Close_Requests`; Red only if an Error/Pending-no-manager exists.

## Closed-loop (roadmap, not executed here)
Resubmitting a concurrent request is a concurrent submit. This skill reports; a human resubmits.
