---
name: add-dff-to-upload
description: Add descriptive flexfield (DFF) handling to a Blitz Upload - context and attribute columns with context-dependent lists of values, segment prompts as column headers, Success SQL, and the PL/SQL that merges untouched segments, validates the DFF and converts display values to ids before the API call. Use when asked to add, validate or fix DFF / attribute columns of an upload, e.g. "add validation for the attribute5 flexfield segment of my upload".
metadata:
  title: Add DFF Handling to an Upload
  category: Upload Development
---

# Add DFF Handling to a Blitz Upload

Adds one descriptive flexfield to an existing upload the standard Blitz Report way. Users see and enter display values in Excel; the download converts stored values to display values, and the upload procedure validates the whole DFF with the Oracle flexfield engine and converts it back to stored ids. A generator script writes every artefact from the flexfield's facts; the steps below say where each one goes. The `upload-development` rules, section E, are the checklist behind it.

## Inputs

- The upload: its XML (exported from the Blitz Report setup form, Tools > Export) and the PL/SQL package of its upload procedure.
- The flexfield, by name or by the table that carries it, and a short column prefix for the entity (`subinv`, `loc`, `line`).
- A development instance to deploy and test on, as described in `blitz-environment.md`.

## Step 0 - Check the Blitz Report build

Run the last query of `references/flexfield_facts.sql`. It must return `P_COLUMN_PREFIX`. Otherwise the build predates 18 September 2026, lacks `xxen_upload.parameter_exists` or `p_column_prefix`, and validates DFFs with contexts incorrectly. Stop and ask for an upgrade.

## Step 1 - Collect the flexfield facts

Run queries 1 to 3 of `references/flexfield_facts.sql`:

| Result | Generator argument / use |
|---|---|
| `application_id`, `application_short_name`, `descriptive_flexfield_name` | `--app-id`, `--app-short-name`, `--flexfield`. Several DFFs can sit on one table: take the one the Oracle form uses. |
| `context_column_name` | `--context-column` (not always `ATTRIBUTE_CATEGORY`; `GL_CODE_COMBINATIONS` uses `CONTEXT`) |
| attribute column family and count (Query 3) | `--family` (default `ATTRIBUTE`; HR uses `PEI_INFORMATION`, `ORG_INFORMATION`, ...), `--count` = number of attribute columns of the table, whether used or not. Query 3 returns one row per schema with a table of that name: take the product schema's. |
| `max_length` (Query 3) | over 150: the procedure's record holds 150 bytes per attribute, values above that raise `ORA-06502`; tell the user |
| `display_flag` `N` (Query 2) | `--hidden` with those columns |
| `context_user_override_flag` `N` with a `default_context_field_name` | the context follows a reference field: see Special cases |

## Step 2 - Generate the artefacts

```
python ${CLAUDE_PLUGIN_ROOT}/skills/add-dff-to-upload/scripts/gen_dff.py \
  --app-id 401 --app-short-name INV --flexfield MTL_SECONDARY_INVENTORIES \
  --prefix subinv --count 15 --alias msi \
  --guid <upload GUID> --rule-name "XX Subinventory DFF Attributes" \
  --first-column <COLUMN_NUMBER of UPLOAD_ROW> --first-sequence <last upload parameter's DISPLAY_SEQUENCE + 1> \
  --template-keys ORGANIZATION_CODE,SUBINVENTORY \
  --package <upload package> --procedure <upload procedure> \
  --key-params p_organization_code,p_subinventory \
  --cursor-from "mtl_parameters mp,mtl_secondary_inventories msi" \
  --cursor-where "mp.organization_code=p_organization_code and mp.organization_id=msi.organization_id and msi.secondary_inventory_name=p_subinventory" \
  --out <folder>
```

- `--first-column`: the DFF columns go before `UPLOAD_ROW`, or before the column you name instead. `--first-sequence`: the procedure's new parameters follow its existing ones.
- `--template-keys`: the upload column names that identify the record, as in the upload XML.
- `--alias` must be the alias of the flexfield's own table (Query 1 `application_table_name`) in the main SQL, not of a view: its rowid resolves dependent value sets.
- `--param-prefix` / `--context-param` name the procedure parameters (default `p_attribute`, `p_attribute_category`); give each DFF its own when an upload has several.
- `--dry-run` writes a test build that reports the values the API would receive instead of calling it. Run the tests with it first.
- Aliases must stay within 30 bytes for databases before 12.2; the script warns.

Output: `main_sql_columns.sql`, `success_sql_columns.sql`, `upload_columns.xml`, `upload_parameters.xml`, `translation_rule.xml`, `template.xml`, `<package>.pks`, `<package>.pkb`.

## Step 3 - Upload definition

