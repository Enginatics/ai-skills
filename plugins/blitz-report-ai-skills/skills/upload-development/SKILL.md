---
name: upload-development
description: Blitz Upload XML and PL/SQL rules: upload columns, completeness checklist, processing package architecture, E2E testing. Use whenever creating or editing a Blitz Upload.
user-invocable: false
---

# Upload Development

Workflow for a new upload: `/analyze-form` (form analysis document, FAD, saved under `C:\Temp`) → `/build-upload` → `/review-upload` (independent validator pass, always, without asking). Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/lint_upload_xml.py <xml>` and `python ${CLAUDE_PLUGIN_ROOT}/scripts/lint_plsql.py <pks> <pkb>` to zero violations before declaring done; the pre-commit hook enforces both. Rule IDs below match the linters.

## Upload Completeness Checklist (MANDATORY)

**Every new or modified upload MUST pass this checklist before deployment.** Do not skip items — every skipped item is a bug the user will find. Both the build step and the review/test step must verify this list independently.

### A. XML Structure — UPLOAD_COLUMNS

- [ ] **A1. Mandatory framework columns in SQL SELECT**: `action_`, `status_`, `message_`, `modified_columns_` — all `COLUMN_TYPE_DSP=Char`, `DATA_TYPE=varchar2`, with `modified_columns_` hidden. Optional: `request_id_` (hidden). **`upload_row` is required as the last column AND must be `<HIDDEN>Y</HIDDEN>`** — it is an internal framework column (never user-facing) used to preserve uploaded row order in the result report.
- [ ] **A2. Every column has**: `COLUMN_NUMBER`, `COLUMN_NAME`, `COLUMN_TYPE_DSP`, `DATA_TYPE`
- [ ] **A3. Column numbers are sequential** and match the SQL SELECT order exactly (1-based)
- [ ] **A3C. Count columns with `dbms_sql.describe_columns`, never by counting comma-terminated lines.** The obvious heuristic - count select-list lines ending in `,` up to the first bare `from` - **truncates at the first scalar subquery in the select list**, because that subquery's own `from` sits on its own line. It can report a 233-column upload as 21. Parse the section with binds replaced by `null` and read `describe_columns`; compare main, Success SQL and `xxen_upload_columns`, which must all agree.
- [ ] **A3T. Template visible-column sequences are gapless integers.** Within every `TEMPLATES_ROW`, positive `TEMPLATE_COLUMNS_ROW/DISPLAY_SEQUENCE` values must be exactly `1..N` after sorting. When inserting a displayed column, renumber all following displayed columns; never use midpoint decimals such as `2.5`. Negative sequences represent hidden columns and are outside this visible sequence.
- [ ] **A4. Data types match SQL**: `varchar2` for text, `date` for dates, `number` for numbers
- [ ] **A5. Every select item in the main SQL is ALIASED** — an un-aliased expression makes Oracle name the derived upload column after the expression itself, e.g. a bare `to_char(null),` yields a column literally called **`TO_CHAR(NULL)`**. It is dead (no parameter can reference it) but it still occupies a column position, so it makes the Success SQL's arity *look* correct and hides the real defect. This is the classic residue of a half-done 11i neutralisation (`milk.alias alias,` → `to_char(null),`) — when a column does not apply, **remove it from the main SQL and its paired line from the Success SQL**, never leave an anonymous placeholder. **Arity agreement between the Error and Success SQL proves they agree, not that either is right.** Detect generically (offline, over all upload content):
  ```sql
  select xrt.report_name, xuc.column_number, xuc.column_name
  from xxen_upload_columns xuc, xxen_reports_tl xrt
  where xuc.report_id=xrt.report_id and xrt.language='US'
  and regexp_like(xuc.column_name,'^[A-Za-z_]+\(');
  ```
  Do NOT widen this to "name is not a plain identifier" — that returns 27, and the other 26 are legitimate quoted aliases carrying spaces (`Id or Value`, `Supplier Item Number`, `Requestor (Alias)`, …).

### B. XML Structure — UPLOAD_PARAMETERS

- [ ] **B0. The XML must carry the UPLOAD_PARAMETERS rows of a procedure that takes arguments.** Only saving the upload in the setup form derives them (`xxen_upload.parse_upload_parameters`); `import_xml` loads the element exactly as the file has it, and an empty `<UPLOAD_PARAMETERS/>` deletes every row, so the generated call has no arguments and every upload fails with `PLS-00306` in `upload_host`. Check after an import: `select count(*) from xxen_upload_parameters xup where xup.report_id=<id>`.

- [ ] **B1. Every row has**: `SOURCE` (U), `DISPLAY_SEQUENCE`, `PARAMETER_NAME`, `IN_OUT`, `PARAMETER_TYPE`
- [ ] **B2. Mandatory out parameters**: `status_` (`out`, `COLUMN_NAME=STATUS_CODE_`), `message_` (`out`, `COLUMN_NAME=MESSAGE_`)
- [ ] **B3. `action_` included** as `in` parameter with `COLUMN_NAME=ACTION_CODE_` (if procedure uses it)
- [ ] **B4. COLUMN_NAME matches** the upload column name (or framework internal name for action_/status_/message_)
- [ ] **B5. Parameter order** in DISPLAY_SEQUENCE matches the PL/SQL procedure parameter order
- [ ] **B6. DEFAULTED=Y** on every parameter declared `default null` in PL/SQL, with or without a COLUMN_NAME: it mirrors the signature, not the mapping
- [ ] **B6a. Map every parameter whose column exists.** An OUT parameter without COLUMN_NAME breaks every run: the framework writes OUT values back to `<column>_CHR`, so the generated block references `xu."_CHR"` and fails with `ORA-00904: "XU"."_CHR": invalid identifier` before any row is processed. An IN parameter left unmapped is never passed (the procedure sees its default) and its column is read-only in the generated workbook. Hidden id round trips map the IN and the OUT parameter to the same column.
- [ ] **B7. No orphan UPLOAD_PARAMETERS_ROW entries.** Every UPLOAD_PARAMETERS_ROW with a non-null COLUMN_NAME must reference a column that actually exists in UPLOAD_COLUMNS (or a framework internal like STATUS_CODE_, MESSAGE_, ACTION_CODE_). Declaring e.g. a `REQUEST_ID_` UPLOAD_PARAMETER without a matching UPLOAD_COLUMNS_ROW (or without it being a standard framework shadow column) makes the framework look for a non-existent view column like `XU.REQUEST_ID__CHR` and fail with `ORA-00904` inside `upload_host`. Don't invent parameters — if your PL/SQL doesn't need `request_id_`, don't declare it. **This is an authoring rule for hand-written XML only — do NOT tell someone to delete parameter rows by hand after removing a column through the setup form.** Saving the report there runs `xxen_upload.parse_upload_columns`, which re-derives the column list AND nulls `xxen_upload_parameters.column_name` for every column that has disappeared, so the orphan cannot occur on that path.

### C. PL/SQL Procedure

- [ ] **C1. All optional parameters have `default null`** in BOTH spec and body — spec and body defaults must match exactly
- [ ] **C2. Flag parameters accept 'Y'/null** — convert to 'Y'/'N' with `nvl(p_flag,'N')` inside the procedure
- [ ] **C3. Name-to-ID resolution** for any LOV column that passes a display name but the API needs an ID
- [ ] **C4. Spec procedure order matches body order**
- [ ] **C5. Auto-detect create/update** — query DB for existing records; do not rely solely on action_ column
- [ ] **C6. Never do direct DML on application base tables** — always use standard Oracle APIs or table handlers
- [ ] **C7. Use the highest-level public API available** — search (including web search) for published Oracle public APIs (`*_PUB`, `*_API`, `*_GRP`) or interface tables/concurrent programs before falling back to table handlers (`*_PKG`). Higher-level APIs provide more validation. If the API doesn't cover all fields (e.g. DFF attributes), use the API for core fields and supplement with targeted updates for the rest.
- [ ] **C8. Every identifier is ≤30 bytes** — procedure/function names (incl. private nested ones), and any DDL object name (table/index/constraint/sequence/view/type). Over-30 compiles fine on our **19c** dev but fails on **11.2/12.1** customers with `PLS-00114` (PL/SQL) / `ORA-00972` (DDL) — the package is then dropped / the object silently not created. Verify with `python ${CLAUDE_PLUGIN_ROOT}/scripts/lint_plsql.py` (rule **R55**) or `echo -n <name> | wc -c`. See `coding-standards` skill #55.

### D. Flag / Yes-No Columns

- [ ] **D1. SQL uses `xxen_util.yes()`** for flag columns — in main SQL AND Success SQL
- [ ] **D2. Upload column uses the standard Yes LOV**: `LOV_NAME=Yes`, `LOV_GUID=8E2FF36EDEA679D2E0530100007F1FF2`
- **D2 exception**: When a Yes/No column needs to be filtered based on another column's value (cross-field LOV dependency), the shared Yes LOV cannot be used — it has no bind support. In that case, use `COLUMN_TYPE_DSP=LOV custom` with a LOV_QUERY_DSP that returns `'Y'` and `'N'` rows but adds a WHERE clause referencing `:$column$.<parent_column>`. The framework still enforces the filtered result at upload time, as the column is not free text. Example: an ALLOW_RESERVATION column whose valid options depend on QUANTITY_TRACKED.
- [ ] **D3. LOV_QUERY_DSP**: `select 'Y' id, xxen_util.meaning('Y','YES_NO',0) value, null description from dual`
- [ ] **D4. Default for Enabled-type flags**: `xxen_util.meaning('Y','YES_NO',0)` (defaults to Yes)
- [ ] **D5. PL/SQL converts** blank to 'N': `nvl(p_enabled_flag,'N')`

### D+. Delete Column (when upload supports deletion)

- [ ] **D+1. Delete column** uses standard Yes LOV with conditional LOV_QUERY_DSP that only shows "Yes" when the deletable record exists (e.g. `where :$column$.child_range_low is not null`)
- [ ] **D+2. PL/SQL returns a specific delete message** (e.g. "Child range 420-428 deleted."), not the generic "Record processed successfully"
- [ ] **D+3. PL/SQL early-returns after delete** — do not proceed with create/update logic after a successful deletion
- [ ] **D+4. Success SQL uses outer join from xu** — `target_table(+)` so deleted records (no longer in DB) still appear in the result report. Use `nvl(target.col, xu.col)` to show the uploaded values for deleted rows.
- [ ] **D+5. Success SQL shows xu.delete_column** directly (not `to_char(null)`) so the result report indicates which rows were deletions
- [ ] **D+6. Excel validation** prevents delete without identifying the record to delete
- [ ] **D+7. Deletion only deletes the child entity**, not the parent — e.g. deleting the last child range must NOT delete the parent flex value

### E. DFF Attribute Columns

**If the upload has DFF attributes, ALL of the following are required:**

- [ ] **E1. Context column** (`attribute_category`/`value_category`) has `COLUMN_TYPE_DSP=LOV custom` with LOV querying `fnd_descr_flex_contexts_vl` for the DFF
- [ ] **E2. Every attribute column has `COLUMN_TYPE_DSP=LOV custom`** with `xxen_util.dff_attribute_lov()` LOV query referencing context and all sibling attributes via `:$column$`. **`dff_attribute_lov` returns each row as a single `value~description` string in `column_value` — the LOV MUST split it into separate `value` and `description` columns**, never `select lov.column_value value` (that returns the whole `value~description` as the value, so the dropdown shows `machine~My desc` and validation fails on the stored bare `machine`). Canonical split (copy verbatim from AR Customer Upload / any shipped DFF upload):
  ```sql
  select
  substrb(lov.column_value,1,instrb(lov.column_value,'~',1,1)-1) value,
  substrb(lov.column_value,instrb(lov.column_value,'~',1,1)+1,lengthb(lov.column_value)) description
  from
  table(xxen_util.dff_attribute_lov(p_application_id=>..., p_descriptive_flexfield_name=>'...', p_context_name=>:$column$.<context_col>, p_column_name=>'ATTRIBUTEn', p_attribute1=>:$column$.<attr1>, ...)) lov
  order by value
  ```
- [ ] **E3. No attribute column is Free Text** (no `FREE_TEXT` element)
- [ ] **E4. Every attribute column has `<COMMENTS>`** with the DFF context usage SQL
- [ ] **E5. Main SQL uses `xxen_util.display_flexfield_context/value()`** — not raw `table.attribute1`
- [ ] **E5a. DFF column aliases must be prefixed** to distinguish from other entities' DFF columns in the same upload. Use a short entity prefix (e.g. `loc_attribute1` for location DFF, `site_attribute1` for site DFF). This ensures that if additional entities with their own DFF attributes are added later, column names don't collide. The prefix should be short and derived from the entity name.
- [ ] **E6. Dynamic column translation rule** in `content/r12/dynamic_column_translation_rules.xml` with the upload's GUID, in alphabetical order, with `x.len<=4000` filter
- [ ] **E7. PL/SQL calls `xxen_fnd_upload.validate_dff_attributes()`** with `p_values_or_ids_in=>'V', p_values_or_ids_out=>'I'`
  - `'V'` mode takes the context from where the flexfield definition allows one: the user when the context field is displayed (`fnd_descriptive_flexs.context_user_override_flag='Y'`), or the reference field (`default_context_field_name`, e.g. `FND_COMMON_LOOKUPS` from `LOOKUP_TYPE`, `Extra Person Info DDF` from `INFORMATION_TYPE`), and then validates and translates that context's segments normally. With neither, standard usage allows global segments only (`WIP_DISCRETE_JOBS`, `WIP_MOVE_TRANSACTIONS`: the standard `'V'` call is right) and `fnd_flex_descval.val_desc` in `'V'` mode ignores a passed context: its segments are neither validated nor translated, so a bad value or a missing required segment passes as typed. `MTL_EAM_ASSET_ATTR_VALUES` is that setup with the context set by Oracle's form from the asset's attribute group: translate each character value with `xxen_util.dff_attribute_value_to_id` and validate in `'I'` mode (or let the Oracle API validate the ids); the record type has no number or date slots, so `N_`/`D_` columns are passed typed.
- **E8. An invalid attribute value never reaches the PL/SQL.** The framework's generated pre-validation rejects any LOV column that is not free text whose value is not in its LOV, with the message `<Column Display Name> is invalid` (the *untranslated* upload column name — dynamic column translation is not applied there), and the row is errored before the upload procedure runs. So `validate_dff_attributes` in the procedure is the **second** line of defence, catching what a plain list check cannot: dependent value sets, cross-segment rules, flexfield security and disabled/date-expired values. Both layers are needed; don't drop the server-side call because "the LOV already validates".
- **E8a. A DFF column is identified by its FULL name, never by its trailing digits.** `validate_dff_attributes` and `xxen_util.dff_attribute_lov`/`dff_attribute_value_to_id` map `application_column_name` to the caller's `attributeN` / `p_attributeN` slot. A context can enable two families at once — `ATTRIBUTE4` plus a customer-added `SEGMENT4`, `ADDRESS_LINE1` plus `CITY` — so matching only the numeric suffix feeds `ATTRIBUTE4`'s value to `SEGMENT4` and validates it against the wrong value set (`Value <x> for the flexfield segment <other segment> does not exist in the value set <other value set>`, on a segment the template does not even map), and the write-back then overwrites `ATTRIBUTE4` with the other segment's id. Match `p_column_prefix||n` exactly and pass null for every other family; `p_column_prefix` defaults to `ATTRIBUTE` and the two `PER` callers pass `ORG_INFORMATION` / `PEI_INFORMATION`. In `XXEN_UTIL` the family is `p_column_name`'s own prefix, so a dependent value set's bind on another family resolves to null.
- **E9. The DFF context column is NOT always `attribute_category`.** Read `fnd_descriptive_flexs_vl.context_column_name` for the flexfield — e.g. `GL_CODE_COMBINATIONS` (app 101, title "GL Accounts") uses **`CONTEXT`** and has only **`ATTRIBUTE1..10`**. `gl_code_combinations_kfv` exposes `context`, `attribute1..10` and `ROWID`, so the download/Success SQL can use it directly. When the DFF has fewer than 30 attributes, pass only the existing ones to `xxen_util.dff_attribute_lov` and size the record/API mapping accordingly.
- **E10. A bad DFF context value must never abort the whole upload.** `xxen_util.dff_attribute_lov` takes the context **NAME**, resolves it to the context **CODE**, and keeps the passed value when nothing matches (`l_context_code:=nvl(l_context_code,p_context_name)`), so a caller may pass a code directly. `l_context_code` is therefore declared `descriptive_flex_context_name%type` (varchar2(80)), not `descriptive_flex_context_code%type` (varchar2(30)) — an unresolvable value over 30 bytes would otherwise raise **`ORA-06502: character string buffer too small`** and abort the run instead of returning no rows.
  - **The blast radius is the entire run, not the row.** The DFF LOV calls sit in the SELECT list of the generated validation cursor, alongside the very `not exists` check that would have reported `Line Attribute Category is invalid`. The exception escapes `upload_host` before any row is judged, so the concurrent program dies with *"Program exited with status 1"*, an empty output file, and **zero** rows processed — every other row in the file is lost too. Stack signature: `XXEN_UTIL` (the `nvl` line, then the handler's `raise`) → `SYS.DBMS_SQL` → `XXEN_UPLOAD`.
  - **Trigger needs BOTH conditions** (verified on the development instance): unresolvable **and** >30 bytes. A valid long name resolves to its ≤30-byte code and is fine; an unknown short value degrades gracefully to 0 rows. It also needs the attribute column itself to be non-empty and flagged in `modified_columns_` — a pasted row flags every column, which is why paste-heavy files hit it.
- **E11. DFF round-trip facts.**
  - `validate_dff_attributes` in `'V'` mode returns non-displayed segments (`display_flag='N'`) empty: copy their stored values back before comparing.
  - DFF dates travel as text in `XXEN_REPORT_XLSX_DATE_FORMAT` (else the ICX mask), with a two-digit year unless `XXEN_REPORT_XLSX_USE_LONG_DATE_FORMAT`=Y. Validation reads them in the ICX mask, so a year outside 1950-2049, or an XLSX mask that differs from the ICX mask, corrupts or rejects even untouched dates of a row whose DFF changed.
  - The workbook's DFF-column detection (`DFF Validation_` sheet) matches `xxen_util.dff_attribute_lov` and its named literal arguments case-sensitively, within the first 1,000 characters of the LOV query.
  - Emptying one DFF cell, or the context, in either Excel client empties every filled sibling attribute cell, because each attribute LOV references all siblings.

### F. Column Defaults and Dependencies

- [ ] **F1. Parameter-sourced defaults**: columns defaulting from a parameter use `:$flex$.Parameter_Name` (with underscores for spaces in the parameter name) — NOT `:p_param_name` which passes the literal bind name unresolved
- [ ] **F2. Column-sourced defaults**: columns defaulting from another column use `:$column$.parent_column`
- [ ] **F3. Translated/display columns** default from the source column
- [ ] **F4. LOV columns with parent dependencies** use `:$column$.parent_column` in LOV_QUERY_DSP
- [ ] **F4a. A LOV or default that filters on a date column** (`nvl(x.disable_date,:$column$.transaction_date+1)>:$column$.transaction_date`) returns no rows while that cell is empty, so give the date column a `DEFAULT_VALUE` (`sysdate` or `trunc(sysdate)`, as the form does). The pre-add-in upload macro sent an empty date cell as serial 0, which the server binds as 30-DEC-1899 and which lets such a filter pass every row; the add-in sends an empty cell as null, so "the LOV worked on the old version" is that defect, not a regression.
- [ ] **F5. DEFAULT_VALUE is always the display value**, not the internal ID
- [ ] **F6. Lookup-based columns** display translated meaning via `xxen_util.meaning()`, not raw codes

### G. Upload Mode Parameter

- [ ] **G1. Uses standard Blitz Upload Mode LOV** (GUID `E811F942597A2075E0530100007FF4F2`)
- [ ] **G2. SQL_TEXT**: `:p_upload_mode like '%'||xxen_upload.action_update` — bind must be `:p_upload_mode`
- [ ] **G3. DEFAULT_VALUE** is the raw code `C` or `C,U` — not display meaning — on the parameter and in every template default. The Blitz Upload Mode list has no `U`: a `U` default is dropped and the run screen opens with Upload Mode blank. An upload that offers an Update-only mode uses the list `Blitz Upload Mode with Update only` (INV Item Upload), where `U` is valid.
- [ ] **G4. REQUIRED=Y**
- [ ] **G5. All parameters on same WHERE clause use anchor `1=1`** — no separate anchors
- **G6. An upload that only ever lists existing rows (selection-style uploads such as the Custom Reports Converter) has no Upload Mode parameter** - Create mode would download nothing. To let the user upload a downloaded set without touching every row, add a Yes parameter and emit `action_`/`status_`/`message_` from it (`xxen_upload.action_meaning(xxen_upload.action_update)`, `xxen_upload.status_meaning(xxen_upload.status_new)`, `xxen_util.description('U_EXCEL_MSG_VALIDATION_PENDING','XXEN_REPORT_TRANSLATIONS',0)`): a downloaded row with no Action is skipped on upload, the pre-flagged rows validate and upload unchanged. Linter G1 flags the missing parameter for such uploads; that is the documented exception.

### H. UPLOAD_SQLS (Error SQL, Success SQL, Order By)

- [ ] **H1. Error SQL row exists** — `<SQL_TYPE>Error SQL</SQL_TYPE>` with NO `<SQL_TEXT>` (auto-generated)
- [ ] **H2. Order By row exists** — `<SQL_TYPE>Order By</SQL_TYPE>` with column list
- [ ] **H3. Success SQL row exists** — `<SQL_TYPE>Success SQL</SQL_TYPE>` with a proper SELECT that:
  - Includes the upload view in FROM (e.g. `xxen_module_upload_NNNN_u xu`)
  - Joins `xu` to the target table(s) on business key columns
  - **Re-displays each stored data column FROM the Oracle tables, not as a bare `xu.<col>` echo (see H3b)**
  - Filters `xu.status_code_=xxen_upload.status_success`
  - Does NOT contain ORDER BY
  - Column count matches the framework's first UNION ALL branch
  - Generate a draft with `xxen_upload.default_sql(p_report_id, 'Success SQL')`, then **rewrite the SELECT list to `nvl(oracle, xu)` and add the joins** (the draft is a bare echo — see H3b)
- [ ] **H3b. Success SQL is Oracle-sourced, NOT a bare `xu` echo** — the result XLSM must show what the database **actually stored**, not what the user typed. Re-display every stored data column from the Oracle table(s) joined to `xu` by the business key, as **`nvl(<the same expression the main/download SQL uses>, xu.<col>) <col>`**. The `nvl(…, xu.col)` fallback keeps deleted/failed rows visible (their Oracle row is gone → falls back to the uploaded value). **Exception — an upload with a SEPARATE custom Error SQL sources data DIRECTLY from the DB table (bare `oracle.col`), NOT `nvl(oracle, xu)`:** failed rows go to the Error SQL (which echoes `xu`) and (absent delete support) the Success SQL's rows always have a live DB row, so the `nvl` fallback is unnecessary AND wrong — it would surface an **un-saved uploaded value** for any DB-null column (e.g. a Reason the user typed on a skipped repeated-parent row that was never saved). Match the existing entity columns (the INV Item Upload's item columns are bare `msiv.description`, `msiv.long_description`, … — no `nvl`). Reserve `nvl(oracle, xu)` for uploads relying on the auto-generated Error SQL or supporting deletes. Only the 5 framework columns (`xu.action_/status_/message_/modified_columns_/upload_row`) and genuinely non-stored input columns may stay bare `xu` echoes (list the latter in the build notes with a reason). **A pure `select xu.col, xu.col, … from <view> xu` echo is WRONG** — it can never reflect an API transformation (e.g. an upper-cased document number) or a derived/defaulted value. Join strategy: header by `upper(<document number>)`+version+org (the API upper-cases keys); line/detail by header_id+line_type+item/step (NOT an often-blank auto line number); descriptor lookups (item description) by the user's value (`msiv.concatenated_segments=xu.item`) + owner org, so they resolve independent of the line join. Use `(+)` outer joins everywhere. Linter rule **H3b** flags a Success SQL whose FROM references only the upload view.
- [ ] **H4. No ORDER BY in main SQL** — the framework wraps main + success SQL in UNION ALL
- [ ] **H4b. Display a stored project, task or expenditure organization by id from `pa_projects_all`, `pa_tasks` and `hr_all_organization_units_vl`, never from `pa_projects_expend_v`, `pa_tasks_expend_v` or `pa_organizations_expend_v`** — those views return one row per accessible operating unit that may charge the project or use the organization, so under a multi-OU responsibility a scalar lookup raises `ORA-01427` and an outer join repeats the row, while a single-OU test passes. Keep the views for LOVs listing chargeable values. Reproduce with a responsibility whose MO: Security Profile spans those operating units (the development instance: Sourcing Super User, Vision Construction 60013, profile 790).
- [ ] **H5. A column added to the main SQL is added to the custom Error SQL and Success SQL too** — result columns map POSITIONALLY, so a column appended last to the main SQL but not to the custom result SQLs renders BLANK in the result workbook with no error (the counts still match each other, so the UNION parses and ORA-01789 never fires). Append the same expression at the same position in every custom `UPLOAD_SQLS_ROW`.

### I. XML Structural Elements

- [ ] **I1. GUID** present in `REPORTS_ROW`
- [ ] **I2. REPORT_TRANSLATIONS** with `LANGUAGE=US` and `REPORT_NAME`
- [ ] **I3. CATEGORY_ASSIGNMENTS** (at least one: `Enginatics` for uploads shipped by Enginatics, your own category for customer content, never `Enginatics`)
- [ ] **I4. ANCHORS** section declares all anchors used in SQL
- [ ] **I5. No UPLOAD_DEPENDENCIES section** — `import_xml` derives both the column-level dependencies (`$column$`/`$flex$` references in upload columns) and the parameter-level dependencies (`$flex$` references in parameter LOVs) automatically; omit the section from the XML. See `report-development` skill "XML Import" section.
- [ ] **I6. TYPE=U, UPLOAD_TYPE=A**, `UPLOAD_OBJECT` points to correct PL/SQL procedure
- [ ] **I7. Assignments — `Function` level ONLY, update-enabled functions ONLY.** Uploads modify data, so they must **never** be assigned at Form / Application / Request-Group level: a Form can be granted to a read-only responsibility in query-only mode (which would let it modify data it should only view), and an Application/Request-Group assignment would expose the data-modifying upload to everyone in that group. Assign each upload **only at `Function` level**, to the function(s) that allow **updating the same object** through that form function manually — the entry/update function, **never** a read-only/`QUERY_ONLY="YES"` function (e.g. AP Invoice Upload → `AP_APXINWKB` "Invoices", NOT `AP_APXINWKB_SUMMARY_VIEW`; INV Item Upload → `INV_INVIDITM` "Master Items", NOT `INV_INVIDITM_ORG_RO`; WIP Job Upload → `WIP_WIPDJMDF_DEFINE`, NOT `WIP_WIPDJMDF_QUERY`/`_CLOSE`). `LEVEL_VALUE` = internal `function_name`; no `APPLICATION_SHORT_NAME`; empty `FORM_PARAMETERS`. To pick it: resolve the object’s data-entry form, list its `fnd_form_functions`, exclude any whose `parameters` contain `QUERY_ONLY` or whose name/user-name says View/Inquiry/Read-only/Close. The `<ASSIGNMENTS>` block is a TOP-LEVEL sibling of `<REPORTS>` (see `report-development` skill "Report Assignments" + "Upload assignments (#6)"). Reports (read-only) get the richer Application/Request-Group/Form assignments — that distinction is the whole reason Function-level exists for uploads.

**The function MUST be `fnd_form_functions.type='FORM'` (a Forms function with a `form_id`) — OAF/JSP/SUBFUNCTION functions are INVALID and produce dead/corrupt assignments.** The Blitz upload zoom only sets `xxen_report_ebs.zoom_function_id` when launching from an Oracle **Form** (via CUSTOM.pll), never from an OAF page — so a Function assignment to a JSP/OAF function (e.g. `AP_APXVDMVD` Suppliers, `CE_BANK_OVERVIEW`, `EAM_FAILURE_CODES_PAGE`) never matches at runtime. **If the object is maintained ONLY via OAF in R12** (Suppliers, Bank Accounts, EAM Failure Codes/Sets, etc.), the upload gets **NO Function assignment** (Developer/System access only). Verify the chosen function: `select type from fnd_form_functions where function_name='<X>'` must return `FORM`.

- [ ] **I8. No `<APPS_INITIALIZE_DATA><USER_NAME>ENGINATICS</USER_NAME>...</APPS_INITIALIZE_DATA>` block** in hand-written / agent-generated dev XMLs. The block tags every imported version with `last_updated_by=ENGINATICS`, which is the master-export user. Our dev imports should default to `ANONYMOUS` (omit the block entirely) or use `OPERATIONS` for explicit attribution. Shipped XMLs in `content/r12/uploads/` carry this block because they are auto-exported from the master EBS instance — that's correct for the master export, but the block must NOT be copy-pasted from those into new uploads we author. The `<ROOT>` element should open straight into `<REPORTS>`.
- [ ] **I9. `<VERSION_COMMENTS>` on every change** — when modifying an existing upload, add a fresh `<VERSION_COMMENTS>` element (in the `REPORTS_ROW`, immediately after `</SQL_TEXT>`) describing THIS change. Each `import_xml` bumps the version and writes a Forms **Version History** row; **if you omit it the new version is loaded with the PREVIOUS version's comment carried over** (not blank), mis-labeling the change in the version history. Always supply a new, accurate comment on every import. See `report-development` skill "VERSION_COMMENTS on EVERY report/upload change".
- [ ] **I10. `<DESCRIPTION>` uses line breaks, not one run-on paragraph** — break the upload's `<DESCRIPTION>` (and any multi-sentence parameter description) into short paragraphs with blank lines, flush-left. It renders verbatim in the Forms setup editor and the website library page; a single wrapped block is unreadable. Verify `regexp_count(xrt.description,chr(10)) > 0` after import. See `report-development` skill "Report / Upload DESCRIPTION (and parameter text) - use line breaks".
- [ ] **I11. Ship templates with every new upload** — a `Default` template with the form's main columns (no DFF or other flexfield columns), set as the global default (`DEFAULT_TEMPLATES_ROW` with `TEMPLATE_GUID` and no `USER_NAME`), plus one template per distinct business scenario (a mass correction of a few fields, a status change, an empty create sheet, the flexfields). Each template: a fresh GUID, the lot/record key columns, `<FREEZE_PANES>Y</FREEZE_PANES>` on the first column after the leading key columns (on the first data column when the template starts with no key, so Action, Status and Message stay visible), a short `<DESCRIPTION>` of the scenario, a Site `TEMPLATE_SHARING_ROW`, the Upload Mode default as a `TEMPLATE_PARAMETER_DEFAULTS_ROW`; a create-only template locks Upload Mode to `C` (`<LOCKED>Y</LOCKED>`) and excludes the download filters (`PARAMETER_EXCLUSION_ROW`). A column absent from a template is not downloaded and keeps its stored value on upload, so verify each template by downloading it and by one update round trip that leaves the omitted columns unchanged. Reference: INV Lot Upload.

### I+. Field Completeness and Column Ordering

- [ ] **I+1. All UI fields included** — systematically walk through every tab, window, and region in the Oracle form (or standalone edit forms) and verify each user-visible field has a corresponding upload column. Do NOT rely only on the main form — detail entities (operations, resources, components) may have separate standalone edit forms with additional fields not visible from the parent form's inquiry view.
- [ ] **I+2. Column order matches UI layout** — upload columns must follow the form's visual layout tab by tab, region by region. After building, verify the column order against the actual form by opening each tab/window and checking the field sequence matches.
- [ ] **I+3. Standalone edit forms checked** — when the parent form opens detail blocks in inquiry mode (read-only), check the standalone edit forms (e.g., WIP Operations form `WIPOPMDF` separate from Discrete Jobs form `WIPDJMDF`) for the full set of editable fields, LOV queries, defaults, and validation logic. The parent form's inquiry view may show fewer fields than the standalone edit form.
- [ ] **I+4. `$column$` references use display values** — `$column$` always passes the display value, never the LOV `id` value. When a LOV has an `id` column (e.g., `inventory_item_id`), any DEFAULT_VALUE or LOV_QUERY_DSP that needs to compare against a numeric ID column must resolve via a subquery (e.g., `(select msiv.inventory_item_id from mtl_system_items_vl msiv where msiv.concatenated_segments=:$column$.assembly)`). Direct comparison like `table.item_id=:$column$.assembly` causes `ORA-01722: invalid number`.
- [ ] **I+5. Display-only / descriptor columns must auto-default at DATA ENTRY (mandatory)** — every read-only descriptor column derived from a parent the user enters (Item Description, Assembly / Component / Routing / BOM-reference descriptions, etc.) MUST have **(a)** `READ_ONLY=Y`, **(b)** a `DEFAULT_VALUE` that derives it from its parent key via `:$column$.<parent>` — which also registers the upload dependency, so it auto-fills in the template the moment the user enters the parent, exactly like the Oracle form — and **(c)** be Oracle-sourced in the Success SQL per H3b. **Never ship a descriptor column with no default** (it shows blank at data entry, forcing the user to look the value up, and is blank in the result unless H3b sources it). Example: `ITEM_DESCRIPTION` → `DEFAULT_VALUE` = `select msiv.description from mtl_system_items_vl msiv, mtl_parameters mp where msiv.concatenated_segments=:$column$.item and msiv.organization_id=mp.organization_id and mp.organization_code=:$column$.organization_code`, parents Item + Organization Code, `READ_ONLY=Y`. Linter rule **I+5** flags a `READ_ONLY=Y` description-type column with no `DEFAULT_VALUE`.

### J. E2E Test Verification — MANDATORY TEST MATRIX

**All tests must go through the framework via `xxen_upload.submit_upload_process` — never substitute direct PL/SQL calls.** Direct PL/SQL hides bugs in framework wiring (Success SQL referencing wrong columns, hidden cells with wrong codes, view-name drift, missing UPLOAD_PARAMETERS mappings).

**The agent must run ALL of the following scenarios in a single multi-row upload before declaring `/build-upload` or `/review-upload` complete.** Skipping scenarios is the single biggest source of post-deployment defects — every scenario below corresponds to a real bug class that has slipped through testing.

| # | Scenario | Test row in XLSM | Expected `Status` | Expected `Message` contents | DB-side verification |
|---|---|---|---|---|---|
| 1 | **CREATE** | new business key, ALL required fields + 2-3 optional fields populated | `S` (Valid → Created) | "<Entity> created." (or upload-defined message) | row exists in target table with all uploaded fields populated correctly |
| 2 | **UPDATE — modify** | existing business key, change 2-3 fields | `S` | "<Entity> updated." | target row reflects new values |
| 3 | **UPDATE — no change** | existing business key, no field changes vs DB | `S` | "No change." / "No changes detected." | target row unchanged (no last_update_date bump) |
| 4 | **Validation error — invalid LOV value** | one column with a value not in the LOV | `E` | clear error mentioning the field name | NO DB change |
| 5 | **Validation error — missing required field** | required field left blank on a CREATE row | `E` | clear error stating which field is required | NO DB change |
| 6 | **Delete** (only if upload supports delete) | existing business key with Delete=Yes | `S` | "<Entity> deleted." | row removed from target table |

**Mandatory verification steps** (one per scenario):

- [ ] **J1. Download template** with restrictive parameters → request `phase_code=C, status_code=C`, output file >0 bytes
- [ ] **J2. Inspect the XLSM**: all columns present, correct headers, LOV dropdowns work, default values populated. Verify hidden Action/Status/Modified Columns at end of sheet.
- [ ] **J3. Prepare ONE test XLSM containing ALL applicable scenarios from the matrix above** (typically 5-6 rows total). Use real, valid LOV values (query the actual LOV SQL to find them — never guess).
- [ ] **J4. Upload via `xxen_upload.submit_upload_process`** → main request `phase_code=C, status_code=C`.
- [ ] **J5. Open the result XLSM and check EVERY ROW**:
  - Row order matches input
  - `Status` column matches expected value per scenario
  - `Message` column contains expected text per scenario (NOT empty for successful rows — empty Message on `S` rows usually means Success SQL hardcoded `null message_` instead of `xu.message_`, see rule H3a in linter)
  - **For any column the DB TRANSFORMS or DERIVES, the result shows the STORED value, not the echoed input**: document-number keys appear in their stored (e.g. upper-cased) form, and derived descriptor columns (Item Description, etc.) are POPULATED even when left blank in the upload. If the result echoes the raw typed input for a transformed column, the Success SQL is a bare `xu` echo (H3b violation) -- fix it before declaring done.
- [ ] **J6. Result sub-request** — `status_code=C` AND output file > 0 bytes. Empty output = Success SQL broken.
- [ ] **J7. Verify DB state per scenario**:
  - Created rows exist with correct field values
  - Updated rows reflect modifications (verify modified fields specifically, plus last_update_date bumped)
  - No-change rows: `last_update_date` should NOT have changed
  - Error rows: NO trace in target table (savepoint rollback worked)
  - Deleted rows (if applicable): not in target table
- [ ] **J8. Document the test in the build notes**: list each scenario, the test data used, the request_id, the resulting per-row Status+Message, and the DB verification result. This document is what the human reviewer reads before approving the upload.

**Common defect classes this matrix catches** (all of which have shipped in past uploads):
1. Empty `Message` on successful rows → Success SQL has hardcoded `null message_` instead of `xu.message_` (linter H3a now catches this)
2. UPDATE silently does nothing when no fields changed → missing change detection in PL/SQL
3. Validation error message is generic "Invalid value" with no field name → poor UX
4. Multi-row uploads work for first row but fail subsequent rows → savepoint scoping bug
5. Delete branch not exercised → the API call is wrong but no test catches it
6. UPDATE on inactive/expired record → API returns error but our PL/SQL doesn't surface it cleanly
7. Asset_category / department / accounting_class display values that look valid but don't pass the value-to-id translation → caught only by trying the actual upload
8. Result shows the user’s typed value instead of the stored value (lowercase document number, blank descriptor) → Success SQL is a bare `xu` echo instead of `nvl(oracle, xu)` (linter H3b; rules H3b / I+5)
9. Result sub-request errors (status CE) with `ORA-01790: expression must have same datatype` -> an Oracle-sourced Success SQL column has a type that differs from the main SQL’s first UNION branch (classic case: `to_char(grcv.num_col)` in the Success SQL while the main SQL projects the raw NUMBER). The standalone Success SQL parses fine (`select count(*) from (<success sql>)` = 0); only the UNION at result-render catches it. So **J6 (result sub-request CC + output>0 bytes) is mandatory** — a clean lint + standalone parse is NOT sufficient. Fix: make each Success column the SAME type/expression as the main SQL’s inner expression (don’t wrap a numeric in to_char just to match the varchar2 upload-view column — `nvl(grcv.num_col, xu.col)` coerces xu to NUMBER and matches the branch).


## XML standards

- Element order per row block follows the export: UPLOAD_COLUMNS_ROW `COLUMN_NUMBER → COLUMN_NAME → COLUMN_TYPE_DSP → DATA_TYPE → FREE_TEXT → FILTER_BEFORE_DISPLAY_DSP → LOV_QUERY_DSP → UPLOAD_EXCEL_VALIDATION → VALUE_TO_ID_QUERY → DEFAULT_VALUE → REQUIRED → READ_ONLY → HIDDEN → COMMENTS`; PARAMETERS_ROW `SORT_ORDER → DISPLAY_SEQUENCE → ANCHOR → SQL_TEXT → PARAMETER_TYPE_DSP → LOV_NAME → LOV_GUID → FREE_TEXT → FILTER_BEFORE_DISPLAY_DSP → LOV_QUERY_DSP → ID_OR_VALUE → MATCHING_VALUE → DEFAULT_VALUE → REQUIRED`; UPLOAD_PARAMETERS_ROW `SOURCE → DISPLAY_SEQUENCE → PARAMETER_NAME → IN_OUT → PARAMETER_TYPE → DEFAULTED → COLUMN_NAME`. No blank lines inside row blocks.
- Upload columns/parameters merge by NAME, so renumbering `COLUMN_NUMBER`/`DISPLAY_SEQUENCE` on an existing upload is safe (unlike report `SORT_ORDER`). Deploy the package before the XML; new PL/SQL params `default null`.
- Decision: a column that can change on a downloaded row, directly or through its default, is not read-only, and one that cannot is. The add-in never re-defaults a read-only column on an Update row, and `xxen_upload_columns_v` forces read-only on every column that is neither an `in` procedure parameter nor a parent of another column (`unused`), whatever `READ_ONLY` says. A display column whose default follows an editable column (a department from an operation sequence) is therefore mapped to a procedure parameter even though the procedure ignores it. Reference: `p_to_department` in WIP Move Transaction Upload.
- Never name a data column `STATUS`, `ACTION` or `MESSAGE`: its header equals the framework column's, and the result workbook and every tool that maps by header read the data column as the row status (e.g. `Active Assignment` in the Status cell). Qualify it (`ASSIGNMENT_STATUS`).
- Never alias a column with an Oracle reserved word (`v$reserved_words.reserved='Y'`, e.g. `SHARE`): the main SQL and the upload view accept it, but the Success SQL's `xu.<column>` fails with `ORA-01747: invalid user.table.column` and the result run errors.
- `DEFAULT_VALUE` is varchar2(4000) (`ORA-01706` on import): move long logic into the module's `XXEN_<x>_UPLOAD` package and keep the row-applicability guard in the default (`select x.col from (select fn(...) col from dual where <guard>) x where x.col is not null`).
- Template-column literal defaults with `;`: read-only column → sanctioned value set (first value prefilled); not read-only → the whole string is the default. `xxen_report.upload_default_query` is the one wrapper making defaults executable.
- `:$column$` in `UPLOAD_EXCEL_VALIDATION` passes display values — PL/SQL params `varchar2`. `:$flex$` in `COMMENTS` resolves at download; never `:$column$` there.
- `:$flex$.<name>` passes a report parameter's LOV id and `:$flex$.<name>.value` its display value, in upload columns (default, list, comments, value to id query, Excel validation, delete condition) exactly as in dependent parameter lists, whatever the parameter's Id or Value binds. A parameter whose LOV has no id column passes the display value either way. `xxen_report.flex_value` converts the stored run value; the bind-variable paths (workbook defaults and comments, webservices) bind the display value as `:f_v__<name>`.
- A column `COMMENTS` value beginning with `select` is **executed as SQL** at download, not shown as text: `XXEN_REPORT` builds `comments_sql` and runs it through `execute_dbms_sql`, which is how the ~89 dynamic comments in AP Supplier Upload work. A plain-English comment that happens to start with that word therefore breaks **every** download of the upload with `ORA-00923: FROM keyword not found where expected`, naming no column and pointing at the main SQL, which parses fine on its own. The test (`xxen_report.is_select`, `^\s*(select|with)`, case-insensitive) has no word boundary, so prose starting with `Selects`, `With` or `Without` is executed too. Start prose comments with any other word.

## LOVs

- Test every LOV after import (`execute immediate 'select count(*) from ('||lov||') where rownum=1'` with binds nulled).
- Never give a user-entered column a list whose query computes its value from a sibling column (`:$column$.<other>`) — supply `DEFAULT_VALUE` alone. A list returning exactly one row is written straight into the cell without showing the picker, and both Enter and double-click open the list on a list column, so the computed value silently replaces what the user typed. A reciprocal pair such as quantity and inverse quantity needs only the two defaults, which already keep each other in step. A single-row list is right only where the value is not user-entered: a Yes-only flag, or a derived display column that is not free text.
- Leave `FILTER_BEFORE_DISPLAY` unset: each instance sets it from the LOV's row count (Blitz Report Update LOV Filter Before Display). Set `<FREE_TEXT>Y</FREE_TEXT>` only on a column that must accept values outside its LOV.
- **An upload column LOV's `value` must be unique within its own filtered population.** `xxen_upload.value_to_id` resolves a cell with `select x.id, x.value from (<lov>) x where x.value=:p_value and rownum=1`, so a value shared by two rows silently hands an arbitrary id to every Number parameter mapped to that column. The report-level `UPLOAD_EXCEL_VALIDATION` is NOT a backstop for it: that text is consumed only by `XXEN_WEBSERVICES` for the add-in's Validate call, never by `XXEN_UPLOAD` while processing, so a csv/xlsx, programmatic or staged row that arrives `Valid` skips it entirely and the wrong record is updated with no error. Where the business key behind the list is not unique, qualify the value with one that is (`'500123 (Manual-Consult)'`) and qualify ONLY the rows that collide (`case when count(*) over (partition by <key>)>1 then ... end`), so pasted plain keys still pass the list check; resolve the value back through the same expression over the same population, in one function that both the list and every dependent default calls. A run-screen parameter list with an `id` column resolves each entered or picked value the same way (`x.value=:p_bind and rownum=1`, value by value for multiple values), so a value that repeats across the selected parents (an order line number over several sales orders) needs the same qualification.
- Put the `id` column in the custom LOV; the framework translates before calling PL/SQL — never re-translate display→id in the procedure (symptom: `Action "24" not found`). `VALUE_TO_ID_QUERY` only for shared-LOV columns needing an id, or a measurably cheaper query; a mismatch between LOV and translation query rejects the column's own downloaded value. Nulling binds makes a dependent list empty — not a mismatch.
- The framework finds a list's `id` column by describing the list with every `:$column$`/`:$flex$` token replaced by `null` (`xxen_api.lov_has_id_column`), so an id list must parse that way. `trunc(:$column$.<date column>)` becomes the numeric `trunc(null)` and fails the describe with `ORA-00932`: no id column is found, the display value reaches the Number parameter and every row carrying a value fails with `ORA-06502` before the procedure runs. Compare the date token untruncated (`nvl(x.start_date_active,:$column$.d)<=:$column$.d and nvl(x.end_date_active,:$column$.d)+1>:$column$.d`) and check `xxen_api.lov_has_id_column(<report id>,'<COLUMN>')='Y'` after the import.
- An id LOV translates every non-null cell of a processed row, modified or not, and a `VALUE_TO_ID_QUERY` replaces the column's server-side LOV check. So a translation query must carry the LOV's access restriction (`org_access_view` for an organization), while a filter that a downloaded value can later fall out of (an item attribute changed after download) belongs in the procedure, checked on create or when the value changes.
- An id-column LOV passes the resolved id to EVERY parameter mapped to that column (a second Char parameter does not receive the display value), and an unresolvable value errors the row with `<Column> is invalid` before the procedure runs, whether or not the column is free text. A column that must accept values not yet in the LOV (dynamic-insert KFF combinations, e.g. the FA asset key) therefore needs a VALUE-ONLY LOV (no id column, Free Text) plus PL/SQL resolution: look the value up, then create it with `fnd_flex_ext.get_ccid` and surface `fnd_flex_ext.get_message` on failure. The same applies to a column that may name a record an earlier row of the same file creates (a parent supplier, an alternate pay site): the framework translates when it opens its row cursor, before the first row is processed, so an id list rejects it with `<Column> is invalid`.
- Numeric flag columns: `mfg_lookups SYS_YES_NO` (1/2) for `in number` params; `fnd_lookups YES_NO` (Y/N) for varchar2. Cross-field Yes/No filters resolve the effective parent (`nvl(:$column$.parent, <org-level default via :$column$.organization_code>)`).
- Yes-only flags display null for No. SQL display format must equal the LOV `value` format.
- `READ_ONLY` locks the column on every downloaded row, blank cells included; only new rows can set it. Never make the key columns of a child that can be added on a downloaded row (a bank account assignment, a tax registration) read-only: restrict each key's list to its current value while the child's hidden id is set and the row is not a Create row, `(:$column$.<id> is null or :$column$.action_=xxen_upload.action_meaning(xxen_upload.action_create) or <value>=(select ... where ...=to_number(:$column$.<id>)))` as in Site Bank Assignment Level, and reject a changed key in the procedure: a list without an id column is checked in Excel only, and a free-text key has no list.
- A `LOV Oracle` naming a non-existent value set yields an empty LOV and `ORA-00903 from () x` at cell open — lookup-backed fields use `LOV custom` over `mfg_lookups`/`fnd_lookups`.
- Yes/No columns pass the stored code through the LOV id (SYS_YES_NO 1/2, PMI_YES_NO 1/0, YES_NO Y/N by storage); never map in PL/SQL. A Yes-or-blank display maps blank→No in PL/SQL, not blank→resource default.

## PL/SQL architecture

- `for c in (select ... from <static view name> xu ...) loop` with inline SQL; no dynamic SQL for reading/updating upload data (linter R45; standalone metadata-driven helpers over other tables are allowed). Static `update <view>` with `forall`.
- One package per module (`xxen_<module>_upload`). Fetch view columns into `varchar2(4000)`.
- `mo_global.set_policy_context('S',org_id)` expects an OU; INV/EAM orgs use `fnd_profile.put('MFG_ORGANIZATION_ID',...)`.
- Auto-detect with the full unique key into a `%rowtype`; cache key mirrors the lookup key exactly; hidden id columns for mutable business keys, trusted only on update; hidden original-value columns for mutable composite keys.
- `xxen_upload.new_value('p_x',p_x,l_rec.x,l_action)` for every updatable field at every entity level (pass the auto-detected `l_action`). Local wrapper only to set `g_entity_changed` or to convert sentinels (`hr_api.g_varchar2`); interface tables with mixed null semantics use `nullif(new_value(...),fnd_api.g_miss_*)` per column. `new_value` returns `fnd_api.g_miss_*` for a cell cleared on update, so an api that reads `g_miss` as keep, a table handler and direct DML need the same `nullif`, or the clear is ignored or the sentinel stored. Gate API updates on `g_entity_changed`; interface inserts always.
- Merge, validate and convert a DFF with `xxen_fnd_upload.merge_dff`, never a private copy: an untouched cell keeps the stored value per segment, a context change clears the old context's untouched segments, the change flag compares ids. Never translate the stored record with `validate_dff_attributes('I','V')`: it is all-or-nothing, so one invalid stored segment rejects segments the user did not touch.
- Value validations on update gate on `value_modified` or create (never re-validate an untouched downloaded value, especially time-relative checks); required/existence/enum/cross-field checks stay ungated. Key-immutable checks: `value_modified and nvl(new,'#')<>nvl(old,'#')`. `value_modified` is unconditionally true for a `.csv`/`.xlsx` upload (no Modified Columns row), so logic that must skip work when nothing changed - not just skip a validation - compares the resolved value against the stored one instead.
- Row-type-free detail processing by key presence (`if`, not `elsif`); hidden `row_type_sort` for order. Upload identifier column for system-generated keys; Success SQL joins `nvl(xu.name, xu.identifier)`.
- The generated block rolls back to its row savepoint only when the procedure raises; a row returned with status E keeps whatever DML the procedure did before the error. A procedure that writes and then validates further sets its own savepoint at entry and rolls back to it in its `le_validation_error` handler.
- Parent/child: process the parent once; savepoint per row; save/restore `g_last_*` on error; `le_validation_error` with only the error in `message_`; let other exceptions propagate after `write_exception`; `status_:=g_status_success` at entry; entry log + key params are the first statements. `write_log` gated on `XXEN_REPORT_DEBUG`; `write_exception` always with the stack.
- Error cascade for atomic parents: capture every row's `upload_rowid` (including inside the `l_failed` skip block and BEFORE first-row validations that can raise) so `tag_rows` marks the whole parent.
- `UPLOAD_PARAMETERS_ROW/SOURCE` is `U` for the row procedure and `P` for the post procedure, never a report parameter. A run parameter (e.g. Upload Mode) reaches the procedure through a hidden upload column: the main SQL selects the parameter's bind (`:p_upload_mode upload_mode`) for downloaded rows and the column defaults from `:$flex$.<parameter name>` for new rows (the LOV id, e.g. `U`); the Success SQL echoes `xu.<column>`. Reference: `UPLOAD_MODE` in BOM Bill of Materials Upload.
- Post-procedure is called once per distinct combination of its IN parameters over Success rows; its `status_`/`message_` overwrite every row of that group. IN and OUT parameters must not share a `COLUMN_NAME` (duplicate record field → `ORA-06550`); read a row's current message from the view instead. Include the row key among the IN params for per-row results; one-shot work guarded by a `run_id`-keyed global. Placeholder `group_id` = `fnd_api.g_miss_num` + `request_id=fnd_global.conc_request_id`, promoted per org in the post-procedure.
- Hidden id round-trip: `p_x` IN + `p_x_out` OUT on the same `COLUMN_NAME` with distinct `DISPLAY_SEQUENCE`; `p_x_out:=p_x` at entry. A single `IN OUT` is only proven for column-mapped U-parameters (CST uploads).
- Interface rowids stored in hidden sheet columns (`item_row_id`, `p_job_rowid`, `p_line_row_id`) identify a row of an EARLIER run. Any delete of that stale row must also match the row's content (`request_id<>` this run's request, or the business key): once the import has deleted the old rows, Oracle reuses their rowids for the rows this very run inserts, so an unguarded `delete ... where rowid=chartorowid(p_x_row_id)` silently removes an earlier sheet row's pending interface row. Signature: a re-uploaded result file reports Success on every row while an apparently random subset of the records stays unchanged and the import log shows no error.
- A staged run (add-in and API callers via `xxen_webservices.stage_upload_rows`, then `submit_upload` with the run id) has no upload file: `xxen_upload.g_file_id` is null. An upload that attaches its source file to the created records calls `xxen_upload.attach_source_file(function, type, category, entity, pk1..pk5)` (GL journals); the framework applies the attachments after the post procedure's out values are written back, rendering the staged rows once as uploaded (`xxen_upload.g_render_source_rows` makes the engine list the upload view with Status Valid instead of running the Success and Error SQLs; template columns and dynamic column translations apply) or attaching the uploaded file itself. Runtime options are lookup-defined setup, so a transient engine switch is a package flag, not `set_runtime_option`; package constants cannot be referenced inside generated SQL. The header row (`upload_row=1`) is consumed and deleted when processing starts; `submit_upload_process` takes the staged run id through `x_run_id in out`; csv and workbook uploads are unchanged.
- A staged run carries the parameter values of the download run only when the uploading user created that run: `stage_upload_rows` creates the run without values and the add-in submit copies them from a source run of the same user only. A procedure that reads run parameter values through `xxen_upload.property('xxen_run_id')` treats a run without the value of a required parameter as having no download run. Reference: `move_run_parameters` in `XXEN_WIP_UPLOAD`.
- An Oracle api that commits internally destroys the row savepoint: after its commit a `rollback to <row savepoint>` raises `ORA-01086`, and from an exception handler that escapes the procedure and aborts the whole run. Call such an api from a nested `pragma autonomous_transaction` procedure - its commit lands in its own transaction, the row savepoint stays valid, and the row's own work still rolls back to the entry point on a later failure. The api's work is committed independently and survives that rollback, which is the trade: it cannot be made atomic with the row while the api forces the commit. Establish the row savepoint before any branch that can `return`, or the handler rolls back to a savepoint that path never set.
- `hr_integration_utils.add_or_update_session(sysdate)` for value sets joining `fnd_sessions`.
- Multi-entity uploads: Row Type LOV; UNION download per entity with `row_type`/`row_type_sort`; Success SQL UNION per entity (view numeric/date columns are NUMBER/DATE); dispatch by `row_type`; flush in dependency order at the parent boundary.
- Dual-flow uploads sharing `P_TRX_IDX`/`'H:'` namespaces must offset one flow's index space (`g_applied_cm_trx_offset`); mirror value guards across all sibling branches; test a MIXED file.
- A boolean from `<nullable> in (...)` must `nvl` first (`null in (...)` is NULL and breaks `not flag`).
- Single-call mode (no `UPLOAD_PARAMETERS`; the procedure reads the view itself, `XXEN_ONT_UPLOAD`, `upload_distribution_set`) is the pattern for a parent saved atomically with a cross-row check: savepoint per parent, one `forall` status write-back per parent. The framework's list-of-values pre-validation has already errored the invalid rows before the procedure runs, so derive a per-parent error flag over ALL rows (`max(case when status_code_='E' ...) over (partition by <parent key>)`) before filtering to `status_valid`, or the parent is saved without them. `value_modified` names are the lowercase column names in this mode. Numeric and date view columns are computed from `<col>_chr` and are not updatable; write a generated id back through `<col>_chr`. For a generated workbook that pre-validation checks a list column only when its cell is in Modified Columns, so a dependent value left over after its parent was edited (a downloaded contact number after the contact name changed) reaches the procedure unchecked: resolve such a pair in the procedure and error the row when it does not match.
- For `.xlsm` files the framework does not check REQUIRED columns on the server (only csv/xlsx); the add-in and the upload template check them when validating before the upload, so only a row marked Valid without that validation (programmatic files, a macro-free download, staged API rows) arrives blank. A procedure whose write would fail on a blank required value checks it and reports `xxen_util.description('U_EXCEL_MSG_MISSING_DATA','XXEN_REPORT_TRANSLATIONS',0)||': '||<column names>`. Numeric cells reach the procedure rounded to `xxen_reports.upload_decimal_places`, else profile `XXEN_UPLOAD_ROUND_TO_DECIMAL_PLACES` (default 5).
- Whole-row Excel validators (`UPLOAD_EXCEL_VALIDATION` at REPORTS_ROW level) accumulate all failures joined with a space (the Message cell shows only the first line), gate each rule on its flow discriminator, use the LOV's own filter context for uniqueness checks (`count(distinct pk)`), and keep new params `default null`. Call the same function server-side as the backstop.
- Bucket/org-capability gating (BOM Standard Operations pattern): download-gate inapplicable soft columns (blank them per bucket), gate defaults on a READ-ONLY trigger column (never the editable code column — a re-fired default blanks user input), reject only a deliberate No outside the bucket; keep column `<COMMENTS>` in sync with the validator gates.


## Reuse Existing LOVs

Always prefer `PARAMETER_TYPE_DSP>LOV` + `LOV_NAME` + `LOV_GUID` over `LOV custom` for parameters.

| LOV Name | GUID | Use for |
|---|---|---|
| Blitz Upload Mode | `E811F942597A2075E0530100007FF4F2` | Upload Mode parameter |
| HR Operating Unit | `8E2FF36EDEB979D2E0530100007F1FF2` | Operating Unit parameter |
| GL Ledger | `8E2FF36EDEB879D2E0530100007F1FF2` | Ledger parameter |
| Yes | `8E2FF36EDEA679D2E0530100007F1FF2` | Single Yes (filter on/off) parameter |

For Yes/No selectors, reuse the **Oracle standard FND value set `Yes_No`** — do NOT create a custom LOV. Reference it via `COLUMN_TYPE_DSP=LOV Oracle` (or `PARAMETER_TYPE_DSP=LOV Oracle`) + `LOV_NAME=Yes_No`. No `LOV_GUID` or `LOV_QUERY_DSP` needed — the framework resolves it from the FND value set definition. Returns `Y`/`N` codes with translated meanings. Used by many existing uploads (e.g. AR_Customer_Upload).

Use `LOV custom` for upload **columns** (not parameters) only when `:$column$.` cross-column dependencies are needed.

## KFF Processing in Upload Procedures

- **Dynamic column translation rules** for KFF segment labels — use `fnd_id_flex_segments_vl.form_left_prompt`
- **Comments prefix with KFF name** (e.g. `'Cost Allocation: '`) for clarity when multiple KFFs or DFFs are in the same upload


## Procedure style

  - `p_<id>_out out number` — OUT — framework writes this back to the cell after row processing

## E2E Upload Testing (CRITICAL)

E2E means full framework round-trip — NOT just calling PL/SQL directly. **Never substitute direct PL/SQL procedure calls for a real E2E test** — they mask signature mismatches, missing defaults, and framework-generated code issues that only surface at upload runtime.

A direct call also bypasses the id translation, so the harness feeds a parameter the DISPLAY value where the real run passes the LOV id. Hand-written values then exercise branches the product never takes, and a `case <param> when 'LINE'` that matches in production looks dead in the harness — which reads as a bug in the package and invites a "fix" that breaks it. A column resolves to an id through its LOV's `id` column OR a `VALUE_TO_ID_QUERY`; the setup form's Id-or-Value flag on the upload parameter is the quickest check, and `xxen_upload_columns.value_to_id_query` the scriptable one. Read both before concluding anything about the form a parameter arrives in.

### Testing Philosophy

E2E testing simulates what the user does through the frontend:
1. Generate/download a template XLSM (with existing data for update mode)
2. Inspect the generated XLSM — verify all expected columns appear with correct headers, LOV dropdowns, and default values
3. Modify the XLSM with test data covering multiple scenarios (creates, updates, edge cases)
4. Upload the modified XLSM through the framework
5. Check row-level results — every row must succeed or fail with a clear message
6. Verify the actual database records match expectations

### Test Scenarios to Cover

For each new upload, test at minimum:
- **Create**: Insert a new record with all required fields + a few optional fields
- **Update**: Modify an existing record's editable fields (downloaded in Create+Update mode)
- **Validation errors**: Upload a row with an invalid LOV value and verify it gets a clear error
- **Edge cases**: Null optional fields, boundary values, dependent field combinations

### E2E Test Data Freshness

`xxen_upload.new_value` and its local wrappers correctly compare the new uploaded value vs the old DB value, and set `g_entity_changed_flag` only when they actually differ. **If your test data matches what's already in the DB from a prior run, you'll see "No change." legitimately** — that's idempotent behavior, not a bug. Use fresh values each run (e.g. append a run number to description: `'E2E run-2 description'`), or reset DB state between runs, to re-exercise the update API path. After the first run lands the test data, subsequent identical re-runs will all show "No change." for the same locator/customer/asset — the `g_entity_changed_flag` gate correctly skips the API call.

When debugging "why didn't my E2E test trigger the update path?" — first check the DB for the current value of the field you're trying to update. If it already matches your test data, that's why.

### Test Environment Setup

- **Use an appropriate responsibility** — submit uploads using a responsibility that matches the module (e.g. `Receivables, Vision Operations` for AR uploads, not System Administrator). The responsibility determines MOAC context and what data the user can access.
- **Validate test data against LOV queries** — before using any test data value (customer, supplier, item, etc.), run the actual LOV query from the upload XML to confirm the value is returned. Common pitfalls: inactive accounts (`status='I'`), sites not in the target operating unit, date-effective records outside the test date range. Never assume a record is valid just because it exists in the base table.
- **Check the generated result XLSM for errors** — the most reliable source of error information is the result XLSM (output of the sub-request). Some uploads have post-processing steps that store errors in PL/SQL caches which may be cleared by the time the Error SQL runs. The result XLSM captures the error at the point it was detected.
- **Custom Error SQL needs manual column updates** — when adding a column to the main SQL and Success SQL, check whether the Error SQL has custom `SQL_TEXT`. If it does, add the new column there too — otherwise the UNION ALL between the framework's auto-generated branch and the Error/Success SQL branches fails with ORA-01789 (incorrect number of result columns).
- **Upload submission ORA-06502 with OPERATIONS user** — if the upload report submission fails with `ORA-06502: PL/SQL: numeric or value error` at `DBMS_LOB` when using the OPERATIONS user (user_id=1318), fall back to the developer's own username. The likely cause is no `ICX_SESSIONS` entries exist for the OPERATIONS user because it is never used in the frontend.
- **"You are not allowed to upload data for <upload> with your current responsibility"** from `submit_upload_process` in a test session: the upload is assigned at Function level, which only matches when launched from the form. Put `fnd_profile.put('XXEN_REPORT_ACCESS','S')` in the test session (System access is exempt).

### 1. Download Template
```sql
declare
l_run_id number;
l_request_id number;
l_error varchar2(4000);
begin
fnd_global.apps_initialize(user_id=>1318, resp_id=>20420, resp_appl_id=>1);
mo_global.init('M');
mo_global.set_policy_context('M', null);
l_run_id:=xxen_api.create_run_id_('Upload Name');
xxen_api.set_parameter_value_(p_parameter_name=>'Upload Mode', p_value=>'Create, Update', p_run_id=>l_run_id);
-- Add required parameters here
-- Note: use report_submit_concurrent with p_run_id to pass parameters
l_error:=xxen_api.report_submit_concurrent(xxen_report.report_id('Upload Name'), l_run_id, l_request_id);
dbms_output.put_line(nvl(l_error,'Request ID: '||l_request_id));
end;
```
Output file: `$APPLCSF/out/`

### 2. Inspect the Generated XLSM (CRITICAL — Do Not Skip)

After downloading, **always inspect the generated file before proceeding**:
- **Column headers**: Verify all expected columns appear with correct names — missing columns indicate SQL/UPLOAD_COLUMNS mismatches
- **Default values**: Check that columns with `DEFAULT_VALUE` show the expected defaults in new rows
- **LOV dropdowns**: Verify LOV columns have working dropdown lists with correct values
- **Existing data**: In Create+Update mode, verify downloaded rows have correct data populated
- **Hidden columns**: Verify framework columns (Modified Columns, Upload Row) are hidden

If the XLSM is not accessible for direct inspection, at minimum check the output file size (empty template ~50KB, template with data should be larger) and the request log for parsing errors.

### 3. Prepare Valid Test Data
- Run "Blitz Upload Data" report for the upload to see data from previous successful uploads
- Check required columns in the XML (`<REQUIRED>Y</REQUIRED>`)
- Check LOV validations — query the LOV SQL directly to find valid values
- Start from a previously successful upload XLSM and modify only the columns being tested
- **Status column (B) must be "Valid"** (the display meaning, NOT the code 'V'). Message column (C) shows "Validation complete." after validation.

### 4. Modify the XLSM
```bash
# Extract
unzip -q template.xlsm -d work_dir
# Modify xl/sharedStrings.xml and xl/worksheets/sheet1.xml
# Repack
zip -q -r output.xlsm .
```
- Hidden columns (Operating Unit, Source, Default GL Date) are at the END of the Excel
- **The position of the `MODIFIED_COLUMNS_` cell varies by upload** — it's wherever the framework placed the hidden column when generating the template (e.g. BK in INV Stock Locator Upload but elsewhere in other uploads). Look up the header position dynamically rather than hard-coding a column letter.
- **When building the XLSM programmatically (not via VBA), populate framework hidden cells with DISPLAY VALUES, not internal codes.** The XLSM parser translates display→code before the framework pivot filter runs. Passing codes (`C`, `V`) bypasses the translation and produces the silent symptom "N cells retrieved, 0 rows created".
  - Action (col A): `Create` / `Update` / `Delete` (NOT `C` / `U` / `D`)
  - Status (col B): `Valid` (NOT `V`)
  - Message (col C): `Validation complete.`
  - Modified Columns: comma-delimited **Excel column position numbers** wrapped in leading+trailing commas, e.g. `,1,5,6,8,` (A=1, B=2, ..., Z=26, AA=27, ..., DD=108). NOT `xxen_upload_columns.column_number`. Matches what VBA writes via `track_changed_columns(p_row, p_column As Long)`.
  - To debug "0 rows created": byte-compare your XLSM against a recently-successful upload XLSM from the server's fnd_lobs to spot the discrepancy.
- **Read-only columns are NOT auto-flagged by VBA.** When a user edits Excel, VBA's `track_changed_columns` doesn't add a read-only column's position to `modified_columns_` — in fact users can't edit read-only cells in Excel at all. For programmatic E2E test design:
  - DO manually set Action='Update', Status='Valid', Message='Validation complete.' on any update row you want the framework to process — otherwise it's skipped.
  - DON'T add a read-only column's Excel position to `modified_columns_` — mimic the natural VBA behavior. Functionally the framework would tolerate it, but it's incorrect convention.
  - Exception: when a test deliberately tries to force a read-only-column reject scenario (e.g. simulating "what if this column were editable?"), include the position so the `value_modified`-guarded PL/SQL check fires.

### 4a. Building Test XLSMs Programmatically (Python)

Manual XLSM editing in Excel is slow and error-prone. The reliable approach is to **start from the framework-generated template** and modify cells programmatically.

**Required mechanics — every one of these has bitten us with silent corruption or "0 rows created":**

- **Always start from a freshly-downloaded template** for the upload — preserves VBA, formatting, and the hidden column structure. Never build the .xlsm from scratch.
- **Use string-based XML manipulation, not ElementTree.** Python's `xml.etree.ElementTree.write()` strips the worksheet's default namespace, producing a file that Excel "repairs" with `Removed Records: Cell information from /xl/worksheets/sheet1.xml part`. Modify `xl/worksheets/sheet1.xml` and `xl/sharedStrings.xml` as text.
- **Cells must be sorted by Excel column letter within each row.** Excel rejects out-of-order cell references with the same "Cell information" corruption. Sort A, B, C, ..., Z, AA, AB, ... before writing.
- **`modified_columns_` cell uses Excel column position numbers**, not the upload's `xxen_upload_columns.column_number`. The framework's pivot SQL filters by `xxen_util.colnum(excel_letter)` (A=1, B=2, ..., Z=26, AA=27, ..., DD=108). Format: comma-delimited with leading and trailing commas, e.g. `,1,5,8,108,`. Compute via `col_letters_to_num(excel_col_letter)` directly from the cell's column ref — no per-upload mapping table needed.

This applies regardless of whether the upload is read via VBA at data-entry time or processed server-side — the .xlsm must be valid for both paths.

### 5. Upload via Framework
```sql
declare
l_file_id number;
l_blob blob;
l_bfile bfile;
l_amount number;
l_request_id number;
l_return_status varchar2(4000);
begin
select fnd_lobs_s.nextval into l_file_id from dual;
insert into fnd_lobs (file_id, file_name, file_content_type, upload_date, program_name, language, oracle_charset, file_data, file_format)
values (l_file_id, 'test.xlsm', 'application/vnd.ms-excel.sheet.macroEnabled.12', sysdate, 'XXEN_UPLOAD', 'US', 'UTF8', empty_blob(), 'binary');
select fl.file_data into l_blob from fnd_lobs fl where fl.file_id=l_file_id for update;
l_bfile:=bfilename('TMP','test.xlsm');
dbms_lob.fileopen(l_bfile, dbms_lob.file_readonly);
l_amount:=dbms_lob.getlength(l_bfile);
dbms_lob.loadfromfile(l_blob, l_bfile, l_amount);
dbms_lob.fileclose(l_bfile);
l_return_status:=xxen_upload.submit_upload_process(
p_report_name=>'Upload Name',
p_template_name=>null,
p_file_id=>l_file_id,
x_request_id=>l_request_id
);
commit;
dbms_output.put_line(nvl(l_return_status,'Request ID: '||l_request_id));
end;
```

### 5a. Generated-block errors

A parse failure of the generated `upload_host` block (`PLS-00103`, `PLS-00364 loop var C`, `ORA-00942/00904`) comes from the XML config (wrong `SOURCE`, a LOV over a non-existent table/column, a mis-typed parameter). Set `XXEN_REPORT_DEBUG=Y` at SITE and re-run: the request log prints the full generated block with line numbers.

- `0 cells retrieved from '<file>.xlsm'` followed by the Data table insert failing (`ORA-01747`; `ORA-03050 ")" is a reserved word` on 23ai) means `xxen_report.unzipped_files` found no zip end-of-central-directory record in the `fnd_lobs` blob and returned no files: the stored content is not a complete xlsm (truncated or non-zip upload). Verify on the log's `File id`: `dbms_lob.getlength` against the file size on the user's PC, `rawtohex(dbms_lob.substr(fl.file_data,4,1))`='504B0304' and the last 22 bytes starting '504B0506'. A valid file with no sheet named `Upload` gives the same zero-cell log but finishes in seconds.

### 6. Check Results
```sql
-- Main upload request status
select decode(fcr.phase_code,'C','Completed','R','Running','P','Pending',fcr.phase_code) phase,
decode(fcr.status_code,'C','Normal','E','Error','G','Warning',fcr.status_code) status,
fcr.completion_text
from fnd_concurrent_requests fcr where fcr.request_id=&id;

