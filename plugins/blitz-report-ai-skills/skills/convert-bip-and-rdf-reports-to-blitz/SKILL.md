---
name: convert-bip-and-rdf-reports-to-blitz
description: End-to-end conversion of Oracle RDF, BI Publisher, or Concurrent Program reports to Blitz Reports. Includes conversion rules, deployment, testing, duplicate detection, and iterative performance optimization.
metadata:
  title: Convert Oracle Reports to Blitz Report
  category: Migration
---

## Arguments

$ARGUMENTS should contain one of:
- File path to source report (`.xml` data template or auto-converted Blitz XML)
- Concurrent program name (e.g., `FADTXA`)
- Report description (e.g., "FA Tax Reserve Report")

If a folder path is provided, look for both the auto-converted Blitz XML and the original RDF data template within it.

## Output Location

All versioned XML files (`_v01.xml`, `_v02.xml`, etc.) are placed in the **same folder as the source files**.
## Converting Oracle BI Publisher and RDF Reports to Blitz Reports

### SQL Consolidation

BI Publisher data definitions often contain multiple SQL queries (Q1, Q2, Q3, etc.) linked via parent-child relationships. For Blitz Reports, consolidate these into a single SQL using `UNION ALL` with a discriminator column (e.g., `exception_type`) to identify the source.

- **Separate queries become `union all` branches; a `union` inside one original query stays `union`.** It de-duplicates over the original's whole select list, ids and rowids included, so carry those key columns through an inline view and drop them in the outer select.
- **Consolidate only what the original prints.** A query whose parent group has a group filter, or whose frame has a format trigger returning FALSE, prints only when those allow it. A section the original never prints is not a branch. Read section 3 of the field inventory (`migrate-custom-reports/field_inventory.py`) before choosing branches.

**Example from APXPCER (Period Close Exceptions):**
```sql
select x.* from (
  select 'Unaccounted Invoices' exception_type, ... from ... where 2=2
  union all
  select 'Unaccounted Payments' exception_type, ... from ... where 3=3
  union all
  select 'Future Dated Payments' exception_type, ... from ... where 4=4
) x where 1=1
```

### Report Assignments - CRITICAL

**`ASSIGNMENT_LEVEL` now uses FULL WORDS** (`Application`, `Request Group`, `Form`, `Function`, ...) — the old single-letter codes (`A`/`G`/`F`) no longer resolve and are silently skipped on import. **DO NOT** rely on a single application-level assignment. Derive assignments **data-driven** from the report's data domain + `fnd_request_group_units` (the program's request groups), mirroring each relevant application's request groups, plus major-country localization request groups, per `report-development` skill "Report Assignments" (reach model, #1 mirror, #4 localization, #3 security, #5 forms). For uploads, assign **Function level only, to update-enabled functions** (`upload-development` skill I7).

**Assignment Derivation SQL**:
```sql
select distinct
  'Request Group' assignment_level,
  'I' include_exclude,   -- Include
  frg.request_group_name level_value,
  fa.application_short_name
from
  fnd_request_groups frg,
  fnd_request_group_units frgu,
  fnd_application fa,
  fnd_concurrent_programs fcp
where
  frg.request_group_id = frgu.request_group_id and
  frg.application_id = fa.application_id and
  (
    (frgu.unit_application_id = fcp.application_id and
     frgu.request_unit_id = fcp.concurrent_program_id and
     frgu.request_unit_type = 'P')  -- Program directly assigned
    or
    (frgu.unit_application_id = fcp.application_id and
     frgu.request_unit_type = 'A')  -- Application assigned
  ) and
  fcp.concurrent_program_name = :p_concurrent_program_name
```

