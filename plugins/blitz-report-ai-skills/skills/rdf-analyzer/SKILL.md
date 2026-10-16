---
name: rdf-analyzer
description: Analyze Oracle EBS standard reports (.rdf and XML Publisher data templates) to extract SQL queries, parameters, output structure, and PL/SQL logic. Use when converting an Oracle report to Blitz Report format.
metadata:
  title: Oracle Report Analyzer
  category: Migration
---

# RDF Analyzer Skill

Extracts the data model, parameters, output columns, and PL/SQL logic from Oracle EBS reports — both **Oracle Reports** (.rdf) and **XML Publisher** (BI Publisher) data templates. Produces a structured **Report Analysis Document** (RAD) that the report builder and conversion skill consume.

## When to Use

- Before converting an Oracle Report (.rdf) to a Blitz Report
- Before converting a BI Publisher report to a Blitz Report
- When user provides a concurrent program name and wants to understand the report structure

## Arguments

$ARGUMENTS should contain the report filename (e.g., "FADTXA.rdf"), concurrent program name (e.g., "FADTXA"), or a description of the report (e.g., "FA Tax Reserve Report").

## Report Type Detection

| Type | File Extension | Location | Conversion Tool |
|------|---------------|----------|-----------------|
| Oracle Reports | `.rdf` | `$APPL_TOP/{mod}/12.0.0/reports/US/` | `rwconverter` |
| XML Publisher | `.xml` | `$APPL_TOP/{mod}/12.0.0/patch/115/publisher/defs/` | Not needed (already XML) |

## Phase 1: Locate Report Source

### 1.1 Find by Concurrent Program Name

```sql
-- Find the concurrent program and its executable
select
fcp.concurrent_program_name,
fcp.user_concurrent_program_name,
fe.execution_file_name,
fe.execution_method_code,
fa.application_short_name
from
fnd_concurrent_programs fcp,
fnd_executables fe,
fnd_application fa
where
fcp.executable_id=fe.executable_id and
fcp.executable_application_id=fe.application_id and
fcp.application_id=fa.application_id and
(fcp.concurrent_program_name=:program_name or
 fcp.user_concurrent_program_name like '%'||:keyword||'%')
order by
fcp.concurrent_program_name
```

**Execution methods:**
- `O` = Oracle Reports (.rdf file)
- `J` = Java / XML Publisher
- `P` = PL/SQL stored procedure
- `S` = SQL*Plus script

### 1.2 Find the Source File

The source files are on the apps tier of the EBS instance (`$<PROD>_TOP/reports/US` for .rdf files). Connect to it as described in `blitz-environment.md`, or ask the DBA to copy the files.

```bash
# Source the apps tier environment file first

# Oracle Reports (.rdf)
find $APPL_TOP/*/12.0.0/reports/US -name "FILENAME.rdf" 2>/dev/null

# XML Publisher data templates
find $APPL_TOP/*/12.0.0/patch/115/publisher/defs -name "FILENAME*.xml" 2>/dev/null
```

### 1.3 Find Concurrent Program Parameters

```sql
-- Get parameter definitions
select
fdfcuv.column_seq_num,
fdfcuv.end_user_column_name,
fdfcuv.form_left_prompt,
fdfcuv.default_type,
fdfcuv.default_value,
fdfcuv.required_flag,
fdfcuv.enabled_flag,
fdfcuv.display_flag,
fdfcuv.flex_value_set_id,
ffvs.flex_value_set_name,
ffvs.validation_type
from
fnd_descr_flex_col_usage_vl fdfcuv,
fnd_flex_value_sets ffvs
where
fdfcuv.application_id=:app_id and
fdfcuv.descriptive_flexfield_name='$SRS$.'||:program_name and
fdfcuv.descriptive_flex_context_code='Global Data Elements' and
fdfcuv.flex_value_set_id=ffvs.flex_value_set_id(+)
order by
fdfcuv.column_seq_num
```

## Phase 2: Convert and Read Oracle Reports (.rdf)

### 2.1 Convert to XML

```bash
# Copy to /tmp and convert
cp $APPL_TOP/{mod}/12.0.0/reports/US/FILENAME.rdf /tmp/
cd /tmp
rwconverter stype=rdffile source=/tmp/FILENAME.rdf dtype=xmlfile dest=/tmp/FILENAME.xml batch=yes
```

**If rwconverter fails** (segfault, exit 139 — happens with some files):

```bash
# Fallback: extract readable content with strings
strings /tmp/FILENAME.rdf > /tmp/FILENAME_strings.txt

# Search for SQL queries
strings /tmp/FILENAME.rdf | grep -i 'select.*from' | head -20

# Search for parameter references
strings /tmp/FILENAME.rdf | grep -i ':P_' | head -20
```

### 2.2 Extract Data Model from Converted XML

The converted XML has these key sections:

#### Parameters (`<userParameter>`)

