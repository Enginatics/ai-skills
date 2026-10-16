---
name: br-analytics-standards
description: >
  Shared performance and coding standards for all br_ analytics skills (br-ap-holds-analysis,
  br-ap-close-readiness, br-ar-close-readiness, br-gl-close-readiness,
  br-fa-close-readiness, br-inv-cost-close-readiness, br-ce-recon-readiness,
  br-subledger-gl-reconciliation, br-close-process-monitor, br-month-end-readiness).
  Read at the start of any br_ skill run via read_skill("br-analytics-standards").
---

# br_ Analytics Skills — Shared Performance Standards

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


Read this at the start of any br_ skill run. These rules override any conflicting
guidance in individual skill files.

## Why these rules exist
The main cause of slow runs (10–15 min) is too many sequential round-trips between the
model and Excel. Each `execute_office_js` or `set_cell_range` call has latency. The
target runtime for a single-module analysis is under 7 minutes; for a chained
orchestration (e.g. month-end readiness) under 20 minutes.

## Rule 1 — One call per step: read + compute + write in the same block
Every analytics step must read its source data, run all calculations, and write its output
sheet in a **single `execute_office_js` call**. Never issue a separate read call then a
separate write call for the same step.

❌ Wrong:
- Call 1: `get_cell_ranges` to read column values
- Call 2: `execute_office_js` to write the results

✅ Right:
- Call 1: `execute_office_js` that reads, computes, and writes in one JS block

## Rule 2 — All dashboard/scorecard sections in one call
All KPI cards, summary tables, charts-data, and narrative rows for a single output sheet
go into a **single `execute_office_js` call**. Do not use multiple `set_cell_range` calls
for different sections of the same sheet.

Exception: charts require a second call (separate API round-trip) — this is the one
permitted exception.

## Rule 3 — Skip mid-pipeline verification reads
Trust the `formula_results` field returned by `set_cell_range` — it shows computed formula
values and errors. Do NOT insert intermediate `get_cell_ranges` calls between pipeline
steps to check intermediate values. Only do one explicit re-read at the **final validation
step** of the pipeline.

## Rule 4 — Combine headers + seed formula + autoFill in one call
When adding derived columns to a source sheet, write all column headers, the seed formula
row, and call `autoFill` down to the last data row — all in a single `execute_office_js`
block. Do not spread these across separate `set_cell_range` calls.

## Rule 5 — Combine write-back with the step that computed it
Any column written back to a source sheet (e.g. a Cluster label, a Flag column, a
Category code) must be populated in the **same JS call** that computed the value — not in
a follow-up call.

## Rule 6 — Bulk write all narrative cells in one call
All recommendation bullets, insight text, and status labels for a single sheet go into a
**single `set_cell_range` call** (or included in the single `execute_office_js` call for
that sheet). Do not call `set_cell_range` once per bullet or once per row.

## Rule 7 — Anchor before analysis; reconcile at the end
Before any analytics step: capture the row count and a SUM of the key amount column as
the reconciliation anchor. At the final validation step: confirm the dashboard/scorecard
total equals the anchor. This is the one permitted verification read outside of Step 1b.

## Rule 8 — Chained orchestrations: each sub-skill follows these rules independently
When a master skill (e.g. `br-month-end-readiness`) delegates to sub-skills
(e.g. `br-ap-close-readiness`), each sub-skill must follow these rules within its own
pipeline. The orchestrator must not insert extra read calls between sub-skill invocations
to inspect their output — read the return values from the sub-skill's final JS call instead.

## Quick reference — permitted call counts per pipeline step

| Step type | Max calls |
|---|---|
| Extract (br-run-reports delegation) | As needed by br-run-reports |
| Anchor (rename + row count + SUM) | 1 × execute_office_js |
| Add derived columns to source sheet | 1 × execute_office_js |
| Anomaly / clustering / RFM / forecast | 1 × execute_office_js |
| Output sheet data (scorecard/dashboard) | 1 × execute_office_js |
| Charts on output sheet | 1 × execute_office_js (separate, permitted) |
| Narrative/recommendation bullets | 1 × set_cell_range |
| Tab reorder + final validation | 1 × execute_office_js + 1 read |

