---
name: upload-builder
description: Build Blitz Upload XML definitions and PL/SQL processing packages for Oracle EBS. Use when creating a new upload or significantly modifying an existing one.
metadata:
  title: Upload Builder
  category: Upload Development
---

# Upload Builder Skill

Builds the XML definition and PL/SQL processing package for a Blitz Upload based on requirements or a Form Analysis Document from the oracle-forms-analyzer.

## When to Use

- Creating a new Blitz Upload from scratch
- Significantly modifying an existing upload (adding columns, changing processing logic)
- Converting a Form Analysis Document into a working upload

## Arguments

$ARGUMENTS should contain the upload name, target module, and optionally a reference to the Form Analysis Document.

## Inputs

1. **Form Analysis Document** (from oracle-forms-analyzer) — field inventory, LOVs, defaults, API details
2. **Existing similar uploads** — find in `content/r12/uploads/` for reference patterns
3. **`coding-standards` skill** — always loaded, must be followed strictly

## Phase 1: Design

### 1.1 Determine Processing Approach

| Approach | When to Use | UPLOAD_TYPE |
|----------|------------|-------------|
| **API** | Oracle provides a public API (e.g., `hr_employee_api`, `ar_invoice_api_pub`) | A |
| **Interface Table** | Oracle uses interface + concurrent processor (e.g., FA Mass Additions, PO PDOI) | A |
| **Direct DML** | No API available, or API doesn't work on Vision (rare, last resort) | A |

### 1.2 Design Row Structure

Determine how entities map to Excel rows. For single-entity uploads (one table, one row per record), this is straightforward — skip to 1.3. For multi-entity uploads (parent/child, multiple detail types under the same parent), design the row layout before the column list.

**Questions to answer:**

1. **How many entity types does the upload cover?** List them (e.g., Job Header, Operation, Resource, Component). Identify the hierarchy — which are parents, which are children, and which are siblings.

2. **Do sibling entities share rows or get their own rows?**
   - **Shared rows** (flat/cartesian) — appropriate when entities are 1:1 or naturally paired (e.g., invoice header + one line per row). Also works when detail entity types can be freely combined on a single row and the PL/SQL procedure determines which entities to process based on which columns are populated (e.g., QP Price List Upload, QP Modifier Upload).
   - **Separate rows with Row Type** — appropriate when multiple independent child entity types exist under the same parent and combining them on one row would create artificial duplication or ambiguity (e.g., N resources x M components = NxM rows instead of N+M). Each row represents one detail entity.

3. **How does parent data relate to detail rows?**
   - Parent columns come first in the column layout, before the Row Type and detail columns
   - Parent data repeats across all detail rows — users mass-paste data, so every row carries the full parent context
   - There is no separate "Header" row type — the parent is processed on the first row encountered and skipped on subsequent rows, regardless of detail content
   - The PL/SQL procedure detects a new parent by comparing the current parent key against the previous one

4. **What is the expected row ordering?**
   - Rows are grouped by parent key, with detail rows underneath
   - Within details, the ordering should follow the natural hierarchy (e.g., operations before their child resources/components)
   - The Order By SQL must enforce this grouping (e.g., `upload_row, job_name, row_type_sort, operation_seq_num`)

5. **Row Type column — exposed or hidden?** This is upload-specific:
   - **Hidden** (download-only) — when the row type is purely for structuring downloaded data. During upload, users can populate columns from different entity types on the same row and the PL/SQL procedure determines which entities to process based on which columns are populated. Detail LOVs are not restricted by row type. Examples: QP Price List Upload, QP Modifier Upload.
   - **Visible** (user-selected) — when entity types are independent siblings and mixing them on one row would cause duplication or ambiguity. The row type drives which columns are relevant, which LOVs are active, and which validation rules apply. Detail LOVs filter by context columns or by the row type value itself.

**Column layout pattern:**

| Position | Columns | Notes |
|----------|---------|-------|
| First | Framework columns (action_, status_, message_, modified_columns_) | Always first |
| Next | Parent/header columns (e.g., Job Name, Assembly, Class, Status, Dates) | Repeat on every row |
| Next | Row Type | Hidden or visible depending on upload design |
| Next | Detail columns shared across types (e.g., Operation Seq) | Linking column for child rows |
| Last | Detail columns specific to each type (e.g., Resource, Component, Qty/Assy) | Blank when not applicable |

