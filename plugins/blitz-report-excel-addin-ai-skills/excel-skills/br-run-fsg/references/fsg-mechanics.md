# br-run-fsg — mechanics

## The functions

Write each into a cell of the helper sheet `blitz_` (never activate it) and read the result. They
are Excel worksheet functions of the Blitz Report add-in, not tools or connectors.

| Function | Purpose | Returns |
|---|---|---|
| `br_fsg_ledgers_external([environment])` | ledgers a statement can be built for | `Ledger` |
| `br_fsg_ledger_external(ledger, [environment])` | what a balance formula for the ledger needs | `Item \| Value \| Balance Argument`: Ledger, Functional Currency, Latest Open Period, one `Segment` row per segment in display order (its name, e.g. `Account (3)`, and its argument number), `Balance Formula` (the pattern) |
| `br_fsg_values_external(ledger, list_name, [search], [parent_value], [environment])` | values of one list, as the formula takes them | `Value \| Description`, plus `Parent` (Yes = a parent value that rolls up children) for a segment |
| `br_fsg_new_statement_external(ledger, [sheet_name], [environment])` | make a sheet a statement of the ledger | action: `BLITZ_RUNNING: ...`, then status `DONE: sheet '<name>' is a statement for ledger '<ledger>' (functional currency ..., latest open period ...)` |
| `br_fsg_refresh_external([sheet_name], [force])` | calculate the statement's balances | action: status `DONE: <n> value(s) refreshed[; still without an answer: <cells>][; <warnings>]` |
| `br_fsg_drill_external(cell_address, level, [sheet_name])` | the lines behind balance cells, on a new sheet | action: status `DONE: <n> rows on sheet '<name>'` or `DONE: 0 rows - the drill found no lines` |
| `_blitz_run_status` (workbook name, read with `=_blitz_run_status`) | outcome of the last action | `RUNNING: ...` / `DONE: ...` / `ERROR: ...` |

`list_name`: a segment as the ledger profile names it (`Account (3)` or just `Account`), or one of
`Period`, `Amount Type`, `Balance Type`, `Currency`, `Currency Type`, `Budget`, `Encumbrance Type`,
`Journal Source`, `Journal Category`, `Conversion Type`, `Movement`. `search` keeps values whose value
or description contains it - use it on large segments (a list stops after 2000 values and says so).
`parent_value` lists the members of that parent value of a segment.

The three lookups and the statement function take an optional environment as their last argument,
the way the report functions do (see the br-run-reports skill): omit it to use the current one;
`br_environments_external()` lists them; only a connected environment can be used, since a worksheet
function cannot log in. Refresh and drill take NO environment argument: a statement is always
refreshed and drilled by the environment and responsibility it was made in.

### Errors returned in the cell
| Return | Meaning / what to do |
|---|---|
| `#BLITZ_NOT_CONNECTED` | ask the user to connect on the Blitz Report ribbon |
| `#BLITZ_ENV_NOT_CONNECTED` / `#BLITZ_ENV_NOT_FOUND` / `#BLITZ_ENV_SWITCH_FAILED` | that environment is not connected / not known / could not be switched to - ask the user to select it under Environments on the Blitz Report ribbon |
| `#BLITZ_LEDGER_NOT_FOUND` | the name is not a ledger of the user's responsibilities - list the ledgers and pick the exact name |
| `#BLITZ_LIST_NOT_FOUND` | not a list or segment of the ledger - use the names above or the profile's segment names |
| `#BLITZ_SHEET_NOT_FOUND` / `#BLITZ_NOT_FSG` | no such sheet / the sheet is not a statement - make it one first |
| `BLITZ_RUNNING: a run is already in progress` | another action is still running - wait for its status, do not retry |
| `#BLITZ_ERROR: ...` | anything else - report the message |

## Running an action and waiting

Same discipline as running a report:
1. Write the action formula and read the cell's return in the SAME operation, then in your next
   operation replace that cell with plain text. A second read of a still-present action formula
   can start the action twice.
2. Read `=_blitz_run_status` once per turn, generously spaced; never re-enter the action formula
   to check on it. A value read before your own trigger is stale - it belongs to an earlier action.
3. While an action runs, pause other workbook edits: the add-in is writing the sheet.
4. `ERROR: ...` is the add-in's reason - report it, fix what it names, and try once more at most.

## The balance formula

