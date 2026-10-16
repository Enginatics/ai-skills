---
name: br-bom-validator
description: >
  Validate Oracle EBS bill-of-material accuracy against how the shop floor actually consumes
  material: compare BOM structures with WIP component requirements and shortages, flag suspect
  components (never issued, always short, quantity drift), and stage approved BOM corrections via
  the BOM Bill of Materials Upload — only on explicit user confirmation. Use when the user asks
  whether BOMs are accurate, why jobs are always short the same part, or wants BOM cleanup done.
  Recommend-first; WRITES to Oracle EBS only via the gated correction step.
# Trigger: Slash command + auto
---

# BOM Accuracy Validator (br-bom-validator)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.

> **Performance:** read `br-analytics-standards` at the start of every run. For the correction step,
> **read `br-run-uploads` FIRST**.

## When to use
"Are our BOMs accurate", "why is every job short part X", "clean up the BOM for assembly Y",
"which BOM components are dead". For job-level health and WIP value use
**br-wip-variance-analysis**; this skill judges the BILL, using the jobs as evidence.

## Inputs
- **Organization Code** (required) — ask if not supplied.
- **Assembly scope** — an assembly, a range, or org-wide (warn on org-wide size; narrow if the user
  can).
- **Evidence window** — default 12 months of WIP history; say so.

## Reports and uploads used (authoritative names — do NOT broad-search for them)
| Name | Type | Role |
|---|---|---|
| `BOM Bill of Material Structure` | Report | the bills as defined — components, quantities, yields, effectivity |
| `WIP Required Components` | Report | what jobs actually required/issued per component |
| `WIP Discrete Job Shortage` | Report | recurring shortages — the "bill says X, floor needs more" signal |
| `WIP Component Report` | Report | issue detail cross-check on suspect components |
| `BOM Bill of Materials Upload` | Upload | **write path** for approved corrections |

Pass the exact names; fall back to a search only on `#BLITZ_REPORT_NOT_FOUND`.
Engineering-change (ECN) impact is out of scope — no ECN report ships; say so if asked.

## Workflow
1. **Extract** the BOM structures for the scope and the WIP evidence for the window (one call per
   report).
2. **Score each BOM component** against the evidence:
   - **DEAD** — on the bill, never required/issued by any job in the window (candidate to remove or
     end-date).
   - **UNDER-QUANTITY** — jobs consistently issue/require more than the bill quantity, or the part
     recurs on shortages across jobs (candidate to raise qty or fix yield).
   - **OVER-QUANTITY** — jobs consistently consume less (candidate to lower qty; scrap-factor
     suspects called out).
   - **OFF-BOM USAGE** — components jobs issue that are NOT on the bill (candidate to add).
   - **OK** — evidence matches the bill.
   Every non-OK class carries its evidence inline: jobs counted, average actual vs bill quantity.
3. **Rank** by financial effect (quantity drift × component cost × annual build volume) so the
   cleanup list starts where it pays.
4. **Deliverable**: per-assembly validation sheet + the ranked correction candidates + dashboard
   (br-data-dashboard).
5. **Correct (optional, gated)**: only for corrections the user explicitly approves — download the
   `BOM Bill of Materials Upload` for the assemblies, apply ONLY the approved changes (quantity
   updates, end-dates, additions), validate, show assembly/component count and before/after values,
   submit on a second explicit confirmation. Remind the user a changed bill affects future jobs
   and cost rollups — existing jobs keep their snapshots.

## Hard rules
- Evidence below a minimum job count (default 5 jobs — CONFIG, label it) → the component is
  INSUFFICIENT-EVIDENCE, never a candidate.
- Alternate/option-class structures: validate only the standard bill unless the user names an
  alternate; say which bill was judged.
- Never propose removing a component that appears on open jobs' requirements.

## Degradation rules
- No WIP history for an assembly (never built in the window) → the bill is UNVERIFIABLE, listed
  separately — absence of evidence is not accuracy.

## Talk in the user's language
Assemblies, components, quantities, jobs — never `br_*` functions or helper sheets.