1. **Main SQL**: insert `main_sql_columns.sql` after the entity's columns, before `upload_row`.
2. **Upload columns**: insert the `upload_columns.xml` rows and renumber the `COLUMN_NUMBER` of the columns after them, which must follow the select-list order.
   - Context column: `LOV custom` over `fnd_descr_flex_contexts_vl`, returning context names. Keep it when the DFF has only global segments: its list stays empty until a context is defined, as in the shipped uploads.
   - Attribute columns: `LOV custom` over `xxen_util.dff_attribute_lov`, with all siblings passed as `:$column$`, the `value~description` split, not free text, and a `select` comment listing the segment per context in the shipped format `(Context) Attribute1: (Global) <prompt>, (<context>) <prompt>`.
   - Keep the generated LOV text as it is (named arguments, lower case, literals at the start): the framework reads those literals from the first 1,000 characters to give Excel per-context date and number checks.
3. **Upload parameters**: insert the `upload_parameters.xml` rows in the procedure's parameter order and renumber `DISPLAY_SEQUENCE` after them.
4. **Success SQL**: add `success_sql_columns.sql` at the same position as in the main SQL. The tables sit in an inline view `x` that selects `rowid row_id`, because pre-12c databases allow an outer-joined table to reference only one other table:
   ```sql
   from
   <data view> xu,
   (
   select
   mp.organization_code,
   msi.rowid row_id,
   msi.*
   from
   mtl_parameters mp,
   mtl_secondary_inventories msi
   where
   mp.organization_id=msi.organization_id
   ) x
   where
   xu.organization_code=x.organization_code(+) and
   xu.subinventory=x.secondary_inventory_name(+) and
   xu.status_code_=xxen_upload.status_success
   ```
   The data view name is shown on the setup form's Upload Results tab.
5. **Templates**:
   - Keep the DFF columns out of the default template. An upload without one shows every column: add a default template with the existing columns.
   - Insert the `template.xml` row into the upload XML's `<TEMPLATES>`. It holds the key columns and all DFF columns, as the shipped uploads do, Upload Mode Update, and Site sharing.
6. **Translation rule**: import `translation_rule.xml` after the upload, as its own file. A rule whose upload does not exist yet is skipped, and rules import before reports in a combined file. It renames the attribute headers to the segment prompts. Developer access can also maintain it under Tools > Dynamic Column Translations.

Import the XML through the setup form (Tools > Import) or `bin/import_xml`. Editing an upload needs System access.

## Step 4 - Upload procedure

Add the generated parameters (`default null`) to the procedure in spec and body. Then merge the generated declarations, helper functions and DFF block into it:

- **Helper functions:**
  - `modified(p)`: `parameter_exists` plus `value_modified`. A hand-built csv/xlsx counts every parameter as modified, also those its template omits. Test the entity's other columns with it too: `xxen_upload.new_value` alone clears a column the csv template omits.
  - `dff_modified`: true on any DFF change.
  - `segment_enabled`: whether an enabled segment uses a column.
  - `merged`: builds the value of each cell:
    - a changed cell takes the uploaded value;
    - an untouched cell takes the stored value in display form;
    - a column without an enabled segment keeps its stored value unconverted;
    - after a context change, the old context's untouched segments are cleared, as in the Oracle form.
- **Read the stored row** with its `rowid` into `l_stored`, and initialise `l_dff:=l_stored`. The generated code treats a key without a stored row as a create; in an update-only upload, keep the procedure's own not-found error ahead of the DFF block.
- **Merge and validate** only on create or when `dff_modified`: merge, then `validate_dff_attributes` from `'V'` to `'I'`. On error, set `message_` and raise.
- **Detect a change** by comparing the converted ids with `l_stored`, and report "No change." when nothing changed.
- **Rename consistently:** every parameter name literal (`modified('p_attribute5')`, the first argument of each `merged` call, the context parameter) must match the declared parameters, or edits are dropped silently.
- **API call:** replace `xx_my_api.create_or_update` with the entity's API and check its return status. A cleared cell is null in the record. How to pass it:

| API family | Null means | Pass |
|---|---|---|
| Table handlers, APIs writing every column | clear | the record as is |
| HR (`hr_*_api`) | clear; omitted = `hr_api.g_varchar2` = keep | the record as is, never `hr_api.g_varchar2` for a cleared cell |
| TCA (`hz_*_v2pub`) | keep | on update `fnd_api.g_miss_char` for a null attribute, on create null |
| Interface tables | per import program | its clear marker (WIP Mass Load `fnd_api.g_miss_*`, item revisions `'!'`) |

Never convert the stored record with `validate_dff_attributes('I','V')`: the conversion is all or nothing, so one invalid stored segment blocks every row.

## Special cases