**Assignment XML Structure:**
```xml
<ASSIGNMENTS>
 <ASSIGNMENTS_ROW>
  <REPORT_NAME>AP Period Close Exceptions</REPORT_NAME>
  <INCLUDE_EXCLUDE>I</INCLUDE_EXCLUDE>
  <ASSIGNMENT_LEVEL>Request Group</ASSIGNMENT_LEVEL>
  <LEVEL_VALUE>All Reports</LEVEL_VALUE>
  <APPLICATION_SHORT_NAME>SQLAP</APPLICATION_SHORT_NAME>
  <FORM_PARAMETERS>
  </FORM_PARAMETERS>
 </ASSIGNMENTS_ROW>
</ASSIGNMENTS>
```

**Assignment Levels** (use the full-word value in `<ASSIGNMENT_LEVEL>`):
| Level (value) | Reaches | Notes |
|-------|------|-------------|
| `Application` | all responsibilities owned by the application | keep only for apps owning no low-privilege/self-service responsibilities |
| `Request Group` | all responsibilities using that request group | **preferred**; `APPLICATION_SHORT_NAME` mandatory (names repeat across apps) |
| `Form` | responsibilities granting that form | reports only; supports `FORM_PARAMETERS` zoom mapping |
| `Function` | responsibilities granting that function | **uploads only** — update-enabled functions ONLY (no read-only) |
| `Responsibility` | that responsibility | |
| `User` | that user | |

### Report Translations

Include translations for all supported languages from the original BI Publisher report:
- AR (Arabic), D (German), E (Spanish), F (French), I (Italian)
- JA (Japanese), KO (Korean), PTB (Brazilian Portuguese)
- RU (Russian), S (Swedish), TR (Turkish), US (English), ZHS (Simplified Chinese)

### Categories

Include appropriate categories:
- `BI Publisher` - Indicates source is BI Publisher
- `R12 only` - Only if report uses R12-specific tables/features not available in 11i (use sparingly)

**Note:** Categories must be defined in a `<CATEGORIES>` section in the XML before being referenced. See "Parameter Design Patterns" section below.

### Anchors for Branch-Specific Filtering

Use numbered anchors to apply parameters to specific UNION branches:
- `1=1` - Outer query filter (applies to all)
- `2=2` through `9=9` - Branch-specific filters

### Parameter Design Patterns

#### CATEGORIES Section Required
When using categories in a report XML, define them in a separate `<CATEGORIES>` section BEFORE the `<REPORTS>` section:
```xml
<ROOT>
 <APPS_INITIALIZE_DATA>...</APPS_INITIALIZE_DATA>
<CATEGORIES>
 <CATEGORIES_ROW>
  <BASE_CATEGORY>BI Publisher</BASE_CATEGORY>
  <CATEGORY_TRANSLATIONS>
   <CATEGORY_TRANSLATIONS_ROW>
    <LANGUAGE>US</LANGUAGE>
    <CATEGORY>BI Publisher</CATEGORY>
   </CATEGORY_TRANSLATIONS_ROW>
  </CATEGORY_TRANSLATIONS>
 </CATEGORIES_ROW>
</CATEGORIES>
<REPORTS>
 ...
</REPORTS>
</ROOT>
```

#### Linked Parameters (No DISPLAY_SEQUENCE) for Multi-Branch Filters
When the same user-entered value needs to filter multiple UNION ALL branches, use **linked parameters**:

1. Create ONE visible parameter with `<DISPLAY_SEQUENCE>` - this shows in the UI
2. Create additional "ghost" parameters WITHOUT `<DISPLAY_SEQUENCE>` that use the same bind variable but different anchors

