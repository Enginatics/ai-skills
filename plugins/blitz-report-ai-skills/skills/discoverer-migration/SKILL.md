---
name: discoverer-migration
description: Reviewing and finishing Oracle Discoverer workbooks converted to Blitz Reports. Use when working on Discoverer-converted reports.
user-invocable: false
---

# Discoverer → Blitz Report Migration (product reference)

## Pipeline

1. **Export** (`DIS Workbook Export Script` report) generates `dis51adm.exe /export ... /xmlworkbook` commands per workbook (`if not exist` re-run safety, `ping` stagger). Set `Executable Path`, `DB Service Name`, EUL + password. `Ignore Access History`/`Workbook Id` list workbooks without statistics. By default the list holds only workbooks whose name and owner appear in `eul5_qpp_stats`, so never-run workbooks, recently created ones and those whose runs are recorded under another owner or a same-named copy are missing; when the customer chooses the scope from their own inventory, export with `Ignore Access History=Yes` and `Not yet imported only=Yes`, and repeat that before each conversion round to pick up new workbooks. Run the export commands with `NLS_LANG=AMERICAN_AMERICA.AL32UTF8` set in the command window: `dis51adm` converts through its Oracle home's client character set (`WE8MSWIN1252` by default) and writes every character outside it as `¿` into the `.eex`, so Chinese or other non-Western prompts and condition values arrive as `¿` and a hardcoded condition such as `'ORDER TYPE ¿¿'` silently matches nothing. Run one command alone before the bulk run: when the owner of an Applications EUL lacks any grant of `grant_eul_privileges.sql` (one missing SELECT on `APPS.FND_USER_RESP_GROUPS` is enough), `dis51adm` does not exit but waits on the warning `You have connected to an Applications EUL, but the required Applications tables cannot be found` and leaves a 0-byte `.eex`, so every process of the bulk run hangs. `Discoverer Administrator cannot be launched as the environment variables TEMP and TMP either do not exist, or point to directories that are not accessible`, together with C++ runtime and OLE library errors, means too many processes were started at once (one laptop failed at about 350), not a TEMP problem: those processes never connect and create no `.eex`, so close them and re-run the commands in smaller batches.
2. **Upload** (`Setup>Tools>Import>XML Upload`, Win10-style zip — `fix-zip-compatibility` skill) → `xxen_discoverer_workbook_xmls` keyed (eul, doc_id), EUL from profile `XXEN_REPORT_DISCOVERER_DEFAULT_EUL` (set it BEFORE upload when >1 EUL). Workbooks whose owner is unknown on the target are rejected. An already staged (eul, doc_id) is skipped on a second upload (`ignore_row_on_dupkey_index`, reported as already existing), so a corrected re-export replaces nothing until the staged row is removed.
3. **Select** (`DIS Workbook Conversion Selection` upload, `XXEN_DIS_UPLOAD`) → `convert_flag` NULL / `Y` selected / `C` converted; `Submit Import=Yes` submits and waits for the import and reports per workbook; `Report Name Prefix` param.
4. **Import** (`Blitz Report Discoverer Import` = `xxen_xdo.import_discoverer_folders_cp`; params End User Layer, Report Name Prefix, Object Use Key (`;`-list), Existing Reports (table value set `XXEN_DISCOVERER_EXISTING_REPORTS` over a `union all` from `dual`, codes `UPDATE`/`SKIP`/`REPLACE`; Skip is offered only without an Object Use Key and Delete and Recreate only with one, through `:$FLEX$.XXEN_DISCOVERER_OBJECT_USE_KEY:NULL`; folder sets without a report are always imported)).
5. **Validate** with the Blitz validation reports (Parameter Uniqueness, LOV SQL, SQL, Bind Variable, Table Alias, `DIS Migration identify missing EulConditions`, `DIS Workbook Import Validation`) and the `discoverer_*_fix.sql` scripts (static date defaults, `All`/`%` sentinels, output file name token, pivot/having, range parameter order) after every round.

### Profiles

