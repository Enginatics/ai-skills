---
name: oracle-forms-analyzer
description: Analyze Oracle EBS standard forms to extract field definitions, validation logic, LOV queries, defaulting rules, and API calls. Use when building or reviewing a Blitz Upload that replicates Oracle form functionality.
metadata:
  title: Oracle Forms Analyzer
  category: Upload Development
---

# Oracle Forms Analyzer Skill

Extracts comprehensive field-level and form-level metadata from Oracle EBS entry forms — both **Oracle Forms** (.fmb/.fmx) and **OAF web pages** (HTML/self-service) — and their underlying database packages. The output is a structured **Form Analysis Document** used as input by the upload-builder and upload-validator.

## When to Use

- Before building a new Blitz Upload — to understand what the form does
- When reviewing an existing upload — to compare against the form
- When user asks to analyze a specific Oracle form or OAF page

## Arguments

$ARGUMENTS should contain the Oracle form name (e.g., "FAXASSET", "APXINWKB") or OAF page description (e.g., "iProcurement requisition", "iExpenses"), and optionally the EBS module context.

## Form Type Detection

Determine whether the target is an **Oracle Forms** entry form or an **OAF** (self-service web) page:

| Indicator | Oracle Forms | OAF Page |
|-----------|-------------|----------|
| File extension | `.fmb` / `.fmx` | `*PG.xml` page definitions |
| Location | `$AU_TOP/forms/US/` | `$APPL_TOP/{mod}/mds/` |
| UI technology | Java applet (thick client) | HTML (browser-based) |
| Navigation | Responsibilities → Navigator | Self-service menu / HTML links |
| Module tendency | FA, AP, AR, GL, PO, INV, WIP | iProcurement, iExpenses, iSupplier, SSHR |

If unsure, check both locations. Some modules have both (e.g., PO has Forms for buyers and OAF for requestors).

## Common Form Names by Module

### Oracle Forms (.fmb)

| Module | Form | Purpose |
|--------|------|---------|
| FA | FAXASSET | Asset Workbench (additions, books, assignments) |
| FA | FAXASSIG | Asset Assignments |
| AP | APXINWKB | Invoice Workbench |
| AP | APXVDMVD | Suppliers |
| AR | ARXTWMAI | Transactions |
| AR | ARXRWMAI | Receipts |
| PO | POXRQERQ | Requisitions |
| PO | POXPOEPO | Purchase Orders |
| INV | INVTXSFR | Material Transactions |
| GL | GLXJEENT | Journal Entry |
| WIP | WIPDJMEN | Discrete Jobs |
| HR | PERWSHRG | People (HRMS) |
| QA | QABORDFR | Quality Results |
| CE | CEBALREV | Bank Statements |

### OAF Pages (Self-Service)

| Module | Page Path | Purpose |
|--------|-----------|---------|
| ICX/POR | `icx/por/req/webui/CheckoutLinesPG` | iProcurement Requisitions |
| ICX/POR | `icx/por/req/webui/ShoppingCartPG` | iProcurement Shopping Cart |
| AP/OIE | `ap/oie/webui/ExpenseReportPG` | iExpenses |
| POS | `pos/supplier/webui/SupplierPG` | iSupplier Portal |
| PER/SSHR | `per/sshr/webui/PersonalInfoPG` | Self-Service HR |
| PER/SSHR | `per/sshr/webui/AbsencePG` | Self-Service Absence |
| ONT | `ont/oeoh/webui/OrderInformationPG` | Order Management HTML |
| CHV | `chv/webui/SchedulePG` | Supplier Scheduling |

## Phase 1: Locate and Convert Form Source Files

### 1.1 Find the Form File

The `.fmb` (Forms Module Binary) is a binary file — it **cannot be read directly**. It must first be converted to a readable format.

The source files are on the apps tier of the EBS instance (`$AU_TOP/forms/US`). Connect to it as described in `blitz-environment.md`, or ask the DBA to copy the files.