**Main SQL structure for downloads** — UNION ALL branches, one per detail entity type:
```sql
select
null action_,
null status_,
null message_,
null modified_columns_,
x.*
from
(
-- Branch 1: entity type A
select parent_cols, 'Type A' row_type, shared_detail_cols, type_a_cols,
  null type_b_col1, null type_b_col2  -- null columns for other types
from parent_table, type_a_table where ...
union all
-- Branch 2: entity type B
select parent_cols, 'Type B' row_type, shared_detail_cols,
  null type_a_col1, null type_a_col2,  -- null columns for other types
  type_b_cols
from parent_table, type_b_table where ...
) x
```

### 1.2b Design Error and Success SQL

Before designing the column list, determine how errors and successes will be detected and reported. These decisions directly affect which columns are needed (hidden rowid columns, request_id_, etc.).

**Questions to answer:**

#### Error SQL Design

1. **Can the auto-generated Error SQL be used?**
   - **Yes** — when the upload procedure directly creates/updates records via API calls and sets `status_`/`message_` per row. The default `nvl(xu.status_code_,xxen_upload.status_error)<>xxen_upload.status_success` is sufficient.
   - **No** — when the upload inserts into interface tables and a separate concurrent program does the actual processing. The procedure sets all rows to success after inserting into the interface, but the concurrent program may reject some rows. A custom Error SQL is needed to detect these post-processing failures.

2. **For interface-based uploads, how do we detect errors?**
   - Check the interface table's `process_status` column (e.g., `process_status=3` for error in WIP/PO interfaces), NOT the existence of error message rows. The process status is the authoritative error indicator.
   - Link upload rows to interface rows via hidden rowid columns (see below).
   - The WHERE clause checks: `nvl(xu.status_code_,xxen_upload.status_error)<>xxen_upload.status_success` OR `exists (interface row with error status)`.

3. **How do we retrieve error messages?**
   - Join from the interface rowid to the interface error table in the SELECT (not the WHERE).
   - Use `coalesce` to try detail-level errors first, then header-level errors, then the framework `xu.message_`, then a catchall message (e.g., `'No error message returned. Check the <Program> concurrent request.'`).
   - The status column should show `xxen_upload.status_meaning(xxen_upload.status_error)` — not `xu.status_` which reflects the pre-processing status (success after interface insert, before concurrent program ran).

4. **Interface rowid columns** — add hidden `in out varchar2` columns for each interface table the upload inserts into. These serve dual purpose:
   - **Error detection**: join upload rows to interface records to check `process_status`
   - **Cleanup on re-upload**: when a rowid is populated from a previous failed upload, delete the stale interface error and interface record before re-processing

   Implementation:
   - Use `RETURNING rowidtochar(rowid) INTO p_row_id` on each interface table insert
   - Position these columns in the outer query after `modified_columns_` (standard position for in/out framework columns)
   - In the PL/SQL procedure, at the start: if any rowid parameter is populated, delete the corresponding error rows first, then the interface record, then clear the parameter before re-inserting

5. **Always list individual columns in Error SQL** — never use `xu.*`. The column count must match the main SQL exactly.

6. **Always use the actual upload view name** (e.g., `xxen_module_upload_NNNN_u`) — never the `&upload_view` lexical.

#### Success SQL Design

1. **What defines success?**
   - For API-based uploads: `xu.status_code_=xxen_upload.status_success` is sufficient.
   - For interface-based uploads: success means `xu.status_code_=xxen_upload.status_success` AND the interface records were processed without error. Add `not exists` checks against interface tables with error `process_status`.

2. **How to link upload rows to the created/updated entities?**
   - **Preferred**: hidden ID columns returned as `in out` parameters from the API (e.g., `p_wip_entity_id in out`). The Success SQL joins on these IDs.
   - **Interface-based fallback**: when the API inserts into interface tables and a concurrent program creates the actual entities, the IDs aren't available at upload time. Join on logical business keys instead (e.g., `xu.job_name=we.wip_entity_name`). Use outer joins for detail entities (operations, resources, components) since not every upload row has all detail types.

3. **Post procedure `request_id_` pattern** — for interface-based uploads:
   - Add `request_id_ out number` to the post procedure signature
   - After submitting the concurrent program, set `request_id_:=l_request_id`
   - Add a corresponding `UPLOAD_PARAMETERS_ROW` with `SOURCE=P`, `IN_OUT=out`, `COLUMN_NAME=REQUEST_ID_`
   - The Success SQL can then use `xu.request_id_` to correlate with the concurrent request

