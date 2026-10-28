---
name: webadi-migration
description: Converting Oracle WebADI integrators gathered by the Blitz Report Custom Reports Converter into Blitz Uploads. Use with the upload-builder skill.
user-invocable: false
---

# WebADI Integrator Migration

A customer's WebADI integrators are converted to Blitz Uploads. The Blitz Report Custom Reports Converter gathers them (parameter Include WebADI Integrators, program type WebADI Integrator), the conversion classifies them with the outcomes of `custom-reports-migration` skill, and the upload is built with the `upload-builder` skill.

- Decision: an integrator that a shipped upload covers is delivered as a template of that upload, in the upload's own category; one that needs a new upload goes into category `Custom Uploads <ABBR>`.
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
