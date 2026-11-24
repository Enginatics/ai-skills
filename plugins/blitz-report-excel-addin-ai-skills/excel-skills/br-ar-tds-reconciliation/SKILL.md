---
name: br-ar-tds-reconciliation
description: >
  Reconcile the TDS that customers deducted from their payments (India, Form 26AS or AIS, any
  section such as 194Q, 194C or 194J) with the TDS booked in Oracle EBS Receivables: extract the
  TDS clearing account lines per customer with GL Account Analysis, map every deductor TAN of Form
  26AS to a customer, and show per customer and financial year what is matched, in Form 26AS but not
  booked, booked but missing from Form 26AS, or from an unidentified deductor. Proposes the claim
  journal, credit memos and customer follow-ups on a TDS_Actions sheet; changes nothing in Oracle.
  Use when the user asks for a TDS reconciliation, 26AS reconciliation, TDS receivable or TDS
  credit tie-out, short-deducted or short-deposited TDS by customers.
shared:
  - tds-actions-sheet
  - party-name-normalisation
# Trigger: Slash command + auto
---

# Customer TDS Reconciliation (br-ar-tds-reconciliation)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.

> **Performance:** read `br-analytics-standards` at the start of every run. Read
> `references/matching.md` before the matching step and `references/tds-actions-sheet.md` before
> writing the actions.

Customers who pay net of TDS leave two records: the TDS the company booked against them in Oracle,
and the TDS they reported to the tax department, which appears in the company's Form 26AS. This
skill ties the two per customer and financial year. You own orchestration, matching and the
verdict; br-run-reports does extraction. **Read-only:** the staging of memos and the journal is
**br-ar-tds-adjustments**, after the user has approved the actions.

## When to use
"Reconcile TDS with 26AS", "which customers deducted TDS but did not deposit it", "TDS receivable
does not match the 26AS", "TDS credits we never booked", quarterly or year-end TDS review.

## Inputs (ask once, up front, in one question)
- **Ledger** (required) and the **TDS account(s)**: the natural account value(s) on which TDS
  deducted by customers is booked. Never guess them; if the user does not know, they are the
  accounts their receipt write-off or TDS activity posts to.
- **Financial year(s)**: April to March; default the last completed year and the current one.
- **Form 26AS**: the user downloads it (or the AIS) from the income-tax portal and pastes Part I,
  or the whole statement, into a sheet of this workbook. Ask for the sheet name. No 26AS → stop and
  say what to download; never reconcile against the books alone.
- *Optional:* which amount counts (default `TDS Deposited`), sections to include (default all),
  tolerance per customer and year (default 1.00), customers to leave out (the user's policy), an
  existing `TDS_Deductor_Map` sheet from an earlier run.

## Reports used (authoritative names — do NOT broad-search for them)
| Report (exact name) | Run with | Role |
|---|---|---|
| `GL Account Analysis` | Ledger, `Period=` (empty), Period From, Period To (first and last period of the years), and the account segment parameter, named after the chart of accounts' account segment (e.g. `Account`), with the TDS account(s) comma-separated | the TDS booked: Accounting Date, Accounted Amount, Vendor Or Customer Number and Name, Transaction Number, Cash Receipt Number, Source Name, Concatenated Segments |
| `AR Customers and Sites` | Level=Customer, `Operating Unit=` (empty: it does not apply at customer level, and older versions of the report return no customer when it is set), Show Tax Registrations=Yes | Party Number, Party Name, Account Number, Taxpayer Id, the tax registrations (a TAN held there matches exactly) |

**Always pass `Period=` empty with Period From and Period To**: omitted, the add-in adds the latest
period as Period and the run returns that one period, or nothing, instead of the years. Pass the
exact names; fall back to a search only on `#BLITZ_REPORT_NOT_FOUND`.

## Pipeline
1. **Extract — DELEGATE** both reports to br-run-reports. Wait for each; touch nothing mid-run.
2. **Read Form 26AS** into `TDS_26AS` with formulas (one row per deductor transaction; mapping,
   status codes and the financial-year formula in `references/matching.md`). Rows whose booking
   status is not final (`F`) are kept but never counted as credit; they get their own total.
3. **Booked TDS** into `TDS_Booked`: one row per GL line with Party Number (through the account
   number in the customer master), Financial Year of the Accounting Date and the Accounted Amount
   (debit positive). A line without a customer number is **booked without customer** (a manual
   journal, usually) — listed, never spread over customers.
4. **Map deductors to customers** in the order of `references/matching.md`: the confirmed map
   sheet, a TAN held as a tax registration, a unique exact normalised name; the rest you propose
   from the two name lists and **the user confirms in one question**, largest amounts first.
   Confirmed pairs go to `TDS_Deductor_Map` for the next run. An unconfirmed deductor stays
   **unidentified** and is never netted into a customer.
5. **Reconcile** per party and financial year on `TDS_By_Customer` (SUMIFS over the two tables):
   TDS in 26AS, TDS booked, difference = 26AS − booked, class `Matched` (within the tolerance),
   `In 26AS, not booked`, `Booked, not in 26AS`, plus the `Unidentified deductor` and `Booked
   without customer` rows.
6. **Propose actions** on `TDS_Actions` exactly as the shared contract describes, every row
   `Proposed`, with the follow-up letter drafted for each `Follow up` row (customer, year, TDS
   booked against them, credit in Form 26AS, the difference, a request to file a correction
   statement or pay it by a date the user names). Never write a `Debit memo` row yourself.
7. **Summary** on `TDS_Recon` (first tab): per financial year the 26AS credit, booked, matched,
   not booked, booked not in 26AS, unidentified, booked without customer and not-final 26AS
   amounts; the ten largest differences; cells sharing a format adjacent, one write per block.
8. **Narrative** (≤5 bullets): matched share, largest gaps, the unidentified deductors to map,
   what the actions would book. Then offer br-ar-tds-adjustments for the approved rows.

## Hard rules
- **Never assign a deductor on similarity alone.** Exact evidence (map, TAN registration, unique
  exact normalised name) or the user's confirmation; everything else stays unidentified.
- The two totals survive: the class totals add back to the 26AS credit and to the TDS booked for
  every year — check it before the summary and say so if they do not.
- Never invent accounts, transaction types or a policy; the claim journal is proposed only where
  the user books claims that way.
- Analysis only: never write to Oracle and never run an upload from this skill.

## Degradation rules
- 26AS pasted without transaction dates (deductor totals only) → ask which financial year it is
  and reconcile that year only.
- No customer number on most GL lines (TDS booked by manual journals) → say the books cannot be
  attributed, show the deductor totals against the account total, and stop at that level.
- Customer master without TANs → matching by name only; say how many deductors that leaves open.

## Talk in the user's language
Customers, TANs, financial years and rupee amounts — never `br_*` functions or helper sheets.
