---
name: br-data-dashboard
description: Build an interactive dashboard on top of any tabular data sheet — KPI cards, charts, and slicers — without modifying the source columns. Use when the user asks for a dashboard, demo view, or interactive summary built from an existing data table or pivot.
---

## When to use

Trigger when the user asks to:
- "Build a dashboard" / "make a dashboard" on top of existing data
- Create a "demo view", "interactive summary", or "filterable view"
- Add KPIs, charts, and slicers around a flat data table or pivot
- Showcase a tool's ability to regenerate / re-filter data live

Do NOT trigger for: simple one-off charts, single pivot table requests, or formatting-only tasks.

## Hard constraints (always)

- **Never add, rename, or delete columns** on the source data sheet. The only structural change allowed is wrapping the existing range as an Excel Table.
- **Never modify existing pivot sheets** the user has already built. Build alongside them.
- The dashboard must remain **live** — slicer selections should update KPIs and charts together.

## Workflow

### Step 1 — Inspect the data
Read the first few rows of the source sheet with `get_cell_ranges` (headers + 3-5 data rows). Identify:
- A numeric measure column (e.g. Amount, Revenue, Sales) — primary KPI
- A quantity / count column if present
- 3-4 categorical columns suitable for slicing (Customer, Product, Store, Status, Region, Category)
- A date column if present (for time-series chart)

**Done when:** you know the table name candidate, the measure column, and the slice dimensions.

### Step 2 — Confirm scope (only if ambiguous)
If the data has many candidate dimensions or no obvious measure, use `ask_user_question` with two short questions max: dashboard scope (full vs minimal) and location (new sheet vs existing). Skip if the request is clear.

### Step 3 — Convert source to Excel Table
Slicers require a Table. Wrap the source used range as a Table named `tblOrders` (or `tbl<DataName>`). If a table already exists, just rename it. Apply `TableStyleMedium2`.

```js
const used = src.getUsedRange();
used.load("address");
await context.sync();
const tables = src.tables;
tables.load("items/name");
await context.sync();
let tbl = tables.items[0] || src.tables.add(used.address, true);
tbl.name = "tblOrders";
tbl.style = "TableStyleMedium2";
```

**Done when:** the table exists and is named.

### Step 4 — Create Dashboard sheet
Add a new sheet named `Dashboard`. If one exists, delete and recreate. Do NOT set `position` via the property (it errors); use `Excel.WorksheetPositionType` if needed, or leave at end.

**Done when:** Dashboard sheet exists and is active.

### Step 5 — Title bar, subtitle band, KPI cards

**Layout (top to bottom):**
- Row 2 (height 36): title — merged B2:N2, large bold white on dark blue (#1F4E78)
- Row 3 (height 40): **subtitle / spacer band** — optional merged B3:N3 subtitle text, or leave empty for breathing room below the title
- Row 4 (height 8): spacer
- Row 5 (height 24): KPI headers — 4 cards across [B:I], each merged across 2 columns (B5:C5, D5:E5, F5:G5, H5:I5), white bold on #2E75B6
- Row 6 (height 40): KPI values — large bold #1F4E78, thin #1F4E78 borders around each card

KPI formulas use `SUBTOTAL` over `tblOrders[<column>]` so they respect slicer filters:
- Total measure: `=SUBTOTAL(9, tblOrders[Amount])` — currency format
- Total rows: `=SUBTOTAL(3, tblOrders[<id column>])` — integer
- Total quantity: `=SUBTOTAL(9, tblOrders[Quantity])` — integer
- Average unit metric: `=SUBTOTAL(1, tblOrders[Unit Price])` — 2-decimal currency

**Done when:** all 4 KPIs return numbers (not errors) — verify via `formula_results`.

### Step 6 — Build pivot tables on a hidden helper sheet
Create a sheet `_PivotData`. Build 4 pivots **using the table name as source** (`"tblOrders"`) so they share the slicer cache:
- `pvtCustomer` at A1: rows = primary entity (Customer), values = sum of measure
- `pvtProduct` at E1: rows = secondary entity (Product), values = sum of measure
- `pvtStore` at I1: rows = location/store, values = sum of measure + sum of quantity
- `pvtStatus` at M1: rows = status, values = count of id

Sort `pvtCustomer` and `pvtProduct` descending by the data hierarchy.

**Done when:** all 4 pivots have populated address ranges — load `layout.getRange().address` to verify.

### Step 7 — Add charts on Dashboard
Anchor charts via `setPosition("topLeftCell", "bottomRightCell")`:
- Chart 1 (BarStacked or BarClustered) — Revenue by Customer, source = pvtCustomer range
- Chart 2 (BarClustered) — Top N Products by Revenue, source = first 15-16 rows of pvtProduct
- Chart 3 (ColumnClustered) — Revenue & Quantity by Store, source = pvtStore
- Chart 4 (Doughnut) — Orders by Status, source = pvtStatus

Hide legend on single-series charts. Bold 12pt titles. Place in a 2x2 grid below KPIs (e.g. B8:G24, H8:N24, B25:G40, H25:N40).

**Done when:** 4 charts render with titles.

### Step 8 — Add slicers
Use `workbook.slicers.add(table, "<Column Name>", dashboardSheet)`. Slicers attached to the table propagate to:
- The table's `SUBTOTAL` formulas (KPIs)
- Any pivot built from the table (charts)

Add 4 slicers for the categorical columns identified in step 1. Set `name`, `caption`, then position via `left`, `top`, `width`, `height` properties. Place along the right side of the dashboard.

**Done when:** clicking a slicer tile updates KPIs AND charts together.

### Step 9 — Polish
- Set column widths (~75pt for content columns, narrow 12pt gutters)
- Confirm row heights: title 36, subtitle/spacer band 40, KPI header 24, KPI value 40
- Add thin border around each KPI card
- `dash.gridlines = false`
- Hide the `_PivotData` helper sheet: `helper.visibility = Excel.SheetVisibility.hidden`

**Done when:** Dashboard sheet is clean, gridlines off, helper hidden.

### Step 10 — Verify and report
- Activate Dashboard sheet
- Read back KPI values to confirm they're not errors
- Tell the user: where the dashboard is, what the slicers do, and that the source columns are unchanged

## Common gotchas

- `worksheet.position = N` throws — don't set it via the property. Add the sheet, accept default position, or use `WorksheetPositionType` enum on `add()`.
- Pivot tables sourced from a **range** ('Sheet'!A1:O100) do NOT share the slicer cache — slicers won't filter them. Always source pivots from the **table name** (`"tblOrders"`).
- Table slicers (`workbook.slicers.add(table, ...)`) filter the table; pivot slicers filter only one pivot. Use table-based slicers so KPIs + pivots all respond.
- Loading `pivotTable.name` requires `load("items/name")` and a `sync` first. Same for any property read.
- Don't dump pivot data into chart calls — pass the pivot's `layout.getRange()` (or a sub-range like first 16 rows for "top N" charts).

## Customization notes for non-sales data

The skill above uses sales/orders terminology (Customer/Product/Store/Status) as the canonical example. For other domains, map to the same shape:
- HR data: Employee / Department / Location / Status, measure = Headcount or Salary
- Finance: Account / Cost Center / Period / Status, measure = Amount
- Inventory: SKU / Warehouse / Category / Status, measure = On-Hand or Value
- Tickets: Assignee / Priority / Team / Status, measure = Count or Hours

Pick whichever 4 categorical columns make the most natural slice dimensions, and the most meaningful numeric column as the primary KPI measure.
