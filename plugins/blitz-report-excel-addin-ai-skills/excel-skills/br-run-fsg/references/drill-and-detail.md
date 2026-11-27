# br-run-fsg — drilling a balance and the detail behind it

## Drill levels

`=br_fsg_drill_external("<cells>","<level>","<sheet>")` writes the lines behind the cells onto a NEW
sheet of this workbook and reports `DONE: <n> rows on sheet '<name>'`. Run it like any action, in
two operations (write and read; then replace the cell with text and read the status together).

| Drilled from | Level | You get |
|---|---|---|
| balance cells of a statement | `Balances` | one row per account combination behind the balance: opening, period debits and credits, closing |
| balance cells of a statement | `Journals` | the journal lines behind the balance |
| balance cells of a statement | `Subledger` | the subledger transaction lines behind the balance, directly |
| rows of a Balances drill sheet | `Journals` | the journal lines of those accounts |
| rows of a Journals drill sheet | `Subledger` | the subledger transactions behind those journal lines |
| rows of a Journals drill sheet | `Full Journal` | every line of those journals, all accounts |

Several cells or rows drill in ONE request onto one sheet (`"C8:C12"`, `"A4:A40"`). To keep each
balance's lines apart (one explanation per statement line), drill each cell on its own. A text or
total cell is not a balance, and rows without a drilldown link have nothing behind them: the status
then reads `ERROR: Select a balance cell ...` / `ERROR: Select one or more rows carrying a journal
drilldown.` / `ERROR: Select one or more journal rows to drill to the subledger.` - point the drill
at the balance cells or the drill sheet's data rows instead.

## The drill sheet

- Row 1 title, row 2 the criteria (period, amount type, currency, ledger), row 3 the column
  headings, data from row 4, and a total row (SUBTOTAL) after the data - leave it out of your own
  sums and counts.
- Find columns by their heading text, never by letter: the columns follow the chart of accounts and
  the site's drilldown setup. Drill sheets of the same level in one workbook share their columns,
  so read the heading row of the first one only.
- Journal lines carry, among others: Effective Date, Batch Name, Journal Name, Source Name, Category
  Name, Period, Currency, Line Number, entered and accounted debit/credit, Concatenated Segments,
  Line Description, and a drilldown link per row.
- Subledger lines carry, among others: Source Name, Category Name, Journal Name, Document Number,
  Transaction Number, Transaction Date, Vendor Or Customer, DESCRIPTION, Purchase Order, Asset
  Number, Project, Sales Order, Goods Receipt Number, Cash Receipt Number, entered and accounted
  amounts.
- Journals whose source has no subledger detail (manual, spreadsheet, intercompany, payroll and
  similar journals) show no link and drill to nothing - explain them from the journal lines.

## Analysing the drilled lines (in the workbook, as Excel formulas)

1. **Tie-out first.** The drill restates the balance it came from: compare the drill's net
   (accounted debits minus credits) with the balance cell and report any difference before drawing
   conclusions. A difference usually means a restriction the drill does not share (an amount type
   other than PTD, journal source or category filters) - say so rather than guessing.
2. **Where the amount comes from.** Group by Source Name, then Category Name, then Journal Name (journal
   lines) or Vendor Or Customer and Transaction Number (subledger lines); give each group's total and
   share, largest first. Use dynamic-array formulas (`UNIQUE`, `SUMIFS`, `SORTBY`) on a new analysis
   sheet so the user can see and re-use the working; never type computed numbers in. Subledger lines
   with no Vendor Or Customer and no Transaction Number (older or converted data posted without
   document links) are a group of their own, `No document reference`, with their total: the groups
   still add up to the drill. Never present the documents you can name as all of a source - say how
   much of its amount they cover.
3. **What stands out.** Manual journals in a subledger-fed account, one-off large lines, round
   amounts, entries late in the period or reversed in the next, a single vendor or customer driving
   most of the movement.
4. Report the findings with the cells or rows they come from.

