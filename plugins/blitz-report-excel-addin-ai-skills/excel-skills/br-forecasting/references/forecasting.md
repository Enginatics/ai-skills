# Forecasting — Excel FORECAST.ETS reference

These are **native Excel formulas** written into cells on the `br_calc_` spine, then read via
`formula_results`. They are not JavaScript. Adapt cell ranges to the data.

## TOC
1. Build the regular period spine
2. Aggregate values into the spine
3. Seasonality detection
4. Forecast + confidence interval
5. Backtest MAPE

---

## 1. Build the regular period spine
Monthly spine from a start date in `A2`, one period per row:
```
A3:  =EDATE(A2,1)        ' drag down to the last period; gives 1st-of-month dates
```
Weekly spine (7-day step):
```
A3:  =A2+7
```
The timeline must be strictly evenly spaced with **no gaps and no duplicates**. Verify the count of
periods equals (last−first)/step + 1.

## 2. Aggregate the metric into each period (fill gaps with 0)
With raw dates in `Data!D:D` and amounts in `Data!E:E`, monthly bucket on spine date `A3`:
```
B3:  =SUMIFS(Data!$E:$E, Data!$D:$D, ">="&A3, Data!$D:$D, "<"&EDATE(A3,1))
```
A period with no transactions returns 0 — that is correct and required; do not leave it blank.

## 3. Seasonality detection
```
=FORECAST.ETS.SEASONALITY(B3:B40, A3:A40)
```
Returns the detected cycle length (e.g. 12). If the series has fewer than 2 full cycles of history,
override to 1 (no seasonality) in the forecast call below and note it. Known cycles: 12 monthly-annual,
7 daily-weekly, 4 quarterly-annual.

## 4. Forecast and confidence bounds for a future period in `A41`
```
Forecast:  =FORECAST.ETS(A41, $B$3:$B$40, $A$3:$A$40, 12, 1)
ConfInt :  =FORECAST.ETS.CONFINT(A41, $B$3:$B$40, $A$3:$A$40, 0.95, 12, 1)
Lower   :  =Forecast - ConfInt
Upper   :  =Forecast + ConfInt
```
Arguments: (target_date, values, timeline, [seasonality], [data_completion=1 fills gaps],
[aggregation]). Set seasonality to 1 to disable. `FORECAST.ETS.STAT(values,timeline,stat,…)` returns
fit detail (stat 4 = alpha, 5 = beta, 6 = gamma, 8 = MASE) if you want to report smoothing parameters.

## 5. Backtest MAPE (trust signal)
Hold out the last `h` actual periods, forecast them from earlier data only, then:
```
Per-period APE:   =ABS(Actual - Forecast)/ABS(Actual)
MAPE:             =AVERAGE(of the APE column)    ' express as %
```
Skip periods where Actual = 0 (division blows up) or use a small-denominator guard. Interpretation:
≲10% strong, 10-20% usable, 20-50% rough, >50% treat as directional only.
