---
name: br-inv-exception-triage
description: >
  Triage Oracle EBS Inventory exceptions in Excel: have the br-run-reports skill extract negative
  on-hand balances, stuck interface/error transactions, and cycle counts pending approval, then
  rank everything by severity with a recommended owner and fix, and build one exception dashboard.
  Use when the user asks what's wrong in inventory, negative on-hand, stuck transactions,
  unprocessed material transactions, or an inventory exception review.
# Trigger: Slash command + auto
---

# INV Exception Triage (br-inv-exception-triage)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes.

Produce a ranked inventory exception register in one workbook. You own classification, severity and
the register; br-run-reports does extraction and br-data-dashboard the build. Run steps in order,
keeping intermediate sheets. Stuck interface rows are also a **period-close blocker** — if this run
feeds a close assessment, hand the interface-error verdict to br-inv-cost-close-readiness rather
than duplicating its scorecard.

**Requires:** br-run-reports, br-data-dashboard. *(Optional:* br-anomaly-detection for unusual
transaction patterns.)*

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** All extraction is by **br-run-reports**; never call
`br_*` functions or touch a result sheet mid-run. **Read-and-recommend only** — this skill never
corrects on-hand, resubmits interface rows, or approves counts; it ranks and routes.

## When to use
"What's broken in inventory", "negative on-hand check", "stuck material transactions", "pending
transactions review", "cycle counts waiting for approval", "inventory exception triage". For the
period-close verdict itself, use **br-inv-cost-close-readiness**.

## Inputs
- **Organization Code** (inventory org) — required; ask if not supplied. *(Optional:* subinventory,
  date window for the interface errors.)*

## Reports used (authoritative names — do NOT broad-search for them)
Pass the **documented name directly**; search only on `#BLITZ_REPORT_NOT_FOUND`.

| Report (exact name) | Run with | Notes |
|---|---|---|
| `INV Onhand Quantities` | Org (+ subinventory) | Scan for **negative on-hand** rows — the driver for the Critical class. Filter client-side; do not assume a "negative only" parameter exists. |
| `CAC Interface Error Summary` | Org / ledger scope as offered | **Stuck interface/error transactions** across the material-transaction interfaces — each aged row is data missing from stock and from the GL. |
| `INV Cycle counts pending approval` | Org | Counts entered but not approved — adjustments in limbo. |
| `INV Material Transactions` *(optional, evidence)* | Org + item + recent dates | Pull ONLY when drilling into a specific exception — never wide-open. |

## CONFIG
### Severity classes
| Exception | Class | Route to |
|---|---|---|
| Negative on-hand in an asset (costed) subinventory | **Critical** | Inventory control — investigate the driving transaction; correct via the standard adjustment flow |
| Interface/error transactions older than 2 days | **Critical** | The module owner per the error source — each row is an unposted transaction |
| Negative on-hand in an expense subinventory | **High** | Review — often tolerated, still worth a look |
| Interface errors ≤ 2 days | **High** | Watch — may clear on resubmit |
| Cycle counts pending approval past 7 days, or adjustment beyond tolerance | **High** | Count supervisor |
| Cycle counts pending within tolerance/age | **Review** | Routine approval queue |

**Defaults (edit to the customer):** interface aging 2 days; count-approval aging 7 days;
adjustment tolerance = the org's own cycle-count tolerance if visible, else 5%.

### Output sheets & tab order (left to right)
`INV_Exceptions` (first), `Exception_Register` (every exception, ranked), `INV_Onhand`,
`Interface_Errors`, `Cycle_Pending` (last).

## Pipeline
1. **Extract — DELEGATE.** br-run-reports runs the three reports → `INV_Onhand`,
   `Interface_Errors`, `Cycle_Pending`. Wait for each. **On-hand can be large** — pass the
   subinventory filter when the user gave one, and if the org is huge, ask before a wide-open pull.
2. **Anchor.** Record: negative-row count and total negative units/$ by subinventory; interface
   error count by source and age; pending-count rows and oldest age. All zero → a clean one-line
   verdict, no register needed.
3. **Classify  *(single `execute_office_js` call)*.** Build `Exception_Register` in memory — one
   row per exception: class, org, subinventory/source, item, quantity/$, age, recommended owner and
   fix per CONFIG — sorted Critical → High → Review, $ descending inside a class. Write in one
   `.values =` call.
4. **Dashboard *(single call; charts second)*** (delegate to br-data-dashboard if it fires; else
   inline). KPI cards per class, exceptions-by-subinventory and by-age charts, top-10 by $ table
   linking to the register. NEW sheet at **position 0**; do NOT rename the report sheets; no
   multi-row `copyToRange`; clear strays; widen amount columns.
5. **Narrative.** ≤5 bullets: worst exception, systemic pattern if any (one subinventory, one error
   source), recommended first fix.
6. **Arrange tabs + final validation.** Order per CONFIG; `INV_Exceptions` active. **One permitted
   verification read:** register class counts tie to the Step-2 anchor.

## Validation
Register ties to raw sheets; Critical only where CONFIG says so; an unassessable source (report not
found / module absent) is shown as "not assessed", never silently skipped.

## Add-on: slow movers & obsolescence (OPT-IN — extra extract, offer once before Step 1)
Costs one extra report run, answers a different question ("what should we stop stocking"), so it
runs only when the request implies it ("slow movers", "obsolete stock", "dead inventory") or the
user says yes to a single up-front offer. Never re-ask mid-pipeline.
- **Extract** `INV Transaction Historical Summary` (org, trailing 12 months, issues/usage view)
  alongside the standard pulls.
- **Classify** items carrying on-hand value: **DEAD** (no issues in 12 months), **SLOW** (issues in
  fewer than 3 of 12 months — CONFIG, label it), each with months-since-last-issue and on-hand $.
- **Disposition candidates** ranked by value: use-up / transfer / write-down review — always
  "review candidate", never "write this off" (disposition is the customer's policy call).
- Adds a `Slow_Movers` sheet before `Cycle_Pending` and a dashboard section; both degrade cleanly
  when the add-on didn't run (no `#REF!` placeholders).
- A DEAD item with recent RECEIPTS but no issues is its own callout — buying what nobody consumes.

## Closed-loop (roadmap, not executed here)
Corrections route through the shipped INV uploads (item, subinventory, physical inventory) and the
standard resubmit flows. This skill triages; a human fixes. Slow-mover stock-parameter fixes
(min/max, safety stock) belong to **br-inv-stock-optimizer**, which owns that gated write.
