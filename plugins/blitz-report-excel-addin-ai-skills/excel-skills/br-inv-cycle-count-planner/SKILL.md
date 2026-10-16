---
name: br-inv-cycle-count-planner
description: >
  Plan and steer Oracle EBS cycle counting: analyse count accuracy history, find never-counted and
  overdue items, recommend count priorities by value/velocity/accuracy (ABC-weighted), and surface
  the approval and adjustment backlog. Read-only — recommendations feed the customer's own cycle
  count scheduling in EBS. Use when the user asks what to count next, why inventory accuracy is
  slipping, which adjustments await approval, or wants a count program review.
# Trigger: Slash command + auto
---

# INV Cycle Count Planner (br-inv-cycle-count-planner)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.

> **Performance:** read `br-analytics-standards` at the start of every run. The ABC segmentation
> reuses the technique in `br-clustering` when the value/velocity classing runs.

## When to use
"What should we count next", "cycle count program review", "why is count accuracy slipping",
"what adjustments are waiting for approval", "which items never get counted". This skill is
**read-and-recommend only** — EBS's own cycle count scheduling generates the count requests; the
deliverable here is the prioritized recommendation and the health picture, not a write.

## Inputs
- **Organization Code** (required) — ask if not supplied.
- **Cycle count name** — if the org runs several, ask which (or analyse all and say so).
- *Optional:* lookback window for accuracy history (default 12 months, say so).

## Reports used (authoritative names — do NOT broad-search for them)
| Report (exact name) | Role |
|---|---|
| `INV Cycle count entries and adjustments` | count results + adjustment values — the accuracy record |
| `INV Cycle count hit/miss analysis` | accuracy rate by class — the trend spine |
| `INV Cycle count unscheduled items` | items in scope but never/not recently scheduled |
| `INV Cycle count open requests listing` | the open count backlog |
| `INV Cycle counts pending approval` | adjustments awaiting approval — the control breach risk |
| `INV Cycle count listing` | count definition scope/classes context |
| `INV Physical inventory accuracy analysis` | physical-inventory accuracy cross-check where PI is used |
| `INV Onhand Quantities` | value on hand per item — the value weighting |

Pass the exact names; fall back to a search only on `#BLITZ_REPORT_NOT_FOUND`.

## Workflow
1. **Extract** the accuracy history, unscheduled items, open requests, pending approvals and
   on-hand values (one call per report).
2. **Health picture**: hit rate trend, gross vs net adjustment value over the lookback, approval
   backlog age (pending adjustments distort on-hand until approved — call that out), and open-
   request aging (a stale open request blocks the item's next schedule).
3. **Coverage gaps**: unscheduled/never-counted items ranked by on-hand value; items whose last
   count is older than their class frequency implies.
4. **Recommend count priorities**: rank items by value at risk × historical miss rate × time since
   last count — ABC-weighted (A-class first). Deliverable = the prioritized "count next" list with
   the driver named per item ("high value, missed twice, 7 months uncounted"), sized to the org's
   evident weekly count capacity (derive from history; state the assumption).
5. **Dashboard** (br-data-dashboard): accuracy trend, adjustment value trend, coverage %, approval
   backlog.

## Hard rules
- Never present a pending adjustment as an accuracy result — it isn't one until approved.
- Accuracy is measured in both units and value; report the one that tells the worse story, show
  both.

## Degradation rules
- Org uses physical inventory only (no cycle counts) → say so, pivot to
  `INV Physical inventory accuracy analysis` as the accuracy record, skip the schedule-driven steps.
- Hit/miss report empty for the window → derive accuracy from entries-and-adjustments directly and
  say the derived basis.

## Talk in the user's language
Items, counts, adjustment dollars, approvals — never `br_*` functions or helper sheets.