```bash
# Source the apps tier environment file first

# Forms source (.fmb) is in $AU_TOP/forms/US/
find $AU_TOP/forms/US -name "FORMNAME.fmb" 2>/dev/null

# Common locations by module:
# $AU_TOP/forms/US/FAXASSET.fmb (FA)
# $AU_TOP/forms/US/APXINWKB.fmb (AP)
# $AU_TOP/forms/US/ARXTWMAI.fmb (AR)
```

### 1.2 Convert .fmb to Readable XML

**Preferred method**: Use Oracle's `frmf2xml.sh` (Forms2XML) tool:

```bash
# Copy .fmb to /tmp (always work in /tmp to keep the server clean)
cp $AU_TOP/forms/US/FORMNAME.fmb /tmp/
cd /tmp

# Convert to XML (outputs FORMNAME.xml in current directory)
frmf2xml.sh FORMNAME.fmb
```

**Known issue**: `frmf2xml.sh` may fail with `"Error initialising the Forms Jdapi: _jni_initialize: Failed to create new forms context"` if the server has no X11 display. Workarounds:
1. Run with Xvfb if installed: `Xvfb :99 & export DISPLAY=:99 && frmf2xml.sh FORMNAME.fmb`
2. Run from a machine with Oracle Forms Builder installed (Windows/GUI)

**Fallback method**: If `frmf2xml.sh` fails, use `strings` to extract readable content from the binary:

```bash
# Extract all readable strings (PL/SQL triggers, SQL queries, field names)
strings /tmp/FORMNAME.fmb > /tmp/FORMNAME_strings.txt

# Search for specific content:
strings /tmp/FORMNAME.fmb | grep -i 'when-validate\|when-new-record\|pre-insert\|on-insert'
strings /tmp/FORMNAME.fmb | grep -i 'select.*from'
strings /tmp/FORMNAME.fmb | grep -i 'book_type_code\|asset_number\|category'
```

The `strings` output is unstructured but contains all trigger code, LOV SQL queries, field names, and PL/SQL logic embedded in the form. It's sufficient for analysis when the XML conversion is unavailable. It drops every line shorter than four characters, so a lone `*/` disappears and commented-out code reads as active: check the comment boundaries before relying on a condition.

**EBS 11i (Forms 6i)** has no `frmf2xml.sh`. Convert the form to its text format with `f60gen` on the 11i instance's apps tier, which gives the prompts, canvases, tab pages and positions that `strings` cannot:

```bash
mkdir -p /tmp/fmt && cp $AU_TOP/forms/US/FORMNAME.fmb /tmp/fmt/
export FORMS60_PATH=$AU_TOP/forms/US:$FORMS60_PATH   # APPSTAND.fmb must resolve
export DISPLAY=<a running X display, e.g. Xvfb>
f60gen module=/tmp/fmt/FORMNAME.fmb userid=apps/$APPS_PWD script=yes module_type=form batch=yes
```

`/tmp/fmt/FORMNAME.fmt` lists every object as a `FRM50_IDFO` record (`IDFOS_OID` id, `IDFOS_TYP` type, `IDFOS_NAM` name, `IDFOS_OOI` owning block) followed by its properties as `F50T` (text), `F50N` (number), `F50B` (boolean) and `F50O` (object reference) records keyed by property number. Blocks are type 7, items 30, tab pages 88 (label in text property 151, in tab order by object id). Item text properties: 211 name, 394 prompt, 151 check box label, 33 canvas or tab page (empty: the item is not displayed), 165 list of values; number properties 372 and 373 are the X and Y position. A record group is a type 64 object whose query is one of its text properties. Sort a block's displayed items by canvas, then Y, then X for the visual order.

**For PL/SQL libraries (.pll)**: Similar approach — `.pll` files are also binary. Use `strings` as a fallback or convert using the Forms Builder GUI.

**Cleanup**: Always remove temp files from `/tmp` when done.

### 1.3 Find Associated PL/SQL Libraries

Forms reference PL/SQL libraries (.pll) with shared logic:

```bash
ls $AU_TOP/resource/*.pll
ls $FA_TOP/resource/*.pll
```

Common: `FAXOLSTD.pll`, `APPCORE.pll`, `CUSTOM.pll`

