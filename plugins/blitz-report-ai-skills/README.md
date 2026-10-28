# Blitz Report Development

Build, convert, test and tune Blitz Reports and Blitz Uploads for Oracle E-Business Suite: report and upload XML, report SQL, upload PL/SQL packages, Custom Reports Converter migrations, Oracle report and form analysis

Browse with search: https://www.enginatics.com/ai-skills/blitz-report-ai-skills/

```
/plugin marketplace add enginatics/ai-skills
/plugin install blitz-report-ai-skills@enginatics
```

Then run `/blitz-report-ai-skills:blitz-environment-setup` once to describe your EBS development instance. Never point it at production.

## Getting Started

- [Environment Setup](https://www.enginatics.com/ai-skills/blitz-environment-setup/) (`blitz-environment-setup`): Set up the Blitz Report environment file (.claude/rules/blitz-environment.md) that the Blitz Report development skills use to reach the Oracle EBS development instance.

## Migration

- [Convert Oracle Reports to Blitz Report](https://www.enginatics.com/ai-skills/convert-bip-and-rdf-reports-to-blitz/) (`convert-bip-and-rdf-reports-to-blitz`): End-to-end conversion of Oracle RDF, BI Publisher, or Concurrent Program reports to Blitz Reports. Includes conversion rules, deployment, testing, duplicate detection, and iterative performance optimization.
- [Custom Reports Migration Rules](https://www.enginatics.com/ai-skills/custom-reports-migration/) (`custom-reports-migration`): Rules for migrating custom Oracle EBS reports gathered by the Blitz Report Custom Reports Converter into Blitz Reports.
- [Discoverer Migration Rules](https://www.enginatics.com/ai-skills/discoverer-migration/) (`discoverer-migration`): Reviewing and finishing Oracle Discoverer workbooks converted to Blitz Reports.
- [Migrate Custom Reports](https://www.enginatics.com/ai-skills/migrate-custom-reports/) (`migrate-custom-reports`): Phase-2 engagement workflow for migrating a customer's gathered custom Oracle EBS reports (the Blitz Report Custom Reports Converter zip output) into Blitz Reports — inventory, extract SQL, classify each report into one of three outcomes (complete map / enhance / new custom build), build/recommend, categorize as "Custom Reports <ABBR>", and prove each report prints what the original prints (field inventory + value fidelity gate) on the conversion instance.
- [Oracle Report Analyzer](https://www.enginatics.com/ai-skills/rdf-analyzer/) (`rdf-analyzer`): Analyze Oracle EBS standard reports (.rdf and XML Publisher data templates) to extract SQL queries, parameters, output structure, and PL/SQL logic.
- [WebADI Migration Rules](https://www.enginatics.com/ai-skills/webadi-migration/) (`webadi-migration`): Converting Oracle WebADI integrators gathered by the Blitz Report Custom Reports Converter into Blitz Uploads.

## Report Development

- [Blitz Report Developer](https://www.enginatics.com/ai-skills/blitz-report-developer/) (`blitz-report-developer`): Create and update Blitz Reports and uploads for Oracle EBS.
- [Report Development Rules](https://www.enginatics.com/ai-skills/report-development/) (`report-development`): Blitz Report XML rules: parameters, LOVs, anchors, lexicals, templates, assignments, columns, the report engine.

## Standards

- [Development Workflow](https://www.enginatics.com/ai-skills/development-workflow/) (`development-workflow`): Working method for Blitz Report content development: baseline, change, deploy, re-run, regression-diff, test data rules, no hard-coded credentials.
- [EBS 11i Compatibility](https://www.enginatics.com/ai-skills/ebs-11i-compatibility/) (`ebs-11i-compatibility`): Making Blitz Report content work on Oracle EBS 11i and older databases: 11i twins, translations, version traps.
- [SQL and PL/SQL Coding Standards](https://www.enginatics.com/ai-skills/coding-standards/) (`coding-standards`): SQL and PL/SQL coding standards for Blitz Report content: report SQL, LOV queries, upload packages.

## Testing and Tuning

- [Report Performance Tuning](https://www.enginatics.com/ai-skills/tune-report-performance/) (`tune-report-performance`): Tune Blitz Report SQL performance by measuring buffer IO per row, identifying expensive components, and applying targeted fixes.
- [Report Tester](https://www.enginatics.com/ai-skills/report-tester/) (`report-tester`): Test a Blitz Report by running the original Oracle standard report and the Blitz version with the same parameters, then comparing output.
- [ZIP Compatibility Fix](https://www.enginatics.com/ai-skills/fix-zip-compatibility/) (`fix-zip-compatibility`): Re-compress a ZIP file for Oracle compatibility.

## Upload Development

- [Add DFF Handling to an Upload](https://www.enginatics.com/ai-skills/add-dff-to-upload/) (`add-dff-to-upload`): Add descriptive flexfield (DFF) handling to a Blitz Upload - context and attribute columns with context-dependent lists of values, segment prompts as column headers, Success SQL, and the PL/SQL that merges untouched segments, validates the DFF and converts display values to ids before the API call.
- [EBS API Patterns for Uploads](https://www.enginatics.com/ai-skills/upload-api-patterns/) (`upload-api-patterns`): Oracle EBS module API specifics for Blitz Uploads (ONT, PO, INV, WIP, CST, AP, AR, HR, FA, CE, EAM, OPM, PA, QA and more).
- [Oracle Forms Analyzer](https://www.enginatics.com/ai-skills/oracle-forms-analyzer/) (`oracle-forms-analyzer`): Analyze Oracle EBS standard forms to extract field definitions, validation logic, LOV queries, defaulting rules, and API calls.
- [Upload Builder](https://www.enginatics.com/ai-skills/upload-builder/) (`upload-builder`): Build Blitz Upload XML definitions and PL/SQL processing packages for Oracle EBS.
- [Upload Development Rules](https://www.enginatics.com/ai-skills/upload-development/) (`upload-development`): Blitz Upload XML and PL/SQL rules: upload columns, completeness checklist, processing package architecture, E2E testing.
- [Upload Validator](https://www.enginatics.com/ai-skills/upload-validator/) (`upload-validator`): Review a Blitz Upload against the Oracle standard form and run E2E tests.