```xml
<!-- Visible parameter (user enters value here) -->
<PARAMETERS_ROW>
  <SORT_ORDER>4</SORT_ORDER>
  <DISPLAY_SEQUENCE>40</DISPLAY_SEQUENCE>  <!-- Has DISPLAY_SEQUENCE = shows in UI -->
  <ANCHOR>2=2</ANCHOR>
  <SQL_TEXT>aid.accounting_date>=:p_period_start_date</SQL_TEXT>
  <PARAMETER_TYPE_DSP>Date</PARAMETER_TYPE_DSP>
  <DEFAULT_VALUE>trunc(sysdate,'MM')</DEFAULT_VALUE>
  <PARAMETER_TRANSLATIONS>...</PARAMETER_TRANSLATIONS>
</PARAMETERS_ROW>

<!-- Linked parameter for anchor 3=3 (NO DISPLAY_SEQUENCE = hidden) -->
<PARAMETERS_ROW>
  <SORT_ORDER>5</SORT_ORDER>
  <!-- NO DISPLAY_SEQUENCE - parameter doesn't show in UI but applies filter -->
  <ANCHOR>3=3</ANCHOR>
  <SQL_TEXT>aph.accounting_date>=:p_period_start_date</SQL_TEXT>  <!-- Same bind variable -->
  <PARAMETER_TRANSLATIONS>...</PARAMETER_TRANSLATIONS>
</PARAMETERS_ROW>

<!-- Linked parameter for anchor 4=4 -->
<PARAMETERS_ROW>
  <SORT_ORDER>6</SORT_ORDER>
  <ANCHOR>4=4</ANCHOR>
  <SQL_TEXT>aca.future_pay_due_date>=:p_period_start_date</SQL_TEXT>
  <PARAMETER_TRANSLATIONS>...</PARAMETER_TRANSLATIONS>
</PARAMETERS_ROW>
```

**Key Points:**
- Parameters WITHOUT `<DISPLAY_SEQUENCE>` don't appear in the UI but still apply their SQL_TEXT
- Use the SAME bind variable (`:p_period_start_date`) across all linked parameters
- Each linked parameter can reference different columns appropriate to its branch
- This is preferred over hidden parameters with `<DISPLAY_TYPE>H</DISPLAY_TYPE>`

#### Date Comparison Best Practice
Use `< date + 1` instead of `<= date` for end date comparisons to properly handle time components:

```xml
<!-- Bad: May miss records with time component -->
<SQL_TEXT>aid.accounting_date<=:p_period_end_date</SQL_TEXT>

<!-- Good: Properly includes all records on the end date -->
<SQL_TEXT>aid.accounting_date<:p_period_end_date+1</SQL_TEXT>
```

#### Ledger LOV Security
Ledger LOVs must respect GL Access Set security. Use this pattern:
```sql
select
gl.name value,
fifsv.id_flex_structure_name||': '||decode(gl.ledger_category_code,'NONE',
  xxen_util.meaning(gl.object_type_code,'LEDGERS',101),
  xxen_util.meaning(gl.ledger_category_code,'GL_ASF_LEDGER_CATEGORY',101))||': '||gl.description description
from
gl_ledgers gl,
fnd_id_flex_structures_vl fifsv
where
gl.ledger_id in (
  select nvl(glsnav.ledger_id,gasna.ledger_id)
  from gl_access_set_norm_assign gasna, gl_ledger_set_norm_assign_v glsnav
  where gasna.access_set_id=fnd_profile.value('GL_ACCESS_SET_ID')
  and gasna.ledger_id=glsnav.ledger_set_id(+)
) and
gl.chart_of_accounts_id=fifsv.id_flex_num and
fifsv.id_flex_code='GL#' and
fifsv.application_id=101
order by
fifsv.id_flex_structure_name,
decode(gl.ledger_category_code,'PRIMARY',1,'SECONDARY',2,'ALC',3,'NONE',4),
gl.name
```

### Performance: Outer Query (1=1) vs Inner Branch Anchors

**Critical Performance Consideration:**

Parameters on `1=1` (outer query) filter AFTER all UNION branches execute:
```sql
select x.* from (
  -- Branch 1: Executes fully
  union all
  -- Branch 2: Executes fully
  ...
) x
where 1=1  -- Filters applied HERE, after all data fetched
```