- **Reference-field context** (override `N`, `default_context_field_name` set): give the context column a `DEFAULT_VALUE` that derives the context name from the reference column, as the FND Lookup Upload does for `FND_COMMON_LOOKUPS`.
- **Context set by the Oracle form itself**, with neither override nor reference field (`MTL_EAM_ASSET_ATTR_VALUES`): in `'V'` mode only global segments are validated, and context segments come back as typed. Convert each segment with `xxen_util.dff_attribute_value_to_id` and validate in `'I'` mode. That function converts only segments with a list; convert dates and numbers with `fnd_date`/`fnd_number` yourself.
- **Non-displayed segments** (`--hidden`): `'V'` mode returns them empty, so the generated code copies their stored values back.
- **Value sets joining `fnd_sessions`** (common in HR): call `hr_integration_utils.add_or_update_session(<effective date>)` at the start of the procedure.
- **Date segments**:
  - DFF dates travel as text in the Blitz Report XLSX Date Format profile, or else the ICX date mask, but validation reads them in the ICX mask. Keep the two equal.
  - Set Blitz Report XLSX Use Long Date Format = Yes when a date can fall outside 1950-2049; otherwise even untouched dates change century.
- **Several DFFs in one upload**: one prefix, parameter set and translation rule per DFF. Generate each with its own `--prefix`, `--param-prefix` and `--context-param`. Merge the helper functions under per-DFF names, or parametrise them with flexfield, record, rowid and context flag.
- **One DFF on several records of a row** (the contact points of a party, a site and a contact all carry the same flexfield): the translated headings must start with the record they belong to (`Site Email Email Invoice`), otherwise identical prompts give duplicate column headings. Edit the generated rule's translation to put the prefix first and truncate only the prompt, so prefix and prompt fit `xxen_report.max_column_length` (30 bytes before database 12.2).

## Step 5 - Deploy and test

1. Compile the package with `--dry-run` code, import the upload XML, then the rule. Check that the attribute headers show the prompts.
2. Download with the Descriptive Flexfield template, edit the rows, upload, and check the result workbook. Excel accepts only list values and valid dates, so write the error rows into the file outside Excel (cells as shared strings, Modified Columns listing the changed column positions). A csv maps by position: Action, Status, Message, then the template's columns in template order.

| Scenario | Expected |
|---|---|
| Change one segment | Success; the other segments keep their stored values |
| Clear a segment | Success; segment cleared (Excel also empties the row's other filled attribute cells: re-enter those that should stay) |
| No DFF change | "No change." |
| Value not in the list / invalid context | `<Column> is invalid` from the list check, naming the column (`Subinv Attribute5`), not the segment prompt; the procedure is not called |
| Invalid date in a free-text date segment | message from `validate_dff_attributes` |
| Context change without a required segment of the new context | "The following required field does not have a value: ..." |
| Context change with values / context emptied | Success; old context segments cleared |
| Upload with the Default template, and a csv without DFF columns uploaded with it | "No change." |

3. Replace the dry-run block with the API call, then repeat the tests and check the table.

## Troubleshooting

| Symptom | Cause |
|---|---|
| List shows `value~description`, downloaded values rejected | LOV returns `column_value` without the split |
| Headers still generic | rule not enabled or not assigned to the upload, prefix differs from the column names, or no segment uses the column |
| Edits report "No change." | a parameter name literal does not match the declared parameter |
| Untouched segments rejected | the stored value is no longer valid (disabled, expired, newly required): correct it in the same row |
| Stored DFF cleared by an upload | parameters passed instead of the merged record, or a csv/xlsx uploaded without a template |
| Every download fails with `ORA-00923` | a plain-text column comment starts with the word "select" |
| Works on 19c, fails on 11.2/12.1 | identifier over 30 bytes, or an outer join to two tables in the Success SQL (`ORA-01417`) |

## Reference

- `xxen_util.display_flexfield_context(app_id, flexfield, context_code)`: returns the context name.
- `xxen_util.display_flexfield_value(app_id, flexfield, context_code, column_name, rowid, value)`: returns the display value.
- `xxen_util.dff_attribute_lov(p_application_id, p_descriptive_flexfield_name, p_context_name, p_column_name, p_lov_delimter default '~', p_attribute1..30)`: pipelined, one `value~description` row per value. Call it with named notation.
- `xxen_fnd_upload.validate_dff_attributes(p_appl_sn, p_flexfield_name, p_values_or_ids_in, p_values_or_ids_out, p_column_prefix, px_attribute_rec, x_error_message)`: on error the record is unchanged and the message is set.
- `xxen_upload.value_modified(p)` / `xxen_upload.parameter_exists(p)`: parameter names in lower case, as declared.
- Shipped uploads to compare: INV Manufacturer Upload (one DFF), AR Customer Upload (five DFFs, one rule with a `case` on the flexfield name), FND Lookup Upload (reference-field context).
