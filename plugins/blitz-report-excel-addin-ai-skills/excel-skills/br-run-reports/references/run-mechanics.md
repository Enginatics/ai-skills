# br-run-reports — full run mechanics

# Run Blitz Reports in Excel

## 🚨 Blitz data comes from WORKSHEET UDFs — never from tools or connectors (read this first)

The `br_*` functions are **Excel worksheet functions (UDFs)** provided by the Blitz Report **Excel add-in** (the "Blitz Report" ribbon in Excel). Use them by **writing `=br_...()` into a cell** (via `execute_office_js` / `set_cell_range`) and reading the spilled result. They are the **only** way to pull Oracle EBS data here.

They are **NOT** MCP tools and **NOT** an MCP connector. So whenever you need Blitz data you must **never**:
- `tool_search` / look in the tool list for `br_*` — they are worksheet functions and will never appear as tools;
- call `refresh_mcp_connectors`, or look for / ask the user to add an "Oracle EBS" or "Blitz" connector — the add-in is an Excel add-in, not a connector, so it will **never** appear in the connector list, and its absence there is **expected**;
- conclude "the data source isn't connected" or "no connector is set up".

**Your first extraction action is always to write a `br_` UDF into a cell** (e.g. `=br_report_list_external("...")`, `=br_run_report_external(...)`). The only genuine "unavailable" signals are a `br_` UDF **returning** `#BLITZ_NOT_CONNECTED` (add-in loaded — the user picks an environment on the Blitz Report ribbon) or `#NAME?` (add-in not installed). A missing MCP connector is **never** a blocker.


You can run Oracle EBS **Blitz Reports** directly in this workbook through the custom add-in
functions below. You handle the language, discovery, and analysis; the Blitz Report add-in handles
authentication, execution, and deterministic full-fidelity cell population.

The Blitz Report add-in must be loaded and **connected to an environment** (the user does this once
via the Blitz Report ribbon). If a function returns `#BLITZ_NOT_CONNECTED`, ask the user to open the
Blitz Report ribbon and connect first.

## Choosing the environment and responsibility (optional)
The add-in can be connected to **several environments**, each with **several responsibilities**.
Every discovery/run function below takes an optional trailing **`environment`** and
**`responsibility`** argument; omit them to use whatever the add-in is currently on.
- See what's available: `=br_environments_external()` → `Environment | Connected | Current | URL`,
  and `=br_responsibilities_external("<Environment>")` → `Responsibility | Current`.
- Only environments showing **`Connected = Yes`** can be targeted — a UDF cannot log in. If the user
  names one that isn't connected (you get `#BLITZ_ENV_NOT_CONNECTED`), ask them to select it under
  Environments on the Blitz Report ribbon, which logs them in to it. `#BLITZ_RESP_NOT_FOUND` means that responsibility isn't available in
  the chosen environment — list them with `br_responsibilities_external` and pick a valid one.
- Selection is **sticky**: passing `environment`/`responsibility` switches the session to it for that
  call and subsequent calls, so you can set it once (e.g. on the run) or repeat it on each call.
- When the user names an environment/responsibility, pass the SAME values to the parameter-inspection
  AND the run, so the parameters/LOVs you see match where the report will actually run.

