# br-run-fsg — statement recipes

All formulas below assume a five-segment chart whose profile pattern is
`=br_balance("<Period>","PTD","USD","T","A",,,,,,,,"<Company (1)>","<Department (2)>","<Account (3)>","<Sub-Account (4)>","<Product (5)>")`.
Build every formula from YOUR ledger's pattern: same idea, the segment slots it lists.

## The criteria block (every statement starts with it)

Set B1:B5 to Text, then write:

| | A | B |
|---|---|---|
| 1 | Period | `Dec-12` |
| 2 | Amount Type | `PTD` (income statement) or `YTD` (balance sheet) |
| 3 | Currency | the functional currency from the profile |
| 4 | Currency Type | `T` |
| 5 | Balance Type | `A` |

Every balance formula then takes `$B$1,$B$2,$B$3,$B$4,$B$5` as its first five arguments, so the
user changes the period in one cell and refreshes. Leave one empty row under the block.

## One balance ("what was cash at the end of December?")

1. Find the account: `=br_fsg_values_external("<Ledger>","Account","cash")`.
2. On the statement sheet, under the criteria block (Amount Type `YTD` for a balance at period end):
   `A8` (Text) `1110`, `B8` `=br_segment_description("Account (3)",$A8)`,
   `C8` `=br_balance($B$1,$B$2,$B$3,$B$4,$B$5,,,,,,,,"","",$A8,"","")`.
3. Refresh the sheet, read C8, answer with the value and the period, and say where it is.

## Trial balance by account

1. List the detail accounts: `=br_fsg_values_external("<Ledger>","Account")` (rows with Parent blank;
   use `search` or a parent value when the list is long).
2. Headings in row 7 (`Account`, `Description`, `Balance`), one account per row from row 8: account
   in column A (Text), `=br_segment_description("Account (3)",$A8)` in B,
   `=br_balance($B$1,$B$2,$B$3,$B$4,$B$5,,,,,,,,"","",$A8,"","")` in C, filled down.
3. A total row `=SUM(C8:C<last>)` - a trial balance on all accounts of a balanced ledger totals 0.
4. Refresh. Rows that came back 0 can be hidden or filtered once the user agrees.

## Income statement / balance sheet

1. Agree the structure with the user before building: which accounts or account ranges make up each
   line (revenue, cost of sales, operating expenses...; assets, liabilities, equity). Offer what the
   chart already has: parent values (`Parent` = Yes in the segment list) are ready-made summary lines,
   and `=br_fsg_values_external("<Ledger>","Account",,"<parent>")` lists what one rolls up. Never
   guess the account classification silently - state it, the user confirms. Built from a parent,
   the statement carries EVERY detail value it rolls up: one that fits no section goes on an
   `Other` line, never off the statement.
2. One row per line: label in A, the account criterion in B as Text (`4000-4999`, a parent value, or
   `5100;5200`), the balance in C with `$B8` in the account slot; revenue, liability and equity rows
   take multiplier `-1` (argument 10) if the user wants them positive.
3. Subtotals and totals as ordinary Excel formulas (`=SUM(C8:C10)`, `=C11-C15`), never as balance
   formulas.
4. Income statement: Amount Type `PTD` for the month, `YTD` for the year to date (two columns: put
   `PTD` and `YTD` in a header row and reference that cell instead of `$B$2`). Balance sheet: `YTD`.
5. A `Check` row under the bottom line: the bottom line minus the balance of the parent itself (the
   parent value in the account slot, multiplier `-1` when profit shows positive). It reads 0 when no
   account is missing; anything else is an account left off - add it, never report around it.

## Columns per period

Period headings in row 7: C7 `=$B$1`, D7 `=br_period_offset(C7,-1)`, E7 `=br_period_offset(D7,-1)`
and so on - the refresh resolves the periods before the balances that read them. Balance in C8:
`=br_balance(C$7,$B$2,$B$3,$B$4,$B$5,,,,,,,,"","",$A8,"","")`, filled right and down.
Same period last year: `=br_period_offset($B$1,-12,,"Exclude")`.

## Columns per department (or any other segment)

Department values across row 7 (Text, from `=br_fsg_values_external("<Ledger>","Department")`), the
balance in C8: `=br_balance($B$1,$B$2,$B$3,$B$4,$B$5,,,,,,,,"",C$7,$A8,"","")`.

## Actual against budget

Budget names: `=br_fsg_values_external("<Ledger>","Budget")`. Actual in C, budget in D:
`=br_balance($B$1,$B$2,$B$3,$B$4,"B","<Budget name>",,,,,,,"","",$A8,"","")` (or the budget name in
a Text cell referenced instead), variance `=C8-D8`, and `%` as `=IF(D8=0,"",(C8-D8)/ABS(D8))` - over the magnitude, so a credit
balance that grows shows a negative % like its negative variance.

## Before you report

- Refresh status `DONE` with no cells "still without an answer" - else fix and refresh.
- Totals that should tie do (trial balance 0; assets = liabilities + equity on a full balance sheet,
  where the current year's result is part of equity until closed; the `Check` row of a statement
  built from a parent reads 0).
- Say the ledger, period, amount type, currency and sign convention the numbers are in.