## Excel correctness — bake these in UPFRONT (each caused a mid-run debug loop + re-run)
These are not speed rules, but each one cost multiple diagnosis/re-run passes on a real run
(that's how a target-7-minute job became 30). Handle them in the FIRST write of every step,
not after you discover the symptom.

1. **Never apply Text ("@") number format to a cell that holds a FORMULA.** It turns the
   formula into a literal string that never evaluates (symptom seen: all COUNTIF aging counts
   came back 0). Apply "@" ONLY to literal data/label cells that must stay verbatim — never to
   a formula range — and set the format BEFORE writing the value.

2. **Force literal labels that Excel could coerce — to text.** Values like an aging bucket
   `"8-30"`, a period `"Feb-09"`, or a range `"1000-1999"` are parsed by the workbook's locale
   (US: setting a cell `.values = "8-30"` becomes the 30-Aug date serial, zeroing the data
   underneath). Write such labels as text: prefix with an apostrophe (`'8-30`) OR pre-set those
   *label* cells (not formula cells, per #1) to "@" before writing — or use an unambiguous form
   (`"8–30 days"`).

3. **Classify from the ACTUAL source value, including literal sentinels.** When you derive a
   category/flag from a column, test the real value — do not assume "non-empty = a person /
   the normal case". (Symptom seen: a `Held By` column contains the literal text "System", so a
   "any value in Held By means a person → Manual" rule misclassified all 460 rows and forced a
   k-means re-run.) Enumerate the real values first; handle the sentinel/blank cases explicitly.

4. **Sanitize every string cell that Excel will parse as a FORMULA before writing it.** A string
   whose value begins with `=`, `+`, `-`, or `@` (e.g. an invoice number `"=-"`, a code `"+A1"`,
   `"@dept"`) is interpreted as a formula, and one bad value makes the **whole** `Range.values` write
   throw a `GeneralException` / `InvalidArgument`. Because the write is one big array, the error names
   no row — so you waste several round-trips binary-searching for the offender (symptom seen: invoice
   number `"=-"` on row 103 forced a 4-call binary search). Bake it into the FIRST write: map every
   string cell through `v => (typeof v === "string" && /^[=+\-@]/.test(v)) ? "'" + v : v`
   (apostrophe-prefix forces a text literal), AND pre-set any id / key / invoice-number / code column
   to text format (`range.numberFormat = "@"`) so values like `"=-"`, `"001234"`, `"1E5"` store
   verbatim. Never discover this from the symptom.

5. **Compute and WRITE in separate calls when the source range is big — never load the whole used
   range into the write call.** Reading a large used range (1400+ rows × 50+ cols) into JS *and*
   writing the result in the same call hits the office-js memory ceiling and throws a
   `GeneralException` at `Range.values` with no useful location (symptom seen: two failed 1478×52
   single-call attempts). For a big extract this is the one place Rule 1 yields: **call 1** reads only
   the specific columns you need (not `usedRange.values`), computes, and stashes the result array with
   `blobs.setJSON("<key>", result)`; **call 2** reads it back with `blobs.getJSON("<key>")` and does a
   single full-range `.values =` write — not row-by-row, not chunk-and-sync. Set the autofilter with
   `sheet.autoFilter.apply(headerRange)` — `range.autoFilter()` is not a function and throws. Set
   column widths in the same write so amounts never render `######`.

6. **Get-or-create a sheet with `getItemOrNullObject` — NEVER `getItem` inside a try/catch.** office-js
   defers `worksheets.getItem("X")`'s `ItemNotFound` to `context.sync()`, *after* the catch block — so
   `try { ws = sheets.getItem("X"); ws.getUsedRange().clear(...); } catch { ws = sheets.add("X"); }`
   does **not** catch the missing-sheet case; the whole call throws `ItemNotFound` at
   `WorksheetCollection.getItem` and wastes a retry (symptom seen: `blitz_` and `Dup_Candidates`
   creation each failed once this way in the same run). Always:
   `const ws = ctx.workbook.worksheets.getItemOrNullObject("X"); ws.load("isNullObject"); await ctx.sync();`
   then `const sheet = ws.isNullObject ? ctx.workbook.worksheets.add("X") : ws;` (clear `sheet` if it
   was reused). Same rule for any get-or-create of a chart / name / table: use the `*OrNullObject`
   variant + `load("isNullObject")`, never a try/catch around the throwing getter. (Generic office-js
   discipline the same runs also slipped on, FYI: **assign a range to a variable, `load()` it, `await
   ctx.sync()`, then read from that SAME variable — never re-call `sheet.getRange("A1")` for the read.
   Each `getRange()` returns a fresh, un-loaded proxy, so loading one and reading another throws
   `PropertyNotLoaded` at `Range.values`** — this cost ~5 retries in one run. Also: when writing a 2-D
   array, the array shape must match the target range exactly (`[[v]]` → a 1×1 cell, not a 1×N range);
   and validate a `getRange("A1:..")` address is non-empty before adding a chart from it.)

7. **Building a chart: let `charts.add` create the series; recolor by loading `series.items` — never
   `series.add()`, and `numberFormat` belongs on a RANGE, not a chart.** Two chart-styling slips cost
   retries in a real run: (a) calling `chart.series.add()` to inject a series manually throws — instead
   create the chart from the data range in one shot (`const ch = sheet.charts.add(Excel.ChartType.columnClustered,
   sheet.getRange("K15:L20"), Excel.ChartSeriesBy.columns)`), which builds the series for you; to recolor,
   `ch.series.load("items"); await ctx.sync();` then `ch.series.items[i].format.fill.setSolidColor("#2E75B6")`.
   (b) `numberFormat` is a **Range** property — set it on the source cells *before* charting
   (`range.numberFormat = "$#,##0"`, a single string for the whole range — not a shape-mismatched 2-D
   array, per #6); to format a chart's axis use `ch.axes.valueAxis.numberFormat = "$#,##0"`, never
   `Range.numberFormat` on the chart object. Keep the chart call minimal — title + position + one
   `setSolidColor` per series — and do it in the **second** (charts-only) `execute_office_js` call.

8. **A date read via `range.values` is a SERIAL NUMBER — keep it a real date by applying a date
   `numberFormat` on every date column you write to a derived sheet.** office-js `range.values` returns
   a date cell's underlying **serial** (e.g. `39814`), NOT the formatted text — the source sheet's date
   *format* does not travel with `.values`. (And `.values` is the *right* thing to read: the analytics
   needs the serial for date math — `date2 − date1` for a "within N days" rule — so do NOT switch to
   `.text`.) The miss is purely on the **write**: when you write that serial into your `Dup_Candidates`
   / `Worklist` / `Pay_Schedule` / dashboard sheet, apply a date number-format to those columns exactly
   like you format the amount columns — `sheet.getRange("H2:H<last>").numberFormat = "dd-mmm-yyyy"`
   (single string for the whole column, per #6) — so it renders as a real, sortable Excel date instead
   of `39814`. (Symptom seen: `Dup_Candidates` `Invoice Date A/B` showed raw serials because the write
   formatted the `$` columns but not the date columns.) Pass the serial through unchanged — do not
   convert to a string; the date-format makes it a true date the user can sort and filter.
   **🚨 Do NOT "solve" the serial display by stringifying it** with a `formatDate()` helper that emits
   `"13-Mar-2009"` — a live run did exactly that and the dates can no longer sort or filter as dates
   (text, not a date). Keep the serial in the array; format the column. Canonical pattern (the whole
   fix is one extra line per date column):
   ```js
   // write the RAW serials (not strings) ...
   sheet.getRange(`H2:H${lastRow}`).values = dateSerials;          // [[39885],[40179],...]
   // ... then format the column so they render as real dates:
   sheet.getRange(`H2:H${lastRow}`).numberFormat = "dd-mmm-yyyy";  // one string for the whole column
   ```
