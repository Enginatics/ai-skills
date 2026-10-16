---
name: br-ap-payment-optimizer
description: >
  Optimize an Oracle EBS Accounts Payable payment run in Excel: have the br-run-reports skill
  extract the AP cash requirement (due invoices, available early-pay discounts, due dates, payment
  priority), classify each invoice as capture-discount / pay-to-avoid-late / defer-to-due /
  priority-must-pay, select the best pay run within a cash constraint by discount ROI, quantify the
  discount $ captured and DPO impact, and build a payment-run dashboard. Use when the user asks which
  invoices to pay and when, capture early-pay discounts, optimize a payment batch, plan a cash
  disbursement, or improve DPO.
# Trigger: Slash command + auto
---

# AP Payment-Run Optimizer (br-ap-payment-optimizer)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: **Standard run under 5 minutes** — one extract, one classify pass, one optimize
> pass, dashboard. Step 6 (cash-outflow projection) is the only deep-dive add-on and is opt-in; do
> not run it unasked. There is no Step-0 depth prompt here because that single add-on is the only
> optional work — just don't volunteer it.

Produce an optimized AP payment-run recommendation in one Excel workbook. You own the orchestration,
the per-invoice classification, the cash-constrained selection, and the written recommendation; the
specialist skills do the extraction and the dashboard build. Run steps **in order**, on separate
turns, keeping every intermediate sheet so the user can audit each decision.

