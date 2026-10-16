# Value fidelity gate

A converted report is delivered only when it is proven to print what the original prints, for the same data and parameters. Parsing, running, returning rows, matching parameters and matching headings are necessary and prove none of this. The customer's UAT is not the comparison: every defect it finds costs a round.

The gate applies to the first delivery and to every correction. Record each result in the Proof column of the report's field inventory.

## Inputs

- The field inventory, `field_inventory.py <program folder>`, with every row's Blitz expression filled in.
- The Blitz report imported on the conversion instance.
- The customer's reference output: one ERP output of the original program with its parameters (step 1 of the skill). An earlier Blitz output is never a reference.

## Checks

1. **Inventory complete.** Every printed field (section 1), formula (2), row-control item (3) and package output element (5) has a Blitz expression or implementation. The only other acceptable entry is a reason the item never reaches the output, citing the source: a formula the layout does not print, a trigger that returns TRUE for every value the program's parameters allow. An empty cell is an open defect.
2. **Formula port.** The original's formula functions and per-row package code, ported as static PL/SQL with their binds as arguments, run on every row of the Blitz SQL and are compared with the Blitz columns: 0 differences on every column (skeleton A). Where the instance has no data for a path, feed identical stand-in rows to both sides (skeleton D).
3. **Reference output.** Checked against the customer's ERP output:
   - The parsed columns match its columns, order and headings, apart from the rendering limits in the rules.
   - Every relation the file lets you recompute holds on every row: totals equal their components, FC equals IC times rate, ages equal as-of minus due date, bucket sums equal outstanding.
   - Row grain matches: one row per what the ERP prints one row for, with the same row order.
4. **Old against new** (a correction of a delivered report): every column the change does not intend to alter has 0 differences, rows joined on the report's key, and `minus` both ways on the key set (skeleton B). A performance rewrite that replaces correlated sub-queries with aggregates is also checked sub-query by sub-query: each aggregate's key must equal the sub-query's correlation, outer-join `(+)` predicates included, because the instance may hold no row that exercises the difference (an adjustment on an invoice with several instalments).
5. **Full-fetch cost.** Fetch every output column of old and new over the same window, twice, and report elapsed seconds and buffer gets per row from the second run (skeleton C). A `count(*)` is not a measurement, because Oracle prunes the columns it does not reference. A new column that multiplies the cost is tuned before delivery.
6. **Independent audit** before the first delivery: a second agent, given only the original's files and the Blitz XML, lists every item and its verdict (`fidelity-audit-prompt.md`). Every DIFFERENT or MISSING is fixed or answered from the source before the file goes out.

## Edge behaviour the original prints

Reproduce these exactly. They are where conversions silently diverge.

- **Single-row lookup** (`select ... into` in a formula): 0 or 2+ rows prints what the exception handler returns, usually blank or 0. Write it as `case when count(*)=1 then max(x) end`. When the handler does not reset the variable, PL/SQL leaves an undefined value that is in practice the first fetched row. Measure the shape on the instance before choosing: kept for a group-by and a unique-key join, not kept for an `in` list.
- **Declared widths:** a `varchar2(n)` placeholder or variable overflows into its handler, so the value prints blank. `number(p,s)` rounds.
- **Null defaults:** `nvl` defaults in the code (`'NA'`, `0`, `'No'`) and the RDF column's `valueIfNull`.
- **Dates:** a date the original prints as text in a fixed mask stays text in that mask. A date it prints as a date stays a date, without time where the original truncates.
- **Row order:** the query's `order by`, else the group break order.
- **Row grain:** group and break keys, and the `union` key, which is the whole select list including ids and rowids the layout never prints.
- **Per-row numbering and running totals** the layout prints: `row_number()` and analytic `sum()` over the report's order.
- **Report modes:** a summary option, sections switched by a parameter, and a group filter that suppresses a whole section each print what the original prints.
- **Header values** printed once (legal entity, customer on a ledger) become a column on every row.
- **Empty and odd parameter values:** with an empty parameter `col=nvl(:p,col)` drops the rows whose column is null; a value equal to the original's `nvl()` stand-in also matches the empty rows; an upper-case-only value set upper-cases free text. Each is a test case of the proof, not only the filled, ordinary value.
- **What the layout actually reads:** Oracle Reports writes a column under its XML tag, which can differ from the column name, and an RTF field whose name matches no tag prints blank. When the source cannot settle what the original prints, run it: the data template and RTF through the BI Publisher engine on the instance, or the package's own procedure into its session temp table and roll back.

## Skeletons

Upload the Blitz SQL as a file and read it into a clob from the `TMP` directory. Resolve the anchors as a run would: replace each `n=n` with its predicates, and each `:bind` with a literal. Keep `dbms_output` lines under 255 bytes.

**A. Formula port**, one function per ported formula, compared per row:

```sql
set serveroutput on size 1000000
declare
l_sql clob:=<fread('p_new.sql')>;
l_cur sys_refcursor;
r_invoice_id number;
r_blitz_col varchar2(4000);
l_diff pls_integer:=0;
l_rows pls_integer:=0;
--the original's formula, its binds as parameters, its select into and handler unchanged
function cf_x(p_invoice_id number) return varchar2 is
l_v varchar2(240);
begin
  select ... into l_v from ... where ...=p_invoice_id;
  return l_v;
exception when others then
  return null;
end;
begin
  open l_cur for 'select x.invoice_id, x."Heading" from ('||l_sql||') x';
  loop
    fetch l_cur into r_invoice_id, r_blitz_col;
    exit when l_cur%notfound;
    l_rows:=l_rows+1;
    if nvl(r_blitz_col,'<null>')<>nvl(cf_x(r_invoice_id),'<null>') then
      l_diff:=l_diff+1;
      if l_diff<=3 then
        dbms_output.put_line('DIFF '||r_invoice_id||' blitz ['||r_blitz_col||'] original ['||cf_x(r_invoice_id)||']');
      end if;
    end if;
  end loop;
  dbms_output.put_line('rows '||l_rows||', Heading differences '||l_diff);
end;
/
```

Carry a key column (`invoice_id`) through the Blitz SQL for the harness only when the output does not already have one, and drop it from the delivered report.

**B. Old against new**, per-column difference counts on joined rows:

```sql
select
count(*) joined,
sum(decode(o.col1,n.col1,0,1)) col1,
sum(decode(o.col2,n.col2,0,1)) col2
from
(<old sql>) o,
(<new sql>) n
where
o.key=n.key
```

`decode` treats two nulls as equal. Run `select key from (<old>) minus select key from (<new>)` and the reverse, which must both be empty unless the change intends to add or remove rows.

**C. Full fetch.** Parse with `dbms_sql`, `describe_columns3`, define every column as `varchar2(4000)` (a date and number column converts), fetch every row, and read `session logical reads` from `v$mystat` before and after. Elapsed time comes from `dbms_utility.get_time`. Run old and new alternately, twice each, and report the second run.

**D. Stand-in data**, for a table the instance has no rows for, such as India Localization tax lines or the customer's own tables. Replace the table with the same inline view in both the ported original and the Blitz SQL:

```sql
(
select 101 invoice_id, 'TDS/CM/1' dm_invoice_num from dual union all
select 102, 'TDS/CM/1' from dual union all
select 103, 'TDS/CM/2' from dual
) jati
```

Cover no match, one match, two or more matches with different values, a value in another operating unit, and a boundary such as the length limit or an invalid date. 0 differences on every case.