Parameters on inner anchors (2=2, 3=3, etc.) filter DURING branch execution:
```sql
select x.* from (
  select ... where 2=2  -- Filter applied HERE, can use indexes
  union all
  select ... where 3=3  -- Filter applied HERE, can use indexes
) x where 1=1
```

**Recommendations:**
| Filter Type | Recommended Anchor | Reason |
|-------------|-------------------|--------|
| Date ranges | Inner (2=2, 3=3...) | Critical for performance - enables index usage |
| Ledger/Org Unit | Can use 1=1 | Oracle may push predicates; acceptable for period reports |
| Exception Type | 1=1 is OK | Oracle can eliminate branches for literal comparisons |
| Supplier | 1=1 is OK | Different source tables per branch make inner filtering complex |

**For high-volume reports:** Push Ledger and Operating Unit filters into each branch for guaranteed predicate pushdown:
```sql
-- Inside each branch, add:
aia.set_of_books_id in (select gl.ledger_id from gl_ledgers gl where gl.name=:p_ledger) and
aia.org_id in (select haou.organization_id from hr_all_organization_units haou where haou.name=:p_operating_unit) and
```

### Critical: Anchor Uniqueness per Table Structure

**Each UNION branch with different table structures MUST have its own unique anchor.**

When converting BI Publisher reports that use Global Temporary Tables (GTT), the original report pre-filters data into the GTT, then queries it. When converting to Blitz Report (querying base tables directly), each branch may have different tables available for filtering.

**Example Problem - AP Period Close Exceptions:**
```sql
-- Branch 1: Unaccounted Invoice Distributions (has aid table)
select ... from ap_invoice_distributions_all aid ... where 2=2

-- Branch 2: Invoices Without Distributions (NO aid table!)
select ... from ap_invoices_all aia, ap_invoice_lines_all aila ...
where not exists (select null from ap_invoice_distributions_all aid2 ...) and
2=2  -- ERROR: Parameter aid.accounting_date will fail - no aid table!
```

**Solution:** Use different anchors for branches with different table structures:
```sql
-- Branch 1: Use 2=2 with aid.accounting_date filter
select ... from ap_invoice_distributions_all aid ... where 2=2

-- Branch 2: Use 10=10 with aia.invoice_date filter (appropriate column for this branch)
select ... from ap_invoices_all aia, ap_invoice_lines_all aila ...
where not exists (...) and 10=10
```

**Key Rule:** Before assigning an anchor, verify that ALL columns referenced in parameters for that anchor exist in the branch's FROM clause.

### R12 Table Column Differences

Some R12 tables don't have columns you might expect. Common issues:

| Table | Missing Column | Solution |
|-------|----------------|----------|
| `ap_checks_all` | `set_of_books_id` | Join through `ap_system_parameters_all asp` using `aca.org_id=asp.org_id` and `asp.set_of_books_id=gl.ledger_id` |

### Conversion Checklist

- [ ] Field inventory generated (`migrate-custom-reports/field_inventory.py`) and every row given a Blitz expression or a reason from the source
- [ ] Consolidate the printed queries into a single statement with UNION ALL, keeping a `union` inside an original query as `union` over its key
- [ ] Per-row logic reproduced: formula columns, placeholders, package loop code filling cursor literals, format triggers and group filters
- [ ] Edge behaviour reproduced: lookups with no row or several, widths, `nvl` defaults, dates as text, row order and grain, serial numbers, report modes
- [ ] Add discriminator column for exception/record types
- [ ] Derive assignments from fnd_request_group_units (Request Group level G)
- [ ] Include all language translations
- [ ] Define categories in `<CATEGORIES>` section before `<REPORTS>`
- [ ] Generate unique GUID: `select rawtohex(sys_guid()) from dual`
- [ ] Map parameters with correct LOVs and dependencies
- [ ] Set up anchors for branch-specific filtering
- [ ] Verify each anchor's columns exist in that branch's FROM clause (critical!)
- [ ] Use linked parameters (no DISPLAY_SEQUENCE) for multi-branch date filters
- [ ] Use `< date+1` instead of `<= date` for end date comparisons
- [ ] Include GL Access Set security in Ledger LOV query
- [ ] Place performance-critical filters (dates) on inner anchors, not 1=1
- [ ] Remove BIP Code reference if the Blitz SQL is fully self-contained (see below)