## Keep the workbook tidy — use a throwaway helper sheet
Do all discovery (`br_report_list_external`, `br_report_params_external`), the run trigger, the
status check, and any intermediate/helper formulas on a dedicated helper sheet named
**`blitz_`** (create it if it doesn't exist). Read the values you need from it, then
**delete `blitz_` when you're done** so the user's workbook stays clean.
- You must read a spill **while the sheet is visible** — so clean up *afterwards*, not before. (A
  permanently hidden sheet can't be read, which is why we delete rather than hide.)
- **Talk to the user in their language, never in function names.** The `br_*` functions, `blitz_`
  and `_blitz_run_status` are your plumbing — say "I'm running the AR Aging report for you", not
  "I'll call `br_run_report_external()` and poll `_blitz_run_status`". Report and column names are
  fine; the add-in's internals stay behind the curtain.
- **Visible does NOT mean active — never call `activate()` on `blitz_`.** Writing formulas to it and
  reading them back works perfectly well while the user stays on their own sheet; activating it just
  drops the user onto a scratch sheet. Leave the user's report/upload sheet active throughout.
- The report DATA lands on its **own new sheet** created by `br_run_report_external` — leave that
  visible; that's the deliverable.
- Keep the user's original/active sheet untouched, and present findings in the chat.

## Workflow — always follow these steps in order

### Fast path — when you already know the exact report name
If a calling skill or the user gives you the **exact** report name (e.g. "AP Period Close
Exceptions"), **skip Step 1 (discovery)** — do not run `br_report_list_external`. Go straight to
Step 3 (run) with that name (inspect params via Step 2 only if you need an exact LOV value). The run
function validates the name server-side, so a wrong name just returns `#BLITZ_REPORT_NOT_FOUND`
instantly without executing anything. **Only on that error** fall back to Step 1 to find the closest
matching name, then re-run. Step 1 below is for when you do NOT already have the name.

1. **Find the report.** On the `blitz_` helper sheet, in an empty cell write:
   `=br_report_list_external("<search words>")`
   It spills a table: `Report Name | Category | Type | Description`. Read it and choose the exact
   `Report Name`. (Search matches both name and description, so refine if too broad.)

2. **Inspect its parameters.** On `blitz_`, in an empty cell write:
   `=br_report_params_external("<Report Name>")`
   It spills: `Parameter | Type | Required | Must Set? | Multiple | Default | Has LOV | Depends On | Description`.
   - The **`Must Set?`** column is the authority on what you must provide (`Yes` = required with no
     server default at all). **Set every `Must Set? = Yes` parameter; treat everything else as
     optional** — the run fills defaults automatically, including ones the `Default` column shows as
     **blank**. A blank `Default` does NOT mean "no default": many defaults are computed at run from
     other values (e.g. `Ledger Currency` is derived from the ledger → `USD`; a ledger id is derived
     from the ledger name). If `Must Set? = ""`, omit it and let the server compute it — do not try
     to guess or enumerate it. So a `Must Set?=Yes` whose LOV returns no rows is the *only* case you
     should ask the user about; a `Must Set?=""` empty LOV just means "leave it to the server".
   - **A non-empty `Default` is applied when you omit the parameter.** E.g. if `Ledger` shows a
     default of `Vision Operations (USA)`, omitting it runs for *that* ledger — not "all ledgers".
     To scope differently (a specific value, or to broaden), set the parameter explicitly.
   - Also set any other parameters you want to filter or restrict on.
   - `Multiple = Y` means the parameter accepts a list (comma-separated values).
   - **Dependencies (`Depends On`):** a dependent parameter's valid values depend on its parent(s).
     Both the run and `br_param_values_external` **auto-apply the parent's default**, so by default a
     dependent LOV resolves under the default parent (e.g. `Period` under the default `Ledger`) — you
     do NOT have to pass the parent. To scope to a *different* parent, set that parent explicitly in
     the run, and pass it to the values lookup so the list is filtered to it:
     `=br_param_values_external("<Report Name>","<Parameter>","<Parent=Value; …>")`
     → spills `Value | ID | Description`; pass the chosen `Value` to the run.
   - You usually don't need to enumerate a parameter's values just to set it — common formats are
     obvious (periods are `Mon-YY` e.g. `Jan-08`, dates `YYYY-MM-DD`). **If the user already gave you
     the value (e.g. they said "Jan-08"), just use it — do not look it up.** Use
     `br_param_values_external` only when you need the exact spelling of an LOV value you don't know.
   - **An empty or erroring `br_param_values_external` is NOT a blocker — never abort the run over
     it.** Some `Must Set?=Yes` LOVs (e.g. `Period` on GL ledger reports) are computed at **run time**
     from values not yet resolved during a standalone lookup (a hidden ledger id), so the lookup
     returns nothing even though the report runs fine. When a lookup is empty/errors: use the value
     you already have (or the obvious format), run the report, and let the server validate it. Only
     ask the user when it's a `Must Set?=Yes` value you genuinely cannot infer **and** the lookup
     gave you nothing. Put each lookup in its **own clear cell with empty space below/right** so the
     spilled list doesn't collide (`#SPILL!`) with other helper formulas.

3. **Run it.** On `blitz_`, in an empty cell write:
   `=br_run_report_external("<Report Name>","<params>")`
   - To run against a specific environment/responsibility, add them as trailing args:
     `=br_run_report_external("<Report Name>","<params>","<template or blank>","<Environment>","<Responsibility>")`
   - `params` format: `"Name=Value; Name2=A,B,C"` — `;` separates parameters, `,` separates
     multiple values for one parameter. Dates as `YYYY-MM-DD`.
   - **Templates control the column set.** `=br_report_templates_external("<Report Name>")` lists them
     (`Template | Default? | Description`). Pass the exact name as the 3rd argument when the user asks
     for a specific layout; if several plausibly match their wording, ask rather than guess. Omit it
     and the report runs with its **default** template (the `Default?` = `Yes` row), same as the
     ribbon — pass a template explicitly if you need a different column set.
   - The cell returns `BLITZ_RUNNING: ...`. The add-in authenticates, runs the report, and creates a
     **new sheet** named after the report, populated with the data.
   - **Write the run formula and read its `BLITZ_RUNNING` return in the SAME operation batch, then
     immediately replace that formula cell's content with a plain text note (or clear it) in your
     next operation.** A separate read of the still-present formula can itself force a second
     evaluation — i.e. start a *duplicate* run — before your replace lands (seen live: the ghost
     run collided with the finished one and popped an add-in error dialog after the data had
     already landed; the data was complete). Then poll only `_blitz_run_status` (a workbook name —
     independent of the cell); never re-read or re-enter the run formula to check progress.

4. **Wait for completion — patiently, with minimal workbook activity.** On `blitz_`, read the
   workbook name with a formula: `=_blitz_run_status` → `RUNNING: ...`, then `DONE: <n> rows on
   sheet '<sheet name>'`, or `ERROR: <message>`.
   - **A status value that predates YOUR run is STALE — never act on it.** `_blitz_run_status`
     persists in the workbook across runs and sessions, so an `ERROR:` (including the bare
     `ERROR: ERROR`) read BEFORE you have triggered anything is leftover from an earlier run —
     it is not a reason to abort, retry, adapt parameters, or report failure. Start your run;
     the add-in overwrites the name with `RUNNING:` at trigger time, and only values that
     appear after that belong to you.
   - The add-in writes the result sheet in a background step (`Sheets.Add` + bulk write). Other
     workbook operations issued while it is writing can conflict with it and make the write fail
     (Excel error 1004) — the sheet then never appears and the status name is never published, so
     polling only ever shows `#NAME?`. **After triggering the run, pause your other workbook
     edits:** do ONE lightweight status check, then wait. Space the checks out generously.
   - Timer functions are not available to you here, so never wait inside a single call — do one
     quick check per turn and let the natural gap between turns give the write a clean window.
   - A **missing name / `#NAME?`** early just means the status isn't published yet — keep waiting.
   - **If it seems stuck:** when after a few patient checks there is still **no new report sheet**
     AND the status is missing/`#NAME?`, the background write likely failed. **Run the report once
     more** (the one exception to "never run a report twice" — it applies only because NO data
     sheet was created), then check once and wait. If it still never lands, explain to the user
     that the add-in's background write and this automation can interfere (a known add-in
     limitation) rather than polling forever.
   Wait until it says `DONE` before reading results.

5. **Analyze.** Open the new sheet and read the data. **The sheet layout is fixed and
   deterministic — do not probe for it:**
   - **Row 1** = a title/info banner (the report name and the run formula) — *not* data, *not* headers.
   - **Row 2** = the column headers.
   - **Row 3 onward** = the data rows, starting at column A.

   So read headers from **row 2** and data from **row 3 down**; never treat row 1 as the header row.
   Then answer the user's question (summaries, top-N, totals, trends, anomalies, etc.). Never
   fabricate values — read them from the sheet.

## Rules
- Use report and parameter names **exactly** as returned by the discovery functions (or exactly as a calling skill supplied them).
- Only pass parameters you have values for; respect `Required`.
- `#BLITZ_NOT_CONNECTED` → tell the user to open the Blitz Report ribbon and connect to an environment first.
- `#BLITZ_REPORT_NOT_FOUND` → the name didn't match; re-check with `br_report_list_external` (this is the fast-path fallback — search for the closest matching name, then re-run).
- `#BLITZ_ENV_NOT_CONNECTED` / `#BLITZ_ENV_NOT_FOUND` → the named environment isn't connected/known; the add-in can't log in from a formula, so ask the user to select it under Environments on the Blitz Report ribbon (check `br_environments_external()`).
- `#BLITZ_RESP_NOT_FOUND` → that responsibility isn't available in the chosen environment; pick one from `br_responsibilities_external("<Environment>")`.
- `_blitz_run_status` = `ERROR: ...` → report the message to the user; do not invent data. In
  particular `ERROR: Please set required parameter(s): X` means a mandatory parameter with no default
  was omitted — set it (use `br_param_values_external` for its valid values) and run again.
- **Never re-run a report that already produced a data sheet.** A second `br_run_report_external` call
  (or a recalc of the formula cell) creates a duplicate `<Report> (1)` sheet and can collide with the
  first run. If `_blitz_run_status` shows `ERROR:` **but a new sheet with data rows exists**, the data
  populated and the error is only in post-processing — **use that data, note the warning, and do NOT
  re-run.** Treat `ERROR:` as a true failure only when no populated sheet was created.
- A report can return many rows; read what you need for the analysis rather than echoing the whole sheet.

## Worked example
User: "Show me the slowest concurrent programs from the last day."
1. `=br_report_list_external("concurrent requests")` → choose `FND Concurrent Requests`.
2. `=br_report_params_external("FND Concurrent Requests")` → note `Started within Days` (Number).
3. `=br_run_report_external("FND Concurrent Requests","Started within Days=1")` → a new sheet appears.
4. `=_blitz_run_status` → `DONE: <n> rows on sheet 'FND Concurrent Requests'`.
5. Open that sheet, sort by the run-duration column, and report the slowest programs.

## Multi-value / date example
`=br_run_report_external("AR Aging","Operating Unit=Vision Operations; As of Date=2012-12-31; Phase=Completed,Running")`
- `Operating Unit` = single value; `As of Date` = ISO date; `Phase` = two values (multi-value).

## The functions (reference)
| Function | Purpose | Returns |
|---|---|---|
| `br_environments_external()` | list connected environments | spilled table: Environment, Connected, Current, URL |
| `br_responsibilities_external([environment])` | list responsibilities in an environment (current if omitted) | spilled table: Responsibility, Current |
| `br_report_list_external([search], [environment], [responsibility])` | discover reports | spilled table: Report Name, Category, Type, Description |
| `br_report_params_external(report_name, [environment], [responsibility])` | discover a report's parameters | spilled table: Parameter, Type, Required, Must Set?, Multiple, Default, Has LOV, Depends On, Description |
| `br_param_values_external(report_name, parameter, [parent=value;…], [environment], [responsibility])` | valid values for an LOV / dependent parameter (parent-filtered) | spilled table: Value, ID, Description |
| `br_run_report_external(report_name, [params], [template], [environment], [responsibility])` | run a report (blank template = the report's default template) | `BLITZ_RUNNING: ...`; data populates a new sheet; `_blitz_run_status` set to `DONE`/`ERROR` |
| `br_report_templates_external(report_name, [environment], [responsibility])` | list a report's templates (the column set) | `Template \| Default? \| Description` |
| `_blitz_run_status` (workbook name) | run completion signal | `RUNNING:` / `DONE: <n> rows on sheet '<name>'` / `ERROR: <message>` |
