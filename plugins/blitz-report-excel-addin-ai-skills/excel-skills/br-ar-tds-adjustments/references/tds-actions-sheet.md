# The TDS_Actions sheet (contract between br-ar-tds-reconciliation and br-ar-tds-adjustments)

`br-ar-tds-reconciliation` writes it and never changes Oracle. `br-ar-tds-adjustments` reads it and
stages only the rows whose `Decision` is `Approved`. Row 1 holds the headers, data starts in row 2,
one row per customer and financial year and action. Find columns by their row-1 header text.

| Column | Content |
|---|---|
| Action | `Claim journal`, `Credit memo`, `Follow up` or `Debit memo` |
| Decision | `Proposed` when written; the user sets `Approved` (or `Rejected`). A `Follow up` row becomes a `Debit memo` row only when the user changes its Action after the follow-up deadline. |
| Financial Year | `FY2025-26` (April to March) |
| Party Number | the customer's party (registry) number |
| Customer Name | the party name |
| Account Number | the customer account the memo goes to: the account that carries the party's booked TDS, or the party's only account; blank when the party has several and none is evident - the adjustments skill asks |
| Amount | positive amount of the action in the ledger currency |
| TDS in 26AS | the party's Form 26AS credit for the year |
| TDS Booked | the party's TDS on the TDS account for the year |
| Deductor TAN | the TAN(s) of Form 26AS mapped to the party, comma-separated |
| Clearing Account | the account combination the party's TDS was booked to (its most used one); for a party with nothing booked, the most used combination of the whole TDS account |
| Reason | the line description for the memo or journal, e.g. `TDS FY2025-26 as per Form 26AS, TAN AAAA12345B` |
| Letter | the drafted follow-up text (`Follow up` rows only) |
| Result | written by br-ar-tds-adjustments only: `Uploaded - <transaction or journal>` or the error message |

Meaning of the actions:
- **Claim journal** - the part of the year's TDS that is both booked and in Form 26AS
  (the smaller of the two). It moves from the TDS clearing account to the income-tax TDS asset
  of that year, if the company books the claim that way; otherwise the user rejects these rows.
- **Credit memo** - TDS in Form 26AS that was never booked: the customer's open balance is
  overstated by it. An on-account credit memo to the customer whose line goes to the clearing
  account books it.
- **Follow up** - TDS booked that Form 26AS does not show: the customer deducted it but did not
  deposit or report it. The customer is asked to correct the TDS return or pay the amount.
- **Debit memo** - the same amount after the follow-up deadline: a debit memo to the customer
  whose line goes to the clearing account reverses the TDS, so the customer owes it again.
