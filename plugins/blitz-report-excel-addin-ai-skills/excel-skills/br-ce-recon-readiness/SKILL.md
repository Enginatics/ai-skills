---
name: br-ce-recon-readiness
description: >
  Assess Oracle EBS Cash Management bank reconciliation / period-close readiness in Excel: have
  the br-run-reports skill extract unreconciled bank statement lines and the GL cash
  reconciliation, then give a red/amber/green verdict with remediation and build a CE
  reconciliation-readiness scorecard. Use when the user asks about bank reconciliation status,
  unreconciled statements, or cash management period close.
# Trigger: Slash command + auto
---

# Cash Management Reconciliation Readiness (br-ce-recon-readiness)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Produce a CE reconciliation-readiness scorecard in one workbook. You own orchestration, scoring,
and the verdict; br-run-reports does extraction and br-data-dashboard the build. Run
steps in order, on separate turns, keeping intermediate sheets.

**Requires:** br-run-reports, br-data-dashboard.

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** All extraction is done by **br-run-reports**
(connection, auth, async run, completion, cell population). Never call `br_*` functions, and never
rename/read/sum the result sheet or start analysis until extraction is confirmed complete. This
skill is **read-and-recommend only**: it reports blockers and the recommended action.

## When to use
Bank reconciliation status, unreconciled statement lines, GL cash account variance, cash
management period close.

## Inputs
- **Bank Account** (one or several) — required; **Period** / statement date range.

## Reports used (authoritative names — do NOT broad-search for them)
These exact report names are known. When you ask br-run-reports to run one, pass the
**documented name directly** — do NOT run a `br_report_list_external` discovery search first. Inspect
parameters only if you need an exact LOV spelling. **Fallback:** only if a run returns
`#BLITZ_REPORT_NOT_FOUND` (the instance renamed it, or the module isn't installed) do a name search.

| Report (exact name) | Run with | Notes |
|---|---|---|
| `CE Transactions Available for Reconciliation` | Bank Account + Period | **The verdict driver** — unreconciled statement lines |
| `CE General Ledger Reconciliation` | Bank Account + Period | GL cash account variance |
| `CE Bank Statement and Reconciliation` *(optional)* | Bank Account + Period | Statement import / missing-statement check (Review) |

## CONFIG
### Checks → class + remediation
| Check (source report) | Class | Remediation |
|---|---|---|
| Unreconciled statement lines (`CE Transactions Available for Reconciliation`) | **Blocker** | Reconcile or clear the open lines |
| GL cash account variance (`CE General Ledger Reconciliation`) | **Blocker** | Investigate the bank↔GL difference |
| Statement import errors / missing statements (`CE Bank Statement and Reconciliation`) | **Review** | Import / correct the statement (closed-loop: bank statement import upload) |

### Readiness (RAG)
- **Red** — unreconciled lines or a bank↔GL variance over materiality.
- **Amber** — only Review-class import items.
- **Green** — statements imported, lines reconciled, cash ties to GL.

### Output sheets & tab order (left to right)
`CE_Recon_Readiness` (first), `GL_Cash_Recon`, `Unreconciled_Lines` (last).

## Pipeline
1. **Extract — DELEGATE.** br-run-reports runs **"CE Transactions Available for Reconciliation"** (Bank Account + period) → `Unreconciled_Lines`; then **"CE General Ledger Reconciliation"** → `GL_Cash_Recon`. Wait for each; do nothing mid-run.
2. **Anchor.** Record unreconciled line count + $ and the GL cash variance. Clean → Green scorecard.
3. **Score.** Apply CONFIG; rank blockers; attach remediation.
4. **Scorecard *(single `execute_office_js` call)*** (delegate to br-data-dashboard if it fires; else build inline). Write all scorecard sections to `CE_Recon_Readiness` in one call: RAG banner (account+period); unreconciled lines, GL cash variance, blocking-items list. Any charts follow in a second call.
   - **Build mechanics (learned on a real run):** build on a NEW sheet at **position 0** (first tab); leave each report on the sheet br-run-reports created (its report name) — do NOT rename it, the dashboard links to it. **Do NOT use a multi-row `copyToRange`** to fill formula rows (it can latch onto the wrong source box and duplicate headers into the data) — write each row's formula explicitly. After building, scan **beyond** the dashboard's column range, clear any stray cells, and widen amount columns so values don't render as `######`.
5. **Narrative.** ≤5 bullets.
6. **Arrange tabs + final validation.** Arrange tabs per CONFIG; make `CE_Recon_Readiness` active. Only after the scorecard. **Then do the one permitted verification read:** confirm the scorecard's unreconciled line count + $ and the GL cash variance tie to the Step-2 anchor. This is the only explicit re-read allowed in the entire pipeline outside of the anchor step.

## Validation
Scorecard ties to raw sheets; Red only if a Blocker exists.

## Closed-loop (roadmap, not executed here)
Bank statement import is deliverable via a Blitz Upload. This skill recommends; a human runs it.
