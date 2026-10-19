---
name: upload-validator
description: Review a Blitz Upload against the Oracle standard form and run E2E tests. Use when user asks to review, validate, or test an upload — or after building/modifying an upload.
metadata:
  title: Upload Validator
  category: Upload Development
---

# Upload Validator Skill

Reviews a Blitz Upload by comparing it against the Oracle EBS standard form and runs automated end-to-end tests. Acts as the **Validator** in the multi-agent upload development workflow.

## When to Use

- After creating or significantly modifying an upload (XML + PL/SQL)
- When user asks to review, validate, or test an upload
- As the final quality gate before delivering an upload

## Arguments

$ARGUMENTS should contain the upload name or XML file path (e.g., "FA Asset Upload" or "content/r12/uploads/FA_Asset_Upload.xml").

## Inputs Required

1. **Upload XML file** — the Blitz upload XML definition
2. **Upload PL/SQL package** — the processing package (spec + body)
3. **Oracle form name** — the standard EBS form this upload replicates (e.g., FAXASSET for FA, APXINWKB for AP)

If the Oracle form name is not provided, infer it from the upload's module and purpose.

## Phase 1: Oracle Form Analysis

Use the `oracle-forms-analyzer` skill to analyze the standard form. Request the full Form Analysis Document: field inventory, LOV map, defaulting map, validation map, KFF map, and API details.

Save the output for comparison in Phase 2.

## Phase 2: Upload Review Checklist

Compare the upload XML + PL/SQL against the Form Analysis Document. Check each category and report findings.

### Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **BLOCKER** | Upload will fail, corrupt data, or miss critical validation | Must fix before import |
| **MAJOR** | Incorrect behavior vs Oracle form, data quality risk | Should fix before production use |
| **MINOR** | Cosmetic or minor deviation from form behavior | Fix if time permits |
| **SUGGESTION** | Enhancement opportunity, not a defect | Consider for future iteration |

### Issue ID Format

Each issue gets a structured ID: `[CAT-n-NNN]` where:
- `CAT` = category number (1-10)
- `n` = severity (B=blocker, M=major, m=minor, S=suggestion)
- `NNN` = sequential number within category

Example: `[CAT-4-B-001]` = Category 4 (LOVs), Blocker, first issue.

### 2.1 Missing Fields

For every field visible/editable in the Oracle form:
- Check if a corresponding column exists in the upload
- Exceptions: framework columns (Action, Status, Message, Modified Columns), display-only computed fields, WHO columns

**Common misses:**
- DFF attributes (ATTRIBUTE_CATEGORY + ATTRIBUTE1..15)
- KFF individual segments (form allows segment-by-segment entry)
- Alias fields for flexfields
- Comments/notes fields

### 2.2 Field Naming (CRITICAL — Use Form Prompts)

For each upload column, verify the alias matches the **form Prompt attribute** from the FAD (section 4.1), NOT the internal database column name:
- Upload column aliases become Excel headers — must match what Oracle form users see
- The FAD field inventory includes the Prompt for each field — use it as the upload column alias
- Related fields should use consistent prefixes (e.g., "Expense Account", "Expense Segment1")

**Common issues:**
- Internal DB column names instead of form Prompts (e.g., "RECEIPT_METHOD_ID" instead of "Receipt Method")
- Form Prompt differs from DB column (e.g., form says "Amount" but DB column is "RECEIPT_AMOUNT")
- Missing module prefix when name is ambiguous
- Inconsistent naming across related fields

**How to check:**
1. For each upload column alias, find the corresponding field in FAD section 4.1
2. Compare upload alias against the FAD's Prompt column
3. Flag any mismatch as MAJOR — users expect the same labels they see in the Oracle form

### 2.3 Field Order (CRITICAL — Must Match Form Visual Layout)

Compare upload column order against the **form's visual field order** from FAD section 4.2. This is the definitive order — do NOT guess or use generic grouping rules.

**Validation steps:**
1. Get the ordered field list from FAD section 4.2 (extracted from .fmb canvas coordinates: YPosition → XPosition)
2. Map each FAD field to its corresponding upload column
3. Verify the upload columns appear in the SAME order as the FAD visual field list
4. Framework columns (action_, status_, message_, modified_columns_) are always first — they are exempt from ordering

