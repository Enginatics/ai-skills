---
description: "Validate Upload XML: Analyze a Blitz Report upload XML definition for common issues and consistency."
---

# Validate Upload XML

Analyze a Blitz Report upload XML definition for common issues and consistency.

## Arguments

$ARGUMENTS should be the path to the XML file to validate (e.g., "content/r12/uploads/AR_Transaction_Upload.xml").

## Checks to Perform

### 1. Column Consistency
- Verify COLUMN_NAME entries match the SQL select columns
- Check that UPLOAD_COLUMN_NUMBER assignments are sequential and correct
- Ensure PARAMETER_TYPE_DSP matches the column data type
- Verify VALUE_TO_ID_QUERY references are valid (if column has one)
- Check that VALIDATE_FROM_LIST_DSP is appropriate for each column

### 2. Upload Dependencies
- For each DEFAULT_VALUE that contains `:$column$.column_name` references:
  - Verify a matching UPLOAD_DEPENDENCIES_ROW exists
  - Check column name matches exactly (case-sensitive)
- Flag any orphaned dependencies (dependency without matching default value reference)

### 3. Parameter Dependencies
- For each LOV query containing `:$flex$.Parameter_Name` references:
  - Verify a matching PARAMETER_DEPENDENCIES_ROW exists
  - Check parameter names match exactly
- Verify null handling pattern: `(:$flex$.Param is null or xxen_util.contains(:$flex$.Param, column)='Y')`

### 4. Anchor Consistency
- Every anchor referenced in PARAMETERS must be declared in ANCHORS section
- Every anchor in the SQL (1=1, 2=2, etc.) should have parameters using it
- Check SQL_TEXT syntax for each anchor type

### 5. Upload Object
- Verify UPLOAD_OBJECT package.procedure exists in the codebase
- Check procedure signature matches expected column mappings

### 6. General Quality
- Check for proper XML escaping (& as &amp;, etc.)
- Verify GUID is present and unique
- Check REPORT_TRANSLATIONS has at least one entry
- Verify TYPE is 'U' for uploads

## Output

Provide a summary of:
- Total issues found (errors vs warnings)
- List of each issue with location and suggested fix
- Overall assessment (ready to deploy / needs fixes)
