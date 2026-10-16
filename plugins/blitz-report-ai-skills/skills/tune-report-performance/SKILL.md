---
name: tune-report-performance
description: Tune Blitz Report SQL performance by measuring buffer IO per row, identifying expensive components, and applying targeted fixes. Use when a report has high MB/row or slow execution.
metadata:
  title: Report Performance Tuning
  category: Testing and Tuning
---

# Blitz Report Performance Tuning Skill

Systematic approach to diagnose and fix Blitz Report SQL performance issues by measuring Oracle buffer IO per row.

## Performance Target

- **Target:** < 1 MB/row (128 buffer gets/row)
- **Rule of thumb:** num_tables × 4 blocks × 8KB = expected MB worst case
- **Excellent:** < 0.5 MB/row
- **Acceptable:** < 1 MB/row
- **Needs work:** > 1 MB/row
- **Critical:** > 5 MB/row

## Methodology: Incremental Build-Up

### Phase 1: Baseline Measurement

1. Read the report XML and understand the SQL structure
2. Deploy and run the report on the development instance with standard parameters
3. Measure buffer_gets from v$sql:

```sql
select s.sql_id, s.buffer_gets, s.rows_processed,
round(s.buffer_gets/nullif(s.rows_processed,0)) gets_per_row,
round(s.buffer_gets/nullif(s.rows_processed,0)*8/1024,1) mb_per_row
from v$sql s
where s.sql_text like '<first_words_of_sql>%'
and s.parsing_schema_name='APPS'
and s.last_active_time>sysdate-1/24
and s.rows_processed>100
order by s.last_active_time desc;
```

**Important:** v$sql.buffer_gets INCLUDES recursive SQL from PL/SQL function calls (e.g. xxen_util.meaning, hz_format_pub.format_address, xxen_util.segments_description).

### Phase 2: Isolate Expensive Components

Build up the query incrementally via standalone PL/SQL test scripts. Each test adds one more component and measures the cost delta.

**Test script template:**
```sql
set serveroutput on size 1000000
set feedback off
declare
l_bg1 number;
l_bg2 number;
l_rows number:=0;
l_dummy varchar2(4000);
begin
fnd_global.apps_initialize(user_id=><user_id>, resp_id=>20420, resp_appl_id=>1); --your own EBS user: select fu.user_id from fnd_user fu where fu.user_name='<YOUR_USER>'
mo_global.init('M');
mo_global.set_policy_context('M', null);

select ss.value into l_bg1 from v$mystat ss, v$statname sn
where ss.statistic#=sn.statistic# and sn.name='session logical reads';

for c in (
  -- TEST QUERY HERE
) loop
  l_dummy:=c.col1||c.col2;  -- touch all columns to force evaluation
  l_rows:=l_rows+1;
end loop;

select ss.value into l_bg2 from v$mystat ss, v$statname sn
where ss.statistic#=sn.statistic# and sn.name='session logical reads';

dbms_output.put_line('Test: '||l_rows||' rows, '||(l_bg2-l_bg1)||' gets = '
  ||round((l_bg2-l_bg1)/nullif(l_rows,0))||' per row = '
  ||round((l_bg2-l_bg1)/nullif(l_rows,0)*8/1024,1)||' MB/row');
end;
/
```

**Build-up strategy:**
1. **Test A:** Core tables only (FROM/WHERE, no functions) → establishes base join cost
2. **Test B:** Add PL/SQL function calls one at a time → identify expensive functions
3. **Test C:** Add each CTE/subquery one at a time → identify expensive data sources
4. **Test D:** Add each outer join one at a time → identify expensive lookups

For each test, compare gets_per_row to the previous test. A large jump (>10x) indicates the bottleneck.

### Phase 3: Root Cause Analysis

Common performance killers in Blitz Reports:

1. **CTE materialization when not needed**
   - Oracle materializes WITH (CTE) clauses even when outer join conditions make them unnecessary
   - Fix: Add parameter guard inside CTE WHERE clause: `:show_param='Y' and`
   - This makes Oracle skip the CTE entirely when the parameter is null

2. **Expensive Oracle views in CTEs**
   - `ce_bank_branches_v` — joins many internal tables, very expensive
   - `ap_supplier_sites_all` with DFF columns
   - Fix: Ensure these are gated by parameters

3. **Correlated subqueries in SELECT**
   - `coalesce(select max()..., select max()...)` patterns scan large tables per row
   - Fix: Make these optional via lexical parameter `&column_name`

4. **Non-cached PL/SQL functions**
   - `xxen_util.segments_description()` (4-param) — does dynamic SQL per call, NOT cached
   - `hz_format_pub.format_address()` — ~19 gets per call, NOT cached
   - `xxen_util.meaning()` — uses result_cache, negligible after warmup
   - Fix: For non-cached functions, consider making the columns optional