### 1.4 Find the Underlying Database Package

The form calls a database package for DML. Find it by:
1. Check ON-INSERT, ON-UPDATE, ON-DELETE triggers for `package.procedure` calls
2. Common naming: form FAXASSET → `FA_MASS_ADDITIONS_PKG`, `FA_ADDITION_PUB`, etc.

```sql
-- Search for packages related to a module
select object_name, object_type from all_objects
where object_name like 'FA_%PKG' and object_type='PACKAGE'
order by object_name;

-- Search for API packages
select object_name from all_objects
where object_name like 'FA_%PUB' and object_type='PACKAGE'
order by object_name;
```

## Phase 1-OAF: Locate and Read OAF Page Files

**Use this phase instead of Phase 1 when the target is an OAF self-service page.**

### 1-OAF.1 Find the Page Definition (PG.xml)

OAF page definitions are XML files in the JRAD metadata store (mds):

```bash
# Source the apps tier environment file first

# Page definitions are in $APPL_TOP/{module_short}/12.0.0/mds/
# Example: iProcurement checkout lines
find $APPL_TOP/icx/12.0.0/mds -name "*Checkout*PG.xml" 2>/dev/null

# Common module paths:
# $APPL_TOP/icx/12.0.0/mds/por/req/webui/     (iProcurement)
# $APPL_TOP/ap/12.0.0/mds/oie/webui/           (iExpenses)
# $APPL_TOP/pos/12.0.0/mds/supplier/webui/     (iSupplier)
# $APPL_TOP/per/12.0.0/mds/sshr/webui/         (Self-Service HR)

# If module is unknown, search broadly:
find $APPL_TOP/*/12.0.0/mds -name "*KEYWORD*PG.xml" 2>/dev/null
```

**Page XML files are fully readable XML** — no conversion needed (unlike .fmb files).

### 1-OAF.2 Find View Objects (VO.xml) and Application Modules (AM.xml)

These contain the SQL queries and data model:

```bash
# VOs and AMs are in $JAVA_TOP/oracle/apps/{module}/{submodule}/server/
# Example: iProcurement
ls $JAVA_TOP/oracle/apps/icx/por/req/server/*.xml

# Key files to look for:
# *VO.xml  — View Objects (contain SQL queries)
# *AM.xml  — Application Modules (VO hierarchy)
# *VOImpl.class — compiled Java (no source available)
```

### 1-OAF.3 Read and Analyze the Page XML

The PG.xml defines the complete UI layout. Key elements to extract:

```xml
<!-- Page-level: which AM backs this page -->
<oa:pageLayout amDefName="oracle.apps.icx.por.req.server.RequisitionAM">

<!-- Field definitions: type, prompt, VO binding -->
<oa:messageTextInput id="Description" prompt="Description"
    viewName="ReqLinesVO" viewAttr="ItemDescription"
    required="yes" maximumLength="240"/>

<oa:messageLovInput id="CategoryLov" prompt="Category"
    viewName="ReqLinesVO" viewAttr="CategoryDescription"
    externalListOfValues="/oracle/apps/icx/por/req/webui/CategoryLovRN"
    required="yes" selectiveSearchCriteria="true"/>

<oa:messageCheckBox id="TaxableFlag" prompt="Taxable"
    viewName="ReqLinesVO" viewAttr="TaxableFlag"
    checkedValue="Y" uncheckedValue="N"/>

<!-- Hidden fields (formValue = not displayed but passed to server) -->
<oa:formValue id="CategoryId" viewName="ReqLinesVO" viewAttr="CategoryId"/>

<!-- Regions define layout groupings (like form tabs) -->
<oa:stackLayout id="LineDetailsRN">
  <!-- child items here -->
</oa:stackLayout>
```

**OAF element types → form equivalents:**

| OAF Element | Oracle Forms Equivalent | Notes |
|-------------|------------------------|-------|
| `messageTextInput` | Text Item | Standard text entry |
| `messageLovInput` | Text Item + LOV | LOV attached |
| `messageChoice` | List Item (poplist) | Dropdown |
| `messageCheckBox` | Check Box | Yes/No |
| `messageDateField` | Date Item | Date picker |
| `formValue` | Hidden Item | Not visible, passes data |
| `messageStyledText` | Display Item | Read-only |
| `advancedTable` | Multi-record block | Tabular data |
| `stackLayout` / `flowLayout` | Tab / Canvas | Layout regions |