```xml
<userParameter name="P_BOOK" datatype="character" width="15" initialValue=""/>
<userParameter name="P_PERIOD" datatype="character" width="25"/>
<userParameter name="P_CONC_REQUEST_ID" datatype="number" width="15" initialValue="0"/>
```

Extract: name, datatype, width, initialValue, any `<listOfValues>` children.

#### SQL Queries (`<dataSource>`)

```xml
<dataSource name="Q_MAIN">
  <select><![CDATA[
    select ad.asset_number, ad.description, fb.cost, fb.date_placed_in_service
    from fa_additions ad, fa_books fb
    where ad.asset_id=fb.asset_id and fb.book_type_code=:P_BOOK
    and fb.date_effective between :P_START and nvl(:P_END, sysdate)
    order by ad.asset_number
  ]]></select>
</dataSource>
```

#### Groups and Columns (`<group>`, `<dataItem>`)

```xml
<group name="G_MAIN">
  <dataItem name="ASSET_NUMBER" oracleDatatype="varchar2" width="15">
    <dataDescriptor expression="ad.asset_number" order="1"/>
  </dataItem>
  <formula name="CF_TOTAL" source="cf_totalformula" datatype="number"/>
  <summary name="CS_COST_SUM" source="COST" function="sum" reset="G_MAIN"/>
</group>
```

- `<dataItem>` = a column from the SQL query
- `<formula>` = a PL/SQL-computed column (see `<programUnits>`)
- `<summary>` = aggregate (sum, count, min, max, avg) with break/reset group
- `<placeholder>` = a variable populated by triggers at runtime

#### Master-Detail Relationships

Nested `<group>` elements within a `<dataSource>` indicate master-detail:
```xml
<dataSource name="Q_DETAIL">
  <group name="G_HEADER">
    <!-- header columns -->
    <group name="G_LINES">
      <!-- line columns — detail of G_HEADER -->
    </group>
  </group>
</dataSource>
```

#### PL/SQL Triggers (`<programUnits>`)

```xml
<function name="beforereport">
  <textSource><![CDATA[
    function BeforeReport return boolean is
    begin
      srw.user_exit('FND SRWINIT');
      -- parameter preprocessing, dynamic WHERE clause construction
      return true;
    end;
  ]]></textSource>
</function>

<function name="cf_totalformula" returnType="number">
  <textSource><![CDATA[
    function CF_TotalFormula return Number is
    begin
      return :cost * :quantity;
    end;
  ]]></textSource>
</function>
```

**Key things to extract from PL/SQL:**
1. `BeforeReport` — often builds dynamic WHERE clauses via lexical parameters (`&WHERE_CLAUSE`)
2. Formula functions — computed columns that need SQL equivalents
3. `SRW.USER_EXIT` calls — especially `FND FLEXSQL`, `FND FORMAT_CURRENCY` (flexfield and currency formatting)

#### Lexical Parameters

These are string substitution variables (not bind variables). They appear as `&NAME` in the SQL:

```sql
select ... from table where &WHERE_DAS_CLAUSE and &H_WHERE
```

The `BeforeReport` trigger typically builds these dynamically. They need to be converted to Blitz Report anchors or parameterized conditions.

## Phase 3: Read XML Publisher Data Templates

XML Publisher templates are already clean XML — no conversion needed.

### 3.1 Extract SQL Queries

```xml
<dataQuery>
  <sqlStatement name="Q_PARAMETERS">
    <![CDATA[SELECT :P_DATE param_date FROM sys.dual]]>
  </sqlStatement>
  <sqlStatement name="Q_MAIN">
    <![CDATA[SELECT inv.invoice_num, inv.invoice_amount
    FROM ap_invoices_all inv
    WHERE inv.org_id = :P_ORG_ID]]>
  </sqlStatement>
</dataQuery>
```

### 3.2 Extract Parameters

```xml
<parameters>
  <parameter name="P_ORG_ID" dataType="NUMBER"/>
  <parameter name="P_DATE" dataType="DATE" defaultValue="{$SYSDATE$}"/>
</parameters>
```

### 3.3 Extract Output Structure

```xml
<dataStructure>
  <group name="G_HEADER" source="Q_MAIN">
    <element name="INVOICE_NUM" value="INVOICE_NUM"/>
    <element name="TOTAL_AMOUNT" value="G_LINES.LINE_AMOUNT" function="SUM()"/>
    <group name="G_LINES" source="Q_LINES">
      <element name="LINE_AMOUNT" value="LINE_AMOUNT"/>
    </group>
  </group>
</dataStructure>
```

### 3.4 Check for PL/SQL Package

```xml
<dataTemplate defaultPackage="AP_SOME_RPT_PKG">
```

If `defaultPackage` is set, the report calls PL/SQL functions for computed columns. Read the package source:

```sql
select text from all_source
where name=:package_name and type='PACKAGE BODY'
order by line;
```