**Severity:**
- Fields significantly out of order (e.g., Receipt Method at position 17 when it's the first field in the form) = **MAJOR**
- Minor reordering within a logical group = **MINOR**

**Common issues:**
- Builder used generic grouping rules instead of actual form layout
- Fields from different form regions/tab pages mixed together
- Header fields appearing after detail fields

**Fallback** (only if FAD section 4.2 is unavailable):
- Key/identifier fields first
- Grouping: identifiers → classification → amounts → dates → methods → accounts → locations → DFFs
- But this is a last resort — always prefer the actual form visual order

### 2.4 List of Values (LOVs)

For each field with a LOV in the form:
- Verify upload column has matching LOV
- Compare LOV query: same values? same filters? (enabled, date-active, org-specific)
- Check dependent filtering matches form behavior
- Check FREE_TEXT matches the form's LOV validation (set only where the form accepts values outside the list)
- Check FILTER_BEFORE_DISPLAY_DSP for large LOVs

#### 2.4a LOV Performance (CRITICAL)

Scan every LOV_QUERY_DSP for `is null or` patterns on parent column dependencies:
```sql
-- BAD (prevents index usage — full table scan every time):
(:$column$.customer_name is null or hp.party_name=:$column$.customer_name)
-- GOOD (index-friendly — requires parent field to be entered first):
hp.party_name=:$column$.customer_name
```

**When to flag:**
- If the FAD's Data Entry Workflow (section 4.2b) shows the form **enforces** entering the parent field before the child LOV is available, then the upload LOV MUST use a required join (no `is null or`). Severity: **MAJOR**.
- If the form allows the child LOV to be opened without the parent, `is null or` is acceptable.

**How to check:**
1. Find all `is null or` patterns in LOV_QUERY_DSP across the upload XML
2. For each, check the FAD's Data Entry Workflow — does the form require the parent field first?
3. If yes → flag as MAJOR: "LOV uses `is null or` pattern but form enforces parent-first entry. This prevents index usage and causes poor performance on large tables."
4. Also check: if `FILTER_BEFORE_DISPLAY_DSP` is set on a LOV that uses `is null or`, the LOV is effectively broken — the filter popup won't help because the underlying query is already slow.

#### 2.4b LOV Filtering vs Form Behavior

Compare each LOV's dependent filtering against the form's actual data entry workflow:
- If form **requires** Field A before allowing Field B's LOV → upload LOV for B must have a **required** join on A (no `is null or`)
- If form **allows** Field B's LOV without Field A → upload LOV may use `is null or` for optional filtering

**Common issues:**
- Missing date-active or enabled_flag filter
- Missing org/book-dependent filtering
- Wrong table (base table instead of _vl for translated values)
- `fnd_lookup_values` with language filter instead of `fnd_lookup_values_vl` with `security_group_id=0`
- A validated field marked FREE_TEXT, or a free-text field without it
- Missing VALUE_TO_ID_QUERY when PL/SQL needs the ID
- `is null or` pattern on joins where form enforces parent-first entry (performance killer)
- `FILTER_BEFORE_DISPLAY_DSP` used as a workaround for slow LOV instead of fixing the query

### 2.5 Defaulting Logic

For each field with a default in the form:
- Check upload column has matching DEFAULT_VALUE
- Compare defaulting logic: same source data? same conditions?
- Check cross-field defaults have correct UPLOAD_DEPENDENCIES

**Common issues:**
- Missing date defaults (period end date, sysdate)
- Missing cross-field defaults (Category → Depreciation Method, Life)
- Hardcoded delimiters in segment concatenation (must query fnd_id_flex_structures)
- Hardcoded segment count (must query fnd_id_flex_segments)
- Circular two-way dependencies (only one direction in DEFAULT_VALUE; reverse in PL/SQL)
- DEFAULT_VALUE returns wrong column (id vs value)

### 2.6 Validation Logic

Compare validate function against form validation triggers:
- All mandatory fields checked
- All cross-field validations replicated
- Range checks, format checks, date range checks

**Common issues:**
- Returns on first error instead of concatenating all (must use nested `message()` procedure)
- Missing conditional validation (validate X only when Y='VALUE')
- Validating fields already LOV-validated (redundant)
- Missing date-in-open-period validation

### 2.7 KFF Handling

For KFF fields, verify:
- **Alias column** present (if form supports aliases)
- **Concatenated column** present
- **Individual segment columns** present (one per enabled segment)
- **PL/SQL resolution** is dynamic (queries flex structure, not hardcoded)

**Correct pattern** (from GL Journal Upload):
1. DEFAULT_VALUE: alias → concatenated → segments (one direction only)
2. PL/SQL: segments → concatenated → CCID (dynamic via fnd_id_flex_structures + fnd_id_flex_segments)
3. No hardcoded delimiters or segment counts

### 2.8 Upload Processing Logic

- Correct Oracle API used (same as form)
- Handles create and update (auto-detect, not relying on action_ column)
- Error handling: catches API errors, extracts FND message stack
- status_/message_ set correctly on success and failure
- No unused parameters (every PL/SQL param has UPLOAD_PARAMETERS_ROW)
- Parameters typed correctly: Number for IDs from LOV `id`, Char for display values

### 2.9 XML Structure Checks

- COLUMN_NAME entries match SQL select columns
- UPLOAD_COLUMN_NUMBER sequential
- DATA_TYPE correct: always varchar2 for LOV columns
- UPLOAD_DEPENDENCIES auto-generated (never manually edited)
- PARAMETER_DEPENDENCIES match `:$flex$.` references
- ANCHORS declared for all anchors used
- All filter parameters use `1=1` anchor
- Upload Mode uses standard Blitz Upload Mode LOV
- No ORDER BY in main SQL or success SQL
- VERSION_COMMENTS present when SQL was modified

### 2.10 Success SQL and Error SQL

- **Error SQL**: Prefer default (framework auto-generated)
- **Success SQL**:
  - Upload view (`xxen_{prefix}_{id}_u xu`) in FROM clause
  - Column count matches framework's first UNION ALL branch
  - Joins to actual Oracle tables to confirm record creation
  - `xu.status_code_='S'` filter present
  - No ORDER BY

## Phase 3: E2E Testing

### 3.1 Prerequisites

```sql
-- Find report_id
select xrv.report_id from xxen_reports_v xrv where xrv.report_name='Upload Name';
-- Find upload view name
select view_name from all_views where view_name like 'XXEN_%_U' order by view_name;
-- Check PL/SQL compiles clean
select uo.status from user_objects uo where uo.object_name='PACKAGE_NAME';
```

### 3.2 Template Download

```sql
declare
l_run_id number;
l_request_id number;
l_message varchar2(4000);
begin
fnd_global.apps_initialize(<user_id>,50553,101); --your own EBS user, not OPERATIONS (no ICX_SESSIONS -> ORA-06502): select fu.user_id from fnd_user fu where fu.user_name='<YOUR_USER>'
mo_global.init('S');
l_run_id:=xxen_api.create_run_id(<report_id>);
xxen_api.set_parameter_value_(p_parameter_name=>'Upload Mode', p_value=>'Create', p_report_name=>'<Upload Name>', p_run_id=>l_run_id);
-- Set other required parameters
l_message:=xxen_api.report_submit_concurrent(<report_id>, l_run_id, x_request_id=>l_request_id);
commit;
dbms_output.put_line('request_id: '||l_request_id);
end;
```

### 3.3 Test Scenarios

**For all uploads:**
- Create mode: new records with all required fields
- Create with optional fields: DFFs, notes, references
- Validation errors: missing required fields, invalid LOV values, bad dates
- Multiple rows: at least 3 records

**For uploads with update mode:**
- Update existing: download, modify a field, re-upload
- Mixed create + update: some new, some modified

**For KFF uploads:**
- Existing combination from LOV
- Via alias entry
- Via individual segments (PL/SQL resolves to CCID)
- New combination (if allowed)

**For interface-based uploads:**
- Post-procedure error detection
- Concurrent program completion

### 3.4 XLSM Manipulation

1. Extract XLSM (ZIP) to working directory
2. Map column positions from `xl/worksheets/sheet1.xml` headers
3. Add test data using shared string format (t="s" with index)
4. Key rules:
   - Column A = Action: "Create" (or "Update")
   - Column B = Status: "Valid" (display meaning, NOT code 'V')
   - Column C = Message: "Validation complete."
   - Dates = Excel serial numbers (base: 1899-12-30)
   - LOV columns = display values (framework translates to IDs)
5. Repack XLSM

### 3.5 Upload Submission

```sql
declare
l_file_id number;
l_request_id number;
l_message varchar2(4000);
begin
fnd_global.apps_initialize(<user_id>,50553,101);
mo_global.init('S');
insert into fnd_lobs (file_id, file_name, file_content_type, file_data, upload_date, program_name, language, file_format)
values (fnd_lobs_s.nextval, '<filename>.xlsm', 'application/vnd.ms-excel.sheet.macroEnabled.12',
  bfilename('TMP','<filename>.xlsm'), sysdate, 'FNDATTCH', 'US', 'binary')
returning file_id into l_file_id;
commit;
l_message:=xxen_upload.submit_upload_process(
p_report_name=>'<Upload Name>',
p_template_name=>null,
p_file_id=>l_file_id,
x_request_id=>l_request_id
);
commit;
dbms_output.put_line('request_id: '||l_request_id||' message: '||l_message);
end;
```

### 3.6 Result Verification

1. Wait for concurrent request to complete
2. Fetch output XLSM from fnd_lobs
3. Check: row count matches, Status=Success for valid rows, error messages descriptive and concatenated
4. Verify records in Oracle tables
5. Compare with form: records look same as if entered through Oracle form

### 3.7 Test Data Guidelines

- **NEVER use made-up values** — check LOVs, value sets, valid orgs
- Run "Blitz Upload Data" report for example data
- **Vision dates**: AR Dec-12, FA Jun-08, Manufacturing Dec-2012
- **XLSM dates**: numeric serial numbers (03-DEC-2012 = 41246)

## Phase 4: Report Findings

### Report Format

```markdown
# Blitz Upload Validation Report
**Upload:** <report name>
**Form:** <Oracle form name>
**Date:** <date>

## Summary
| Category | Issues | Blockers | Majors | Minors | Suggestions |
|----------|--------|----------|--------|--------|-------------|
| 1. Missing Fields | n | n | n | n | n |
| 2. Field Naming | n | n | n | n | n |
| ... | | | | | |
| **TOTAL** | n | n | n | n | n |

## BLOCKER Issues (must fix before import)
### [CAT-1-B-001] Missing required field: Depreciation Method
- **Location:** UPLOAD_COLUMNS (missing)
- **Expected:** Column for depreciation method (FAD field #12, REQUIRED)
- **Actual:** Not present in upload
- **Fix:** Add column with LOV from fa_methods

## MAJOR Issues
### [CAT-4-M-001] LOV missing org filter
- **Location:** UPLOAD_COLUMNS > SUPPLIER_NAME > LOV_QUERY_DSP
- **Expected:** Filter by operating unit
- **Actual:** Returns all suppliers across orgs
- **Fix:** Add `and aps.org_id=:$column$.org_id` to WHERE clause

## MINOR Issues
...

## SUGGESTIONS
...

## Passed Checks
- Category 2: Field naming — all aliases consistent
- Category 3: Field order — matches form tab order
- Category 7: KFF handling — dynamic resolution, no hardcoded delimiters
- ...

## E2E Test Results
| Scenario | Result | Details |
|----------|--------|---------|
| Create with all required fields | Pass | Record created in fa_additions_b |
| Missing required field | Pass | Error: "Book Type Code is required." |
| ... | | |

## Recommended Test Scenarios
1. Create a new record with all mandatory fields — verify success
2. Create with missing mandatory field — verify error message
3. Update existing record — verify only changed fields updated
4. KFF: select via alias, verify segments populate
5. KFF: enter individual segments, verify CCID resolution
6. LOV dependent filtering (e.g., category → asset type)
7. <Module-specific tests from form analysis>
```

### Issue Details

For each issue include:
- **Issue ID**: `[CAT-n-X-NNN]` format
- **Location**: XML element path or PL/SQL function
- **Expected**: What it should be (from Oracle form / FAD)
- **Actual**: What is in the upload
- **Fix**: Specific code/XML change

## Relationship to Other Commands

This skill is the comprehensive validator. Lightweight shortcuts:
- `/validate-upload-xml` — XML structure checks only (Phase 2.9)
- `/test-upload` — E2E testing only (Phase 3)

## Multi-Agent Context

| Agent | Skill | Purpose |
|-------|-------|---------|
| Planner | `blitz-report-developer` | Requirements, spec |
| Form Analyzer | `oracle-forms-analyzer` | Form field extraction |
| Builder | `upload-builder` | Build XML + PL/SQL |
| **Validator** | **`upload-validator`** (this) | Review + E2E test |
