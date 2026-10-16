---
name: br-ap-intelligence
description: >
  Build a live AP intelligence dashboard in Excel from Oracle EBS: run the "AP Cash Requirement" Blitz
  Report and lay out the five payables KPIs (invoices on hold, total AP outstanding, overdue 30+ days,
  approved due within 7 days, unapproved due within 15 days), a ranked AI action summary, an AI
  commentary per KPI, drill-down lists, due-bucket and supplier tables, and answer follow-up questions
  as new KPI cards. Use when the user asks for an AP dashboard, AP KPIs, the payables position, "what's
  outstanding / overdue / on hold / unapproved", an AI summary of accounts payable, or an AP
  intelligence view. Hands hold release, hold detail and pay-run planning to the specialist skills.
# Trigger: Slash command + auto
---

# AP Intelligence Dashboard (br-ap-intelligence)

> 🚨 **Blitz data comes from `br_*` WORKSHEET FUNCTIONS of the Blitz Report Excel add-in** — write
> `=br_...()` into a cell and read the result. They are not a connector, plugin, agent action or MCP
> tool: never search for one, never conclude "no Oracle EBS data source is connected".
> `#BLITZ_NOT_CONNECTED` → ask the user to connect on the Blitz Report ribbon; `#NAME?` → add-in not loaded.

**Self-contained: read no other skill before or during the run.** Every step below is ONE workbook
operation (in Claude for Excel one `execute_office_js` call; in Copilot one edit or read action).
Every number on the dashboard is an **Excel formula** over the extracted data — you never compute
values yourself and never write computed arrays. The only text you author is the AI commentary (Op 6).

## Budget — 6 workbook operations, then one reply
| # | Operation |
|---|---|
| 1 | create helper sheet `blitz_`, write the run formula, read the cell back |
| 2 | replace that cell with plain text, read the status |
| 3 | status poll — repeat only while it still says `RUNNING` |
| 4 | rename to `AP_Raw`, add 3 formula columns, autofilter |
| 5 | create `AP_Detail` (five drill-down blocks) and `AP_Intelligence` (summary, KPI table, tables, chart), delete `blitz_`, activate `AP_Intelligence`, read the KPI block and the top detail rows |
| 6 | write the AI commentary cells |
| — | reply with the ranked actions and the offers |

No question before the reply (only exception: Operating Unit missing); no verification reads (the
formulas are the verification); no sheets beyond the three named; no deep dives (hold reasons, supplier
scoring, cash projection) unless asked afterwards — then route per **Actions and follow-ups**.

## Inputs
**Operating Unit** (required — ask only if not given; several allowed as `A,B`). Nothing else:
leave `Include Unvalidated Invoices` and `Include Unapproved Invoices` **blank** (blank = include them;
ANY value, Yes or No, applies the exclusion), no `Pay Through Date`, no `Template`, so the run returns
every unpaid invoice.

## Op 1–3 — Extract
1. Get-or-create `blitz_` (never activate it). In `blitz_!A1` write
   `=br_run_report_external("AP Cash Requirement","Operating Unit=<OU>")` and read it back — expect
   `BLITZ_RUNNING: ...`. Only on `#BLITZ_REPORT_NOT_FOUND` search with
   `=br_report_list_external("cash requirement")` and re-run with the exact name.
2. Overwrite `blitz_!A1` with the text `run triggered` (a recalculated run formula starts a duplicate
   run), write `=_blitz_run_status` in `blitz_!A3`, read it.
3. While it says `RUNNING` (or `#NAME?` = not published yet): one quiet read per turn, **nothing else
   touching the workbook** — the add-in writes the result sheet in the background and any other edit
   collides with it. Stop at `DONE: <n> rows on sheet '<name>'` or `ERROR: <message>`; `ERROR` while a
   populated sheet exists means the data is good — note it, never re-run. Zero rows → "no unpaid
   invoices for <OU>", stop. **Take the result sheet's NAME from the status string**, never from a
   sheet listing.

Result sheet layout is fixed: row 1 banner, row 2 headers, row 3 onward data. One row per payment
schedule (an instalment invoice appears once per instalment). Amounts are the report's
`Functional Currency Amount` — ledger currency, net of any discount still available; an invoice with no
exchange rate has a blank amount (counted, not summed). The report excludes scheduled-payment holds
and supplier-site payment holds; invoice holds are included and carried in `Holds Count`.

