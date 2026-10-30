---
name: migrate-webadi
description: Convert a customer's Oracle WebADI integrators, gathered by the Blitz Report Custom Reports Converter (Include WebADI Integrators), into Blitz Uploads - inventory the gathered zip, generate a form analysis document per integrator from its definition, decide between a template of a shipped upload and a new upload, build it with the upload-builder skill keeping the integrator's commit behaviour, and prove it against the customer's own spreadsheet on an instance of the customer's release.
metadata:
  title: Migrate WebADI Integrators
  category: Migration
---

## When to use

A customer ran the **Blitz Report Custom Reports Converter** with Include WebADI Integrators and selected integrators of program type WebADI Integrator. The gathered zip (`CONV_<ABBR>_<request id>_<timestamp>/`) holds one folder per integrator. This skill turns each one into a Blitz Upload, a template of a shipped upload, a report, or a documented "nothing to convert".

Read `webadi-migration` skill first: it holds the decisions (category, commit behaviour), the gathered file layout and the WebADI metadata facts this skill relies on. The build itself follows `upload-development` skill and the `upload-builder` skill; this skill supplies their input and the WebADI-specific steps.

## Arguments

- The customer abbreviation (category `Custom Uploads <ABBR>`).
- The gathered zip or its unzipped folder.
- Optionally one integrator code to process only that one.

## Instance

Build and test on an instance of the customer's EBS release where you can compile packages and import content. The integrator's API must exist there: several Oracle integrators exist only on 12.2 (Quoting - Create Quote, Field Service Debrief), and a customer integrator needs its gathered objects compiled first. Check before building: `select ao.object_name, ao.status from all_objects ao where ao.object_name='<API PACKAGE>' and ao.object_type='PACKAGE BODY'`.

## Workflow

### 1. Inventory

1. Unzip into a working folder; read `manifest.txt` (abbreviation, custom object prefix) and `gather_summary.txt`.
2. Run `python ${CLAUDE_PLUGIN_ROOT}/skills/migrate-webadi/webadi_fad.py <gathered folder> [--content <folder of shipped upload XMLs>]`. It writes `webadi_inventory.md` into the folder, `FAD_<INTEGRATOR>.md` into each integrator folder that uploads data, and `<INTEGRATOR>_download_sql.md` for each download-only integrator. `--content` (or the environment variable `BLITZ_CONTENT_DIR`) points at exported shipped uploads (`content/r12/uploads` in the Blitz Report repository), so that the document names shipped uploads that already cover the integrator.
3. Route each integrator by its kind in the inventory:

| Kind | Meaning | Route |
|---|---|---|
| Upload | an interface of type Table, API or Java upload class | steps 2 to 6 |
| Download only | every interface is download only: WebADI fills a sheet from SQL and uploads nothing | a report: convert `<INTEGRATOR>_download_sql.md` with the `migrate-custom-reports` skill |
| No interface | no interface and no SQL download: a shell, or an integrator driven entirely by Java | nothing to convert; ask the customer what they upload with it |

4. Ask the customer, in one message, for what the definition cannot give:
   - per integrator, the layout they use and one spreadsheet they uploaded, with its row count: the acceptance reference of step 5, and the only evidence of which columns they really fill;
   - for every importer program the document flags as customer-built: a converter run that selects that program as a concurrent program, so that its definition and executable are gathered;
   - the source of every customer Java class the document names (validators, defaults, download classes).

### 2. Review the form analysis document

The document is generated: verify each section against the API source before building on it.

- Read the package the interface calls (section 6) and the importer (section 7): a customer package from the gathered `.sql` files, an Oracle one from the instance. Establish what the row procedure does (stages into a table or calls a public API), how it reports an error (raises, returns a status, writes an error table), what groups rows into one importer call (the GROUP columns, often a record id from a sequence), and what the cleanup procedure deletes.
- Section 2 is the sheet the user sees: the column order, read-only columns and defaults of the layout the customer uses.
- Every Java validator or default in section 12 is logic WebADI ran outside the database. Find what it checks in the API source first (the API often repeats the check); otherwise read the class, and reproduce it in the upload package as a row error.
- Section 5 drafts each list of values from the WebADI table validation. Replace a draft with a shared Blitz Report list wherever one covers the same table, and copy the shipped list's where clause for a security-scoped table (`upload-development` skill, Reuse Existing LOVs).
- Tokens without a known equivalent are listed under Open questions; resolve every one.