4. **Success message showing actions taken** — use the post procedure's `request_id_` to determine what happened:
   - Query `fnd_concurrent_requests.actual_start_date` for the processing request
   - Compare each entity's `creation_date` and `last_update_date` against this timestamp
   - `creation_date >= actual_start_date` → "created"
   - `last_update_date >= actual_start_date` → "updated"
   - Concatenate across entities to build a descriptive message (e.g., "Job created, Operation 10 created, Resource 10 created")

#### Impact on Column List

These decisions feed directly into the column list (Phase 1.3):
- **Hidden rowid columns** — one per interface table inserted into, positioned after `modified_columns_` in the outer query
- **`request_id_`** — already a standard framework column, but ensure it's included when the post procedure returns a concurrent request ID
- **Hidden ID columns** — for linking Success SQL to actual entities (e.g., `wip_entity_id`)
- **Business key columns** — must be sufficient to join back to the entity tables in the Success SQL

### 1.3 Design Column List

From the Form Analysis Document, map form fields to upload columns:

1. **Framework columns** (always first, always these 4):
   ```sql
   null action_,
   null status_,
   null message_,
   null modified_columns_,
   ```

2. **Data columns in form visual order (CRITICAL)**:
   - **Use the FAD section 4.2 (Visual Field Order)** as the definitive column sequence
   - This is extracted from .fmb canvas coordinates (YPosition → XPosition) and reflects the actual form layout
   - Do NOT use generic grouping rules — follow the form's exact visual order
   - **Walk through every tab and window** in the form systematically — main tab, scheduling tab, bill tab, routing tab, and any detail windows (operations, components, resources). Missing a tab means missing fields.
   - **Check standalone edit forms** — detail entities (operations, resources, components) may have separate standalone edit forms with fields not visible from the parent form's inquiry view. For example, the WIP Discrete Jobs form opens operations in inquiry mode, but the standalone Operations form (`WIPOPMDF`) has the full editable field set. Check both forms for the complete field inventory.
   - **Include description columns** for key LOV columns (e.g., Assembly Description, Component Description) — these are display-only columns that default from the parent LOV column via `$column$` reference
   - Exception: DFF fields (Attribute Category + Attribute1..15) always go last in each entity group, regardless of form position
   - Exception: KFF groups stay together (alias → concatenated → segments) even if form shows them differently

   **Fallback** (only if FAD section 4.2 is unavailable):
   - Key/identifier fields first (Book, Asset Number, etc.)
   - Classification fields (Category, Type, etc.)
   - Amount fields (Cost, Salvage Value, etc.)
   - Date fields
   - Method/rule fields
   - KFF groups: alias → concatenated → individual segments
   - Assignment fields (Employee, Location)
   - DFF fields last

3. **Each column needs**:
   - SQL alias (becomes Excel header) — **must match the form Prompt attribute** from FAD section 4.1, NOT the internal DB column name
   - Source expression in main SQL (table.column or null for new)
   - DATA_TYPE: varchar2 for LOV columns (always), number/date for non-LOV
   - LOV definition (if applicable)
   - DEFAULT_VALUE (if applicable)
   - REQUIRED flag
   - **CRITICAL: `$column$` references always pass display values** — when a column has a LOV with `id`/`value`, the `$column$` reference in DEFAULT_VALUE or other LOV queries passes the display `value`, NOT the `id`. Any DEFAULT_VALUE or LOV_QUERY_DSP that needs to compare against a numeric ID column (e.g., `inventory_item_id`, `project_id`) must resolve via a subquery: `(select msiv.inventory_item_id from mtl_system_items_vl msiv where msiv.concatenated_segments=:$column$.assembly)`. Direct comparison like `msiv.inventory_item_id=:$column$.assembly` causes `ORA-01722: invalid number`.

