---
name: br-subledger-gl-reconciliation
description: >
  Reconcile Oracle EBS subledgers to the General Ledger in Excel: have the
  br-run-reports skill extract AP, AR, Inventory and FA control balances and tie each
  to its GL control account, surfacing the variance per subledger with a red/amber/green verdict.
  For receivables it also explains the difference between the aging and the receivable accounts
  per customer (manual journals, unaccounted or untransferred items, cross-customer applications,
  memos accounted elsewhere) on request. Use when the user asks to reconcile AP/AR/INV/FA to GL,
  subledger-to-GL tie-out, AR aging against the trial balance, or control account differences at
  period end.
# Trigger: Slash command + auto
---

# Subledger-to-GL Reconciliation (br-subledger-gl-reconciliation)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Read `references/ar-difference-explainer.md` when the AR explainer runs.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Tie each subledger to its GL control account in one workbook and surface the variances. You own
orchestration, the tie-out, and the verdict; br-run-reports does extraction and
br-data-dashboard the build. Run steps in order, keeping intermediate sheets.

**Requires:** br-run-reports, br-data-dashboard.

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** All extraction is done by **br-run-reports**
(connection, auth, async run, completion, cell population). Never call `br_*` functions, and never
rename/read/sum the result sheet or start analysis until extraction is confirmed complete. This
skill is **read-only**: it reconciles and reports; it changes nothing.

## When to use
"Reconcile AP/AR/INV/FA to GL", subledger-to-GL tie-out, control-account differences, period-end recon.

## Inputs
- **Ledger** (required); **Period**; *optional:* which subledgers to include (default AP, AR, INV, FA).
- **AR explainer** (opt-in, asked once up front): explain the AR difference per customer. It runs
  one more report and the drills of the reference, so it is offered, never run by default.

## Reports used (authoritative names — do NOT broad-search for them)
These exact report names are known. When you ask br-run-reports to run one, pass the
**documented name directly** — do NOT run a `br_report_list_external` discovery search first. Inspect
parameters only if you need an exact LOV spelling. **Fallback:** only if a run returns
`#BLITZ_REPORT_NOT_FOUND` (the instance renamed it, or the module isn't installed) do a name search.

| Report (exact name) | Run with | Notes |
|---|---|---|
| `AP Trial Balance` | Ledger + Period | AP liability ending balance |
| `AR Aging to GL Reconciliation` | Ledger + Period + **Period From** (the first period of that financial year; always pass it: omitted, the add-in sends a default computed for another period) | per receivable account the GL closing balance, the aging's AR closing balance, the difference and the reconciling items; template `Customer Differences` for the explainer. On `#BLITZ_REPORT_NOT_FOUND` (a Blitz Report build before this report) use `AR to GL Reconciliation`, which ties only the period's Receivables activity, and say so |
| `CST Period Close Subinventory Value` (+ `CST AP and PO Accrual Reconciliation`) | Org / Ledger + Period | INV value |
| `FA Journal Entry Reserve Ledger` | Book + Period | FA cost + reserve |
| `GL Trial Balance Detail` | Ledger + Period | GL control balances (all four tie-outs) |

## CONFIG
### Subledger → source report → GL control account
| Subledger | Subledger balance source | GL side | Tie-out |
|---|---|---|---|
| AP | `AP Trial Balance` (liability ending balance) | GL liability control account (`GL Trial Balance Detail`) | AP ending = GL liability |
| AR | `AR Aging to GL Reconciliation` (AR Closing Balance) | its own GL Closing Balance per receivable account | AR closing = GL closing per account; the report's Closing Difference |
| INV | `CST Period Close Subinventory Value` (+ `CST AP and PO Accrual Reconciliation`) | GL inventory / accrual accounts | INV value = GL inventory |
| FA | `FA Journal Entry Reserve Ledger` (cost + reserve) | GL asset / accumulated-depreciation accounts | FA = GL asset accounts |

### Materiality / RAG
- **Green** — every included subledger ties within the materiality threshold (ask the user; default 0).
- **Amber** — a variance within a small tolerance the user accepts.
- **Red** — any variance over materiality.

### Output sheets & tab order (left to right)
`Subledger_GL_Recon` (first), then one sheet per subledger (`AP_TB`, `AR_GL`, [`AR_GL_Explained`], `INV_Value`, `FA_Reserve`), GL balance sheet last.

## Pipeline
1. **Extract — DELEGATE.** For each included subledger, br-run-reports runs its source report (CONFIG) for the Ledger+Period, plus **"GL Trial Balance Detail"** for the GL control balances. Wait for each; do nothing mid-run.
2. **Anchor & tie-out** *(single `execute_office_js` call)*. In one call: read each subledger's ending balance and the matching GL control balance (the **reconciliation anchor** for the final step), compute variance = subledger − GL per subledger, and classify per CONFIG materiality. Trust formula_results from the write call. No re-read needed here.
3. **Scorecard** *(single `execute_office_js` call)* (delegate to br-data-dashboard if it fires; else build inline). Write all sections to `Subledger_GL_Recon` in one call: the tie-out table (subledger, subledger balance, GL balance, variance, status), the RAG banner, and the worst-variance highlight.
   - **Build mechanics (learned on a real run):** build on a NEW sheet at **position 0** (first tab); leave each report on the sheet br-run-reports created (its report name) — do NOT rename it, the dashboard links to it. **Do NOT use a multi-row `copyToRange`** to fill formula rows (it can latch onto the wrong source box and duplicate headers into the data) — write each row's formula explicitly. After building, scan **beyond** the dashboard's column range, clear any stray cells, and widen amount columns so values don't render as `######`.
4. **Narrative** *(single `set_cell_range` call)*. Write all ≤5 bullets in one call: which subledgers tie, which don't, the largest variance and where to look.
4b. **AR explainer (only if accepted).** br-run-reports runs `AR Aging to GL Reconciliation` with
   the template `Customer Differences` (Ledger, Period, Period From as in step 1; Show
   Customers=Yes, Differences Only=Yes, Show Monthly Movement=Yes). Explain the AR difference per `references/ar-difference-explainer.md` on
   `AR_GL_Explained`: timing items, GL-only journals, cross-customer pairs, items to reclass, with
   the evidence and the remainder left unexplained. A reclass is handed to **br-gl-account-coder**
   (its gated journal step); this skill books nothing.
5. **Arrange tabs + final validation** *(single `execute_office_js` call + one read)*. In one call: reorder tabs per CONFIG and make `Subledger_GL_Recon` active. Only after the scorecard. **Then do the one permitted verification read:** confirm each scorecard subledger/GL balance equals the Step-2 anchor.

## Validation
Each variance = its subledger balance − its GL balance; Red only if a variance exceeds materiality.
If a subledger's control account mapping is unknown on the instance, say so rather than reporting a false tie.
