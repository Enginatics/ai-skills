# Fix procedures

## The converted formulas (for reading them; never name them to the user)

- Balance: `br_balance(period, amount type, currency, currency type, balance type, budget,
  encumbrance, ledger, movement, multiplier, , , segment 1, segment 2, ... segment 20)` - segment n
  is argument 12+n.
- Period name: `br_period_name(year, period number, ledger, , )`.
- Period offset: `br_period_offset(period cell, n, , , ledger)` = n periods after that cell's period.
- Segment description: `br_segment_description("segment name", value, ledger)`.
- A stored formula may carry a file prefix before the function (`'...Blitz Report.xlam'!br_balance(`,
  `[1]!br_balance(`): keep it exactly as it is.
- Segment values: `a;b` list, `a-b` range, `~a` excluded, `%` wildcard; a parent value includes its
  children. Amount types: PTD, QTD, YTD, CTD (CTD over a period range `first-last`). Currency type:
  T = the ledger currency total, E = amounts entered in that currency.
- Every argument is a plain cell reference or a quoted literal; a computed value goes into a helper
  cell. A helper cell is an empty cell next to the cell it serves (read it first); prefer the cell to
  the right, then the one below.

When a reference moves to another cell, keep its `$` anchors (`$K$5` -> `$S$5`, `K$5` -> `S$5`) and
prefix the sheet (`'Sheet name'!`) when the target is on another sheet than the formula.

## P1 - A formula still reads a period cell as a number
The period cell (named in the message) now shows a period name; the formula (log `Cell`) expects the
period number it held before. Read both formulas.
1. Find where the number is now: the period cell's formula.
   - `br_period_name(year, <ref>, ...)` with a cell reference: the number is in that cell. Replace
     the formula's reference to the period cell with it.
   - `br_period_name(year, "n", ...)` with a quoted number: write n into a helper cell, change that
     argument from `"n"` to the helper (absolute, `$L$5`), and replace the formula's reference to
     the period cell with the helper.
   - `br_period_offset(<base>, n, ...)`: the number is the base cell's number plus n. Find the base
     cell's number source as above and replace the reference with `(<source>+n)`.
   - Two period calls joined by `&"-"&` (a range or a year to date): ask which number the formula
     needs.
2. The period cell is read inside a range (`SUM(K5:K9)`), or the formula is an array formula: ask.

## P2 - Restore a period cell's own formula
The message shows the formula the period cell had (`=<formula>`) and the value it was replaced by.
Write that formula into a helper cell and change the period call's number argument (the quoted value)
to the helper, so the period follows it again.

## P3 - One cell, two meanings
List the converted formulas that read the cell (search the formulas for its address). Offer a second
cell beside it holding the other value, and point the formulas that need the other meaning at it.
Never change which value the first group reads.

## P4 - Format cell / amount type
Spreadsheet Server format -> amount type: PER -> PTD, LTD -> YTD, QTR or DQTR -> QTD (the period
becomes the quarter's last period), YTD or RANGE -> CTD over a period range.
- Formula-driven format cell that only switches among PER, LTD, QTR and DQTR, and the user wants it
  to keep driving the balances: helper cell next to it with
  `=IFERROR(INDEX({"PTD","YTD","QTD","QTD"},MATCH(<format cell>,{"PER","LTD","QTR","DQTR"},0)),<format cell>)`,
  then replace the quoted amount type (argument 2) in each balance formula that came from that
  format cell (same row or column as the log `Cell`) with the helper.
- YTD or RANGE also change the period: leave the literal and explain.
- Unknown format: ask what it means, then write the amount type it maps to.

## P5 - Currency type E or T on a ledger this instance does not have
Ask: "Is <C> the ledger currency of <L>?" Yes -> T: write `T` into the cell the balance's argument
4 reads (it changes every balance reading that cell), or replace the quoted `"E"` in that formula.
No -> leave E. Unknown type -> ask what it stands for.

## P6 - Reporting currency (M) or a translated currency
Blitz FSG reads a reporting currency from its reporting ledger. Ask for that ledger's name; set the
balance's ledger (argument 8, or the cell it reads) to it and the currency type to T. Without a
reporting ledger there is no equivalent: mark Needs you.

## P7 - Hierarchy value with a segment suffix
A Spreadsheet Server hierarchy value is `<parent value>_<Segment_Name>` (`1000_Natural_Account` =
parent 1000 of segment "Natural Account"). The converter strips the suffix only on an instance that
has the ledger. Recommend converting on such an instance. If the user instead confirms the segment
name, strip `_<Segment_Name>` from every value of that segment: the values sit in the segment cells
the balance formulas read (argument 12+n), often several `;`-separated in one cell. Show before/after
per cell; never strip a suffix that differs from the confirmed one.

## P8 - Formula-driven segment value
Keep the formula; rewrite the Spreadsheet Server syntax inside its quoted text only: drop `[` and `]`,
list separator `,` -> `;`, range `.` -> `-`, exclusion `/` -> `~`, `*` -> `%`, drop a leading `^^`
(and its suffix, P7). Use the delimiters the batch line names when the log has one.

## P9 - Segment list (`^list`) or field (`@field`)
These have no Blitz Report equivalent. Ask for the values the list held and write them `;`-separated
into the cell.

## P10 - Let the converter finish
Correct the input first, then the user runs the converter again on this workbook (Blitz Report ribbon
> Tools > Converter > Spreadsheet Server or GL Wand). It converts only the formulas still in the
old form, and writes a new Conversion Log sheet for what remains.
- An argument that is an expression, or a period argument that is not a cell: move the expression
  into a helper cell and point the argument at it.
- "the segment names of ledger <L> are not loaded": choose <L> in the ribbon's Ledger box on that
  sheet first.
- "period <n> of <year> not found": ask for the period the user means.
- "balance type P (project) is not supported": no equivalent, Needs you.
- GL Wand "not loaded" / "names none": log in, or choose the ledger on the ribbon, first.
- "could not be written": the sheet is protected or the cell is part of an array formula; unprotect
  it first.

## P11 - Balance type cell is empty
The formula reads its balance type (A actual, B budget, E encumbrance) from a cell that is empty,
usually a spare column of the template; Spreadsheet Server returned nothing for it. List the columns
affected (one cell names them all) and ask:
- it should read a balance type: write that letter into the named cell (one cell serves the whole
  column), then let the converter finish (P10);
- the column is unused: clear its unconverted formulas, after the user confirms.