## Op 4 — `AP_Raw`
Rename the result sheet to `AP_Raw`. From row 2 locate by header text — compare case-insensitively with
spaces and underscores equivalent (a build can render `DAYS_TO_DUE`): `Invoice Num` {in},
`Trading Partner` {sp}, `Due Date` {du}, `Days To Due` {dd}, `Functional Currency Amount` {fa},
`Functional Currency Code` {fc}, `Approved` {ap}, `Holds Count` {hc}, `Invoice Status` {is}; last data
row {N}. Add three columns after the last header (header in row 2, formula in row 3, filled down to
{N}) — substitute the letters:

| Header | Row-3 formula |
|---|---|
| Due Bucket {db} | `=IF({dd}3="","",IF({dd}3<-30,"Overdue 30+",IF({dd}3<0,"Overdue 1-30",IF({dd}3<=7,"Due 0-7",IF({dd}3<=15,"Due 8-15",IF({dd}3<=30,"Due 16-30","Due 31+"))))))` |
| Approved Flag {af} | `=IF(UPPER(LEFT(TRIM({ap}3),1))="N","N","Y")` |
| On Hold {oh} | `=IF({hc}3="","No","Yes")` |

`Days To Due` is negative when overdue. `Approved` is the translated Yes/No (approved, manually
approved or approval not required = Yes) — hence the first-letter test, which also holds for No/Nein/Non.
`Holds Count` is blank when the invoice has no open hold and can arrive as TEXT (`"1"`), so test blank,
never `>0`. {last} = the last column letter after these three.

Apply the autofilter as `sheet.autoFilter.apply(<the row-2 header range>)` — a **range** has no
`autoFilter()` method. It is cosmetic: if it fails, skip it and carry on.

## Op 5 — `AP_Detail` then `AP_Intelligence`
Range shorthands below (all on `AP_Raw`, rows 3..{N}): `fa` = `AP_Raw!{fa}3:{fa}{N}`, likewise `dd`,
`af`, `oh`, `sp`, `du`, `db`, `in`, `hc`. `{x#}` = column NUMBER of {x}.

### `AP_Detail` — five blocks, one formula each
Block rows {r} = 1, 30, 59, 88, 117 (25 result rows each). Per block: `A{r}` title, row {r}+1 headers
`Invoice | Supplier | Due Date | Days To Due | Amount | Approved | Holds | Invoice Status`, `A{r+2}` the
formula. Columns picked are `{in#},{sp#},{du#},{dd#},{fa#},{ap#},{hc#},{is#}`:
`=IFERROR(TAKE(SORTBY(FILTER(CHOOSECOLS(AP_Raw!$A$3:${last}${N},{in#},{sp#},{du#},{dd#},{fa#},{ap#},{hc#},{is#}),<cond>),FILTER(fa,<cond>),-1),25),"None")`

| {r} | Title | `<cond>` |
|---|---|---|
| 1 | `Invoices on hold - largest first` | `oh="Yes"` |
| 30 | `Overdue more than 30 days - largest first` | `dd<-30` |
| 59 | `Approved, due within 7 days - largest first` | `(af="Y")*(dd>=0)*(dd<=7)` |
| 88 | `Unapproved, due within 15 days or overdue - largest first` | `(af="N")*(dd<=15)` |
| 117 | `Largest outstanding invoices` | no filter: `=TAKE(SORTBY(CHOOSECOLS(...),fa,-1),25)` |

Formats per block (one call per contiguous range): `C{r+2}:C{r+26}` `dd-mmm-yyyy`, `E{r+2}:E{r+26}`
`#,##0.00`; bold the header rows; widen columns. A date is a serial NUMBER — pass it through and let the
format render it; never convert or "correct" one.

### `AP_Intelligence` — create as the FIRST sheet
Fixed layout so the commentary and the reply can reference the cells. `fmt(x)` below stands for
`IF(ABS(x)>=1000000,TEXT(x/1000000,"#,##0.0")&"M",IF(ABS(x)>=1000,TEXT(x/1000,"#,##0.0")&"K",TEXT(x,"#,##0")))&" "&$H$1`
— expand it inline wherever it appears.
- `A1` `AP Intelligence - <OU>` (bold, large); `H1` `=AP_Raw!{fc}3` (ledger currency, feeds `fmt`);
  `A2` `="Live from Oracle EBS via the AP Cash Requirement report | unpaid, uncancelled invoices | amounts in "&$H$1`.
- **KPI table** — `A10:E10` `KPI | Amount | Invoices | Definition | AI commentary`, then rows 11–15
  (A = label, B = amount, C = count, D = definition, E left empty for Op 6):