| Profile | Purpose | Default |
|---|---|---|
| `XXEN_REPORT_DISCOVERER_DEFAULT_EUL` ("Blitz Report Discoverer Default EUL") | EUL that the **XML Upload tags** all uploaded `.eex` with, via `xxen_util.dis_default_eul`. **Set this before upload if there is more than one EUL.** | — |
| `XXEN_REPORT_DISCOVERER_IMPORT_LOV_ACCESS_HISTORY_DAYS` | look-back window for the export script's "recently used" default (`Accessed After`). The import no longer reads it — see the stats-free section below | 600 days |
| `XXEN_REPORT_DISCOVERER_IMPORT_REPORT_NAME_PREFIX` | fallback report-name prefix when the conc `Report Name Prefix` param is blank | — |

## Staging tables

**`object_use_key`** = dot-separated list of the Discoverer folder `obj_id`s a worksheet draws from, derived from the flattened `.eex` by `xxen_xdo.sheet_object_use_key`. It is the **grouping key**: one Blitz Report is built per distinct object_use_key. The created report records its identity in the description as `Object IDs: <object_use_key>` + `EUL: <eul>` — this marker drives the "already imported" exclusion, the targeted `Object Use Key` reload, and the delta refresh's report lookup. It is NOT stored in a column, so re-deriving it is the only way to find an existing report for a folder set.

---

## Condition handling — and the "hardcoded conditions ≠ defaulted parameters" rule

| Condition kind | Example | `complex_condition` | Default import result |
|---|---|---|---|
| Parameter-driven | `item = :MyParam` | N (parameter_value not null) | **visible** parameter — the genuine prompt |
| Hardcoded, simple operator | `status = 'ACTIVE'`, `dept in (…)`, `name like 'X%'` | N (literal, simple op, no calc) | **visible** parameter (e.g. `Status`) **pre-filled with the literal**; SQL rewritten to `status=:status` |
| Hardcoded, complex / no literal | calc-based, `between`, `is null` | Y | **hidden** Yes-toggle (negative display_seq), default `Y`, full condition baked into SQL via `2=2` |

## Purge per EUL

Per-EUL purge (from the report description) — deletes the 5 staging tables for `l_eul`, then all `Discoverer`-category reports + their orphaned (all-uppercase-description) LOVs:

```sql
declare l_eul varchar2(30):='eul_us';
begin
  delete xxen_discoverer_workbook_xmls xdwx where xdwx.eul=l_eul;
  delete xxen_discoverer_fnd_user xdfu where xdfu.eul=l_eul;
  delete xxen_discoverer_pivot_fields xdpf where xdpf.eul=l_eul;
  delete xxen_discoverer_sheets xds where xds.eul=l_eul;
  delete xxen_discoverer_workbooks xdw where xdw.eul=l_eul;
  for c in (select xrca.report_id from xxen_report_categories_v xrcv, xxen_report_category_assigns xrca where xrcv.category='Discoverer' and xrcv.category_id=xrca.category_id) loop
    xxen_api.delete_report(c.report_id,'Y');
  end loop;
  for c in (select xrplv.lov_id from xxen_report_parameter_lovs_v xrplv where xrplv.description=upper(xrplv.description) and xrplv.lov_id not in (select xrp.lov_id from xxen_report_parameters xrp where xrp.parameter_type='LOV' and xrp.lov_id is not null)) loop
    xxen_api.delete_lov(c.lov_id);
  end loop;
  commit;
end;
```

For a single folder set, prefer the conc program's **Object Use Key** parameter (deletes+recreates just that report) over a full purge.

## Phase D — Post-import validation (the real cleanup)

Run these after import (from the export script description); each catches a class of Discoverer-ism that doesn't translate cleanly:

