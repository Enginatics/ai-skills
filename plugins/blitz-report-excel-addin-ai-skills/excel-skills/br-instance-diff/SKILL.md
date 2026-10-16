---
name: br-instance-diff
description: >
  Compare Oracle EBS instances through Blitz Reports in Excel: run the same report with the same
  parameters against two configured environments (DEV/TEST/PROD, pre/post-upgrade, source/clone)
  and explain the differences — row counts, missing and extra keys, changed values by column — or
  diff the two instances' report catalogs. Use when the user asks to compare environments, validate
  an upgrade or clone, check TEST against PROD, or "why is this report different on X".
# Trigger: Slash command + auto
---

# Instance Diff (br-instance-diff)

> 🚨 **Blitz data = Excel worksheet UDFs, not MCP tools/connectors.** Extract data only by writing `=br_...()` into a cell (via `execute_office_js`) and reading the spill — **never** `tool_search` for `br_*`, **never** `refresh_mcp_connectors`, and never conclude "no Oracle EBS / Blitz connector is set up" (the Blitz Report add-in is an Excel add-in, not an MCP connector, so it never appears in the connector list — its absence there is expected). Load the extraction mechanism first: `read_skill("br-run-reports")`.

Run the identical question against two instances and explain what differs. The environment plumbing
already exists — `br_environments_external()` lists the configured environments, and every run/list
UDF takes an `environment` argument. This skill adds the discipline: identical parameters, honest
alignment, and a difference report that separates *data drift* from *definition drift*.

**Requires:** br-run-reports.

## Division of responsibility — READ FIRST
Extraction is by **br-run-reports** (pass it the environment and responsibility per run). This
skill owns pairing, key alignment, and the diff. **Read-only on both sides** — never an upload,
never a fix, on either instance.

## When to use
"Compare TEST to PROD", "did the upgrade change the numbers", "validate the clone", "same report,
two instances", "is the report list the same on both". NOT for comparing two *periods* on one
instance — that is an ordinary report question.

## Two modes — ask which if unclear
- **Catalog diff** — which reports exist / differ between the instances. Cheap; run it first when
  the question is about an upgrade or content transfer.
- **Data diff** — same report + same parameters on both; compare the rows. The main event for
  clone/upgrade validation.

## Ground rules that keep a diff honest
1. **Both environments must be configured in the add-in** (ribbon → Environments) and reachable.
   `=br_environments_external()` first; if the target is missing, the user adds it — you cannot.
2. **Logins are interactive.** A run against a not-yet-connected environment returns
   `#BLITZ_NOT_CONNECTED` — ask the user to connect to THAT environment via the ribbon, then
   retry. Expect this once per environment per session. The responsibility must exist for the user
   on both sides; pass the same responsibility name to both runs.
3. **Identical parameters, restrictive parameters.** Never diff wide-open extracts — pick filters
   that bound the set (a period, an OU, a customer range) and pass the byte-same values to both
   runs. If a parameter's LOV value differs across instances (a renamed ledger), say so — that is
   itself a finding.
4. **Clones drift by age.** A TEST cloned in June differs from PROD in August by every transaction
   since — that is expected, not a defect. Ask for the clone date up front and lead the report
   with it; the interesting differences are the ones a clone-lag CANNOT explain (setup, missing
   columns, changed valuations on pre-clone data).
5. **Run the two sides close together in time** so in-flight activity doesn't masquerade as drift.

## Pipeline

### Step 0 — Frame  *(one `ask_user_question` if anything is missing)*
Mode; the two environments (from `br_environments_external()`); for data diff: the report (exact
name — via **br-report-finder** if the user only knows the topic), the parameter set, and the **key
columns** that identify a row (invoice number, journal name + line, item + org…). No key, no
row-level diff — offer aggregate-only comparison instead.

### Mode A — Catalog diff  *(two calls + one in-memory compare)*
`=br_report_list_external("", "<envA>")` → sheet `Catalog_A`; same for B. Compare on Report Name:
only-in-A, only-in-B, both-but-different (Category or Type changed). Output `Catalog_Diff` with the
three lists and counts. Typical reading: only-in-A after a content transfer = reports that did not
make it; Type changes = a report replaced by an upload.

### Mode B — Data diff
1. **Extract twice — DELEGATE.** br-run-reports runs the report with the agreed parameters against
   env A → `Diff_A`, then env B → `Diff_B`. Sequentially, never overlapped. Record row counts and
   run times.
2. **Align  *(single `execute_office_js` call)*.** Verify the two sheets' column headers match —
   **a header mismatch is a definition difference; report it first and diff only the shared
   columns.** Build the key per row; flag duplicate keys (they force aggregate comparison for that
   key).
3. **Diff  *(same or second call)*.** Three buckets: keys only in A, only in B, and matched keys
   with per-column value differences — numeric columns compared with a tolerance (default 0.01;
   surface systematic offsets like FX or rounding as a pattern, not 10,000 cell diffs), text/date
   columns exact. Cap the detail at the top 500 differing rows by absolute $ impact; always keep
   full counts.
4. **Report  *(one `.values =` write per sheet)*.** `Instance_Diff` (first tab): verdict line
   (IDENTICAL / EXPLAINED BY CLONE LAG / DIFFERENCES FOUND), the counts (rows A/B, missing, extra,
   changed), per-column change counts, and the top differences with A-value vs B-value side by
   side. Detail rows on `Diff_Detail`. State the clone date and which differences it explains.
5. **Narrative.** ≤5 bullets: the verdict, the largest unexplained difference, definition drift if
   any, recommended follow-up (usually: re-run after the next refresh, or investigate one named
   setup difference).

## Validation
- Both runs used byte-identical parameter strings (echo them on `Instance_Diff`).
- Missing + extra + changed + identical = total matched universe; the counts reconcile.
- Header mismatches reported as definition drift, never silently intersected away.
- No wide-open extract; no write to either instance.

## Re-run / refresh
Same pairing re-run overwrites `Diff_A`/`Diff_B` and rebuilds the diff sheets; a different report
or environment pair starts fresh sheets. After a PROD→TEST refresh, re-run to confirm the diff
collapses to IDENTICAL — that is the clone-validation sign-off.
