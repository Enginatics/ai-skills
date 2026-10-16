---
name: blitz-report-developer
description: Create and update Blitz Reports and uploads for Oracle EBS. Use when user asks to create a new report, modify existing reports, create uploads, migrate reports from RDF/BI Publisher/XML/PL/SQL, or analyze Oracle forms validation logic.
metadata:
  title: Blitz Report Developer
  category: Report Development
---

# Blitz Report Developer Skill

This skill helps create and maintain Blitz Reports and uploads for Oracle E-Business Suite (EBS).

## Capabilities

1. **Create new Blitz Reports** from scratch or by migrating from other technologies
2. **Modify/update existing reports** - add columns, parameters, fix data issues
3. **Create uploads** (data import templates) with proper validation logic
4. **Migrate reports** from Oracle Reports Builder (RDF), BI Publisher, XML, or custom PL/SQL
5. **Analyze Oracle EBS forms** to replicate validation logic in uploads

## Key Resources

### Documentation
- Developer Guide: https://www.enginatics.com/blitz-report-developer-guide/
- Training Video: https://youtu.be/C7jRstrvA-A

### Example Reports (in content/r12/reports/)
- **Simple**: `AP_Suppliers.xml` - basic supplier listing with joins
- **Medium**: `GL_Account_Analysis_Distributions.xml` - GL distributions with parameters
- **Complex**: `AR_Aging.xml` - migrated from Oracle standard with bucket calculations

### Example Uploads (in content/r12/uploads/)
- **Simple**: `Blitz_Report_Assignment_Upload.xml` - basic upload with validation function
- **Complex**: `AP_Supplier_Upload.xml` - multi-table upload with extensive validation

### Test Environment
- **Ledger**: Vision Operations (USA)
- **Operating Unit**: Vision Operations
- **Inventory Org**: M1

## Report XML Structure

The `<CATEGORIES>` section is **required** — it defines the category before `<REPORTS>` so the import can create/find it. Without it, `<CATEGORY_ASSIGNMENTS>` inside the report will silently fail.

```xml
<ROOT>
 <APPS_INITIALIZE_DATA>
  <USER_NAME>ENGINATICS</USER_NAME>
  <RESPONSIBILITY_KEY>SYSTEM_ADMINISTRATOR</RESPONSIBILITY_KEY>
  <APPLICATION_SHORT_NAME>SYSADMIN</APPLICATION_SHORT_NAME>
 </APPS_INITIALIZE_DATA>
<CATEGORIES>
<!-- loader xml for Enginatics Blitz Report category: Category Name -->
 <CATEGORIES_ROW>
  <BASE_CATEGORY>Category Name</BASE_CATEGORY>
  <CATEGORY_TRANSLATIONS>
   <CATEGORY_TRANSLATIONS_ROW>
    <LANGUAGE>US</LANGUAGE>
    <CATEGORY>Category Name</CATEGORY>
   </CATEGORY_TRANSLATIONS_ROW>
  </CATEGORY_TRANSLATIONS>
 </CATEGORIES_ROW>
</CATEGORIES>
<REPORTS>
<!-- loader xml for Enginatics Blitz Report: Report Name -->
 <REPORTS_ROW>
  <GUID>...</GUID>
  <SQL_TEXT>select ... from ...</SQL_TEXT>
  <ENABLED>Y</ENABLED>
  <REPORT_TRANSLATIONS>...</REPORT_TRANSLATIONS>
  <CATEGORY_ASSIGNMENTS>
   <CATEGORY_ASSIGNMENTS_ROW>
    <CATEGORY>Category Name</CATEGORY>
   </CATEGORY_ASSIGNMENTS_ROW>
  </CATEGORY_ASSIGNMENTS>
  <ANCHORS>...</ANCHORS>
  <PARAMETERS>...</PARAMETERS>
  <COLUMNS>...</COLUMNS>
 </REPORTS_ROW>
</REPORTS>
</ROOT>
```

## Upload XML Structure

