---
name: br-po-match-exceptions
description: >
  Triage Oracle EBS 3-way match exceptions — invoices held because PO, receipt and invoice disagree
  on quantity or price — explain the root cause per hold (not received, over-billed, price change,
  receipt discrepancy), and route each to the right resolver: receiving, buyer, or AP. Read-only.
  Use when the user asks about match holds, quantity/price mismatches, "why is this invoice on
  match hold", or wants the match-exception backlog worked down.
# Trigger: Slash command + auto
---

# PO 3-Way Match Exception Triage (br-po-match-exceptions)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.

> **Performance:** read `br-analytics-standards` at the start of every run.

## When to use
"Why are these invoices on match hold", "work down the match-exception backlog", "quantity vs price
mismatch analysis", "what's blocking these invoices — receiving or the buyer?". For the full holds
landscape (all hold types) use **br-ap-holds-analysis**; to actually release holds use
**br-ap-hold-release**. This skill is the match-specific deep dive that tells each team what THEY
must fix — it is read-and-recommend only.

## Inputs
- **Operating Unit** (required) — ask if not supplied.
- *Optional:* Supplier, Hold Date range, PO Number, materiality threshold (see CONFIG).

## Reports used (authoritative names — do NOT broad-search for them)
| Report (exact name) | Role |
|---|---|
| `AP Invoice on Hold` | the spine — match-class holds (quantity received, quantity ordered, price) with invoice + PO context |
| `AP Invoices and Lines` | invoice line detail for held invoices (billed qty/price) |
| `PO Headers and Lines` | ordered qty/price and the buyer per PO line |
| `PO Receipts/Deliveries Discrepancy` | receipt-side discrepancies backing the "not received / short received" classes |

Pass the exact names; fall back to a search only on `#BLITZ_REPORT_NOT_FOUND`.

## Workflow
1. **Extract** the match-class holds for the OU (filter `AP Invoice on Hold` to the matching hold
   names), then the supporting detail — one call per report.
2. **Classify each hold** by comparing the three legs:
   - **NOT RECEIVED / SHORT RECEIVED** — billed qty > received qty → resolver: **Receiving**
     ("receive the goods or dispute the billing").
   - **OVER-BILLED QTY** — billed qty > ordered qty → resolver: **Buyer** (amend the PO) or **AP**
     (supplier credit).
   - **PRICE MISMATCH** — invoice price ≠ PO price → resolver: **Buyer** (price change / new quote)
     or **AP** (within-tolerance candidate — see CONFIG).
   - **RECEIPT DISCREPANCY** — receipt exists but disagrees with the delivery per the discrepancy
     report → resolver: **Receiving**.
   Never force a class: a hold whose legs cannot be reconciled from the data is UNCLASSIFIED with
   the reason stated.
3. **Build the routed worklists** — one sheet per resolver (Receiving / Buyer / AP), ranked by $
   held, with per-row plain-language cause ("Billed 100, received 60 on receipt R-1234") and the
   PO/buyer named. Supplier-level roll-up: repeat offenders by class.
4. **Summarize**: $ on match hold by class, aging, close exposure (holds on invoices dated in the
   closing period), and the top 5 systemic patterns (one supplier always over-bills, one PO's price
   is stale, ...). Dashboard via br-data-dashboard.

## CONFIG — placeholder policy, label it as such
The price-tolerance figure ("within tolerance, candidate to release") is the customer's matching
tolerance policy — this data does not carry it. Until the user states it, mark such rows
"review candidate — confirm against your tolerance policy", never "safe to release".

## Hand-off
When the user wants to act: releasable candidates go to **br-ap-hold-release** (it owns the
release safety contract). This skill never writes.

## Degradation rules
- `PO Receipts/Deliveries Discrepancy` returning nothing does NOT mean no receipt problems — say
  "no delivery discrepancies recorded" and classify from the qty legs alone.
- A hold on an unmatched (no-PO) invoice is out of scope — count it, point at
  br-ap-holds-analysis, don't force it into a match class.

## Talk in the user's language
Name suppliers, POs, buyers and dollar amounts — never `br_*` functions or helper sheets.
