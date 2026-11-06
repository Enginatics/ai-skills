# Template for a generated skill

Copy this file text, replace every `<...>`, delete the lines that do not apply (marked *optional*
or *action skills only*). Keep the fixed sentences unchanged: they are what makes the skill run the
same way on Claude in Excel and Copilot in Excel. Use single quotes or backticks, never a double
quote character, in the generated text.

```
---
name: <skill-name>
description: >
  <What it does, in Oracle EBS terms, one sentence>. Use when the user asks '<prompt 1>',
  '<prompt 2>', or <trigger phrases in their words>. <Writes nothing to Oracle EBS. |
  WRITES to Oracle EBS after two confirmations.>
---

# <Title> (<skill-name>)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude 'no Oracle EBS / Blitz connector is set up' (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill('br-run-reports')`.

> **Performance:** read `br-analytics-standards` at the start of every run. Every pipeline step
> follows those rules: one workbook operation per step, no mid-pipeline verification reads.

<One paragraph: what the skill produces and the decision it supports. Who does what: you own
scoring and the verdict; br-run-reports does extraction<; br-data-dashboard the build>.>

**Requires:** br-run-reports<, br-data-dashboard><, br-run-uploads>.

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** All extraction is done by **br-run-reports** (it owns
connection, responsibility, the run and the completion check). Never call `br_*` functions, and
never read or rename the result sheet until the extraction is confirmed complete.
<This skill is read-and-recommend only: it never changes Oracle EBS data. | This skill changes
Oracle EBS data only through **br-run-uploads**, only on the confirmed rows, and only after the
two confirmations below.>

## When to use
'<prompt 1>', '<prompt 2>', <trigger phrases>. For <a neighbouring need> use <other skill> instead.

## Inputs
- **<Input>** (required) — ask if not supplied.
- **<Input>** — default <value>; say so and let the user change it.
- *Optional:* <input>, <input>.

## Reports used (authoritative names — do NOT broad-search for them)
Pass the documented name directly; search only on `#BLITZ_REPORT_NOT_FOUND`.

| Report (exact name) | Run with | Notes |
|---|---|---|
| `<Report Name>` | `<Parameter>=<value>; <Parameter>=<value>` | <its role: the driver, the evidence, the cross-check> |
| `<Report Name>` *(optional)* | `<Parameter>=<value>` | <when to run it> |

Dates are passed as `YYYY-MM-DD`; a parameter whose desired value is the default is omitted (a
comma in a value splits it into several values).

## CONFIG
### Classes
| Condition (report, column) | Class | Recommendation |
|---|---|---|
| <condition> | **<Class>** | <what the user does about it> |

### Defaults (edit to the customer)
- <threshold> = <value> (<confirmed by the user | placeholder until the customer confirms>).
- <threshold> = <value> (...).
The summary sheet shows these values under 'Assumptions'.

### Output sheets & tab order (left to right)
`<Summary>` (first), `<Detail>`, [`<Optional>`], raw report sheets last.

## Pipeline
1. **Extract — DELEGATE.** br-run-reports runs `<Report Name>` with <parameters> → sheet
   `<name>`; then `<Report Name>` → `<name>`. Wait for each completion; do nothing mid-run.
2. **Anchor.** Record <row count and the total of <amount column>> from the raw sheet.
3. **Classify *(single workbook operation)*.** <The formulas or logic, by column header name, never
   by column position>. Write `<Detail>` in one write: <columns>.
4. **Summary *(single workbook operation)*.** On a new sheet at position 0: <banner with the
   verdict>, <KPI block>, <ranked list>, 'Assumptions' block from CONFIG. Charts in a second
   operation at most.
5. **Narrative.** At most five bullets: overall call, biggest item, recommended next action.
6. **Validation read.** The one permitted re-read: the summary's count and total equal the anchor.

## Validation
- `<Summary>` count and total tie to `<Detail>` and to the anchor.
- <Class> only when <condition>; <verdict colour> only when <condition>.

## Degradation rules
- `<Report Name>` returns no rows → <say so and stop | fall back to `<Report Name>` and say so>.
- A required input is missing → ask; never guess an organization, ledger or period.
- The user declines an optional stage → the sheets so far are the deliverable; never nag.

## Talk in the user's language
Say '<the business action>' and name reports by their names; never name worksheet functions, the
helper sheet or trigger cells.

## Action step (action skills only)
7. **Propose → confirmation 1.** List the rows to change with count, amounts and <key field>;
   ask 'Fill the <Upload Name> grid for these <n> rows (<amount>)?'. Nothing is written yet.
8. **Fill and validate.** br-run-uploads downloads `<Upload Name>` for <scope>, writes only
   `<column>` on the confirmed rows, validates, and shows the validation results.
9. **Confirmation 2 → submit.** Ask 'Submit <n> validated rows (<amount>) to Oracle EBS now?'.
   Only 'yes' to this question submits. Report the per-row results afterwards.
Untouched rows are inert. Never mix two uploads in one confirmation.
```

## Filling guidance
- The description is the trigger: put the user's own words in it. 'Use when the user asks' followed
  by two or three prompts beats a generic sentence.
- One report per role: a driver (the rows to judge), evidence (why), a cross-check (ties the
  total). More reports make the run slower, not better.
- A CONFIG value the user gave is 'confirmed by the user'; one you chose is a placeholder, named
  as such in the skill and on the summary sheet.
- Formulas, not code: Copilot in Excel runs no scripts, so classification is FILTER, SORTBY,
  SUMIFS, XLOOKUP and LET over the raw sheet, written by column header name.
- A sheet layout where cells sharing a format sit next to each other, one write per block.