4. **DFF columns — always include by default**:
   - Check the FAD for DFF registrations on the main entity table(s) (identified by the `DF` item or `FND_FLEX.EVENT` triggers in the form)
   - For each registered DFF, include: context column (`<prefix>_attribute_category`) + attribute columns (`<prefix>_attribute1..15`)
   - Use entity prefix per rule E5a (e.g., `job_attribute1` for WIP jobs, `loc_attribute1` for locations)
   - Position DFF columns last in the header column group, before the Row Type and detail columns
   - SQL: use `xxen_util.display_flexfield_context()` and `xxen_util.display_flexfield_value()` — never raw `table.attribute1`
   - LOVs: context column queries `fnd_descr_flex_contexts_vl`; attribute columns use `xxen_util.dff_attribute_lov()` with `$column$` references to context and all siblings
   - COMMENTS: each attribute column has a SQL query showing the DFF context usage per attribute
   - All attribute columns have `VALIDATE_FROM_LIST_DSP=Y`
   - Add a dynamic column translation rule in `content/r12/dynamic_column_translation_rules.xml` with the upload's GUID, using the entity prefix pattern (`'PREFIX_'||x.application_column_name`)
   - PL/SQL: call `xxen_fnd_upload.validate_dff_attributes()` with `p_values_or_ids_in=>'V', p_values_or_ids_out=>'I'`
   - See `upload-development` skill section E for the full checklist

### 1.4 Design PL/SQL Package

- **Package name**: `XXEN_<MODULE>_UPLOAD` (e.g., `XXEN_FA_UPLOAD`, `XXEN_AP_PAYMENT_UPLOAD`)
- **Validate function**: `validate_<entity>` — returns varchar2 (null=valid, non-null=error)
- **Processing procedure**: `create_update_<entity>` — status_ and message_ out params
- **Post procedure** (if interface-based): `post_<entity>` — submits concurrent processor

## Phase 2: Build the PL/SQL Package

### 2.1 Validation Function Pattern

```sql
function validate_asset(
p_field1 in varchar2,
p_field2 in number
) return varchar2 is
l_message varchar2(4000);

procedure message(p_message in varchar2) is
begin
  l_message:=l_message||case when l_message is not null then chr(10) end||p_message;
end message;

begin
  -- Required field checks
  if p_field1 is null then
    message('Field1 is required.');
  end if;

  -- Cross-field validations
  if p_field2 is not null and p_field2<=0 then
    message('Field2 must be positive.');
  end if;

  -- Foreign key existence checks (use not exists pattern)
  for c in (
  select null from dual where not exists (
  select null from some_table st where st.code=p_field1
  )
  ) loop
    message('Invalid Field1: '||p_field1||'.');
  end loop;

  return l_message;
end validate_asset;
```

**Key rules:**
- Use nested `message()` procedure to concatenate ALL errors (never return on first error)
- Don't validate fields already covered by LOV with VALIDATE_FROM_LIST=Y
- Use `not exists` pattern instead of `l_found` flag variables
- Follow `coding-standards` skill (no spaces around operators, lowercase, etc.)

### 2.2 Logging Procedures (Standard Pattern)

Every upload package must include these two procedures:

```sql
procedure write_exception(p_text in varchar2) is
begin
  xxen_report.write_log(replace(p_text,chr(0),' ')||chr(10)||dbms_utility.format_error_stack||dbms_utility.format_error_backtrace);
end write_exception;

procedure write_log(p_text in varchar2) is
begin
  if fnd_profile.value('XXEN_REPORT_DEBUG')='Y' then
    xxen_report.write_log(p_text);
  end if;
end write_log;
```

- `write_log` — normal debug logging, gated by profile. Call directly as a procedure: `write_log('message');`
- `write_exception` — always logs, includes full error stack. Use in unexpected exception handlers.
- Never use a function returning varchar2 (`l_dummy:=write_log(...)`) — always use procedure calls.

### 2.3 Processing Procedure Pattern

```sql
procedure create_update_entity(
p_action in varchar2 default null,
status_ out varchar2,
message_ out varchar2,
p_key_id in number default null,
p_key_field in varchar2,
p_data_field in varchar2 default null
) is
l_rec target_table%rowtype;
l_action varchar2(10);
begin
  write_log('create_update_entity entry');
  write_log('p_key_field: '||p_key_field);

  status_:=xxen_upload.g_status_success;

  -- Auto-detect with full old value fetch using %rowtype
  for c in (
  select t.*
  from target_table t
  where p_action=xxen_upload.g_action_update and p_key_id is not null and t.id=p_key_id
  or not(p_action=xxen_upload.g_action_update and p_key_id is not null) and t.key=p_key_field
  ) loop
    l_rec:=c;
  end loop;

  l_action:=case when l_rec.id is null then xxen_upload.g_action_create else xxen_upload.g_action_update end;

  -- Apply new_value for all updatable fields
  l_rec.data_field:=xxen_upload.new_value('p_data_field',p_data_field,l_rec.data_field,l_action);

  if l_action=xxen_upload.g_action_create then
    -- Create: call API or insert into interface
    null;
  else
    -- Update: call API or insert into interface
    null;
  end if;

  message_:='Record processed.';
exception
when le_validation_error then
  status_:=xxen_upload.g_status_error;
when others then
  write_exception('create_update_entity error for '||p_key_field);
  raise;
end create_update_entity;
```

