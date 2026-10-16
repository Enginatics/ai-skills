---
name: coding-standards
description: SQL and PL/SQL coding standards for Blitz Report content: report SQL, LOV queries, upload packages. Use whenever writing or reviewing SQL or PL/SQL for a Blitz Report or Blitz Upload.
user-invocable: false
---

# Coding Standards

Self-audit every SQL / PL-SQL / VBA edit against these rules before presenting or deploying it — including one-off operator, migration and test scripts, which are written standards-compliant from the first draft (never "functional first, restyle later"). Most-missed: alias every table including the `delete`/`update`/`insert` target and qualify every column (#5/#6); a space around `=`; a redundant `nvl`; `!=` instead of `<>`.

## PL/SQL Coding Standards

1. **No redundant brackets or code** - AND has higher precedence than OR, so inner brackets around AND conditions are redundant
   ```sql
   -- Bad
   if ((:xxen_reports_run_v.type is not null) and (:xxen_reports_run_v.type='U')) then
   -- Good
   if :xxen_reports_run_v.type='U' then

   -- Bad (redundant inner brackets - AND binds tighter than OR)
   (xu.order_number=p_order_number or (xu.order_number is null and p_order_number is null))
   -- Good
   (xu.order_number=p_order_number or xu.order_number is null and p_order_number is null)
   ```

2. **No redundant nvl()**
   ```sql
   -- Bad
   if nvl(fnd_profile.value('XXEN_REPORT_DEBUG'),'N')='Y' then
   -- Good
   if fnd_profile.value('XXEN_REPORT_DEBUG')='Y' then
   ```
   - **`nvl(col, sentinel) = literal` is redundant BECAUSE OF the `=` operator, NOT because the column is non-null** — do not "verify the column can't be null" to justify removing it. When `sentinel <> literal`, a null column already fails the equality (`null='VALID'` is not true) and so does the sentinel (`nvl(null,'X')='VALID'` -> `'X'='VALID'` -> false): identical result whether or not nulls occur. Just write `col=literal`.
   - Same for the negation when **`sentinel = literal`**: `nvl(col,'INVALID')<>'INVALID'` is redundant (null and 'INVALID' both give false) -> `col<>'INVALID'`.
   - The one case where the nvl is NOT redundant is a negation with **`sentinel <> literal`**: `nvl(col,'X')<>'VALID'` flags a null row (`'X'<>'VALID'` is true) whereas bare `col<>'VALID'` does not (`null<>'VALID'` is null/not-true). Keep it there only if nulls can occur AND you want them flagged; otherwise (column provably non-null for the filtered set) removing it is correct and keeping it is a guard that can't fire (rule #50).

3. **No redundant else null in case statements**
   ```sql
   -- Bad
   case when x.shared_string='s' then to_number(x.shared_string_id) else to_number(null) end
   -- Good
   case when x.shared_string='s' then to_number(x.shared_string_id) end
   ```

4. **One `when` clause per line in case statements**
   - Keep `when` and `then` on the same line when the statement is simple enough to fit
   - Split onto separate lines only when the `when` condition or `then` expression is complex and doesn't fit readably on one line
   ```sql
   -- Bad (multiple when clauses on one line):
   when 1 then p_attribute1 when 2 then p_attribute2 when 3 then p_attribute3

   -- Good (simple - when/then on same line):
   when 1 then p_attribute1
   when 2 then p_attribute2
   when 3 then p_attribute3

   -- Good (complex - split for readability):
   when p_status='ACTIVE' and p_end_date is null then
     some_long_function_call(p_param1, p_param2, p_param3)
   ```

4. **Space between closing bracket and keywords**
   ```sql
   -- Bad: )loop
   -- Good: ) loop
   ```

5. **Always use table aliases — even on single-table queries** — and qualify every column with its alias
   ```sql
   -- Bad (no alias)
   select 1 from dual where exists (select 1 from xxen_report_sql_columns)
   -- Good (alias on the only table)
   select null from xxen_report_sql_columns xrsc where rownum=1

   -- Bad (single-table query without alias)
   select 'Y' from fnd_irep_classes where irep_name='XXEN_WEBSERVICES' and deployed_flag='Y';
   -- Good (alias plus qualified columns)
   select 'Y' from fnd_irep_classes fic where fic.irep_name='XXEN_WEBSERVICES' and fic.deployed_flag='Y';

   -- Bad (alias declared but not all columns qualified)
   select count(*) from user_ords_roles uor where name='xxen_webservices';
   -- Good
   select count(*) from user_ords_roles uor where uor.name='xxen_webservices';
   ```
   The only exception is `dual`, which is conventionally referenced without an alias when no column is selected from it (`select sysdate from dual`, `select 'X' from dual`). Any other table — including one-off existence checks, scalar lookups in `select` lists, and queries against data-dictionary views — must have an alias and column-qualified references. Applies equally to PL/SQL `select … into` statements, `for c in (...)` cursors, and SQL embedded in shell here-docs.

6. **Use correct table alias conventions**
   - Alias is formed from first letter of each word part in the table name
   - Include the _v suffix for views
   - Exception: if alias would be a reserved keyword, keep full short form (e.g. `ap_suppliers` → `aps` not `as`)
   - When table name changes, alias must change accordingly
   - When joining the same table multiple times, add descriptive suffix
   ```sql
   -- xxen_reports -> xr
   -- xxen_reports_tl -> xrt
   -- xxen_report_parameters -> xrp
   -- xxen_report_run_param_values -> xrrpv (not xrrpvt)
   -- xxen_report_dynamic_col_rules -> xrdcr
   -- xxen_report_dyn_col_rule_rpts -> xrdcrr
   -- ra_rules -> rr
   -- ra_terms -> rt
   -- wsh_carrier_ship_methods_v -> wcsmv (include _v for views)
   -- qp_list_headers_vl -> qlhv
   -- hz_cust_site_uses_all -> hcsua
   -- po_headers_all -> pha
   -- mtl_system_items_b_kfv -> msibk (NOT mtl_system_items_kfv — always use _b_kfv directly)
   -- ap_suppliers -> aps (not 'as' — reserved word)

   -- When same table joined multiple times, add suffix:
   -- ra_rules for accounting rule -> rr_a
   -- ra_rules for invoicing rule -> rr_i
   -- hz_cust_site_uses_all for ship_to -> hcsua_ship
   -- hz_cust_site_uses_all for bill_to -> hcsua_bill
   -- wsh_carrier_ship_methods_v for line -> wcsmv_ln
   -- gc_code_combinations_kfv multiple joins -> gcck1, gcck2
   ```

7. **Two blank lines BEFORE AND AFTER each top-level procedure in the package body — consistently.** Single blank line within procedures and in the spec.
   - Two blanks above the first procedure (after the package globals / private helpers).
   - Two blanks between every pair of top-level procedures.
   - Two blanks after the last procedure, before `end <pkg_name>;`.
   - The point is **visual symmetry**: each top-level procedure stands out the same way, with two blank lines separating it from whatever comes before AND after. Not 1, not 3.
   - **No blank lines between `procedure X is` (or `function X is`) and the first declaration / `begin`.** Declarations start immediately on the next line. Same for nested procedures.
   - In the spec: single blank line between procedure declarations.

8. **No standalone comment separator lines**
   ```sql
   -- Bad
   --
   -- comment
   -- Good (just blank line before comment)

   -- comment
   ```

9. **No spaces around assignment or comparison operators**
   ```sql
   -- Bad: l_row := l_row + 1;
   -- Good: l_row:=l_row+1;
   -- Bad: nvl(ac.status,'A') <> 'I'
   -- Good: nvl(ac.status,'A')<>'I'
   -- In XML: use &lt;&gt; with no surrounding spaces
   ```

10. **Use bind variables instead of literals in dynamic SQL**
    ```sql
    -- Bad: 'where xur.run_id='||g_upload_run_id
    -- Good: 'where xur.run_id=:g_upload_run_id'
    ```

11. **Package spec procedure order must match body order**
    - The order of function/procedure declarations in the package spec MUST exactly match the order of their implementations in the package body
    - When adding a new public function, find where it's located in the body and add the spec declaration at the corresponding position
    - This is a PL/SQL requirement - mismatched order causes compilation errors
    ```sql
    -- Example: If body has functions in order: func_a, func_b, func_c
    -- Then spec MUST have them in same order: func_a, func_b, func_c
    -- NOT: func_a, func_c, func_b (wrong order - will fail to compile)
    ```

12. **Simplify nested loops - combine into single query where possible**

13. **CRITICAL: No code duplication** - This is a fundamental rule. Code must be minimalistic.
    - Never create a new procedure/function when similar logic already exists - refactor and reuse
    - When adding functionality that exists elsewhere, move the existing code to a shared location
    - If a local/nested procedure needs to be called from multiple places, move it to package level
    - When fixing a bug, ensure the fix applies to all places using that logic (should be one place)
    - Before writing new code, search for existing implementations that can be extended
    - If you find yourself copying code, STOP and refactor into a single reusable unit

14. **No unnecessary global variables or functions - use local scope**
    - Helper functions/procedures used by only one parent procedure should be defined locally within that procedure's declare section, not at the package body level
    - This keeps scope tight, makes dependencies clear, and avoids polluting the package namespace

15. **Use EBS standard types (fnd_table_of_varchar2_4000) instead of custom record types when possible**

16. **Use Windows line endings (CRLF) for SQL/PL/SQL files, and NO UTF-8 BOM.** Files must start with the first byte of `create or replace ...`, not the 3-byte BOM (`EF BB BF`). SQL*Plus does not strip the BOM; it interprets it as part of the first command and emits `SP2-0734: unknown command beginning '<feff>create or...'` with all subsequent declarations following also rejected as garbage. Verify after writing/editing a `.pkb` / `.pks`:
    ```bash
    file path/to/X.pkb   # must say "UTF-8 text" or "ASCII text", NOT "UTF-8 (with BOM) text"
    ```
    To strip an existing BOM in-place while preserving CRLF (Python; on Linux: `sed -i '1s/^\xef\xbb\xbf//'`):
    ```python
    with open(path,'rb') as f: data=f.read()
    if data.startswith(b'\xef\xbb\xbf'):
        with open(path,'wb') as f: f.write(data[3:])
    ```

17. **Avoid exception handling unless required** - Let errors propagate with full stack trace rather than catching and logging
    - When `when others` IS needed, always log the full error stack — never just `sqlerrm` (which loses line numbers and the call stack)
    ```sql
    -- Bad (loses stack trace):
    exception when others then
      write_log('error: '||sqlerrm);

    -- Good (full stack with line numbers):
    exception when others then
      write_log('error: '||dbms_utility.format_error_stack||dbms_utility.format_error_backtrace);
    ```

18. **Consistent log/error messages in proper English**
    ```sql
    -- Bad: write_log ('p_source_line_id        :'||p_source_line_id);
    -- Good: write_log('p_source_line_id: '||p_source_line_id);
    ```

19. **All code must be lowercase** - including function parameters like userenv('lang')
    ```sql
    -- Bad: SELECT * FROM ... userenv('LANG')
    -- Good: select * from ... userenv('lang')
    ```
    - **The rule governs CODE tokens (keywords, identifiers, function names) — NOT case-significant string-literal DATA.** A literal whose exact case is part of a stored value or wire contract keeps its case: parameter/column type codes (`'Date'`, `'DateTime'`, `'Number'`, `'Char'`, `'LOV'` — the values stored in `xxen_report_parameters.parameter_type` and sent in the add-in's `F` bind field), the engine's semantic markers (`'<multiple_values>'`, `'<null>'`, `'<id>'`), display meanings, and any value compared against case-sensitive data. Lowercasing these breaks the comparison. The `userenv('lang')` example is lowercased only because that particular argument is case-insensitive.

20. **No redundant get_ prefix in function names**
    ```sql
    -- Bad: get_site_use_id, get_new_value, get_inventory_item_id
    -- Good: site_use_id, new_value, inventory_item_id
    ```

21. **Use traditional Oracle SQL syntax, not ANSI**
    ```sql
    -- Bad (ANSI):
    select * from t1 left join t2 on t2.id=t1.id
    -- Good (traditional):
    select * from t1, t2 where t2.id(+)=t1.id
    ```
    - Exception: a genuine full outer join uses ANSI `full join`, confined to its own inline view that joins only the keys, while the rest of the statement stays traditional (Oracle rejects `(+)` and ANSI joins in the same query block). Typical case: two child lists sharing a key, which outer-joined to their parent separately multiply each other.

22. **Use xxen_util functions for lookup translations instead of querying lookup tables**
    - `xxen_util.meaning(code, lookup_type, application_id)` - code to meaning
    - `xxen_util.lookup_code(meaning, lookup_type, application_id)` - meaning to code
    - Works for fnd_lookup_values, oe_lookups (660), ar_lookups (222), etc.
    ```sql
    -- Bad (querying lookup table):
    select ol.lookup_code from oe_lookups ol
    where ol.lookup_type='FOB' and ol.meaning=p_meaning and rownum=1
    -- Good (using function):
    xxen_util.lookup_code(p_meaning,'FOB',660)

    -- Bad (joining to lookup table):
    from fnd_lookup_values flv
    where flv.lookup_type='FREIGHT_TERMS' and flv.lookup_code=ooha.freight_terms_code
    select flv.meaning
    -- Good (using function):
    select xxen_util.meaning(ooha.freight_terms_code,'FREIGHT_TERMS',660)
    ```
    - For FND lookups in LOV queries: use `fnd_lookup_values_vl` (flvv) with `security_group_id=0` and `enabled_flag='Y'` — NOT `fnd_lookup_values` with language filter

23. **WHERE clause formatting** - Each restriction on a new line, join direction flows left to right matching FROM clause order
    - Outer join (+) goes on the right side, matching the natural reading flow from driving table to lookup table
    - Exception: when joining to constant values like `rtt.language(+)=userenv('lang')`, the (+) stays on the left
    ```sql
    -- Bad (wrong direction, uppercase LANG):
    where
    ooha.header_id(+)=xu.header_id and
    qlhv.list_header_id(+)=ooha.price_list_id and
    rtt.language(+)=userenv('LANG')
    -- Good (left to right flow, lowercase lang):
    where
    xu.header_id=ooha.header_id(+) and
    ooha.price_list_id=qlhv.list_header_id(+) and
    rtt.language(+)=userenv('lang')
    ```
    The same left-to-right flow applies to **correlated scalar subqueries**: the restriction coming from the outer query drives the subquery, so the outer value goes on the LEFT:
    ```sql
    -- Bad (outer correlation on the right):
    (select cbv.bank_name from ce_banks_v cbv where cbv.bank_party_id=ieba.bank_id) bank_name,
    -- Good (outer correlation on the left):
    (select cbv.bank_name from ce_banks_v cbv where ieba.bank_id=cbv.bank_party_id) bank_name,
    ```

24. **Indentation: declare section flat, begin section indented 2 spaces**
    - Everything between `declare` and `begin` (variables, types, inline functions) has NO indentation — sits at the same level as `declare`
    - Everything between `begin` and `end` is indented 2 spaces from `begin` — **no exceptions**. The first statement after `begin` must be indented. Nested blocks (loop body, if body) add another 2 spaces.
    - This applies at every nesting level: inline functions in a declare block follow the same rule — their own declare section is flat, their own begin section is indented 2
    - Parameters and local variables use same indentation as procedure/function name
    - Procedure/function headers on one line: `function foo return boolean is`
    - No alignment padding on local variable declarations
    - **Verification**: After writing or editing a procedure, check that no line between `begin` and `end` has zero indentation (except `exception`, `end`, and multi-line string literal continuation lines)
    ```sql
    -- Bad (declare section indented):
    declare
      l_sql clob;
      l_error varchar2(4000);

      function decode_b64(p_b64 varchar2) return clob is
      begin
        return utl_raw.cast_to_varchar2(...);
      end;
    begin
      l_sql:=decode_b64(:input);

    -- Good (declare section flat, begin section indented 2):
    declare
    l_sql clob;
    l_error varchar2(4000);

    function decode_b64(p_b64 varchar2) return clob is
    begin
      return utl_raw.cast_to_varchar2(...);
    end;
    begin
      l_sql:=decode_b64(:input);

    -- Same rule for named procedures/functions:
    -- Bad (indented parameters and variables):
    function default_header_value(
      p_attribute_code in varchar2,
      p_operating_unit in varchar2 default null
    ) return varchar2 is
      l_header_rec oe_ak_order_headers_v%rowtype;
      l_default_id number;
    begin

    -- Good (no extra indentation):
    function default_header_value(
    p_attribute_code in varchar2,
    p_operating_unit in varchar2 default null
    ) return varchar2 is
    l_header_rec oe_ak_order_headers_v%rowtype;
    l_default_id number;
    begin

    -- For calls, parameters match the call's indentation:
          process_sales_order(
          p_header_rec=>l_header_rec,
          p_line_tbl=>l_line_tbl
          );
    ```

25. **Minimalistic SQL - no redundant null checks**
    - Equality conditions naturally handle nulls (null = anything is never true)
    - Don't add explicit "is not null" checks when the value is already used in an equality condition
    ```sql
    -- Bad (redundant null checks):
    where xu.order_number is not null and xu.order_type is not null and
    ooha.order_number=xu.order_number and ottt.name=xu.order_type
    -- Good (equality handles nulls):
    where ooha.order_number=xu.order_number and ottt.name=xu.order_type
    ```

26. **Understand unique keys - no redundant rownum=1**
    - Know which columns have unique indexes/constraints and don't add `rownum=1` when the query can only return one row
    - Example: `hr_all_organization_units.name` is unique, so no `rownum=1` needed when filtering by name
    ```sql
    -- Bad (redundant rownum on unique column):
    select haouv.organization_id from hr_all_organization_units_vl haouv
    where haouv.name=xu.operating_unit and rownum=1
    -- Good (name is unique):
    select haouv.organization_id from hr_all_organization_units_vl haouv
    where haouv.name=xu.operating_unit
    ```
    This applies equally to correlated scalar subqueries: do not add a defensive `rownum<=1` "for safety" when the correlation key is unique (e.g. `ce_banks_v.bank_party_id`) — same family as rule #50, a guard that cannot fire hides a broken assumption.

27. **Use subqueries with x/y/z aliases instead of `with ... as` blocks (CTEs), and use * to avoid repeating columns**
    - Prefer nested subqueries over `with ... as` blocks
    - Use short aliases (x, y, z) for subquery levels
    - Use `select x.*` to pass through columns instead of listing them all
    - **When a subquery is written in multiline style, put the opening `(` on its own line and start `select` on the next line** — never `(select` on the same line. (A subquery kept entirely on one line is fine as `(select ... ) alias`; this only applies once it spans multiple lines.)
    ```sql
    -- Bad (multiline subquery with '(select' on the same line):
    (select msit.description
    from mtl_system_items_tl msit
    where msit.inventory_item_id=x.item_id and msit.language=userenv('lang')
    ) item_description

    -- Good ('(' on its own line, select on the next):
    (
    select msit.description
    from mtl_system_items_tl msit
    where msit.inventory_item_id=x.item_id and msit.language=userenv('lang')
    ) item_description

    -- Good (short subquery stays on one line):
    (select ppx.full_name from per_people_x ppx where ppx.person_id=x.buyer_id and rownum=1) buyer
    ```
    ```sql
    -- Bad (with ... as blocks, repeating columns):
    with base as (
      select xu.col1, xu.col2, xu.col3, ... from table xu
    ),
    enriched as (
      select base.col1, base.col2, base.col3, ..., extra from base
    )
    select enriched.col1, ... from enriched

    -- Good (nested subqueries with * and x/y/z):
    select y.*, ooha.extra_col
    from (
      select x.*, (select ...) resolved_id
      from (select xu.* from table xu) x
    ) y, other_table ooha
    where y.resolved_id=ooha.id(+)
    ```

28. **No redundant 'as' keyword for column aliases**
    ```sql
    -- Bad:
    select count(*) as order_line_count, min(x.upload_row) as order_sort
    -- Good:
    select count(*) order_line_count, min(x.upload_row) order_sort
    ```

29. **Use cursor for loop instead of select into with exception handling**
    - Shorter and more elegant than begin/exception/end blocks
    - Loop naturally handles no_data_found (just doesn't execute)
    - For multi-line SQL, keep same indentation level as the `for` statement
    ```sql
    -- Bad (verbose with exception handling):
    begin
      select mp.organization_id into l_org_id
      from mtl_parameters mp where mp.organization_code=p_warehouse;
    exception when no_data_found then null;
    end;

    -- Good (cursor for loop, single line):
    for c in (select mp.organization_id from mtl_parameters mp where mp.organization_code=p_warehouse) loop
      l_org_id:=c.organization_id;
    end loop;

    -- Good (multi-line SQL, same indentation as for):
    for c in (
    select ooha.header_id
    from oe_order_headers_all ooha
    where ooha.order_number=p_order_number
    ) loop
      return c.header_id;
    end loop;

    -- Bad (SQL indented further than for):
    for c in (
        select ooha.header_id
        from oe_order_headers_all ooha
    ) loop
    ```

30. **No redundant nvl() or implicit type conversions**
    - Comparisons handle null naturally (null > 0 is false, not an error)
    - Numeric comparisons do implicit to_number conversion
    ```sql
    -- Bad (redundant nvl and to_number):
    nvl(to_number(c.debug_level),0)>0
    -- Good:
    c.debug_level>0

    -- Bad (redundant nvl - null > 0 is already false):
    nvl(l_count,0)>0
    -- Good:
    l_count>0
    ```

31. **SQL formatting - one line per select column, from table, where clause, insert column, values expression**
    - One column per line after `select`, one table per line after `from`, one condition per line after `where`
    - **`insert into <table> ( ... ) values ( ... )`** — one column name per line in the column list, one value/expression per line in the values list. Never pack multiple columns or values on the same line.
    - Applies everywhere: main SQL, LOV queries in XML, Success SQL, PL/SQL cursors, DML statements
    - Only use single-line format for very small simple queries (e.g. `select mp.organization_id from mtl_parameters mp where mp.organization_code=p_code`)
    - FROM clause table order must follow the restriction flow — the table restricted first (by bind variable, constant, or driving condition) comes first
    ```sql
    -- Bad (columns and tables on same line as keywords):
    select ooha.header_id
    from oe_order_headers_all ooha,oe_transaction_types_tl ottt
    where ooha.order_number=p_order_number

    -- Good (separate lines):
    select
    ooha.header_id
    from
    oe_order_headers_all ooha,
    oe_transaction_types_tl ottt
    where
    ooha.order_number=p_order_number and
    ooha.order_type_id=ottt.transaction_type_id

    -- OK for very small queries (single line):
    for c in (select mp.organization_id from mtl_parameters mp where mp.organization_code=p_code) loop

    -- Bad (insert with packed columns/values):
    insert into qa_plan_char_actions (
    plan_char_action_id, plan_char_action_trigger_id, action_id,
    assigned_char_id, assign_type, message,
    creation_date, created_by, last_update_date, last_updated_by, last_update_login
    ) values (
    l_plan_char_action_id, l_plan_char_action_trigger_id, p_action_id,
    p_assigned_element_id, p_assign_type, p_action_message,
    sysdate, fnd_global.user_id, sysdate, fnd_global.user_id, fnd_global.login_id
    );

    -- Good (insert with one column / value per line):
    insert into qa_plan_char_actions (
    plan_char_action_id,
    plan_char_action_trigger_id,
    action_id,
    assigned_char_id,
    assign_type,
    message,
    creation_date,
    created_by,
    last_update_date,
    last_updated_by,
    last_update_login
    ) values (
    l_plan_char_action_id,
    l_plan_char_action_trigger_id,
    p_action_id,
    p_assigned_element_id,
    p_assign_type,
    p_action_message,
    sysdate,
    fnd_global.user_id,
    sysdate,
    fnd_global.user_id,
    fnd_global.login_id
    );
    ```

32. **No hardcoded user-facing values - use lookup codes for multi-language support**
    - Never hardcode translated/translatable values like 'Book Order', 'Cancel', etc.
    - LOVs display `xxen_util.meaning(code, lookup_type, app_id)` to users
    - In PL/SQL, use `xxen_util.lookup_code(meaning, lookup_type, app_id)` to convert back to code
    - Compare against the lookup CODE (e.g., 'BOOK', 'CANCEL'), not the translated meaning
    ```sql
    -- Bad (hardcoded translated value - breaks in other languages):
    if l_order_action='Book Order' then

    -- Good (convert meaning to code, compare against code):
    if xxen_util.lookup_code(l_order_action,'ORDER ACTION',660)='BOOK' then
    ```
    - **An error message a user sees comes from the Oracle message dictionary wherever one exists** - `fnd_message.get_string('<application>','<message name>')`, or `fnd_message.set_name`+`get` where the message takes tokens. It is already translated and already says what the user is used to reading, and a rejection our code raises is then indistinguishable from the one the standard program would have raised for the same condition. Reproduce an Oracle validation ourselves (because an interface or api cannot see the rows) and reuse its message and `error_code` verbatim. Write a literal only when no seeded message fits.
    ```sql
    -- Bad (our own wording for a condition Oracle already names):
    message_:='Costs already exist for this item and cost type.';

    -- Good (the message the Cost Import itself writes):
    message_:=substrb(fnd_message.get_string('BOM','CST_CANT_INSERT'),1,240);
    ```

33. **Only one space between column expression and alias**
    - No alignment padding with multiple spaces
    - Remove alias if it matches the column name
    ```sql
    -- Bad (padded alignment, redundant alias):
    haouv.name                         operating_unit,
    rcta.trx_number                    trx_number,
    rctla.unit_selling_price           unit_price,
    -- Good:
    haouv.name operating_unit,
    rcta.trx_number,
    rctla.unit_selling_price unit_price,
    ```

34. **Use `<>` not `!=`** for not-equal comparisons. In XML files, escape as `&lt;&gt;` with no surrounding spaces.

35. **Use coalesce for 3+ fallback values instead of nested nvl**
    ```sql
    -- Bad (nested nvl):
    nvl(a, nvl(b, c))
    -- Good (coalesce):
    coalesce(a, b, c)
    ```
    Two values is fine with `nvl`. Use `coalesce` when there are 3 or more fallback values, and always when a fallback is a scalar subquery or function call: `nvl` evaluates its second argument for every row even when the first is not null (measured: the subquery's full reads with a non-null first argument), while `coalesce` stops at the first non-null value.

36. **PL/SQL string truncation — substr vs substrb**
    - Use `substrb` only when truncating to a variable's byte limit (e.g. 32767 for varchar2). With AL32UTF8, 32767 chars can be 131068 bytes → ORA-06502. Use `substrb(text,1,32767)` instead.
    - Use `substr` when truncating to an arbitrary processing limit (e.g. 4000). You want N characters of content, not bytes.
    - Rule of thumb: Is the limit the target variable's max size? → `substrb`. Is it a "good enough" processing limit? → `substr`.

36a. **`ORA-01489: result of string concatenation is too long` is raised only by `||` / `concat` / `listagg`** — under `max_string_size=STANDARD` (the EBS default, 4000-byte SQL varchar2) the other string functions (`replace`, `regexp_replace`, `rpad`, `lpad`, `substr`) silently truncate at 4000 instead. Corollaries:
    - A PL/SQL function returning `varchar2` is treated as `varchar2(4000)` when called from SQL: a longer result raises `ORA-06502` at the call site, so any value that comes back is already ≤4000 bytes.
    - The classic trap is `'|'||some_function(...)||'|' like '%|FOO|%'` on a value near 4000 bytes: the two extra characters overflow. Rewrite the pipe-anchored `like` as bare patterns (`x like '%|FOO|%' or x like 'FOO|%' or x like '%|FOO' or x='FOO'`), or `substrb(value,1,3900)` before any `||`.
    - Signature in a report log: `ERROR fetching data` with a stack `ORA-01489 → SYS.DBMS_SQL → APPS.XXEN_REPORT (dbms_sql.fetch_rows)` — the framework is only the messenger, the offending `||` is in the report/upload SQL, and it fails only on the rows whose value is that long (a filtered test run passes).

37. **Minimalistic code is paramount**
    - Eliminate unnecessary variables, redundant queries, and extra logic
    - Reuse a single variable rather than declaring separate ones
    - Return directly from loops instead of storing in a variable then returning
    - `if condition then return 'N'; end if; return 'Y';` is cleaner than `if/else return`

38. **Always use the highest-level Oracle standard API** — before writing direct DML or low-level table operations, search for official Oracle APIs in this order: (1) Public APIs (`*_PUB`, `*_API`), (2) Standard utilities/commands (e.g. `FNDGFU` for fnd_lobs uploads, `FNDLOAD` for setup data), (3) Table handlers (`*_PKG`). Example: for fnd_lobs uploads, use the `FNDGFU` command (like `bin/import_xml` does) — never direct INSERT into fnd_lobs.

40. **Product name is "Blitz Report"** — always use the full name "Blitz Report" in labels, descriptions, comments, and user-facing strings. Never abbreviate to just "Blitz" unless it’s an established exception (e.g. profile options like "Blitz Upload", "Blitz FSG" for readability).
    ```sql
    -- Bad:
    p_label=>'Blitz Webservices'
    -- Good:
    p_label=>'Blitz Report Webservices'
    ```

41. **Never display raw Y/N flag values** — always translate using `xxen_util.meaning`
    - **Report display convention: show only "Yes", leave blank for "No"** — users don't want to see a wall of "No" values; a blank cell is clearer. Use the dedicated helper **`xxen_util.yes(col)`** for Y/N flag columns — it returns the translated "Yes" for 'Y' and null (blank) for anything else. It is defined in `XXEN_UTIL` as exactly `decode(p_lookup_code,'Y',meaning('Y','YES_NO',0))`, so always prefer the helper over hand-writing the `decode(col,'Y',xxen_util.meaning('Y','YES_NO',0))` form.
    - For CASE WHEN conditions: `xxen_util.yes(case when condition then 'Y' end)` (omit `else 'N'`)
    - Applies to all boolean/flag columns: `primary_flag`, `dependent_flag`, `beneficiary_flag`, `approved_flag`, `billable_flag`, `reverse_flag`, `capitalized_flag`, `released`, `transferred`, etc.
    ```sql
    -- Bad (shows "No" for every non-Y row):
    xxen_util.meaning(pcr.dependent_flag,'YES_NO',0) dependent,
    xxen_util.meaning(ppaa.reverse_flag,'YES_NO',0) reverse_flag,
    case when pdia.released_date is not null then 'Y' else 'N' end released,

    -- Good (shows "Yes" or blank — use the dedicated xxen_util.yes() helper):
    xxen_util.yes(pcr.dependent_flag) dependent,
    xxen_util.yes(ppaa.reverse_flag) reverse_flag,
    xxen_util.yes(case when pdia.released_date is not null then 'Y' end) released,
    ```
    - **Storage convention for new boolean columns** (Enginatics-owned tables): store `'Y'` or `null` — never `'N'`. Two-valued logic only, no Y/N/null tri-state. On insert/update convert incoming `'N'` to null with `nullif(p_flag,'N')`; on display translate with `xxen_util.meaning(nvl(col,'N'),'YES_NO',0)` so blanks render as language-specific "No". Does NOT apply to existing Oracle EBS flag columns that already use `'N'` — keep their semantics.

42. **Never wrap indexed date columns with trunc() or to_char()** — this prevents index access and forces full table scans
    - For "date from" filters: `column>=:date_from` (no trunc)
    - For "date to" filters: `column<:date_to+1` (before midnight the next day, no trunc)
    - This pattern captures the full day including any time component, while preserving index access
    ```sql
    -- Bad (kills index on transaction_date):
    trunc(rt.transaction_date)>=:date_from
    trunc(rt.transaction_date)<=:date_to

    -- Good (index-friendly):
    rt.transaction_date>=:date_from
    rt.transaction_date<:date_to+1
    ```

43. **Default cached id-lookup variables to an impossible sentinel (e.g. `-99`), not null**, when they will be used in `NOT IN` clauses
    - When replacing a `user_name`/`name`→id subquery with a cached variable (e.g. `l_enginatics_user_id`), initialize to `-99` rather than leaving nullable
    - Reason: `col not in (-1, null)` evaluates to null → filters ALL rows out. The original `user_name not in ('ANONYMOUS','ENGINATICS')` correctly returned rows when the user didn't exist — a null variable would silently break that semantic on instances where the lookup returns no row.
    ```sql
    -- Bad (breaks NOT IN on instances where ENGINATICS user doesn't exist):
    l_enginatics_user_id number;
    for c in (select fu.user_id from fnd_user fu where fu.user_name='ENGINATICS') loop
      l_enginatics_user_id:=c.user_id;
    end loop;
    -- ...
    where xrp.created_by not in (-1,l_enginatics_user_id) -- null → no rows pass

    -- Good (sentinel default):
    l_enginatics_user_id pls_integer:=-99;
    ```

44. **Line wrapping: don't wrap proactively, and put connectors at END of line**
    - **Line length budget**: assume wide screens. Don't wrap until a line clearly exceeds **~200–240 characters**. Wrapping shorter lines hurts readability, not helps. Sweet spot: keep related logic together on one line where possible, only break when the line genuinely won't fit.
    - **Connector position when you DO wrap**: `and` / `or` go at the **END of the previous line**, never at the START of a new line. This is consistent with rule #23 for SQL WHERE clauses, generalized to PL/SQL `if`/`while`/`exit when` conditions and SQL HAVING/ON clauses.
    ```sql
    -- Bad — connector at start of line:
    if l_x is not null
    and l_y is not null
    and l_z is not null then

    -- Bad — wraps too aggressively when one line would fit:
    if l_x is not null and
    l_y is not null and
    l_z is not null then

    -- Good — fits on one line, no wrap:
    if l_x is not null and l_y is not null and l_z is not null then

    -- Good — when wrap is genuinely needed, connector at end:
    if l_x is not null and l_y is not null and
    l_action=xxen_upload.g_action_create or xxen_upload.value_modified('p_x') or xxen_upload.value_modified('p_y') then
    ```

45. **Prefer language views (`_vl`) over manual `_b + _tl` joins.** Oracle EBS provides `_vl` views (e.g. `fa_additions_vl`, `mtl_system_items_vl`, `hr_all_organization_units_vl`, `fnd_lookup_values_vl`) that already join the base table to its `_tl` translations table for `userenv('lang')`. Using the `_vl` view is shorter, more elegant, and harder to get wrong.
    ```sql
    -- Bad (manual _b + _tl join):
    from
    fa_additions_b fab,
    fa_additions_tl fat
    where
    fab.asset_id=fat.asset_id and
    fat.language=userenv('lang') and
    fab.in_use_flag='Y'

    -- Good (language view):
    from
    fa_additions_vl fav
    where
    fav.in_use_flag='Y'
    ```
    Applies in main SQL, LOV queries, Success SQL, PL/SQL cursors. The handful of cases where you do need the underlying `_b` (e.g. you need rowid for `xxen_util.display_flexfield_value`, or you need a non-translated column not exposed by `_vl`) are exceptions — document why in a comment.

    Reinforces existing rule #33: when you switch to a `_vl` view, the now-redundant column aliases (e.g. `fav.description description`) must be removed.

    **Items: use `mtl_system_items_vl msiv` — NOT `mtl_system_items_b_kfv msibk` — for any query that displays the item DESCRIPTION.** `mtl_system_items_b_kfv` is built on the base table `mtl_system_items_b`, so its `description` is the **untranslated** (install-base-language) value; in a non-US session it shows the wrong language. `mtl_system_items_vl` is the language view (`_b` + `_tl` for `userenv('lang')`) and — it **also carries `concatenated_segments`** plus all the base columns an item LOV needs (`recipe_enabled_flag`, `serial_number_control_code`, `primary_uom_code`, `organization_id`, `inventory_item_id`). So `mtl_system_items_vl` is a **complete drop-in replacement**: one view gives both the KFF concat (the item "value") AND the translated description — never join `_b_kfv` for segments + something else for the description, and never reach for a separate `_kfv` table. Use `mtl_system_items_b_kfv` only when you genuinely need a column `_vl` doesn't expose AND translation is irrelevant. Item LOVs, item-description columns, main-SQL item joins, and Success SQL must all source the item from `mtl_system_items_vl`.
    ```sql
    -- Bad (untranslated description from the base KFF view):
    select msibk.concatenated_segments id, msibk.concatenated_segments value, msibk.description description
    from mtl_system_items_b_kfv msibk where msibk.recipe_enabled_flag='Y'
    -- Good (translated description, same concatenated_segments, one view):
    select msiv.concatenated_segments id, msiv.concatenated_segments value, msiv.description
    from mtl_system_items_vl msiv where msiv.recipe_enabled_flag='Y'
    ```

46. **CRITICAL: Users must always see DISPLAY VALUES, never IDs or codes.** Blitz Report and Blitz Upload outputs are user-facing. Whenever output is shown to a user (template XLSM, result XLSM, parameter prompts, LOV dropdowns, error messages), the value must be the human-readable, translated display value — never the underlying internal code or ID.
    - **Status / Action**: Use `xu.status_` and `xu.action_` (display values via `xxen_upload.status_meaning` / `action_meaning`), never `xu.status_code_` / `xu.action_code_` — and never hardcoded `'S'`, `'V'`, `'E'`, `'C'`, `'U'`, `'D'` etc.
    - **LOV-bound columns**: When the LOV has `id`/`value` columns, display the `value`, not the `id`.
    - **Lookup codes** (FND lookups, e.g. `MTL_EAM_ACTIVITY_TYPE`): Translate via `xxen_util.meaning(code, lookup_type, app_id)` — never display the raw `lookup_code`.
    - **Yes/No flags**: Use `xxen_util.meaning('Y','YES_NO',0)` for "Yes", and blank/null for "No" (so the cell renders empty rather than the literal "No"). Never display raw `'Y'`/`'N'`.
    - **Date columns**: Let the framework's standard date formatting render them. Where a date must be text (an LOV `value` column), use `fnd_date.date_to_displaydate(d)`; there is no `xxen_util.user_date`.
    - **Never `to_date()` a Date parameter's bind**: the engine binds Date parameters as DATE, so `to_date(:p,'DD-Mon-YYYY')` converts it back through the session's `nls_date_format`, and a concurrent request's `DD-MON-RR` turns 2027 into year 0027. Use the bind as it is; an LOV that passes a date as its id passes text in an explicit format (`to_char(d,'YYYY/MM/DD')`, converted back with the same mask).
    - **IDs (numeric or rowid)**: Never expose to users in display columns. Even hidden helper columns that hold IDs should be marked `<HIDDEN>Y</HIDDEN>` so users don't see them.
    ```sql
    -- Bad (hardcoded code, user sees "S"):
    'S' status_,

    -- Good (display value, user sees "Success" / "Erfolgreich"):
    xu.status_,

    -- Bad (raw lookup code):
    pcr.dependent_flag,

    -- Good (translated display, blank for 'N'):
    decode(pcr.dependent_flag,'Y',xxen_util.meaning('Y','YES_NO',0)) dependent,
    ```

47. **Use the most restrictive Oracle data-dictionary view possible.** Narrower views are faster and convey intent — `user_objects` says "my own schema", `all_objects` "any object I can see", `dba_objects` "the whole database, needs SELECT ANY DICTIONARY". The choice follows the OWNER of the object (the EBS custom-development storage split):
    - **`user_*`** — objects owned by the schema running the script (`apps` for our install/upgrade flow): APPS-owned packages, views, types, synonyms, our customized Oracle bodies (`FND_WEBFILE`), APPS' own privileges (`user_sys_privs`, `user_tab_privs`), the schema's ORDS objects (`user_ords_*`). Drop redundant `owner='APPS'` / `grantee='APPS'` predicates.
    - **`all_*`** — objects in another schema visible to APPS: the storage objects (`TABLE`, `INDEX`, `SEQUENCE`, their triggers) of the custom schema (`XXEN` by default, customers may choose another — from APPS `user_tables` returns nothing for them), JA, APPLSYS, SYS via SELECT ANY DICTIONARY, ECC, ORDS_METADATA.
    - **`dba_*`** — only when there is no narrower alternative: DB-wide scope (`dba_objects do where do.status<>'VALID'` after an install), tablespace metadata (`dba_tablespaces` — `user_tablespaces` shows only quota'd ones), foreign admin-user lookups (`dba_users du where du.username in ('EBS_SYSTEM','SYSTEM')`).
    ```sql
    -- Bad (XXEN_SCHUB is an APPS-owned package):
    select 'Y' from dba_objects do where do.object_name='XXEN_SCHUB' and do.object_type='PACKAGE' and rownum=1
    -- Good:
    select 'Y' from user_objects uo where uo.object_name='XXEN_SCHUB' and uo.object_type='PACKAGE' and rownum=1

    -- Bad (XXEN_REPORTS lives in the custom schema — user_tables from APPS returns nothing):
    select ut.tablespace_name from user_tables ut where ut.table_name='XXEN_REPORTS' and rownum=1
    -- Good:
    select at.tablespace_name from all_tables at where at.table_name='XXEN_REPORTS' and rownum=1

    -- Bad (checking APPS' own system privilege):
    select dsp.privilege from dba_sys_privs dsp where dsp.grantee='APPS' and dsp.privilege='SELECT ANY DICTIONARY'
    -- Good:
    select usp.privilege from user_sys_privs usp where usp.privilege='SELECT ANY DICTIONARY'
    ```
    - `user_arguments`/`all_arguments` filtered by `package_name` scan every argument of the schema (over 4 minutes on an EBS APPS schema); filter by `object_id` from `user_objects`, which uses the index (0.2 s).
    - **Column-availability trap — `all_*` is not `dba_*` minus a filter.** `all_users` lacks `default_tablespace`, `temporary_tablespace`, `created`, `account_status`, `profile` (they exist only on `dba_users`/`user_users`); `select au.default_tablespace from all_users au` parses on its own but fails at runtime with `ORA-00904`, which inside an embedded cursor cascades into `PLS-00364: loop index variable 'C' use is invalid` on every reference. Before tightening `dba_X` → `all_X`, `desc all_X` and confirm every selected column exists; foreign admin-user metadata always stays on `dba_users`.

48. **`fnd_api.g_miss_*` sentinels are NOT null.** The Oracle FND API "no-change" sentinels are real values masquerading as missing:
    - `fnd_api.g_miss_char` = `chr(0)`
    - `fnd_api.g_miss_num`  = `9.99e125`
    - `fnd_api.g_miss_date` = `'01-JAN-4712'`

    Never assume `is null` will detect them. When calling an Oracle API that uses these as "no change" markers, watch for two failure modes:
    - **Wrapping the value yourself**: `if l_value is not null then ...` skips logic that should run for g_miss; use `if l_value <> fnd_api.g_miss_*` (with type-matched comparison) or `nvl(l_value,sentinel)=sentinel` instead.
    - **API-side `is not null` checks that misfire on the sentinel**: some Oracle public APIs gate work on `if p_date is not null` and use g_miss_date as no-change concurrently. Passing g_miss_date trips the `is not null` check and triggers the work as if you'd supplied a real value. Known case: `inv_loc_wms_pub.update_locator` (bug 7297065) — see `upload-api-patterns` skill § INV Stock Locator Upload for the documented workaround pattern.

49. **Generate rows / split a delimited string with `xxen_util.rowgen(n)` — never `connect by level` or `table(cast(multiset(...)))`.** `xxen_util.rowgen(p_rows in number) return fnd_table_of_number deterministic` returns `n` rows; reference the generated counter as `rowgen.column_value`. It is the standard Blitz idiom (used throughout `XXEN_REPORT.pkb` / `XXEN_XDO.pkb`) for the "explode a row into N rows" pattern, e.g. extracting each token of a delimited list with `regexp_substr(...,1,rowgen.column_value)`. Count the items with the **same** pattern you extract — no `+1`.
    ```sql
    -- Bad (verbose collection-cast / connect-by row generator):
    table(cast(multiset(select level from dual connect by level<=regexp_count(c.list,';')+1) as sys.odcinumberlist)) l
    ... regexp_substr(c.list,'[^;]+',1,l.column_value)

    -- Good (rowgen — count the token pattern, no +1):
    table(xxen_util.rowgen(regexp_count(c.list,'[^;]+'))) rowgen
    ... regexp_substr(c.list,'[^;]+',1,rowgen.column_value)
    ```
    Typical full pattern — split a semicolon-delimited column into one row per token:
    ```sql
    select regexp_substr(c.list,'[^;]+',1,rowgen.column_value) token
    from
    my_table c,
    table(xxen_util.rowgen(regexp_count(c.list,'[^;]+'))) rowgen
    where
    c.list is not null
    ```
    For the "extract the Nth `:bind`" use case the codebase counts the bind pattern: `table(xxen_util.rowgen(regexp_count(x.sql_text,':\w+'))) rowgen` + `regexp_substr(x.sql_text,':\w+',1,rowgen.column_value)`. `rowgen` is `deterministic`, so it costs nothing extra in repeated calls.

50. **No redundant "belt-and-braces" defensive code — a guard that cannot fire hides a broken assumption.** Never add a condition, filter, null-check, or exclusion that is provably unreachable given the surrounding logic. It is confusing (it implies the impossible can happen), bloats the code, and — exactly like a broad `when others` (rule #17) — silently absorbs an inconsistency so you never discover that the code or your initial assumption was wrong. Write the predicate/guard that is *exactly* necessary and no more, so a wrong assumption fails loudly instead of being papered over.
    - Before adding a guard "just in case", verify whether the case can actually occur (query/inspect the data). If it cannot, omit the guard. If you are genuinely unsure, surface the uncertainty to the user rather than defending against it silently.
    - Worked example: a delete that targets rows carrying marker `X` must NOT also carry `and description not like 'Y%'` when `Y`-rows provably never contain `X` (verify: count of `Y`-rows that match `X` is 0). The `X` marker is already the exact discriminator, so the `Y`-exclusion guards an empty set — and worse, it would silently *skip* a mislabelled `Y`-row that genuinely contained `X`, the one case you would actually want surfaced.
    - Same family as #2 (no redundant nvl), #13 (no code duplication), #17 (no needless exception handling) and #37 (minimalistic code is paramount): keep code concise, clean and exact.

51. **Trunc both sides of date comparisons in validation logic — calendar-day semantics, not instant-in-time.** When PL/SQL validation logic compares a date value (column, bind variable, or user-supplied parameter) against `sysdate` for correctness purposes (e.g. "must be ≥ today", "no more than N years in the future", "cannot be in the past"), apply `trunc` to BOTH sides of the comparison. Calendar-day semantics: a "today" check must accept any time during today, not just midnight; a "yesterday" check must reject yesterday regardless of clock time.
    - The canonical pattern: `trunc(p_date)<trunc(sysdate)` for "must be ≥ today" rejection.
    - An asymmetric form like `p_date<trunc(sysdate)` silently lets "yesterday at 11pm" through whenever `sysdate` has elapsed past midnight, because `trunc` strips time on one side only — the bind still carries `23:00:00`, the right side is `00:00:00`, and the comparison says "false, accept" when it should say "true, reject".
    - For "N years from today" caps: use `trunc(p_date)>trunc(sysdate)+N*365` (calendar-day arithmetic with both sides truncated).
    - **Pairs with — does not conflict with — rule #42** (which forbids `trunc` on indexed date columns in WHERE clauses for performance). Rule #42 is about SQL queries against base tables (kills index access → full table scan). This rule is about PL/SQL validation logic comparing user-supplied dates to `sysdate` (correctness — no index involved). The two rules apply in different contexts and have different goals.
    ```sql
    -- Good (trunc both sides — calendar-day semantics, "today" accepted any time of day):
    if trunc(p_effective_date)<trunc(sysdate) then
      message_:='Effective date cannot be in the past.';
      raise le_validation_exception;
    end if;
    if trunc(p_end_date)>trunc(sysdate)+300*365 then
      message_:='End date cannot be more than 300 years in the future.';
      raise le_validation_exception;
    end if;

    -- Bad (no trunc — time-of-day discriminates within a single calendar day, "today 09:00" rejected at 10:00):
    if p_effective_date<sysdate then
      message_:='Effective date cannot be in the past.';
      raise le_validation_exception;
    end if;

    -- Bad (asymmetric — lets yesterday-late-evening through):
    -- p_date holds e.g. yesterday 23:00:00; trunc(sysdate) is today 00:00:00; 23:00<00:00 is false → row accepted as "today"
    if p_effective_date<trunc(sysdate) then
      message_:='Effective date cannot be in the past.';
      raise le_validation_exception;
    end if;
    ```

52. **No backward-compatibility shims for superseded formats — migrate, don't dual-support.** Code must be minimalistic; avoid technical debt that exists only to keep supporting outdated logic. When a stored format / code scheme / data convention is replaced (e.g. single-char assignment-level codes `S`/`A`/`F` → full words `Site`/`Application`/`Form`), do a clean cut-over: a one-time data migration converts existing rows, and ALL code (views, parsers, importers, exporters, forms) speaks ONLY the new format. Do NOT add tolerant "accept both old and new" logic (`decode(x,'F','Form',x)`, `in ('F','Form')`) to keep reading the outdated format at runtime — that debt lingers forever, obscures intent, and silently hides bugs (same family as #13, #17, #37, #50). The ONLY legitimate place the old format may appear is the migration statement itself, which must read the old code once to rewrite it. If you believe a dual-support shim is genuinely needed, surface the specific scenario to the user first — usually there isn't one.

53. **Initialize variables in their declaration** - When the value is a simple expression available at block entry (e.g. a `fnd_profile.value()` call), write `l_x type:=<expr>;` in the declare section instead of declaring the variable and then assigning it on a separate line later in the begin block. Fewer lines, single source of truth. Pairs with #2 (no redundant nvl).

54. **Minimalistic comments in delivered code (PL/SQL, SQL, shell, etc.)** - Keep comments to 1-2 short lines that state WHY a non-obvious line exists. Do NOT narrate the full mechanism, restate the code, justify the design at length, enumerate edge cases, or cite external references (Oracle notes, MOS doc IDs, blog URLs) inside shipped code. A multi-line comment block that dwarfs the code it documents is noise. Deep background (root cause, history, supporting evidence) belongs in the commit message or the `.claude/rules/*.md` knowledge files, not in the delivered source. Same minimalism principle as #37 — applies to all delivered code.
    - **NEVER write a comment that describes the CHANGE, the previous behaviour, or a comparison against it.** A comment documents the code as it stands now, for a reader who has never seen any earlier version. Change history belongs in the commit message and `git log`/`git blame`; it must not accumulate in the source. This is the single most common comment failure when editing existing code, because the change is what is on the author's mind at the time — and it is exactly what the next reader does not need.
    - **Banned phrasings** (each is a rewrite trigger, not a style preference): `previously ...`, `used to ...`, `no longer ...`, `was ... now ...`, `removed the ...`, `added ... because`, `changed from ... to ...`, `instead of re-querying/re-parsing/looping ...`, `avoids the extra ...`, `fixes ...`, `this was a bug`, and any reference to a former implementation, an old parameter, or a deleted line.
    - **The test:** delete the comment and ask what a new reader still cannot infer from the code. Write only that. If the answer is "nothing", write no comment.
    ```sql
    -- Bad (narrates the change and the code it replaced):
    p_template_id:=xxen_report.template_id(p_report_id,p_template_name); --resolve through the core instead of re-querying xxen_report_templates
    l_xml xmltype:=xmltype(p_clob); --parse once, previously every statement re-parsed the full clob
    regexp_substr(fnd_webfile.get_url(...),'[^=]*$'); --removed the hardcoded oapc/oas parameters, which were captured from one instance

    -- Good (states a constraint the code cannot show, or no comment at all):
    p_template_id:=xxen_report.template_id(p_report_id,p_template_name);
    l_xml xmltype:=xmltype(p_clob);
    l_key varchar2(32767):=lower(p_vchr)||'|'||p_col_num||'|'||p_col; --delimited key to avoid collisions between value and column name concatenations
    ```

55. **Every Oracle identifier must be ≤30 bytes — 19c masks a bug that breaks 11g/12.1 (and 11i) installs.** Blitz Report ships to EBS 11i, R12.1 and R12.2 — all of which run on a pre-12.2 database (11.2.0.4 / 12.1.0.2) that enforces the classic **30-byte identifier limit**. Only Oracle Database **12.2+** (e.g. the **19c** development instances) raises the limit to 128 bytes — so a 31-char name **compiles and installs fine on 19c dev and then fails on the customer**. Same 19c-masks-it trap as the `create_update_person_extra_info` note in `upload-api-patterns` skill, generalised to **all** identifiers:
    - **DDL objects** (tables, **indexes**, constraints, sequences, columns, views, triggers, types, synonyms) → over-30 raises **`ORA-00972: identifier is too long`** at create time and the object is **silently not created** (installers tolerate the error and continue), so a missing unique index/constraint can also let bad data in.
    - **PL/SQL identifiers** (package names, and **procedure/function names inside a package spec**, standalone procedures/functions, parameter names) → over-30 raises **`PLS-00114: identifier too long`** (and cascades as `PLS-00201`/`PLS-00307` at call sites). An upload procedure's parameter name over 30 bytes fails on 19c too: the import stores it truncated in the upload parameters, so every upload of the generated block fails with `PLS-00306: wrong number or types of arguments in call to '<procedure>'`.
    - **The generated upload view name** `xxen_<prefix>_<hash>_u` is bounded (prefix truncated to 18 + 4-char hash), so it is safe — but any *hand-named* view/table you add is not.
    - **A report or upload SQL COLUMN ALIAS is an identifier too** — an over-30 alias raises the same `ORA-00972` when the report SQL is parsed, so the report fails for every customer on a pre-12.2 database while running fine on the 19c dev instances. Abbreviate the alias, not the entity prefix, following the existing content (`postal_code` -> `post_code`); the column heading is derived from the alias, so the rename is user-visible and must be carried into every template `COLUMN_NAME` and the matching workbook `cacheField name`. Check with `lengthb(column_name)>30` against `xxen_report_sql_columns` after parsing (exclude the `xxen_util.dff_columns` output, whose names come from the site's own flexfield segments).
    - **Enforced mechanically:** `${CLAUDE_PLUGIN_ROOT}/scripts/lint_plsql.py` rule R55 flags any over-30 procedure/function name or DDL object name (pre-commit hook and `--all`) — a 32-byte procedure name once passed every 19c dev compile and broke the package on a customer's 12.1.0.2 database.

56. **Never parse SQL text with a greedy `.+` regex under the `n` flag — scan it left to right instead.** `regexp_substr` patterns chaining several unbounded `.+` over a whole statement (dot matches newline under `'n'`) backtrack combinatorially AND pick the wrong text: `.+` latches onto the LAST `id`/`value` alias anywhere in the statement (scalar subqueries, inline views, later `union all` branches), whereas Oracle names result columns from the FIRST select. `xxen_api.value_equal_to_id` is the reference scanner.
    - Symptom: pure CPU inside the regex engine — ASH shows `ON CPU` against whatever SQL called it and no slow SQL is findable; read the ASH `Procedure`/`Code` column instead of hunting for a statement.
    - Scanner shape: strip comments preserving literals; track string literals, quoted identifiers and bracket depth; split the select list on depth-0 commas up to the depth-0 `from`; take the trailing identifier as the alias (`as` optional, a bare/qualified column is named after itself, `"Quoted"` honoured); descend into the inline view or `with` block for `select x.* from (..) x`. Bracket depth is what keeps a scalar subquery's inner `from` from ending the select list.
    - PL/SQL `trim`/`rtrim`/`ltrim` strip only SPACES, not newlines or tabs: trim with an explicit set, `ltrim(rtrim(s,g_ws),g_ws)` where `g_ws:=' '||chr(9)||chr(10)||chr(13)||chr(12)`.
    - Package-body constants must precede every subprogram body (`PLS-00103` otherwise).
    - If a regex must stay, gate it behind a cheap linear `regexp_instr` for a literal token it requires (a non-matching regex still pays full backtracking), and `\s` is NOT whitespace inside a bracket expression — Oracle follows POSIX, so `[\s.]` matches backslash, `s` and dot; use `[[:space:].]`.
    - Validate a parser against the whole LOV population AND synthetic cases (id-last select lists), comparing captured groups, not just the boolean result.

57. **Prefer `in (subquery)` over `exists (correlated subquery)` for a plain membership test** — it is shorter, needs no correlation predicate and no `select null`, and reads as what it is. Same minimalism principle as #37.
    ```sql
    -- Bad (correlated, longer, repeats the join column on both sides):
    exists (select null from fnd_conc_pp_actions fcpa where fcr.request_id=fcpa.concurrent_request_id and fcpa.action_type=7)
    -- Good:
    fcr.request_id in (select fcpa.concurrent_request_id from fnd_conc_pp_actions fcpa where fcpa.action_type=7)
    ```
    Keep `exists` only where `in` cannot express the test: a **multi-column** correlation that is not a simple `(a,b) in (...)`, a **`not exists`** anti-join where the subquery column is nullable (`not in` returns no rows when the subquery yields a single null — see #43), or a correlation on something other than equality. Both forms give the same plan for a simple membership test, so the choice is readability, not performance.
    Note this is about a **membership predicate**, not about replacing a join: where the row must be filtered but not multiplied, a subquery (either form) is still required — a join fans the driving row out once per matching child row.

60. **A predicate on an OUTER-JOINED table written without `(+)` silently DROPS the driving row — it does not "keep the row and null the column".** With `(+)` syntax only predicates carrying `(+)` are join conditions; everything else is a post-join filter. `a.id=b.id(+) and <filter on b without (+)>` therefore behaves like an inner join whenever the driving row HAS matches: rows failing the filter are removed and Oracle does not re-null-extend the driving row, so a driving row disappears when ALL its matched rows fail. Rows with NO match still pass (`null` satisfies `nvl(col,x)=x`), which is exactly what hides the bug in testing — it only bites the entities that have child rows.
    - The shape to watch for is an `nvl(<outer table>.<col>,<sentinel>)=<sentinel>` "parent-level child row" filter. It must carry the `(+)` inside the `nvl`:
      ```sql
      -- Bad: an account whose receipt methods are ALL site-level loses its account row completely
      hca.cust_account_id=rcrm.customer_id(+) and
      nvl(rcrm.site_use_id,0)=0 and
      -- Good: stays a join condition, non-matching rows are null-extended
      hca.cust_account_id=rcrm.customer_id(+) and
      nvl(rcrm.site_use_id(+),0)=0 and
      ```
    - Audit rule: in any `from` list with old-style outer joins, every predicate naming an outer-joined alias must either carry `(+)` or be a deliberate "matched rows only" filter you can justify; sibling child tables joined the same way (profiles / contacts / bank accounts / receipt methods) must all be written the same — an odd one out missing the `(+)` is a typo. Verify by counting parents with vs without children before and after.
    - The remedy is not always `(+)`: a filter on the outer-joined table's OWN column (e.g. `nvl(rcrm.primary_flag,'Y')=decode(:p,'Y',nvl(rcrm.primary_flag,'Y'),'Y')`) belongs in an inline view applied BEFORE the join — `(select /*+ inline */ ... from ra_cust_receipt_methods rcrm where rcrm.primary_flag=decode(:p,'Y',rcrm.primary_flag,'Y')) rcrm` — so non-primary rows never enter the join. Audit heuristic: a predicate line that names an outer-joined alias and contains no `(+)` token at all is a filter, not a join condition.
    - When backporting such a fix to a customer's older build, check which UNION branch that customer's PARAMETERS actually execute (e.g. `Update Level = Site` never runs the account branch); the request log's `Parameters and binds` section prints the deployed SQL, so confirm the predicates there rather than inferring them. `ra_cust_receipt_methods` has no `org_id` (keyed on `customer_id` + `site_use_id` only), so a site use in ANY operating unit can match.
    - Related to #23 (join flow) and #50 (no guard that cannot fire): this is the opposite failure — a predicate that fires when it must not.

61. **Building a delimited list: derive the separator from the POSITION, never from the accumulator being non-null.** `l_list:=l_list||case when l_list is not null then '|' end||<value>` is only correct when `<value>` can never be null: a null FIRST element leaves the accumulator null, the second element is appended with no separator, and the list comes back one element short — every positional consumer is then off by one (a null element in the middle is harmless). Fix: `case when c.column_number>1 then '|' end` (or a counter) — identical for a non-null first element, so a safe drop-in. The API output's column-data-type row in `XXEN_REPORT.pkb` is built this way for exactly this reason (a number column with no registered format has a NULL `c.format`); its sibling accumulators (`l_api_column_headers`, `l_column_width`) are safe only because their values cannot be null — do not "fix" them (#50).

62. **Never put an XMLTABLE-based subquery inside a set-based DML predicate against a real table — the optimizer re-shreds the XML once per row of the target table.** An `in`/`exists` subquery reading `xmltable(... passing <clob/xmltype> ...)` gets unnested into a semi-join; because the optimizer has no cardinality for XMLTABLE (8168 rows by default, cubed across a three-level shred) it drives from the real table and pushes the predicate into the subquery view, so the entire shred re-executes for every target row. The statement looks set-based and its cost is `target_rows × cost_of_one_full_shred`.
    - Symptom: a `VIEW PUSHED PREDICATE VW_NSO_*` (or a `FILTER`) whose subtree contains `XMLTABLE EVALUATION`, on the inner side of a `NESTED LOOPS SEMI` whose outer side scans the DML target; wildly inflated E-Rows for a tiny XML is the tell.
    - Fix: drive a cursor loop from the XML ALONE (no table in the cursor) so it is shredded exactly once, and make the DML body a per-iteration statement keyed on an indexed column (one iteration per entity in the XML, so the loop is not the cost). `import_templates`' template parameter exclusion insert in `XXEN_REPORT.pkb` is the reference. Cost scales with the target table AND the xml, so a batch import or a bigger customer is far worse than the dev measurement — same family as #58.
    - A plain JOIN of xmltables to a table has the same trap: with a nested-loop order driven by the table, the xmltables are re-evaluated per table row (a 34 MB batch file: 0.8 s xml-first, over 10 minutes parameters-first). The dev instances pick the xml-first hash plan, so only a customer shows it. Pin every such statement with `leading(<xml aliases>)`, as `import_templates` does.
    - Testing caveat for xml round trips: `xxen_api.import_xml(<clob>)` does NOT strip CRs, while the real file path (`bin/import_xml` → FNDGFU → `xxen_report_ebs.import_xml_file_name` → `import_xml_file`) does, and `export_file_data` converts every `chr(10)` to `chr(13)||chr(10)` on the way out — feeding an `export_report` clob straight back into `import_xml` adds one `chr(13)` per line on each round trip. Round-trip tests go through a file and `bin/import_xml`.

65. **`decode(x,0,null,x)` returns VARCHAR2, not NUMBER — use `nullif(x,0)`.** Oracle types `decode` from its FIRST result, and a null first result converts the return value to varchar2, so the "blank out a zero" idiom silently turns a number column into text: the report column parses as `varchar2`, Excel writes it as a string, and the user cannot sum or chart it. `nullif(x,0)` is the exact equivalent (both treat NULL input as NULL) and keeps the native type.
    - Do NOT "fix" it with `to_number(decode(...))` — that round-trips number → varchar2 → number and is NLS-dependent. `nullif` is also shorter: `decode(a-b-c,0,null,a-b-c)` → `nullif(a-b-c,0)`.
    - The type leak compounds in an aggregate: `max(decode(x,0,null,x))` is a STRING max (`'9' > '10'`); `sum()` still works via implicit conversion but is NLS-dependent.
    - Detect with `regexp_like(sql_text,'decode\(([A-Za-z0-9_.-]+),0,null,\1\)')`.
    - Verify the swap by re-parsing, not by reading the diff: the affected columns must flip `varchar2` → `number` in `xxen_report_sql_columns` (the flip itself proves every operand was numeric), and the Excel output must write them as numeric cells (no `t="s"`). Identical on 11.2, so no ` 11i` twin is needed.

66. **`xxen_util.clob_replace` loops until nothing matches — never call it when the replacement contains the search text.** It repeats `replace_first_occurrence` while `dbms_lob.instr(result,search)>0`, so an insertion that keeps the searched text inside it (`<anchor>` → `<predicate> and <anchor>`) re-matches its own output and grows the CLOB until temp space is gone; the session shows one UPDATE on `write complete waits` with lob reads in the millions. For a single insertion use `xxen_util.replace_first_occurrence` after proving the text occurs once; `clob_replace` is for replacements that remove or transform the searched text. The trap is data-dependent (only when the character before the anchor makes the search re-match), so a script that passed hundreds of reports can still hang on one — same family as #56 (parsers validated on the whole population).

67. **A PL/SQL function inside a subquery's range or filter predicate is evaluated once per CANDIDATE ROW, not once per subquery execution — wrap it in `(select f(...) from dual)`.** The optimizer cannot prove a non-`deterministic` function is invariant, so a bound such as `between col and mrp_calendar.date_offset(outer.a,outer.b,outer.c,1)-1` lands in the table-access filter and runs for every row the index range returns, although its arguments are constant for that execution. The scalar-subquery form evaluates it once and caches it, for identical output.
    - The call count is the KEY RANGE's row count, not the result's, whenever the bound column is missing from the index (`mrp_forecast_updates.forecast_update_date` is not in `MRP_FORECAST_UPDATES_N1`): every row of the key is fetched and filtered.
    - Signature: ASH shows the top-level statement `ON CPU` with no `sql_plan_line_id` and there is no slow SQL to find; the cost sits in `v$sql` as a recursive cursor belonging to the called package with executions in the hundreds of thousands. Read those recursive cursors' `executions`, not the plan.
    - Do NOT add `deterministic` to someone else's function to get the same effect; and when counting the saving, remember a `select count(*)` wrapper discards the select list, so it measures neither the scalar subqueries nor their function calls.

68. **Never guess whether an input is an id or a display value - a routine is told which one it receives.** Trying `to_number(p_x)` as an id and falling back to a lookup by code, testing `regexp_like(p_x,'^[0-9]+$')`, or accepting `'Y'` and the translated `Yes` alike all misfire as soon as a code or name is numeric: a department code `5101` is taken as department id 5101. Numeric codes are common at customers (departments, lines, organizations, segment values, document numbers), while Vision data is mostly alphabetic, so such code passes every internal test.
    - Give each routine one input form. When the callers hold different forms, convert in the caller (an upload's server-side backstop resolves its ids to the display values the add-in sends, as `upload_std_op` does before calling `validate_std_op_excel_row`).
    - A reusable routine that must accept both takes an explicit indicator of what is passed (`'id'` or `'value'`, as `validate_val`'s `p_bind_column` in `XXEN_REPORT`) and never infers it from the content.
    - The rule is about inputs that are processed or validated. A display column may fall back to the raw code when no translation exists (`nvl(xxen_util.meaning(code,...),code)`): showing the code is better than a blank.

69. **Never give a `result_cache` function a high-cardinality key (code combination, segment value, row id) or have it read a table that transactions change; cache such results per session in a package collection, as Oracle's flex engine does for value security (`fnd_plsql_cache` in `FND_FLEX_SERVER`).** Each result takes at least one 1 KB block of the instance-wide cache, a committed DML on any table the function reads invalidates every result of the function (a new `gl_code_combinations` row flushes all cached code combination results), and once the cache is full every new result scans the LRU chain under the `Result Cache: RC Latch`, which makes a full cache far slower than no cache. Keep `result_cache` for small, stable key spaces such as setup lookups. Store a session cache entry only after its evaluation succeeds: a default stored first stays cached when the evaluation raises, and for security that means access granted.
    - Signature: ASH on the report or LOV SQL dominated by `latch free` (P2 = the `Result Cache: RC Latch` number in `v$latchname`) and `enq: RC - Result Cache: Contention`, or by CPU in the calling PL/SQL frame; `DBA Result Cache Statistics` shows Current Size equal to Maximum Size with `Delete Count Valid` rising as fast as `Create Count Success`; `DBA Result Cache Objects and Dependencies` lists the function with hundreds of thousands of results.

70. **Test a code for the value you mean, not for the absence of another: `security_enabled_flag='N'`, not `security_enabled_flag<>'Y'`.** When a column's values are known (a `Y`/`N` flag, an `I`/`E` indicator, a value set validation type), compare with the value the condition is about (`include_exclude_indicator='E'`, `validation_type in ('D','Y','F')`) instead of negating the other one: it reads directly, and both forms exclude null, so they are equivalent whenever the listed values are all the column holds. Keep `<>`/`not in` for open-ended values; for an Enginatics `Y`-or-null flag (#41) the other value is `is null`.