5. **Missing push_pred hints**
   - When outer joining to inline views/CTEs, Oracle may not push predicates
   - Fix: Add `/*+ push_pred(alias) */` hint

### Phase 4: Apply Fixes

1. **Parameter-gated CTE pattern:**
   ```sql
   q_expensive_data as (
     select ...
     from expensive_view ev, ...
     where :show_param='Y' and  -- gate: skips CTE when param is null
     ev.id=other.id and ...
   )
   ```

2. **Lexical parameter for expensive columns:**
   - Move expensive columns from inner subquery to outer SELECT via `&column_name` lexical
   - Add parameter with LOV Yes, DEFAULT_VALUE=Y (so columns appear by default)
   - Users can clear the parameter to exclude expensive columns

3. **Fix formatting while touching the code** — no spaces around `=`, `<>`, `(+)`

### Phase 5: Regression Test

**CRITICAL:** Always do a before/after comparison:

1. Run report BEFORE changes, save output Excel
2. Apply fixes, deploy, run report AFTER changes
3. Compare Excel files cell by cell:
   - Same number of columns? (check for accidentally removed columns)
   - Same data in matching columns? (check for logic bugs)
   - Acceptable performance improvement?

```python
# Quick column comparison
import openpyxl
wb1 = openpyxl.load_workbook('before.xlsx', read_only=True)
wb2 = openpyxl.load_workbook('after.xlsx', read_only=True)
h1 = [c.value for c in next(wb1.active.iter_rows(max_row=1)) if c.value]
h2 = [c.value for c in next(wb2.active.iter_rows(max_row=1)) if c.value]
print(f'Before: {len(h1)} cols, After: {len(h2)} cols')
missing = set(h1) - set(h2)
if missing: print(f'Missing columns: {missing}')
```

### Phase 6: Measure Final Performance

Run the report and check v$sql to confirm the improvement meets the target.

## Submitting Reports for Testing

```sql
declare
l_run_id number;
l_error varchar2(4000);
l_request_id number;
begin
fnd_global.apps_initialize(user_id=><user_id>, resp_id=>20420, resp_appl_id=>1);
mo_global.init('M');
mo_global.set_policy_context('M', null);
l_run_id:=xxen_api.create_run_id_('Report Name');
xxen_api.set_parameter_value_(p_parameter_name=>'Operating Unit', p_value=>'Vision Operations', p_run_id=>l_run_id);
xxen_api.set_parameter_value_(p_parameter_name=>'Level', p_value=>'Site Use', p_run_id=>l_run_id);
-- set ALL required/default parameters explicitly — API does not apply XML defaults
l_error:=xxen_report.report_submit_concurrent(xxen_report.report_id('Report Name'), l_run_id, l_request_id);
dbms_output.put_line(nvl(l_error, 'Request ID: '||l_request_id));
end;
```

**Important:** When submitting via API, you must set ALL required parameters and any parameters with defaults that affect the SQL. The API does NOT automatically apply `<DEFAULT_VALUE>` from the XML definition.

## Automated Performance Loop via DBA SGA Reports

When using the `convert-bip-and-rdf-reports-to-blitz` pipeline, performance analysis is automated using two Blitz Reports that query Oracle's `gv$sql` and `gv$sql_plan` views.

### DBA SGA SQL Performance Summary

Provides per-SQL metrics for a specific module (report). Submit with `Module Name` parameter set to the first 34 characters of the report name.

**Key columns to analyze:**

| Column | What It Tells You | Action Threshold |
|--------|-------------------|-----------------|
| Percentage | % of total module time | Focus on entries > 5% |
| Time Exec | Seconds per execution | > 60s needs optimization |
| IO Row | MB per row | > 1 MB needs optimization |
| Code | PL/SQL package name (if SQL from function) | Check for per-row functions |
| Executions | Times this SQL was executed | > 10K suggests per-row PL/SQL function |
| Rows Exec | Rows per execution | 1 row + high executions = per-row function |
| Sorts | Total sort operations | Very high = unnecessary GROUP BY or ORDER BY |

**Reading the results:**
1. **Main report SQL** — highest Percentage, has the report SQL text, shows overall Time Exec and IO Row
2. **PL/SQL function SQLs** — have `Code` column populated with function name, high Executions count
3. **Framework SQL** — from XXEN_REPORT package, usually low Percentage, ignore unless > 5%

### DBA SGA SQL Execution Plan History

Shows the full execution plan tree for a specific SQL_ID. Submit with `SQL Id` parameter.

**Key patterns to look for in the plan:**