**Note:** Use `&amp;` for ampersands in XML (e.g., "Implementation Sales & Service" becomes "Implementation Sales &amp; Service")

### BIP Code (Data Source Reference)

The `XDO_APPLICATION_SHORT_NAME` and `XDO_DATA_SOURCE_CODE` XML elements link a Blitz Report to an Oracle BI Publisher data template. When set, the framework executes the data template's **beforeReportTrigger** PL/SQL package before running the report SQL.

**Keep BIP Code when:**
- The Blitz SQL **depends on** the Oracle before-report trigger to initialize package variables, populate GTTs, or perform setup

**Remove BIP Code when:**
- The Blitz SQL is **fully self-contained** — all joins, subqueries, and parameters are in the BR itself
- All data template logic has been inlined into the SQL during conversion
- Unnecessary references cause harmless but noisy "package variable does not exist" warnings in the log

```xml
<!-- Remove these two lines when not needed -->
<XDO_APPLICATION_SHORT_NAME>GMF</XDO_APPLICATION_SHORT_NAME>
<XDO_DATA_SOURCE_CODE>GMFDSUR</XDO_DATA_SOURCE_CODE>
```

## Report GUID Generation

When creating new Blitz Report XML definitions, the GUID field must be populated with a globally unique identifier.

**GUID Field Details:**
- Database Type: `RAW(16)` - 16 bytes binary data
- XML Format: 32-character hexadecimal string (uppercase, no hyphens or separators)
- Uniqueness: Must be unique across all reports in the system
- Indexed: Unique index exists on `xxen_reports.guid`

**How GUID is Generated:**
The GUID is generated using Oracle's built-in `sys_guid()` function.

**SQL to Generate New GUID:**
```sql
select rawtohex(sys_guid()) from dual;
```

**Example GUID Values:**
```
4A9F4B6B0E4F285AE0530100007F85D7
D23CFAD3DBADE590E05362FB0905CC73
E0530100007F0001E0530100007F0001
```

**XML Format:**
```xml
<REPORTS_ROW>
  <GUID>4A9F4B6B0E4F285AE0530100007F85D7</GUID>
  <SQL_TEXT>select...</SQL_TEXT>
  ...
</REPORTS_ROW>
```

**Important:**
- Always generate a new GUID for each new report definition
- Never reuse GUIDs from other reports
- The `copied_from_guid` field (also `RAW(16)`) can reference another report's GUID if the report was copied
- LOVs also have their own GUIDs in `xxen_report_parameter_lovs.guid`

## End-to-End Conversion Pipeline

When converting a report end-to-end, follow these phases. The conversion rules above cover the SQL/XML creation (Phase 2). The phases below add analysis, deployment, testing, and performance optimization.

### Phase 1 — Analyze Source

**Invoke:** `rdf-analyzer` skill (or `/analyze-rdf` command)

1. Identify report type (Oracle Reports .rdf, BI Publisher XML template, Concurrent Program)
2. Locate source files:
   - Auto-converted Blitz XML (from "Blitz Report RDF Import" tool)
   - Original RDF data template (`.xml` with `<dataTemplate>`)
   - Or concurrent program definition in the database
   - Pull a data template out of `xdo_lobs` (BLOB) and an `xxen_api.export_report` CLOB with `utl_file` in binary mode (`fopen(...,'wb')` + `put_raw`) into the `TMP` directory: `dbms_output` raises `host bind array too small` above 32767 bytes per line and text-mode `utl_file.put` silently truncates at `max_linesize`. `xxen_api.import_concurrent_program` followed by the export gives the auto-derived parameters, LOVs and request-group assignments to start from.
