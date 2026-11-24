---
name: br-ar-customer-master-audit
description: >
  Audit the Oracle EBS customer master in Excel: duplicate customers (same tax id or same
  normalised name on different parties), missing payment terms, bill-to sites or address data,
  credit settings that contradict each other (a credit limit on advance-payment terms, credit check
  without a limit), inactive parties with active accounts, and, for India, GSTIN and PAN checks
  (length, format, check digit, state code against the site's state, PAN inside the GSTIN). Lists
  every finding with its evidence and the proposed correction on an Audit_Findings sheet; changes
  nothing in Oracle. Use when the user asks for a customer master audit, customer data quality,
  duplicate customers, GST number or PAN validation, or a correction list for the master data team.
shared:
  - customer-audit-findings
  - party-name-normalisation
# Trigger: Slash command + auto
---

# Customer Master Audit (br-ar-customer-master-audit)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.

> **Performance:** read `br-analytics-standards` at the start of every run. Read
> `references/checks.md` before scoring and `references/customer-audit-findings.md` before writing
> the findings.

Find the customer records that will cause trouble downstream — wrong invoices, tax returns that do
not reconcile, orders released without credit control — and hand over one correction list. You own
orchestration, the checks and the findings; br-run-reports does extraction. **Read-only:** the
corrections the customer upload can make are staged by **br-ar-customer-master-fix** after the user
approves them; everything else goes to the master data team as the list.

## When to use
"Audit the customer master", "find duplicate customers", "check the GST numbers", "customers
without payment terms", monthly master data review, before a migration or a go-live.

## Inputs (ask once, up front, in one question)
- **Operating unit(s)** (required).
- **Checks**: default all generic checks of `references/checks.md`; the India checks when the
  customers are in India or the user asks for them.
- **Policy lists**, only for the checks that need them: the payment terms that mean payment in
  advance (offer the terms found in the data as a list; never guess them from their names), and
  whether every active account must have a collector or a default warehouse.
- **Where GSTIN and PAN are held** when the India checks run: by default the GSTIN in the site's or
  party's tax registration number and the PAN in Taxpayer Id; ask when the data shows otherwise.

## Reports used (authoritative names — do NOT broad-search for them)
| Report (exact name) | Run with | Role |
|---|---|---|
| `AR Customers and Sites` | Operating Unit, Level=Site Use, Show Profile Amounts=Yes, Show Tax Registrations=Yes | one row per site use (and tax registration and profile amount): party, account, site, address, state, statuses, payment terms, credit check and hold, credit limits, collector, warehouse, Taxpayer Id, tax registrations |

Show active only stays at its default (Yes). Several operating units → one run each. Pass the
exact name; fall back to a search only on `#BLITZ_REPORT_NOT_FOUND`.

## Pipeline
1. **Extract — DELEGATE** to br-run-reports. Wait; touch nothing mid-run.
2. **Build the check columns** next to the data on a helper sheet with formulas
   (`references/checks.md`): normalised party name, PAN and GSTIN findings, state code against the
   site's state, missing values, credit consistency. One formula per column, filled down.
3. **Duplicates** on `Duplicate_Groups`: different parties sharing a Taxpayer Id (or the PAN inside
   their GSTINs) or a normalised name; then the near-identical names you find by comparison
   (`references/party-name-normalisation.md`), marked as suspects with their evidence. One party
   with a GSTIN per state is normal and never a duplicate.
4. **Findings** on `Audit_Findings` per the shared contract, one row per finding, `Decision`
   `Proposed`; a `Proposed Value` only where it is derived (the PAN of a valid GSTIN when Taxpayer
   Id is blank) or the user gave it.
5. **Scorecard** on `Customer_Audit` (first tab): per check the severity, the number of findings
   and of accounts; the accounts with the most findings; the share of active accounts clean.
   Cells sharing a format adjacent, one write per block.
6. **Narrative** (≤5 bullets): the worst checks, the duplicate suspects, what the customer upload
   can correct and what goes to the master data team. Offer br-ar-customer-master-fix for the
   approved upload-fixable rows.

## Hard rules
- A finding states its evidence; a duplicate is a **suspect** until a person decides, and merging
  parties is never proposed as an upload fix.
- Never invent a correction value: no payment term, credit limit or tax number that the data or
  the user did not give.
- Policy checks run only with the user's policy; without it they are skipped and said so.
- Analysis only: never write to Oracle and never run an upload from this skill.

## Degradation rules
- No tax registrations in the data (GSTIN kept outside the standard tax registrations, as some
  localisations do) → say the GST checks could not run, and run the rest.
- A state the GST state list does not know → `State not checked`, never a mismatch.
- A very large customer base → run with `Show trx count within x days=365` and audit the accounts
  with transactions first, and say so.

## Talk in the user's language
Customers, accounts, sites, tax numbers and fields — never `br_*` functions or helper sheets.