**Requires:** br-run-reports (extraction). **Optional:** br-data-dashboard (dashboard build — if it
doesn't fire, build inline per Step 5); br-forecasting (forward cash-outflow projection — Step 6).

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** All extraction is performed by the **br-run-reports**
skill, which owns add-in connection, authentication, asynchronous execution, completion polling, and
deterministic cell population.
- Never call `br_*` add-in functions directly.
- Never rename the result sheet, read its values, sum a column, or start any analysis **until
  extraction is confirmed complete** — touching the workbook while the add-in's run is still in
  flight can stall it and the run will never finish.
- Your job is only: (1) ask br-run-reports to fetch the data, then (2) once it has fully landed,
  classify, optimize, and present it.

**This skill is read-and-recommend only.** It does NOT create or submit a Payment Process Request,
select invoices for payment in EBS, or place/release any hold. It produces a recommended pay run and
a deferred list; building the actual payment batch is a separate, human-approved step.

## When to use
"Which invoices should we pay this week and when", "capture early-pay discounts", "optimize our
payment run", "plan the cash disbursement", "improve DPO without missing discounts", "what can we
safely defer". For a plain due-invoices list with no optimization, use br-run-reports directly.

## Inputs (collect up front)
- **Operating Unit** (required) — ask if not supplied.
- **Pay Through Date** (required) — the horizon: which invoices are in scope for this run (the report
  shows everything due on/before it).
- *Optional:* **Cash available** — the constraint for this run. If omitted, there is **no cap** and
  the optimizer recommends the economically-ideal run (capture every beneficial discount, pay
  everything due, defer the rest); if supplied, it selects the best subset within the cap.
- *Optional:* Supplier / Payment Method / Payment Priority filter; "include unvalidated/unapproved"
  (default **No** — only payable invoices); a cost-of-cash / annual borrowing rate (default **10%**)
  used to judge whether paying early to capture a discount is genuinely beneficial.

## Reports used  (authoritative names — do NOT broad-search for them)
These exact report names are known. When you ask br-run-reports to run one, pass the **documented
name directly** — do NOT run a `br_report_list_external` discovery search first. Inspect parameters
only if you need an exact LOV spelling. **Fallback:** only if a run returns `#BLITZ_REPORT_NOT_FOUND`
do a name search. If a run returns a bare `ERROR: ERROR`, the param names didn't match — have
br-run-reports inspect params (`br_report_params_external`) and adapt, then retry; don't abandon it.

| Report (exact name) | Run with | Role |
|---|---|---|
| `AP Cash Requirement` | **Operating Unit** (**required**, multi-value) + **Pay Through Date** (the run horizon — the report's own param is *optional*, but set it to scope which invoices are in play). Optional: Due Date From/To, Payment Method, Payment Priority From/To, and **Economically Beneficial = Yes** (a *filter* param — see note). Leave **Include Unvalidated Invoices / Include Unapproved Invoices = No** unless asked. | **The optimization base** — one row per due invoice with the discount columns, due date, priority, and in-report hold flags. Payables (always present) |
| `AP Invoice on Hold` *(optional, rarely needed)* | **Operating Unit** | A separate held-invoice list — usually **unnecessary**: `AP Cash Requirement` already carries `HOLD_FLAG` / `HOLDS_COUNT` per row, so exclude held invoices in-sheet. |
| `AP Invoices and Lines` *(optional)* | Operating Unit + Open only = Yes + Display Level = Headers | Richer terms / context if `AP Cash Requirement` lacks a column you need. |

> **Verified output columns (r12, parsed):** `TRADING_PARTNER` (the supplier), `INVOICE_NUM`,
> `INVOICE_DATE`, `DUE_DATE`, `DAYS_TO_DUE`, `GROSS_AMOUNT` / `AMOUNT` (payment ccy) /
> `FUNCTIONAL_CURRENCY_AMOUNT`, `INVOICE_CURRENCY_CODE`, `PAYMENT_PRIORITY`, `PAYMENT_METHOD`,
> `PAY_GROUP`, `DISCOUNT_DATE`, `DISCOUNT_AMOUNT_AVAILABLE`, `DISCOUNT_AMOUNT_REMAINING`,
> `PAYMENT_STATUS`, `INVOICE_STATUS`, `APPROVED`, `HOLD_FLAG`, `HOLDS_COUNT`, `OPERATING_UNIT`,
> `INVOICE_ID`.
> **🚨 There is NO "Economically Beneficial" output column** — it exists only as a Yes-only *filter
> parameter* (set it = Yes to have EBS pre-filter to invoices where the discount beats the cost of
> cash). This skill computes its own discount **ROI** from `DISCOUNT_AMOUNT_AVAILABLE` + `DISCOUNT_DATE`
> + `DUE_DATE`/`DAYS_TO_DUE`, so it does **not** depend on that flag — but you MAY set
> `Economically Beneficial = Yes` to shrink the working set on a very large OU.

## CONFIG  — edit to match the customer; logic below reads from here

### 🚨 Amount column — MANDATORY functional consolidation when currencies mix
**First check how many `INVOICE_CURRENCY_CODE` values are present. If more than one, you MUST sum
`FUNCTIONAL_CURRENCY_AMOUNT` — never `GROSS_AMOUNT` (payment currency).** Summing payment-currency
magnitudes across currencies is meaningless: a foreign line in its own units doesn't compare to a USD
line (real Vision rows: `FRF 2,060,630` gross = `$345,134` functional; `EGP 4,400` = `$151,400`;
`JPY 26,991` = `$212`). **Do NOT write `grossAmount || functionalAmount`** (the `||` prefers gross and
reintroduces the bug). Pick one column up front by currency count:
```js
// COPY VERBATIM (port of skill_logic.py::consolidated_amount)
const multiCcy = new Set(rows.map(r => r.invoiceCurrencyCode)).size > 1;
const amountOf = inv => Number(multiCcy ? inv.functionalAmount : inv.grossAmount) || 0;
```
Single currency → `GROSS_AMOUNT` is fine and reads natively. Label every total as functional when
`multiCcy`.

### Per-invoice decision class  (columns are the verified r12 headers)
Classify each in-scope invoice (today = run date), reading `DISCOUNT_AMOUNT_AVAILABLE`,
`DISCOUNT_DATE`, `DUE_DATE`, `DAYS_TO_DUE`, `PAYMENT_PRIORITY`, `HOLD_FLAG`/`HOLDS_COUNT`,
`INVOICE_STATUS`, `APPROVED`, and the amount (`amountOf` above — functional when the OU mixes
currencies, gross otherwise). **🚨 Test the classes in EXACTLY this order — each `if`/`else if`
falls through to the next:**
- **Excluded** (test **1st**) — `HOLD_FLAG`='Y' / `HOLDS_COUNT`>0, or not approved/validated
  (`APPROVED` / `INVOICE_STATUS` not in a payable state). Not payable → show but never select.
- **Capture-Discount** (test **2nd — BEFORE Priority and Late**) — `DISCOUNT_AMOUNT_AVAILABLE` > 0
  **and** `DISCOUNT_DATE` ≥ today **and** the discount is beneficial (ROI > cost of cash, below). Pay
  **by `DISCOUNT_DATE`** to capture `DISCOUNT_AMOUNT_AVAILABLE`. **🚨 This MUST be tested before
  Priority-Must-Pay / Pay-To-Avoid-Late** — a beneficial discount whose date hasn't passed is captured
  even on a high-priority or overdue invoice (you still pay it, AND you save the discount). A live run
  tested Priority first and **under-reported capturable discount by ~$119K** ($690K instead of $809K)
  because high-priority discount-eligible invoices were mis-labelled Priority-Must-Pay.
- **Pay-To-Avoid-Late** (test **3rd**) — `DAYS_TO_DUE` ≤ 0 (already due / past due) with no remaining
  discount. Pay **now** to avoid late penalties / supplier-relationship damage.
- **Priority-Must-Pay** (test **4th**) — `PAYMENT_PRIORITY` at/above the critical threshold (default
  **≤ 10**, i.e. highest), or a flagged critical supplier — pay regardless of economics.
- **Defer-To-Due** (the fall-through default) — no beneficial discount **and** `DAYS_TO_DUE` > 0 —
  **hold the cash, pay on `DUE_DATE`** to maximize DPO. (Deferring is the *correct* default; never pay
  early with no discount.)

### Discount ROI (ranks the discount-capture opportunities)
`discount_%` ≈ `DISCOUNT_AMOUNT_AVAILABLE` ÷ amount; `days_accelerated` ≈ `DUE_DATE` − `DISCOUNT_DATE`
(how much earlier you pay to earn it). The implied annualized return is
`ROI ≈ discount_% ÷ days_accelerated × 365`. A 2%/10-net-30 discount ≈ 36% annualized — far above any
cost of cash. The discount is **beneficial** when this ROI exceeds the user's cost-of-cash
(default 10%). Rank capture opportunities by **`DISCOUNT_AMOUNT_AVAILABLE`** for headline impact, and
by **ROI** when cash is constrained (highest-return discounts first per dollar of accelerated cash).
*(EBS tiers later discounts too — `SECOND_DISC_AMT_AVAILABLE`/`THIRD_DISC_AMT_AVAILABLE` with
`SECOND_DISCOUNT_DATE`/`THIRD_DISCOUNT_DATE`; default to the first discount, surface the later tiers
only if asked.)*

### Cash-constrained selection (only when "Cash available" is supplied)
Select invoices to **maximize (discount $ captured + late penalties avoided)** subject to
Σ paid ≤ cash cap, in this precedence:
1. **Priority-Must-Pay** and **Pay-To-Avoid-Late** first (non-negotiable — these get paid).
2. Then **Capture-Discount** by descending **ROI** (greedy) until the cash runs out — each captured
   discount is free money per day of accelerated cash.
3. **Defer-To-Due** is not funded by this run (it isn't due yet).
If steps 1–2 exceed the cap, report the **shortfall** and which beneficial discounts had to be
dropped (the cost of the cash constraint = the discount $ left on the table). With no cap, the
recommended run = all Priority/Late + all beneficial Capture-Discount, by their pay-by dates.

### DPO / cash framing
- **`pay_by_date`** = discount date (Capture-Discount), run date (Pay-To-Avoid-Late / Priority), or
  due date (Defer-To-Due). The run schedule is grouped by `pay_by_date`.
- **DPO impact** — paying only what's due/beneficial and deferring the rest **lengthens** DPO; flag
  any invoice being paid **early with no discount** as a DPO leak (should be Defer-To-Due).

### Output sheet names & tab order (left to right)
`AP_Pay_Run` (dashboard, first), `Pay_Schedule` (selected invoices by pay-by date), `Deferred`
(not-funded / defer-to-due, with deferral note), `AP_Cash_Req` (the extracted base — its report name).

---

## Pipeline

### Step 1 — Extract  (DELEGATE to br-run-reports — do not run it yourself)
Ask **br-run-reports** to run **"AP Cash Requirement"** with Operating Unit = {OU} and Pay Through
Date = {horizon} (Include Unvalidated/Unapproved = No). The report already carries `HOLD_FLAG` per
row, so **no separate holds run is needed** (only add "AP Invoice on Hold" if the user wants hold
detail). Pass the exact name directly; wait for completion; do nothing mid-run.
- `#BLITZ_NOT_CONNECTED` → relay it, ask the user to connect via the Blitz Report ribbon, retry.
- **Fallback:** if the hand-off doesn't fire or the data never lands, tell the user to run "AP Cash
  Requirement" themselves for the OU + pay-through date, then ask you to optimize it; resume at 1b.

### Step 1b — Anchor  *(single `execute_office_js` call)*
In one call: locate the columns (`TRADING_PARTNER`, `INVOICE_NUM`, `GROSS_AMOUNT`, `DUE_DATE`,
`DAYS_TO_DUE`, `DISCOUNT_AMOUNT_AVAILABLE`, `DISCOUNT_DATE`, `PAYMENT_PRIORITY`, `HOLD_FLAG`,
`INVOICE_CURRENCY_CODE`), record the **invoice count**, **total amount due in horizon**
(SUM `GROSS_AMOUNT`), and **total discount available** (SUM `DISCOUNT_AMOUNT_AVAILABLE`) as the
reconciliation anchors, and return them. **If zero invoices:** report "no AP invoices due on/before
{pay-through date} for {OU}" and stop.

### Step 2 — Classify + economics  *(single `execute_office_js` call)*
In one call: derive `days_accelerated` (`DUE_DATE` − `DISCOUNT_DATE`), `ROI`, `pay_by_date`, and the
**decision class** per CONFIG — excluding held/unapproved rows **in-sheet via `HOLD_FLAG`/`APPROVED`**
(no separate report needed) — writing all headers + seed row + `autoFill` to the last row in the same
block (Rule 4). Compute "beneficial" yourself (ROI > cost of cash); do **not** look for an
Economically Beneficial column (there isn't one). **Consolidate amounts via
`FUNCTIONAL_CURRENCY_AMOUNT` when the OU mixes currencies** (otherwise compare same-currency only).
Text-format only literal label cells, never formula cells (Excel-correctness #1). Return counts + $
by decision class and total discount $ capturable.

### Step 3 — Optimize the run  *(single `execute_office_js` call)*
In one call: if **Cash available** was supplied, run the cash-constrained greedy selection per CONFIG
(Priority + Late first, then Capture-Discount by ROI until the cap) and mark each invoice
**Selected** or **Deferred** with the reason; if no cap, mark all Priority/Late/beneficial-Capture as
Selected and all not-yet-due as Deferred. Build `Pay_Schedule` (Selected, grouped by `pay_by_date`)
and `Deferred` (not funded / defer-to-due, each with a one-line reason and the deferral cost if a
discount was dropped). Return: total to pay, discount $ captured, late exposure avoided, and (if
capped) the discount $ left on the table.

### Step 4 — (reserved)  *(no-op placeholder to keep Step 3 and the dashboard as separate single calls)*

### Step 5 — Dashboard  *(two `execute_office_js` calls: data then charts)*  (delegate to br-data-dashboard if it fires; else inline)
**Call 1 — all data sections** on a NEW `AP_Pay_Run` sheet at **position 0**: KPI band (**Total due
in horizon**, **Recommended pay-run $**, **Discount $ captured**, **Late exposure avoided**, **$
deferred**, and — if capped — **discount $ left on the table**); a decision-class breakdown
(count + $ for Capture-Discount / Pay-To-Avoid-Late / Priority-Must-Pay / Defer-To-Due / Excluded); a
**pay-by-date schedule** (cash needed per date); and the **top-N discount-capture opportunities** by
$ (supplier, invoice, discount $, discount date, ROI). Every KPI is a formula referencing
`Pay_Schedule` / `AP_Cash_Req` (COUNTIFS/SUMIFS) so it refreshes on re-run.
**Call 2 — charts only:** a cash-needed-by-date column chart and a decision-class bar chart.
- **Build mechanics (house standard):** build only on the new sheet; do **not** rename the report
  sheet (KPIs link to it). Do **NOT** use a multi-row `copyToRange` to fill schedule rows — write each
  formula explicitly. After building, scan beyond the dashboard range, clear stray cells, widen amount
  columns so values don't render as `######`.

### Step 6 — Cash-outflow projection  *(OPTIONAL add-on — only if the user asks)*
Delegate to br-forecasting (or compute inline) a weekly cash-outflow profile from the `pay_by_date`
schedule across the horizon → a `Cash_Outflow` panel/sheet. This is a **schedule roll-up**, not a
statistical forecast — label it so.
It derives purely from `Pay_Schedule`, so **adding it later costs no re-extract**: verify
`Pay_Schedule` is unchanged, build `Cash_Outflow`, and re-run Step 8 to place the tab. Never point a
dashboard KPI at `Cash_Outflow` unless this step ran.

### Step 7 — Narrative  *(single `set_cell_range` call)*
Write all ≤6 bullets on `AP_Pay_Run` in one call: "pay these N by <discount date> to capture $X in
discounts"; the total recommended pay-run $ and the cash needed by date; how much can be **safely
deferred** to lengthen DPO (and confirm nothing is being paid early for no discount); the single
biggest discount opportunity (supplier + $ + ROI); if capped, the discount $ left on the table and
what extra cash would unlock it; and any **excluded** held/unvalidated invoices to clear first.

Then, in your reply (not on the sheet), if Step 6 was skipped, offer it in one line and say it needs
no re-extract — e.g. "Want the weekly cash-outflow profile off this schedule? I can add it without
re-running the report."

### Step 8 — Arrange tabs + final validation  *(single `execute_office_js` call + one read)*
Reorder tabs to `AP_Pay_Run`, `Pay_Schedule`, `Deferred`, `AP_Cash_Req` (+ `Cash_Outflow` if built);
delete the `blitz_` helper sheet; activate `AP_Pay_Run`.
**Then the one permitted verification read:** confirm **Selected $ + Deferred $ + Excluded $ = total
due** (Step-1b anchor), that **Selected $ ≤ cash cap** when a cap was given, and that captured
discount $ ties to the schedule. This is the only explicit re-read outside Step 1b.

---

## Validation (before declaring done)
- **Reconcile:** Selected + Deferred + Excluded $ = the Step-1b total-due anchor; the pay-by-date
  schedule sums to the recommended pay-run $.
- **Constraint:** when a cash cap was supplied, recommended pay-run $ ≤ cap; the shortfall and dropped
  discounts are reported.
- **Economics sanity:** every Capture-Discount invoice has `DISCOUNT_DATE` ≥ run date and a computed
  ROI > cost of cash; no invoice is paid **early without a discount** (those must be Defer-To-Due).
- **No `######`** and no stray cells outside the dashboard range.

## Re-run / refresh
Never re-extract when you don't have to:
- **"Different cash budget"** (same data) — re-run only Steps 3 and 5–8; the extract and the Step-2
  classification are unchanged.
- **"Add the cash-outflow projection"** (same data) — run only Step 6, then Step 8 for the tab.
- **"Next week's run" / a new Pay Through Date / "rebuild"** (new data) — re-drive from Step 1,
  rebuilding the same set of sheets the previous run produced.

## Closed-loop (roadmap, not executed here)
Building the payment batch is a Payment Process Request (a concurrent submit / Payments-form action);
placing or releasing an invoice hold is a Blitz Upload. This skill recommends the run; a human
executes it.