3. Extract into a Report Analysis Document (RAD):
   - All SQL queries (Q_MAIN, Q_DETAIL, etc.)
   - Parameters with types, defaults, value sets
   - PL/SQL formula functions and their logic
   - Master-detail relationships
   - Output columns and calculated fields
   - Request group assignments
4. If source is an auto-converted Blitz XML, also check for corrupted/duplicated SQL fragments
5. Generate the field inventory from the gathered files: `python ${CLAUDE_PLUGIN_ROOT}/skills/migrate-custom-reports/field_inventory.py <folder>`. It lists every printed field and where the original computes it, every formula and what it assigns, and everything that decides which rows print. It is the work list for Phase 2.

**Gate:** RAD must contain at least 1 SQL query and parameter definitions, and the field inventory must exist.

### Phase 2 — Convert to Blitz

Apply all the conversion rules documented above (SQL Consolidation, Assignments, Translations, Categories, Anchors, Parameters, etc.) plus the `coding-standards` skill rules. Convert every row of the field inventory, not only the queries, and fill in its Blitz expression column as you go.

**Output:** `<ReportName>_v01.xml` in the source folder

**Gate:** Valid XML with SQL_TEXT, PARAMETERS, ANCHORS, ASSIGNMENTS sections.

### Phase 3 — Deploy & First Run

**Invoke:** `deploy-xml` skill

1. **Deploy to the development instance** (see `blitz-environment.md` for how to reach the instance): copy the XML to a temp directory on the apps tier and import it from there, or import the file content with `xxen_api.import_xml(<clob>)`:
   ```bash
   cd /tmp && $XXEN_TOP/bin/import_xml $APPS_PWD <filename>
   ```

2. **Submit report** with parameters from the RAD:
   ```sql
   declare
   l_run_id number;
   l_request_id number;
   l_error varchar2(4000);
   begin
   fnd_global.apps_initialize(user_id=><user_id>, resp_id=>20420, resp_appl_id=>1); --your own EBS user: select fu.user_id from fnd_user fu where fu.user_name='<YOUR_USER>'
   mo_global.init('M');
   mo_global.set_policy_context('M', null);
   l_run_id:=xxen_api.create_run_id_('<Report Name>');
   -- Set ALL required parameters
   xxen_api.set_parameter_value_(p_parameter_name=>'<Name>', p_value=>'<Value>', p_run_id=>l_run_id);
   l_error:=xxen_report.report_submit_concurrent(xxen_report.report_id('<Report Name>'), l_run_id, l_request_id);
   dbms_output.put_line(nvl(l_error, 'Request ID: '||l_request_id));
   commit;
   end;
   ```

3. **Wait for completion:**
   ```sql
   select fcr.phase_code, fcr.status_code, fcr.completion_text
   from fnd_concurrent_requests fcr where fcr.request_id=:request_id
   ```

4. **If error**: Read log, diagnose, fix SQL, create `_v02.xml`, re-deploy, retry (max 3 attempts)

**Gate:** Report completes with `phase_code='C'` and `status_code='C'`.

### Phase 4 — Validate Results

1. **Row count check**: Must return > 0 rows
   ```sql
   select fcr.number_of_copies from fnd_concurrent_requests fcr where fcr.request_id=:request_id
   -- Or check completion_text for row count
   ```

2. **Row grain**: Identify key columns from the SQL (transaction IDs, line IDs, unique identifiers) and check:
   ```sql
   select count(*) total_rows, count(distinct x.key_col1||'~'||x.key_col2) distinct_rows
   from (<report_sql_with_params>) x
   ```
   If `total_rows > distinct_rows`, find which join fans out. Then compare with the original's grain: its group and break keys and its `union` key. Repeated rows the original also prints are correct, and rows it collapses are not.