### 1-OAF.4 Read View Object SQL

VO XML files contain the actual SQL query:

```xml
<!-- PoRequisitionLinesVO.xml -->
<ViewObject Name="PoRequisitionLinesVO">
  <SQLQuery><![CDATA[
    select requisition_line_id, item_description, category_id,
           unit_meas_lookup_code, quantity, unit_price, amount,
           suggested_vendor_name, org_id
    from po_requisition_lines_all
    where requisition_header_id = :1
  ]]></SQLQuery>

  <!-- Attribute definitions (column metadata) -->
  <ViewAttribute Name="RequisitionLineId" ColumnName="REQUISITION_LINE_ID"
      Type="oracle.jbo.domain.Number" IsPersistent="false"/>
  <ViewAttribute Name="ItemDescription" ColumnName="ITEM_DESCRIPTION"
      Type="oracle.jbo.domain.String" UpdateableFlag="Always"/>
</ViewObject>
```

**What to extract from VO XML:**
1. **SQL query** — the base table(s), joins, WHERE clause
2. **Attribute definitions** — column name, Java type, updateable flag
3. **Bind variables** — parameterized WHERE conditions
4. **Entity references** — which Entity Object handles DML

### 1-OAF.5 Understand LOVs in OAF

OAF LOVs are defined as separate Region XML files (`*LovRN.xml`) or inline:

```bash
# Find LOV region definitions
find $APPL_TOP/*/12.0.0/mds -name "*LovRN.xml" -path "*/req/*" 2>/dev/null

# LOV regions define:
# - lovMappings (which VO attrs pass to/from the LOV)
# - Search criteria
# - Result columns displayed
```

The LOV mapping tells you:
- **lovInputSourceId** — which page field's value is passed as search criteria
- **returnItemId** — which page field receives the selected value
- **criteriaItemId** — search criteria VO attribute

### 1-OAF.6 Validation Logic in OAF

OAF validation lives in three places (check all):

1. **VO.xml declarative rules** — `<ViewAttribute ... Mandatory="true" />`, value constraints
2. **Entity Object validation** — `*EOImpl.class` (compiled, read package body SQL instead)
3. **Server-side PL/SQL packages** — same as Oracle Forms, the API packages do the real validation. This is the most important source.

**Since Java source (.java) is not available** on the server (only compiled .class), focus on:
- Declarative metadata from the XML files (field types, mandatory, LOV bindings)
- The underlying PL/SQL API packages (same as Phase 3 for Oracle Forms)
- Database table constraints and triggers

**Continue to Phase 2** to extract field details from the PG.xml, then **Phase 3** to analyze the API packages.

---

## Phase 2: Extract Form Metadata

> **OAF pages**: The same metadata needs to be extracted, but from different sources. Use the PG.xml for field inventory (item elements = fields), VO.xml for data types and SQL, and LovRN.xml for LOVs. The output format (FAD sections 4.1-4.7) is identical regardless of form type.

### 2.1 Data Blocks

For each data block, document:
- Block Name, Base Table, Record Count (single/multi)
- Query/Insert/Update/Delete Allowed
- WHERE Clause, ORDER BY
- Master-detail relationships

### 2.2 Fields (Items)

For EVERY visible/editable item in each data block, extract:

| Attribute | What to Extract | Why It Matters |
|-----------|----------------|----------------|
| **Item Name** | Internal name (e.g., `ASSET_NUMBER`) | Maps to upload column |
| **Prompt/Label** | Displayed text (e.g., "Asset Number") | Upload column alias should match |
| **DB Column** | Underlying table column | Maps to SQL select |
| **Data Type** | Char, Number, Date | Upload DATA_TYPE |
| **Max Length** | Maximum input length | Validation constraint |
| **Mandatory** | See classification below | Upload REQUIRED flag |
| **Canvas/Tab** | Which tab page it appears on | Column grouping/order |
| **Visual Position** | Exact position in the form layout (see below) | Upload column order |
| **LOV Name** | Attached LOV | Upload LOV needed |
| **LOV Validation** | LOV validates? (Y/N) | VALIDATE_FROM_LIST_DSP |
| **Default Value** | Static default or trigger-based | Upload DEFAULT_VALUE |
| **Enabled/Visible** | When enabled/hidden? | Conditional logic |
| **Format Mask** | Display format | Data formatting |

