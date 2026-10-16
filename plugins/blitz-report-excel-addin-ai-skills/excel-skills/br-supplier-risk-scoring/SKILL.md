---
name: br-supplier-risk-scoring
description: >
  Score Oracle EBS suppliers on risk in Excel: have the br-run-reports skill extract spend, holds,
  price variance and delivery history, then combine dependency, reliability, price stability and
  anomaly signals into a ranked supplier risk register with a named driver per supplier. Use when
  the user asks which suppliers are risky, supplier risk review, vendor scorecard, supplier
  dependency/concentration, or who to review before contract renewal.
# Trigger: Slash command + auto
---

# Supplier Risk Scoring (br-supplier-risk-scoring)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 10 minutes (multiple extracts).

Produce a ranked supplier risk register in one workbook. You own the scoring model and the
register; br-run-reports does extraction, **br-rfm-analysis** the spend-pattern segmentation,
**br-anomaly-detection** the invoice-anomaly scan, br-data-dashboard the build. Run steps in order,
keeping intermediate sheets.

**Requires:** br-run-reports, br-rfm-analysis, br-anomaly-detection, br-data-dashboard.

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** Extraction is by **br-run-reports**; never call `br_*`
functions or touch a result sheet mid-run. **Read-and-recommend only** — this skill never holds a
supplier, changes sites, or blocks POs; it scores and routes to review.

## 🚨 A score is a review queue, not a verdict
This model sees only EBS transaction history — no financials, sanctions, ESG or news. A high score
means *look at this supplier*, never *this supplier is failing*. Say so on the dashboard, and never
auto-derive an action from the score.

## When to use
"Which suppliers are risky", "supplier risk assessment", "vendor scorecard", "how dependent are we
on X", "who should procurement review this quarter". For duplicate payments specifically, use
**br-ap-duplicate-payments**; for holds, **br-ap-holds-analysis**.

## Inputs
- **Operating Unit** — required. **Lookback window** — default 12 months (spend/history);
  the window drives extract size, so confirm it before a big pull.

## Step 0 — Analysis depth  *(one `ask_user_question`, before any extraction)*
Delivery performance costs an extra extract and is empty at sites not using supplier scheduling —
ask once, nothing pre-selected:
- **Standard** — spend, holds, price variance (3 extracts).
- **+ Delivery performance** — adds the on-time-delivery extract.
Skip the question when the request implies it ("delivery risk" → include; "quick look" → Standard).

## Reports used (authoritative names — do NOT broad-search for them)
Pass the **documented name directly**; search only on `#BLITZ_REPORT_NOT_FOUND`.

| Report (exact name) | Run with | Feeds |
|---|---|---|
| `AP Invoices and Lines` | OU + Invoice Date window | Spend, frequency, recency per supplier — the RFM base. **The heaviest extract**: restrict to the window, header-level template if offered. |
| `AP Invoice on Hold` | OU | Holds count/aging per supplier — the friction signal. |
| `PO Invoice Price Variance` | OU + date window | Price instability per supplier. |
| `AP Suppliers` | (site filters as offered) | Master data: sites, terms, inactive flags — and the register's display names. |
| `PO Vendor Service Performance Analysis` *(optional — Step 0)* | OU + window | Delivery performance. **If empty/not found, score without it and say so** — never fake a delivery score. |

## CONFIG — scoring model (edit weights to the customer)
Score 0–100 per supplier = weighted sum of four 0–25 components:

| Component | Source | High-risk signal |
|---|---|---|
| **Dependency** | Invoice spend | Share of OU spend (concentration), single-site supplier for that spend |
| **Friction** | Holds | Holds per 100 invoices, aged holds outstanding |
| **Price instability** | IPV | Variance $ / spend ratio, worsening trend across the window |
| **Anomaly** | br-anomaly-detection over the supplier's invoices | Outlier amounts, round-number clusters, duplicate-shaped patterns |

*(With delivery data: reweight to five components × 20; late-delivery rate is the fifth.)*
Band: **High ≥ 70, Medium 40–69, Low < 40.** Every High supplier must carry a one-line **driver**
("82% of spend in one site", "14 aged holds", …) — a number with no reason is not reportable.
Exclusions: intercompany suppliers, employees-as-suppliers, one-time suppliers under the $ floor
(default $10k window spend).

### Output sheets & tab order (left to right)
`Supplier_Risk` (dashboard, first), `Risk_Register` (every scored supplier), `AP_Invoices`,
`AP_Holds`, `PO_IPV`, `AP_Suppliers`, [`PO_Delivery`] (last).

## Pipeline
1. **Extract — DELEGATE.** br-run-reports runs the Step-0 report set → their sheets. Wait for each;
   the invoice extract is the long pole.
2. **Anchor.** Supplier count, total window spend, holds count, IPV total $. Record per-sheet row
   counts.
3. **Segment  *(delegate to br-rfm-analysis if it fires; else inline)*.** RFM over the invoice
   extract keyed on supplier — recency of activity, invoice frequency, monetary spend. Keep the
   segment per supplier for the register.
4. **Anomaly scan  *(delegate to br-anomaly-detection if it fires; else inline)*.** Over the
   invoice extract grouped by supplier; carry each supplier's anomaly count + worst finding.
5. **Score  *(single `execute_office_js` call)*.** Join holds, IPV, (delivery), segments and
   anomalies per supplier; apply CONFIG; write `Risk_Register` in one `.values =` call: supplier,
   number, band, score, the four component scores, the driver line, window spend, segment.
6. **Dashboard *(single call; charts second)*** (delegate to br-data-dashboard if it fires; else
   inline). KPI cards (High count, spend at High, top concentration), band distribution and
   spend-vs-score charts, top-10 High table with drivers. NEW sheet at **position 0**; don't rename
   report sheets; no multi-row `copyToRange`; clear strays; widen amount columns. Carry the "review
   queue, not a verdict" line on the dashboard itself.
7. **Narrative.** ≤5 bullets: the top risk and its driver, the concentration headline, any
   systemic pattern, recommended first review. If delivery was skipped, label the model
   "excl. delivery" — an unscored dimension must read as *not scored*, never as clean.
8. **Arrange tabs + final validation.** Order per CONFIG; `Supplier_Risk` active. **One permitted
   verification read:** register band counts and total spend tie to the Step-2 anchor.

## Validation
Every High has a driver; excluded suppliers listed, not silently dropped; component sources absent
on the instance shown as "not scored"; register ties to raws.

## Closed-loop (roadmap, not executed here)
Findings route to procurement review; supplier-master fixes to the AP Supplier Upload; hold
follow-ups to br-ap-holds-analysis. This skill scores; a human decides.
