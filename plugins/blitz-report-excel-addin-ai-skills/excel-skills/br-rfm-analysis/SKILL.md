---
name: br-rfm-analysis
description: Score customers (or vendors) on Recency, Frequency, and Monetary value from a transactional Blitz Report and map them to named segments like Champions, Loyal, At Risk, and Hibernating. Use this whenever the user wants RFM analysis, customer-value segmentation, to find their best / lapsing / at-risk customers, prioritise accounts, or target win-back and retention from an Oracle EBS / Blitz Report of invoices, orders, or sales. Trigger for "who are our best customers", "which customers are slipping away", "segment customers by value", or any RFM request.
---

# br-rfm-analysis — score and name customers by behaviour

> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Take a transactional Blitz Report (AR invoices, sales orders, shipments) and turn it into a ranked,
named customer segmentation a commercial team can act on the same day. Pure aggregation +
quintile scoring — computed in the workbook with formulas (and light JS where convenient), so it
stays transparent and refreshable. No ML black box: every score is explainable.

## When to use / not use
- **Use** for: customer/vendor value segmentation from dated, valued transactions; finding
  Champions, At-Risk, Lapsed accounts; prioritising outreach.
- **Don't use** for: clustering on arbitrary behavioural features (`br-clustering`), or data without
  a per-entity transaction history (no dates/amounts to score).

## Shared conventions (the br_ analytics house style)
1. **Source** = an existing Blitz Report sheet; row 1 is headers. **Never modify source columns.**
2. **Scratch work** on `br_calc_`; delete when done.
3. **Outputs (all four):** a results sheet `br_rfm_results` (`Customer | Recency | Frequency |
   Monetary | R | F | M | RFM | Segment`); a chart; a dashboard (reuse `br-data-dashboard` for
   KPI/slicer layout; slicer on `Segment`); a plain-English chat summary with per-segment actions.
4. **Determinism:** quintile scoring is deterministic; state the as-of date and the scoring scheme.
5. **Privacy:** operate only on the provided sheet.

## Workflow — follow in order

### Step 1 — Identify columns and the as-of date
Read headers + sample rows. Identify the **entity key** (Customer/Account), the **transaction date**,
the **monetary amount**, and optionally a **transaction/invoice id** for frequency. Set the **as-of
date**:
- default to the **latest date in the data** (so recency is measured against the extract, not
  today — important for historical extracts),
- offer "today" if the data is live.
State which you used.

### Steps 2-5 — Aggregate, score, segment + write results sheet  *(single `execute_office_js` call)*
In one call: read the entity key + date + amount (+ optional id) columns, then aggregate per entity
(Step 2), score R/F/M by quintile (Step 3), map to named segments (Step 4), and write the
`br_rfm_results` sheet (Step 5) — all in the same JS block. Trust the values it returns; do not
insert a verification read between aggregating, scoring, segmenting, and writing. The per-step
detail (formulas, scoring scheme, segment matrix) follows.

### Step 2 — Aggregate per entity
For each customer compute:
- **Recency** = as-of date − most recent transaction date, in **days** (lower = better).
- **Frequency** = count of transactions (or distinct invoice/order ids).
- **Monetary** = sum of amount. Decide gross vs net of returns/credits and say so; negatives need a
  rule (exclude credits, or net them).
Formulas (`MAXIFS`, `COUNTIFS`, `SUMIFS`) in `references/rfm.md`.

### Step 3 — Score R, F, M on 1-5 by quintile
Bin each measure into 1-5 by quintiles. **Recency is reverse-scored** (most recent → 5).
Frequency and Monetary higher → 5. If a measure has fewer than 5 distinct values (e.g. many
one-purchase customers), use fewer bins and note it rather than forcing 5. Quintile formulas in
`references/rfm.md`.

### Step 4 — Map to named segments
Combine **R** with a **FM** score (average or max of F and M) and map to the standard segment names
— Champions, Loyal, Potential Loyalist, New/Recent, Promising, Need Attention, About To Sleep, At
Risk, Can't Lose Them, Hibernating, Lost — using the matrix in `references/rfm.md`. Also keep the raw
3-digit `RFM` cell (e.g. "545") for power users.

### Step 5 — Results sheet (written in the Steps 2-5 call)
`br_rfm_results`: `Customer | Recency | Frequency | Monetary | R | F | M | RFM | Segment`, sorted by
Monetary or by segment priority. This sheet is created and populated **inside the combined Steps 2-5
`execute_office_js` call** — not as a separate write.

### Step 6 — Charts  *(single `execute_office_js` call — the permitted separate charts call)*
- a **segment-size bar** (customers per segment),
- a **Recency-vs-Frequency bubble** chart sized by Monetary (shows where the valuable, active
  customers sit) — or a segment-by-revenue bar if a bubble is awkward.

### Step 7 — Dashboard
Dashboard from `br_rfm_results` with KPI cards: **total customers**, **total monetary**,
**% of revenue in top segments (Champions + Loyal)**, **count At-Risk/Can't-Lose**. Slicer on
`Segment` so the team can pull one segment's customer list.

### Step 8 — Chat summary
Report: the segment distribution, **where the value concentrates** (e.g. "Champions are 9% of
customers but 38% of revenue"), the at-risk value exposure, and **specific actions per priority
segment** — retain/reward Champions, win back Can't-Lose-Them and At-Risk before they lapse, nurture
Potential Loyalists, re-engage Hibernating with a low-cost offer. End with where the sheet and
dashboard are.

## Gotchas
- As-of date drives recency — for a historical extract use the data's max date, not today, or every
  customer looks lapsed.
- Returns/credits create negative or inflated monetary; pick a rule (exclude vs net) and state it.
- One-transaction customers cluster at Frequency = 1 and can break quintiles — bin on distinct
  values and note reduced granularity.
- Quintile ties: customers on a boundary may land in adjacent bins; that's expected, don't over-tune.
- Tiny datasets don't segment meaningfully — say so rather than forcing 11 segments onto 30 customers.
