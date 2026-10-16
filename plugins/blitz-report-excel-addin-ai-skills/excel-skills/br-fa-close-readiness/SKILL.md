---
name: br-fa-close-readiness
description: >
  Assess Oracle EBS Fixed Assets period-close readiness in Excel: have the
  br-run-reports skill extract the mass-additions backlog, depreciation/reserve
  status, and FA-to-GL reconciliation, then give a red/amber/green verdict with remediation and
  build an FA close-readiness scorecard. Use when the user asks "can we close FA for {period}",
  "fixed assets period close readiness", mass additions backlog, or depreciation not run.
# Trigger: Slash command + auto
---

# FA Period Close Readiness (br-fa-close-readiness)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.


> **Performance:** Read `br-analytics-standards` at the start of every run
> (`read_skill("br-analytics-standards")`). All pipeline steps must follow those rules.
> Target runtime: under 7 minutes for single-module, under 20 minutes for orchestrations.

Produce an FA close-readiness scorecard in one workbook. You own orchestration, scoring, and the
verdict; br-run-reports does extraction and br-data-dashboard the build. Run steps in
order, on separate turns, keeping intermediate sheets.

**Requires:** br-run-reports, br-data-dashboard.

## Division of responsibility — READ FIRST
**You do NOT run Blitz reports yourself.** All extraction is done by **br-run-reports**
(connection, auth, async run, completion, cell population). Never call `br_*` functions, and never
rename/read/sum the result sheet or start analysis until extraction is confirmed complete. This
skill is **read-and-recommend only**: it never runs depreciation, posts mass additions, or uploads;
it reports blockers and the recommended action.

## When to use
"Can we close FA for May", "fixed assets period close readiness", mass additions backlog,
depreciation not run/closed, FA↔GL reconciliation.

## Inputs
- **Book** (corporate/tax book) — required; **Period**.

## Reports used (authoritative names — do NOT broad-search for them)
These exact report names are known. When you ask br-run-reports to run one, pass the
**documented name directly** — do NOT run a `br_report_list_external` discovery search first. Inspect
parameters only if you need an exact LOV spelling. **Fallback:** only if a run returns
`#BLITZ_REPORT_NOT_FOUND` (the instance renamed it, or the module isn't installed) do a name search.

| Report (exact name) | Run with | Notes |
|---|---|---|
| `FA Depreciation by period` | Book | **The verdict driver** — depreciation-run status per period; the latest period with depreciation rows is the last period depreciation ran. If that's before your target period, depreciation is **not run** → Blocker. |
| `FA Unposted Mass Additions` | Book | **The backlog queue** — unposted mass additions by status (New / On Hold / Merged). "New" lines are ready to post → Blocker until posted. (Confirm exact name on the instance; the run-screen name may carry a suffix.) |
| `FA Journal Entry Reserve Ledger` *(optional, FA↔GL tie-out)* | Book + Period (+ **Set of Books Currency**) | Reserve vs GL. ⚠️ Needs a **Currency / Set of Books Currency** param and **errors on dual-currency ledgers** (ambiguous USD) — use only for the GL tie-out, not as the dep-status driver. |
| `FA Depreciation Reserve` *(optional)* | Book + Period | Reserve-status proxy — may return 0 rows on some instances; don't rely on it for the verdict. |

FA periods are **per-book** (not GL/CAC accounting periods), so there is **no `CAC Accounting Period Status` step** here — the depreciation-by-period report itself reflects whether the FA period's depreciation has run.

## CONFIG
### Checks → class + remediation
| Check (source report) | Class | Remediation |
|---|---|---|
| Mass-additions backlog (unposted additions awaiting review) | **Blocker** | Review and post via **FA Mass Additions upload** → Post Mass Additions |
| Depreciation not run for the period (`FA Journal Entry Reserve Ledger`, `FA Depreciation Reserve` as reserve-status proxies) | **Blocker** | Run Depreciation (close period) |
| FA↔GL reconciliation variance (reserve ledger vs GL) | **Blocker** | Investigate the difference |
| Pending transactions (additions/adjustments/retirements not processed) | **Review** | Process before close |

> **Data-source note (resolved on a real run):** the mass-additions backlog queue is
> **`FA Unposted Mass Additions`** (status New / On Hold / Merged). Use it directly — no new SQL
> needed. Only if it isn't found on the instance, flag it rather than forcing a wrong report.

### Readiness (RAG)
- **Red** — mass-additions backlog, depreciation not run, or FA↔GL variance over materiality.
- **Amber** — only Review-class pending items.
- **Green** — additions posted, depreciation run, FA ties to GL.

### Output sheets & tab order (left to right)
`FA_Close_Readiness` (first), [`FA_GL_Recon`], `FA_Mass_Additions`, `FA_Depreciation` (last).

## Pipeline
1. **Extract — DELEGATE.** br-run-reports runs **`FA Depreciation by period`** (Book) → `FA_Depreciation` (the latest period with rows = last period depreciation ran); and **`FA Unposted Mass Additions`** (Book) → `FA_Mass_Additions` (backlog by status). Optionally `FA Journal Entry Reserve Ledger` for the FA↔GL tie-out → `FA_GL_Recon` (needs a Set of Books Currency param; skip if it errors on a dual-currency ledger). Wait for each; do nothing mid-run.
2. **Anchor.** Record mass-additions backlog count, whether depreciation has run, FA↔GL variance. Clean → Green scorecard.
3. **Score.** Apply CONFIG; rank blockers; attach remediation.
4. **Scorecard *(single `execute_office_js` call)*** (delegate to br-data-dashboard if it fires; else build inline). Write all scorecard sections to `FA_Close_Readiness` in one call: RAG banner (book+period); mass-additions backlog, depreciation status, FA↔GL variance, blocking-items list. Any charts follow in a second call.
   - **Build mechanics (learned on a real run):** build on a NEW sheet at **position 0** (first tab); leave each report on the sheet br-run-reports created (its report name) — do NOT rename it, the dashboard links to it. **Do NOT use a multi-row `copyToRange`** to fill formula rows (it can latch onto the wrong source box and duplicate headers into the data) — write each row's formula explicitly. After building, scan **beyond** the dashboard's column range, clear any stray cells, and widen amount columns so values don't render as `######`.
5. **Narrative.** ≤5 bullets: overall call, biggest blocker, recommended next action.
6. **Arrange tabs + final validation.** Arrange tabs per CONFIG; make `FA_Close_Readiness` active. Only after the scorecard. **Then do the one permitted verification read:** confirm the scorecard's mass-additions backlog count and FA↔GL variance tie to the Step-2 anchor. This is the only explicit re-read allowed in the entire pipeline outside of the anchor step.

## Validation
Scorecard ties to raw sheets; Red only if a Blocker exists. If the mass-additions backlog data
source is unconfirmed, say so in the narrative rather than reporting a false Green.

## Closed-loop (roadmap, not executed here)
FA Mass Additions upload posts additions; Depreciation is a concurrent submit. This skill recommends; a human runs it.