**CRITICAL — Visual Field Order (from .fmb XML):**
The upload column order MUST match the form's visual layout. Extract this from the converted form XML, NOT from guesswork.

**Method 1: From frmf2xml output (preferred)**
The converted XML contains canvas coordinates for each item:
```xml
<Item Name="RECEIPT_METHOD_NAME" ... XPosition="10" YPosition="20" Canvas="MAIN_CANVAS" .../>
<Item Name="RECEIPT_NUMBER" ... XPosition="10" YPosition="50" Canvas="MAIN_CANVAS" .../>
```
Sort items by: Canvas → TabPage → YPosition → XPosition to get the visual order.

**Method 2: From `strings` output (fallback)**
When XML conversion isn't available, the `strings` output preserves item ordering within blocks. Items appear in their internal sequence order, which generally follows the tab order. Cross-reference with Prompt text to map internal names to user-facing labels.

**Method 3: From a form screenshot**
If a screenshot is available, read fields top-to-bottom, left-to-right within each region.

**Steps:**
1. **Group by canvas/tab page** — header canvas first, then each detail tab in order
2. **Sort within each canvas** by Y coordinate (top→bottom), then X coordinate (left→right)
3. **Note visual groupboxes** — form frame labels (e.g., "Receipt", "Customer", "Remittance Bank")
4. **Number each field sequentially** — this number becomes the upload column order

**CRITICAL — Use Prompts, not internal names:**
- The form's **Prompt** attribute (e.g., "Receipt Method", "GL Date") is what users see
- Upload column aliases MUST match these prompts, NOT the internal database column names
- Extract prompts from the XML: `<Item Name="RECEIPT_METHOD_ID" Prompt="Receipt Method" .../>`
- When a prompt differs from the DB column (e.g., Prompt="Location" for column CUSTOMER_SITE_USE_ID), always use the prompt
- If `strings` fallback is used, prompts appear near their item names in the output

**CRITICAL — Form Data Entry Workflow:**
Document the order in which users MUST enter data, noting dependencies:
- Which fields must be filled before others become enabled or their LOV works?
- Example: "Customer must be entered before the Invoice LOV shows results"
- Example: "Book must be selected before Category LOV is filtered"
- Look for WHEN-VALIDATE-ITEM triggers that enable/disable other items
- Look for LOV WHERE clauses that reference other form items (`:block.item`)
- This directly affects LOV query design — dependent LOVs should use **required joins** (not `is null or` patterns that prevent index usage)

**Mandatory classification** — be precise:
- `REQUIRED` — form raises error if empty on save
- `CONDITIONAL` — mandatory only when another field has a specific value (document the condition)
- `OPTIONAL` — can be left blank
- `SYSTEM` — set by the system, user cannot enter (creation_date, created_by, etc.)

**Default value — document EXACTLY:**
- Hardcoded value: `'STANDARD'`
- Profile option: `fnd_profile.value('ORG_ID')`
- Sequence: `FA_MASS_ADDITIONS_S.NEXTVAL`
- Derived from other field: `DEPRECIATION_METHOD derived from CATEGORY via fa_category_books`
- Trigger-based: describe the trigger code

### 2.3 Triggers — The Most Critical Part

Extract ALL triggers at item, block, and form level.

#### Item-Level Triggers

| Trigger | What It Does | Upload Equivalent |
|---------|-------------|-------------------|
| **WHEN-VALIDATE-ITEM** | Validates field value | `UPLOAD_EXCEL_VALIDATION` function |
| **WHEN-LIST-CHANGED** | List item changes | DEFAULT_VALUE dependency |
| **POST-CHANGE** | After value changes | DEFAULT_VALUE dependency |