| Pattern | Indicates | Fix |
|---------|-----------|-----|
| Multiple `VIEW PUSHED PREDICATE (VW_SSQ_N)` with same base tables | Duplicate correlated subqueries | Consolidate into single inline view with CASE WHEN |
| `TABLE ACCESS FULL` on large table | Missing index or wrong join | Check join conditions, add index hint |
| `HASH JOIN` where `NESTED LOOPS` expected | Optimizer chose wrong plan | Check statistics, consider hints |
| Very high Cardinality at `SORT GROUP BY` | Unnecessary aggregation | Remove GROUP BY, use template aggregation |
| Chain of `NESTED LOOPS OUTER` (7+ levels) | Many correlated subqueries | Consolidate subqueries that share same tables |

### Consolidation Patterns (from real-world optimization)

**Pattern: Multiple correlated subqueries → single inline view**

Real example: 6 tax subqueries against `jai_tax_det_factors + jai_tax_lines + oe_order_lines_all`, each filtering on a different `tax_rate_code` (SGST, CGST, IGST, FREIGHT, etc.). Each created a separate `VIEW PUSHED PREDICATE` in the plan.

Fix: Single inline view with conditional aggregation:
```sql
(select
oola.line_id,
sum(jtl.rounded_tax_amt_fun_curr) total_tax,
sum(case when upper(jtl.tax_rate_code) like '%SGST%' then jtl.rounded_tax_amt_fun_curr end) sgst,
sum(case when upper(jtl.tax_rate_code) like '%CGST%' then jtl.rounded_tax_amt_fun_curr end) cgst,
sum(case when upper(jtl.tax_rate_code) like '%IGST%' then jtl.rounded_tax_amt_fun_curr end) igst
from oe_order_lines_all oola, jai_tax_det_factors jtdf, jai_tax_lines jtl
where oola.header_id=jtdf.ref_doc_trx_id and oola.line_id=jtdf.ref_doc_line_id
and jtdf.det_factor_id=jtl.det_factor_id and jtdf.application_id=707
group by oola.line_id) tax
```
Join: `d.line_id=tax.line_id(+)` — Oracle pushes the predicate into the view.

Result: 6 table lookup chains per row → 1. ~60% buffer IO reduction.

**Pattern: PL/SQL function called per-row → inline SQL**

Example (object names made up): a custom `XX_ITEM_ATTRIBUTE(item_id, date)` function called 587K times (2 internal SQLs each = 1.17M context switches, 55s total).

Fix: Query `all_source` to find the function's SQL, then inline:
```sql
(select xia.attribute_value
from mtl_system_items_b msi, xx_item_attributes xia
where msi.inventory_item_id=d.inventory_item_id and msi.organization_id=102
and xia.segment1=msi.segment1 and xia.segment2=msi.segment2
and t.trx_date between nvl(xia.start_date,t.trx_date) and nvl(xia.end_date,t.trx_date)
and rownum=1) item_attribute
```

### Performance Loop Thresholds

| Metric | Pass | Fail |
|--------|------|------|
| Time per execution | < 60s | >= 60s |
| IO per row | < 1 MB | >= 1 MB |
| PL/SQL function executions | < 10K | >= 10K (inline candidate) |

**Max iterations:** 3 optimization rounds. If still above thresholds after 3 rounds, report findings for manual review.

### Parsing DBA SGA Report Output

The DBA SGA reports output XLSM files. Parse with Python/openpyxl:

```python
import openpyxl

wb = openpyxl.load_workbook('DBA_SGA_Performance.xlsx', data_only=True)
ws = wb.active
headers = [cell.value for cell in ws[1]]

for row_idx in range(2, ws.max_row+1):
    row = {headers[i]: ws.cell(row=row_idx, column=i+1).value for i in range(len(headers)) if headers[i]}
    if row.get('Percentage', 0) and row['Percentage'] > 5:
        print(f"SQL ID: {row.get('Sql Id')}")
        print(f"  Time/exec: {row.get('Time Exec', 0):.1f}s")
        print(f"  IO/row: {row.get('IO Row', 0):.2f} MB")
        print(f"  Rows/exec: {row.get('Rows Exec', 0):.0f}")
        if row.get('Code'):
            print(f"  PL/SQL: {row['Code']} (executions: {row.get('Executions', 0)})")
```

## Key Oracle Performance Facts

- 1 buffer get = 1 Oracle 8KB block read from buffer cache
- 128 buffer gets = 1 MB of data
- v$sql.buffer_gets includes recursive SQL from PL/SQL function calls
- `result_cache` pragma makes functions essentially free after first call
- CTEs (WITH clauses) may be materialized even when not needed — always gate with parameter
- `push_pred` hint helps when outer joining to inline views but NOT when join key is always null