### 3. Classify

- A shipped upload that covers the columns of section 2: deliver a template of it, in its own category (decision in `webadi-migration` skill). A few missing columns are an enhancement of that upload: raise it as a product change, never as a customer-specific copy.
- Otherwise a new upload in category `Custom Uploads <ABBR>`.

### 4. Build

Build with the `upload-builder` skill from the reviewed document, and keep the processing WebADI used: call the integrator's own API or interface, never a reimplementation of it. The mapping:

| WebADI | Blitz Upload |
|---|---|
| Line block columns, in layout order | Upload columns, headed by the WebADI prompt |
| Context and header block columns | An upload parameter when the value scopes the whole file (ledger, budget, organization), otherwise a column repeated on every row; the Database context value is dropped |
| Required interface column outside the layout | A hidden column with its default, or set in the procedure |
| Alias column (interface column type 2) | A column the user sees that feeds a flexfield or list; not passed to the API |
| Document parameter (`$PARAM$`) | An upload parameter; defaults and lists read it as `:$flex$.<parameter name>` |
| Table validation | A list of values: the shared list, else the section 5 draft |
| Key flexfield (and its segments) | Concatenated segments with segment lists (`xxen_util.kff_segment_lov`); a combination id resolved in the procedure |
| Descriptive flexfield (and its segments) | Attribute columns, built with the `add-dff-to-upload` skill |
| Expanded SQL column set (period amounts) | One row per expanded value (a period and its amount), or fixed columns when the set is fixed |
| Java validator or default | A check or derivation in the procedure, from what the class does |
| SQL, constant, profile, parameter or environment default | `DEFAULT_VALUE` from section 4 |
| Sequence default per row | Assigned in the procedure |
| API interface (types 2 and 5) | The upload procedure calls the API once per row with the section 6 parameters, and turns its error into the row message |
| Table interface (type 1) | The procedure inserts the interface row, keeping its rowid in a hidden column (`upload-builder`, Error and Success SQL design), and the Error SQL reads the interface error status |
| Importer with GROUP columns | The post procedure, with the group columns as its IN parameters |
| PL/SQL importer step | Called by the post procedure, once per group |
| Concurrent request importer step | Submitted by the post procedure per group with the mapped arguments, waited for, its result read back by the Error and Success SQL |
| Cleanup PL/SQL | Called at the end of the post procedure |
| Commit All Rows | Single-call mode with one savepoint for the whole file: one rejected row errors every row and the importer does not run |
| Commit Each Row | Row by row |
| Download content SQL | The main SQL, for Create and Update |
| FORM functions of the responsibilities file | Function assignments; with none, the update function of the form that maintains the entity, or no assignment |

Put each upload procedure into the module package `XXEN_<MODULE>_UPLOAD` in `sql/extensions` (decision in `webadi-migration` skill): the module is the product code of the API or table the integrator writes (`ASO_WEBADI_PVT` gives `XXEN_ASO_UPLOAD`, `GL_BUDGET_INTERFACE` gives `XXEN_GL_UPLOAD`), section 11 of the document names the package and whether it exists. Add the procedure to the existing package, else create the package. The package ships to every customer, so:

- Call a customer's own package, and an API that not every release the package ships to has (the 12.2-only `ASO_WEBADI_PVT` in a package that also runs on 12.1.3), through `execute immediate` only: a static reference makes the whole module package invalid wherever the object is missing.
- Compile the package on every release it ships to before delivery, with `${CLAUDE_PLUGIN_ROOT}/scripts/lint_plsql.py` clean.

### 5. Test

Run the test matrix of `upload-development` skill (section J), and add:

- The customer's spreadsheet, row for row through the Blitz upload, and the same rows through WebADI on the build instance where the integrator runs there; compare the records each creates.
- For All Rows: a file with one bad row creates nothing and reports every row.
- For a group importer: two groups in one file, each processed once.

### 6. Deliver

- New uploads: one XML per category with every upload of it, plus the package files and their install order.
- A template of a shipped upload: as an Outcome 1 template of `custom-reports-migration` skill, the shipped upload's XML with the template and without an `ASSIGNMENTS` block.
- Per integrator, a line in the delivery mail with its route (upload, template, report, nothing to convert) and the input still open from step 1.