**What to extract from WHEN-VALIDATE-ITEM:**
1. **Validation SQL**: What query does it run?
2. **Error message**: What error on failure?
3. **Cross-field updates**: Does it populate OTHER items? (This IS the defaulting logic)
4. **Conditional logic**: Does validation depend on other field values?

Example extraction:
```
WHEN-VALIDATE-ITEM on CATEGORY:
  1. Query fa_categories_b where category_id=:ADDITIONS.CATEGORY_ID
  2. If found: set DEPRECIATE_FLAG, LIFE_IN_MONTHS, DEPRN_METHOD from fa_category_books
  3. If not found: raise error "Invalid Category"
  → Upload: DEFAULT_VALUE on Depreciate, Life, Method dependent on Category
  → Upload: Validation in validate_asset function
```

#### Block-Level Triggers

| Trigger | What It Does | Upload Equivalent |
|---------|-------------|-------------------|
| **WHEN-VALIDATE-RECORD** | Cross-field validation | validate function (concatenated errors) |
| **WHEN-NEW-RECORD-INSTANCE** | Defaults on new record | DEFAULT_VALUE (unconditional) |
| **PRE-INSERT** | Logic before insert | Processing procedure (create path) |
| **PRE-UPDATE** | Logic before update | Processing procedure (update path) |
| **ON-INSERT** | Override DML for insert | Processing procedure API call |
| **ON-UPDATE** | Override DML for update | Processing procedure API call |
| **POST-QUERY** | After querying record | Main SQL (joins/transforms) |

**What to extract from WHEN-VALIDATE-RECORD:**
1. All cross-field checks (field A requires field B, date range validations)
2. Conditional requirements (field X required only when field Y='VALUE')
3. Business rules (amount positive, quantity matches UOM)

**What to extract from WHEN-NEW-RECORD-INSTANCE:**
1. Default values and their source (parent block? profile? system date? period end?)
2. Conditional defaults based on mode/context

### 2.4 LOV Definitions

For each LOV, extract:
- **LOV Name** and **Record Group** name
- **Full SQL Query** — including all WHERE conditions, references to form items, ORDER BY
- **Column Mapping** — which LOV column maps to which form item
- **Dependent Filters** — does the query reference other form items (`:block.item`)?

Example:
```sql
-- LOV: CATEGORY_LOV (dependent on Book)
select fcb.category_id, fcbk.concatenated_segments, fcbk.description
from fa_categories_b fcb, fa_categories_b_kfv fcbk, fa_category_books fcbo
where fcb.category_id=fcbk.category_id
and fcbo.category_id=fcb.category_id
and fcbo.book_type_code=:BOOKS.BOOK_TYPE_CODE  -- DEPENDENT on Book
and fcb.enabled_flag='Y'
and trunc(sysdate) between nvl(fcb.start_date_active,trunc(sysdate))
                        and nvl(fcb.end_date_active,trunc(sysdate))
order by fcbk.concatenated_segments
```

### 2.5 Key Flexfields (KFF)

For each KFF field, extract:

| Attribute | What to Extract |
|-----------|----------------|
| **Flex Code** | e.g., 'GL#', 'LOC#', 'CAT#' |
| **Application ID** | e.g., 101 (GL), 140 (FA) |
| **Structure Number** | id_flex_num (may be dynamic) |
| **Segments** | Count, names, value sets |
| **Delimiter** | Segment separator |
| **Alias Support** | Does form support shorthand aliases? |
| **Dynamic Insert** | Can users create new combinations? |