3. **Data comparison** (invoke `report-tester` skill):
   - If the original concurrent program can be run, submit it with same parameters
   - Compare row counts and key aggregate totals (SUM of amount columns)
   - Document any expected differences (e.g., Blitz shows detail vs original shows summary)

4. **Value fidelity gate** (`migrate-custom-reports/references/value-fidelity.md`). This is the check that compares values; steps 1 to 3 do not.
   - The field inventory is complete.
   - The original's formulas, ported as PL/SQL, agree with every Blitz column on every row. Use stand-in rows where the instance lacks the data.
   - The customer's ERP output agrees on columns, order, headings, grain and every recomputable relation.
   - A correction leaves every unchanged column at 0 differences.
   - Before the first delivery, an independent audit agent finds nothing DIFFERENT or MISSING.

   Row counts and sums match on wrong reports too: a column that is blank for one branch, a lookup that picks the wrong one of several rows, or a date basis that differs all leave them unchanged.

**Gate:** The value fidelity gate passes. Row grain matches the original's, and row counts and aggregates match the original or the differences are explained.

### Phase 5 — Performance Analysis & Optimization Loop

**Target:** Time/exec < 60 seconds AND IO/row < 1 MB

**Follow the `tune-report-performance` skill** for the full methodology:

1. Run report with production-like parameters (wide date range, thousands of rows). In a harness, fetch every output column; a `count(*)` lets Oracle skip the select-list subqueries and hides their cost.
2. Run "DBA SGA SQL Performance Summary" with `Module Name` = first 34 chars of report name
3. Run "DBA SGA SQL Execution Plan History" for the main SQL_ID
4. Apply fixes using consolidation patterns from the tune skill

**Decision logic:**
- If `Time Exec < 60` AND `IO Row < 1`: **PASS** → go to Phase 6
- If any PL/SQL function has `Executions > 10000`: flag for inlining
- If main SQL has `IO Row > 1`: **FAIL** → optimize, re-deploy, re-measure (max 3 iterations)

### Phase 6 — Finalize

1. Update `<VERSION_COMMENTS>` in the final XML with a summary of all changes across versions
2. Generate a **Conversion Summary Report**:

```markdown
# Conversion Summary: <Report Name>
**Source:** <RDF/BIP concurrent program name>
**Date:** <date>

## Versions
| Version | Changes | Status |
|---------|---------|--------|
| v01 | Initial conversion from RDF | Error: ORA-XXXXX |
| v02 | Fixed function signature, added assignments | Runs OK, 486s/exec |
| v03 | Consolidated 6 tax subqueries, inlined item attribute function | 180s/exec |

## Performance
| Metric | Before (v02) | After (v03) | Improvement |
|--------|-------------|-------------|-------------|
| Time/exec | 486s | 180s | 63% |
| IO/row | 6.91 MB | 2.1 MB | 70% |
| Buffer IO | 1.7 TB | 520 GB | 69% |

## Test Results
- Row count: 83,540 rows (matches original)
- Duplicates: None detected
- Key aggregates: Match within rounding tolerance
```

## Error Recovery

| Error | Recovery |
|-------|----------|
| ORA-06553: PLS-306 wrong arguments | Query `all_source` for function signature, fix parameter count/types |
| ORA-00904: invalid identifier | Check column names against table definitions, fix typos |
| ORA-01008: not all variables bound | Check parameter anchor vs bind syntax, add missing PARAMETERS_ROW |
| Report returns 0 rows | Verify parameter defaults, check date ranges against data |
| Duplicate rows detected | Analyze joins for fan-out, add DISTINCT or fix join conditions |
| Import error | Check XML structure, ensure CATEGORIES before REPORTS, valid escaping |

## Integration with Existing Skills

This skill orchestrates these existing skills:
1. `rdf-analyzer` → Phase 1
2. `blitz-report-developer` → Phase 2 (report patterns)
3. `deploy-xml` → Phase 3
4. `report-tester` → Phase 4
5. `tune-report-performance` → Phase 5