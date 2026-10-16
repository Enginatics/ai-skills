---
description: "Analyze Oracle Form: Analyze an Oracle EBS standard form to extract field definitions, validation logic, LOV queries, defaulting rules, and API calls."
---

# Analyze Oracle Form

Analyze an Oracle EBS standard form to extract field definitions, validation logic, LOV queries, defaulting rules, and API calls. Produces a structured Form Analysis Document (FAD).

## Arguments

$ARGUMENTS should contain the Oracle form name (e.g., "FAXASSET", "APXINWKB") or OAF page description (e.g., "iProcurement requisition", "iExpenses entry").

## Instructions

Load and follow the `oracle-forms-analyzer` skill. It provides the complete methodology for:
1. Locating form source files and converting `.fmb` to readable format
2. Extracting data blocks, fields, triggers, LOVs, KFFs, and DFFs
3. Analyzing underlying database packages and APIs
4. Producing the structured Form Analysis Document
5. Completing the quality checklist before finishing
6. Reporting any open questions that need user input

## Output

A complete FAD named `FAD_<MODULE>_<FORM>_<YYYYMMDD>.md` (saved to `/tmp` on server or `C:\Temp` on Windows).

The FAD is used as input by the `upload-builder` and `upload-validator` skills.