Query flex structure:
```sql
select fifsg.segment_name, fifsg.segment_num, fifsg.application_column_name,
  fifsg.required_flag, ffvs.flex_value_set_name
from fnd_id_flex_segments fifsg, fnd_flex_value_sets ffvs
where fifsg.application_id=:app_id and fifsg.id_flex_code=:flex_code
and fifsg.id_flex_num=:flex_num and fifsg.enabled_flag='Y'
and ffvs.flex_value_set_id=fifsg.flex_value_set_id
order by fifsg.segment_num;

select fifst.concatenated_segment_delimiter
from fnd_id_flex_structures fifst
where fifst.application_id=:app_id and fifst.id_flex_code=:flex_code
and fifst.id_flex_num=:flex_num;

select count(*) from fnd_shorthand_flex_aliases fsfa
where fsfa.application_id=:app_id and fsfa.id_flex_code=:flex_code
and fsfa.id_flex_num=:flex_num and fsfa.enabled_flag='Y';
```

### 2.6 Descriptive Flexfields (DFF)

Check if form has DFF support (ATTRIBUTE_CATEGORY + ATTRIBUTE1..15):

```sql
select fdfv.title, fdfv.application_table_name
from fnd_descriptive_flexs_vl fdfv
where fdfv.application_id=:app_id
and fdfv.descriptive_flexfield_name=:dff_name;
```

## Phase 3: Analyze Database Packages

### 3.1 Find Package Source

```sql
select text from all_source
where name=:package_name and type='PACKAGE BODY'
order by line;
```

### 3.2 Extract API Procedures

Document:
1. **Procedure signature**: All parameters with types and IN/OUT
2. **Mandatory parameters**: Which cannot be null?
3. **Validation logic**: What checks does it perform?
4. **DML operations**: What tables does it insert/update?
5. **Error handling**: Status + message? Exceptions? FND message stack?

### 3.3 Interface Tables (if applicable)

| Form | Interface Table | Processor |
|------|----------------|-----------|
| FAXASSET | FA_MASS_ADDITIONS | FAMAPT |
| POXPOEPO | PO_HEADERS_INTERFACE | PDOI (POXPDOI) |
| INVTXSFR | MTL_TRANSACTIONS_INTERFACE | INCTCM |
| WIPDJMEN | WIP_JOB_SCHEDULE_INTERFACE | WIP Mass Load |
| CEBALREV | CE_STATEMENT_HEADERS_INT | ARPLABIM |

For interface-based: document ALL interface columns, processor concurrent program, error table(s).

### 3.4 Record Identification

How does the form uniquely identify an existing record for UPDATE:

```
Primary Key Column(s): e.g., ASSET_ID, BOOK_TYPE_CODE
Business Key (user-visible): e.g., ASSET_NUMBER + BOOK
Lookup SQL: select fa.asset_id from fa_additions fa where fa.asset_number=:value
```

### 3.5 Delete / Close / Cancel Logic

```
Can records be deleted? YES/NO
Delete restrictions: conditions that prevent deletion
Soft delete? Y flag or status code used
Alternatives to delete: Cancel, Close, Void — document each
API for cancel/close: package.procedure
```

## Phase 4: Produce the Form Analysis Document

### 4.1 Summary

```
Form: FAXASSET (FA Asset Workbench)
Module: Fixed Assets (FA)
Base Tables: FA_ADDITIONS_B, FA_BOOKS, FA_DISTRIBUTION_HISTORY
API/Interface: FA_MASS_ADDITIONS (interface) → FAMAPT (processor)
DFF: FA_ADDITIONS (ATTRIBUTE_CATEGORY + ATTRIBUTE1..15)
KFFs: GL# (Expense Account), LOC# (Location), CAT# (Category)
```

### 4.2 Visual Field Order

**CRITICAL — this section defines the upload column order.**

Document fields in the exact visual layout order (top-to-bottom, left-to-right within each region/tab):

```
Region: [Header/Detail Tab Name]
 #  Field Label              Block.Item              Type    Req  LOV
 1  Receipt Method           RECEIPTS.RECEIPT_METHOD Char    Y    RECEIPT_METHOD_LOV
 2  Receipt Number           RECEIPTS.RECEIPT_NUMBER Char    N    —
 3  Receipt Amount           RECEIPTS.AMOUNT         Number  Y    —
 ...
Region: [Detail - Main Tab]
 7  Customer Name            DETAIL.CUSTOMER_NAME    Char    N    CUSTOMER_LOV
 ...
```

### 4.2b Data Entry Workflow