| Report | Catches |
|---|---|
| `Blitz Report Parameter Uniqueness Validation` | duplicate parameter names within a report (Discoverer allows dupes; Blitz needs unique) |
| `Blitz Report LOV SQL Validation` | LOVs that error; slow `distinct`-style LOVs to rewrite as fast SQL |
| `Blitz Report SQL Validation` | main SQLs that don't parse |
| `Blitz Report Parameter Bind Variable Validation` | with `Parameters with missing :binds`: parameters that own no bind because another parameter took every bind name in their SQL, so a value entered for them never reaches the SQL |
| `DIS Migration identify missing EulConditions` | Discoverer conditions not carried over |
| `Blitz Report Parameter Table Alias Validation` | alias mismatches |
| `Blitz Reports` (col `required_parameters`) | reports that came in over-required (see C4 step 10) |
| `Blitz Report Parameter Default Values` | defaults containing `partition` (see C4 step 11) |
| `Blitz Report Templates` (desc `Subtotals: Y`) | compact-pivot sheets — retrain users to switch to tabular |
| `DIS Workbook Import Validation` | coverage gaps: which workbooks/worksheets are uploaded, selected, converted, and which lack a migrated report/template |

**`DIS Workbook Import Validation` was reworked to the stats-free methodology:** worksheet spine from the flattened staged xmls (`eul5_documents` FULL-joined to `xxen_discoverer_workbook_xmls`, so both EUL-only and staged-after-deletion workbooks appear), `Object Use Key` derived per sheet via `xxen_xdo.sheet_object_use_key`, `Selected For Conversion`/`Converted` from the flag, report matched by the derived object use key (OUK) marker, template by the `Doc Id:`+`Sheet:` markers; usage statistics OUTER-joined as informational columns bounded by `Accessed after`. The `Include Inactive` parameter (the old `&full` stats join toggle) was removed and `Workbook Owner` retargeted from the stats rows to the workbook owner. A **helper sheet** (`[9,n]`-referenced) shows its folder set's report but no template — the `Not yet imported` filter (`template_name is null`) therefore lists helper sheets too; expected, not a gap. An underivable workbook (foreign-EUL folders) shows uploaded+selected with a blank OUK and nothing matched — exactly the gap the report exists to surface.

- Check that every template can satisfy the report's `required_parameters`: at least one `or` clause whose parameters are all visible or carry a default in that template. The expression is report-wide while Discoverer's mandatory prompts are per worksheet, so a worksheet whose condition did not convert (a subquery on another worksheet, `Set Of Books Name = "Sheet 2"`) keeps its prompts excluded and its template fails every run with `Please enter sufficient parameters` on a run screen showing no parameters. Show the prompts that reproduce the condition (in the Templates window on an existing report: an import cannot remove an exclusion) and write one clause per parameter set the templates use.
- Run `discoverer_conversion_audit.sql` after every conversion round and every correction import, and resolve every row before user testing. It is one read-only select (a read-only account can run it), and each row names the check, report, template and parameter; the numbered bullets below are its checks.
- (check 1) A template has fewer columns than its worksheet displays when the worksheet shows two columns with the same heading, or two same-named items of different folders: the select list keeps one column per item name and the template columns are matched by heading. Add the missing items to the report SQL under numbered aliases and rebuild the template's columns in worksheet order. A worksheet that displays the same item twice, an item the end user layer no longer has, or a calculation on such an item correctly stays short.
- (checks 2-5) An aggregated worksheet condition becomes a hidden parameter on `&template_having_clause` whose template default is the condition. The engine writes that text after `having` on the template's outer query (`select ... from (<report SQL>) x group by ...`), so it may use only `x.<output column>`: an inner table alias raises `ORA-00904`, and each inner expression maps to the output column with the same expression. One template takes one such default, because the engine joins the texts of several parameters on one lexical anchor with no separator (`ORA-00933`); combine them with ` and `. The clause is ignored on a template without an aggregated column. When a prompt with the condition's name already exists, the condition parameter is named `<name>_1` and reaches only the first template, while the other templates' prompt receives the condition's constants as a value list: give every template whose worksheet carries the condition the default.
- `col >= DECODE(:p,' <ALL>',MIN(col),'<ALL>',MIN(col),:p)` (and the `<=`/`MAX` form) is a range filter with an "all" sentinel, not an aggregate test, whenever the template groups by `col`: make it a prompt on the WHERE anchor, `(:p in (' <ALL>','<ALL>') or col>=:p)`. A condition on a group total, such as an amount built from `SUM(...)`, stays one having condition per template, `sum(x.<column>) between nvl(:low,<min>) and nvl(:high,<max>)`, fed by two bind prompts.
- A workbook prompt converts to `item=:bind`. When the worksheet uses it with `>=`, `<=`, `>` or `<` (Low/High, From/To pairs), both prompts get the same SQL and the duplicate clearing deletes one of them: rebuild them as `col>=:low` and `col<=:high`.
- (checks 6, 7) A prompt's template default can be made of the condition's constants instead of the Discoverer parameter's `DefaultValue`, which is usually empty:
  - the fallback of `NVL(col,'0') LIKE :p`, default `0`, which returns only rows where the column is empty;
  - the arguments of a decode, `instr` or lookup call: `<multiple_values>999999999999;NULL;999999999999`, `<multiple_values>,;-1;1;1`, `<multiple_values>YES_NO;Y;0`;
  - the constant of another column in the same condition: `Set Of Books Name = 'X' AND Period Name = :Period Name` opens the period prompt prefilled with `X` and returns no rows;
  - the text `NULL` of a prompt without a default.

  Remove these defaults.
