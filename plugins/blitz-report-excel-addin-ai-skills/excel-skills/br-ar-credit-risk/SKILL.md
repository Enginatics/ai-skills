---
name: br-ar-credit-risk
description: >
  Score customer credit risk and analyse DSO from Oracle EBS Receivables: combine credit limits and
  utilization, aging severity, payment behaviour and balance trend into a per-customer risk grade
  with the drivers named, plus a DSO decomposition showing which segments and behaviours move it.
  Read-only. Use when the user asks which customers are a credit risk, wants credit limits
  reviewed, asks "why is our DSO rising", or needs a credit-review worklist.
# Trigger: Slash command + auto
---

# AR Credit Risk & DSO Analysis (br-ar-credit-risk)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.

> **Performance:** read `br-analytics-standards` at the start of every run. The payment-behaviour
> scoring reuses the technique in `br-rfm-analysis` — read it when that add-on runs.

## When to use
"Which customers are a credit risk", "review credit limits", "who is close to / over their limit",
"why is DSO up this quarter", "credit-review worklist for the committee". For chase-this-week
collections prioritization use **br-ar-collections-worklist** (it owns dunning); this skill is the
slower-cadence credit and DSO view. They compose: run this first, hand the high-risk names to the
worklist.

## Inputs
- **Operating Unit** (required) — ask if not supplied.
- **As-of date** — default today; say so.
- *Optional:* customer scope, the payment-behaviour add-on (extra extract — offer once, yes/no).

## Reports used (authoritative names — do NOT broad-search for them)
| Report (exact name) | Role |
|---|---|
| `AR Customer Credit Snapshot` | the spine — per-customer credit position |
| `AR Customer Credit Limits` | limits per customer/site/currency to compute utilization |
| `AR Aging` | open balance by bucket — severity input |
| `AR Customer Open Balances Period Lookback` | balance trend over trailing periods |
| `AR Applied Receipts` | payment behaviour add-on — days-to-pay distribution (extra extract, offer first) |
| `AR Customer Profiles` | profile class, terms, collector — context columns |

Pass the exact names; fall back to a search only on `#BLITZ_REPORT_NOT_FOUND`.

## Workflow
1. **Extract** snapshot, limits, aging and lookback for the OU (one call each). Run
   `AR Applied Receipts` only if the behaviour add-on was accepted.
2. **Score each customer** on four dimensions, each 0–25, with the raw driver kept beside the score:
   - **Utilization** — open balance vs credit limit (over-limit caps the dimension at 25).
     Customers with NO limit set are their own class — "unlimited exposure", listed separately,
     never scored as safe.
   - **Aging severity** — share of balance past 60/90 days.
   - **Trend** — balance growth over the lookback periods (growing balance + worsening aging is the
     compound signal to call out).
   - **Payment behaviour** — weighted days-to-pay vs terms from applied receipts; when the add-on
     was skipped, this dimension reads "not scored" and the total is out of 75 — SAY SO, never
     silently rescale.
3. **Grade** A–D from the total (thresholds are CONFIG placeholders — label them), and produce the
   credit-review worklist: grade C/D + over-limit + unlimited-exposure customers, ranked by open
   balance, one plain-language line each ("82% utilized, balance +40% in 3 months, pays 18 days
   late").
4. **DSO decomposition**: DSO from aging balance vs credited sales proxy (lookback periods), split
   by customer segment/profile class — which segment moves the number, and whether the driver is
   balance growth or payment slowdown. Trend across the lookback.
5. **Dashboard** (br-data-dashboard): grade distribution, exposure by grade, DSO trend, top-10
   exposure list.

## Hard rules
- A recommendation is a REVIEW candidate, never "cut this customer's credit" — credit decisions
  are the customer's policy, and the sheet says so.
- Never net credit balances into risk scores silently — a large unapplied credit is its own
  callout, not a risk reducer.

## Degradation rules
- No `AR Customer Credit Limits` rows (site doesn't use limits) → utilization dimension reads
  "limits not used", scoring proceeds on the other dimensions with the reduced denominator stated.
- Thin lookback history → trend dimension "not scored", stated.

## Talk in the user's language
Customer names, balances, grades — never `br_*` functions or helper sheets.
