---
name: br-po-close-readiness
description: >
  Assess Oracle EBS Purchasing period-close readiness in Excel: have the br-run-reports skill
  extract the AP/PO accrual reconciliation, the aged uninvoiced receipts, and the period status,
  then give a red/amber/green verdict with remediation and build a PO close-readiness scorecard.
  Use when the user asks "can we close PO for {period}", "purchasing close readiness", "accrual
  reconciliation status", or uninvoiced receipts backlog.
# Trigger: Slash command + auto
---

# PO Period Close Readiness (br-po-close-readiness)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Produce a PO close-readiness scorecard in one workbook. You own orchestration, scoring, and the
verdict; br-run-reports does extraction and br-data-dashboard the build. Run steps in order, on
separate turns, keeping intermediate sheets. This is the purchasing-accrual leg the subledger-to-GL
reconciliation does not cover.

**Requires:** br-run-reports, br-data-dashboard.

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** All extraction is done by **br-run-reports**. Never call
`br_*` functions, and never touch a result sheet until extraction is confirmed complete. This skill
is **read-and-recommend only**: it never closes the period, runs the accrual load, or matches
invoices; it reports blockers and the recommended action.

## When to use
"Can we close Purchasing for May", "PO close readiness", "does the accrual tie out", "how big is
the uninvoiced receipts backlog", "receipt accrual reconciliation status".

## Inputs
- **Operating Unit** — required; **Period**. *(Optional:* materiality $ for the accrual variance —
  default in CONFIG.)*

## Reports used (authoritative names — do NOT broad-search for them)
Pass the **documented name directly** to br-run-reports — no discovery search first. **Fallback:**
only on `#BLITZ_REPORT_NOT_FOUND` do a name search (the instance may have renamed it or lack the
module).

| Report (exact name) | Run with | Notes |
|---|---|---|
| `CST AP and PO Accrual Reconciliation` | OU (+ period/date params as offered) | **The verdict driver** — receipt-accrual balance vs AP/PO activity. ⚠️ It reads the accrual RELOAD snapshot: if the run screen shows a load-request/date param and the last load predates the period end, ask the user to run the accrual load first (or flag the verdict as stale-snapshot). |
| `CST Uninvoiced Receipts` | OU (+ aging/date params as offered) | **The backlog queue** — received-not-invoiced lines; these ARE the accrual. Aged lines mean invoices missing or matching stuck. |
| `CAC Accounting Period Status` | Ledger/OU + Period | Is the PO (and INV) period still open where it should be, and prior periods closed. |
| `PO Headers and Lines` *(optional, housekeeping)* | OU + open-order filters | Old open POs past need-by that should be closed/cancelled — close hygiene, not a blocker. |

## CONFIG
### Checks → class + remediation
| Check (source) | Class | Remediation |
|---|---|---|
| Accrual reconciliation variance beyond materiality (`CST AP and PO Accrual Reconciliation`) | **Blocker** | Investigate write-offs / mis-matched invoices before close |
| Uninvoiced receipts older than the aging threshold and above the $ floor (`CST Uninvoiced Receipts`) | **Blocker** | Chase the invoices or resolve the receipt; they land in the accrual |
| Accrual snapshot older than period end | **Blocker (data)** | Run the accrual load, then re-assess — never score a stale snapshot Green |
| PO period already closed / prior period still open (`CAC Accounting Period Status`) | **Review** | Fix period statuses with the GL/INV owner |
| Open POs past need-by (`PO Headers and Lines`) | **Review** | Mass-close/cancel candidates — hygiene, next cycle |

**Defaults (edit to the customer):** materiality = $1,000 net variance; uninvoiced aging threshold =
30 days; $ floor per line = $100.

### Readiness (RAG)
- **Red** — accrual variance over materiality, aged uninvoiced backlog over threshold, or a stale
  accrual snapshot.
- **Amber** — only Review-class items (period-status oddities, old open POs).
- **Green** — accrual ties within materiality on a current snapshot; backlog young and small.

### Output sheets & tab order (left to right)
`PO_Close_Readiness` (first), `PO_Accrual_Recon`, `PO_Uninvoiced`, `Period_Status`,
[`PO_Open_Orders`] (last).

## Pipeline
1. **Extract — DELEGATE.** br-run-reports runs `CST AP and PO Accrual Reconciliation` →
   `PO_Accrual_Recon`; `CST Uninvoiced Receipts` → `PO_Uninvoiced`; `CAC Accounting Period Status`
   → `Period_Status`; optionally `PO Headers and Lines` → `PO_Open_Orders`. Wait for each; do
   nothing mid-run.
2. **Anchor.** Record net accrual variance, uninvoiced line count / total $ / aged count+$, period
   statuses, snapshot currency (load date vs period end). Clean → Green scorecard.
3. **Score.** Apply CONFIG; rank blockers by $; attach remediation.
4. **Scorecard *(single `execute_office_js` call)*** (delegate to br-data-dashboard if it fires;
   else inline). RAG banner (OU+period); accrual variance vs materiality; uninvoiced backlog KPIs
   (count, $, aged share); period-status line; blocking-items list with $ and remediation. Charts
   in a second call. Build on a NEW sheet at **position 0**; leave each report on the sheet
   br-run-reports created (do NOT rename — the dashboard links to it); **do NOT use a multi-row
   `copyToRange`** for formula rows; after building, clear strays beyond the range and widen amount
   columns so values don't render as `######`.
5. **Narrative.** ≤5 bullets: overall call, biggest blocker $, snapshot caveat if any, recommended
   next action.
6. **Arrange tabs + final validation.** Order per CONFIG; `PO_Close_Readiness` active. **Then the
   one permitted verification read:** the scorecard's variance and backlog figures tie to the
   Step-2 anchor.

## Validation
Scorecard ties to raw sheets; Red only if a Blocker exists; a stale accrual snapshot is never
reported Green — say "not assessable until the accrual load runs" instead.

## Closed-loop (roadmap, not executed here)
Invoice matching gaps route to AP (the AP Invoice Upload exists); PO mass-close is a Forms action.
This skill recommends; a human runs them.
