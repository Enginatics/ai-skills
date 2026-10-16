---
name: br-ar-close-readiness
description: >
  Assess Oracle EBS Accounts Receivable period-close readiness in Excel: have the
  br-run-reports skill extract unaccounted AR transactions, AutoInvoice interface
  errors, and the AR-to-GL reconciliation, then give a red/amber/green verdict with remediation
  and build an AR close-readiness scorecard. Use when the user asks "can we close AR for
  {period}", "AR period close readiness", unaccounted receivables, unapplied receipts, or
  AutoInvoice backlog.
# Trigger: Slash command + auto
---

# AR Period Close Readiness (br-ar-close-readiness)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Produce an AR close-readiness scorecard in one workbook. You own orchestration, scoring, and
the verdict; br-run-reports does extraction and br-data-dashboard the build. Run
steps in order, on separate turns, keeping intermediate sheets.

**Requires:** br-run-reports, br-data-dashboard.

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** All extraction is done by **br-run-reports**
(it owns connection, auth, async run, completion, cell population). Never call `br_*` functions,
and never rename/read/sum the result sheet or start analysis until extraction is confirmed
complete — touching the workbook mid-run stalls it. This skill is **read-and-recommend only**:
it never sweeps, runs accounting, or uploads; it reports blockers and the recommended action.

## When to use
"Can we close AR for May", "AR period close readiness", unaccounted receivables/receipts,
unapplied/unidentified receipts, AutoInvoice interface errors, AR↔GL out of balance.

## Inputs
- **Operating Unit** *or* **Ledger** (required); **Period Name** (or From/To Accounting Date).

## Reports used (authoritative names — do NOT broad-search for them)
These exact report names are known. When you ask br-run-reports to run one, pass the
**documented name directly** — do NOT run a `br_report_list_external` discovery search first. Inspect
parameters only if you need an exact LOV spelling. **Fallback:** only if a run returns
`#BLITZ_REPORT_NOT_FOUND` (the instance renamed it, or the module isn't installed) do a name search.

| Report (exact name) | Run with | Notes |
|---|---|---|
| `AR Unaccounted Transaction Sweep` | **Reporting Level + Reporting Context** (e.g. Reporting Level=`Operating Unit`, Reporting Context=`<OU>`) + Period; **Sweep Now = No** (read-only list). It does **NOT** take a bare `Operating Unit` param. | **The verdict driver.** Receivables (always present) |
| `CAC Accounting Period Status` | **Functional Area = Receivables** (the param is `Functional Area`, NOT `Application`) + OU/Ledger + Period | Period-status check (Step 1c). **Costing/CAC** — may be absent → note it and skip |
| `AR Autoinvoice Interface Summary` | **Operating Unit only — no Period param** | Interface-error check |
| `AR to GL Reconciliation` *(optional)* | Ledger + Period | AR↔GL tie-out — only if the user asks |

**If a run returns a bare/uninformative `ERROR` (e.g. `ERROR: ERROR`), the param names didn't match the report** — have br-run-reports inspect params (`br_report_params_external`) and adapt, then retry. Do NOT abandon the run.

## CONFIG
### Checks → class + remediation
| Check (source report) | Class | Remediation |
|---|---|---|
| Unaccounted AR transactions (`AR Unaccounted Transaction Sweep`, **Sweep Now = No** = read-only list) | **Blocker** | Run **Create Accounting** (Receivables); or sweep to next period if policy allows |
| AutoInvoice interface errors (`AR Autoinvoice Interface Summary`) | **Blocker** | Correct the interface rows and resubmit AutoInvoice Import |
| Incomplete transactions (not completed → not accounted) | **Blocker** | Complete the transactions |
| Unapplied / unidentified receipts | **Review** | Apply receipts (closed-loop: receipt application upload) |
| AR↔GL variance (`AR to GL Reconciliation`) | **Blocker** | Investigate the reconciling difference |

### Readiness (RAG)
- **Red** — any Blocker (unaccounted, interface errors, incomplete, AR↔GL variance over materiality).
- **Amber** — only Review-class items (e.g. unapplied receipts) the user accepts.
- **Green** — no unaccounted, no interface errors, AR ties to GL.

### Output sheets & tab order (left to right)
`AR_Close_Readiness` (first), [`AR_GL_Recon`], `AR_AutoInvoice_Errors`, `AR_Unaccounted` (last).

## Pipeline
1. **Extract — DELEGATE.** br-run-reports runs **"AR Unaccounted Transaction Sweep"** with **Reporting Level + Reporting Context** (e.g. Operating Unit = the OU) + Period and **Sweep Now = No** (read-only) → `AR_Unaccounted`; then **"AR Autoinvoice Interface Summary"** (Operating Unit only — no Period) → `AR_AutoInvoice_Errors`; optionally **"AR to GL Reconciliation"** → `AR_GL_Recon`. Wait for each to fully complete before the next; do nothing mid-run.
1c. **Confirm the period is open (recommended).** Delegate to br-run-reports to run **"CAC Accounting Period Status"** (**Functional Area = Receivables** — the param is `Functional Area`, not `Application` — for the OU/Ledger + Period). Confirm the AR period is **Open** — a "ready to close" verdict is meaningless if it's already Closed or still Future. Show the status on the scorecard. If the report isn't found on the instance, note that and proceed (don't block on it).
2. **Anchor.** Record unaccounted count + $ and AutoInvoice error count. Clean → Green scorecard.
3. **Score.** Apply CONFIG; rank blockers by $; attach remediation; flag runnable vs manual.
4. **Scorecard *(single `execute_office_js` call)*** (delegate to br-data-dashboard if it fires; else build inline). Write all scorecard sections to `AR_Close_Readiness` in one call: RAG banner; unaccounted by class/$, AutoInvoice errors, AR↔GL variance, blocking-items list. KPIs tie to raw sheets. Any charts follow in a second call.
   - **Build mechanics (learned on a real run):** build on a NEW sheet at **position 0** (first tab); leave each report on the sheet br-run-reports created (its report name) — do NOT rename it, the dashboard links to it. **Do NOT use a multi-row `copyToRange`** to fill formula rows (it can latch onto the wrong source box and duplicate headers into the data) — write each row's formula explicitly. After building, scan **beyond** the dashboard's column range, clear any stray cells, and widen amount columns so values don't render as `######`.
5. **Narrative.** ≤5 bullets: overall call, biggest blocker, $ unaccounted, recommended next action.
6. **Arrange tabs + final validation.** Arrange tabs per CONFIG; make `AR_Close_Readiness` active. Only after the scorecard. **Then do the one permitted verification read:** confirm the scorecard's unaccounted count + $ tie to the Step-2 anchor. This is the only explicit re-read allowed in the entire pipeline outside of the anchor step.

## Validation
Scorecard counts/$ tie to `AR_Unaccounted`; Red only if a Blocker exists.

## Closed-loop (roadmap, not executed here)
Receipt application is deliverable via a Blitz Upload; Create Accounting / AutoInvoice resubmit are concurrent submits. This skill recommends; a human runs it. (The `AR Unaccounted Transaction Sweep` report can itself sweep when Sweep Now = Yes — this skill keeps it OFF.)
