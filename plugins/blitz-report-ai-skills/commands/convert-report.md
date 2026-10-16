---
description: "Convert Report to Blitz: End-to-end automated conversion of an Oracle RDF, BI Publisher, or Concurrent Program report to Blitz Report format."
---

# Convert Report to Blitz

End-to-end automated conversion of an Oracle RDF, BI Publisher, or Concurrent Program report to Blitz Report format. Includes analysis, conversion, deployment, testing, duplicate detection, and iterative performance optimization.

## Arguments

$ARGUMENTS should contain one of:
- File path to source report folder or XML file
- Concurrent program name (e.g., `FADTXA`)
- Report description (e.g., "FA Tax Reserve Report")

If a folder is provided, look for both the auto-converted Blitz XML and the original RDF/BIP data template.

## Instructions

Load and follow the `convert-bip-and-rdf-reports-to-blitz` skill. It covers both the conversion rules and the full end-to-end pipeline (see "End-to-End Conversion Pipeline" section).

All versioned XML files are placed in the same folder as the source files.

The converted report must ship with a top-level `<ASSIGNMENTS>` block so responsibilities can see it. Derive it data-driven (not by name prefix): the applications/request groups the report's data serves (mirror app→request-group), major-country localization request groups, and Form-level zoom assignments where applicable — see `report-development` skill "Report Assignments" (reach model, #1 mirror, #4 localization, #3 security, #5 forms). Prefer Request Group level for the concurrent program's request groups (`fnd_request_group_units`).

## Output

- Blitz Report XML definition (`_v01.xml`, `_v02.xml`, etc.)
- Conversion Summary Report (markdown)
- Performance before/after metrics
