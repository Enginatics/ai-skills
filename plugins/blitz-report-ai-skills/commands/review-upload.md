---
description: "Review Upload: Review a Blitz Upload against the Oracle standard form and run E2E tests."
---

# Review Upload

Review a Blitz Upload against the Oracle standard form and run E2E tests. This is the comprehensive validation command that subsumes `/validate-upload-xml` and `/test-upload`.

## Arguments

$ARGUMENTS should contain the upload name or XML file path (e.g., "FA Asset Upload" or "content/r12/uploads/FA_Asset_Upload.xml").

## Instructions

Load and follow the `upload-validator` skill. It provides the complete methodology for:

1. **Phase 1: Form Analysis** — analyze the Oracle form via `oracle-forms-analyzer` skill
2. **Phase 2: Review Checklist** — compare upload against form across 10 categories:
   - Missing fields, field naming, field order
   - LOVs, defaulting logic, validation logic
   - KFF handling, processing logic
   - XML structure, success/error SQL
3. **Phase 3: E2E Testing** — download template, create test data, upload, verify results
4. **Phase 4: Report Findings** — structured report with BLOCKER/MAJOR/MINOR/SUGGESTION severity, issue IDs, passed checks, and recommended test scenarios

## Output

A validation report with:
- If BLOCKERs found: stop and request fixes before proceeding
- If only MINOR/SUGGESTION issues: present them with recommended fixes
- Passed checks listed for completeness

For quick checks without full form comparison:
- `/validate-upload-xml` — XML structure checks only (Phase 2.9)
- `/test-upload` — E2E testing only (Phase 3)
