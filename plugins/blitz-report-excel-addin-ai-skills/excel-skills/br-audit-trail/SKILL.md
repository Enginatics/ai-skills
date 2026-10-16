---
name: br-audit-trail
description: >
  Answer "who changed what, when" across Oracle EBS setups and access: mine the FND Audit Trail
  reports for setup and profile changes by record and column, correlate with user login history and
  responsibility assignments, and produce a reviewable change narrative for an audit window or an
  incident. Read-only. Use when the user asks who changed a setup, wants a segregation-of-duties or
  access review, needs audit evidence for a period, or is investigating an unexpected configuration
  change.
# Trigger: Slash command + auto
---

# EBS Audit Trail & Access Review (br-audit-trail)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.

> **Performance:** read `br-analytics-standards` at the start of every run.

## When to use
"Who changed this supplier's bank account", "what setup changed last month", "audit evidence for
the Q2 window", "who had this responsibility and when did they last use it", "unexpected config
change — investigate". Read-only by nature — this skill produces evidence and narrative, never
changes anything.

## Inputs
- **The question** — an entity/table, a user, or a time window; at least one is required.
- **Date range** — required for window reviews; ask rather than defaulting wide.

## Reports used (authoritative names — do NOT broad-search for them)
| Report (exact name) | Role |
|---|---|
| `FND Audit Setup` | which tables/columns are under AuditTrail — ALWAYS run first (see the hard rule) |
| `FND Audit Table Changes by Record` | the change log per record — who, when, what row |
| `FND Audit Table Changes by Column` | old value → new value per audited column |
| `FND User Login History` | session context around a change — who was on, from where |
| `FND User Responsibilities` | who holds which responsibility, with dates — the access half |
| `FND Users` | account status, last logon — dormant/shared-account signals |

Pass the exact names; fall back to a search only on `#BLITZ_REPORT_NOT_FOUND`.

## 🚨 The hard rule — audit coverage first, never silence
AuditTrail only records tables the customer has ENABLED it for. Run `FND Audit Setup` first, and:
- If the asked-about table/column is NOT audited, the answer is **"not auditable — AuditTrail is
  not enabled for X"**, stated up front — NEVER "no changes found", which reads as a clean bill.
- Every window review names its coverage: "this narrative covers the N audited tables; changes
  outside them are invisible to AuditTrail."
This distinction is the whole integrity of the deliverable.

## Workflow
1. **Coverage**: `FND Audit Setup` → what is auditable. Answer the coverage question explicitly.
2. **Extract** the change log for the scope (by record + by column for the audited entities in the
   window), and the access context (login history, responsibilities) — one call per report.
3. **Build the change narrative**: per change — who, when, old → new, and the session context
   (login proximity). Group by entity and by user; flag the review-worthy patterns:
   - changes outside business hours or from atypical users,
   - rapid change-and-revert pairs (old→new→old),
   - changes by dormant or generic accounts,
   - high-sensitivity columns (bank accounts, profile values, flexfield security) — call these out
     by name.
4. **Access review mode** (when asked): responsibilities per user vs last-login recency — unused
   grants, active grants on dormant accounts, and users holding review-flagged combinations (the
   combination list is CONFIG — the customer's SoD matrix, not ours; label placeholders).
5. **Deliverable**: the narrative sheet (filterable change log), the flagged-patterns summary, and
   the coverage statement. Dashboard optional (br-data-dashboard) for window reviews.

## Hard rules
- Never characterize a change as wrong or unauthorized — report who/what/when and the pattern;
  judgment belongs to the reviewer.
- Old/new values may be sensitive (bank accounts). Present them where the question requires,
  and never copy them beyond the deliverable sheet.

## Degradation rules
- AuditTrail enabled but shadow tables empty for the window → "audited, no changes recorded" —
  that IS a clean answer, distinct from not-audited.
- Login history purged for part of the window → narrative proceeds, context gap stated.

## Talk in the user's language
Users, screens, setups, dates — never `br_*` functions, shadow tables, or helper sheets.