**Key rules:**
- `status_` and `message_` are mandatory OUT params
- Auto-detect using ALL unique key columns, fetch old values into `%rowtype` record
- Apply `xxen_upload.new_value` to every updatable field at every entity level — MANDATORY for updates
- For API-based uploads: use local `new_value` wrappers with `g_entity_changed` to gate update calls
- For interface-table uploads: call `xxen_upload.new_value` directly — no wrappers needed when sentinels match
- `le_validation_error` for business errors, `when others` with `write_exception` + `raise` for unexpected errors
- No unused parameters — every param must have UPLOAD_PARAMETERS_ROW in XML

### 2.3 KFF Segment Resolution (Dynamic Pattern)

When the upload accepts individual segment values and needs to resolve to a CCID:

```sql
-- Dynamic concatenation (no hardcoded delimiters or segment counts)
l_concat_segs:=null;
for c in (
select fifst.concatenated_segment_delimiter d, fifsg.application_column_name
from fnd_id_flex_structures fifst,
fnd_id_flex_segments fifsg
where
fifst.application_id=:app_id and
fifst.id_flex_code=:flex_code and
fifst.id_flex_num=:flex_num and
fifsg.application_id=fifst.application_id and
fifsg.id_flex_code=fifst.id_flex_code and
fifsg.id_flex_num=fifst.id_flex_num and
fifsg.enabled_flag='Y'
order by
fifsg.segment_num
) loop
  l_concat_segs:=l_concat_segs||case when l_concat_segs is not null then c.d end||
    case c.application_column_name
    when 'SEGMENT1' then p_segment1
    when 'SEGMENT2' then p_segment2
    -- ... up to max segments for this flex
    end;
end loop;

-- Look up existing
for c in (select kfv.code_combination_id from kfv_table kfv where kfv.concatenated_segments=l_concat_segs) loop
  l_ccid:=c.code_combination_id;
end loop;

-- Create new (if allowed)
if l_ccid is null then
  l_ccid:=fnd_flex_ext.get_ccid(:app_short, :flex_code, :flex_num, to_char(sysdate,'YYYY/MM/DD HH24:MI:SS'), l_concat_segs);
  if l_ccid=0 then
    status_:=xxen_upload.status_error;
    message_:='Invalid combination: '||l_concat_segs||'. '||fnd_flex_ext.get_message;
    return;
  end if;
end if;
```

### 2.4 Post Procedure (Interface-Based Uploads)

```sql
procedure post_entity(
p_org_code in varchar2,
status_ out varchar2,
message_ out varchar2
) is
l_request_id number;
begin
  l_request_id:=fnd_request.submit_request(:app, :program, null, null, false, :arg1, :arg2);
  commit;
  if l_request_id=0 then
    status_:=xxen_upload.status_error;
    message_:=fnd_message.get;
    return;
  end if;
  -- Wait for completion, check interface error table,
  -- update xxen_upload_data for failed rows
end post_entity;
```

## Phase 3: Build the XML Definition

### 3.1 XML Skeleton