## On to the documents: invoices, purchase orders, payments, assets

When the user wants the documents behind drilled lines, run a Blitz Report for them with the
**br-run-reports** skill: the report the drill sheet's own links name where it has links, otherwise
the report of the table further down.

### The drill sheet's own links

A site can define, for each drill level, the Blitz Report a column leads on to - the invoice report
from the invoice or transaction number, the purchase order report from Purchase Order, and so on. A
moment after the drill the add-in turns the cells of such a column into links: a cell still shows
its value, and its formula names the report and what to pass to it:

`br_run_report(br_drilldown("<value>","<report>","<template>",<n>),br_environment("<environment>","<responsibility>"),br_parameters("<parameter>",<source>,"<parameter>",<source>))`

1. **Find them.** Read the formulas, not the values, of the drill sheet's data rows; where you can
   read values only, `=FORMULATEXT('<drill sheet>'!A4:AZ40)` on `blitz_` lists them (an error for a
   cell without a formula). A link's formula contains `br_run_report(br_drilldown(`, and a column
   holds links only in the rows that show a value. None on the sheet: read once more, as they are
   written just after the drill, then go by the table below.
2. **Read one link of the column you follow**: report, template (often empty), environment,
   responsibility, the number `<n>`, and the source of every parameter:

   | Source in the formula | What to pass |
   |---|---|
   | `"$SELF"` | the values the link cells show |
   | a cell reference (`K4`) | the values of that column in the same rows |
   | `"$PARAM:Ledger"`, `"$PARAM:Period"`, `"$PARAM:Currency"` | the ledger, period or currency the sheet was drilled for (its row 2 names them) |
   | any other quoted text | that text (`<null>` clears the report's own default) |
3. **Run the report once for all the rows you explain**:
   `=br_run_report_external("<report>","<parameter>=<v1>,<v2>; <parameter>=<value>; DRILLDOWN_ASSIGNMENT_ID=<n>","<template>","<environment>","<responsibility>")`
   with the distinct values of those rows. `DRILLDOWN_ASSIGNMENT_ID=<n>` goes in when `<n>` is above
   0: the run then also takes the values the site fixed for the report's other parameters, as a
   click on the link does. Leave it out for 0 or a negative number.
4. A link fed from two columns (invoice number and supplier) returns every combination of the
   values passed: keep the report rows whose combination occurs on the drill rows.

### Without links: the report by subledger

Inspect the report's parameters first (names can differ by version and setup), and run it with a
responsibility of that subledger (a Payables one for invoices, `br_responsibilities_external()`):
after statement work the session is on the statement's General Ledger responsibility, under which a
subledger report may not be available or may see other operating units.

| Subledger lines from | Report | Restrict with (several values allowed) |
|---|---|---|
| Payables invoices | AP Invoices and Lines | Invoice Number (+ the ledger or operating unit the report requires) - invoice numbers repeat across suppliers, so keep only the rows of the drill's suppliers afterwards |
| Payables payments | AP Invoice Payments | Check Number |
| Receivables transactions and adjustments | AR Transactions and Lines | Transaction Number |
| Assets | FA Asset Additions or FA Asset Transfers | Asset Number |
| Receiving (Cost Management) | PO Receiving Transactions | Receipt Number |
| Purchasing | PO Headers and Lines | PO Number |
| Receipts, Projects, Cash Management, anything else | no exact match - explain from the subledger lines | |

### Either way

- Take the distinct numbers of the rows from the drill sheet (a `UNIQUE` formula) and pass them as
  one comma-separated parameter value. A long list goes into a helper cell on `blitz_` that the run
  formula references (`=br_run_report_external("AP Invoices and Lines", B2)`), because a formula's
  text is limited. A number containing `,` or `;` cannot be passed - say so and use the drill lines
  for it instead.
- The report lands on its own sheet; relate its rows back to the drill (same numbers) and say how
  many of the drill's transactions it covers.