## Phase 4: Produce the Report Analysis Document (RAD)

### 4.1 Summary

```
Report: FADTXA (FA Tax Reserve Ledger)
Module: Fixed Assets (FA)
Type: Oracle Reports (.rdf) / XML Publisher
Concurrent Program: FADTXA
Executable: FADTXA.rdf
Application: OFA
```

### 4.2 Parameters

| # | Name | Prompt | Type | Required | Default | Value Set |
|---|------|--------|------|----------|---------|-----------|
| 1 | P_BOOK | Book | Char | Y | — | FA_BOOK |
| 2 | P_PERIOD | Period | Char | Y | — | FA_PERIOD |
| 3 | P_CATEGORY | Category | Char | N | — | — |

### 4.3 SQL Queries

For each query, document:
- **Query name** (Q_MAIN, Q_DETAIL, etc.)
- **Full SQL text** — complete with all joins and conditions
- **Bind variables** — which parameters are referenced
- **Lexical parameters** — `&NAME` substitutions and how they're built in BeforeReport

### 4.4 Output Columns

| # | Column | Source | Type | Width | Formula/Summary |
|---|--------|--------|------|-------|-----------------|
| 1 | ASSET_NUMBER | Q_MAIN.ASSET_NUMBER | Char | 15 | — |
| 2 | COST | Q_MAIN.COST | Number | 20 | — |
| 3 | TOTAL_COST | CS_COST_SUM | Number | 20 | SUM(COST) by G_BOOK |
| 4 | FORMATTED_AMT | CF_FORMAT | Char | 30 | FND FORMAT_CURRENCY |

### 4.5 Groups and Breaks

| Group | Parent | Source Query | Break Column | Aggregates |
|-------|--------|-------------|--------------|------------|
| G_BOOK | — | Q_MAIN | BOOK_TYPE_CODE | — |
| G_ASSET | G_BOOK | Q_MAIN | ASSET_NUMBER | SUM(COST) |

### 4.6 PL/SQL Logic

Document:
- `BeforeReport` — dynamic WHERE clause construction, parameter validation
- Formula functions — each with its SQL equivalent
- `SRW.USER_EXIT` calls — flexfield handling, currency formatting
- `AfterReport` — cleanup, `FND SRWEXIT`

### 4.7 Blitz Conversion Notes

Based on the analysis, note:
- Which queries to consolidate (UNION ALL vs subqueries), keeping a `union` inside an original query as `union` over its key, and leaving out sections a group filter or format trigger never prints
- Which formulas can be replaced with SQL expressions
- Which lexical parameters become Blitz anchors
- Which SRW user exits need `xxen_util` function equivalents:
  - `FND FLEXSQL` → `xxen_util.segments()` or KFF column references
  - `FND FORMAT_CURRENCY` → `to_char()` with format mask
  - `FND SRWINIT` / `FND SRWEXIT` → `fnd_global.apps_initialize()` (handled by Blitz framework)
- Master-detail groups → flattened with joins or kept as separate SQL (depends on layout)
- Any concurrent program parameters that need Blitz LOVs

### 4.8 Request Group Assignments

```sql
-- Find which responsibilities can run this report
select distinct
frg.request_group_name,
fa.application_short_name
from
fnd_request_groups frg,
fnd_request_group_units frgu,
fnd_application fa,
fnd_concurrent_programs fcp
where
frg.request_group_id=frgu.request_group_id and
frg.application_id=fa.application_id and
fcp.concurrent_program_name=:program_name and
(frgu.unit_application_id=fcp.application_id and
 frgu.request_unit_id=fcp.concurrent_program_id and
 frgu.request_unit_type='P'
 or
 frgu.unit_application_id=fcp.application_id and
 frgu.request_unit_type='A')
order by
frg.request_group_name
```

## Quality Checklist

Before producing the RAD, verify:
- [ ] All SQL queries extracted completely (no truncation)
- [ ] All parameters documented with type and default
- [ ] Field inventory generated (`${CLAUDE_PLUGIN_ROOT}/skills/migrate-custom-reports/field_inventory.py <folder>`): every printed field traced to its source
- [ ] All formula functions have SQL equivalents identified, including the placeholders they assign and what their exception handlers return
- [ ] Group filters, parent-child links and format triggers that can return FALSE listed with the rows or sections they hide
- [ ] For a PL/SQL program, every variable the loop writes to the output traced to its assignments (cursor literals such as `0 basic` are filled there)
- [ ] Lexical parameters traced back to BeforeReport logic
- [ ] Master-detail hierarchy is clear
- [ ] SRW.USER_EXIT calls identified and mapped to xxen_util functions
- [ ] Request group assignments captured

## Handoff

The RAD is consumed by:
- **convert-bip-and-rdf-reports-to-blitz** skill — for building the Blitz Report XML
- **report-tester** — for running and comparing the original vs Blitz output
