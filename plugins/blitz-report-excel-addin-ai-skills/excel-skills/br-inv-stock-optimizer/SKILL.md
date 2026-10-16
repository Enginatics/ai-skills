---
name: br-inv-stock-optimizer
description: >
  Recommend min/max quantities, reorder points and safety stock per item and subinventory in Oracle
  EBS from actual demand history and on-hand position — then, only on explicit user confirmation,
  apply the approved recommendations back to EBS via the INV Item Subinventory Upload or INV Safety
  Stock Upload. Use when the user asks to optimize stock levels, review min/max settings, right-size
  safety stock, reduce excess inventory, or fix reorder points. WRITES to Oracle EBS (optional,
  gated).
# Trigger: Slash command + auto
---

# INV Stock Level Optimizer (br-inv-stock-optimizer)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.

> **Performance:** read `br-analytics-standards` at the start of every run. For the optional apply
> step, **read `br-run-uploads` FIRST** — it owns the upload mechanics; this skill only adds what is
> specific to stock parameters.

## When to use
"Optimize our min/max settings", "are our reorder points right", "right-size safety stock",
"which items are over-stocked / under-stocked", "review replenishment parameters for org X".
For day-to-day inventory exceptions (negative on-hand, stuck transactions) use
**br-inv-exception-triage** instead; for demand forecasting alone use **br-forecasting**.

## Inputs
- **Organization Code** (required) — ask if not supplied.
- **Lookback window** — default 12 months of demand history; say so and let the user change it.
- *Optional:* Subinventory, item category/range, service-level target (see CONFIG).

## Reports and uploads used (authoritative names — do NOT broad-search for them)
| Name | Type | Role |
|---|---|---|
| `INV Item Demand History` | Report | demand per item per period — the consumption baseline |
| `INV Onhand Quantities` | Report | current position per item/subinventory |
| `INV Safety Stocks` | Report | current safety-stock settings to compare against |
| `INV Transaction Historical Summary` | Report | issue/receipt velocity cross-check |
| `INV Item Subinventory Upload` | Upload | **write path** for min/max and reorder-point changes |
| `INV Safety Stock Upload` | Upload | **write path** for safety-stock changes |

Pass these exact names; only fall back to a name search on `#BLITZ_REPORT_NOT_FOUND`.
There is no shipped generic min-max listing report — current min/max values come back on the
`INV Item Subinventory Upload` download grid itself (run it in Create, Update mode), which is also
what makes the apply step safe: you edit only the rows you propose.

## Workflow
1. **Extract** demand history, on-hand and current safety stocks for the org (one call per report,
   per br-analytics-standards batching).
2. **Profile each item**: average and variability of period demand (mean, coefficient of variation),
   lead-time assumption (see CONFIG), current on-hand vs current min/max/safety stock.
3. **Recommend** per item-subinventory: suggested min, max, reorder point and safety stock, each with
   the driver stated in plain language ("demand doubled since the setting was last right",
   "9 months of zero demand — candidate to cut to zero"). Classify: RAISE / LOWER / LEAVE /
   NO-DATA (never guess where history is too thin — say so).
4. **Quantify** the working-capital effect: excess units × item cost where the recommendation lowers
   stock; exposure where it raises. Present as a ranked sheet + dashboard (br-data-dashboard).
5. **Apply (optional, gated)** — only when the user explicitly asks to apply: download the
   `INV Item Subinventory Upload` (or `INV Safety Stock Upload` for safety stock) for the org, fill
   ONLY the approved rows' min/max/reorder columns, validate, show the user exactly what will change
   (item count + before/after values), and submit only on their second explicit confirmation.
   Untouched rows are inert. Never mix the two uploads in one confirmation.

## CONFIG — placeholder policy, label it as such
Service level (default 95%), lead-time days (default: ask, or use a stated assumption and LABEL it),
and the zero-demand cut threshold (default 9 months) are PLACEHOLDERS until the customer states
policy. Every recommendation sheet must carry a visible note naming the assumptions used.

## Degradation rules
- No demand history for an item → NO-DATA class, never a recommendation.
- `INV Item Demand History` empty for the org (demand history not compiled) → fall back to
  `INV Transaction Historical Summary` issues as the consumption proxy and say so.
- The user declines the apply step → the recommendation sheet IS the deliverable; never nag.

## Talk in the user's language
Say "apply the approved stock settings to Oracle" — never name `br_*` functions, the `blitz_`
sheet or trigger cells. Ask about the ACTION: "Apply new min/max to 34 items in M1 —
lowering stock value by ~$210k?"