- (check 8) A parameter on a WHERE or lexical anchor with an empty SQL text injects a bare `and`: `ORA-00936`, with the error line showing only `and`. A bind-anchor parameter row has no `<SQL_TEXT>` element, so moving it to a WHERE anchor in an XML needs the element added.
- (check 9) A parameter SQL on a table alias the report SQL does not have fails with `ORA-00904` once the prompt has a value; when every template excludes it, delete it.
- (check 10) `col IN (:p,'X')`, a prompt and a constant in one list, is rewritten to `col=:p,'X'`, which fails with `ORA-00933` whenever the prompt has a value or a default: write `(col=:p or col in ('X'))`.
- A worksheet condition comparing a string constant where a column was meant (`NVL('Third Party Name','0') LIKE :p`) filters nothing in Discoverer either: keep it and tell the customer.
- A case-only duplicate prompt pair (`Enter starting BU number`, `Enter Starting BU number`) is two parameters to the import but one bind in `required_parameters`, which binds by lower-case name; whichever row binds last decides the check. Rename one.
- Each bind belongs to the first parameter in display order that uses it (`xxen_report.bind_map`), so a parameter whose binds all belong to earlier parameters owns none: when it has a value its condition is added with the other parameter's value, empty on its templates, and the run returns no rows (the request log lists it without a `(:bind)`). The import creates such parameters when a worksheet prompt's name already exists with another SQL text (`<name>_1` with the Discoverer bind names) and numbers their binds at the end of the conversion, keeping one text for the prompts of a range. Conversions made before that correction: find them with `Blitz Report Parameter Bind Variable Validation`, `Parameters with missing :binds` = Yes, or the read-only `discoverer_parameter_bind_preview.sql`, and rename their binds with `discoverer_parameter_bind_fix.sql`.

### Post-import DATA fixes — run after EVERY import round

The validation reports above find what does not *parse*. These repair what parses and is still
wrong — so nothing errors and only a human notices. Each takes `PREVIEW` / `APPLY` (no commit) and
lists rather than guesses; **re-run them after every round**, because the conversion keeps emitting
what they repair.

