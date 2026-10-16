# RFM — scoring formulas and segment matrix

Excel formulas on the `br_calc_` sheet (read via `formula_results`); a little JS only if you prefer
to bin in script. Adapt ranges to the data.

## TOC
1. Per-entity aggregation
2. Quintile scoring (R reverse-scored)
3. Segment matrix (R × FM → name)
4. Edge cases

---

## 1. Per-entity aggregation
With raw data Customer `Data!A`, Date `Data!D`, Amount `Data!E`, and an as-of date in `$Z$1`:
```
Last txn date:  =MAXIFS(Data!$D:$D, Data!$A:$A, <Customer>)
Recency (days): =$Z$1 - <Last txn date>
Frequency:      =COUNTIFS(Data!$A:$A, <Customer>)            ' or COUNTIFS on distinct invoice ids
Monetary:       =SUMIFS(Data!$E:$E, Data!$A:$A, <Customer>)  ' decide gross vs net of credits
```
Build the distinct customer list first (Remove Duplicates on a copy of `Data!A`, or UNIQUE).

## 2. Quintile scoring on 1-5
Frequency and Monetary: higher value → higher score.
```
F score:  =MATCH(<Freq>, {q20,q40,q60,q80}, 1)        ' returns 0..4; +1 for 1..5  -> wrap: 1+MATCH(...)
```
Simpler with PERCENTRANK bands across the column `F2:F500`:
```
F score:  =CEILING.MATH(PERCENTRANK.INC($F$2:$F$500, F2)*5, 1)   ' 1..5 (clamp 0 up to 1)
M score:  =CEILING.MATH(PERCENTRANK.INC($M$2:$M$500, M2)*5, 1)
```
**Recency is reverse-scored** — most recent (smallest days) gets 5:
```
R score:  =6 - CEILING.MATH(PERCENTRANK.INC($R$2:$R$500, R2)*5, 1)   ' 1..5, high = recent
```
Clamp any 0 result to 1. If a measure has < 5 distinct values, score on the distinct values (e.g.
1-3) and note the reduced granularity.

## 3. Segment matrix (R score × FM score)
Let `FM = ROUND((Fscore+Mscore)/2, 0)`. Map with this lookup (rows = R, cols = FM, both 1-5):

```
              FM=1            FM=2            FM=3            FM=4            FM=5
R=5  New/Recent     Promising       Potential Loyal Loyal           Champions
R=4  Promising      Potential Loyal Potential Loyal Loyal           Champions
R=3  About To Sleep Need Attention  Need Attention  Loyal           Loyal
R=2  At Risk        At Risk         Need Attention  Can't Lose Them Can't Lose Them
R=1  Lost           Hibernating     At Risk         Can't Lose Them Can't Lose Them
```

Implement as a 5×5 lookup table on `br_calc_` and `INDEX(matrix, 6-Rscore, FM)` (rows listed R=5..1
top-to-bottom as above), or as nested IFS. Keep the raw 3-digit `RFM = Rscore & Fscore & Mscore`
("545") alongside the name for power users.

Segment intent / action:
- **Champions** (R high, FM high): reward, ask for referrals/reviews.
- **Loyal** / **Potential Loyalist**: upsell, build into Champions.
- **New/Recent**, **Promising**: onboard, encourage a second purchase.
- **Need Attention**, **About To Sleep**: timely reactivation offers.
- **At Risk**, **Can't Lose Them** (were valuable, now slipping): win-back priority — highest revenue
  exposure.
- **Hibernating**, **Lost**: low-cost re-engagement; don't over-invest.

## 4. Edge cases
- As-of date = data max (historical extract) vs today (live) — state which; it moves every R score.
- Credits/returns → negative monetary: exclude or net, and say so.
- Single-transaction customers pile at F=1; bin on distinct values.
- Very small datasets: report fewer, coarser segments rather than the full 11.
