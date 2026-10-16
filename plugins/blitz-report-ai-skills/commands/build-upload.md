---
description: "Build Upload: Build a Blitz Upload XML definition and PL/SQL processing package for Oracle EBS."
---

# Build Upload

Build a Blitz Upload XML definition and PL/SQL processing package for Oracle EBS.

## Arguments

$ARGUMENTS should contain the upload name and target module (e.g., "FA Asset Upload" or "CE Bank Statement Upload"). Optionally include a reference to a Form Analysis Document (FAD).

## Instructions

Load and follow the `upload-builder` skill. It provides the complete methodology for:
1. Designing the column list, PL/SQL package, and processing approach
2. Building the validation function (with concatenated error messages)
3. Building the processing procedure (auto-detect create/update)
4. Building the XML definition (parameters, columns, LOVs, defaults, dependencies, and a `Function`-level `<ASSIGNMENTS>` block — update-enabled functions ONLY, never Form/Application/Request-Group; see `upload-development` skill I7)
5. Deploying PL/SQL and importing XML to the development instance (see `blitz-environment.md`)
6. Auto-generating dependencies and exporting clean XML
7. Running the quality checklist before handoff

If no FAD is available, first run `/analyze-form` on the relevant Oracle form.

## Output

- PL/SQL package (spec + body) in `sql/extensions/`
- Upload XML in `content/r12/uploads/`
- Both deployed to the development instance and ready for testing

After building, run `/review-upload` to validate against the Oracle form and run E2E tests.
