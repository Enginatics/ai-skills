# Conversion Log messages

`Message` texts as the converters write them (`<...>` = a variable part). Match on the fixed words.
**Class**: Fix = you can correct it after the confirmation; Ask = needs the user's answer first;
Info = nothing to change; Re-run = correct the input if needed, then the user runs the converter
again on this workbook. **Proc** = the procedure in `fixes.md`.

## Spreadsheet Server

| Message | Class | Proc |
|---|---|---|
| `reads the period number from <cell> instead of the period cell <cell>` | Info — the converter already repointed this formula; check it shows the period number it showed before | — |
| `uses the period cell <cell>, which now holds the period name instead of the period number` | Fix | P1 |
| `uses the period cell <cell> and could not be rewritten: <error>` | Fix (an array formula: rewrite the whole array range) | P1 |
| `period cell <cell> formula =<formula> replaced by its value <n>` | Fix | P2 |
| `period cell <cell> is shared by formulas with different formats or ledgers (...), converted for the first` | Ask | P3 |
| `period cell <cell>: <format> <value> embedded as literal period numbers, the link to <cell> is not kept` | Info (a quarter or range period no longer follows that cell; P2 restores it on request) | P2 |
| `literal period <p> resolved to "<name>" at conversion time` | Info (the period is fixed text; offer a period cell only if the user wants it to roll) | — |
| `format cell <cell> is formula-driven, amount type <type> embedded as a literal` | Ask | P4 |
| `unknown format '<f>' left unchanged` | Ask | P4 |
| `translation type E kept, ledger <L> is not on this instance; change it to T where <C> is that ledger's currency` | Ask | P5 |
| `T with <C> on ledger <L> returns that ledger's own currency total, verify <C> is its currency` | Ask (confirm only) | P5 |
| `translated balances in <C> are not supported, T returns the ledger currency total` | Ask | P6 |
| `translation type M (multiple reporting currencies) has no Blitz Report equivalent` | Ask | P6 |
| `unknown translation type '<t>'` | Ask | P5 |
| `key data cell <cell> is formula-driven, its values are embedded as literals` | Info | — |
| `key data <name>=<value> has no Blitz Report equivalent and is ignored`, `key data <name> is ignored` | Info | — |
| `hierarchy value <v> keeps its segment suffix, segment <n> of ledger <L> is not on this instance` | Ask, recommend Re-run | P7 |
| `hierarchy value <v> does not end with <suffix>, the segment name of ledger <L>, and is kept as is` | Ask | P7 |
| `hierarchy values are converted to parent values, the refresh reports an unknown one as invalid` | Info | — |
| `segment value <v> in <cell> is formula-driven and needs manual conversion` | Fix | P8 |
| `segment list or @ field <v> in <cell> has no Blitz Report equivalent` | Ask | P9 |
| `single character mask <v> only applies together with a % wildcard` | Info | — |
| `numeric cell <cell> displays <text> but holds <value>, converted from the stored value` | Info (check the value) | — |
| `<cell> is used as <a> and <b>, converted as <a>` | Ask (the cell feeds two different parameters; offer a second cell for <b>) | P3 |
| `<list> of ledger <L> could not be read: <error>` | Info | — |
| `balance type <cell> is empty` (level Error) | Ask | P11 |
| Any other level `Error` (the cell still holds the Spreadsheet Server formula) | Re-run | P10 |

## GL Wand (all level Error)

| Message | Class | Proc |
|---|---|---|
| `left unconverted: segment descriptions need the ledger's segment names, which are not loaded - log in and convert again` | Re-run (log in first) | P10 |
| `left unconverted: glw_set_of_books_name needs the statement's ledger, and the sheet names none` | Re-run (choose the ledger on the ribbon first) | P10 |
| `left unconverted: a segment description whose segment number is not a literal number` | Fix, then Re-run | P10 |
| `left unconverted: a segment description names segment <n>, which the ledger's chart of accounts does not carry` | Ask | — |
| `left unconverted: a GL Wand call could not be parsed` | Re-run after correcting the syntax | P10 |
| `could not be written: <error>`, `parameter cell could not be written: <error>` | Re-run (unprotect the sheet first) | P10 |

## Batch lines (no cell)

| Message | Class |
|---|---|
| `the formulas name ledger <L>, which your responsibilities do not offer; the workbook is bound to <D>` | Ask: convert again under a responsibility that offers <L>, or confirm <D> |
| `period or segment values use characters other than the delimiters <d> chosen for this batch; check the converted values` | Ask: which range, list and exclusion characters this workbook uses; then P8 on the affected values |
| `The conversion stopped: <error>` | Re-run |
