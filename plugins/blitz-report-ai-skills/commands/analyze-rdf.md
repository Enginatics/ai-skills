---
description: "Analyze Oracle Report: Analyze an Oracle EBS standard report (.rdf or XML Publisher data template) to extract SQL queries, parameters, output columns, formulas, and PL/SQL logic."
---

# Analyze Oracle Report

Analyze an Oracle EBS standard report (.rdf or XML Publisher data template) to extract SQL queries, parameters, output columns, formulas, and PL/SQL logic. Produces a structured Report Analysis Document (RAD).

## Arguments

$ARGUMENTS should contain the report filename (e.g., "FADTXA.rdf"), concurrent program name (e.g., "FADTXA"), or a description (e.g., "FA Tax Reserve Report").

## Instructions

Load and follow the `rdf-analyzer` skill. It provides the complete methodology for:
1. Locating the report source file (.rdf or XML Publisher data template)
2. Converting .rdf to readable XML using `rwconverter` (or `strings` fallback)
3. Extracting SQL queries, parameters, groups, formulas, and PL/SQL triggers
4. Documenting master-detail relationships and aggregates
5. Identifying lexical parameters and SRW user exits
6. Capturing request group assignments

## Output

A complete RAD documenting everything needed to build the equivalent Blitz Report.

The RAD is used as input by the `convert-bip-and-rdf-reports-to-blitz` skill and the `report-tester` skill.
