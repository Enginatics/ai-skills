---
name: webadi-migration
description: Converting Oracle WebADI integrators gathered by the Blitz Report Custom Reports Converter into Blitz Uploads. Use with the migrate-webadi skill.
user-invocable: false
---

# WebADI Integrator Migration

A customer's WebADI integrators are converted to Blitz Uploads. The Blitz Report Custom Reports Converter gathers them (parameter Include WebADI Integrators, program type WebADI Integrator), and the `migrate-webadi` skill converts the gathered folder: its `webadi_fad.py` writes a form analysis document per integrator for the `upload-builder` skill.

- Decision: an integrator that a shipped upload covers is delivered as a template of that upload, in the upload's own category; one that needs a new upload goes into category `Custom Uploads <ABBR>`.
- Decision: a converted upload's procedure goes into the module package `XXEN_<MODULE>_UPLOAD` in `sql/extensions`, the existing one for the product code of the API or table the integrator writes (`ASO_WEBADI_PVT` gives `XXEN_ASO_UPLOAD`), else a new one; never into a customer-specific package. Such a package ships to every customer, so a customer object, or an API missing from a release the package ships to, is called through `execute immediate` only.
- Decision: a converted upload keeps the integrator's commit behaviour. WebADI commits per upload parameter `bne:commitrows` (lookup `BNE_COMMITROWS`: All Rows, the default, or Each Row, offered only when the integrator's upload parameter list includes it). All Rows means one failing row commits nothing, and the unit is the whole uploaded file: build it in the single-call mode of `upload-development` skill with one savepoint before the first row, and when any row failed the framework's list validation or the API rejects any row, roll back to it and error every row. An Each Row integrator stays row by row.

## Gathered files (one folder per integrator)

| File | Content |
|---|---|
| `<INTEGRATOR>_integrator.ldt` | `FNDLOAD bneintegrator.lct BNE_INTEGRATORS` export: interfaces and their columns (prompts, validation, defaults), layouts, contents with their download SQL, mappings, the upload and importer parameter lists, components and security rules. EBS 11i ships no `bneintegrator.lct`, so there the file is missing. |
| `<INTEGRATOR>_responsibilities.txt` | Pipe-delimited: each function that grants the integrator through its security rule or names it in a `bne:integrator=` parameter, the function type, and every active responsibility whose menu reaches the function. |
| `<OWNER>.<NAME>.<type>.sql` | Custom dependency DDL: objects matching the Custom Object Prefix anywhere in the ldt (interface tables, API packages, validation tables, download SQL) and their custom closure. |

## Metadata facts

- An API interface names its package and procedure (`<PACKAGE>.<PROCEDURE>`) in a `BNE_ATTRIBUTES` row of its upload parameter list (`UPLOAD_PARAMS` of `BNE_INTERFACES`); `INTERFACE_NAME` holds only the procedure and `UPLOAD_OBJ_NAME` is usually empty.
- A table interface's importer names the concurrent program it submits in the `BNE_ATTRIBUTES` rows of its concurrent request parameter list: `ATTRIBUTE1` is the argument (`APPLICATION`, `PROGRAM`), `ATTRIBUTE5` the quoted value (`'SQLGL'`, `'GLLEZL'`).
- Only the `FORM` functions of the responsibilities file can become the upload's Function assignments. Seeded security rules also name the generic Create Document functions (`BNE_ADI_CREATE_DOCUMENT`, `BNE_CREATE_DOCUMENT`), which are on most menus.
- WebADI usage per integrator (`BNE_DOC_ACTIONS.UPLOAD_COUNT` per document and user, documents linked through the `BNE_DOC_CREATION_PARAMS` parameter `bne:integrator` = `<application id>:<integrator code>`) exists only on R12, so the converter listing, which also runs on 11i, shows no run counts for integrators.
- `BNE_INTERFACES.UPLOAD_TYPE`: 1 table, 2 and 5 API (the attribute row of the upload parameter list says `PROCEDURE` or `FUNCTION`), 4 download only, 0 a Java upload class (`UPLOAD_OBJ_NAME`). An integrator whose interfaces are all type 4 is a report; one with no interface uploads nothing.
- `BNE_INTERFACE_COLS.DATA_TYPE`: 1 number, 2 text, 3 date, 5 and 6 date with time. `INTERFACE_COL_TYPE` 2 is an alias column, which feeds a flexfield or list and is not passed to the API or table. `UPLOAD_PARAM_LIST_ITEM_NUM` maps a column to the API parameter of that item number.
- Context and header block values are entered once per WebADI document and apply to every line.
- Tokens in defaults and validation where clauses: `$PROFILES$.<name>` is `fnd_profile.value`, `$PARAM$.<name>` a document parameter the user entered when creating the sheet, `$TABLE$.<table>.<column>` and `$INTERFACE$.<column>` another column of the same row, `$ENV$.userid`, `respid` and `language` the session user, responsibility and language. Environment defaults: `SYSDATE`, `OAUSER.ID`, and `DATABASE` (the context block's instance name).
- Java validators, Java defaults (`JAVA`, `JAVA_OVERRIDE`, `JAVA_EACH_ROW`), Java download content and `GROUP` validators run in the WebADI middle tier, so the definition holds only their class names. Content classes under `oracle.apps.bne` (None, Text File) download nothing from the database.
- The importer is the integrator's `IMPORT` parameter list: steps `GROUP` (the columns whose distinct values make one importer call), `SQL`, `PLSQL`, `CONCURRENT_REQUEST`, `CLEANUP_PLSQL`, `ROW_MAPPING`, `ERRORED_ROWS`, `ERROR_LOOKUP` and `SUCCESS_MESSAGE`, each pointing at its own parameter list (`<application id>:<list code>`); an argument's attribute `7=IMPORT 8=<table>.<column>` takes its value from that interface column.
- A row `OWNER` of `ORACLE<release>` marks an Oracle-delivered integrator; `BNE_INTEGRATORS_B.SOURCE` does not separate Oracle's integrators from customer ones, since Oracle-delivered integrators carry `C` as well.
- A customer importer concurrent program is not gathered with the integrator, because the closure follows database objects only: gather it by selecting it as a concurrent program in a converter run.
- Several Oracle integrators and their APIs exist only on 12.2 (Quoting - Create Quote with `ASO_WEBADI_PVT`, Field Service Debrief with `CSF_DEB_WEBADI_PKG`), so a conversion is built on an instance of the customer's release.