**IMPORTANT:** For regular reports, do NOT include a `<TYPE>` element at all — omitting it leaves TYPE blank (correct for reports). Only uploads use `<TYPE>U</TYPE>`. If after importing a report the UI shows TYPE as "Upload", clear it manually in the setup form. This can happen if a randomly generated GUID collides with an existing upload record during import.

Uploads have additional elements:
- `<TYPE>U</TYPE>` - marks as upload
- `<UPLOAD_TYPE>A</UPLOAD_TYPE>` - A=API, I=Interface table
- `<UPLOAD_OBJECT>package.procedure</UPLOAD_OBJECT>` - processing procedure
- `<UPLOAD_EXCEL_VALIDATION>...</UPLOAD_EXCEL_VALIDATION>` - validation PL/SQL

Standard upload columns (always first):
```sql
select
null action_,
null status_,
null message_,
null modified_columns_,
-- actual data columns follow
```

## Workflow

### Creating/Updating Reports

1. **Analyze requirements** - understand what data is needed
2. **Find existing similar reports** - search in content/r12/reports/
3. **Build SQL query** - follow coding standards from `coding-standards` skill
4. **Create/update XML** - use proper structure; every new parameter gets a `<DESCRIPTION>` in its US translation row, and user-visible behaviour changes get a report description update in the same edit (see `report-development` skill)
5. **Import & test on the development instance (see `blitz-environment.md`)** — `import_xml` derives the parameter and upload dependencies automatically from the `:$flex$`/`:$column$` references, so there is no separate regeneration step:
   - **Reports:** copy the XML to the apps tier of the development instance and run `$XXEN_TOP/bin/import_xml $APPS_PWD <file>` (or import the file content with `xxen_api.import_xml(<clob>)`); see `blitz-environment.md` for how to reach the instance.
   - **Uploads:** lint the XML with `${CLAUDE_PLUGIN_ROOT}/scripts/lint_upload_xml.py`, import it, then check every LOV parses (the deploy procedure in `blitz-environment.md`).
   - Exact commands + rules: `report-development` skill ("XML Import") and `upload-development` skill ("Upload Dependencies").
6. **Run report via API**:
   ```sql
   select xxen_report.run_report_api(
     p_report_name=>'Report Name',
     p_operating_unit=>'Vision Operations'
   ) from dual;
   ```
7. **Review results** and iterate

### Creating Uploads

1. **Understand target tables/APIs** - what Oracle API or tables to use
2. **Analyze Oracle forms validation** - use oracle-forms-analyzer subagent
3. **Create download SQL** - query existing data for template
4. **Create validation function** in appropriate package (usually xxen_upload or module-specific)
5. **Create processing procedure** for actual data import
6. **Build XML with validation references**
7. **Test with sample data**

### Migrating Reports

**From RDF (Oracle Reports Builder)**:
1. Extract SQL from report definition
2. Simplify: move function logic into main SQL where possible
3. Convert parameters to Blitz format
4. Replace Oracle report functions with SQL equivalents

**From BI Publisher**:
1. Extract data template SQL
2. Convert parameters
3. Simplify nested data sets into single query with joins

**From Custom PL/SQL**:
1. Analyze cursor/query logic
2. Convert to single SQL statement where possible
3. Move procedural logic to SQL CASE/DECODE statements

## SQL Coding Standards

Follow all rules in the **PL/SQL Coding Standards** section of `coding-standards` skill. Key rules for reports: lowercase everything, no spaces around operators, proper table aliases, use `xxen_util.meaning()` for lookups, bind variables (not literals), no redundant code.

## Common Patterns

### Operating Unit Parameter
```sql
where haouv.name=:p_operating_unit
```

### Ledger Parameter
```sql
where gl.name=:p_ledger
```

### Date Range Parameters
```sql
where trunc(aia.invoice_date) between :p_date_from and :p_date_to
```

### Multi-value LOV Parameter
```sql
where 1=1
and :p_supplier_name=:p_supplier_name  -- anchor
-- with SQL: aps.vendor_name in (select regexp_substr(:p_supplier_name,'[^,]+',1,level) from dual connect by level<=regexp_count(:p_supplier_name,',')+1)
```