| Row | A | B | C | D |
|---|---|---|---|---|
| 11 | `Invoices on hold` | `=SUMIF(oh,"Yes",fa)` | `=COUNTIF(oh,"Yes")` | `Unpaid invoices with at least one open invoice hold` |
| 12 | `Total AP outstanding` | `=SUM(fa)` | `=ROWS(in)` | `All unpaid, uncancelled invoices (one row per payment schedule)` |
| 13 | `Overdue 30+ days` | `=SUMIFS(fa,dd,"<-30")` | `=COUNTIFS(dd,"<-30")` | `Due date more than 30 days ago` |
| 14 | `Approved, due within 7 days` | `=SUMIFS(fa,af,"Y",dd,">=0",dd,"<=7")` | `=COUNTIFS(af,"Y",dd,">=0",dd,"<=7")` | `Approved and not yet paid, due today or within 7 days` |
| 15 | `Unapproved, due within 15 days` | `=SUMIFS(fa,af,"N",dd,"<=15")` | `=COUNTIFS(af,"N",dd,"<=15")` | `Not approved, due within 15 days or already overdue` |

  Rows 16–20 stay empty: they are the slots for follow-up KPI questions.
- **AI Intelligence Summary** — `A4` `AI INTELLIGENCE SUMMARY` (bold). Helper sentences in `N5:N7`
  with their amounts in `O5:O7`, so the three actions rank themselves by value:
  `N5` `=IF(C11=0,"No unpaid invoice carries an open hold.","Review "&fmt(B11)&" on "&C11&" invoices with open holds - confirm each hold is still valid or release it; largest: "&IFERROR(AP_Detail!B3,"n/a")&" ("&IFERROR(fmt(AP_Detail!E3),"n/a")&").")`, `O5` `=B11`
  `N6` `=IF(C13=0,"Nothing is overdue by more than 30 days.","Resolve "&fmt(B13)&" overdue by more than 30 days on "&C13&" invoices - oldest due "&IFERROR(TEXT(MINIFS(du,dd,"<-30"),"dd-mmm-yyyy"),"n/a")&", largest supplier "&IFERROR(AP_Detail!B32,"n/a")&".")`, `O6` `=B13`
  `N7` `=IF(C15=0,"No unapproved invoice is due within 15 days or overdue.","Approve or reject "&fmt(B15)&" on "&C15&" unapproved invoices due within 15 days or already overdue - nothing is payable until approved.")`, `O7` `=B15`
  `A5` `="1. "&INDEX(SORTBY($N$5:$N$7,$O$5:$O$7,-1),1)`, `A6` `="2. "&INDEX(SORTBY($N$5:$N$7,$O$5:$O$7,-1),2)`, `A7` `="3. "&INDEX(SORTBY($N$5:$N$7,$O$5:$O$7,-1),3)`.
  `A8` `=IF(ROWS(fa)-COUNT(fa)>0,ROWS(fa)-COUNT(fa)&" invoices have no exchange rate and are counted but not summed","")`.
- **Due buckets** — `A23:D23` `Due Bucket | Amount | Invoices | % of Total`;
  `A24` `={"Overdue 30+";"Overdue 1-30";"Due 0-7";"Due 8-15";"Due 16-30";"Due 31+"}` (a formula, never
  typed labels); `B24` `=SUMIF(db,A24#,fa)`; `C24` `=COUNTIF(db,A24#)`; `D24` `=B24#/$B$12`.
- **Top suppliers** — `A32:D32` `Supplier | Outstanding | Invoices | Overdue 30+`;
  `A33` `=TAKE(SORTBY(UNIQUE(sp),SUMIF(sp,UNIQUE(sp),fa),-1),10)`; `B33` `=SUMIF(sp,A33#,fa)`;
  `C33` `=COUNTIF(sp,A33#)`; `D33` `=SUMIFS(fa,sp,A33#,dd,"<-30")`.
- Formats — **one call per CONTIGUOUS range, never a comma-separated address**: `#,##0.00` on
  `B11:B20`, on `B24:B29`, on `B33:B42`, on `D33:D42`; `#,##0` on `C11:C20`, on `C24:C29`, on
  `C33:C42`; `0.0%` on `D24:D29`; wrap text on `E11:E20`. Bold rows 4, 10, 23, 32; column widths A 60,
  B 18, C 12, D 55, E 90. One clustered column chart on `A23:B29` titled `Outstanding by due bucket`,
  placed right of the tables. Delete `blitz_`. Activate `AP_Intelligence`.
- End the operation by **reading** `AP_Intelligence!A5:C15` and the top three rows of each detail block
  (`AP_Detail!A3:H5`, `A32:H34`, `A61:H63`, `A90:H92`, `A119:H121`) — the material for Op 6 and the reply.