| script | repairs |
|---|---|
| `discoverer_static_date_default_fix.sql` | a **static date defaulted into a Date parameter**. A Discoverer worksheet stores the LAST RUN values, not defaults, so the migrated report opens pinned to one historical window. Dynamic defaults (`sysdate`, `trunc(sysdate,'MM')`, a select, `:$flex$`) are legitimate and kept; `locked` defaults and defaults on an EXCLUDED parameter (`keep (hidden)` -- a converted hardcoded date condition, where the default IS the restriction) are never touched. The converter now writes no visible static date default itself (a hardcoded date is stored canonically on an excluded parameter, a prompted date default is skipped), so the script's remaining targets are older conversions and the AI fallout generator, which does not check the parameter type |
| `discoverer_all_sentinel_fix.sql` | Discoverer word sentinels (`All`/`Yes`/`NULL`): defaults corrupted to `<multiple_values>X;All;X`, and the `decode(:b,'All',<self>,:b)` construct → `(:b='All' or col like :b)` |
| `discoverer_pct_%_fix_sql_texts.sql` | dead `'%'` decodes in parameter SQL, only where `'%'` can no longer reach the bind |
| `discoverer_parameter_bind_fix.sql` | parameters that own no bind because another parameter took every bind name in their SQL, on reports converted before the converter numbered them itself: renames their binds to `<bind>_<first display sequence>`, shared by the parameters with the same SQL text so a range pair stays one condition; more binds than parameters, an upper bound displayed first or a taken name are listed for review. Checks the result with `xxen_report.bind_map` and changes nothing when a check fails. Read-only twin `discoverer_parameter_bind_preview.sql` rebuilds the bind assignment in plain SQL for a read-only account |
| `discoverer_pct_%_wildcard_fix.sql` | `'%'` wildcard defaults (always-true predicate → wide-open scan) + the stranded `required='Y'` |
| `discoverer_output_file_name_fix.sql` | the underscore token `<template_name>` the import writes (see the Gotchas entry on the two spellings) |
| `discoverer_template_pivot_and_having_fix.sql` | a `&template_having_clause` default with **no column aggregation** (a HAVING with nothing aggregated filters nothing → SUM is set on the number columns), and templates over the 40 pivot-ROW-field limit that must fall back to tabular |
| `discoverer_range_parameter_order_fix.sql` | range parameter pairs prompted upper-bound-first on reports converted before the converter's ordering correction — replays the converter's adjacent-pair and grouped-block merges (same range-name reduction, same shared-name guard) on already-converted reports and resequences; needed because a refresh run preserves matched parameters' sequences, so the import-time correction never reaches existing reports. Name-based only — no dependency on the flattened staging tables or the document-order column, so it works on instances gathered before that column existed |

### The parameter ceiling — a report can carry only as many parameters as the concurrent program has formals

`xxen_report_ebs.report_host` passes parameters **positionally** through `XXEN_REPORT`: it numbers
them `row_number() over (order by display_sequence, parameter_id)` over the rows where
`display_sequence is not null` (or the whole same-name group is invisible), and dispatches with a
literal `elsif c.parameter_number=<n> and parameter<n> is not null` chain. **There is no branch past
the last formal, so a parameter beyond it is SILENTLY DROPPED at submit** — the report runs with one
filter not applied. A wrong answer, not an error.

* **A migration hits this because grafting merges parameter sets.** Each Discoverer worksheet
  brings its own prompts onto the shared report, and the count only grows.
* **Hiding does not free a slot.** The test is `display_sequence IS NOT NULL`: a per-template
  `PARAMETER_EXCLUSION` leaves the sequence intact, and a **negative** sequence is not null either.
  Only a row with **no `DISPLAY_SEQUENCE` at all** (a sub-row) is free — and a name whose rows are
  all sub-rows still takes one slot. A template parameter default frees nothing.
* **Remedies:** merge duplicate prompts that mean the same thing; demote a pure anchor-injection
  parameter to a sub-row; or split the report with `discoverer_split_template_to_copy.sql`
  so each copy carries only its own templates' parameters (then re-export the baseline and
  regenerate). Never delete a live parameter to make room — that is destructive and needs a ruling.

## A converted report with MORE THAN 85 PARAMETERS cannot be submitted — consolidate the hidden worksheet-condition toggles into matching-value parameters