`=br_balance(period, amount type, currency, currency type, balance type, budget, encumbrance type,
ledger, movement, multiplier, journal source, journal category, segment 1, ..., segment 20)` -
arguments 13 onward are the segments in COLUMN order, which on many charts is not the display
order: always take each segment's argument number from the ledger profile, or start from its
`Balance Formula` pattern and replace each `<placeholder>`.

| # | Argument | Values |
|---|---|---|
| 1 | Period | a period name (`Dec-12`); a range of periods for CTD (`Jan-12-Mar-12`); an effective date or date range for the JED types (`01-Dec-2012-15-Dec-2012`) |
| 2 | Amount type | `PTD` period to date, `QTD`, `YTD`, `CTD` custom range, `FYS` fiscal year start, `FYE` fiscal year end, `JED` journal effective date - full list with descriptions from the `Amount Type` list |
| 3 | Currency | normally the ledger's functional currency (profile) |
| 4 | Currency type | `T` total in the ledger currency (the normal choice), `E` entered amounts in a foreign currency - see the `Currency Type` list |
| 5 | Balance type | `A` actual, `B` budget (with argument 6), `E` encumbrance (with argument 7) |
| 6 | Budget | a name from the `Budget` list, only with `B` |
| 7 | Encumbrance type | from the `Encumbrance Type` list, only with `E` |
| 8 | Ledger | leave empty: the statement's own ledger |
| 9 | Movement | empty = net, `Dr` debits only, `Cr` credits only |
| 10 | Multiplier | empty = 1; `-1` shows the balance with the opposite sign |
| 11, 12 | Journal source, journal category | restrict to journals of that source / category; empty = all |
| 13+ | Segments | see below; empty = every value of that segment |

Segment value syntax: one value `"1110"`, a range `"1110-1199"`, several `"1110;1210"`, an exclusion
`"~1120"` (combine: `"11%;~1120"`), a wildcard `"11%"`, a parent value (expands to its children).
Always restrict the account segment: a balance restricted only on the balancing segment (company)
nets to zero, as double entry does.

Signs: balances are debit positive and credit negative, so revenue, liabilities and equity come
back negative. Present them positive with multiplier `-1` on those rows, and say which convention
the statement uses.

## The other FSG functions (also calculated by the refresh)

| Formula | Returns |
|---|---|
| `=br_segment_description("<Segment name>", <value>)` | the description of a segment value; the segment name exactly as the profile lists it, e.g. `"Account (3)"` |
| `=br_period_offset(<period>, <n>, , [adjustment])` | the period n periods before (negative) or after; `"Exclude"` as the 4th argument skips adjustment periods - use it for the same period last year (`-12`) |
| `=br_period_name(<year>, <period number>)` | the name of a period by year and number |
| `=br_daily_rate(<from currency>, <to currency>, <conversion type>, <date>)` | a daily exchange rate |

## Formula hygiene (each mistake gives a wrong number or a dead cell)

- Every argument is a quoted literal or a plain cell reference (`$B$1`, `C$1`, `$A8`), never an
  expression or a nested function - the add-in reads the arguments from the formula text.
- Cells holding a literal period, segment value or code are Text format, set BEFORE the value is
  written (`Dec-12` would become a date, `01` would become 1).
- A formula is never written into a Text-format cell (it would stay text): set General first.
- Anchor references with `$` so one formula fills across the period columns and down the rows.
- After writing or changing formulas the cells show `(pending)` until the next refresh. That is
  normal - refresh, do not rewrite them.

## The statement sheet

`br_fsg_new_statement_external(ledger, sheet_name)`:
- no sheet carries that name: a new sheet with it (blank name: a new sheet Excel names);
- an empty sheet: built into;
- a sheet holding the user's layout: claimed as it is, nothing on it changes;
- already a statement of the same ledger: `DONE`, nothing to do; of another ledger: `ERROR` - use
  another sheet rather than re-pointing the user's statement.

## Refresh

- `br_fsg_refresh_external("<Sheet>")` calculates the values still pending (new or changed formulas).
  `force` TRUE fetches every value again - use it for current balances after new postings. A blank
  sheet name refreshes every statement of the workbook, always forced.
- `<n> value(s) refreshed` counts server answers, not cells - cells with the same arguments share one.
- `still without an answer: <cells>` lists cells showing `(pending)`, an error, or the add-in's own
  answer: `Error (Period)` / `(Amount Type)` / `(Currency)` / `(Currency Type)` / `(Balance Type)` -
  that argument is empty or unusable; `invalid (Period)` - no such period in the ledger;
  `Error(Segment)` - the segment name of a description is not the profile's. A cell waiting on a
  period cell that is still `(pending)` resolves on the next refresh.