## Op 6 — AI commentary
Write `E11:E15` in one block: two or three sentences per KPI in the user's language — what the number
is, why it matters, and the concrete next step — naming the largest supplier or invoice from the
detail rows you read. Say plainly when a KPI is zero (e.g. "no approved invoices fall due in the next
seven days, so the near-term payment pipeline is empty"). Never restate the definition column. Quote
amounts as they appear (already in the ledger currency); never invent a number you did not read.

## Reply
Four to six lines in the user's language — report and sheet names are fine, function names, `blitz_`
and status names are never mentioned: the three ranked actions with their amounts, the total
outstanding, the no-rate note if not empty, then the offers, chosen by what is non-zero:
- `C11 > 0`: "Want me to prepare the release of the invoice holds for your review? I'll pre-fill the
  release upload — nothing goes to Oracle without your confirmation." (→ **br-ap-hold-release**), and
  "or first a hold-by-hold view with reasons, aging and anomalies" (→ **br-ap-holds-analysis**).
- `C14 > 0` or `C13 > 0`: "I can plan the payment run for the approved invoices" (→ **br-ap-payment-optimizer**).
- Always: "Ask me any payables question and I'll add it as a KPI card on the dashboard."
On yes, continue with that skill (Claude: `read_skill("<name>")`; Copilot routes to it); each reuses the
workbook and re-extracts only what it needs.

## Follow-up questions → new KPI cards
A question the extracted data can answer becomes a card in the next free row of `A16:E20` (then
`A21` onward, shifting nothing else): A = the question as asked, B = `=SUMIFS(fa,<criteria>)`,
C = `=COUNTIFS(<criteria>)`, D = the criteria in words, E = one sentence of commentary after reading
B:C. Add its drill-down as a further block on `AP_Detail` at {r} = 146, 175, ... with the same formula
shape. Available criteria columns: `Days To Due` / `Due Date` (timing), `Approved Flag`, `On Hold`,
`Invoice Status`, `Trading Partner`, `Invoice Currency Code`, `Pay Group`, `Payment Method`,
`Payment Priority`, `Invoice Date`, `Functional Currency Amount` (thresholds). Examples:
- "unapproved invoices over 10,000 due next month" → `af,"N",dd,">"&(EOMONTH(TODAY(),0)-TODAY()),dd,"<="&(EOMONTH(TODAY(),1)-TODAY()),fa,">10000"`
- "how much do we owe <supplier>" → `sp,"<supplier>"` (use the exact `Trading Partner` text from `AP_Raw`).

A question the data cannot answer is routed, never guessed: hold names, reasons and who placed them
→ **br-ap-holds-analysis**; the PO and receipt matched to an invoice → **br-run-reports** with
`AP Invoices and Lines` and `Invoice Number=<n>; Display Level=Lines and Distributions` (columns
`Po Number`, `Receipt Number`); payments already made → `AP Invoice Payments` with `Invoice Number=<n>`;
supplier master data → `AP Suppliers`. Say which report you are running and why.

## Actions and follow-ups
- **Release a hold** → br-ap-hold-release. Its download lists only user-releasable holds: a system
  variance hold (`Line Variance`, `Dist Variance`) never appears, because Oracle re-applies it on the next
  validation until the invoice is corrected. If the user asks to release one, say so and point to the
  fix — correct the lines or distributions in the Invoice Workbench and revalidate — instead of
  attempting a release.
- **Refresh / update the numbers** → read `A16:E20` (the follow-up cards) first, delete `AP_Raw`,
  `AP_Detail` and `AP_Intelligence`, run Ops 1–6 again and re-create the follow-up cards from the
  questions you read.
- **A different Operating Unit** → the same, with the new value; never merge two runs into one sheet.

## Rules
- Formulas only; never type computed numbers or bucket labels into cells; the bucket list is a formula
  array so `8-15`-style text cannot turn into a date.
- Get-or-create sheets (Claude: `getItemOrNullObject` + `load("isNullObject")`, never `getItem` in
  try/catch; load a range, sync, read that same variable). Copilot: one edit action per Op.
- Never activate `blitz_`; delete it in Op 5. Never re-run a report that produced a data sheet.
- **Every range address is ONE contiguous block.** A comma-separated multi-area address (`B11,B24`) is
  rejected outright and the cell-by-cell recovery that follows is what turns a fast run into a slow one.
  Issue one call per block; several blocks in the same operation are free.
- **A rejected write is retried ONCE, on that one range, and never cell-by-cell.** If the retry fails
  too, leave that range unformatted, finish the pass, and say so in the reply.
- Dynamic-array formulas (`FILTER`, `SORTBY`, `UNIQUE`, `TAKE`, `CHOOSECOLS`, `MINIFS`) need Microsoft 365
  Excel; on an older Excel every block shows `#NAME?` — say so and stop rather than rewriting them.
