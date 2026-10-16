---
name: br-wip-variance-analysis
description: >
  Analyze Oracle EBS WIP job health and cost exposure in Excel: have the br-run-reports skill
  extract job statuses, WIP value, and component shortages, then rank stuck and past-due jobs,
  surface value concentration and close candidates, and build one WIP analysis dashboard. Use when
  the user asks about open WIP jobs, jobs past due, WIP value, discrete job aging, component
  shortages, or which jobs should be closed.
# Trigger: Slash command + auto
---

# WIP Job & Variance Analysis (br-wip-variance-analysis)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes.

Produce a WIP health analysis in one workbook: which jobs are stuck, where the value sits, what
blocks completion, and which jobs are ready to close. You own scoring and the register;
br-run-reports does extraction and br-data-dashboard the build. Run steps in order, keeping
intermediate sheets. Unclosed complete jobs are also a **period-close drag** — hand that verdict to
br-inv-cost-close-readiness when this run feeds a close assessment.

**Requires:** br-run-reports, br-data-dashboard.

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** Extraction is by **br-run-reports**; never call `br_*`
functions or touch a result sheet mid-run. **Read-and-recommend only** — this skill never closes a
job, changes a status, or transacts material; it ranks and recommends.

## When to use
"Which WIP jobs are stuck", "WIP value by job", "jobs past their completion date", "what's blocking
the shop floor", "which jobs can we close", "WIP aging". For creating/updating jobs, the WIP Job
Upload exists — different skill territory, do not act here.

## Inputs
- **Organization Code** (manufacturing org) — required. *(Optional:* schedule group, assembly,
  status filter.)*

## Reports used (authoritative names — do NOT broad-search for them)
Pass the **documented name directly**; search only on `#BLITZ_REPORT_NOT_FOUND`.

| Report (exact name) | Run with | Notes |
|---|---|---|
| `WIP Entities` | Org | **The job register** — every job with status and dates. The driver for aging and close-candidate logic. |
| `WIP Value` (or `WIP Value Summary` for big orgs) | Org (+ period as offered) | $ in WIP per job — costs charged vs relieved; the exposure driver. |
| `WIP Discrete Job Shortage` | Org | Component shortages per open job — the "why is it stuck" evidence. |
| `WIP Account Distribution` *(add-on — cost-variance breakdown)* | Org + period (+ variance accounts) | The variance evidence for the opt-in add-on below — never wide-open. |
| `WIP Completion Report` *(add-on, evidence)* | Org + job | Completion quantities when a variance needs the yield side checked. |

## CONFIG
### Job classes
| Condition (from the register + value) | Class | Recommendation |
|---|---|---|
| Status Complete / Complete-No Charges, not Closed, past completion date | **Close candidate** | Close the job — every open period it stays open, its variances wait |
| Released, past scheduled completion by > aging threshold, still carrying value | **Stuck** | Investigate — shortage? (join `WIP_Shortages`) no recent activity? |
| Released, past due, with open shortages | **Blocked** | The shortage list IS the action — expedite or de-schedule |
| Unreleased older than threshold | **Review** | Cancel or release — planning hygiene |
| On Hold | **Review** | Confirm the hold is intentional |
| Released, on schedule | Healthy | — |

**Defaults (edit to the customer):** aging threshold 14 days past scheduled completion; unreleased
threshold 30 days; value floor for ranking $1,000.

### Output sheets & tab order (left to right)
`WIP_Analysis` (first), `Job_Register` (every job, classed and ranked), `WIP_Jobs` (the entities
extract), `WIP_Value`, `WIP_Shortages`, [`WIP_Accounts`] (last).

## Pipeline
1. **Extract — DELEGATE.** br-run-reports runs `WIP Entities` → `WIP_Jobs`; `WIP Value` (Summary
   for large orgs) → `WIP_Value`; `WIP Discrete Job Shortage` → `WIP_Shortages`. Wait for each.
2. **Anchor.** Record open-job count by status, total WIP $, past-due count, shortage-line count,
   close-candidate count. All healthy → short verdict, skip the heavy register.
3. **Classify  *(single `execute_office_js` call)*.** Join value and shortages onto the job
   register by job name in memory; apply CONFIG classes; rank inside each class by WIP $
   descending. Write `Job_Register` in one `.values =` call: job, assembly, status, class, dates,
   days overdue, WIP $, shortage count, recommendation.
4. **Dashboard *(single call; charts second)*** (delegate to br-data-dashboard if it fires; else
   inline). KPI cards (open jobs, WIP $, past due, close candidates), value-by-class and aging
   charts, top-10 stuck jobs table linking to the register. NEW sheet at **position 0**; don't
   rename report sheets; no multi-row `copyToRange`; clear strays; widen amount columns.
5. **Narrative.** ≤5 bullets: exposure headline, the biggest stuck job and its cause, the
   close-candidate payoff (jobs × $ that would leave WIP), first action.
6. **Arrange tabs + final validation.** Order per CONFIG; `WIP_Analysis` active. **One permitted
   verification read:** register class counts and WIP $ tie to the Step-2 anchor.

## Add-on: cost-variance breakdown (OPT-IN — extra extract, offer once before Step 1)
Answers "WHERE is the variance coming from", a different question from job health — so it runs only
when the request implies it ("cost variance", "why are variances so high", "variance by job") or
the user accepts a single up-front offer. Never re-ask mid-pipeline.
- **Extract** `WIP Account Distribution` for the org + period alongside the standard pulls.
- **Decompose** per job: charges vs relief by cost element (material / resource / overhead /
  outside processing) — which element drives each job's net variance, and the org-level pattern
  (one assembly family, one element, one period spike).
- **Driver patterns to call out**: material-heavy variance on jobs that also sit on the shortage
  list (substitutions/over-issue), resource-heavy variance concentrated in one department (rate or
  routing suspect — hand assembly-level suspects to **br-bom-validator** for the bill-side check),
  variance parked on open Complete jobs (the close-candidate payoff quantified).
- Adds a `Cost_Variance` sheet after `WIP_Value` and a dashboard section; both degrade cleanly when
  the add-on didn't run. `WIP Completion Report` is pulled per-job only when a yield question needs
  it — never wide-open.
- Variance judgment is a REVIEW flag with the element and $ named — root cause belongs to costing;
  never assert "the standard is wrong".

## Validation
Register ties to raw sheets; every Stuck/Blocked call is backed by a date or shortage the user can
see; jobs missing from the value report show blank $, not zero (say which). When the add-on ran,
`Cost_Variance` element totals tie to the account-distribution extract.

## Closed-loop (roadmap, not executed here)
Close candidates route to the WIP close flow; job changes to the WIP Job Upload. This skill
recommends; a human executes.