Document field entry dependencies — which fields must be populated before others work:
```
1. Receipt Method → required first (determines bank account defaults)
2. Customer Name/Number → must be entered before Invoice LOV works
3. Book → must be selected before Category LOV is filtered
```
This directly impacts upload LOV design: dependent LOVs should use **required joins** (not `is null or` patterns that disable index usage).

### 4.3 Field Inventory (Detailed)

| # | Block | Item | Label | Type | Len | Req | LOV | Default | Validates |
|---|-------|------|-------|------|-----|-----|-----|---------|-----------|
| 1 | BOOKS | BOOK_TYPE_CODE | Book | Char | 30 | Y | BOOK_LOV | — | WVI |
| 2 | ADDITIONS | ASSET_NUMBER | Asset Number | Char | 15 | N | — | Auto-gen | — |
| ... | | | | | | | | | |

### 4.4 Defaulting Map

| Target Field | Source | Trigger | Condition |
|-------------|--------|---------|-----------|
| DATE_PLACED_IN_SERVICE | fa_deprn_periods.calendar_period_close_date | WNRI | Book selected |
| DEPRECIATION_METHOD | fa_category_books.deprn_method | WVI on CATEGORY | Category valid |

### 4.5 Validation Map

| Validation | Trigger | Fields | Error Message | SQL/Logic |
|-----------|---------|--------|---------------|-----------|
| Category exists | WVI | category_id | "Invalid Category" | `select from fa_categories_b` |
| Life > 0 | WVR | life, depreciate | "Life required" | `if depreciate='Y' and life is null` |

### 4.6 LOV Map

| LOV Name | Field | SQL Query | Dependent On | Filters |
|----------|-------|-----------|-------------|---------|
| BOOK_LOV | BOOK | `select from fa_book_controls` | — | `date_ineffective is null` |
| CATEGORY_LOV | CATEGORY | `select from fa_categories_b_kfv` | Book | `book_type_code=:book` |

### 4.7 KFF Map

| KFF | Flex Code | App ID | Structure | Segments | Delimiter | Aliases | Dynamic Insert |
|-----|-----------|--------|-----------|----------|-----------|---------|---------------|
| Expense Account | GL# | 101 | chart_of_accounts_id | 5 | . | Yes | No |
| Location | LOC# | 140 | 101 | 4 | - | Yes | Yes |

### 4.8 API/Interface Details

Document the exact API call or interface table insert, including all parameters/columns.

### 4.9 Record Identification

```
Primary Key: ASSET_ID
Business Key: ASSET_NUMBER + BOOK_TYPE_CODE
Lookup SQL: select fa.asset_id from fa_additions fa where fa.asset_number=:asset_number
```

### 4.10 Delete / Cancel Logic

Document if records can be deleted, cancelled, closed, or voided — and which API to use.

### 4.11 Upload Design Recommendations

Based on the analysis, recommend:
- Which form fields to expose as upload columns (vs system-set)
- Fields that should be read-only in upload
- Suggested default values for upload parameters
- Identified risks / tricky validations the builder must handle
- Which actions to support: Create / Update / Delete

### 4.12 Open Questions

List any assumptions made where form source was unclear, so the developer can verify before building.

## Quality Checklist Before Handoff

Before producing the FAD, verify:
- Every mandatory field has a default or is exposed as an upload column
- Every LOV has its full SQL query documented
- Every cross-field dependency is documented
- The API package and procedure signature is confirmed
- Primary key and business key are both identified
- Initialization requirements (apps_initialize, mo_global) are noted
- At least one existing similar Blitz upload was referenced for patterns

## Tips for Accurate Analysis

1. **Don't rely on form layout alone** — real logic is in triggers and database packages
2. **Check PL/SQL libraries (.pll)** — significant logic may live there
3. **Test on live instance** — enter data in form and observe auto-population
4. **Check profile options** — defaults may come from `fnd_profile.value()` calls

## Handoff

The Form Analysis Document is consumed by:
- **upload-builder** — uses field inventory, LOVs, defaults, and API details to build the upload
- **upload-validator** — uses the document to compare against the built upload and find gaps