```xml
<ROOT>
 <APPS_INITIALIZE_DATA>
  <USER_NAME>ENGINATICS</USER_NAME>
  <RESPONSIBILITY_KEY>SYSTEM_ADMINISTRATOR</RESPONSIBILITY_KEY>
  <APPLICATION_SHORT_NAME>SYSADMIN</APPLICATION_SHORT_NAME>
 </APPS_INITIALIZE_DATA>
<CATEGORIES>
 <CATEGORIES_ROW>
  <BASE_CATEGORY>Module Name</BASE_CATEGORY>
  <CATEGORY_TRANSLATIONS>
   <CATEGORY_TRANSLATIONS_ROW>
    <LANGUAGE>US</LANGUAGE>
    <CATEGORY>Module Name</CATEGORY>
   </CATEGORY_TRANSLATIONS_ROW>
  </CATEGORY_TRANSLATIONS>
 </CATEGORIES_ROW>
</CATEGORIES>
<REPORTS>
 <REPORTS_ROW>
  <GUID>generate-unique-guid</GUID>
  <SQL_TEXT>...</SQL_TEXT>
  <VERSION_COMMENTS>Initial version</VERSION_COMMENTS>
  <ENABLED>Y</ENABLED>
  <TYPE>U</TYPE>
  <UPLOAD_TYPE>A</UPLOAD_TYPE>
  <UPLOAD_OBJECT>xxen_module_upload.create_update_entity</UPLOAD_OBJECT>
  <UPLOAD_EXCEL_VALIDATION>xxen_module_upload.validate_entity(:$column$.field1, :$column$.field2)</UPLOAD_EXCEL_VALIDATION>
  ...
 </REPORTS_ROW>
</REPORTS>
</ROOT>
```

### 3.2 Main SQL Rules

- No ORDER BY (use UPLOAD_SQLS Order By instead)
- Traditional Oracle join syntax (not ANSI)
- Follow `coding-standards` skill strictly
- Lowercase everything, no spaces around operators

### 3.3 Parameters

**Always include Upload Mode** — standard Blitz Upload Mode LOV:
```xml
<PARAMETERS_ROW>
 <SORT_ORDER>1</SORT_ORDER>
 <DISPLAY_SEQUENCE>10</DISPLAY_SEQUENCE>
 <ANCHOR>1=1</ANCHOR>
 <SQL_TEXT>:p_upload_mode like '%' || xxen_upload.action_update</SQL_TEXT>
 <PARAMETER_TYPE_DSP>LOV</PARAMETER_TYPE_DSP>
 <LOV_NAME>Blitz Upload Mode</LOV_NAME>
 <LOV_GUID>E811F942597A2075E0530100007FF4F2</LOV_GUID>
 <VALIDATE_FROM_LIST_DSP>Y</VALIDATE_FROM_LIST_DSP>
 <LOV_QUERY_DSP>select xxen_upload.action_create id, xxen_upload.action_meaning(xxen_upload.action_create) value, null description from dual union all
select xxen_upload.action_create || ',' || xxen_upload.action_update id, xxen_upload.action_meaning(xxen_upload.action_create)||', '||xxen_upload.action_meaning(xxen_upload.action_update) value, null description from dual</LOV_QUERY_DSP>
 <REQUIRED>Y</REQUIRED>
</PARAMETERS_ROW>
```

**Rules:**
- All filter parameters use `1=1` anchor (never create 2=2, 3=3 unless genuinely different SQL positions)
- Reuse existing LOVs: HR Operating Unit (`8E2FF36EDEB979D2E0530100007F1FF2`), GL Ledger (`8E2FF36EDEB879D2E0530100007F1FF2`)
- Use `LOV custom` only for upload columns, not parameters

### 3.3b LOV Performance and Data Entry Workflow (CRITICAL)

When building LOV queries for upload columns, match the Oracle form's data entry workflow from FAD section 4.2b:

**Rule: If the form enforces entering Field A before Field B's LOV is available, the upload LOV for B must use a REQUIRED join on A — no `is null or` pattern.**

```sql
-- BAD (prevents index usage — full table scan):
select rcta.trx_number value from ra_customer_trx_all rcta, hz_cust_accounts hca
where rcta.bill_to_customer_id=hca.cust_account_id and
(:$column$.customer_number is null or hca.account_number=:$column$.customer_number)

-- GOOD (index-friendly — parent field required, matching form behavior):
select rcta.trx_number value from ra_customer_trx_all rcta, hz_cust_accounts hca
where rcta.bill_to_customer_id=hca.cust_account_id and
hca.account_number=:$column$.customer_number
```

**Why this matters:**
- `is null or column=:bind` forces the optimizer to plan for both null and non-null cases → typically a full table scan
- When the form requires the parent field first, the `is null` branch can never happen in practice
- On large tables (invoices, receipts, journal lines), this causes seconds-long LOV load times

**When `is null or` IS acceptable:**
- The form allows opening the child LOV without the parent field populated
- The child table is small (< 10K rows) and a full scan is acceptable

