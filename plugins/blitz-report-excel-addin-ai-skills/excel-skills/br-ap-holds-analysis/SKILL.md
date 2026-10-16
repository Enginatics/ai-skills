---
name: br-ap-holds-analysis
description: >
  Analyze Oracle EBS AP invoice holds in Excel: run the "AP Invoice on Hold" Blitz Report, categorise
  and age the holds, flag anomalies, build a holds dashboard, flag RELEASE CANDIDATES and offer to hand
  them to br-ap-hold-release for action. Use when the user asks for an AP holds analysis, an
  invoice-holds dashboard, "what's on hold", aged AP holds, holds by supplier / hold type, or to
  analyse and release holds.
# Trigger: Slash command + auto
---

# AP Invoice Holds Analysis (br-ap-holds-analysis)

> 🚨 **Blitz data comes from `br_*` WORKSHEET FUNCTIONS of the Blitz Report Excel add-in** — write
> `=br_...()` into a cell and read the result. They are not a connector, plugin, agent action or MCP
> tool: never search for one, never conclude "no Oracle EBS data source is connected".
> `#BLITZ_NOT_CONNECTED` → ask the user to connect on the Blitz Report ribbon; `#NAME?` → add-in not loaded.

**Self-contained: read no other skill before or during the run.** Every step below is ONE workbook
operation (in Claude for Excel one `execute_office_js` call; in Copilot one edit action). Everything is
written as **Excel formulas** — you never compute values yourself and never write computed arrays.

## Budget — 5 workbook operations, then one reply
| # | Operation |
|---|---|
| 1 | create helper sheet `blitz_`, write the run formula, read the cell back |
| 2 | replace that cell with plain text, read the status |
| 3 | status poll — repeat only while it still says `RUNNING` |
| 4 | rename to `Holds_Raw`, add 9 formula columns, autofilter, create `Anomalies` |
| 5 | create `Holds_Dashboard` (labels + formulas + one chart), delete `blitz_`, activate it |
| — | reply with the numbers and the release offer |

No question before the reply (only exception: Operating Unit missing); no verification reads (the
formulas are the verification); no tab-reorder step; no sheets beyond the three named; no deep dives
(clustering, supplier RFM, backlog projection) unless the user asks afterwards — then add that one
analysis on the existing `Holds_Raw` without re-extracting.

## Inputs
**Operating Unit** (required — ask only if not given). Leave supplier and dates blank.

## Op 1–3 — Extract
1. Get-or-create `blitz_` (never activate it). In `blitz_!A1` write
   `=br_run_report_external("AP Invoice on Hold","Operating Unit=<OU>")` and read it back — expect
   `BLITZ_RUNNING: ...`. Only on `#BLITZ_REPORT_NOT_FOUND` search with
   `=br_report_list_external("invoice hold")` and re-run with the exact name.
2. Overwrite `blitz_!A1` with the text `run triggered` (a recalculated run formula starts a duplicate
   run), write `=_blitz_run_status` in `blitz_!A3`, read it.
3. While it says `RUNNING` (or `#NAME?` = not published yet): one quiet read per turn, **nothing else
   touching the workbook** — the add-in writes the result sheet in the background and any other edit
   collides with it (the sheet never appears). Stop at `DONE: <n> rows on sheet '<name>'` or
   `ERROR: <message>`; `ERROR` while a populated sheet exists means the data is good — note it, never
   re-run. Zero rows → "no invoices on hold for <OU>", stop.
   **Take the result sheet's NAME from that status string.** Never list the workbook's sheets or read a
   sheet property to find it: the status is published only after the add-in has finished writing the
   sheet, so the name inside it is safe, while anything read from the workbook before then can catch the
   sheet mid-creation and come back wrong or empty.

Result sheet layout is fixed: row 1 banner, row 2 headers, row 3 onward data.