-- Upload data results (row-level status)
select xud.column2 status, xud.column3 message
from xxen_upload_data xud where xud.run_id=&run_id;
```

**CRITICAL — Check all three levels of success:**
1. **Main request** (`status_code='C'`): Normal completion of the upload process
2. **Result report sub-request**: The main request log contains "Request id: NNNNN" after "Report completed". Check that sub-request's `status_code='C'` too — `status_code='E'` means the **Success SQL failed** (e.g. ORA-01799 if outer join used with subquery). The upload data rows may show 'S' but the output XLSM will not be generated.
3. **Row-level status in xxen_upload_data**: `column2='S'` and expected message

A "Normal completion" on the main request does NOT guarantee end-to-end success. Always verify the result report sub-request and the actual database records.

### 7. Verify Database Records

After a successful upload, **always query the database** to confirm the records were actually created/updated correctly:
```sql
-- Example: verify a created record exists with expected values
select ... from target_table where key_column=uploaded_value;
```
Do not rely solely on the upload status — verify the data landed in the target table with the correct values.


## Programmatic test XLSMs

Start from a fresh template; edit `xl/worksheets/sheet1.xml` and `xl/sharedStrings.xml` as text (ElementTree strips the namespace); sort cells by column letter; hidden cells carry DISPLAY values (`Create`/`Valid`/`Validation complete.`); `MODIFIED_COLUMNS_` = `,<excel positions>,`; do not flag read-only columns. Upload: insert into `fnd_lobs` (`bfilename('TMP',...)`) then `xxen_upload.submit_upload_process`. Check main request, result sub-request (log line "Request id: N"), row status, DB rows.


## Offline data entry (upload template)

The `XXEN_UPLOAD` concurrent program's directory mode (`DB/Apps Tier File Directory`, `File Name Starts With`, `Reprocess Error Files`) applies any upload from a folder; pass `''` for skipped middle args to `fnd_request.submit_request`. Plain `.xlsx`/`.csv` lack `Status`/`Modified Columns` and misfire `value_modified` — keep `.xlsm` produced by the template. A `.csv`/`.xlsx` maps columns by position in the template's column order (hidden columns last) and ignores the header text, and gets no upload column defaults (those are applied by the Excel template), so a hidden required column such as GL Daily Rates `Mode Flag` must be filled in the file. The csv delimiter is taken from the header row (semicolon when it holds more semicolons than commas); a csv number or date that does not convert with the run's Date/Numeric Format errors its row as `<Column> is invalid`, while text in an `.xlsx` number cell still aborts the run in the upload view (`ORA-06502` at `FND_NUMBER`). An `Error: FNDGFU failed` line in the log names a file the concurrent manager could not load (the file is then renamed `BLITZ_ERROR_`).