### 3.4 Column DATA_TYPE Rules

- `varchar2` for ALL LOV columns (even when LOV has numeric `id`)
- `number` for numeric non-LOV columns
- `date` for date columns

### 3.5 KFF Column Groups

For each KFF, add columns in this order:
1. **Alias** — LOV custom, VALIDATE_FROM_LIST=Y, queries `fnd_shorthand_flex_aliases`
2. **Concatenated** — LOV custom, queries `_kfv` view, DEFAULT_VALUE from alias
3. **Segment1..N** — LOV custom, queries `fnd_flex_values_vl`, DEFAULT_VALUE from concatenated

DEFAULT_VALUE flows ONE direction only: alias → concatenated → segments.
PL/SQL handles the reverse: segments → concatenated → CCID.

### 3.6 Upload Parameters (PL/SQL Mapping)

```xml
<UPLOAD_PARAMETERS_ROW>
 <DISPLAY_SEQUENCE>10</DISPLAY_SEQUENCE>
 <PARAMETER_NAME>p_key_field</PARAMETER_NAME>
 <DATA_TYPE_DSP>Char</DATA_TYPE_DSP>
 <SOURCE>U</SOURCE>
 <COLUMN_NAME>KEY_FIELD</COLUMN_NAME>
</UPLOAD_PARAMETERS_ROW>
```

- SOURCE=U for upload column values, SOURCE=P for parameter values
- DATA_TYPE_DSP: Number for ID params from LOV `id`, Char for strings
- DISPLAY_SEQUENCE must be unique

### 3.7 Success SQL

```sql
select
'Success' status_,
t.key_field,
...
from
xxen_module_upload_NNN_u xu,
target_table t
where
xu.status_code_='S' and
xu.key_field=t.key_field
```

**Rules:**
- Upload view `xu` MUST be in FROM clause (not auto-injected)
- Column count must match main SQL exactly
- No ORDER BY
- After first import, find actual view name: `select view_name from all_views where view_name like 'XXEN_%_U'`

### 3.8 Error SQL

**Always use framework default** — include the row with NO `<SQL_TEXT>` element:

```xml
<UPLOAD_SQLS_ROW>
 <SQL_TYPE>Error SQL</SQL_TYPE>
</UPLOAD_SQLS_ROW>
```

When `sql_text` is NULL, the framework auto-generates the Error SQL via `xxen_upload.default_sql()` and the "Default" checkbox is checked in the UI. This means the Error SQL auto-updates whenever main SQL columns change — no manual maintenance needed.

**Rules:**
- Never write explicit Error SQL text when the default pattern (`nvl(xu.status_code_,xxen_upload.status_error)<>xxen_upload.status_success`) is sufficient
- Only use custom Error SQL (with explicit `<SQL_TEXT>`) if non-standard error detection logic is required
- Never directly update DB tables to set flags — always go through XML import

### 3.9 UPLOAD_SQLS Order By

```xml
<UPLOAD_SQLS>
 <UPLOAD_SQLS_ROW>
  <SQL_TYPE>Error SQL</SQL_TYPE>
 </UPLOAD_SQLS_ROW>
 <UPLOAD_SQLS_ROW>
  <SQL_TYPE>Order By</SQL_TYPE>
  <SQL_TEXT>key_field, description</SQL_TEXT>
 </UPLOAD_SQLS_ROW>
</UPLOAD_SQLS>
```

## Phase 4: Deploy

Deploy to the development instance (see `blitz-environment.md`), the package before the XML.

### 4.1 Deploy PL/SQL

Follow `/deploy-plsql`: compile `sql/extensions/XXEN_MODULE_UPLOAD.pks` then `.pkb` on the development instance (`sqlplus apps/$APPS_PWD`, `set define off`), and confirm the package is VALID with no `show errors` output.

### 4.2 Import XML

Lint the XML with `${CLAUDE_PLUGIN_ROOT}/scripts/lint_upload_xml.py`, import it with the installed `$XXEN_TOP/bin/import_xml $APPS_PWD <file>` on the apps tier of the development instance (or `xxen_api.import_xml(<clob>)`), then check every LOV parses — the deploy procedure in `blitz-environment.md`. After it runs, verify the Function assignment (see Access Assignments).

### 4.3 Dependencies

**Do NOT put an UPLOAD_DEPENDENCIES section in the XML.** `import_xml` derives the column and parameter dependencies from the `:$column$`/`:$flex$` references automatically.