## Using Oracle Forms Analyzer

When creating uploads that need to replicate Oracle standard form validations:

Use the `oracle-forms-analyzer` subagent to:
1. Analyze Oracle EBS standard forms (.fmb/.fmx)
2. Extract validation logic, triggers, and API calls
3. Document SQL queries used by the form
4. Identify required fields and business rules

Example use cases:
- Creating AP Invoice upload -> analyze APXINWKB form
- Creating PO Requisition upload -> analyze POXRQERQ form
- Creating Supplier upload -> analyze APXVDMVD form

## PL/SQL Packages

### Core Packages (in sql/)
- `XXEN_REPORT.pkb/pks` - main report engine
- `XXEN_UPLOAD.pkb/pks` - upload processing engine
- `XXEN_UTIL.pkb/pks` - utility functions
- `XXEN_REPORT_EBS.pkb/pks` - EBS-specific utilities

### Upload Validation Pattern
```sql
function validate_something(
  p_field1 in varchar2,
  p_field2 in varchar2
) return varchar2 is
begin
  if p_field1 is null then
    return 'Field1 is required';
  end if;
  -- more validations
  return null; -- null means valid
end;
```

## Finding Reports

Search existing reports:
```bash
# Find by module
ls content/r12/reports/AP_*.xml
ls content/r12/reports/GL_*.xml
ls content/r12/reports/AR_*.xml

# Find by keyword in SQL
grep -l "ap_invoices" content/r12/reports/*.xml
```

## Important Rules

### REQUIRED_PARAMETERS vs REQUIRED Flag

- **`<REQUIRED>Y</REQUIRED>`** on a parameter: Use this to make a parameter mandatory. The system enforces this automatically.
- **`<REQUIRED_PARAMETERS>`** on the report: Use this ONLY for advanced validation of **optional** parameter combinations.

**WRONG**: Using REQUIRED_PARAMETERS to check if required parameters are filled:
```xml
<REQUIRED_PARAMETERS>:p_from_date is not null</REQUIRED_PARAMETERS>  <!-- WRONG - redundant -->
```

**CORRECT**: Using REQUIRED_PARAMETERS for optional parameter dependencies:
```xml
<REQUIRED_PARAMETERS>:p_detail_level='Detail' or :p_show_amounts is null</REQUIRED_PARAMETERS>
```

If all your key parameters already have `<REQUIRED>Y</REQUIRED>`, leave `<REQUIRED_PARAMETERS>` empty/null.

## Tips

1. **Start from existing reports** - find similar reports and modify
2. **Test incrementally** - import and run after each significant change
3. **Use meaningful column aliases** - they become Excel headers
4. **Keep SQL readable** - use proper indentation and line breaks
5. **Document complex logic** - add comments in XML description


## Access Assignments (MANDATORY)

Every new/converted report MUST ship with a top-level `<ASSIGNMENTS>` block (sibling of `<REPORTS>`) or no responsibility can see it. Generate it **data-driven from the report's SQL data domain**, not the name prefix (an INV report may also serve Manufacturing/BOM/Cost/WMS). Full methodology in `report-development` skill "Report Assignments":
- **#1** mirror each relevant application with the request groups its normal responsibilities use (Inventory→`All Inclusive GUI`@INV, Payables→`All Reports`@SQLAP, Cost Management→`Cost Management`/`-SLA`@BOM, ...).
- **#4** add major-country localization request groups (India `JAI_<Module>_RG` + DE/FR/IT/ES/BR/MX/CN/JP/AU).
- **#3** never use Application=`Human Resources` (290 self-service responsibilities) — use HR request groups; same caution for Assets/iSupplier/OTL/Learning.
- **#5** add `Form`-level zoom assignments (with `FORM_PARAMETERS`) for the report's primary Oracle entity form where applicable.
- **Uploads** (TYPE=U) get `Function`-level assignments to update-enabled functions ONLY — see `upload-development` skill I7.
