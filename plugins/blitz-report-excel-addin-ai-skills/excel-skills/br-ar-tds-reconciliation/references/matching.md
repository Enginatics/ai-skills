# Form 26AS reading, deductor matching and the reconciliation classes

## Reading Form 26AS (step 2)
Part I of Form 26AS lists, per deductor, a summary line (Name of Deductor, TAN of Deductor, Total
Amount Paid / Credited, Total Tax Deducted, Total TDS Deposited) followed by its transaction lines
(Section, Transaction Date, Status of Booking, Date of Booking, Remarks, Amount Paid / Credited,
Tax Deducted, TDS Deposited). A text export of the portal separates fields with `^`; an AIS export
has one row per transaction with the deductor on every row. Map the columns by their header
meaning, show the mapping once when a header is ambiguous, and build `TDS_26AS` with one row per
transaction:

`TAN | Deductor | Section | Transaction Date | Financial Year | Status | Amount Paid | Tax Deducted | TDS Deposited`

- A deductor's summary line is not a transaction: carry its TAN and name down to its transaction
  lines and drop the summary line itself (else every deductor counts twice).
- **Status of Booking:** only `F` (final) counts as credit. `U` (unmatched), `P` (provisional),
  `O` (overbooked) and any other code are shown as *not final* per customer and year.
- **Financial year** (April to March) of a date in A2:
  `=LET(y,YEAR(A2)-(MONTH(A2)<4),"FY"&y&"-"&TEXT(MOD(y+1,100),"00"))`. Use the same formula for
  the Accounting Date of the booked lines.
- The amount that counts is `TDS Deposited` unless the user chose `Tax Deducted`; say which.
- Keep the sections the user asked for (default all) and show the total per section.

## Matching a deductor to a customer (step 4), in this order
1. **Confirmed map**: `TDS_Deductor_Map` (`TAN | Deductor | Party Number | Party Name | Basis |
   Confirmed On`) from an earlier run, or one the user pastes. A TAN found there is settled.
2. **TAN registration**: a tax registration number in the customer master equal to the TAN.
3. **Exact normalised name**, unique over the parties: normalise the deductor and party names with
   the formula in `references/party-name-normalisation.md`. Two parties with the same normalised
   name are not a match; they are candidates.
4. **Suggestions for the rest**, by the comparison rules of the same reference: at most three
   parties per deductor, each with its evidence. **A suggestion is never an assignment.**
5. **Confirmation**, one question, largest 26AS amounts first: `Deductor (TAN) - amount - proposed
   customer - evidence`, options to accept all shown, choose per line, or leave them unidentified.
   Write accepted pairs to `TDS_Deductor_Map` with Basis `Confirmed` and the date.

A deductor without a customer after step 5 is **Unidentified deductor**: its amount is shown on
its own row per TAN and year and never added to a customer.

## Classes per customer and financial year (step 5)
| Class | Test (difference = 26AS - booked) | Proposed action |
|---|---|---|
| Matched | abs(difference) ≤ tolerance | Claim journal for the matched amount |
| In 26AS, not booked | difference > tolerance | Claim journal for the booked part, credit memo for the difference |
| Booked, not in 26AS | difference < -tolerance | Claim journal for the 26AS part, follow up for the difference |
| Unidentified deductor | 26AS line without a customer | none until mapped |
| Booked without customer | GL line without a customer | none: the user explains the journals |

The class totals of every year add back to the 26AS credit and to the TDS booked. A customer the
user excluded is reconciled and shown, but gets no action row.