### 4.4 Keep the authored XML

The file in `content/r12/uploads/` remains the deliverable. Never overwrite it with an `xxen_api.export_report` export, which omits `<ASSIGNMENTS>` and other languages (`report-development` skill).

## Quality Checklist

Before delivering, verify:

- [ ] **Column order matches FAD section 4.2 visual field order** (not generic grouping)
- [ ] **Column aliases match FAD form Prompts** (not internal DB column names)
- [ ] **No `is null or` in LOVs where form enforces parent-first entry** (FAD section 4.2b)
- [ ] Every FAD mandatory field is in UPLOAD_COLUMNS or handled in PL/SQL
- [ ] Every FAD LOV has a corresponding LOV_QUERY_DSP on the upload column
- [ ] Every cross-field rule from the FAD has an UPLOAD_DEPENDENCY
- [ ] Every PL/SQL parameter has a matching UPLOAD_PARAMETERS_ROW in XML
- [ ] LOV columns use DATA_TYPE `varchar2` (even when LOV has numeric `id`)
- [ ] Validate function uses nested `message()` — never returns on first error
- [ ] Processing procedure sets `status_`/`message_` in every code path
- [ ] KFF resolution is dynamic (queries flex structure, no hardcoded delimiters/segment counts)
- [ ] No ORDER BY in main SQL or success SQL (use UPLOAD_SQLS Order By)
- [ ] Error SQL present as default (no SQL_TEXT — framework auto-generates)
- [ ] Upload Mode uses standard Blitz Upload Mode LOV (not custom)
- [ ] All filter parameters share `1=1` anchor (no unnecessary 2=2, 3=3)
- [ ] XML special chars escaped: `&amp;` `&apos;` `&lt;` `&gt;`
- [ ] GUID is a new UUID (not copied from another upload)
- [ ] Report name follows convention: `<MODULE> <Entity> Upload` (e.g. `AR Customer Upload`), file `content/r12/uploads/<Name_With_Underscores>.xml`
- [ ] VERSION_COMMENTS present after SQL_TEXT
- [ ] Templates per `upload-development` skill I11: global `Default` (main columns, no flexfields) plus one per business scenario
- [ ] No UPLOAD_DEPENDENCIES section in the XML (derived automatically on import)
- [ ] PL/SQL follows `coding-standards` skill (lowercase, no spaces around operators, traditional joins)

## Handoff

The Builder produces:
- **PL/SQL package** (spec + body) in `sql/extensions/`
- **Upload XML** in `content/r12/uploads/`
- Both deployed to the development instance and ready for testing

These are consumed by **upload-validator** for review and E2E testing.


## Access Assignments (MANDATORY — Function level only)

Every upload MUST ship with a top-level `<ASSIGNMENTS>` block (sibling of `<REPORTS>`, not nested) so responsibilities can run it. Uploads modify data, so the rule is strict (see `upload-development` skill **I7** and `report-development` skill "Upload assignments (#6)"):

- **`Function` level ONLY** — never Form, Application, or Request Group (a Form can be granted query-only, and App/Request-Group would expose the data-modifying upload too broadly).
- **Update-enabled functions ONLY** — resolve the object's data-entry form, list its `fnd_form_functions`, and assign the entry/update function(s); EXCLUDE any whose `parameters` contain `QUERY_ONLY` or whose name/user-name says View/Inquiry/Read-only/Close. Examples: AP Invoice Upload→`AP_APXINWKB`, INV Item Upload→`INV_INVIDITM`, FND User Upload→`FND_FNDSCAUS`, WIP Job Upload→`WIP_WIPDJMDF_DEFINE`.
- **Function must be `type='FORM'`** — OAF/JSP functions are invalid (the Blitz zoom only fires from an Oracle Form). If the object is OAF-only in R12 (Suppliers, Bank Accounts, EAM Failure Codes/Sets), the upload gets **no** Function assignment. Verify: `select type from fnd_form_functions where function_name='<X>'` must return `FORM`.
- `LEVEL_VALUE` = internal `function_name`; no `APPLICATION_SHORT_NAME`; empty `FORM_PARAMETERS`.
- Verify after import: `select assignment_level,level_value from xxen_report_assignments_v where report_name='<Upload>'` shows the Function row(s); and the function is update-capable (not QUERY_ONLY).