**The hard limit:** `bin/XXEN_REPORT.prog` / `xxen_report_ebs.report_host` declare `parameter1..parameter85`, so a report whose parameter count exceeds 85 cannot run at all (heavy Discoverer workbooks reach this — one worksheet condition = one hidden Yes-toggle parameter each). **Only DISPLAY rows count**: the `report_host` argument-mapping cursor filters `display_sequence is not null` (a name's sub-rows are excluded via the `min(display_sequence) over (partition by parameter_name)` test) — so **matching-value sub-rows sharing one parameter name consume NO argument slot**, which is what makes consolidation possible without touching the run screen.

**The recipe** (worked example: a report with 93 parameters and 150 templates, reduced to 71 parameters): the conversion's hidden Yes-toggle condition parameters (negative `display_sequence`, shared Yes LOV, literal bind-free SQL_TEXT, activated ONLY by a per-template default `'Y'`, never excluded by any template) merge into a few hidden **matching-value** parameters:
- One merged parameter `Template Condition <n>` per group: primary row carries `DISPLAY_SEQUENCE` (negative), `LOV custom` listing the codes (`select '<CODE>' value, '<original condition name>' description from dual union all …`), not free text; each condition becomes a row with `MATCHING_VALUE=<code>` + its original SQL_TEXT; each template's default row changes from `(toggle,'Y')` to `(merged param, <code>)`.
- **Grouping constraint: two conditions defaulted by the SAME template must land in DIFFERENT merged parameters** (one parameter holds one value). Build the co-occurrence conflict graph over the template defaults and color it — the max co-occurrence dictates the merged-parameter count (e.g. max 3 co-occurring conditions → 3 parameters absorb 24 conditions).
- **When the max co-occurrence is too high for coloring, use ONE merged parameter with one code per DISTINCT per-template condition SET instead** — each matching row's SQL_TEXT is that set's member conditions each wrapped in parentheses and AND-joined. Worked example: a report (98 → 75 parameters) had a template defaulting 8 conditions at once (per-condition coloring would only reach 82), but only 20 distinct condition sets across 174 templates → one parameter, 20 matching rows, each template defaults its set code. The trade-off is SQL duplication across combo rows (a condition edited later must be edited in every set containing it) — acceptable because these are frozen Discoverer worksheet conditions, and it is actually truer to the original (one code = one worksheet's condition set).
- **A toggle defaulted by NO template is dead** (hidden + no report default = never injects) — delete it outright.
- Template defaults resolve by NAME to the **display row only** (import join `xrp.display_sequence is not null`), so the sub-rows can never receive a default. Exclusions were never written for the toggles by the conversion, so no exclusion rewiring is needed — and the visible parameters (with their thousands of per-template exclusion rows) stay byte-identical.
- **Import-on-top is safe** when kept rows keep their exact `SORT_ORDER` (the upsert key) and the new merged rows use fresh sort orders past the old max; the removed toggles' rows are seeded and get deleted by the parameter sync, cascading their old default rows.

**Verify three ways:** (a) offline — per template, the set of injected condition SQLs before vs after must be identical; (b) post-import DB — display-param count, defaults land on exactly the merged display rows, no dangling exclusion/default rows; (c) runtime — `xxen_report.initialize_parameter_values(report_id, null, template_id)` puts the CODE into the tmp values, `xxen_api.create_run_id` harvests it, and the executed SQL (v$sql) contains exactly the defaulted conditions and none of the sibling matching rows. A missing customer view is stood in per the established stand-in pattern (typed null columns from the referenced-column list), then dropped. **When asserting injection via v$sql, filter on `length(sql_fulltext)` and probe `sql_fulltext` with `dbms_lob.instr`** — a bare `sql_text like '%<literal>%'` check matches your OWN monitoring query (self-observation), and `sql_text` holds only the first 1000 chars, so the real run cursor (whose FROM clause sits ~75k chars in) is missed while the false self-match "passes".

## Converter design (statistics-independent)

- One Blitz Report per object_use_key; worksheets become templates (`template_name` = `Workbook[: Sheet]`, `Doc Id:`/`Sheet:` markers). Category `Discoverer`. Anchor `2=2`.
- Update (`Existing Reports=UPDATE`): builds a new report and transplants it (`refresh_report`); parameters matched by normalised `sql_text` (else anchor), unmatched target parameters kept; templates matched by worksheet name, hand-made ones untouched; template defaults/exclusions inserted only where absent. Always reconciles parameters (no report-only option). Old stats-path `Object IDs:` markers may not match derived keys — compare before re-running.
- Post-import corrections done by the converter: duplicate names (`lower(trim())` comparison + `unique_parameter_name`), range-pair ordering (adjacent and grouped merges keyed on the direction-word-stripped range name), prompt order from `.eex` document order (`display_sequence` captured at flatten), `%` defaults dropped, degenerate/oversized (>40 row fields) pivots removed, operator suffixes in names (`from`/`to` unbracketed, others `(equals)` etc.), `ORA-00936` items skipped. No post-build parse (use `Blitz Report SQL Validation`).
- Hardcoded conditions (`parameter_value` null, `complex_condition='N'`) become per-template EXCLUDED parameters carrying a template default that the engine still applies (`initialize_parameter_values` change); dates stored canonical `YYYY/MM/DD`; prompted date defaults are skipped (last-run values). Identification is by origin only — name/operator heuristics over-matched twice.
- Two conditions that give the same parameter SQL (`col=:a` from one worksheet, `col=:b` from another) become one parameter, and the value of the one removed moves to the kept parameter for its template (hidden, unless the kept parameter is a prompt of that template; two exclusion lists on one column in one template are merged). Reports converted before this lost those hardcoded conditions: the template shows the kept parameter as an empty prompt and returns more rows than the worksheet. Find them by exclusion rows whose parameter no longer exists (`xxen_report_templ_excl_params.parameter_id not in (select parameter_id from xxen_report_parameters)`), and restore each value from the worksheet's condition in `xxen_discoverer_sheets`/`xxen_discoverer_workbooks` (a condition's `case_sensitive` null means the kept parameter is the `upper(col)` one; Discoverer function `[1,86]` is `>=`, `[1,85]` is `<=`, and a date literal carries its format after the value).
- A case-insensitive condition (`case_sensitive` null) on text converts to `upper(col)<op>upper(:bind)`, as Discoverer compares `UPPER(col)=UPPER('value')`; the engine expands that form for multiple values (`upper(col) in (select upper(...))`). Reports converted before compare `upper(col)` with the value as written, so a value with lower-case letters matches nothing (no rows for `=`, no exclusion for `<>`). Find them with `regexp_like(sql_text,'^\s*upper\(.+\)\s*(=|<>|>=|<=|>|<)\s*:\w+\s*$')` and wrap the bind in `upper()`.
- Reports over 85 parameters cannot be submitted (`report_host` formals; hidden and negative sequences still count): consolidate hidden condition toggles into matching-value parameters (one per co-occurrence colour, or one code per distinct condition set); verify via v$sql `sql_fulltext`.
- Date hierarchy items call `EUL_DATE_TRUNC(<date>,'<display mask>')`, and Oracle `trunc` accepts only a single format element, so the converter truncates to the finest element of the mask (`mm/dd/yyyy` to the day, `Mon-YYYY` to the month, `"Q"Q-YYYY` to the quarter; a mask without a year keeps the 1900 constant-year form). A mask passed to `trunc` unchanged parses, so `Blitz Report SQL Validation` and `Blitz Report LOV SQL Validation` report it valid, and the report fails at run time with `ORA-01898`, `ORA-01821` or `ORA-01899` as soon as a row has a date: re-convert such a report on a current build, or replace the `trunc(<date>,'<mask>')` in its SQL, parameters and LOVs by hand.
- A day-level date filter on Date parameters is written as a range on the date column, so an index on the column can be used: `trunc(col) between :from and :to` becomes `(col>=:from and col<:to+1)`, `trunc(col)>=:from` becomes `col>=:from`, `trunc(col)<=:to` becomes `col<:to+1`. It selects the same rows because a Date parameter's value carries no time. A bind that also belongs to a parameter of another type (a Char parameter holding a date) keeps its `trunc`, since `:to+1` fails on text. A refresh (`Existing Reports=UPDATE`) compares both forms as equal, so a report holding the `trunc` form is matched rather than given a second parameter. To bring existing reports to this form, rewrite their parameter SQL in an export of the category, together with any multi-element date formats, and import it.
- A calculation that references an item no longer in the end user layer is skipped like any other unconvertible expression (`Column "<name>" skipped` in the import log), as Discoverer itself can no longer run it.
- Never render the literal token `[5,1,"NULL"]` as `null`: Discoverer itself generates it as the string `'NULL'` (its saved worksheet SQL in `ams_discoverer_sql` shows `TO_NUMBER(DECODE(...,'NULL'))`, `ELSE 'NULL'`, `NVL(x,'NULL') IN (...,'NULL')`), and `xml_expression_to_rpn`/`dis_formula` already reproduce that. The NULL keyword is a different token, the function `[1,115]()`, rendered `null`. A quoted `'NULL'` in a numeric position therefore raises `ORA-01722` in Discoverer too — a latent error in the source worksheet, fixed per report, not in the converter.
- The SQL Discoverer generated for a worksheet is in `ams_discoverer_sql` (chunks by `sequence_order`, assembled by `xxen_util.dis_worksheet_sql`), written by the EUL function `eul_trigger$post_save_document` on every save; `workbook_owner_name` is the EUL user name (`#<user_id>`) and there is no doc id. Use it to settle what Discoverer did with an expression before changing the converter.
- `Query@IsDistinct` → `distinct_flag` → `select distinct` wrap, which collapses identical detail rows; a Discoverer output showing duplicates ran without the flag.
- A `<multiple_values>` parameter on a converted report over a complex customer view (a DISTINCT view with per-row lookups or scalar subqueries) runs the view UNFILTERED. The engine rewrites `col=:bind` to `col in (select dbms_lob.substr(xrrpv.value) ... from xxen_report_run_param_values xrrpv ...)`; a subquery predicate is not pushed into the view the way Discoverer's literal `in ('…')` is — Oracle unnests it to a semi-join ABOVE the view, so the view executes for every row before the item list applies. On 12c+ the CLOB reference is what excludes the subquery from complex view merging (a `merge` hint cannot force it; the identical subquery over a varchar2 column merges); on 11.2 neither form merges. Plan signature: the `VIEW` as the outer side of a `NESTED LOOPS SEMI` probing `XXEN_REPORT_RUN_PARAM_VALUES` last, with a normal-looking cost. Single-value runs are unaffected (`=:bind` pushes like a literal) and are the immediate workaround; `push_pred` on the view is refused (not legal into a DISTINCT view). Per-report fix: a hidden same-name sub-row on an `&item_filter` lexical anchor whose SQL_TEXT reads the run's values from `xxen_report_run_param_values` by `:run_id` (always bound in `dynamic_sql_text`) and parameter name, splits them with `xxen_util.rowgen` into a quote-escaped literal `in` list, capped (`case when count(*) between 1 and 200`) so oversize selections fall back to the bind subquery; the visible parameter and its bind predicate stay untouched. Two lexical-evaluation traps: other binds inside a lexical resolve to ONE value even for multi-select (`insert_run_bind_values` keeps `min keep dense_rank first` per bind — never reference the parameter's own bind), and lexicals evaluate BEFORE `build_sql` expands the stored `<multiple_values>a;b;c` row into N rows, so the lexical must handle both storage forms. Engine-level literal inlining is the general fix (product decision pending). Never test view mergeability with a `no_merge` harness (it suppresses the transformation in question) and never extrapolate merge behaviour across database versions.
- "Columns missing": diff the Discoverer SQL against `xxen_reports.sql_text`; negative template `display_sequence` = column absent from the SQL; fix the SQL, never the template; `<name>2` suffixed columns select the source column twice.
- Class-A `ORA-00904 "<ALIAS>"."<COL>"` on old-engine reports = orphan FROM folder; re-convert on the current engine.
- Purge per EUL: delete the five staging tables, `delete_report` for `Discoverer` category, orphan LOVs; prefer the Object Use Key parameter for one folder set.