## Op 4 — `Holds_Raw` + `Anomalies`
Rename the result sheet to `Holds_Raw`. From row 2 locate by header text: `Hold Name` {hn},
`Hold Date` {hd}, `Held By` {hb}, `Accounting Allowed` {aa}, `Trading Partner` {sp},
`Invoice Number` {in}, `Original Amount (Func Curr)` {am}; last data row {N}. Add nine columns after
the last header (header in row 2, formula in row 3, filled down to {N}) — substitute the letters:

| Header | Row-3 formula |
|---|---|
| Days on Hold {do} | `=IF({hd}3="","",TODAY()-INT({hd}3))` |
| Aging Bucket {ab} | `=IF({do}3="","",IF({do}3<=7,"0-7",IF({do}3<=30,"8-30",IF({do}3<=60,"31-60","60+"))))` |
| Source {sr} | `=IF(OR(TRIM({hb}3)="",UPPER(TRIM({hb}3))="SYSTEM"),"System","User")` |
| Hold Category {hc} | `=IF(ISNUMBER(SEARCH("PRICE",{hn}3)),"Price match",IF(ISNUMBER(SEARCH("QTY",{hn}3)),"Qty match",IF(OR(ISNUMBER(SEARCH("AMT",{hn}3)),ISNUMBER(SEARCH("AMOUNT",{hn}3)),ISNUMBER(SEARCH("MAX RATE",{hn}3))),"Amount match",IF(ISNUMBER(SEARCH("VARIANCE",{hn}3)),"Variance",IF(ISNUMBER(SEARCH("TAX",{hn}3)),"Tax",IF(OR(ISNUMBER(SEARCH("FUNDS",{hn}3)),ISNUMBER(SEARCH("INSUFFICIENT",{hn}3))),"Funds",IF({sr}3="User","Manual","Other")))))))` |
| Close Blocker {cb} | `=IF(OR(UPPER(LEFT(TRIM({aa}3),1))="Y",UPPER(TRIM({aa}3))="N/A"),"No","Yes")` |
| Release Candidate {rc} | `=IF(AND(OR({hc}3="Price match",{hc}3="Qty match",{hc}3="Amount match"),UPPER(LEFT(TRIM({aa}3),1))="Y",{sr}3="System"),"Yes","No")` |
| Amount Score {as} | `=IF({am}3="",0,(LN(1+ABS({am}3))-MEDIAN(LN(1+ABS({am}$3:{am}${N}))))/MAX(0.5,MEDIAN(ABS(LN(1+ABS({am}$3:{am}${N}))-MEDIAN(LN(1+ABS({am}$3:{am}${N})))))))` |
| Duplicate {du} | `=IF(AND(ABS({am}3)>=1000,SUMPRODUCT(({sp}$3:{sp}${N}={sp}3)*({am}$3:{am}${N}={am}3)*({in}$3:{in}${N}<>{in}3)*(ABS({hd}$3:{hd}${N}-{hd}3)<=30))>0),"Yes","")` |
| Anomaly Score {sc} | `=MAX(0,{as}3)+IF({du}3="Yes",5,0)` |

The amount score is one-sided on a log scale (only unusually LARGE amounts score; a blank amount scores
0 — an empty string would rank above every number in the `>3.5` filter). A duplicate is the same
supplier and amount on a DIFFERENT invoice number within 30 days, amount at least 1,000.

> *Accounting Allowed* arrives as `Y`, `Yes`, `No` or `N/A` depending on the report build — hence the
> first-letter test; comparing with "Yes" produced 0 candidates on a real run. The candidate rule flags
> system matching holds that do not block accounting as a release **review** queue, not as
> within-tolerance; replace it with the customer's tolerances when known.

