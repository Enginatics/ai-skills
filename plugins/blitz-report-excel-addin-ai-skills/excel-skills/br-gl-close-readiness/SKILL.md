---
name: br-gl-close-readiness
description: >
  Assess Oracle EBS General Ledger period-close readiness in Excel: have the
  br-run-reports skill extract GL period statuses, unposted/error journals, and
  the trial balance, then give a red/amber/green verdict with remediation and build a GL
  close-readiness scorecard. Use when the user asks "can we close GL for {period}", "GL
  period close readiness", unposted journals, subledgers not closed, or out-of-balance.
# Trigger: Slash command + auto
---

# GL Period Close Readiness (br-gl-close-readiness)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Produce a GL close-readiness scorecard in one workbook. You own orchestration, scoring, and
the verdict; br-run-reports does extraction and br-data-dashboard the build. Run
steps in order, on separate turns, keeping intermediate sheets.

**Requires:** br-run-reports, br-data-dashboard.

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** All extraction is done by **br-run-reports**
(it owns connection, auth, async run, completion, cell population). Never call `br_*` functions,
and never rename/read/sum the result sheet or start analysis until extraction is confirmed
complete — touching the workbook mid-run stalls it. This skill is **read-and-recommend only**:
it never posts, runs accounting, or uploads; it reports blockers and the recommended action.

## When to use
"Can we close GL for May", "GL period close readiness", unposted journals, journals in error,
subledgers still open, trial balance out of balance, suspense balances.

## Inputs
- **Ledger** (required); **Period** (Period From / Period To, e.g. `May-26`). Optional Chart of Accounts.

## Reports used (authoritative names — do NOT broad-search for them)
These exact report names are known. When you ask br-run-reports to run one, pass the
**documented name directly** — do NOT run a `br_report_list_external` discovery search first. Inspect
parameters only if you need an exact LOV spelling. **Fallback:** only if a run returns
`#BLITZ_REPORT_NOT_FOUND` (the instance renamed it, or the module isn't installed) do a name search.

| Report (exact name) | Run with | Notes |
|---|---|---|
| `GL Period Status` | Ledger + Period (Chart of Accounts defaults from the Ledger) | **The verdict driver** — and the period-status check: shows the GL period AND each subledger's period status, so no separate `CAC Accounting Period Status` call is needed here. If a wrong Chart of Accounts default is applied (e.g. an unrelated COA), set **Chart of Accounts** to the ledger's COA (e.g. `Operations Accounting Flex`). |
| `GL Journals` | filtered to the period; posted = No / error | Unposted/error journals |
| `GL Trial Balance Detail` *(optional)* | Ledger + Period | Balance / suspense tie-out |

## CONFIG
### Checks → class + remediation
| Check (source report) | Class | Remediation |
|---|---|---|
| Subledger periods still Open for the period (`GL Period Status`) | **Blocker** | Close AP/AR/INV/FA first (see their readiness skills) before closing GL |
| Unposted journals (`GL Journals`, posted = No) | **Blocker** | Run **Posting**; for adjusting/top-side entries, load via **GL journal upload** then post |
| Journals in error / Journal Import errors | **Blocker** | Fix and repost |
| Trial balance not balanced / suspense balances (`GL Trial Balance Detail`) | **Blocker** | Investigate suspense / unbalanced sources |
| Untranslated or unrevalued balances (foreign-currency ledgers) | **Review** | Run Translation / Revaluation if required |

### Readiness (RAG)
- **Red** — any Blocker present (unposted/error journals, or subledger periods still open).
- **Amber** — only Review-class items, or an in-balance ledger with pending translation.
- **Green** — all journals posted, subledgers closed, trial balance in balance.

### Output sheets & tab order (left to right)
`GL_Close_Readiness` (first), `GL_Period_Status`, `GL_Unposted_Journals`, [`GL_Trial_Balance`], (raw last).

## Pipeline
1. **Extract — DELEGATE.** Ask br-run-reports to run **"GL Period Status"** (Ledger + Period) → `GL_Period_Status`, then **"GL Journals"** filtered to the period (unposted/error) → `GL_Unposted_Journals`. Optionally **"GL Trial Balance Detail"** → `GL_Trial_Balance` if reconciling balance. Do nothing while each runs; wait for completion before the next.
2. **Anchor.** Record unposted-journal count + total, and which modules' periods are still Open. If everything clean → Green scorecard.
3. **Score.** Apply CONFIG: list blockers ranked by impact (subledger-open first, then unposted $); attach remediation; flag manual vs runnable.
4. **Scorecard *(single `execute_office_js` call)*** (delegate to br-data-dashboard if it fires; else build inline). Write all scorecard sections to `GL_Close_Readiness` in one call: RAG banner (ledger+period); period-status grid per module; unposted journals count/$ by source; blocking-items list. KPIs tie to the raw sheets. Any charts follow in a second call.
   - **Build mechanics (learned on a real run):** build on a NEW sheet at **position 0** (first tab); leave each report on the sheet br-run-reports created (its report name) — do NOT rename it, the dashboard links to it. **Do NOT use a multi-row `copyToRange`** to fill formula rows (it can latch onto the wrong source box and duplicate headers into the data) — write each row's formula explicitly. After building, scan **beyond** the dashboard's column range, clear any stray cells, and widen amount columns so values don't render as `######`.
5. **Narrative.** ≤5 bullets: overall call, biggest blocker, which subledgers must close first, recommended next action.
6. **Arrange tabs + final validation.** Arrange tabs to the CONFIG order; make `GL_Close_Readiness` active. Only after the scorecard exists. **Then do the one permitted verification read:** confirm the scorecard's unposted-journal count + $ tie to the Step-2 anchor. This is the only explicit re-read allowed in the entire pipeline outside of the anchor step.

## Validation
Scorecard counts/$ tie to `GL_Unposted_Journals`; Red only if a Blocker exists; Green only if none.

## Closed-loop (roadmap, not executed here)
GL journal upload delivers adjusting/top-side entries; Posting is a concurrent submit. This skill recommends; a human runs it.
