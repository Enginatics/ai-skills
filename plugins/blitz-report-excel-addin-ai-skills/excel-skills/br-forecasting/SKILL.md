---
name: br-forecasting
description: Forecast a time series from a Blitz Report — future demand, sales, GL trend, AR collections, cash, or inventory — using Excel's native FORECAST.ETS (Holt-Winters) with seasonality detection, confidence intervals, and a backtest accuracy check. Use this whenever the user wants to forecast, project, predict, or extrapolate future values of a dated metric in an Oracle EBS / Blitz Report sheet — "forecast next quarter's sales", "project AR collections", "what will the GL trend look like", "predict demand". Trigger it for any "forecast / projection / what will happen next" request over time.
---

# br-forecasting — project a Blitz Report metric forward

> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Turn a dated metric in a Blitz Report into a forward forecast with confidence bounds, and tell the
user how much to trust it. Use Excel's **native `FORECAST.ETS`** family (exponential
smoothing / Holt-Winters) — it lives in the workbook, handles seasonality and prediction intervals,
and stays live if the source refreshes. No external compute needed.

## When to use / not use
- **Use** for: time-series forecasting of a single metric over regular periods (monthly sales,
  weekly demand, GL balance trend, collections).
- **Don't use** for: predicting a per-row outcome from features (that's regression/classification),
  or when there isn't a real time axis. **Be honest about short history**: reliable seasonality
  needs **≥ 2 full cycles** (≥ 24 months for monthly seasonality); with less, forecast without
  seasonality and say the bands are wide.

## Shared conventions (the br_ analytics house style)
1. **Source** = an existing Blitz Report sheet; row 1 is headers. **Never modify source columns.**
2. **Scratch work** on `br_calc_`; delete when done.
3. **Outputs (all four):** a results sheet `br_forecast_results` (`Period | Actual | Forecast |
   Lower | Upper`); a chart; a dashboard (reuse `br-data-dashboard` for KPI layout); a
   plain-English chat summary with the accuracy read-out and caveats.
4. **Determinism:** ETS is deterministic given the same series and settings; state the period,
   horizon, seasonality, and confidence level you used.
5. **Privacy:** operate only on the provided sheet.

## Workflow — follow in order

### Step 1 — Identify the series and settings
Read headers + sample rows. Identify the **date column** and the **value column**. Decide:
- **Period grain:** monthly by default; weekly if the data is daily operational volume. State it.
- **Horizon:** how many future periods (default 12).
- **As-of cutoff:** forecast from the last complete period (drop a partial final period so it
  doesn't read as a fake drop).
Confirm only if ambiguous.

### Steps 2-4 — Spine + seasonality + forecast formulas  *(single `execute_office_js` call)*
In one call: read the date + value columns, build the regular period spine (Step 2), and write the
seasonality (Step 3) and `FORECAST.ETS` / `CONFINT` / `STAT` formula block (Step 4) — headers, seed
formula row, and `autoFill` down the spine — all in the same JS block. Trust the `formula_results`
this call returns; do not insert a verification read between building the spine and reading the
forecast. The per-step detail follows.

### Step 2 — Build a regular period spine (critical)
`FORECAST.ETS` requires an **evenly spaced timeline with no gaps**. On `br_calc_`, build a continuous
list of periods from first to last, and aggregate the value into each period (`SUMIFS`). **Fill
missing periods explicitly** — a month with no rows is a real **0**, not absent. Confirm there are no
duplicate or skipped periods before forecasting. Formulas in `references/forecasting.md`.

### Step 3 — Detect seasonality
Use `FORECAST.ETS.SEASONALITY(values, timeline)` to detect the cycle length, or set it from the
known business cycle (12 = monthly annual, 7 = daily weekly). If detected seasonality would need more
history than you have (< 2 cycles), set seasonality to 1 (none) and note it.

### Step 4 — Forecast with bounds and fit stats
- `FORECAST.ETS(targetDate, values, timeline, [seasonality])` for each future period.
- `FORECAST.ETS.CONFINT(targetDate, values, timeline, 0.95, [seasonality])` for the ± interval →
  Lower/Upper bounds.
- `FORECAST.ETS.STAT(...)` for fit statistics if you want to report smoothing/error detail.

### Step 5 — Backtest accuracy (the trust signal)
Hold out the **last h periods**, forecast them from the earlier data only, and compute **MAPE**
(mean absolute % error) against the actuals. Report it: ≲ 10% strong, 10-20% usable, 20-50% rough,
> 50% don't rely on point values. This number is what tells the user whether to believe the forecast.

### Step 6 — Results sheet + chart  *(results in one `execute_office_js` call; chart is the permitted second call)*
`br_forecast_results`: `Period | Actual | Forecast | Lower | Upper` (Actual blank for future
periods; Forecast/Lower/Upper blank for history except the fitted line if you include it) — write the
full sheet in a single call. Then, in the permitted separate charts call, chart a **line of Actual +
Forecast with a shaded confidence band** (Upper/Lower as a band series). Mark where history ends and
forecast begins.

### Step 7 — Dashboard
Dashboard from `br_forecast_results` with KPI cards: **next-period forecast**, **trend %**
(forecast vs last actual), **seasonality found**, **backtest MAPE**.

### Step 8 — Chat summary
Report: the forecast for the horizon (or the headline next 1-3 periods), the trend direction,
whether seasonality was found and its cycle, the **MAPE accuracy**, and caveats — wide bands far out,
don't forecast through a known structural break (price change, system migration, COVID-type shock),
and that outliers in history distort ETS (consider running `br-anomaly-detection` first to clean).

## Gotchas
- Gaps break ETS. Build the regular spine and fill empty periods with 0 (or interpolate only if a 0
  is clearly wrong, and say so). Step 2 is mandatory.
- A partial last period looks like a cliff — drop it or annotate it.
- Seasonality needs ≥ 2 full cycles; otherwise turn it off rather than inventing a pattern.
- Confidence bands widen with horizon — long forecasts are illustrative, not precise.
- Outliers and one-off spikes pull the smoothing; clean or flag them first.
- These are native Excel functions — write them as cell formulas on the spine and read results via
  `formula_results`; they are not JS.