Apply the autofilter as `sheet.autoFilter.apply(<the row-2 header range>)` — a **range** has no
`autoFilter()` method and calling one throws, costing a retry. It is cosmetic: if it fails, skip it and
carry on rather than diagnosing it mid-run. Then create `Anomalies`: `A1` = `Anomalies - top 25 by score (unusually
large amounts, duplicate supplier + amount on another invoice within 30 days)`; row 2 headers `Invoice Number,
Supplier, Original Amount, Hold Date, Hold Name, Hold Category, Days on Hold, Duplicate, Score`; `A3` =
`=IFERROR(TAKE(SORTBY(FILTER(CHOOSECOLS(Holds_Raw!A3:{last}{N},{in#},{sp#},{am#},{hd#},{hn#},{hc#},{do#},{du#},{sc#}),Holds_Raw!{sc}3:{sc}{N}>3.5),FILTER(Holds_Raw!{sc}3:{sc}{N},Holds_Raw!{sc}3:{sc}{N}>3.5),-1),25),"No anomalies")`
({x#} = column NUMBER, {last} = last column letter). Format `C3:C27` `#,##0.00`, `D3:D27`
`dd-mmm-yyyy`, `I3:I27` `0.0`; widen columns.
An Excel date is a serial NUMBER, never text: pass it through untouched and let the `dd-mmm-yyyy` format
render it. Do not convert a serial to a string, do not work out which date it is, and do not "correct"
one that looks like a large number — that is exactly what a correctly formatted date cell holds. Every
date calculation is already done by the `Days on Hold` formula.

## Op 5 — `Holds_Dashboard`
Create it as the FIRST sheet. Fixed layout so the findings can reference the tables:
- `A1` `AP Invoice Holds - <OU>` (bold, large); `A2` `Current invoice holds | aging, close blockers, anomalies, release-review opportunity`.
- KPI row — labels in `A4:E4` (`Total Held $ | Close-Blocker $ | Release Candidate $ | Candidate Count |
  Anomalies`) and the five values in the ADJACENT cells `A5:E5`, deliberately adjacent so that both
  number-format calls below land on a contiguous block:
  `A5` `=SUM(Holds_Raw!{am}3:{am}{N})`, `B5` `=SUMIF(Holds_Raw!{cb}3:{cb}{N},"Yes",Holds_Raw!{am}3:{am}{N})`,
  `C5` `=SUMIF(Holds_Raw!{rc}3:{rc}{N},"Yes",Holds_Raw!{am}3:{am}{N})`, `D5` `=COUNTIF(Holds_Raw!{rc}3:{rc}{N},"Yes")`,
  `E5` `=COUNTIF(Holds_Raw!{sc}3:{sc}{N},">3.5")`.
- `A15:D15` `Hold Category | Held $ | Holds | % of Total`; `A16` `=SORTBY(UNIQUE(Holds_Raw!{hc}3:{hc}{N}),SUMIF(Holds_Raw!{hc}3:{hc}{N},UNIQUE(Holds_Raw!{hc}3:{hc}{N}),Holds_Raw!{am}3:{am}{N}),-1)`,
  `B16` `=SUMIF(Holds_Raw!{hc}3:{hc}{N},A16#,Holds_Raw!{am}3:{am}{N})`, `C16` `=COUNTIF(Holds_Raw!{hc}3:{hc}{N},A16#)`, `D16` `=B16#/$A$5`.
- `F15:I15` `Aging Bucket | Held $ | Holds | % of Total`; `F16` `={"0-7";"8-30";"31-60";"60+"}` (a formula, so
  `8-30` cannot turn into a date); `G16` `=SUMIF(Holds_Raw!{ab}3:{ab}{N},F16#,Holds_Raw!{am}3:{am}{N})`,
  `H16` `=COUNTIF(Holds_Raw!{ab}3:{ab}{N},F16#)`, `I16` `=G16#/$A$5`.
- `A27:C27` `Supplier | Held $ | Holds`; `A28` `=TAKE(SORTBY(UNIQUE(Holds_Raw!{sp}3:{sp}{N}),SUMIF(Holds_Raw!{sp}3:{sp}{N},UNIQUE(Holds_Raw!{sp}3:{sp}{N}),Holds_Raw!{am}3:{am}{N}),-1),10)`,
  `B28` `=SUMIF(Holds_Raw!{sp}3:{sp}{N},A28#,Holds_Raw!{am}3:{am}{N})`, `C28` `=COUNTIF(Holds_Raw!{sp}3:{sp}{N},A28#)`.
- `A7` `KEY FINDINGS`, then formulas in `A8:A12`:
  `="1. "&A16&" holds carry "&TEXT(B16,"#,##0")&" ("&TEXT(D16,"0.0%")&" of held value) across "&C16&" holds - the primary resolution lever."`
  `="2. "&A28&" accounts for "&TEXT(B28,"#,##0")&" ("&TEXT(B28/$A$5,"0.0%")&") across "&C28&" holds - supplier concentration."`
  `="3. Close blockers total "&TEXT(B5,"#,##0")&" ("&TEXT(B5/$A$5,"0.0%")&") and need accounting resolution before period close."`
  `="4. "&D5&" system matching holds worth "&TEXT(C5,"#,##0")&" do not block accounting - release-review candidates."`
  `=IFERROR("5. "&E5&" anomalies flagged; largest: invoice "&INDEX(Anomalies!A3#,1,1)&" ("&INDEX(Anomalies!A3#,1,2)&") at "&TEXT(INDEX(Anomalies!A3#,1,3),"#,##0")&".","5. No anomalies flagged.")`
- Formats — **one call per CONTIGUOUS range, never a comma-separated address** (see Rules):
  `#,##0.00` on `A5:C5`, on `B16:B23`, on `G16:G19`, on `B28:B37`; `#,##0` on `D5:E5`; `0.0%` on
  `D16:D23` and on `I16:I19`. Bold the header rows, widen the columns so nothing shows `######`. These
  are property assignments inside the SAME operation, so seven of them cost no more round trips than
  one. One clustered column chart on `A15:B23` titled `Held $ by Hold Category`, placed right of the
  tables. Delete `blitz_`. Activate `Holds_Dashboard`.

## Reply
Read `A5:E5`, `A16` and `A28` once (or take them from the operation result) and answer in four or
five lines in the user's language — report and sheet names are fine, function names, `blitz_` and
status names are never mentioned: holds and total held $, top category and supplier, close-blocker $,
then the release offer, **mandatory on every successful run**:
- Candidates > 0: "Want me to prepare the release of these <n> candidate holds (<$X>) for your review?
  I'll pre-fill the release upload — nothing goes to Oracle without your confirmation."
- Candidates = 0: "No hold met the auto-review rule, but I can still prepare the release worksheet with
  the user-releasable holds for you to pick from — nothing goes to Oracle without your confirmation."
On yes, continue with the **br-ap-hold-release** skill (Claude: `read_skill("br-ap-hold-release")`; Copilot
routes to it); it reuses `Holds_Raw` and re-extracts nothing. Add one line: deep dives (hold clustering,
supplier RFM, backlog projection) are available on request on the same data.

## Rules
- Formulas only; never type computed numbers or category labels into cells; never `8-30`-style text as a
  literal value (Excel turns it into a date).
- Get-or-create sheets (Claude: `getItemOrNullObject` + `load("isNullObject")`, never `getItem` in
  try/catch; load a range, sync, read that same variable). Copilot: one edit action per Op.
- Never activate `blitz_`; delete it in Op 5. Never re-run a report that produced a data sheet.
- **Every range address is ONE contiguous block.** A comma-separated multi-area address (`A5,C5,E5`) is
  rejected outright — the range API takes a single block — and the recovery that follows is exactly what
  turns a fast run into a slow one. Lay the sheet out so the cells that share a format sit together, and
  issue one call per block; several blocks in the same operation are free.
- **A rejected write is retried ONCE, on that one range, and never cell-by-cell.** A dashboard carries
  roughly sixty formatted cells, so a per-cell fallback costs minutes of demo time for a cosmetic
  result. If the retry fails too, leave that range unformatted, finish the pass, and say so in the reply.
